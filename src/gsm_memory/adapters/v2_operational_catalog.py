"""Operational catalog and dataset generator for Driver Operations Ontology V2 (July 2025).

Provides high-fidelity, deterministic operational datasets simulating realistic fleet operations:
- 10 Drivers (active, suspended, off-duty)
- 10 Vehicles (EV cars, EV bikes, gasoline sedan)
- 7 Hubs across Hanoi, HCMC, Da Nang
- 8 Zones across Hanoi, HCMC, Da Nang
- 8 PolicyRules governing safety, cancellations, tariffs, hygiene, fraud, and route compliance
- 40 Shifts spanning early, mid, and late July 2025 (4 shifts per driver)
- 135 Trips (completed, cancelled_by_driver, cancelled_by_customer)
- 32 Incidents with severity, penalty points, fault rate, and detection channels
- 38 CustomerComplaints across reckless driving, overcharging, hygiene, attitude, and routing
- 26 MaintenanceEvents covering battery health, BMS firmware, periodic checks, and repairs
- 28 RewardPenalty decisions (bonuses, warnings, fines, temporary locks, retraining)
"""

from __future__ import annotations

from typing import Any

SNAPSHOT_ID = "snapshot-2025-07"

# =========================================================================
# 1. CORE ENTITIES: HUBS / FLEET TEAMS (7 Hubs)
# =========================================================================
HUBS = [
    {
        "id": "v2_hub_caugiay",
        "hub_id": "v2_hub_caugiay",
        "name": "Hub Cầu Giấy (Đội Xanh 1)",
        "supervisor_name": "Lê Hoàng Long",
        "region": "Miền Bắc - Hà Nội",
        "address": "Số 8 Phạm Hùng, Cầu Giấy, Hà Nội",
        "zone_id": "v2_zone_caugiay",
        "managed_vehicles": ["v2_veh_001", "v2_veh_005", "v2_veh_010"],
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
        "id": "v2_hub_namtuliem",
        "hub_id": "v2_hub_namtuliem",
        "name": "Hub Nam Từ Liêm (Đội Xanh Tây Hà Nội)",
        "supervisor_name": "Trần Trọng Đạt",
        "region": "Miền Bắc - Hà Nội",
        "address": "Đại lộ Thăng Long, Nam Từ Liêm, Hà Nội",
        "zone_id": "v2_zone_namtuliem",
        "managed_vehicles": ["v2_veh_006"],
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
        "managed_vehicles": ["v2_veh_004", "v2_veh_008"],
    },
    {
        "id": "v2_hub_thuduc",
        "hub_id": "v2_hub_thuduc",
        "name": "Hub Thủ Đức (Đội Xanh Khu Công Nghệ Cao)",
        "supervisor_name": "Đinh Quốc Bảo",
        "region": "Miền Nam - TP. Hồ Chí Minh",
        "address": "Khu Công nghệ cao, TP. Thủ Đức, TP.HCM",
        "zone_id": "v2_zone_thuduc",
        "managed_vehicles": ["v2_veh_007"],
    },
    {
        "id": "v2_hub_danang",
        "hub_id": "v2_hub_danang",
        "name": "Hub Hải Châu (Đội Xanh Trung Tâm Đà Nẵng)",
        "supervisor_name": "Mai Thế Anh",
        "region": "Miền Trung - Đà Nẵng",
        "address": "Đường Bạch Đằng, Hải Châu, Đà Nẵng",
        "zone_id": "v2_zone_haichau",
        "managed_vehicles": ["v2_veh_009"],
    },
]

# =========================================================================
# 2. CORE ENTITIES: ZONES / AREAS (8 Zones)
# =========================================================================
ZONES = [
    {
        "id": "v2_zone_noibai",
        "zone_id": "v2_zone_noibai",
        "name": "Khu vực Sân bay Nội Bài",
        "zone_name": "Khu vực Sân bay Quốc tế Nội Bài",
        "city": "Hà Nội",
        "risk_level": "medium",
        "traffic_profile": "airport_congestion_and_high_speed_expressway",
    },
    {
        "id": "v2_zone_hoankiem",
        "zone_id": "v2_zone_hoankiem",
        "name": "Khu vực Phố cổ Hoàn Kiếm",
        "zone_name": "Khu vực Phố cổ & Trung tâm Hoàn Kiếm",
        "city": "Hà Nội",
        "risk_level": "high",
        "traffic_profile": "narrow_dense_alleys_and_pedestrian_zones",
    },
    {
        "id": "v2_zone_caugiay",
        "zone_id": "v2_zone_caugiay",
        "name": "Khu đô thị Cầu Giấy",
        "zone_name": "Khu đô thị & Công nghệ Cầu Giấy",
        "city": "Hà Nội",
        "risk_level": "medium",
        "traffic_profile": "heavy_traffic_peak_hours",
    },
    {
        "id": "v2_zone_namtuliem",
        "zone_id": "v2_zone_namtuliem",
        "name": "Khu vực Nam Từ Liêm",
        "zone_name": "Khu liên hợp Thể thao & Đô thị Nam Từ Liêm",
        "city": "Hà Nội",
        "risk_level": "low",
        "traffic_profile": "wide_boulevards_and_stadium_connectors",
    },
    {
        "id": "v2_zone_tansonnhat",
        "zone_id": "v2_zone_tansonnhat",
        "name": "Khu vực Sân bay Tân Sơn Nhất",
        "zone_name": "Khu vực Sân bay Quốc tế Tân Sơn Nhất",
        "city": "TP. Hồ Chí Minh",
        "risk_level": "high",
        "traffic_profile": "airport_congestion_and_ring_road_traffic",
    },
    {
        "id": "v2_zone_quan1",
        "zone_id": "v2_zone_quan1",
        "name": "Khu vực Trung tâm Quận 1",
        "zone_name": "Khu vực Trung tâm Quận 1",
        "city": "TP. Hồ Chí Minh",
        "risk_level": "high",
        "traffic_profile": "heavy_traffic_peak_hours_and_one_way_streets",
    },
    {
        "id": "v2_zone_thuduc",
        "zone_id": "v2_zone_thuduc",
        "name": "Khu đô thị Thủ Đức",
        "zone_name": "Khu đô thị Sáng tạo Thủ Đức",
        "city": "TP. Hồ Chí Minh",
        "risk_level": "low",
        "traffic_profile": "wide_boulevards_and_highway_connectors",
    },
    {
        "id": "v2_zone_haichau",
        "zone_id": "v2_zone_haichau",
        "name": "Khu vực Hải Châu & Cầu Rồng",
        "zone_name": "Khu vực Trung tâm Hải Châu & Cầu Rồng",
        "city": "Đà Nẵng",
        "risk_level": "medium",
        "traffic_profile": "tourist_hotspots_and_bridges",
    },
]

# =========================================================================
# 3. CORE ENTITIES: VEHICLES (10 Vehicles)
# =========================================================================
VEHICLES = [
    {
        "id": "v2_veh_001",
        "vehicle_id": "v2_veh_001",
        "name": "VinFast VF 8 (29E-888.12)",
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
        "name": "VinFast VF e34 (29E-666.89)",
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
        "name": "VinFast VF 5 Plus (51K-777.33)",
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
        "name": "VinFast VF e34 (51K-444.11)",
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
        "name": "VinFast Feliz S (29MD-123.45)",
        "plate_number": "29MD-123.45",
        "model": "VinFast Feliz S",
        "vehicle_type": "electric_bike",
        "battery_health": 97.5,
        "fuel_type": "electric",
        "odometer_km": 8900,
    },
    {
        "id": "v2_veh_006",
        "vehicle_id": "v2_veh_006",
        "name": "VinFast VF 7 (29E-999.77)",
        "plate_number": "29E-999.77",
        "model": "VinFast VF 7",
        "vehicle_type": "electric_suv",
        "battery_health": 99.1,
        "fuel_type": "electric",
        "odometer_km": 11200,
    },
    {
        "id": "v2_veh_007",
        "vehicle_id": "v2_veh_007",
        "name": "VinFast VF 3 (51K-333.11)",
        "plate_number": "51K-333.11",
        "model": "VinFast VF 3",
        "vehicle_type": "electric_mini",
        "battery_health": 99.5,
        "fuel_type": "electric",
        "odometer_km": 6400,
    },
    {
        "id": "v2_veh_008",
        "vehicle_id": "v2_veh_008",
        "name": "VinFast Klara S (59-X3 789.12)",
        "plate_number": "59-X3 789.12",
        "model": "VinFast Klara S",
        "vehicle_type": "electric_bike",
        "battery_health": 96.8,
        "fuel_type": "electric",
        "odometer_km": 12500,
    },
    {
        "id": "v2_veh_009",
        "vehicle_id": "v2_veh_009",
        "name": "Toyota Vios 1.5G (43A-555.88)",
        "plate_number": "43A-555.88",
        "model": "Toyota Vios 1.5G",
        "vehicle_type": "gasoline_sedan",
        "battery_health": None,
        "fuel_type": "gasoline",
        "odometer_km": 58000,
    },
    {
        "id": "v2_veh_010",
        "vehicle_id": "v2_veh_010",
        "name": "VinFast VF 6 (29E-777.55)",
        "plate_number": "29E-777.55",
        "model": "VinFast VF 6",
        "vehicle_type": "electric_suv",
        "battery_health": 97.0,
        "fuel_type": "electric",
        "odometer_km": 19000,
    },
]

# =========================================================================
# 4. POLICIES & ASSESSMENTS: POLICY RULES (8 Rules)
# =========================================================================
POLICY_RULES = [
    {
        "id": "v2_rule_p154",
        "rule_id": "RULE-P154-CANCEL",
        "name": "Quy chế P154 - Giới hạn tỷ lệ hủy chuyến",
        "rule_name": "Quy chế P154 - Giới hạn tỷ lệ hủy chuyến",
        "threshold_description": "Tỷ lệ hủy chuyến chủ động trong chu kỳ tháng vượt quá 15% hoặc hủy giờ cao điểm bất thường > 3 cuốc liên tiếp",
        "penalty_action": "Cảnh cáo văn bản, phạt 500,000 VND và tạm đình chỉ tài khoản nếu tái phạm",
    },
    {
        "id": "v2_rule_p151",
        "rule_id": "RULE-P151-ACCEPT",
        "name": "Quy chế P151 - Tiêu chuẩn tỷ lệ nhận cuốc",
        "rule_name": "Quy chế P151 - Tiêu chuẩn tỷ lệ nhận cuốc",
        "threshold_description": "Tỷ lệ chấp nhận cuốc xe (AR) trong chu kỳ tháng đạt dưới 85%",
        "penalty_action": "Hạ bậc ưu tiên phát cuốc và nhắc nhở đào tạo lại quy trình vận hành",
    },
    {
        "id": "v2_rule_safety_speed",
        "rule_id": "RULE-SAFETY-SPEED",
        "name": "Quy chuẩn An toàn Vận hành & Giới hạn Tốc độ",
        "rule_name": "Quy chuẩn An toàn Vận hành & Giới hạn Tốc độ",
        "threshold_description": "Vượt quá tốc độ quy định trên 20km/h ghi nhận từ thiết bị viễn thông Telematics IoT",
        "penalty_action": "Tạm khóa tài khoản 3 ngày, trừ điểm an toàn và yêu cầu thi sát hạch an toàn",
    },
    {
        "id": "v2_rule_p23_attitude",
        "rule_id": "RULE-P23-ATTITUDE",
        "name": "Quy chế P23 - Quy tắc ứng xử và Văn hóa phục vụ GSM",
        "rule_name": "Quy chế P23 - Quy tắc ứng xử và Văn hóa phục vụ GSM",
        "threshold_description": "Khách hàng phản ánh thái độ gắt gỏng, lái xe ẩu hoặc thu sai tiền cước được thẩm định là đúng",
        "penalty_action": "Phạt tiền bồi hoàn cho khách, cảnh cáo văn bản và hạ xếp hạng sao tài xế",
    },
    {
        "id": "v2_rule_fraud_promo",
        "rule_id": "RULE-FRAUD-PROMO",
        "name": "Quy chế Chống gian lận Khuyến mãi & Cuốc ảo",
        "rule_name": "Quy chế Chống gian lận Khuyến mãi & Cuốc ảo",
        "threshold_description": "Phát hiện hành vi tự tạo đơn ảo, đặt cuốc chéo hoặc thông đồng trục lợi voucher khuyến mãi hệ thống",
        "penalty_action": "Tạm khóa tài khoản 14 ngày đến vĩnh viễn, thu hồi toàn bộ tiền thưởng và xử lý bồi hoàn",
    },
    {
        "id": "v2_rule_route_deviation",
        "rule_id": "RULE-ROUTE-COMPLIANCE",
        "name": "Tiêu chuẩn Định tuyến Lộ trình & Chống chạy vòng",
        "rule_name": "Tiêu chuẩn Định tuyến Lộ trình & Chống chạy vòng",
        "threshold_description": "Cố ý chạy sai lệch lộ trình GPS định tuyến > 30% cự ly mà không có lý do kẹt xe hoặc yêu cầu khách",
        "penalty_action": "Phạt bồi hoàn cước phí chênh lệch cho khách hàng, trừ điểm đánh giá nghiệp vụ",
    },
    {
        "id": "v2_rule_vehicle_hygiene",
        "rule_id": "RULE-VEHICLE-HYGIENE",
        "name": "Tiêu chuẩn Vệ sinh Phương tiện và Trải nghiệm 5 sao",
        "rule_name": "Tiêu chuẩn Vệ sinh Phương tiện và Trải nghiệm 5 sao",
        "threshold_description": "Phương tiện có mùi khói thuốc lá, rác thải bừa bãi hoặc ghế ngồi bẩn khiến hành khách phàn nàn",
        "penalty_action": "Cảnh cáo văn bản, đình chỉ nhận chuyến trong ngày để vệ sinh tổng thể phương tiện",
    },
    {
        "id": "v2_rule_tariff_overcharge",
        "rule_id": "RULE-TARIFF-OVERCHARGE",
        "name": "Quy định Minh bạch Cước phí & Chống thu quá tiền",
        "rule_name": "Quy định Minh bạch Cước phí & Chống thu quá tiền",
        "threshold_description": "Thu tiền mặt phát sinh ngoài cước hiển thị trên ứng dụng hoặc không trả lại tiền thừa cho khách",
        "penalty_action": "Hoàn trả 100% tiền thu thừa, phạt vi phạm 200,000 VND và cảnh cáo nhắc nhở",
    },
]

# =========================================================================
# 5. CORE ENTITIES: DRIVERS (10 Drivers)
# =========================================================================
DRIVERS = [
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
            ("v2_zone_caugiay", 0.70, "morning"),
            ("v2_zone_hoankiem", 0.30, "afternoon"),
        ],
    },
    {
        "id": "v2_drv_006",
        "driver_id": "v2_drv_006",
        "driver_code": "DRV-V2-006",
        "name": "Hoàng Văn Thắng",
        "phone": "0901888006",
        "email": "thang.hv@gsm.vn",
        "onboarding_date": "2024-01-10",
        "tier_level": "Bạch Kim",
        "rating_avg": 4.98,
        "status": "active",
        "hub_id": "v2_hub_namtuliem",
        "vehicle_id": "v2_veh_006",
        "frequent_zones": [
            ("v2_zone_namtuliem", 0.50, "all_day"),
            ("v2_zone_noibai", 0.50, "evening"),
        ],
    },
    {
        "id": "v2_drv_007",
        "driver_id": "v2_drv_007",
        "driver_code": "DRV-V2-007",
        "name": "Đỗ Minh Khang",
        "phone": "0901888007",
        "email": "khang.dm@gsm.vn",
        "onboarding_date": "2025-03-01",
        "tier_level": "Tiêu chuẩn",
        "rating_avg": 3.85,
        "status": "suspended",
        "hub_id": "v2_hub_thuduc",
        "vehicle_id": "v2_veh_007",
        "frequent_zones": [
            ("v2_zone_thuduc", 0.80, "afternoon"),
        ],
    },
    {
        "id": "v2_drv_008",
        "driver_id": "v2_drv_008",
        "driver_code": "DRV-V2-008",
        "name": "Vũ Bích Ngọc",
        "phone": "0901888008",
        "email": "ngoc.vb@gsm.vn",
        "onboarding_date": "2024-12-01",
        "tier_level": "Vàng",
        "rating_avg": 4.92,
        "status": "off-duty",
        "hub_id": "v2_hub_tanbinh",
        "vehicle_id": "v2_veh_008",
        "frequent_zones": [
            ("v2_zone_tansonnhat", 0.70, "morning"),
        ],
    },
    {
        "id": "v2_drv_009",
        "driver_id": "v2_drv_009",
        "driver_code": "DRV-V2-009",
        "name": "Bùi Đức Tiến",
        "phone": "0901888009",
        "email": "tien.bd@gsm.vn",
        "onboarding_date": "2024-10-05",
        "tier_level": "Bạc",
        "rating_avg": 4.20,
        "status": "active",
        "hub_id": "v2_hub_danang",
        "vehicle_id": "v2_veh_009",
        "frequent_zones": [
            ("v2_zone_haichau", 0.90, "all_day"),
        ],
    },
    {
        "id": "v2_drv_010",
        "driver_id": "v2_drv_010",
        "driver_code": "DRV-V2-010",
        "name": "Trịnh Thanh Tùng",
        "phone": "0901888010",
        "email": "tung.tt@gsm.vn",
        "onboarding_date": "2025-01-15",
        "tier_level": "Tiêu chuẩn",
        "rating_avg": 4.35,
        "status": "active",
        "hub_id": "v2_hub_caugiay",
        "vehicle_id": "v2_veh_010",
        "frequent_zones": [
            ("v2_zone_caugiay", 0.50, "morning"),
            ("v2_zone_hoankiem", 0.50, "evening"),
        ],
    },
]

