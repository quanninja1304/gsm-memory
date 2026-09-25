# Báo cáo chi tiết dataset `gsm-dev-core-0.2.2`

| Thuộc tính | Giá trị |
| --- | --- |
| Dự án | Scalable Retrieval for Memory-Augmented AI Agents |
| Ngày lập báo cáo | 2026-09-22 |
| Release hiện hành | `gsm-dev-core-0.2.2` |
| Trạng thái release | `FROZEN` |
| Schema version | `1.1` |
| Release spec version | `0.2.0` |
| Root seed | `42` |
| Commit freeze tham chiếu | `372e4d1ada9bb0f0c604106483fa6e5fdc86b337` |
| Checkpoint repository khi lập báo cáo | `30eead44a6306783ad09880fe45fec34ac9679ff` |

---

## 1. Kết luận điều hành

Dataset `gsm-dev-core-0.2.2` **đã sẵn sàng làm data foundation cho phát triển và đánh giá retrieval trên tập dev**. Kết luận này dựa trên các bằng chứng sau:

- release đã `FROZEN`, verifier read-only kiểm đủ `636/636` inventory entries;
- không có file thiếu, sai byte hash hoặc file material bất ngờ;
- `DFG01–DFG06` đều `PASS`;
- `A1_G1–A1_G6` đều `PASS`;
- hai clean candidate builds tương đương logic trên toàn bộ 636 inventory entries;
- 42/42 semantic cases được independent reconstruction;
- 110/110 support locators resolve được tới public evidence;
- 12/12 runtime snapshots và 8/8 ledger timelines đã được kiểm tra;
- offline data suite đã pass `39` tests mà không cần provider credentials.

Phạm vi của kết luận trên cần được hiểu chính xác: dataset đã sẵn sàng cho **nghiên cứu trên development/conformance catalogue**, nhưng chưa phải một held-out benchmark hoàn chỉnh. Release có 42 dev queries và 0 test queries. Nó không tự chứng minh retrieval success, Graphiti correctness, reader/agent accuracy, chi phí production hay model superiority.

Sau khi dataset đóng băng, Phase B.1 đã chạy offline retrieval baseline trên chính release này. Kết quả cho thấy data plumbing và temporal isolation hoạt động, nhưng proof-preserving selection hiện là bottleneck: candidate stage hoàn chỉnh proof cho `30/42`, selected context chỉ giữ được `15/42`. Đây là kết quả của baseline retrieval, không phải lỗi freeze hay lỗi gold của dataset.

---

## 2. Dataset này dùng để làm gì?

`gsm-dev-core-0.2.2` là một pilot dataset có kiểm soát nhằm nghiên cứu retrieval và evidence construction cho memory-augmented AI agents. Bài toán kết hợp ba loại bằng chứng:

1. **Tài liệu/chính sách thực:** các bài viết GSM đã pin theo archive và snapshot.
2. **Dữ liệu vận hành synthetic có thời gian:** entity, chuyến xe, reported measures, incident, source registry, correction/retraction và coverage.
3. **Bằng chứng tính toán:** các kết quả phải được dẫn xuất bằng số học chính xác từ một population được chứng minh là đủ coverage.

Năng lực mà dataset được thiết kế để kiểm tra gồm:

- document/policy retrieval với đúng source edition;
- temporal KG retrieval với valid time và known time tách biệt;
- entity resolution và scope correctness;
- source authority, correction, replacement và retraction;
- conflict và missing-evidence semantics;
- exact aggregate có coverage/source-set proof;
- hybrid evidence selection;
- proof completeness và failure attribution cho downstream reader/agent.

Dataset **không** phải generic memory framework, không phải production traffic sample, và không được thiết kế để ước lượng accuracy ngoài catalogue 42 cases hiện có.

---

## 3. Identity và bằng chứng freeze

### 3.1. Cryptographic identities

| Artifact | SHA-256 |
| --- | --- |
| Release manifest | `f2eb6919d9a30541e804af5f51dc27b005f8332e8109a8eb0ddeffdc2a8d2737` |
| Logical comparison report | `8438acb3f0e42a41b90f547003e4eea7d1abd79e78a0261bf94018444c11ddb7` |
| Logical inventory digest | `cf738397417b7644a51fd6ed11b17b2bc5cac64ea2c9402e75707aad6452aa49` |
| Candidate validation artifact | `ec3240cf4b7c5965069cbbec894ca9ba4c432666fc1194bd03d6cc0d772f513f` |
| Pinned source archive | `cfe9e4555dbedf81396004c7a7d0ace52dcbb1deb758110c4aded3b6741ba9c9` |
| Source catalog | `d6f273d35bb2d5314b7f2509960629faaac2a62323a97bac70880f68fef4c2d4` |

