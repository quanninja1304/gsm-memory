# Kế hoạch triển khai lưu đồ thị bền và trình xem đồ thị

| Thuộc tính | Giá trị |
| --- | --- |
| Kho mã nguồn | `memory/` |
| Bản dữ liệu | `gsm-dev-core-0.2.2` — đã đóng băng |
| Phạm vi | Phase B — truy xuất và xây dựng ngữ cảnh |
| Hệ đồ thị hiện tại | Graphiti `0.30.2` + Kùzu `0.11.3` |
| Chế độ đã chạy | Mode A, 12/12 ảnh chụp |
| Ngoài phạm vi | Chẩn đoán xe, Mode B, tác tử trả lời, giao diện sản phẩm |
| Mốc mã nguồn | `30eead44a6306783ad09880fe45fec34ac9679ff` |
| Ngày lập kế hoạch | 2026-09-22 |

---

## 1. Mục tiêu

Kế hoạch này hoàn thiện hai khả năng còn thiếu:

1. **Lưu đồ thị bền:** đồ thị Mode A sau khi dựng được lưu ngoài bản dữ liệu đóng băng, có thể mở lại và truy vấn mà không phải dựng lại.
2. **Trình xem đồ thị:** người phát triển có thể xem nút, cạnh, thời gian, nguồn và trạng thái bằng chứng của một câu hỏi bằng giao diện chỉ đọc.

Hai khả năng này phục vụ:

- tái lập thí nghiệm;
- giảm thời gian dựng lại đồ thị;
- dò lỗi truy xuất;
- kiểm tra cô lập ảnh chụp và dòng lịch sử;
- kiểm tra nguồn của từng cạnh;
- so sánh tập ứng viên với bằng chứng được chọn.

Chúng không thay đổi:

- nội dung `gsm-dev-core-0.2.2`;
- 42 câu hỏi;
- đáp án và hồ sơ chứng minh;
- ý nghĩa thời gian, nguồn hoặc xung đột;
- trạng thái các cổng BRG đang bị chặn bởi nhà cung cấp hoặc mô hình.

---

## 2. Hiện trạng

### 2.1. Đồ thị hiện được dựng như thế nào?

Mã hiện tại nằm tại:

```text
src/gsm_memory/adapters/graphiti.py
```

Hàm chính:

```python
construct_mode_a(snapshot_dir, database=":memory:", search_queries=None, search_limit=40)
```

Hàm này đang làm nhiều trách nhiệm cùng lúc:

1. đọc một ảnh chụp công khai;
2. mở Kùzu;
3. tạo nút, cạnh và tập sự kiện;
4. tạo chỉ mục;
5. kiểm tra ghi lặp không nhân bản dữ liệu;
6. chạy tìm kiếm cho các câu hỏi;
7. trả kết quả và đóng bộ điều khiển.

Trong luồng chạy đầy đủ, tham số `database` không được truyền nên mặc định là `:memory:`. Đồ thị biến mất khi tiến trình kết thúc.

### 2.2. Dữ liệu đầu vào

Mỗi ảnh chụp nằm tại:

```text
data/gsm-dev-core-0.2.2/public/snapshots/<snapshot_id>/
```

Mode A có 12 tệp đầu vào tại:

```text
data/gsm-dev-core-0.2.2/public/graph_inputs/mode_a/
```

Đầu vào chính của đồ thị gồm:

- `manifest.json` của ảnh chụp;
- `record_ledger.parquet`;
- thông tin nguồn và phạm vi nằm trong bản ghi;
- câu hỏi công khai được tuyến tới ảnh chụp đó.

### 2.3. Kết quả sinh ra hiện tại

Kết quả hiện chỉ được giữ trong báo cáo lần chạy:

- số nút;
- số cạnh;
- số tập sự kiện;
- liên kết từ nguồn sang đối tượng đồ thị;
- kết quả tìm kiếm;
- thời gian dựng;
- kiểm tra ghi lặp;
- kiểm tra sai phạm vi.

Thư mục:

```text
artifacts/graphs/
```

hiện chỉ có `README.md`, chưa có cơ sở dữ liệu đồ thị được lưu.

### 2.4. Giới hạn kỹ thuật cần xử lý

`KuzuDriver.close()` của phiên bản đang dùng không chủ động đóng kết nối mà dựa vào cơ chế thu gom bộ nhớ. Trên Windows, cách này có thể giữ khóa tệp sau khi hàm trả về.

Vì vậy không nên triển khai bằng cách đơn giản:

```python
construct_mode_a(snapshot, database="artifacts/graphs/foo")
```

rồi đổi tên hoặc di chuyển thư mục ngay trong cùng tiến trình.

Kế hoạch phải bảo đảm:

- tiến trình dựng kết thúc hoàn toàn;
- mọi tay cầm tệp đã được hệ điều hành giải phóng;
- đồ thị dở dang không bị coi là hoàn chỉnh;
- hai tiến trình không ghi đồng thời vào cùng một đích.

---

## 3. Nguyên tắc bắt buộc

### 3.1. Bản dữ liệu đóng băng chỉ đọc

Không ghi vào:

```text
data/gsm-dev-core-0.2/
data/gsm-dev-core-0.2.1/
data/gsm-dev-core-0.2.2/
```

Tất cả đồ thị và tệp xem phải nằm dưới:

```text
artifacts/graphs/
```

hoặc một đường dẫn đầu ra được truyền rõ ràng.

### 3.2. Chỉ dùng dữ liệu công khai

Tiến trình dựng, mở lại, tìm kiếm và xuất đồ thị không được đọc:

```text
private/oracle/
private/eval/
gold_answers.jsonl
proofs.jsonl
support_atoms.jsonl
support_links.jsonl
task_bindings.jsonl
```

Trình xem mặc định cũng chỉ được dùng dữ liệu công khai và báo cáo lần chạy công khai.

### 3.3. Mỗi ảnh chụp là một đồ thị độc lập