# =========================================================================
# 6. SHIFTS (40 Shifts spanning July 2025 - 4 shifts per driver)
# =========================================================================
SHIFTS_DATA = [
    # Driver 1 (Trần Quốc Toản)
    ("v2_shift_001_1", "v2_drv_001", "2025-07-05", "2025-07-05T06:00:00Z", "2025-07-05T15:30:00Z", 9.5, 0.98, 1.0, "Ca sáng 05/07 - Trần Quốc Toản"),
    ("v2_shift_001_2", "v2_drv_001", "2025-07-12", "2025-07-12T06:00:00Z", "2025-07-12T15:30:00Z", 9.5, 0.96, 1.0, "Ca ngày 12/07 - Trần Quốc Toản"),
    ("v2_shift_001_3", "v2_drv_001", "2025-07-19", "2025-07-19T06:30:00Z", "2025-07-19T16:30:00Z", 10.0, 1.00, 1.0, "Ca VIP 19/07 - Trần Quốc Toản"),
    ("v2_shift_001_4", "v2_drv_001", "2025-07-26", "2025-07-26T07:00:00Z", "2025-07-26T17:00:00Z", 10.0, 1.00, 1.0, "Ca sân bay 26/07 - Trần Quốc Toản"),

    # Driver 2 (Lê Văn Hùng)
    ("v2_shift_002_1", "v2_drv_002", "2025-07-08", "2025-07-08T07:00:00Z", "2025-07-08T16:00:00Z", 9.0, 0.85, 0.88, "Ca làm 08/07 - Lê Văn Hùng"),
    ("v2_shift_002_2", "v2_drv_002", "2025-07-15", "2025-07-15T07:30:00Z", "2025-07-15T16:30:00Z", 9.0, 0.82, 0.85, "Ca làm 15/07 - Lê Văn Hùng"),
    ("v2_shift_002_3", "v2_drv_002", "2025-07-20", "2025-07-20T07:00:00Z", "2025-07-20T17:00:00Z", 10.0, 0.80, 0.80, "Ca nắng nóng 20/07 - Lê Văn Hùng"),
    ("v2_shift_002_4", "v2_drv_002", "2025-07-28", "2025-07-28T08:00:00Z", "2025-07-28T18:00:00Z", 10.0, 0.78, 0.73, "Ca mưa bão 28/07 - Lê Văn Hùng"),

    # Driver 3 (Nguyễn Hoàng Nam)
    ("v2_shift_003_1", "v2_drv_003", "2025-07-06", "2025-07-06T07:30:00Z", "2025-07-06T16:30:00Z", 9.0, 0.95, 0.98, "Ca sáng 06/07 - Nguyễn Hoàng Nam"),
    ("v2_shift_003_2", "v2_drv_003", "2025-07-12", "2025-07-12T08:00:00Z", "2025-07-12T17:00:00Z", 9.0, 0.96, 1.0, "Ca làm 12/07 - Nguyễn Hoàng Nam"),
    ("v2_shift_003_3", "v2_drv_003", "2025-07-18", "2025-07-18T08:30:00Z", "2025-07-18T17:30:00Z", 9.0, 0.94, 0.98, "Ca ngày 18/07 - Nguyễn Hoàng Nam"),
    ("v2_shift_003_4", "v2_drv_003", "2025-07-24", "2025-07-24T09:00:00Z", "2025-07-24T18:30:00Z", 9.5, 0.98, 1.0, "Ca chiều 24/07 - Nguyễn Hoàng Nam"),

    # Driver 4 (Phạm Thị Mai)
    ("v2_shift_004_1", "v2_drv_004", "2025-07-04", "2025-07-04T08:00:00Z", "2025-07-04T17:00:00Z", 9.0, 0.89, 0.92, "Ca làm 04/07 - Phạm Thị Mai"),
    ("v2_shift_004_2", "v2_drv_004", "2025-07-10", "2025-07-10T08:30:00Z", "2025-07-10T17:30:00Z", 9.0, 0.88, 0.90, "Ca trễ hẹn 10/07 - Phạm Thị Mai"),
    ("v2_shift_004_3", "v2_drv_004", "2025-07-14", "2025-07-14T09:00:00Z", "2025-07-14T18:00:00Z", 9.0, 0.87, 0.89, "Ca sân bay 14/07 - Phạm Thị Mai"),
    ("v2_shift_004_4", "v2_drv_004", "2025-07-18", "2025-07-18T09:00:00Z", "2025-07-18T18:00:00Z", 9.0, 0.85, 0.88, "Ca vi phạm 18/07 - Phạm Thị Mai"),

    # Driver 5 (Đặng Văn Phúc)
    ("v2_shift_005_1", "v2_drv_005", "2025-07-07", "2025-07-07T06:30:00Z", "2025-07-07T17:30:00Z", 11.0, 0.98, 1.0, "Ca giao hàng 07/07 - Đặng Văn Phúc"),
    ("v2_shift_005_2", "v2_drv_005", "2025-07-15", "2025-07-15T07:00:00Z", "2025-07-15T18:00:00Z", 11.0, 0.96, 1.0, "Ca ngày 15/07 - Đặng Văn Phúc"),
    ("v2_shift_005_3", "v2_drv_005", "2025-07-22", "2025-07-22T07:00:00Z", "2025-07-22T18:00:00Z", 11.0, 0.97, 1.0, "Ca phanh gấp 22/07 - Đặng Văn Phúc"),
    ("v2_shift_005_4", "v2_drv_005", "2025-07-29", "2025-07-29T06:30:00Z", "2025-07-29T17:30:00Z", 11.0, 0.99, 1.0, "Ca mưa lớn 29/07 - Đặng Văn Phúc"),

    # Driver 6 (Hoàng Văn Thắng)
    ("v2_shift_006_1", "v2_drv_006", "2025-07-09", "2025-07-09T07:00:00Z", "2025-07-09T16:30:00Z", 9.5, 1.00, 1.0, "Ca VIP 09/07 - Hoàng Văn Thắng"),
    ("v2_shift_006_2", "v2_drv_006", "2025-07-16", "2025-07-16T07:00:00Z", "2025-07-16T16:30:00Z", 9.5, 1.00, 1.0, "Ca làm 16/07 - Hoàng Văn Thắng"),
    ("v2_shift_006_3", "v2_drv_006", "2025-07-21", "2025-07-21T07:30:00Z", "2025-07-21T17:00:00Z", 9.5, 1.00, 1.0, "Ca ngoại giao 21/07 - Hoàng Văn Thắng"),
    ("v2_shift_006_4", "v2_drv_006", "2025-07-25", "2025-07-25T08:00:00Z", "2025-07-25T17:30:00Z", 9.5, 1.00, 1.0, "Ca đón khách 25/07 - Hoàng Văn Thắng"),

    # Driver 7 (Đỗ Minh Khang)
    ("v2_shift_007_1", "v2_drv_007", "2025-07-05", "2025-07-05T09:00:00Z", "2025-07-05T17:00:00Z", 8.0, 0.82, 0.85, "Ca làm 05/07 - Đỗ Minh Khang"),
    ("v2_shift_007_2", "v2_drv_007", "2025-07-11", "2025-07-11T09:00:00Z", "2025-07-11T17:00:00Z", 8.0, 0.78, 0.80, "Ca đơn ảo 11/07 - Đỗ Minh Khang"),
    ("v2_shift_007_3", "v2_drv_007", "2025-07-17", "2025-07-17T10:00:00Z", "2025-07-17T18:00:00Z", 8.0, 0.76, 0.75, "Ca làm 17/07 - Đỗ Minh Khang"),
    ("v2_shift_007_4", "v2_drv_007", "2025-07-21", "2025-07-21T10:00:00Z", "2025-07-21T18:00:00Z", 8.0, 0.72, 0.65, "Ca gian lận 21/07 - Đỗ Minh Khang"),

    # Driver 8 (Vũ Bích Ngọc)
    ("v2_shift_008_1", "v2_drv_008", "2025-07-04", "2025-07-04T06:30:00Z", "2025-07-04T14:30:00Z", 8.0, 0.95, 1.0, "Ca sớm 04/07 - Vũ Bích Ngọc"),
    ("v2_shift_008_2", "v2_drv_008", "2025-07-09", "2025-07-09T06:30:00Z", "2025-07-09T14:30:00Z", 8.0, 0.96, 1.0, "Ca sáng 09/07 - Vũ Bích Ngọc"),
    ("v2_shift_008_3", "v2_drv_008", "2025-07-14", "2025-07-14T06:30:00Z", "2025-07-14T14:00:00Z", 7.5, 0.96, 1.0, "Ca làm 14/07 - Vũ Bích Ngọc"),
    ("v2_shift_008_4", "v2_drv_008", "2025-07-19", "2025-07-19T06:30:00Z", "2025-07-19T14:00:00Z", 7.5, 0.97, 1.0, "Ca cuối tháng 19/07 - Vũ Bích Ngọc"),

    # Driver 9 (Bùi Đức Tiến)
    ("v2_shift_009_1", "v2_drv_009", "2025-07-08", "2025-07-08T07:00:00Z", "2025-07-08T17:30:00Z", 10.5, 0.86, 0.90, "Ca đón khách 08/07 - Bùi Đức Tiến"),
    ("v2_shift_009_2", "v2_drv_009", "2025-07-14", "2025-07-14T07:30:00Z", "2025-07-14T18:00:00Z", 10.5, 0.85, 0.88, "Ca làm 14/07 - Bùi Đức Tiến"),
    ("v2_shift_009_3", "v2_drv_009", "2025-07-19", "2025-07-19T07:30:00Z", "2025-07-19T18:00:00Z", 10.5, 0.84, 0.88, "Ca thu sai tiền 19/07 - Bùi Đức Tiến"),
    ("v2_shift_009_4", "v2_drv_009", "2025-07-27", "2025-07-27T08:00:00Z", "2025-07-27T18:30:00Z", 10.5, 0.81, 0.85, "Ca đêm Cầu Rồng 27/07 - Bùi Đức Tiến"),

    # Driver 10 (Trịnh Thanh Tùng)
    ("v2_shift_010_1", "v2_drv_010", "2025-07-06", "2025-07-06T07:30:00Z", "2025-07-06T16:00:00Z", 8.5, 0.91, 0.95, "Ca sáng 06/07 - Trịnh Thanh Tùng"),
    ("v2_shift_010_2", "v2_drv_010", "2025-07-12", "2025-07-12T07:30:00Z", "2025-07-12T16:00:00Z", 8.5, 0.90, 0.94, "Ca vượt đèn 12/07 - Trịnh Thanh Tùng"),
    ("v2_shift_010_3", "v2_drv_010", "2025-07-23", "2025-07-23T08:00:00Z", "2025-07-23T16:30:00Z", 8.5, 0.89, 0.92, "Ca chạy vòng 23/07 - Trịnh Thanh Tùng"),
    ("v2_shift_010_4", "v2_drv_010", "2025-07-29", "2025-07-29T08:30:00Z", "2025-07-29T17:00:00Z", 8.5, 0.88, 0.91, "Ca phụ phí 29/07 - Trịnh Thanh Tùng"),
]

