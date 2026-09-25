# Bàn giao phát triển Core Retrieval

| Thuộc tính | Giá trị |
| --- | --- |
| Repository | `memory/` |
| Dataset release | `gsm-dev-core-0.2.2` |
| Dataset state | `FROZEN` |
| Schema / release spec | `1.1` / `0.2.0` |
| Seed | `42` |
| Checkpoint khi bàn giao | `30eead44a6306783ad09880fe45fec34ac9679ff` |
| Ngày bàn giao | 2026-09-22 |
| Phase | Phase B — Core retrieval |
| Trạng thái | Offline foundation `PASS`; full BRG `PARTIAL` |

---

## 1. Mục tiêu bàn giao

Nhóm dev tiếp quản phần **core retrieval và evidence construction** trên frozen release `gsm-dev-core-0.2.2`.

Mục tiêu gần nhất không phải thêm reader, prompt engineering hay thay gold. Mục tiêu là:

1. giữ nguyên correctness của document và temporal KG retrieval đã có;
2. xử lý hai expected-visible candidate misses;
3. thay selector hiện tại bằng một **gold-blind, proof-preserving hybrid selector**;
4. giảm selection loss trong cùng hoặc tốt hơn context budget/latency;
5. giữ đầy đủ trace và failure attribution để sau đó tích hợp dense/reranker, Mode B và reader mà không phải thiết kế lại retrieval contract.

Kết quả cần bàn giao là một retrieval pipeline public-only, deterministic, snapshot-isolated và có thể chấm độc lập sau runtime.

---

## 2. Trạng thái xuất phát

### 2.1. Dataset foundation

Dataset đã hoàn tất:

```text
A0 repository/data assurance   PASS
A1 semantic assurance          PASS
DFG01–DFG06                  6/6 PASS
A1_G1–A1_G6                  6/6 PASS
Frozen verification            636/636 PASS
Independent reconstruction     42/42 PASS
Support locators               110/110 PASS
```

Freeze identities:

```text
manifest SHA-256:
f2eb6919d9a30541e804af5f51dc27b005f8332e8109a8eb0ddeffdc2a8d2737

comparison SHA-256:
8438acb3f0e42a41b90f547003e4eea7d1abd79e78a0261bf94018444c11ddb7

logical inventory digest:
cf738397417b7644a51fd6ed11b17b2bc5cac64ea2c9402e75707aad6452aa49
```

### 2.2. Retrieval implementation đã có

| Capability | Trạng thái |
| --- | --- |
| Deterministic document construction | `PASS` |
| BM25 retrieval | `PASS` |
| Exact document/source lineage | `PASS` |
| Mode A Graphiti construction | `PASS` |
| Mode A KG search 42/42 | `PASS` |
| Snapshot/ledger isolation | `PASS` |
| Valid-time/known-time eligibility | `PASS` |
| Entity catalog expansion | `PASS` |
| Exact full-source computation | `PASS` |
| Hybrid candidate union | `PASS` |
| Deterministic public selector | `PASS`, quality cần cải thiện |
| Candidate/selected attribution | `PASS` |
| Dense retrieval | `BLOCKED_MODEL_ARTIFACT` |
| Reranker | `BLOCKED_MODEL_ARTIFACT` |
| Mode B native | `BLOCKED_PROVIDER` |
| Live reader/C0 | `BLOCKED_PROVIDER` |

### 2.3. Baseline numbers

```text
Queries/traces:               42/42
Document candidates:          621
Raw KG candidates:            2,666
Eligible KG/catalog:          1,152
Computation candidates:       4
Hybrid candidates:            1,777
Selected evidence:            504

Candidate proof complete:     30/42 = 71.4%
Selected proof complete:      15/42 = 35.7%
Selection retention:          15/30 = 50.0%
Candidate incomplete:         12
  intentionally unavailable:  10
  expected visible misses:      2
Selection loss:               15
```

Hai con số quan trọng nhất cho phase này:

- candidate generation đã cung cấp đủ proof cho 30 queries;
- selector làm mất proof ở 15 trong 30 queries đó.

