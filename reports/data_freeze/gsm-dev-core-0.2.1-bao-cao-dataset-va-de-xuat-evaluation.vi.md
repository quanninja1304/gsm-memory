# Báo cáo dataset `gsm-dev-core-0.2.1` và đề xuất sử dụng cho evaluation

## 1. Tóm tắt dataset

`gsm-dev-core-0.2.1` là dataset pilot đã đóng băng cho bài toán **Scalable
Retrieval for Memory-Augmented AI Agents**. Dataset được thiết kế để kiểm tra
khả năng truy xuất và xây dựng bằng chứng từ ba nhóm thông tin:

1. tài liệu/chính sách dạng văn bản;
2. dữ liệu vận hành có entity, valid time và known time;
3. bằng chứng lai cần kết hợp document với operational facts hoặc temporal KG.

Đây không phải dataset huấn luyện mô hình và cũng chưa phải blind test set.
Vai trò chính của release là:

- kiểm tra conformance của loader, index và graph adapter;
- phát triển document, temporal-KG và hybrid retrieval;
- kiểm tra entity/time/source correctness;
- đo khả năng tập hợp một bộ bằng chứng đầy đủ;
- chẩn đoán lỗi ở retrieval, selection và downstream reasoning;
- làm development dataset trước khi tạo một test release độc lập.

Thông tin nhận diện:

| Thuộc tính | Giá trị |
| --- | --- |
| Dataset version | `gsm-dev-core-0.2.1` |
| Schema version | `1.1` |
| Release spec version | `0.2.0` |
| Root seed | `42` |
| Ngôn ngữ query | Tiếng Việt |
| Trạng thái | `FROZEN` |
| Dev queries | 42 |
| Test queries | 0 |

Release này thay thế `gsm-dev-core-0.2`. Bản 0.2 vẫn bất biến nhưng đã được
đánh dấu `DEPRECATED` do 17 RuntimeQuery chứa alias hoặc time-scope shorthand
nội bộ. Bản 0.2.1 có 0 finding cùng loại.

---

## 2. Dataset được tạo để đo điều gì?

Đối tượng nghiên cứu chính không phải là một memory framework tổng quát mà là
**retrieval và evidence construction**. Dataset cho phép trả lời các câu hỏi
sau:

- Hệ thống có tìm đúng source snapshot và đúng clause được yêu cầu không?
- Hệ thống có resolve đúng entity khi có tên trùng hoặc lịch sử alias không?
- Hệ thống có phân biệt valid time với known/transaction time không?
- Sau correction hoặc retraction, hệ thống có dùng đúng phiên bản observable ở
  từng cutoff không?
- Hệ thống có nhận biết thiếu bằng chứng thay vì đoán từ hidden world không?
- Khi hai nguồn ngang quyền mâu thuẫn, hệ thống có trả
  `unresolved_conflict` thay vì chọn bản ghi mới nhất không?
- Với câu hỏi multi-hop, hệ thống có lấy đủ bridge và mọi proof role bắt buộc
  hay chỉ lấy vài mảnh liên quan?
- Evidence selector có làm mất proof mặc dù candidate retrieval đã tìm thấy đủ
  bằng chứng không?
- Reader/agent có dùng đúng evidence, tính đúng giá trị và trích dẫn đúng
  provenance không?

Dataset được tổ chức để có thể tách các lỗi trên thành các tầng retrieval,
entity/time, context selection và downstream answer.

---

## 3. Tổng quan quy mô

| Thành phần | Số lượng |
| --- | ---: |
| World | 1 |
| Drivers | 8 |
| Distinct terminal trips | 80 |
| Canonical real articles | 224 |
| Audited real sources | 6 |
| Primary-gold real sources | 4 |
| Synthetic policy versions | 3 |
| Public definitions | 12 |
| Operational source types | 7 |
| Ledger timelines | 8 |
| Public snapshots | 12 |
| Scenario roots | 25 |
| Scenario variants | 32 |
| Semantic cases | 42 |
| Direct query renderings | 42 |
| Support atoms | 110 |
| Gold support links | 110 |
| Dev/Test queries | 42/0 |

Các số lượng trên có ý nghĩa khác nhau. Ví dụ, 42 queries là 42 fixtures dùng
chung world, histories và nhiều scenario roots; chúng không phải 42 quan sát
độc lập thống kê. Source copies, revisions và duplicate observations không
được tính thành terminal trips mới.

---

## 4. Nguồn tài liệu thật

### 4.1. Corpus 224 bài

