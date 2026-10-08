# Bàn giao GSM Operational KG v1

**Tên kỹ thuật:** `gsm-operational-kg-v1`

**Nền tảng:** Neo4j Aura

**Nguồn:** `data/gsm-dev-core-0.2.2/`

**Trạng thái:** đã nạp và xác minh đủ 12 snapshot

**Label nhận diện chung:** `GSMOperationalV1`

## 1. KG này lưu gì?

GSM Operational KG v1 lưu lịch sử vận hành tổng hợp của tài xế trong frozen dataset:

- tài xế thuộc đội xe/depot nào;
- depot nằm tại khu vực nào;
- tài xế hoạt động tại khu vực nào;
- tài xế thực hiện những chuyến nào;
- chuyến thuộc dịch vụ và khu vực nào;
- tài xế có sự cố nào;
- trạng thái của tài xế hoặc sự cố theo thời gian;
- các chỉ số được nguồn báo cáo theo từng kỳ.

Luồng dữ liệu:

```text
Frozen public snapshots 0.2.2
              ↓ phép chiếu xác định
GSM Operational KG v1 trên Neo4j
```

Đây là dữ liệu tổng hợp dùng cho nghiên cứu. Nó không phải dữ liệu vận hành GSM thật.

## 2. Nguồn đầu vào

Mỗi snapshot được dựng từ thư mục:

```text
data/gsm-dev-core-0.2.2/public/snapshots/<snapshot_id>/
```

Các tệp đầu vào:

| Tệp | Vai trò |
| --- | --- |
| `manifest.json` | Xác nhận dataset, snapshot và mốc dữ liệu được biết |
| `text_observations.jsonl` | Các record và assertion công khai |
| `source_registry.jsonl` | Danh sách nguồn và thứ hạng thẩm quyền |
| `entity_catalog.jsonl` | Danh sách thực thể và tên công khai |

Loader chỉ đọc các tệp công khai trên. Frozen release không bị chỉnh sửa trong quá trình
nạp.

## 3. Schema tổng quát

Mỗi node có hai label:

```text
(:GSMOperationalV1:<BusinessLabel>)
```

Ví dụ:

```text
(:GSMOperationalV1:Driver)
(:GSMOperationalV1:Trip)
```

Mọi node có tối thiểu:

| Trường | Ý nghĩa |
| --- | --- |
| `id` | Định danh ổn định dùng để upsert và nối cạnh |
| `name` | Tên ngắn để hiển thị |
| `description` | Mô tả node bằng ngôn ngữ dễ đọc |

Không dùng `elementId()` nội bộ của Neo4j làm định danh ứng dụng.

## 4. Các loại node

### 4.1. `Driver`

Đại diện cho một tài xế tổng hợp.

| Trường | Ý nghĩa |
| --- | --- |
| `id` | ID chuẩn của tài xế trong entity catalog |
| `name` | Tên tài xế tổng hợp |
| `description` | Mô tả đây là tài xế trong bộ benchmark |

Đội xe, khu vực và trạng thái không được ghi cố định trên Driver vì chúng có thể thay đổi
theo thời gian.

### 4.2. `Fleet`

Đại diện cho đội xe hoặc depot.

| Trường | Ý nghĩa |
| --- | --- |
| `id` | ID chuẩn của đội xe/depot |
| `name` | Tên đội xe/depot |
| `description` | Mô tả đơn vị vận hành |

### 4.3. `Region`

Đại diện cho khu vực hoạt động.

| Trường | Ý nghĩa |
| --- | --- |
| `id` | ID chuẩn của khu vực |
| `name` | Tên khu vực |
| `description` | Mô tả khu vực tổng hợp |

### 4.4. `Service`

Đại diện cho loại dịch vụ của chuyến.

| Trường | Ý nghĩa |
| --- | --- |
| `id` | ID chuẩn của dịch vụ |
| `name` | Tên loại dịch vụ |
| `description` | Mô tả loại dịch vụ |

### 4.5. `Trip`

Đại diện cho một chuyến terminal riêng biệt.

