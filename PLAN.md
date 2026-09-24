# Kế hoạch Dự án: GSM Memory AI Agent — Truy xuất & Suy luận Đa phương thức cho Tài xế GSM

> **Dự án:** Scalable Retrieval for Memory-Augmented AI Agents (GSM Memory R&D)  
> **Lĩnh vực:** Hỗ trợ nghiệp vụ, giải đáp chính sách và tra cứu dữ liệu vận hành cho tài xế **GSM (Taxi Xanh SM)**  
> **Tài liệu quy chuẩn nguồn:** [`AGENTS.md`](AGENTS.md), [`docs/01_problem_and_evaluation.md`](docs/01_problem_and_evaluation.md), [`docs/02_synthetic_schema_and_data_design.md`](docs/02_synthetic_schema_and_data_design.md), [`docs/05_dataset_release_spec.md`](docs/05_dataset_release_spec.md), [`reports/benchmark_readiness/phase-b-offline-closure.md`](reports/benchmark_readiness/phase-b-offline-closure.md).

---

## 1. Chủ đề và Bài toán của Dự án

### 1.1. Bối cảnh & Nghiệp vụ
Tài xế và đội ngũ vận hành GSM (Taxi Xanh SM) thường xuyên cần tra cứu:
- **Chính sách & Quy định công ty:** Quy chế thưởng phạt, tiêu chuẩn dịch vụ, điều kiện duy trì hạng tài xế (Bạc, Vàng, Kim Cương), tỷ lệ nhận chuyến (AR), tỷ lệ huỷ chuyến (CR), quy định xử lý sự cố. Các văn bản chính sách này thay đổi liên tục theo thời gian và có phạm vi áp dụng khác nhau.
- **Lịch sử hoạt động của tài xế:** Dữ liệu chuyến đi, thời gian phục vụ, doanh thu ghi nhận, đánh giá sao của khách hàng, vi phạm ghi nhận theo từng ca/ngày/tháng.

### 1.2. Thách thức kỹ thuật
Một câu hỏi như: *"Tuần vừa rồi tôi có 2 chuyến khách hủy do xe hỏng, vậy tỷ lệ hủy chuyến của tôi có bị vượt ngưỡng phạt và mất thưởng hạng Kim Cương theo quy chế mới nhất không?"* đòi hỏi hệ thống:
1. **Đúng phiên bản chính sách theo thời gian:** Không dùng quy chế cũ đã hết hiệu lực hoặc chưa ban hành tại thời điểm tính toán (`valid_time` vs `known_time`).
2. **Đúng danh tính & dữ kiện lịch sử:** Không nhầm lẫn giữa các tài xế, liên kết chính xác các chuyến đi thực tế và sự cố hợp lệ.
3. **Tính toán số học chính xác:** Tính tỷ lệ huỷ chuyến bằng số học hữu tỉ chính xác (rational arithmetic), không làm tròn sai lệch.
4. **Chứng minh có căn cứ (Grounded Proofs):** Mọi kết luận phải dẫn xuất từ tập bằng chứng (Evidence Bundle) gồm điều khoản văn bản + dữ kiện đồ thị, loại bỏ hoàn toàn hiện tượng ảo giác (hallucination).

---

## 2. Kiến trúc Hệ thống Hiện tại