### 3.2. Read-only verification result

| Trường | Kết quả |
| --- | ---: |
| Declared inventory checked | 636 |
| Missing | 0 |
| Mismatched | 0 |
| Unexpected | 0 |
| Verifier result | `PASS` |
| Release state | `FROZEN` |

Trên filesystem, release có 637 files: 612 public và 25 private. Inventory khai báo 636 material artifacts; file manifest `private/eval/manifest.json` là root của contract và không tự liệt kê/tự hash chính nó. Vì vậy `636/636` là count đúng theo freeze contract, không phải bỏ sót một file.

Tổng footprint hiện tại xấp xỉ 13.84 MB theo byte thập phân:

- public: 612 files, 13,232,040 bytes;
- private: 25 files, 612,306 bytes.

### 3.3. Quan hệ với các release cũ

- `gsm-dev-core-0.2` vẫn immutable nhưng đã deprecated vì 17 public `RuntimeQuery` làm lộ private aliases hoặc time-scope metadata.
- `gsm-dev-core-0.2.1` vẫn `FROZEN` và không bị sửa, nhưng đã bị thay thế do provenance locators và task bindings chưa đủ cho independent semantic reconstruction.
- `gsm-dev-core-0.2.2` là corrective release hiện hành. Nó giữ nguyên schema `1.1`, release spec `0.2.0` và business semantics, đồng thời bổ sung provenance, coverage và independent assurance.

Không dùng `0.2` hoặc `0.2.1` cho experiment mới.

---

## 4. Thành phần tổng thể

| Hạng mục | Số lượng | Ghi chú |
| --- | ---: | --- |
| Private synthetic world | 1 | `W0` |
| Drivers | 8 | Entity identity deterministic |
| Distinct terminal trips | 80 | Không đếm source copies/revisions là trip mới |
| Scenario roots | 25 | Root business scenarios |
| Scenario variants | 32 | 25 base + 7 branch mutations |
| Ledger timelines | 8 | `L0` + 7 alternate branches |
| Semantic cases | 42 | Development/conformance catalogue |
| Direct Vietnamese queries | 42 | 42 dev, 0 test |
| Runtime snapshots | 12 | Public allowlist packages |
| Real canonical articles | 224 | Aggregate duplicate bị loại khỏi retrieval corpus |
| Synthetic policy versions | 3 | `S_BRIDGE:v1`, `S_VERSION:v1`, `S_VERSION:v2` |
| Public document revisions | 227 | 224 real + 3 synthetic |
| Public definitions | 12 | Versioned definition artifacts |
| Public entity catalog rows | 16 | Entity/name catalogue |
| Public source registry rows | 7 | Authority/correction scope |
| Public source sets | 2 | Exact membership sets |
| Base text observations | 359 | Mode B source-level observations |
| Support atoms | 110 | Semantic evidence units |
| Gold support links | 110 | Resolvable public provenance locators |
| Gold answers | 42 | Typed expected result/status |
| Proof records | 42 | 32 sufficient + 10 diagnostic |
| Relevance judgments | 0 | Ranking qrels chưa được xây dựng |

### 4.1. Gold status distribution

| Expected status | Số case | Ý nghĩa |
| --- | ---: | --- |
| `answerable` | 32 | Public evidence đủ để kết luận |
| `insufficient_evidence` | 8 | Thiếu premise/evidence cần thiết |
| `unresolved_conflict` | 1 | Nguồn cùng authority rank mâu thuẫn |
| `ambiguous_request` | 1 | Request chưa đủ rõ để bind duy nhất |
| **Tổng** | **42** | |

Không được quy ước `missing`, `undefined` hoặc `conflict` thành `false` hay `0`. Mười proof records mang trạng thái `diagnostic`, tương ứng với các case không có sufficient proof do missing/conflict/ambiguity; 32 records còn lại là `sufficient`.

### 4.2. Phân bổ theo foundation task

| Task | Cases |
| --- | ---: |
| T01 | 2 |
| T02 | 11 |
| T03 | 3 |
| T04 | 3 |
| T05 | 3 |
| T06 | 2 |
| T07 | 4 |
| Auxiliary/non-foundation cases | 14 |
| **Tổng** | **42** |

T01–T07 là các task được pin vào intended edition/snapshot. Mười bốn case không gán foundation task dùng để kiểm tra các semantics bổ trợ như entity, time, correction, conflict, missing bridge, coverage và context.

