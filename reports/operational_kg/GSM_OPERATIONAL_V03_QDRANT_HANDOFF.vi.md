# Bàn giao Operational KG v0.3 và chỉ mục chính sách Qdrant

## 1. Phạm vi bàn giao

Tài liệu này mô tả phần triển khai mới nhất được giữ lại để tiếp tục xây luồng
tìm bằng chứng. Phạm vi gồm:

- Operational KG v0.3 trên Neo4j, có 12 ảnh chụp nối tiếp của timeline `L0`;
- các công cụ truy vấn thực thể, trạng thái, phạm vi và `cancel_rate_30d`;
- kế hoạch lập chỉ mục toàn bộ corpus chính sách `retrieval_full@1` trên Qdrant;
- tìm kiếm kết hợp dense và sparse bằng RRF trong Qdrant;
- ranh giới ánh xạ giữa Qdrant và Neo4j.

Phần này không sửa frozen release `gsm-dev-core-0.2.2`. Nó cũng chưa bao gồm
reader/agent, Jev, hợp nhất bằng chứng KG–Qdrant hoàn chỉnh hoặc đánh giá trên
held-out test set.

## 2. Quyết định kiến trúc đã chốt

| Thành phần | Trách nhiệm |
| --- | --- |
| Neo4j | Lưu node, cạnh, quan hệ nghiệp vụ, valid time, known time và khả năng nhìn thấy theo snapshot |
| Qdrant `policy_chunks` | Lưu dense/sparse vector của các đoạn thuộc toàn bộ 224 tài liệu chính sách chuẩn |
| Qdrant `operational_evidence` | Dự kiến lưu vector của `Complaint` và `Incident`; chưa triển khai/nạp |
| Mã nối hai kho | Dùng `document_id`, `clause_ids` hoặc `node_id`, không dùng vector làm danh tính nghiệp vụ |

Không lưu vector trực tiếp trong Neo4j. Module và cấu hình thử nghiệm cũ từng
ghi vector vào graph không thuộc bản bàn giao mới nhất và không được stage.

## 3. Luồng code hiện tại

```text
frozen gsm-dev-core-0.2.2
        |
        +--> operational_mock.py
        |      +--> candidate nodes.jsonl / edges.jsonl / snapshots.jsonl
        |      +--> kiểm tra ID, thời gian, provenance và tính tái lập
        |
        +--> neo4j_operational_v2.py
        |      +--> upsert namespace GSMOperationalV3Timeline
        |      +--> verify node/cạnh và kiểm tra idempotency
        |
        +--> operational_tools.py
        |      +--> entity resolution chính xác
        |      +--> lọc snapshot + valid time + known time
        |      +--> trạng thái Driver/Incident: resolved/conflict/missing
        |      +--> count/list có phân trang và cancel_rate_30d có coverage
        |
        +--> documents.py
               +--> dựng chunk công khai, xác định
               +--> qdrant_hybrid.py tạo point ID + payload lineage
               +--> qdrant_policy.py upsert/verify/search dense+sparse RRF
```

Các lệnh `operational-v2-*` được giữ tên để tương thích CLI cũ, nhưng mặc định
mới trỏ tới dataset `gsm-operational-mock-v0.3` và contract
`operational-kg-v3-r2.json`.

## 4. Operational KG v0.3

### 4.1. Dữ liệu và thời gian

- Dataset thử nghiệm: `gsm-operational-mock-v0.3`.
- Nguồn: frozen `gsm-dev-core-0.2.2`; không sửa byte của release.
- Namespace Neo4j: `GSMOperationalV3Timeline`.
- Một timeline vận hành duy nhất: `L0`.
- 12 snapshot theo thứ tự thời gian.
- Fact chỉ lưu một lần và mang `visibility_snapshot_ids`; không sao chép 12 đồ thị.
- Mọi truy vấn lịch sử phải đồng thời áp dụng snapshot, valid time và known time.
- Bảy nhánh lỗi frozen chỉ dùng cho đánh giá robustness, không trộn vào graph vận hành.

### 4.2. Quy mô đã được ghi nhận

| Hạng mục | Số lượng |
| --- | ---: |
| Node | 201 |
| Cạnh | 582 |
| Driver | 8 |
| Trip | 80 |
| Complaint | 11 |
| Incident | 5, gồm 4 incident tổng hợp và 1 incident từ frozen projection |
| Snapshot | 12 |

Logical digest đã ghi trong báo cáo triển khai mới nhất:

```text
5c51fec1b29fce60e30716aaaada21ef7f8ffc23421f64dba6bc3a3f774390f7
```

