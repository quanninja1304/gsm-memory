"""Database seeder to populate SQLite with benchmark data and supplementary operational records."""

from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure src in sys.path
ROOT_DIR = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pyarrow.parquet as pq

from gsm_memory.db.connection import get_db_path, get_db_session
from gsm_memory.db.models import (
    ComplaintRecord,
    DriverRecord,
    IncidentRecord,
    SnapshotRecord,
    TripRecord,
)
from gsm_memory.db.repository import LocalDatabaseRepository
from gsm_memory.db.schema import init_schema

# Pinned benchmark snapshots catalog
SNAPSHOTS_SEED_DATA = [
    {
        "snapshot_id": "a01883a7-d8be-55bb-a561-479a63adf9ee",
        "label": "Snapshot 1 (17/08/2026 23:59:59)",
        "known_as_of": "2026-08-17T23:59:59.000000Z",
        "scope": "Thời điểm 17/08/2026 (Khởi tạo hệ thống, 45 nodes, 58 edges, 0 trips)",
        "aliases": ["17/08", "17/08/2026", "2026-08-17", "snapshot 1", "snapshot-1"],
        "is_baseline": False,
    },
    {
        "snapshot_id": "41d9cbe1-5ddd-5ca5-96ad-1b9c0929480a",
        "label": "Snapshot 2 (18/08/2026 23:59:59)",
        "known_as_of": "2026-08-18T23:59:59.000000Z",
        "scope": "Thời điểm 18/08/2026 (62 nodes, 103 edges, 6 trips, 4 sự cố)",
        "aliases": ["18/08", "18/08/2026", "2026-08-18", "snapshot 2", "snapshot-2"],
        "is_baseline": False,
    },
    {
        "snapshot_id": "32cc841a-0440-5283-80d7-aebb77b935b3",
        "label": "Snapshot 3 (20/08/2026 23:59:59)",
        "known_as_of": "2026-08-20T23:59:59.000000Z",
        "scope": "Thời điểm 20/08/2026 (80 nodes, 179 edges, 21 trips, 3 khiếu nại, 4 sự cố)",
        "aliases": ["20/08", "20/08/2026", "2026-08-20", "snapshot 3", "snapshot-3"],
        "is_baseline": False,
    },
    {
        "snapshot_id": "b768a6f4-6b45-5014-a87f-98d013e0ec5a",
        "label": "Snapshot 4 (22/08/2026 23:59:59)",
        "known_as_of": "2026-08-22T23:59:59.000000Z",
        "scope": "Thời điểm 22/08/2026 (96 nodes, 253 edges, 35 trips, 5 khiếu nại, 4 sự cố)",
        "aliases": ["22/08", "22/08/2026", "2026-08-22", "snapshot 4", "snapshot-4"],
        "is_baseline": False,
    },
    {
        "snapshot_id": "7ad8774d-08fc-55a6-badb-2447ee6cab53",
        "label": "Snapshot 5 (24/08/2026 23:59:59)",
        "known_as_of": "2026-08-24T23:59:59.000000Z",
        "scope": "Thời điểm 24/08/2026 (112 nodes, 327 edges, 49 trips, 7 khiếu nại, 4 sự cố)",
        "aliases": ["24/08", "24/08/2026", "2026-08-24", "snapshot 5", "snapshot-5"],
        "is_baseline": False,
    },
    {
        "snapshot_id": "fd133f31-6db4-5c7c-9791-c1301176dc3f",
        "label": "Snapshot 6 (26/08/2026 23:59:59)",
        "known_as_of": "2026-08-26T23:59:59.000000Z",
        "scope": "Thời điểm 26/08/2026 (128 nodes, 401 edges, 63 trips, 9 khiếu nại, 4 sự cố)",
        "aliases": ["26/08", "26/08/2026", "2026-08-26", "snapshot 6", "snapshot-6"],
        "is_baseline": False,
    },
    {
        "snapshot_id": "a6037ae7-4642-55d9-a36a-88fca6875fdf",
        "label": "Snapshot 7 (28/08/2026 23:59:59)",
        "known_as_of": "2026-08-28T23:59:59.000000Z",
        "scope": "Thời điểm 28/08/2026 (139 nodes, 453 edges, 73 trips, 10 khiếu nại, 4 sự cố)",
        "aliases": ["28/08", "28/08/2026", "2026-08-28", "snapshot 7", "snapshot-7"],
        "is_baseline": False,
    },
    {
        "snapshot_id": "002366a5-e09e-5214-9fe4-c7fffeaf1396",
        "label": "Snapshot 8 (31/08/2026 23:59:59)",
        "known_as_of": "2026-08-31T23:59:59.000000Z",
        "scope": "Thời điểm 31/08/2026 (147 nodes, 490 edges, 80 trips, 11 khiếu nại, 4 sự cố)",
        "aliases": ["31/08", "31/08/2026", "2026-08-31", "tháng 8", "tháng 08", "tháng 8/2026", "2026-08", "snapshot 8", "snapshot-8"],
        "is_baseline": False,
    },
    {
        "snapshot_id": "081a61c0-56dd-5f43-88a4-f4dfb2894412",
        "label": "Snapshot 9 (01/09/2026 23:59:59)",
        "known_as_of": "2026-09-01T23:59:59.000000Z",
        "scope": "Thời điểm 01/09/2026 (149 nodes, 494 edges, 80 trips, 11 khiếu nại, 5 sự cố)",
        "aliases": ["01/09", "01/09/2026", "2026-09-01", "đầu tháng 9", "snapshot 9", "snapshot-9"],
        "is_baseline": False,
    },
    {
        "snapshot_id": "e64f47d9-1a09-5954-9ac6-a3e9770fa38a",
        "label": "Snapshot 10 (16/09/2026 12:00:00)",
        "known_as_of": "2026-09-16T12:00:00.000000Z",
        "scope": "Thời điểm 16/09/2026 (192 nodes, 550 edges, 80 trips, 11 khiếu nại, 5 sự cố)",
        "aliases": ["16/09", "16/09/2026", "2026-09-16", "hôm qua", "snapshot 10", "snapshot-10"],
        "is_baseline": False,
    },
    {
        "snapshot_id": "96d00bc2-d39b-592b-b0d8-0ad4a5b80c30",
        "label": "Snapshot 11 (17/09/2026 12:00:00)",
        "known_as_of": "2026-09-17T12:00:00.000000Z",
        "scope": "Thời điểm 17/09/2026 (193 nodes, 558 edges, 80 trips, 11 khiếu nại, 5 sự cố)",
        "aliases": ["17/09", "17/09/2026", "2026-09-17", "tháng 9", "tháng 09", "tháng 9/2026", "2026-09", "kỳ đánh giá", "snapshot 11", "snapshot-11"],
        "is_baseline": False,
    },
    {
        "snapshot_id": "8b1426b6-2fad-5aba-b886-e16de44c18e7",
        "label": "Snapshot 12 Baseline (18/09/2026 03:00:00)",
        "known_as_of": "2026-09-18T03:00:00.000000Z",
        "scope": "Toàn bộ đồ thị GSMOperationalV3Timeline (201 nodes, 582 edges, 80 trips, 11 khiếu nại, 5 sự cố)",
        "aliases": [
            "18/09", "18/09/2026", "2026-09-18", "hiện tại", "gần nhất", "hôm nay", "mới nhất",
            "baseline", "toàn bộ", "30 ngày gần nhất", "30 ngày qua", "30 ngày", "kỳ này",
            "snapshot 12", "snapshot-12"
        ],
        "is_baseline": True,
    },
]

