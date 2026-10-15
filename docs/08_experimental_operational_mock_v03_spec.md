# Đặc tả GSM Operational Mock v0.3

Trạng thái: `EXPERIMENTAL`
Dataset: `gsm-operational-mock-v0.3`
Hợp đồng đồ thị: `gsm-operational-kg-v3-draft-2`
Nguồn nền: frozen `gsm-dev-core-0.2.2` ở chế độ chỉ đọc
Seed: `42`

## 1. Mục tiêu

V0.3 là bản sửa nội dung và khả năng truy vấn của Operational KG v3. Bản này
không sửa frozen dataset, không đổi ontology nghiệp vụ và không tạo embedding.
Quy mô là 201 node và 582 cạnh. Đồ thị vận hành chỉ dùng timeline chuẩn `L0`;
bảy nhánh lỗi của frozen release vẫn được giữ nguyên cho evaluation nhưng không
được trộn vào graph mà nhân viên truy vấn.

V0.2 được giữ làm checkpoint tái lập với digest:

```text
fee5c817cd3bff9dfeddb19579a485711166a54c2850ffeadfa25b911b0b7cae
```

## 2. Thay đổi nội dung

| Phần | V0.3 |
| --- | --- |
| Complaint | 11 tình huống cụ thể, mỗi tình huống nối đúng một Trip |
| Incident tổng hợp | 4 tình huống cụ thể, mỗi tình huống nối Driver, Trip và trạng thái |
| Vòng đời Incident | Lưu `open`, sau đó `resolved`, và `reopened` khi kịch bản có các chuyển trạng thái đó |
| Dấu hiệu dữ liệu tổng hợp | Chỉ lưu bằng `source_kind=synthetic_extension`; không chèn chữ “mock” hoặc “mô phỏng” vào nội dung nghiệp vụ |
| Trách nhiệm | Mô tả chỉ ghi nhận phản ánh/sự kiện, không tự kết luận lỗi |
| Trạng thái tài xế | Tên và mô tả nêu tài xế, giá trị, khoảng hiệu lực và thời điểm nguồn được biết |
| `driver_program` | Hiển thị là “chương trình vận hành”, không phải loại phương tiện |

Incident frozen duy nhất vẫn không được tự gắn Trip vì nguồn công khai không có
bằng chứng cho liên kết đó.

## 3. Mô hình thời gian

V0.3 giữ bốn ý nghĩa thời gian độc lập:

- `event_time`: sự kiện xảy ra khi nào;
- `valid_from`/`valid_to`: fact đúng trong khoảng nào;
- `known_from`/`known_to`: hệ thống được phép biết fact từ khi nào;
- `ingestion_time`: thời điểm logic cố định của lần dựng dữ liệu.

Mọi truy vấn lịch sử phải cung cấp cả `valid_at` và `known_at`, bỏ cạnh có
`resolution_status=superseded`, rồi mới áp dụng khoảng `[from, to)`. Timestamp
được chuẩn hóa về UTC và so sánh bằng kiểu `datetime` của Neo4j. Nếu hai nguồn
ngang quyền vẫn mâu thuẫn tại cùng cutoff, runtime không được tự chọn một giá trị.

V0.3 có 12 snapshot vận hành nối tiếp nhau trên cùng timeline `L0`. Đây là các
view tích lũy của một graph, không phải 12 bản sao và không phải 12 thế giới
song song. Node tham chiếu ổn định như Driver, Fleet, Region, Vehicle và Zone
luôn hiện trong mọi snapshot. Cấu trúc Policy chỉ hiện từ mốc nguồn tài liệu
được công bố (`2026-09-16T00:00:00Z`) để không rò dữ liệu tương lai. Trip,
Complaint, Incident,
Measurement, StateObservation, Finding và Decision chỉ xuất hiện từ lúc hệ
thống được phép biết chúng; khi đã xuất hiện thì vẫn được giữ để truy vấn lịch
sử. `valid_from`/`valid_to` và `known_from`/`known_to` tiếp tục quyết định fact
nào đang có hiệu lực tại thời điểm hỏi.

