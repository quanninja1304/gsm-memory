# GSM — Benchmark → Dataset Design Mapping

**Ngày đối chiếu:** 16/09/2026  
**Design note:** `gsm-benchmark-mapping-v0.3` — đề xuất thiết kế dataset, chưa phải dataset release đã freeze.  
**Contract áp dụng:** `02_synthetic_schema_and_data_design.md`, Schema v1.1, scope `gsm-policy-retrieval-core-v1.1`. SHA-256: `2310f80d281b0f703e4b8eb9a738ed0ef2a9b81a3d766cc25662f6f097e759f8`.

**Kết luận thiết kế:** xây một bộ dữ liệu GSM từ policy snapshots và structured ledger đã chốt; áp dụng có chọn lọc cách tạo evidence, câu hỏi, distractors và protocol của các benchmark. Không ghép mười corpus thành một benchmark chung, không chuyển mọi dữ liệu nghiệp vụ thành hội thoại và không thêm framework memory để đáp ứng taxonomy của paper.

Phân tích này đối chiếu nội dung công khai của đúng mười công trình qua paper/repository chính thức. Chưa có mười PDF theo tên được nêu để xác nhận chúng trùng byte hoặc revision với bản người dùng đã lưu. Bảng dưới ghi rõ arXiv version được đọc; không xem tên file là bằng chứng về phiên bản. Các ô “Thiết kế GSM” là **đề xuất áp dụng**, không phải kết quả đã được paper chứng minh trên dữ liệu GSM.

## 1. Ràng buộc từ schema v1.1

| Đã freeze trong 02 | Hệ quả bắt buộc khi thiết kế dataset |
| --- | --- |
| T01–T07 thuộc PF01–PF04; PF05/PF06 và các decision tasks chưa đủ điều kiện được hoãn | Benchmark chỉ gợi ý phương pháp tạo/đánh giá mẫu. Không dùng paper để tự mở lại các hàng DEFER |
| Hai predicates mới: `REPORTED_MEASURE`, `DRIVER_PROGRAM` | Không thêm offer lifecycle, online sessions, raw revenue/rating, payroll hoặc persona attributes cho đủ benchmark |
| Bốn reported definitions; `cancel_rate_30d` là derived metric riêng | Phân biệt tìm đúng số đã báo cáo với tính đúng số từ toàn bộ events; không đánh đồng hai năng lực |
| Immutable ledger, stable IDs, valid time, known time, provenance, source precedence | Mẫu update phải có targets và hai đồng hồ rõ; “câu nói gần nhất thắng” không phải oracle mặc định |
| Ba gold tracks: `source_grounded`, `conditional_binding`, `synthetic_control` | Báo điểm riêng. Policy snapshot thật không tự chứng minh hiệu lực hiện hành hoặc toàn bộ lịch sử policy |
| Gold bằng `SupportAtom` + `EvidenceProof` + source locators | Đổi chunking/Graphiti UUID không được đổi semantic gold; chấp nhận các tập bằng chứng đủ tương đương |
| Retrieval, context construction và reasoning là các tầng khác nhau | Dataset phải chứa evidence gold và expected status, không chỉ cặp question–answer |
| Graphiti là reference; Mode A và Mode B cần phân biệt | Cùng nguồn, queries và gold; đo construction trước khi quy lỗi cho retrieval |

Tài liệu 03 v0.1.1 có đồng bộ corpus protocol nhưng vẫn giữ các planning notes/fingerprints lịch sử trước audit. Khi triển khai, dùng whitelist/definitions của **02 v1.1**, evaluation contract 01 v0.1.1 và exact release contract **05 v0.2.0** làm chuẩn; các đề xuất cũ trong 03 không mở lại DEFER tasks hoặc đổi gold.

## 2. Mapping từ từng benchmark sang dataset GSM

P0 = dùng trong **thiết kế core ngay**, không có nghĩa mọi experiment phải chạy trước pilot; P1 = diagnostic sau baseline; P2 = hoãn năng lực ngoài phạm vi. Thứ tự thực thi: BM05 + BM07 + BM03 → canonical pilot → BM02 wording diagnostic → BM01/BM06 scale-noise diagnostics. Stress/capacity experiments chỉ chạy sau end-to-end pilot. Mức ưu tiên áp dụng cho cơ chế cụ thể.

