"""Deterministic Neo4j Knowledge Graph Adapter for Driver Operations Ontology V2 (Snapshot 07/2025).

This adapter implements the stratified GraphRAG ontology for driver operations:
1. Core Entities: Driver, Vehicle, Hub, Zone
2. Operations & Tasks: Shift, Trip
3. Operational Events & Alerts: Incident, CustomerComplaint, MaintenanceEvent
4. Policies & Assessments: PolicyRule, RewardPenalty

Isolation Guarantee:
- All nodes carry the secondary marker label `DriverOpsV2`
- All edges have property `snapshot_id = 'snapshot-2025-07'`
- Node IDs are isolated (prefixed with `v2_`)
- Zero relationships connect to `GSMOperationalV1` or any legacy nodes.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any, Iterable
from dotenv import load_dotenv
from pathlib import Path

# Ensure src in sys.path
SRC_DIR = Path(__file__).resolve().parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

load_dotenv()

MARKER_LABEL = "DriverOpsV2"
SNAPSHOT_ID = "snapshot-2025-07"
SNAPSHOT_LABEL = "Snapshot V2 Tháng 07/2025 (Driver Operations Ontology)"
ONTOLOGY_VERSION = "gsm-driver-ops-kg-v2"

BUSINESS_LABELS = (
    "Driver",
    "Vehicle",
    "Hub",
    "Zone",
    "Shift",
    "Trip",
    "Incident",
    "CustomerComplaint",
    "MaintenanceEvent",
    "PolicyRule",
    "RewardPenalty",
)

RELATIONSHIP_SPECS = (
    ("OPERATES", "Driver", "Vehicle"),
    ("BELONGS_TO", "Driver", "Hub"),
    ("WORKS_SHIFT", "Driver", "Shift"),
    ("SERVED_TRIP", "Driver", "Trip"),
    ("INVOLVED_IN", "Driver", "Incident"),
    ("RECEIVES", "Driver", "RewardPenalty"),
    ("PICKUP_IN", "Trip", "Zone"),
    ("DROPOFF_IN", "Trip", "Zone"),
    ("RECEIVES_COMPLAINT", "Trip", "CustomerComplaint"),
    ("UNDERWENT", "Vehicle", "MaintenanceEvent"),
    ("VIOLATES", "Incident", "PolicyRule"),
    ("VIOLATES", "CustomerComplaint", "PolicyRule"),
    ("BASED_ON", "RewardPenalty", "Incident"),
    ("BASED_ON", "RewardPenalty", "PolicyRule"),
    ("FREQUENTLY_OPERATES_IN", "Driver", "Zone"),
    ("CONTAINS_TRIP", "Shift", "Trip"),
    ("USES_VEHICLE", "Trip", "Vehicle"),
    ("LOCATED_IN", "Hub", "Zone"),
    ("MANAGES_VEHICLE", "Hub", "Vehicle"),
    ("OCCURRED_IN", "Incident", "Shift"),
    ("ESCALATED_TO", "CustomerComplaint", "Incident"),
)


def get_credentials(env_prefix: str = "NEO4J") -> tuple[str, tuple[str, str], str | None]:
    """Retrieve Neo4j credentials from environment."""
    uri = os.getenv(f"{env_prefix}_URI") or os.getenv("NEO4J_URI")
    username = (
        os.getenv(f"{env_prefix}_USERNAME")
        or os.getenv(f"{env_prefix}_USER")
        or os.getenv("NEO4J_USERNAME")
        or os.getenv("NEO4J_USER")
    )
    password = os.getenv(f"{env_prefix}_PASSWORD") or os.getenv("NEO4J_PASSWORD")
    database = (
        os.getenv(f"{env_prefix}_DATABASE")
        or os.getenv("NEO4J_DATABASE")
        or None
    )

    if not uri:
        raise RuntimeError("Missing NEO4J_URI in environment.")
    if not username:
        raise RuntimeError("Missing NEO4J_USERNAME in environment.")
    if not password:
        raise RuntimeError("Missing NEO4J_PASSWORD in environment.")

    return uri, (username, password), database


from gsm_memory.adapters.v2_operational_catalog import build_v2_graph_dataset


def generate_v2_operational_data() -> dict[str, list[dict[str, Any]]]:
    """Delegate to comprehensive V2 operational catalog (342 nodes, 1097 edges)."""
    return build_v2_graph_dataset()


def ensure_v2_constraints(session: Any) -> None:
    """Create uniqueness constraints for V2 ontology under marker DriverOpsV2."""
    session.run(
        f"CREATE CONSTRAINT constraint_v2_driverops_id IF NOT EXISTS "
        f"FOR (n:{MARKER_LABEL}) REQUIRE n.id IS UNIQUE"
    ).consume()


def ingest_driver_ops_v2(env_prefix: str = "NEO4J") -> dict[str, Any]:
    """Ingest the V2 ontology dataset into Neo4j in a strictly isolated manner."""
    from neo4j import GraphDatabase

    uri, auth, database = get_credentials(env_prefix)
    driver = GraphDatabase.driver(uri, auth=auth)
    dataset = generate_v2_operational_data()

    try:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            ensure_v2_constraints(session)

            # Clean up existing V2 nodes and relationships cleanly to ensure zero stale entities
            session.run(
                f"MATCH (n:{MARKER_LABEL}) DETACH DELETE n"
            ).consume()

            # Ingest Nodes
            nodes_created = 0
            for label in BUSINESS_LABELS:
                batch = [n for n in dataset["nodes"] if n["label"] == label]
                if not batch:
                    continue
                res = session.run(
                    f"UNWIND $rows AS row "
                    f"MERGE (n:{MARKER_LABEL}:{label} {{id: row.id}}) "
                    "ON CREATE SET n += row.props, n.created_at = datetime() "
                    "ON MATCH SET n += row.props, n.updated_at = datetime() "
                    "RETURN count(n) AS cnt",
                    rows=batch,
                ).single()
                if res:
                    nodes_created += res["cnt"]

            # Ingest Edges
            edges_created = 0
            for rel_type, start_label, end_label in RELATIONSHIP_SPECS:
                matching_edges = [
                    e for e in dataset["edges"]
                    if e["type"] == rel_type
                    and e["start_label"] == start_label
                    and e["end_label"] == end_label
                ]
                if not matching_edges:
                    continue

                res = session.run(
                    f"UNWIND $rows AS row "
                    f"MATCH (a:{MARKER_LABEL}:{start_label} {{id: row.start_id}}) "
                    f"MATCH (b:{MARKER_LABEL}:{end_label} {{id: row.end_id}}) "
                    f"MERGE (a)-[r:{rel_type} {{snapshot_id: row.props.snapshot_id}}]->(b) "
                    "ON CREATE SET r += row.props, r.ingested_at = datetime() "
                    "ON MATCH SET r += row.props, r.updated_at = datetime() "
                    "RETURN count(r) AS cnt",
                    rows=matching_edges,
                ).single()
                if res:
                    edges_created += res["cnt"]

            verification = verify_driver_ops_v2_internal(session, dataset)
    finally:
        driver.close()

    return {
        "status": "success" if verification["is_valid"] else "failed",
        "snapshot_id": SNAPSHOT_ID,
        "ontology_version": ONTOLOGY_VERSION,
        "nodes_ingested": len(dataset["nodes"]),
        "edges_ingested": len(dataset["edges"]),
        "verification": verification,
    }


def verify_driver_ops_v2_internal(session: Any, dataset: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Verify isolation, node counts, and integrity."""
    # 1. Total V2 Nodes
    v2_node_count = session.run(
        f"MATCH (n:{MARKER_LABEL}) RETURN count(n) AS cnt"
    ).single()["cnt"]

    # 2. Total V2 Edges
    v2_edge_count = session.run(
        f"MATCH (a:{MARKER_LABEL})-[r]->(b:{MARKER_LABEL}) "
        f"WHERE r.snapshot_id = $snap "
        "RETURN count(r) AS cnt",
        snap=SNAPSHOT_ID,
    ).single()["cnt"]

    # 3. CRITICAL ISOLATION CHECK: Check for cross-contamination with old graph (GSMOperationalV1)
    cross_contamination = session.run(
        f"MATCH (v2:{MARKER_LABEL})-[r]-(old:GSMOperationalV1) "
        "RETURN count(r) AS cross_cnt"
    ).single()["cross_cnt"]

    # 4. Check for any edge leading outside DriverOpsV2
    leakage = session.run(
        f"MATCH (v2:{MARKER_LABEL})-[r]-(other) "
        f"WHERE NOT other:{MARKER_LABEL} "
        "RETURN count(r) AS leak_cnt"
    ).single()["leak_cnt"]

    # 5. Label Breakdown
    breakdown_records = session.run(
        f"MATCH (n:{MARKER_LABEL}) "
        "RETURN [lbl IN labels(n) WHERE lbl <> $marker][0] AS label, count(n) AS cnt",
        marker=MARKER_LABEL,
    ).data()
    label_breakdown = {r["label"]: r["cnt"] for r in breakdown_records if r["label"]}

    is_valid = (
        v2_node_count == len(dataset["nodes"])
        and v2_edge_count == len(dataset["edges"])
        and cross_contamination == 0
        and leakage == 0
    )

    return {
        "is_valid": is_valid,
        "v2_node_count": v2_node_count,
        "v2_edge_count": v2_edge_count,
        "cross_contamination_count": cross_contamination,
        "external_leakage_count": leakage,
        "label_breakdown": label_breakdown,
    }