Dataset pin 224 bài riêng lẻ từ GSM policy/news corpus. File tổng hợp chứa các
bài trùng lặp được loại khỏi tập document retrieval độc lập.

Source archive có SHA-256:

```text
cfe9e4555dbedf81396004c7a7d0ace52dcbb1deb758110c4aded3b6741ba9c9
```

Raw source được giữ nguyên. Normalization chỉ thực hiện:

- CRLF thành LF;
- UTF-8;
- offsets theo Unicode code points;
- span dạng `[start, end)`;
- line number bắt đầu từ 1.

Không deduplicate theo title, không crawl lại website, không dùng phiên bản mới
ở cùng URL để thay thế source đã pin và không tự sửa wording của nguồn.

### 4.2. Mức độ review

| Nhóm | Số bài | Vai trò |
| --- | ---: | --- |
| P154, P151, P05, P23 | 4 | Reviewed TEXT spans cung cấp primary gold |
| P172, P26 | 2 | Audited distractors |
| Các bài còn lại | 218 | Retrieval-only, chưa có exhaustive judgments |

Điểm quan trọng:

```text
unreviewed ≠ irrelevant
```

218 bài retrieval-only không được tự động gán relevance bằng 0. Một passage có
nội dung gần giống cũng không tự động thay thế proof yêu cầu đúng source hoặc
đúng edition.

### 4.3. Ba synthetic policy versions

Ngoài 224 tài liệu thật, release có ba document versions thuộc các synthetic
controls:

- `S_BRIDGE:v1`;
- `S_VERSION:v1`;
- `S_VERSION:v2`.

Các tài liệu này chỉ dùng để kiểm tra bridge, policy publication và version
semantics mà corpus thật không cung cấp đủ lịch sử quan sát. Chúng được đánh
dấu rõ là synthetic, không được diễn giải như chính sách GSM thật.

---

## 5. Hai corpus profiles

### 5.1. `debug_core@1`

Profile này chứa sáu audited real snapshots:

```text
P154, P151, P05, P23, P172, P26
```

Ngoài ra profile dùng chung ba synthetic versions và 12 public definitions.

Mục đích phù hợp:

- smoke test loader;
- kiểm tra chunk/source locators;
- phát triển adapter;
- kiểm tra public/private isolation;
- chạy vòng lặp debug nhanh;
- xác minh Mode A/B và ProjectionLink trong BRG.

Không nên dùng `debug_core@1` làm kết quả retrieval chính vì corpus đã thu hẹp
về sáu nguồn audited và chưa phản ánh nhiễu của full corpus.

### 5.2. `retrieval_full@1`

Profile này chứa đủ 224 canonical real articles, đồng thời dùng chung ba
synthetic versions và 12 definitions.

Đây là profile mặc định được đề xuất cho:

- sparse retrieval;
- dense retrieval;
- document reranking;
- document + KG hybrid retrieval;
- evidence selection;
- end-to-end agent evaluation trên dev fixtures.

Do relevance judgments chưa đầy đủ, kết quả phải báo judgment coverage. Recall
trên confirmed supports, complete-proof rate và proof coverage là các metric
an toàn hơn precision/nDCG khi top-K còn nhiều tài liệu unjudged.

### 5.3. Cách hiểu đúng về hai profiles

Hai profiles chỉ thay đổi tập candidate documents thật. Chúng không tạo thêm:

- world;
- semantic case;
- query độc lập;
- operational fact;
- ledger branch;
- gold answer.

Không được chạy qua hai profiles rồi gọi đó là 84 samples.

---

## 6. Synthetic operational world

Dataset có một world `W0`, được xây dựng deterministic từ seed 42. World chứa:

- 8 drivers;
- 4 fleets/depots phục vụ các bridge và membership cases;
- các region và service entities cần thiết;
- incident entity cho trạng thái open/resolved/reopened;
- 80 terminal trip events;
- reported measures;
- source registry và publication records;
- correction, replacement, retraction và conflict controls.

World riêng tư dùng để sinh dữ liệu nhất quán. Gold công khai không được suy
trực tiếp từ private world. Nếu evidence observable thiếu, đáp án đúng có thể là
`insufficient_evidence` dù generator biết private truth.

### 6.1. Reported measures

Dataset phân biệt giá trị được nguồn báo cáo với metric do benchmark tự tính.

Reported measures gồm:

- `RM_REVENUE`;
- `RM_OPDAY`;
- `RM_ACCEPTANCE`;
- `RM_RATING`.