Cả 15 observed selection losses đều chạm hard cap 12 items trong khi dropped evidence vẫn có thể nằm trong 1,800-token budget. Đây là bottleneck đã được đo, không phải phỏng đoán.

---

## 3. Phạm vi core retrieval

### Trong phạm vi

- document indexing, chunking và lexical retrieval;
- optional dense retrieval và bounded reranking sau khi model artifact được phê duyệt;
- Mode A temporal KG search;
- public entity resolution candidates;
- valid-time, known-time, scope và snapshot filtering;
- exact computation trên complete source sets;
- hybrid merge và canonical-locator deduplication;
- evidence scoring, dependency-aware selection và packing;
- candidate/selected traces;
- retrieval metrics và failure attribution;
- deterministic configs, cache/index identity và latency accounting.

### Ngoài phạm vi phase này

- thay đổi frozen dataset, queries, gold, proofs hoặc support links;
- thêm business predicates/domain mới;
- reader prompt optimization;
- agent planning/action framework;
- Graphiti Mode B extraction nếu chưa có provider approval;
- tạo held-out test release;
- production deployment, QPS/SLA hoặc online serving;
- dùng private gold làm runtime feature.

---

## 4. Các invariant không được vi phạm

### 4.1. Frozen release là read-only

Không ghi, normalize, regenerate hoặc sửa bất kỳ file nào dưới:

```text
data/gsm-dev-core-0.2/
data/gsm-dev-core-0.2.1/
data/gsm-dev-core-0.2.2/
```

Index, graph, trace, cache và experiment output phải nằm ngoài frozen release, ví dụ:

```text
artifacts/indexes/
artifacts/graphs/
runs/experiments/
reports/benchmark_readiness/
```

### 4.2. Runtime chỉ được đọc public package

Retrieval runtime không được mount hoặc đọc:

```text
private/oracle/
private/eval/
gold_answers.jsonl
proofs.jsonl
support_atoms.jsonl
support_links.jsonl
task_bindings.jsonl
```

Private gold chỉ được evaluator đọc **sau khi runtime trace đã materialize**.

### 4.3. Snapshot là allowlist

Mỗi query có một `public_snapshot_id`. Runtime chỉ được đọc snapshot package tương ứng. Không đọc full operational archive rồi tự lọc sau.

Isolation áp dụng cho:

- documents;
- ledger prefix;
- entity catalog;
- source registry;
- definitions;
- coverage artifacts;
- source-set members;
- synthetic policy publications.

### 4.4. Không sửa evidence semantics

- `unjudged` không đồng nghĩa `irrelevant`;
- missing/undefined/conflict không được đổi thành `false` hoặc `0`;
- exact aggregate yêu cầu complete coverage;
- không aggregate trên top-k;
- equal-rank conflict không dùng score hoặc recency để tự resolve;
- valid time và known time phải được lọc riêng;
- public missing không được lấp bằng private world truth;
- Graphiti UUID, chunk ID và vector ID không phải semantic atom identity.

### 4.5. Determinism

Không dùng wall clock, random global state, filesystem iteration order hoặc process hash cho persistent identity/ranking tie-break. Mọi tie-break phải explicit và stable.

---

## 5. Kiến trúc mục tiêu

```text
RuntimeQuery + selected public snapshot
                    |
          +---------+---------+
          |                   |
   Document retrieval     Temporal KG retrieval
   BM25 / dense / RRF     Mode A, later Mode B
          |                   |
   document candidates    raw KG candidates
          |                   |
          |             eligibility filter
          |             entity/catalog links
          |                   |
          +---------+---------+
                    |
          Exact computation adapter
          coverage + full source set
                    |
             canonical hybrid union
                    |
       public dependency-aware selector
                    |
            selected evidence bundle
                    |
               runtime trace
                    |
       post-runtime private evaluator
```

Core retrieval phải dừng ở `selected evidence bundle` và runtime trace. Reader là consumer phía sau, không được nhúng ngược vào retrieval để thay đổi candidate/gold semantics.

---

## 6. Code map hiện tại