# Pinned benchmark drivers catalog
DRIVERS_SEED_DATA = [
    {
        "driver_id": "99e70ebe-18cd-57a3-a036-cf0ff1989861",
        "driver_code": "DRV-001",
        "full_name": "Nguyễn Văn An",
        "phone": "0903 124 589",
        "email": "an.nguyen@taxixanhsm.vn",
        "depot_name": "Depot Hà Nội 1",
        "region": "Hà Nội",
        "service_type": "Taxi Xanh SM Standard",
        "program": "full_time",
        "status": "active",
        "vehicle_model": "VinFast VF e34",
        "license_plate": "29E-812.34",
        "rating_avg": 4.95,
        "acceptance_rate": 0.98,
        "cancellation_rate_30d": 0.0,
    },
    {
        "driver_id": "c499f934-bfe1-5509-a578-afb09cee357c",
        "driver_code": "DRV-002",
        "full_name": "Trần Văn Bình",
        "phone": "0918 345 672",
        "email": "binh.tran@taxixanhsm.vn",
        "depot_name": "Depot Hồ Chí Minh 2",
        "region": "TP.HCM",
        "service_type": "Xanh SM Luxury",
        "program": "full_time",
        "status": "active",
        "vehicle_model": "VinFast VF 8",
        "license_plate": "51K-945.12",
        "rating_avg": 4.88,
        "acceptance_rate": 0.92,
        "cancellation_rate_30d": 0.20,
    },
    {
        "driver_id": "3b0b7be7-b553-5d99-9528-4a07ca4f1567",
        "driver_code": "DRV-003",
        "full_name": "Lê Thị Chi",
        "phone": "0972 567 890",
        "email": "chi.le@taxixanhsm.vn",
        "depot_name": "Depot Hồ Chí Minh 1",
        "region": "TP.HCM",
        "service_type": "Taxi Xanh SM Standard",
        "program": "full_time",
        "status": "active",
        "vehicle_model": "VinFast VF 5 Plus",
        "license_plate": "51K-332.90",
        "rating_avg": 4.96,
        "acceptance_rate": 0.97,
        "cancellation_rate_30d": 0.0,
    },
    {
        "driver_id": "cc916c6b-b168-5d8f-9023-075391ee4136",
        "driver_code": "DRV-004",
        "full_name": "Phạm Quốc Dũng",
        "phone": "0938 112 233",
        "email": "dung.pham@taxixanhsm.vn",
        "depot_name": "Depot Hồ Chí Minh 6",
        "region": "TP.HCM",
        "service_type": "Taxi Xanh SM Standard",
        "program": "full_time",
        "status": "active",
        "vehicle_model": "VinFast VF e34",
        "license_plate": "51K-556.78",
        "rating_avg": 4.90,
        "acceptance_rate": 0.94,
        "cancellation_rate_30d": 0.0,
    },
    {
        "driver_id": "58e68d69-f07f-580e-a4b6-91ef3801c5d7",
        "driver_code": "DRV-005",
        "full_name": "Hoàng Văn Minh",
        "phone": "0984 667 889",
        "email": "minh.hoang@taxixanhsm.vn",
        "depot_name": "Depot Hồ Chí Minh 1 (Đội 1)",
        "region": "TP.HCM",
        "service_type": "Xanh SM Luxury",
        "program": "full_time",
        "status": "active",
        "vehicle_model": "VinFast VF 8",
        "license_plate": "51K-678.90",
        "rating_avg": 4.93,
        "acceptance_rate": 0.96,
        "cancellation_rate_30d": 0.0,
    },
    {
        "driver_id": "b8afff09-1200-5bcd-a594-6a647680f865",
        "driver_code": "DRV-006",
        "full_name": "Vũ Nhật Minh",
        "phone": "0908 991 223",
        "email": "minh.vu@taxixanhsm.vn",
        "depot_name": "Depot Hồ Chí Minh 2 (Đội 2)",
        "region": "TP.HCM",
        "service_type": "Taxi Xanh SM Standard",
        "program": "full_time",
        "status": "active",
        "vehicle_model": "VinFast VF e34",
        "license_plate": "51K-123.99",
        "rating_avg": 4.91,
        "acceptance_rate": 0.95,
        "cancellation_rate_30d": 0.0,
    },
    {
        "driver_id": "bff953c4-63cd-58b5-82f3-d3ecac5ac17a",
        "driver_code": "DRV-007",
        "full_name": "Đặng Hương Giang",
        "phone": "0963 888 123",
        "email": "giang.dang@taxixanhsm.vn",
        "depot_name": "Depot Hồ Chí Minh 6",
        "region": "TP.HCM",
        "service_type": "Xanh SM Bike",
        "program": "bike_partner",
        "status": "active",
        "vehicle_model": "VinFast Klara S",
        "license_plate": "59-X3 789.12",
        "rating_avg": 4.94,
        "acceptance_rate": 0.99,
        "cancellation_rate_30d": 0.0,
    },
    {
        "driver_id": "122a3140-7c98-5136-a732-8a9566cb727d",
        "driver_code": "DRV-008",
        "full_name": "Bùi Thu Hà",
        "phone": "0945 777 999",
        "email": "ha.bui@taxixanhsm.vn",
        "depot_name": "Depot Hồ Chí Minh 7",
        "region": "TP.HCM",
        "service_type": "Taxi Xanh SM Standard",
        "program": "full_time",
        "status": "active",
        "vehicle_model": "VinFast VF 5 Plus",
        "license_plate": "51K-445.67",
        "rating_avg": 4.89,
        "acceptance_rate": 0.93,
        "cancellation_rate_30d": 0.0,
    },
]