Không gộp 12 ảnh chụp vào một cơ sở dữ liệu dùng chung nếu việc đó cho phép truy vấn vượt qua ranh giới ảnh chụp.

Mỗi đồ thị phải gắn rõ:

```text
snapshot_id
ledger_id
scope_id
```

Không được dùng một bộ lọc sau truy vấn để sửa việc đã nạp nhầm dữ liệu từ ảnh chụp khác.

### 3.4. Đồ thị là kết quả có thể dựng lại

Nguồn chân lý vẫn là dữ liệu công khai đã đóng băng. Đồ thị chỉ là bản chiếu phục vụ truy xuất.

Không sửa trực tiếp cơ sở dữ liệu đồ thị. Khi đầu vào hoặc cấu hình thay đổi:

- tạo mã đồ thị mới;
- dựng thư mục mới;
- kiểm tra lại;
- không ghi đè đồ thị cũ.

### 3.5. Không phụ thuộc sâu vào Kùzu

Kùzu đã bị phía thượng nguồn ngừng duy trì và Graphiti thông báo sẽ bỏ hỗ trợ trong tương lai.

Vì vậy:

- phần nhận diện, tệp mô tả và tệp xuất phải độc lập với Kùzu;
- logic truy xuất không được phụ thuộc vào cấu trúc thư mục nội bộ của Kùzu;
- trình xem đọc định dạng JSON trung lập;
- việc chuyển sang Neo4j hoặc hệ khác sau này không làm đổi giao diện của trình xem.

---

## 4. Kiến trúc mục tiêu

```text
Bản dữ liệu công khai đã đóng băng
              |
              v
     Tính mã nhận diện đồ thị
              |
              v
   Dựng trong thư mục tạm bằng tiến trình con
              |
              v
      Mở lại và kiểm tra độc lập
              |
              v
   Ghi tệp mô tả + biên nhận + dấu READY
              |
              v
      Đổi tên nguyên tử sang thư mục chính
              |
       +------+------+
       |             |
       v             v
  Tìm kiếm lại   Xuất đồ thị trung lập
                       |
                       v
                Trình xem chỉ đọc
```

Luồng truy xuất đầy đủ sau thay đổi:

```text
Câu hỏi
  → xác định ảnh chụp
  → xác định mã đồ thị
  → kiểm tra đồ thị đã lưu
  → mở đồ thị ở chế độ đọc
  → tìm kiếm và lọc thời gian
  → hợp nhất với bằng chứng tài liệu
  → chọn bằng chứng
  → ghi báo cáo lần chạy
```

---

## 5. Phần 1 — Thiết kế lưu đồ thị bền

### 5.1. Cấu trúc thư mục

Đề xuất:

```text
artifacts/graphs/phase-b/
├── index.json
└── <graph_id>/
    ├── READY
    ├── manifest.json
    ├── database/
    ├── projection_links.jsonl
    ├── construction_receipt.json
    ├── verification.json
    └── public_export.json
```

Ý nghĩa:

| Tệp | Trách nhiệm |
| --- | --- |
| `READY` | Chỉ tồn tại khi mọi bước dựng và kiểm tra đã hoàn tất |
| `manifest.json` | Nhận diện đầu vào, cấu hình, phần mềm và đồ thị |
| `database/` | Dữ liệu Kùzu được lưu bền |
| `projection_links.jsonl` | Liên kết bản ghi/khẳng định công khai tới đối tượng đồ thị |
| `construction_receipt.json` | Số lượng, thời gian và trạng thái dựng |
| `verification.json` | Kết quả mở lại và kiểm tra độc lập |
| `public_export.json` | Bản xuất trung lập cho trình xem và kiểm tra |
| `index.json` | Danh mục đồ thị đã hoàn chỉnh dưới thư mục gốc |

`index.json` chỉ là danh mục tiện dụng. Từng `manifest.json` mới là nguồn nhận diện chính.

### 5.2. Mã nhận diện đồ thị

`graph_id` phải được tính xác định từ nội dung sau:

```text
phiên bản lược đồ tệp mô tả đồ thị
mã băm public/runtime_manifest.json
dataset_version
snapshot_id
ledger_id
scope_id
mã băm các tệp đầu vào công khai của ảnh chụp
chế độ đồ thị: A
cấu hình đồ thị
mã băm bộ chuyển đổi Graphiti
phiên bản Graphiti
loại và phiên bản hệ cơ sở dữ liệu
phiên bản bộ tạo véc-tơ dò đường hiện tại
```

Không đưa vào `graph_id`:

- thời gian chạy;
- đường dẫn tuyệt đối;
- tên máy;
- thứ tự duyệt thư mục;
- mã băm Python ngẫu nhiên;
- cấu hình chia đoạn tài liệu nếu đồ thị không phụ thuộc vào nó;
- đáp án hoặc bằng chứng nội bộ.

Điểm cần sửa so với hiện tại: `graph_namespace_key()` đang nhận mã cấu hình chia đoạn tài liệu. Nhận diện đồ thị nên tách khỏi nhận diện chỉ mục tài liệu. Báo cáo lần chạy sẽ tham chiếu đồng thời `graph_id` và mã chỉ mục tài liệu.

### 5.3. Nội dung `manifest.json`

Tối thiểu:

```json
{
  "schema_version": "persistent-graph-manifest-v1",
  "state": "READY",
  "graph_id": "...",
  "dataset_version": "gsm-dev-core-0.2.2",
  "release_public_digest": "...",
  "snapshot_id": "...",
  "ledger_id": "...",
  "scope_id": "...",
  "mode": "A",
  "input_files": [
    {"path": "...", "sha256": "..."}
  ],
  "adapter_sha256": "...",
  "graph_config": {},
  "graphiti_version": "0.30.2",
  "database_engine": "kuzu",
  "database_version": "0.11.3",
  "counts": {
    "records": 0,
    "nodes": 0,
    "edges": 0,
    "episodes": 0,
    "projection_links": 0
  },
  "logical_digest": "..."
}
```