| File | Trách nhiệm hiện tại |
| --- | --- |
| `src/gsm_memory/retrieval/documents.py` | Deterministic chunks, coordinates, ProjectionLinks, inventory digest |
| `src/gsm_memory/retrieval/bm25.py` | Unicode tokenization và BM25 index/search |
| `src/gsm_memory/retrieval/evidence.py` | Evidence item, simple budget selector, temporal helpers |
| `src/gsm_memory/retrieval/offline.py` | Mode A closure, document/KG/computation candidates, hybrid merge, selector, latency traces |
| `src/gsm_memory/adapters/graphiti.py` | Deterministic Mode A graph construction/search/projection lineage |
| `src/gsm_memory/evaluation/runtime.py` | Post-runtime proof coverage và failure attribution |
| `src/gsm_memory/benchmark.py` | Thin experiment CLI |
| `configs/benchmark/phase-b-baseline.json` | Pinned Phase B baseline configuration |
| `tests/unit/retrieval/` | Retrieval unit/regression tests |
| `tests/integration/retrieval/` | Public-only runtime integration tests |
| `tests/conformance/graphiti/` | Temporal/Graphiti conformance tests |

Không tạo generic memory framework mới. Nếu tách module selector/scoring, module mới phải có trách nhiệm rõ ràng và giữ dependency direction đơn giản.

---

## 7. Runtime contracts cần bảo toàn

### 7.1. RuntimeQuery

Public query hiện mang các trường chính:

```text
query_id
query
public_snapshot_id
known_as_of
time_scope
access_scope
entity_refs
application_context.source_snapshot_refs
application_context.definition_refs
```

Không bổ sung private case ID, task ID, expected status hoặc proof roles vào RuntimeQuery.

### 7.2. Candidate evidence

Mỗi candidate cần giữ tối thiểu:

```text
evidence_id
source_kind
source_id
content
source_locator
origin_stage
rank
score
token_cost
eligibility
snapshot_id
```

Structured candidates có thể bổ sung:

```text
entity_refs
predicate
valid
known_at
ledger_id
coverage_status
typed_value
members
```

Mọi evidence phải truy ngược được tới public source locator. Không đưa candidate không resolve được lineage vào selected context như một grounded fact.

### 7.3. Source locator

Các semantic target hiện có:

```text
document clause/span
ledger assertion
entity catalog row
definition artifact
coverage artifact
full-source computation
```

Hybrid dedup chỉ được hợp nhất khi canonical locators giống nhau. Hai candidate nói nội dung tương tự nhưng khác source/revision/time không được tự dedup thành một.

### 7.4. Runtime trace

Mỗi query phải kết thúc bằng terminal trace, kể cả timeout/unsupported/error. Trace cần giữ:

```text
query_id / snapshot_id / ledger_id
raw and eligible candidates per stage
excluded candidates and reasons
hybrid candidates
selected evidence
token and item budget states
truncation flags
stage latency
terminal status
config/runtime identity
```

Không silently drop query.

---

## 8. Bottleneck và nguyên nhân hiện tại

Selector hiện tại là deterministic round-robin theo modality:

```text
document
definition
entity_catalog
kg
coverage
computation
```

Trong từng bucket, selector ưu tiên public-pinned source rồi score/rank. Nó dừng ở:

```text
token_budget = 1800
max_items    = 12
```

Điểm mạnh:

- gold-blind;
- deterministic;
- cân bằng modality cơ bản;
- có exclusion reason và budget state;
- không vượt token budget.

Điểm yếu:

- hard cap đếm physical items thay vì semantic contribution;
- không nhận biết dependency bundle;
- một ledger assertion có thể cần entity/definition/coverage companion;
- round-robin không đảm bảo giữ đủ chain correction/revision;
- không ưu tiên complete minimal public explanation;
- structured evidence bị rơi nhiều hơn document evidence.

Observed selected recall:

| Evidence type | Candidate | Selected |
| --- | ---: | ---: |
| Document links | 28/31 | 26/31 |
| Ledger links | 65/67 | 48/67 |
| Entity catalog | 3/4 | 1/4 |
| Definitions | 3/3 | 3/3 |
| Coverage | 3/5 | 3/5 |

Ưu tiên cần sửa là entity/catalog, ledger dependencies, coverage và revision chains; không nên chỉ tăng document top-k.

---

## 9. Hướng thiết kế selector