# =========================================================================
# 7. TRIPS (135 Trips simulating realistic fleet operations)
# =========================================================================
TRIPS_DATA = [
    # (trip_id, driver_id, shift_id, vehicle_id, name, fare, dist_km, dur_min, status, pu_zone, do_zone, timestamp)
    
    # --- DRIVER 1: Trần Quốc Toản (VF 8 - Luxury Hà Nội) (14 trips, 100% completed, high fare) ---
    ("v2_trip_001_01", "v2_drv_001", "v2_shift_001_1", "v2_veh_001", "Chuyến #001 (Nội Bài -> Hoàn Kiếm)", 295000, 28.0, 42, "completed", "v2_zone_noibai", "v2_zone_hoankiem", "2025-07-05T07:15:00Z"),
    ("v2_trip_001_02", "v2_drv_001", "v2_shift_001_1", "v2_veh_001", "Chuyến #002 (Hoàn Kiếm -> Cầu Giấy)", 110000, 9.5, 25, "completed", "v2_zone_hoankiem", "v2_zone_caugiay", "2025-07-05T09:30:00Z"),
    ("v2_trip_001_03", "v2_drv_001", "v2_shift_001_1", "v2_veh_001", "Chuyến #003 (Cầu Giấy -> Nội Bài)", 280000, 26.0, 38, "completed", "v2_zone_caugiay", "v2_zone_noibai", "2025-07-05T12:00:00Z"),
    ("v2_trip_001_04", "v2_drv_001", "v2_shift_001_1", "v2_veh_001", "Chuyến #004 (Nội Bài -> Cầu Giấy)", 270000, 25.0, 35, "completed", "v2_zone_noibai", "v2_zone_caugiay", "2025-07-05T14:15:00Z"),
    ("v2_trip_001_05", "v2_drv_001", "v2_shift_001_2", "v2_veh_001", "Chuyến #005 (Cầu Giấy -> Hoàn Kiếm)", 125000, 10.0, 26, "completed", "v2_zone_caugiay", "v2_zone_hoankiem", "2025-07-12T07:30:00Z"),
    ("v2_trip_001_06", "v2_drv_001", "v2_shift_001_2", "v2_veh_001", "Chuyến #006 (Hoàn Kiếm -> Nội Bài)", 290000, 28.0, 40, "completed", "v2_zone_hoankiem", "v2_zone_noibai", "2025-07-12T10:00:00Z"),
    ("v2_trip_001_07", "v2_drv_001", "v2_shift_001_2", "v2_veh_001", "Chuyến #007 (Nội Bài -> Nam Từ Liêm)", 310000, 30.0, 44, "completed", "v2_zone_noibai", "v2_zone_namtuliem", "2025-07-12T13:30:00Z"),
    ("v2_trip_001_08", "v2_drv_001", "v2_shift_001_3", "v2_veh_001", "Chuyến #008 (Nam Từ Liêm -> Hoàn Kiếm)", 160000, 12.0, 28, "completed", "v2_zone_namtuliem", "v2_zone_hoankiem", "2025-07-19T08:00:00Z"),
    ("v2_trip_001_09", "v2_drv_001", "v2_shift_001_3", "v2_veh_001", "Chuyến #009 (Hoàn Kiếm -> Cầu Giấy)", 115000, 9.8, 24, "completed", "v2_zone_hoankiem", "v2_zone_caugiay", "2025-07-19T11:15:00Z"),
    ("v2_trip_001_10", "v2_drv_001", "v2_shift_001_3", "v2_veh_001", "Chuyến #010 (Cầu Giấy -> Nội Bài VIP)", 320000, 27.5, 39, "completed", "v2_zone_caugiay", "v2_zone_noibai", "2025-07-19T14:00:00Z"),
    ("v2_trip_001_11", "v2_drv_001", "v2_shift_001_4", "v2_veh_001", "Chuyến #011 (Nội Bài -> Hoàn Kiếm)", 295000, 28.0, 41, "completed", "v2_zone_noibai", "v2_zone_hoankiem", "2025-07-26T08:30:00Z"),
    ("v2_trip_001_12", "v2_drv_001", "v2_shift_001_4", "v2_veh_001", "Chuyến #012 (Hoàn Kiếm -> Nam Từ Liêm)", 150000, 11.5, 27, "completed", "v2_zone_hoankiem", "v2_zone_namtuliem", "2025-07-26T11:00:00Z"),
    ("v2_trip_001_13", "v2_drv_001", "v2_shift_001_4", "v2_veh_001", "Chuyến #013 (Nam Từ Liêm -> Cầu Giấy)", 75000, 6.2, 16, "completed", "v2_zone_namtuliem", "v2_zone_caugiay", "2025-07-26T13:45:00Z"),
    ("v2_trip_001_14", "v2_drv_001", "v2_shift_001_4", "v2_veh_001", "Chuyến #014 (Cầu Giấy -> Nội Bài)", 285000, 26.0, 37, "completed", "v2_zone_caugiay", "v2_zone_noibai", "2025-07-26T15:30:00Z"),

    # --- DRIVER 2: Lê Văn Hùng (VF e34 - Hà Nội) (15 trips, nhiều ca hủy giờ cao điểm & mưa bão) ---
    ("v2_trip_002_01", "v2_drv_002", "v2_shift_002_1", "v2_veh_002", "Chuyến #015 (Hoàn Kiếm -> Cầu Giấy)", 120000, 10.2, 28, "completed", "v2_zone_hoankiem", "v2_zone_caugiay", "2025-07-08T08:30:00Z"),
    ("v2_trip_002_02", "v2_drv_002", "v2_shift_002_1", "v2_veh_002", "Chuyến #016 (Cầu Giấy -> Hoàn Kiếm - Tự hủy)", 115000, 9.8, 0, "cancelled_by_driver", "v2_zone_caugiay", "v2_zone_hoankiem", "2025-07-08T12:15:00Z"),
    ("v2_trip_002_03", "v2_drv_002", "v2_shift_002_1", "v2_veh_002", "Chuyến #017 (Hoàn Kiếm -> Nam Từ Liêm)", 140000, 11.0, 30, "completed", "v2_zone_hoankiem", "v2_zone_namtuliem", "2025-07-08T14:00:00Z"),
    ("v2_trip_002_04", "v2_drv_002", "v2_shift_002_2", "v2_veh_002", "Chuyến #018 (Nam Từ Liêm -> Hoàn Kiếm)", 145000, 11.2, 32, "completed", "v2_zone_namtuliem", "v2_zone_hoankiem", "2025-07-15T09:00:00Z"),
    ("v2_trip_002_05", "v2_drv_002", "v2_shift_002_2", "v2_veh_002", "Chuyến #019 (Hoàn Kiếm -> Nội Bài - Pin yếu hủy)", 280000, 27.0, 0, "cancelled_by_driver", "v2_zone_hoankiem", "v2_zone_noibai", "2025-07-15T11:30:00Z"),
    ("v2_trip_002_06", "v2_drv_002", "v2_shift_002_2", "v2_veh_002", "Chuyến #020 (Hoàn Kiếm -> Cầu Giấy)", 110000, 9.5, 27, "completed", "v2_zone_hoankiem", "v2_zone_caugiay", "2025-07-15T14:30:00Z"),
    ("v2_trip_002_07", "v2_drv_002", "v2_shift_002_3", "v2_veh_002", "Chuyến #021 (Hoàn Kiếm - Tự ý hủy cao điểm)", 85000, 5.2, 0, "cancelled_by_driver", "v2_zone_hoankiem", "v2_zone_hoankiem", "2025-07-20T08:30:00Z"),
    ("v2_trip_002_08", "v2_drv_002", "v2_shift_002_3", "v2_veh_002", "Chuyến #022 (Hoàn Kiếm -> Cầu Giấy - Tắt điều hòa)", 130000, 11.0, 32, "completed", "v2_zone_hoankiem", "v2_zone_caugiay", "2025-07-20T11:45:00Z"),
    ("v2_trip_002_09", "v2_drv_002", "v2_shift_002_3", "v2_veh_002", "Chuyến #023 (Cầu Giấy -> Hoàn Kiếm - Tự hủy lần 2)", 95000, 7.0, 0, "cancelled_by_driver", "v2_zone_caugiay", "v2_zone_hoankiem", "2025-07-20T14:30:00Z"),
    ("v2_trip_002_10", "v2_drv_002", "v2_shift_002_3", "v2_veh_002", "Chuyến #024 (Hoàn Kiếm -> Hoàn Kiếm - Cãi nhau điểm trả)", 70000, 4.0, 15, "completed", "v2_zone_hoankiem", "v2_zone_hoankiem", "2025-07-20T16:00:00Z"),
    ("v2_trip_002_11", "v2_drv_002", "v2_shift_002_4", "v2_veh_002", "Chuyến #025 (Hoàn Kiếm -> Long Biên - Mưa hủy)", 110000, 8.0, 0, "cancelled_by_driver", "v2_zone_hoankiem", "v2_zone_hoankiem", "2025-07-28T09:15:00Z"),
    ("v2_trip_002_12", "v2_drv_002", "v2_shift_002_4", "v2_veh_002", "Chuyến #026 (Hoàn Kiếm -> Cầu Giấy - Mưa hủy lần 2)", 125000, 10.0, 0, "cancelled_by_driver", "v2_zone_hoankiem", "v2_zone_caugiay", "2025-07-28T11:00:00Z"),
    ("v2_trip_002_13", "v2_drv_002", "v2_shift_002_4", "v2_veh_002", "Chuyến #027 (Hoàn Kiếm -> Nội Bài - Hủy cuốc mưa 3)", 285000, 27.0, 0, "cancelled_by_driver", "v2_zone_hoankiem", "v2_zone_noibai", "2025-07-28T14:00:00Z"),
    ("v2_trip_002_14", "v2_drv_002", "v2_shift_002_4", "v2_veh_002", "Chuyến #028 (Hoàn Kiếm -> Nam Từ Liêm - Mưa hủy 4)", 150000, 12.0, 0, "cancelled_by_driver", "v2_zone_hoankiem", "v2_zone_namtuliem", "2025-07-28T15:30:00Z"),
    ("v2_trip_002_15", "v2_drv_002", "v2_shift_002_4", "v2_veh_002", "Chuyến #029 (Hoàn Kiếm -> Cầu Giấy)", 110000, 9.5, 35, "completed", "v2_zone_hoankiem", "v2_zone_caugiay", "2025-07-28T17:15:00Z"),

    # --- DRIVER 3: Nguyễn Hoàng Nam (VF 5 Plus - TP.HCM) (14 trips, ổn định, 100% nhận) ---
    ("v2_trip_003_01", "v2_drv_003", "v2_shift_003_1", "v2_veh_003", "Chuyến #030 (Quận 7 -> Quận 1)", 95000, 7.8, 22, "completed", "v2_zone_thuduc", "v2_zone_quan1", "2025-07-06T08:30:00Z"),
    ("v2_trip_003_02", "v2_drv_003", "v2_shift_003_1", "v2_veh_003", "Chuyến #031 (Quận 1 -> Tân Sơn Nhất)", 140000, 9.5, 28, "completed", "v2_zone_quan1", "v2_zone_tansonnhat", "2025-07-06T11:45:00Z"),
    ("v2_trip_003_03", "v2_drv_003", "v2_shift_003_1", "v2_veh_003", "Chuyến #032 (Tân Sơn Nhất -> Quận 7)", 190000, 15.0, 38, "completed", "v2_zone_tansonnhat", "v2_zone_thuduc", "2025-07-06T14:30:00Z"),
    ("v2_trip_003_04", "v2_drv_003", "v2_shift_003_2", "v2_veh_003", "Chuyến #033 (Quận 1 -> Thủ Đức)", 165000, 14.5, 32, "completed", "v2_zone_quan1", "v2_zone_thuduc", "2025-07-12T09:15:00Z"),
    ("v2_trip_003_05", "v2_drv_003", "v2_shift_003_2", "v2_veh_003", "Chuyến #034 (Thủ Đức -> Quận 7)", 180000, 16.0, 36, "completed", "v2_zone_thuduc", "v2_zone_thuduc", "2025-07-12T12:00:00Z"),
    ("v2_trip_003_06", "v2_drv_003", "v2_shift_003_2", "v2_veh_003", "Chuyến #035 (Quận 7 -> Quận 1)", 90000, 7.5, 20, "completed", "v2_zone_thuduc", "v2_zone_quan1", "2025-07-12T15:30:00Z"),
    ("v2_trip_003_07", "v2_drv_003", "v2_shift_003_3", "v2_veh_003", "Chuyến #036 (Quận 1 -> Tân Sơn Nhất)", 135000, 9.0, 26, "completed", "v2_zone_quan1", "v2_zone_tansonnhat", "2025-07-18T09:30:00Z"),
    ("v2_trip_003_08", "v2_drv_003", "v2_shift_003_3", "v2_veh_003", "Chuyến #037 (Tân Sơn Nhất -> Thủ Đức)", 185000, 16.5, 37, "completed", "v2_zone_tansonnhat", "v2_zone_thuduc", "2025-07-18T12:15:00Z"),
    ("v2_trip_003_09", "v2_drv_003", "v2_shift_003_3", "v2_veh_003", "Chuyến #038 (Thủ Đức -> Quận 1 - Va quẹt nhẹ)", 150000, 13.0, 34, "completed", "v2_zone_thuduc", "v2_zone_quan1", "2025-07-18T15:00:00Z"),
    ("v2_trip_003_10", "v2_drv_003", "v2_shift_003_3", "v2_veh_003", "Chuyến #039 (Quận 1 -> Quận 7)", 95000, 8.0, 22, "completed", "v2_zone_quan1", "v2_zone_thuduc", "2025-07-18T16:45:00Z"),
    ("v2_trip_003_11", "v2_drv_003", "v2_shift_003_4", "v2_veh_003", "Chuyến #040 (Quận 7 -> Quận 1)", 90000, 7.5, 20, "completed", "v2_zone_thuduc", "v2_zone_quan1", "2025-07-24T10:00:00Z"),
    ("v2_trip_003_12", "v2_drv_003", "v2_shift_003_4", "v2_veh_003", "Chuyến #041 (Quận 1 -> Thủ Đức)", 155000, 13.8, 30, "completed", "v2_zone_quan1", "v2_zone_thuduc", "2025-07-24T12:30:00Z"),
    ("v2_trip_003_13", "v2_drv_003", "v2_shift_003_4", "v2_veh_003", "Chuyến #042 (Thủ Đức -> Quận 1)", 160000, 14.0, 31, "completed", "v2_zone_thuduc", "v2_zone_quan1", "2025-07-24T15:30:00Z"),
    ("v2_trip_003_14", "v2_drv_003", "v2_shift_003_4", "v2_veh_003", "Chuyến #043 (Quận 1 -> Quận 7)", 95000, 7.9, 21, "completed", "v2_zone_quan1", "v2_zone_thuduc", "2025-07-24T17:45:00Z"),

    # --- DRIVER 4: Phạm Thị Mai (VF e34 - TP.HCM) (13 trips, vi phạm tốc độ & trễ hẹn & đường cấm) ---
    ("v2_trip_004_01", "v2_drv_004", "v2_shift_004_1", "v2_veh_004", "Chuyến #044 (Tân Sơn Nhất -> Quận 1)", 160000, 9.2, 24, "completed", "v2_zone_tansonnhat", "v2_zone_quan1", "2025-07-04T09:30:00Z"),
    ("v2_trip_004_02", "v2_drv_004", "v2_shift_004_1", "v2_veh_004", "Chuyến #045 (Quận 1 -> Tân Sơn Nhất)", 150000, 8.8, 22, "completed", "v2_zone_quan1", "v2_zone_tansonnhat", "2025-07-04T12:15:00Z"),
    ("v2_trip_004_03", "v2_drv_004", "v2_shift_004_1", "v2_veh_004", "Chuyến #046 (Tân Sơn Nhất -> Thủ Đức)", 195000, 17.0, 38, "completed", "v2_zone_tansonnhat", "v2_zone_thuduc", "2025-07-04T15:00:00Z"),
    ("v2_trip_004_04", "v2_drv_004", "v2_shift_004_2", "v2_veh_004", "Chuyến #047 (Tân Sơn Nhất -> Quận 1)", 165000, 9.5, 25, "completed", "v2_zone_tansonnhat", "v2_zone_quan1", "2025-07-10T09:15:00Z"),
    ("v2_trip_004_05", "v2_drv_004", "v2_shift_004_2", "v2_veh_004", "Chuyến #048 (Quận 1 -> Tân Sơn Nhất - Trễ hẹn 25p)", 175000, 10.5, 48, "completed", "v2_zone_quan1", "v2_zone_tansonnhat", "2025-07-10T13:45:00Z"),
    ("v2_trip_004_06", "v2_drv_004", "v2_shift_004_2", "v2_veh_004", "Chuyến #049 (Tân Sơn Nhất -> Tân Bình)", 85000, 5.0, 16, "completed", "v2_zone_tansonnhat", "v2_zone_tansonnhat", "2025-07-10T16:00:00Z"),
    ("v2_trip_004_07", "v2_drv_004", "v2_shift_004_3", "v2_veh_004", "Chuyến #050 (Tân Sơn Nhất -> Quận 1)", 155000, 9.0, 23, "completed", "v2_zone_tansonnhat", "v2_zone_quan1", "2025-07-14T10:00:00Z"),
    ("v2_trip_004_08", "v2_drv_004", "v2_shift_004_3", "v2_veh_004", "Chuyến #051 (Quận 1 -> Thủ Đức - Bóp còi inh ỏi)", 170000, 14.0, 31, "completed", "v2_zone_quan1", "v2_zone_thuduc", "2025-07-14T13:00:00Z"),
    ("v2_trip_004_09", "v2_drv_004", "v2_shift_004_3", "v2_veh_004", "Chuyến #052 (Thủ Đức -> Tân Sơn Nhất)", 185000, 16.0, 35, "completed", "v2_zone_thuduc", "v2_zone_tansonnhat", "2025-07-14T16:15:00Z"),
    ("v2_trip_004_10", "v2_drv_004", "v2_shift_004_4", "v2_veh_004", "Chuyến #053 (Tân Sơn Nhất -> Quận 1 - Lái ẩu 82km/h)", 190000, 11.2, 26, "completed", "v2_zone_tansonnhat", "v2_zone_quan1", "2025-07-18T10:10:00Z"),
    ("v2_trip_004_11", "v2_drv_004", "v2_shift_004_4", "v2_veh_004", "Chuyến #054 (Quận 1 -> Tân Sơn Nhất - Đi đường cấm)", 185000, 12.0, 52, "completed", "v2_zone_quan1", "v2_zone_tansonnhat", "2025-07-18T14:30:00Z"),
    ("v2_trip_004_12", "v2_drv_004", "v2_shift_004_4", "v2_veh_004", "Chuyến #055 (Tân Sơn Nhất -> Quận 1 - SOS khẩn cấp)", 160000, 9.2, 24, "completed", "v2_zone_tansonnhat", "v2_zone_quan1", "2025-07-18T16:30:00Z"),
    ("v2_trip_004_13", "v2_drv_004", "v2_shift_004_4", "v2_veh_004", "Chuyến #056 (Quận 1 -> Tân Bình)", 90000, 6.5, 18, "completed", "v2_zone_quan1", "v2_zone_tansonnhat", "2025-07-18T17:30:00Z"),

    # --- DRIVER 5: Đặng Văn Phúc (Feliz S - Xe máy điện Hà Nội) (15 trips) ---
    ("v2_trip_005_01", "v2_drv_005", "v2_shift_005_1", "v2_veh_005", "Chuyến #057 (Cầu Giấy -> Cầu Giấy)", 28000, 3.5, 12, "completed", "v2_zone_caugiay", "v2_zone_caugiay", "2025-07-07T07:15:00Z"),
    ("v2_trip_005_02", "v2_drv_005", "v2_shift_005_1", "v2_veh_005", "Chuyến #058 (Cầu Giấy -> Nam Từ Liêm)", 42000, 5.8, 18, "completed", "v2_zone_caugiay", "v2_zone_namtuliem", "2025-07-07T09:30:00Z"),
    ("v2_trip_005_03", "v2_drv_005", "v2_shift_005_1", "v2_veh_005", "Chuyến #059 (Nam Từ Liêm -> Hoàn Kiếm)", 65000, 11.0, 30, "completed", "v2_zone_namtuliem", "v2_zone_hoankiem", "2025-07-07T12:00:00Z"),
    ("v2_trip_005_04", "v2_drv_005", "v2_shift_005_1", "v2_veh_005", "Chuyến #060 (Hoàn Kiếm -> Cầu Giấy)", 52000, 8.5, 24, "completed", "v2_zone_hoankiem", "v2_zone_caugiay", "2025-07-07T15:00:00Z"),
    ("v2_trip_005_05", "v2_drv_005", "v2_shift_005_2", "v2_veh_005", "Chuyến #061 (Cầu Giấy -> Hoàn Kiếm)", 55000, 8.5, 26, "completed", "v2_zone_caugiay", "v2_zone_hoankiem", "2025-07-15T08:15:00Z"),
    ("v2_trip_005_06", "v2_drv_005", "v2_shift_005_2", "v2_veh_005", "Chuyến #062 (Hoàn Kiếm -> Cầu Giấy)", 48000, 7.8, 24, "completed", "v2_zone_hoankiem", "v2_zone_caugiay", "2025-07-15T11:00:00Z"),
    ("v2_trip_005_07", "v2_drv_005", "v2_shift_005_2", "v2_veh_005", "Chuyến #063 (Cầu Giấy -> Nam Từ Liêm)", 40000, 5.5, 17, "completed", "v2_zone_caugiay", "v2_zone_namtuliem", "2025-07-15T13:30:00Z"),
    ("v2_trip_005_08", "v2_drv_005", "v2_shift_005_2", "v2_veh_005", "Chuyến #064 (Nam Từ Liêm -> Cầu Giấy)", 38000, 5.0, 16, "completed", "v2_zone_namtuliem", "v2_zone_caugiay", "2025-07-15T16:00:00Z"),
    ("v2_trip_005_09", "v2_drv_005", "v2_shift_005_3", "v2_veh_005", "Chuyến #065 (Cầu Giấy - Đơn nội khu)", 35000, 4.8, 16, "completed", "v2_zone_caugiay", "v2_zone_caugiay", "2025-07-22T08:00:00Z"),
    ("v2_trip_005_10", "v2_drv_005", "v2_shift_005_3", "v2_veh_005", "Chuyến #066 (Cầu Giấy -> Hoàn Kiếm - Phanh gấp)", 52000, 8.0, 22, "completed", "v2_zone_caugiay", "v2_zone_hoankiem", "2025-07-22T11:30:00Z"),
    ("v2_trip_005_11", "v2_drv_005", "v2_shift_005_3", "v2_veh_005", "Chuyến #067 (Hoàn Kiếm -> Cầu Giấy)", 50000, 7.8, 23, "completed", "v2_zone_hoankiem", "v2_zone_caugiay", "2025-07-22T14:45:00Z"),
    ("v2_trip_005_12", "v2_drv_005", "v2_shift_005_3", "v2_veh_005", "Chuyến #068 (Cầu Giấy -> Nam Từ Liêm)", 45000, 6.0, 18, "completed", "v2_zone_caugiay", "v2_zone_namtuliem", "2025-07-22T16:30:00Z"),
    ("v2_trip_005_13", "v2_drv_005", "v2_shift_005_4", "v2_veh_005", "Chuyến #069 (Cầu Giấy -> Hoàn Kiếm)", 55000, 8.6, 26, "completed", "v2_zone_caugiay", "v2_zone_hoankiem", "2025-07-29T08:30:00Z"),
    ("v2_trip_005_14", "v2_drv_005", "v2_shift_005_4", "v2_veh_005", "Chuyến #070 (Hoàn Kiếm -> Nam Từ Liêm)", 68000, 11.5, 32, "completed", "v2_zone_hoankiem", "v2_zone_namtuliem", "2025-07-29T12:00:00Z"),
    ("v2_trip_005_15", "v2_drv_005", "v2_shift_005_4", "v2_veh_005", "Chuyến #071 (Nam Từ Liêm -> Cầu Giấy)", 42000, 5.8, 17, "completed", "v2_zone_namtuliem", "v2_zone_caugiay", "2025-07-29T15:30:00Z"),

    # --- DRIVER 6: Hoàng Văn Thắng (VF 7 - Luxury Hà Nội) (13 trips, VIP 5 sao) ---
    ("v2_trip_006_01", "v2_drv_006", "v2_shift_006_1", "v2_veh_006", "Chuyến #072 (Nam Từ Liêm -> Hoàn Kiếm)", 165000, 12.0, 28, "completed", "v2_zone_namtuliem", "v2_zone_hoankiem", "2025-07-09T08:00:00Z"),
    ("v2_trip_006_02", "v2_drv_006", "v2_shift_006_1", "v2_veh_006", "Chuyến #073 (Hoàn Kiếm -> Nội Bài VIP)", 310000, 29.0, 42, "completed", "v2_zone_hoankiem", "v2_zone_noibai", "2025-07-09T11:15:00Z"),
    ("v2_trip_006_03", "v2_drv_006", "v2_shift_006_1", "v2_veh_006", "Chuyến #074 (Nội Bài -> Nam Từ Liêm)", 320000, 31.0, 45, "completed", "v2_zone_noibai", "v2_zone_namtuliem", "2025-07-09T14:30:00Z"),
    ("v2_trip_006_04", "v2_drv_006", "v2_shift_006_2", "v2_veh_006", "Chuyến #075 (Nam Từ Liêm -> Nội Bài - VIP SUV)", 320000, 31.5, 45, "completed", "v2_zone_namtuliem", "v2_zone_noibai", "2025-07-16T08:00:00Z"),
    ("v2_trip_006_05", "v2_drv_006", "v2_shift_006_2", "v2_veh_006", "Chuyến #076 (Nội Bài -> Cầu Giấy)", 275000, 25.5, 38, "completed", "v2_zone_noibai", "v2_zone_caugiay", "2025-07-16T11:30:00Z"),
    ("v2_trip_006_06", "v2_drv_006", "v2_shift_006_2", "v2_veh_006", "Chuyến #077 (Cầu Giấy -> Nam Từ Liêm)", 80000, 6.0, 17, "completed", "v2_zone_caugiay", "v2_zone_namtuliem", "2025-07-16T14:45:00Z"),
    ("v2_trip_006_07", "v2_drv_006", "v2_shift_006_3", "v2_veh_006", "Chuyến #078 (Nam Từ Liêm -> Hoàn Kiếm)", 170000, 12.5, 29, "completed", "v2_zone_namtuliem", "v2_zone_hoankiem", "2025-07-21T08:30:00Z"),
    ("v2_trip_006_08", "v2_drv_006", "v2_shift_006_3", "v2_veh_006", "Chuyến #079 (Hoàn Kiếm -> Nội Bài Ngoại Giao)", 330000, 29.5, 43, "completed", "v2_zone_hoankiem", "v2_zone_noibai", "2025-07-21T12:00:00Z"),
    ("v2_trip_006_09", "v2_drv_006", "v2_shift_006_3", "v2_veh_006", "Chuyến #080 (Nội Bài -> Nam Từ Liêm)", 325000, 31.0, 44, "completed", "v2_zone_noibai", "v2_zone_namtuliem", "2025-07-21T15:15:00Z"),
    ("v2_trip_006_10", "v2_drv_006", "v2_shift_006_4", "v2_veh_006", "Chuyến #081 (Nam Từ Liêm -> Cầu Giấy)", 85000, 6.5, 18, "completed", "v2_zone_namtuliem", "v2_zone_caugiay", "2025-07-25T09:15:00Z"),
    ("v2_trip_006_11", "v2_drv_006", "v2_shift_006_4", "v2_veh_006", "Chuyến #082 (Cầu Giấy -> Nội Bài)", 290000, 26.0, 40, "completed", "v2_zone_caugiay", "v2_zone_noibai", "2025-07-25T12:00:00Z"),
    ("v2_trip_006_12", "v2_drv_006", "v2_shift_006_4", "v2_veh_006", "Chuyến #083 (Nội Bài -> Nam Từ Liêm)", 325000, 32.0, 46, "completed", "v2_zone_noibai", "v2_zone_namtuliem", "2025-07-25T15:00:00Z"),
    ("v2_trip_006_13", "v2_drv_006", "v2_shift_006_4", "v2_veh_006", "Chuyến #084 (Nam Từ Liêm -> Hoàn Kiếm VIP)", 180000, 13.0, 30, "completed", "v2_zone_namtuliem", "v2_zone_hoankiem", "2025-07-25T16:45:00Z"),

    # --- DRIVER 7: Đỗ Minh Khang (VF 3 - TP.HCM) (13 trips, nhiều cuốc ảo & gian lận voucher) ---
    ("v2_trip_007_01", "v2_drv_007", "v2_shift_007_1", "v2_veh_007", "Chuyến #085 (Thủ Đức -> Quận 1)", 110000, 11.0, 25, "completed", "v2_zone_thuduc", "v2_zone_quan1", "2025-07-05T10:00:00Z"),
    ("v2_trip_007_02", "v2_drv_007", "v2_shift_007_1", "v2_veh_007", "Chuyến #086 (Quận 1 -> Thủ Đức)", 105000, 10.5, 24, "completed", "v2_zone_quan1", "v2_zone_thuduc", "2025-07-05T13:30:00Z"),
    ("v2_trip_007_03", "v2_drv_007", "v2_shift_007_1", "v2_veh_007", "Chuyến #087 (Thủ Đức -> Thủ Đức - Nghi ảo)", 60000, 4.0, 14, "completed", "v2_zone_thuduc", "v2_zone_thuduc", "2025-07-05T15:45:00Z"),
    ("v2_trip_007_04", "v2_drv_007", "v2_shift_007_2", "v2_veh_007", "Chuyến #088 (Thủ Đức -> Quận 1)", 115000, 11.2, 26, "completed", "v2_zone_thuduc", "v2_zone_quan1", "2025-07-11T10:30:00Z"),
    ("v2_trip_007_05", "v2_drv_007", "v2_shift_007_2", "v2_veh_007", "Chuyến #089 (Quận 1 -> Thủ Đức - Khách hủy ảo)", 105000, 10.5, 0, "cancelled_by_customer", "v2_zone_quan1", "v2_zone_thuduc", "2025-07-11T14:45:00Z"),
    ("v2_trip_007_06", "v2_drv_007", "v2_shift_007_2", "v2_veh_007", "Chuyến #090 (Thủ Đức -> Thủ Đức - Đơn ảo 1)", 50000, 3.2, 0, "cancelled_by_driver", "v2_zone_thuduc", "v2_zone_thuduc", "2025-07-11T16:15:00Z"),
    ("v2_trip_007_07", "v2_drv_007", "v2_shift_007_3", "v2_veh_007", "Chuyến #091 (Thủ Đức -> Quận 1)", 110000, 10.8, 25, "completed", "v2_zone_thuduc", "v2_zone_quan1", "2025-07-17T11:00:00Z"),
    ("v2_trip_007_08", "v2_drv_007", "v2_shift_007_3", "v2_veh_007", "Chuyến #092 (Quận 1 -> Thủ Đức)", 112000, 11.0, 26, "completed", "v2_zone_quan1", "v2_zone_thuduc", "2025-07-17T13:45:00Z"),
    ("v2_trip_007_09", "v2_drv_007", "v2_shift_007_3", "v2_veh_007", "Chuyến #093 (Thủ Đức -> Thủ Đức - GPS bất thường)", 70000, 5.0, 18, "completed", "v2_zone_thuduc", "v2_zone_thuduc", "2025-07-17T16:00:00Z"),
    ("v2_trip_007_10", "v2_drv_007", "v2_shift_007_4", "v2_veh_007", "Chuyến #094 (Thủ Đức -> Quận 1)", 115000, 11.5, 27, "completed", "v2_zone_thuduc", "v2_zone_quan1", "2025-07-21T11:30:00Z"),
    ("v2_trip_007_11", "v2_drv_007", "v2_shift_007_4", "v2_veh_007", "Chuyến #095 (Quận 1 -> Thủ Đức - Đơn ảo voucher)", 120000, 12.0, 0, "cancelled_by_customer", "v2_zone_quan1", "v2_zone_thuduc", "2025-07-21T14:15:00Z"),
    ("v2_trip_007_12", "v2_drv_007", "v2_shift_007_4", "v2_veh_007", "Chuyến #096 (Thủ Đức - Đơn ảo tự tạo lần 2)", 65000, 4.5, 0, "cancelled_by_driver", "v2_zone_thuduc", "v2_zone_thuduc", "2025-07-21T15:30:00Z"),
    ("v2_trip_007_13", "v2_drv_007", "v2_shift_007_4", "v2_veh_007", "Chuyến #097 (Thủ Đức - SIM rác tạo đơn ảo lần 3)", 75000, 5.5, 0, "cancelled_by_customer", "v2_zone_thuduc", "v2_zone_thuduc", "2025-07-21T17:00:00Z"),

    # --- DRIVER 8: Vũ Bích Ngọc (Klara S - Xe máy điện TP.HCM) (12 trips) ---
    ("v2_trip_008_01", "v2_drv_008", "v2_shift_008_1", "v2_veh_008", "Chuyến #098 (Tân Sơn Nhất -> Quận 1)", 45000, 6.8, 22, "completed", "v2_zone_tansonnhat", "v2_zone_quan1", "2025-07-04T07:30:00Z"),
    ("v2_trip_008_02", "v2_drv_008", "v2_shift_008_1", "v2_veh_008", "Chuyến #099 (Quận 1 -> Tân Sơn Nhất)", 40000, 6.2, 20, "completed", "v2_zone_quan1", "v2_zone_tansonnhat", "2025-07-04T10:00:00Z"),
    ("v2_trip_008_03", "v2_drv_008", "v2_shift_008_1", "v2_veh_008", "Chuyến #100 (Tân Sơn Nhất -> Tân Bình)", 30000, 4.0, 14, "completed", "v2_zone_tansonnhat", "v2_zone_tansonnhat", "2025-07-04T12:30:00Z"),
    ("v2_trip_008_04", "v2_drv_008", "v2_shift_008_2", "v2_veh_008", "Chuyến #101 (Tân Sơn Nhất -> Tân Bình)", 35000, 4.5, 15, "completed", "v2_zone_tansonnhat", "v2_zone_tansonnhat", "2025-07-09T08:00:00Z"),
    ("v2_trip_008_05", "v2_drv_008", "v2_shift_008_2", "v2_veh_008", "Chuyến #102 (Tân Sơn Nhất -> Quận 1)", 48000, 7.0, 23, "completed", "v2_zone_tansonnhat", "v2_zone_quan1", "2025-07-09T10:30:00Z"),
    ("v2_trip_008_06", "v2_drv_008", "v2_shift_008_2", "v2_veh_008", "Chuyến #103 (Quận 1 -> Tân Sơn Nhất)", 46000, 6.8, 22, "completed", "v2_zone_quan1", "v2_zone_tansonnhat", "2025-07-09T13:00:00Z"),
    ("v2_trip_008_07", "v2_drv_008", "v2_shift_008_3", "v2_veh_008", "Chuyến #104 (Tân Sơn Nhất -> Tân Bình)", 35000, 4.5, 15, "completed", "v2_zone_tansonnhat", "v2_zone_tansonnhat", "2025-07-14T08:00:00Z"),
    ("v2_trip_008_08", "v2_drv_008", "v2_shift_008_3", "v2_veh_008", "Chuyến #105 (Tân Sơn Nhất -> Tân Bình)", 45000, 5.5, 20, "completed", "v2_zone_tansonnhat", "v2_zone_tansonnhat", "2025-07-14T09:30:00Z"),
    ("v2_trip_008_09", "v2_drv_008", "v2_shift_008_3", "v2_veh_008", "Chuyến #106 (Tân Bình -> Quận 1)", 50000, 7.2, 24, "completed", "v2_zone_tansonnhat", "v2_zone_quan1", "2025-07-14T12:00:00Z"),
    ("v2_trip_008_10", "v2_drv_008", "v2_shift_008_4", "v2_veh_008", "Chuyến #107 (Quận 1 -> Tân Sơn Nhất)", 48000, 7.0, 22, "completed", "v2_zone_quan1", "v2_zone_tansonnhat", "2025-07-19T07:45:00Z"),
    ("v2_trip_008_11", "v2_drv_008", "v2_shift_008_4", "v2_veh_008", "Chuyến #108 (Tân Sơn Nhất -> Quận 1)", 45000, 6.5, 21, "completed", "v2_zone_tansonnhat", "v2_zone_quan1", "2025-07-19T10:15:00Z"),
    ("v2_trip_008_12", "v2_drv_008", "v2_shift_008_4", "v2_veh_008", "Chuyến #109 (Quận 1 -> Tân Bình)", 38000, 5.0, 16, "completed", "v2_zone_quan1", "v2_zone_tansonnhat", "2025-07-19T12:45:00Z"),

    # --- DRIVER 9: Bùi Đức Tiến (Toyota Vios - Xe xăng Đà Nẵng) (14 trips, thu quá cước & xe bẩn & ghép khách) ---
    ("v2_trip_009_01", "v2_drv_009", "v2_shift_009_1", "v2_veh_009", "Chuyến #110 (Hải Châu -> Hải Châu)", 65000, 4.2, 15, "completed", "v2_zone_haichau", "v2_zone_haichau", "2025-07-08T08:45:00Z"),
    ("v2_trip_009_02", "v2_drv_009", "v2_shift_009_1", "v2_veh_009", "Chuyến #111 (Hải Châu -> Cầu Rồng)", 80000, 5.5, 18, "completed", "v2_zone_haichau", "v2_zone_haichau", "2025-07-08T13:30:00Z"),
    ("v2_trip_009_03", "v2_drv_009", "v2_shift_009_1", "v2_veh_009", "Chuyến #112 (Cầu Rồng -> Hải Châu)", 85000, 5.8, 19, "completed", "v2_zone_haichau", "v2_zone_haichau", "2025-07-08T16:00:00Z"),
    ("v2_trip_009_04", "v2_drv_009", "v2_shift_009_2", "v2_veh_009", "Chuyến #113 (Hải Châu -> Hải Châu)", 70000, 4.5, 16, "completed", "v2_zone_haichau", "v2_zone_haichau", "2025-07-14T09:00:00Z"),
    ("v2_trip_009_05", "v2_drv_009", "v2_shift_009_2", "v2_veh_009", "Chuyến #114 (Hải Châu -> Cầu Rồng)", 90000, 6.0, 20, "completed", "v2_zone_haichau", "v2_zone_haichau", "2025-07-14T12:30:00Z"),
    ("v2_trip_009_06", "v2_drv_009", "v2_shift_009_2", "v2_veh_009", "Chuyến #115 (Cầu Rồng -> Hải Châu - Khói thuốc lá)", 85000, 5.7, 19, "completed", "v2_zone_haichau", "v2_zone_haichau", "2025-07-14T15:30:00Z"),
    ("v2_trip_009_07", "v2_drv_009", "v2_shift_009_3", "v2_veh_009", "Chuyến #116 (Hải Châu -> Cầu Rồng - Thu tiền sai 50k)", 95000, 6.8, 22, "completed", "v2_zone_haichau", "v2_zone_haichau", "2025-07-19T11:15:00Z"),
    ("v2_trip_009_08", "v2_drv_009", "v2_shift_009_3", "v2_veh_009", "Chuyến #117 (Cầu Rồng -> Hải Châu - Ghế bẩn cafe)", 90000, 6.0, 20, "completed", "v2_zone_haichau", "v2_zone_haichau", "2025-07-19T14:45:00Z"),
    ("v2_trip_009_09", "v2_drv_009", "v2_shift_009_3", "v2_veh_009", "Chuyến #118 (Hải Châu -> Cầu Rồng - Từ chối hành lý)", 85000, 5.5, 18, "completed", "v2_zone_haichau", "v2_zone_haichau", "2025-07-19T16:30:00Z"),
    ("v2_trip_009_10", "v2_drv_009", "v2_shift_009_4", "v2_veh_009", "Chuyến #119 (Hải Châu - Ép tip & giữ 30k thừa)", 75000, 5.0, 16, "completed", "v2_zone_haichau", "v2_zone_haichau", "2025-07-27T09:30:00Z"),
    ("v2_trip_009_11", "v2_drv_009", "v2_shift_009_4", "v2_veh_009", "Chuyến #120 (Hải Châu -> Cầu Rồng - Ghép khách lạ)", 120000, 8.5, 26, "completed", "v2_zone_haichau", "v2_zone_haichau", "2025-07-27T14:15:00Z"),
    ("v2_trip_009_12", "v2_drv_009", "v2_shift_009_4", "v2_veh_009", "Chuyến #121 (Cầu Rồng -> Hải Châu - Phóng nhanh đêm)", 105000, 7.2, 15, "completed", "v2_zone_haichau", "v2_zone_haichau", "2025-07-27T21:00:00Z"),
    ("v2_trip_009_13", "v2_drv_009", "v2_shift_009_4", "v2_veh_009", "Chuyến #122 (Hải Châu -> Hải Châu - Hơi cồn nghi vấn)", 65000, 4.0, 14, "completed", "v2_zone_haichau", "v2_zone_haichau", "2025-07-27T22:30:00Z"),
    ("v2_trip_009_14", "v2_drv_009", "v2_shift_009_4", "v2_veh_009", "Chuyến #123 (Hải Châu -> Cầu Rồng)", 80000, 5.2, 17, "completed", "v2_zone_haichau", "v2_zone_haichau", "2025-07-27T23:15:00Z"),

    # --- DRIVER 10: Trịnh Thanh Tùng (VF 6 - Hà Nội) (12 trips, chạy vòng & vượt đèn & thu sai phụ phí) ---
    ("v2_trip_010_01", "v2_drv_010", "v2_shift_010_1", "v2_veh_010", "Chuyến #124 (Cầu Giấy -> Hoàn Kiếm)", 140000, 10.5, 30, "completed", "v2_zone_caugiay", "v2_zone_hoankiem", "2025-07-06T09:00:00Z"),
    ("v2_trip_010_02", "v2_drv_010", "v2_shift_010_1", "v2_veh_010", "Chuyến #125 (Hoàn Kiếm -> Cầu Giấy)", 135000, 10.0, 28, "completed", "v2_zone_hoankiem", "v2_zone_caugiay", "2025-07-06T12:30:00Z"),
    ("v2_trip_010_03", "v2_drv_010", "v2_shift_010_1", "v2_veh_010", "Chuyến #126 (Cầu Giấy -> Cầu Giấy)", 50000, 4.2, 14, "completed", "v2_zone_caugiay", "v2_zone_caugiay", "2025-07-06T14:45:00Z"),
    ("v2_trip_010_04", "v2_drv_010", "v2_shift_010_2", "v2_veh_010", "Chuyến #127 (Cầu Giấy -> Hoàn Kiếm)", 145000, 10.5, 30, "completed", "v2_zone_caugiay", "v2_zone_hoankiem", "2025-07-12T09:00:00Z"),
    ("v2_trip_010_05", "v2_drv_010", "v2_shift_010_2", "v2_veh_010", "Chuyến #128 (Hoàn Kiếm -> Cầu Giấy - Vượt đèn vàng)", 155000, 11.0, 32, "completed", "v2_zone_hoankiem", "v2_zone_caugiay", "2025-07-12T13:30:00Z"),
    ("v2_trip_010_06", "v2_drv_010", "v2_shift_010_2", "v2_veh_010", "Chuyến #129 (Cầu Giấy -> Nam Từ Liêm)", 80000, 6.2, 18, "completed", "v2_zone_caugiay", "v2_zone_namtuliem", "2025-07-12T15:30:00Z"),
    ("v2_trip_010_07", "v2_drv_010", "v2_shift_010_3", "v2_veh_010", "Chuyến #130 (Cầu Giấy -> Hoàn Kiếm - Đi vòng xa)", 185000, 13.8, 38, "completed", "v2_zone_caugiay", "v2_zone_hoankiem", "2025-07-23T15:15:00Z"),
    ("v2_trip_010_08", "v2_drv_010", "v2_shift_010_3", "v2_veh_010", "Chuyến #131 (Hoàn Kiếm -> Cầu Giấy)", 135000, 9.8, 28, "completed", "v2_zone_hoankiem", "v2_zone_caugiay", "2025-07-23T17:45:00Z"),
    ("v2_trip_010_09", "v2_drv_010", "v2_shift_010_4", "v2_veh_010", "Chuyến #132 (Cầu Giấy -> Nội Bài - Thu sai phụ phí)", 310000, 27.0, 42, "completed", "v2_zone_caugiay", "v2_zone_noibai", "2025-07-29T10:15:00Z"),
    ("v2_trip_010_10", "v2_drv_010", "v2_shift_010_4", "v2_veh_010", "Chuyến #133 (Nội Bài -> Hoàn Kiếm)", 290000, 28.0, 40, "completed", "v2_zone_noibai", "v2_zone_hoankiem", "2025-07-29T13:00:00Z"),
    ("v2_trip_010_11", "v2_drv_010", "v2_shift_010_4", "v2_veh_010", "Chuyến #134 (Hoàn Kiếm -> Cầu Giấy - Thả khách xa)", 140000, 10.2, 29, "completed", "v2_zone_hoankiem", "v2_zone_caugiay", "2025-07-29T15:30:00Z"),
    ("v2_trip_010_12", "v2_drv_010", "v2_shift_010_4", "v2_veh_010", "Chuyến #135 (Cầu Giấy -> Nam Từ Liêm)", 75000, 6.0, 17, "completed", "v2_zone_caugiay", "v2_zone_namtuliem", "2025-07-29T17:00:00Z"),
]