---

## 5. Corpus tài liệu thực

### 5.1. Nguồn pin và materialization

Nguồn gốc được pin tại:

```text
data/raw/archives/policy_green_sm_source.zip
```

Archive SHA-256:

```text
cfe9e4555dbedf81396004c7a7d0ace52dcbb1deb758110c4aded3b6741ba9c9
```

Workflow offline materialize đúng 225 Markdown members:

- 224 individual articles;
- 1 aggregate duplicate.

Aggregate duplicate được giữ để source-integrity/audit nhưng **không** được coi là retrieval document độc lập. Source materializer xác minh archive hash trước extraction, chống ZIP path traversal, giữ nguyên member bytes và không silently overwrite non-empty target.

Raw Markdown checkout bytes dùng CRLF vì byte hashes của pinned archive được tạo từ CRLF. Normalized document artifacts dùng LF theo `crlf-to-lf-v1`. `.gitattributes` khóa hai hành vi này độc lập với OS và `core.autocrlf`; ZIP/Parquet được xử lý như binary.

### 5.2. Corpus profiles

| Profile | Real articles | Synthetic versions | Definitions | Mục đích |
| --- | ---: | ---: | ---: | --- |
| `debug_core@1.0` | 6 | 3 | 12 | Fast debugging, conformance, loader development |
| `retrieval_full@1.0` | 224 | 3 | 12 | Default full retrieval baseline |

Sáu real snapshots trong `debug_core` là P154, P151, P05, P23, P172 và P26. Trong đó:

- primary reviewed gold: P154, P151, P05, P23;
- audited distractors: P172, P26;
- các tài liệu còn lại trong `retrieval_full` là retrieval-only/unjudged, không tự động nhận executable binding hoặc primary gold.

Vì qrels hiện rỗng, không thể đánh đồng tất cả unreviewed documents với irrelevant. Precision và nDCG phải để `N/A` cho đến khi có judgment protocol và judgment coverage phù hợp.

### 5.3. Publication time không phải normative effective time

Với real policy artifacts, bốn khái niệm sau được giữ tách biệt:

- `posted_date`;
- `captured_at`;
- `ARTIFACT_PUBLICATION` availability;
- normative effective time.

Dataset không suy diễn real policy supersession hay lịch sử website publication ngoài evidence đã pin. T01–T07 truy vấn supplied edition/snapshot theo contract, không khẳng định rằng availability timestamp là thời điểm policy có hiệu lực pháp quy.

---

## 6. Synthetic world và operational ledger

### 6.1. World identity

| Semantic object | Stable ID |
| --- | --- |
| World `W0` | `2e7c997a-ccf5-5a49-bc46-a6fc0cb50293` |
| Scope `S0` | `427b436e-b39c-57f0-90a8-1f838a2170d1` |
| Driver `D_B` | `c499f934-bfe1-5509-a578-afb09cee357c` |
| Driver `D_H` | `122a3140-7c98-5136-a732-8a9566cb727d` |
| Event source | `4330e39a-f5f2-5566-90c5-8ee983ca8fe3` |
| Incident source | `bbd81324-2784-50ce-857b-99c0b6ad4812` |
| Derived publisher | `3dcc5e8d-dbd8-5d7b-8f93-ada834da3de3` |

Canonical semantic IDs dùng UUIDv5 từ stable private keys. Chúng không phụ thuộc list position, filesystem order, Python hash randomization, mtime, wall clock hay Graphiti UUID.

### 6.2. Tám timeline tách biệt

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

`L0` là base ledger. Bảy timeline còn lại là alternate branches. Chúng không được concatenate hay ingest chung thành một timeline. Shared immutable records giữ nguyên ID, payload, hash và `commit_seq`; branch mutation thao tác trên record set và phải loại cả dependent artifacts nếu chúng làm lộ fact đã mask.

Phân bổ 32 scenario variants:

- 25 `base` variants trên `L0`;
- 5 `observation_mask` variants;
- 1 `retraction_branch`;
- 1 `source_conflict`.

### 6.3. Immutable ledger semantics

Ledger hỗ trợ ba thao tác:

```text
assert
replace
retract
```

Correction/retraction phải target canonical assertion ID và phải được source authority cho phép. Resolution không dùng quy tắc chung chung `latest timestamp wins`; nó phụ thuộc fact key, scope, valid time, known cutoff, source authority, correction permissions và conflict rules. Hai claim trái ngược cùng highest authority rank giữ trạng thái `unresolved_conflict` nếu không có correction relation hợp lệ.

