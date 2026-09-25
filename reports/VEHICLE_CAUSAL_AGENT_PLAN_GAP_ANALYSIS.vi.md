# Đối chiếu kế hoạch Vehicle Causal Agent với repository `gsm-memory`

| Thuộc tính | Giá trị |
| --- | --- |
| Tài liệu đối chiếu | `Plan: AI Agent cho tài xế với Graph Memory và Causal Reasoning` |
| Repository hiện tại | `memory/` |
| Dataset hiện tại | `gsm-dev-core-0.2.2` — `FROZEN` |
| Checkpoint | `30eead44a6306783ad09880fe45fec34ac9679ff` |
| Ngày đối chiếu | 2026-09-22 |
| Kết luận | Có thể tái sử dụng assurance/retrieval patterns; không phải cùng domain hoặc cùng MVP |

---

## 1. Kết luận điều hành

Kế hoạch trong file đính kèm và repository hiện tại có chung một số nguyên tắc kỹ thuật:

- graph-based retrieval;
- temporal evidence;
- provenance;
- entity identity;
- evidence-grounded output;
- missing/conflict handling;
- deterministic evaluation và failure attribution.

Tuy nhiên, chúng **không phải cùng một bài toán sản phẩm**.

Repository hiện tại nghiên cứu retrieval và evidence construction cho:

```text
GSM policy documents
+ synthetic driver/operation records
+ temporal ledger/snapshots
+ typed gold/proofs
```

Kế hoạch đính kèm yêu cầu một sản phẩm chẩn đoán xe end-to-end:

```text
vehicle diagnostic ontology
+ causal graph/path traversal
+ conversational and episodic memory
+ LLM reasoning/synthesis
+ safety policy
+ API/UI/deployment stack
```

Do đó:

1. `gsm-dev-core-0.2.2` không phải dataset cho chẩn đoán linh kiện hoặc sự cố xe.
2. Core retrieval hiện tại không phải causal diagnosis engine.
3. Báo cáo bàn giao `CORE_RETRIEVAL_DEVELOPMENT_HANDOFF.vi.md` chỉ đáp ứng một phần retrieval/evidence foundation của kế hoạch đính kèm.
4. Không được thêm ontology `Vehicle/Component/Symptom/FailureMode/...` vào frozen schema `1.1` hoặc release `0.2.2`.
5. Nếu kế hoạch đính kèm là mục tiêu sản phẩm thật, cần một domain contract, dataset family và benchmark riêng; nên dùng repository/package riêng hoặc một major-version track được phê duyệt rõ ràng.

---

## 2. Hai bài toán khác nhau ở đâu?

| Trục | Repository hiện tại | Kế hoạch đính kèm |
| --- | --- | --- |
| Primary objective | Retrieval/evidence benchmark | Vehicle diagnostic assistant MVP |
| Domain | Policy + driver operations | Vehicle components, symptoms, failures, sensor codes |
| User | Research/benchmark pipeline | Driver end user |
| Input | 42 direct Vietnamese RuntimeQueries | Voice/text, session context, vehicle context |
| Knowledge | 224 policy articles + synthetic ledger | Manuals, OBD-II, diagnostic rules, event history |
| Graph meaning | Temporal assertions/provenance | Causal and diagnostic paths |
| Reasoning | Observable proof/status semantics | Conditional causal diagnosis and risk assessment |
| Output | Evidence bundle/typed evaluation | Answer, causes, confidence, safety actions, follow-up |
| Runtime | Offline CLI/reports | FastAPI + LangGraph + Redis + frontend |
| Benchmark | 42 dev cases, 0 test | 50–100 grounded diagnostic cases |
| Deployment | Không phải mục tiêu hiện tại | Docker Compose local MVP |

Sự khác nhau không chỉ là backend hoặc tên node. Nó nằm ở ontology, dữ liệu nguồn, gold semantics, safety requirements và evaluation target.

---

## 3. Ma trận đáp ứng yêu cầu

Quy ước:

```text
ALIGNED     nguyên tắc/capability tương thích đáng kể
PARTIAL     có nền tảng nhưng chưa đáp ứng contract mục tiêu
MISSING     chưa có implementation/dataset
CONFLICT    không được thêm vào frozen scope hiện tại
```

### 3.1. Mục tiêu sản phẩm