Một reported measure chỉ nói rằng nguồn đã báo một giá trị. Nó không chứng minh
dataset có raw-event lineage mà GSM đã dùng để tính giá trị đó.

### 6.2. Derived metric

Metric derived bắt buộc là:

```text
cancel_rate_30d = cancelled / (cancelled + completed)
```

Metric dùng exact rational arithmetic và cần evidence về complete coverage.
Denominator bằng 0 tạo `undefined`, không tự chuyển thành 0.

---

## 7. Operational sources

Public source registry có bảy nguồn logic:

| Alias | Source kind | Vai trò |
| --- | --- | --- |
| `registry` | `registry` | Membership, region, status, program và names |
| `event` | `event_log` | Terminal trip outcomes |
| `incident` | `incident_log` | Incident state/history |
| `feed_a` | `metric_feed` | Reported measures |
| `feed_b` | `metric_feed` | Equal-rank conflict controls |
| `policy` | `policy_publisher` | Policy/artifact publication |
| `derived` | `derived` | Derived artifacts và coverage-related evidence |

Các nguồn có predicate permissions và correction permissions rõ ràng. Generic
rule “timestamp mới nhất luôn thắng” không được sử dụng.

---

## 8. Ledger và temporal design

### 8.1. Bốn loại thời gian

Dataset giữ riêng:

- event time;
- valid time;
- known/transaction time;
- ingestion time của system run sau này.

Canonical storage dùng UTC. Business calendar dùng
`Asia/Ho_Chi_Minh` khi BC01 yêu cầu. Interval có semantics `[from, to)`.

Một fact có thể future-effective nhưng đã được biết, hoặc đã xảy ra nhưng chỉ
được biết muộn. Snapshot lịch sử không được nhìn thấy records có known time ở
tương lai.

### 8.2. Tám ledger timelines

| Ledger | Records | Ý nghĩa diagnostic |
| --- | ---: | --- |
| `L0` | 359 | Timeline chuẩn |
| `L_NO_OPDAY` | 358 | Thiếu operating-day evidence |
| `L_WRONG_DRIVER` | 358 | Evidence thuộc sai driver |
| `L_CONFLICT` | 359 | Hai claim ngang quyền mâu thuẫn |
| `L_RETRACT` | 359 | Assertion/replacement bị retract |
| `L_WRONG_WINDOW` | 358 | Measure thuộc sai measurement window |
| `L_NO_BRIDGE` | 358 | Thiếu relation/fact trung gian |
| `L_NO_COVERAGE` | 358 | Thiếu coverage evidence cho aggregate |

Các ledgers là alternate branches độc lập. Runtime của một query chỉ được nạp
branch tương ứng. Concatenate tám ledgers thành một timeline sẽ tạo evidence
leakage và làm sai gold.

### 8.3. Mười hai public snapshots

Release materialize 12 allowlisted snapshot packages:

- 5 cutoff packages từ `L0`;
- 7 packages ở final cutoff cho bảy alternate branches.

Phân bố known cutoff:

| `known_as_of` | Số snapshot |
| --- | ---: |
| `2026-08-04T00:00:00Z` | 1 |
| `2026-08-06T00:00:00Z` | 1 |
| `2026-09-16T12:00:00Z` | 1 |
| `2026-09-17T01:00:00Z` | 1 |
| `2026-09-17T12:00:00Z` | 8 |

Hai snapshot sớm chứa lần lượt 29 và 30 operational records, chưa thấy 224 real
documents vì publication availability chưa tới. Các snapshot sau chứa 224
document references và prefix ledger đúng cutoff.

Snapshot package là allowlist. Runtime không được bypass package bằng cách đọc
full operational archive hoặc future catalogs.

---

## 9. Policy tasks T01–T07

42 cases gồm 28 policy-task queries và 14 foundation controls.

| Task | Số case | Nội dung được hỏi | Giới hạn claim |
| --- | ---: | --- | --- |
| T01 | 2 | P154 nói gì về scope, ngày vận doanh và công thức truy thu | Không kết luận policy hiện hành trong production |
| T02 | 11 | Áp dụng công thức của edition P154 lên reported measures trong scenario | Không xác minh wallet deduction hoặc raw revenue accounting |
| T03 | 3 | Reported acceptance có thỏa riêng rule auto-accept của P151 không | Không kết luận penalty hoặc feature thật đã bật |
| T04 | 3 | P05 định nghĩa clock, multi-point unit và rating/week thế nào | Không tự dựng raw rating events |
| T05 | 3 | Reported weekly rating có đạt riêng điều kiện `> 4,85` không | Không kết luận full bonus eligibility |
| T06 | 2 | P23 nêu nhóm Depot và kỳ áp dụng nào | Không đổi literal payroll period thành UTC range |
| T07 | 4 | Driver có thuộc nhóm đối tượng P23 nêu theo registry/state được cấp không | Không tuyên bố notice effective hoặc full eligibility |

