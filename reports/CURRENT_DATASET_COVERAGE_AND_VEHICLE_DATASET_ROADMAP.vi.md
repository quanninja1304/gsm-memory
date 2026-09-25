# Báo cáo phạm vi bộ dữ liệu hiện tại và lộ trình xây bộ dữ liệu chẩn đoán xe

| Thuộc tính | Giá trị |
| --- | --- |
| Kho mã nguồn | `memory/` |
| Bộ dữ liệu hiện tại | `gsm-dev-core-0.2.2` |
| Trạng thái | Đã đóng băng (`FROZEN`) |
| Phiên bản lược đồ / đặc tả | `1.1` / `0.2.0` |
| Giá trị khởi tạo | `42` |
| Mốc mã nguồn | `30eead44a6306783ad09880fe45fec34ac9679ff` |
| Ngày lập báo cáo | 2026-09-22 |

---

## 1. Kết luận chính

`gsm-dev-core-0.2.2` là bộ dữ liệu hoàn chỉnh cho bài toán hiện tại của dự án:

> Truy xuất tài liệu chính sách, truy xuất đồ thị theo thời gian và xây dựng gói bằng chứng cho các câu hỏi về tài xế và hoạt động vận hành GSM.

Bộ dữ liệu đã làm tốt các phần sau:

- bảo toàn và kiểm tra nguồn tài liệu;
- quản lý định danh thực thể;
- biểu diễn sự kiện và trạng thái theo thời gian;
- xử lý sửa đổi, rút lại và xung đột nguồn;
- tách dữ liệu công khai khỏi đáp án nội bộ;
- cô lập dữ liệu theo từng ảnh chụp thời điểm;
- tính toán chính xác khi có bằng chứng về độ đầy đủ;
- cung cấp đáp án chuẩn, bằng chứng và địa chỉ truy nguyên;
- tái tạo bộ dữ liệu một cách xác định;
- chẩn đoán lỗi ở từng bước truy xuất và chọn bằng chứng.

Tuy nhiên, bộ dữ liệu này **không đủ cho kế hoạch tác tử AI chẩn đoán sự cố xe** vì chưa có:

- linh kiện, triệu chứng, dạng hỏng và mã lỗi xe;
- quan hệ nhân quả và điều kiện vận hành;
- lịch sử quan sát, kiểm tra và sửa chữa xe;
- mức rủi ro và khuyến cáo an toàn;
- đường chẩn đoán chuẩn;
- hội thoại nhiều lượt và bộ nhớ phiên;
- tập kiểm thử khóa kín cho miền chẩn đoán xe.

Hướng đúng là:

1. giữ nguyên `gsm-dev-core-0.2.2`;
2. dùng cách tổ chức và kiểm định của nó làm mẫu;
3. xây một họ bộ dữ liệu chẩn đoán xe riêng;
4. chỉ xây tác tử và giao diện sau khi dữ liệu, quy tắc an toàn và đáp án chuẩn đã đủ rõ.

---

## 2. Bộ dữ liệu hiện tại gồm những gì?

### 2.1. Nguồn tài liệu

Bộ dữ liệu chứa 224 bài viết GSM đã được cố định từ một tệp nén nguồn. Mỗi tài liệu có:

- mã định danh ổn định;
- bản thô và bản đã chuẩn hóa;
- mã băm SHA-256;
- thông tin nguồn;
- thời điểm được phép xuất hiện trong bộ dữ liệu;
- địa chỉ tới đoạn hoặc điều khoản đã được rà soát;
- thông tin thuộc nhóm tài liệu nào.

Hai nhóm tài liệu chính:

| Nhóm | Thành phần | Mục đích |
| --- | --- | --- |
| `debug_core@1.0` | 6 bài thực, 3 phiên bản chính sách tổng hợp, 12 định nghĩa | Kiểm tra nhanh và dò lỗi |
| `retrieval_full@1.0` | 224 bài thực, 3 phiên bản tổng hợp, 12 định nghĩa | Chạy truy xuất đầy đủ |

Trong 224 bài:

- 6 nguồn đã được rà soát;
- 4 nguồn được dùng làm bằng chứng chuẩn chính;
- 2 nguồn đã rà soát đóng vai trò gây nhiễu;
- các bài còn lại chủ yếu dùng để kiểm tra khả năng tìm đúng tài liệu giữa một kho lớn hơn.

Một tệp gộp trùng lặp vẫn được giữ để kiểm tra nguồn nhưng không được tính là một tài liệu truy xuất độc lập.

### 2.2. Thế giới tổng hợp

Bộ dữ liệu tạo một thế giới tổng hợp xác định gồm:

```text
1 thế giới W0
8 tài xế
80 chuyến xe kết thúc
các số liệu được báo cáo
các sự cố
lịch sử tên và quan hệ thực thể
các chính sách tổng hợp dùng để kiểm tra
```

Thế giới nội bộ giúp sinh dữ liệu nhất quán. Nó không được dùng để lấp chỗ trống cho dữ liệu công khai.

Nguyên tắc quan trọng:

```text
Sự thật nội bộ không đồng nghĩa với điều có thể kết luận từ bằng chứng công khai.
```

Ví dụ:

- nội bộ biết một tài xế thuộc khu vực nào, nhưng ảnh chụp công khai chưa có bằng chứng thì phải trả lời “không đủ bằng chứng”;
- hai nguồn công khai có cùng mức thẩm quyền nhưng nói khác nhau thì phải trả lời “xung đột chưa giải quyết”, không được dùng dữ liệu nội bộ để chọn một bên.

### 2.3. Sổ sự kiện theo thời gian

Bộ dữ liệu có tám dòng lịch sử độc lập:

```text
L0
L_NO_OPDAY
L_WRONG_DRIVER
L_CONFLICT
L_RETRACT
L_WRONG_WINDOW
L_NO_BRIDGE
L_NO_COVERAGE
```

Mỗi dòng lịch sử là một nhánh riêng. Không được trộn chúng thành một dòng chung.

Sổ sự kiện hỗ trợ:

```text
ghi nhận mới
thay thế thông tin cũ
rút lại thông tin
```

Mỗi bản ghi giữ:

- nguồn phát hành;
- phạm vi áp dụng;
- thời điểm thông tin được biết;
- nội dung khẳng định;
- mã bản ghi và mã khẳng định;
- liên kết tới bản ghi bị sửa hoặc bị rút;
- dấu vết nguồn.

Bộ dữ liệu phân biệt bốn loại thời gian:

| Khái niệm | Ý nghĩa |
| --- | --- |
| Thời điểm sự kiện | Khi sự kiện thực tế xảy ra |
| Thời gian có hiệu lực | Khoảng thời gian một trạng thái đúng |
| Thời gian được biết | Khi nguồn công bố thông tin đó |
| Thời gian nhập hệ thống | Khi hệ thống nhận hoặc xử lý dữ liệu |

Nhờ vậy, hệ thống có thể trả lời đúng câu hỏi lịch sử trước và sau một lần sửa dữ liệu.

### 2.4. Câu hỏi, đáp án và bằng chứng

Bộ dữ liệu đóng gói:

```text
25 gốc tình huống
32 biến thể tình huống
42 trường hợp ngữ nghĩa
42 câu hỏi tiếng Việt dùng để phát triển
0 câu hỏi kiểm thử khóa kín
12 ảnh chụp dữ liệu công khai
42 đáp án chuẩn
42 hồ sơ chứng minh
110 đơn vị bằng chứng
110 liên kết bằng chứng
```

Phân bố trạng thái đáp án:

| Trạng thái | Số trường hợp | Ý nghĩa |
| --- | ---: | --- |
| Có thể trả lời | 32 | Bằng chứng công khai đủ |
| Không đủ bằng chứng | 8 | Thiếu một hoặc nhiều điều kiện cần |
| Xung đột chưa giải quyết | 1 | Nguồn cùng mức thẩm quyền mâu thuẫn |
| Yêu cầu mơ hồ | 1 | Không xác định được duy nhất đối tượng cần hỏi |

Mỗi trường hợp có thể trả lời đều có:

- giá trị đúng với kiểu dữ liệu rõ ràng;
- tập bằng chứng tối thiểu đủ để kết luận;
- nguồn, thực thể và thời gian đúng;
- các vai trò bằng chứng cần thiết.

Các trường hợp không thể trả lời không được coi là đúng chỉ vì đưa ra một gói bằng chứng rỗng.

---

## 3. Những năng lực đã được bao phủ

### 3.1. Tính toàn vẹn của nguồn

Bộ dữ liệu đã chứng minh:

- tệp nén nguồn đúng mã băm;
- có thể dựng nguồn mà không cần mạng;
- đủ 224 tài liệu chuẩn;
- bản thô và bản chuẩn hóa được phân biệt rõ;
- xuống dòng ổn định trên Windows và Linux;
- tệp nhị phân không bị chỉnh sửa như văn bản;
- thiếu, thừa hoặc đổi một tệp đều bị phát hiện.

Kết quả kiểm tra bản đóng băng:

```text
Số mục đã kiểm:       636/636
Thiếu:                0
Sai mã băm:           0
Tệp ngoài danh sách:  0
Kết quả:              ĐẠT
```

### 3.2. Định danh thực thể

Bộ dữ liệu kiểm tra được:

- mã định danh ổn định;
- hai người cùng tên không bị gộp;
- tên cũ và tên mới theo thời gian;
- ánh xạ tên công khai về đúng thực thể;
- câu hỏi mơ hồ không được tự chọn một người;
- bằng chứng của tài xế khác không được dùng thay.

Điểm này có thể áp dụng lại cho xe, linh kiện và mã lỗi, nhưng danh mục thực thể hiện tại vẫn chỉ thuộc miền GSM.

### 3.3. Tính đúng đắn theo thời gian

Các trường hợp đã có gồm:

- trạng thái có hiệu lực trong tương lai;
- thông tin chỉ xuất hiện sau một thời điểm công bố;
- sửa lại dữ liệu lịch sử;
- truy vấn trước và sau lần sửa;
- sự kiện đến muộn;
- sửa thời điểm sự kiện;
- biên thời gian trùng nhau;
- trạng thái bị rút lại;
- truy vấn lại một ảnh chụp lịch sử cũ.

Đây là phần có thể dùng lại mạnh nhất khi thiết kế lịch sử quan sát và sửa chữa xe.

### 3.4. Thẩm quyền nguồn, sửa đổi và xung đột

Bộ dữ liệu kiểm tra:

- nguồn nào được phép phát hành loại thông tin nào;
- nguồn nào được phép sửa nguồn nào;
- thay thế và rút lại có đúng đối tượng hay không;
- nguồn thẩm quyền thấp hơn không lấn nguồn cao hơn;
- hai nguồn cao nhất mâu thuẫn phải giữ trạng thái xung đột;
- rút lại một khẳng định không có nghĩa khẳng định ngược lại là đúng.

Trong miền xe, nguyên tắc này có thể dùng để phân biệt:

```text
tài liệu nhà sản xuất
kết quả cảm biến
quan sát của tài xế
kiểm tra của kỹ thuật viên
kết luận của tác tử AI
```

### 3.5. Độ đầy đủ và bằng chứng phủ định

Bộ dữ liệu phân biệt:

1. có danh sách đầy đủ và danh sách không rỗng;
2. có danh sách đầy đủ nhưng danh sách rỗng;
3. không biết danh sách đã đầy đủ hay chưa.