| Yêu cầu | Trạng thái | Nhận xét |
| --- | --- | --- |
| Nhận câu hỏi tự nhiên | `PARTIAL` | Có 42 Vietnamese text queries; chưa có generic intake/API |
| Voice input/transcript | `MISSING` | Không có speech/voice pipeline |
| Duy trì hội thoại | `MISSING` | Không có session/working memory |
| Lịch sử sự kiện theo thời gian | `ALIGNED` về pattern | Immutable ledger, valid/known time rất mạnh nhưng domain khác |
| Multi-hop diagnostic graph | `MISSING` | Có graph search Mode A nhưng không có diagnostic ontology/path contract |
| Conditional causal reasoning | `PARTIAL` về principle | Có conditional/proof/counterfactual semantics; không có causal diagnosis engine |
| Hallucination control | `ALIGNED` về evidence | Public evidence, provenance và missing/conflict semantics có thể tái sử dụng |
| Explanation path | `PARTIAL` | Có support locators/proofs; chưa có user-facing causal path |
| Confidence/risk/safety actions | `MISSING` | Không có risk taxonomy hay safety policy |
| Backend/UI/deployment | `MISSING` | Không có FastAPI, Next.js hoặc Docker Compose stack |

### 3.2. MVP technology stack

| Thành phần yêu cầu | Repository hiện tại | Gap |
| --- | --- | --- |
| FastAPI | Không có dependency/implementation | Cần service/API project |
| LangGraph | Không có | Cần agent state machine mới |
| Neo4j service | Chỉ có optional Python driver | Graphiti path hiện đo trên Kùzu; chưa có Neo4j deployment/config |
| Redis | Không có | Cần session/cache policy, schema và lifecycle |
| Qdrant/vector episodic memory | Không có | Cần lựa chọn/pin backend và memory semantics |
| Next.js/Tailwind | Không có frontend workspace | Cần frontend riêng |
| SSE/WebSocket | Chưa có server stream | `websockets` chỉ là transitive package, không phải feature |
| Docker Compose | Không có | Cần service orchestration và smoke test |
| Provider-neutral LLM layer | Chưa có runtime reader | Cần interface, config, structured output và instrumentation |

Không nên suy ra “đã có Neo4j” chỉ vì `neo4j==6.3.0` xuất hiện trong optional `graphiti` dependencies. Repository chưa có Neo4j service, schema migration, deployment hay measured runtime path trên Neo4j.

### 3.3. Vehicle ontology

Toàn bộ ontology sau hiện chưa tồn tại:

```text
Vehicle
Component
Symptom
FailureMode
SensorCode
OperatingCondition
Environment
Action
Risk
Event
```

Các edge sau cũng chưa tồn tại:

```text
INDICATES
CAUSES
LEADS_TO
OCCURS_IN
AGGRAVATES
REQUIRES
RESOLVES
INVOLVES
OBSERVED_UNDER
PRECEDED_BY
```

Đây không phải “thêm vài labels” vào Graphiti adapter. Nó yêu cầu:

- domain semantics;
- identity rules;
- edge direction/cardinality;
- temporal semantics;
- condition-rule language;
- provenance contract;
- probability/confidence calibration;
- correction/retraction/versioning;
- safety review;
- independent conformance fixtures.

Theo `AGENTS.md`, repository hiện tại không được mở thêm business domain/predicate ngoài frozen contract. Vì vậy việc thêm ontology này vào `gsm-dev-core-0.2.2` là `CONFLICT`, không phải backlog Phase B.

### 3.4. Retrieval và reasoning flow

| Bước trong plan | Hiện trạng | Mức tái sử dụng |
| --- | --- | --- |
| Intent recognition | Chưa có | Thấp |
| Entity linking | Có public entity refs/catalog ở domain GSM | Pattern dùng được; ontology/model phải làm mới |
| Working memory | Chưa có | Không |
| Candidate subgraph | Có Mode A search theo snapshot | Adapter/trace pattern dùng được |
| N-hop traversal | Chưa có explicit path engine | Cần mới |
| Causal pruning | Chưa có | Temporal/scope filters dùng được một phần |
| Path ranking | Chưa có | Candidate scoring/instrumentation dùng được một phần |
| Verification | Có source/time/snapshot/proof verification | Pattern tái sử dụng cao |
| Synthesis | Reader chưa chạy | Cần mới |
| Episodic write-back | Chưa có | Cần observation/inference write policy mới |

### 3.5. API contracts

Plan yêu cầu:

```python
get_subgraph(...)
find_causal_paths(...)
get_related_events(...)
```

Repository hiện tại chưa export ba interface này. Các primitive gần nhất là:

- document BM25 search;
- `construct_mode_a()` và Graphiti search;
- entity catalog candidates;
- temporal eligibility filtering;
- exact computation candidates;
- hybrid union và public selection.

Các primitive đó là implementation reference, không phải drop-in implementation cho `find_causal_paths`.

