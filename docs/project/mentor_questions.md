# Các thông tin cần xác nhận với mentor

## 1. Business use case và phạm vi bài toán

### 1.1. Agent cuối cùng được kỳ vọng giải quyết bài toán gì?

Cần xác định rõ các task chính mà AI Agent sẽ thực hiện trong khối Kinh doanh Vận hành, ví dụ:

* hỏi đáp chính sách / SOP;
* hỗ trợ xử lý case vận hành;
* tra cứu lịch sử tài xế / phương tiện / sự cố;
* hỗ trợ điều tra hoặc tổng hợp thông tin;
* recommendation / next-best-action;
* sử dụng kinh nghiệm từ các case đã xử lý trước đó;
* các task khác.

**Câu hỏi cần xác nhận:**

> Use case chính mà hệ thống AI Agent + Memory cần phục vụ là gì? Có thể cho một vài ví dụ query/task representative không?

---

## 2. Memory thực sự cần lưu những gì?

Cần xác định các loại memory nằm trong scope.

Các nhóm có thể gồm:

* **Document memory:** policy, SOP, FAQ, guideline, tài liệu nghiệp vụ;
* **Entity/state memory:** tài xế, xe, đội xe, đơn hàng, sự cố, trạng thái;
* **Interaction memory:** lịch sử trao đổi giữa user và agent;
* **Episodic/case memory:** các case trước đây, cách xử lý và outcome;
* **Workflow/procedural memory:** quy trình và kinh nghiệm vận hành;
* **Relational memory:** quan hệ giữa nhiều entity, phù hợp với Knowledge Graph.

**Câu hỏi cần xác nhận:**

> Trong các loại memory trên, đâu là phạm vi bắt buộc của bài toán hiện tại?

---

## 3. Vai trò của Document Memory và Knowledge Graph

Hiện tại cần làm rõ việc nhắc đến Document Memory và Knowledge Graph mang ý nghĩa:

* đây là **hai thành phần bắt buộc** phải có trong solution;

hay

* đây là **hai hướng công nghệ cần nghiên cứu/thử nghiệm**, và chỉ sử dụng nếu chứng minh được lợi ích.

**Câu hỏi cần xác nhận:**

> Document Memory và Knowledge Graph là requirement cố định của solution, hay là các technology direction cần đánh giá và áp dụng khi phù hợp?

---

# 4. Baseline / hệ thống hiện tại

Mentor đã đề cập team hiện có một hệ thống "chạy được". Cần biết đủ về hệ thống này để xác định baseline và tránh nghiên cứu lại những thứ đã có.

Không nhất thiết cần source code hoặc chi tiết confidential.

### Thông tin cần biết

* chức năng hiện tại;
* kiến trúc high-level;
* memory được lưu ở đâu;
* retrieval hiện tại hoạt động như thế nào;
* có Vector DB / relational DB / graph DB hay không;
* có reranking hay multi-stage retrieval không;
* memory được update/invalidate như thế nào;
* model/agent tương tác với memory ra sao.

**Câu hỏi cần xác nhận:**

> Có thể chia sẻ high-level architecture của hệ thống hiện tại và các công nghệ chính đang được sử dụng không?

Ví dụ mức thông tin mong muốn:

```text
Source data
    ↓
Processing / Extraction
    ↓
Memory Storage
    ↓
Retrieval
    ↓
Agent / LLM
```

---

# 5. Vấn đề của hệ thống hiện tại

Đây là một trong những thông tin quan trọng nhất.

Cần biết lý do team muốn nghiên cứu thêm công nghệ mới.

Ví dụ:

* retrieval quality chưa tốt;
* latency tăng mạnh khi dữ liệu lớn;
* graph quá khó maintain;
* ingestion/update chậm;
* memory bị trùng lặp;
* khó xử lý information update;
* token/context cost lớn;
* multi-hop reasoning kém;
* framework hiện tại không scale;
* infrastructure cost cao.

**Câu hỏi cần xác nhận:**

> Hệ thống hiện tại đang gặp những limitation/bottleneck nào khiến team muốn thử nghiệm các công nghệ memory mới?

---

# 6. "Scale" cụ thể nghĩa là gì?

Mentor đã nhấn mạnh **scale là yêu cầu ưu tiên hàng đầu**, vì vậy đây phải là phần được làm rõ kỹ nhất.

Scale có thể đề cập đến nhiều dimension khác nhau:

* tổng số memory records;
* tổng document/chunk;
* số users / drivers;
* số entity;
* số edges trong Knowledge Graph;
* số interaction/event trên mỗi entity;
* write/update throughput;
* query throughput / QPS;
* concurrent users/agents;
* retrieval latency khi dataset tăng;
* storage footprint;
* LLM/API cost.

**Câu hỏi cần xác nhận:**

> Khi nói scale là priority số một, team đang quan tâm nhất đến dimension nào?

Và:

> Có thể cung cấp order-of-magnitude của production target không?

Ví dụ không cần số chính xác, chỉ cần mức:

```text
10^5 records
10^6 records
10^7 records
...
```

hoặc range tương ứng.

---

# 7. Production constraints / target

Để chứng minh một solution "phù hợp để productionize", cần biết ít nhất các target hoặc constraint gần đúng.

Có thể gồm:

* latency target;
* QPS/concurrency;
* ingestion throughput;
* freshness requirement;
* storage limit;
* API/LLM cost;
* hardware/infrastructure constraints.

