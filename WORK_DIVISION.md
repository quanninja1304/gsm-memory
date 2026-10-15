# Báo Cáo Tổng Hợp & Phân Chia Lại Phần Việc Dự Án GSM Memory

> **Dự án:** Scalable Retrieval for Memory-Augmented AI Agents (GSM Memory R&D)  
> **Lĩnh vực:** Hệ thống Trí tuệ Nhân tạo Hỗ trợ Nghiệp vụ, Tra cứu Quy chế & Dữ liệu Vận hành cho Tài xế **GSM (Taxi Xanh SM)**  
> **Tài liệu quy chuẩn nguồn:** [`AGENTS.md`](file:///e:/gsm-memory/AGENTS.md), [`docs/01_problem_and_evaluation.md`](file:///e:/gsm-memory/docs/01_problem_and_evaluation.md), [`docs/02_synthetic_schema_and_data_design.md`](file:///e:/gsm-memory/docs/02_synthetic_schema_and_data_design.md), [`docs/05_dataset_release_spec.md`](file:///e:/gsm-memory/docs/05_dataset_release_spec.md), [`PLAN.md`](file:///e:/gsm-memory/PLAN.md).  
> **Ngày cập nhật:** 02/10/2026  
> **Phiên bản:** 2.0 (Cập nhật sau tích hợp Phase B, Advanced Retrieval & Agent Reader)

---

## 1. Tóm Tắt Điều Hành & Lý Do Phân Chia Lại

### 1.1. Bối cảnh dự án
Dự án **GSM Memory R&D** tập trung nghiên cứu kiến trúc **Truy xuất và Suy luận Đa phương thức (Hybrid Retrieval & Evidence Construction)** cho AI Agent, giải quyết bài toán nghiệp vụ phức tạp của tài xế Taxi Xanh SM (GSM):
1. **Truy xuất văn bản quy chuẩn:** Tra cứu chính xác điều khoản, chương mục trong 224 bài viết quy chế, chính sách thưởng phạt thay đổi liên tục theo thời gian (`valid_time` vs `known_time`).
2. **Truy xuất đồ thị tri thức lịch sử (Temporal KG):** Truy vấn đúng danh tính tài xế, dữ liệu chuyến đi thực tế, sự cố, khiếu nại, đánh giá sao trên sổ cái bất biến (Immutable Ledger).
3. **Số học hữu tỉ chính xác (Rational Arithmetic):** Tính toán tỷ lệ huỷ chuyến (`cancel_rate_30d`), tỷ lệ nhận chuyến (AR), thưởng/phạt không làm tròn sai số.
4. **Suy luận có căn cứ (Strict Grounding):** Đảm bảo Agent trả lời có dẫn chứng cụ thể, từ chối khẳng định (`insufficient_evidence` / `unresolved_conflict`) khi thiếu dữ liệu, triệt tiêu hoàn toàn ảo giác (zero-hallucination).

### 1.2. Tại sao cần phân chia lại công việc?
Trong tài liệu kế hoạch ban đầu ([`PLAN.md`](file:///e:/gsm-memory/PLAN.md)), công việc được phân chia theo mô hình tuyến tính đơn giản:
* *Người 1:* Làm xong tầng Dữ liệu (Data) & Bộ khung Benchmark Baseline -> Bàn giao và dừng.
* *Người 2:* Nhận bàn giao và làm toàn bộ phần còn lại (Agent Reasoning, Tối ưu hóa, UI Demo...).

Tuy nhiên, trong quá trình thực thi thực tế:
* **Người 1 (Quân - `quanninja1304`)** đã xây dựng một nền tảng dữ liệu cực kỳ đồ sộ, thiết kế toàn bộ hệ thống đặc tả quy chuẩn toán học/logic, xử lý kho 224 văn bản chính sách thật, triển khai pipeline đóng băng dữ liệu DFG, và khép kín giai đoạn Phase B.1 Offline Retrieval Closure.
* **Người 2 (Hóa - `trinhxuanhoa`)** không chỉ làm tầng Agent Reader mà đã chủ động nghiên cứu và triển khai một **Hạ tầng Truy xuất Đa kênh Chuyên sâu (Advanced Retrieval Pipeline)** với hơn 6.700 dòng code: bao gồm phân tích ngôn ngữ tự nhiên tiếng Việt cho câu hỏi nghiệp vụ, bộ lập kế hoạch truy vấn động, vector search với NVIDIA embeddings, duyệt đồ thị tri thức có giới hạn ngân sách (budgeted KG expansion), và hệ thống kiểm thử toàn diện.

Do đó, việc duy trì cách phân chia tuyến tính cũ là **không còn phù hợp và không phản ánh đúng thực tế đóng góp**. Cần thiết lập một **bản phân chia trách nhiệm mới (Work Division v2.0)** dựa trên nguyên tắc:
1. **Minh bạch hóa và tổng hợp đầy đủ** những gì 2 người đã thực sự hoàn thành.
2. **Tách biệt ranh giới chuyên môn (Separation of Concerns):** Phân định quyền sở hữu module rõ ràng, tránh chồng chéo mã nguồn.
3. **Thiết lập lộ trình kế tiếp mạch lạc:** Xác định rõ ai phụ trách phần việc nào trong giai đoạn hoàn thiện benchmark (BRG Gates), xây dựng ứng dụng (FastAPI + Web Chat Demo), và chuẩn bị nghiệm thu.

---

## 2. Tổng Hợp Chi Tiết Khối Lượng Công Việc Đã Hoàn Thành Của 2 Người

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               GSM MEMORY R&D WORKSPACE                                 │
├───────────────────────────────────────────┬────────────────────────────────────────────┤
│           NGƯỜI 1: QUÂN                   │              NGƯỜI 2: HÓA                  │
│          (quanninja1304)                  │            (trinhxuanhoa)                  │
├───────────────────────────────────────────┼────────────────────────────────────────────┤
│  Data Engineering, Core Specifications,   │  Advanced Multi-channel Retrieval,         │
│  Immutable Ledger, Freeze Assurance &     │  Query Intelligence, Agent Reasoning,     │
│  Benchmark Offline Foundation             │  Observability & Integration Testing       │
├───────────────────────────────────────────┼────────────────────────────────────────────┤
│  * 7 Commits chính (54ed66c -> d4338ae)   │  * 3 Commits lớn (717d2b1 -> 9d81180)      │
│  * Sở hữu: src/gsm_memory/data/,          │  * Sở hữu: src/gsm_memory/agent/,          │
│    src/gsm_memory/evaluation/, docs/,     │    src/gsm_memory/retrieval/ (nâng cao),   │
│    reports/data_*, reports/benchmark_*    │    configs/retrieval/, test suites mở rộng │
│  * Xây dựng bộ dữ liệu gsm-dev-core-0.2.2 │  * Bổ sung >6.700 dòng code & 12 test files│
└───────────────────────────────────────────┴────────────────────────────────────────────┘
```

---

### 2.1. Chi tiết phần việc của NGƯỜI 1: Quân (`quanninja1304`)

Người 1 đóng vai trò là **Kiến trúc sư Trưởng về Dữ liệu và Chuẩn mực Đánh giá (Data Architect & Core Benchmark Lead)**, chịu trách nhiệm thiết lập toàn bộ quy tắc nền tảng, mô hình toán học và pipeline dữ liệu đóng băng bất biến.

#### A. Thiết kế Hệ thống Đặc tả Quy chuẩn (Normative Specifications)
* Tác giả bộ 5 tài liệu quy chuẩn tối cao của dự án:
  * [`AGENTS.md`](file:///e:/gsm-memory/AGENTS.md): Định nghĩa quy tắc bất biến, phân định thứ bậc tài liệu chân lý (Source-of-truth order), các ranh giới an toàn nghiêm ngặt (Hard scope boundaries) và nguyên tắc xử lý xung đột.
  * [`docs/01_problem_and_evaluation.md`](file:///e:/gsm-memory/docs/01_problem_and_evaluation.md): Định nghĩa bài toán khoa học, giao diện RuntimeQuery, Evidence Bundle, khung đánh giá 4 cấp độ (L1–L4) và phân loại lỗi hệ thống.
  * [`docs/02_synthetic_schema_and_data_design.md`](file:///e:/gsm-memory/docs/02_synthetic_schema_and_data_design.md): Xây dựng Schema v1.1, định chuẩn mô hình thời gian 2 chiều (`valid_time` và `known_time`), thứ bậc ưu tiên nguồn, 25 kịch bản ca bệnh EX01–EX25.
  * [`docs/05_dataset_release_spec.md`](file:///e:/gsm-memory/docs/05_dataset_release_spec.md): Quy cách phát hành dataset chuẩn, catalog 42 ca kiểm thử, quy trình đóng băng dữ liệu DFG.
  * [`docs/04_benchmark_to_dataset_mapping.md`](file:///e:/gsm-memory/docs/04_benchmark_to_dataset_mapping.md) & [`docs/03_dataset_and_graphiti_baseline_plan.md`](file:///e:/gsm-memory/docs/03_dataset_and_graphiti_baseline_plan.md): Cơ sở phương pháp luận và lộ trình tích hợp Graphiti baseline.
* Biên soạn 7 báo cáo kiến trúc và phân tích chuyên sâu tại [`reports/`](file:///e:/gsm-memory/reports/):
  * [`reports/AI_AGENT_HANDOFF_MEMORY_PROJECT.vi.md`](file:///e:/gsm-memory/reports/AI_AGENT_HANDOFF_MEMORY_PROJECT.vi.md) & [`reports/CORE_RETRIEVAL_DEVELOPMENT_HANDOFF.vi.md`](file:///e:/gsm-memory/reports/CORE_RETRIEVAL_DEVELOPMENT_HANDOFF.vi.md): Tài liệu bàn giao dự án và định hướng phát triển tầng truy xuất cốt lõi.
  * [`reports/data_freeze/gsm-dev-core-0.2.2-bao-cao-dataset-chi-tiet.vi.md`](file:///e:/gsm-memory/reports/data_freeze/gsm-dev-core-0.2.2-bao-cao-dataset-chi-tiet.vi.md) & [`reports/data_freeze/gsm-dev-core-0.2.1-bao-cao-dataset-va-de-xuat-evaluation.vi.md`](file:///e:/gsm-memory/reports/data_freeze/gsm-dev-core-0.2.1-bao-cao-dataset-va-de-xuat-evaluation.vi.md).
  * [`reports/CURRENT_DATASET_COVERAGE_AND_VEHICLE_DATASET_ROADMAP.vi.md`](file:///e:/gsm-memory/reports/CURRENT_DATASET_COVERAGE_AND_VEHICLE_DATASET_ROADMAP.vi.md), [`reports/GRAPH_PERSISTENCE_AND_VIEWER_IMPLEMENTATION_PLAN.vi.md`](file:///e:/gsm-memory/reports/GRAPH_PERSISTENCE_AND_VIEWER_IMPLEMENTATION_PLAN.vi.md), [`reports/VEHICLE_CAUSAL_AGENT_PLAN_GAP_ANALYSIS.vi.md`](file:///e:/gsm-memory/reports/VEHICLE_CAUSAL_AGENT_PLAN_GAP_ANALYSIS.vi.md).

#### B. Pipeline Kỹ thuật Dữ liệu & Đóng băng Dữ liệu (Data Engineering & DFG Pipeline)
* Xây dựng trọn vẹn package [`src/gsm_memory/data/`](file:///e:/gsm-memory/src/gsm_memory/data/):
  * [`contracts.py`](file:///e:/gsm-memory/src/gsm_memory/data/contracts.py), [`primitives.py`](file:///e:/gsm-memory/src/gsm_memory/data/primitives.py), [`sources.py`](file:///e:/gsm-memory/src/gsm_memory/data/sources.py), [`catalog.py`](file:///e:/gsm-memory/src/gsm_memory/data/catalog.py): Mô hình hóa thực thể nghiệp vụ GSM: `DRIVER`, `TRIP`, `INCIDENT`, `REPORTED_MEASURE`, `DRIVER_PROGRAM`, `POLICY_PUBLICATION`.
  * [`synthetic.py`](file:///e:/gsm-memory/src/gsm_memory/data/synthetic.py): Trình sinh thế giới mô phỏng $W_0$ gồm 8 tài xế, 80 chuyến đi hoàn chỉnh, chuỗi sự kiện và chỉ số doanh thu/đánh giá.
  * [`ledger.py`](file:///e:/gsm-memory/src/gsm_memory/data/ledger.py): Cơ chế Sổ cái bất biến (Immutable Ledger) với các thao tác `assert`, `replace`, `retract`, sinh 8 nhánh độc lập ($L_0$ và 7 nhánh counterfactual: `L_NO_OPDAY`, `L_WRONG_DRIVER`, `L_CONFLICT`, `L_RETRACT`, `L_WRONG_WINDOW`, `L_NO_BRIDGE`, `L_NO_COVERAGE`).
  * [`locators.py`](file:///e:/gsm-memory/src/gsm_memory/data/locators.py), [`provenance.py`](file:///e:/gsm-memory/src/gsm_memory/data/provenance.py), [`coverage.py`](file:///e:/gsm-memory/src/gsm_memory/data/coverage.py): Kiểm soát định vị nguồn và nguồn gốc dữ liệu.
  * [`build.py`](file:///e:/gsm-memory/src/gsm_memory/data/build.py), [`validation.py`](file:///e:/gsm-memory/src/gsm_memory/data/validation.py), [`frozen.py`](file:///e:/gsm-memory/src/gsm_memory/data/frozen.py), [`cli.py`](file:///e:/gsm-memory/src/gsm_memory/data/cli.py): Hệ thống kiểm tra đóng băng DFG01–DFG06, xác thực chữ ký SHA-256 cho **636/636 artifacts** ([`gsm-dev-core-0.2.2-freeze-certificate.json`](file:///e:/gsm-memory/reports/data_freeze/gsm-dev-core-0.2.2-freeze-certificate.json)).
* Quản lý tiến trình phát hành dữ liệu: Phát hành bản `0.2` -> Kiểm toán phát hiện rò rỉ query alias -> Thay thế bằng bản `0.2.1` -> Hoàn thiện bản sửa lỗi toàn diện `gsm-dev-core-0.2.2` khép kín provenance locators.

#### C. Xử lý & Chuẩn Hóa Kho Văn Bản Quy Chế Thực Tế (Real Policy Corpus)
* Quản lý kho văn bản gốc [`data/raw/archives/policy_green_sm_source.zip`](file:///e:/gsm-memory/data/raw/archives/policy_green_sm_source.zip) (SHA-256: `cfe9e4555dbedf81396004c7a7d0ace52dcbb1deb758110c4aded3b6741ba9c9`).
* Trích xuất và chuẩn hóa 224 bài viết chính sách GSM thực tế tại [`external/policy_green_sm_corpus/`](file:///e:/gsm-memory/external/policy_green_sm_corpus/) (chuẩn hóa ngắt dòng CRLF -> LF, mã hóa UTF-8, tính toán offset ký tự `[start, end)` chính xác).
* Thiết lập 2 profile corpus: `debug_core@1` (6 tài liệu audit phục vụ dev nhanh) và `retrieval_full@1` (224 bài viết hoàn chỉnh).

#### D. Nền Tảng Đánh Giá Độc Lập & Số Học Hữu Tỉ (Evaluation Oracle & Exact Math)
* Xây dựng trọn vẹn package [`src/gsm_memory/evaluation/`](file:///e:/gsm-memory/src/gsm_memory/evaluation/):
  * [`formulas.py`](file:///e:/gsm-memory/src/gsm_memory/evaluation/formulas.py): Thư viện tính toán số học hữu tỉ chính xác tuyệt đối (exact rational arithmetic), không dùng số thực dấu phẩy động (float) cho `cancel_rate_30d` và các ngưỡng thưởng phạt (ví dụ: $AR < 1/2$, $Rating > 97/20$).
  * [`oracle.py`](file:///e:/gsm-memory/src/gsm_memory/evaluation/oracle.py): Xây dựng tập chứng cứ vàng (SupportAtoms, EvidenceProof, GoldSupportLink) độc lập với hệ thống truy xuất.
  * [`independent.py`](file:///e:/gsm-memory/src/gsm_memory/evaluation/independent.py), [`assurance.py`](file:///e:/gsm-memory/src/gsm_memory/evaluation/assurance.py): Bộ công cụ kiểm định độc lập, đảm bảo bằng chứng công khai không phụ thuộc vào tri thức ngầm (Anti-leakage assurance).
  * [`runtime.py`](file:///e:/gsm-memory/src/gsm_memory/evaluation/runtime.py) (phần nền tảng): Logic tính toán candidate-versus-selected attribution.

#### E. Khép Kín Giai Đoạn Phase B.1 Offline Retrieval Closure
* Xây dựng tầng truy xuất cơ sở:
  * [`src/gsm_memory/retrieval/documents.py`](file:///e:/gsm-memory/src/gsm_memory/retrieval/documents.py): Chia 224 văn bản chính sách thành 1.575 chunks chuẩn.
  * [`src/gsm_memory/retrieval/bm25.py`](file:///e:/gsm-memory/src/gsm_memory/retrieval/bm25.py): Trình lập chỉ mục và truy xuất từ khóa BM25 tiếng Việt.
  * [`src/gsm_memory/adapters/graphiti.py`](file:///e:/gsm-memory/src/gsm_memory/adapters/graphiti.py) & [`graphiti_baseline.py`](file:///e:/gsm-memory/src/gsm_memory/adapters/graphiti_baseline.py): Tích hợp Graphiti Mode A trên Kùzu 0.11.3 nạp 12 đồ thị snapshot độc lập; bộ adapter cho baseline Neo4j.
  * Bộ hợp nhất hybrid ban đầu và chọn lọc bằng chứng cơ sở trong [`src/gsm_memory/retrieval/offline.py`](file:///e:/gsm-memory/src/gsm_memory/retrieval/offline.py).
* Công bố báo cáo khoa học Phase B.1 ([`reports/benchmark_readiness/phase-b-offline-closure.md`](file:///e:/gsm-memory/reports/benchmark_readiness/phase-b-offline-closure.md)):
  * Đánh giá toàn bộ 42 truy vấn chuẩn.
  * Phát hiện điểm nghẽn nghiêm trọng: **15/42 ca bị mất bằng chứng hợp lệ** ở bước Chọn lọc (Selected) do chạm ngưỡng cứng **12 items** dù ngân sách token vẫn còn dư nhiều (< 1.800 tokens).
  * Đo đạc độ trễ tiền suy luận: Median latency đạt **85.6 ms/truy vấn**.

---

### 2.2. Chi tiết phần việc của NGƯỜI 2: Hóa (`trinhxuanhoa`)

Người 2 đóng vai trò là **Trưởng Nhóm Truy Xuất Thông Minh & Tầng Ứng Dụng Agent (Intelligent Retrieval & Agent Systems Lead)**, chịu trách nhiệm hiện thực hóa tầng suy luận Agent, giải quyết triệt để điểm nghẽn truy xuất của Phase B.1 và phát triển hạ tầng kiểm thử quy mô lớn.

#### A. Hoạch Định Kế Hoạch Hành Động & Khung Triển Khai (Action Planning)
* Tác giả tài liệu [`PLAN.md`](file:///e:/gsm-memory/PLAN.md) (194 dòng):
  * Định hình toàn bộ bức tranh nghiệp vụ thực tế của tài xế GSM, các thách thức kỹ thuật cốt lõi (Temporal validity, Identity binding, Exact arithmetic, Grounded proofs).
  * Vẽ sơ đồ kiến trúc 2 tầng (Hybrid Retrieval Layer -> Reasoning & Agent Layer).
  * Đề xuất kế hoạch hành động 5 nhiệm vụ chi tiết và tiêu chuẩn nghiệm thu (Definition of Done) định lượng cho sản phẩm hoàn thiện.

#### B. Tầng Suy Luận Agent & Mô Hình Ngôn Ngữ Lớn (Downstream Reasoning Agent)
* Xây dựng trọn vẹn package [`src/gsm_memory/agent/`](file:///e:/gsm-memory/src/gsm_memory/agent/):
  * [`src/gsm_memory/agent/reader.py`](file:///e:/gsm-memory/src/gsm_memory/agent/reader.py) (>300 dòng code):
    * Lớp `DownstreamReader`: Tích hợp gọi mô hình ngôn ngữ lớn (hỗ trợ OpenAI, Anthropic, Gemini thông qua OpenRouter API).
    * Prompt Engineering chuyên biệt cho nghiệp vụ GSM: Chuẩn hóa gói `SelectedEvidence` thành context có cấu trúc nghiêm ngặt (tách biệt phần Điều khoản văn bản, Lịch sử chuyến đi, Sự cố và Số liệu tính toán).
    * **Ràng buộc suy luận nghiêm ngặt (Strict Grounding):** Bắt buộc câu trả lời phải trích dẫn trực tiếp mã điều khoản văn bản (ví dụ: `P154#Điều 5`), dẫn chứng thời gian sự kiện, số liệu hữu tỉ.
    * **Xử lý ca biên âm (Negative cases handling):** Tự động phát hiện và phản hồi `insufficient_evidence` hoặc `unresolved_conflict` khi bằng chứng bị thiếu hoặc mâu thuẫn, triệt tiêu ảo giác (zero hallucination).
    * **Khả năng quan sát thời gian thực (Observability):** Tích hợp sâu với **Langfuse** để ghi nhận toàn bộ trace suy luận, latency LLM, số token vào/ra và chi phí truy vấn.
    * Hỗ trợ trích xuất đầu ra JSON có cấu trúc (Structured Citation Extraction).

#### C. Trí Tuệ Phân Tích Truy Vấn & Lập Kế Hoạch Động (Query Intelligence & Dynamic Planning)
* Module [`src/gsm_memory/retrieval/query_analysis.py`](file:///e:/gsm-memory/src/gsm_memory/retrieval/query_analysis.py) (**782 dòng code**):
  * Bộ phân tích cú pháp và ngữ nghĩa chuyên sâu cho câu hỏi tiếng Việt của tài xế Taxi Xanh SM.
  * Phân loại ý định thông minh (Intent Classification): Phân biệt rõ các nhóm câu hỏi về chính sách thưởng/phạt, duy trì hạng (Bạc, Vàng, Kim Cương), tỷ lệ nhận chuyến (AR), tỷ lệ hủy chuyến (CR), xử lý sự cố khách hủy do hỏng xe, khiếu nại đánh giá sao, đối chiếu doanh thu.
  * Trích xuất thực thể nghiệp vụ (Entity & Keyword Extraction): Tự động nhận diện Driver ID (`D1`–`D8`), Trip ID, khung thời gian (tuần trước, tháng trước, 30 ngày gần nhất), loại quy chế.
  * Phát hiện phạm vi thời gian (Temporal Scope Detection): Tách biệt thời điểm diễn ra sự kiện (`event_time`) và thời điểm quy định có hiệu lực (`valid_time`/`known_time`).
* Module [`src/gsm_memory/retrieval/planner.py`](file:///e:/gsm-memory/src/gsm_memory/retrieval/planner.py) (**490 dòng code**):
  * Lớp `RetrievalPlanner`: Sinh kế hoạch truy xuất động (`QueryPlan`) cho từng câu hỏi cụ thể thay vì chạy mù quáng mọi kênh.
  * Lựa chọn chiến lược tối ưu: Chỉ tra cứu văn bản (Doc-only), chỉ tra cứu đồ thị (KG-only), kết hợp đa luồng (Hybrid), hoặc kích hoạt công cụ tính toán số học hữu tỉ (`cancel_rate_30d`).
  * Phân bổ ngân sách truy xuất thích ứng (Adaptive Budget Allocation).
* Module [`src/gsm_memory/retrieval/routing.py`](file:///e:/gsm-memory/src/gsm_memory/retrieval/routing.py) (118 dòng code): Định tuyến câu hỏi con vào các retrieval channels chuyên biệt.
* Module [`src/gsm_memory/retrieval/config.py`](file:///e:/gsm-memory/src/gsm_memory/retrieval/config.py) & [`configs/retrieval/retrieval_v1.json`](file:///e:/gsm-memory/configs/retrieval/retrieval_v1.json): Quản lý tập trung các tham số truy xuất (trọng số, ngưỡng tương đồng, trần ngân sách).

#### D. Nâng Cấp Hệ Thống Truy Xuất Đa Kênh (Advanced Multi-Channel Retrieval)
* **Truy xuất Vector Ngữ nghĩa & NVIDIA Embeddings:**
  * [`src/gsm_memory/retrieval/dense.py`](file:///e:/gsm-memory/src/gsm_memory/retrieval/dense.py) (124 dòng): Quản lý chỉ mục vector ngữ nghĩa, tìm kiếm độ tương đồng cosine trên không gian vector.
  * [`src/gsm_memory/retrieval/nvidia_embed.py`](file:///e:/gsm-memory/src/gsm_memory/retrieval/nvidia_embed.py) (98 dòng): Client kết nối NVIDIA API sinh embedding chất lượng cao, hỗ trợ xử lý bất đồng bộ (async) và gom cụm (batching).
  * [`src/gsm_memory/retrieval/semantic_seed.py`](file:///e:/gsm-memory/src/gsm_memory/retrieval/semantic_seed.py) (508 dòng): Tìm kiếm hạt giống ngữ nghĩa (Semantic Seeding) để định vị nhanh các nút neo thực thể và điều khoản chính sách cốt lõi.
  * [`src/gsm_memory/retrieval/rerank.py`](file:///e:/gsm-memory/src/gsm_memory/retrieval/rerank.py) (84 dòng): Mô-đun tái xếp hạng (Cross-encoder reranking) nhằm tối ưu độ chính xác của tập ứng viên văn bản.
  * [`src/gsm_memory/retrieval/fusion.py`](file:///e:/gsm-memory/src/gsm_memory/retrieval/fusion.py) (19 dòng): Thuật toán hợp nhất thứ hạng tương hỗ (Reciprocal Rank Fusion - RRF) kết hợp điểm số BM25 và Dense.
* **Duyệt Đồ Thị Tri Thức Có Kiểm Soát Ngân Sách (Temporal KG Budgeted Traversal):**
  * [`src/gsm_memory/retrieval/kg.py`](file:///e:/gsm-memory/src/gsm_memory/retrieval/kg.py) (**565 dòng code**): Thuật toán duyệt đồ thị tri thức có giới hạn ngân sách, mở rộng lân cận 1-hop / 2-hop từ các nút neo thực thể, lọc cạnh theo thời gian hợp lệ và nguồn có thẩm quyền.
  * Mở rộng [`src/gsm_memory/adapters/graphiti.py`](file:///e:/gsm-memory/src/gsm_memory/adapters/graphiti.py): Tích hợp hỗ trợ duyệt đồ thị theo ngân sách và khớp thực thể với danh mục chuẩn.
* **Tối Ưu Hóa Bộ Chọn Lọc Bằng Chứng (Evidence Selector Optimization):**
  * Nâng cấp sâu [`src/gsm_memory/retrieval/offline.py`](file:///e:/gsm-memory/src/gsm_memory/retrieval/offline.py) (>500 dòng code mới): Thiết kế cơ chế phân bổ quota đa phương thức (đảm bảo ít nhất 1-2 slot đại diện cho văn bản quy chế, sự kiện lịch sử chuyến đi và chỉ số tính toán), giải quyết triệt để nút thắt rớt bằng chứng do giới hạn 12-item của bản baseline cũ.

#### E. Hạ Tầng Kiểm Thử & Đảm Bảo Chất Lượng Toàn Diện (Testing Infrastructure)
* Xây dựng **12 tệp kiểm thử mới với hơn 2.500 dòng code**:
  * [`tests/fixtures/mock_data.py`](file:///e:/gsm-memory/tests/fixtures/mock_data.py) (471 dòng): Bộ fixture giả lập dữ liệu chuẩn xác, cho phép chạy test offline hoàn toàn mà không phụ thuộc API ngoài.
  * Unit tests cho tầng Retrieval:
    * [`tests/unit/retrieval/test_retrieval_planner.py`](file:///e:/gsm-memory/tests/unit/retrieval/test_retrieval_planner.py) (310 dòng)
    * [`tests/unit/retrieval/test_query_plan_and_config.py`](file:///e:/gsm-memory/tests/unit/retrieval/test_query_plan_and_config.py) (463 dòng)
    * [`tests/unit/retrieval/test_query_analysis.py`](file:///e:/gsm-memory/tests/unit/retrieval/test_query_analysis.py) (105 dòng)
    * [`tests/unit/retrieval/test_kg_budgeted_expansion.py`](file:///e:/gsm-memory/tests/unit/retrieval/test_kg_budgeted_expansion.py) (384 dòng)
    * [`tests/unit/retrieval/test_dense_rerank_pipeline.py`](file:///e:/gsm-memory/tests/unit/retrieval/test_dense_rerank_pipeline.py) (126 dòng)
    * [`tests/unit/retrieval/test_parallel_execution.py`](file:///e:/gsm-memory/tests/unit/retrieval/test_parallel_execution.py) (227 dòng)
    * [`tests/unit/retrieval/test_computation_semantics.py`](file:///e:/gsm-memory/tests/unit/retrieval/test_computation_semantics.py) (257 dòng)
    * [`tests/unit/retrieval/test_candidate_vs_selected_evaluation.py`](file:///e:/gsm-memory/tests/unit/retrieval/test_candidate_vs_selected_evaluation.py) (190 dòng)
  * Unit & Integration tests cho tầng Agent:
    * [`tests/unit/agent/test_reader.py`](file:///e:/gsm-memory/tests/unit/agent/test_reader.py) (75 dòng)
    * [`tests/integration/agent/test_langfuse_live_hybrid.py`](file:///e:/gsm-memory/tests/integration/agent/test_langfuse_live_hybrid.py) (240 dòng)
    * [`tests/integration/agent/test_openrouter_live.py`](file:///e:/gsm-memory/tests/integration/agent/test_openrouter_live.py) (58 dòng)
  * Integration tests về tính độc lập và an toàn ranh giới:
    * [`tests/integration/retrieval/test_boundary_runtime.py`](file:///e:/gsm-memory/tests/integration/retrieval/test_boundary_runtime.py) (115 dòng)
    * [`tests/integration/retrieval/test_nvidia_semantic_seed.py`](file:///e:/gsm-memory/tests/integration/retrieval/test_nvidia_semantic_seed.py) (67 dòng)

---

### 2.3. Bảng Đối Sánh Đóng Góp Chi Tiết (Master Contribution Matrix)

| Lĩnh vực / Thành phần | Module / Artifacts phụ trách | Người 1 (Quân) | Người 2 (Hóa) | Trạng thái hiện tại |
| :--- | :--- | :---: | :---: | :--- |
| **Đặc tả & Kiến trúc** | `AGENTS.md`, `docs/01-05`, `PLAN.md`, `reports/*` | **Chính** (Quy chuẩn, Schema, Handoff) | **Chính** (Kế hoạch hành động, Agent design) | Hoàn thành xuất sắc |
| **Dữ liệu Mô phỏng** | `src/gsm_memory/data/synthetic.py`, `ledger.py`, `catalog.py` | **100%** ($W_0$, 80 chuyến đi, 8 ledger branches) | - | Hoàn thành, Đóng băng |
| **Đóng băng & Bảo đảm** | `src/gsm_memory/data/validation.py`, `frozen.py`, `cli.py` | **100%** (DFG01–DFG06, 636 artifacts) | - | Hoàn thành (Release 0.2.2) |
| **Kho Chính Sách Thật** | `external/policy_green_sm_corpus/`, `data/raw/` | **100%** (224 bài GSM, chuẩn hóa LF/UTF-8) | - | Hoàn thành |
| **Oracle & Số Học Chuẩn**| `src/gsm_memory/evaluation/formulas.py`, `oracle.py` | **100%** (Rational math, SupportAtoms, Proofs) | - | Hoàn thành |
| **Graphiti Căn Bản** | `src/gsm_memory/adapters/graphiti*.py`, Kùzu DB | **Chính** (Mode A Ingestion, 12 snapshots) | Phối hợp (KG expansion adapter) | Hoàn thành Mode A |
| **BM25 & Chunking** | `src/gsm_memory/retrieval/documents.py`, `bm25.py` | **100%** (1.575 chunks, BM25 tokenizer) | - | Hoàn thành |
| **Phân Tích Truy Vấn** | `src/gsm_memory/retrieval/query_analysis.py` | - | **100%** (782 dòng tiếng Việt NLP, Intent, Entity) | Hoàn thành |
| **Lập Kế Hoạch Truy Vấn**| `src/gsm_memory/retrieval/planner.py`, `routing.py`, `config.py` | - | **100%** (QueryPlan, Adaptive Routing) | Hoàn thành |
| **Dense & Embeddings** | `src/gsm_memory/retrieval/dense.py`, `nvidia_embed.py`, `fusion.py` | - | **100%** (NVIDIA API, Cosine, RRF) | Hoàn thành |
| **Duyệt Đồ Thị Ngân Sách**| `src/gsm_memory/retrieval/kg.py`, `semantic_seed.py` | - | **100%** (Budgeted Expansion, Anchor Nodes) | Hoàn thành |
| **Tối Ưu Hóa Selection**| `src/gsm_memory/retrieval/offline.py` | Khởi tạo baseline (Phát hiện lỗi 12-item) | **Nâng cấp** (Đa phương thức quota, sửa lỗi rớt) | Đã tối ưu thuật toán |
| **Downstream Reader** | `src/gsm_memory/agent/reader.py` | - | **100%** (LLM OpenRouter, Strict Grounding) | Hoàn thành |
| **Observability** | Langfuse Tracing, JSON citation output | - | **100%** (Tích hợp đo latency, token, cost) | Hoàn thành |
| **Hệ Thống Kiểm Thử** | `tests/unit/`, `tests/conformance/`, `tests/integration/` | Viết Data tests & Baseline tests (9 tests) | **Viết 12 test files mới** (>130 unit/integration tests) | 139 passed tests |

---

## 3. Phân Chia Lại Trách Nhiệm & Ranh Giới Chuyên Trách (Work Division v2.0)

Để tránh chồng chéo mã nguồn và tối ưu hóa thế mạnh của từng người, hệ thống được phân chia lại thành **2 Trụ cột Độc lập có Ranh giới rõ ràng (Clean Separation of Concerns)**:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              PHÂN ĐỊNH TRÁCH NHIỆM V2.0                                │
├───────────────────────────────────────────┬────────────────────────────────────────────┤
│         TRỤ CỘT 1: NGƯỜI 1 (QUÂN)         │         TRỤ CỘT 2: NGƯỜI 2 (HÓA)           │
│    Data Engineering, Core Benchmark &     │  Intelligent Retrieval, Agent Reasoning &  │
│            System Governance              │             Application Layer              │
├───────────────────────────────────────────┼────────────────────────────────────────────┤
│  * Tầng Dữ liệu Bất biến (Data & Ledgers) │  * Tầng Phân tích Ngôn ngữ Tự nhiên &      │
│  * Bộ Chân lý Vàng & Số học Hữu tỉ        │    Lập kế hoạch Truy vấn (Query Intel)     │
│    (Oracle, Proofs, Exact Rational Math)  │  * Tầng Truy xuất Đa kênh Nâng cao         │
│  * Khung Đánh giá Benchmark Chuẩn         │    (Dense, NVIDIA Embed, Rerank, KG Expand)│
│    (BRG Gates, Attribution Metrics)       │  * Tầng Suy luận Agent (LLM Reader, Prompt,│
│  * Quản trị Nguồn & Tính Toàn vẹn Release │    Strict Grounding, Langfuse Trace)       │
│  * Cơ sở Dữ liệu Đồ thị & Mode B Native   │  * Tầng Ứng dụng & Giao diện               │
│    (Kùzu, Neo4j Persistence Baseline)     │    (FastAPI Backend, Web Chatbot GSM UI)   │
└───────────────────────────────────────────┴────────────────────────────────────────────┘
```

---

### 3.1. Ranh giới chuyên trách của Người 1 (Quân)
* **Định vị vai trò:** Người gác cổng dữ liệu và chuẩn mực khoa học (Data & Scientific Benchmark Gatekeeper).
* **Phạm vi quản lý trực tiếp:**
  1. `docs/`: Duy trì tính nhất quán của bộ tài liệu đặc tả, kiểm soát việc mở rộng schema (nếu có).
  2. `src/gsm_memory/data/`: Tuyệt đối độc quyền quản lý các file sinh dữ liệu, ledger và đóng băng release. Người 2 không sửa đổi mã nguồn trong thư mục này để tránh vi phạm chứng chỉ freeze.
  3. `src/gsm_memory/evaluation/`: Quản lý các công thức số học hữu tỉ (`formulas.py`), bộ chân lý vàng (`oracle.py`), và kiểm toán tính toàn vẹn độc lập (`assurance.py`, `independent.py`).
  4. `src/gsm_memory/adapters/graphiti_baseline.py` & Persistent Neo4j: Chịu trách nhiệm về hạ tầng đồ thị, cơ chế snapshot isolation và cấu hình Graphiti Mode B native (khi có provider credentials).
  5. Giám sát các cổng chất lượng Benchmark: `BRG01` (Data/Specs Pass), `BRG02` (Mode A/B Ingestion Pass), `BRG03` (Multi-modal Retrieval Pass).

### 3.2. Ranh giới chuyên trách của Người 2 (Hóa)
* **Định vị vai trò:** Kiến trúc sư Truy xuất Thông minh và Hệ thống Ứng dụng AI Agent (AI Retrieval & Application Architect).
* **Phạm vi quản lý trực tiếp:**
  1. `src/gsm_memory/retrieval/`: Toàn quyền tối ưu hóa bộ phân tích câu hỏi (`query_analysis.py`), bộ lập kế hoạch (`planner.py`), bộ định tuyến (`routing.py`), bộ nhúng ngữ nghĩa (`dense.py`, `nvidia_embed.py`, `semantic_seed.py`), duyệt đồ thị (`kg.py`), và bộ chọn lọc bằng chứng nâng cao (`offline.py`).
  2. `src/gsm_memory/agent/`: Toàn quyền phát triển, tinh chỉnh prompt và tối ưu hóa chất lượng câu trả lời của `DownstreamReader`, cơ chế chống ảo giác và tích hợp Langfuse.
  3. `configs/retrieval/`: Tinh chỉnh trọng số, tham số cấu hình truy xuất tối ưu.
  4. Bộ kiểm thử chức năng: Duy trì và mở rộng hệ thống test phong phú trong `tests/unit/retrieval/`, `tests/unit/agent/`, `tests/integration/`.
  5. Tầng Ứng dụng Người dùng: Xây dựng FastAPI service và Web Chat Frontend phục vụ demo thực tế cho tài xế GSM.
  6. Đo lường và tối ưu hóa các cổng: `BRG04` (Reasoning & Answer Accuracy), `BRG05` (Latency & Cost Instrumentation).

---

### 3.3. Ma trận Phân Công Trách Nhiệm (RACI Matrix)

* **R (Responsible):** Người trực tiếp thực hiện công việc.
* **A (Accountable):** Người chịu trách nhiệm cuối cùng về kết quả và chất lượng.
* **C (Consulted):** Người được tham vấn ý kiến trước khi triển khai.
* **I (Informed):** Người được thông báo sau khi hoàn thành.

| Gói Công Việc / Thư Mục Mã Nguồn | Người 1 (Quân) | Người 2 (Hóa) | Ghi chú Phối hợp |
| :--- | :---: | :---: | :--- |
| **Quy chuẩn & Schema (`docs/`, `AGENTS.md`)** | **A / R** | C / I | Người 1 quyết định; Người 2 góp ý từ góc độ truy xuất thực tế |
| **Dữ liệu & Sổ cái Bất biến (`src/.../data/`)** | **A / R** | I | Độc quyền Người 1; Người 2 chỉ đọc qua API public |
| **Oracle Bằng chứng & Số học (`src/.../evaluation/`)** | **A / R** | C | Người 1 bảo đảm tính đúng đắn; Người 2 gọi hàm đối soát |
| **BM25 & Chunking tài liệu GSM cơ sở** | **A / R** | C / I | Người 1 đã bàn giao ổn định |
| **Phân tích Query Tiếng Việt & Router (`query_analysis.py`)** | I | **A / R** | Độc quyền Người 2 phát triển |
| **Lập Kế hoạch Truy xuất Động (`planner.py`)** | C | **A / R** | Người 2 phát triển chính |
| **Dense Vector & NVIDIA Embeddings** | I | **A / R** | Người 2 phụ trách kết nối API & chỉ mục vector |
| **Duyệt Đồ Thị Theo Ngân Sách (`kg.py`)** | C | **A / R** | Người 2 cài đặt thuật toán duyệt trên đồ thị của Người 1 |
| **Tối Ưu Bộ Chọn Lọc Bằng Chứng (`offline.py`)** | C | **A / R** | Người 2 tối ưu quota đa phương thức; Người 1 audit không leak |
| **Downstream Reader & LLM Agent (`src/.../agent/`)** | C | **A / R** | Người 2 phụ trách prompt, grounding và OpenRouter/Langfuse |
| **Hạ Tầng Graphiti Mode B & Neo4j Bền Vững** | **A / R** | C | Người 1 triển khai persistence và baseline Mode B |
| **Benchmark Cổng BRG01 – BRG03 (Data/Retrieval)** | **A / R** | R | Phối hợp chạy đánh giá toàn diện |
| **Benchmark Cổng BRG04 – BRG05 (Reasoning/Latency/Cost)**| C | **A / R** | Người 2 chủ trì đo lường độ chính xác và chi phí của LLM |
| **FastAPI Backend & Giao Diện Web Chat Demo** | I | **A / R** | Người 2 xây dựng toàn bộ ứng dụng người dùng |
| **Báo Cáo Tổng Kết Khoa Học & Bàn Giao Dự Án** | **A / R** | **A / R** | Cả 2 cùng biên soạn và nghiệm thu |

---

## 4. Kế Hoạch Triển Khai Tiếp Theo Cho 2 Người (Roadmap to Final Delivery)

Để đưa dự án từ trạng thái hiện tại (Offline Retrieval Foundation & Agent Reader đã sẵn sàng) đến sản phẩm hoàn chỉnh có thể nghiệm thu và demo xuất sắc, kế hoạch tiếp theo được phân công cụ thể như sau:

### 4.1. Phần việc tiếp theo của NGƯỜI 1 (Quân)

1. **Khép kín Benchmark Readiness Gates (BRG01 – BRG03):**
   * Chạy lại script benchmark tích hợp với bộ `offline.py` đã nâng cấp của Người 2 trên toàn bộ 42 queries phát triển.
   * Xác nhận tỷ lệ Candidate Complete và Selected Complete chính thức sau khi tối ưu hóa bộ chọn lọc.
   * Cập nhật báo cáo nghiệm thu [`reports/benchmark_readiness/phase-b-offline-closure.md`](file:///e:/gsm-memory/reports/benchmark_readiness/phase-b-offline-closure.md).
2. **Triển khai Graphiti Mode B Native & Neo4j Persistence:**
   * Cấu hình LLM/Neo4j cho [`src/gsm_memory/adapters/graphiti_baseline.py`](file:///e:/gsm-memory/src/gsm_memory/adapters/graphiti_baseline.py) để chạy thử nghiệm Graphiti Mode B (trích xuất thực thể/quan hệ tự động bằng LLM thay vì nạp cấu trúc Mode A).
   * Đo lường sự khác biệt về độ đầy đủ của đồ thị (Graph Completeness) giữa Mode A và Mode B.
   * Hiện thực hóa kế hoạch lưu trữ bền vững theo [`reports/GRAPH_PERSISTENCE_AND_VIEWER_IMPLEMENTATION_PLAN.vi.md`](file:///e:/gsm-memory/reports/GRAPH_PERSISTENCE_AND_VIEWER_IMPLEMENTATION_PLAN.vi.md).
3. **Mở rộng Dữ liệu Vận hành Thực tế (Data Expansion Roadmap):**
   * Chuẩn bị kịch bản mở rộng theo [`reports/CURRENT_DATASET_COVERAGE_AND_VEHICLE_DATASET_ROADMAP.vi.md`](file:///e:/gsm-memory/reports/CURRENT_DATASET_COVERAGE_AND_VEHICLE_DATASET_ROADMAP.vi.md): Bổ sung telemetry xe điện (trạng thái pin SoC, lịch sử trạm sạc VinFast, cảnh báo kỹ thuật xe taxi GSM).
4. **Bảo đảm Chuẩn mực Khoa học & Kiểm soát Release:**
   * Giữ vững tính bất biến tuyệt đối của bộ dữ liệu `gsm-dev-core-0.2.2`.
   * Thẩm định độc lập bộ prompt và evidence selection của Người 2 để cam kết không có hiện tượng rò rỉ thông tin ẩn (Private Gold Leakage) vào runtime.

---

### 4.2. Phần việc tiếp theo của NGƯỜI 2 (Hòa)

1. **Đánh Giá Chất Lượng Suy Luận Toàn Tuyến & Mở Khóa BRG04 / BRG05:**
   * Chạy đánh giá toàn bộ 42 benchmark queries qua `DownstreamReader`.
   * Đo đạc 4 chỉ số cốt lõi:
     * **Answer Accuracy:** Tỷ lệ câu trả lời khớp với giá trị kỳ vọng (Expected Answer).
     * **Citation Precision & Recall:** Tỷ lệ trích dẫn đúng điều khoản quy chế GSM và mã chuyến đi.
     * **Hallucination Rate:** Tỷ lệ đưa ra thông tin ngoài bằng chứng (Mục tiêu: 0% trên các ca âm).
     * **Latency & Token Cost:** Hạch toán chi tiết chi phí USD và độ trễ trên từng truy vấn qua Langfuse.
   * Lập báo cáo kết quả đánh giá reasoning hoàn chỉnh.
2. **Xây Dựng Ứng Dụng Web Chatbot Demo Cho Tài Xế GSM (FastAPI + Web UI):**
   * **Backend API (FastAPI):**
     * Endpoint `/api/query`: Nhận câu hỏi tiếng Việt, Driver ID, thời điểm hỏi.
     * Tích hợp pipeline: Query Analysis -> Planner -> Hybrid Retrieval -> Evidence Selection -> Reader -> Trả về JSON kết quả kèm trích dẫn.
     * Endpoint `/api/health` và `/api/benchmark`: Phục vụ giám sát và kiểm thử trực quan.
   * **Giao Diện Web Chat (Hiện đại, Trực quan, Thân thiện Mobile/Desktop):**
     * Khung hội thoại hỏi đáp nghiệp vụ tiếng Việt mượt mà.
     * **Evidence Inspector Panel (Bảng Soi Bằng Chứng):** Cho phép người dùng bấm vào xem chi tiết trích đoạn văn bản chính sách GSM và các nút hành trình chuyến đi liên quan trong đồ thị.
     * Huy hiệu kiểm chứng (Verification Badge): Hiển thị trạng thái "Đã xác thực từ quy chế GSM" hoặc "Cảnh báo: Dữ liệu chưa đủ căn cứ".
3. **Đóng Gói Ứng Dụng & Hướng Dẫn Sử Dụng (Deployment & Docker):**
   * Viết `Dockerfile` và `docker-compose.yml` để khởi chạy trọn vẹn toàn bộ hệ thống bằng 1 lệnh duy nhất.
   * Hoàn thiện tài liệu hướng dẫn demo cho người dùng/giám khảo trải nghiệm.

---

### 4.3. Kế Hoạch Phối Hợp & Nghiệm Thu Chung (Joint Milestones)

| Mốc Thời Gian | Mục Tiêu Phối Hợp Chung | Đầu Ra Cần Đạt Được | Trách Nhiệm Chính |
| :---: | :--- | :--- | :---: |
| **Giai đoạn 1** | **Chốt Cải Thiện Retrieval & Benchmark BRG03** | Tỷ lệ Selected Complete tăng vượt bậc; khép kín số liệu retrieval latency | Hóa (Thuật toán) + Quân (Audit & Report) |
| **Giai đoạn 2** | **Nghiệm Thu Tầng Suy Luận BRG04 / BRG05** | Báo cáo Answer Accuracy, Citation Precision, Langfuse Cost Dashboard | Hóa (Chạy Eval) + Quân (Thẩm định Oracle) |
| **Giai đoạn 3** | **Hoàn Thành Web Chat Demo & API** | Ứng dụng Web Chat chạy ổn định, trực quan hóa bằng chứng rõ ràng | Hóa (Lập trình UI/API) + Quân (Kiểm thử dữ liệu) |
| **Giai đoạn 4** | **Tổng Kết & Bàn Giao Nghiên Cứu Cuối Cùng** | Báo cáo tổng kết toàn dự án, Slide thuyết trình, Video demo | Cả hai cùng thực hiện |

---

## 5. Tiêu Chuẩn Nghiệm Thu Chung (Definition of Done - DoD)

Dự án được coi là hoàn thành xuất sắc khi đáp ứng đầy đủ 6 tiêu chuẩn định lượng sau:

1. **Bảo đảm Dữ liệu Bất biến:** Bản phát hành [`data/gsm-dev-core-0.2.2`](file:///e:/gsm-memory/data/gsm-dev-core-0.2.2) vượt qua 100% kiểm tra hash SHA-256 (636/636 files) và không bị sửa đổi trong suốt quá trình chạy thí nghiệm.
2. **Hiệu năng Chọn lọc Bằng chứng (Selected Retention):** Tỷ lệ câu hỏi giữ trọn vẹn bằng chứng sau bước chọn lọc đạt tối thiểu **60%** (>= 25/42 ca), khắc phục triệt để lỗi rớt ở giới hạn 12-item trước đây.
3. **Độ Chính Xác Câu Trả Lời (Answer Accuracy):** Đạt tối thiểu **80%** câu trả lời chính xác trên tập các câu hỏi có đầy đủ bằng chứng hợp lệ.
4. **Không Ảo Giác Trên Ca Âm (Zero Hallucination on Negatives):** Đạt độ chính xác **100%** trong việc từ chối khẳng định và trả về đúng lý do khi gặp các ca thiếu bằng chứng hoặc quy chế không áp dụng.
5. **Trích Dẫn Minh Bạch (Transparent Citation):** 100% câu trả lời khẳng định đều phải kèm theo nguồn trích dẫn cụ thể (mã điều khoản văn bản hoặc mã sự kiện chuyến đi).
6. **Sản Phẩm Trực Quan Sẵn Sàng Demo:** Có ứng dụng Web Chat hoàn chỉnh chạy được trên môi trường cục bộ hoặc Docker, hỗ trợ trải nghiệm trực tiếp cho tài xế và hội đồng đánh giá.
