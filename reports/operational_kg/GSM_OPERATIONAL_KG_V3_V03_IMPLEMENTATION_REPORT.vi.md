# Báo cáo triển khai GSM Operational KG v3 — mock v0.3

## Kết quả

Operational KG v3 đã được cập nhật để truy vấn đúng theo thời gian và 12
snapshot nối tiếp trên cùng timeline `L0` mà không nhân bản toàn bộ đồ thị.
Bảy nhánh lỗi của frozen release không còn bị trộn vào graph vận hành.

| Hạng mục | Kết quả | Chú thích |
| --- | --- | --- |
| Candidate A | PASS | Dựng mới từ frozen 0.2.2 và L0 |
| Candidate B | PASS | Dựng độc lập lần hai |
| So sánh logic | PASS | Không có mismatch |
| Logical digest | `5c51fec1b29fce60e30716aaaada21ef7f8ffc23421f64dba6bc3a3f774390f7` | Hai candidate giống nhau |
| Neo4j V3 Timeline | PASS | 201 node, 582 cạnh trong namespace `GSMOperationalV3Timeline` |
| Nạp lần hai | PASS | Tạo thêm 0 node, 0 cạnh |
| Smoke nghiệp vụ | PASS | 6/6 nhóm truy vấn |
| Snapshot | PASS | 12 mốc thời gian tăng dần trên `L0`; số liệu Aura khớp candidate |
| Frozen 0.2.2 | PASS | 636/636 tệp, không sửa |

## Nội dung đã thay đổi

| Phần | Thay đổi | Ý nghĩa |
| --- | --- | --- |
| So sánh thời gian | Chuẩn hóa UTC và dùng `datetime` của Neo4j | Hai múi giờ biểu diễn cùng thời điểm cho cùng kết quả |
| Snapshot | Fact chung lưu một lần, kèm danh sách snapshot nhìn thấy | Snapshot sau bao hàm snapshot trước mà không nhân 12 toàn bộ graph |
| Timeline | Chỉ chiếu frozen ledger `L0` vào graph vận hành | Nhánh lỗi vẫn dùng cho evaluation nhưng không gây xung đột trong graph chính |
| Node cố định | Driver, Fleet, Region, Service, Vehicle và Zone hiện ở mọi snapshot | Không làm snapshot đầu bị rỗng vì thiếu node tham chiếu |
| Policy | Chỉ hiện từ `dataset_release_at=2026-09-16T00:00:00Z` | Không làm lộ tài liệu ở snapshot lịch sử trước khi nguồn được công bố |
| Lọc lịch sử | Áp dụng snapshot, valid time và known time lên mọi cạnh được duyệt | Không lấy fact tương lai; vẫn hỏi lại được fact lịch sử |
| Incident | Bổ sung `open → resolved → reopened` bằng các khoảng không chồng nhau | Hỏi được trạng thái sự cố tại một thời điểm |
| Tool trạng thái | Thêm truy vấn Driver và Incident | Trả `resolved`, `conflict` hoặc `missing` |
| EnforcementDecision | Bỏ chữ “mock” khỏi tên, mô tả và trạng thái | Nội dung nghiệp vụ dễ đọc hơn |
| Coverage | Tool tự kiểm tra coverage artifact của snapshot | Caller không còn truyền boolean để tự khai báo dữ liệu đầy đủ |

## Thống kê node

| Node | Số lượng |
| --- | ---: |
| Trip | 80 |
| Measurement | 17 |
| StateObservation | 18 |
| PolicyClause | 13 |
| Complaint | 11 |
| Driver / Vehicle / MaintenanceEvent | 8 mỗi loại |
| Incident | 5 |
| Fleet / Zone / PolicyRule / PolicyAction / ViolationFinding / EnforcementDecision / PolicyDocument | 4 mỗi loại |
| Region / VehicleType | 2 mỗi loại |
| Service | 1 |
| **Tổng** | **201** |

## Diễn tiến 12 snapshot trên Aura

| STT | Cutoff UTC | Node | Cạnh | Trip | Complaint | Incident |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 2026-08-17 23:59:59 | 45 | 58 | 0 | 0 | 0 |
| 2 | 2026-08-18 23:59:59 | 62 | 103 | 6 | 0 | 4 |
| 3 | 2026-08-20 23:59:59 | 80 | 179 | 21 | 3 | 4 |
| 4 | 2026-08-22 23:59:59 | 96 | 253 | 35 | 5 | 4 |
| 5 | 2026-08-24 23:59:59 | 112 | 327 | 49 | 7 | 4 |
| 6 | 2026-08-26 23:59:59 | 128 | 401 | 63 | 9 | 4 |
| 7 | 2026-08-28 23:59:59 | 139 | 453 | 73 | 10 | 4 |
| 8 | 2026-08-31 23:59:59 | 147 | 490 | 80 | 11 | 4 |
| 9 | 2026-09-01 23:59:59 | 149 | 494 | 80 | 11 | 5 |
| 10 | 2026-09-16 12:00:00 | 192 | 550 | 80 | 11 | 5 |
| 11 | 2026-09-17 12:00:00 | 193 | 558 | 80 | 11 | 5 |
| 12 | 2026-09-18 03:00:00 | 201 | 582 | 80 | 11 | 5 |

Mỗi dãy số trên được đếm trực tiếp trong Aura bằng
`visibility_snapshot_ids`. Snapshot không sao chép node/cạnh; nó chỉ là một
allowlist để nhìn đúng phần graph đã được biết tại cutoff đó.

## Kiểm tra nghiệp vụ Neo4j

| Luồng | Kết quả |
| --- | --- |
| Driver → Trip | 7 tài xế có chuyến, 80 chuyến |
| Driver → Complaint → Trip | 11 phản ánh, 11 chuyến |
| Driver → Vehicle → MaintenanceEvent | 8 tài xế, 8 sự kiện |
| PolicyRule → PolicyClause → PolicyDocument | 4 rule, 13 clause, 4 document |
| Driver → Finding → Decision | 4 finding, 4 decision |
| Driver → Incident → Trip → State | 4 incident tổng hợp, 4 trip, 7 state |
| Incident lifecycle | `open`, `resolved`, `reopened` đúng theo thời điểm |
| `cancel_rate_30d` | Coverage đầy đủ trả `1/5`; thiếu coverage không trả `0` |

## Kiểm thử

- 211 test data, retrieval, conformance và integration PASS;
- provider keys không cần thiết;
- candidate E/F giống nhau hoàn toàn;
- nạp Neo4j lần hai tạo 0 node và 0 cạnh;
- frozen verifier PASS 636/636.

## Giới hạn còn giữ nguyên

- Đây là dữ liệu tổng hợp để nghiên cứu retrieval, không phải dữ liệu GSM thật.
- Không có Shift vì thiếu nguồn mở/tắt ứng dụng.
- Incident chưa mở rộng thành Cause → Action → OperationsUnit → System.
- Chưa tạo embedding node.
- Chưa có held-out test set; 42 câu hỏi hiện tại vẫn là dev/conformance.
- Không dùng kết quả này để khẳng định chất lượng production.