| Trường | Ý nghĩa |
| --- | --- |
| `id` | `trip_id` chuẩn từ dữ liệu chuyến |
| `name` | Nhãn ngắn của chuyến |
| `description` | Mô tả chuyến và kết quả |
| `event_time` | Thời điểm chuyến xảy ra |
| `outcome` | `completed` hoặc `cancelled` |
| `reason_code` | Mã lý do nếu nguồn có cung cấp |

### 4.6. `Incident`

Đại diện cho một sự cố của tài xế.

| Trường | Ý nghĩa |
| --- | --- |
| `id` | ID chuẩn của sự cố, giữ nguyên qua các lần cập nhật |
| `name` | Tên sự cố tổng hợp |
| `description` | Mô tả công khai của sự cố |

Trạng thái `open`, `resolved` hoặc `reopened` không ghi đè lên Incident mà được lưu bằng
`StateObservation`.

### 4.7. `Measurement`

Đại diện cho một chỉ số được nguồn báo cáo trong một kỳ xác định.

| Trường | Ý nghĩa |
| --- | --- |
| `id` | ID assertion nguồn |
| `name` | Tên chỉ số kèm cửa sổ thời gian |
| `description` | Mô tả chỉ số, tài xế và kỳ báo cáo |
| `definition_id` | Định nghĩa của chỉ số |
| `definition_version` | Phiên bản định nghĩa |
| `value` | Giá trị chính xác được báo cáo |
| `value_type` | Kiểu của giá trị |
| `unit` | Đơn vị nếu có |
| `window_start`, `window_end` | Cửa sổ `[start, end)` |
| `reported_status` | Trạng thái báo cáo |
| `undefined_reason` | Lý do không xác định nếu có |
| `calendar_id`, `timezone` | Lịch nghiệp vụ và múi giờ nếu áp dụng |

Một Measurement luôn mang ngữ cảnh của con số; không tồn tại node chỉ chứa một giá trị
rời rạc như `100` mà không biết đó là chỉ số gì.

### 4.8. `StateObservation`

Đại diện cho một quan sát trạng thái có thời gian.

| Trường | Ý nghĩa |
| --- | --- |
| `id` | ID assertion nguồn |
| `name` | Tên loại trạng thái và giá trị |
| `description` | Mô tả trạng thái của đối tượng |
| `state_kind` | `driver_status`, `driver_program` hoặc `incident_status` |
| `value` | Giá trị như `active`, `bike_partner`, `open` |

Thời gian hiệu lực của trạng thái nằm trên cạnh `HAS_STATE`.

## 5. Các loại cạnh

| Cạnh | Từ → Đến | Ý nghĩa |
| --- | --- | --- |
| `MEMBER_OF` | Driver → Fleet | Tài xế thuộc đội xe/depot |
| `BASED_IN` | Fleet → Region | Đội xe/depot đặt tại khu vực |
| `OPERATES_IN` | Driver → Region | Tài xế hoạt động chính tại khu vực |
| `USES_SERVICE` | Driver → Service | Tài xế sử dụng dịch vụ khi có public fact trực tiếp |
| `PERFORMED` | Driver → Trip | Tài xế thực hiện chuyến |
| `FOR_SERVICE` | Trip → Service | Chuyến thuộc loại dịch vụ |
| `IN_REGION` | Trip → Region | Chuyến diễn ra tại khu vực |
| `HAS_INCIDENT` | Driver → Incident | Sự cố thuộc tài xế |
| `HAS_MEASUREMENT` | Driver → Measurement | Chỉ số được báo cáo cho tài xế |
| `HAS_STATE` | Driver/Incident → StateObservation | Trạng thái của tài xế hoặc sự cố |

`USES_SERVICE` được schema hỗ trợ nhưng dữ liệu hiện tại không có public fact trực tiếp,
do đó số cạnh thực tế bằng 0.

## 6. Metadata trên cạnh

Mỗi cạnh chứa các trường phù hợp trong nhóm sau:

| Trường | Ý nghĩa |
| --- | --- |
| `snapshot_id` | Snapshot mà cạnh được phép xuất hiện |
| `evidence_ref` | ID assertion nguồn trong frozen public ledger |
| `event_time` | Thời điểm sự kiện xảy ra nếu có |
| `valid_kind` | Kiểu thời gian hiệu lực |
| `valid_at` | Thời điểm hiệu lực của point |
| `valid_from`, `valid_to` | Khoảng hiệu lực `[from, to)` |
| `known_from`, `known_to` | Khoảng thời gian hệ thống biết fact |
| `resolution_status` | `accepted`, `superseded` hoặc `unresolved_conflict` |
| `ingested_at` | Thời điểm kỹ thuật cạnh được ghi vào Neo4j |

Bốn khái niệm thời gian không được trộn lẫn:

```text
event time      thời điểm sự kiện xảy ra
valid time      thời gian fact có hiệu lực
known time      thời gian fact được hệ thống biết
ingestion time  thời gian kỹ thuật ghi vào Neo4j
```

Không dùng `ingested_at` để kết luận fact nào đúng hoặc mới nhất.

## 7. Các đường nghiệp vụ chính

### 7.1. Tổ chức và khu vực

```text
Driver ──MEMBER_OF──> Fleet ──BASED_IN──> Region

Driver ──OPERATES_IN──> Region
```

Đường đầu cho biết vị trí depot. Đường thứ hai cho biết khu vực hoạt động chính của tài
xế. Chúng có ý nghĩa khác nhau.

### 7.2. Chuyến đi

```text
Driver ──PERFORMED──> Trip ──FOR_SERVICE──> Service
                         └────IN_REGION────> Region
```

Một fact chuyến được chiếu thành một node Trip và ba cạnh trên.

### 7.3. Chỉ số

```text
Driver ──HAS_MEASUREMENT──> Measurement
```

### 7.4. Trạng thái tài xế

```text
Driver ──HAS_STATE──> StateObservation
```

### 7.5. Sự cố

```text
Driver ──HAS_INCIDENT──> Incident
Incident ──HAS_STATE──> StateObservation
```

## 8. Quy tắc snapshot

Dataset có 12 snapshot. Một snapshot là ảnh chụp dữ liệu công khai được phép biết tại một
mốc và nhánh lịch sử cụ thể.

Node nghiệp vụ được dùng chung giữa các snapshot. Cạnh mang `snapshot_id`, vì cùng một
fact có thể xuất hiện trong nhiều snapshot.

Mọi truy vấn phải nhận đúng snapshot từ yêu cầu runtime và lọc cạnh:

```cypher
MATCH (d:GSMOperationalV1:Driver {id: $driver_id})-[r:MEMBER_OF]->(f:Fleet)
WHERE r.snapshot_id = $snapshot_id
RETURN d, r, f;
```

Không lọc `snapshot_id` có thể làm trộn các nhánh lịch sử hoặc đọc dữ liệu ngoài phạm vi
được phép.

## 9. Dữ liệu đã nạp

### 9.1. Tổng số

| Chỉ số | Kết quả |
| --- | ---: |
| Snapshot | 12 |
| Node duy nhất | 125 |
| Cạnh theo snapshot | 2.997 |
| Missing | 0 |
| Mismatched | 0 |
| Unexpected | 0 |
| Kết quả xác minh | `PASS` |

### 9.2. Node

| Label | Số lượng |
| --- | ---: |
| Driver | 8 |
| Fleet | 4 |
| Region | 2 |
| Service | 1 |
| Trip | 80 |
| Incident | 1 |
| Measurement | 18 |
| StateObservation | 11 |

### 9.3. Cạnh

| Loại | Số lượng |
| --- | ---: |
| `PERFORMED` | 799 |
| `FOR_SERVICE` | 799 |
| `IN_REGION` | 799 |
| `HAS_MEASUREMENT` | 165 |
| `OPERATES_IN` | 130 |
| `HAS_STATE` | 126 |
| `MEMBER_OF` | 122 |
| `BASED_IN` | 47 |
| `HAS_INCIDENT` | 10 |
| `USES_SERVICE` | 0 |

Số cạnh lớn hơn số sự kiện duy nhất vì cạnh được tách theo 12 snapshot.