# =========================================================================
# 8. INCIDENTS & VIOLATIONS (32 Incidents)
# =========================================================================
INCIDENTS_DATA = [
    {
        "id": "v2_inc_001",
        "incident_id": "v2_inc_001",
        "name": "Sự cố: Hủy chuyến bất thường giờ cao điểm (Lê Văn Hùng)",
        "driver_id": "v2_drv_002",
        "shift_id": "v2_shift_002_3",
        "type": "abnormal_cancellation",
        "timestamp": "2025-07-20T08:35:00Z",
        "severity": "medium",
        "description": "Hủy 3 cuốc liên tiếp vào khung giờ cao điểm sáng tại khu vực Hoàn Kiếm không lý do chính đáng",
        "fault_rate": 100,
        "penalty_points": 5,
        "violates_rules": ["v2_rule_p154"],
        "detected_by": "system_dispatch_audit",
    },
    {
        "id": "v2_inc_002",
        "incident_id": "v2_inc_002",
        "name": "Sự cố: Chạy quá tốc độ & lái xe ẩu (Phạm Thị Mai)",
        "driver_id": "v2_drv_004",
        "shift_id": "v2_shift_004_4",
        "type": "overspeeding",
        "timestamp": "2025-07-18T10:15:00Z",
        "severity": "high",
        "description": "Chạy quá tốc độ 82km/h tại đoạn đường đô thị giới hạn 50km/h trên tuyến sân bay Tân Sơn Nhất",
        "fault_rate": 100,
        "penalty_points": 10,
        "violates_rules": ["v2_rule_safety_speed", "v2_rule_p23_attitude"],
        "detected_by": "telematics_iot_sensor",
    },
    {
        "id": "v2_inc_003",
        "incident_id": "v2_inc_003",
        "name": "Sự cố: Gian lận voucher khuyến mãi tạo cuốc ảo (Đỗ Minh Khang)",
        "driver_id": "v2_drv_007",
        "shift_id": "v2_shift_007_4",
        "type": "promotion_fraud",
        "timestamp": "2025-07-21T14:30:00Z",
        "severity": "critical",
        "description": "Phát hiện tài xế sử dụng thiết bị phụ tự đặt 4 đơn ảo trong 2 giờ nhằm chiếm đoạt voucher giảm giá 100,000 VND",
        "fault_rate": 100,
        "penalty_points": 25,
        "violates_rules": ["v2_rule_fraud_promo"],
        "detected_by": "fraud_detection_engine",
    },
    {
        "id": "v2_inc_004",
        "incident_id": "v2_inc_004",
        "name": "Sự cố: Thu quá cước và xe bẩn khói thuốc (Bùi Đức Tiến)",
        "driver_id": "v2_drv_009",
        "shift_id": "v2_shift_009_3",
        "type": "overcharging_and_hygiene",
        "timestamp": "2025-07-19T11:30:00Z",
        "severity": "medium",
        "description": "Tài xế tự ý thu thêm 50,000 VND phụ phí hành lý không có trong app và để xe bốc mùi khói thuốc lá",
        "fault_rate": 100,
        "penalty_points": 8,
        "violates_rules": ["v2_rule_tariff_overcharge", "v2_rule_vehicle_hygiene", "v2_rule_p23_attitude"],
        "detected_by": "customer_complaint_audit",
    },
    {
        "id": "v2_inc_005",
        "incident_id": "v2_inc_005",
        "name": "Sự cố: Vi phạm lộ trình chạy vòng ép giá cước (Trịnh Thanh Tùng)",
        "driver_id": "v2_drv_010",
        "shift_id": "v2_shift_010_3",
        "type": "route_deviation",
        "timestamp": "2025-07-23T15:45:00Z",
        "severity": "medium",
        "description": "Cố ý chạy vòng thêm 6.5km so với lộ trình gợi ý của GPS bản đồ nhằm tăng cước của khách du lịch",
        "fault_rate": 100,
        "penalty_points": 6,
        "violates_rules": ["v2_rule_route_deviation"],
        "detected_by": "gps_telematics_audit",
    },
    {
        "id": "v2_inc_006",
        "incident_id": "v2_inc_006",
        "name": "Sự cố: Từ chối bật điều hòa giữa trưa nắng (Lê Văn Hùng)",
        "driver_id": "v2_drv_002",
        "shift_id": "v2_shift_002_3",
        "type": "service_attitude_violation",
        "timestamp": "2025-07-20T12:00:00Z",
        "severity": "low",
        "description": "Tài xế kiên quyết tắt máy lạnh giữa trưa nắng 38°C để tiết kiệm điện xe e34 và to tiếng với khách",
        "fault_rate": 100,
        "penalty_points": 4,
        "violates_rules": ["v2_rule_p23_attitude"],
        "detected_by": "customer_complaint_audit",
    },
    {
        "id": "v2_inc_007",
        "incident_id": "v2_inc_007",
        "name": "Sự cố: Hủy chuyến hàng loạt khi trời mưa bão (Lê Văn Hùng)",
        "driver_id": "v2_drv_002",
        "shift_id": "v2_shift_002_4",
        "type": "abnormal_cancellation",
        "timestamp": "2025-07-28T14:15:00Z",
        "severity": "high",
        "description": "Tài xế hủy liên tiếp 4 cuốc nhận khi trời mưa to gió lớn tại khu vực Hoàn Kiếm, tỷ lệ hủy ngày vượt 25%",
        "fault_rate": 100,
        "penalty_points": 8,
        "violates_rules": ["v2_rule_p154"],
        "detected_by": "system_dispatch_audit",
    },
    {
        "id": "v2_inc_008",
        "incident_id": "v2_inc_008",
        "name": "Sự cố: Vượt đèn tín hiệu ngã tư nguy hiểm (Trịnh Thanh Tùng)",
        "driver_id": "v2_drv_010",
        "shift_id": "v2_shift_010_2",
        "type": "traffic_light_violation",
        "timestamp": "2025-07-12T13:45:00Z",
        "severity": "medium",
        "description": "Camera hành trình AI ghi nhận xe vượt đèn vàng khi đang có người đi bộ qua đường tại ngã tư Cầu Giấy",
        "fault_rate": 100,
        "penalty_points": 7,
        "violates_rules": ["v2_rule_safety_speed", "v2_rule_p23_attitude"],
        "detected_by": "telematics_iot_sensor",
    },
    {
        "id": "v2_inc_009",
        "incident_id": "v2_inc_009",
        "name": "Sự cố: Đến điểm đón trễ 25 phút không liên hệ (Phạm Thị Mai)",
        "driver_id": "v2_drv_004",
        "shift_id": "v2_shift_004_2",
        "type": "late_pickup_abandonment",
        "timestamp": "2025-07-10T14:20:00Z",
        "severity": "medium",
        "description": "Nhận cuốc đi sân bay Tân Sơn Nhất nhưng đứng yên một chỗ 25 phút không liên lạc làm khách suýt trễ giờ check-in",
        "fault_rate": 100,
        "penalty_points": 5,
        "violates_rules": ["v2_rule_p151", "v2_rule_p23_attitude"],
        "detected_by": "customer_complaint_audit",
    },
    {
        "id": "v2_inc_010",
        "incident_id": "v2_inc_010",
        "name": "Sự cố: Tái diễn đặt cuốc ảo trục lợi voucher (Đỗ Minh Khang)",
        "driver_id": "v2_drv_007",
        "shift_id": "v2_shift_007_4",
        "type": "promotion_fraud",
        "timestamp": "2025-07-21T16:00:00Z",
        "severity": "critical",
        "description": "Tiếp tục dùng SIM rác thứ 3 để tạo cuốc ảo khứ hồi Thủ Đức ngay sau khi bị hệ thống nhắc nhở",
        "fault_rate": 100,
        "penalty_points": 30,
        "violates_rules": ["v2_rule_fraud_promo"],
        "detected_by": "fraud_detection_engine",
    },
    {
        "id": "v2_inc_011",
        "incident_id": "v2_inc_011",
        "name": "Sự cố: Giữ lại tiền thừa và ép trả tiền boa (Bùi Đức Tiến)",
        "driver_id": "v2_drv_009",
        "shift_id": "v2_shift_009_4",
        "type": "overcharging",
        "timestamp": "2025-07-27T10:00:00Z",
        "severity": "medium",
        "description": "Cước 70k khách đưa 100k, tài xế không trả lại 30k và tự ý xem đó là tiền boa phục vụ rồi khóa cửa xe",
        "fault_rate": 100,
        "penalty_points": 9,
        "violates_rules": ["v2_rule_tariff_overcharge", "v2_rule_p23_attitude"],
        "detected_by": "customer_complaint_audit",
    },
    {
        "id": "v2_inc_012",
        "incident_id": "v2_inc_012",
        "name": "Sự cố: Cố tình đi vào đường cấm làm trễ chuyến bay (Phạm Thị Mai)",
        "driver_id": "v2_drv_004",
        "shift_id": "v2_shift_004_4",
        "type": "route_deviation",
        "timestamp": "2025-07-18T15:00:00Z",
        "severity": "high",
        "description": "Không tuân thủ lộ trình bản đồ hướng dẫn, đi vào đường một chiều bị cảnh sát giao thông nhắc nhở làm khách trễ chuyến bay",
        "fault_rate": 100,
        "penalty_points": 12,
        "violates_rules": ["v2_rule_route_deviation", "v2_rule_p23_attitude"],
        "detected_by": "customer_complaint_audit",
    },
    {
        "id": "v2_inc_013",
        "incident_id": "v2_inc_013",
        "name": "Sự cố: Ghép thêm khách lạ vào chuyến đi riêng (Bùi Đức Tiến)",
        "driver_id": "v2_drv_009",
        "shift_id": "v2_shift_009_4",
        "type": "unauthorized_carpooling",
        "timestamp": "2025-07-27T14:40:00Z",
        "severity": "medium",
        "description": "Tài xế dừng đón thêm người quen đi chung mà không có sự đồng ý của khách hàng đã đặt cuốc xe riêng",
        "fault_rate": 100,
        "penalty_points": 8,
        "violates_rules": ["v2_rule_p23_attitude"],
        "detected_by": "customer_complaint_audit",
    },
    {
        "id": "v2_inc_014",
        "incident_id": "v2_inc_014",
        "name": "Sự cố: Phóng nhanh 75km/h trên cầu Rồng ban đêm (Bùi Đức Tiến)",
        "driver_id": "v2_drv_009",
        "shift_id": "v2_shift_009_4",
        "type": "overspeeding",
        "timestamp": "2025-07-27T21:15:00Z",
        "severity": "high",
        "description": "Chạy quá tốc độ quy định trên cầu Rồng (giới hạn 40km/h khu vực cầu ngắm cảnh du lịch)",
        "fault_rate": 100,
        "penalty_points": 10,
        "violates_rules": ["v2_rule_safety_speed"],
        "detected_by": "telematics_iot_sensor",
    },
    {
        "id": "v2_inc_015",
        "incident_id": "v2_inc_015",
        "name": "Sự cố: Phanh gấp suýt ngã xe máy khi chở khách (Đặng Văn Phúc)",
        "driver_id": "v2_drv_005",
        "shift_id": "v2_shift_005_3",
        "type": "reckless_driving_incident",
        "timestamp": "2025-07-22T13:45:00Z",
        "severity": "low",
        "description": "Phanh gấp để tránh xe máy khác tạt đầu trên đường Cầu Giấy khiến khách nữ giật mình khiếu nại (tài xế lỗi 50%)",
        "fault_rate": 50,
        "penalty_points": 2,
        "violates_rules": ["v2_rule_p23_attitude"],
        "detected_by": "customer_complaint_audit",
    },
    {
        "id": "v2_inc_016",
        "incident_id": "v2_inc_016",
        "name": "Sự cố: Pin cạn dưới 2% trên đường vành đai (Lê Văn Hùng)",
        "driver_id": "v2_drv_002",
        "shift_id": "v2_shift_002_2",
        "type": "battery_depletion",
        "timestamp": "2025-07-15T12:00:00Z",
        "severity": "medium",
        "description": "Không chủ động sạc pin xe e34 khi dung lượng xuống dưới 15%, dẫn tới cạn pin giữa đường phải gọi xe cứu hộ",
        "fault_rate": 100,
        "penalty_points": 5,
        "violates_rules": ["v2_rule_p151"],
        "detected_by": "telematics_iot_sensor",
    },
    {
        "id": "v2_inc_017",
        "incident_id": "v2_inc_017",
        "name": "Sự cố: Va quẹt trầy cản sau tại hầm gửi xe (Nguyễn Hoàng Nam)",
        "driver_id": "v2_drv_003",
        "shift_id": "v2_shift_003_3",
        "type": "minor_collision",
        "timestamp": "2025-07-18T15:30:00Z",
        "severity": "low",
        "description": "Lùi xe vào cột hầm TTTM Quận 1 làm trầy xước cản sau xe VF 5, tự giác báo cáo về Hub quản lý",
        "fault_rate": 100,
        "penalty_points": 2,
        "violates_rules": ["v2_rule_safety_speed"],
        "detected_by": "safety_supervisor",
    },
    {
        "id": "v2_inc_018",
        "incident_id": "v2_inc_018",
        "name": "Sự cố: Tranh cãi gay gắt về điểm trả khách (Lê Văn Hùng)",
        "driver_id": "v2_drv_002",
        "shift_id": "v2_shift_002_3",
        "type": "service_attitude_violation",
        "timestamp": "2025-07-20T16:15:00Z",
        "severity": "medium",
        "description": "Không chịu dừng đúng số nhà trong ngõ Hoàn Kiếm, bắt khách đi bộ dưới nắng và to tiếng khi khách nhắc nhở",
        "fault_rate": 100,
        "penalty_points": 6,
        "violates_rules": ["v2_rule_p23_attitude"],
        "detected_by": "customer_complaint_audit",
    },
    {
        "id": "v2_inc_019",
        "incident_id": "v2_inc_019",
        "name": "Sự cố: Cảnh báo gia tốc giật & đánh lái gắt (Phạm Thị Mai)",
        "driver_id": "v2_drv_004",
        "shift_id": "v2_shift_004_3",
        "type": "telematics_alert",
        "timestamp": "2025-07-14T13:30:00Z",
        "severity": "medium",
        "description": "Hệ thống Telematics ghi nhận 6 lần phanh gấp và 4 lần đánh lái gắt trên đoạn đường 5km",
        "fault_rate": 100,
        "penalty_points": 4,
        "violates_rules": ["v2_rule_safety_speed"],
        "detected_by": "telematics_iot_sensor",
    },
    {
        "id": "v2_inc_020",
        "incident_id": "v2_inc_020",
        "name": "Sự cố: Từ chối nhận chuyến giờ mưa cao điểm (Lê Văn Hùng)",
        "driver_id": "v2_drv_002",
        "shift_id": "v2_shift_002_4",
        "type": "dispatch_refusal",
        "timestamp": "2025-07-28T16:00:00Z",
        "severity": "high",
        "description": "Tắt nhận cuốc tự động và từ chối 5 điều phối liên tiếp trong lúc tổng đài thiếu xe giờ bão",
        "fault_rate": 100,
        "penalty_points": 8,
        "violates_rules": ["v2_rule_p151", "v2_rule_p154"],
        "detected_by": "system_dispatch_audit",
    },
    {
        "id": "v2_inc_021",
        "incident_id": "v2_inc_021",
        "name": "Sự cố: Thu thêm phụ phí cổng sân bay sai quy định (Trịnh Thanh Tùng)",
        "driver_id": "v2_drv_010",
        "shift_id": "v2_shift_010_4",
        "type": "overcharging",
        "timestamp": "2025-07-29T10:45:00Z",
        "severity": "medium",
        "description": "Tự ý yêu cầu khách trả thêm 20,000 VND vé vào cổng Nội Bài dù hệ thống app đã tự động cộng tiền",
        "fault_rate": 100,
        "penalty_points": 5,
        "violates_rules": ["v2_rule_tariff_overcharge"],
        "detected_by": "customer_complaint_audit",
    },
    {
        "id": "v2_inc_022",
        "incident_id": "v2_inc_022",
        "name": "Sự cố: Cảnh báo can thiệp định vị GPS giả lập (Đỗ Minh Khang)",
        "driver_id": "v2_drv_007",
        "shift_id": "v2_shift_007_3",
        "type": "gps_spoofing",
        "timestamp": "2025-07-17T16:20:00Z",
        "severity": "critical",
        "description": "Phát hiện tọa độ GPS nhảy vọt 15km trong 3 giây nghi vấn sử dụng phần mềm fake GPS giả lập vị trí",
        "fault_rate": 100,
        "penalty_points": 20,
        "violates_rules": ["v2_rule_fraud_promo"],
        "detected_by": "fraud_detection_engine",
    },
    {
        "id": "v2_inc_023",
        "incident_id": "v2_inc_023",
        "name": "Sự cố: Cốp xe đầy đồ riêng từ chối chở vali khách (Bùi Đức Tiến)",
        "driver_id": "v2_drv_009",
        "shift_id": "v2_shift_009_3",
        "type": "service_attitude_violation",
        "timestamp": "2025-07-19T16:45:00Z",
        "severity": "medium",
        "description": "Để thùng hàng cá nhân chiếm hết khoang hành lý cốp sau xe Vios và từ chối chở vali của 2 hành khách",
        "fault_rate": 100,
        "penalty_points": 6,
        "violates_rules": ["v2_rule_vehicle_hygiene", "v2_rule_p23_attitude"],
        "detected_by": "customer_complaint_audit",
    },
    {
        "id": "v2_inc_024",
        "incident_id": "v2_inc_024",
        "name": "Sự cố: Ghế nỉ dính vết bẩn cà phê làm bẩn áo khách (Bùi Đức Tiến)",
        "driver_id": "v2_drv_009",
        "shift_id": "v2_shift_009_3",
        "type": "hygiene_violation",
        "timestamp": "2025-07-19T15:00:00Z",
        "severity": "low",
        "description": "Không vệ sinh ghế sau sau khi đổ cà phê, khiến vết bẩn dính vào đầm dạ hội của khách hàng",
        "fault_rate": 100,
        "penalty_points": 4,
        "violates_rules": ["v2_rule_vehicle_hygiene"],
        "detected_by": "customer_complaint_audit",
    },
    {
        "id": "v2_inc_025",
        "incident_id": "v2_inc_025",
        "name": "Sự cố: Bám đuôi xe trước sát nút và liên tục bấm còi (Phạm Thị Mai)",
        "driver_id": "v2_drv_004",
        "shift_id": "v2_shift_004_3",
        "type": "reckless_driving_incident",
        "timestamp": "2025-07-14T13:15:00Z",
        "severity": "medium",
        "description": "Bám đuôi xe tải ở khoảng cách dưới 2m trên đường Trường Sơn và liên tục bấm còi gây hoảng sợ",
        "fault_rate": 100,
        "penalty_points": 5,
        "violates_rules": ["v2_rule_safety_speed", "v2_rule_p23_attitude"],
        "detected_by": "customer_complaint_audit",
    },
    {
        "id": "v2_inc_026",
        "incident_id": "v2_inc_026",
        "name": "Sự cố: Điểm đánh giá trung bình tuần rơi dưới 4.0 sao (Đỗ Minh Khang)",
        "driver_id": "v2_drv_007",
        "shift_id": "v2_shift_007_3",
        "type": "low_rating_alert",
        "timestamp": "2025-07-17T17:00:00Z",
        "severity": "high",
        "description": "Điểm sao trung bình 7 ngày liên tiếp chỉ đạt 3.82 sao, kích hoạt cảnh báo suy giảm chất lượng dịch vụ",
        "fault_rate": 100,
        "penalty_points": 10,
        "violates_rules": ["v2_rule_p23_attitude"],
        "detected_by": "system_dispatch_audit",
    },
    {
        "id": "v2_inc_027",
        "incident_id": "v2_inc_027",
        "name": "Sự cố: Thả khách cách điểm đến 300m vì ngại quay đầu xe (Trịnh Thanh Tùng)",
        "driver_id": "v2_drv_010",
        "shift_id": "v2_shift_010_4",
        "type": "early_dropoff",
        "timestamp": "2025-07-29T16:00:00Z",
        "severity": "medium",
        "description": "Không chịu quay đầu xe theo định vị, yêu cầu khách đi bộ 300m qua đường mưa lớn",
        "fault_rate": 100,
        "penalty_points": 5,
        "violates_rules": ["v2_rule_p23_attitude", "v2_rule_route_deviation"],
        "detected_by": "customer_complaint_audit",
    },
    {
        "id": "v2_inc_028",
        "incident_id": "v2_inc_028",
        "name": "Sự cố: Hủy chuyến khi thấy khách mang theo lồng thú cưng (Lê Văn Hùng)",
        "driver_id": "v2_drv_002",
        "shift_id": "v2_shift_002_2",
        "type": "pet_refusal",
        "timestamp": "2025-07-15T15:00:00Z",
        "severity": "low",
        "description": "Khách có lồng vận chuyển mèo đúng quy cách nhưng tài xế gạt tay từ chối và bấm hủy chuyến",
        "fault_rate": 100,
        "penalty_points": 3,
        "violates_rules": ["v2_rule_p154", "v2_rule_p23_attitude"],
        "detected_by": "customer_complaint_audit",
    },
    {
        "id": "v2_inc_029",
        "incident_id": "v2_inc_029",
        "name": "Sự cố: Kích hoạt nút SOS khẩn cấp trong chuyến đi (Phạm Thị Mai)",
        "driver_id": "v2_drv_004",
        "shift_id": "v2_shift_004_4",
        "type": "sos_alert",
        "timestamp": "2025-07-18T16:45:00Z",
        "severity": "critical",
        "description": "Hành khách nữ nhấn nút SOS trên app do tài xế lái xe tốc độ cao, liên tục phanh giật và không trả lời",
        "fault_rate": 100,
        "penalty_points": 15,
        "violates_rules": ["v2_rule_safety_speed", "v2_rule_p23_attitude"],
        "detected_by": "customer_complaint_audit",
    },
    {
        "id": "v2_inc_030",
        "incident_id": "v2_inc_030",
        "name": "Sự cố: Hút thuốc lá trong cabin xe giữa các cuốc nhận (Bùi Đức Tiến)",
        "driver_id": "v2_drv_009",
        "shift_id": "v2_shift_009_2",
        "type": "smoking_in_cabin",
        "timestamp": "2025-07-14T15:45:00Z",
        "severity": "medium",
        "description": "Hút thuốc lá trong xe đóng kín cửa điều hòa làm ám mùi khét lẹt cho chuyến xe kế tiếp",
        "fault_rate": 100,
        "penalty_points": 6,
        "violates_rules": ["v2_rule_vehicle_hygiene"],
        "detected_by": "customer_complaint_audit",
    },
    {
        "id": "v2_inc_031",
        "incident_id": "v2_inc_031",
        "name": "Sự cố: Cố tình lội nước ngập sâu quá mức an toàn khuyến nghị (Lê Văn Hùng)",
        "driver_id": "v2_drv_002",
        "shift_id": "v2_shift_002_4",
        "type": "ev_water_wading",
        "timestamp": "2025-07-28T17:30:00Z",
        "severity": "high",
        "description": "Lái xe VF e34 lội qua đoạn ngập quá nửa bánh xe tại phố Tràng Tiền làm kích hoạt cảnh báo an toàn điện",
        "fault_rate": 100,
        "penalty_points": 8,
        "violates_rules": ["v2_rule_safety_speed"],
        "detected_by": "telematics_iot_sensor",
    },
    {
        "id": "v2_inc_032",
        "incident_id": "v2_inc_032",
        "name": "Sự cố: Phát hiện nồng độ cồn khi kiểm tra đột xuất tại Hub (Bùi Đức Tiến)",
        "driver_id": "v2_drv_009",
        "shift_id": "v2_shift_009_4",
        "type": "alcohol_violation",
        "timestamp": "2025-07-27T23:30:00Z",
        "severity": "critical",
        "description": "Kiểm tra nồng độ cồn ngẫu nhiên qua hơi thở tại cổng Hub Đà Nẵng phát hiện chỉ số 0.12 mg/L khí thở",
        "fault_rate": 100,
        "penalty_points": 30,
        "violates_rules": ["v2_rule_safety_speed", "v2_rule_p23_attitude"],
        "detected_by": "breathalyzer_test",
    },
]

