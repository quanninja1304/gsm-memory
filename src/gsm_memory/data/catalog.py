from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CaseSpec:
    alias: str
    root: str
    ledger: str
    task: str | None
    foundation: str | None
    family: str
    status: str
    text: str
    known: str
    answer: Any


A0 = "2026-09-16T12:00:00.000000Z"
AC = "2026-09-17T01:00:00.000000Z"
A1 = "2026-09-17T12:00:00.000000Z"


def _c(alias: str, root: int, task: str, family: str, status: str, text: str, answer: Any,
       ledger: str = "L0", known: str = A1) -> CaseSpec:
    foundation = task[4:] if task.startswith("FND:") else None
    return CaseSpec(alias, f"SC{root:02d}", ledger, None if foundation else task, foundation,
                    family, status, text, known, answer)


CASES = [
 _c("C001",1,"T01","Q1","answerable","Theo snapshot P154, quy định doanh số tối thiểu dành cho nhóm tài xế nào, tại khu vực nào?",{"group":"bike_partner","region":"Hà Nội"}),
 _c("C002",1,"T01","Q1","answerable","Theo snapshot P154, ngày vận doanh được hiểu thế nào và truy thu phần doanh số thiếu được tính ra sao?",{"formula":"max(280000-R,0)/5","unit":"VND"}),
 _c("C003",2,"T02","Q4","answerable","Theo edition P154 và conventions được cấp, khoản truy thu theo rule cho tài xế trong W11 là bao nhiêu?",16000),
 _c("C004",3,"T02","Q4","answerable","Theo edition P154 và conventions được cấp, khoản truy thu theo rule cho tài xế trong W12 là bao nhiêu?",0),
 _c("C005",4,"T02","Q4","answerable","Theo edition P154 và conventions được cấp, khoản truy thu theo rule cho tài xế trong W13 là bao nhiêu?",0),
 _c("C006",5,"T02","Q4","answerable","Theo edition P154 và conventions được cấp, khoản truy thu theo rule cho tài xế trong W10 là bao nhiêu?",{"verdict":"not_applicable","amount":None}),
 _c("C007",2,"T02","Q7","insufficient_evidence","Theo edition P154 và conventions được cấp, khoản truy thu theo rule cho tài xế trong W11 là bao nhiêu?",None,"L_NO_OPDAY"),
 _c("C008",2,"T02","Q7","insufficient_evidence","Theo edition P154 và conventions được cấp, khoản truy thu theo rule cho tài xế trong W11 là bao nhiêu?",None,"L_WRONG_DRIVER"),
 _c("C009",6,"T02","Q6","answerable","Theo edition P154, khoản truy thu theo rule cho tài xế trong W14 là bao nhiêu?",16000,"L0",A0),
 _c("C010",6,"T02","Q6","answerable","Theo edition P154, khoản truy thu theo rule cho tài xế trong W14 là bao nhiêu?",8000),
 _c("C011",6,"T02","Q6","answerable","Theo edition P154, khoản truy thu theo rule cho tài xế trong W14 là bao nhiêu?",8000,"L0",AC),
 _c("C012",6,"T02","Q7","unresolved_conflict","Theo edition P154, khoản truy thu theo rule cho tài xế trong W14 là bao nhiêu?",None,"L_CONFLICT"),
 _c("C013",6,"T02","Q7","insufficient_evidence","Theo edition P154, khoản truy thu theo rule cho tài xế trong W14 là bao nhiêu?",None,"L_RETRACT"),
 _c("C014",7,"T03","Q4","answerable","Theo riêng rule auto-accept của P151, tài xế có thỏa điều kiện tại checkpoint cuối WA14 không? Nếu có, văn bản nêu đến khi nào?",{"condition_met":True,"until":"23h59"}),
 _c("C015",8,"T03","Q4","answerable","Theo riêng rule auto-accept của P151, tài xế có thỏa điều kiện tại checkpoint cuối WA15 không?",{"condition_met":False}),
 _c("C016",7,"T03","Q7","insufficient_evidence","Theo riêng rule auto-accept của P151, tài xế có thỏa điều kiện tại checkpoint cuối WA14 không?",None,"L_WRONG_WINDOW"),
 _c("C017",9,"T04","Q1","answerable","Theo FAQ P05, mốc thời gian nào quyết định khung giờ quy đổi điểm của chuyến?","customer_request_time"),
 _c("C018",9,"T04","Q1","answerable","Theo FAQ P05, đơn vị tính điểm cho đơn giao nhiều điểm là gì?","completed_delivery_points"),
 _c("C019",9,"T04","Q1","answerable","Theo FAQ P05, không có đánh giá có bị tính 0 sao không, và kết quả thưởng giữa các tuần có cộng dồn không?",{"unrated_is_zero":False,"weeks_accumulate":False}),
 _c("C020",10,"T05","Q4","answerable","Theo riêng điều kiện rating trong P05, rating báo cáo của tài xế trong WW0 có đạt ngưỡng không?",False),
 _c("C021",11,"T05","Q4","answerable","Theo riêng điều kiện rating trong P05, rating báo cáo của tài xế trong WW1 có đạt ngưỡng không?",True),
 _c("C022",12,"T05","Q7","insufficient_evidence","Theo riêng điều kiện rating trong P05, rating báo cáo của tài xế trong WW2 có đạt ngưỡng không?",None),
 _c("C023",13,"T06","Q1","answerable","Thông báo P23 nêu nhóm tài xế và các Depot nào trong phạm vi?",{"group":"taxi_driver","depots":[1,6,7],"region":"HCM_OLD"}),
 _c("C024",13,"T06","Q1","answerable","Thông báo P23 nêu áp dụng từ kỳ lương nào?","tháng 6/2026"),
 _c("C025",14,"T07","Q4","answerable","Xét program và membership tại Tf, tài xế có thuộc nhóm được nêu trong edition P23 không?",True,"L0",A0),
 _c("C026",15,"T07","Q4","answerable","Xét program và membership tại Tf, tài xế có thuộc nhóm được nêu trong edition P23 không?",False),
 _c("C027",16,"T07","Q4","answerable","Xét program và membership tại Tf, tài xế có thuộc nhóm được nêu trong edition P23 không?",False),
 _c("C028",14,"T07","Q6","answerable","Xét program và membership tại Tf, tài xế có thuộc nhóm được nêu trong edition P23 không?",False),
 _c("C029",17,"FND:aggregate","Q3","answerable","Tính chính xác cancel_rate_30d của tài xế tại Tm theo definition được cấp, kèm bằng chứng population và coverage.",{"n":1,"d":5}),
 _c("C030",18,"FND:bridge","Q5","answerable","Theo S_BRIDGE, tài xế có thỏa rule tại Tm không? Cần bằng chứng về fleet_region và ngoại lệ.",True),
 _c("C031",18,"FND:bridge","Q7","insufficient_evidence","Theo S_BRIDGE, tài xế có thỏa rule tại Tm không? Cần bằng chứng về fleet_region và ngoại lệ.",None,"L_NO_BRIDGE"),
 _c("C032",19,"FND:entity_resolution","Q7","ambiguous_request","Minh thuộc Depot nào tại Tm?",None),
 _c("C033",20,"FND:state","Q2","answerable","Trạng thái tài xế tại 2026-09-17T16:59:59.999999Z là gì theo thông tin được phép biết?","active","L0",A0),
 _c("C034",20,"FND:state","Q6","answerable","Trạng thái tài xế tại 2026-09-17T17:00:00Z là gì theo thông tin được phép biết?","suspended","L0",A0),
 _c("C035",21,"FND:event","Q7","insufficient_evidence","Terminal outcome của chuyến được cung cấp là gì?",None,"L0",A0),
 _c("C036",21,"FND:event","Q6","answerable","Terminal outcome của chuyến được cung cấp là gì?","completed"),
 _c("C037",22,"FND:state","Q2","answerable","Operating region của tài xế tại 2026-08-01T12:00:00Z là gì theo snapshot được yêu cầu?","HCM_OLD","L0","2026-08-04T00:00:00.000000Z"),
 _c("C038",22,"FND:state","Q6","answerable","Operating region của tài xế tại 2026-08-01T12:00:00Z là gì theo snapshot được yêu cầu?","HN","L0","2026-08-06T00:00:00.000000Z"),
 _c("C039",23,"FND:aggregate","Q3","answerable","cancel_rate_30d của tài xế tại Tm có trạng thái và giá trị nào theo definition được cấp?",{"metric_status":"undefined","value":None}),
 _c("C040",17,"FND:aggregate","Q7","insufficient_evidence","Tính chính xác cancel_rate_30d của tài xế tại Tm theo definition được cấp, kèm bằng chứng population và coverage.",None,"L_NO_COVERAGE"),
 _c("C041",24,"FND:policy_version","Q6","answerable","Tại 2026-09-14T17:00:00Z, phiên bản nào của policy tổng hợp S_VERSION có hiệu lực, và yêu cầu operating_region nào?",{"version":"v2","region":"HCM_OLD"},"L0",A0),
 _c("C042",25,"FND:bridge","Q4","answerable","Theo S_BRIDGE, tài xế có thỏa rule tại Tm không? Cần bằng chứng về fleet_region và ngoại lệ.",False),
]

ROOT_VARIANTS = {
 1:["L0"],2:["L0","L_NO_OPDAY","L_WRONG_DRIVER"],3:["L0"],4:["L0"],5:["L0"],6:["L0","L_CONFLICT","L_RETRACT"],
 7:["L0","L_WRONG_WINDOW"],8:["L0"],9:["L0"],10:["L0"],11:["L0"],12:["L0"],13:["L0"],14:["L0"],15:["L0"],16:["L0"],
 17:["L0","L_NO_COVERAGE"],18:["L0","L_NO_BRIDGE"],19:["L0"],20:["L0"],21:["L0"],22:["L0"],23:["L0"],24:["L0"],25:["L0"]}