Không đưa thời gian đo vào phần dùng để tính `logical_digest`.

### 5.4. Tách trách nhiệm trong mã nguồn

Hiện `construct_mode_a()` vừa dựng vừa tìm kiếm. Nên tách thành:

```python
build_mode_a_graph(...)
verify_mode_a_graph(...)
search_mode_a_graph(...)
export_mode_a_graph(...)
```

Giữ `construct_mode_a()` làm lớp bọc tương thích cho các bài kiểm tra và lệnh cũ trong giai đoạn chuyển đổi.

Trách nhiệm đề xuất:

#### `build_mode_a_graph()`

- chỉ đọc ảnh chụp công khai;
- tạo cơ sở dữ liệu;
- ghi nút, cạnh và tập sự kiện;
- ghi liên kết nguồn;
- kiểm tra ghi lặp;
- trả biên nhận dựng;
- không chạy 42 câu hỏi.

#### `verify_mode_a_graph()`

- mở lại cơ sở dữ liệu từ đĩa;
- kiểm tra mã ảnh chụp, phạm vi và dòng lịch sử;
- kiểm tra số nút/cạnh/tập sự kiện;
- kiểm tra thuộc tính nguồn và thời gian;
- kiểm tra liên kết nguồn;
- kiểm tra không có nhóm sai phạm vi;
- chạy một truy vấn dò xác định;
- không sửa đồ thị.

#### `search_mode_a_graph()`

- mở đúng đồ thị đã kiểm tra;
- chỉ tìm trong đúng nhóm của ảnh chụp;
- áp dụng điều kiện thực thể, thời gian có hiệu lực và thời gian được biết;
- trả cùng khuôn dạng ứng viên hiện tại;
- không đọc nội bộ;
- không sửa đồ thị.

#### `export_mode_a_graph()`

- xuất nút/cạnh sang khuôn dạng trung lập;
- giữ địa chỉ nguồn và thời gian;
- không xuất trường nội bộ;
- sắp xếp xác định;
- tạo mã băm nội dung logic.

### 5.5. Mô-đun mới đề xuất

```text
src/gsm_memory/retrieval/graph_store.py
src/gsm_memory/retrieval/graph_export.py
```

`graph_store.py` chịu trách nhiệm:

- kiểu dữ liệu tệp mô tả;
- tính `graph_id`;
- bố trí thư mục;
- kiểm tra tệp đầu vào;
- điều phối tiến trình con;
- kiểm tra `READY`;
- từ chối đồ thị sai nhận diện;
- lập danh mục đồ thị.

`graph_export.py` chịu trách nhiệm:

- mô hình nút/cạnh trung lập;
- xuất toàn đồ thị công khai;
- xuất đồ thị con theo câu hỏi;
- kiểm tra giới hạn số nút/cạnh;
- tạo JSON và HTML cho trình xem.

Không đưa logic nghiệp vụ thời gian vào hai mô-đun này; tiếp tục dùng bộ lọc đã kiểm tra trong bộ chuyển đổi Graphiti.

### 5.6. Dựng an toàn bằng tiến trình con

Quy trình:

1. Tiến trình chính tính `graph_id`.
2. Nếu thư mục đích có `READY`, kiểm tra và dùng lại.
3. Nếu thư mục đích tồn tại nhưng không có `READY`, báo lỗi rõ ràng; không dùng.
4. Tạo thư mục tạm cùng ổ đĩa:

   ```text
   artifacts/graphs/phase-b/.staging-<graph_id>-<random>/
   ```

5. Khởi chạy một tiến trình Python con để dựng Kùzu trong thư mục tạm.
6. Tiến trình con ghi cơ sở dữ liệu, liên kết nguồn và biên nhận rồi thoát.
7. Tiến trình chính mở lại đồ thị trong một tiến trình kiểm tra riêng.
8. Nếu kiểm tra đạt, ghi `verification.json`, `manifest.json`, sau cùng ghi `READY`.
9. Đổi tên thư mục tạm thành `<graph_id>` trên cùng ổ đĩa.
10. Nếu đích đã xuất hiện do tiến trình khác hoàn tất trước, kiểm tra đích; chỉ bỏ thư mục tạm sau khi xác nhận đích hợp lệ.

Không dùng lệnh xóa đệ quy với đường dẫn chưa xác minh. Mọi dọn dẹp chỉ được phép dưới `artifacts/graphs/phase-b/.staging-*` sau khi đường dẫn tuyệt đối đã được kiểm tra.

### 5.7. Chính sách dùng lại

Ba chế độ rõ ràng:

```text
memory          luôn dựng trong bộ nhớ như hiện tại
require         bắt buộc có đồ thị bền hợp lệ; thiếu thì lỗi
reuse-or-build  dùng lại nếu hợp lệ, nếu thiếu thì dựng mới
```

Không âm thầm dùng đồ thị có mã không khớp.

Đối với báo cáo chính thức, nên dùng `require` sau khi chạy bước dựng riêng. Điều này tách thời gian dựng khỏi thời gian truy xuất.

### 5.8. Lệnh dòng lệnh đề xuất

#### Dựng toàn bộ 12 đồ thị

```powershell
uv run --extra dev --extra graphiti python -m gsm_memory.benchmark materialize-graphs `
  --release data/gsm-dev-core-0.2.2 `
  --output-root artifacts/graphs/phase-b
```

#### Dựng một ảnh chụp để dò lỗi

```powershell
uv run --extra dev --extra graphiti python -m gsm_memory.benchmark materialize-graphs `
  --release data/gsm-dev-core-0.2.2 `
  --snapshot-id <snapshot-id> `
  --output-root artifacts/graphs/phase-b
