# GSM — Problem Definition and Evaluation Contract

**Mục tiêu:** trong sáu tuần, xây dựng và đánh giá một AI Agent có memory, với trọng tâm là truy xuất bằng chứng từ tài liệu doanh nghiệp và temporal Knowledge Graph về tài xế.

**Phiên bản contract:** v0.1.1 — bổ sung corpus profiles và incomplete-judgment protocol ngày 16/09/2026. Tài liệu quy định phạm vi, giao diện và cách đánh giá; không chứng nhận hệ thống đã đạt yêu cầu production. `MUST` là bắt buộc; `PENDING` là đầu vào chưa xác nhận.

**Cơ sở:** `docs/research/gsm_retrieval_research.md`, đặc biệt mục 2, 7–14, 16; đối chiếu tab `Paper matrix` của `docs/research/gsm_paper_matrix.xlsx`. Giữ các ưu tiên P01, P13, P26 và lựa chọn đánh giá P04, P06, P11, P21–P25. Các định nghĩa metric dưới đây là quy ước triển khai của dự án, không phải kết quả thực nghiệm đã có.

## 1. Problem Definition

Về nghiệp vụ, agent phải tìm được quy định áp dụng và dữ kiện liên quan đến tài xế để trả lời hoặc hỗ trợ một tác vụ vận hành. Đúng chủ đề chưa đủ: bằng chứng có thể sai người, sai phiên bản, thiếu ngoại lệ hoặc không cùng thời điểm.

Về kỹ thuật, dự án thiết kế và đánh giá một retrieval layer có khả năng mở rộng, kết hợp document memory và temporal KG. Đầu ra phải chính xác, đủ cho tác vụ, phù hợp thời gian và truy vết được nguồn, trong giới hạn latency, chi phí và freshness.

Ký hiệu:

$$
C(q)=D(q)\cup G(q),\qquad E(q)=\operatorname{Select}(C(q),B),\qquad y=A(q,E(q)).
$$

`D`, `G` là các tập ứng viên theo từng nguồn; phép hợp giữ nguyên loại evidence. `E` là bundle thực sự cung cấp cho agent, `B` là ngân sách evidence tokens. Ba đối tượng MUST được đánh giá riêng:

| Đối tượng | Câu hỏi đánh giá | Ví dụ thất bại |
| --- | --- | --- |
| Retrieval | Bằng chứng cần thiết có trong `C` không? | Thiếu clause hoặc bridge |
| Context construction | `E` có giữ đủ bằng chứng đúng từ `C` không? | Rerank/packing bỏ ngoại lệ |
| Agent reasoning | Agent có sử dụng `E` đúng không? | Đủ evidence nhưng kết luận sai |

Đối tượng tối ưu là retrieval và context construction; agent là tầng kiểm chứng tác dụng downstream. Document retrieval cần clause, version và applicability. KG retrieval cần identity, relations, paths, trạng thái và provenance. Hai nguồn có thể đảm nhận các vai trò logic bổ sung.

Một query answerable chỉ thành công toàn tuyến khi đủ evidence hợp lệ, context tuân thủ contract và đầu ra đúng, có căn cứ. Câu trả lời đúng nhờ kiến thức sẵn có nhưng thiếu bằng chứng không được tính là grounded success.

## 2. Scope

Trong phạm vi: truy xuất tài liệu; temporal KG; evidence về profile/behavior; entity resolution; source provenance; liên kết document–KG; chọn context; reasoning và tác vụ mô phỏng; incremental updates/corrections; đánh giá chất lượng, latency, throughput, storage và chi phí.

Sản phẩm là một hệ thống tích hợp có adapters, dữ liệu đánh giá, logs và kết quả chạy lại được. Tái sử dụng framework và database sẵn có. Graphiti là graph layer tham chiếu ban đầu.

## 3. Non-Scope

Ngoài phạm vi: huấn luyện foundation model mới hoặc graph foundation model lớn; viết graph/vector database; tái tạo toàn bộ memory framework; giải quyết mọi bài toán conversational memory; tái lập mọi paper; hoàn tất HA, security và DevOps production.

Tuy nhiên, access scope, tính đúng của evidence và đo giới hạn vận hành vẫn bắt buộc trong prototype. Không suy ra đánh giá hành vi tài xế thật từ dữ liệu giả lập.

## 4. Retrieval Contract

### 4.1. Request

Đây là schema logic cho adapter, không phải schema nội bộ GSM.