Selector mới vẫn phải gold-blind. Có thể dùng public query fields, candidate metadata, public relations và dependency structure; không được dùng support atoms/proofs/private roles tại runtime.

### 9.1. Nguyên tắc đề xuất

1. **Eligibility before scoring**
   Candidate sai scope/snapshot/entity/time không được cứu bằng score cao.

2. **Pinned public constraints first**
   Source editions và definitions được query pin phải có representation trong candidate/selected bundle nếu visible.

3. **Select evidence bundles, không chỉ item rời**
   Ví dụ một assertion có thể kéo theo entity catalog row; exact computation kéo theo coverage artifact; revision có thể cần target assertion.

4. **Reserve structured slots hoặc structured budget**
   Không để document chunks chiếm toàn bộ item cap trong khi entity/coverage evidence có token cost nhỏ.

5. **Dependency closure**
   Nếu chọn computation, phải giữ coverage và lineage cần để reader kiểm chứng. Nếu chọn replacement/retraction, giữ đủ target relation để diễn giải.

6. **Semantic compression**
   Cho phép gộp nhiều assertion refs vào một evidence bundle khi chúng cùng vai trò công khai, nhưng phải giữ toàn bộ canonical locators và không biến aggregate thành precomputed opaque verdict.

7. **Marginal utility per token**
   Score cuối có thể kết hợp public relevance, source pin, modality scarcity, dependency completion và token cost.

8. **Stable tie-break**
   Tie-break bằng canonical fields/evidence ID; cùng input/config phải cho cùng selected bundle.

### 9.2. Public signals được phép dùng

- lexical/dense/reranker score;
- query-pinned source/definition IDs;
- explicit entity refs;
- public source authority;
- predicate/type;
- valid/known eligibility;
- candidate origin/modality;
- public dependency edges;
- revision targets;
- coverage/computation relationship;
- duplicate canonical locator;
- token cost;
- already-selected entity/source/modalities.

### 9.3. Signals bị cấm

- gold answer/status;
- semantic case ID;
- proof ID hoặc minimal atom sets;
- support atom roles;
- private task bindings;
- fault/mutation labels;
- private world truth;
- evaluator-produced `candidate_complete` hoặc `selection_loss` dùng ngược vào runtime.

Private evaluator được dùng để đo thiết kế sau run, không được trở thành feature generator.

---

## 10. Work packages đề xuất

### CR1 — Khóa regression baseline

Mục tiêu:

- giữ một immutable logical baseline của current offline closure;
- pin config, release digest, implementation hash và evaluation report;
- bảo đảm mọi thay đổi sau đó có paired delta.

Deliverables:

- baseline command/config record;
- current 42-query runtime/evaluation summaries;
- regression assertions cho public-only runtime, determinism và latency invariants.

### CR2 — Phân tích hai expected-visible candidate misses

Đọc machine-readable inventory tại:

```text
reports/benchmark_readiness/retrieval-full-mode-a-evaluation.json
  #/candidate_incomplete_inventory
```

Với từng query:

- xác định missing locator type và support role;
- xác định stage sớm nhất: document, KG hoặc computation;
- kiểm tra source có visible trong selected snapshot không;
- kiểm tra search miss, eligibility filter, entity expansion hoặc locator normalization;
- sửa generic retrieval behavior, không thêm `if query_id == ...`;
- thêm regression fixture độc lập.

Acceptance:

- không giảm 30 candidate-complete hiện tại;
- expected-visible misses giảm nếu generic fix hợp lệ;
- 10 intentionally-unavailable diagnostics vẫn không bị fabricate evidence;
- wrong-time/wrong-branch evidence không tăng.

### CR3 — Proof-preserving public selector

Thay hoặc mở rộng `select_public()` bằng selector có:

- explicit candidate dependencies;
- evidence bundles;
- configurable item cap;
- token-budget enforcement;
- per-modality/structured reservation;
- exclusion reason;
- stable deterministic ordering;
- no-gold runtime guard.

Acceptance bắt buộc:

- deterministic repeated result;
- không vượt token budget;
- không vi phạm snapshot/scope/time eligibility;
- không đọc private tree;
- mọi selected item resolve source locator;
- candidate pool không bị selector mutate;
- selection loss inventory được sinh đầy đủ;
- selected completeness không regression so với 15/42.