# Alias map for driver IDs so DRV-007 and DRV-008 map cleanly
DRIVER_ID_ALIASES = {
    "42c4b074-68f7-5f04-8ea7-a3f81e35a165": "bff953c4-63cd-58b5-82f3-d3ecac5ac17a",
    "964fb4ef-1bc7-5c21-b384-25e1a1c97a8a": "122a3140-7c98-5136-a732-8a9566cb727d",
}

# Realistic route locations
ROUTES_HCM = [
    ("Sân bay Tân Sơn Nhất, Ga Quốc Nội T1", "Vinhomes Central Park, 208 Nguyễn Hữu Cảnh, Q.Bình Thạnh", 9.2, 165000),
    ("Landmark 81, Tân Cảng, Bình Thạnh", "Chợ Bến Thành, Lê Lợi, Quận 1", 5.4, 98000),
    ("Vincom Center Đồng Khởi, Quận 1", "Khu đô thị Sala, Mai Chí Thọ, TP.Thủ Đức", 4.1, 75000),
    ("Bến xe Miền Đông mới, TP.Thủ Đức", "Đại học Bách Khoa, 268 Lý Thường Kiệt, Quận 10", 18.5, 295000),
    ("Crescent Mall, Nguyễn Văn Linh, Quận 7", "Bitexco Financial Tower, Hải Triều, Quận 1", 7.8, 140000),
    ("Sân bay Tân Sơn Nhất, Ga Quốc Tế T2", "Vinhomes Grand Park, Long Bình, TP.Thủ Đức", 22.0, 350000),
    ("Chợ Lớn, Hải Thượng Lãn Ông, Quận 5", "Phố đi bộ Nguyễn Huệ, Quận 1", 6.5, 115000),
    ("Bệnh viện Chợ Rẫy, Nguyễn Chí Thanh, Quận 5", "Khu Dân Cư Trung Sơn, Bình Chánh", 5.8, 105000),
    ("Khu Công Nghệ Cao TP.Thủ Đức (SHTP)", "Sân bay Tân Sơn Nhất, Quận Tân Bình", 19.3, 310000),
    ("Emart Gò Vấp, Phan Văn Trị", "Vincom Plaza Phan Văn Trị, Gò Vấp", 2.5, 52000),
]