| Trường | Quy định |
| --- | --- |
| `request_id`, `query_id`, `query` | Bắt buộc; ID ổn định trong run và nguyên văn query |
| `entity_refs` | ID/alias được cung cấp; nullable. Khóa nghiệp vụ và cách resolution: **PENDING schema** |
| `time_scope` | Chế độ current, point hoặc interval; chứa `valid_at`/window khi cần. Ngày và timezone phải được giải nghĩa rõ |
| `known_as_of` | Tùy chọn cho câu hỏi “hệ thống đã biết gì”; thiếu nghĩa là snapshot hiện tại của run, không bỏ qua valid time |
| `access_scope` | Bắt buộc từ application context; demo dùng scope tổng hợp. Mapping quyền GSM: **PENDING** |
| `query_type_hint` | Tùy chọn, có nguồn gốc; gold `query_family` chỉ dành cho evaluator |
| `context_token_budget` | Bắt buộc; ngân sách evidence sau serialization theo tokenizer đã pin |
| `deadline`, `retrieval_config_id` | Bắt buộc trong experiment; giá trị cấu hình được lưu, chưa coi là production SLA |

Thiếu ID hoặc ngày quan trọng MUST dẫn tới resolution/clarification có ghi nhận. Không tự chọn tài xế theo tên gần nhất hoặc thay thời điểm lịch sử bằng “bây giờ”. Với current query, ghi thời điểm đã dùng. Chế độ thời gian không được hỗ trợ phải trả trạng thái tương ứng.

### 4.2. Evidence unit

| Trường | Quy định |
| --- | --- |
| `evidence_id` | ID ổn định theo nội dung/phiên bản; có mapping sang gold support atom |
| `source_type`, `evidence_kind` | Nguồn: document, KG, source event, computation; loại: clause, fact, path, event, measure, summary, inference |
| `source_id`, `source_version` | ID nguồn và phiên bản/snapshot; mapping nghiệp vụ **PENDING schema** |
| `entity_ids` | Entity đã resolution; document chung có thể là danh sách rỗng |
| `content` | Text nguyên gốc hoặc structured fact; không dùng summary thay nguồn gốc |
| `graph_structure` | Nếu có: node/edge IDs, relation type, direction, ordered path hoặc subgraph edges |
| `event_time`, `valid_time`, `known_time` | Thời gian phù hợp loại evidence; phân biệt unknown, not-applicable và open-ended |
| `provenance` | Locator tới clause/span/event; nguồn và version của extraction/derivation; dependency IDs |
| `claims_supported`, `evidence_roles` | Claim/role mà unit được đề xuất hỗ trợ; không tự coi là gold label |
| `applicability_status` | Applicable, historical/comparison context, conflicting hoặc unverified, kèm lý do |
| `scores` | Method, stage, rank, raw score; score nullable nếu không áp dụng, có lý do |
| `token_cost` | Chi phí text/fact đã serialize; kiểm tra thêm tổng bundle gồm separators/metadata |

Một graph assertion và đoạn text sinh ra assertion đó không phải hai nguồn độc lập. Derived measure MUST có công thức, cửa sổ, phạm vi dữ liệu và phiên bản phép tính; inference MUST được gắn nhãn suy diễn.

### 4.3. Response và trace

Response gồm resolved request, snapshot IDs, candidate sets theo nguồn/stage, selected bundle có thứ tự, excluded evidence/reasons, roles còn thiếu, conflicts, budget sử dụng, latency và limit flags. Agent chỉ nhận selected bundle; evaluator giữ toàn trace.

Trạng thái gồm `evidence_available`, `insufficient_evidence`, `unresolved_conflict`, `ambiguous_request`, `unsupported`, `timeout`, `error`. `evidence_available` không chứng nhận sufficiency; empty result do backend lỗi không được đổi thành “không có dữ kiện”.

## 5. Query Families

| Family | Pattern tổng hợp | Năng lực cần kiểm tra |
| --- | --- | --- |
| Q1 — Document/Policy | SOP X yêu cầu gì dưới điều kiện Y? | Clause, applicability, version, exception |
| Q2 — Driver/Entity State | Tài xế D ở trạng thái nào tại T? | Identity và historical state |
| Q3 — Behavior/History | Events nào hỗ trợ nhận định X trong window W? | Phân biệt quan sát, measure, summary, inference |
| Q4 — Hybrid | Với trạng thái D tại T, policy P có áp dụng không? | Fact và rule cùng đủ, tương thích |
| Q5 — Multi-hop/Bridge | Bằng chứng trả lời chỉ tìm được qua entity/relation trung gian | Bridge/path coverage |
| Q6 — Update/Correction | Đáp án thay đổi thế nào sau update hoặc sửa lịch sử? | Old/new queries, valid-at, known-as-of |
| Q7 — Conflict/Insufficient | Có đủ dữ kiện để kết luận không? | Abstention, unresolved conflict |

Mỗi query có một primary family để tính macro score, cùng secondary tags cho các đặc tính chồng lấn. Quy tắc gán nhãn và phân bố MUST được đóng băng trước final test. Ví dụ ở đây không mô tả chính sách GSM thật.