# =========================================================================
# 9. CUSTOMER COMPLAINTS (38 Complaints)
# =========================================================================
COMPLAINTS_DATA = [
    # (complaint_id, trip_id, escalated_to_inc, violates_rule, category, sentiment, created_at, channel, name, content)
    ("v2_comp_001", "v2_trip_004_10", "v2_inc_002", "v2_rule_p23_attitude", "reckless_driving", -0.89, "2025-07-18T10:45:00Z", "customer_hotline", "Khiếu nại: Lái xe ẩu & phóng nhanh phanh gấp", "Khách hàng phản ánh tài xế phóng nhanh vượt ẩu, phanh gấp khiến hành khách hoảng sợ và say xe"),
    ("v2_comp_002", "v2_trip_009_07", "v2_inc_004", "v2_rule_tariff_overcharge", "overcharging", -0.92, "2025-07-19T11:45:00Z", "mobile_app", "Khiếu nại: Thu tiền cước sai quy định", "Tài xế đòi thêm 50,000 VND tiền mặt phụ phí hành lý dù app không thông báo, nói năng hách dịch"),
    ("v2_comp_003", "v2_trip_009_07", "v2_inc_004", "v2_rule_vehicle_hygiene", "dirty_vehicle", -0.78, "2025-07-19T12:00:00Z", "mobile_app", "Khiếu nại: Xe bẩn và nồng nặc khói thuốc", "Xe Toyota Vios bốc mùi thuốc lá nồng nặc, sàn xe đầy tàn thuốc và rác giấy vụn chưa dọn"),
    ("v2_comp_004", "v2_trip_010_07", "v2_inc_005", "v2_rule_p23_attitude", "attitude", -0.85, "2025-07-23T16:10:00Z", "mobile_app", "Khiếu nại: Thái độ gắt gỏng khi khách hỏi đường", "Khi khách hỏi sao không đi theo đường trên app mà đi vòng, tài xế lớn tiếng quát nạt và tắt điều hòa"),
    ("v2_comp_005", "v2_trip_002_08", "v2_inc_006", "v2_rule_p23_attitude", "comfort_ac", -0.82, "2025-07-20T12:15:00Z", "mobile_app", "Khiếu nại: Tài xế không bật điều hòa trưa nắng", "Trời trưa nắng gay gắt nhưng tài xế kiên quyết không bật điều hòa, bảo đi giá rẻ ráng chịu nóng"),
    ("v2_comp_006", "v2_trip_002_11", "v2_inc_007", "v2_rule_p154", "cancellation", -0.90, "2025-07-28T09:30:00Z", "customer_hotline", "Khiếu nại: Bắt khách đợi 15 phút rồi tự hủy", "Trời mưa to bắt khách đứng ngoài hè 15 phút rồi bấm hủy chuyến không một lời giải thích"),
    ("v2_comp_007", "v2_trip_010_05", "v2_inc_008", "v2_rule_safety_speed", "reckless_driving", -0.95, "2025-07-12T13:50:00Z", "mobile_app", "Khiếu nại: Vượt đèn tín hiệu giao thông", "Tài xế cố tình nhấn ga vượt đèn vàng suýt đâm vào xe khác ở ngã tư, khách cực kỳ hoảng sợ"),
    ("v2_comp_008", "v2_trip_004_05", "v2_inc_009", "v2_rule_p23_attitude", "late_pickup", -0.88, "2025-07-10T14:30:00Z", "customer_hotline", "Khiếu nại: Đón trễ 25 phút không báo trước", "Tài xế đứng im tại chỗ 25 phút không chịu đi đón, gọi điện không bắt máy làm suýt trễ giờ bay"),
    ("v2_comp_009", "v2_trip_007_12", "v2_inc_010", "v2_rule_fraud_promo", "attitude", -0.94, "2025-07-21T16:15:00Z", "mobile_app", "Khiếu nại: Đơn hàng bất thường bị tự ý hoàn thành", "Khách hàng nhận thông báo cuốc xe hoàn thành trong khi chưa từng bước lên xe"),
    ("v2_comp_010", "v2_trip_009_10", "v2_inc_011", "v2_rule_tariff_overcharge", "overcharging", -0.91, "2025-07-27T10:15:00Z", "mobile_app", "Khiếu nại: Không trả lại 30k tiền thừa", "Khách đưa 100k tiền mặt cho cuốc 70k, tài xế giữ luôn bảo tiền boa không thối lại"),
    ("v2_comp_011", "v2_trip_004_11", "v2_inc_012", "v2_rule_route_deviation", "route_deviation", -0.79, "2025-07-18T15:15:00Z", "customer_hotline", "Khiếu nại: Đi vào đường cấm làm trễ chuyến bay", "Tài xế không nghe khách nhắc đường, cố tình chạy vào đường một chiều dẫn đến trễ chuyến bay Tân Sơn Nhất"),
    ("v2_comp_012", "v2_trip_009_08", "v2_inc_024", "v2_rule_vehicle_hygiene", "dirty_vehicle", -0.65, "2025-07-19T15:30:00Z", "mobile_app", "Khiếu nại: Ghế xe dính vết ố cà phê bẩn", "Ghế ngồi hàng sau dính vết cà phê loang lổ chưa lau dọn, làm bẩn áo sơ mi trắng của khách"),
    ("v2_comp_013", "v2_trip_009_11", "v2_inc_013", "v2_rule_p23_attitude", "unauthorized_carpooling", -0.87, "2025-07-27T15:00:00Z", "customer_hotline", "Khiếu nại: Tự ý chở thêm người lạ ghép xe", "Tôi đặt cuốc xe riêng nhưng tài xế tạt vào đón thêm một người lạ bảo tiện đường về cùng"),
    ("v2_comp_014", "v2_trip_009_12", "v2_inc_014", "v2_rule_safety_speed", "reckless_driving", -0.84, "2025-07-27T21:30:00Z", "mobile_app", "Khiếu nại: Phóng xe như bay trên cầu Rồng", "Đêm vắng tài xế đạp ga hơn 70km/h trên cầu Rồng, bóp còi inh ỏi làm khách rất bất an"),
    ("v2_comp_015", "v2_trip_005_10", "v2_inc_015", "v2_rule_p23_attitude", "reckless_driving", -0.45, "2025-07-22T14:00:00Z", "mobile_app", "Khiếu nại: Xe máy phanh gấp suýt ngã", "Tài xế phanh gấp khi tránh xe khác làm tôi giật mình suýt rớt điện thoại"),
    ("v2_comp_016", "v2_trip_010_09", "v2_inc_021", "v2_rule_tariff_overcharge", "overcharging", -0.86, "2025-07-29T11:00:00Z", "mobile_app", "Khiếu nại: Thu thêm phụ phí sân bay sai quy định", "Tài xế đòi thêm 20,000 VND vé vào cổng Nội Bài dù hệ thống đã tự động cộng vào cước app"),
    ("v2_comp_017", "v2_trip_002_02", None, "v2_rule_p154", "cancellation", -0.68, "2025-07-08T12:30:00Z", "mobile_app", "Khiếu nại: Tài xế gọi điện yêu cầu hủy chuyến", "Tài xế gọi kêu bận ăn cơm bảo khách bấm hủy giùm để không bị phạt"),
    ("v2_comp_018", "v2_trip_002_05", "v2_inc_016", "v2_rule_p151", "cancellation", -0.75, "2025-07-15T11:45:00Z", "mobile_app", "Khiếu nại: Bị hủy chuyến vì tài xế hết pin", "Đang vội đi sân bay thì tài xế bảo xe sắp hết pin không đi được rồi tự hủy cuốc"),
    ("v2_comp_019", "v2_trip_002_10", "v2_inc_018", "v2_rule_p23_attitude", "attitude", -0.89, "2025-07-20T16:30:00Z", "mobile_app", "Khiếu nại: Tài xế to tiếng văng tục khi trả khách", "Tài xế dừng cách nhà 200m bắt khách tự lội bộ, phàn nàn thì nói lời khiếm nhã"),
    ("v2_comp_020", "v2_trip_004_08", "v2_inc_025", "v2_rule_safety_speed", "reckless_driving", -0.72, "2025-07-14T13:45:00Z", "mobile_app", "Khiếu nại: Lái xe bám đuôi và bóp còi liên tục", "Tài xế lái xe rất sốt ruột, bấm còi inh ỏi và dí sát đuôi xe phía trước"),
    ("v2_comp_021", "v2_trip_004_12", "v2_inc_029", "v2_rule_safety_speed", "reckless_driving", -0.98, "2025-07-18T17:00:00Z", "customer_hotline", "Khiếu nại: Cảm thấy nguy hiểm đến tính mạng", "Hành khách phải nhấn nút báo động SOS vì tài xế không chịu giảm tốc độ khi được yêu cầu"),
    ("v2_comp_022", "v2_trip_007_05", None, "v2_rule_fraud_promo", "cancellation", -0.80, "2025-07-11T15:00:00Z", "mobile_app", "Khiếu nại: Tài xế gọi kêu không đi mà đòi tiền voucher", "Tài xế gọi điện thương lượng xin chia đôi tiền voucher khuyến mãi"),
    ("v2_comp_023", "v2_trip_007_11", "v2_inc_003", "v2_rule_fraud_promo", "attitude", -0.92, "2025-07-21T14:30:00Z", "mobile_app", "Khiếu nại: Tài khoản bị trừ tiền cuốc xe lạ", "Khách nhận thông báo trừ tiền chuyến đi dù đang ngồi ở văn phòng làm việc"),
    ("v2_comp_024", "v2_trip_009_06", "v2_inc_030", "v2_rule_vehicle_hygiene", "dirty_vehicle", -0.76, "2025-07-14T16:00:00Z", "mobile_app", "Khiếu nại: Xe nồng nặc mùi thuốc lá khó thở", "Xe có mùi khói thuốc lá rất nặng làm con nhỏ của tôi bị ho sặc sụa suốt chuyến đi"),
    ("v2_comp_025", "v2_trip_009_09", "v2_inc_023", "v2_rule_vehicle_hygiene", "luggage_refusal", -0.83, "2025-07-19T17:00:00Z", "mobile_app", "Khiếu nại: Tài xế từ chối mở cốp chở hành lý", "Tài xế bảo cốp để đầy đồ cá nhân của mình, bắt khách ôm vali lên lòng ghế sau"),
    ("v2_comp_026", "v2_trip_009_13", "v2_inc_032", "v2_rule_safety_speed", "attitude", -0.95, "2025-07-27T23:00:00Z", "customer_hotline", "Khiếu nại: Tài xế có mùi rượu bia nồng nặc", "Khi lên xe ngửi thấy nồng nặc mùi bia rượu từ người tài xế, nói năng líu lưỡi"),
    ("v2_comp_027", "v2_trip_010_11", "v2_inc_027", "v2_rule_p23_attitude", "route_deviation", -0.74, "2025-07-29T16:00:00Z", "mobile_app", "Khiếu nại: Bị bỏ lại giữa đường trời mưa", "Tài xế không chịu chạy vào tận cửa sảnh chung cư mà thả xuống giữa trời mưa gió"),
    ("v2_comp_028", "v2_trip_002_09", "v2_inc_001", "v2_rule_p154", "cancellation", -0.70, "2025-07-20T14:45:00Z", "mobile_app", "Khiếu nại: Tài xế nhận cuốc xong đứng im 10 phút rồi hủy", "Đang cần đi gấp mà tài xế đứng im câu giờ bắt khách tự hủy rồi tự bấm hủy"),
    ("v2_comp_029", "v2_trip_002_12", "v2_inc_007", "v2_rule_p154", "cancellation", -0.79, "2025-07-28T11:20:00Z", "customer_hotline", "Khiếu nại: Tổng đài báo có xe nhưng tài xế từ chối", "Tài xế gọi lại bảo mưa ngập không đi đâu, tự tìm xe khác"),
    ("v2_comp_030", "v2_trip_004_02", None, "v2_rule_p23_attitude", "attitude", -0.55, "2025-07-04T12:45:00Z", "mobile_app", "Khiếu nại: Không giúp khách xách vali nặng", "Tài xế ngồi im trên xe bấm điện thoại không thèm xuống mở cốp giúp khách nữ"),
    ("v2_comp_031", "v2_trip_003_09", "v2_inc_017", "v2_rule_safety_speed", "reckless_driving", -0.40, "2025-07-18T15:45:00Z", "hub_frontdesk", "Phản ánh: Xe va quẹt cột làm khách hoảng hốt", "Khi lùi xe tài xế sơ ý đụng trúng cột hầm làm xe bị giật một phát"),
    ("v2_comp_032", "v2_trip_007_06", None, "v2_rule_fraud_promo", "cancellation", -0.85, "2025-07-11T16:30:00Z", "mobile_app", "Khiếu nại: Chuyến đi biến mất bí ẩn", "Đặt xe thành công xong 2 phút sau tài xế hủy với lý do khách không có mặt"),
    ("v2_comp_033", "v2_trip_007_13", "v2_inc_010", "v2_rule_fraud_promo", "attitude", -0.88, "2025-07-21T17:15:00Z", "customer_hotline", "Khiếu nại: Số điện thoại lạ tự đặt xe tới nhà tôi", "Có xe tới bấm còi đòi đón trong khi tôi không hề đặt chuyến"),
    ("v2_comp_034", "v2_trip_010_01", None, "v2_rule_route_deviation", "route_deviation", -0.50, "2025-07-06T09:45:00Z", "mobile_app", "Khiếu nại: Tài xế đi đường lạ không báo trước", "Tài xế rẽ vào đường tránh làm chuyến đi lâu hơn 10 phút"),
    ("v2_comp_035", "v2_trip_002_13", "v2_inc_007", "v2_rule_p154", "cancellation", -0.85, "2025-07-28T14:30:00Z", "customer_hotline", "Khiếu nại: Lỡ hẹn chuyến bay vì tài xế hủy cuốc", "Tài xế hủy chuyến phút chót lúc trời mưa to làm tôi phải bắt taxi dù giá cắt cổ"),
    ("v2_comp_036", "v2_trip_002_14", "v2_inc_007", "v2_rule_p154", "cancellation", -0.82, "2025-07-28T16:00:00Z", "mobile_app", "Khiếu nại: Bị hủy chuyến lần thứ 4 trong ngày bão", "Hệ thống xếp xe nhưng tài xế bấm hủy ngay lập tức"),
    ("v2_comp_037", "v2_trip_010_08", None, "v2_rule_p23_attitude", "attitude", -0.60, "2025-07-23T18:15:00Z", "mobile_app", "Khiếu nại: Thái độ bực bội cau có suốt chuyến", "Tài xế liên tục cằn nhằn về đường kẹt xe và bấm còi khó chịu"),
    ("v2_comp_038", "v2_trip_009_03", None, "v2_rule_tariff_overcharge", "overcharging", -0.65, "2025-07-08T16:30:00Z", "mobile_app", "Khiếu nại: Không có tiền lẻ trả lại cho khách", "Tài xế không chuẩn bị tiền lẻ, bảo khách tự bỏ qua 15,000 VND"),
]