---

## 7. Mô hình thời gian và số học

### 7.1. Bốn trục thời gian

Dataset phân biệt:

- event time;
- valid time;
- known/transaction time;
- ingestion time.

Intervals có dạng nửa mở `[from, to)`. `unknown` không đồng nghĩa infinity. Point event không phải empty interval. Future-effective fact có thể đã được biết, nhưng future-known fact không được rò rỉ vào historical prefix. `known_to` phải được suy ra từ visible prefix thay vì sao chép từ future record.

Business calendar dùng `Asia/Ho_Chi_Minh` khi task yêu cầu; canonical storage timestamps dùng UTC.

### 7.2. Exact arithmetic

Normative threshold và formula logic dùng integer/rational arithmetic, không dùng binary floating point. Các boundary như:

```text
acceptance_rate < 1/2
rating > 97/20
```

được so sánh trên rational value chính xác; rounded display value không được dùng làm truth.

### 7.3. Reported measure và derived metric

`REPORTED_MEASURE` là một source claim về giá trị đã được tính, ví dụ `RM_REVENUE`, `RM_ACCEPTANCE`, `RM_RATING`, `RM_OPDAY`. Nó không ngụ ý dataset biết raw-event lineage nội bộ.

`cancel_rate_30d` là derived metric do benchmark tính từ complete raw population theo definition rõ ràng. Exact aggregate này phải có coverage/source-set evidence; reported value không thể thay thế proof từ raw events.

---

## 8. Coverage và exact aggregate assurance

Release corrective bổ sung ba coverage recipes tại common known cutoff `2026-09-16T03:00:00Z`:

| Coverage | Requested interval | Members | Kết quả |
| --- | --- | ---: | --- |
| D_B terminal trips | `[2026-08-16T17:00:00Z, 2026-09-15T17:00:00Z)` | 10 | 8 completed, 2 cancelled |
| D_H terminal trips | Cùng 30-day interval | 0 | Complete empty set |
| D_B incidents | `[2026-07-01T00:00:00Z, 2026-09-15T17:00:00.000001Z)` | 0 | Complete empty set |

Ba tình huống semantic khác nhau được giữ tách biệt:

1. **Complete non-empty:** D_B có 10 members, 2 chuyến cancelled, do đó `cancel_rate_30d = 2/10 = 1/5`.
2. **Complete empty:** D_H có source-set hoàn chỉnh nhưng 0 members; denominator bằng 0 nên kết quả là `undefined`, không phải 0.
3. **Missing coverage:** `L_NO_COVERAGE` loại coverage publication/artifact visibility. Branch vẫn giữ các trip assertions nhưng không đủ bằng chứng để khẳng định population complete; evaluator phải trả `missing_coverage`/`insufficient_evidence` tùy interface, không được tự enumerate và xem đó là đầy đủ.

Riêng `L_NO_COVERAGE` vẫn chứa 10 D_B trip assertions và world vẫn có đủ 80 terminal trip records. Thiết kế này cố ý phân biệt “có thể thấy một số event” với “có bằng chứng rằng đã thấy toàn bộ population”.

---

## 9. Public/private packaging và snapshot isolation

### 9.1. Public runtime surface

Public package chứa:

- normalized/raw documents và document catalog;
- public definitions;
- entity catalog;
- source registry và source sets;
- operational records/text observations;
- 12 snapshot allowlists;
- Mode A/Mode B source input manifests;
- 42 dev RuntimeQueries và empty test file;
- runtime manifest và corpus-profile manifests.

Mode A trỏ tới deterministic structured public data. Mode B cung cấp deterministic textual observations của cùng public information. Hai mode phải giữ parity về source identity, fact, valid/known time, revision target và provenance. Mode B không được thêm fact và cũng không được bỏ gold-critical fact.

### 9.2. Private evaluation/oracle surface

Private package chứa:

- private world tables và observation plan;
- task bindings;
- scenarios, semantic cases và splits;
- gold answers và proofs;
- support atoms/links;
- corpus roles và review metadata;
- validation report và release manifest.

Runtime retrieval không được mount hay import private package. Public RuntimeQuery không lộ C001–C042 aliases, task IDs, fault labels, expected status, proof hints, private AST hay hidden operand values.

### 9.3. Snapshot là allowlist

Mỗi RuntimeQuery route tới đúng một `public_snapshot_id`. Runtime chỉ được truy cập package của snapshot đó. Isolation áp dụng đồng thời cho:

- ledger prefix;
- entity names;
- source registry;
- documents;
- definitions;
- coverage và source-set members;
- artifacts.