**Câu hỏi cần xác nhận:**

> Team có target hoặc constraint gần đúng cho latency, throughput, memory size, cost hoặc freshness không?

Nếu chưa có hard SLO, có thể hỏi:

> Trong các yếu tố quality, scalability, latency, cost và maintainability, thứ tự ưu tiên của team là gì?

---

# 8. Data và synthetic workload

Hiện tại chỉ được cung cấp schema và phải tự sinh mock data.

Schema là cần thiết nhưng chưa đủ để mô phỏng workload thực tế.

Nếu có thể, nên xin thêm các thông tin aggregate không nhạy cảm.

### Các thông tin hữu ích

* cardinality của từng entity;
* tỷ lệ giữa các bảng/entity;
* average và p95 records/entity;
* distribution có long-tail/skew hay không;
* graph density / average degree;
* document length distribution;
* update frequency;
* temporal characteristics;
* tỷ lệ các loại query;
* một số query template representative.

**Câu hỏi cần xác nhận:**

> Ngoài schema, team có thể cung cấp các statistical characteristics hoặc order-of-magnitude để việc sinh mock data gần với production workload hơn không?

Không cần dữ liệu thật.

---

# 9. Representative queries

Đây là thông tin rất quan trọng để xây custom benchmark.

Schema cho biết dữ liệu tồn tại thế nào, nhưng query mới cho biết **hệ thống cần sử dụng memory như thế nào**.

Nên xin khoảng 5–20 sanitized query/task examples hoặc query templates.

Ví dụ:

```text
- Simple document retrieval
- Cross-document reasoning
- Historical state lookup
- Entity relationship query
- Multi-hop query
- Policy update/conflict query
- Previous-case retrieval
- Workflow recommendation
```

**Câu hỏi cần xác nhận:**

> Team có thể cung cấp một số query/task mẫu đại diện cho workload thực tế không? Có thể anonymize hoặc chỉ cung cấp template.

---

# 10. Kỳ vọng đối với solution sau 6 tuần

Cần thống nhất definition of done.

Working assumption hiện tại:

> Build một AI Agent end-to-end được tích hợp memory, sử dụng các công nghệ/framework hiện đại phù hợp thay vì xây toàn bộ memory framework từ đầu; sau đó đánh giá quality và đặc biệt là scalability để chứng minh giải pháp có tiềm năng áp dụng trong production.

**Câu hỏi cần xác nhận:**

> Sau 6 tuần, deliverable kỳ vọng có phải là một memory-enabled AI Agent hoàn chỉnh ở mức prototype, kèm benchmark, scale test và recommendation để productionize tiếp, thay vì một hệ thống production-ready hoàn chỉnh không?

---

# 11. Mức độ freedom trong lựa chọn công nghệ

Cần biết bạn có thể:

* lựa chọn framework khác;
* kết hợp nhiều framework;
* thay đổi retrieval/indexing strategy;
* thay storage backend;
* tune framework;
* thêm custom components.

hay phải tuân thủ một stack có sẵn.

**Câu hỏi cần xác nhận:**

> Em có freedom đến mức nào trong việc lựa chọn, kết hợp và customize các memory technology/framework?

---

# 12. Tiêu chí cuối cùng để solution được coi là thành công

Đây là câu giúp định nghĩa toàn bộ evaluation.

Có thể là:

$$
Quality
$$

$$
Scale
$$

$$
Latency
$$

$$
Cost
$$

$$
Maintainability
$$

$$
Production\ compatibility
$$

**Câu hỏi cần xác nhận:**

> Điều kiện nào khiến team kết luận rằng solution mới đủ tốt để cân nhắc áp dụng trong production?

Ví dụ:

> giữ hoặc tăng quality trong khi scale tốt hơn baseline;

hoặc:

> đạt latency/cost target ở quy mô production;

hoặc combination của nhiều tiêu chí.

---

# Các câu ưu tiên nhất nếu thời gian trao đổi ngắn

Nếu không thể hỏi tất cả, cần ưu tiên 8 câu sau:

1. **Use case chính của AI Agent + Memory là gì?**
2. **Memory cụ thể cần lưu những loại thông tin nào?**
3. **Document Memory và Knowledge Graph là requirement hay technology candidate?**
4. **High-level architecture và technology stack của hệ thống hiện tại là gì?**
5. **Limitation/bottleneck hiện tại là gì?**
6. **"Scale" cụ thể là scale theo dimension nào và target magnitude khoảng bao nhiêu?**
7. **Ngoài schema, có thể cung cấp workload statistics và representative query templates không?**
8. **Sau 6 tuần, definition of done và tiêu chí để solution được coi là production-viable là gì?**

---

# Thông tin cần có trước khi chốt benchmark

Chỉ nên chốt benchmark chính sau khi có ít nhất:

```text
Business use case
        +
Memory types
        +
Current baseline
        +
Current bottleneck
        +
Scale dimension
        +
Target magnitude
        +
Representative workload
        +
Success criteria
```

Từ đó mới suy ra hợp lý:

```text
Problem Definition
        ↓
Evaluation Requirements
        ↓
Benchmark Selection
        ↓
Synthetic Data Design
        ↓
Technology Selection
        ↓
System Architecture
        ↓
Evaluation Plan
```

Thứ tự này giúp tránh việc chọn benchmark hoặc framework trước rồi mới cố ép bài toán GSM vào benchmark đó.
