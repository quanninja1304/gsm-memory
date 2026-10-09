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
from gsm_memory.db.models import DriverRecord, SnapshotRecord, TripRecord
from gsm_memory.db.repository import LocalDatabaseRepository
from gsm_memory.db.schema import init_schema

# Pinned benchmark snapshots catalog
SNAPSHOTS_SEED_DATA = [
    {
        "snapshot_id": "d4cc0438-d831-541a-8123-ddda94ccdac8",
        "label": "L0 Canonical Baseline (17/09/2026 12:00)",
        "known_as_of": "2026-09-17T12:00:00.000000Z",
        "scope": "Tháng 09/2026 & Toàn bộ 80 chuyến đi (L0)",
        "aliases": [
            "tháng 9", "tháng 09", "tháng 9/2026", "2026-09",
            "30 ngày gần nhất", "30 ngày qua", "30 ngày",
            "kỳ này", "kỳ đánh giá", "hôm nay", "hiện tại", "gần nhất",
            "17/09", "17/09/2026", "snapshot l0"
        ],
        "is_baseline": True,
    },
    {
        "snapshot_id": "25b69c05-6a60-51e3-9209-74e5d49816fa",
        "label": "L0 Cutoff A0 (16/09/2026 12:00)",
        "known_as_of": "2026-09-16T12:00:00.000000Z",
        "scope": "Ngày 16/09/2026 (79 chuyến đi)",
        "aliases": ["16/09", "16/09/2026", "2026-09-16", "hôm qua", "cutoff a0"],
        "is_baseline": False,
    },
    {
        "snapshot_id": "624c0fb1-f1e5-59af-9642-0771d1d2571f",
        "label": "L0 Cutoff AC (17/09/2026 01:00)",
        "known_as_of": "2026-09-17T01:00:00.000000Z",
        "scope": "Sáng sớm 17/09/2026 (80 chuyến đi)",
        "aliases": ["17/09 sáng", "2026-09-17t01", "cutoff ac"],
        "is_baseline": False,
    },
    {
        "snapshot_id": "da177d3f-6b43-52ae-a778-4fa7c6edbbf1",
        "label": "L0 Cutoff 06/08 (06/08/2026)",
        "known_as_of": "2026-08-06T00:00:00.000000Z",
        "scope": "Tháng 08/2026 (Chốt ngày 06/08)",
        "aliases": ["06/08", "06/08/2026", "2026-08-06", "cutoff 06/08"],
        "is_baseline": False,
    },
    {
        "snapshot_id": "d8c98a0b-7b07-50f2-b1ed-9fe102ccc5e6",
        "label": "L0 Cutoff 04/08 (04/08/2026)",
        "known_as_of": "2026-08-04T00:00:00.000000Z",
        "scope": "Đầu tháng 08/2026 (Chốt ngày 04/08)",
        "aliases": ["tháng 8", "tháng 08", "tháng 8/2026", "2026-08", "đầu tháng 8", "04/08", "04/08/2026", "2026-08-04", "tháng trước", "cutoff 04/08"],
        "is_baseline": False,
    },
    # 7 Alternate Benchmark Branches (All known as of 17/09/2026 12:00)
    {
        "snapshot_id": "df057563-78f4-5ac1-aba6-5b48c572fb4a",
        "label": "Branch L_NO_OPDAY (17/09/2026 12:00)",
        "known_as_of": "2026-09-17T12:00:00.000000Z",
        "scope": "Nhánh đối chứng thiếu ngày vận hành (L_NO_OPDAY)",
        "aliases": ["l_no_opday", "no_opday", "thiếu ngày vận hành", "nhánh thiếu ngày vận hành", "snapshot no opday"],
        "is_baseline": False,
    },
    {
        "snapshot_id": "d644104b-2ae9-54e3-b07f-ed1cefe897f1",
        "label": "Branch L_WRONG_DRIVER (17/09/2026 12:00)",
        "known_as_of": "2026-09-17T12:00:00.000000Z",
        "scope": "Nhánh đối chứng sai định danh tài xế (L_WRONG_DRIVER)",
        "aliases": ["l_wrong_driver", "wrong_driver", "sai tài xế", "nhánh sai tài xế", "snapshot wrong driver"],
        "is_baseline": False,
    },
    {
        "snapshot_id": "6c606951-1fbd-586a-bf9b-51faafb07a24",
        "label": "Branch L_CONFLICT (17/09/2026 12:00)",
        "known_as_of": "2026-09-17T12:00:00.000000Z",
        "scope": "Nhánh đối chứng xung đột dữ liệu (L_CONFLICT)",
        "aliases": ["l_conflict", "conflict", "xung đột", "xung đột dữ liệu", "nhánh xung đột", "snapshot conflict"],
        "is_baseline": False,
    },
    {
        "snapshot_id": "296f03c2-6abf-57b3-8a17-249486d98fe8",
        "label": "Branch L_RETRACT (17/09/2026 12:00)",
        "known_as_of": "2026-09-17T12:00:00.000000Z",
        "scope": "Nhánh đối chứng rút lại dữ liệu (L_RETRACT)",
        "aliases": ["l_retract", "retract", "rút lại", "rút lại dữ liệu", "nhánh rút lại", "snapshot retract"],
        "is_baseline": False,
    },
    {
        "snapshot_id": "ff172ebe-4740-54d3-a235-e819dc21c959",
        "label": "Branch L_WRONG_WINDOW (17/09/2026 12:00)",
        "known_as_of": "2026-09-17T12:00:00.000000Z",
        "scope": "Nhánh đối chứng sai cửa sổ thời gian (L_WRONG_WINDOW)",
        "aliases": ["l_wrong_window", "wrong_window", "sai cửa sổ", "sai cửa sổ thời gian", "nhánh sai cửa sổ", "snapshot wrong window"],
        "is_baseline": False,
    },
    {
        "snapshot_id": "f70bbf42-f1ec-5bcf-b8d3-8a7b53086076",
        "label": "Branch L_NO_BRIDGE (17/09/2026 12:00)",
        "known_as_of": "2026-09-17T12:00:00.000000Z",
        "scope": "Nhánh đối chứng thiếu liên kết bắc cầu (L_NO_BRIDGE)",
        "aliases": ["l_no_bridge", "no_bridge", "thiếu cầu nối", "nhánh thiếu cầu nối", "snapshot no bridge"],
        "is_baseline": False,
    },
    {
        "snapshot_id": "688de316-96de-59b6-9c70-3d4745aba76f",
        "label": "Branch L_NO_COVERAGE (17/09/2026 12:00)",
        "known_as_of": "2026-09-17T12:00:00.000000Z",
        "scope": "Nhánh đối chứng thiếu độ phủ dữ liệu (L_NO_COVERAGE)",
        "aliases": ["l_no_coverage", "no_coverage", "thiếu độ phủ", "nhánh thiếu độ phủ", "snapshot no coverage"],
        "is_baseline": False,
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

    # 2. SEED 80 BENCHMARK TRIPS FROM RECORD_LEDGER.PARQUET
    ledger_path = ROOT_DIR / "data" / "gsm-dev-core-0.2.2" / "public" / "operational" / "record_ledger.parquet"
    benchmark_trips_count = 0

    if ledger_path.exists():
        print("  🚕 Importing 80 canonical terminal trips from ledger...")
        table = pq.read_table(str(ledger_path))
        for row in table["assertions"].to_pylist():
            for a in row:
                if a.get("predicate") == "TRIP_OUTCOME":
                    q = a.get("qualifiers", {})
                    trip_id = q.get("trip_id")
                    raw_driver_id = a.get("subject_id")
                    driver_id = DRIVER_ID_ALIASES.get(raw_driver_id, raw_driver_id)
                    outcome = q.get("outcome", "completed")
                    reason_code = q.get("reason_code", "unspecified")
                    event_time = a.get("event_time") or "2026-09-01T08:00:00.000000Z"

                    # Realistic route selection based on driver
                    route = ROUTES_HN[benchmark_trips_count % len(ROUTES_HN)] if "Hà Nội" in str(driver_id) or benchmark_trips_count % 5 == 0 else ROUTES_HCM[benchmark_trips_count % len(ROUTES_HCM)]
                    pickup, dropoff, dist, fare = route

                    is_cancelled = outcome == "cancelled"
                    cancel_party = "driver" if is_cancelled else "none"
                    rating = None if is_cancelled else random.choice([5, 5, 5, 4])
                    feedback = None if is_cancelled else random.choice(FEEDBACK_GOOD)
                    notes = "Chuyến xe bị hủy theo yêu cầu tài xế" if is_cancelled else "Hoàn thành tốt"

                    # Calculate end time (~20 - 45 mins after start)
                    try:
                        st_dt = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
                    except Exception:
                        st_dt = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
                    end_dt = st_dt + timedelta(minutes=int(dist * 2.5) + 10)

                    t_rec = TripRecord(
                        trip_id=trip_id,
                        driver_id=driver_id,
                        snapshot_id="d4cc0438-d831-541a-8123-ddda94ccdac8",
                        start_time=st_dt.isoformat(),
                        end_time=end_dt.isoformat(),
                        pickup_address=pickup,
                        dropoff_address=dropoff,
                        region="TP.HCM" if "TP.HCM" in dropoff or "Quận" in dropoff else "Hà Nội",
                        service_type="Taxi Xanh SM",
                        distance_km=dist,
                        fare_amount=fare if not is_cancelled else 0,
                        outcome="cancelled" if is_cancelled else "completed",
                        reason_code=reason_code,
                        cancel_party=cancel_party,
                        passenger_rating=rating,
                        passenger_feedback=feedback,
                        notes=notes,
                        created_at=st_dt.isoformat(),
                    )
                    repo.upsert_trip(t_rec)
                    benchmark_trips_count += 1

    print(f"  ✅ Imported {benchmark_trips_count} benchmark trips.")

    # 3. SUPPLEMENTARY REALISTIC TRIPS FOR FULL COMPREHENSIVE COVERAGE
    print("  🚗 Generating supplementary trips for August & September 2026...")
    supp_count = 0
    base_dates = [
        datetime(2026, 8, 10, 7, 30, tzinfo=timezone.utc),
        datetime(2026, 8, 15, 9, 15, tzinfo=timezone.utc),
        datetime(2026, 8, 20, 11, 45, tzinfo=timezone.utc),
        datetime(2026, 8, 25, 14, 20, tzinfo=timezone.utc),
        datetime(2026, 8, 30, 17, 10, tzinfo=timezone.utc),
        datetime(2026, 9, 2, 8, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 5, 10, 30, tzinfo=timezone.utc),
        datetime(2026, 9, 8, 13, 15, tzinfo=timezone.utc),
        datetime(2026, 9, 11, 16, 45, tzinfo=timezone.utc),
        datetime(2026, 9, 14, 19, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 16, 8, 30, tzinfo=timezone.utc),
    ]

    for d_info in DRIVERS_SEED_DATA:
        d_id = d_info["driver_id"]
        # Generate 10-15 trips per driver
        routes_pool = ROUTES_HN if d_info["region"] == "Hà Nội" else ROUTES_HCM
        for i, dt in enumerate(base_dates):
            t_id = f"trip-supp-{d_info['driver_code'].lower()}-{i+1:03d}"
            route = routes_pool[i % len(routes_pool)]
            pickup, dropoff, dist, fare = route

            trip_start = dt + timedelta(hours=i % 4, minutes=random.randint(0, 30))
            trip_end = trip_start + timedelta(minutes=int(dist * 2.8) + 8)

            supp_snap = "d8c98a0b-7b07-50f2-b1ed-9fe102ccc5e6" if trip_start.month == 8 else "d4cc0438-d831-541a-8123-ddda94ccdac8"
            t_rec = TripRecord(
                trip_id=t_id,
                driver_id=d_id,
                snapshot_id=supp_snap,
                start_time=trip_start.isoformat(),
                end_time=trip_end.isoformat(),
                pickup_address=pickup,
                dropoff_address=dropoff,
                region=d_info["region"],
                service_type=d_info["service_type"],
                distance_km=dist,
                fare_amount=fare,
                outcome="completed",
                reason_code="completed_normal",
                cancel_party="none",
                passenger_rating=5 if i % 4 != 0 else 4,
                passenger_feedback=random.choice(FEEDBACK_GOOD),
                notes="Chuyến đi vận hành tiêu chuẩn",
                created_at=trip_start.isoformat(),
            )
            repo.upsert_trip(t_rec)
            supp_count += 1

    print(f"  ✅ Added {supp_count} supplementary trips.")

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