Ví dụ:

- có đúng 10 chuyến, trong đó 2 chuyến bị hủy thì tỷ lệ là `1/5`;
- chứng minh được không có chuyến nào thì kết quả tỷ lệ là “không xác định”, không phải 0;
- nhìn thấy 10 bản ghi nhưng không có giấy chứng nhận độ đầy đủ thì không được tuyên bố đó là toàn bộ dữ liệu.

Nguyên tắc tương ứng trong chẩn đoán xe:

> Không tìm thấy mã lỗi không chứng minh rằng xe không có lỗi, trừ khi có bằng chứng rằng phép quét hoặc kiểm tra đã bao phủ đầy đủ phần cần kiểm tra.

### 3.6. Truy nguyên tài liệu

Bộ dữ liệu kiểm tra:

- đúng phiên bản tài liệu;
- đúng đoạn và điều khoản;
- đúng thời điểm tài liệu được phép xuất hiện;
- không dùng tài liệu gây nhiễu thay cho nguồn được chỉ định;
- giữ riêng định nghĩa, tài liệu và dữ liệu vận hành;
- không bịa lịch sử thay thế của chính sách thật.

Cách làm này phù hợp để áp dụng cho sách hướng dẫn sửa chữa, thông báo kỹ thuật và tài liệu OBD-II.

### 3.7. Cấu trúc bằng chứng

110 liên kết bằng chứng hiện tại gồm:

| Loại địa chỉ truy nguyên | Số lượng |
| --- | ---: |
| Đoạn tài liệu | 31 |
| Khẳng định trong sổ sự kiện | 67 |
| Dòng trong danh mục thực thể | 4 |
| Tệp định nghĩa | 3 |
| Tệp chứng nhận độ đầy đủ | 5 |

Nhờ cấu trúc này, hệ thống có thể phân biệt:

- bước tìm kiếm chưa lấy đủ bằng chứng;
- bước chọn bằng chứng đã làm mất một phần chứng minh;
- bằng chứng sai người, sai thời gian hoặc sai nguồn;
- bằng chứng đúng nhưng phần suy luận phía sau vẫn trả lời sai.

### 3.8. Kiểm định độc lập

Các nhóm kiểm tra đều đạt:

| Nhóm | Kết quả |
| --- | ---: |
| Kiểm tra dữ liệu V01–V14 | 14/14 |
| Kiểm tra tình huống SM01–SM08 | 8/8 |
| Ví dụ chuẩn EX01–EX25 | 25/25 |
| Kiểm tra bổ trợ | 9/9 |
| Kiểm tra thay đổi một nguyên nhân | 7/7 |
| Tổng kiểm tra ứng viên | 63/63 |
| Cổng đóng băng DFG01–DFG06 | 6/6 |
| Cổng kiểm định độc lập A1_G1–A1_G6 | 6/6 |

Một bộ đánh giá độc lập đã tái tạo đúng 42/42 kết quả mà không đọc đáp án đã sinh làm đầu vào tính toán.

### 3.9. Nền truy xuất hiện tại

Kho mã đã có:

- chia tài liệu thành đoạn;
- tìm kiếm BM25;
- dựng và tìm kiếm đồ thị Graphiti theo Mode A;
- lọc theo thực thể, phạm vi và thời gian;
- tính toán từ toàn bộ tập nguồn khi có bằng chứng độ đầy đủ;
- hợp nhất bằng chứng tài liệu và đồ thị;
- chọn bằng chứng trong giới hạn dung lượng;
- đánh giá riêng tập ứng viên và tập đã chọn.

Kết quả:

```text
Đủ bằng chứng ở tập ứng viên: 30/42
Đủ bằng chứng sau bước chọn:   15/42
Mất bằng chứng khi chọn:       15 trường hợp
```

Kết quả này cho thấy bộ dữ liệu đã đủ tốt để chỉ ra chính xác nút thắt của hệ thống hiện tại. Nó chưa chứng minh hệ thống truy xuất đã tốt hoặc tác tử đã hoạt động.

---

## 4. Những phần chưa đáp ứng kế hoạch chẩn đoán xe

### 4.1. Kiến thức chuyên ngành xe

Chưa có:

- dòng xe, đời xe và cấu hình xe;
- linh kiện và quan hệ linh kiện–cụm linh kiện;
- triệu chứng và tên gọi tương đương;
- dạng hỏng;
- mã cảm biến hoặc mã OBD-II;
- điều kiện vận hành và môi trường;
- bước kiểm tra;
- hành động sửa chữa hoặc xử lý;
- mức rủi ro.

### 4.2. Quan hệ nhân quả

Đồ thị hiện tại lưu các khẳng định theo thời gian. Nó chưa định nghĩa các quan hệ:

```text
GÂY_RA
CHỈ_BÁO
DẪN_ĐẾN
LÀM_NẶNG_THÊM
YÊU_CẦU_XỬ_LÝ
KHẮC_PHỤC
```

Chưa có quy tắc cho:

- điều kiện bắt buộc;
- điều kiện loại trừ;
- hướng của nguyên nhân và kết quả;
- nhiều nguyên nhân cùng gây một triệu chứng;
- một nguyên nhân gây nhiều triệu chứng;
- đường chẩn đoán thay thế;
- cách xử lý nguồn mâu thuẫn;
- cách hiểu xác suất và độ tin cậy.

### 4.3. Nguồn chẩn đoán

Chưa có:

- sách hướng dẫn sửa chữa;
- sách hướng dẫn sử dụng xe;
- đặc tả OBD-II;
- thông báo kỹ thuật của nhà sản xuất;
- quy trình kiểm tra;
- hướng dẫn an toàn đã rà soát;
- lịch sử chẩn đoán đã được kiểm chứng.

