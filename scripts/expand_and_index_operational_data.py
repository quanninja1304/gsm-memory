"""Script to expand operational data (trips, complaints, incidents) across drivers,
persist to SQLite and Neo4j, and index into Qdrant for semantic graph retrieval.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Ensure src is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

from gsm_memory.db.models import ComplaintRecord, IncidentRecord, TripRecord
from gsm_memory.db.repository import LocalDatabaseRepository
from gsm_memory.retrieval.nvidia_embed import NvidiaNemotronEmbedder


SNAPSHOT_ID = "8b1426b6-2fad-5aba-b886-e16de44c18e7"

CORE_DRIVERS = {
    "DRV-001": {"id": "99e70ebe-18cd-57a3-a036-cf0ff1989861", "name": "An", "full_name": "Nguyễn Văn An"},
    "DRV-002": {"id": "c499f934-bfe1-5509-a578-afb09cee357c", "name": "Bình", "full_name": "Trần Văn Bình"},
    "DRV-003": {"id": "3b0b7be7-b553-5d99-9528-4a07ca4f1567", "name": "Chi", "full_name": "Lê Thị Chi"},
    "DRV-004": {"id": "cc916c6b-b168-5d8f-9023-075391ee4136", "name": "Dũng", "full_name": "Phạm Quốc Dũng"},
    "DRV-005": {"id": "58e68d69-f07f-580e-a4b6-91ef3801c5d7", "name": "Minh", "full_name": "Hoàng Văn Minh"},
    "DRV-006": {"id": "b8afff09-1200-5bcd-a594-6a647680f865", "name": "Minh", "full_name": "Vũ Nhật Minh"},
    "DRV-007": {"id": "bff953c4-63cd-58b5-82f3-d3ecac5ac17a", "name": "Giang", "full_name": "Đặng Hương Giang"},
    "DRV-008": {"id": "122a3140-7c98-5136-a732-8a9566cb727d", "name": "Hà", "full_name": "Bùi Thu Hà"},
}

def deterministic_uuid(prefix: str, key: str) -> str:
    """Generate reproducible UUIDv5 from prefix and key."""
    namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
    return str(uuid.uuid5(namespace, f"{prefix}:{key}"))


# 1. Authoritative new operational records for the 8 core drivers
NEW_CORE_DATA = [
    # --- Nguyễn Văn An (DRV-001) ---
    {
        "driver_code": "DRV-001",
        "trip": {
            "pickup": "128 Đội Cấn, Ba Đình, Hà Nội",
            "dropoff": "Tòa nhà FPT, Duy Tân, Cầu Giấy, Hà Nội",
            "start_time": "2026-08-20T04:30:00.000000Z",
            "distance_km": 7.5,
            "fare": 115000,
            "outcome": "completed",
            "rating": 2,
            "feedback": "Tài xế khó chịu khi khách nhờ bật điều hòa lạnh hơn giữa trưa hè.",
        },
        "complaint": {
            "category": "comfort_air_conditioner",
            "event_time": "2026-08-20T05:15:00.000000Z",
            "name": "Phản ánh: Tài xế từ chối hạ nhiệt độ điều hòa và tỏ thái độ",
            "description": "Trong chuyến xe giữa trưa hè 38 độ C, hành khách đề nghị chỉnh điều hòa xuống 22 độ nhưng tài xế từ chối với lý do tiết kiệm pin cho xe điện VinFast, sau đó tỏ thái độ cáu kỉnh và gắt gỏng suốt chuyến đi.",
        },
    },
    {
        "driver_code": "DRV-001",
        "trip": {
            "pickup": "Bệnh viện Bạch Mai, Giải Phóng, Hà Nội",
            "dropoff": "Khu đô thị Times City, Hai Bà Trưng, Hà Nội",
            "start_time": "2026-08-22T08:10:00.000000Z",
            "distance_km": 4.8,
            "fare": 75000,
            "outcome": "completed",
            "rating": 2,
            "feedback": "Tài xế đeo tai nghe nói chuyện riêng liên tục không tập trung lái xe.",
        },
        "complaint": {
            "category": "service_attitude_phone",
            "event_time": "2026-08-22T08:45:00.000000Z",
            "name": "Phản ánh: Sử dụng tai nghe gọi điện cá nhân liên tục khi chở khách",
            "description": "Khách hàng phàn nàn tài xế đeo tai nghe Bluetooth nói chuyện cá nhân to tiếng liên tục trong suốt hành trình, không tập trung quan sát tín hiệu đèn giao thông khiến xe suýt phanh gấp tại ngã tư.",
        },
    },
    {
        "driver_code": "DRV-001",
        "trip": {
            "pickup": "Ngõ 285 Đội Cấn, Ba Đình, Hà Nội",
            "dropoff": "Sân bay Quốc tế Nội Bài, Sóc Sơn, Hà Nội",
            "start_time": "2026-08-25T01:30:00.000000Z",
            "distance_km": 28.0,
            "fare": 320000,
            "outcome": "completed",
            "rating": 3,
            "feedback": "Xe lùi quẹt nhẹ vào mốc ngõ làm trễ giờ 15 phút.",
        },
        "incident": {
            "incident_type": "minor_collision",
            "event_time": "2026-08-25T01:45:00.000000Z",
            "name": "Sự cố: Va quẹt nhẹ trầy xước cản sau khi lùi vào ngõ hẹp",
            "description": "Khi lùi xe đón khách trong ngõ 285 Đội Cấn, xe va chạm nhẹ với trụ bê tông mép đường gây trầy xước cản sau bên phụ. Hai bên kiểm tra không có thiệt hại người hay tài sản thứ ba, tài xế tiếp tục chuyến sau khi báo cáo điều hành.",
        },
    },

    # --- Trần Văn Bình (DRV-002) ---
    {
        "driver_code": "DRV-002",
        "trip": {
            "pickup": "Khách sạn Daewoo, Liễu Giai, Ba Đình, Hà Nội",
            "dropoff": "Sân bay Nội Bài, Hà Nội",
            "start_time": "2026-08-21T09:00:00.000000Z",
            "distance_km": 34.5,
            "fare": 380000,
            "outcome": "completed",
            "rating": 1,
            "feedback": "Tài xế tự ý đi đường vòng tránh tắc làm khách suýt trễ chuyến bay.",
        },
        "complaint": {
            "category": "route_detour",
            "event_time": "2026-08-21T10:20:00.000000Z",
            "name": "Khiếu nại: Tự ý đi đường vòng làm kéo dài thời gian di chuyển",
            "description": "Khách hàng khiếu nại tài xế không đi theo chỉ dẫn GPS mà tự ý rẽ vào đường gom và đường vòng để tránh trạm thu phí, làm thời gian chuyến đi kéo dài thêm 35 phút khiến hành khách suýt trễ chuyến bay quốc tế.",
        },
    },
    {
        "driver_code": "DRV-002",
        "trip": {
            "pickup": "TTTM Vincom Bà Triệu, Hai Bà Trưng, Hà Nội",
            "dropoff": "Bến xe Giáp Bát, Hoàng Mai, Hà Nội",
            "start_time": "2026-08-24T11:00:00.000000Z",
            "distance_km": 6.2,
            "fare": 95000,
            "outcome": "completed",
            "rating": 2,
            "feedback": "Tài xế to tiếng khi khách đòi tiền thối lại 25 nghìn.",
        },
        "complaint": {
            "category": "fare_dispute",
            "event_time": "2026-08-24T11:40:00.000000Z",
            "name": "Phản ánh: Tranh cãi tiền thừa và có lời lẽ thiếu lịch sự",
            "description": "Khách thanh toán tiền mặt 120,000 VND cho cước phí 95,000 VND nhưng tài xế viện lý do không có tiền lẻ và yêu cầu không thối lại. Khi khách yêu cầu chuyển khoản, tài xế lớn tiếng tỏ vẻ bực dọc.",
        },
    },
    {
        "driver_code": "DRV-002",
        "trip": {
            "pickup": "Nút giao Ngã Tư Sở, Đống Đa, Hà Nội",
            "dropoff": "Khu đô thị Trung Hòa Nhân Chính, Cầu Giấy, Hà Nội",
            "start_time": "2026-08-26T10:15:00.000000Z",
            "distance_km": 0.0,
            "fare": 0,
            "outcome": "cancelled",
            "rating": None,
            "feedback": None,
        },
        "incident": {
            "incident_type": "abnormal_cancellation",
            "event_time": "2026-08-26T10:25:00.000000Z",
            "name": "Sự cố: Hủy liên tiếp 3 cuốc xe giờ cao điểm tại nút giao tắc",
            "description": "Hệ thống phát hiện tài xế Trần Văn Bình nhận và tự ý hủy liên tiếp 3 cuốc xe được điều phối tự động trong vòng 20 phút tại nút giao thông Ngã Tư Sở với lý do 'tắc đường không muốn vào đón'.",
        },
    },

    # --- Lê Thị Chi (DRV-003) ---
    {
        "driver_code": "DRV-003",
        "trip": {
            "pickup": "Chợ Đồng Xuân, Hoàn Kiếm, Hà Nội",
            "dropoff": "Chung cư Mipec Riverside, Long Biên, Hà Nội",
            "start_time": "2026-08-21T07:30:00.000000Z",
            "distance_km": 5.0,
            "fare": 80000,
            "outcome": "completed",
            "rating": 2,
            "feedback": "Xe bốc mùi tanh nồng từ hải sản của cuốc trước chưa dọn.",
        },
        "complaint": {
            "category": "vehicle_hygiene",
            "event_time": "2026-08-21T08:10:00.000000Z",
            "name": "Phản ánh: Vệ sinh xe kém, khoang xe nồng mùi khó chịu",
            "description": "Hành khách phản ánh nội thất xe có mùi hải sản tanh nồng từ lượt khách chở hàng trước đó nhưng tài xế không lau chùi và khử mùi trước khi đón khách mới, thảm sàn sau có vết bẩn ẩm ướt.",
        },
    },
    {
        "driver_code": "DRV-003",
        "trip": {
            "pickup": "Cầu Vĩnh Tuy, Hai Bà Trưng, Hà Nội",
            "dropoff": "Khu đô thị Vinhomes Ocean Park, Gia Lâm, Hà Nội",
            "start_time": "2026-08-27T06:00:00.000000Z",
            "distance_km": 12.0,
            "fare": 160000,
            "outcome": "completed",
            "rating": 3,
            "feedback": "Xe báo lỗi pin yếu giữa cầu phải chạy rùa bò.",
        },
        "incident": {
            "incident_type": "low_battery_warning",
            "event_time": "2026-08-27T06:25:00.000000Z",
            "name": "Sự cố: Cảnh báo dung lượng pin dưới mức an toàn (SOC < 8%)",
            "description": "Xe VF e34 báo động pin yếu SOC xuống dưới 8% khi đang chở khách trên cầu Vĩnh Tuy. Hệ thống xe tự động hạn chế công suất vận hành (rùa bò). Tài xế phải bật đèn khẩn cấp di chuyển đến trạm sạc gần nhất sau khi hoàn tất chuyến.",
        },
    },

    # --- Phạm Quốc Dũng (DRV-004) ---
    {
        "driver_code": "DRV-004",
        "trip": {
            "pickup": "Bến xe Nước Ngầm, Hoàng Mai, Hà Nội",
            "dropoff": "Cầu Giấy, Hà Nội",
            "start_time": "2026-08-22T09:30:00.000000Z",
            "distance_km": 13.5,
            "fare": 185000,
            "outcome": "completed",
            "rating": 1,
            "feedback": "Lái xe quá ẩu, phanh gấp suýt tông xe máy phía trước.",
        },
        "complaint": {
            "category": "reckless_driving",
            "event_time": "2026-08-22T10:15:00.000000Z",
            "name": "Khiếu nại: Lái xe ẩu, lạng lách và phanh gấp gây nguy hiểm",
            "description": "Khách hàng gửi khiếu nại khẩn cấp phản ánh tài xế Phạm Quốc Dũng liên tục lạng lách qua các khe hẹp giữa xe tải trên đường Vành Đai 3, nhiều lần phanh gấp khiến hành khách hoảng loạn và say xe nghiêm trọng.",
        },
    },
    {
        "driver_code": "DRV-004",
        "trip": {
            "pickup": "Ga Hà Nội, Lê Duẩn, Đống Đa, Hà Nội",
            "dropoff": "Khu đô thị Ngoại Giao Đoàn, Bắc Từ Liêm, Hà Nội",
            "start_time": "2026-08-26T02:00:00.000000Z",
            "distance_km": 9.8,
            "fare": 140000,
            "outcome": "completed",
            "rating": 2,
            "feedback": "Không hỗ trợ bê vali cho người già, ngồi im trong xe.",
        },
        "complaint": {
            "category": "luggage_support",
            "event_time": "2026-08-26T02:40:00.000000Z",
            "name": "Phản ánh: Thiếu tinh thần phục vụ, không hỗ trợ hành lý cho khách",
            "description": "Hành khách lớn tuổi mang 2 kiện vali nặng đón xe tại Ga Hà Nội nhưng tài xế chỉ ngồi trong xe bấm nút mở cốp, từ chối xuống xe hỗ trợ nâng vali lên xe dù khách đã lịch sự nhờ giúp đỡ.",
        },
    },
    {
        "driver_code": "DRV-004",
        "trip": {
            "pickup": "Đường Giải Phóng, Hoàng Mai, Hà Nội",
            "dropoff": "Đường Vành Đai 3 trên cao, Hà Nội",
            "start_time": "2026-08-28T14:20:00.000000Z",
            "distance_km": 10.0,
            "fare": 130000,
            "outcome": "completed",
            "rating": 3,
            "feedback": "Xe chạy quá tốc độ cảm biến báo liên tục.",
        },
        "incident": {
            "incident_type": "overspeeding",
            "event_time": "2026-08-28T14:35:00.000000Z",
            "name": "Sự cố: Chạy quá tốc độ quy định trong khu đô thị (74km/h / 50km/h)",
            "description": "Thiết bị giám sát hành trình IoT ghi nhận xe của tài xế Phạm Quốc Dũng duy trì vận tốc 74km/h trong 3 phút liên tục tại đoạn đường Giải Phóng quy định tốc độ tối đa 50km/h, vi phạm quy chuẩn an toàn lái xe GSM.",
        },
    },

    # --- Hoàng Văn Minh (DRV-005) ---
    {
        "driver_code": "DRV-005",
        "trip": {
            "pickup": "Hồ Tây, Quảng An, Tây Hồ, Hà Nội",
            "dropoff": "Sân bay Quốc tế Nội Bài, Hà Nội",
            "start_time": "2026-08-23T04:15:00.000000Z",
            "distance_km": 24.0,
            "fare": 270000,
            "outcome": "completed",
            "rating": 2,
            "feedback": "Tài xế hút thuốc lá điện tử trước khi đón khách, mùi nồng.",
        },
        "complaint": {
            "category": "smoking_violation",
            "event_time": "2026-08-23T05:00:00.000000Z",
            "name": "Khiếu nại: Mùi thuốc lá điện tử nồng nặc trong khoang xe",
            "description": "Khách hàng phản ánh tài xế Hoàng Văn Minh hút thuốc lá điện tử (vape) trong xe ngay trước giờ đón khách, mùi khói hoá chất đậm đặc khiến hành khách bị dị ứng ho liên tục trong suốt chuyến đi.",
        },
    },
    {
        "driver_code": "DRV-005",
        "trip": {
            "pickup": "Trạm thu phí Cầu Giấy, Hà Nội",
            "dropoff": "Đại lộ Thăng Long, Hà Nội",
            "start_time": "2026-08-27T08:00:00.000000Z",
            "distance_km": 15.0,
            "fare": 190000,
            "outcome": "completed",
            "rating": 2,
            "feedback": "Đòi thêm tiền vé cầu đường dù app đã tính trọn gói.",
        },
        "complaint": {
            "category": "toll_overcharge",
            "event_time": "2026-08-27T08:50:00.000000Z",
            "name": "Khiếu nại: Thu thêm tiền phí cầu đường sai quy định",
            "description": "Hành khách phản ánh tài xế yêu cầu trả thêm 35,000 VND tiền mặt với lý do phí qua trạm BOT tự động, dù đơn đặt xe qua ứng dụng Xanh SM đã thông báo cước trọn gói bao gồm toàn bộ phụ phí cầu đường.",
        },
    },
    {
        "driver_code": "DRV-005",
        "trip": {
            "pickup": "Sảnh T1 Sân bay Nội Bài, Hà Nội",
            "dropoff": "Trung tâm Hội nghị Quốc gia, Nam Từ Liêm, Hà Nội",
            "start_time": "2026-08-29T09:30:00.000000Z",
            "distance_km": 27.5,
            "fare": 310000,
            "outcome": "completed",
            "rating": 3,
            "feedback": "Đến điểm đón trễ 25 phút không báo trước.",
        },
        "incident": {
            "incident_type": "pickup_delay",
            "event_time": "2026-08-29T10:00:00.000000Z",
            "name": "Sự cố: Chậm trễ giờ đón khách đặt trước 25 phút tại sân bay",
            "description": "Tài xế Hoàng Văn Minh nhận đơn chuyến đặt trước đi sân bay nhưng di chuyển sai luồng đón và tắt chuông điện thoại, khiến khách chờ đợi 25 phút tại sảnh đến trong tình trạng không liên lạc được.",
        },
    },

    # --- Vũ Nhật Minh (DRV-006) ---
    {
        "driver_code": "DRV-006",
        "trip": {
            "pickup": "Đại học Quốc gia Hà Nội, Xuân Thủy, Cầu Giấy",
            "dropoff": "Phố đi bộ Hồ Gươm, Hoàn Kiếm, Hà Nội",
            "start_time": "2026-08-23T11:00:00.000000Z",
            "distance_km": 8.5,
            "fare": 125000,
            "outcome": "completed",
            "rating": 2,
            "feedback": "Tài xế gắt gỏng khi khách xin đỗ né vũng nước ngập.",
        },
        "complaint": {
            "category": "service_attitude",
            "event_time": "2026-08-23T11:45:00.000000Z",
            "name": "Phản ánh: Thái độ gắt gỏng khi khách nhờ tránh vũng nước ngập",
            "description": "Hành khách trời mưa nhờ tài xế lách xe thêm 10 mét để tránh vũng nước ngập sâu trước sảnh nhưng tài xế từ chối và nói lớn tiếng 'tôi chỉ đỗ đúng định vị, khách không xuống thì tự hủy chuyến'.",
        },
    },
    {
        "driver_code": "DRV-006",
        "trip": {
            "pickup": "Cầu Nhật Tân, Tây Hồ, Hà Nội",
            "dropoff": "Sân bay Nội Bài, Hà Nội",
            "start_time": "2026-08-28T07:15:00.000000Z",
            "distance_km": 21.0,
            "fare": 240000,
            "outcome": "completed",
            "rating": 3,
            "feedback": "Xe dính đinh thủng lốp giữa cầu trễ 30 phút.",
        },
        "incident": {
            "incident_type": "flat_tire_incident",
            "event_time": "2026-08-28T07:35:00.000000Z",
            "name": "Sự cố: Phương tiện cán đinh thủng lốp trên cầu Nhật Tân",
            "description": "Khi xe đang chở khách trên cầu Nhật Tân thì lốp sau bên lái bị cán vật nhọn tụt áp suất khẩn cấp. Tài xế dừng xe an toàn vào làn dừng khẩn cấp và gọi xe dự phòng hỗ trợ khách tiếp tục hành trình.",
        },
    },

    # --- Đặng Hương Giang (DRV-007) ---
    {
        "driver_code": "DRV-007",
        "trip": {
            "pickup": "Khu đô thị Royal City, Nguyễn Trãi, Thanh Xuân, Hà Nội",
            "dropoff": "Bệnh viện Việt Đức, Tràng Thi, Hoàn Kiếm, Hà Nội",
            "start_time": "2026-08-25T03:00:00.000000Z",
            "distance_km": 7.0,
            "fare": 105000,
            "outcome": "completed",
            "rating": 2,
            "feedback": "Đỗ sai sảnh đón bắt khách bệnh đi bộ xa.",
        },
        "complaint": {
            "category": "pickup_confusion",
            "event_time": "2026-08-25T03:40:00.000000Z",
            "name": "Khiếu nại: Đỗ sai sảnh đón và từ chối di chuyển lại gần khách",
            "description": "Khách đặt xe đưa người nhà đi viện tại sảnh R2 nhưng tài xế đỗ tại sảnh R5 (cách 400m) và kiên quyết yêu cầu khách đi bộ sang chứ không chịu đánh xe qua đón, dù đường nội khu thông thoáng.",
        },
    },
    {
        "driver_code": "DRV-007",
        "trip": {
            "pickup": "Tòa nhà Keangnam Landmark 72, Phạm Hùng, Cầu Giấy",
            "dropoff": "Văn Miếu Quốc Tử Giám, Đống Đa, Hà Nội",
            "start_time": "2026-08-29T02:15:00.000000Z",
            "distance_km": 8.0,
            "fare": 120000,
            "outcome": "completed",
            "rating": 3,
            "feedback": "Màn hình xe bị đơ khởi động lại mấy lần.",
        },
        "incident": {
            "incident_type": "display_infotainment_freeze",
            "event_time": "2026-08-29T02:30:00.000000Z",
            "name": "Sự cố: Màn hình trung tâm ô tô bị đơ treo ứng dụng dẫn đường",
            "description": "Trong quá trình đón khách, màn hình cảm ứng trung tâm của xe VinFast VF8 bị treo đen màn hình, tài xế phải tấp vào lề khởi động lại hệ thống xe mất 10 phút trước khi có thể dẫn đường tiếp tục.",
        },
    },

    # --- Bùi Thu Hà (DRV-008) ---
    {
        "driver_code": "DRV-008",
        "trip": {
            "pickup": "Công viên Cầu Giấy, Duy Tân, Hà Nội",
            "dropoff": "Nhà hát Lớn Hà Nội, Tràng Tiền, Hoàn Kiếm",
            "start_time": "2026-08-24T08:30:00.000000Z",
            "distance_km": 9.2,
            "fare": 135000,
            "outcome": "completed",
            "rating": 2,
            "feedback": "Lái xe giật cục, nhấn ga nhả ga liên tục làm say xe.",
        },
        "complaint": {
            "category": "driving_style",
            "event_time": "2026-08-24T09:15:00.000000Z",
            "name": "Phản ánh: Kỹ năng lái xe giật cục gây say xe khó chịu",
            "description": "Hành khách phản ánh tài xế Bùi Thu Hà đạp ga và nhả ga ngắt quãng liên tục, không giữ đều chân ga trên đường thẳng khiến xe bị giật cục từng cơn làm phụ nữ mang thai ngồi sau buồn nôn khó chịu.",
        },
    },
    {
        "driver_code": "DRV-008",
        "trip": {
            "pickup": "Tòa nhà Lotte Center, Đào Tấn, Ba Đình, Hà Nội",
            "dropoff": "Khu đô thị Ecopark, Văn Giang, Hưng Yên",
            "start_time": "2026-08-26T12:00:00.000000Z",
            "distance_km": 18.5,
            "fare": 250000,
            "outcome": "completed",
            "rating": 3,
            "feedback": "Khách bỏ quên ô dù và ví tiền, tài xế chậm trễ trả đồ.",
        },
        "complaint": {
            "category": "lost_property_delay",
            "event_time": "2026-08-26T14:30:00.000000Z",
            "name": "Khiếu nại: Chậm trễ hỗ trợ hoàn trả đồ bỏ quên của khách",
            "description": "Khách bỏ quên ví tiền và giấy tờ tùy thân trên ghế sau xe. Dù khách đã liên hệ tổng đài ngay sau khi kết thúc chuyến 15 phút, tài xế không chịu kiểm tra xe ngay mà đến chiều tối hôm sau mới báo có thấy đồ.",
        },
    },
    {
        "driver_code": "DRV-008",
        "trip": {
            "pickup": "Hầm chui Kim Liên, Đống Đa, Hà Nội",
            "dropoff": "Bệnh viện Bạch Mai, Hà Nội",
            "start_time": "2026-08-28T04:10:00.000000Z",
            "distance_km": 3.0,
            "fare": 50000,
            "outcome": "completed",
            "rating": 3,
            "feedback": "Mất tín hiệu GPS làm app nhảy lung tung.",
        },
        "incident": {
            "incident_type": "gps_signal_loss",
            "event_time": "2026-08-28T04:25:00.000000Z",
            "name": "Sự cố: Mất tín hiệu kết nối định vị GPS quá 20 phút",
            "description": "Thiết bị điện thoại tài xế mất sóng kết nối GPS và 4G liên tục trong hơn 20 phút sau khi qua hầm chui Kim Liên, hệ thống trung tâm không cập nhật được vị trí và trạng thái chuyến xe của tài xế.",
        },
    },
]


def expand_and_seed_database() -> dict[str, Any]:
    """1. Generate and seed new trips, complaints, and incidents into SQLite & JSON."""
    db_path = ROOT_DIR / "data" / "gsm_local.db"
    repo = LocalDatabaseRepository(db_path)
    
    seed_json_path = ROOT_DIR / "data" / "v3_timeline_seed.json"
    with open(seed_json_path, "r", encoding="utf-8") as f:
        seed_data = json.load(f)

    existing_trip_ids = {t["trip_id"] for t in seed_data.get("trips", [])}
    existing_comp_ids = {c["complaint_id"] for c in seed_data.get("complaints", [])}
    existing_inc_ids = {i["incident_id"] for i in seed_data.get("incidents", [])}

    added_trips = []
    added_complaints = []
    added_incidents = []

    for item in NEW_CORE_DATA:
        driver_code = item["driver_code"]
        driver_info = CORE_DRIVERS[driver_code]
        d_id = driver_info["id"]
        d_name = driver_info["name"]
        
        # 1. Trip
        t_data = item.get("trip")
        trip_id = deterministic_uuid("trip", f"{driver_code}:{t_data['start_time']}")
        if trip_id not in existing_trip_ids:
            trip_dict = {
                "trip_id": trip_id,
                "driver_id": d_id,
                "driver_name": d_name,
                "start_time": t_data["start_time"],
                "outcome": t_data["outcome"],
                "reason_code": "unspecified" if t_data["outcome"] == "completed" else "driver_cancellation",
                "description": f"Chuyến {trip_id[:8]} của tài xế {d_name} từ {t_data['pickup']} đến {t_data['dropoff']}.",
                "visibility_snapshot_ids": [SNAPSHOT_ID],
                "region": "Hà Nội",
                "service_type": "Taxi Xanh SM",
                "pickup": t_data["pickup"],
                "dropoff": t_data["dropoff"],
            }
            seed_data["trips"].append(trip_dict)
            existing_trip_ids.add(trip_id)
            added_trips.append(trip_dict)

            # Persist to SQLite
            is_canc = t_data["outcome"] == "cancelled"
            repo.upsert_trip(TripRecord(
                trip_id=trip_id,
                driver_id=d_id,
                snapshot_id=SNAPSHOT_ID,
                visibility_snapshot_ids=[SNAPSHOT_ID],
                start_time=t_data["start_time"],
                end_time=(datetime.fromisoformat(t_data["start_time"].replace("Z", "+00:00")) + timedelta(minutes=30)).isoformat(),
                pickup_address=t_data["pickup"],
                dropoff_address=t_data["dropoff"],
                region="Hà Nội",
                service_type="Taxi Xanh SM",
                distance_km=t_data["distance_km"],
                fare_amount=t_data["fare"],
                outcome=t_data["outcome"],
                reason_code="completed_normal" if not is_canc else "driver_cancelled",
                cancel_party="none" if not is_canc else "driver",
                passenger_rating=t_data["rating"],
                passenger_feedback=t_data["feedback"],
                notes=trip_dict["description"],
                created_at=t_data["start_time"],
            ))

        # 2. Complaint (if any)
        c_data = item.get("complaint")
        if c_data:
            comp_id = deterministic_uuid("complaint", f"{driver_code}:{c_data['event_time']}")
            if comp_id not in existing_comp_ids:
                comp_dict = {
                    "complaint_id": comp_id,
                    "driver_id": d_id,
                    "driver_name": driver_info["full_name"],
                    "trip_id": trip_id,
                    "category": c_data["category"],
                    "event_time": c_data["event_time"],
                    "name": c_data["name"],
                    "description": c_data["description"],
                    "visibility_snapshot_ids": [SNAPSHOT_ID],
                }
                seed_data["complaints"].append(comp_dict)
                existing_comp_ids.add(comp_id)
                added_complaints.append(comp_dict)

                # Persist to SQLite
                repo.upsert_complaint(ComplaintRecord(
                    complaint_id=comp_id,
                    driver_id=d_id,
                    trip_id=trip_id,
                    category=c_data["category"],
                    event_time=c_data["event_time"],
                    name=c_data["name"],
                    description=c_data["description"],
                    visibility_snapshot_ids=[SNAPSHOT_ID],
                    created_at=c_data["event_time"],
                ))

        # 3. Incident (if any)
        i_data = item.get("incident")
        if i_data:
            inc_id = deterministic_uuid("incident", f"{driver_code}:{i_data['event_time']}")
            if inc_id not in existing_inc_ids:
                inc_dict = {
                    "incident_id": inc_id,
                    "driver_id": d_id,
                    "driver_name": driver_info["full_name"],
                    "trip_id": trip_id,
                    "incident_type": i_data["incident_type"],
                    "event_time": i_data["event_time"],
                    "name": i_data["name"],
                    "description": i_data["description"],
                    "visibility_snapshot_ids": [SNAPSHOT_ID],
                }
                seed_data["incidents"].append(inc_dict)
                existing_inc_ids.add(inc_id)
                added_incidents.append(inc_dict)

                # Persist to SQLite
                repo.upsert_incident(IncidentRecord(
                    incident_id=inc_id,
                    driver_id=d_id,
                    trip_id=trip_id,
                    incident_type=i_data["incident_type"],
                    event_time=i_data["event_time"],
                    name=i_data["name"],
                    description=i_data["description"],
                    visibility_snapshot_ids=[SNAPSHOT_ID],
                    created_at=i_data["event_time"],
                ))

    # Also import V2 catalog complaints & incidents into SQLite if not already there
    from gsm_memory.adapters.v2_operational_catalog import COMPLAINTS_DATA, INCIDENTS_DATA, DRIVERS
    v2_driver_map = {d["id"]: d["name"] for d in DRIVERS}

    for c in COMPLAINTS_DATA:
        cid, c_trip, c_inc, c_rule, c_cat, c_sent, c_time, c_src, c_name, c_desc = c
        # Derive driver from trip e.g. v2_trip_004_10 -> v2_drv_004
        d_id = f"v2_drv_{c_trip.split('_')[2]}" if "_" in c_trip else "v2_drv_001"
        valid_trip_id = c_trip if c_trip in existing_trip_ids else None
        if cid not in existing_comp_ids:
            repo.upsert_complaint(ComplaintRecord(
                complaint_id=cid,
                driver_id=d_id,
                trip_id=valid_trip_id,
                category=c_cat,
                event_time=c_time,
                name=c_name,
                description=c_desc,
                visibility_snapshot_ids=[SNAPSHOT_ID],
                created_at=c_time,
            ))
            existing_comp_ids.add(cid)
            added_complaints.append({
                "complaint_id": cid,
                "driver_id": d_id,
                "driver_name": v2_driver_map.get(d_id, "Tài xế GSM"),
                "trip_id": valid_trip_id,
                "category": c_cat,
                "event_time": c_time,
                "name": c_name,
                "description": c_desc,
            })

    for i in INCIDENTS_DATA:
        iid = i.get("id") or i.get("incident_id")
        d_id = i.get("driver_id", "v2_drv_001")
        i_trip = i.get("shift_id")
        valid_i_trip = i_trip if i_trip in existing_trip_ids else None
        if iid not in existing_inc_ids:
            repo.upsert_incident(IncidentRecord(
                incident_id=iid,
                driver_id=d_id,
                trip_id=valid_i_trip,
                incident_type=i.get("type", "operational_incident"),
                event_time=i.get("timestamp"),
                name=i.get("name"),
                description=i.get("description", ""),
                visibility_snapshot_ids=[SNAPSHOT_ID],
                created_at=i.get("timestamp") or "2025-07-20T00:00:00Z",
            ))
            existing_inc_ids.add(iid)
            added_incidents.append({
                "incident_id": iid,
                "driver_id": d_id,
                "driver_name": v2_driver_map.get(d_id, "Tài xế GSM"),
                "trip_id": valid_i_trip,
                "incident_type": i.get("type", "operational_incident"),
                "event_time": i.get("timestamp"),
                "name": i.get("name"),
                "description": i.get("description", ""),
            })

    # Save expanded JSON
    with open(seed_json_path, "w", encoding="utf-8") as f:
        json.dump(seed_data, f, ensure_ascii=False, indent=2)

    print(f"✅ Database & JSON updated:")
    print(f"   Trips added: {len(added_trips)} (Total: {len(seed_data['trips'])})")
    print(f"   Complaints added: {len(added_complaints)} (Total in DB: {len(existing_comp_ids)})")
    print(f"   Incidents added: {len(added_incidents)} (Total in DB: {len(existing_inc_ids)})")

    return {
        "added_trips": added_trips,
        "added_complaints": added_complaints,
        "added_incidents": added_incidents,
    }


def update_neo4j_graph(all_complaints: list[dict], all_incidents: list[dict], all_trips: list[dict]) -> None:
    """2. Update Neo4j graph nodes and relationships for Complaints, Incidents and Trips."""
    from neo4j import GraphDatabase

    uri = os.getenv("NEO4J_OPERATIONAL_URI") or os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_OPERATIONAL_USERNAME") or os.getenv("NEO4J_USERNAME")
    pwd = os.getenv("NEO4J_OPERATIONAL_PASSWORD") or os.getenv("NEO4J_PASSWORD")

    if not uri or not pwd:
        print("⚠️ Neo4j credentials missing, skipping Neo4j update.")
        return

    print(f"🚀 Updating Neo4j at {uri}...")
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    with driver.session() as s:
        # A. Upsert Trips
        trip_cypher = """
        UNWIND $trips AS t
        MERGE (trip:Trip:GSMOperationalV3Timeline {id: t.trip_id})
        SET trip.name = t.name,
            trip.driver_id = t.driver_id,
            trip.start_time = t.start_time,
            trip.outcome = t.outcome,
            trip.pickup = t.pickup,
            trip.dropoff = t.dropoff,
            trip.description = t.description,
            trip.visibility_snapshot_ids = t.visibility_snapshot_ids
        WITH trip, t
        MATCH (d:Driver:GSMOperationalV3Timeline)
        WHERE (d.id = t.driver_id OR d.id = trip.driver_id)
        MERGE (d)-[r:PERFORMED]->(trip)
        SET r.outcome = t.outcome,
            r.visibility_snapshot_ids = t.visibility_snapshot_ids
        """
        trips_payload = [
            {
                "trip_id": t["trip_id"],
                "name": f"Chuyến {t['trip_id'][:8]}",
                "driver_id": t["driver_id"],
                "start_time": t["start_time"],
                "outcome": t["outcome"],
                "pickup": t.get("pickup", ""),
                "dropoff": t.get("dropoff", ""),
                "description": t.get("description", ""),
                "visibility_snapshot_ids": t.get("visibility_snapshot_ids", [SNAPSHOT_ID]),
            }
            for t in all_trips
        ]
        if trips_payload:
            s.run(trip_cypher, trips=trips_payload)
            print(f"   - Neo4j: Merged {len(trips_payload)} Trips and PERFORMED edges.")

        # B. Upsert Complaints
        comp_cypher = """
        UNWIND $comps AS c
        MERGE (comp:Complaint:GSMOperationalV3Timeline {id: c.complaint_id})
        SET comp.name = c.name,
            comp.driver_id = c.driver_id,
            comp.category = c.category,
            comp.description = c.description,
            comp.event_time = c.event_time,
            comp.visibility_snapshot_ids = c.visibility_snapshot_ids
        WITH comp, c
        MATCH (d:Driver:GSMOperationalV3Timeline)
        WHERE (d.id = c.driver_id OR d.id = comp.driver_id)
        MERGE (d)-[rc:RECEIVED_COMPLAINT]->(comp)
        SET rc.category = c.category,
            rc.visibility_snapshot_ids = c.visibility_snapshot_ids
        WITH comp, c
        WHERE c.trip_id IS NOT NULL
        MATCH (t:Trip:GSMOperationalV3Timeline {id: c.trip_id})
        MERGE (comp)-[rt:ABOUT_TRIP]->(t)
        SET rt.visibility_snapshot_ids = c.visibility_snapshot_ids
        """
        comps_payload = [
            {
                "complaint_id": c["complaint_id"],
                "name": c["name"],
                "driver_id": c["driver_id"],
                "category": c["category"],
                "description": c["description"],
                "event_time": c["event_time"],
                "trip_id": c.get("trip_id"),
                "visibility_snapshot_ids": c.get("visibility_snapshot_ids", [SNAPSHOT_ID]),
            }
            for c in all_complaints
        ]
        if comps_payload:
            s.run(comp_cypher, comps=comps_payload)
            print(f"   - Neo4j: Merged {len(comps_payload)} Complaints and RECEIVED_COMPLAINT edges.")

        # C. Upsert Incidents
        inc_cypher = """
        UNWIND $incs AS i
        MERGE (inc:Incident:GSMOperationalV3Timeline {id: i.incident_id})
        SET inc.name = i.name,
            inc.driver_id = i.driver_id,
            inc.incident_type = i.incident_type,
            inc.description = i.description,
            inc.event_time = i.event_time,
            inc.visibility_snapshot_ids = i.visibility_snapshot_ids
        WITH inc, i
        MATCH (d:Driver:GSMOperationalV3Timeline)
        WHERE (d.id = i.driver_id OR d.id = inc.driver_id)
        MERGE (d)-[ri:HAS_INCIDENT]->(inc)
        SET ri.incident_type = i.incident_type,
            ri.visibility_snapshot_ids = i.visibility_snapshot_ids
        WITH inc, i
        WHERE i.trip_id IS NOT NULL
        MATCH (t:Trip:GSMOperationalV3Timeline {id: i.trip_id})
        MERGE (inc)-[rt:ABOUT_TRIP]->(t)
        SET rt.visibility_snapshot_ids = i.visibility_snapshot_ids
        """
        incs_payload = [
            {
                "incident_id": i["incident_id"],
                "name": i["name"],
                "driver_id": i["driver_id"],
                "incident_type": i.get("incident_type") or i.get("type", "operational"),
                "description": i["description"],
                "event_time": i["event_time"],
                "trip_id": i.get("trip_id"),
                "visibility_snapshot_ids": i.get("visibility_snapshot_ids", [SNAPSHOT_ID]),
            }
            for i in all_incidents
        ]
        if incs_payload:
            s.run(inc_cypher, incs=incs_payload)
            print(f"   - Neo4j: Merged {len(incs_payload)} Incidents and HAS_INCIDENT edges.")

    driver.close()
    print("✅ Neo4j update completed.")


def index_nodes_to_qdrant(complaints: list[dict], incidents: list[dict]) -> None:
    """3. Method 1: Embed complaints & incidents with NVIDIA Nemotron 1B and index into Qdrant."""
    import requests

    qdrant_url = os.getenv("QDRANT_URL", "").rstrip("/")
    qdrant_key = os.getenv("QDRANT_API_KEY", "")
    collection = os.getenv("QDRANT_COLLECTION", "gsm-memory")

    if not qdrant_url:
        print("⚠️ QDRANT_URL missing, skipping Qdrant indexing.")
        return

    headers = {"Content-Type": "application/json"}
    if qdrant_key:
        headers["api-key"] = qdrant_key

    # Ensure payload schema index for quick driver filtering
    print(f"🚀 Preparing Qdrant collection '{collection}'...")
    for field in ["driver_id", "node_id", "kind", "category"]:
        requests.put(
            f"{qdrant_url}/collections/{collection}/index",
            headers=headers,
            json={"field_name": field, "field_schema": "keyword"},
            timeout=10,
        )

    embedder = NvidiaNemotronEmbedder()

    # Build items to embed
    items_to_index = []
    
    # 1. Complaints
    for c in complaints:
        node_id = c["complaint_id"]
        # Deterministic Qdrant Point UUID
        point_id = deterministic_uuid("qdrant_complaint", node_id)
        d_name = c.get("driver_name", "Tài xế")
        text_for_embed = (
            f"Khiếu nại khách hàng: {c['name']}. "
            f"Thể loại phản ánh: {c['category']}. "
            f"Nội dung phản ánh: {c['description']} "
            f"Tài xế liên quan: {d_name}."
        )
        payload = {
            "node_id": node_id,
            "kind": "complaint",
            "node_type": "Complaint",
            "driver_id": c["driver_id"],
            "driver_name": d_name,
            "category": c["category"],
            "name": c["name"],
            "description": c["description"],
            "event_time": c["event_time"],
            "trip_id": c.get("trip_id", ""),
            "text": text_for_embed,
        }
        items_to_index.append((point_id, text_for_embed, payload))

    # 2. Incidents
    for i in incidents:
        node_id = i["incident_id"]
        point_id = deterministic_uuid("qdrant_incident", node_id)
        d_name = i.get("driver_name", "Tài xế")
        text_for_embed = (
            f"Sự cố vận hành: {i['name']}. "
            f"Phân loại sự cố: {i.get('incident_type', '')}. "
            f"Mô tả chi tiết: {i['description']} "
            f"Tài xế liên quan: {d_name}."
        )
        payload = {
            "node_id": node_id,
            "kind": "incident",
            "node_type": "Incident",
            "driver_id": i["driver_id"],
            "driver_name": d_name,
            "category": i.get("incident_type", "operational"),
            "name": i["name"],
            "description": i["description"],
            "event_time": i["event_time"],
            "trip_id": i.get("trip_id", ""),
            "text": text_for_embed,
        }
        items_to_index.append((point_id, text_for_embed, payload))

    print(f"📦 Total items to embed & index into Qdrant: {len(items_to_index)}")

    # Batch embedding with NVIDIA Nemotron 1B
    BATCH_SIZE = 30
    points_to_upload = []

    for idx in range(0, len(items_to_index), BATCH_SIZE):
        batch = items_to_index[idx : idx + BATCH_SIZE]
        texts = [b[1] for b in batch]
        print(f"   Embedding batch {idx // BATCH_SIZE + 1}/{(len(items_to_index) + BATCH_SIZE - 1) // BATCH_SIZE} ({len(texts)} items)...")
        vecs = embedder.embed_passages(texts)
        for b, vec in zip(batch, vecs):
            points_to_upload.append({
                "id": b[0],
                "vector": vec,
                "payload": b[2],
            })

    # Upload points to Qdrant
    print(f"⚡ Uploading {len(points_to_upload)} points to Qdrant...")
    for idx in range(0, len(points_to_upload), 50):
        sub_points = points_to_upload[idx : idx + 50]
        resp = requests.put(
            f"{qdrant_url}/collections/{collection}/points",
            headers=headers,
            json={"points": sub_points},
            timeout=30,
        )
        if resp.status_code not in (200, 201):
            print(f"❌ Qdrant upload batch error: {resp.status_code} {resp.text}")
        else:
            print(f"   - Uploaded {len(sub_points)} points successfully.")

    print(f"🎉 Qdrant Indexing Completed for {len(points_to_upload)} operational nodes!")


def main() -> None:
    # Step 1: Expand database
    data_res = expand_and_seed_database()

    # Step 2: Fetch all complaints & incidents for Neo4j and Qdrant
    db_path = ROOT_DIR / "data" / "gsm_local.db"
    repo = LocalDatabaseRepository(db_path)
    all_comps = repo.get_complaints(limit=500)
    all_incs = repo.get_incidents(limit=500)
    all_trips = repo.get_trips(limit=500)

    # Convert to dict
    comp_dicts = [
        {
            "complaint_id": c.complaint_id,
            "driver_id": c.driver_id,
            "driver_name": repo.get_driver(c.driver_id).full_name if repo.get_driver(c.driver_id) else "Tài xế GSM",
            "trip_id": c.trip_id,
            "category": c.category,
            "event_time": c.event_time,
            "name": c.name or f"Khiếu nại {c.complaint_id[:8]}",
            "description": c.description or "",
            "visibility_snapshot_ids": [SNAPSHOT_ID],
        }
        for c in all_comps
    ]

    inc_dicts = [
        {
            "incident_id": i.incident_id,
            "driver_id": i.driver_id,
            "driver_name": repo.get_driver(i.driver_id).full_name if repo.get_driver(i.driver_id) else "Tài xế GSM",
            "trip_id": i.trip_id,
            "incident_type": i.incident_type,
            "event_time": i.event_time,
            "name": i.name or f"Sự cố {i.incident_id[:8]}",
            "description": i.description or "",
            "visibility_snapshot_ids": [SNAPSHOT_ID],
        }
        for i in all_incs
    ]

    trip_dicts = [
        {
            "trip_id": t.trip_id,
            "driver_id": t.driver_id,
            "name": t.passenger_feedback or f"Chuyến {t.trip_id[:8]}",
            "start_time": t.start_time,
            "outcome": t.outcome,
            "pickup": t.pickup_address,
            "dropoff": t.dropoff_address,
            "description": t.notes or "",
            "visibility_snapshot_ids": [SNAPSHOT_ID],
        }
        for t in all_trips
    ]

    # Step 2: Update Neo4j
    update_neo4j_graph(comp_dicts, inc_dicts, trip_dicts)

    # Step 3: Index onto Qdrant
    index_nodes_to_qdrant(comp_dicts, inc_dicts)


if __name__ == "__main__":
    main()