# =========================================================================
# 10. MAINTENANCE EVENTS (26 Events)
# =========================================================================
MAINT_EVENTS_DATA = [
    # (event_id, vehicle_id, name, type, date, cost, status, desc, odo)
    ("v2_maint_001", "v2_veh_001", "Bảo dưỡng 20,000km & Pin (VinFast VF 8)", "battery_health_and_20k_km_check", "2025-07-10", 1200000, "completed", "Bảo dưỡng định kỳ 20,000km và cân bằng điện áp pack pin VinFast VF 8", 20100),
    ("v2_maint_002", "v2_veh_002", "Bảo dưỡng định kỳ 35k km (VinFast VF e34)", "periodic_35k_check", "2025-07-08", 1450000, "completed", "Kiểm tra động cơ điện và bảo dưỡng hệ thống phanh tái sinh VF e34", 35100),
    ("v2_maint_003", "v2_veh_003", "Thay má phanh trước (VinFast VF 5 Plus)", "brake_pad_replacement", "2025-07-14", 850000, "completed", "Thay má phanh trước và kiểm tra hệ thống tái sinh năng lượng VF 5 Plus", 14500),
    ("v2_maint_004", "v2_veh_004", "Kiểm tra điều hòa & Pin (VinFast VF e34)", "battery_and_ac_inspection", "2025-07-16", 1100000, "completed", "Kiểm tra hệ thống điều hòa nhiệt độ và sức khỏe cell pin xe VF e34", 41100),
    ("v2_maint_005", "v2_veh_005", "Bảo dưỡng 10k km xe máy điện (VinFast Feliz S)", "periodic_10k_km_check", "2025-07-25", 320000, "completed", "Bảo dưỡng định kỳ 10,000km và kiểm tra động cơ Inhub xe Feliz S", 8800),
    ("v2_maint_006", "v2_veh_008", "Đổi pin & Kiểm tra sạc xe máy (VinFast Klara S)", "battery_swap_and_inspection", "2025-07-15", 150000, "completed", "Thay cụm pin lithium và kiểm tra an toàn giắc cắm sạc xe Klara S", 12400),
    ("v2_maint_007", "v2_veh_009", "Thay dầu máy & Lọc gió xe xăng (Toyota Vios)", "engine_oil_and_filter_service", "2025-07-12", 680000, "completed", "Thay dầu nhớt động cơ đốt trong và lọc gió định kỳ 55k km xe Toyota Vios", 57800),
    ("v2_maint_008", "v2_veh_006", "Cân chỉnh độ chụm bánh & cân bằng động (VF 7)", "wheel_alignment_check", "2025-07-11", 750000, "completed", "Cân chỉnh độ chụm bánh lái và kiểm tra hệ thống treo điện tử VF 7", 11050),
    ("v2_maint_009", "v2_veh_007", "Kiểm tra trụ sạc DC nhanh Autel (VF 3)", "charging_system_inspection", "2025-07-13", 200000, "completed", "Kiểm tra cổng sạc CCS2 và tốc độ nhận dòng sạc nhanh DC xe VF 3", 6350),
    ("v2_maint_010", "v2_veh_010", "Cập nhật firmware BMS quản lý pin v2.4 (VF 6)", "bms_firmware_update", "2025-07-17", 300000, "completed", "Nâng cấp phần mềm quản lý pin BMS phiên bản 2.4 tối ưu tầm vận hành VF 6", 18800),
    ("v2_maint_011", "v2_veh_002", "Vá lốp xe dính đinh & cân mâm (VF e34)", "tire_puncture_repair", "2025-07-21", 250000, "completed", "Xử lý lốp sau bên phụ bị cán đinh và cân bằng động lốp xe VF e34", 35280),
    ("v2_maint_012", "v2_veh_009", "Khử mùi Ozone & giặt nội thất nỉ (Toyota Vios)", "interior_deep_cleaning", "2025-07-20", 550000, "completed", "Tổng vệ sinh nội thất và xông khử mùi thuốc lá bắt buộc sau phản ánh", 57950),
    ("v2_maint_013", "v2_veh_001", "Thay chổi gạt mưa & nước làm mát pin (VF 8)", "wiper_and_coolant_service", "2025-07-22", 450000, "completed", "Thay gạt mưa silicon trước và châm thêm nước làm mát pack pin VinFast VF 8", 20380),
    ("v2_maint_014", "v2_veh_005", "Bảo dưỡng ổ trục & vòng bi bánh trước (Feliz S)", "bearing_and_hub_service", "2025-07-28", 180000, "completed", "Thay vòng bi bạc đạn bánh trước bị rơ xe máy điện Feliz S", 8950),
    ("v2_maint_015", "v2_veh_003", "Kiểm tra hệ thống treo định kỳ 15k km (VF 5)", "suspension_check", "2025-07-26", 600000, "completed", "Kiểm tra rô-tuyn cân bằng và giảm xóc trước xe VinFast VF 5 Plus", 14750),
    ("v2_maint_016", "v2_veh_008", "Hoán đổi pin nhanh trạm sạc Tân Sơn Nhất (Klara S)", "battery_swap_quick", "2025-07-18", 50000, "completed", "Đổi 2 pack pin LFP đầy 100% tại trạm sạc xe máy điện Tân Bình", 12480),
    ("v2_maint_017", "v2_veh_002", "Cứu hộ kích bình & sạc khẩn cấp trên vành đai (VF e34)", "roadside_assistance_charging", "2025-07-15", 800000, "completed", "Xe cứu hộ lưu động sạc khẩn cấp 10% pin sau khi cạn kiệt", 35210),
    ("v2_maint_018", "v2_veh_003", "Sơn dặm & đánh bóng cản sau bị trầy (VF 5)", "bumper_scratch_repair", "2025-07-19", 950000, "completed", "Sơn phục hồi góc cản sau bên lái sau sự cố quẹt cột hầm", 14620),
    ("v2_maint_019", "v2_veh_002", "Bảo dưỡng kiểm tra cách điện sau lội nước (VF e34)", "high_voltage_insulation_check", "2025-07-29", 1200000, "completed", "Kiểm tra an toàn hệ thống điện cao áp và gioăng chống nước sau mưa ngập", 35320),
    ("v2_maint_020", "v2_veh_004", "Thay lốp trước bên lái mòn lệch (VF e34)", "tire_replacement", "2025-07-19", 1800000, "completed", "Thay lốp Michelin Primacy mới do mòn lệch và phanh gấp nhiều", 41250),
    ("v2_maint_021", "v2_veh_009", "Thay má phanh tang trống sau (Toyota Vios)", "rear_brake_service", "2025-07-22", 650000, "completed", "Vệ sinh và thay guốc phanh sau xe Toyota Vios", 57980),
    ("v2_maint_022", "v2_veh_001", "Bảo dưỡng hệ thống trợ lái điện ADAS (VF 8)", "adas_calibration", "2025-07-28", 1500000, "completed", "Căn chỉnh radar và camera ADAS hỗ trợ giữ làn đường VF 8", 20420),
    ("v2_maint_023", "v2_veh_006", "Vệ sinh chi tiết nội thất da cao cấp Nappa (VF 7)", "premium_interior_detailing", "2025-07-22", 850000, "completed", "Dưỡng da ghế Nappa và bảo dưỡng cửa sổ trời toàn cảnh VF 7", 11180),
    ("v2_maint_024", "v2_veh_010", "Kiểm tra hệ thống đèn chiếu sáng LED (VF 6)", "lighting_system_check", "2025-07-14", 250000, "completed", "Kiểm tra và cân chỉnh độ cao luồng sáng đèn pha LED VF 6", 18920),
    ("v2_maint_025", "v2_veh_007", "Kiểm tra chốt an toàn dây curoa trợ lực lái (VF 3)", "steering_rack_check", "2025-07-22", 300000, "completed", "Siết ốc thước lái và tra mỡ bôi trơn khớp nối xe VF 3", 6380),
    ("v2_maint_026", "v2_veh_005", "Thay dây curoa truyền động xe máy điện (Feliz S)", "drive_belt_replacement", "2025-07-30", 350000, "completed", "Thay dây curoa truyền động chính hãng sau 8,900km vận hành", 8980),
]