Engineering target khuyến nghị, không phải normative dataset threshold:

- giảm đáng kể 15 selection losses;
- stretch goal: giữ proof cho phần lớn hoặc toàn bộ 30 candidate-complete queries trong cùng 1,800-token budget;
- nếu vẫn cần item cap, chứng minh cap bằng latency/reader/context contract thay vì giữ hard-coded 12 không có justification.

### CR4 — Selector ablations

Chạy paired ablations trên cùng candidate pools:

```text
round-robin baseline
cap-only increase
structured slot reservation
dependency bundle selection
utility-per-token selection
```

Báo:

- candidate completeness;
- selected completeness;
- selection retention;
- modality recall;
- selected items/tokens;
- latency;
- per-query gains/regressions;
- exclusion reasons.

Không Cartesian sweep quá lớn trên 42 dev queries. Mỗi comparison nên thay một thành phần và ghi rõ đây là dev tuning.

### CR5 — Dense/reranker integration, chỉ sau artifact approval

Không dùng local cache tùy ý. Trước khi code measured path phải pin:

- repository/model ID;
- immutable revision;
- license;
- artifact hashes;
- tokenizer/runtime versions;
- device/precision;
- offline/cache behavior;
- embedding dimension và normalization;
- top-k/fusion/rerank caps.

Dense/reranker phải trả cùng candidate contract và source lineage như BM25. Fusion không được làm mất exact source/revision identity.

Nếu chưa có approved artifact, giữ trạng thái `BLOCKED_MODEL_ARTIFACT`; không đổi thành `PASS` hoặc silently fallback rồi gọi đó là dense baseline.

### CR6 — Retrieval closure report

Sau khi CR2–CR4 ổn định:

- chạy 42/42 `retrieval_full` queries;
- chạy hai independent logical runs;
- cập nhật machine-readable result;
- cập nhật BRG sub-gates có liên quan;
- giữ reader, Mode B và provider metrics là `not_run/blocked` nếu chưa thực sự chạy.

---

## 11. Evaluation protocol

### 11.1. Primary retrieval metrics

Ưu tiên metrics gắn với proof:

```text
candidate proof completeness
selected proof completeness
selection retention
support-link recall by locator type
correct entity rate
valid-time eligibility rate
known-time eligibility rate
correct snapshot/branch rate
source-locator resolution rate
```

Không dùng answer accuracy thay retrieval quality trước khi reader tồn tại.

### 11.2. Ranking metrics

Precision/nDCG hiện phải là:

```text
N/A (incomplete_judgments)
```

`relevance_judgments.jsonl` đang rỗng. Không map toàn bộ unjudged documents thành relevance 0.

### 11.3. Failure attribution

Mỗi query phải được phân vào stage sớm nhất:

```text
runtime/configuration failure
document candidate miss
KG candidate miss
eligibility/filtering error
computation/coverage miss
candidate complete, selector dropped proof
selected complete, reader failure       # future phase
intentionally unavailable diagnostic
```

### 11.4. Không có normative quality threshold

DFG/BRG không quy định retrieval phải đạt một accuracy cụ thể mới được gọi là executable benchmark. Điểm số thấp nhưng được đo đúng là một kết quả hợp lệ. Không sửa gold hoặc nới evaluator để đạt target.

---

## 12. Test strategy

### Unit tests

- stable chunk and candidate identity;
- canonical locator deduplication;
- half-open interval và point eligibility;
- deterministic ranking/tie-break;
- dependency bundle closure;
- item/token budget boundaries;
- entity/coverage/definition reservation;
- correction/retraction chain packing;
- selector không mutate inputs;
- missing coverage không tạo computation candidate;
- complete-empty aggregate giữ `undefined`, không thành 0.

### Conformance tests

- wrong snapshot/scope bị reject;
- future-known evidence không leak;
- wrong entity/window/source edition không selected;
- equal-rank conflict giữ cả candidates cần thiết hoặc explicit conflict evidence;
- public pinned edition được bảo toàn;
- Mode A source/time/provenance round-trip;
- no private-tree access.