| STT | Snapshot ID | Cutoff UTC | Trip | Complaint | Incident | Ý nghĩa |
| ---: | --- | --- | ---: | ---: | ---: | --- |
| 1 | `a01883a7-d8be-55bb-a561-479a63adf9ee` | 2026-08-17 23:59:59 | 0 | 0 | 0 | Trước đợt chuyến thử nghiệm |
| 2 | `41d9cbe1-5ddd-5ca5-96ad-1b9c0929480a` | 2026-08-18 23:59:59 | 6 | 0 | 4 | Hết ngày 18/08 |
| 3 | `32cc841a-0440-5283-80d7-aebb77b935b3` | 2026-08-20 23:59:59 | 21 | 3 | 4 | Hết ngày 20/08 |
| 4 | `b768a6f4-6b45-5014-a87f-98d013e0ec5a` | 2026-08-22 23:59:59 | 35 | 5 | 4 | Hết ngày 22/08 |
| 5 | `7ad8774d-08fc-55a6-badb-2447ee6cab53` | 2026-08-24 23:59:59 | 49 | 7 | 4 | Hết ngày 24/08 |
| 6 | `fd133f31-6db4-5c7c-9791-c1301176dc3f` | 2026-08-26 23:59:59 | 63 | 9 | 4 | Hết ngày 26/08 |
| 7 | `a6037ae7-4642-55d9-a36a-88fca6875fdf` | 2026-08-28 23:59:59 | 73 | 10 | 4 | Hết ngày 28/08 |
| 8 | `002366a5-e09e-5214-9fe4-c7fffeaf1396` | 2026-08-31 23:59:59 | 80 | 11 | 4 | Đã nhận đủ chuyến và phản ánh tổng hợp |
| 9 | `081a61c0-56dd-5f43-88a4-f4dfb2894412` | 2026-09-01 23:59:59 | 80 | 11 | 5 | Frozen incident đã được công bố |
| 10 | `e64f47d9-1a09-5954-9ac6-a3e9770fa38a` | 2026-09-16 12:00:00 | 80 | 11 | 5 | Đã nhận báo cáo và tài liệu công khai |
| 11 | `96d00bc2-d39b-592b-b0d8-0ad4a5b80c30` | 2026-09-17 12:00:00 | 80 | 11 | 5 | Đã nhận các bản sửa trên L0 |
| 12 | `8b1426b6-2fad-5aba-b886-e16de44c18e7` | 2026-09-18 03:00:00 | 80 | 11 | 5 | Trạng thái Operational KG v3 hiện tại |

Các snapshot frozen thuộc `L_NO_OPDAY`, `L_WRONG_DRIVER`, `L_CONFLICT`,
`L_RETRACT`, `L_WRONG_WINDOW`, `L_NO_BRIDGE` và `L_NO_COVERAGE` không bị xóa.
Chúng tiếp tục phục vụ test/evaluation riêng, nhưng không phải lịch sử production
và không được đưa vào namespace Operational KG v3.

Trên Neo4j Aura, thay `snapshot_id` bằng một ID trong bảng trên:

```cypher
WITH "8b1426b6-2fad-5aba-b886-e16de44c18e7" AS snapshot_id
MATCH (n:GSMOperationalV3Timeline)
WHERE snapshot_id IN coalesce(n.visibility_snapshot_ids, [])
OPTIONAL MATCH (n)-[r]->(m:GSMOperationalV3Timeline)
WHERE snapshot_id IN coalesce(r.visibility_snapshot_ids, [])
  AND snapshot_id IN coalesce(m.visibility_snapshot_ids, [])
RETURN n, r, m
LIMIT 2000
```

Không dùng `MATCH (n)` để xem snapshot vì lệnh đó trộn mọi namespace và bỏ qua
allowlist thời gian.

Tool trạng thái trả một trong ba kết quả: `resolved`, `conflict`, `missing`.
Tool `cancel_rate_30d` tự đọc và kiểm tra coverage artifact trong snapshot đã
chọn; caller không còn truyền một boolean `coverage_complete`.

## 4. Những gì giữ nguyên

- Không tạo Shift vì chưa có thời gian mở/tắt ứng dụng.
- Giữ Measurement vì đây là số liệu do nguồn báo, không phải Summary do tool tính.
- Không tạo Driver/Fleet/Zone Summary.
- Không thêm Cause, Action, OperationsUnit hoặc System trong revision này.
- Không chọn hay chạy mô hình embedding trong revision này.
- Không sửa 42 câu hỏi, Oracle KG, Graphiti hoặc frozen release.

## 5. Điều kiện nghiệm thu

- 201 node và 582 cạnh;
- đủ 12 snapshot tăng dần trên cùng `L0`, không nhân bản toàn bộ graph;
- node/cạnh của snapshot sau bao hàm snapshot trước;
- hai candidate sạch có cùng logical digest;
- v0.2 vẫn tái lập đúng digest lịch sử;
- lần nạp Neo4j đầu khớp candidate;
- lần nạp thứ hai tạo 0 node và 0 cạnh;
- truy vấn nghiệp vụ đại diện PASS;
- không có thay đổi dưới `data/gsm-dev-core-0.2.2/`.