## 6. Evidence Requirements

**Minimal sufficient evidence set** là một tập support atoms đủ chứng minh kết luận theo oracle, mà bỏ một atom sẽ mất sufficiency. Một query có thể có nhiều tập đúng hoặc nguồn tương đương. Không bắt hệ thống tìm mọi cách chứng minh.

Gold MUST được định nghĩa theo clause/fact/event/quan hệ hỗ trợ, có mapping sang chunk/edge IDs của từng index. Cách này tránh thay chunking làm thay đổi chính đối tượng được đánh giá. Role coverage không thay thế kiểm tra nội dung evidence.

| Family | Minimal evidence / constraints | Optional support | Distractors / failure điển hình | Provenance bắt buộc |
| --- | --- | --- | --- | --- |
| Q1 | Rule + điều kiện + applicable version; exception nếu liên quan | Định nghĩa, ví dụ SOP | Đúng chủ đề, sai vùng/version; thiếu ngoại lệ | Document/version, clause/span, effective interval |
| Q2 | Đúng entity + fact thỏa valid/known time | Event chuyển trạng thái | Trùng tên; stale/future state | Entity ID, fact ID, source event/version |
| Q3 | Events liên quan; measure cần đủ phạm vi tính; summary/inference phải có nguồn | Events bối cảnh | Top-k events bị coi là toàn bộ lịch sử | Event IDs; window, numerator/denominator, derivation version |
| Q4 | Driver facts + rule/exception + applicability bridge; thời gian tương thích | Định nghĩa điều kiện | Hai nguồn riêng đúng nhưng ghép sai | Cả hai nguồn và khóa/điều kiện join |
| Q5 | Ít nhất một đường/tập bridge hợp lệ tới evidence đích | Đường chứng minh thay thế | Node gần query nhưng thiếu cạnh nối | Edge IDs, direction/type, source và time |
| Q6 | Versions/events cần để so sánh theo query; update/correction links | Summary thay đổi | Nhầm arrival time với effective time | Before/after snapshots; valid/known intervals |
| Q7 | Conflict: các assertion bất đồng chưa phân xử; insufficient: xác định role còn thiếu | Partial evidence hợp lệ | Không tìm thấy bị biến thành phủ định chắc chắn | Nguồn đối lập hoặc search/coverage diagnostics |

## 7. Failure Taxonomy

Gắn nhiều error tags khi cần; ghi stage đầu tiên quan sát được lỗi, downstream symptoms và confidence của chẩn đoán. Không quy lỗi reasoning nếu selected context thiếu evidence. Lỗi extraction/ingestion phải được phân biệt với lỗi tìm kiếm trên graph đúng.

| Nhóm | Mã và nguyên nhân | Dấu hiệu chẩn đoán |
| --- | --- | --- |
| Construction | `I_ENTITY_MERGE/SPLIT`, `I_FACT`, `I_TIME`, `I_LINEAGE` | Gold ledger đúng nhưng index/graph biểu diễn sai |
| Document | `D_LEXICAL`, `D_SEMANTIC`, `D_DOCUMENT`, `D_SECTION`, `D_VERSION`, `D_EXCEPTION`, `D_RERANK` | Sai corpus item/section/version; gold có trước rerank nhưng mất sau đó |
| KG | `G_RESOLUTION`, `G_ENTITY`, `G_RELATION`, `G_BRIDGE`, `G_FANOUT`, `G_STALE`, `G_TIME_CONFLICT`, `G_PROVENANCE` | Nhầm identity; thiếu path; expansion dư; facts không tương thích |
| Hybrid/context | `H_JOIN`, `H_APPLICABILITY`, `H_SOURCE_DOMINANCE`, `H_REDUNDANCY`, `H_INCOMPATIBLE`, `H_SELECTION` | Thiếu role từ một nguồn; bỏ bridge; budget bị chiếm bởi evidence trùng |
| Agent | `A_REASONING`, `A_UNSUPPORTED`, `A_CITATION`, `A_ABSTENTION`, `A_ACTION` | Bundle đủ nhưng đáp án/hành động sai; inference không được hỗ trợ |
| Scale | `S_LATENCY`, `S_FANOUT`, `S_INDEX_GROWTH`, `S_RERANK`, `S_UPDATE_LAG`, `S_WRITE_AMP`, `S_CALLS` | Tail latency, backlog, resource/call growth hoặc chất lượng suy giảm |
| Contract/runtime | `C_SCOPE`, `C_BUDGET`, `C_SCHEMA`, `C_SNAPSHOT`, `R_TIMEOUT/ERROR` | Vi phạm scope/budget, trace không đủ, snapshot không nhất quán hoặc backend lỗi |