Nguồn bằng chứng chi tiết nằm tại
`reports/operational_kg/GSM_OPERATIONAL_KG_V3_V03_IMPLEMENTATION_REPORT.vi.md`.
Các file JSON sinh trong lúc chạy là run artifact, không phải source code và
không cần commit.

### 4.3. Các loại node

| Node | Số lượng | Ý nghĩa |
| --- | ---: | --- |
| `Driver` | 8 | Tài xế cần tra cứu lịch sử vận hành |
| `Trip` | 80 | Chuyến đã kết thúc, có thời gian và kết quả chuyến |
| `Complaint` | 11 | Phản ánh của khách hàng; nội dung chưa tự động được xem là kết luận vi phạm |
| `Incident` | 5 | Sự cố vận hành, gồm 4 tình huống tổng hợp và 1 sự cố chiếu từ frozen data |
| `Vehicle` | 8 | Phương tiện được gán cho tài xế trong bộ thử nghiệm |
| `VehicleType` | 2 | Loại phương tiện để nối phạm vi dịch vụ/chính sách |
| `MaintenanceEvent` | 8 | Sự kiện kiểm tra hoặc bảo dưỡng phương tiện |
| `Measurement` | 17 | Số liệu do nguồn báo cáo; không phải kết quả mà tool tự tính lại |
| `StateObservation` | 18 | Trạng thái có khoảng hiệu lực, như trạng thái tài xế, chương trình vận hành hoặc vòng đời incident |
| `Fleet` | 4 | Đội xe hoặc depot mà tài xế thuộc về theo thời gian |
| `Region` | 2 | Khu vực vận hành cấp lớn |
| `Zone` | 4 | Vùng đón/trả chi tiết nằm trong region |
| `Service` | 1 | Dịch vụ gắn với chuyến |
| `PolicyDocument` | 4 | Tài liệu nguồn của bốn chính sách đã được cấu trúc trong KG |
| `PolicyClause` | 13 | Điều khoản nguồn đã được rà soát và định danh |
| `PolicyRule` | 4 | Biểu diễn có cấu trúc của quy tắc được rút ra từ điều khoản đã rà soát |
| `PolicyAction` | 4 | Hành động nghiệp vụ mà quy tắc mô tả |
| `ViolationFinding` | 4 | Kết quả đối chiếu dữ liệu với một quy tắc; không thay thế bằng chứng nguồn |
| `EnforcementDecision` | 4 | Quyết định xử lý được dẫn từ finding và policy action |
| **Tổng** | **201** | Không có node Shift hoặc Summary |

### 4.4. Các loại cạnh

Operational KG v0.3 có tổng cộng **582 cạnh**. Bảng dưới đây mô tả toàn bộ loại
cạnh nghiệp vụ; nhiều cạnh cùng loại có thể tồn tại vì chúng nối các thực thể
khác nhau hoặc có khoảng valid/known time khác nhau.

| Cạnh | Từ → đến | Ý nghĩa |
| --- | --- | --- |
| `PERFORMED` | Driver → Trip | Tài xế thực hiện chuyến |
| `RECEIVED_COMPLAINT` | Driver → Complaint | Tài xế nhận một phản ánh |
| `ABOUT_TRIP` | Complaint/Incident → Trip | Phản ánh hoặc sự cố liên quan tới chuyến cụ thể |
| `HAS_INCIDENT` | Driver → Incident | Sự cố được ghi nhận trong lịch sử tài xế |
| `HAS_STATE` | Driver/Incident/Vehicle → StateObservation | Đối tượng có trạng thái trong một khoảng thời gian |
| `HAS_MEASUREMENT` | Driver/Vehicle → Measurement | Đối tượng có số liệu do nguồn báo cáo |
| `MEMBER_OF` | Driver → Fleet | Tài xế thuộc đội xe/depot theo thời gian |
| `OPERATES_IN` | Driver → Region | Khu vực vận hành của tài xế |
| `OPERATED` | Driver → Vehicle | Tài xế sử dụng phương tiện |
| `HAS_TYPE` | Vehicle → VehicleType | Phương tiện thuộc loại nào |
| `UNDERWENT` | Vehicle → MaintenanceEvent | Phương tiện có sự kiện bảo dưỡng/kiểm tra |
| `IN_REGION` | Trip → Region | Chuyến diễn ra trong region |
| `PICKUP_IN` | Trip → Zone | Vùng đón của chuyến |
| `DROPOFF_IN` | Trip → Zone | Vùng trả của chuyến |
| `FOR_SERVICE` | Trip → Service | Chuyến thuộc dịch vụ nào |
| `BASED_IN` | Fleet → Region | Đội xe/depot nằm trong region |
| `CONTAINS_ZONE` | Region → Zone | Region chứa zone |
| `CONTAINS` | PolicyDocument → PolicyClause | Tài liệu chứa điều khoản |
| `DEFINED_IN` | PolicyRule → PolicyClause | Quy tắc được cấu trúc từ điều khoản nguồn |
| `HAS_ACTION` | PolicyRule → PolicyAction | Quy tắc mô tả hành động nghiệp vụ |
| `APPLIES_TO` | PolicyRule → Fleet/Region/Service/VehicleType/Zone | Phạm vi áp dụng đã được điều khoản nguồn hỗ trợ |
| `HAS_FINDING` | Driver → ViolationFinding | Tài xế có kết quả đối chiếu quy tắc |
| `EVALUATED_AGAINST` | ViolationFinding → PolicyRule | Finding được tính theo quy tắc nào |
| `SUPPORTED_BY` | ViolationFinding → Complaint/Incident/Measurement/Trip | Bằng chứng công khai hỗ trợ finding |
| `RECEIVED_DECISION` | Driver → EnforcementDecision | Tài xế nhận quyết định xử lý |
| `BASED_ON` | EnforcementDecision → ViolationFinding | Quyết định dựa trên finding nào |
| `APPLIES_ACTION` | EnforcementDecision → PolicyAction | Quyết định áp dụng hành động nào |