## 10. Idempotency

Node được upsert theo:

```text
(business label, id)
```

Cạnh được upsert theo:

```text
(relationship type, start node, end node, snapshot_id, evidence_ref)
```

Trước khi ghi, loader so sánh dữ liệu đang có với projection dự kiến:

- dữ liệu thiếu được tạo;
- dữ liệu giống được giữ nguyên;
- cùng khóa nhưng khác nội dung làm lệnh thất bại;
- cạnh thừa trong snapshot làm lệnh thất bại;
- không tự động ghi đè mismatch.

Kết quả chạy lại sau khi đã nạp đủ:

```text
created_nodes = 0
created_edges = 0
unchanged_edges = 2997
status = PASS
```

## 11. Cấu hình kết nối

Các biến sau nằm trong `.env` và không được commit:

```dotenv
NEO4J_OPERATIONAL_URI=
NEO4J_OPERATIONAL_USERNAME=
NEO4J_OPERATIONAL_PASSWORD=
NEO4J_OPERATIONAL_DATABASE=
```

Không ghi thông tin kết nối thật vào source code, report hoặc Git.

## 12. Lệnh vận hành

### 12.1. Nạp đủ 12 snapshot

```powershell
uv run --env-file .env --extra graphiti python -m gsm_memory.benchmark operational-ingest-all `
  --release data/gsm-dev-core-0.2.2 `
  --output runs/experiments/gsm-operational-v1-full-ingestion.json
```

### 12.2. Xác minh đủ 12 snapshot

```powershell
uv run --env-file .env --extra graphiti python -m gsm_memory.benchmark operational-verify-all `
  --release data/gsm-dev-core-0.2.2 `
  --output runs/experiments/gsm-operational-v1-full-verification.json
```

### 12.3. Nạp một snapshot

```powershell
uv run --env-file .env --extra graphiti python -m gsm_memory.benchmark operational-ingest `
  --release data/gsm-dev-core-0.2.2 `
  --snapshot-id <snapshot-id> `
  --output runs/experiments/gsm-operational-v1-snapshot-ingestion.json
```

### 12.4. Xác minh một snapshot

```powershell
uv run --env-file .env --extra graphiti python -m gsm_memory.benchmark operational-verify `
  --release data/gsm-dev-core-0.2.2 `
  --snapshot-id <snapshot-id> `
  --output runs/experiments/gsm-operational-v1-snapshot-verification.json
```

Lệnh xác minh chỉ đọc Neo4j và frozen input để so sánh; nó không sửa frozen release.

## 13. Cách xem trên Neo4j Aura

Mở đúng instance Operational KG trên Neo4j Aura, chọn Query hoặc Explore và chạy các câu
lệnh sau.

### 13.1. Đếm node theo loại

```cypher
MATCH (n:GSMOperationalV1)
UNWIND [label IN labels(n) WHERE label <> 'GSMOperationalV1'] AS node_type
RETURN node_type, count(*) AS count
ORDER BY node_type;
```

### 13.2. Đếm cạnh theo loại

```cypher
MATCH (:GSMOperationalV1)-[r]->(:GSMOperationalV1)
RETURN type(r) AS relationship_type, count(*) AS count
ORDER BY relationship_type;
```

### 13.3. Xem danh sách tài xế

```cypher
MATCH (d:GSMOperationalV1:Driver)
RETURN d.id AS id, d.name AS name, d.description AS description
ORDER BY name;
```

### 13.4. Lấy một snapshot ID có sẵn

```cypher
MATCH (:GSMOperationalV1)-[r]->(:GSMOperationalV1)
RETURN DISTINCT r.snapshot_id AS snapshot_id
ORDER BY snapshot_id;
```

### 13.5. Xem vùng lân cận của một tài xế trong một snapshot

```cypher
MATCH (d:GSMOperationalV1:Driver {id: $driver_id})-[r]->(n:GSMOperationalV1)
WHERE r.snapshot_id = $snapshot_id
RETURN d, r, n
LIMIT 100;
```

### 13.6. Xem Driver → Trip → Service/Region