| Benchmark và bản đối chiếu | Cơ chế thiết kế được nguồn mô tả | Thiết kế GSM đề xuất | Mapping vào 02 v1.1 | Gold / phép đo cần có | Quyết định và giới hạn |
| --- | --- | --- | --- | --- | --- |
| **BM01 — BEAM**. *Beyond a Million Tokens*. [2510.27246v1, §2.2–2.4](https://arxiv.org/html/2510.27246v1) | Lập kế hoạch diễn biến trước khi sinh hội thoại; gắn probes với các đoạn nguồn; chấm các tiêu chí nội dung nhỏ; nhiều mức độ dài | Dùng timeline/observation plan để tạo lịch sử tài xế nhất quán. Giữ core evidence, tăng distractor histories và khoảng cách giữa các mảnh evidence. Chia rubric trả lời thành claims có thể kiểm tra | `ObservationPlan`, source refs, `SupportAtom`, §§17/21/22; Q3/Q5/Q6/Q7 | Claim coverage, complete proof, temporal correctness; đường quality–latency–cost | **P0:** cách tổ chức lịch sử và stress. Không sao chép LIGHT, không đặt 10M tokens thành gate, không coi token scale là database scale |
| **BM02 — LoCoMo-Conv**. *When Users Don’t Ask*. [2609.03467v1, §3–4](https://arxiv.org/html/2609.03467v1); [repo tác giả](https://github.com/MiuLab/LoCoMo-Conv) | Biến đổi QA thành dialog, implicit, counterfactual-premise và composed; giữ liên kết evidence, đánh giá retrieval và response riêng | Từ một semantic case tạo cách hỏi trực tiếp/hội thoại/ẩn ý; thêm câu có tiền đề sai cần sửa. Ghép các yêu cầu tương thích vào query nhiều phần sau pilot | `RuntimeQuery`, `QueryGenerationTrace`, `split_group`, proof alternatives; T01–T07 | Chênh lệch recall/sufficiency giữa paired styles; sửa tiền đề sai; coverage từng yêu cầu | **P0:** direct/dialog/implicit/false-premise. **P1:** composed. Phải giữ đủ public context để câu hỏi ẩn ý vẫn xác định; composed cần proof mới, không copy một gold cũ |
| **BM03 — LoCoMo**. *Evaluating Very Long-Term Conversational Memory*. [2402.17753v1, §3–4](https://arxiv.org/html/2402.17753v1) | Persona và temporal event graph định hướng nhiều sessions; con người sửa tính nhất quán; QA và event summarization có grounding | Sinh trạng thái, events và source revisions trước; render thành operational observations theo nhiều phiên. Giữ IDs/lineage qua các cách diễn đạt, không dùng tên làm identity | Private world → public ledger → `text_observations`; Q2/Q3/Q5/Q6; metric/profile lineage | Entity/event attribution, supporting atoms, summary factuality và source citations | **P0:** lịch sử nhất quán và evidence alignment. Không cần hội thoại đời tư hay multimodal; temporal event graph trong paper không thay bitemporal ledger |
| **BM04 — LongMemEval-V2**. *Experienced Colleagues*. [2605.12493v1, §3.1–3.4](https://arxiv.org/html/2605.12493v1) | Lịch sử web-agent trajectories; gán nhãn trajectories chứa đáp án; memory trả context cho reader cố định; kiểm cả câu hỏi có tiền đề không phù hợp môi trường | Chuẩn hóa retriever trả evidence bundle; giữ reader/budget chung. So retrieved context với gold context; kiểm lỗi chọn evidence riêng với lỗi đọc/suy luận | `EvidenceUnit`, bundle E, `EvidenceProof`; L1–L4 trong 01; T02/T03/T05/T07 | Candidate/selected sufficiency, correctness khi context đủ, latency; oracle-context control | **P0:** context-gathering protocol. **P2:** UI affordance, workflow/gotcha learning từ web trajectories. Đây là hướng khác LongMemEval gốc, không chỉ corpus hội thoại lớn hơn |
| **BM05 — LongMemEval**. [2410.10813v1, §3.2–3.4](https://arxiv.org/html/2410.10813v1) | Question/evidence statements được thiết kế và kiểm thủ công; evidence nằm trong các sessions giữa distractors; có update, temporal reasoning, abstention và answer-location labels | Với mỗi task, xác định proof trước; phân bố nguồn hỗ trợ qua documents, reports và state records; tạo before/after update, thiếu dữ liệu và distractors có kiểm soát | `TaskBinding`, `SupportAtom`, `GoldSupportLink`, revisions, Q1–Q7 | Evidence-set recall, answer/status accuracy, wrong-period/stale rates; split theo scenario | **P0:** nền chính cho query/evidence design. Không kế thừa ontology đời tư; không dùng LLM-generated QA làm gold duy nhất |
| **BM06 — MemBench (`membench.pdf`)**. [2506.21605v1, §3.1–3.4 và §4](https://arxiv.org/html/2506.21605v1) | Phân biệt observation/participation, factual/reflective memory; tạo evidence trước; đo recall, accuracy, efficiency/capacity; thêm noise không mâu thuẫn | Core chạy bằng nguồn quan sát cố định. Tách facts/reports khỏi derived metric và summaries; thay đổi lượng noise, đo đọc và ghi riêng | `SourceRecord`, `ReportedMeasure`, `MetricArtifact`, profile dependencies; Q2/Q3/Q6 | Evidence recall, source fidelity, summary freshness, ingest/read latency | **P0:** observation setting và phân tầng evidence. Reflective preferences không tương đương profile hành vi được chứng minh; không bật hypothesis generation. MCQ chỉ là diagnostic |
| **BM07 — MemoryAgentBench**. [2507.05257v1, §3.2–3.4](https://arxiv.org/html/2507.05257v1) | Chuyển dữ liệu dài thành các chunks nạp tuần tự; nhiều câu hỏi dùng chung lịch sử. FactConsolidation đặt factual edits theo thứ tự và ưu tiên thông tin mới | Replay các atomic `SourceRecord` theo logical publication; hỏi ở nhiều checkpoints; tái sử dụng index cho một cohort. Tách snapshot comparison với update-serving lag | `assert/replace/retract`, `known_at`, `commit_seq`, `IngestionReceipt`; Q6/Q7 và T02/T07 | Correction adoption, old-snapshot preservation, conflict status, time-to-searchable, write amplification | **P0:** sequential ingestion. Phải thay recency-wins bằng reducer của GSM; không xóa khả năng trả lời lịch sử. Test-time skill learning ngoài core |
| **BM08 — MemoryArena**. [2602.16313v1, §3.1–3.2](https://arxiv.org/html/2602.16313v1) | Nhiều subtasks phụ thuộc nhau qua sessions; hành động nhận feedback và thay đổi thông tin cần cho bước sau | Sau baseline có thể thử một chuỗi lookup–check–recheck có dependencies rõ; đo từng bước và kết quả cuối. Trước mắt Q6 replay vẫn là update test riêng | Có thể tái dùng T02/T07 và traces cho read-only diagnostic; chưa có environment/action contract tương đương | Step success và chain success; ablate memory; ghi rõ nguồn thông tin giữa các phiên | **P1:** diagnostic dependency nhỏ. **P2:** đầy đủ action–environment loop. Nạp events theo lịch rồi hỏi không phải replication MemoryArena |
| **BM09 — MemoryBench (`docs/research/papers/memory_bench.pdf`)**. [2510.17281v1, §2.2–2.4](https://arxiv.org/html/2510.17281v1) | Task provider, user-feedback simulator và test monitor; feedback của các task học được tách khỏi test; nhắm continual learning | Kế thừa sự tách biệt adaptation/dev và locked test. Nếu nghiên cứu học từ feedback về sau, tạo feedback stream riêng có provenance và budget | Split/release/experiment metadata; core chưa có procedural-feedback learning task | Transfer sang unseen cases, chi phí học và forgetting nếu mở extension; hiện chỉ dùng split discipline | **P0:** chống test leakage. **P2:** học từ feedback. Source correction của doanh số không đồng nghĩa feedback về chất lượng câu trả lời; không thêm training loop vào core |
| **BM10 — PersonaMem-v2**. [2512.06688v1, §2.1–2.5](https://arxiv.org/html/2512.06688v1) | Preferences xuất hiện gián tiếp trong task-driven conversations; có update, tình huống giả định và thông tin người thứ ba; queries cần cá nhân hóa | Mượn thử thách attribution: driver cùng tên, mention của người khác, câu hỏi giả định không được coi là fact mới. Không dựng sở thích/tính cách từ vài chuyến xe | Entity resolution, historical aliases, query rendering; Q2/Q7 và Mode B diagnostic có kiểm soát | Wrong-entity rate, unsupported inference, groundedness; attribution labels | **P1:** attribution/language diagnostic. **P2:** implicit persona inference, personalization và RL. `profiles.hypotheses_enabled=false` vẫn giữ |

**Ba khác biệt không được làm mất khi áp dụng:**

| Khác biệt | Hệ quả cho benchmark GSM |
| --- | --- |
| MemBench và MemoryBench là hai công trình khác nhau | BM06 giúp observation/evidence/cost; BM09 tập trung feedback/continual learning. Không gộp thành một citation hoặc taxonomy |
| LongMemEval và LongMemEval-V2 có đối tượng memory khác nhau | BM05 phù hợp query/evidence generation; từ BM04 chủ yếu lấy protocol evidence → fixed reader, không nhận cả web-agent task scope |
| Persona/reflective memory khác profile vận hành | Không dùng khuynh hướng ngôn ngữ hoặc vài events để gán trait chắc chắn. Profile core chỉ là summary/metric có dependencies và provenance |

Trong bản MemoryAgentBench đọc ở đây, §3 dùng tên Conflict Resolution; một số bản mô tả khác dùng Selective Forgetting. Thiết kế GSM dựa vào **protocol FactConsolidation đã đọc**, không suy semantics từ tên competency. Historical correction, retraction và xóa dữ liệu vì quyền riêng tư cũng là ba yêu cầu khác nhau.

## 3. Một dataset, nhiều phép kiểm tra độc lập

Giữ nguyên ba gold tracks của 02. Không tạo “mười datasets GSM” chỉ vì có mười papers.

| Gold track | Input | Queries | Điều score có thể chứng minh |
| --- | --- | --- | --- |
| `source_grounded` | Policy snapshot thật và TEXT clauses đã review | T01/T04/T06 | Tìm và diễn giải đúng nội dung bản được chỉ định; không chứng minh current-policy selection |
| `conditional_binding` | Cùng policy snapshots + synthetic states/reports + public conventions | T02/T03/T05/T07 | Kết luận đúng trong các premises đã khai báo; không chứng minh raw metric computation hay quyền lợi thật |
| `synthetic_control` | Synthetic rules + canonical events/states/publications/coverage | Foundation Q2/Q3/Q5/Q6/Q7; temporal-policy controls | Kiểm những semantics mà corpus policy thật thiếu lịch sử hoặc chưa đủ observables |

Trên mỗi track, chỉ bật các axes có nghĩa với task:

| Axis | Biến đổi được kiểm soát | Giữ cố định | Benchmark gợi ý / phần GSM bổ sung |
| --- | --- | --- | --- |
| Query wording | Direct, dialog, implicit; false-premise có rubric riêng | Entity/time/answer scope và public premises | BM02; GSM thêm semantic-equivalence validation |
| Evidence distribution | Đổi physical/context placement và distractor distance trong cách trình bày, không tráo lịch công bố | Cùng proof, canonical publication order, `known_at`, `commit_seq`, revision dependencies và source semantics | BM01/BM03/BM05; presentation position ≠ logical time. Nếu thêm source records làm đổi prefix thì đó là ledger variant mới, phải validate lại |
| Temporal revision | Future-effective, late, correction, retraction, conflict | Task definition; chỉ gold bị ảnh hưởng mới đổi | BM05/BM07; GSM bổ sung valid/known matrix và precedence |
| Retrieval difficulty | Sai driver, sai kỳ, sai edition, gần ngưỡng, thiếu bridge | Answerable core không bị đổi truth bởi distractor | BM05/BM06; tạo intentional conflicts trong stratum riêng |
| Construction | Mode A deterministic và Mode B natural-language extraction | Visible source information, queries, gold | Contract GSM; không coi đây là ablation ranking |
| Memory scale | Chunks, entities, events/entity, edges, revisions, update rate, concurrency | Core questions/proofs ở bài stress distractor | BM01/BM06 gợi ý growth; GSM đo thêm serving/database dimensions |
| Context selection | Candidate pool → selected context dưới budget | Reader và output rubric | BM04; tách L1 khỏi L3/L4 |

Không lấy full Cartesian product. Core chạy direct wording ở scale nhỏ trước; tiếp theo dùng paired wording subset, temporal subset và scale subset. Chỉ phối hợp nhiều axes khi đã có giả thuyết lỗi cụ thể.

### 3.1. Corpus decision đã chốt

`retrieval_full` gồm 224 real articles, là corpus mặc định cho baseline document/hybrid khi pipeline đã chạy; `debug_core` gồm sáu audited snapshots để kiểm tích hợp. Primary-gold sources hiện có bốn: P154/P151/P05/P23, chỉ reviewed TEXT spans. P172/P26 là audited distractors; 218 bài bổ sung chưa có relevance judgments đầy đủ. Hai profiles dùng chung ba synthetic version documents và 12 definitions, cùng operational facts/revisions và conventions. Publication metadata cho nguồn bổ sung phải được materialize theo 05; không hứa giữ nguyên bytes/counts của release sáu bài cũ.

42 queries giữ semantics fixed-edition: app cấp source reference, prefilter hợp lệ có thể thu policy document candidates còn một bài, nhưng vẫn phải tìm clauses/definitions và KG evidence. Log counts trước/sau edition filtering; không gọi corpus expansion là document-discovery benchmark. Discovery subset sau pilot cần public disambiguating context, reviewed gold/answerability và protocol version riêng; không suy policy hiện hành từ crawl thiếu lịch sử.

Unreviewed không đồng nghĩa irrelevant; nguồn khác có text giống không tự thành alternative proof. Review có mục tiêu các near-gold passages và pooled top results; pin qrels universe/coverage theo 01 §8.2 và 05 §6.6. Không cần executable rule cho 218 bài bổ sung. Profile identity chỉ thay document retrieval configuration, không tạo thêm semantic cases/worlds hoặc tăng số independent samples. Corpus roles/task bindings private; A/B phải dùng cùng active profile, scope và cutoff. Giữ graph construction cố định trong document-corpus comparison; KG scalability là trục khác.

### 3.2. Scenario → semantic cases → query renderings

`ScenarioManifest` là **private evaluation sidecar**, không là business entity/predicate. Một scenario là tình huống gốc; variant mô tả world/observation/presentation được chọn; semantic case chốt phép hỏi và snapshot; rendering chốt wording. Query trước/sau correction có thể là hai cases trong cùng variant, còn paraphrases là nhiều renderings của một case.

| Field/group | Contract tóm tắt |
| --- | --- |
| `scenario_id` | Root tình huống, dùng lại trong `QueryGold.scenario_id`. `base_scenario_id` là alias suy ra bằng giá trị này trong release v0.2, không lưu hai cột cùng nghĩa |
| `scenario_variant_id`, `parent_variant_id`, `mutation_type` | Một manifest row/variant; root có parent=null. Parent DAG acyclic; mutation có input targets/delta và invariants |
| `world_id`, `ledger_id`, `scope_id` | World truth tách khỏi observation branch. World perturbation tạo world mới; mask/conflict/retraction fixture có thể dùng world cũ với ledger branch mới |
| `gold_track`, `task_id` hoặc `foundation_task` | Chính xác một loại task, đúng whitelist/synthetic-control scope |
| `policy_snapshot_refs`, `public_snapshot_refs` | Pin source snapshots và packages theo `(world,ledger,scope,known_as_of)`; không tạo fake policy history |
| `semantic_case_ids`, `query_ids` | Truy vết cases và renderings; không nhét gold labels vào RuntimeQuery |
| `split_group`, `seed` | Tất cả variants/cases/renderings và shared histories cùng group; seed streams có version |

Known-time pair chỉ chọn hai prefixes của cùng ledger; không tạo world mới. Query false-premise không mutate nguồn. Presentation changes không được đổi clocks hoặc publication order. `05` quy định fields, enums, FK và check cụ thể; future extensions ngoài contract phải version lại.

## 4. Mapping cụ thể theo bảy policy tasks

Đây là nơi xác định **dữ liệu phải sinh**, thay vì chỉ dán tên benchmark vào Q1–Q7.

| Task / family | Dữ liệu và query phải tạo | Minimal evidence và gold | Negative / distractor quan trọng | Cơ chế benchmark áp dụng |
| --- | --- | --- | --- | --- |
| T01 / PF01 | Câu hỏi về scope, định nghĩa ngày vận doanh hoặc công thức của edition P154; giữ snapshot gốc | Clause/definition đúng nội dung được hỏi + source locator; đáp án source-grounded | Một actual corpus document/snapshot khác có topic/scope gần, như khác vùng hoặc kỳ tính; không giả định supersession/version relationship nếu chưa có bằng chứng. Hỏi hiệu lực hiện hành khi nguồn không đủ phải tách khỏi T01 | BM05 evidence-first; BM02 wording |
| T02 / PF01 | Sinh program/operating-region intervals và `RM_OPDAY`, `RM_REVENUE` cùng ngày W; queries không tiết lộ doanh số cần retrieve | Nếu premises E đúng: `max(280000−R,0)/5`; proof có rule, definitions, states/reports cần thiết và version tại known cutoff | R của người khác/kỳ khác; report bị sửa; thiếu operating-day; conflict ngang quyền; E=false khác amount=0 | BM05 distributed evidence; BM07 replay; BM04 fixed-reader control |
| T03 / PF02 | Bike program và `RM_ACCEPTANCE` đúng window/checkpoint; lấy các điểm dưới/bằng/trên 1/2 | Chỉ điều kiện AR<1/2 và literal action đến 23h59; không thực hiện action thật | Sai window, nhầm < thành ≤, nhầm ngưỡng chế tài tuần, program không phù hợp | BM02 false-premise; BM05 boundary + distractors |
| T04 / PF03 | Queries về FAQ P05: clock dùng tính điểm, đơn vị đa điểm, rating/unrated và tuần | Gold từ các TEXT spans tương ứng; không cần sinh trips/raw ratings để trả lời định nghĩa | Clock trả chuyến thay clock khách đặt; chuyến thay điểm giao; unrated bị coi 0 sao; OCR table chưa duyệt | BM05 clause-level evidence; BM02 phrasing |
| T05 / PF03 | `RM_RATING` theo tuần chính xác; giá trị 4,84/4,85/4,86 hoặc rational tương đương; explicit undefined | `rating_condition_met=(rating>97/20)`; gold chỉ riêng điều kiện rating, không full reward eligibility | Rating sai tuần, làm tròn vượt boundary, undefined/missing, đúng sao nhưng kết luận luôn được thưởng | BM05 evidence/rubric; BM04 premise/scope controls |
| T06 / PF04 | Queries hỏi nhóm trong P23 và literal kỳ lương tháng 6/2026 | Scope clause hoặc date clause tùy câu hỏi; không chuyển payroll thành calendar interval | Dẫn P172 thay notice P23; tự thêm Depot 2; tự chọn ngày đầu/kết thúc kỳ lương | BM02/BM05 source-grounded question design |
| T07 / PF04 | Synthetic Taxi/Bike program, `MEMBER_OF` tại T/as-of A, registry map tên Depot→IDs; hỏi nhóm notice nêu | Rule scope lấy từ P23 + program + fleet/mapping cần thiết; true/false/insufficient/conflict theo proof | Fleet đổi, cùng tên, Depot 2, Bike driver; false không đồng nghĩa vẫn được thưởng | BM03 identity/history; BM05 complementary evidence; BM07 state revision |

T07 không mặc định là Q5. Nếu một membership edge và mapping tên đã đủ thì đó là proof hợp lệ. Q5 bắt buộc dùng foundation rule có operand `fleet_region` và path `MEMBER_OF → BASED_IN`; cạnh `OPERATES_IN` không được thay thế.

T05 có thể được gọi từ context đã chỉ rõ task/định nghĩa; không phải thêm toàn bộ program/cohort của chương trình thưởng để chấm riêng phép so sánh rating. Ngược lại, nếu query hỏi toàn bộ quyền lợi thì phải chuyển sang task chưa được hỗ trợ, không âm thầm dùng T05 trả lời thay.

## 5. Cách tạo query variants mà không làm hỏng gold

Các ví dụ sau đều giả định application context công khai đã chỉ rõ driver, kỳ đo và edition/conventions cần thiết. Không đưa các giá trị gold cần retrieve vào query.

| Variant | Ví dụ / thao tác | Gold thay đổi thế nào? | Điều kiện hợp lệ |
| --- | --- | --- | --- |
| Direct | “Theo riêng rule P151 được cấp, rate của D tại checkpoint này có thỏa điều kiện auto-accept không?” | Semantic case gốc | Driver/window/source scope xác định |
| Dialog | “Anh kiểm tra giúp em điều kiện tự động nhận đơn ở mốc đó với.” | Giữ answer/proof khi context xác định “em” và “mốc đó” | Không giả có lịch sử chat mà runtime chưa được cấp |
| Implicit | “Với số liệu ở mốc đó, em cần lưu ý gì về chế độ tự động nhận đơn?” | Giữ claim chính; output rubric cho phép diễn đạt phù hợp | Câu hỏi vẫn chỉ đến rule đang kiểm, không mở thành mọi chế tài |
| False-premise | Trong fixture có AR=50% nhưng query không tiết lộ số đó: “Em nhớ số liệu ở mốc đó vẫn thuộc nhóm dưới ngưỡng kích hoạt, đúng không?” | Giữ source truth; thêm yêu cầu bác bỏ premise sai | Có proof bác bỏ thì expected_status=answerable, không ép abstention. Đây không phải thay world hoặc cập nhật memory |
| Composed | “Mốc nào dùng tính điểm đa điểm, và một đơn nhiều điểm được đếm theo đơn vị nào?” | Tạo rubric nhiều phần và proof cho từng phần; không nhận hoàn thành khi chỉ trả một phần | Chỉ compose tasks/claims đã được duyệt, cùng source/scope; không gộp thành quyền lợi mới |
| World perturbation | Đổi report từ 49% thành 50% trong một sibling fixture | Recompute answer và proof; verdict có thể đổi | Cùng schema; sibling giữ chung split; đây khác paraphrase |
| Known-time pair | Giữ W, hỏi trước/sau correction được công bố | Recompute visible facts và gold tại từng A | Hai known cutoffs; source publication/availability được kiểm |
| Harmless distractor | Thêm rating của driver khác hoặc tuần khác | Gold không đổi | Validator chứng minh record không tạo alternative support hoặc conflict liên quan |

Trong LoCoMo-Conv, “counterfactual” chủ yếu là query chứa tiền đề sai cần sửa, không phải phép can thiệp causal vào world. Mapping GSM giữ sự khác nhau này. Một request chủ động báo sửa thông tin và một câu hỏi kiểm tra thông tin không được tự động cùng đi vào write path.

Không bắt mọi implicit answer phải lặp lại nguyên văn mọi fact. Chấm claim cần cho task và citations hỗ trợ nó. Ngược lại, câu trả lời chung chung “hãy kiểm tra lại chính sách” không được nhận full task success khi task yêu cầu verdict/amount xác định.

## 6. Quy trình tạo dữ liệu và gold

| Bước | Input → output | Cơ chế áp dụng / kiểm tra |
| --- | --- | --- |
| 1. Pin sources và bindings | Snapshots/clauses đã audit → source catalog + bindings private của T01–T07 theo schema 02 | Dùng lại audit 02; không cho LLM invent exception, effective date hoặc denominator |
| 2. Sinh structured world và observations | Config/seed → states/events/reports → immutable source ledger + observation plan | Lịch sử nhất quán kiểu BM03; giữ scope, IDs, cardinality và atomic corrections |
| 3. Chọn semantic cases và proof | Visible ledger prefix + reviewed binding → expected status/answer + support atoms/proof | Evidence-first kiểu BM05; truth theo thông tin được phép biết, không lấy hidden world lấp phần bị che |
| 4. Tạo public projections | Cùng public records → structured inputs Mode A, narratives Mode B, document corpus | Mọi projection có source links; narratives không thêm/bớt facts quyết định gold; real policy text giữ snapshot |
| 5. Render queries và distractors | Semantic cases → direct/paired queries; core corpus → controlled haystacks | BM02/BM01/BM06; LLM chỉ hỗ trợ ngôn ngữ. Review entity/time/scope, negation và answer leakage |
| 6. Validate, split và release | Sources + cases + proofs + outputs → versioned dataset | Conformance trước full generation; freeze test sau pilot và trước proposed-system tuning |

Gold generator không truy vấn Graphiti để xác định đúng/sai. Mode A không được gọi private gold evaluator trong runtime. Nếu reducer được tái sử dụng giữa generator và adapter, cần hand-checked fixtures và kiểm tra độc lập các case thời gian để tránh hai bên cùng đúng theo một bug.

Tách rõ hai nghĩa “truth”: private world kiểm generator, còn gold chấm agent theo **visible evidence**. Nếu nguồn ngang quyền bất đồng, hidden world biết giá trị nào thật cũng không cho evaluator ép agent chọn giá trị đó.

| Vật mang dữ liệu trong 02 | Cách dùng trong generator benchmark | Public/private |
| --- | --- | --- |
| `SourceDocumentSnapshot`, `PolicyClause` | Policy source với hash/locator/review state | Nội dung và provenance public; annotation quyết định task private |
| `SourceRecord`, `AssertionVersion` | Assertions và logical revision stream | Prefix hợp scope public |
| `ReportedMeasure` | Nguồn đã báo một số liệu/status cho đúng kỳ | Public; không giả có raw-event lineage |
| `MetricArtifact` + coverage/source set | Derived aggregate có khả năng tái tính | Artifact và nguồn được phép public; không cấp verdict policy sẵn |
| `SupportAtom`, `EvidenceProof` | Gold semantic units và AND/OR proof alternatives | Private |
| `ProjectionLink` | Map clause/assertion nguồn sang chunk/edge của từng system | Public audit mapping; không chứa relevance labels |
| `QueryGenerationTrace`, `QueryGold` | Case ID, style, sibling group, tags, difficulty, split | Private; lưu metadata vào cấu trúc evaluation/sidecar, không thêm business predicate |
| `RuntimeQuery` | Natural-language request + context thực sự được cấp | Public; không có task ID/gold family/required proof hint ngầm |
| `IngestionReceipt` và run traces | Thời gian nạp thực tế, errors, candidates, selected context, answers | Run artifact; gold-enriched trace chỉ evaluator đọc |

Benchmark IDs là **BM01–BM10**; business tasks là **T01–T07**. Bindings đã freeze trong 02 giữ tên B01–B07, luôn tham chiếu đầy đủ `task_binding:B02@1.0` hoặc “binding của T02”; không dùng bare Bxx trong 04/05 để gọi benchmark. Không đổi IDs của normative schema chỉ để sửa cách đặt tên tài liệu.

## 7. Worked design: một T02 tạo được nhiều phép kiểm tra

Fixture dùng edition P154 và conventions BC01–BC07 dưới giả định được nêu công khai. W là ngày 14/09/2026 ở Việt Nam: `[2026-09-13T17:00Z, 2026-09-14T17:00Z)`. Driver là Bike partner, operating region HN ổn định suốt W; nguồn xác nhận operating-day=true. Đây là scenario tổng hợp, không tuyên bố P154 đang hiệu lực vào ngày này.

| Sự kiện nguồn | Valid/measurement extent | Known/publication time | Nội dung |
| --- | --- | --- | --- |
| Policy/definitions được cấp cho fixture | Theo source/task semantics, không backdate normative history | 16/09 00:00Z | Snapshot và conventions có thể được retrieve |
| Report r1 | W | 16/09 01:00Z | `RM_REVENUE=200000` |
| Correction r2, target=r1 | Cùng W | 17/09 01:00Z | `RM_REVENUE=240000`; đóng known interval của r1 |

| Case | Corpus/query variation | Gold hợp lệ | Failure được phân biệt |
| --- | --- | --- | --- |
| A — historical knowledge | Query A0=16/09 12:00Z; chỉ prefix trước correction | `(280000−200000)/5=16000` VND, dùng r1 | Dùng future r2 là known-time leak |
| B — revised knowledge | Query A1=17/09 12:00Z; correction đã visible | `(280000−240000)/5=8000` VND, dùng r2 | Dùng r1 như current report là stale evidence |
| C — wording pair | Cùng case B, đổi direct sang dialog/implicit đã review | Cùng amount và proof; wording được đổi | Recall giảm do cách hỏi; không phải lỗi temporal reducer |
| D — irrelevant scale | Giữ B, thêm reports của drivers/kỳ khác | Cùng gold 8000; cost/latency có thể tăng | Entity/window contamination hoặc bottleneck |
| E — missing evidence sibling | Case B nhưng report cần thiết bị che; không còn alternative report hợp lệ | `insufficient_evidence`; amount=null | Tự suy từ world truth hoặc R=0 là sai |
| F — conflict sibling | Thay correction bằng hai active claims 200000/240000 ngang quyền | `unresolved_conflict`; amount=null | Chọn claim mới nhất trái source semantics |

Minimal proof của A/B gồm rule clause, quantity/window definitions, identity/scope và những state/report premises cần thiết. Không ép lấy cả r1/r2 khi câu hỏi chỉ cần current amount; nếu hỏi “vì sao thay đổi?” thì proof phải thêm revision lineage và hai phiên bản cần so sánh. Report không đủ để chứng minh app đã tính đúng doanh số từ trips.

Các trường hợp A–F cùng nguồn gốc scenario phải ở một split group. Hai sibling E/F là mutations riêng, không là hai trạng thái xảy ra đồng thời trong cùng fixture.

## 8. Pilot và mở rộng với chi phí kiểm soát được

Giữ starting target của 02: khoảng **8 drivers, 80 terminal trips và 42 runtime queries**. Các reports, source revisions, coverage records và document units được đếm riêng. Chỉ cần catalog có các Depot IDs cần cho T07; không tạo hàng loạt fleet histories để tăng số lượng.

Bảng sau là **allocation đề xuất**, chưa phải dữ liệu đã sinh. Các case trong 25 worked examples của 02 được dùng làm seeds; chúng chưa phải 25 mẫu test độc lập.

| Cohort | Số queries pilot | Nội dung ưu tiên |
| --- | ---: | --- |
| T01 | 2 | Scope/định nghĩa và công thức source-grounded |
| T02 | 11 | EX01–EX06, EX13–EX17: numeric boundary, missing, wrong entity, correction, conflict, retraction |
| T03 | 3 | EX07–EX09: dưới/bằng ngưỡng và sai kỳ |
| T04 | 3 | Clock, đơn vị đa điểm, rating/week/unrated definitions |
| T05 | 3 | EX10–EX12: strict boundary, đạt điều kiện, undefined |
| T06 | 2 | Nhóm Depot và kỳ lương literal |
| T07 | 4 | EX18–EX20 và một membership revision case |
| Foundation controls | 14 | Bao gồm EX23–EX25; thêm identity, state/time, coverage/denominator và synthetic-version cases |
| **Tổng** | **42** | 28 policy-task queries + 14 foundation queries |

Đây là grouping theo task, không phải phân bố primary Q1–Q7. Một T02 correction có primary family Q6, một T02 conflict có thể là Q7. Mandatory conformance fixtures ngoài 42 queries vẫn phải chạy theo 02; không cắt invariants để khớp bảng số lượng.

| Giai đoạn | Dataset work | Điều kiện chuyển bước |
| --- | --- | --- |
| Pilot core | 42 canonical queries, đủ nguồn/proofs; `debug_core` cho positive + negative path, sau đó baseline mặc định `retrieval_full` | C0 traces và full-profile readiness theo 05; numeric/status/source/time đúng; không coi snapshot-bound queries là discovery |
| Wording diagnostic | Chọn subset answerable, thêm dialog/implicit và false-premise pairs | Equivalence/answerability review; gold constraints không đổi ngầm |
| Temporal replay | Known checkpoints, corrections/retractions, stale dependent artifacts | Reducer/projection conformance; snapshot correctness tách update lag |
| Frozen comparison set | Tăng độc lập scenario groups và drivers; khóa templates/gold/splits | Không còn ambiguity ảnh hưởng answerable gold; pin reader/budget/config |
| Scale | Ít nhất ba mức N khả thi sau pilot; one-axis studies trước mixed workload | Chất lượng, p50/p95, throughput/cost và ingestion freshness được đo |
| Optional diagnostics | Composed requests, read-only task chain, attribution challenge | Baseline đã chỉ ra nhu cầu; không mở domain DEFER để đủ paper coverage |

Không áp ngay mọi style lên cả 42 câu rồi gọi vài trăm paraphrases là dataset lớn. Số **scenario groups độc lập**, số semantic questions và số rendered variants phải báo riêng. Full test query count/seed list chốt sau pilot theo chi phí và uncertainty cần báo, chưa invent power target ở đây.

Public benchmark replication là một đường riêng. Research report hiện ưu tiên LongMemEval và một multi-hop subset có ngân sách; bảng này không thay quyết định đó bằng yêu cầu chạy cả mười. Nếu chạy subset, lưu IDs/version/protocol và gọi đúng là subset result. Dataset GSM được biến đổi không có official LoCoMo/LongMemEval score.

## 9. Splits, leakage và so sánh baseline–proposed

| Rủi ro | Quy tắc thiết kế |
| --- | --- |
| Paraphrases, before/after hoặc mutations lọt qua dev/test | Toàn bộ siblings của một base scenario nằm cùng split group; confidence intervals resample theo group, không theo từng câu diễn đạt |
| Đánh đồng nhiều loại generalization | Main holdout dùng driver/scenario groups; template/style holdout là stress slice riêng. Không tuyên bố đồng thời held-out policy families khi chỉ có bốn families hoạt động |
| Trùng policy clauses qua dev/test | Cho phép trong in-domain retrieval evaluation và công bố rõ. Muốn kiểm unseen-policy transfer phải tạo split riêng đủ nguồn; hiện chưa được chứng minh |
| Metadata trả sẵn đáp án | Không export expected roles, `eligible_for`, gold family hoặc P23→target Depot set; registry chỉ names/aliases→IDs |
| Query đã chứa metric/fleet kết luận | Không đặt doanh số/rating cần retrieve hoặc membership gold vào câu hỏi chính. Cases có input trực tiếp phải là control riêng |
| Future leakage | Retriever, source tools, profiles, caches và resolver chỉ nhận cùng visible prefix/scope; không giữ summary từ tương lai |
| Nhiều queries dùng chung history làm nhiễm nhau | Index/ingested memory dùng chung, nhưng các probes độc lập không ghi câu hỏi/answer/gold trở lại memory. Read-time writes nếu có phải reset/clone hoặc đưa vào protocol stateful riêng |
| LLM viết text và tự quyết gold | Gold từ reviewed clauses + structured reducer/formulas. LLM chỉ render/paraphrase, hỗ trợ kiểm; hard numeric/status chấm xác định |
| Baseline và proposed không cùng budget | Cùng public inputs, snapshot, reader, max context và gold. Log retrieval calls/tokens/latency riêng; methods có thêm tool budget phải báo trade-off |
| Đổi construction rồi nhận công là retrieval improvement | Main retrieval comparison giữ construction mode. Mode A/B là experiment riêng; đo construction errors trước L1–L4 |
| Feedback từ test dùng để cải thiện cùng test | Không cập nhật prompt/rules/router từ test answers. Feedback learning nếu mở sau phải có adaptation stream và held-out test riêng |

Trong core, incremental updates là **nguồn nghiệp vụ thay đổi độc lập với câu trả lời agent**. Trong MemoryBench-style learning, feedback phụ thuộc output agent. Trong MemoryArena-style environment, actions có thể ảnh hưởng observations kế tiếp. Ba protocol này không thay thế nhau.

## 10. Metrics cần dataset hỗ trợ

| Tầng | Nhãn/trace cần có | Metric và ý nghĩa |
| --- | --- | --- |
| Construction diagnostic | Canonical visible assertions và projection/source mappings | Sai entity/time/revision, mất event hoặc provenance; biết lỗi xuất hiện trước search |
| L1 — Document retrieval | Clauses, acceptable equivalents, qrels version/universe, judged coverage; profile và counts trước/sau filtering | Known-gold coverage khi qrels thiếu; Precision/MRR/nDCG theo 01 §8.2, N/A khi thiếu judgments; sai source/version không hoàn thành proof |
| L1 — KG/hybrid retrieval | Entity IDs, required relations/paths, support atoms | Candidate complete-proof rate, minimal-evidence coverage, valid bridge coverage; không dùng node-ranking score thay path correctness |
| L2 — Entity/time | Query valid time, known cutoff, exact measure window, source rank | Entity accuracy, stale/wrong-window rate, historical state accuracy và conflict handling |
| L3 — Context | Candidate pool, selected units, context thực gửi reader, budget | Selected complete-proof rate, evidence precision, redundancy, source-role coverage, token cost |
| L4 — Reasoning | Structured answer/status, scope rubric, claim–citation mapping | Numeric/decision correctness, grounding, citation correctness, unsupported scope expansion |
| Q7 | Missing roles, conflict groups, identity ambiguity | Status confusion matrix; abstention precision/recall và false-abstention trên answerable cases |
| Replay | Publication times, receipts, indexed state theo checkpoint | Time-to-searchable, correction adoption, stale duration, write amplification; API failures tính riêng |
| Scale | Actual chunks/entities/edges/events/updates/concurrency | Quality–latency–cost curves; read/write API calls, storage, p50/p95, p99 khi đủ samples |

Với query answerable q, gọi \(\mathcal{P}_q\) là tập các minimal sufficient proofs hợp lệ và \(M(S)\) là atoms được evidence S hỗ trợ đúng entity/time/source. Dùng định nghĩa của 01/02:

\[
\operatorname{Complete}(S,q)=\mathbf{1}\{\exists P\in\mathcal{P}_q:P\subseteq M(S)\},\qquad
\operatorname{Coverage}(S,q)=\max_{P\in\mathcal{P}_q}\frac{|P\cap M(S)|}{|P|}.
\]

Chấm cả candidate C và selected bundle E. Nếu `Complete(C,q)=1` nhưng `Complete(E,q)=0`, vấn đề ở context selection. Nếu `Complete(E,q)=1` mà answer sai, điều tra reader/reasoning; không tự quy là thiếu memory. Non-answerable cases không có empty proof để nhận điểm 1; dùng status/proof-of-conflict diagnostics phù hợp.

Trong mỗi comparison giữ ba controls: **no retrieved context**, **retrieved context**, **gold evidence context** với cùng reader. Gold context lấy public source evidence đủ chứng minh, không chứa private answer hoặc reasoning đã giải sẵn. Nếu gold proof không vừa budget, báo riêng. No-context success kiểm nguy cơ shortcut nhưng không tự động loại mẫu theo một model cụ thể; fixed gold/source criteria mới là chuẩn.

Numeric/status và identity/time ưu tiên exact deterministic scoring. Free-form explanations dùng claim rubric có human audit; không thay toàn bộ L1–L4 bằng một LLM judge hoặc BLEU/ROUGE. Không dùng một điểm tổng hợp để che lỗi temporal/hybrid hoặc scope expansion.

## 11. Quyết định triển khai sau mapping

| Quyết định | Phạm vi |
| --- | --- |
| Thiết kế core ngay | BM05 evidence-first, BM03 coherent ledger, BM07 replay và BM04 fixed-reader protocol; thiết kế knobs cho BM01/BM06 nhưng chưa chạy capacity study |
| Thứ tự thực thi | Canonical pilot với debug_core → baseline mặc định retrieval_full → BM02 wording diagnostic → BM01/BM06 scale-noise/cost experiments; không yêu cầu BEAM-scale ở release v0.2 |
| Áp dụng có giới hạn | BM10 attribution diagnostics, BM09 split discipline; không bật personalization hoặc feedback learning |
| Sau khi baseline có kết quả | Composed queries và MemoryArena-inspired read-only dependencies; chỉ là diagnostic GSM, không claim benchmark replication |
| Giữ nguyên schema | Không thêm operational predicate ngoài `REPORTED_MEASURE`/`DRIVER_PROGRAM`; evaluation tags dùng metadata/sidecars |
| Chưa freeze | Generator implementation, concrete generated dataset, split manifests, full test counts và empirical score targets |

Hai completion gates được tách rõ:

| Gate | Bằng chứng bắt buộc | Không phải điều kiện của gate |
| --- | --- | --- |
| Data Freeze Gate | Sources/ledger, ScenarioManifests, queries, reviewed gold/proofs, split groups, versions/hashes và independent data validation | Không cần Graphiti loader, embeddings, baseline score hoặc agent run |
| Benchmark Readiness Gate | Frozen dataset + Graphiti/document loaders + baseline execution + projection links, evaluator và traces | Không thay thế Data Freeze; baseline có lỗi vẫn phải được đo/truy nguyên, không chỉnh gold cho baseline pass |

Các input packages có thể được validate như dữ liệu trước khi loader tồn tại; chunk IDs, Graphiti UUIDs và ingestion receipts quan sát được nằm trong run artifacts. `05_dataset_release_spec.md` chốt exact files, 42-query catalogue, generator stages và Data Freeze Gate. Trạng thái hiện tại là design/specification, chưa có generated dataset được nghiệm thu.

Đóng góp phương pháp của dataset GSM sẽ nằm ở việc kết hợp **policy evidence + entity/temporal evidence + complementary proofs + scale/update evaluation** trong contract đã chốt. Đây là lựa chọn thiết kế của dự án; mười benchmark cung cấp các cơ chế tham khảo, chưa chứng minh tính đúng hoặc production applicability của hệ thống GSM.