## 8. Evaluation Layers

### 8.1. Quy ước chung

Đánh giá cùng frozen queries, corpus snapshots và gold version. Báo per-family, macro average và sample counts; chỉ dùng trọng số nghiệp vụ sau khi được xác nhận. Dùng paired comparisons, confidence intervals 95% bằng bootstrap theo scenario/driver, không coi các paraphrase là độc lập.

Với tập evidence `S`, gọi `M(S)` là các support atoms được chứng minh hợp lệ; `Gq` là tập các minimal sufficient sets của query answerable:

$$
\operatorname{Complete}(S,q)=\mathbb{1}[\exists g\in G_q:g\subseteq M(S)],
\qquad
\operatorname{Coverage}(S,q)=\max_{g\in G_q}\frac{|g\cap M(S)|}{|g|}.
$$

Evidence sai entity, thời gian hoặc nguồn không được matching chỉ vì text giống. Tính `Complete`/`Coverage` tại candidate pool và selected bundle. Query không answerable không nhận sufficiency bằng một gold set rỗng; đánh giá expected status/abstention riêng. Metric không áp dụng ghi `N/A` cùng mẫu số.

### 8.2. L1 — Retrieval

| Metric | Định nghĩa / phạm vi |
| --- | --- |
| Recall@K | Relevant units duy nhất được lấy / tất cả relevant units đã gán nhãn; theo từng nguồn và stage |
| Precision@K | Relevant units trong K vị trí đầu / K; vị trí thiếu tính không relevant |
| MRR@K | Trung bình nghịch đảo rank của relevant item đầu tiên; không tìm thấy là 0; dùng khi một item có ý nghĩa đủ rõ |
| nDCG@K | DCG dùng gain `2^rel − 1`, discount `log2(rank + 1)`, chia ideal DCG; `rel=2`: hỗ trợ yêu cầu bắt buộc, `1`: bổ trợ hợp lệ, `0`: không liên quan/không hợp lệ; ideal DCG bằng 0 thì N/A |
| Evidence-set recall | Trung bình `Complete(C,q)`; metric chính cho multi-evidence retrieval |
| Minimal-evidence coverage | Trung bình `Coverage(C,q)`; chẩn đoán thiếu một phần chứng minh |

Relevance và equivalence mapping phải được pin; loại duplicate IDs trước khi chấm ranking. MRR/nDCG phù hợp cho ranked clauses/facts có qrels. Không áp máy móc lên danh sách nodes để kết luận path đúng. Q5 ưu tiên bridge/path coverage và complete evidence set; partial path không được tính như full path.

**Judgment coverage.** `unreviewed` hoặc chưa có qrel không mặc nhiên là relevance=0. Judgment gắn với query, canonical source/version/span và source/scope constraints. Với query yêu cầu đúng snapshot, passage từ snapshot khác không hoàn thành proof chỉ vì text giống; ghi lý do sai nguồn/phạm vi. Chỉ chấp nhận alternative support sau review và cập nhật equivalence mapping có version.

Khi qrels chưa đủ, Recall/Complete/Coverage phải ghi `support_basis=reviewed_gold` và giới hạn ở supports đã xác nhận; không diễn giải thành exhaustive recall trên corpus. Nếu có evidence chưa phân xử có thể hoàn thành một proof khác, ghi `evaluation_status=unjudged` cho kết luận sufficiency bị ảnh hưởng, không tự gán system failure. Precision@K chỉ báo khi các vị trí trả về trong top K đã được judged; vị trí thiếu vẫn theo định nghĩa ở bảng. MRR@K cần judgments đủ xác định relevant item đầu tiên hoặc xác nhận không có trong top K. nDCG@K chỉ báo trên qrels universe đã khai báo và pin, có gain/ideal DCG xác định; pooled qrels phải được gọi rõ là pooled-qrels evaluation, không là exhaustive corpus judgment. Mặc định metric không đủ judgments là `N/A (incomplete_judgments)`, kèm judged/unjudged counts và mẫu số. Không loại unjudged khỏi ranking rồi gọi điểm còn lại là metric chuẩn.

Có thể review hợp tuyển top results của BM25, dense, fusion và reranker; pin pool membership, depth, source spans, reviewer/rubric và qrels version trước paired comparison. Review xác định validity theo nguồn/contract, không sửa gold để ưu ái output hệ thống. DFG không đòi có pooled retrieval results; qrels mở rộng sau freeze phải là annotation version/extension mới.

### 8.3. L2 — Entity/Temporal Correctness