Loader không được bypass isolation bằng cách đọc archive/root operational directory. Việc future object xuất hiện qua catalog entry, filename, header, cache hoặc `known_to` đều được xem là leakage.

---

## 10. Gold, proof và provenance

### 10.1. Observable gold thay vì private truth

Private world được dùng để sinh synthetic data một cách coherent. Gold được chấm theo public evidence quan sát được tại visible prefix.

Do đó:

- private truth biết `X` nhưng public evidence thiếu có thể dẫn tới `insufficient_evidence`;
- hai visible equal-rank sources bất đồng dẫn tới `unresolved_conflict`, ngay cả khi private world biết source nào đúng;
- empty proof không thể làm negative case nhận `Complete=1`;
- short-circuit proof chỉ hợp lệ khi task semantics cho phép.

Gold được xác định trước retrieval output và không phụ thuộc BM25, dense retrieval, reranker, Graphiti, LLM judgment hay baseline answer.

### 10.2. Năm loại support locator

| Locator type | Count | Public target |
| --- | ---: | --- |
| `document_clause` | 31 | Pinned document clause/span |
| `ledger_assertion` | 67 | Public immutable assertion/revision |
| `entity_catalog` | 4 | Public entity identity/name record |
| `definition_artifact` | 3 | Public definition/convention |
| `coverage_artifact` | 5 | Public coverage/source-set artifact |
| **Tổng** | **110** | |

Toàn bộ 110 locators được resolve tới public artifacts. Semantic atom identity không dùng chunk ID, vector-store ID hay Graphiti UUID.

### 10.3. Structured bindings

Bảy structured bindings B01–B07 đều pass. Chúng ràng buộc task với entity/source/time/window/definition/coverage premises cần thiết, thay vì chỉ lưu một expected answer vector. Independent evaluator đã reconstruct chính xác 42/42 expected statuses và typed values mà không đọc generated gold làm oracle duy nhất.

---

## 11. Semantic assurance

### 11.1. Validation summary

| Nhóm | Pass | Fail | Not run | Ghi chú |
| --- | ---: | ---: | ---: | --- |
| V01–V14 | 14 | 0 | 0 | Release/schema/integrity validations |
| SM01–SM08 | 8 | 0 | 0 | Scenario-manifest constraints |
| EX01–EX25 | 25 | 0 | 0 | Executable normative conformance fixtures |
| AUX | 9 | 0 | 0 | Identity, time, event, incident, revision, policy, artifact, context, access |
| Counterfactual groups | 7 | 0 | 0 | Single-premise causal mutations |
| Candidate validation total | 63 | 0 | 0 | Machine-readable validation report |
| DFG01–DFG06 | 6 | 0 | 0 | Data Freeze Gate |
| A1_G1–A1_G6 | 6 | 0 | 0 | Independent assurance gates |

### 11.2. Các placeholder đã được loại bỏ

`AUX_INCIDENT` không còn literal `True`; executable fixtures bao phủ:

- incident open;
- resolved;
- reopened;
- same-time boundary;
- known-time visibility;
- missing service/incident coverage không chứng minh absence;
- identity của cùng canonical incident qua revisions.

Counterfactual checks không còn equality tautology, self-digest comparison hay mutation không đổi input. Mỗi fixture thay đúng một causal premise và chạy reducer/evaluator thật, bao phủ threshold boundary, known-time prefix, correction/retraction, equal-rank conflict, bridge removal, coverage removal và proof-atom removal.

EX01–EX25 đã được port thành independent executable fixtures. Expected fixture table không sinh từ production helper, không dùng private world để lấp public evidence, và kiểm tra các premise về entity/source authority/valid-known time/window/scope/correction/conflict/coverage/exact arithmetic/typed status.

### 11.3. Reproducibility

- clean candidate A: validation `63/63 PASS`;
- clean candidate B: validation `63/63 PASS`;
- logical comparison: 636 files, 0 mismatch;
- provider credentials: không cần;
- source materialization: offline và deterministic;
- cross-platform EOL/binary checkout: được regression-test;
- historical release `0.2.1`: `635/635 PASS`, không thay đổi;
- frozen paths `0.2`, `0.2.1`, `0.2.2`: không bị mutate bởi validation/retrieval workflow.

Logical equality, không phải Parquet byte equality giữa khác toolchain, là reproducibility contract chính. Official A/B comparison dùng cùng pinned toolchain.

---

## 12. Trạng thái retrieval baseline sau freeze