```text
[ Người dùng / Tài xế GSM ]
            │
            ▼  (Câu hỏi nghiệp vụ bằng tiếng Việt)
┌────────────────────────────────────────────────────────────────────────┐
│                        TẦNG TRUY XUẤT HYBRID                           │
│                                                                        │
│   ┌─────────────────────┐   ┌──────────────────────────────────────┐   │
│   │   Document Store    │   │         Temporal KG (Graphiti)       │   │
│   │ (224 bài viết GSM,  │   │  (12 đồ thị snapshot trên Kùzu,      │   │
│   │   1.575 chunks,     │   │   8 nhánh ledger L0 - L_NO_COVERAGE, │   │
│   │   BM25 Retriever)   │   │   chuyến đi, sự cố, chỉ số tài xế)   │   │
│   └──────────┬──────────┘   └──────────────────┬───────────────────┘   │
│              │                                 │                       │
│              └────────────────┬────────────────┘                       │
│                               ▼                                        │
│               ┌───────────────────────────────┐                        │
│               │ Exact Rational Aggregator     │                        │
│               │ (cancel_rate_30d, thresholds) │                        │
│               └───────────────┬───────────────┘                        │
│                               ▼                                        │
│               ┌───────────────────────────────┐                        │
│               │  Hybrid Candidate Merge       │                        │
│               └───────────────┬───────────────┘                        │
│                               ▼                                        │
│               ┌───────────────────────────────┐                        │
│               │  Deterministic Selector       │                        │
│               │  (Token budget & Item cap)    │                        │
│               └───────────────┬───────────────┘                        │
└───────────────────────────────┼────────────────────────────────────────┘
                                │ Evidence Bundle (SelectedEvidence)
                                ▼
┌────────────────────────────────────────────────────────────────────────┐
│               TẦNG SUY LUẬN & AGENT (KẾ HOẠCH TIẾP THEO)               │
│                                                                        │
│               ┌───────────────────────────────┐                        │
│               │  LLM Downstream Reader        │                        │
│               │  (Grounded Reasoning & Cite)  │                        │
│               └───────────────┬───────────────┘                        │
│                               ▼                                        │
│               ┌───────────────────────────────┐                        │
│               │  Giao diện / Chat Assistant   │                        │
│               │  (FastAPI + Web Chat Demo)    │                        │
│               └───────────────────────────────┘                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Hiện trạng Đã Xây dựng Đến Đâu?

### 3.1. Dữ liệu & Đóng băng Bản phát hành (`gsm-dev-core-0.2.2`) — **ĐÃ HOÀN THÀNH (PASS)**
- **Schema v1.1:** Định chuẩn các thực thể và vị từ: `DRIVER`, `TRIP`, `REPORTED_MEASURE`, `INCIDENT`, `DRIVER_PROGRAM`, `POLICY_PUBLICATION`.
- **Thế giới mô phỏng $W_0$:** 8 tài xế, 80 chuyến đi hoàn chỉnh, chuỗi sự kiện sự cố và chỉ số doanh thu/đánh giá.
- **Sổ cái bất biến (Immutable Ledger):** 1 nhánh chuẩn $L_0$ và 7 nhánh counterfactual (`L_NO_OPDAY`, `L_WRONG_DRIVER`, `L_CONFLICT`, `L_RETRACT`, `L_WRONG_WINDOW`, `L_NO_BRIDGE`, `L_NO_COVERAGE`).
- **42 Semantic Cases & Direct Queries:** Bộ 42 câu hỏi tiếng Việt có ground-truth proof đầy đủ (SupportAtoms, EvidenceProof).
- **Freeze Assurance:** Xác thực 636/636 artifacts nguyên vẹn theo chứng chỉ SHA-256 ([`gsm-dev-core-0.2.2-freeze-certificate.json`](reports/data_freeze/gsm-dev-core-0.2.2-freeze-certificate.json)).

### 3.2. Nền tảng Benchmark Retrieval (Phase B.1 Offline Closure) — **ĐÃ HOÀN THÀNH (PASS)**
- **Document Retrieval:** Trích xuất 224 bài viết chính sách GSM thực tế vào [external/policy_green_sm_corpus/](external/policy_green_sm_corpus/) và lập chỉ mục BM25 (1.575 chunks).
- **Temporal KG Mode A:** Tích hợp Graphiti Core 0.30.2 trên Kùzu 0.11.3, nạp thành công 12 đồ thị snapshot độc lập.
- **Hợp nhất và Chọn lọc Bằng chứng:** Chạy kiểm thử thành công toàn bộ 42 queries phát triển.
- **Quy kết lỗi (Candidate vs Selected Attribution):**
  - **30/42** câu hỏi có tập Candidate chứa đủ bằng chứng hợp lệ.
  - **15/42** câu hỏi giữ được đủ bằng chứng sau bước Chọn lọc (Selected).
  - **Phát hiện mấu chốt:** 15 ca bị rơi bằng chứng do chạm giới hạn đóng gói **12 items** dù ngân sách token vẫn còn dư nhiều (< 1.800 tokens).
- **Hạch toán thời gian thực thi:** Median latency tiền suy luận (pre-reader) đạt **85.6 ms/truy vấn**.

---

## 4. Phân Chia Trách Nhiệm Chi Tiết

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        NGƯỜI 1 (ĐÃ HOÀN THÀNH)                         │
│                    Data Engineering & Retrieval Core                   │
│                                                                        │
│  [x] Pipeline dữ liệu synthetic & Immutable Ledger (Schema v1.1)       │
│  [x] Đóng băng và bảo đảm an toàn dữ liệu gsm-dev-core-0.2.2 (DFG)     │
│  [x] Xây dựng Document Chunking & BM25 Retriever (224 bài GSM)         │
│  [x] Graphiti Mode A Ingestion trên Kùzu (12 snapshot graphs)          │
│  [x] Bộ tính toán chính xác Rational Arithmetic (cancel_rate_30d)      │
│  [x] Hybrid Candidate Merging & Baseline Deterministic Selector        │
│  [x] Khép kín Phase B.1 Offline Retrieval Closure & Phân tích quy kết  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Bàn giao toàn bộ nền tảng
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         NGƯỜI 2 (CẦN LÀM TIẾP)                         │
│             Reasoning, Agent Orchestration & Application Layer         │
│                                                                        │
│  [ ] 1. Tối ưu thuật toán Evidence Selection (sửa lỗi rớt ở 12-item)   │
│  [ ] 2. Triển khai Downstream Reader / Reasoning Agent (tích hợp LLM)  │
│  [ ] 3. Đánh giá chất lượng suy luận toàn tuyến (BRG04 / BRG05)        │
│  [ ] 4. Xây dựng API (FastAPI) & Giao diện Demo (Web Chatbot GSM)      │
│  [ ] 5. (Mở rộng) Thử nghiệm Graphiti Mode B & Dense Retriever        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Danh Mục Công Việc Cụ Thể Của Người 2 (Kế Hoạch Hành Động)

### Nhiệm vụ 1: Tối ưu hóa Thuật toán Chọn lọc Bằng chứng (Evidence Selector Optimization)
- **Mục tiêu:** Nâng tỷ lệ Selected-complete từ **15/42** lên tiệm cận **30/42**.
- **File cần chỉnh sửa:** [`src/gsm_memory/retrieval/offline.py`](src/gsm_memory/retrieval/offline.py) và cấu hình chọn lọc [`configs/benchmark/phase-b-baseline.json`](configs/benchmark/phase-b-baseline.json).
- **Hành động:**
  - Nghiên cứu cơ chế nới trần số lượng items (ví dụ từ 12 lên 20–25 items) hoặc áp dụng chiến lược đóng gói ưu tiên đa phương thức (đảm bảo mỗi loại bằng chứng: điều khoản quy chế, sự kiện chuyến đi, chỉ số số học đều có ít nhất 1-2 slots đại diện).
  - Giữ vững quy tắc an toàn: Tuyệt đối không đọc private gold/proof trong quá trình chọn lọc runtime; chỉ sử dụng tín hiệu public từ query và metadata ứng viên.
  - Chạy lại script benchmark đánh giá để chứng minh cải thiện trên bảng `selection_loss_inventory`.

### Nhiệm vụ 2: Xây dựng Tầng Agent Reasoning / Downstream Reader
- **Mục tiêu:** Biến gói bằng chứng `SelectedEvidence` thành câu trả lời giải thích tự nhiên, chính xác, có dẫn nguồn.
- **Thư mục triển khai:** [`src/gsm_memory/agent/`](src/gsm_memory/agent/) (hiện mới chỉ có file khung `__init__.py`).
- **Hành động:**
  - Tạo module `src/gsm_memory/agent/reader.py`:
    - Định dạng prompt đưa gói bằng chứng (`SelectedEvidence`) kèm câu hỏi của tài xế vào LLM (hỗ trợ OpenAI, Gemini hoặc Anthropic thông qua cấu hình linh hoạt).
    - Thiết lập ràng buộc đầu ra nghiêm ngặt (Strict Grounding):
      - Trả lời đúng trọng tâm câu hỏi nghiệp vụ.
      - Trích dẫn chính xác mã điều khoản / tên văn bản GSM (ví dụ: `P154#Điều 5`).
      - Dẫn chứng sự kiện thời gian và số liệu tính toán.
      - Xử lý trường hợp không đủ bằng chứng: Trả về trạng thái `insufficient_evidence` hoặc `unresolved_conflict` khi dữ liệu bị thiếu/xung đột, không tự bịa đặt câu trả lời.