### Integration tests

- chạy 42/42 public queries khi private tree bị loại khỏi runtime view;
- mỗi query có terminal trace;
- evaluator chỉ chạy sau khi trace được ghi;
- mutated/missing evidence cho expected attribution;
- two-run logical determinism;
- sequential/parallel latency invariants.

### Commands tối thiểu

```powershell
uv sync --extra dev --extra graphiti

Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
Remove-Item Env:GEMINI_API_KEY -ErrorAction SilentlyContinue
Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue

uv run --extra dev pytest -q tests/unit/retrieval
uv run --extra dev --extra graphiti pytest -q tests/conformance/graphiti
uv run --extra dev --extra graphiti pytest -q tests/integration/retrieval

uv run --extra dev --extra graphiti python -m gsm_memory.benchmark offline-closure `
  --release data/gsm-dev-core-0.2.2 `
  --profile retrieval_full `
  --output runs/experiments/phase-b/<run-name>.json `
  --document-top-k 10 `
  --graph-top-k 40 `
  --token-budget 1800

uv run --extra dev --extra graphiti python -m gsm_memory.benchmark evaluate `
  --release data/gsm-dev-core-0.2.2 `
  --runtime-report runs/experiments/phase-b/<run-name>.json `
  --output reports/benchmark_readiness/<evaluation-name>.json
```

Trước và sau test:

```powershell
uv run --extra dev python -m gsm_memory.data.cli verify-frozen `
  --release data/gsm-dev-core-0.2.2 `
  --certificate reports/data_freeze/gsm-dev-core-0.2.2-freeze-certificate.json `
  --comparison reports/data_freeze/gsm-dev-core-0.2.2-logical-comparison.json

git diff --name-only -- `
  data/gsm-dev-core-0.2 `
  data/gsm-dev-core-0.2.1 `
  data/gsm-dev-core-0.2.2
