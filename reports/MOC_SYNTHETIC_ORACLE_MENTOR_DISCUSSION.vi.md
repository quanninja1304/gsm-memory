# Trao đổi với mentor trước khi xây MOC Synthetic Oracle

## 1. Mục đích buổi trao đổi

Mục tiêu là thống nhất phạm vi và hợp đồng dữ liệu trước khi xây một bộ dữ liệu
MOC hoàn toàn tổng hợp để phát triển và kiểm thử kỹ thuật.

MOC trong tài liệu này phục vụ **đội kinh doanh vận hành GSM**. Đối tượng sử
dụng là nhân sự vận hành theo dõi chỉ số, nhận diện tình huống và phối hợp xử
lý. Đây không phải ứng dụng hỏi đáp dành cho tài xế và cũng không mặc định là
bài toán giám sát sự cố hạ tầng CNTT.

Nhóm thực hiện **không được phân quyền truy cập dữ liệu nội bộ**. Vì vậy bộ dữ
liệu dự kiến:

- không sử dụng cảnh báo hoặc sự cố thực tế;
- không chứa SOP/runbook nội bộ;
- không chứa tên hệ thống, máy chủ hoặc dịch vụ nội bộ;
- không chứa tên, email, lịch trực hoặc tài khoản nhân viên;
- không chứa thông tin khách hàng, thông tin xác thực hoặc bí mật vận hành;
- chỉ dùng tên, mã, mô tả và quan hệ giả lập;
- chỉ được dùng để phát triển và đánh giá kỹ thuật, không đại diện cho production.

Tên làm việc đề xuất:

```text
moc-synthetic-v0.1
```

## 2. Hiểu biết high-level hiện tại

Từ nội dung bàn giao, luồng nghiệp vụ dự kiến là:

```text
Alert
  → Case
  → Cause
  → Action
  → Owner/Role
  → System
```

Hệ thống sau này nhận một cảnh báo hoặc mô tả tự nhiên và hỗ trợ trả lời:

1. Đây có thể là case nào?
2. Những nguyên nhân nào có thể liên quan?
3. Cần thực hiện các hành động nào?
4. Vai trò hoặc nhóm nào phụ trách?
5. Cần thao tác trên loại hệ thống nào?
6. Kết quả dựa trên nguồn hoặc phiên bản dữ liệu nào?

`Alert` ở đây nên được hiểu trước hết là cảnh báo/chỉ báo về hoạt động kinh
doanh vận hành, chẳng hạn biến động cung-cầu, tỷ lệ hoàn thành, tỷ lệ hủy, thời
gian đón, năng lực đội xe hoặc chất lượng dịch vụ. Các ví dụ này chỉ là nhóm
tổng quát để thảo luận, chưa phải quy tắc nghiệp vụ GSM đã được xác nhận.

Neo4j sẽ giữ các quan hệ chuẩn. BM25/Qdrant có thể được dùng để tìm Alert hoặc
Case từ câu mô tả tự nhiên. Qdrant không thay thế Neo4j và không phải nguồn tạo
ra đáp án chuẩn.

## 3. Giới hạn của Synthetic Oracle

Synthetic Oracle là đáp án chuẩn **bên trong thế giới giả lập**:

```text
Quy tắc mô phỏng đã duyệt
          ↓
Dữ liệu tổng hợp
          ↓
Synthetic Oracle trên Neo4j
```

Synthetic Oracle không chứng minh:

- graph phản ánh đúng vận hành MOC thực tế;
- hành động được đề xuất an toàn để chạy trên production;
- owner hoặc system tương ứng với tổ chức thật;
- độ chính xác trên dữ liệu thực tế đạt 95%;
- hệ thống đã sẵn sàng tự động giao việc hoặc thực thi hành động.

## 4. Những điểm cần mentor xác nhận

### 4.1. Phạm vi tác vụ

Đánh dấu các tác vụ thuộc phạm vi MVP:

| Tác vụ | Có | Không | Ghi chú |
| --- | :---: | :---: | --- |
| Từ alert tìm case | [ ] | [ ] | |
| Từ case tìm nguyên nhân | [ ] | [ ] | |
| Từ case tìm hành động | [ ] | [ ] | |
| Xác định thứ tự hành động | [ ] | [ ] | |
| Xác định owner hoặc vai trò phụ trách | [ ] | [ ] | |
| Xác định hệ thống cần thao tác | [ ] | [ ] | |
| Trả nguồn/hướng dẫn liên quan | [ ] | [ ] | |
| Gợi ý chuyển cấp | [ ] | [ ] | |
| Tự động tạo công việc | [ ] | [ ] | |
| Tự động thực thi hành động | [ ] | [ ] | |
| Theo dõi trạng thái xử lý | [ ] | [ ] | |

