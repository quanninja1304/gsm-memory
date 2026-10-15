# Oracle KG của `gsm-dev-core-0.2.2`

## 1. Mục đích của tài liệu

Tài liệu này giải thích Oracle KG hiện tại theo cách dễ hiểu, bám sát frozen
dataset `gsm-dev-core-0.2.2`, đồng thời hướng dẫn kiểm tra và xem đồ thị trên
giao diện web của Neo4j Aura.

Oracle KG là hạ tầng kiểm tra chất lượng xây dựng đồ thị. Nó chưa phải đồ thị
phục vụ người dùng cuối, kho vector tài liệu hoặc bằng chứng rằng retrieval đã
hoạt động tốt.

## 2. Oracle KG hiện tại là gì?

Hiểu đơn giản:

> Oracle KG là đáp án chuẩn về cấu trúc đồ thị, được chuyển thẳng từ frozen
> dataset sang Neo4j mà không nhờ mô hình ngôn ngữ đoán.

Luồng tạo Oracle:

```text
Frozen public ledger 0.2.2
          ↓ chuyển đổi theo quy tắc cố định
Oracle KG trên Neo4j Aura
```

Oracle không dùng:

- OpenAI;
- Graphiti;
- mô hình embedding;
- Qdrant;
- suy diễn bằng LLM;
- private gold hoặc đáp án câu hỏi.

Mỗi khẳng định dữ liệu (`assertion`) trong frozen ledger được chuyển thành đúng
một quan hệ `ORACLE_FACT`. Oracle vì vậy trả lời câu hỏi:

> Nếu chuyển dữ liệu chuẩn sang đồ thị mà không có lỗi trích xuất, đồ thị đúng
> phải trông như thế nào?

Sau này, các đồ thị được đối chiếu với cùng Oracle:

```text
                       ┌─ Mode A
Oracle KG chuẩn ───────┼─ Graphiti Mode B
                       └─ Hệ thống đề xuất
```

Phép đối chiếu cho biết mỗi hệ thống:

- thiếu thực thể hoặc quan hệ nào;
- tạo thừa dữ liệu nào;
- nối sai chủ thể hoặc đối tượng nào;
- làm mất nguồn, thời gian hoặc lịch sử sửa đổi nào;
- có trộn dữ liệu giữa các snapshot hay không.

## 3. Oracle bám vào frozen dataset như thế nào?

Frozen dataset hiện có:

```text
8 tài xế
80 chuyến đã kết thúc
8 nhánh lịch sử
12 public snapshot
3.641 bản ghi khi tính theo snapshot
3.702 assertion khi tính theo snapshot
```

Một snapshot là ảnh chụp dữ liệu mà hệ thống được phép biết tại một thời điểm
và trên một nhánh lịch sử cụ thể.

Mười hai snapshot không có nghĩa là có 12 bộ tài xế khác nhau. Cùng một tài xế,
bản ghi hoặc assertion có thể xuất hiện trong nhiều snapshot nếu dữ liệu đó
được nhìn thấy ở các thời điểm tương ứng.

Oracle vật chất hóa từng snapshot riêng để tránh:

- nhìn thấy dữ liệu tương lai;
- trộn các nhánh lịch sử;
- dùng bản sửa chưa được công bố;
- lấy dữ liệu của snapshot khác;
- vô tình dùng trạng thái cuối cùng để trả lời câu hỏi lịch sử.

Định danh trong Neo4j vì vậy bao gồm cả `snapshot_id`. Danh tính nghiệp vụ gốc
vẫn được giữ trong `canonical_id`, `record_id` và `assertion_id`.

## 4. Oracle đang lưu những nút gì?

Oracle hiện có năm loại nút:

| Loại | Số lượng | Nội dung |
| --- | ---: | --- |
| `OracleSnapshot` | 12 | Mười hai ảnh chụp dữ liệu công khai |
| `OracleRecord` | 3.641 | Bản ghi được một nguồn công bố |
| `OracleAssertion` | 3.702 | Một phát biểu cụ thể trong bản ghi |
| `OracleEntity` | 2.495 | Tài xế, đội xe, khu vực, dịch vụ, sự cố, tài liệu và các thực thể công khai khác |
| `OracleValue` | 184 | Giá trị như `active`, `240000`, `97/20` |

`2.495 OracleEntity` không có nghĩa dataset có 2.495 tài xế. Con số này bao
gồm:

- cùng thực thể được vật chất hóa riêng trong nhiều snapshot;
- tài xế;
- đội xe;
- khu vực;
- dịch vụ;
- sự cố;
- tài liệu và phiên bản tài liệu;
- các thực thể công khai khác được ledger tham chiếu.

Danh tính nghiệp vụ thật nằm trong `canonical_id`. Khi muốn đếm số tài xế
nghiệp vụ, phải đếm `DISTINCT canonical_id`, không đếm tổng số node.

## 5. Oracle đang lưu những quan hệ gì?

Oracle có sáu loại quan hệ:

| Quan hệ | Số lượng | Ý nghĩa |
| --- | ---: | --- |
| `CONTAINS_RECORD` | 3.641 | Snapshot chứa record |
| `ASSERTS` | 3.702 | Record công bố assertion |
| `SUBJECT` | 3.702 | Chủ thể của assertion |
| `OBJECT` | 3.702 | Đối tượng của assertion |
| `ORACLE_FACT` | 3.702 | Quan hệ nghiệp vụ chuẩn |
| `TARGETS` | 48 | Record sửa hoặc thu hồi assertion cũ |

Ví dụ, phát biểu “tài xế An thuộc Depot 1” được lưu theo hai góc nhìn bổ sung
cho nhau:

```text
OracleSnapshot
   └─ CONTAINS_RECORD → OracleRecord
          └─ ASSERTS → OracleAssertion
                 ├─ SUBJECT → Tài xế An
                 └─ OBJECT  → Depot 1

Tài xế An
   └─ ORACLE_FACT {predicate: MEMBER_OF}
          → Depot 1
```

Nhánh thứ nhất giữ nguồn gốc và cấu trúc ledger. Nhánh thứ hai giúp xem và truy
vấn quan hệ nghiệp vụ thuận tiện.

Các quan hệ nghiệp vụ như:

```text
MEMBER_OF
OPERATES_IN
BASED_IN
TRIP_OUTCOME
DRIVER_STATUS
DRIVER_PROGRAM
REPORTED_MEASURE
HAS_INCIDENT
INCIDENT_STATUS
ARTIFACT_PUBLICATION
```

được lưu trong thuộc tính `predicate` của `ORACLE_FACT`.

## 6. Vì sao có các cụm rời và không nối vào tài xế?

Đồ thị không phải cây thư mục và tài xế không phải node gốc vật lý của toàn bộ
database.

Một số cụm không nối trực tiếp với tài xế là bình thường vì chúng có thể biểu
diễn:

- quy chế hoặc phiên bản tài liệu;
- bản công bố tài liệu;
- nguồn dữ liệu;
- khu vực hoặc dịch vụ dùng chung;
- coverage và tập nguồn;
- trạng thái hoặc giá trị;
- lịch sử sửa đổi và thu hồi.

Ngoài ra, 12 snapshot được cô lập có chủ ý. Khi hiển thị toàn bộ database,
cùng một thực thể nghiệp vụ có thể xuất hiện trong nhiều vùng tách biệt vì mỗi
vùng thuộc một snapshot khác nhau. Không nên mở toàn bộ 10.034 node cùng lúc để
đánh giá hình dạng của một snapshot.

Ảnh đồ thị cũ có hai loại node `Entity`, `Episodic` và hai quan hệ `MENTIONS`,
`RELATES_TO` là graph Graphiti Mode B trên instance cũ, không phải Oracle mới.
Graphiti dùng kiểu vật lý chung và đặt tên nghiệp vụ trong thuộc tính của cạnh.
Oracle mới tách rõ snapshot, record, assertion, subject, object và fact.

## 7. Node và edge có đang “hash” không?

Oracle có hash, nhưng hash chỉ dùng để:

- kiểm tra dữ liệu có bị thay đổi không;
- tạo định danh ổn định;
- phát hiện cùng khóa nhưng khác nội dung;
- bảo đảm chạy lại không âm thầm tạo dữ liệu khác.

Hash không phải embedding:

```text
SHA-256 / UUID
→ định danh và kiểm tra toàn vẹn

Embedding
→ vector số dùng để tìm kiếm theo ngữ nghĩa
```

Trạng thái Oracle hiện tại:

```text
Hash định danh/kiểm tra: Có
Embedding:               Không
Vector:                  Không
OpenAI:                  Không
```

Verifier đã xác nhận:

```text
vector_property_count = 0
provider calls         = 0
provider cost          = 0 USD
```