# =========================================================================
# 11. REWARD & PENALTY DECISIONS (28 Decisions)
# =========================================================================
DECISIONS_DATA = [
    # (decision_id, driver_id, action_type, effective_date, reason, status, rules, inc_id, name)
    ("v2_dec_001", "v2_drv_001", "bonus", "2025-07-31", "Khen thưởng tài xế tiêu biểu Tháng 7/2025 đạt xếp hạng Kim Cương, 100% tỷ lệ hoàn thành", "awarded", ["v2_rule_p151"], None, "Khen thưởng: Tài xế Kim Cương xuất sắc (Trần Quốc Toản)"),
    ("v2_dec_002", "v2_drv_002", "fine", "2025-07-22", "Phạt tiền 500,000 VND và cảnh cáo văn bản do vi phạm tỷ lệ hủy chuyến theo Quy chế P154", "enforced", ["v2_rule_p154"], "v2_inc_001", "Xử phạt vi phạm P154: Phạt tiền 500k (Lê Văn Hùng)"),
    ("v2_dec_003", "v2_drv_004", "temporary_lock", "2025-07-19", "Tạm khóa tài khoản 3 ngày và trừ điểm an toàn do vi phạm chạy quá tốc độ và phản ánh lái xe ẩu", "enforced", ["v2_rule_safety_speed", "v2_rule_p23_attitude"], "v2_inc_002", "Tạm đình chỉ tài khoản 3 ngày: Chạy quá tốc độ (Phạm Thị Mai)"),
    ("v2_dec_004", "v2_drv_006", "bonus", "2025-07-31", "Khen thưởng 1,500,000 VND và vinh danh dịch vụ VIP 5 sao không có phàn nàn trong tháng 7", "awarded", ["v2_rule_p151"], None, "Khen thưởng: Dịch vụ VIP 5 sao (Hoàng Văn Thắng)"),
    ("v2_dec_005", "v2_drv_007", "temporary_lock", "2025-07-22", "Tạm đình chỉ tài khoản 14 ngày và thu hồi toàn bộ tiền thưởng do vi phạm gian lận voucher khuyến mãi cuốc ảo", "enforced", ["v2_rule_fraud_promo"], "v2_inc_003", "Tạm khóa tài khoản 14 ngày & Thu hồi thưởng (Đỗ Minh Khang)"),
    ("v2_dec_006", "v2_drv_009", "warning", "2025-07-20", "Cảnh cáo bằng văn bản, bắt buộc hoàn trả 50,000 VND cho khách và tạm ngưng 1 ngày để vệ sinh tổng thể xe", "enforced", ["v2_rule_tariff_overcharge", "v2_rule_vehicle_hygiene"], "v2_inc_004", "Cảnh cáo văn bản: Thu sai cước & Vệ sinh xe (Bùi Đức Tiến)"),
    ("v2_dec_007", "v2_drv_010", "fine", "2025-07-24", "Phạt tiền 200,000 VND và trừ 6 điểm tín nhiệm nghiệp vụ do cố tình chạy vòng đường ép tăng cước", "enforced", ["v2_rule_route_deviation"], "v2_inc_005", "Xử phạt vi phạm lộ trình GPS: Phạt tiền 200k (Trịnh Thanh Tùng)"),
    ("v2_dec_008", "v2_drv_003", "bonus", "2025-07-31", "Khen thưởng 1,000,000 VND hoàn thành xuất sắc 100% tỷ lệ nhận cuốc khu vực Nam Sài Gòn", "awarded", ["v2_rule_p151"], None, "Khen thưởng: Tỷ lệ nhận cuốc 100% (Nguyễn Hoàng Nam)"),
    ("v2_dec_009", "v2_drv_005", "bonus", "2025-07-31", "Khen thưởng 800,000 VND đối tác 2 bánh tiêu biểu giao hàng an toàn đạt 100% cuốc hoàn thành", "awarded", ["v2_rule_p151"], None, "Khen thưởng: Đối tác xe máy tiêu biểu (Đặng Văn Phúc)"),
    ("v2_dec_010", "v2_drv_002", "warning", "2025-07-21", "Cảnh cáo bằng văn bản về hành vi từ chối bật điều hòa giữa trưa nắng gay gắt phục vụ hành khách", "enforced", ["v2_rule_p23_attitude"], "v2_inc_006", "Cảnh cáo văn bản: Không bật điều hòa (Lê Văn Hùng)"),
    ("v2_dec_011", "v2_drv_002", "fine", "2025-07-29", "Phạt tiền 500,000 VND do tái phạm hủy chuyến hàng loạt khi trời mưa bão vi phạm nghiêm trọng P154", "enforced", ["v2_rule_p154"], "v2_inc_007", "Xử phạt tái phạm P154: Phạt tiền 500k (Lê Văn Hùng)"),
    ("v2_dec_012", "v2_drv_010", "fine", "2025-07-13", "Phạt tiền 300,000 VND và trừ 7 điểm an toàn do hành vi vượt đèn tín hiệu giao thông", "enforced", ["v2_rule_safety_speed", "v2_rule_p23_attitude"], "v2_inc_008", "Phạt tiền: Vượt đèn tín hiệu giao thông (Trịnh Thanh Tùng)"),
    ("v2_dec_013", "v2_drv_004", "temporary_lock", "2025-07-19", "Tạm khóa tài khoản thêm 7 ngày do đi vào đường cấm làm trễ chuyến bay của hành khách", "enforced", ["v2_rule_route_deviation", "v2_rule_p23_attitude"], "v2_inc_012", "Tạm khóa 7 ngày: Đi vào đường cấm (Phạm Thị Mai)"),
    ("v2_dec_014", "v2_drv_007", "temporary_lock", "2025-07-23", "Đình chỉ tài khoản 30 ngày và chuyển hồ sơ kiểm toán do tái diễn tạo cuốc ảo trục lợi hệ thống", "enforced", ["v2_rule_fraud_promo"], "v2_inc_010", "Đình chỉ tài khoản 30 ngày: Tái diễn cuốc ảo (Đỗ Minh Khang)"),
    ("v2_dec_015", "v2_drv_009", "fine", "2025-07-28", "Phạt tiền 500,000 VND, hoàn trả 30,000 VND cho khách và cảnh cáo kỷ luật do ép tip & ghép khách lạ", "enforced", ["v2_rule_tariff_overcharge", "v2_rule_p23_attitude"], "v2_inc_011", "Phạt tiền 500k: Giữ tiền thừa & ghép khách lạ (Bùi Đức Tiến)"),
    ("v2_dec_016", "v2_drv_001", "bonus", "2025-07-20", "Khen thưởng nóng 500,000 VND và thư cảm ơn từ hành khách nước ngoài bỏ quên ví tiền trên xe", "awarded", ["v2_rule_p23_attitude"], None, "Khen thưởng nóng: Trả lại ví tiền cho khách VIP (Trần Quốc Toản)"),
    ("v2_dec_017", "v2_drv_002", "temporary_lock", "2025-07-30", "Tạm đình chỉ tài khoản 7 ngày do vi phạm tổng hợp: tỷ lệ hủy chuyến vượt chuẩn và cạn pin trên cao tốc", "enforced", ["v2_rule_p154", "v2_rule_p151"], "v2_inc_016", "Tạm khóa 7 ngày: Vi phạm tổng hợp P154 & Cạn pin (Lê Văn Hùng)"),
    ("v2_dec_018", "v2_drv_004", "retraining", "2025-07-20", "Bắt buộc tham gia khóa đào tạo lại văn hóa ứng xử và kỹ năng lái xe an toàn 16 giờ", "enforced", ["v2_rule_safety_speed", "v2_rule_p23_attitude"], "v2_inc_029", "Yêu cầu đào tạo lại lái xe an toàn (Phạm Thị Mai)"),
    ("v2_dec_019", "v2_drv_006", "bonus", "2025-07-23", "Thưởng đột xuất 1,000,000 VND phục vụ đoàn ngoại giao Bộ Ngoại Giao với tác phong chuyên nghiệp", "awarded", ["v2_rule_p151"], None, "Khen thưởng: Phục vụ đoàn Ngoại giao chuẩn VIP (Hoàng Văn Thắng)"),
    ("v2_dec_020", "v2_drv_009", "temporary_lock", "2025-07-28", "Đình chỉ quyền nhận cuốc 14 ngày do vi phạm phóng nhanh trên cầu Rồng và chở khách ghép lậu", "enforced", ["v2_rule_safety_speed", "v2_rule_p23_attitude"], "v2_inc_014", "Đình chỉ nhận cuốc 14 ngày: Phóng nhanh cầu Rồng (Bùi Đức Tiến)"),
    ("v2_dec_021", "v2_drv_010", "warning", "2025-07-30", "Cảnh cáo văn bản và bắt buộc hoàn trả 20,000 VND phí sân bay thu sai của hành khách", "enforced", ["v2_rule_tariff_overcharge"], "v2_inc_021", "Cảnh cáo văn bản: Thu sai phí sân bay (Trịnh Thanh Tùng)"),
    ("v2_dec_022", "v2_drv_008", "bonus", "2025-07-31", "Khen thưởng đối tác xe máy điện xuất sắc không vi phạm quy chế trong chu kỳ tháng 7", "awarded", ["v2_rule_p151"], None, "Khen thưởng: Đối tác xe máy chuẩn mực (Vũ Bích Ngọc)"),
    ("v2_dec_023", "v2_drv_002", "warning", "2025-07-22", "Nhắc nhở văn bản về thái độ phục vụ khách hàng sau tranh cãi về điểm trả khách tại Hoàn Kiếm", "enforced", ["v2_rule_p23_attitude"], "v2_inc_018", "Nhắc nhở văn bản: Tranh cãi điểm trả khách (Lê Văn Hùng)"),
    ("v2_dec_024", "v2_drv_009", "termination", "2025-07-29", "Chấm dứt hợp đồng hợp tác và thu hồi thiết bị do vi phạm nồng độ cồn và tái phạm vi phạm văn hóa", "enforced", ["v2_rule_safety_speed", "v2_rule_p23_attitude"], "v2_inc_032", "Chấm dứt hợp đồng hợp tác: Vi phạm nồng độ cồn (Bùi Đức Tiến)"),
    ("v2_dec_025", "v2_drv_007", "termination", "2025-07-25", "Đề xuất chấm dứt hợp đồng vĩnh viễn và chuyển cơ quan chức năng điều tra hành vi gian lận voucher", "enforced", ["v2_rule_fraud_promo"], "v2_inc_022", "Chấm dứt hợp đồng vĩnh viễn: Gian lận trục lợi (Đỗ Minh Khang)"),
    ("v2_dec_026", "v2_drv_005", "bonus", "2025-07-15", "Khen thưởng tuần: Hoàn thành 100 chuyến xe máy điện không trễ giờ", "awarded", ["v2_rule_p151"], None, "Khen thưởng tuần: 100 chuyến xe máy an toàn (Đặng Văn Phúc)"),
    ("v2_dec_027", "v2_drv_003", "bonus", "2025-07-20", "Khen thưởng tự giác báo cáo sự cố va quẹt và phối hợp bồi hoàn nhanh chóng cho đối tác", "awarded", ["v2_rule_safety_speed"], "v2_inc_017", "Khen thưởng: Tinh thần tự giác báo cáo sự cố (Nguyễn Hoàng Nam)"),
    ("v2_dec_028", "v2_drv_010", "retraining", "2025-07-31", "Yêu cầu kiểm tra lại định tuyến bản đồ và quy chuẩn thu cước đối với tài xế", "enforced", ["v2_rule_route_deviation", "v2_rule_tariff_overcharge"], "v2_inc_027", "Đào tạo lại: Nghiệp vụ định tuyến & Cước phí (Trịnh Thanh Tùng)"),
]