---

## 4. Phần có thể tái sử dụng tốt

### 4.1. Data assurance pattern

Có thể tái sử dụng:

- pinned source archive và immutable source snapshots;
- raw/normalized hashes;
- source catalog;
- public/private packaging;
- deterministic IDs;
- materialization và frozen verification;
- clean-build logical comparison;
- release certificate.

Vehicle dataset cũng nên có pipeline tương tự trước khi xây agent.

### 4.2. Temporal and provenance model

Repository hiện tại có các nguyên tắc mạnh phù hợp với episodic/diagnostic history:

- tách event time, valid time, known time và ingestion time;
- immutable `assert/replace/retract` ledger;
- source authority và correction authorization;
- same fact qua revisions giữ lineage;
- historical prefix không nhìn thấy future information;
- equal-rank conflict không tự resolve;
- missing evidence không biến thành false;
- public snapshot là allowlist.

Các nguyên tắc này nên được đưa vào vehicle event schema thay vì chỉ lưu một mutable “latest vehicle state”.

### 4.3. Evidence contract

Có thể tái sử dụng các ý tưởng:

```text
canonical source locator
ProjectionLink
semantic support atom
minimal sufficient proof
candidate vs selected evidence
source/time/entity correctness
post-runtime evaluator
```

Trong vehicle domain, locator có thể mở rộng cho:

- manual page/section;
- OBD specification/version;
- diagnostic procedure step;
- sensor/event record;
- inspection report;
- hypothesis edge.

### 4.4. Retrieval instrumentation

Có thể tái sử dụng:

- per-stage candidates;
- excluded reasons;
- candidate/selected attribution;
- token and item budgets;
- latency aggregation unit/denominator;
- cold/warm status;
- deterministic run identity;
- provider call/token/cost placeholders;
- explicit `unsupported/blocked/not_run` states.

### 4.5. Proof-preserving selector work

Core selector work hiện tại có ích cho plan mới vì một diagnostic answer thường cần giữ đồng thời:

```text
symptom
condition
candidate cause
source clause
risk/action relation
contradicting evidence
```

Dependency-aware evidence packing có thể tái sử dụng ở cấp thiết kế. Candidate schema và domain dependencies phải được định nghĩa lại cho vehicle ontology.

---

## 5. Phần không thể tái sử dụng trực tiếp

### 5.1. Dataset

`gsm-dev-core-0.2.2` chứa policy documents và synthetic driver-operation facts, không chứa:

- vehicle components;
- symptoms;
- failure modes;
- sensor codes;
- diagnostic manuals;
- repair/inspection actions;
- calibrated causal probabilities;
- safety risks.

42 current queries không thể dùng để đo causal-path top-1 hoặc vehicle diagnosis accuracy.

### 5.2. Gold semantics

Current gold kiểm tra source/time/proof semantics. Vehicle benchmark cần thêm:

- symptom/entity linking ground truth;
- acceptable alternative causal paths;
- required condition matches;
- ruled-out causes;
- risk level;
- safe action policy;
- abstention/follow-up requirements;
- prohibited unsafe claims.

Không được chuyển một diagnostic label đơn lẻ thành gold nếu nhiều cause/path hợp lệ.

### 5.3. Causal probability và confidence

Repository hiện tại dùng source authority, exact rules và observable proof; không có calibrated causal probability.

Plan mới phải định nghĩa riêng:

- `probability` là prior, conditional probability hay expert score;
- population và điều kiện áp dụng;
- cách combine nhiều edge probabilities;
- cách xử lý source conflict;
- `confidence` thuộc source, extraction hay conclusion;
- calibration/evaluation protocol.

Không nên nhân edge probabilities dọc path nếu chưa có probabilistic model hợp lệ.

### 5.4. Safety layer

Không có safety policy cho chẩn đoán xe. Cần một contract độc lập về:

- risk taxonomy;
- escalation rules;
- stop-driving conditions;
- emergency fallback;
- disclaimer;
- source authority cho safety action;
- human review/audit.

LLM không được tự tạo safety threshold từ text retrieval.

---

## 6. So sánh benchmark

| Hạng mục | Hiện tại | Plan yêu cầu |
| --- | --- | --- |
| Cases | 42 dev/conformance | 50–100 diagnostic cases |
| Test split | 0 | Cần ground-truth benchmark |
| Independence | 25 roots/32 variants | Chưa định nghĩa |
| Gold | Typed status/value + proof atoms | Cause/path/risk/action ground truth |
| Ranking qrels | Chưa có | Cần cho path/cause ranking |
| Reader evaluation | Chưa chạy | Bắt buộc |
| Safety evaluation | Không có | Bắt buộc |
| Latency | Pre-reader offline | Full text response P95 < 8s đề xuất |
| Generalization | Không claim | Plan chưa thiết kế held-out protocol |