```

Frozen diff bắt buộc rỗng.

---

## 13. Latency và instrumentation contract

Mỗi thống kê phải ghi:

```text
aggregation unit
denominator
included count
cold/warm/cache status
included stages
median / p95
```

Sequential execution:

```text
total_pre_reader >= sum(included stage durations)
```

Parallel execution:

```text
total_pre_reader >= max(included stage wall-clock durations)
```

Baseline hiện tại, cold/42 queries:

| Stage | Median ms | P95 ms |
| --- | ---: | ---: |
| Document | 16.8015 | 30.386 |
| KG search | 62.455 | 93.522 |
| Eligibility/normalization | 0.6025 | 1.869 |
| Computation | 0.003 | 0.004 |
| Hybrid merge | 0.290 | 0.472 |
| Selection | 0.055 | 0.083 |
| Total pre-reader | 85.6245 | 118.010 |

Selector optimization không cần hy sinh correctness để giảm 0.055 ms; proof preservation quan trọng hơn micro-optimization ở stage này.

---

## 14. Git và artifact policy

### Source/config/tests/reports có thể commit

```text
src/gsm_memory/retrieval/
src/gsm_memory/evaluation/
src/gsm_memory/adapters/graphiti.py       # chỉ khi cần cho retrieval contract
src/gsm_memory/benchmark.py
configs/benchmark/
tests/unit/retrieval/
tests/conformance/graphiti/
tests/integration/retrieval/
reports/benchmark_readiness/              # curated reports
```

### Generated paths không stage

```text
artifacts/indexes/
artifacts/graphs/
artifacts/data_builds/
runs/experiments/
```

Trước khi code:

```powershell
git status --short --branch
git rev-parse HEAD
rg --files
```

Không reset/clean hoặc ghi đè untracked user files.

---

## 15. Definition of Done cho Core Retrieval checkpoint

Checkpoint core retrieval được coi là hoàn thành khi có evidence cho tất cả mục sau:

- [ ] Frozen verifier vẫn `636/636 PASS`.
- [ ] Frozen release diff rỗng.
- [ ] 42/42 queries có terminal retrieval traces.
- [ ] Runtime chạy được khi private tree không được mount.
- [ ] Candidate generation không regression so với baseline đã pin.
- [ ] Hai expected-visible misses có root-cause và regression coverage; nếu chưa sửa được phải ghi blocker chính xác.
- [ ] Selector mới deterministic và gold-blind.
- [ ] Selected evidence không vượt token budget.
- [ ] Snapshot/scope/valid/known-time eligibility giữ 100% trên eligible candidates.
- [ ] Tất cả selected evidence có resolvable public lineage.
- [ ] Selection-loss inventory được cập nhật machine-readable.
- [ ] Selected proof completeness không thấp hơn 15/42 và có paired delta rõ ràng.
- [ ] Mỗi regression/gain có query-level attribution.
- [ ] Latency statistics có unit/denominator/cache status/included stages.
- [ ] Two-run logical determinism pass.
- [ ] Unit, conformance và integration retrieval suites pass.
- [ ] Precision/nDCG vẫn `N/A` nếu judgments chưa đầy đủ.
- [ ] Mode B, dense/reranker hoặc reader không bị claim `PASS` nếu chưa thực sự chạy.

Không gọi checkpoint này là full BRG hoặc benchmark generalization.

---

## 16. Blockers và quyết định cần owner phê duyệt

### Không chặn core selector work

- provider credentials;
- Mode B extraction model;
- live reader model;
- held-out test release;
- dense/reranker artifact.

Core candidate/selection work hiện tại có thể tiếp tục hoàn toàn offline.

### Cần quyết định trước khi mở capability tương ứng

1. **Dense model:** repository, revision, license, hashes, runtime/dependencies.
2. **Reranker:** model, revision, license, maximum candidates và latency budget.
3. **Mode B:** provider/model/prompt/config, quota, cost ceiling và retry policy.
4. **Reader:** provider/model/prompt, output schema, context/output budget và oracle-context control.
5. **Held-out release:** world/scenario split, query volume và lock/unsealing protocol.

Thiếu các quyết định này phải được ghi `BLOCKED`, không tự chọn model/provider để lấp chỗ trống.

---

## 17. Tài liệu cần đọc theo thứ tự

1. `AGENTS.md`
2. `docs/02_synthetic_schema_and_data_design.md`
3. `docs/05_dataset_release_spec.md`
4. `docs/01_problem_and_evaluation.md`
5. `README.md`
6. `reports/data_freeze/gsm-dev-core-0.2.2-DFG-A1.md`
7. `reports/data_freeze/gsm-dev-core-0.2.2-bao-cao-dataset-chi-tiet.vi.md`
8. `reports/benchmark_readiness/phase-b-offline-closure.md`
9. `reports/benchmark_readiness/brg-report.json`
10. `reports/benchmark_readiness/retrieval-full-mode-a-evaluation.json`
11. retrieval implementation và tests trong code map ở mục 6.

Quyền quyết định semantics:

```text
AGENTS.md
  → docs 02: business/schema semantics
  → docs 05: release composition/implementation
  → docs 01: runtime/evaluation
  → docs 04: methodology
  → docs 03: historical planning
```

Nếu docs 02 và 05 mâu thuẫn thật về semantics, dừng phần bị ảnh hưởng và báo exact sections; không tự chọn rule thuận tiện cho retriever.

---

## 18. Kết luận bàn giao

Core retrieval không bắt đầu từ số 0. Repository đã có một offline end-to-end evidence path với document retrieval, Mode A temporal KG, exact computation, hybrid candidates, deterministic selection và private post-runtime evaluation.

Bottleneck đã được định lượng:

```text
candidate generation: 30/42 proof-complete
selection:            15/42 proof-complete
selection loss:       15 queries
```

Hướng triển khai hợp lý là:

```text
1. khóa regression baseline
2. xử lý 2 expected-visible candidate misses
3. triển khai dependency-aware, proof-preserving public selector
4. chạy paired selector ablations
5. đóng offline core retrieval checkpoint
6. sau đó mới mở dense/reranker, Mode B và reader khi blockers được giải quyết
```

Thành công của phase này được đo bằng proof preservation, lineage correctness, temporal/snapshot isolation và reproducibility; không được đo bằng việc làm cho gold dễ hơn hoặc đưa private evaluation metadata vào runtime.