## 5. Qdrant chính sách

### 5.1. Phạm vi corpus

Luồng persistent ingest luôn dùng `retrieval_full@1`:

- 224 tài liệu chính sách chuẩn;
- loại file tổng hợp trùng lặp;
- không giới hạn ở 4 `PolicyRule` đang được cấu trúc trong Neo4j;
- giữ `document_id`, revision, hash, offsets và `clause_ids` trong payload.

### 5.2. Chia đoạn hiện tại

Baseline hiện tại dùng cửa sổ 180 token, overlap 30 token và ID xác định từ
revision, span và cấu hình chunker. Đây là baseline tái lập được, chưa phải kết
luận chunking tối ưu. Bước đánh giá tiếp theo cần so sánh nó với chunk theo
heading/điều khoản, nhưng không được sửa văn bản frozen.

### 5.3. Tìm kiếm

Contract hiện tại cấu hình:

- dense: `intfloat/multilingual-e5-small`, 384 chiều;
- sparse: `qdrant/bm25`;
- hợp nhất dense/sparse: RRF native của Qdrant;
- collection: `gsm_policy_chunks_v2`.

Tên model hiện là baseline tạm thời, cần đánh giá tiếng Việt trước khi gọi là
model chính thức. Đổi model hoặc kích thước vector phải dùng collection/version
mới, không ghi đè im lặng collection cũ.

Code đã có plan, upsert, verify và search. Chưa có run artifact chứng minh toàn
bộ corpus đã được nạp thành công lên Qdrant Cloud, vì vậy trạng thái hiện tại là
`implemented_not_run`.

## 6. Embedding node vận hành

Ở MVP chỉ chuẩn bị text đầu vào cho:

| Node | Text dùng để embedding | Trạng thái |
| --- | --- | --- |
| Complaint | `description` đã viết thành tình huống cụ thể | Có dữ liệu; chưa upsert Qdrant |
| Incident | `description` của 4 incident tổng hợp cụ thể | Có dữ liệu; chưa upsert Qdrant |

`Driver`, `Trip`, `Vehicle`, `Fleet`, `Region`, `Zone`, `Measurement`,
`StateObservation`, UUID, hash và snapshot không embedding mặc định. Chúng được
tìm bằng ID, thuộc tính có cấu trúc và quan hệ Neo4j.

`MaintenanceEvent` và `EnforcementDecision` được hoãn khỏi collection MVP. Chỉ
đưa thêm khi có câu hỏi đánh giá chứng minh tìm kiếm ngữ nghĩa trên hai loại này
có giá trị.

## 7. Luồng retrieval mục tiêu

```text
Câu hỏi
   |
   +--> phân tích thực thể, thời gian, snapshot và ý định
   |
   +--> Qdrant policy: dense + sparse + RRF
   +--> Qdrant operational: Complaint/Incident (chưa triển khai)
   +--> Neo4j: lọc thực thể và duyệt quan hệ có giới hạn
   |
   +--> hợp nhất candidate theo loại bằng chứng
   +--> chọn bằng chứng nhưng không làm rơi entity/time/coverage/source premises
   +--> reader trả lời hoặc báo missing/conflict
```

Jev chưa được triển khai. Nếu thử, chỉ dùng như reranker tùy chọn trên một tập
candidate nhỏ sau retrieval, chạy shadow/ablation trước. Jev không thay thế
embedding, không tạo candidate và không được tự quyết định temporal conflict hay
proof completeness.