Đề xuất phạm vi ban đầu:

```text
Tìm kiếm và trả lời có nguồn.
Không tự động thực thi hành động.
Không kết nối tài khoản, ca trực hoặc hệ thống production.
```

Quyết định:

> ..............................................................................

### 4.2. Loại thực thể

Danh sách dự kiến:

| Loại thực thể | Có cần không? | Ý nghĩa cần thống nhất |
| --- | :---: | --- |
| `AlertType` | [ ] | Loại cảnh báo hay một lần cảnh báo cụ thể? |
| `CaseType` | [ ] | Mẫu xử lý hay một sự cố thực tế? |
| `CauseType` | [ ] | Nguyên nhân khả dĩ hay đã được xác nhận? |
| `Action` | [ ] | Một bước xử lý riêng biệt |
| `ActionGroup` | [ ] | Nhóm phân loại hành động |
| `OwnerRole` | [ ] | Vai trò/nhóm, không phải cá nhân thật |
| `SystemType` | [ ] | Loại hệ thống hoặc hệ thống logic giả |
| `Procedure` | [ ] | Tài liệu/hướng dẫn giả lập |
| `Priority` | [ ] | Mức ưu tiên |
| `SourceRecord` | [ ] | Nguồn gốc của một quan hệ trong mock |

Các loại khác cần bổ sung:

> ..............................................................................

### 4.3. Loại quan hệ

Các quan hệ dự kiến:

```text
AlertType → MAPS_TO          → CaseType
CaseType  → HAS_CAUSE        → CauseType
CaseType  → REQUIRES_ACTION  → Action
Action    → BELONGS_TO       → ActionGroup
Action    → OWNED_BY         → OwnerRole
Action    → EXECUTED_ON      → SystemType
Action    → NEXT_ACTION      → Action
CaseType  → DOCUMENTED_BY    → Procedure
```

Cần xác nhận:

- [ ] Một alert có thể liên kết nhiều case.
- [ ] Một case có thể có nhiều nguyên nhân.
- [ ] Một nguyên nhân có thể được dùng lại ở nhiều case.
- [ ] Một case có thể có nhiều chuỗi hành động.
- [ ] Hành động có thứ tự bắt buộc.
- [ ] Hành động có thể chạy song song.
- [ ] Hành động có thể có nhánh điều kiện.
- [ ] Một hành động có thể có nhiều owner.
- [ ] Cần phân biệt owner chính và owner phối hợp.
- [ ] Một hành động có thể tác động nhiều hệ thống.
- [ ] Có trường hợp không đủ thông tin để chọn case.

Quy tắc hoặc bội số khác:

> ..............................................................................

### 4.4. Mức mô hình hóa owner và system

Đề xuất cho dữ liệu tổng hợp:

```text
Owner  = vai trò hoặc nhóm giả lập
System = loại hệ thống hoặc hệ thống logic giả lập
```

Ví dụ:

```text
ROLE_OPERATION_CONTROLLER
ROLE_REGIONAL_OPERATIONS
ROLE_DRIVER_SUPPLY_OPERATIONS
ROLE_SERVICE_QUALITY
ROLE_COMMERCIAL_OPERATIONS

SYSTEM_TYPE_OPERATION_DASHBOARD
SYSTEM_TYPE_TRIP_MANAGEMENT
SYSTEM_TYPE_DRIVER_SUPPLY
SYSTEM_TYPE_CUSTOMER_SUPPORT
SYSTEM_TYPE_PRICING_PROMOTION
SYSTEM_TYPE_REPORTING
SYSTEM_TYPE_TASK_MANAGEMENT
```

Cần xác nhận:

- [ ] Mock ở mức vai trò/nhóm, không mock cá nhân.
- [ ] Mock ở mức loại hệ thống, không mock máy chủ/instance.
- [ ] Được phép sử dụng tên và mã hoàn toàn giả.

Quyết định:

> ..............................................................................

### 4.5. Quy mô dữ liệu

Các con số đọc được từ kế hoạch bàn giao, cần xác nhận lại:

| Hạng mục | Con số dự kiến | Đã xác nhận |
| --- | ---: | :---: |
| Use case | 113 | [ ] |
| Nhóm hành động | 7 | [ ] |
| Hệ thống/dịch vụ | 7 | [ ] |
| Truy vấn đánh giá | 100 | [ ] |