T01–T07 luôn pin source snapshot/edition được hỏi. Dataset hiện tại kiểm tra
source-bound retrieval và evidence reasoning, không phải open-ended discovery
của “chính sách hiện hành”.

---

## 10. Foundation controls

14 foundation cases kiểm tra các semantics không nên gắn vào policy thật khi
source evidence không đủ:

| Foundation family | Số case | Mục tiêu |
| --- | ---: | --- |
| Aggregate | 3 | Exact derived metric, zero denominator, coverage |
| Bridge | 3 | Membership, fleet region, incident exception |
| Entity resolution | 1 | Same-name ambiguity |
| State | 4 | Historical state, correction và boundaries |
| Event | 2 | Event visibility và missing terminal event |
| Policy version | 1 | Synthetic publication/version selection |

Các controls này cho phép kiểm tra temporal KG và hybrid logic mà không bịa
normative history cho real GSM policies.

---

## 11. Phân bố query families Q1–Q7

| Query family | Số case | Năng lực chính |
| --- | ---: | --- |
| Q1 | 7 | Document/definition lookup |
| Q2 | 2 | Entity resolution |
| Q3 | 2 | Temporal state/event lookup |
| Q4 | 12 | Rule application và evidence-conditioned answer |
| Q5 | 1 | Multi-hop bridge |
| Q6 | 8 | Update/correction/version replay |
| Q7 | 10 | Missing, conflict, ambiguity và abstention |
| **Tổng** | **42** |  |

Một task có thể xuất hiện ở nhiều query families. Ví dụ T02 có direct numeric
cases, correction variants và missing/conflict variants. Task ID và query
family là private evaluation metadata, không xuất hiện trong RuntimeQuery.

---

## 12. Query và answer composition

### 12.1. Query renderings

Release có đúng 42 direct Vietnamese renderings:

- 42 trong `dev.jsonl`;
- 0 trong `test.jsonl`;
- không có canonical paraphrases;
- không có dialog/implicit/composed variants;
- query policy thật pin intended edition/snapshot;
- public request có entity refs, time scope, known cutoff, access scope và
  public application context phù hợp.

Ví dụ dạng câu hỏi:

> Theo snapshot được chỉ định, quy định doanh số tối thiểu dành cho nhóm tài xế
> nào, tại khu vực nào?

> Theo edition và conventions được cấp, khoản truy thu theo rule cho tài xế
> trong khoảng thời gian được chỉ định là bao nhiêu?

Public query không chứa aliases `Cxxx`, `D_A`–`D_H`, window shorthand, expected
status hoặc proof hints.

### 12.2. Gold statuses

| Expected status | Số case | Ý nghĩa |
| --- | ---: | --- |
| `answerable` | 32 | Observable evidence đủ cho answer/proof |
| `insufficient_evidence` | 8 | Thiếu ít nhất một required proof role |
| `unresolved_conflict` | 1 | Active equal-rank sources mâu thuẫn |
| `ambiguous_request` | 1 | Không resolve duy nhất được entity được hỏi |

Negative cases không nhận `Complete=1` từ empty proof. Chúng lưu missing roles,
conflict groups hoặc candidate identities để chẩn đoán.

---

## 13. Evidence gold

Gold được biểu diễn bằng ba lớp semantic:

- `SupportAtom` — đơn vị bằng chứng theo vai trò;
- `EvidenceProof` — tập atom tối thiểu đủ để trả lời;
- `GoldSupportLink` — mapping atom về canonical source và locator.

Release có:

```text
110 support atoms
110 gold support links
32 sufficient proofs
10 diagnostic proofs
```

Các support roles chính gồm:

| Role | Số atom |
| --- | ---: |
| Document rules | 17 |
| Driver programs | 17 |
| Document clauses | 11 |
| Operating regions | 10 |
| Operating days | 10 |
| Reported revenue | 8 |
| Membership | 6 |
| Reported rating | 3 |
| Metric definition | 3 |
| Terminal population | 3 |
| Synthetic rule | 3 |
| Incident evidence | 3 |
| Fleet registry | 3 |
| Reported acceptance | 2 |
| Complete coverage | 2 |
| Fleet region | 2 |
| Candidate identity | 1 |
| Terminal event | 1 |
| Policy publication | 1 |