```

#### Kiểm tra lại mà không dựng

```powershell
uv run --extra dev --extra graphiti python -m gsm_memory.benchmark verify-graphs `
  --release data/gsm-dev-core-0.2.2 `
  --graph-root artifacts/graphs/phase-b
```

#### Chạy truy xuất với đồ thị đã lưu

```powershell
uv run --extra dev --extra graphiti python -m gsm_memory.benchmark offline-closure `
  --release data/gsm-dev-core-0.2.2 `
  --profile retrieval_full `
  --graph-root artifacts/graphs/phase-b `
  --graph-policy require `
  --output runs/experiments/phase-b/persistent-graph-run.json
```

Tên lệnh và tùy chọn có thể điều chỉnh theo quy ước cuối cùng, nhưng trách nhiệm phải giữ như trên.

### 5.9. Kiểm tra tính đúng đắn khi mở lại

Mỗi đồ thị phải vượt các kiểm tra:

- `graph_id` khớp thư mục;
- mã băm đầu vào khớp bản dữ liệu hiện tại;
- `snapshot_id`, `ledger_id`, `scope_id` khớp;
- chỉ có đúng một nhóm đồ thị công khai;
- số bản ghi bằng số tập sự kiện;
- mọi khẳng định đã chiếu có cạnh tương ứng;
- mọi cạnh có `record_id`, `source_id`, thời gian và địa chỉ nguồn;
- số liên kết chiếu đúng;
- ghi lặp không làm tăng số nút/cạnh;
- truy vấn dò trả đối tượng truy nguyên được;
- không có dữ liệu từ ảnh chụp khác;
- không có đường dẫn hoặc nội dung nội bộ trong bản xuất.

### 5.10. Kết quả báo cáo

Tổng hợp sau khi dựng 12 đồ thị:

```json
{
  "status": "pass",
  "graph_count": 12,
  "verified_count": 12,
  "failed_count": 0,
  "graphs": [
    {
      "graph_id": "...",
      "snapshot_id": "...",
      "ledger_id": "...",
      "counts": {},
      "construction_ms": 0,
      "verification_status": "pass"
    }
  ]
}
```

Thời gian dựng là số đo của tiến trình dựng. Thời gian mở lại và tìm kiếm phải được báo riêng.

---

## 6. Phần 2 — Thiết kế trình xem đồ thị

### 6.1. Mục tiêu của bản đầu

Trình xem là công cụ dò lỗi, không phải giao diện sản phẩm.

Nó cần trả lời nhanh các câu hỏi:

- ảnh chụp này có những thực thể và quan hệ nào?
- cạnh này đến từ bản ghi và nguồn nào?
- cạnh có hiệu lực khi nào và được biết khi nào?
- câu hỏi đã tìm thấy những cạnh nào?
- cạnh nào bị loại và vì sao?
- bằng chứng nào được chọn?
- bước chọn đã làm mất bằng chứng cấu trúc nào?

### 6.2. Không đọc trực tiếp cấu trúc Kùzu

Trình xem chỉ đọc một tệp JSON trung lập. Điều này:

- tách giao diện khỏi hệ cơ sở dữ liệu;
- cho phép kiểm tra nội dung trước khi hiển thị;
- tránh mở cơ sở dữ liệu để ghi ngoài ý muốn;
- giúp lưu một đồ thị con cùng báo cáo lỗi;
- hỗ trợ đổi hệ cơ sở dữ liệu sau này.

### 6.3. Khuôn dạng `public_export.json`

```json
{
  "schema_version": "public-graph-export-v1",
  "graph_id": "...",
  "snapshot_id": "...",
  "ledger_id": "...",
  "scope_id": "...",
  "nodes": [
    {
      "id": "...",
      "label": "...",
      "kind": "entity|value",
      "source_count": 0
    }
  ],
  "edges": [
    {
      "id": "...",
      "source": "...",
      "target": "...",
      "predicate": "...",
      "fact": "...",
      "record_id": "...",
      "source_id": "...",
      "known_at": "...",
      "known_to": null,
      "valid": {},
      "operation": "assert|replace|retract",
      "source_refs": []
    }
  ]
}
```

Mọi mảng được sắp xếp xác định theo ID.

### 6.4. Khuôn dạng đồ thị con theo câu hỏi

Tệp dùng để dò một câu hỏi cần thêm:

```json
{
  "query": {
    "query_id": "...",
    "text": "...",
    "known_as_of": "...",
    "time_scope": {},
    "entity_refs": []
  },
  "display": {
    "max_nodes": 200,
    "max_edges": 400,
    "truncated": false
  },
  "nodes": [],
  "edges": [
    {
      "candidate_state": "raw|eligible|excluded|not_retrieved",
      "selected": true,
      "rank": 1,
      "score": 0.0,
      "exclusion_reason": null
    }
  ]
}
```

Thông tin `selected` và lý do loại được lấy từ báo cáo lần chạy công khai, không từ đáp án nội bộ.

### 6.5. Phạm vi đồ thị con

Không tải toàn bộ đồ thị nếu chỉ xem một câu hỏi.

Thứ tự chọn:

1. các cạnh xuất hiện trong tập ứng viên thô;
2. các cạnh đủ điều kiện;
3. các cạnh được chọn;
4. các cạnh bị loại có liên quan trực tiếp;
5. các cạnh lân cận tối đa hai bước nếu người dùng yêu cầu;
6. nút đầu và cuối của các cạnh trên.

Giới hạn mặc định:

```text
tối đa 200 nút
tối đa 400 cạnh
tối đa 2 bước mở rộng
```

Đây là giới hạn hiển thị, không thay đổi kết quả truy xuất. Nếu bị cắt, giao diện phải báo rõ.

### 6.6. Chức năng của trình xem bản đầu

#### Bắt buộc