## 8. Dữ liệu chunk đang ở local hay Qdrant?

Phần tài liệu hiện có:

- 224 bài thật trong frozen release;
- chunk được dựng xác định;
- BM25 chạy local;
- chưa upsert dense vector lên Qdrant;
- chưa chốt mô hình embedding cho document retrieval.

Oracle KG trên Neo4j và kho vector tài liệu là hai phần khác nhau:

```text
Neo4j Oracle
→ lưu sự kiện, thực thể, lịch sử và quan hệ chuẩn

Qdrant
→ sau này lưu vector của các đoạn tài liệu/quy chế
```

Kiến trúc dự kiến:

```text
Câu hỏi
 ├─ Neo4j: lấy lịch sử và quan hệ của tài xế
 └─ BM25/Qdrant: lấy điều khoản quy chế
               ↓
          hợp nhất bằng chứng
```

Qdrant có thể chạy local hoặc Cloud. Hiện chưa có dữ liệu nào của dự án được
upsert lên Qdrant.

Các mô hình NVIDIA/Nemotron có thể được đưa vào danh sách thử nghiệm sau, nhưng
chưa nên chốt trước khi đo:

- chất lượng tiếng Việt;
- khả năng tìm đúng điều khoản trên tập dev;
- tốc độ;
- RAM;
- kích thước vector;
- chi phí và độ ổn định vận hành.

## 9. Có cần tài khoản để biết tài xế nào đang hỏi không?

Có. Ứng dụng thật cần ánh xạ:

```text
account_id → canonical driver_id
```

Luồng đúng:

```text
Tài xế đăng nhập
        ↓
Hệ thống tài khoản xác định driver_id
        ↓
Máy chủ tự gắn driver_id vào truy vấn
        ↓
Neo4j tìm đúng node tài xế trong đúng snapshot/phạm vi
```

Người dùng không nên phải nhập UUID tài xế.

Thông tin tài khoản và mật khẩu không nên lưu trong Oracle KG. Chúng nên nằm
trong PostgreSQL, hệ thống xác thực hoặc database ứng dụng hiện có. Neo4j chỉ
cần nhận `driver_id` chuẩn từ tầng ứng dụng.

Frozen dataset không có bảng tài khoản vì đây là dataset đánh giá retrieval,
không phải một ứng dụng đăng nhập hoàn chỉnh.

## 10. Người dùng có phải nhập tên quy chế không?

Không nên.

Trong 42 câu hỏi hiện tại, phiên bản quy chế được chỉ định có chủ ý để benchmark
biết chính xác tài liệu nào phải được dùng.

Trong ứng dụng thật:

```text
Người dùng hỏi tự nhiên
        ↓
BM25/Qdrant tìm quy chế liên quan
        ↓
Neo4j lấy dữ liệu tài xế
        ↓
Hệ thống kết hợp hai nguồn
```

Nếu người dùng nói rõ tên quy chế thì có thể dùng nó làm bộ lọc. Nếu không,
tầng tìm kiếm tài liệu phải tìm các tài liệu ứng viên phù hợp.

Dataset hiện chưa có lịch sử chuẩn tắc đầy đủ để tự quyết định “quy chế thực tế
đang có hiệu lực mới nhất” cho toàn bộ 224 bài. Không được suy diễn kết luận đó
từ một snapshot duy nhất.

## 11. Dữ liệu lịch sử là tự sinh hay thời gian thực?

Phần lịch sử tài xế hiện tại là dữ liệu tổng hợp được tạo xác định:

```text
8 tài xế
80 chuyến
reported measures
trạng thái
chương trình
sự cố
correction/retraction
8 nhánh ledger
12 snapshot
```

Dữ liệu này không được lấy trực tiếp từ hệ thống GSM thật. Nó được thiết kế để
kiểm tra:

- tìm đúng tài xế;
- tìm đúng thời gian;
- xử lý bản sửa;
- xử lý thu hồi;
- xử lý xung đột;
- không nhìn thấy dữ liệu tương lai;
- lấy đủ bằng chứng.

Ứng dụng production có thể cập nhật theo thời gian nhưng cần thêm đường ống:

```text
Hệ thống nguồn
    → sự kiện mới
    → chuẩn hóa thành record/assertion
    → ghi nối tiếp vào ledger
    → cập nhật KG
```

Prototype chưa kết nối hệ thống thời gian thực. Hiện chỉ có thể thử phát lại
tăng dần các record đã đóng băng.