Phần này là bằng chứng Phase B.1 sinh ra **sau khi** dataset đóng băng. Nó giúp đánh giá khả năng sử dụng của dataset, nhưng không thay đổi freeze identity hoặc gold.

### 12.1. Construction và execution

| Chỉ số | Kết quả |
| --- | ---: |
| Snapshots constructed | 12/12 |
| Ledgers isolated | 8/8 |
| Document chunks | 1,575 |
| Document ProjectionLinks | 1,575 |
| Runtime queries | 42 |
| Terminal retrieval traces | 42 |
| Completed retrieval | 42/42 |
| Document candidates | 621 |
| Raw KG candidates | 2,666 |
| Eligible KG/catalog candidates | 1,152 |
| Computation candidates | 4 |
| Hybrid candidates | 1,777 |
| Selected evidence items | 504 |
| Provider calls | 0 |
| Errors/retries | 0/0 |

Mode A structured projection, offline document retrieval, temporal KG search, eligibility normalization, exact aggregate computation, hybrid merge và deterministic selection đã chạy end-to-end cho 42/42 queries. Mode B/Graphiti extraction và live reader chưa chạy do provider boundary.

### 12.2. Proof completeness

| Chỉ số | Kết quả |
| --- | ---: |
| Candidate-complete | 30/42 = 71.4% |
| Selected-complete | 15/42 = 35.7% |
| Selection retention | 15/30 = 50.0% |
| Candidate-incomplete | 12 |
| Selection-loss | 15 |

Trong 12 candidate-incomplete queries:

- 10 là intentionally unavailable diagnostic cases;
- 2 là expected-visible retrieval misses.

Trong 15 selection-loss queries, proof đã đủ tại candidate stage nhưng selector làm rơi ít nhất một required atom. Error inventory machine-readable nằm trong `reports/benchmark_readiness/retrieval-full-mode-a-evaluation.json`.

### 12.3. Support-link recall theo evidence type

| Evidence type | Candidate | Selected |
| --- | ---: | ---: |
| Document clause | 28/31 = 90.32% | 26/31 = 83.87% |
| Ledger assertion | 65/67 = 97.01% | 48/67 = 71.64% |
| Entity catalog | 3/4 = 75.00% | 1/4 = 25.00% |
| Definition artifact | 3/3 = 100.00% | 3/3 = 100.00% |
| Coverage artifact | 3/5 = 60.00% | 3/5 = 60.00% |

Selector đang làm mất tương đối nhiều structured evidence, đặc biệt entity catalog và ledger links. Cả 15 selection losses đều gắn với hard cap 12 items trong khi evidence vẫn còn nằm trong 1,800-token budget. Vì vậy hướng kỹ thuật hợp lý tiếp theo là proof-preserving hybrid selection, chưa phải đổi gold hay regenerate dataset.

### 12.4. Correctness và latency instrumentation

Trên retrieved candidates, các rate sau đạt 100%:

- correct entity;
- valid-time eligibility;
- known-time eligibility;
- correct branch/snapshot;
- source locator resolution.

Cold sequential latency trên 42 queries:

| Stage | Median (ms) | P95 (ms) | Aggregation unit |
| --- | ---: | ---: | --- |
| Document | 16.8015 | 30.386 | query |
| KG search | 62.455 | 93.522 | query search call |
| Eligibility/normalization | 0.6025 | 1.869 | query |
| Computation | 0.003 | 0.004 | query |
| Hybrid merge | 0.290 | 0.472 | query |
| Selection | 0.055 | 0.083 | query |
| **Total pre-reader** | **85.6245** | **118.010** | query, sum of six stages |

Mọi stage trên có denominator/included count 42 và cache status `cold`. `total_pre_reader` dùng sequential accounting và pass invariant `total >= sum(included stages)` cho 42/42 queries. Graph construction có median 8,534.6795 ms, P95 10,685.483 ms trên 12 cold snapshot graphs. Reader latency, token usage và provider cost là `not_run`/`N/A` vì không có provider call.

### 12.5. Determinism của Phase B.1

Hai offline runs A/B có cùng logical digest:

```text
c03dd779cc646f7635d780f5bb762e909dc057bfb695c67984ad74154d461c53
```

Byte hashes của run artifacts khác nhau vì measured latency được giữ trong output; đây không phải logical nondeterminism.

---

## 13. Readiness matrix