Plan nói “benchmark 50–100 tình huống” nhưng chưa đủ để bảo đảm generalization. Cần tách:

```text
conformance fixtures
development cases
locked held-out test cases
```

Không nên tune prompt/traversal/ranking rồi báo kết quả trên cùng 50–100 cases mà không có group-held-out split.

Nên split theo:

- vehicle platform/model family;
- component/failure family;
- symptom cluster;
- manual/source family;
- operating-condition combination;
- scenario root.

Paraphrases của cùng một case không được tính là independent test samples.

---

## 7. So sánh Definition of Done

### Current core-retrieval DoD

- 42/42 retrieval traces;
- public-only runtime;
- correct snapshot/entity/time/source lineage;
- proof-preserving selection;
- deterministic runs;
- candidate/selected attribution;
- frozen dataset unchanged.

### Vehicle MVP DoD

- full Docker Compose stack;
- API + agent + graph + working/episodic memory;
- grounded diagnostic answer;
- causal paths;
- condition filtering;
- risk and safety actions;
- conversation continuity;
- frontend visualization;
- benchmark accuracy/hallucination/latency report.

Kết luận: hoàn thành current core retrieval chỉ đóng góp một phần vào vehicle MVP DoD; nó không thay thế agent, memory, causal ontology, safety, service và UI work.

---

## 8. Xung đột với repository contract hiện tại

Các thay đổi sau không được thực hiện dưới frozen/current schema contract:

- thêm vehicle diagnostic business domain;
- thêm node/predicate `Component`, `Symptom`, `FailureMode`, `CAUSES`, v.v.;
- thay 42 canonical queries bằng diagnostic cases;
- đổi gold để chấm causal diagnosis;
- đưa session/episodic write-back vào frozen ledger;
- dùng Neo4j/LLM output làm source of truth cho dataset;
- gọi current 42-case catalogue là vehicle benchmark.

Nếu muốn làm trong cùng repository, cần tối thiểu:

1. task-specific authorization thay đổi scope;
2. normative domain/schema document mới;
3. dataset release family mới;
4. config/IDs/manifest/validation namespace mới;
5. tách hoàn toàn khỏi frozen `gsm-dev-core-0.2.x`;
6. tests và reports riêng;
7. cập nhật `AGENTS.md` sau review, không sửa ngầm.

Về quản trị kỹ thuật, một repository riêng cho vehicle agent là lựa chọn an toàn hơn vì giảm nguy cơ trộn schema, dependencies và product concerns vào research benchmark hiện tại.

---

## 9. Đánh giá kế hoạch 6 tuần

Kế hoạch sáu tuần có dependency order hợp lý nhưng scope hiện quá rộng cho hai người nếu bắt đầu từ dữ liệu chưa có. Các hạng mục cùng lúc gồm:

- domain research và source review;
- ontology;
- Text-to-Graph;
- entity resolution;
- Neo4j graph;
- episodic vector memory;
- Redis working memory;
- LangGraph agent;
- Text2Cypher validation;
- causal path ranking;
- LLM verification;
- FastAPI/SSE;
- Next.js/voice/UI;
- 50–100 case benchmark;
- Docker deployment.

Rủi ro chính không phải code integration mà là **grounded domain data và safety semantics**. Mục tiêu “1.000 quan hệ mẫu ở tuần 2” không có ý nghĩa nếu quan hệ chưa được source-review và condition/provenance chưa đúng.

### Điều chỉnh phạm vi khuyến nghị

Trong sáu tuần, nên ưu tiên một vertical slice:

```text
text-only input
10–20 reviewed diagnostic roots
one vehicle/component family
Neo4j or one graph backend
no free-form Text2Cypher in critical path
fixed retrieval tools
one working-memory implementation
grounded answer + abstention + safety fallback
minimal web chat
```

Voice, generic ingestion, multi-backend vector memory và polished graph UI nên là stretch goals.

---

## 10. Kế hoạch chuyển đổi đề xuất

### Phase V0 — Approve domain and safety contract

Deliverables:

- use-case boundaries;
- vehicle/region/manual scope;
- diagnostic and safety disclaimers;
- ontology v0.1;
- allowed predicates;
- probability/confidence semantics;
- source acceptance policy;
- observation vs inference distinction;
- API contracts.

Không code Text-to-Graph trước khi phase này được duyệt.

