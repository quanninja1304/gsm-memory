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


def generate_v2_operational_data() -> dict[str, list[dict[str, Any]]]:
    """Generate deterministic, high-fidelity July 2025 operational dataset for V2 ontology.
    
    Contains 5 distinct drivers, 5 electric vehicles, 4 hubs, 6 zones, shifts,
    trips, maintenance events, incidents, customer complaints, policy rules, and reward/penalties.
    """
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    def add_node(label: str, node_id: str, props: dict[str, Any]) -> None:
        nodes.append({
            "label": label,
            "id": node_id,
            "props": {
                "id": node_id,
                "snapshot_id": SNAPSHOT_ID,
                **props,
            },
        })

    def add_edge(
        rel_type: str,
        start_label: str,
        start_id: str,
        end_label: str,
        end_id: str,
        props: dict[str, Any] | None = None,
    ) -> None:
        p = props or {}
        edges.append({
            "type": rel_type,
            "start_label": start_label,
            "start_id": start_id,
            "end_label": end_label,
            "end_id": end_id,
            "props": {
                "snapshot_id": SNAPSHOT_ID,
                **p,
            },
        })

    # =========================================================================
    # 1. CORE ENTITIES: HUBS
    # =========================================================================
    hubs = [
        {
            "id": "v2_hub_caugiay",
            "hub_id": "v2_hub_caugiay",
            "name": "Hub Cầu Giấy (Đội Xanh 1)",
            "supervisor_name": "Lê Hoàng Long",
            "region": "Miền Bắc - Hà Nội",
            "address": "Số 8 Phạm Hùng, Cầu Giấy, Hà Nội",
            "zone_id": "v2_zone_caugiay",
            "managed_vehicles": ["v2_veh_001", "v2_veh_005"],
        },
        {
            "id": "v2_hub_longbien",
            "hub_id": "v2_hub_longbien",
            "name": "Hub Long Biên (Đội Xanh 2)",
            "supervisor_name": "Nguyễn Minh Tuấn",
            "region": "Miền Bắc - Hà Nội",
            "address": "Vinhomes Riverside, Long Biên, Hà Nội",
            "zone_id": "v2_zone_hoankiem",
            "managed_vehicles": ["v2_veh_002"],
        },
        {
            "id": "v2_hub_quan7",
            "hub_id": "v2_hub_quan7",
            "name": "Hub Quận 7 (Đội Xanh Nam Sài Gòn)",
            "supervisor_name": "Phạm Văn Thành",
            "region": "Miền Nam - TP. Hồ Chí Minh",
            "address": "Đại lộ Nguyễn Văn Linh, Quận 7, TP.HCM",
            "zone_id": "v2_zone_thuduc",
            "managed_vehicles": ["v2_veh_003"],
        },
        {
            "id": "v2_hub_tanbinh",
            "hub_id": "v2_hub_tanbinh",
            "name": "Hub Tân Bình (Đội Xanh Tân Sơn Nhất)",
            "supervisor_name": "Võ Quốc Huy",
            "region": "Miền Nam - TP. Hồ Chí Minh",
            "address": "Đường Hoàng Văn Thụ, Tân Bình, TP.HCM",
            "zone_id": "v2_zone_tansonnhat",
            "managed_vehicles": ["v2_veh_004"],
        },
    ]
    for h in hubs:
        h_props = {k: v for k, v in h.items() if k not in ("zone_id", "managed_vehicles")}
        add_node("Hub", h["id"], h_props)
        add_edge("LOCATED_IN", "Hub", h["id"], "Zone", h["zone_id"])
        for v_id in h["managed_vehicles"]:
            add_edge("MANAGES_VEHICLE", "Hub", h["id"], "Vehicle", v_id)

    # =========================================================================
    # 2. CORE ENTITIES: ZONES
    # =========================================================================
    zones = [
        {
            "id": "v2_zone_noibai",
            "zone_id": "v2_zone_noibai",
            "zone_name": "Khu vực Sân bay Nội Bài",
            "city": "Hà Nội",
            "risk_level": "medium",
            "traffic_profile": "airport_congestion_and_high_speed_expressway",
        },
        {
            "id": "v2_zone_hoankiem",
            "zone_id": "v2_zone_hoankiem",
            "zone_name": "Khu vực Phố cổ & Trung tâm Hoàn Kiếm",
            "city": "Hà Nội",
            "risk_level": "high",
            "traffic_profile": "narrow_dense_alleys_and_pedestrian_zones",
        },
        {
            "id": "v2_zone_caugiay",
            "zone_id": "v2_zone_caugiay",
            "zone_name": "Khu đô thị & Công nghệ Cầu Giấy",
            "city": "Hà Nội",
            "risk_level": "medium",
            "traffic_profile": "heavy_traffic_peak_hours",
        },
        {
            "id": "v2_zone_tansonnhat",
            "zone_id": "v2_zone_tansonnhat",
            "zone_name": "Khu vực Sân bay Tân Sơn Nhất",
            "city": "TP. Hồ Chí Minh",
            "risk_level": "high",
            "traffic_profile": "airport_congestion_and_ring_road_traffic",
        },
        {
            "id": "v2_zone_quan1",
            "zone_id": "v2_zone_quan1",
            "zone_name": "Khu vực Trung tâm Quận 1",
            "city": "TP. Hồ Chí Minh",
            "risk_level": "high",
            "traffic_profile": "heavy_traffic_peak_hours_and_one_way_streets",
        },
        {
            "id": "v2_zone_thuduc",
            "zone_id": "v2_zone_thuduc",
            "zone_name": "Khu đô thị Sáng tạo Thủ Đức",
            "city": "TP. Hồ Chí Minh",
            "risk_level": "low",
            "traffic_profile": "wide_boulevards_and_highway_connectors",
        },
    ]
    for z in zones:
        add_node("Zone", z["id"], z)

    # =========================================================================
    # 3. CORE ENTITIES: VEHICLES
    # =========================================================================
    vehicles = [
        {
            "id": "v2_veh_001",
            "vehicle_id": "v2_veh_001",
            "plate_number": "29E-888.12",
            "model": "VinFast VF 8",
            "vehicle_type": "electric_suv",
            "battery_health": 98.2,
            "fuel_type": "electric",
            "odometer_km": 20450,
        },
        {
            "id": "v2_veh_002",
            "vehicle_id": "v2_veh_002",
            "plate_number": "29E-666.89",
            "model": "VinFast VF e34",
            "vehicle_type": "electric_car",
            "battery_health": 92.5,
            "fuel_type": "electric",
            "odometer_km": 35200,
        },
        {
            "id": "v2_veh_003",
            "vehicle_id": "v2_veh_003",
            "plate_number": "51K-777.33",
            "model": "VinFast VF 5 Plus",
            "vehicle_type": "electric_car",
            "battery_health": 96.0,
            "fuel_type": "electric",
            "odometer_km": 14800,
        },
        {
            "id": "v2_veh_004",
            "vehicle_id": "v2_veh_004",
            "plate_number": "51K-444.11",
            "model": "VinFast VF e34",
            "vehicle_type": "electric_car",
            "battery_health": 89.0,
            "fuel_type": "electric",
            "odometer_km": 41300,
        },
        {
            "id": "v2_veh_005",
            "vehicle_id": "v2_veh_005",
            "plate_number": "29MD-123.45",
            "model": "VinFast Feliz S",
            "vehicle_type": "electric_bike",
            "battery_health": 97.5,
            "fuel_type": "electric",
            "odometer_km": 8900,
        },
    ]
    for v in vehicles:
        add_node("Vehicle", v["id"], v)

    # =========================================================================
    # 4. POLICIES & ASSESSMENTS: POLICY RULES
    # =========================================================================
    policy_rules = [
        {
            "id": "v2_rule_p154",
            "rule_id": "RULE-P154-CANCEL",
            "rule_name": "Quy chế P154 - Giới hạn tỷ lệ hủy chuyến",
            "threshold_description": "Tỷ lệ hủy chuyến chủ động trong chu kỳ tháng vượt quá 15% hoặc hủy giờ cao điểm bất thường > 3 cuốc liên tiếp",
            "penalty_action": "Cảnh cáo văn bản, phạt 500,000 VND và tạm đình chỉ tài khoản nếu tái phạm",
        },
        {
            "id": "v2_rule_p151",
            "rule_id": "RULE-P151-ACCEPT",
            "rule_name": "Quy chế P151 - Tiêu chuẩn tỷ lệ nhận cuốc",
            "threshold_description": "Tỷ lệ chấp nhận cuốc xe (AR) trong chu kỳ tháng đạt dưới 85%",
            "penalty_action": "Hạ bậc ưu tiên phát cuốc và nhắc nhở đào tạo lại quy trình vận hành",
        },
        {
            "id": "v2_rule_safety_speed",
            "rule_id": "RULE-SAFETY-SPEED",
            "rule_name": "Quy chuẩn An toàn Vận hành & Giới hạn Tốc độ",
            "threshold_description": "Vượt quá tốc độ quy định trên 20km/h ghi nhận từ thiết bị viễn thông Telematics IoT",
            "penalty_action": "Tạm khóa tài khoản 3 ngày, trừ điểm an toàn và yêu cầu thi sát hạch an toàn",
        },
        {
            "id": "v2_rule_p23_attitude",
            "rule_id": "RULE-P23-ATTITUDE",
            "rule_name": "Quy chế P23 - Quy tắc ứng xử và Văn hóa phục vụ GSM",
            "threshold_description": "Khách hàng phản ánh thái độ gắt gỏng, lái xe ẩu hoặc thu sai tiền cước được thẩm định là đúng",
            "penalty_action": "Phạt tiền bồi hoàn cho khách, cảnh cáo văn bản và hạ xếp hạng sao tài xế",
        },
    ]
    for r in policy_rules:
        add_node("PolicyRule", r["id"], r)

    # =========================================================================
    # 5. CORE ENTITIES: DRIVERS
    # =========================================================================
    drivers = [
        {
            "id": "v2_drv_001",
            "driver_id": "v2_drv_001",
            "driver_code": "DRV-V2-001",
            "name": "Trần Quốc Toản",
            "phone": "0901888001",
            "email": "toan.tq@gsm.vn",
            "onboarding_date": "2024-03-15",
            "tier_level": "Kim Cương",
            "rating_avg": 4.95,
            "status": "active",
            "hub_id": "v2_hub_caugiay",
            "vehicle_id": "v2_veh_001",
            "frequent_zones": [
                ("v2_zone_noibai", 0.65, "morning_rush_hour"),
                ("v2_zone_hoankiem", 0.35, "afternoon_rush_hour"),
            ],
        },
        {
            "id": "v2_drv_002",
            "driver_id": "v2_drv_002",
            "driver_code": "DRV-V2-002",
            "name": "Lê Văn Hùng",
            "phone": "0901888002",
            "email": "hung.lv@gsm.vn",
            "onboarding_date": "2024-08-20",
            "tier_level": "Bạc",
            "rating_avg": 4.42,
            "status": "active",
            "hub_id": "v2_hub_longbien",
            "vehicle_id": "v2_veh_002",
            "frequent_zones": [
                ("v2_zone_hoankiem", 0.70, "all_day"),
            ],
        },
        {
            "id": "v2_drv_003",
            "driver_id": "v2_drv_003",
            "driver_code": "DRV-V2-003",
            "name": "Nguyễn Hoàng Nam",
            "phone": "0901888003",
            "email": "nam.nh@gsm.vn",
            "onboarding_date": "2024-05-10",
            "tier_level": "Vàng",
            "rating_avg": 4.82,
            "status": "active",
            "hub_id": "v2_hub_quan7",
            "vehicle_id": "v2_veh_003",
            "frequent_zones": [
                ("v2_zone_quan1", 0.55, "morning_rush_hour"),
                ("v2_zone_thuduc", 0.45, "evening"),
            ],
        },
        {
            "id": "v2_drv_004",
            "driver_id": "v2_drv_004",
            "driver_code": "DRV-V2-004",
            "name": "Phạm Thị Mai",
            "phone": "0901888004",
            "email": "mai.pt@gsm.vn",
            "onboarding_date": "2025-02-01",
            "tier_level": "Tiêu chuẩn",
            "rating_avg": 4.15,
            "status": "suspended",
            "hub_id": "v2_hub_tanbinh",
            "vehicle_id": "v2_veh_004",
            "frequent_zones": [
                ("v2_zone_tansonnhat", 0.60, "morning_rush_hour"),
                ("v2_zone_quan1", 0.40, "afternoon_rush_hour"),
            ],
        },
        {
            "id": "v2_drv_005",
            "driver_id": "v2_drv_005",
            "driver_code": "DRV-V2-005",
            "name": "Đặng Văn Phúc",
            "phone": "0901888005",
            "email": "phuc.dv@gsm.vn",
            "onboarding_date": "2024-11-15",
            "tier_level": "Vàng",
            "rating_avg": 4.88,
            "status": "active",
            "hub_id": "v2_hub_caugiay",
            "vehicle_id": "v2_veh_005",
            "frequent_zones": [
                ("v2_zone_caugiay", 0.80, "all_day"),
            ],
        },
    ]

    for d in drivers:
        d_props = {k: v for k, v in d.items() if k not in ("hub_id", "vehicle_id", "frequent_zones")}
        add_node("Driver", d["id"], d_props)

        # Edge: Driver -> Vehicle
        add_edge(
            "OPERATES", "Driver", d["id"], "Vehicle", d["vehicle_id"],
            {"assigned_date": d["onboarding_date"], "is_primary": True},
        )
        # Edge: Driver -> Hub
        add_edge(
            "BELONGS_TO", "Driver", d["id"], "Hub", d["hub_id"],
            {"joined_date": d["onboarding_date"]},
        )
        # Edge: Driver -> Zone (Frequently Operates In)
        for zone_id, ratio, time_slot in d.get("frequent_zones", []):
            add_edge(
                "FREQUENTLY_OPERATES_IN", "Driver", d["id"], "Zone", zone_id,
                {"operating_ratio": ratio, "time_slot": time_slot},
            )

    # =========================================================================
    # 6. OPERATIONS: SHIFTS & TRIPS (THÁNG 07/2025)
    # =========================================================================
    shifts = [
        # Driver 1 (Trần Quốc Toản - Xuất sắc)
        {
            "id": "v2_shift_001_1",
            "shift_id": "v2_shift_001_1",
            "driver_id": "v2_drv_001",
            "date": "2025-07-15",
            "start_time": "2025-07-15T06:00:00Z",
            "end_time": "2025-07-15T15:30:00Z",
            "total_online_hours": 9.5,
            "acceptance_rate": 0.98,
            "completion_rate": 1.0,
        },
        # Driver 2 (Lê Văn Hùng - Hủy chuyến nhiều)
        {
            "id": "v2_shift_002_1",
            "shift_id": "v2_shift_002_1",
            "driver_id": "v2_drv_002",
            "date": "2025-07-20",
            "start_time": "2025-07-20T07:00:00Z",
            "end_time": "2025-07-20T17:00:00Z",
            "total_online_hours": 10.0,
            "acceptance_rate": 0.81,
            "completion_rate": 0.82,
        },
        # Driver 3 (Nguyễn Hoàng Nam - Tốt)
        {
            "id": "v2_shift_003_1",
            "shift_id": "v2_shift_003_1",
            "driver_id": "v2_drv_003",
            "date": "2025-07-12",
            "start_time": "2025-07-12T08:00:00Z",
            "end_time": "2025-07-12T17:00:00Z",
            "total_online_hours": 9.0,
            "acceptance_rate": 0.94,
            "completion_rate": 0.98,
        },
        # Driver 4 (Phạm Thị Mai - Vi phạm an toàn & khiếu nại)
        {
            "id": "v2_shift_004_1",
            "shift_id": "v2_shift_004_1",
            "driver_id": "v2_drv_004",
            "date": "2025-07-18",
            "start_time": "2025-07-18T09:00:00Z",
            "end_time": "2025-07-18T18:00:00Z",
            "total_online_hours": 9.0,
            "acceptance_rate": 0.88,
            "completion_rate": 0.91,
        },
        # Driver 5 (Đặng Văn Phúc - Xe máy Feliz S)
        {
            "id": "v2_shift_005_1",
            "shift_id": "v2_shift_005_1",
            "driver_id": "v2_drv_005",
            "date": "2025-07-22",
            "start_time": "2025-07-22T07:00:00Z",
            "end_time": "2025-07-22T18:00:00Z",
            "total_online_hours": 11.0,
            "acceptance_rate": 0.97,
            "completion_rate": 1.0,
        },
    ]

    for s in shifts:
        s_props = {k: v for k, v in s.items() if k != "driver_id"}
        add_node("Shift", s["id"], s_props)
        add_edge("WORKS_SHIFT", "Driver", s["driver_id"], "Shift", s["id"], {"date": s["date"]})

    trips = [
        # Driver 1: Sân bay Nội Bài -> Hoàn Kiếm (Completed)
        {
            "id": "v2_trip_001_1",
            "trip_id": "v2_trip_001_1",
            "driver_id": "v2_drv_001",
            "shift_id": "v2_shift_001_1",
            "vehicle_id": "v2_veh_001",
            "fare": 295000,
            "distance_km": 28.0,
            "duration_min": 42,
            "status": "completed",
            "pickup_zone_id": "v2_zone_noibai",
            "dropoff_zone_id": "v2_zone_hoankiem",
            "timestamp": "2025-07-15T08:15:00Z",
        },
        # Driver 2: Hoàn Kiếm (Cancelled by driver - peak hour)
        {
            "id": "v2_trip_002_1",
            "trip_id": "v2_trip_002_1",
            "driver_id": "v2_drv_002",
            "shift_id": "v2_shift_002_1",
            "vehicle_id": "v2_veh_002",
            "fare": 85000,
            "distance_km": 5.2,
            "duration_min": 0,
            "status": "cancelled_by_driver",
            "pickup_zone_id": "v2_zone_hoankiem",
            "dropoff_zone_id": "v2_zone_hoankiem",
            "timestamp": "2025-07-20T08:30:00Z",
        },
        # Driver 3: Quận 1 -> Thủ Đức (Completed)
        {
            "id": "v2_trip_003_1",
            "trip_id": "v2_trip_003_1",
            "driver_id": "v2_drv_003",
            "shift_id": "v2_shift_003_1",
            "vehicle_id": "v2_veh_003",
            "fare": 165000,
            "distance_km": 14.5,
            "duration_min": 32,
            "status": "completed",
            "pickup_zone_id": "v2_zone_quan1",
            "dropoff_zone_id": "v2_zone_thuduc",
            "timestamp": "2025-07-12T10:00:00Z",
        },
        # Driver 4: Tân Sơn Nhất -> Quận 1 (Completed with complaint & reckless speed)
        {
            "id": "v2_trip_004_1",
            "trip_id": "v2_trip_004_1",
            "driver_id": "v2_drv_004",
            "shift_id": "v2_shift_004_1",
            "vehicle_id": "v2_veh_004",
            "fare": 190000,
            "distance_km": 11.2,
            "duration_min": 26,
            "status": "completed",
            "pickup_zone_id": "v2_zone_tansonnhat",
            "dropoff_zone_id": "v2_zone_quan1",
            "timestamp": "2025-07-18T10:10:00Z",
        },
        # Driver 5: Cầu Giấy (Completed - 2 bánh)
        {
            "id": "v2_trip_005_1",
            "trip_id": "v2_trip_005_1",
            "driver_id": "v2_drv_005",
            "shift_id": "v2_shift_005_1",
            "vehicle_id": "v2_veh_005",
            "fare": 35000,
            "distance_km": 4.8,
            "duration_min": 16,
            "status": "completed",
            "pickup_zone_id": "v2_zone_caugiay",
            "dropoff_zone_id": "v2_zone_caugiay",
            "timestamp": "2025-07-22T08:45:00Z",
        },
    ]

    for t in trips:
        t_props = {
            k: v for k, v in t.items()
            if k not in ("driver_id", "shift_id", "vehicle_id", "pickup_zone_id", "dropoff_zone_id", "timestamp")
        }
        add_node("Trip", t["id"], t_props)

        # Edge: Driver -> Trip
        add_edge("SERVED_TRIP", "Driver", t["driver_id"], "Trip", t["id"], {"role": "primary_driver"})
        # Edge: Shift -> Trip (Trip occurs during Shift)
        add_edge("CONTAINS_TRIP", "Shift", t["shift_id"], "Trip", t["id"], {"timestamp": t["timestamp"]})
        # Edge: Trip -> Vehicle (Trip uses Vehicle)
        add_edge("USES_VEHICLE", "Trip", t["id"], "Vehicle", t["vehicle_id"])
        # Edge: Trip -> Zone (Pickup & Dropoff)
        add_edge("PICKUP_IN", "Trip", t["id"], "Zone", t["pickup_zone_id"], {"timestamp": t["timestamp"]})
        add_edge("DROPOFF_IN", "Trip", t["id"], "Zone", t["dropoff_zone_id"], {"timestamp": t["timestamp"]})

    # =========================================================================
    # 7. MAINTENANCE EVENTS (Covers all 5 vehicles)
    # =========================================================================
    maint_events = [
        {
            "id": "v2_maint_001",
            "event_id": "v2_maint_001",
            "vehicle_id": "v2_veh_001",
            "type": "battery_health_and_20k_km_check",
            "date": "2025-07-10",
            "cost": 1200000,
            "status": "completed",
            "description": "Bảo dưỡng định kỳ 20,000km và cân bằng điện áp pack pin VinFast VF 8",
            "odometer_km": 20100,
        },
        {
            "id": "v2_maint_002",
            "event_id": "v2_maint_002",
            "vehicle_id": "v2_veh_002",
            "type": "periodic_35k_check",
            "date": "2025-07-08",
            "cost": 1450000,
            "status": "completed",
            "description": "Kiểm tra động cơ điện và bảo dưỡng hệ thống phanh tái sinh VF e34",
            "odometer_km": 35100,
        },
        {
            "id": "v2_maint_003",
            "event_id": "v2_maint_003",
            "vehicle_id": "v2_veh_003",
            "type": "brake_pad_replacement",
            "date": "2025-07-14",
            "cost": 850000,
            "status": "completed",
            "description": "Thay má phanh trước và kiểm tra hệ thống tái sinh năng lượng VF 5 Plus",
            "odometer_km": 14500,
        },
        {
            "id": "v2_maint_004",
            "event_id": "v2_maint_004",
            "vehicle_id": "v2_veh_004",
            "type": "battery_and_ac_inspection",
            "date": "2025-07-16",
            "cost": 1100000,
            "status": "completed",
            "description": "Kiểm tra hệ thống điều hòa nhiệt độ và sức khỏe cell pin xe VF e34",
            "odometer_km": 41100,
        },
        {
            "id": "v2_maint_005",
            "event_id": "v2_maint_005",
            "vehicle_id": "v2_veh_005",
            "type": "periodic_10k_km_check",
            "date": "2025-07-25",
            "cost": 320000,
            "status": "completed",
            "description": "Bảo dưỡng định kỳ 10,000km và kiểm tra động cơ Inhub xe Feliz S",
            "odometer_km": 8800,
        },
    ]
    for m in maint_events:
        m_props = {k: v for k, v in m.items() if k not in ("vehicle_id", "odometer_km")}
        add_node("MaintenanceEvent", m["id"], m_props)
        add_edge("UNDERWENT", "Vehicle", m["vehicle_id"], "MaintenanceEvent", m["id"], {"odometer_km": m["odometer_km"]})

    # =========================================================================
    # 8. INCIDENTS & VIOLATIONS
    # =========================================================================
    incidents = [
        # Sự cố của Driver 2: Hủy chuyến bất thường giờ cao điểm
        {
            "id": "v2_inc_001",
            "incident_id": "v2_inc_001",
            "driver_id": "v2_drv_002",
            "shift_id": "v2_shift_002_1",
            "type": "abnormal_cancellation",
            "timestamp": "2025-07-20T08:35:00Z",
            "severity": "medium",
            "description": "Hủy 3 cuốc liên tiếp vào khung giờ cao điểm sáng tại khu vực Hoàn Kiếm không lý do chính đáng",
            "fault_rate": 100,
            "penalty_points": 5,
            "violates_rules": ["v2_rule_p154"],
            "detected_by": "system_dispatch_audit",
        },
        # Sự cố của Driver 4: Chạy quá tốc độ trên đường Hoàng Văn Thụ
        {
            "id": "v2_inc_002",
            "incident_id": "v2_inc_002",
            "driver_id": "v2_drv_004",
            "shift_id": "v2_shift_004_1",
            "type": "overspeeding",
            "timestamp": "2025-07-18T10:15:00Z",
            "severity": "high",
            "description": "Chạy quá tốc độ 82km/h tại đoạn đường đô thị giới hạn 50km/h trên tuyến sân bay Tân Sơn Nhất",
            "fault_rate": 100,
            "penalty_points": 10,
            "violates_rules": ["v2_rule_safety_speed", "v2_rule_p23_attitude"],
            "detected_by": "telematics_iot_sensor",
        },
    ]

    for inc in incidents:
        inc_props = {
            k: v for k, v in inc.items()
            if k not in ("driver_id", "shift_id", "fault_rate", "penalty_points", "violates_rules", "detected_by")
        }
        add_node("Incident", inc["id"], inc_props)

        # Edge: Driver -> Incident
        add_edge(
            "INVOLVED_IN", "Driver", inc["driver_id"], "Incident", inc["id"],
            {"fault_rate": inc["fault_rate"], "penalty_points": inc["penalty_points"]},
        )
        # Edge: Incident -> Shift (Occurred during Shift)
        add_edge("OCCURRED_IN", "Incident", inc["id"], "Shift", inc["shift_id"])
        # Edge: Incident -> PolicyRule (Can violate multiple rules)
        for r_id in inc["violates_rules"]:
            add_edge(
                "VIOLATES", "Incident", inc["id"], "PolicyRule", r_id,
                {"detected_by": inc["detected_by"]},
            )

    # =========================================================================
    # 9. CUSTOMER COMPLAINTS
    # =========================================================================
    complaints = [
        {
            "id": "v2_comp_001",
            "complaint_id": "v2_comp_001",
            "trip_id": "v2_trip_004_1",
            "escalated_to_incident_id": "v2_inc_002",
            "violates_rule_id": "v2_rule_p23_attitude",
            "category": "reckless_driving",
            "sentiment_score": -0.89,
            "created_at": "2025-07-18T10:45:00Z",
            "channel": "customer_hotline",
            "content": "Khách hàng phản ánh tài xế phóng nhanh vượt ẩu, phanh gấp khiến hành khách hoảng sợ và say xe",
        },
    ]
    for c in complaints:
        c_props = {
            k: v for k, v in c.items()
            if k not in ("trip_id", "escalated_to_incident_id", "violates_rule_id", "channel")
        }
        add_node("CustomerComplaint", c["id"], c_props)
        # Edge: Trip -> CustomerComplaint
        add_edge("RECEIVES_COMPLAINT", "Trip", c["trip_id"], "CustomerComplaint", c["id"], {"channel": c["channel"]})
        # Edge: CustomerComplaint -> Incident (Escalated to safety incident)
        add_edge("ESCALATED_TO", "CustomerComplaint", c["id"], "Incident", c["escalated_to_incident_id"])
        # Edge: CustomerComplaint -> PolicyRule (Violates service attitude policy)
        add_edge("VIOLATES", "CustomerComplaint", c["id"], "PolicyRule", c["violates_rule_id"])

    # =========================================================================
    # 10. REWARD & PENALTY DECISIONS
    # =========================================================================
    decisions = [
        # Thưởng Driver 1
        {
            "id": "v2_dec_001",
            "decision_id": "v2_dec_001",
            "driver_id": "v2_drv_001",
            "action_type": "bonus",
            "effective_date": "2025-07-31",
            "reason": "Khen thưởng tài xế tiêu biểu Tháng 7/2025 đạt xếp hạng Kim Cương, 100% tỷ lệ hoàn thành",
            "status": "awarded",
            "rules": ["v2_rule_p151"],
            "incident_id": None,
        },
        # Phạt Driver 2 (Hủy chuyến P154)
        {
            "id": "v2_dec_002",
            "decision_id": "v2_dec_002",
            "driver_id": "v2_drv_002",
            "action_type": "fine",
            "effective_date": "2025-07-22",
            "reason": "Phạt tiền 500,000 VND và cảnh cáo văn bản do vi phạm tỷ lệ hủy chuyến theo Quy chế P154",
            "status": "enforced",
            "rules": ["v2_rule_p154"],
            "incident_id": "v2_inc_001",
        },
        # Tạm khóa Driver 4 (Chạy quá tốc độ & lái xe ẩu vi phạm P23)
        {
            "id": "v2_dec_003",
            "decision_id": "v2_dec_003",
            "driver_id": "v2_drv_004",
            "action_type": "temporary_lock",
            "effective_date": "2025-07-19",
            "reason": "Tạm khóa tài khoản 3 ngày và trừ điểm an toàn do vi phạm chạy quá tốc độ và phản ánh lái xe ẩu",
            "status": "enforced",
            "rules": ["v2_rule_safety_speed", "v2_rule_p23_attitude"],
            "incident_id": "v2_inc_002",
        },
    ]

    for d in decisions:
        d_props = {k: v for k, v in d.items() if k not in ("driver_id", "rules", "incident_id")}
        add_node("RewardPenalty", d["id"], d_props)

        # Edge: Driver -> RewardPenalty
        add_edge(
            "RECEIVES", "Driver", d["driver_id"], "RewardPenalty", d["id"],
            {"issued_at": d["effective_date"] + "T08:00:00Z", "status": d["status"]},
        )
        # Edge: RewardPenalty -> PolicyRule
        for r_id in d.get("rules", []):
            add_edge(
                "BASED_ON", "RewardPenalty", d["id"], "PolicyRule", r_id,
                {"reason": d["reason"]},
            )
        # Edge: RewardPenalty -> Incident
        if d.get("incident_id"):
            add_edge(
                "BASED_ON", "RewardPenalty", d["id"], "Incident", d["incident_id"],
                {"reason": d["reason"]},
            )

    return {"nodes": nodes, "edges": edges}


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

            # Clean up existing V2 relationships for this snapshot to prevent stale edges
            session.run(
                f"MATCH (a:{MARKER_LABEL})-[r]->(b:{MARKER_LABEL}) "
                "WHERE r.snapshot_id = $snap "
                "DELETE r",
                snap=SNAPSHOT_ID,
            ).consume()

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
    """Traverse 2-hop neighborhood in V2 ontology for a specific driver."""
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
    nodes[driver_id] = {"id": driver_id, "label": "Driver", "name": records[0]["driver_name"], "props": driver_props}

    trip_ids = []
    incident_ids = []
    decision_ids = []

    for r in records:
        m_id = r["m_id"]
        m_label = r["m_label"]
        if m_id not in nodes:
            nodes[m_id] = {
                "id": m_id,
                "label": m_label,
                "name": r["m_props"].get("name") or r["m_props"].get("rule_name") or f"{m_label} {m_id}",
                "props": r["m_props"],
            }
        edges.append({
            "start_id": driver_id,
            "end_id": m_id,
            "rel_type": r["rel_type"],
            "props": r["rel_props"],
        })
        if m_label == "Trip":
            trip_ids.append(m_id)
        elif m_label == "Incident":
            incident_ids.append(m_id)
        elif m_label == "RewardPenalty":
            decision_ids.append(m_id)

    # Hop 2: Secondary neighbors (Trip -> Zone/Complaint, Incident -> PolicyRule, Decision -> PolicyRule/Incident, Vehicle -> Maintenance)
    vehicle_id = driver_props.get("vehicle_id") or [
        e["end_id"] for e in edges if e["rel_type"] == "OPERATES"
    ]
    target_ids = list(set(trip_ids + incident_ids + decision_ids + (vehicle_id if isinstance(vehicle_id, list) else [vehicle_id])))

    if target_ids:
        hop2_cypher = f"""
        MATCH (src:{MARKER_LABEL})-[r2]->(tgt:{MARKER_LABEL})
        WHERE src.id IN $target_ids AND r2.snapshot_id = $snapshot_id
        RETURN src.id AS src_id, type(r2) AS rel_type, properties(r2) AS rel_props,
               [lbl IN labels(tgt) WHERE lbl <> '{MARKER_LABEL}'][0] AS tgt_label,
               tgt.id AS tgt_id, properties(tgt) AS tgt_props
        """
        hop2_records = session.run(hop2_cypher, target_ids=target_ids, snapshot_id=SNAPSHOT_ID).data()
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
            edges.append({
                "start_id": r2["src_id"],
                "end_id": tgt_id,
                "rel_type": r2["rel_type"],
                "props": r2["rel_props"],
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