| Hạng mục | Trạng thái | Diễn giải |
| --- | --- | --- |
| A0 — Repository/data assurance | `PASS` | Byte portability, frozen verification, source materialization |
| A1 — Semantic assurance | `PASS` | Provenance, coverage, independent reconstruction |
| Frozen release 0.2.2 | `PASS` | `FROZEN`, 636/636 |
| Historical release 0.2.1 | `PASS` | `FROZEN`, 635/635, unchanged |
| Phase B initial offline baseline | `PASS` | Provider-independent baseline exists |
| Phase B.1 offline closure | `PASS` | 42/42 terminal traces, deterministic |
| Mode A KG retrieval | `PASS` | Structured projection path exercised |
| Hybrid candidate construction | `PASS` | 42/42 queries |
| Deterministic selection | `PASS` | Runs on all 42 queries |
| Proof-preserving selection quality | `NEEDS_IMPROVEMENT` | Selected proof complete only 15/42 |
| BRG01 | `PASS` | Offline data/runtime foundation |
| Mode B | `BLOCKED_PROVIDER` | Graphiti extraction/provider not run |
| Dense/reranker | `BLOCKED_MODEL_ARTIFACT` | Chưa có approved/pinned model artifact |
| Live reader/C0 | `BLOCKED_PROVIDER` | Provider path not run |
| BRG02–BRG05 | `BLOCKED` | Các phụ thuộc trên chưa sẵn sàng |
| Full Phase B / full BRG | `PARTIAL` | Không được gọi là benchmark-ready |
| Held-out test release | `NOT_AVAILABLE` | 0 test queries |

---

## 14. Giới hạn và cách diễn giải đúng

### 14.1. Có thể khẳng định

- Dataset frozen bytes và logical contents được kiểm chứng.
- Source materialization có thể thực hiện offline từ pinned archive.
- Business/time/provenance semantics có executable conformance coverage.
- Public/private và snapshot isolation được thiết kế và regression-test.
- 42 dev queries có typed gold, support atoms, proofs và failure semantics.
- Dataset đủ ổn định để tiếp tục phát triển retrieval mà không sửa frozen release.

### 14.2. Không được khẳng định

- Không gọi `0.2.2` là held-out benchmark.
- Không suy rộng 42 cases thành statistically independent production sample.
- Không claim model superiority hay production accuracy.
- Không claim Graphiti correctness: Mode B chưa chạy.
- Không claim reader/agent quality: reader chưa chạy.
- Không claim provider latency/cost: provider calls bằng 0.
- Không báo Precision/nDCG khi qrels universe còn incomplete.
- Không dùng private oracle để resolve public missing/conflict.

### 14.3. Rủi ro còn lại

1. **Không có held-out test set.** Mọi tuning trên 42 queries có nguy cơ overfit catalogue.
2. **Incomplete relevance judgments.** Ranking metrics truyền thống chưa thể diễn giải đúng.
3. **Selector làm mất proof.** Candidate retrieval đang tốt hơn selected-context completeness rất nhiều.
4. **Hai expected-visible retrieval misses.** Candidate generation vẫn chưa hoàn hảo.
5. **Mode B chưa được xác nhận end-to-end.** Dataset có Mode B inputs nhưng Graphiti/provider extraction chưa chạy.
6. **Dense/reranker artifact chưa được phê duyệt.** Local cache không phải repository-pinned artifact và license/runtime dependencies chưa đủ.

---

## 15. Hướng sử dụng và tái lập

### 15.1. Cài đặt

```powershell
uv sync --extra dev
```

### 15.2. Materialize pinned sources offline

Chọn một output rỗng; canonical ignored path là `external/policy_green_sm_corpus`.

```powershell
uv run --extra dev python -m gsm_memory.data.cli materialize-sources `
  --config configs/datasets/gsm-dev-core-0.2.2.json `
  --output external/policy_green_sm_corpus
```

Nếu target đã non-empty, không overwrite ngầm. Hãy dùng explicit verification mode theo CLI help hoặc một empty target khác.

### 15.3. Inventory và candidate build

```powershell
uv run --extra dev python -m gsm_memory.data.cli inventory `
  --config configs/datasets/gsm-dev-core-0.2.2.json

uv run --extra dev python -m gsm_memory.data.cli build `
  --config configs/datasets/gsm-dev-core-0.2.2.json `
  --output <empty-candidate-output>
```

Candidate validation là pre-freeze workflow; nó có thể ghi candidate validation report. Không chạy candidate validator trực tiếp trên frozen release.

### 15.4. Read-only frozen verification

```powershell
uv run --extra dev python -m gsm_memory.data.cli verify-frozen `
  --release data/gsm-dev-core-0.2.2 `
  --certificate reports/data_freeze/gsm-dev-core-0.2.2-freeze-certificate.json `
  --comparison reports/data_freeze/gsm-dev-core-0.2.2-logical-comparison.json
```