### 4.4. Lịch sử xe và bộ nhớ sự kiện

Chưa có mô hình cho:

- quan sát triệu chứng;
- mã lỗi xuất hiện;
- kết quả đo cảm biến;
- kết quả kiểm tra;
- thay linh kiện;
- bảo dưỡng;
- triệu chứng tái xuất hiện;
- phản hồi sau sửa chữa.

Đặc biệt, chưa có quy tắc tách biệt:

```text
điều đã quan sát
giả thuyết của hệ thống
kết luận đã xác nhận
khuyến nghị
hành động đã thực hiện
```

### 4.5. An toàn

Chưa có:

- bảng mức rủi ro;
- điều kiện cần dừng xe;
- điều kiện cần gọi hỗ trợ khẩn cấp;
- ngưỡng yêu cầu kiểm tra chuyên môn;
- hành động tạm thời an toàn;
- hướng dẫn bị cấm;
- câu trả lời khi không đủ bằng chứng;
- nguồn có thẩm quyền cho khuyến cáo an toàn.

### 4.6. Đáp án chuẩn cho chẩn đoán

Chưa có:

- nguyên nhân chấp nhận được;
- đường nhân quả chấp nhận được;
- nguyên nhân bị loại và lý do;
- điều kiện vận hành cần khớp;
- mức rủi ro đúng;
- hành động an toàn đúng;
- câu hỏi cần hỏi thêm;
- trường hợp phải từ chối kết luận.

### 4.7. Hội thoại và bộ nhớ phiên

Chưa kiểm tra:

- câu hỏi nối tiếp;
- thông tin người dùng sửa lại;
- giữ ngữ cảnh giữa nhiều lượt;
- chọn phần lịch sử nào cần đưa vào câu trả lời;
- quyền truy cập và thời hạn lưu bộ nhớ;
- tránh ghi một suy đoán thành sự thật.

### 4.8. Tập kiểm thử khóa kín

Bộ dữ liệu hiện tại có:

```text
42 câu hỏi phát triển
0 câu hỏi kiểm thử khóa kín
```

Do đó chưa thể dùng để tuyên bố khả năng khái quát hóa, kể cả trong miền GSM; càng không thể dùng để đánh giá chẩn đoán xe.

### 4.9. Hạ tầng sản phẩm

Chưa có:

- FastAPI;
- LangGraph;
- Redis;
- kho véc-tơ cho bộ nhớ sự kiện;
- giao diện Next.js;
- nhận giọng nói;
- Docker Compose chạy toàn hệ thống.

Đây là khoảng trống của sản phẩm, không phải chỉ là khoảng trống dữ liệu.

---

## 5. Phần có thể dùng lại

| Cách làm hiện tại | Áp dụng cho miền chẩn đoán xe |
| --- | --- |
| Cố định nguồn và mã băm | Cố định sách hướng dẫn, OBD-II và thông báo kỹ thuật |
| Mã định danh chuẩn | Định danh xe, linh kiện, triệu chứng và dạng hỏng |
| Sổ sự kiện bất biến | Lưu quan sát, kiểm tra, sửa chữa và phản hồi |
| Thời gian có hiệu lực / được biết | Phân biệt lúc sự cố xảy ra và lúc hệ thống biết |
| Sửa đổi và rút lại | Sửa kết quả đo hoặc kết luận chẩn đoán |
| Thẩm quyền nguồn | Phân biệt nhà sản xuất, cảm biến, kỹ thuật viên và người lái |
| Chứng nhận độ đầy đủ | Phân biệt “không tìm thấy” với “đã kiểm tra đầy đủ” |
| Đơn vị và liên kết bằng chứng | Chứng minh nguyên nhân, rủi ro và hành động |
| Ảnh chụp dữ liệu | Không cho hệ thống nhìn thấy thông tin tương lai |
| Bộ đánh giá sau khi chạy | Không để hệ thống đọc đáp án chuẩn |
| Hai lần dựng sạch | Chứng minh dữ liệu có thể tái tạo |

Không dùng lại trực tiếp:

- lược đồ nghiệp vụ GSM;
- 42 câu hỏi hiện tại;
- đáp án hiện tại;
- thế giới 8 tài xế;
- các quy tắc chính sách hiện tại;
- tên miền phát hành `gsm-dev-core-*`.

---

## 6. Bộ dữ liệu chẩn đoán xe cần có cấu trúc nào?

### 6.1. Lớp nguồn

Mỗi nguồn cần có:

```text
mã nguồn
loại nguồn
tiêu đề, phiên bản, lần phát hành
dòng xe và đời xe áp dụng
mức thẩm quyền
thời điểm thu thập hoặc phát hành
mã băm bản thô và bản chuẩn hóa
địa chỉ trang, mục, bảng hoặc đoạn
quyền sử dụng
trạng thái rà soát
```

Nguồn có thể gồm:

- tài liệu của nhà sản xuất;
- sách hướng dẫn sử dụng;
- đặc tả OBD-II;
- thông báo kỹ thuật;
- quy trình kiểm tra đã phê duyệt;
- hướng dẫn an toàn;
- dữ liệu cảm biến hoặc kiểm tra thực tế.

### 6.2. Lớp thực thể

Các loại thực thể tối thiểu:

```text
dòng xe
xe cụ thể
linh kiện
triệu chứng
dạng hỏng
mã cảm biến
điều kiện vận hành
điều kiện môi trường
phép kiểm tra
hành động
rủi ro
sự kiện
```

Mỗi thực thể cần mã chuẩn, tên tương đương, phạm vi áp dụng và nguồn.

### 6.3. Lớp quan hệ chẩn đoán

Mỗi quan hệ cần giữ:

```text
mã quan hệ
chủ thể
loại quan hệ
đối tượng
điều kiện bắt buộc
điều kiện loại trừ
dòng xe áp dụng
thời gian có hiệu lực và được biết
địa chỉ nguồn
trạng thái rà soát
có phải giả thuyết hay không
```

Nếu sử dụng xác suất hoặc độ tin cậy, phải định nghĩa rõ:

- con số nói về cái gì;
- được tính hoặc gán bằng cách nào;
- thuộc nguồn, quan hệ hay kết luận;
- có được cộng, nhân hoặc so sánh giữa các đường hay không;
- cách kiểm tra độ phù hợp của con số đó.

Không để mô hình ngôn ngữ tự gán các con số này mà không có quy tắc.

### 6.4. Lớp sự kiện xe

Các loại sự kiện đề xuất:

```text
quan sát triệu chứng
quan sát mã lỗi
quan sát điều kiện vận hành
kết quả kiểm tra
kết quả phép chẩn đoán
thay linh kiện
bảo dưỡng
phản hồi của người lái
quan sát sau sửa chữa
```

Mỗi sự kiện cần thời điểm xảy ra, thời điểm được biết, nguồn, xe liên quan và trạng thái sửa đổi.

### 6.5. Lớp an toàn

Cần quy định riêng cho:

- mức rủi ro;
- tình huống phải dừng xe;
- tình huống cần hỗ trợ khẩn cấp;
- tình huống cần kiểm tra chuyên môn;
- hành động tạm thời được phép;
- nội dung không được hướng dẫn;
- câu trả lời khi chưa đủ dữ liệu.

Khuyến cáo an toàn phải có bằng chứng riêng, không được suy ra chỉ từ điểm xếp hạng nguyên nhân.

### 6.6. Lớp tình huống đánh giá

Mỗi tình huống cần:

```text
gốc tình huống
câu hỏi hoặc lời nói đầu vào
ngữ cảnh xe
triệu chứng đã quan sát
điều kiện vận hành
phần lịch sử được phép nhìn thấy
các nguyên nhân chấp nhận được
các đường chẩn đoán chấp nhận được
các đường bị loại và lý do
các vai trò bằng chứng bắt buộc
mức rủi ro đúng
hành động an toàn đúng
câu hỏi cần hỏi thêm
trạng thái có thể kết luận hay không
```

Một tình huống có thể có nhiều đường chẩn đoán hợp lệ. Không nên chấm chỉ theo một chuỗi văn bản hoặc một đường duy nhất.

### 6.7. Chia tập dữ liệu

| Tập | Mục đích |
| --- | --- |
| Tập kiểm tra quy tắc | Kiểm từng quy tắc, biên thời gian và ngoại lệ |
| Tập phát triển | Điều chỉnh truy xuất, xếp hạng và lời nhắc |
| Tập kiểm thử khóa kín | Đánh giá cuối sau khi hệ thống đã được khóa |

Phải chia theo gốc tình huống, nhóm linh kiện, dòng xe và họ nguồn. Không để các cách diễn đạt khác nhau của cùng một tình huống rơi vào cả tập phát triển và tập kiểm thử.

---

## 7. Các cổng kiểm định dữ liệu đề xuất

Các cổng dưới đây là đề xuất cho bộ dữ liệu mới, chưa phải kết quả đã đạt.

### VDG01 — Phạm vi, nghiệp vụ và an toàn

Đạt khi:

- mục tiêu sử dụng và phần không làm đã được duyệt;
- danh sách loại thực thể và quan hệ đã được khóa;
- phân biệt quan sát, giả thuyết và kết luận;
- chính sách an toàn có người chịu trách nhiệm;
- cách hiểu xác suất và độ tin cậy đã rõ, hoặc tạm bỏ khỏi phiên bản đầu;
- nguồn và quyền sử dụng đã rõ.

### VDG02 — Tính toàn vẹn của nguồn

Đạt khi:

- mọi nguồn được cố định và có mã băm;
- địa chỉ trang, mục hoặc đoạn truy nguyên được;
- phiên bản và dòng xe áp dụng rõ;
- nguồn đã rà soát và chưa rà soát được tách biệt;
- quan hệ không có nguồn phải được đánh dấu là giả thuyết;
- có thể dựng nguồn mà không phụ thuộc mạng.

### VDG03 — Lược đồ và lịch sử sự kiện

Đạt khi:

- loại thực thể và quan hệ là tập đóng;
- mã định danh và tên tương đương ổn định;
- điều kiện có cấu trúc để máy kiểm tra;
- thời gian xảy ra và thời gian được biết tách biệt;
- sửa đổi, rút lại và xung đột hoạt động đúng;
- quan sát không bị gộp với suy luận;
- phạm vi dòng xe được kiểm tra.

### VDG04 — Tình huống, đáp án và bằng chứng an toàn

Đạt khi:

- có các trường hợp có thể trả lời, thiếu dữ liệu, xung đột, mơ hồ và nguy hiểm;
- có nhiều đường hợp lệ khi nghiệp vụ cho phép;
- mức rủi ro và hành động có nguồn;
- một bộ đánh giá độc lập có thể tái tạo đáp án;
- thay một điều kiện quan trọng làm đường hoặc kết quả đổi đúng dự kiến.

### VDG05 — Đóng gói và chống rò rỉ

Đạt khi:

- dữ liệu công khai không chứa đáp án hoặc nhãn lỗi;
- mỗi câu hỏi chỉ nhìn thấy đúng phần lịch sử được phép;
- đáp án nội bộ nằm riêng;
- không rò kết quả kiểm tra trong tương lai;
- hệ thống chạy được khi thư mục đáp án nội bộ không được gắn vào.

### VDG06 — Tái tạo và đóng băng

Đạt khi:

- mọi kiểm tra bắt buộc đều đã chạy;
- hai lần dựng sạch cho cùng nội dung logic;
- danh sách tệp đầy đủ;
- bộ kiểm tra bản đóng băng chỉ đọc;
- có tệp chứng nhận và mã băm;
- chỉ chuyển sang `FROZEN` sau khi có đủ bằng chứng.

---

## 8. Các cổng kiểm định hệ thống đề xuất

### VBRG01 — Dựng kho truy xuất

- nạp tài liệu;
- dựng đồ thị;
- giữ liên kết về nguồn;
- nạp lịch sử xe;
- lọc đúng thời gian và dòng xe;
- tạo mã nhận diện lần chạy ổn định.

### VBRG02 — Tìm đường chẩn đoán ứng viên

- liên kết thực thể;
- tìm đồ thị trong số bước giới hạn;
- lọc điều kiện có cấu trúc;
- giữ nhiều đường thay thế;
- giữ nguồn và sự kiện liên quan;
- đo tỷ lệ tìm thấy đường đúng trong tập ứng viên.

### VBRG03 — Chọn đường và bằng chứng

- không đọc đáp án nội bộ;
- giữ đủ các phần phụ thuộc của đường;
- giữ bằng chứng phản bác và xung đột;
- tuân thủ giới hạn dung lượng;
- đo riêng tập ứng viên và tập đã chọn.

### VBRG04 — Tác tử và an toàn

- cấu hình mô hình cố định;
- đầu ra có cấu trúc;
- mọi khẳng định quan trọng có trích dẫn;
- mức rủi ro và hành động đúng;
- từ chối kết luận khi thiếu dữ liệu;
- biết hỏi thêm;
- có lần chạy đối chứng với đường chuẩn để tách lỗi truy xuất khỏi lỗi suy luận.

### VBRG05 — Hiệu năng và vận hành

- thời gian nạp, truy xuất và trả lời;
- số lượt gọi, lượng mã thông báo và chi phí;
- thử lại, quá thời gian và giới hạn tốc độ;
- trạng thái bộ nhớ đệm;
- khả năng lặp lại;
- ghi lỗi và sự cố an toàn;
- chạy được bằng Docker Compose trong môi trường sạch.

---

## 9. Lộ trình thực hiện

### Giai đoạn 0 — Khóa phạm vi

Kết quả cần có:

- danh sách trường hợp sử dụng;
- một dòng xe hoặc nhóm xe cụ thể;
- một nhóm triệu chứng và dạng hỏng cụ thể;
- chính sách nguồn và quyền sử dụng;
- lược đồ phiên bản đầu;
- chính sách an toàn phiên bản đầu;
- khuôn dạng đầu vào, đầu ra và công cụ truy xuất;
- nguyên tắc chia tập phát triển và kiểm thử.

Điều kiện chuyển giai đoạn: `VDG01 ĐẠT`.

### Giai đoạn 1 — Xây kho nguồn đã rà soát

Kết quả cần có:

- tài liệu được cố định;
- danh mục nguồn và mã băm;
- địa chỉ trang, mục và đoạn;
- thông tin dòng xe áp dụng;
- các khẳng định hạt giống đã rà soát;
- danh mục thực thể và tên tương đương;
- bảng thẩm quyền nguồn.

Điều kiện chuyển giai đoạn: `VDG02 ĐẠT` trên kho nguồn ban đầu.

### Giai đoạn 2 — Xây lược đồ và sổ sự kiện

Kết quả cần có:

- mô hình dữ liệu đóng;
- mã định danh chuẩn;
- điều kiện có cấu trúc;
- quan hệ chẩn đoán;
- sổ sự kiện xe;
- quy tắc sửa đổi và rút lại;
- dấu vết nguồn và phiên bản;
- bộ kiểm tra từng quy tắc.

Điều kiện chuyển giai đoạn: `VDG03 ĐẠT`.

### Giai đoạn 3 — Tạo bộ tình huống hạt giống

Khuyến nghị ban đầu:

```text
10–20 gốc tình huống đã rà soát kỹ
có trường hợp đúng, thiếu dữ liệu, xung đột, mơ hồ và nguy hiểm
có nhiều đường hợp lệ khi cần
có bằng chứng cho rủi ro và hành động
```

Kết quả cần có:

- tập kiểm tra quy tắc;
- tập phát triển ban đầu;
- đáp án và đường chuẩn nội bộ;
- câu hỏi công khai;
- bộ đánh giá độc lập;
- kiểm tra thay đổi điều kiện.

Điều kiện chuyển giai đoạn: `VDG04 ĐẠT`.

### Giai đoạn 4 — Đóng gói và đóng băng bản hạt giống

Kết quả cần có:

- phần công khai và nội bộ tách biệt;
- ảnh chụp lịch sử cho từng câu hỏi;
- kiểm tra chống rò rỉ;
- hai lần dựng sạch;
- bộ kiểm tra chỉ đọc;
- báo cáo bộ dữ liệu.

Điều kiện chuyển giai đoạn: `VDG05–VDG06 ĐẠT`.

### Giai đoạn 5 — Xây hệ thống truy xuất chuẩn

Thứ tự thực hiện:

1. truy xuất tài liệu;
2. liên kết thực thể;
3. tìm các đường trong đồ thị;
4. lọc theo thời gian và điều kiện;
5. xếp hạng đường;
6. tìm lịch sử sự kiện;
7. hợp nhất và chọn bằng chứng;
8. đánh giá sau khi chạy.

Điều kiện chuyển giai đoạn: `VBRG01–VBRG03 ĐẠT`.

### Giai đoạn 6 — Tạo lát cắt tác tử hoàn chỉnh

Kết quả cần có:

- đầu vào văn bản qua FastAPI;
- bộ công cụ truy xuất cố định;
- luồng LangGraph có số bước giới hạn;
- câu trả lời có cấu trúc;
- cơ chế an toàn khi thiếu dữ liệu;
- câu hỏi bổ sung;
- bộ nhớ phiên;
- đối chứng bằng đường chuẩn;
- trích dẫn tới nguồn.

Điều kiện chuyển giai đoạn: `VBRG04 ĐẠT` trên bản hạt giống.

### Giai đoạn 7 — Mở rộng đánh giá

Sau khi lược đồ và cách chấm đã ổn định:

- mở rộng tới 50–100 trường hợp đã rà soát;
- tăng số nhóm linh kiện, dạng hỏng và nguồn;
- tạo tập kiểm thử khóa kín;
- thêm các cách diễn đạt và nhiễu nhưng giữ liên kết về cùng gốc tình huống;
- rà soát các đường thay thế;
- không điều chỉnh hệ thống trên tập kiểm thử khóa kín.

### Giai đoạn 8 — Đóng gói sản phẩm

- Redis cho bộ nhớ phiên nếu thực sự cần;
- kho véc-tơ cho lịch sử sự kiện nếu thử nghiệm chứng minh có ích;
- truyền kết quả từng phần;
- giao diện web tối thiểu;
- hình đồ thị giải thích;
- Docker Compose;
- ghi nhận chi phí và lỗi nhà cung cấp;
- giọng nói là mục tiêu bổ sung sau cùng.

---

## 10. Ưu tiên trong sáu tuần

Với hai người và sáu tuần, nên chia như sau.

### Bắt buộc

- một phạm vi xe và dạng hỏng rõ ràng;
- nguồn đã cố định;
- lược đồ và quy tắc an toàn;
- 10–20 gốc tình huống có thể kiểm tra;
- công cụ tìm đường đồ thị;
- lọc điều kiện;
- câu trả lời văn bản có căn cứ;
- từ chối an toàn khi thiếu dữ liệu;
- báo cáo lỗi và kết quả;
- giao diện lập trình và Docker tối thiểu.

### Nên có

- 30–50 tình huống phát triển;
- bộ nhớ phiên;
- tìm lịch sử sự kiện;
- giao diện trò chuyện đơn giản;
- hiển thị đường giải thích;
- đo thời gian và chi phí.

### Nếu còn thời gian

- 50–100 trường hợp được rà soát đầy đủ;
- tập kiểm thử khóa kín đủ mạnh;
- nhập bằng giọng nói;
- chuyển văn bản thành đồ thị một cách tổng quát;
- cho mô hình tự viết câu truy vấn Cypher;
- hỗ trợ nhiều kho véc-tơ;
- giao diện hoàn thiện.

Không nên đổi chất lượng nguồn và an toàn lấy mục tiêu số lượng như “1.000 quan hệ” hoặc “100 trường hợp”.

---

## 11. Các chỉ số cần đo

### Chất lượng dữ liệu

- tỷ lệ nguồn và quan hệ đã rà soát;
- tỷ lệ địa chỉ nguồn truy nguyên được;
- tính toàn vẹn của lược đồ;
- tính hợp lệ của điều kiện;
- độ phủ theo dòng xe;
- tính nhất quán thời gian;
- tỷ lệ tái tạo đúng đáp án chuẩn.

### Chất lượng truy xuất

- độ chính xác liên kết thực thể;
- tỷ lệ tìm thấy nguyên nhân đúng trong tập ứng viên;
- tỷ lệ tìm thấy đường đúng trong tập ứng viên;
- tỷ lệ giữ đường đúng sau bước chọn;
- độ chính xác lọc điều kiện;
- tỷ lệ sai xe, linh kiện, nguồn hoặc thời gian;
- độ phủ bằng chứng và trích dẫn;
- tỷ lệ bằng chứng được giữ từ tập ứng viên sang tập đã chọn.

### Chất lượng tác tử

- tỷ lệ chọn đúng nguyên nhân ở vị trí đầu và trong nhóm đầu;
- độ đúng của câu trả lời có cấu trúc;
- tỷ lệ khẳng định có nguồn;
- tỷ lệ khẳng định không có căn cứ;
- độ đúng của mức rủi ro;
- độ đúng của hành động an toàn;
- độ đúng khi từ chối kết luận;
- chất lượng câu hỏi bổ sung;
- độ đúng khi được cung cấp đường chuẩn.

### Chất lượng hệ thống

- thời gian nạp dữ liệu;
- thời gian truy xuất tài liệu và đồ thị;
- thời gian trả lời trung vị và phân vị 95;
- số lượt gọi, lượng mã thông báo và chi phí;
- tỷ lệ quá thời gian, thử lại và bị giới hạn tốc độ;
- trạng thái bộ nhớ đệm;
- khả năng lặp lại cùng kết quả;
- tỷ lệ khởi động thành công trong môi trường sạch.

Các ngưỡng như 90% liên kết thực thể, 75% đường nhân quả đứng đầu, dưới 5% khẳng định vô căn cứ và thời gian phân vị 95 dưới 8 giây chỉ nên được khóa sau khi có kết quả ban đầu và tập kiểm thử rõ ràng.

---

## 12. Thứ tự phụ thuộc và phân công

```text
Phạm vi và an toàn
        ↓
Nguồn đã rà soát
        ↓
Lược đồ và sổ sự kiện
        ↓
Tình huống, đường chuẩn và hành động an toàn
        ↓
Đóng gói và đóng băng dữ liệu
        ↓
Truy xuất và chọn đường
        ↓
Tác tử và kiểm tra an toàn
        ↓
Tập kiểm thử khóa kín và sản phẩm
```

### Người phụ trách dữ liệu và tri thức