Cần quyết định thêm:

| Hạng mục | Giá trị/khoảng mong muốn |
| --- | --- |
| Số AlertType | |
| Số CauseType | |
| Số Action | |
| Số OwnerRole | |
| Số action trung bình/case | |
| Tỷ lệ alert ánh xạ nhiều case | |
| Tỷ lệ case có nhiều nguyên nhân | |
| Tỷ lệ case có chuyển cấp | |
| Tỷ lệ truy vấn nhập nhằng/ngoài phạm vi | |

Nếu không có phân bố tham chiếu, nhóm sẽ đề xuất một phân bố giả lập và yêu cầu
duyệt trước khi sinh đủ dữ liệu.

### 4.6. Nhóm tình huống và nhóm hành động giả lập

Không sử dụng tình huống nội bộ. Có thể chọn từ các dạng tổng quát:

```text
Cung không đáp ứng nhu cầu theo khu vực/khung giờ
Tỷ lệ hoàn thành chuyến giảm
Tỷ lệ hủy chuyến tăng
Thời gian đón khách tăng
Số phương tiện hoặc tài xế hoạt động giảm
Chất lượng dịch vụ giảm
Phản ánh của khách hàng tăng
Chỉ số doanh thu hoặc sản lượng bất thường
Chương trình vận hành không đạt mục tiêu
Dữ liệu báo cáo vận hành không nhất quán
```

Nhóm hành động tổng quát có thể gồm:

```text
Kiểm tra
Xác minh
Thông báo
Chuyển cấp
Khôi phục
Cô lập
Theo dõi
```

Cần mentor xác nhận:

- [ ] Các nhóm trên phù hợp để làm mock kỹ thuật.
- [ ] Cần bỏ nhóm: ..........................................................
- [ ] Cần bổ sung nhóm: .....................................................
- [ ] Action mock chỉ là mô tả, không chứa lệnh vận hành thật.

### 4.7. Thời gian và cập nhật

Chọn một trong hai mức:

#### Mức 1 — snapshot tĩnh

- một phiên bản dữ liệu;
- không đồng bộ hằng ngày;
- không mô phỏng sửa/thu hồi;
- phù hợp để hoàn thiện loader, graph, API và retrieval trước.

#### Mức 2 — có lịch sử tổng hợp

- nhiều phiên bản dữ liệu giả;
- thay đổi owner/action/system theo ngày;
- giữ lịch sử thay vì ghi đè;
- kiểm tra truy vấn theo phiên bản.

Quyết định cho MVP:

- [ ] Mức 1 — snapshot tĩnh.
- [ ] Mức 2 — có lịch sử tổng hợp.

Ghi chú:

> ..............................................................................

### 4.8. Tiêu chí đánh giá

Cần định nghĩa chính xác mục tiêu “đúng ít nhất 95%”:

| Chỉ số | Có dùng? | Ngưỡng/Ghi chú |
| --- | :---: | --- |
| Case đúng ở vị trí đầu tiên | [ ] | |
| Case đúng nằm trong top-k | [ ] | `k = ...` |
| Đúng nguyên nhân | [ ] | Một hay tất cả? |
| Đúng danh sách hành động | [ ] | |
| Đúng thứ tự hành động | [ ] | |
| Đúng owner chính | [ ] | |
| Đúng hệ thống | [ ] | |
| Đủ đường Case → Action → Owner → System | [ ] | |
| Có nguồn cho kết quả | [ ] | |
| Từ chối đúng cảnh báo ngoài phạm vi | [ ] | |
| Độ trễ p95 dưới 10 giây | [ ] | |

Cần xác nhận bộ 100 truy vấn:

- [ ] Có thể hoàn toàn tổng hợp.
- [ ] Phải có câu ngoài phạm vi.
- [ ] Phải có câu nhập nhằng.
- [ ] Phải có câu hỏi nhiều bước.
- [ ] Phải tách tập phát triển và tập kiểm thử.

Đề xuất chia:

```text
40 câu phát triển
20 câu kiểm thử tích hợp
40 câu kiểm thử giữ kín
```

Quyết định:

> ..............................................................................

### 4.9. Schema dữ liệu đề xuất

Schema dưới đây chỉ sử dụng tên, mã và nội dung giả lập. Nhờ mentor xác nhận
cấu trúc này có phù hợp với cách MOC cần được mô hình hóa không, hoặc còn thiếu
loại node, trường hay quan hệ quan trọng nào.