Semantic atom identity độc lập với chunk ID, Graphiti UUID hoặc vector-store ID.
Mỗi system cần tạo ProjectionLink từ physical retrieval units của mình về các
canonical sources/atoms để evaluator chấm nhất quán.

---

## 14. Public và private package

### 14.1. Public runtime data

Public package gồm:

- document raw và normalized representations;
- document catalog và corpus-profile manifests;
- public definitions;
- entity catalog và source registry;
- immutable operational ledgers;
- deterministic text observations;
- 12 snapshot packages;
- Mode A và Mode B source manifests;
- 42 RuntimeQuery dev fixtures.

### 14.2. Private evaluator data

Private package gồm:

- world oracle;
- observation plan;
- policy rules và task bindings;
- scenario manifests và mutation metadata;
- semantic cases;
- gold answers;
- support atoms, proofs và support links;
- corpus roles và relevance protocol;
- validation evidence.

Runtime retriever, KG và reader không được mount hoặc đọc private directories.
Evaluator offline là thành phần duy nhất được đọc gold/private sidecars.

---

## 15. Mode A và Mode B

Dataset cung cấp source-level inputs cho hai construction modes:

### Mode A — structured

Trỏ tới deterministic structured public records. Phù hợp để:

- kiểm tra upper bound khi không có extraction loss;
- xây temporal KG từ canonical assertions;
- tách lỗi retrieval khỏi lỗi information extraction.

### Mode B — textual observations

Trỏ tới deterministic narratives biểu diễn cùng public information. Phù hợp để:

- kiểm tra extraction/construction pipeline;
- so sánh structured ingestion với text ingestion;
- đánh giá liệu KG construction có bỏ mất entity, time, provenance hoặc
  revision links hay không.

Mode A và Mode B giữ parity về source identity, facts, valid time, known time,
revision targets và provenance. Actual graph nodes, edges, embeddings và
Graphiti UUIDs không thuộc frozen dataset; chúng là BRG/run artifacts.

---

## 16. Chất lượng và reproducibility

Dataset đã qua hai clean builds độc lập. Logical comparison kiểm tra 635
semantic files và không phát hiện mismatch.

| Validation group | PASS | FAIL | NOT_RUN |
| --- | ---: | ---: | ---: |
| V01–V10 | 10 | 0 | 0 |
| SM01–SM08 | 8 | 0 | 0 |
| EX01–EX25 | 25 | 0 | 0 |
| AUX | 9 | 0 | 0 |
| Counterfactual | 4 | 0 | 0 |

DFG01–DFG06 đều PASS.

Frozen identity:

```text
manifest SHA-256
61dddfd6c9f078b9b8c8288562c6196ae28a7ece390cd6d61d03041183b515b5

logical inventory digest
4ed08a35393912150ffb731946965c5adc827a403835d4c9a96e9c333df16d11
```

DFG chứng nhận dataset, proofs và package closure. DFG không chứng nhận quality
của Graphiti, retriever, embedding model hoặc agent.

---

# Phần II — Đề xuất sử dụng dataset cho proposed systems

## 17. Khuyến nghị chính

Các proposed systems sau này nên dùng cùng release 0.2.1 nhưng chọn profile và
slice theo mục tiêu:

| Mục tiêu | Dataset configuration nên dùng |
| --- | --- |
| Loader/adapter smoke test | `debug_core@1` + một Mode A snapshot |
| Text construction smoke test | `debug_core@1` + Mode B |
| Document retrieval chính | `retrieval_full@1` |
| Temporal KG retrieval | Mode A, đủ 12 snapshots |
| Text-to-KG evaluation | Mode B, paired với cùng Mode A snapshots |
| Hybrid retrieval | `retrieval_full@1` + operational snapshot cùng query |
| Evidence selection | Candidate pools + 110 support atoms/proofs |
| Agent reasoning | Selected context + 42 dev queries + private evaluator |
| Temporal robustness | `L0` snapshot pairs và bảy alternate branches |
| Final system comparison | Một future locked-test release, không phải 42 dev fixtures này |

`retrieval_full@1` nên là corpus mặc định cho mọi headline retrieval result trên
release hiện tại. `debug_core@1` chỉ dùng cho conformance/debug hoặc được báo rõ
là six-source diagnostic.

---

## 18. Đề xuất cho document retrieval systems

Áp dụng cho BM25, dense retrievers, late interaction, document rerankers và các
proposed document-memory methods.