- rà soát nguồn;
- lược đồ;
- mã định danh và tên tương đương;
- phạm vi áp dụng;
- dấu vết nguồn;
- mô hình sự kiện;
- quan hệ chẩn đoán;
- nạp dữ liệu;
- các cổng kiểm định dữ liệu.

### Người phụ trách truy xuất và suy luận

- liên kết thực thể;
- tìm đường ứng viên;
- lọc điều kiện;
- xếp hạng đường;
- chọn bằng chứng;
- điều phối tác tử;
- kiểm tra an toàn;
- phân tích lỗi;
- ghi nhận hoạt động của hệ thống.

Hai người cùng chịu trách nhiệm về:

- ý nghĩa quan hệ nhân quả;
- ngưỡng an toàn;
- đường chuẩn;
- khuôn dạng trao đổi dữ liệu;
- cách chia tập;
- rà soát lỗi nghiêm trọng.

---

## 13. Các quyết định phải chốt trước khi làm

1. Dòng xe hoặc nhóm xe nào thuộc phiên bản đầu?
2. Tài liệu nào được phép sử dụng?
3. Ai chịu trách nhiệm rà soát chuyên môn và an toàn?
4. Xác suất và độ tin cậy được hiểu thế nào, hay tạm bỏ khỏi phiên bản đầu?
5. Quan hệ nhân quả được lấy từ nguồn, chuyên gia hay mô hình trích xuất?
6. Quan hệ do mô hình trích xuất có bắt buộc được người rà soát duyệt không?
7. Quan sát, giả thuyết và chẩn đoán đã xác nhận được lưu khác nhau thế nào?
8. Tập kiểm thử khóa kín được chia theo nhóm nào?
9. Neo4j có bắt buộc hay chỉ cần một giao diện đồ thị chung?
10. Mô hình tạo câu trả lời và giới hạn chi phí là gì?
11. Mức rà soát pháp lý và an toàn cho câu trả lời là gì?
12. Mục tiêu sáu tuần là thử nghiệm nghiên cứu hay trình diễn sản phẩm?

Không nên làm bộ chuyển văn bản thành đồ thị tổng quát hoặc giao diện hoàn chỉnh trước khi các câu hỏi trên có câu trả lời và người chịu trách nhiệm.

---

## 14. Tiêu chí hoàn thành đề xuất

### Bản dữ liệu chẩn đoán xe đầu tiên

- [ ] Phạm vi và quy tắc an toàn đã được duyệt.
- [ ] Nguồn có mã băm, quyền sử dụng và địa chỉ truy nguyên.
- [ ] Lược đồ và điều kiện đã được khóa.
- [ ] Mã định danh, tên tương đương và phạm vi dòng xe đúng.
- [ ] Sổ sự kiện và quy tắc sửa đổi hoạt động đúng.
- [ ] Tình huống có các đường thay thế và bằng chứng an toàn.
- [ ] Phần công khai và nội bộ tách biệt.
- [ ] Bộ đánh giá độc lập tái tạo đúng kết quả.
- [ ] Hai lần dựng sạch cho cùng nội dung logic.
- [ ] Bộ kiểm tra bản đóng băng chỉ đọc và đạt.

### Hệ thống truy xuất đầu tiên

- [ ] Đã đo độ chính xác liên kết thực thể.
- [ ] Đường ứng viên có nguồn, thời gian và điều kiện.
- [ ] Bước lọc không đọc đáp án nội bộ.
- [ ] Đo riêng tập ứng viên và tập đã chọn.
- [ ] Có danh sách lỗi cho từng câu hỏi.
- [ ] Hệ thống chạy chỉ với dữ liệu công khai.
- [ ] Thời gian, số lượng và cấu hình được ghi đầy đủ.

### Bản trình diễn tác tử

- [ ] Câu hỏi văn bản chạy từ đầu đến cuối.
- [ ] Câu trả lời có đường giải thích và trích dẫn.
- [ ] Mức rủi ro và hành động an toàn được kiểm tra.
- [ ] Thiếu dữ liệu dẫn tới từ chối hoặc hỏi thêm phù hợp.
- [ ] Bộ nhớ phiên không biến suy đoán thành sự thật.
- [ ] Báo cáo kết quả có mẫu số và cách chia tập rõ.
- [ ] Docker Compose chạy trong môi trường sạch.
- [ ] Giới hạn của hệ thống được ghi rõ.

---

## 15. Kết luận cuối

Bộ dữ liệu hiện tại là một nền tảng mạnh cho:

```text
kiểm tra nguồn
định danh và thời gian
dấu vết bằng chứng
xử lý thiếu dữ liệu và xung đột
cô lập ảnh chụp
đánh giá theo bằng chứng
tái tạo và đóng băng dữ liệu
phân tích lỗi truy xuất
```

Nó chưa chứa dữ liệu cần cho tác tử chẩn đoán xe:

```text
linh kiện và triệu chứng
dạng hỏng và mã lỗi
quan hệ nhân quả
điều kiện vận hành
lịch sử xe
rủi ro và hành động an toàn
đường chẩn đoán chuẩn
hội thoại và bộ nhớ
tập kiểm thử xe khóa kín
```

Trạng thái tổng hợp:

```text
Bộ dữ liệu GSM hiện tại                 ĐẠT
Cách làm có thể dùng lại                MẠNH
Độ phủ dữ liệu chẩn đoán xe             CHƯA CÓ
Bộ đánh giá nhân quả cho xe             CHƯA BẮT ĐẦU
Tác tử và sản phẩm chẩn đoán xe         CHƯA BẮT ĐẦU
Cổng cần thực hiện tiếp theo            VDG01
```

Không sửa hoặc mở rộng trực tiếp `gsm-dev-core-0.2.2`. Hãy xây một họ bộ dữ liệu chẩn đoán xe riêng và dùng các cách kiểm định đã chứng minh trong dự án hiện tại.