# =========================================================================
# 12. DATASET GRAPH BUILDER FUNCTION
# =========================================================================
def build_v2_graph_dataset() -> dict[str, list[dict[str, Any]]]:
    """Build complete node and edge lists for Neo4j V2 ontology."""
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

    # 1. Hubs
    for h in HUBS:
        h_props = {k: v for k, v in h.items() if k not in ("zone_id", "managed_vehicles")}
        add_node("Hub", h["id"], h_props)
        add_edge("LOCATED_IN", "Hub", h["id"], "Zone", h["zone_id"], {"timestamp": "2025-07-01T00:00:00Z"})
        for v_id in h["managed_vehicles"]:
            add_edge("MANAGES_VEHICLE", "Hub", h["id"], "Vehicle", v_id, {"timestamp": "2025-07-01T00:00:00Z"})

    # 2. Zones
    for z in ZONES:
        add_node("Zone", z["id"], z)

    # 3. Vehicles
    for v in VEHICLES:
        add_node("Vehicle", v["id"], v)

    # 4. Policy Rules
    for r in POLICY_RULES:
        add_node("PolicyRule", r["id"], r)

    # 5. Drivers
    for d in DRIVERS:
        d_props = {k: v for k, v in d.items() if k not in ("hub_id", "vehicle_id", "frequent_zones")}
        add_node("Driver", d["id"], d_props)
        add_edge(
            "OPERATES", "Driver", d["id"], "Vehicle", d["vehicle_id"],
            {
                "assigned_date": d["onboarding_date"],
                "is_primary": True,
                "valid_from": f"{d['onboarding_date']}T00:00:00Z",
                "valid_to": None,
                "timestamp": f"{d['onboarding_date']}T00:00:00Z",
            },
        )
        add_edge(
            "BELONGS_TO", "Driver", d["id"], "Hub", d["hub_id"],
            {
                "joined_date": d["onboarding_date"],
                "valid_from": f"{d['onboarding_date']}T00:00:00Z",
                "valid_to": None,
                "timestamp": f"{d['onboarding_date']}T00:00:00Z",
            },
        )
        for zone_id, ratio, time_slot in d.get("frequent_zones", []):
            add_edge(
                "FREQUENTLY_OPERATES_IN", "Driver", d["id"], "Zone", zone_id,
                {
                    "operating_ratio": ratio,
                    "time_slot": time_slot,
                    "valid_from": "2025-07-01T00:00:00Z",
                    "valid_to": "2025-07-31T23:59:59Z",
                    "timestamp": "2025-07-01T00:00:00Z",
                },
            )

    # 6. Shifts
    for sid, did, dt, st, et, onl, ar, cr, sname in SHIFTS_DATA:
        add_node("Shift", sid, {
            "shift_id": sid,
            "name": sname,
            "date": dt,
            "start_time": st,
            "end_time": et,
            "total_online_hours": onl,
            "acceptance_rate": ar,
            "completion_rate": cr,
        })
        add_edge("WORKS_SHIFT", "Driver", did, "Shift", sid, {"date": dt, "timestamp": st})

    # 7. Trips
    for tid, did, sid, vid, tname, fare, dist, dur, status, pu, do_, ts in TRIPS_DATA:
        add_node("Trip", tid, {
            "trip_id": tid,
            "name": tname,
            "fare": fare,
            "distance_km": dist,
            "duration_min": dur,
            "status": status,
        })
        add_edge("SERVED_TRIP", "Driver", did, "Trip", tid, {"role": "primary_driver", "timestamp": ts})
        add_edge("CONTAINS_TRIP", "Shift", sid, "Trip", tid, {"timestamp": ts})
        add_edge("USES_VEHICLE", "Trip", tid, "Vehicle", vid, {"timestamp": ts})
        add_edge("PICKUP_IN", "Trip", tid, "Zone", pu, {"timestamp": ts})
        add_edge("DROPOFF_IN", "Trip", tid, "Zone", do_, {"timestamp": ts})

    # 8. Maintenance Events
    for eid, vid, mname, mtype, dt, cost, status, desc, odo in MAINT_EVENTS_DATA:
        add_node("MaintenanceEvent", eid, {
            "event_id": eid,
            "name": mname,
            "type": mtype,
            "date": dt,
            "cost": cost,
            "status": status,
            "description": desc,
        })
        add_edge("UNDERWENT", "Vehicle", vid, "MaintenanceEvent", eid, {"odometer_km": odo, "timestamp": f"{dt}T08:00:00Z"})

    # 9. Incidents
    for inc in INCIDENTS_DATA:
        inc_props = {k: v for k, v in inc.items() if k not in ("driver_id", "shift_id", "fault_rate", "penalty_points", "violates_rules", "detected_by")}
        add_node("Incident", inc["id"], inc_props)
        add_edge(
            "INVOLVED_IN", "Driver", inc["driver_id"], "Incident", inc["id"],
            {"fault_rate": inc["fault_rate"], "penalty_points": inc["penalty_points"], "timestamp": inc["timestamp"]},
        )
        add_edge("OCCURRED_IN", "Incident", inc["id"], "Shift", inc["shift_id"], {"timestamp": inc["timestamp"]})
        for r_id in inc["violates_rules"]:
            add_edge("VIOLATES", "Incident", inc["id"], "PolicyRule", r_id, {"detected_by": inc["detected_by"], "timestamp": inc["timestamp"]})

    # 10. Customer Complaints
    for cid, tid, esc_inc, viol_rule, cat, sent, dt, chan, cname, content in COMPLAINTS_DATA:
        add_node("CustomerComplaint", cid, {
            "complaint_id": cid,
            "name": cname,
            "category": cat,
            "sentiment_score": sent,
            "created_at": dt,
            "content": content,
        })
        add_edge("RECEIVES_COMPLAINT", "Trip", tid, "CustomerComplaint", cid, {"channel": chan, "timestamp": dt})
        if esc_inc:
            add_edge("ESCALATED_TO", "CustomerComplaint", cid, "Incident", esc_inc, {"timestamp": dt})
        if viol_rule:
            add_edge("VIOLATES", "CustomerComplaint", cid, "PolicyRule", viol_rule, {"timestamp": dt})

    # 11. Reward & Penalty Decisions
    for dec_id, did, act_type, eff_date, reason, status, rules, inc_id, dname in DECISIONS_DATA:
        add_node("RewardPenalty", dec_id, {
            "decision_id": dec_id,
            "name": dname,
            "action_type": act_type,
            "effective_date": eff_date,
            "reason": reason,
            "status": status,
        })
        add_edge(
            "RECEIVES", "Driver", did, "RewardPenalty", dec_id,
            {"issued_at": f"{eff_date}T08:00:00Z", "status": status, "timestamp": f"{eff_date}T08:00:00Z"},
        )
        for r_id in rules:
            add_edge("BASED_ON", "RewardPenalty", dec_id, "PolicyRule", r_id, {"reason": reason, "timestamp": f"{eff_date}T08:00:00Z"})
        if inc_id:
            add_edge("BASED_ON", "RewardPenalty", dec_id, "Incident", inc_id, {"reason": reason, "timestamp": f"{eff_date}T08:00:00Z"})

    return {"nodes": nodes, "edges": edges}