Dataset:

```text
release: gsm-dev-core-0.2.1
profile: retrieval_full@1
queries: 42 dev RuntimeQueries
documents: visible documents trong snapshot được route cho từng query
```

Nên đo:

- confirmed-support Recall@K;
- minimal-proof Coverage@K;
- complete-proof retrieval rate;
- first confirmed-support rank khi judgments đủ;
- source/snapshot correctness;
- candidate count trước và sau edition filtering;
- latency và index size sau khi BRG hoàn tất.

Không nên:

- filter corpus bằng private primary-gold labels;
- gán 218 unreviewed articles là negative;
- gọi profile này là open document-discovery benchmark vì T01–T07 vẫn pin
  intended snapshot;
- dùng `debug_core@1` làm headline performance.

---

## 19. Đề xuất cho temporal KG systems

Áp dụng cho Graphiti reference, custom temporal KG, event-sourced graph hoặc
memory graph proposals.

Dataset chính:

- Mode A cho canonical structured construction;
- 12 snapshot packages;
- 8 ledgers;
- operational entity/source registry;
- foundation Q2/Q3/Q5/Q6/Q7 cases.

Nên đo:

- entity resolution accuracy;
- valid-time correctness;
- known-time leakage rate;
- stale evidence rate;
- correction and retraction adoption;
- equal-rank conflict handling;
- bridge/path coverage;
- provenance preservation;
- snapshot-isolation violations.

Graph construction phải tạo ProjectionLink về canonical sources. Graphiti UUID
hoặc internal edge IDs không được dùng làm gold semantic identity.

---

## 20. Đề xuất cho text-to-KG construction systems

Đây là paired Mode A/Mode B experiment.

Thiết kế:

1. ingest Mode A vào structured/temporal graph baseline;
2. ingest Mode B bằng proposed extraction/construction system;
3. dùng cùng snapshots, sources, queries và retrieval/reader budgets;
4. đo construction loss trước khi quy lỗi cho retrieval.

Nên so sánh:

- assertion/entity recall;
- valid/known time preservation;
- revision-target preservation;
- source/provenance coverage;
- missing or fabricated facts;
- downstream complete-proof delta giữa A và B.

Mode B narratives không phải natural uncontrolled corpus; chúng là deterministic
text observations đại diện cùng public information. Kết quả đo khả năng giữ
semantics trong text construction, không phải chất lượng extraction trên mọi
dạng tài liệu ngoài đời.

---

## 21. Đề xuất cho hybrid retrieval systems

Áp dụng cho document + KG fusion, KG-guided document retrieval, evidence graph,
KG²RAG-style hoặc các proposed hybrid methods.

Dataset configuration:

```text
documents: retrieval_full@1
operational data: snapshot được RuntimeQuery route tới
construction: pin Mode A hoặc Mode B
queries: 42 dev fixtures
gold: support atoms + minimal proofs
```

Các task phù hợp nhất:

- T02: document rule + program/region/day/revenue evidence;
- T03: document rule + program + reported acceptance;
- T05: document rule + reported rating;
- T07: document clause + membership + fleet registry;
- aggregate controls: definition + raw population + coverage;
- bridge controls: rule + membership + region + incident evidence.

Nên đo complete-proof rate thay vì chỉ đo có ít nhất một relevant unit. Một
hybrid system lấy được document clause nhưng thiếu operational operand vẫn chưa
có đủ evidence để trả lời.

---

## 22. Đề xuất cho evidence selectors và rerankers

Để tách retrieval loss khỏi selection loss, cần log hai bundle:

- candidate evidence trước selector;
- selected context thực tế gửi reader.

Nên đo ở cả hai tầng:

- complete-proof rate;
- required-role coverage;
- minimal-proof coverage;
- evidence redundancy;
- source/version correctness;
- selected context tokens/bytes;
- candidate-complete nhưng selected-incomplete rate.

Khi so sánh selectors, candidate pool phải cố định. Khi so sánh retrievers,
selector và context budget phải cố định hoặc được báo là một phần của full
system comparison.

---

## 23. Đề xuất cho agent/reader systems

Reader evaluation chỉ nên chạy sau khi evidence bundle được ghi lại. Nên có ba
conditions:

1. retrieved context;
2. selected context;
3. oracle context từ gold proof, chỉ evaluator được tạo.

Nên đo:

- expected-status accuracy;
- typed-value accuracy;
- exact arithmetic correctness;
- groundedness;
- citation precision và citation coverage;
- unsupported inference rate;
- abstention accuracy trên missing/conflict/ambiguous cases;
- gap giữa retrieved-context và oracle-context performance.

