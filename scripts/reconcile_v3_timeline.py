"""Reconciliation script:
1. Delete duplicate/legacy V3 graph (GSMOperationalV3) in Neo4j.
2. Delete all V2 records from SQLite, Neo4j, and Qdrant.
3. Compute exact snapshot time alignment (visibility_snapshot_ids) for all Trips, Complaints, and Incidents.
4. Connect all trips, complaints, and incidents to their corresponding nodes in GSMOperationalV3Timeline:
   - Driver -> PERFORMED -> Trip
   - Trip -> PICKUP_IN -> Zone
   - Trip -> DROPOFF_IN -> Zone
   - Trip -> IN_REGION -> Region
   - Trip -> FOR_SERVICE -> Service
   - Driver -> RECEIVED_COMPLAINT -> Complaint -> ABOUT_TRIP -> Trip
   - Driver -> HAS_INCIDENT -> Incident -> ABOUT_TRIP -> Trip
5. Audit and verify exact parity between SQLite database and Neo4j graph.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

import requests
import sqlite3
from neo4j import GraphDatabase
from gsm_memory.retrieval.nvidia_embed import NvidiaNemotronEmbedder

SNAPSHOT_TIMELINE = [
    ("a01883a7-d8be-55bb-a561-479a63adf9ee", "2026-08-17T23:59:59.000000Z"),
    ("41d9cbe1-5ddd-5ca5-96ad-1b9c0929480a", "2026-08-18T23:59:59.000000Z"),
    ("32cc841a-0440-5283-80d7-aebb77b935b3", "2026-08-20T23:59:59.000000Z"),
    ("b768a6f4-6b45-5014-a87f-98d013e0ec5a", "2026-08-22T23:59:59.000000Z"),
    ("7ad8774d-08fc-55a6-badb-2447ee6cab53", "2026-08-24T23:59:59.000000Z"),
    ("fd133f31-6db4-5c7c-9791-c1301176dc3f", "2026-08-26T23:59:59.000000Z"),
    ("a6037ae7-4642-55d9-a36a-88fca6875fdf", "2026-08-28T23:59:59.000000Z"),
    ("002366a5-e09e-5214-9fe4-c7fffeaf1396", "2026-08-31T23:59:59.000000Z"),
    ("081a61c0-56dd-5f43-88a4-f4dfb2894412", "2026-09-01T23:59:59.000000Z"),
    ("e64f47d9-1a09-5954-9ac6-a3e9770fa38a", "2026-09-16T12:00:00.000000Z"),
    ("96d00bc2-d39b-592b-b0d8-0ad4a5b80c30", "2026-09-17T12:00:00.000000Z"),
    ("8b1426b6-2fad-5aba-b886-e16de44c18e7", "2026-09-18T03:00:00.000000Z"),
]

# Zone, Region, Service IDs in GSMOperationalV3Timeline
ZONE_HN_1 = "c96ba0d9-e6bb-5c37-b302-35dcf1eafe74"  # Vùng 1 — Hà Nội
ZONE_HN_2 = "ea84c177-cfae-590c-9db8-3a48e8f55029"  # Vùng 2 — Hà Nội
ZONE_HCM_1 = "fdb2dcaa-ef51-58ad-b5fe-8d78b0e2565a" # Vùng 1 — TP.HCM theo địa giới cũ
ZONE_HCM_2 = "c873b451-0861-5554-8f62-4943ccfdf59f" # Vùng 2 — TP.HCM theo địa giới cũ

REGION_HN = "67469644-6dad-58dd-89be-bc415951e696"   # Hà Nội
REGION_HCM = "03d4cda7-cd9e-5d2d-a0b2-e5d023a08a52"  # TP.HCM theo địa giới cũ

SERVICE_GEN = "8dc91ecb-5454-570e-acfd-10b835fef4cf" # Dịch vụ tổng hợp


def get_visibility_snapshots(time_iso: str | None) -> tuple[str, list[str]]:
    """Determine earliest snapshot and all subsequent visible snapshot IDs."""
    if not time_iso:
        return "8b1426b6-2fad-5aba-b886-e16de44c18e7", ["8b1426b6-2fad-5aba-b886-e16de44c18e7"]
    t_str = str(time_iso).strip()
    if not t_str.endswith("Z") and not ("+" in t_str or "-" in t_str[-6:]):
        t_str += ".000000Z"
    visible = []
    for snap_id, snap_time in SNAPSHOT_TIMELINE:
        if snap_time >= t_str:
            visible.append(snap_id)
    if not visible:
        visible = ["8b1426b6-2fad-5aba-b886-e16de44c18e7"]
    return visible[0], visible


def resolve_zone_id(address: str, region: str) -> str:
    addr_lower = (address or "").lower()
    reg_lower = (region or "").lower()
    if "tp.hcm" in addr_lower or "sài gòn" in addr_lower or "hcm" in addr_lower or "tp.hcm" in reg_lower or "hcm" in reg_lower:
        if any(w in addr_lower for w in ["vùng 1", "vung 1", "quận 1", "quận 3", "quận 5", "bến thành", "tân sơn nhất", "bình thạnh", "quận 10", "quận 7"]):
            return ZONE_HCM_1
        return ZONE_HCM_2
    else:
        # Hà Nội: Vùng 1 = Ba Đình, Hoàn Kiếm, Đống Đa, Hai Bà Trưng, Tây Hồ
        if any(w in addr_lower for w in ["vùng 1", "vung 1", "ba đình", "hoàn kiếm", "đống đa", "hai bà trưng", "tây hồ", "hồ gươm", "ga hà nội", "đội cấn", "bạch mai", "bà triệu"]):
            return ZONE_HN_1
        return ZONE_HN_2


def resolve_region_id(address: str, region: str) -> str:
    addr_lower = (address or "").lower()
    reg_lower = (region or "").lower()
    if "tp.hcm" in addr_lower or "sài gòn" in addr_lower or "hcm" in addr_lower or "tp.hcm" in reg_lower or "hcm" in reg_lower:
        return REGION_HCM
    return REGION_HN


def deterministic_uuid(prefix: str, key: str) -> str:
    namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
    return str(uuid.uuid5(namespace, f"{prefix}:{key}"))


def step1_clean_neo4j() -> None:
    """Delete legacy GSMOperationalV3 graph and any v2_ nodes from Neo4j."""
    uri = os.getenv("NEO4J_OPERATIONAL_URI") or os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_OPERATIONAL_USERNAME") or os.getenv("NEO4J_USERNAME")
    pwd = os.getenv("NEO4J_OPERATIONAL_PASSWORD") or os.getenv("NEO4J_PASSWORD")

    print("\n--- STEP 1: Cleaning Neo4j legacy V3 and V2 nodes ---")
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    with driver.session() as s:
        # A. Delete GSMOperationalV3 nodes and relationships
        res_v3 = s.run("MATCH (n:GSMOperationalV3) DETACH DELETE n RETURN count(n) as cnt")
        print(f"  🗑️ Deleted {res_v3.consume().counters.nodes_deleted} legacy GSMOperationalV3 nodes.")

        # B. Delete any nodes starting with v2_
        res_v2 = s.run("MATCH (n) WHERE n.id STARTS WITH 'v2_' DETACH DELETE n RETURN count(n) as cnt")
        print(f"  🗑️ Deleted {res_v2.consume().counters.nodes_deleted} V2 nodes (v2_*).")

    driver.close()
    print("  ✅ Neo4j legacy nodes cleaned.")


def step2_clean_sqlite() -> None:
    """Delete V2 records from SQLite database."""
    print("\n--- STEP 2: Cleaning V2 records from SQLite ---")
    db_path = ROOT_DIR / "data" / "gsm_local.db"
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("DELETE FROM drivers WHERE driver_id LIKE 'v2_%'")
    d_cnt = c.rowcount
    c.execute("DELETE FROM trips WHERE driver_id LIKE 'v2_%' OR trip_id LIKE 'v2_%' OR snapshot_id = 'snapshot-2025-07'")
    t_cnt = c.rowcount
    c.execute("DELETE FROM complaints WHERE driver_id LIKE 'v2_%' OR complaint_id LIKE 'v2_%'")
    comp_cnt = c.rowcount
    c.execute("DELETE FROM incidents WHERE driver_id LIKE 'v2_%' OR incident_id LIKE 'v2_%'")
    inc_cnt = c.rowcount
    c.execute("DELETE FROM snapshots WHERE snapshot_id = 'snapshot-2025-07'")
    snap_cnt = c.rowcount

    conn.commit()
    conn.close()

    print(f"  🗑️ Deleted from SQLite: {d_cnt} drivers, {t_cnt} trips, {comp_cnt} complaints, {inc_cnt} incidents, {snap_cnt} snapshot.")
    print("  ✅ SQLite V2 cleanup completed.")


def step3_clean_qdrant() -> None:
    """Delete V2 points from Qdrant collection."""
    print("\n--- STEP 3: Cleaning V2 points from Qdrant ---")
    qdrant_url = os.getenv("QDRANT_URL", "").rstrip("/")
    qdrant_key = os.getenv("QDRANT_API_KEY", "")
    collection = os.getenv("QDRANT_COLLECTION", "gsm-memory")

    if not qdrant_url:
        print("  ⚠️ QDRANT_URL missing, skipping Qdrant cleanup.")
        return

    headers = {"Content-Type": "application/json"}
    if qdrant_key:
        headers["api-key"] = qdrant_key

    # Query all points to find any with v2_ in node_id or driver_id
    scroll_resp = requests.post(
        f"{qdrant_url}/collections/{collection}/points/scroll",
        headers=headers,
        json={
            "filter": {
                "should": [
                    {"key": "kind", "match": {"value": "complaint"}},
                    {"key": "kind", "match": {"value": "incident"}},
                ]
            },
            "limit": 500,
            "with_payload": True,
        },
    )
    points = scroll_resp.json().get("result", {}).get("points", [])
    v2_point_ids = []
    for p in points:
        pl = p.get("payload", {})
        d_id = str(pl.get("driver_id", ""))
        n_id = str(pl.get("node_id", ""))
        if d_id.startswith("v2_") or n_id.startswith("v2_"):
            v2_point_ids.append(p["id"])

    if v2_point_ids:
        del_resp = requests.post(
            f"{qdrant_url}/collections/{collection}/points/delete",
            headers=headers,
            json={"points": v2_point_ids},
        )
        print(f"  🗑️ Deleted {len(v2_point_ids)} V2 points from Qdrant: {del_resp.status_code}")
    else:
        print("  ✅ No V2 points found in Qdrant.")


def step4_align_time_and_connect_graph() -> dict[str, Any]:
    """Calculate exact visibility_snapshot_ids and connect all nodes in GSMOperationalV3Timeline."""
    print("\n--- STEP 4: Time alignment & full graph connection in GSMOperationalV3Timeline ---")
    seed_json_path = ROOT_DIR / "data" / "v3_timeline_seed.json"
    with open(seed_json_path, "r", encoding="utf-8") as f:
        seed_data = json.load(f)

    db_path = ROOT_DIR / "data" / "gsm_local.db"
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # 1. Align Trips
    trips = seed_data.get("trips", [])
    for t in trips:
        st = t["start_time"]
        early_snap, vis = get_visibility_snapshots(st)
        t["snapshot_id"] = early_snap
        t["visibility_snapshot_ids"] = vis

        # Update SQLite
        c.execute(
            "UPDATE trips SET snapshot_id = ?, visibility_snapshot_ids = ? WHERE trip_id = ?",
            (early_snap, json.dumps(vis), t["trip_id"]),
        )

    # 2. Align Complaints
    complaints = seed_data.get("complaints", [])
    for comp in complaints:
        et = comp.get("event_time")
        if not et:
            et = "2026-08-31T23:59:59.000000Z"
            comp["event_time"] = et
        early_snap, vis = get_visibility_snapshots(et)
        comp["snapshot_id"] = early_snap
        comp["visibility_snapshot_ids"] = vis

        # Update SQLite
        c.execute(
            "UPDATE complaints SET event_time = ?, visibility_snapshot_ids = ? WHERE complaint_id = ?",
            (et, json.dumps(vis), comp["complaint_id"]),
        )

    # 3. Align Incidents
    incidents = seed_data.get("incidents", [])
    for inc in incidents:
        et = inc.get("event_time")
        if not et:
            et = "2026-09-01T23:59:59.000000Z"
            inc["event_time"] = et
        early_snap, vis = get_visibility_snapshots(et)
        inc["snapshot_id"] = early_snap
        inc["visibility_snapshot_ids"] = vis

        # Update SQLite
        c.execute(
            "UPDATE incidents SET event_time = ?, visibility_snapshot_ids = ? WHERE incident_id = ?",
            (et, json.dumps(vis), inc["incident_id"]),
        )

    conn.commit()
    conn.close()

    # Save updated seed JSON
    with open(seed_json_path, "w", encoding="utf-8") as f:
        json.dump(seed_data, f, ensure_ascii=False, indent=2)

    print(f"  ✅ Time aligned for {len(trips)} trips, {len(complaints)} complaints, {len(incidents)} incidents.")

    # 4. Connect Full Graph in Neo4j
    uri = os.getenv("NEO4J_OPERATIONAL_URI") or os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_OPERATIONAL_USERNAME") or os.getenv("NEO4J_USERNAME")
    pwd = os.getenv("NEO4J_OPERATIONAL_PASSWORD") or os.getenv("NEO4J_PASSWORD")

    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    with driver.session() as s:
        print("  🚀 Upserting and connecting Trips in GSMOperationalV3Timeline...")
        # Prepare Trip Payloads
        trip_records = []
        for t in trips:
            reg = t.get("region") or "Hà Nội"
            pu_addr = t.get("pickup") or "Hà Nội"
            do_addr = t.get("dropoff") or "Hà Nội"
            trip_records.append({
                "trip_id": t["trip_id"],
                "driver_id": t["driver_id"],
                "name": f"Chuyến {t['trip_id'][:8]}",
                "start_time": t["start_time"],
                "snapshot_id": t["snapshot_id"],
                "outcome": t["outcome"],
                "reason_code": t.get("reason_code", "unspecified"),
                "pickup": pu_addr,
                "dropoff": do_addr,
                "region": reg,
                "description": t.get("description", ""),
                "visibility_snapshot_ids": t["visibility_snapshot_ids"],
                "pickup_zone_id": resolve_zone_id(pu_addr, reg),
                "dropoff_zone_id": resolve_zone_id(do_addr, reg),
                "region_id": resolve_region_id(pu_addr, reg),
                "service_id": SERVICE_GEN,
            })

        cypher_trips = """
        UNWIND $trips AS t
        MATCH (d:Driver:GSMOperationalV3Timeline {id: t.driver_id})
        MATCH (pz:Zone:GSMOperationalV3Timeline {id: t.pickup_zone_id})
        MATCH (dz:Zone:GSMOperationalV3Timeline {id: t.dropoff_zone_id})
        MATCH (r:Region:GSMOperationalV3Timeline {id: t.region_id})
        MATCH (svc:Service:GSMOperationalV3Timeline {id: t.service_id})
        MERGE (trip:Trip:GSMOperationalV3Timeline {id: t.trip_id})
        SET trip.name = t.name,
            trip.driver_id = t.driver_id,
            trip.start_time = t.start_time,
            trip.event_time = t.start_time,
            trip.snapshot_id = t.snapshot_id,
            trip.outcome = t.outcome,
            trip.reason_code = t.reason_code,
            trip.pickup = t.pickup,
            trip.dropoff = t.dropoff,
            trip.description = t.description,
            trip.visibility_snapshot_ids = t.visibility_snapshot_ids
        MERGE (d)-[rp:PERFORMED]->(trip)
        SET rp.outcome = t.outcome,
            rp.visibility_snapshot_ids = t.visibility_snapshot_ids,
            rp.event_time = t.start_time
        MERGE (trip)-[rpz:PICKUP_IN]->(pz)
        SET rpz.visibility_snapshot_ids = t.visibility_snapshot_ids,
            rpz.event_time = t.start_time
        MERGE (trip)-[rdz:DROPOFF_IN]->(dz)
        SET rdz.visibility_snapshot_ids = t.visibility_snapshot_ids,
            rdz.event_time = t.start_time
        MERGE (trip)-[rr:IN_REGION]->(r)
        SET rr.visibility_snapshot_ids = t.visibility_snapshot_ids,
            rr.event_time = t.start_time
        MERGE (trip)-[rs:FOR_SERVICE]->(svc)
        SET rs.visibility_snapshot_ids = t.visibility_snapshot_ids,
            rs.event_time = t.start_time
        """
        s.run(cypher_trips, trips=trip_records)
        # Ensure each trip has exactly 1 PICKUP_IN and 1 DROPOFF_IN (deduplicate any synthetic conflict)
        s.run("""
            MATCH (t:Trip:GSMOperationalV3Timeline)-[r:PICKUP_IN]->()
            WHERE r.evidence_ref IS NULL AND EXISTS { MATCH (t)-[r2:PICKUP_IN]->() WHERE r2.evidence_ref IS NOT NULL }
            DELETE r
        """)
        s.run("""
            MATCH (t:Trip:GSMOperationalV3Timeline)-[r:DROPOFF_IN]->()
            WHERE r.evidence_ref IS NULL AND EXISTS { MATCH (t)-[r2:DROPOFF_IN]->() WHERE r2.evidence_ref IS NOT NULL }
            DELETE r
        """)
        print(f"     -> Connected {len(trip_records)} Trips to Driver, Zones, Region, Service.")

        print("  🚀 Upserting and connecting Complaints in GSMOperationalV3Timeline...")
        comp_records = []
        for c_item in complaints:
            comp_records.append({
                "complaint_id": c_item["complaint_id"],
                "driver_id": c_item["driver_id"],
                "trip_id": c_item.get("trip_id"),
                "category": c_item.get("category", "general"),
                "event_time": c_item["event_time"],
                "snapshot_id": c_item["snapshot_id"],
                "name": c_item.get("name") or f"Khiếu nại {c_item['complaint_id'][:8]}",
                "description": c_item.get("description", ""),
                "visibility_snapshot_ids": c_item["visibility_snapshot_ids"],
            })

        cypher_comps = """
        UNWIND $comps AS c
        MATCH (d:Driver:GSMOperationalV3Timeline {id: c.driver_id})
        MATCH (t:Trip:GSMOperationalV3Timeline {id: c.trip_id})
        MERGE (comp:Complaint:GSMOperationalV3Timeline {id: c.complaint_id})
        SET comp.name = c.name,
            comp.driver_id = c.driver_id,
            comp.trip_id = c.trip_id,
            comp.category = c.category,
            comp.description = c.description,
            comp.event_time = c.event_time,
            comp.snapshot_id = c.snapshot_id,
            comp.visibility_snapshot_ids = c.visibility_snapshot_ids
        MERGE (d)-[rc:RECEIVED_COMPLAINT]->(comp)
        SET rc.category = c.category,
            rc.visibility_snapshot_ids = c.visibility_snapshot_ids,
            rc.event_time = c.event_time
        MERGE (comp)-[rt:ABOUT_TRIP]->(t)
        SET rt.visibility_snapshot_ids = c.visibility_snapshot_ids,
            rt.event_time = c.event_time
        """
        s.run(cypher_comps, comps=comp_records)
        print(f"     -> Connected {len(comp_records)} Complaints to Driver and Trips.")

        print("  🚀 Upserting and connecting Incidents in GSMOperationalV3Timeline...")
        inc_records = []
        for i_item in incidents:
            inc_records.append({
                "incident_id": i_item["incident_id"],
                "driver_id": i_item.get("driver_id"),
                "trip_id": i_item.get("trip_id"),
                "incident_type": i_item.get("incident_type", "operational"),
                "event_time": i_item.get("event_time"),
                "snapshot_id": i_item["snapshot_id"],
                "name": i_item.get("name") or f"Sự cố {i_item['incident_id'][:8]}",
                "description": i_item.get("description", ""),
                "visibility_snapshot_ids": i_item["visibility_snapshot_ids"],
            })

        cypher_incs = """
        UNWIND $incs AS i
        MATCH (d:Driver:GSMOperationalV3Timeline {id: i.driver_id})
        MERGE (inc:Incident:GSMOperationalV3Timeline {id: i.incident_id})
        SET inc.name = i.name,
            inc.driver_id = i.driver_id,
            inc.trip_id = i.trip_id,
            inc.incident_type = i.incident_type,
            inc.description = i.description,
            inc.event_time = i.event_time,
            inc.snapshot_id = i.snapshot_id,
            inc.visibility_snapshot_ids = i.visibility_snapshot_ids
        MERGE (d)-[ri:HAS_INCIDENT]->(inc)
        SET ri.incident_type = i.incident_type,
            ri.visibility_snapshot_ids = i.visibility_snapshot_ids,
            ri.event_time = i.event_time
        WITH inc, i
        WHERE i.trip_id IS NOT NULL
        MATCH (t:Trip:GSMOperationalV3Timeline {id: i.trip_id})
        MERGE (inc)-[rt:ABOUT_TRIP]->(t)
        SET rt.visibility_snapshot_ids = i.visibility_snapshot_ids,
            rt.event_time = i.event_time
        """
        s.run(cypher_incs, incs=inc_records)
        print(f"     -> Connected {len(inc_records)} Incidents to Driver and Trips.")

    driver.close()
    print("  ✅ Neo4j GSMOperationalV3Timeline graph updated and connected.")

    return {
        "trips": len(trips),
        "complaints": len(complaints),
        "incidents": len(incidents),
    }


def step5_verify_and_reconcile() -> None:
    """Verify exact parity between SQLite, Neo4j, and Qdrant."""
    print("\n" + "="*70)
    print("--- STEP 5: VERIFYING RECONCILIATION & PARITY ---")
    print("="*70)

    # 1. SQLite Counts
    db_path = ROOT_DIR / "data" / "gsm_local.db"
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("SELECT count(*) FROM drivers")
    sqlite_drivers = c.fetchone()[0]
    c.execute("SELECT count(*) FROM trips")
    sqlite_trips = c.fetchone()[0]
    c.execute("SELECT count(*) FROM complaints")
    sqlite_comps = c.fetchone()[0]
    c.execute("SELECT count(*) FROM incidents")
    sqlite_incs = c.fetchone()[0]
    c.execute("SELECT count(*) FROM snapshots WHERE is_baseline = 1")
    sqlite_baseline_snaps = c.fetchone()[0]

    conn.close()

    # 2. Neo4j Counts
    uri = os.getenv("NEO4J_OPERATIONAL_URI") or os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_OPERATIONAL_USERNAME") or os.getenv("NEO4J_USERNAME")
    pwd = os.getenv("NEO4J_OPERATIONAL_PASSWORD") or os.getenv("NEO4J_PASSWORD")
    driver = GraphDatabase.driver(uri, auth=(user, pwd))

    with driver.session() as s:
        # Check GSMOperationalV3 remaining count
        v3_remaining = s.run("MATCH (n:GSMOperationalV3) RETURN count(n) as cnt").single()["cnt"]

        # Counts in GSMOperationalV3Timeline
        neo_drivers = s.run("MATCH (d:Driver:GSMOperationalV3Timeline) RETURN count(d) as cnt").single()["cnt"]
        neo_trips = s.run("MATCH (t:Trip:GSMOperationalV3Timeline) RETURN count(t) as cnt").single()["cnt"]
        neo_comps = s.run("MATCH (c:Complaint:GSMOperationalV3Timeline) RETURN count(c) as cnt").single()["cnt"]
        neo_incs = s.run("MATCH (i:Incident:GSMOperationalV3Timeline) RETURN count(i) as cnt").single()["cnt"]

        # Check relationships counts
        rel_performed = s.run("MATCH ()-[r:PERFORMED]->() RETURN count(r) as cnt").single()["cnt"]
        rel_pickup = s.run("MATCH ()-[r:PICKUP_IN]->() RETURN count(r) as cnt").single()["cnt"]
        rel_dropoff = s.run("MATCH ()-[r:DROPOFF_IN]->() RETURN count(r) as cnt").single()["cnt"]
        rel_in_region = s.run("MATCH ()-[r:IN_REGION]->() RETURN count(r) as cnt").single()["cnt"]
        rel_for_service = s.run("MATCH ()-[r:FOR_SERVICE]->() RETURN count(r) as cnt").single()["cnt"]
        rel_complaint = s.run("MATCH ()-[r:RECEIVED_COMPLAINT]->() RETURN count(r) as cnt").single()["cnt"]
        rel_incident = s.run("MATCH ()-[r:HAS_INCIDENT]->() RETURN count(r) as cnt").single()["cnt"]
        rel_about_trip = s.run("MATCH ()-[r:ABOUT_TRIP]->() RETURN count(r) as cnt").single()["cnt"]

    driver.close()

    # 3. Qdrant Counts
    qdrant_url = os.getenv("QDRANT_URL", "").rstrip("/")
    qdrant_key = os.getenv("QDRANT_API_KEY", "")
    collection = os.getenv("QDRANT_COLLECTION", "gsm-memory")
    headers = {"Content-Type": "application/json"}
    if qdrant_key:
        headers["api-key"] = qdrant_key

    q_comps = requests.post(f"{qdrant_url}/collections/{collection}/points/count", headers=headers, json={"filter": {"must": [{"key": "kind", "match": {"value": "complaint"}}]}}).json().get("result", {}).get("count", 0)
    q_incs = requests.post(f"{qdrant_url}/collections/{collection}/points/count", headers=headers, json={"filter": {"must": [{"key": "kind", "match": {"value": "incident"}}]}}).json().get("result", {}).get("count", 0)
    q_policies = requests.post(f"{qdrant_url}/collections/{collection}/points/count", headers=headers, json={"filter": {"must": [{"key": "kind", "match": {"value": "policy_document"}}]}}).json().get("result", {}).get("count", 0)
    q_total = requests.get(f"{qdrant_url}/collections/{collection}", headers=headers).json().get("result", {}).get("points_count", 0)

    print(f"📊 1. DRIVERS PARITY:")
    print(f"   - SQLite Drivers: {sqlite_drivers}")
    print(f"   - Neo4j Drivers:  {neo_drivers}")
    print(f"   -> Match: {'✅ YES' if sqlite_drivers == neo_drivers == 8 else '❌ NO'}")

    print(f"\n📊 2. TRIPS PARITY:")
    print(f"   - SQLite Trips: {sqlite_trips}")
    print(f"   - Neo4j Trips:  {neo_trips}")
    print(f"   -> Match: {'✅ YES' if sqlite_trips == neo_trips == 101 else '❌ NO'}")

    print(f"\n📊 3. COMPLAINTS PARITY:")
    print(f"   - SQLite Complaints: {sqlite_comps}")
    print(f"   - Neo4j Complaints:  {neo_comps}")
    print(f"   - Qdrant Complaints: {q_comps}")
    print(f"   -> Match: {'✅ YES' if sqlite_comps == neo_comps == q_comps == 24 else '❌ NO'}")

    print(f"\n📊 4. INCIDENTS PARITY:")
    print(f"   - SQLite Incidents: {sqlite_incs}")
    print(f"   - Neo4j Incidents:  {neo_incs}")
    print(f"   - Qdrant Incidents: {q_incs}")
    print(f"   -> Match: {'✅ YES' if sqlite_incs == neo_incs == q_incs == 13 else '❌ NO'}")

    print(f"\n📊 5. NEO4J GRAPH EDGES VERIFICATION (101 Trips & 37 Events):")
    print(f"   - PERFORMED edges:         {rel_performed} / 101")
    print(f"   - PICKUP_IN edges:         {rel_pickup} / 101")
    print(f"   - DROPOFF_IN edges:        {rel_dropoff} / 101")
    print(f"   - IN_REGION edges:         {rel_in_region} / 101")
    print(f"   - FOR_SERVICE edges:       {rel_for_service} / 101")
    print(f"   - RECEIVED_COMPLAINT edges:{rel_complaint} / 24")
    print(f"   - HAS_INCIDENT edges:      {rel_incident} / 13")
    print(f"   - ABOUT_TRIP edges:        {rel_about_trip} / 36 (24 comps + 12 incs)")

    print(f"\n📊 6. CLEANUP STATUS:")
    print(f"   - Remaining GSMOperationalV3 nodes: {v3_remaining} (Expected: 0) -> {'✅ CLEAN' if v3_remaining == 0 else '❌ DIRTY'}")
    print(f"   - Total Qdrant points:              {q_total} (1560 policy + 24 comps + 13 incs = 1597)")

    all_ok = (
        sqlite_drivers == neo_drivers == 8
        and sqlite_trips == neo_trips == 101
        and sqlite_comps == neo_comps == q_comps == 24
        and sqlite_incs == neo_incs == q_incs == 13
        and rel_performed == rel_pickup == rel_dropoff == rel_in_region == rel_for_service == 101
        and rel_complaint == 24
        and rel_incident == 13
        and rel_about_trip == 36
        and v3_remaining == 0
    )

    if all_ok:
        print("\n🎉 ALL RECONCILIATION & PARITY CHECKS PASSED PERFECTLY!")
    else:
        print("\n⚠️ SOME CHECKS NEED ATTENTION, PLEASE REVIEW.")


def main():
    step1_clean_neo4j()
    step2_clean_sqlite()
    step3_clean_qdrant()
    step4_align_time_and_connect_graph()
    step5_verify_and_reconcile()


if __name__ == "__main__":
    main()