Verifier phải strictly read-only, exit khác 0 nếu file missing/mutated/extra hoặc certificate/manifest/comparison mismatch, và không tự sửa mismatch.

### 15.5. Offline data tests

Trong PowerShell, tạm thời gỡ provider credentials khỏi process environment trước khi chạy:

```powershell
Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
Remove-Item Env:GEMINI_API_KEY -ErrorAction SilentlyContinue
Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue

uv run --extra dev pytest -q `
  tests/unit/data `
  tests/conformance/data `
  tests/integration/data
```

Expected checkpoint evidence: `39 passed` cho frozen/data suite. Test result cần được báo lại theo environment hiện tại, không suy diễn từ report cũ nếu command không thực sự chạy.

---

## 16. Khuyến nghị phát triển tiếp theo

### 16.1. Không sửa frozen release

Toàn bộ index, graph, trace và experiment output phải nằm ngoài:

```text
data/gsm-dev-core-0.2.2/
```

Nếu phát hiện defect thật sự trong semantic/source/gold, không patch trực tiếp release; cần defect report và version bump mới.

### 16.2. Ưu tiên proof-preserving selection

Mục tiêu gần nhất nên là nâng selected-proof completeness từ `15/42`, đồng thời giữ hoặc cải thiện 1,800-token context budget và latency. Thiết kế nên:

- giữ các atom theo proof role thay vì chỉ global rank;
- reserve slot cho entity catalog, coverage, definition và revision chain;
- deduplicate physical evidence mà không làm mất semantic roles;
- ưu tiên minimal sufficient proof set nếu nhiều atom cùng support một premise;
- báo candidate-complete/selected-incomplete như first-class failure attribution;
- tuyệt đối không đọc private gold tại runtime.

### 16.3. Sau khi selector ổn định

Thứ tự hợp lý:

1. chốt proof-preserving offline selector;
2. audit và pin một dense/reranker artifact hợp lệ nếu thực sự cần;
3. chạy Mode B/Graphiti với provider boundary rõ ràng;
4. chạy reader/agent sau khi evidence interface ổn định;
5. đo latency/token/cost với denominator và cold/warm status rõ ràng;
6. thiết kế held-out test release riêng trước khi claim benchmark performance.

---

## 17. Tài liệu và artifact tham chiếu

### Normative contracts

- `AGENTS.md`
- `docs/02_synthetic_schema_and_data_design.md`
- `docs/05_dataset_release_spec.md`
- `docs/01_problem_and_evaluation.md`
- `docs/04_benchmark_to_dataset_mapping.md`
- `docs/03_dataset_and_graphiti_baseline_plan.md`

Thứ tự quyền quyết định: `AGENTS.md` → docs 02 cho business/schema semantics → docs 05 cho release composition/implementation → docs 01 cho runtime/evaluation → docs 04 cho methodology → docs 03 cho historical planning.

### Freeze/assurance artifacts

- `reports/data_freeze/gsm-dev-core-0.2.2-freeze-certificate.json`
- `reports/data_freeze/gsm-dev-core-0.2.2-logical-comparison.json`
- `reports/data_freeze/gsm-dev-core-0.2.2-DFG-A1.md`
- `data/gsm-dev-core-0.2.2/private/eval/manifest.json`
- `data/gsm-dev-core-0.2.2/private/eval/validation.json`

### Retrieval evidence

- `reports/benchmark_readiness/phase-b-offline-closure.md`
- `reports/benchmark_readiness/phase-b-offline-closure.json`
- `reports/benchmark_readiness/retrieval-full-mode-a-evaluation.json`
- `reports/benchmark_readiness/brg-report.json`

---

## 18. Kết luận cuối

`gsm-dev-core-0.2.2` là một frozen, reproducible và independently assured development dataset. Nó có đủ source integrity, temporal semantics, public/private isolation, coverage evidence, typed gold và proof provenance để làm nền cho retrieval engineering.

Trạng thái chính xác là:

```text
Dataset/repository assurance    PASS
Semantic assurance              PASS
Offline retrieval foundation    PASS
Proof-preserving selection      NEEDS_IMPROVEMENT
Full BRG                        PARTIAL/BLOCKED
Held-out benchmark              NOT_AVAILABLE
```

Do đó, dataset **đã sẵn sàng để tiếp tục phát triển retrieval trên dev set**, nhưng repository **chưa sẵn sàng để tuyên bố full benchmark readiness hay model performance**.