- hiển thị nút và cạnh;
- kéo, phóng to và thu nhỏ;
- tìm theo ID hoặc nhãn;
- lọc theo loại quan hệ;
- lọc theo trạng thái ứng viên;
- lọc cạnh được chọn hoặc bị loại;
- bấm nút/cạnh để xem chi tiết;
- hiển thị nguồn, bản ghi, thời gian và lý do loại;
- hiển thị chú giải màu;
- báo khi đồ thị bị cắt do giới hạn;
- tải xuống JSON đang xem.

#### Nên có

- lọc theo thời gian có hiệu lực;
- lọc theo thời gian được biết;
- bật/tắt cạnh đã bị thay thế hoặc rút lại;
- tô màu theo nguồn;
- tô đậm đường mở rộng một hoặc hai bước;
- liên kết từ cạnh tới tệp/địa chỉ nguồn công khai.

#### Chưa làm

- chỉnh sửa nút/cạnh;
- chạy truy vấn tùy ý vào cơ sở dữ liệu;
- xem đáp án chuẩn;
- hiện vai trò bằng chứng nội bộ;
- đăng nhập và phân quyền nhiều người;
- truyền dữ liệu theo thời gian thực;
- giao diện sản phẩm cho người dùng cuối.

### 6.7. Màu sắc đề xuất

| Trạng thái | Màu |
| --- | --- |
| Cạnh được chọn | Xanh lá đậm |
| Ứng viên đủ điều kiện nhưng không được chọn | Xanh dương |
| Bị loại do thời gian | Cam |
| Bị loại do thực thể/phạm vi | Đỏ |
| Bị thay thế hoặc rút lại | Xám nét đứt |
| Chỉ là cạnh lân cận để giải thích | Xám nhạt |

Màu không được là cách duy nhất để phân biệt; cần nhãn hoặc biểu tượng để hỗ trợ người khó phân biệt màu.

### 6.8. Cách đóng gói trình xem

Bản đầu nên là một tệp HTML tự chứa:

```text
artifacts/graphs/phase-b/views/<query_id>.html
```

Ưu điểm:

- mở trực tiếp bằng trình duyệt;
- không cần máy chủ;
- không cần FastAPI hoặc Next.js;
- dễ đính kèm vào báo cáo lỗi;
- không thêm dịch vụ mới.

Mã tạo HTML nằm trong Python. Dữ liệu JSON được nhúng an toàn vào HTML sau khi thoát ký tự đặc biệt.

Nếu thư viện JavaScript bên ngoài được dùng:

- phải cố định phiên bản;
- lưu cục bộ để xem không cần mạng;
- ghi giấy phép;
- không tải từ mạng phân phối nội dung khi mở tệp.

Khuyến nghị bản đầu: dùng SVG/Canvas nhỏ hoặc một thư viện nhẹ được lưu cục bộ. Không dựng dự án Next.js chỉ cho công cụ dò lỗi này.

### 6.9. Lệnh xuất và xem đề xuất

#### Xuất đồ thị con theo câu hỏi

```powershell
uv run --extra dev --extra graphiti python -m gsm_memory.benchmark export-subgraph `
  --release data/gsm-dev-core-0.2.2 `
  --graph-root artifacts/graphs/phase-b `
  --runtime-report runs/experiments/phase-b/persistent-graph-run.json `
  --query-id <query-id> `
  --output artifacts/graphs/phase-b/views/<query-id>.json
```

#### Tạo HTML tự chứa

```powershell
uv run --extra dev python -m gsm_memory.benchmark render-graph-view `
  --input artifacts/graphs/phase-b/views/<query-id>.json `
  --output artifacts/graphs/phase-b/views/<query-id>.html