Giữ reader, prompt và context budget giống nhau khi so sánh retrieval systems.
Nếu reader thay đổi cùng retriever, phải báo đó là full-system comparison và có
ablation riêng.

---

## 24. Temporal và fault slices nên báo riêng

Ngoài aggregate score, mỗi proposed system nên báo các slices:

| Slice | Dataset source | Failure cần quan sát |
| --- | --- | --- |
| Historical prefix | Hai snapshot sớm của `L0` | Future-known leakage |
| Before/after correction | `L0` cutoff pairs | Stale value hoặc correction adoption |
| Missing operating day | `L_NO_OPDAY` | Đoán giá trị thay vì insufficient evidence |
| Wrong entity | `L_WRONG_DRIVER` | Entity contamination |
| Equal-rank conflict | `L_CONFLICT` | Latest-wins hoặc conflict suppression |
| Retraction | `L_RETRACT` | Dùng assertion đã bị retract |
| Wrong window | `L_WRONG_WINDOW` | Measurement-window contamination |
| Missing bridge | `L_NO_BRIDGE` | Partial path bị chấm như complete proof |
| Missing coverage | `L_NO_COVERAGE` | Exact aggregate khi population chưa complete |

Các slices này quan trọng hơn một accuracy trung bình duy nhất vì chúng chỉ ra
system sai ở temporal reducer, retrieval, entity resolution hay evidence
selection.

---

## 25. Evaluation metrics đề xuất

### 25.1. L1 — Retrieval

- confirmed-support Recall@K;
- complete-proof retrieval rate;
- minimal-evidence Coverage@K;
- bridge/path coverage;
- source/version correctness;
- judgment coverage;
- MRR/nDCG chỉ khi qrels đủ để xác định metric.

### 25.2. L2 — Entity và temporal correctness

- entity accuracy;
- wrong-entity rate;
- valid-time accuracy;
- known-time leakage rate;
- wrong-window rate;
- stale evidence rate;
- source-precedence correctness;
- retraction/conflict handling accuracy.

### 25.3. L3 — Evidence bundle

- selected complete-proof rate;
- required-role coverage;
- provenance coverage;
- evidence precision trên judged units;
- redundancy;
- context budget sử dụng.

### 25.4. L4 — Downstream answer

- expected-status accuracy;
- typed-value correctness;
- numeric exact match;
- groundedness;
- citation precision/coverage;
- unsupported claims;
- abstention precision/recall.

Mọi metric phải ghi denominator, số query thực chạy, blocked/error counts và
judgment convention.

---

## 26. Fair-comparison protocol

Mỗi run cần pin và lưu:

```text
dataset_version
corpus_profile_id + version + manifest hash
public_snapshot_id
scope_id
known_as_of
construction mode
chunker/projection version
retriever/reranker config
top-k
context budget
reader model/prompt/version
qrels/proof/equivalence version
judgment coverage
random seeds
toolchain and hardware
```

Nguyên tắc:

- mọi system dùng cùng public inputs;
- không system nào được đọc private gold ở runtime;
- không đọc full archive thay cho routed snapshot;
- không tăng tool/context budget ngầm cho proposed system;
- main retrieval comparison giữ construction mode cố định;
- Mode A/B comparison giữ retrieval và reader cố định;
- không sửa gold khi baseline hoặc proposed system thất bại;
- contract failure không được bù bằng average accuracy cao hơn.

---

## 27. Giới hạn khi dùng dataset hiện tại

`gsm-dev-core-0.2.1` có các giới hạn cần nêu rõ trong mọi báo cáo:

1. Chỉ có một world.
2. Chỉ có 8 drivers và 80 terminal trips.
3. 42 queries đều là dev/conformance fixtures.
4. `test.jsonl` rỗng có chủ đích.
5. Các queries dùng chung histories nên không IID.
6. Primary real-source gold chỉ đến từ bốn articles.
7. Relevance judgments cho full 224-article corpus chưa exhaustive.
8. Chỉ có direct Vietnamese renderings.
9. T01–T07 pin source edition, vì vậy chưa đo open document discovery.
10. Dataset không chứa actual graph, embeddings hoặc run traces.

Dataset phù hợp để báo:

- fixture-level accuracy;
- error breakdown;
- paired dev deltas;
- conformance;
- temporal/source/evidence diagnostics.

Dataset không đủ để báo:

- production accuracy;
- model superiority tổng quát;
- confidence intervals giả định 42 independent samples;
- unseen-policy generalization;
- final leaderboard result sau khi đã tuning trên cùng 42 queries.

---

## 28. Dataset cần bổ sung cho final evaluation

Để đánh giá proposed systems một cách thuyết phục, cần phát hành một dataset
version mới thay vì thêm test rows vào frozen release này.

Future evaluation dataset nên có:

- nhiều world và scenario groups độc lập;
- entities/drivers mới;
- scenario roots mới, không chỉ đổi tên hoặc paraphrase 42 cases;
- locked test queries với `test > 0`;
- split theo scenario, entity group, time và task/policy family;
- mọi mutation, before/after và wording siblings ở cùng split group;
- proof-first gold được review trước system runs;
- qrels pooling/review protocol có version;
- direct, dialog, implicit và false-premise slices được đếm riêng;
- document discovery subset riêng nếu bỏ pinned source reference;
- nhiều clean builds và DFG độc lập;
- test labels không được dùng để tuning prompt, router hoặc hyperparameters.

Không nên nhân 42 queries thành hàng trăm paraphrases rồi coi đó là hàng trăm
independent samples. Cần báo riêng:

- số world;
- số scenario roots độc lập;
- số semantic cases;
- số renderings;
- số held-out test groups.

---

## 29. Ma trận dataset/run đề xuất

| Run | Dataset/profile | Mode | Query set | Mục đích |
| --- | --- | --- | --- | --- |
| D0 | `debug_core@1` | Mode A | 42 dev | Structured loader smoke test |
| D1 | `debug_core@1` | Mode B | 42 dev | Text construction smoke test |
| D2 | `retrieval_full@1` | Document | 42 dev | Sparse/dense document baseline |
| D3 | Operational snapshots | Mode A | 42 dev | Temporal KG baseline |
| D4 | Operational snapshots | Mode B | 42 dev | Text-to-KG construction diagnostic |
| D5 | `retrieval_full@1` + snapshots | Fixed A hoặc B | 42 dev | Hybrid retrieval |
| D6 | Fixed candidate pools | N/A | 42 dev | Selector/reranker comparison |
| D7 | Retrieved vs oracle context | N/A | 42 dev | Reader và end-to-end gap |
| D8 | Ledger/snapshot fault slices | Fixed mode | Relevant cases | Temporal robustness |
| D9 | Future frozen release | Pinned | Locked test | Final blind comparison |

D0–D8 là development, conformance hoặc diagnostic runs. D9 mới nên được dùng
cho final claims sau khi configs, thresholds và budgets đã khóa.

---

## 30. Đề xuất cuối cùng

Bộ dataset nên dùng cho proposed systems trong giai đoạn kế tiếp là:

```text
Release chuẩn:
  gsm-dev-core-0.2.1

Debug/conformance corpus:
  debug_core@1

Main document/hybrid corpus:
  retrieval_full@1

Structured temporal-KG input:
  Mode A + 12 public snapshots

Text construction input:
  Mode B paired với cùng snapshots

Temporal robustness:
  L0 + 7 alternate ledger branches

Evidence evaluation:
  42 semantic cases + 110 support atoms/proofs

Final system evaluation:
  future independent frozen release có locked test
```

Trong release hiện tại, `retrieval_full@1` là lựa chọn đúng cho headline dev
results; `debug_core@1` chỉ nên dùng cho smoke/conformance. Kết quả tốt nhất nên
được báo theo L1–L4 và fault slices, không chỉ bằng một con số answer accuracy.

---

## 31. Artifact tham chiếu

- `data/gsm-dev-core-0.2.1/private/eval/manifest.json`
- `data/gsm-dev-core-0.2.1/public/runtime_manifest.json`
- `data/gsm-dev-core-0.2.1/public/corpus_profiles/debug_core/manifest.json`
- `data/gsm-dev-core-0.2.1/public/corpus_profiles/retrieval_full/manifest.json`
- `data/gsm-dev-core-0.2.1/public/runtime_queries/dev.jsonl`
- `reports/data_freeze/gsm-dev-core-0.2.1-freeze-certificate.json`
- `reports/data_freeze/gsm-dev-core-0.2.1-logical-comparison.json`
- `reports/data_freeze/gsm-dev-core-0.2-deprecation.json`

Nguồn contract:

- `docs/01_problem_and_evaluation.md`
- `docs/02_synthetic_schema_and_data_design.md`
- `docs/04_benchmark_to_dataset_mapping.md`
- `docs/05_dataset_release_spec.md`