### Phase V1 — Build an auditable vehicle dataset

Deliverables:

- pinned manuals/OBD/source snapshots;
- source hashes and locators;
- canonical entities/aliases;
- reviewed causal/conditional claims;
- versioned event schema;
- 10–20 conformance roots;
- dev/test group plan;
- public/private gold boundary;
- independent validator.

Tái sử dụng data assurance patterns từ `gsm-dev-core-0.2.2`, không tái sử dụng business schema.

### Phase V2 — Fixed retrieval API

Implement:

```python
get_subgraph(...)
find_causal_paths(...)
get_related_events(...)
```

Yêu cầu:

- bounded hops/beam;
- schema allowlist;
- deterministic filters;
- public/source provenance;
- temporal eligibility;
- explicit conflict/missing status;
- no arbitrary database access from LLM;
- complete runtime traces.

### Phase V3 — Agent vertical slice

- text-only FastAPI endpoint;
- fixed LangGraph state machine;
- entity linking;
- retrieval tools;
- causal pruning;
- structured answer;
- safety fallback;
- no write-back of unverified inference as fact.

### Phase V4 — Benchmark and attribution

Đánh giá tách tầng:

```text
entity linking
candidate path recall
selected path recall
condition correctness
source grounding
risk/safety correctness
reader synthesis
end-to-end answer
```

Thêm oracle-path control để phân biệt retrieval failure với reader failure.

### Phase V5 — Product shell

Sau khi text flow ổn định:

- Redis working memory;
- episodic store;
- SSE;
- minimal Next.js UI;
- Docker Compose;
- voice input nếu còn thời gian.

---

## 11. Phân công hai người sau khi điều chỉnh

### Người 1 — Domain Data and Retrieval

- source policy và source review;
- ontology/identity/versioning;
- graph ingestion;
- provenance;
- temporal event schema;
- fixed retrieval interfaces;
- candidate path generation;
- data quality và retrieval conformance.

### Người 2 — Reasoning and Product Runtime

- agent state machine;
- entity linking runtime;
- causal pruning/ranking;
- evidence selector;
- verification và safety fallback;
- working memory;
- structured answer;
- benchmark runner và error attribution;
- API/streaming integration.

### Shared contract cần chốt trước khi làm song song

```text
ontology version
canonical ID rules
event/temporal semantics
retrieval request/response schema
causal path schema
source locator schema
missing/conflict/abstain statuses
risk and safety action schema
benchmark split and metrics
```

---

## 12. Quyết định kiến trúc được khuyến nghị

### Khuyến nghị chính: tách project/domain

Tạo repository hoặc top-level product workspace riêng cho vehicle agent. Dùng `gsm-memory` như reference implementation cho:

- temporal ledger semantics;
- source provenance;
- frozen dataset workflow;
- evidence contracts;
- retrieval traces;
- independent evaluator;
- proof-preserving selection.

Không import trực tiếp frozen dataset schema làm vehicle ontology.

### Nếu buộc phải dùng cùng repository

Phải tạo namespace rõ ràng, ví dụ ở mức khái niệm:

```text
src/vehicle_agent/
configs/vehicle/
data/vehicle-*/
tests/vehicle/
reports/vehicle/
frontend/
```

Nhưng chỉ thực hiện sau khi repository governance cho phép. Không sửa `src/gsm_memory/data/` hoặc `gsm-dev-core-0.2.2` để nhét vehicle predicates.

---

## 13. Kết luận cuối

Mức tương thích đúng nên được hiểu như sau:

| Lớp | Mức phù hợp |
| --- | --- |
| Data provenance/reproducibility | Cao, có thể tái sử dụng pattern |
| Temporal identity/revision semantics | Cao, có thể tái sử dụng pattern |
| Evidence selection/evaluation | Khá cao ở cấp thiết kế |
| Document + graph retrieval plumbing | Một phần |
| Vehicle domain dataset | Không có |
| Causal ontology/path engine | Không có |
| Conversational/episodic memory | Không có |
| Agent reasoning/synthesis | Không có |
| Safety policy | Không có |
| FastAPI/Redis/Next.js/Docker product stack | Không có |
| Generalization benchmark | Không có |

Vì vậy, không nên mô tả repository hiện tại là “đã gần hoàn thành vehicle causal agent”. Cách diễn đạt chính xác là:

> Repository đã cung cấp một reference foundation mạnh cho temporal evidence, provenance, retrieval assurance và failure attribution. Kế hoạch vehicle causal agent có thể kế thừa các nguyên tắc đó, nhưng cần một domain dataset, ontology, causal engine, safety contract và product stack hoàn toàn mới.