```

Không tự động mở trình duyệt trong bài kiểm tra hoặc môi trường tích hợp liên tục.

### 6.10. Chống rò dữ liệu nội bộ

Bộ xuất phải từ chối các trường hoặc đường dẫn có dấu hiệu nội bộ:

```text
private/
gold
proof
support_atom
support_link
expected_status
fault_label
scenario_id nội bộ
```

Kiểm tra không chỉ dựa vào tên tệp. Cần danh sách trường đầu ra đóng: trường không được khai báo phải bị loại hoặc làm lệnh thất bại.

Không tạo “chế độ nội bộ” trong bản đầu. Nếu sau này cần xem kết quả đánh giá, tạo một tệp lớp phủ riêng từ bộ đánh giá và không trộn vào bản xuất công khai.

---

## 7. Các giai đoạn triển khai

### Giai đoạn P0 — Khóa hợp đồng

Mục tiêu:

- chốt tệp mô tả đồ thị;
- chốt cách tính `graph_id`;
- chốt cấu trúc thư mục;
- chốt định dạng xuất công khai;
- chốt ba chính sách `memory`, `require`, `reuse-or-build`.

Tệp thay đổi dự kiến:

```text
configs/benchmark/phase-b-baseline.json
docs hoặc reports kế hoạch liên quan
tests/unit/retrieval/
```

Điều kiện hoàn thành:

- ví dụ JSON được kiểm bằng mô hình đóng;
- đường dẫn tuyệt đối không tham gia mã nhận diện;
- trường nội bộ không có trong định dạng xuất;
- quyết định rõ đồ thị không phụ thuộc cấu hình chia đoạn tài liệu.

### Giai đoạn P1 — Tách dựng và tìm kiếm

Mục tiêu:

- tách `construct_mode_a()` thành các trách nhiệm nhỏ;
- giữ tương thích với lệnh và bài kiểm tra cũ;
- cùng một đồ thị trong bộ nhớ cho kết quả như trước.

Tệp thay đổi dự kiến:

```text
src/gsm_memory/adapters/graphiti.py
tests/conformance/graphiti/
tests/unit/retrieval/
```

Điều kiện hoàn thành:

- Mode A hiện tại vẫn chạy 42/42;
- số nút/cạnh/tập sự kiện không đổi ngoài thay đổi đã giải thích;
- kết quả ứng viên logic không đổi;
- bài kiểm tra hiện có vẫn đạt.

### Giai đoạn P2 — Lưu một đồ thị bền

Mục tiêu:

- dựng một ảnh chụp vào thư mục tạm bằng tiến trình con;
- mở lại sau khi tiến trình con thoát;
- kiểm tra và công bố thư mục `READY`.

Tệp thay đổi dự kiến:

```text
src/gsm_memory/retrieval/graph_store.py
src/gsm_memory/benchmark.py
tests/unit/retrieval/test_graph_store.py
tests/integration/retrieval/test_persistent_graph.py
```

Điều kiện hoàn thành:

- xây và mở lại được trên Windows;
- không còn khóa tệp sau tiến trình con;
- đồ thị dở dang không được dùng;
- lần dựng thứ hai không ghi đè;
- tìm kiếm sau mở lại khớp logic với tìm kiếm trong bộ nhớ.

### Giai đoạn P3 — Dựng đủ 12 đồ thị

Mục tiêu:

- dựng tất cả ảnh chụp;
- tạo danh mục;
- kiểm tra 12/12;
- chạy 42 câu hỏi bằng chính đồ thị đã lưu.

Điều kiện hoàn thành:

- 12 đồ thị có mã khác nhau;
- 8 dòng lịch sử được nhận diện đúng;
- không ảnh chụp nào nhìn thấy dữ liệu ngoài phạm vi;
- 42/42 câu hỏi có kết quả cuối;
- kết quả logic khớp đường chạy trong bộ nhớ;
- thời gian dựng và thời gian dùng lại được báo riêng.

### Giai đoạn P4 — Bản xuất trung lập

Mục tiêu:

- xuất nút/cạnh công khai;
- xuất đồ thị con theo câu hỏi;
- giữ dấu vết nguồn và thời gian;
- giới hạn kích thước hiển thị.

Tệp thay đổi dự kiến:

```text
src/gsm_memory/retrieval/graph_export.py
src/gsm_memory/benchmark.py
tests/unit/retrieval/test_graph_export.py
tests/integration/retrieval/test_public_graph_export.py
```

Điều kiện hoàn thành:

- cùng đồ thị sinh cùng mã băm xuất;
- mọi cạnh xuất có hai đầu nút hợp lệ;
- không có trường nội bộ;
- mọi cạnh ứng viên truy nguyên được;
- giới hạn và trạng thái cắt được báo đúng.

### Giai đoạn P5 — Trình xem bản đầu

Mục tiêu:

- tạo HTML tự chứa;
- xem và lọc đồ thị con;
- xem chi tiết nguồn/thời gian/trạng thái ứng viên.

Tệp thay đổi dự kiến:

```text
src/gsm_memory/retrieval/graph_export.py
src/gsm_memory/retrieval/graph_view.py      # chỉ tạo nếu trách nhiệm đủ lớn
tests/unit/retrieval/test_graph_view.py
tests/integration/retrieval/test_graph_view_output.py
```

Điều kiện hoàn thành:

- mở được khi không có mạng;
- không cần máy chủ;
- không có dữ liệu nội bộ;
- nội dung văn bản được thoát an toàn;
- 200 nút/400 cạnh vẫn thao tác được trên máy hiện tại;
- giao diện chỉ đọc.

### Giai đoạn P6 — Đóng báo cáo và hồi quy

Mục tiêu:

- cập nhật tài liệu vận hành;
- chạy hai lần dựng độc lập;
- so sánh nội dung logic;
- ghi số đo và giới hạn;
- xác nhận bản dữ liệu đóng băng không đổi.

Điều kiện hoàn thành:

- toàn bộ bài kiểm tra liên quan đạt;
- hai lần dựng có cùng `graph_id`, số lượng và mã băm logic;
- báo cáo 12/12 đồ thị;
- báo cáo 42/42 truy vấn;
- kiểm tra bản đóng băng 636/636 đạt;
- khác biệt dưới các thư mục dữ liệu đóng băng rỗng.

---

## 8. Kế hoạch kiểm thử

### 8.1. Kiểm thử đơn vị

#### Nhận diện

- cùng đầu vào tạo cùng `graph_id`;
- đổi ảnh chụp tạo mã khác;
- đổi bộ chuyển đổi tạo mã khác;
- đổi phiên bản hệ cơ sở dữ liệu tạo mã khác;
- đổi đường dẫn tuyệt đối không làm đổi mã;
- đổi cấu hình tài liệu không làm đổi mã đồ thị;
- thứ tự tệp không làm đổi mã.

#### Tệp mô tả

- thiếu trường bắt buộc bị từ chối;
- trường lạ bị từ chối;
- trạng thái khác `READY` không được dùng;
- mã băm đầu vào sai bị từ chối;
- thư mục tên khác `graph_id` bị từ chối.

#### Đường dẫn và an toàn

- đầu ra phải nằm dưới thư mục được chỉ định;
- không chấp nhận `..` thoát thư mục;
- không dọn thư mục ngoài `.staging-*`;
- không ghi đè thư mục hoàn chỉnh;
- thư mục dở dang không được coi là bộ nhớ đệm hợp lệ.

#### Bản xuất

- nút/cạnh được sắp xếp xác định;
- mọi cạnh tham chiếu nút tồn tại;
- không có trường nội bộ;
- văn bản chứa `</script>` không phá HTML;
- giới hạn nút/cạnh hoạt động đúng;
- trạng thái cắt được ghi rõ.

### 8.2. Kiểm thử tích hợp

- dựng một ảnh chụp vào đĩa;
- tiến trình kết thúc rồi mở lại thành công;
- tìm kiếm khớp đường chạy trong bộ nhớ;
- ghi lặp không tăng số đối tượng;
- thiếu tệp cơ sở dữ liệu làm kiểm tra thất bại;
- sửa một byte tệp mô tả làm kiểm tra thất bại;
- xóa `READY` làm kiểm tra thất bại;
- tệp đầu vào thay đổi làm mã nhận diện không khớp;
- chạy khi không có thư mục `private` vẫn thành công;
- không có đường dẫn `private` trong bản xuất;
- hai đồ thị từ hai ảnh chụp không trả chéo dữ liệu.

### 8.3. Kiểm thử đầy đủ

- dựng 12/12 ảnh chụp;
- kiểm tra 12/12;
- chạy 42/42 câu hỏi với chính sách `require`;
- so sánh với đường chạy `memory`;
- chạy hai lần độc lập;
- so sánh mã băm logic;
- tạo HTML cho ít nhất các trường hợp:
  - có thể trả lời;
  - không đủ bằng chứng;
  - xung đột;
  - rút lại;
  - thiếu độ đầy đủ;
  - mất bằng chứng sau bước chọn.

### 8.4. Lệnh kiểm tra dự kiến

```powershell
uv run --extra dev pytest -q tests/unit/retrieval