### Nhiệm vụ 3: Đánh giá Toàn Tuyến & Mở Khóa BRG04 / BRG05
- **Mục tiêu:** Đưa toàn bộ benchmark từ trạng thái `PARTIAL` sang kiểm thử suy luận đầy đủ.
- **Hành động:**
  - Tích hợp hàm reader vào bộ đánh giá [`src/gsm_memory/evaluation/runtime.py`](src/gsm_memory/evaluation/runtime.py).
  - Chấm điểm:
    - **Answer Correctness:** So khớp câu trả lời của agent với giá trị kỳ vọng trong 42 test cases.
    - **Citation Precision & Recall:** Tỷ lệ trích dẫn đúng các nguồn tài liệu quy định.
    - **Hallucination Rate:** Tỷ lệ đưa ra thông tin không có trong bằng chứng được cung cấp.
  - Hạch toán chi phí: Số lượng token vào/ra, chi phí API (USD), thời gian sinh câu trả lời (LLM inference latency).

### Nhiệm vụ 4: Xây dựng Ứng Dụng Demo (FastAPI Backend + Web Chat Frontend)
- **Mục tiêu:** Đóng gói thành sản phẩm chạy được cho người dùng/giám khảo trải nghiệm thực tế.
- **Hành động:**
  - **Backend API (FastAPI):**
    - Endpoint `/api/query`: Nhận câu hỏi, mã tài xế (mô phỏng), thời điểm truy vấn.
    - Chạy qua pipeline: Hybrid Retrieval -> Evidence Selection -> Agent Reasoning -> Trả về kết quả JSON kèm danh sách bằng chứng liên kết.
  - **Frontend (Web Chat UI):**
    - Giao diện chat hiện đại, hỗ trợ tiếng Việt.
    - Panel hiển thị bằng chứng (Evidence Inspector): Cho phép người dùng bấm vào xem trích đoạn điều khoản chính sách GSM và đồ thị hành trình chuyến đi liên quan.
    - Huy hiệu mức độ tin cậy (Confidence & Verification Status).