| Metric | Định nghĩa |
| --- | --- |
| Entity resolution accuracy | Query có resolved ID set đúng oracle / query có gold identity; cần clarification được chấm theo expected outcome |
| Temporal fact accuracy | Facts được đánh dấu applicable thỏa entity và valid/known constraints / facts applicable có gold temporal label |
| Stale-evidence rate | Facts được dùng như applicable nhưng đã hết hiệu lực tại query time / applicable facts có nhãn |
| Correct-version rate | Document units được dùng như applicable có version phù hợp / applicable document units có nhãn |
| Bridge/path coverage | Tỷ lệ bridge requirements được đáp ứng bởi cạnh/đường đúng type, direction, entity và temporal semantics |
| Bundle temporal consistency | Bundle có evidence cần kiểm tra và không vi phạm temporal relations / số bundle temporal không rỗng được đánh giá |

Historical/comparison evidence được gắn đúng role không bị coi là stale chỉ vì không còn hiện hành. Bundle rỗng không nhận điểm consistency hoàn hảo; lỗi thiếu bằng chứng được phản ánh ở coverage. Chấm cả candidate và selected stages khi phù hợp.

### 8.4. L3 — Context/Evidence Bundle

| Metric | Định nghĩa |
| --- | --- |
| Sufficiency@B | `Complete(E,q)` với evidence budget B; metric chính của selection |
| Selection loss | Tỷ lệ query `Complete(C,q)=1` nhưng `Complete(E,q)=0`, trên query có candidate set đủ |
| Required-role coverage | Số role bắt buộc được evidence hợp lệ đáp ứng / tổng required roles |
| Evidence precision | Units được oracle/rubric xác nhận hữu ích và hợp lệ / units được chọn; nhận cả alternative support hợp lệ |
| Redundancy | Tokens của bản lặp sau lần xuất hiện đầu / evidence tokens; duplicate groups được định nghĩa theo claim, source lineage và role |
| Provenance coverage | Selected units có source/version/locator kiểm tra được / selected units cần provenance |
| Budget compliance | Query có serialized evidence tokens ≤ B / tất cả query; log full prompt tokens riêng |

Không coi hai bằng chứng độc lập phục vụ conflict/corroboration là duplicate. Khi gold labels không đủ cho precision, ghi unjudged và audit mẫu thay vì tự gán irrelevant.

### 8.5. L4 — Agent/Downstream Task

Chấm correctness bằng oracle, EM/F1 nơi thích hợp hoặc rubric đã đóng băng. Groundedness là tỷ lệ factual claims được evidence hỗ trợ. Citation precision đo claim–citation links đúng; citation coverage đo claims cần dẫn chứng đã có citation hợp lệ.

Đo abstention precision/recall trên query không đủ dữ liệu hoặc unresolved conflict, cùng false-abstention rate trên query answerable. Task success yêu cầu đúng kết quả và trạng thái/hành động trong simulator. Timeout và output không hợp lệ phải được tính vào task failures.

Để kiểm tra retrieval có giúp reasoning, chạy cùng agent với retrieved context và gold context hợp lệ dưới cùng budget. Báo riêng trường hợp oracle context không vừa budget. So sánh gold KG với extracted KG để tách construction errors; kiểm tra answer correctness có điều kiện trên bundle đủ. Không dùng correlation giữa recall và accuracy làm bằng chứng duy nhất.

## 9. Scalability Evaluation

Đo **đường cong quality–latency–cost**, không chỉ một lần chạy kích thước lớn nhất. Chốt ít nhất ba mức khả thi sau pilot; các mức tải gợi ý trong research report chưa phải mục tiêu production được xác nhận. Index tăng theo dữ liệu không tự là failure; phải đối chiếu budget, mức suy giảm chất lượng và khả năng hoàn tất workload đã đăng ký.

| Trục tăng độc lập | Cần giữ/ghi nhận | Measurements |
| --- | --- | --- |
| Document chunks | Query/gold cố định; thêm distractors có kiểm soát | L1/L3/L4, index bytes, build time, latency |
| Entities | Identity ambiguity, tenant/scope distribution | Resolution, RAM/storage, retrieval latency |
| Graph edges | Relation types, degree distribution, node count | Visited/returned edges, fan-out, graph bytes |
| Events/entity | History length, skew, hot entities | Temporal quality, traversal cost, profile freshness |
| Update volume | Inserts/corrections/retractions, burst size | Records/s, backlog, time-to-searchable, write amplification |
| Concurrent queries | Arrival pattern, offered load, query mix | Achieved throughput, p50/p95/p99, timeouts/errors, resource utilization |

Bắt đầu bằng tăng từng trục, sau đó một mixed workload. Giữ snapshot/gold cố định trong distractor-growth test; update test có gold riêng từng snapshot. Tách một graph lớn và nhiều namespace nhỏ; không đồng nhất logical partition với physical sharding.