## 12. Hướng dẫn xem Oracle KG trên Neo4j Aura Web

Neo4j Aura tích hợp công cụ duyệt và chạy Cypher dưới tên **Query**. Theo tài
liệu chính thức, có thể mở Query từ mục **Tools** ở thanh bên hoặc từ menu
**Connect** trên thẻ instance:

- [Neo4j Aura Console](https://console.neo4j.io/)
- [Hướng dẫn Query trong Aura](https://neo4j.com/docs/browser/deployment-modes/neo4j-aura/)
- [Hướng dẫn kết nối instance](https://neo4j.com/docs/aura/getting-started/connect-instance/)

### 12.1. Mở đúng instance

1. Đăng nhập Neo4j Aura Console.
2. Chọn project chứa instance, dự kiến có tên `gsm-memory-01`.
3. Trên thẻ instance, chọn **Connect → Query**; hoặc mở **Tools → Query**.
4. Trong thanh kết nối, chọn đúng instance.
5. Xác nhận trạng thái kết nối chuyển sang màu xanh và database là `neo4j`.

Tên `neo4j` là tên database bên trong, không phải tên hiển thị của instance.
Nếu cần xác nhận tuyệt đối, so sánh hostname trong `NEO4J_URI` với Connection
URI của instance trên Aura. Không gửi hoặc chụp `NEO4J_PASSWORD`.

### 12.2. Kiểm tra nhanh đúng Oracle instance

```cypher
MATCH (s:OracleSnapshot)
RETURN count(s) AS snapshots
```

Kết quả phải là:

```text
12
```

### 12.3. Kiểm tra số lượng từng loại node

```cypher
MATCH (n:OracleSnapshot)
RETURN 'OracleSnapshot' AS type, count(n) AS count
UNION ALL
MATCH (n:OracleRecord)
RETURN 'OracleRecord' AS type, count(n) AS count
UNION ALL
MATCH (n:OracleAssertion)
RETURN 'OracleAssertion' AS type, count(n) AS count
UNION ALL
MATCH (n:OracleEntity)
RETURN 'OracleEntity' AS type, count(n) AS count
UNION ALL
MATCH (n:OracleValue)
RETURN 'OracleValue' AS type, count(n) AS count
```

Kết quả mong đợi:

| type | count |
| --- | ---: |
| `OracleSnapshot` | 12 |
| `OracleRecord` | 3.641 |
| `OracleAssertion` | 3.702 |
| `OracleEntity` | 2.495 |
| `OracleValue` | 184 |

### 12.4. Kiểm tra số lượng quan hệ

```cypher
MATCH ()-[r]->()
WHERE type(r) IN [
  'CONTAINS_RECORD',
  'ASSERTS',
  'SUBJECT',
  'OBJECT',
  'TARGETS',
  'ORACLE_FACT'
]
RETURN type(r) AS type, count(r) AS count
ORDER BY type
```

Kết quả mong đợi:

| type | count |
| --- | ---: |
| `ASSERTS` | 3.702 |
| `CONTAINS_RECORD` | 3.641 |
| `OBJECT` | 3.702 |
| `ORACLE_FACT` | 3.702 |
| `SUBJECT` | 3.702 |
| `TARGETS` | 48 |

### 12.5. Kiểm tra trạng thái snapshot

```cypher
MATCH (s:OracleSnapshot)
RETURN s.state AS state, count(*) AS snapshots
```

Kết quả mong đợi:

```text
COMPLETE | 12
```

### 12.6. Kiểm tra assertion có bị nhân đôi không

```cypher
MATCH (a:OracleAssertion)
WITH a.snapshot_id AS snapshot_id,
     a.assertion_id AS assertion_id,
     count(*) AS occurrences
WHERE occurrences <> 1
RETURN snapshot_id, assertion_id, occurrences
```

Kết quả mong đợi là `No records`.

### 12.7. Xem các loại quan hệ nghiệp vụ

```cypher
MATCH ()-[r:ORACLE_FACT]->()
RETURN r.predicate AS quan_he, count(*) AS so_luong
ORDER BY so_luong DESC, quan_he
```

Nên xem dưới tab **Table** trước để hiểu phân bố, sau đó mới mở một nhóm nhỏ
dưới tab **Graph**.

### 12.8. Xác nhận dataset có tám tài xế nghiệp vụ

```cypher
MATCH (d:OracleEntity)
WHERE d.entity_type = 'DRIVER'
RETURN count(DISTINCT d.canonical_id) AS so_tai_xe
```

Kết quả mong đợi:

```text
8
```

Xem danh sách:

```cypher
MATCH (d:OracleEntity)
WHERE d.entity_type = 'DRIVER'
RETURN d.canonical_id AS driver_id,
       max(d.display_name) AS ten_hien_thi,
       count(DISTINCT d.snapshot_id) AS so_snapshot_xuat_hien
ORDER BY ten_hien_thi
```

### 12.9. Xem đồ thị một snapshot nhỏ

Không nên trả toàn bộ database. Dùng snapshot nhỏ để giao diện dễ đọc:

```cypher
MATCH (a:OracleEntity)-[r:ORACLE_FACT]->(b)
WHERE r.snapshot_id = 'd8c98a0b-7b07-50f2-b1ed-9fe102ccc5e6'
RETURN a, r, b
LIMIT 100
```

Chọn tab **Graph**, bấm vào node hoặc cạnh để xem thuộc tính. Với cạnh
`ORACLE_FACT`, thuộc tính quan trọng nhất là:

```text
predicate
assertion_id
record_id
source_id
known_at
valid_json
event_time
```

### 12.10. Xem nội dung quan hệ dưới dạng bảng

```cypher
MATCH (a:OracleEntity)-[r:ORACLE_FACT]->(b)
WHERE r.snapshot_id = 'd8c98a0b-7b07-50f2-b1ed-9fe102ccc5e6'
RETURN
  a.display_name AS chu_the,
  a.canonical_id AS ma_chu_the,
  r.predicate AS quan_he,
  coalesce(b.display_name, b.display_value, b.canonical_id) AS doi_tuong,
  r.assertion_id AS assertion_id,
  r.known_at AS known_at
ORDER BY quan_he, chu_the
LIMIT 200
```

### 12.11. Xem đầy đủ nguồn gốc của một assertion

```cypher
MATCH (s:OracleSnapshot)-[:CONTAINS_RECORD]->(r:OracleRecord)
      -[:ASSERTS]->(a:OracleAssertion)
MATCH (a)-[:SUBJECT]->(subject:OracleEntity)
MATCH (a)-[:OBJECT]->(object)
WHERE s.snapshot_id = 'd8c98a0b-7b07-50f2-b1ed-9fe102ccc5e6'
RETURN s.snapshot_id,
       r.record_id,
       r.source_id,
       r.operation,
       r.known_at,
       a.assertion_id,
       a.predicate,
       subject.display_name,
       subject.canonical_id,
       coalesce(object.display_name, object.display_value, object.canonical_id)
LIMIT 100
```

Truy vấn này cho thấy Oracle không chỉ giữ một cạnh rời rạc mà còn giữ đường
truy vết từ snapshot tới record, assertion, chủ thể và đối tượng.

## 13. Kết quả xác minh hiện tại

Lần nạp và lần xác minh độc lập trên Neo4j Aura đều đạt:

```text
Frozen inventory:       636/636 PASS
Oracle snapshots:       12/12 COMPLETE
Oracle records:         3.641
Oracle assertions:      3.702
Oracle facts:           3.702
Missing assertions:     0
Unexpected assertions:  0
Duplicate facts:        0
Wrong snapshot:         0
Vector properties:      0
Provider calls:         0
Provider cost:          0 USD
```

Báo cáo máy đọc được:

```text
runs/experiments/neo4j-oracle-ingestion.json
runs/experiments/neo4j-oracle-verification.json
```

## 14. Trạng thái hệ thống hiện tại

```text
Frozen dataset 0.2.2:         Hoàn thành
Oracle KG Neo4j:              Hoàn thành
12 snapshot Oracle:           Hoàn thành
Oracle embeddings:            Không có, đúng thiết kế
Graphiti Mode B mới:          Chưa nạp lại
Mode A so với Oracle:         Chưa đánh giá
Mode B so với Oracle:         Chưa đánh giá
Document chunks local:        Có
BM25 local:                   Có
Qdrant:                       Chưa triển khai
Dense embedding tài liệu:     Chưa chốt
Tài khoản → driver mapping:   Chưa triển khai
Cập nhật production realtime: Chưa triển khai
```

Oracle hiện tại là mốc chuẩn để đánh giá Graphiti và hệ thống đề xuất. Nó không
phải graph phục vụ trực tiếp người dùng cuối và cũng không phải kho vector tài
liệu.