```cypher
MATCH (d:GSMOperationalV1:Driver)-[p:PERFORMED]->(t:GSMOperationalV1:Trip)
WHERE p.snapshot_id = $snapshot_id
OPTIONAL MATCH (t)-[s:FOR_SERVICE]->(service:GSMOperationalV1:Service)
WHERE s.snapshot_id = $snapshot_id
OPTIONAL MATCH (t)-[g:IN_REGION]->(region:GSMOperationalV1:Region)
WHERE g.snapshot_id = $snapshot_id
RETURN d, p, t, s, service, g, region
LIMIT 50;
```

### 13.7. Xem chỉ số dưới dạng bảng

```cypher
MATCH (d:GSMOperationalV1:Driver)-[r:HAS_MEASUREMENT]->(m:GSMOperationalV1:Measurement)
WHERE r.snapshot_id = $snapshot_id
RETURN d.name AS driver,
       m.definition_id AS metric,
       m.value AS value,
       m.unit AS unit,
       m.window_start AS window_start,
       m.window_end AS window_end,
       r.resolution_status AS resolution
ORDER BY driver, window_start;
```

### 13.8. Xem sự cố và lịch sử trạng thái

```cypher
MATCH (d:GSMOperationalV1:Driver)-[i:HAS_INCIDENT]->(incident:GSMOperationalV1:Incident)
WHERE i.snapshot_id = $snapshot_id
OPTIONAL MATCH (incident)-[s:HAS_STATE]->(state:GSMOperationalV1:StateObservation)
WHERE s.snapshot_id = $snapshot_id
RETURN d, i, incident, s, state;
```

### 13.9. Kiểm tra cạnh thiếu thông tin nguồn

Kết quả đúng phải bằng 0:

```cypher
MATCH (:GSMOperationalV1)-[r]->(:GSMOperationalV1)
WHERE r.snapshot_id IS NULL OR r.evidence_ref IS NULL
RETURN count(r) AS invalid_edges;
```

## 14. Quy tắc truy vấn bắt buộc

1. Luôn bắt đầu từ node có label `GSMOperationalV1`.
2. Luôn lọc `r.snapshot_id` theo snapshot của yêu cầu.
3. Dùng thuộc tính `id`, không dùng Neo4j `elementId()`.
4. Khi câu hỏi có thời gian, kiểm tra `event_time`, valid time và known time đúng nghĩa.
5. Không dùng `ingested_at` làm thời gian nghiệp vụ.
6. Không tự chọn một phía khi `resolution_status = unresolved_conflict`.
7. Không coi thiếu cạnh là bằng chứng rằng một sự kiện không tồn tại.
8. Giữ `evidence_ref` trong kết quả/trace để có thể đối chiếu nguồn.
9. Không bỏ qua correction, retraction hoặc source authority bằng quy tắc “mới nhất thắng”.

## 15. Mã nguồn liên quan

| File | Trách nhiệm |
| --- | --- |
| `src/gsm_memory/adapters/neo4j_operational.py` | Dựng projection, upsert và xác minh KG |
| `src/gsm_memory/benchmark.py` | Cung cấp bốn lệnh CLI vận hành |
| `tests/unit/retrieval/test_neo4j_operational.py` | Kiểm tra schema, định danh và tổng projection |

Receipt của các lần chạy nằm dưới `runs/experiments/` và không chứa credential.

## 16. Trạng thái bàn giao

| Hạng mục | Trạng thái |
| --- | --- |
| Schema node và cạnh | Hoàn thành |
| Tên và mô tả dễ đọc trên node | Hoàn thành |
| Projection từ 12 snapshot | Hoàn thành |
| Nạp Neo4j Aura | Hoàn thành |
| Xác minh 125 node/2.997 cạnh | `PASS` |
| Xác minh missing/mismatch/unexpected | 0/0/0 |
| Chạy lại không nhân đôi dữ liệu | `PASS` |
| Truy vấn mẫu để kiểm tra trên Aura | Có |

GSM Operational KG v1 đã sẵn sàng để thành viên tiếp quản kết nối và phát triển lớp truy
vấn trên Neo4j.