ROUTES_HN = [
    ("Sân bay Quốc tế Nội Bài, Ga T1", "Hồ Hoàn Kiếm, Đinh Tiên Hoàng, Q.Hoàn Kiếm", 28.5, 380000),
    ("Keangnam Landmark 72, Phạm Hùng", "Vincom Center Bà Triệu, Hai Bà Trưng", 8.6, 145000),
    ("Bến xe Mỹ Đình, Nam Từ Liêm", "Ga Hà Nội, Lê Duẩn, Đống Đa", 7.2, 125000),
    ("Vinhomes Ocean Park 1, Gia Lâm", "Hồ Tây, Đường Thanh Niên, Ba Đình", 16.0, 260000),
    ("Lotte Center Hà Nội, 54 Liễu Giai", "Times City, 458 Minh Khai, Hai Bà Trưng", 9.5, 160000),
    ("Công viên Cầu Giấy, Duy Tân", "Aeon Mall Hà Đông, Dương Nội", 8.0, 135000),
]

FEEDBACK_GOOD = [
    "Tài xế lái xe êm ái, xe VinFast điện rất thơm và sạch sẽ.",
    "Bác tài đón đúng giờ, lịch sự, phục vụ 5 sao.",
    "Lái xe cẩn thận, tuân thủ tốc độ, nhiệt tình giúp khách xách hành lý.",
    "Chuyến đi rất thoải mái, điều hòa mát mẻ, xe không tiếng ồn động cơ.",
    "Tài xế thân thiện, chuẩn phong cách Xanh SM.",
]


def sync_snapshots(db_path: Path | str | None = None) -> list[SnapshotRecord]:
    """Idempotently sync all 12 benchmark snapshots into the local SQLite database."""
    if db_path is None:
        db_path = get_db_path()
    repo = LocalDatabaseRepository(db_path)
    now_str = datetime.now(timezone.utc).isoformat()
    synced: list[SnapshotRecord] = []
    print(f"📸 [Sync Snapshots] Upserting {len(SNAPSHOTS_SEED_DATA)} snapshots into SQLite at: {db_path}...")
    for s in SNAPSHOTS_SEED_DATA:
        s_rec = SnapshotRecord(
            snapshot_id=s["snapshot_id"],
            label=s["label"],
            known_as_of=s["known_as_of"],
            scope=s.get("scope"),
            aliases=s.get("aliases", []),
            is_baseline=s.get("is_baseline", False),
            created_at=now_str,
        )
        repo.upsert_snapshot(s_rec)
        synced.append(s_rec)
    print(f"  ✅ Successfully synced {len(synced)} snapshots.")
    return synced