uv run --extra dev --extra graphiti pytest -q `
  tests/conformance/graphiti `
  tests/integration/retrieval

uv run --extra dev python -m gsm_memory.data.cli verify-frozen `
  --release data/gsm-dev-core-0.2.2 `
  --certificate reports/data_freeze/gsm-dev-core-0.2.2-freeze-certificate.json `
  --comparison reports/data_freeze/gsm-dev-core-0.2.2-logical-comparison.json

git diff --name-only -- `
  data/gsm-dev-core-0.2 `
  data/gsm-dev-core-0.2.1 `
  data/gsm-dev-core-0.2.2
```

Lệnh cuối bắt buộc không có kết quả.

---

## 9. Số đo cần báo cáo

### Dựng đồ thị

- số ảnh chụp;
- số đồ thị đạt/thất bại;
- số bản ghi, nút, cạnh và tập sự kiện;
- số liên kết nguồn;
- thời gian dựng trung vị và phân vị 95;
- kích thước trên đĩa;
- trạng thái ghi lặp;
- trạng thái mở lại;
- trạng thái dùng lại.

### Truy xuất từ đồ thị đã lưu

- thời gian mở cơ sở dữ liệu;
- thời gian tìm kiếm theo câu hỏi;
- số ứng viên thô, đủ điều kiện và bị loại;
- tỷ lệ đúng ảnh chụp/phạm vi/thời gian;
- kết quả so với đường chạy trong bộ nhớ;
- trạng thái lạnh hoặc đã mở sẵn.

### Trình xem

- số nút/cạnh đã xuất;
- có bị cắt hay không;
- kích thước JSON và HTML;
- thời gian tạo tệp;
- mở được khi không có mạng;
- số trường nội bộ phát hiện được: phải bằng 0.

Không gộp thời gian dựng đồ thị vào thời gian truy xuất nếu báo cáo đã dùng đồ thị lưu bền. Hai con số phải đứng riêng.

---

## 10. Rủi ro và cách giảm thiểu

| Rủi ro | Cách xử lý |
| --- | --- |
| Kùzu giữ khóa tệp trên Windows | Dựng và kiểm tra bằng tiến trình con, chỉ đổi tên sau khi tiến trình thoát |
| Kùzu không còn được duy trì | Bản xuất trung lập, tách lớp lưu, không để trình xem phụ thuộc Kùzu |
| Dùng nhầm đồ thị cũ | Mã nhận diện theo nội dung và phiên bản, chính sách `require` kiểm tra chặt |
| Đồ thị dở dang bị dùng | Dựng trong thư mục tạm, `READY` được ghi cuối cùng |
| Hai tiến trình dựng cùng lúc | Thư mục tạm riêng; đích theo nội dung; khi va chạm phải kiểm tra đích |
| Trộn ảnh chụp hoặc dòng lịch sử | Một đồ thị cho một ảnh chụp; mã và kiểm tra phạm vi bắt buộc |
| Rò dữ liệu nội bộ | Chỉ đọc public; định dạng xuất là danh sách trường đóng; kiểm thử khi không có private |
| HTML bị chèn mã | Thoát ký tự và nhúng JSON an toàn; không dùng nội dung làm HTML trực tiếp |
| Đồ thị quá lớn làm treo trình duyệt | Xuất theo câu hỏi, giới hạn nút/cạnh, báo rõ khi cắt |
| Người dùng tưởng đồ thị là nguồn chân lý | Giao diện ghi rõ đây là bản chiếu có thể dựng lại |
| Công việc giao diện làm lệch ưu tiên | Trình xem tối thiểu, không làm sản phẩm đầy đủ trước khi bộ chọn bằng chứng ổn định |

---

## 11. Thứ tự ưu tiên

Kế hoạch này không thay đổi ưu tiên chung của Phase B.

Thứ tự đề xuất:

```text
1. Giữ ổn định và cải thiện bộ chọn bằng chứng
2. Khóa hợp đồng nhận diện đồ thị
3. Tách dựng khỏi tìm kiếm
4. Lưu một đồ thị và mở lại
5. Dựng đủ 12 đồ thị
6. Xuất JSON trung lập
7. Tạo trình xem HTML tối thiểu
8. Đóng báo cáo và hồi quy
```

Có thể thực hiện bước 2–5 song song ở mức thiết kế với việc cải thiện bộ chọn, nhưng không để việc làm giao diện trì hoãn nút thắt 15 trường hợp mất bằng chứng.

---

## 12. Tệp dự kiến thay đổi

### Mã nguồn

```text
src/gsm_memory/adapters/graphiti.py
src/gsm_memory/retrieval/graph_store.py          # mới
src/gsm_memory/retrieval/graph_export.py         # mới
src/gsm_memory/retrieval/graph_view.py           # có thể mới
src/gsm_memory/retrieval/offline.py
src/gsm_memory/benchmark.py
```

### Cấu hình

```text
configs/benchmark/phase-b-baseline.json
```

### Kiểm thử

```text
tests/unit/retrieval/test_graph_store.py          # mới
tests/unit/retrieval/test_graph_export.py         # mới
tests/unit/retrieval/test_graph_view.py           # có thể mới
tests/conformance/graphiti/
tests/integration/retrieval/test_persistent_graph.py   # mới
tests/integration/retrieval/test_public_graph_export.py # mới
```

### Tài liệu

```text
artifacts/graphs/README.md
reports/benchmark_readiness/
README.md                                         # chỉ cập nhật trạng thái sau khi có bằng chứng
```

### Kết quả sinh ra, không đưa vào Git

```text
artifacts/graphs/phase-b/
runs/experiments/phase-b/
```

Không sửa bất kỳ tệp nào dưới `data/gsm-dev-core-0.2.2/`.

---

## 13. Tiêu chí hoàn thành

### Lưu đồ thị bền

- [ ] Có mã nhận diện đồ thị ổn định và không phụ thuộc đường dẫn máy.
- [ ] Mỗi ảnh chụp có đồ thị riêng.
- [ ] Dựng qua thư mục tạm và tiến trình con.
- [ ] Mở lại được sau khi tiến trình dựng kết thúc.
- [ ] Đồ thị dở dang không bao giờ được dùng.
- [ ] Không ghi đè đồ thị hoàn chỉnh.
- [ ] Liên kết nguồn đầy đủ.
- [ ] Kiểm tra sai ảnh chụp/phạm vi/thời gian đạt.
- [ ] Đường chạy dùng lại cho kết quả logic như đường chạy trong bộ nhớ.
- [ ] 12/12 đồ thị được dựng và kiểm tra.
- [ ] Hai lần dựng độc lập có cùng mã băm logic.

### Trình xem đồ thị

- [ ] Đọc định dạng JSON trung lập, không đọc trực tiếp Kùzu.
- [ ] Tạo được đồ thị con theo `query_id`.
- [ ] Hiển thị nút, cạnh, nguồn và thời gian.
- [ ] Phân biệt ứng viên thô, đủ điều kiện, bị loại và được chọn.
- [ ] Hiển thị lý do loại.
- [ ] Có tìm kiếm và bộ lọc cơ bản.
- [ ] Báo rõ khi đồ thị bị cắt.
- [ ] Mở được không cần mạng và máy chủ.
- [ ] Chỉ đọc, không chỉnh sửa đồ thị.
- [ ] Không chứa dữ liệu nội bộ.
- [ ] Nội dung được thoát an toàn.

### Toàn bộ thay đổi

- [ ] 42/42 truy vấn có kết quả cuối.
- [ ] Các bài kiểm tra truy xuất hiện có không bị hỏng.
- [ ] Báo cáo thời gian dựng và truy xuất tách biệt.
- [ ] Không tuyên bố Mode B hoặc toàn bộ BRG đã đạt.
- [ ] Bộ kiểm tra bản đóng băng vẫn đạt 636/636.
- [ ] Khác biệt trong ba bản dữ liệu đóng băng rỗng.

---

## 14. Những việc cố ý không làm

- không thêm miền chẩn đoán xe;
- không thay đổi lược đồ nghiệp vụ;
- không xây giao diện người dùng cuối;
- không đưa đáp án chuẩn vào trình xem công khai;
- không cho phép chỉnh sửa đồ thị;
- không tạo công cụ truy vấn Cypher tùy ý;
- không di chuyển sang Neo4j trong cùng thay đổi;
- không chạy Mode B;
- không thêm bộ đọc hoặc tác tử;
- không sửa điểm số bằng cách thay đáp án;
- không đưa thư mục đồ thị sinh ra vào Git.

---

## 15. Mốc bàn giao đề xuất

| Mốc | Kết quả chính | Bằng chứng |
| --- | --- | --- |
| M1 | Hợp đồng nhận diện và tệp mô tả | Bài kiểm tra đơn vị |
| M2 | Một đồ thị lưu bền và mở lại | Biên nhận + kiểm tra tích hợp Windows |
| M3 | 12 đồ thị Mode A | Báo cáo 12/12 |
| M4 | 42 câu hỏi dùng đồ thị đã lưu | So sánh logic với chế độ bộ nhớ |
| M5 | Xuất đồ thị con công khai | JSON xác định, không rò nội bộ |
| M6 | Trình xem HTML tối thiểu | Mẫu cho các nhóm lỗi chính |
| M7 | Đóng hồi quy | Kiểm thử, hai lần dựng, frozen verifier |

Không gộp M2–M6 thành một thay đổi lớn. Mỗi mốc nên có kiểm thử và báo cáo riêng để dễ tìm nguyên nhân nếu có sai lệch.

---

## 16. Kết luận

Nên thực hiện cả hai phần, nhưng theo thứ tự:

```text
lưu đồ thị bền có kiểm chứng
→ xuất đồ thị trung lập
→ trình xem chỉ đọc tối thiểu
```

Giải pháp không nên chỉ thay `:memory:` bằng một đường dẫn. Cần nhận diện theo nội dung, dựng an toàn qua tiến trình con, kiểm tra sau khi mở lại, tách từng ảnh chụp và giữ liên kết nguồn.

Trình xem không nên là một ứng dụng web lớn. Bản đầu chỉ cần HTML tự chứa, đọc JSON công khai, cho phép xem nguồn/thời gian/trạng thái ứng viên và không có khả năng sửa dữ liệu.

Khi hoàn thành, repository sẽ có:

- đồ thị Mode A có thể mở lại;
- lần chạy truy xuất không phải dựng lại đồ thị;
- báo cáo dựng và dùng lại rõ ràng;
- công cụ xem một câu hỏi đã đi qua đồ thị như thế nào;
- nền tảng ít phụ thuộc vào Kùzu hơn nhờ định dạng xuất trung lập;
- không thay đổi bản dữ liệu đóng băng hoặc phạm vi nghiệp vụ hiện tại.