Latency MUST tách resolution/routing, document search, graph search/traversal, rerank, selection, generation và wall-clock toàn tuyến. Không cộng thời gian nhánh song song thành end-to-end latency. Ghi warm/cold cache, warm-up, số request, thời gian chạy, repeats và phần cứng; p99 thiếu mẫu ghi chưa đủ tin cậy.

Throughput là số request hoàn tất mỗi giây đo được, không suy từ nghịch đảo p95. Báo successful throughput và failure rate. Tách extraction LLM, embedding, structured ingestion và serving; cost ghi calls/tokens, tài nguyên, đơn giá/ngày giá nếu có. Không loại timeout khỏi báo cáo để làm đẹp latency.

## 10. Temporal Semantics

| Khái niệm | Nghĩa trong contract |
| --- | --- |
| Event time | Thời điểm sự kiện xảy ra |
| Valid time | Khoảng fact đúng trong nghiệp vụ |
| Transaction/known time | Khoảng hệ thống lưu/biết một phiên bản fact |
| Ingestion time | Thời điểm pipeline nhận bản ghi; khác thời điểm searchable |

Dùng khoảng nửa mở `[from,to)`. Query point tại `t`, known-as-of tại `a` yêu cầu `valid_from ≤ t < valid_to` và, khi áp dụng, `known_from ≤ a < known_to`. Unknown boundary khác open-ended boundary; adapter MUST giữ phân biệt này.

Ví dụ tổng hợp: sự kiện hiệu lực ngày 1 nhưng được nhận ngày 3; bản sửa nhận ngày 5 đổi hiệu lực thành ngày 2. Trạng thái thực tế ngày 1 theo dữ liệu mới khác trạng thái hệ thống đã biết ngày 3. Một timestamp không biểu diễn đủ cả hai câu hỏi.

Fact dùng cho kết luận đồng thời phải tương thích tại query time. Query chuỗi sự kiện dùng ràng buộc thứ tự/window riêng, không bắt mọi event giao nhau. Chính sách timezone, source priority và mapping timestamp Graphiti là **PENDING schema**; không giả định Graphiti tự giải quyết mọi trường hợp.

Synthetic tests MUST gồm future-effective, late arrival, historical correction, policy version change, overlapping intervals, retraction, conflicting sources, timezone/date boundaries và known-as-of trước/sau correction. Kiểm tra cache/summary sau cập nhật. Time-to-searchable đo từ lúc nhận update tới khi query quan sát đúng phiên bản; ghi polling resolution.

## 11. Synthetic Evaluation Data

Oracle là structured ledger cộng policy rules xác định. Từ ledger sinh documents, events và KG inputs; query có thể được diễn đạt bằng LLM, nhưng gold answer/evidence MUST được tính độc lập từ ledger/quy tắc và kiểm tra sự nhất quán của text đã sinh.

Mỗi scenario giữ gold entities, temporal states, policy versions, alternative minimal evidence sets, expected status và source locators. Gold không được truyền cho retriever, router hoặc agent. Với insufficient cases, oracle biết phần dữ liệu bị thiếu nhưng không đưa phần bị che vào corpus.

Sinh hard negatives sai người/ngày/version/điều kiện, conflict chưa có precedence, no-answer và counterfactual pairs. Kiểm tra đổi fact quyết định làm đáp án đổi; đổi distractor không liên quan không được làm đáp án đổi.

Split theo scenario, driver, policy family và thời gian; tránh cùng template chỉ đổi tên xuất hiện ở dev/test. Đóng băng generator, seeds, corpus, queries và labels trước final evaluation. Dùng human review cho logic và mẫu judge bất đồng.

Benchmark công khai bổ trợ: chọn một multi-hop subset, LongMemEval và temporal-update subset theo research report mục 11; ma trận P04/P06/P11/P23. BRIGHT/CRAG là diagnostic tùy ngân sách, không bắt buộc tái lập đầy đủ. Ghi subset IDs/protocol và không gọi subset score là official benchmark score.

Synthetic data không chứng minh phân bố, độ nhiễu hay ngôn ngữ production GSM. Kết luận phải giới hạn theo workload đã thử; mức tăng điểm trong paper không trở thành kỳ vọng đảm bảo.

## 12. Baseline v0

Baseline v0 là cấu hình tham chiếu đầy đủ trước mọi kỹ thuật nâng cao. C0 ở mục 14 chỉ là gate tích hợp tuần đầu; không đồng nghĩa v0 đã hoàn thiện.

| Lớp | Thành phần tối thiểu |
| --- | --- |
| Document | Metadata-aware chunking; source/version/applicability; BM25 + multilingual dense + RRF + bounded reranking |
| KG | Graphiti; stable entity IDs; typed relations; temporal filtering; provenance/source-event access; bounded 1–2 hop traversal |
| Hybrid | Rule/metadata routing; join theo điều kiện áp dụng; giữ required evidence roles; deduplicate và chọn context trong budget |
| Agent | Một model/prompt/tool contract cố định; answer có citations và trạng thái thiếu/mâu thuẫn |