#### `AlertType`

Đại diện cho một **loại cảnh báo**, không phải một lần cảnh báo thực tế.

```text
alert_type_id
name
description
severity
aliases
status
source_id
```

Ví dụ hoàn toàn giả lập:

```text
ALT-001
Trip completion rate decrease
Tỷ lệ hoàn thành chuyến trong một khu vực và khung giờ giảm dưới ngưỡng giả lập
high
["tỷ lệ hoàn thành giảm", "nhiều chuyến không hoàn thành"]
active
```

#### `CaseType`

Đại diện cho một mẫu tình huống cần xử lý.

```text
case_type_id
name
description
priority
status
source_id
```

#### `CauseType`

Đại diện cho một nguyên nhân khả dĩ, không mặc định là nguyên nhân đã được xác
nhận trong một sự cố thực tế.

```text
cause_type_id
name
description
cause_category
status
source_id
```

#### `Action`

Đại diện cho một bước xử lý.

```text
action_id
name
description
action_group_id
sequence
condition
approval_required
status
source_id
```

`condition` chỉ mô tả điều kiện giả lập, không chứa lệnh hoặc thông tin vận hành
thật.

#### `ActionGroup`

Đại diện cho một nhóm hành động.

```text
action_group_id
name
description
```

Bảy nhóm giả lập đề xuất:

```text
Kiểm tra
Xác minh
Thông báo
Chuyển cấp
Khôi phục
Cô lập
Theo dõi
```

#### `OwnerRole`

Đại diện cho một vai trò hoặc nhóm phụ trách, không đại diện cho cá nhân thật.

```text
owner_role_id
name
description
responsibility_level
```

#### `SystemType`

Đại diện cho loại hệ thống hoặc hệ thống logic giả lập.

```text
system_type_id
name
description
system_category
```

#### Ngữ cảnh kinh doanh vận hành cần xác nhận

Vì MOC phục vụ đội kinh doanh vận hành, một cảnh báo có thể chỉ có ý nghĩa khi
gắn với khu vực, loại dịch vụ, khung thời gian hoặc định nghĩa chỉ số. Cần mentor
xác nhận có cần bổ sung các thực thể sau không:

```text
OperationalMetric  Chỉ số vận hành được theo dõi
Region              Khu vực giả lập
ServiceType         Loại dịch vụ giả lập
TimeWindow          Khung thời gian đánh giá
OperatingUnit       Đơn vị vận hành giả lập
ResourceGroup       Nhóm nguồn lực/đội xe/tài xế ở mức tổng hợp
```

Các node này chỉ biểu diễn phạm vi tổng hợp. Không lưu danh tính tài xế, khách
hàng, nhân viên hoặc địa bàn nội bộ thật.

Cần xác nhận:

- [ ] Alert phải gắn với một `OperationalMetric`.
- [ ] Case/Action thay đổi theo `Region`.
- [ ] Case/Action thay đổi theo `ServiceType`.
- [ ] Alert cần một `TimeWindow` rõ ràng.
- [ ] Cần mô hình hóa nguồn lực ở mức nhóm/tổng hợp.
- [ ] Cần phân biệt đơn vị vận hành với `OwnerRole`.

#### `Procedure`

Đại diện cho hướng dẫn xử lý giả lập.

```text
procedure_id
name
description
version
status
```

#### `SourceRecord`

Dùng để truy vết một node hoặc quan hệ được tạo từ phiên bản recipe và template
nào. Đây không phải tài liệu nội bộ thật.

```text
source_id
source_type
template_id
recipe_version
seed
created_at
```

#### Bảng quan hệ chuẩn

```text
relation_id
subject_id
predicate
object_id
sequence
condition
is_required
source_id
status
```

Ví dụ:

```json
{
  "relation_id": "REL-00031",
  "subject_id": "CAS-014",
  "predicate": "REQUIRES_ACTION",
  "object_id": "ACT-031",
  "sequence": 1,
  "condition": null,
  "is_required": true,
  "source_id": "SYNTHETIC_RECIPE_V1",
  "status": "active"
}
```

Cần mentor xác nhận:

- [ ] Schema đề xuất phù hợp với mục tiêu MOC mock.
- [ ] `AlertType` là loại cảnh báo, không phải alert event thực tế.
- [ ] `CaseType` là mẫu tình huống kinh doanh vận hành, không phải một lần phát
  sinh thực tế.