## 8. Trạng thái chức năng

| Hạng mục | Trạng thái |
| --- | --- |
| Operational candidate v0.3 | Đã triển khai |
| Neo4j timeline projection | Đã triển khai và đã có báo cáo PASS trước đó |
| Neo4j idempotency | Đã có báo cáo PASS trước đó |
| Công cụ temporal/state/coverage | Đã triển khai và có unit test |
| Qdrant policy point plan | Đã triển khai |
| Qdrant policy Cloud ingest | Chưa chạy/xác minh trong checkpoint này |
| Qdrant Complaint/Incident collection | Chưa triển khai |
| KG–Qdrant fusion end-to-end | Chưa triển khai |
| Jev reranking | Chưa triển khai |
| Held-out test | Không tồn tại; hiện chỉ có 42 dev/conformance query |

## 9. Những thay đổi chính của bản bàn giao này

| Phần | Trước đây | Bản hiện tại | Lý do |
| --- | --- | --- | --- |
| Timeline | Trộn các snapshot thời gian với nhánh lỗi | Chỉ dùng một timeline vận hành `L0` | Tránh đặt các “thế giới song song” vào cùng graph |
| Snapshot | Khó hiểu là bản sao hay mốc thời gian | 12 mốc nối tiếp; fact lưu một lần và mang `visibility_snapshot_ids` | Nhìn lại lịch sử mà không nhân bản toàn bộ graph |
| Namespace | Dùng namespace v3 thử nghiệm cũ | `GSMOperationalV3Timeline` | Tách bản timeline cuối khỏi các graph thử nghiệm trước |
| Lọc lịch sử | Chưa áp dụng nhất quán | Mọi truy vấn lịch sử lọc snapshot, valid time và known time | Không lấy fact tương lai hoặc fact chưa được biết |
| Incident | Trạng thái rời rạc | Có vòng đời `open → resolved → reopened` bằng khoảng thời gian không chồng nhau | Trả lời trạng thái sự cố tại một thời điểm |
| Trạng thái tài xế | `active` và `suspended` dễ bị hiểu là đồng thời | Mỗi trạng thái có khoảng hiệu lực rõ ràng | Loại bỏ cách đọc “hai trạng thái cùng lúc” |
| `driver_program` | Dễ nhầm với loại xe | Được mô tả là chương trình vận hành, tách khỏi `VehicleType` | Giữ đúng ý nghĩa nghiệp vụ |
| Complaint/Incident | Mô tả chung chung | Có tình huống cụ thể, gắn Trip và không tự kết luận lỗi | Đủ ngữ nghĩa để thử semantic retrieval |
| Shift/Summary | Có node dẫn xuất nhưng dữ liệu không đủ | Loại khỏi v0.3 | Không duy trì dữ liệu tổng hợp trùng với tool/database |
| Coverage | Caller có thể tự truyền cờ đầy đủ | Tool tự xác minh coverage artifact | Không biến thiếu dữ liệu thành giá trị 0 |
| Policy trong KG | Chỉ một cụm nhỏ dễ bị hiểu là toàn bộ corpus | KG chỉ giữ 4 policy đã cấu trúc; Qdrant dự kiến giữ đủ 224 tài liệu | Phân biệt graph có cấu trúc với tìm kiếm toàn văn |
| Embedding graph | Từng có thử nghiệm ghi vector vào Neo4j | Không lưu vector trong Neo4j | Tránh trùng dữ liệu và tách đúng trách nhiệm kho lưu trữ |
| Embedding vận hành | Từng cân nhắc thêm MaintenanceEvent | MVP chỉ chuẩn bị Complaint và Incident | Giảm nhiễu và giữ phạm vi tối thiểu |
| Qdrant policy | Chỉ có retrieval cục bộ | Đã có plan, upsert, verify và dense+sparse RRF cho `retrieval_full@1` | Chuẩn bị tìm kiếm toàn bộ corpus; Cloud ingest vẫn chưa chạy |

## 10. Lưu ý bàn giao

- Các con số 201 node và 582 cạnh thuộc candidate v0.3 mới nhất, không phải frozen release.
- Frozen `gsm-dev-core-0.2.2` vẫn bất biến.
- Qdrant policy mới ở trạng thái `implemented_not_run` trong checkpoint này.
- Collection Qdrant cho Complaint/Incident chưa được triển khai.
- Fusion KG–Qdrant và Jev chưa được triển khai.
- 42 câu hỏi hiện tại là dev/conformance; chưa có held-out test set.
- Không được diễn giải checkpoint này thành chất lượng production hoặc độ chính xác hệ thống hoàn chỉnh.