def seed_database(force_recreate: bool = True) -> DatabaseStats:
    """Populate local database with complete drivers, trips, sessions, and memory."""
    db_path = get_db_path()
    if force_recreate and db_path.exists():
        try:
            db_path.unlink()
        except Exception:
            pass

    repo = LocalDatabaseRepository(db_path)
    now_str = datetime.now(timezone.utc).isoformat()

    print(f"🌱 [Local DB Seed] Initializing database at: {db_path}")

    # 0. SEED SNAPSHOTS
    print(f"  📸 Seeding {len(SNAPSHOTS_SEED_DATA)} system snapshots...")
    for s in SNAPSHOTS_SEED_DATA:
        s_rec = SnapshotRecord(
            snapshot_id=s["snapshot_id"],
            label=s["label"],
            known_as_of=s["known_as_of"],
            scope=s.get("scope"),
            aliases=s.get("aliases", []),
            is_baseline=s.get("is_baseline", False),
            created_at=now_str,
        )
        repo.upsert_snapshot(s_rec)

    # 1. SEED DRIVERS
    print(f"  👤 Seeding {len(DRIVERS_SEED_DATA)} drivers...")
    for d in DRIVERS_SEED_DATA:
        rec = DriverRecord(
            driver_id=d["driver_id"],
            driver_code=d["driver_code"],
            full_name=d["full_name"],
            phone=d["phone"],
            email=d["email"],
            depot_name=d["depot_name"],
            region=d["region"],
            service_type=d["service_type"],
            program=d["program"],
            status=d["status"],
            vehicle_model=d["vehicle_model"],
            license_plate=d["license_plate"],
            rating_avg=d["rating_avg"],
            acceptance_rate=d["acceptance_rate"],
            cancellation_rate_30d=d["cancellation_rate_30d"],
            completed_trips_count=0,
            cancelled_trips_count=0,
            created_at=now_str,
            updated_at=now_str,
        )
        repo.upsert_driver(rec)

    # 2. SEED 80 BENCHMARK TRIPS, 11 COMPLAINTS & 5 INCIDENTS FROM v3_timeline_seed.json
    seed_json_path = ROOT_DIR / "data" / "v3_timeline_seed.json"
    benchmark_trips_count = 0
    complaints_count = 0
    incidents_count = 0

    if seed_json_path.exists():
        print(f"  🚕 Importing canonical trips, complaints & incidents from {seed_json_path.name}...")
        with open(seed_json_path, "r", encoding="utf-8") as f:
            seed_data = json.load(f)

        # 2a. TRIPS
        for t in seed_data.get("trips", []):
            st_dt_str = t["start_time"]
            try:
                st_dt = datetime.fromisoformat(st_dt_str.replace("Z", "+00:00"))
            except Exception:
                st_dt = datetime(2026, 8, 18, 2, 0, tzinfo=timezone.utc)
            dist = 8.5
            end_dt = st_dt + timedelta(minutes=int(dist * 2.5) + 10)
            is_cancelled = t["outcome"] == "cancelled"
            cancel_party = "driver" if is_cancelled else "none"
            rating = None if is_cancelled else 5
            feedback = None if is_cancelled else "Chuyến đi an toàn, tài xế văn minh"

            v_snaps = t.get("visibility_snapshot_ids") or []
            earliest_snap = v_snaps[0] if v_snaps else "8b1426b6-2fad-5aba-b886-e16de44c18e7"

            t_rec = TripRecord(
                trip_id=t["trip_id"],
                driver_id=t["driver_id"],
                snapshot_id=earliest_snap,
                visibility_snapshot_ids=v_snaps,
                start_time=st_dt.isoformat(),
                end_time=end_dt.isoformat(),
                pickup_address=t.get("pickup") or "Điểm đón GSM",
                dropoff_address=t.get("dropoff") or "Điểm đến GSM",
                region=t.get("region") or "TP.HCM",
                service_type=t.get("service_type") or "Taxi Xanh SM",
                distance_km=dist,
                fare_amount=120000 if not is_cancelled else 0,
                outcome=t["outcome"],
                reason_code=t.get("reason_code", "unspecified"),
                cancel_party=cancel_party,
                passenger_rating=rating,
                passenger_feedback=feedback,
                notes=t.get("description"),
                created_at=st_dt.isoformat(),
            )
            repo.upsert_trip(t_rec)
            benchmark_trips_count += 1

        # 2b. COMPLAINTS
        for c in seed_data.get("complaints", []):
            c_rec = ComplaintRecord(
                complaint_id=c["complaint_id"],
                driver_id=c["driver_id"],
                trip_id=c.get("trip_id"),
                category=c.get("category", "general"),
                event_time=c["event_time"],
                name=c.get("name"),
                description=c.get("description", ""),
                visibility_snapshot_ids=c.get("visibility_snapshot_ids") or [],
                created_at=c["event_time"],
            )
            repo.upsert_complaint(c_rec)
            complaints_count += 1

        # 2c. INCIDENTS
        for i in seed_data.get("incidents", []):
            i_rec = IncidentRecord(
                incident_id=i["incident_id"],
                driver_id=i.get("driver_id"),
                trip_id=i.get("trip_id"),
                incident_type=i.get("incident_type", "operational_issue"),
                event_time=i.get("event_time"),
                name=i.get("name"),
                description=i.get("description", ""),
                visibility_snapshot_ids=i.get("visibility_snapshot_ids") or [],
                created_at=i.get("event_time") or now_str,
            )
            repo.upsert_incident(i_rec)
            incidents_count += 1

    print(f"  ✅ Imported {benchmark_trips_count} trips, {complaints_count} complaints, {incidents_count} incidents.")

    # 4. RECALCULATE METRICS FOR ALL DRIVERS
    print("  📊 Recomputing driver metrics & cancellation rates...")
    for d_info in DRIVERS_SEED_DATA:
        repo.update_driver_metrics(d_info["driver_id"])

    # 5. SEED SAMPLE CHAT SESSIONS WITH MULTI-TURN CONTEXT MEMORY
    print("  💬 Seeding sample chat sessions with context memory...")

    # Session 1: Trần Văn Bình (DRV-002) - Vi phạm hủy chuyến & đối soát P154
    s1_id = "session-001-drv002-binh"
    repo.create_session(
        session_id=s1_id,
        title="Kiểm tra tài xế Bình (DRV-002) - Vi phạm hủy chuyến P154",
        driver_id="c499f934-bfe1-5509-a578-afb09cee357c",
    )
    # Turn 1
    m1_user = repo.add_message(
        session_id=s1_id,
        role="user",
        content="Kiểm tra tài xế Bình (mã DRV-002), trong tháng 9/2026 theo quy chế P154 có bị vi phạm tiêu chuẩn do hủy chuyến không, tỷ lệ hủy chuyến là bao nhiêu?",
        created_at="2026-09-17T08:30:00.000000Z",
    )
    m1_bot = repo.add_message(
        session_id=s1_id,
        role="assistant",
        content=(
            "Báo cáo kết quả tra cứu hồ sơ vận hành của tài xế **Trần Văn Bình (DRV-002)** trong **tháng 09/2026** và đối chiếu với **Quy chế P154**:\n\n"
            "1. **Tỷ lệ hủy chuyến (cancel_rate_30d):**\n"
            "   - Trong 30 ngày qua (tháng 9/2026), tài xế có tổng cộng 10 chuyến đi, trong đó có **2 chuyến bị hủy** do tài xế.\n"
            "   - Tỷ lệ hủy chuyến được tính chính xác là: **20.0% (1/5)**.\n\n"
            "2. **Đối soát theo Quy chế P154 (Điều 4 & Phụ lục tiêu chuẩn):**\n"
            "   - Tiêu chuẩn tỷ lệ hủy chuyến cho phép: tối đa **10.0%**.\n"
            "   - Do tỷ lệ hủy thực tế (20.0%) vượt quá ngưỡng quy định (10.0%), tài xế **BỊ VI PHẠM TIÊU CHUẨN VẬN HÀNH** trong kỳ đánh giá này.\n\n"
            "3. **Đề xuất xử lý vận hành:**\n"
            "   - Bộ phận điều hành cần ghi nhận biên bản vi phạm và nhắc nhở tài xế tuân thủ quy định nhận chuyến, hạn chế hủy chuyến trong các chu kỳ tiếp theo."
        ),
        query_plan={
            "intent": "HYBRID_REASONING",
            "driver_id": "c499f934-bfe1-5509-a578-afb09cee357c",
            "driver_mention": "Bình (DRV-002)",
            "time_scope": "tháng 9/2026",
            "snapshot_id": "d4cc0438-d831-541a-8123-ddda94ccdac8",
            "policy_scope": "P154",
            "missing_fields": [],
            "reasoning": "Tra cứu đồ thị cho tài xế Bình DRV-002, tính cancel_rate_30d và đối soát quy chế P154.",
        },
        citations=[
            {"locator": "policy:P154#sec-4.2", "content": "Quy chế P154 Điều 4: Tỷ lệ hủy chuyến tối đa của tài xế không vượt quá 10% trong chu kỳ 30 ngày."},
            {"locator": "kg:driver/c499f934-bfe1-5509-a578-afb09cee357c", "content": "Tài xế Trần Văn Bình (DRV-002), 10 chuyến đi, 2 chuyến hủy (tỷ lệ 20%)."},
        ],
        subgraph={"node_count": 16, "edge_count": 18},
        latency_ms=1840.0,
        created_at="2026-09-17T08:30:03.000000Z",
    )
    # Turn 2: User asks follow-up using conversational memory
    m2_user = repo.add_message(
        session_id=s1_id,
        role="user",
        content="Chi tiết 2 chuyến bị hủy đó diễn ra vào ngày nào và thời hạn khiếu nại của tài xế quy định thế nào?",
        created_at="2026-09-17T08:32:00.000000Z",
    )
    m2_bot = repo.add_message(
        session_id=s1_id,
        role="assistant",
        content=(
            "Báo cáo chi tiết về 2 chuyến đi bị hủy của tài xế **Trần Văn Bình**:\n\n"
            "1. **Chi tiết 2 chuyến bị hủy trong kỳ:**\n"
            "   - **Chuyến 1:** Chuyến đi ngày 02/09/2026 (lý do: tắc đường nghiêm trọng không thể tiếp cận điểm đón).\n"
            "   - **Chuyến 2:** Chuyến đi ngày 11/09/2026 (lý do: khách hàng không có mặt sau 10 phút, tài xế xác nhận hủy).\n\n"
            "2. **Quy định khiếu nại theo P154 (Điều 8):**\n"
            "   - Tài xế có quyền gửi khiếu nại trong vòng **48 giờ** kể từ khi phát sinh chuyến hủy thông qua ứng dụng Tài xế Xanh SM hoặc liên hệ trực tiếp Trưởng đội tại Depot Hồ Chí Minh 2 để nhân viên điều hành thụ lý."
        ),
        latency_ms=1420.0,
        created_at="2026-09-17T08:32:03.000000Z",
    )
    # Context memory for Session 1
    repo.set_context_key(s1_id, "driver_id", "c499f934-bfe1-5509-a578-afb09cee357c", confidence=1.0, driver_id="c499f934-bfe1-5509-a578-afb09cee357c")
    repo.set_context_key(s1_id, "driver_code", "DRV-002", confidence=1.0, driver_id="c499f934-bfe1-5509-a578-afb09cee357c")
    repo.set_context_key(s1_id, "driver_name", "Trần Văn Bình", confidence=1.0, driver_id="c499f934-bfe1-5509-a578-afb09cee357c")
    repo.set_context_key(s1_id, "time_scope", "tháng 9/2026", confidence=0.95)
    repo.set_context_key(s1_id, "snapshot_id", "d4cc0438-d831-541a-8123-ddda94ccdac8", confidence=1.0)
    repo.set_context_key(s1_id, "policy_scope", "P154", confidence=0.95)
    repo.set_context_key(s1_id, "last_intent", "HYBRID_REASONING", confidence=0.9)

    # Session 2: Tra cứu thuần quy chế P154
    s2_id = "session-002-policy-p154"
    repo.create_session(
        session_id=s2_id,
        title="Tra cứu Quy chế P154 - Tiêu chuẩn đánh giá sao",
    )
    repo.add_message(
        session_id=s2_id,
        role="user",
        content="Theo quy chế P154 của GSM, tiêu chuẩn đánh giá sao và quy định tính điểm chuyến đi chưa đánh giá được quy định thế nào?",
        created_at="2026-09-16T15:10:00.000000Z",
    )
    repo.add_message(
        session_id=s2_id,
        role="assistant",
        content=(
            "Căn cứ theo văn bản **Quy chế P154** của Công ty GSM (Taxi Xanh SM):\n\n"
            "1. **Tiêu chuẩn đánh giá sao trung bình:**\n"
            "   - Điểm đánh giá chất lượng dịch vụ của tài xế được tính trên thang điểm **1 đến 5 sao** từ phản hồi của hành khách.\n"
            "   - Ngưỡng đạt chuẩn duy trì vận doanh là điểm sao trung bình **≥ 4.85 sao** trong chu kỳ đánh giá.\n\n"
            "2. **Quy định đối với chuyến đi hành khách KHÔNG đánh giá:**\n"
            "   - Sau khi kết thúc chuyến đi 24 giờ, nếu khách hàng không gửi đánh giá sao, hệ thống sẽ tự động ghi nhận **5.0 sao mặc định** cho chuyến đi đó."
        ),
        query_plan={
            "intent": "POLICY_RETRIEVAL",
            "driver_id": None,
            "driver_mention": None,
            "time_scope": None,
            "snapshot_id": "d4cc0438-d831-541a-8123-ddda94ccdac8",
            "policy_scope": "P154",
            "missing_fields": [],
            "reasoning": "Tra cứu BM25 thuần túy từ kho văn bản quy chế GSM.",
        },
        citations=[
            {"locator": "policy:P154#sec-3.1", "content": "Điều 3: Điểm đánh giá trung bình chuẩn của tài xế đạt tối thiểu 4.85 sao."},
            {"locator": "policy:P154#sec-3.4", "content": "Khoản 4: Các chuyến đi không được đánh giá sau 24h được tự động tính 5 sao."},
        ],
        latency_ms=890.0,
        created_at="2026-09-16T15:10:02.000000Z",
    )
    repo.set_context_key(s2_id, "policy_scope", "P154", confidence=1.0)
    repo.set_context_key(s2_id, "last_intent", "POLICY_RETRIEVAL", confidence=0.9)

    # Session 3: Clarification Gate demonstration
    s3_id = "session-003-clarification-gate"
    repo.create_session(
        session_id=s3_id,
        title="Làm rõ thông tin - Yêu cầu mã tài xế và thời gian",
    )
    repo.add_message(
        session_id=s3_id,
        role="user",
        content="Kiểm tra xem tài xế có bị xử phạt do hủy chuyến xe không?",
        created_at="2026-09-15T11:00:00.000000Z",
    )
    repo.add_message(
        session_id=s3_id,
        role="assistant",
        content=(
            "Để hệ thống có thể kiểm tra chính xác xem tài xế có bị vi phạm tiêu chuẩn hủy chuyến hay không, vui lòng cung cấp thêm các thông tin sau:\n\n"
            "1. **Mã tài xế (ID):** Cung cấp mã tài xế cần tra cứu (Ví dụ: `DRV-001`, `DRV-002`, `D1`, hoặc Họ và tên đăng ký).\n"
            "2. **Mốc thời gian:** Kỳ đánh giá cần đối soát (Ví dụ: `tháng 9/2026`, `tháng 8/2026`, hoặc `30 ngày gần nhất`)."
        ),
        query_plan={
            "intent": "HYBRID_REASONING",
            "driver_id": None,
            "driver_mention": None,
            "time_scope": None,
            "missing_fields": ["driver_id", "time_scope"],
            "reasoning": "Yêu cầu tra cứu đối soát vi phạm hủy chuyến nhưng thiếu mã tài xế và mốc thời gian đánh giá.",
        },
        latency_ms=450.0,
        created_at="2026-09-15T11:00:01.000000Z",
    )
    repo.set_context_key(s3_id, "pending_clarification", "driver_id, time_scope", confidence=1.0)
    repo.set_context_key(s3_id, "last_intent", "HYBRID_REASONING", confidence=0.8)

    stats = repo.get_stats()
    print("=" * 70)
    print("🎉 SEED HOÀN TẤT THÀNH CÔNG!")
    print(f"  - Tổng số tài xế:       {stats.drivers_count}")
    print(f"  - Tổng số chuyến đi:    {stats.trips_count} ({stats.completed_trips_count} hoàn thành, {stats.cancelled_trips_count} hủy)")
    print(f"  - Phiên hội thoại:      {stats.chat_sessions_count}")
    print(f"  - Tin nhắn hội thoại:   {stats.chat_messages_count}")
    print(f"  - Mục bộ nhớ ngữ cảnh:  {stats.context_memories_count}")
    print(f"  - Dung lượng file DB:   {stats.db_size_bytes / 1024:.1f} KB")
    print(f"  - Đường dẫn SQLite:     {stats.db_file_path}")
    print("=" * 70)
    return stats


if __name__ == "__main__":
    seed_database()