### Nhiệm vụ 5 (Tùy chọn nâng cao): Mở rộng Mode B và Dense Retrieval
- **Graphiti Mode B:** Cấu hình API key để Graphiti tự động trích xuất thực thể và quan hệ từ văn bản thông qua LLM, so sánh chất lượng đồ thị với Mode A.
- **Dense Retriever / Reranker:** Tích hợp mô hình embedding tiếng Việt (như `vietnamese-sbert` hoặc BGE tiếng Việt) nếu môi trường cho phép tải model weights.

---

## 6. Lộ Trình Triển Khai 4 Tuần Cho Người 2

| Tuần | Trọng tâm | Đầu ra mong đợi |
| :--- | :--- | :--- |
| **Tuần 1** | **Tối ưu hóa Evidence Selection** | Nâng tỷ lệ Selected-complete từ 15/42 lên > 25/42; cập nhật báo cáo benchmark. |
| **Tuần 2** | **Xây dựng Agent Reader** | Hoàn thiện module `src/gsm_memory/agent/`; kết nối LLM API; sinh câu trả lời có trích dẫn chuẩn cho 42 test cases. |
| **Tuần 3** | **Đánh giá Benchmark Toàn Tuyến** | Báo cáo BRG04/BRG05 hoàn chỉnh: Answer Accuracy, Hallucination Rate, Token & Latency metrics. |
| **Tuần 4** | **Phát triển Demo & Đóng gói** | Hoàn thành Backend FastAPI + Giao diện Web Chat; Docker Compose chạy toàn bộ ứng dụng. |

---

## 7. Tiêu Chuẩn Nghiệm Thu (Definition of Done) Cho Bản Hoàn Thiện

1. **Hiệu năng chọn lọc bằng chứng:** Tỷ lệ Selected-complete trên bộ 42 benchmark queries đạt tối thiểu **60%** (>= 25/42).
2. **Độ chính xác câu trả lời:** Đạt độ chính xác câu trả lời (Answer Accuracy) tối thiểu **75%** trên các ca có đầy đủ bằng chứng.
3. **Không bịa đặt (Zero Hallucination on Negative Cases):** Khi gặp trường hợp thiếu bằng chứng hoặc quy chế không áp dụng, Agent phải từ chối khẳng định và nêu rõ lý do.
4. **Trích dẫn minh bạch:** 100% câu trả lời khẳng định phải kèm theo liên kết dẫn xuất (link đến điều khoản chính sách hoặc sự kiện chuyến đi cụ thể).
5. **Khả năng chạy độc lập:** Cung cấp lệnh chạy đơn giản (hoặc Docker Compose) khởi chạy trọn vẹn từ Backend truy xuất đến Giao diện hỏi đáp.