Route ban đầu: policy → document; entity/state → KG; policy áp dụng cho driver → cả hai; aggregate → structured computation và tài liệu định nghĩa. Không tính aggregate trên top-k events như thể đó là toàn bộ population.

RRF hợp nhất rankings cùng loại đối tượng; không cộng trực tiếp điểm edge với chunk để chúng thay thế nhau. Join dùng ID/điều kiện có nguồn, không mặc định policy chứa tên tài xế. Cắt context phải giữ bridge và exceptions cần thiết.

Chưa đóng băng model cụ thể, top-k, chunk size hoặc rerank cap trong tài liệu này; chọn trên dev và pin trước so sánh. BGE-M3 là ứng viên từ nghiên cứu, chưa là lựa chọn cuối. Giới hạn 1–2 hop là cấu hình baseline, không phải giới hạn ngữ nghĩa của mọi query.

### 12.1. Corpus profiles cho release GSM

Theo release spec 05 v0.2.0, `retrieval_full` gồm 224 bài thật và là corpus mặc định cho baseline document/hybrid sau khi pipeline hoạt động; `debug_core` gồm sáu snapshot đã audit để conformance/debug. Primary gold chỉ lấy reviewed TEXT spans của P154/P151/P05/P23; P172/P26 đã audit nhưng hiện là distractors. Hai profiles dùng chung ba synthetic version documents, 12 definitions và operational facts; source visibility luôn theo scope/known cutoff. Không index file tổng hợp, không formalize 218 bài bổ sung thành executable rules.

T01–T07 cấp sẵn edition/snapshot. Lọc bằng reference công khai là hợp lệ; log số policy documents và chunks trước/sau edition filtering để biết tập ứng viên thực tế. Một policy document sau lọc vẫn có nhiều clauses/chunks, definitions và KG evidence. Đây chưa là document-discovery benchmark; subset discovery phải có query/gold/answerability review riêng sau pilot, không tự suy current-policy truth. Giữ graph construction/sources cố định trong phép so sánh chỉ đổi corpus document; tăng 224 bài không tự kiểm KG scalability.

Mọi comparison pin `corpus_profile_id`, `corpus_profile_version`, `corpus_manifest_sha256`, snapshot, chunker, qrels, reader và budgets. Runtime không đọc private corpus roles/task bindings, không dùng danh sách gold sources làm filter. Corpus/index identity và packaging chính xác theo 05; 42 queries vẫn là dev fixtures, không trở thành independent test samples khi chạy qua hai profiles.

## 13. Baseline Comparison / Ablation

| Track | So sánh tối thiểu | Điều kiện kiểm soát |
| --- | --- | --- |
| Document | BM25; dense; fusion; fusion + reranker | Cùng corpus/chunking, qrels, context budget; log candidate counts |
| KG | Fact retrieval tham chiếu; + explicit temporal eligibility; + bounded expansion | Cùng Graphiti snapshot, entity resolution và sources |
| Hybrid | Document-only; KG-only; hybrid trên Q4 subset | Cùng query/agent/budget; một nguồn riêng có thể cố ý thiếu required role |
| Selection | Candidate set cố định, chọn context đơn giản so với thay đổi cần thử | Đo selection loss và L4, không tăng budget ngầm |
| Oracle | Gold context vs retrieved context; gold KG vs extracted KG | Giữ reader và nhiệm vụ cố định |

Không tạo tích Descartes của mọi track. Nếu Graphiti tham chiếu đã có temporal filtering, ghi rõ cấu hình; không gọi chức năng có sẵn là cải tiến mới. Ablation bỏ guard chỉ chạy offline để chẩn đoán.

Chỉ thử kỹ thuật mới sau khi v0 chạy được, lỗi mục tiêu đã có bằng chứng và hypothesis/metric/budget được ghi trước. So sánh một thay đổi chính mỗi lần; báo effect size và uncertainty.

Một cải tiến chỉ được chấp nhận khi tăng metric evidence mục tiêu và cho thấy lợi ích downstream, không vi phạm integrity constraints hoặc budget đã chốt. Minimum meaningful gains, regression tolerances và latency/cost/freshness ceilings là **PENDING mentor** trước final test. Khi chưa có các ngưỡng này, chỉ báo kết quả quan sát, không kết luận đạt production. Vi phạm scope, mất provenance bắt buộc hoặc vượt context budget là contract failure, không được bù bằng accuracy trung bình.

## 14. C0 — Week-1 Acceptance Gate