- [ ] `CauseType` có thể biểu diễn nguyên nhân khả dĩ.
- [ ] `Procedure` cần có ngay trong MVP.
- [ ] `Priority` nên là thuộc tính hay một node riêng.
- [ ] Mỗi node/cạnh cần có `source_id` để truy vết.

Trường hoặc thực thể cần bổ sung/bỏ:

> ..............................................................................

### 4.10. Định danh và quy tắc sinh dữ liệu

Định danh ổn định đề xuất:

```text
ALT-001    AlertType
CAS-001    CaseType
CAU-001    CauseType
ACT-001    Action
AGR-01     ActionGroup
ROL-01     OwnerRole
SYS-01     SystemType
PRO-001    Procedure
REL-00001  Relation
```

Cần xác nhận:

- [ ] Có lưu bí danh cho alert/case.
- [ ] Hai thực thể trùng tên vẫn có thể là hai thực thể khác nhau.
- [ ] Cause hoặc Action có thể được dùng lại ở nhiều case.
- [ ] Khi đổi nội dung thì giữ ID cũ và tăng phiên bản.
- [ ] Khi đổi danh tính nghiệp vụ thì tạo ID mới.

Nếu không có phân bố tham chiếu, quy tắc sinh ban đầu được đề xuất như sau:

```text
Mỗi AlertType liên kết 1–3 CaseType.
Mỗi CaseType có 1–4 CauseType.
Mỗi CaseType có 2–6 Action.
Mỗi Action có một OwnerRole chính.
Một phần Action có thêm OwnerRole phối hợp.
Mỗi Action liên kết 1–2 SystemType.
Một phần CaseType có chuyển cấp hoặc rẽ nhánh.
Một phần AlertType cố ý nhập nhằng.
Một phần truy vấn nằm ngoài phạm vi.
```

Các con số trên chỉ là giả định tổng hợp. Cần mentor duyệt recipe và 5–10 case
mẫu trước khi sinh đủ 113 case.

Quyết định/điều chỉnh:

> ..............................................................................

### 4.11. Simulator cảnh báo tổng hợp

Synthetic Oracle và simulator có hai trách nhiệm khác nhau:

```text
Synthetic Oracle
→ lưu tri thức chuẩn: AlertType → Case → Cause → Action → OwnerRole → SystemType

Simulator
→ phát sinh AlertEvent giả theo thời gian để kiểm tra luồng đầu cuối
```

Xây Oracle tĩnh không bắt buộc có simulator. Simulator chỉ cần nếu MVP phải thử
nghiệm tiếp nhận sự kiện, cập nhật theo thời gian, xử lý cảnh báo liên tiếp hoặc
đồng bộ hằng ngày.

#### Câu hỏi về simulator hiện có

- [ ] Phía MOC đã có simulator hoặc công cụ phát cảnh báo thử nghiệm.
- [ ] Có thể cung cấp hợp đồng giao tiếp đã ẩn danh, không kèm dữ liệu thật.
- [ ] Simulator giao tiếp qua file.
- [ ] Simulator giao tiếp qua API.
- [ ] Simulator giao tiếp qua hàng đợi sự kiện.
- [ ] Simulator nằm trong phạm vi MVP.

Nếu đã có simulator, nhóm chỉ cần các thông tin không nhạy cảm:

- định dạng sự kiện đầu vào/đầu ra;
- tên và kiểu dữ liệu của các trường;
- giao thức file, API hoặc hàng đợi;
- quy tắc thời gian;
- tần suất phát sự kiện;
- cách biểu diễn trạng thái;
- một hoặc hai mẫu đã thay toàn bộ tên và giá trị nhạy cảm.

#### Schema `AlertEvent` đề xuất

```text
event_id
alert_type_id
occurred_at
observed_at
severity
status
correlation_key
attributes
simulator_scenario_id
```

Ví dụ hoàn toàn giả lập:

```json
{
  "event_id": "EVT-000001",
  "alert_type_id": "ALT-001",
  "occurred_at": "2026-01-01T08:00:00Z",
  "observed_at": "2026-01-01T08:00:03Z",
  "severity": "high",
  "status": "open",
  "correlation_key": "SIM-CORR-001",
  "attributes": {
    "region": "REGION_A",
    "service_type": "SERVICE_TYPE_A",
    "time_window": "WINDOW_A",
    "observed_value": "SYNTHETIC_VALUE_A"
  },
  "simulator_scenario_id": "SIM-001"
}
```

Nếu chưa có simulator, có thể xây một bộ phát lại nhỏ, xác định được bằng seed,
với các kịch bản:

```text
Normal
Burst
Ambiguous
Unknown
Out-of-order
Duplicate
Resolved
Reopened
```

Luồng thử nghiệm:

```text
Synthetic AlertEvent
        ↓
Nhận diện AlertType/CaseType
        ↓
Truy vấn Synthetic Oracle
        ↓
Trả Cause/Action/OwnerRole/SystemType
```

Simulator tự xây sẽ không:

- kết nối hệ thống production;
- gọi lệnh vận hành;
- tạo cảnh báo thật;
- sử dụng tên hệ thống thật;
- sử dụng dữ liệu nội bộ.

Quyết định:

- [ ] MVP chỉ cần Oracle snapshot tĩnh, chưa cần simulator.
- [ ] MVP cần tích hợp simulator hiện có qua hợp đồng đã ẩn danh.
- [ ] MVP cần một simulator tổng hợp nhỏ do nhóm tự xây.

Ghi chú:

> ..............................................................................

## 5. Thông tin không yêu cầu cung cấp

Buổi trao đổi này không yêu cầu mentor cung cấp:

- alert hoặc log vận hành thật;
- case/sự cố nội bộ;
- SOP hoặc runbook nội bộ;
- tên hệ thống, máy chủ, IP, domain hoặc endpoint;
- tên, email, số điện thoại hoặc lịch trực của nhân viên;
- dữ liệu khách hàng;
- tài khoản, mật khẩu, khóa API hoặc thông tin xác thực;
- lệnh xử lý production;
- số liệu kinh doanh hoặc dữ liệu thuộc diện hạn chế truy cập.

Nếu cần ví dụ để xác nhận ontology, chỉ sử dụng ví dụ đã ẩn danh hoặc ví dụ hoàn
toàn giả lập.

## 6. Đầu ra dự kiến sau khi được duyệt

Sau khi hợp đồng mô phỏng được thống nhất, đầu ra dự kiến gồm:

1. `moc-synthetic-v0.1` với manifest ghi rõ dữ liệu tổng hợp.
2. Danh mục Alert, Case, Cause, Action, ActionGroup, OwnerRole và SystemType.
3. Quan hệ chuẩn và nguồn gốc giả lập cho từng quan hệ.
4. Synthetic Oracle trên Neo4j, nạp xác định và chạy lại không nhân đôi.
5. Verifier kiểm tra số node, cạnh, thiếu, thừa, trùng và sai liên kết.
6. Bộ câu hỏi phát triển/kiểm thử và đáp án chuẩn tổng hợp.
7. Tài liệu mô tả để thử BM25/Qdrant.
8. API thử nghiệm truy vấn từ alert đến case, action, owner và system.
9. Báo cáo giới hạn, trong đó khẳng định không đại diện cho production truth.

Manifest tối thiểu dự kiến:

```json
{
  "dataset_id": "moc-synthetic-v0.1",
  "state": "DRAFT",
  "is_synthetic": true,
  "contains_internal_data": false,
  "represents_production_truth": false,
  "approved_for_technical_evaluation": true
}
```

## 7. Điều kiện bắt đầu sinh đủ 113 case

Chỉ sinh đầy đủ sau khi có xác nhận về:

- [ ] phạm vi tác vụ;
- [ ] loại node;
- [ ] loại quan hệ;
- [ ] bội số và ràng buộc;
- [ ] quy mô dữ liệu;
- [ ] nhóm tình huống và hành động giả lập;
- [ ] mức mô hình hóa owner/system;
- [ ] snapshot tĩnh hay lịch sử tổng hợp;
- [ ] tiêu chí đánh giá;
- [ ] quyền sử dụng dữ liệu hoàn toàn giả;
- [ ] người duyệt ontology và một số mẫu ban đầu.

Nếu các nội dung trên chưa được chốt, chỉ nên dựng 5–10 case để kiểm tra Neo4j,
API và giao diện. Không nên gọi bản thử kỹ thuật đó là MOC Oracle hoàn chỉnh.

## 8. Ghi nhận quyết định sau buổi trao đổi

**Ngày trao đổi:** ..............................................................

**Người tham gia:** .............................................................

**Người duyệt thiết kế mock:** ..................................................

**Phạm vi được duyệt:**

> ..............................................................................

**Các giả định được phép sử dụng:**

> ..............................................................................

**Các nội dung loại khỏi phạm vi:**

> ..............................................................................

**Tiêu chí nghiệm thu:**

> ..............................................................................

**Hành động tiếp theo:**

> ..............................................................................