def verify_driver_ops_v2(env_prefix: str = "NEO4J") -> dict[str, Any]:
    """Read-only verification of V2 ontology in Neo4j."""
    from neo4j import GraphDatabase

    uri, auth, database = get_credentials(env_prefix)
    driver = GraphDatabase.driver(uri, auth=auth)
    dataset = generate_v2_operational_data()
    try:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            return verify_driver_ops_v2_internal(session, dataset)
    finally:
        driver.close()


def query_driver_ops_v2_subgraph(driver_id: str, session: Any) -> dict[str, Any]:
    """Traverse multi-hop neighborhood in V2 ontology for a specific driver."""
    # Hop 1: Driver -> Direct Neighbors
    hop1_cypher = f"""
    MATCH (d:{MARKER_LABEL}:Driver {{id: $driver_id}})-[r]->(m:{MARKER_LABEL})
    WHERE r.snapshot_id = $snapshot_id
    RETURN d.id AS driver_id, d.name AS driver_name, properties(d) AS driver_props,
           type(r) AS rel_type, properties(r) AS rel_props,
           [lbl IN labels(m) WHERE lbl <> '{MARKER_LABEL}'][0] AS m_label,
           m.id AS m_id, properties(m) AS m_props
    """
    records = session.run(hop1_cypher, driver_id=driver_id, snapshot_id=SNAPSHOT_ID).data()
    if not records:
        # Check if driver node exists
        d_rec = session.run(
            f"MATCH (d:{MARKER_LABEL}:Driver {{id: $driver_id}}) RETURN properties(d) AS props",
            driver_id=driver_id,
        ).single()
        if not d_rec:
            return {"nodes": [], "edges": []}
        return {"nodes": [{"id": driver_id, "label": "Driver", "props": d_rec["props"]}], "edges": []}

    nodes = {}
    edges = []

    driver_props = records[0]["driver_props"]
    nodes[driver_id] = {
        "id": driver_id,
        "label": "Driver",
        "name": records[0]["driver_name"] or driver_props.get("name", driver_id),
        "props": driver_props,
    }

    for r in records:
        m_id = r["m_id"]
        m_label = r["m_label"]
        if m_id not in nodes:
            nodes[m_id] = {
                "id": m_id,
                "label": m_label,
                "name": r["m_props"].get("name") or r["m_props"].get("rule_name") or r["m_props"].get("zone_name") or f"{m_label} {m_id}",
                "props": r["m_props"],
            }
        edges.append({
            "start_id": driver_id,
            "end_id": m_id,
            "rel_type": r["rel_type"],
            "props": r["rel_props"],
        })

    # Hop 2: Secondary neighbors from all Hop 1 nodes
    hop1_ids = [m_id for m_id in nodes.keys() if m_id != driver_id]
    hop2_discovered_ids = []

    if hop1_ids:
        hop2_cypher = f"""
        MATCH (src:{MARKER_LABEL})-[r2]->(tgt:{MARKER_LABEL})
        WHERE src.id IN $target_ids AND r2.snapshot_id = $snapshot_id
        RETURN src.id AS src_id, type(r2) AS rel_type, properties(r2) AS rel_props,
               [lbl IN labels(tgt) WHERE lbl <> '{MARKER_LABEL}'][0] AS tgt_label,
               tgt.id AS tgt_id, properties(tgt) AS tgt_props
        """
        hop2_records = session.run(hop2_cypher, target_ids=hop1_ids, snapshot_id=SNAPSHOT_ID).data()
        for r2 in hop2_records:
            tgt_id = r2["tgt_id"]
            tgt_label = r2["tgt_label"]
            if tgt_id not in nodes:
                nodes[tgt_id] = {
                    "id": tgt_id,
                    "label": tgt_label,
                    "name": r2["tgt_props"].get("name") or r2["tgt_props"].get("zone_name") or r2["tgt_props"].get("rule_name") or f"{tgt_label} {tgt_id}",
                    "props": r2["tgt_props"],
                }
                hop2_discovered_ids.append(tgt_id)
            edges.append({
                "start_id": r2["src_id"],
                "end_id": tgt_id,
                "rel_type": r2["rel_type"],
                "props": r2["rel_props"],
            })

    # Hop 3: Tertiary neighbors (e.g., CustomerComplaint -> Incident / PolicyRule)
    if hop2_discovered_ids:
        hop3_records = session.run(hop2_cypher, target_ids=hop2_discovered_ids, snapshot_id=SNAPSHOT_ID).data()
        for r3 in hop3_records:
            tgt_id = r3["tgt_id"]
            tgt_label = r3["tgt_label"]
            if tgt_id not in nodes:
                nodes[tgt_id] = {
                    "id": tgt_id,
                    "label": tgt_label,
                    "name": r3["tgt_props"].get("name") or r3["tgt_props"].get("zone_name") or r3["tgt_props"].get("rule_name") or f"{tgt_label} {tgt_id}",
                    "props": r3["tgt_props"],
                }
            edges.append({
                "start_id": r3["src_id"],
                "end_id": tgt_id,
                "rel_type": r3["rel_type"],
                "props": r3["rel_props"],
            })

    return {"nodes": list(nodes.values()), "edges": edges}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Driver Operations V2 Neo4j Adapter")
    parser.add_argument("--ingest", action="store_true", help="Ingest V2 dataset into Neo4j")
    parser.add_argument("--verify", action="store_true", help="Verify V2 dataset in Neo4j")
    args = parser.parse_args()

    if args.ingest:
        print("[Neo4j V2] Starting ingestion for Snapshot 07/2025...")
        result = ingest_driver_ops_v2()
        print("[Neo4j V2] Ingestion Result:")
        import json
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.verify:
        print("[Neo4j V2] Verifying V2 dataset in Neo4j...")
        result = verify_driver_ops_v2()
        import json
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        parser.print_help()