| Điều kiện bắt buộc | Bằng chứng hoàn thành |
| --- | --- |
| Ít nhất một path query → retrieval → evidence → agent → answer | Chạy thật trên fixture, có gold và citations; không dùng gold làm runtime output |
| Graphiti và document adapter khả dụng | Nạp/đọc được fixture qua interface dự kiến; không chỉ mock |
| Positive và insufficient/conflict fixtures | Có expected result, observed result và scorer; answerable fixture thành công, negative fixture không suy diễn thành kết luận chắc chắn |
| Semantics | Ghi entity ID, time, document version và adapter mapping; synthetic assumptions tách khỏi GSM pending |
| Reproducibility | Pin code/packages/models/prompts; ghi hardware và lệnh chạy |
| Instrumentation | Đủ trace dưới đây; có latency/cost measurement pilot |

Trace tối thiểu: `query_id`, `query_family`, gold evidence/answer/status, candidates và scores từng stage, selected evidence, context nguyên văn, latency breakdown, final answer, correctness và citation/grounding result. Gold fields chỉ tồn tại ở evaluation side.

C0 PASS khi mọi điều kiện kỹ thuật được kiểm tra; đây không phải quality/SLA gate production. Thiếu schema thật có thể PASS trên synthetic contract nếu ghi pending mapping rõ ràng; thiếu adapter chạy thật hoặc logs thì FAIL. Nếu chưa lấy được baseline nội bộ, ghi “Graphiti reference tái dựng”, không tuyên bố đã tái lập cấu hình GSM.

## 15. Experiment Logging Contract

| Nhóm | Trường bắt buộc |
| --- | --- |
| Identity | `experiment_id`, `run_id`, contract version, hypothesis, changed component, git commit, dirty diff/hash, timestamp |
| Data | Dataset/generator/schema versions, seeds, split/subset IDs, query-family labels, gold/rubric/qrels versions, judgment coverage, corpus_profile_id/version/manifest hash, corpus/index/graph snapshots |
| Configuration | Retriever/filter/router config; chunking; embedding/tokenizer; reranker; Graphiti package/commit/backend/config; agent/LLM; prompts; decoding settings |
| Budgets | Per-stage top-k/candidate caps; hop/fan-out limits; context budget; deadline; retry/tool-call limits |
| Query trace | Resolved entity/time/access scope; candidates/scores; selected/rejected evidence; joins; conflicts; truncation; serialized context; answer/tool outputs |
| Performance | Hardware/OS, concurrency/load pattern, cache state, warm-up/repeats, stage timings, wall-clock, timeouts/errors, visited nodes/edges |
| Resources | Storage/index/graph size, peak RAM/GPU, ingestion throughput, freshness, rewritten records, LLM/API calls/tokens, cost basis/date |
| Evaluation | L1–L4 metrics và denominators; expected/observed status; error tags; paired deltas/CIs; judge model/prompt; audit notes |

Lưu raw per-query results và aggregate cùng nhau. Không ghi đè run cũ khi đổi config. Contract/schema/gold thay đổi phải tăng version; không gộp kết quả khác protocol thành cùng comparison. Judge hỗ trợ kiểm tra, không là nguồn chân lý duy nhất; mẫu bất đồng cần audit.

## 16. Confirmed Assumptions and Open Questions

**Đã xác nhận:** dự án khoảng sáu tuần; xây agent tích hợp memory bằng công nghệ có sẵn; ưu tiên retrieval và evidence; Graphiti là tham chiếu ban đầu; cần document, temporal KG và hybrid evaluation; scale là tiêu chí cốt lõi; chưa có dữ liệu production, chủ yếu dựa schema và synthetic/public data.

**Chờ mentor/schema xác nhận:**

| Đầu vào | Quyết định phụ thuộc |
| --- | --- |
| Schema và stable driver/entity IDs | Resolution, relations và adapter mappings |
| Event/relation types, source-of-truth, precedence | Gold facts, corrections, conflicts và profile derivations |
| Policy version/applicability representation | Clause lineage và document–driver joins |
| Timezone, interval semantics, known-as-of requirement | Temporal fixtures và timestamp mapping |
| Representative tasks/query distribution | Gold taxonomy weights và task-success rubric |
| Actual Graphiti/backend/model configuration | Baseline nội bộ hay reference tái dựng |
| Chunks/entities/edges/events, skew và update rates | Scale grid và stress workloads |
| QPS/concurrency, latency, freshness, cost targets | Acceptance ceilings và operating envelope |
| Hardware/API budget và access boundaries | Run feasibility, scope filters và measurement setup |
| Minimum gains, regression tolerances, review owner | Final comparison gate trước khi mở test results |

Mỗi pending item phải có owner và thời điểm cần chốt trong project tracking. Giá trị chưa được cung cấp không được thay bằng giả định production ngầm.
