# Bàn giao toàn bộ dự án GSM Memory cho AI agent

**Cập nhật tại:** 17/09/2026 (Asia/Ho_Chi_Minh)  
**Repository:** `D:\vinai\memory`  
**Checkpoint chính:** dataset `gsm-dev-core-0.2.1` đã được pipeline hiện tại đóng băng; BRG và mọi thí nghiệm retrieval/Graphiti/agent vẫn chưa chạy.  
**Đối tượng đọc:** coding/research agent tiếp quản mà không có ngữ cảnh hội thoại trước đó.

---

## 0. Tóm tắt điều hành

Dự án nghiên cứu một retrieval layer cho AI agent cần kết hợp:

1. tài liệu/chính sách có source, edition và clause;
2. operational memory có entity, event, valid time, known time và revision;
3. một evidence bundle đủ để downstream agent trả lời có căn cứ.

Đối tượng tối ưu chính là **retrieval và evidence construction**, không phải xây
một memory framework tổng quát. Graphiti là temporal-KG reference baseline của
giai đoạn sau, không phải nguồn chân lý và cũng chưa được tích hợp vào release
dataset hiện tại.

Trạng thái thực tế của repo:

- DATA_G0–DATA_G6 đã có implementation offline dưới `src/gsm_memory/data/` và
  `src/gsm_memory/evaluation/`.
- Release hiện hành là `data/gsm-dev-core-0.2.1/`, state `FROZEN`.
- Hai clean candidates A/B tồn tại và external comparison ghi 635 semantic
  files, 0 mismatch.
- Freeze certificate ghi DFG01–DFG06 đều PASS.
- Bộ data tests được chạy lại trong lần bàn giao này với provider keys unset:
  `9 passed in 5.83s`.
- `gsm-dev-core-0.2` vẫn bất biến nhưng đã deprecated vì 17/42 RuntimeQuery làm
  lộ private alias hoặc time-scope shorthand. Không dùng release này cho run mới.
- Document/KG retrieval, chunking, embeddings, Graphiti projection/search,
  evidence selector, reader/agent runs, latency/cost và BRG đều **not run**.

Một cảnh báo quan trọng: “DFG PASS” ở trên là kết quả của validator hiện tại.
Implementation validation vẫn còn các kiểm tra nông và một số placeholder/tautology
trong AUX/counterfactual; oracle cũng có nhánh task-specific. Vì vậy cần phân biệt:

```text
artifact status được pipeline hiện tại chứng nhận = FROZEN / DFG PASS
độ bảo đảm semantic độc lập theo toàn bộ tinh thần spec = còn technical debt
benchmark readiness = chưa đạt
```

Agent tiếp theo không được sửa release frozen tại chỗ. Nếu audit độc lập tìm thấy
lỗi ảnh hưởng data/gold, tạo version mới và ghi changelog/deprecation record.

---

## 1. Thứ tự nguồn chuẩn

Đọc theo thứ tự dưới đây; không dùng một tài liệu planning cũ để ghi đè contract
mới hơn.

| Ưu tiên | Tài liệu | Quyền quyết định |
| ---: | --- | --- |
| 1 | `AGENTS.md` | Quy tắc làm việc trong repo, frozen invariants và ranh giới phase |
| 2 | `docs/02_synthetic_schema_and_data_design.md` | Business/data semantics, schema 1.1, identity/time/ledger/proof/formulas |
| 3 | `docs/05_dataset_release_spec.md` | Release composition, 42-case catalog, package, validation và DFG |
| 4 | `docs/01_problem_and_evaluation.md` | Runtime request/evidence contract, Q1–Q7, L1–L4 và failure taxonomy |
| 5 | `docs/04_benchmark_to_dataset_mapping.md` | Methodology và lý do thiết kế benchmark |
| 6 | `docs/03_dataset_and_graphiti_baseline_plan.md` | Kế hoạch baseline/BRG; nhiều status trong file này là lịch sử và đã stale |
| 7 | `docs/research/gsm_retrieval_research.md` | Literature synthesis và hướng kỹ thuật; không override contract |

Quy tắc xử lý xung đột:

- `02` sở hữu business/schema semantics.
- `05` sở hữu exact release composition và implementation contract.
- `01` sở hữu request/evaluation semantics.
- `04` giải thích phương pháp.
- `03` là planning/historical guidance khi chưa bị tài liệu mới hơn thay thế.

Ví dụ về tài liệu stale: `03` còn mô tả repository/implementation là chưa xác
minh; hiện repo đã có Git, code data pipeline, frozen releases và dependency lock.
Không copy các status `[UNKNOWN]` cũ vào báo cáo hiện tại mà không kiểm lại.

---

## 2. Bài toán nghiên cứu

### 2.1. Mục tiêu

Với query `q`, hệ thống lấy document candidates `D(q)` và graph/operational
candidates `G(q)`, hợp nhất thành candidate pool, chọn context theo budget rồi
đưa cho reader:

```text
C(q) = D(q) ∪ G(q)
E(q) = Select(C(q), budget)
y    = Agent(q, E(q))
```

Ba điểm phải đo tách biệt:

| Tầng | Câu hỏi |
| --- | --- |
| Retrieval | Candidate pool có chứa một proof đầy đủ không? |
| Context construction | Selector có giữ proof đó trong context thật không? |
| Reasoning | Reader có dùng đúng evidence và trả đúng status/value/citation không? |

Một câu trả lời đúng do kiến thức sẵn có nhưng không có evidence hợp lệ không
được tính là grounded success.

### 2.2. Bảy query families

| Family | Năng lực |
| --- | --- |
| Q1 | Tìm document/policy clause đúng source, version, scope và exception |
| Q2 | Resolve đúng entity và historical state |
| Q3 | Tìm behavior/history, phân biệt raw event, report, aggregate và inference |
| Q4 | Kết hợp operational facts với document rule/applicability |
| Q5 | Giữ multi-hop bridge/path cần thiết |
| Q6 | Xử lý update, correction, retraction và historical prefix |
| Q7 | Abstain đúng khi missing, conflict hoặc ambiguous |

### 2.3. Failure attribution

Failure taxonomy trong contract chia lỗi thành:

- construction/ingestion: entity merge/split, fact/time/lineage sai;
- document retrieval: lexical, semantic, source/section/version/exception/rerank;
- KG retrieval: resolution, relation, bridge, fan-out, stale/time/provenance;
- hybrid/context: join, applicability, source dominance, redundancy, selection;
- agent: reasoning, unsupported claim, citation, abstention hoặc action.

Nguyên tắc quy lỗi: nếu selected context thiếu evidence thì không được quy lỗi
đầu tiên cho reader. Nếu candidate đủ nhưng selected bundle thiếu, đó là selection
loss. Nếu selected bundle đủ mà answer sai, điều tra reasoning.

### 2.4. Luận điểm kỹ thuật hiện tại

Research report đề xuất thứ tự:

1. giữ Graphiti làm reference, nhưng kiểm temporal fidelity thay vì mặc định tin;
2. xây document baseline mạnh: section-aware BM25 + multilingual dense + RRF +
   bounded reranker;
3. KG retrieval bắt đầu từ business ID, source/time guards và bounded typed
   1–2 hop traversal;
4. hybrid layer route theo task và giữ đủ complementary evidence roles;
5. chỉ thêm IRCoT/contextual hierarchy/learned sparse/late interaction khi
   baseline chỉ ra failure mechanism cụ thể;
6. đo quality–latency–cost–freshness riêng, không suy scale từ số token hoặc
   một accuracy tổng hợp.

Khoảng trống R&D đáng làm nhất là graph–document alignment cho một operational
KG độc lập với policy corpus: đúng entity, đúng hai đồng hồ, đúng source, đủ
bridge/exception và vừa context budget.

---

## 3. Semantics không được làm sai

### 3.1. Public truth khác private world truth

Private world giúp generator tạo dữ liệu nhất quán. Gold chấm cái có thể chứng
minh từ public evidence ở đúng prefix. Do đó:

- private truth là `X` nhưng evidence bị mask → có thể là
  `insufficient_evidence`;
- hai public sources ngang quyền mâu thuẫn → `unresolved_conflict`, dù private
  world biết nguồn nào đúng;
- không dùng oracle làm runtime tool để “sửa” retrieval.

### 3.2. Bốn đồng hồ

| Clock | Ý nghĩa |
| --- | --- |
| `event_time` | Lúc event xảy ra |
| valid time | Lúc fact đúng trong nghiệp vụ |
| known/transaction time | Lúc một assertion version được công bố/biết |
| ingestion/index time | Wall-clock của system run; chỉ thuộc run artifacts |

Interval là `[from, to)`. `unknown` không phải infinity. Future-effective fact
có thể đã known; late event có thể đã xảy ra nhưng chưa known. Historical
snapshot không được mang `known_to`, alias, summary, catalog hoặc embedding từ
tương lai.

### 3.3. Immutable ledger

`SourceRecord` là atomic immutable commit với `assert`, `replace` hoặc `retract`.
Correction/retraction target canonical assertion IDs và phải được source registry
cho phép. Không có generic rule “timestamp mới nhất thắng”. Equal highest-rank
claims khác value giữ conflict unresolved.

Reducer phải:

1. chọn prefix `known_at <= known_as_of`;
2. replay theo `(known_at, commit_seq)`;
3. giữ valid extent tách với known extent;
4. resolve authorization/revisions/source precedence;
5. sau đó mới lọc window/applicability.

### 3.4. Reported measure khác derived metric

Reported measures của pilot:

- `RM_REVENUE`;
- `RM_OPDAY`;
- `RM_ACCEPTANCE`;
- `RM_RATING`.

Chúng chỉ chứng minh “nguồn báo giá trị/status này cho đúng definition/window”,
không chứng minh raw-event lineage. Derived metric bắt buộc là:

```text
cancel_rate_30d = cancelled / (cancelled + completed)
```

Derived exact value cần complete coverage/source set. Denominator 0 với coverage
đầy đủ → `undefined`; thiếu coverage → `incomplete/insufficient`; conflict ảnh
hưởng population → conflict. Không đổi missing/undefined/conflict thành số 0.

### 3.5. Exact arithmetic và công thức

Không dùng binary float cho normative logic:

```text
F_REV(R)    = max(280000 - R, 0) / 5
F_AUTO      = bike_partner AND acceptance < 1/2
F_RATING    = rating > 97/20
F_SCOPE     = taxi_driver AND membership thuộc Depot được P23 nêu
```

Boolean composition giữ T/F/U/C. Một false premise có thể short-circuit hợp lệ;
unknown/conflict không tự thành false.

### 3.6. Identity và provenance

- Canonical IDs là deterministic UUIDv5 từ stable private keys.
- Không dùng `hash()`, list position, wall time, mtime, Graphiti UUID hoặc chunk ID.
- Display name không phải entity ID; hai drivers có thể cùng tên.
- Gold semantic identity là `SupportAtom`, không phải physical retrieval unit.
- Source locator tồn tại trước run; ProjectionLink tới chunk/Graphiti object chỉ
  được tạo sau khi object thật đã được build.

### 3.7. Public/private boundary

Runtime được đọc public snapshot package đã route và bytes của visible refs.
Runtime không được mount:

- `private/oracle/`;
- `private/eval/`;
- task bindings, gold answers, proof hints, mutation/fault labels;
- full operational archive để bypass snapshot;
- profile khác hoặc future catalog.

---

## 4. Kiến trúc dữ liệu và runtime

### 4.1. Các lớp

```text
Private oracle + reviewed bindings
              |
              v
Immutable public source ledger -----> Mode A structured input
              |                       Mode B text observations
              v
       Snapshot allowlists
          /           \
 Document index    Temporal KG/projection
          \           /
       candidate evidence
              |
       role-aware selector
              |
       reader/agent + trace
              |
        private evaluator
```

Dataset frozen hiện mới materialize đến source-level packages/queries/gold.
Các boxes “index/KG/selector/reader/run trace” thuộc BRG và chưa tồn tại.

### 4.2. Mode A và Mode B

- Mode A trỏ vào deterministic structured records, dùng làm reference
  construction và upper bound không extraction loss.
- Mode B trỏ vào deterministic textual observations của cùng public information,
  dùng đo extraction/construction loss.
- Hai mode phải giữ parity về source identity, facts, valid/known time, revision
  targets và provenance.
- So A/B phải giữ snapshots, queries, retriever và reader budgets cố định.

### 4.3. Dependency direction mong muốn

```text
types / IDs / time / serialization
              ↓
          corpus + world
              ↓
             ledger
              ↓
             reducer
              ↓
        cases + gold/proofs
              ↓
      snapshots + packages
              ↓
             queries
              ↓
           validation
              ↓
            packaging
```

Không tạo circular dependency trong đó generator và “independent” validator dùng
cùng một helper cho expected outcome.

---

## 5. Dataset report: `gsm-dev-core-0.2.1`

### 5.1. Identity

| Thuộc tính | Giá trị |
| --- | --- |
| Dataset | `gsm-dev-core-0.2.1` |
| Business schema | `1.1` |
| Release spec | `0.2.0` |
| Seed | `42` |
| Query language | Tiếng Việt |
| State | `FROZEN` |
| Split | dev=42, test=0 |
| Manifest SHA-256 | `61dddfd6c9f078b9b8c8288562c6196ae28a7ece390cd6d61d03041183b515b5` |
| Logical inventory digest | `4ed08a35393912150ffb731946965c5adc827a403835d4c9a96e9c333df16d11` |
| Comparison report SHA-256 | `cf1b105bd0beab4bd63cd774edf61460c49ad8ed6156ae9a734f205d5c721357` |

### 5.2. Release inventory

| Thành phần | Actual |
| --- | ---: |
| World | 1 |
| Drivers | 8 |
| Distinct terminal trips | 80 |
| Canonical real articles | 224 |
| Audited / primary-gold real sources | 6 / 4 |
| Synthetic policy versions | 3 |
| Public definitions | 12 |
| Operational source types | 7 |
| Ledger timelines | 8 |
| Public snapshots | 12 |
| Scenario roots / variants | 25 / 32 |
| Semantic cases / direct renderings | 42 / 42 |
| Support atoms / support links | 110 / 110 |
| Dev / test queries | 42 / 0 |

42 queries là development/conformance fixtures dùng chung world và histories;
không phải 42 IID samples. Chạy hai profiles cũng không biến chúng thành 84 mẫu.

### 5.3. Real corpus

Pinned archive:

```text
data/raw/archives/policy_green_sm_source.zip
SHA-256: cfe9e4555dbedf81396004c7a7d0ace52dcbb1deb758110c4aded3b6741ba9c9
```

Corpus có 224 bài riêng; aggregate duplicate không là retrieval document. Sáu
audited snapshots:

```text
P154, P151, P05, P23 = reviewed TEXT spans và primary gold
P172, P26            = audited distractors
218 bài còn lại      = retrieval-only / unjudged
```

`unreviewed != irrelevant`. Không gán 218 bài relevance=0. Precision/MRR/nDCG
chỉ báo khi qrels/judgment coverage đủ; nếu không thì `N/A
(incomplete_judgments)` và dùng confirmed-support/proof metrics.

### 5.4. Corpus profiles

| Profile | Real articles | Dùng cho |
| --- | ---: | --- |
| `debug_core@1.0` | 6 | loader smoke, conformance, adapter debug |
| `retrieval_full@1.0` | 224 | main document/hybrid dev runs |

Cả hai dùng chung 3 synthetic document versions và 12 definitions. Main result
trên release này phải dùng `retrieval_full`; nếu dùng `debug_core`, ghi rõ đó là
six-source diagnostic.

### 5.5. World và sources

W0 có 8 drivers, 4 fleets, HN/HCM_OLD, service tổng hợp, một incident và 80
terminal trip events. D_E và D_F cùng display name “Minh” để kiểm ambiguity.

Bảy public sources: registry, event log, incident log, metric feed A/B, policy
publisher và derived publisher. Predicate/correction permissions nằm trong
source registry; feed A/B ngang authority để tạo conflict control.

### 5.6. Tám ledger branches

| Branch | Records | Diagnostic |
| --- | ---: | --- |
| `L0` | 359 | canonical timeline |
| `L_NO_OPDAY` | 358 | thiếu operating-day evidence |
| `L_WRONG_DRIVER` | 358 | chỉ còn revenue của driver khác |
| `L_CONFLICT` | 359 | equal-rank 200000/240000 conflict |
| `L_RETRACT` | 359 | report bị retract, không replacement |
| `L_WRONG_WINDOW` | 358 | đúng value nhưng sai window |
| `L_NO_BRIDGE` | 358 | thiếu `BASED_IN` bridge |
| `L_NO_COVERAGE` | 358 | events còn nhưng thiếu completeness proof |

Branches là alternate timelines. Không concatenate hoặc ingest chung.

### 5.7. Mười hai snapshots

- 5 prefixes từ L0: 04/08, 06/08, A0, AC, A1.
- 7 final prefixes cho bảy alternate branches.
- Hai snapshots sớm chưa thấy 224 real docs vì benchmark publication time chưa tới.
- Snapshot là allowlist cho ledger, names, sources, documents, definitions,
  artifacts và source-set members.

### 5.8. Task composition

| Task | Cases | Claim được phép |
| --- | ---: | --- |
| T01 | 2 | Nội dung P154 về scope/day/formula |
| T02 | 11 | Áp rule P154 lên reported inputs, không claim wallet/raw revenue |
| T03 | 3 | Chỉ auto-accept condition của P151 |
| T04 | 3 | Nội dung FAQ P05 về clock/unit/rating/week |
| T05 | 3 | Chỉ rating condition `> 4.85`, không full eligibility |
| T06 | 2 | Nhóm Depot và literal pay-period trong P23 |
| T07 | 4 | Notice scope theo program/membership, không full eligibility |
| Foundation | 14 | aggregate, bridge, entity, state, event, synthetic version |

T01–T07 pin intended source edition. Đây chưa phải open-ended “tìm policy hiện
hành”. Real publication availability cũng không chứng minh normative effective
time.

### 5.9. Case distributions

| Dimension | Composition |
| --- | --- |
| Gold track | source_grounded=7; conditional_binding=21; synthetic_control=14 |
| Status | answerable=32; insufficient=8; conflict=1; ambiguous=1 |
| Family | Q1=7; Q2=2; Q3=2; Q4=12; Q5=1; Q6=8; Q7=10 |

### 5.10. Evidence gold

Gold gồm:

- `SupportAtom`: semantic evidence role;
- `EvidenceProof`: AND/OR và minimal sufficient atom sets;
- `GoldSupportLink`: private mapping atom → canonical source/locator.

Release ghi 32 sufficient proofs và 10 diagnostic proofs. Negative cases không
có empty sufficient proof; chúng giữ missing roles, conflicts hoặc candidate IDs.

### 5.11. Package boundary

Public side gồm documents, profiles, definitions, entity/source registries,
immutable ledgers, text observations, snapshots, Mode A/B manifests và 42 dev
RuntimeQueries.

Private side gồm oracle world, observation plan, policy rules/bindings, scenario
mutations, semantic cases, gold/proofs/support links, corpus roles và validation.

Runtime chỉ được route vào:

```text
active snapshot visible refs
∩ active corpus profile members
∩ access scope
```

### 5.12. Freeze evidence

| Validation group | PASS | FAIL | NOT_RUN |
| --- | ---: | ---: | ---: |
| V01–V10 | 10 | 0 | 0 |
| SM01–SM08 | 8 | 0 | 0 |
| EX01–EX25 | 25 | 0 | 0 |
| AUX groups | 9 | 0 | 0 |
| Counterfactual | 4 | 0 | 0 |

External reports ghi DFG01–DFG06 PASS và clean A/B comparison 635 files, zero
mismatch. Trong lần bàn giao này, một phép kiểm read-only đã hash lại toàn bộ
635 entries trong frozen `file_inventory`: 635 checked, 0 missing/hash mismatch;
manifest và comparison-report hashes đều khớp freeze certificate. Xem phần 8 để
hiểu giới hạn semantic assurance của những checks này.

---

## 6. Release history

### 6.1. `gsm-dev-core-0.2`

- Đã frozen và phải giữ immutable.
- Manifest SHA-256:
  `ce7ff9edfaf116716551f5af4907b47c66bf4bd878df0cea4d89062b808ab190`.
- Deprecated external record:
  `reports/data_freeze/gsm-dev-core-0.2-deprecation.json`.
- Lý do: 17/42 public query renderings lộ private aliases hoặc time-scope labels.

### 6.2. `gsm-dev-core-0.2.1`

- Regenerated với dataset namespace mới, public query leakage regression guard.
- Zero finding cùng loại theo validator hiện tại.
- Supersedes 0.2 cho mọi experiment mới.
- Không sửa bytes của 0.2.

Nếu tạo 0.2.2 hoặc release khác, phải nêu rõ lỗi semantic/source/gold nào buộc
version bump; không đổi version chỉ để tuning baseline.

---

## 7. Implementation hiện có

### 7.1. Dependencies

Project Python 3.12, quản lý bởi `uv`:

- core: `pyarrow==21.0.0`, `pydantic==2.13.5`;
- dev: `pytest==8.4.2`;
- optional Graphiti: `graphiti-core==0.30.2` và provider/backend packages.

Offline G0–G6 không được phụ thuộc provider keys/network/Graphiti.

### 7.2. Module map

| File | Trách nhiệm hiện tại |
| --- | --- |
| `data/primitives.py` | version constants, UUIDv5, seed, UTC/rational/canonical hash, JSONL I/O |
| `data/contracts.py` | closed Pydantic `ScenarioManifest` và mutation specs |
| `data/catalog.py` | fixed 42 `CaseSpec`s và 25-root/32-variant catalog |
| `data/ledger.py` | ledger validation, prefix reduction, source precedence/conflict |
| `evaluation/formulas.py` | exact formulas |
| `evaluation/oracle.py` | observable-case evaluation used during generation |
| `data/build.py` | G0–G5 materialization và draft manifest |
| `data/validation.py` | V/SM/EX/AUX/CF checks, semantic inventory, comparison |
| `data/cli.py` | `inventory`, `build`, `validate`, `compare-logical`, `freeze` |

`retrieval/`, `adapters/` và `agent/` hiện chỉ là package skeletons. Không mô tả
chúng như implemented baseline.

### 7.3. CLI

```powershell
uv run python -m gsm_memory.data.cli --help
uv run python -m gsm_memory.data.cli inventory --config configs/datasets/gsm-dev-core-0.2.1.json
uv run python -m gsm_memory.data.cli build --config configs/datasets/gsm-dev-core-0.2.1.json --output <empty-candidate>
uv run python -m gsm_memory.data.cli validate --candidate <candidate>
uv run python -m gsm_memory.data.cli compare-logical --candidate-a <A> --candidate-b <B> --report <report.json>
uv run python -m gsm_memory.data.cli freeze --candidate <A> --comparison <comparison.json> --target <new-release-path> --report <certificate.json>
```

Build từ chối output non-empty. Freeze từ chối target đã tồn tại và kiểm
comparison/validation trước promotion.

### 7.4. Tests hiện có

```text
tests/unit/data/test_primitives.py
tests/unit/data/test_ledger.py
tests/conformance/data/test_examples.py
tests/integration/data/test_release.py
```

Lần chạy lại khi soạn bàn giao:

```powershell
$env:OPENAI_API_KEY=$null
$env:GEMINI_API_KEY=$null
$env:ANTHROPIC_API_KEY=$null
uv run pytest -q tests/unit/data tests/conformance/data tests/integration/data
```

Kết quả: exit 0, `9 passed in 5.83s`.

Frozen byte inventory cũng được kiểm read-only bằng `Get-FileHash -Algorithm
SHA256`: 635/635 files khớp manifest; manifest hash và comparison-report hash
khớp các giá trị ở §5.1. Không chạy `validate` trực tiếp lên frozen target vì
implementation hiện ghi lại `private/eval/validation.json`.

---

## 8. Audit kỹ thuật: điều đã tốt và technical debt cần biết

### 8.1. Phần đã có nền tảng tốt

- Pinned archive và checkout bytes được kiểm; 224 + aggregate contract rõ.
- UUIDv5 namespace và exact rational primitives tồn tại.
- Ledger có authorization, strict replay order, replace/retract và equal-rank
  conflict tests.
- Build offline, deterministic, tạo đủ public/private tree và two-profile layout.
- Snapshot branches, historical cutoffs, freeze overwrite guard và logical
  comparison đã được implement.
- Regression release 0.2.1 xử lý public RuntimeQuery leakage thay vì sửa release
  frozen cũ.

### 8.2. Validator chưa phải independent semantic audit đầy đủ

Các điểm cần agent tiếp theo biết trước khi dựa vào DFG report:

1. `AUX_INCIDENT` trong `validate_release` hiện dùng literal `True`, không dựng
   và kiểm open→resolved→reopen fixture.
2. Một counterfactual check là literal `True`; check replay còn lại so một digest
   với chính nó.
3. EX01–EX25 hiện chủ yếu là một vector expected/actual dựa trên formula helpers,
   chưa port đầy đủ source/identity/time/isolation premises của từng fixture.
4. Một số V checks chỉ kiểm count/shape hoặc presence, chưa chứng minh toàn bộ
   semantics mà tên check đại diện.
5. `validate_release` ghi lại `private/eval/validation.json`; vì vậy không chạy
   trực tiếp lên frozen target nếu mục tiêu là read-only verification.

Hệ quả: external report “56/56 pass” đúng với bộ checks đã implement, nhưng không
đồng nghĩa mọi sub-assertion trong spec §8 đã được chứng minh độc lập.

### 8.3. Oracle/gold generation còn task-specific

`evaluation/oracle.py` không đọc expected answer table trực tiếp, nhưng vẫn có
nhiều nhánh theo task/foundation và query text; nhánh ambiguous còn nhìn
`spec.status`. Một số T07/foundation outputs được hard-code theo alias/cutoff.

`build.py` cũng tạo proof roles theo task và missing-role table. Đây là chấp nhận
được như pilot implementation shortcut, nhưng chưa đạt lý tưởng “general reducer
+ proof evaluator suy hoàn toàn từ canonical public evidence”. Trước khi mở rộng
dataset hoặc claim strong independent gold, nên:

- tách rule evaluation khỏi case aliases/text;
- encode task bindings/operands đủ cấu trúc;
- suy expected status/value từ ledger + bindings + exact formulas;
- giữ một fixed expectation suite thật sự độc lập;
- mutation/counterfactual tests phải thay input và quan sát output thay đổi.

### 8.4. Mode B narratives còn tối giản

Text observation hiện mang metadata/assertions và câu mô tả tổng quát kiểu “bản
ghi công bố N assertions”. Nó bảo toàn structured payload trong JSONL nhưng chưa
phải naturalistic Vietnamese observation corpus. Một text-to-KG experiment dùng
Mode B phải nói rõ giới hạn này; nếu cải thiện narratives, cần version dataset và
revalidate parity/no-added-facts/no-omitted-gold-critical-facts.

### 8.5. Package fidelity cần audit sâu hơn trước BRG

Một vài semantic models/files trong spec được materialize ở dạng tối giản, ví dụ
task bindings, policy rules, snapshot manifests và narrative locators. Trước khi
viết adapter, kiểm exact fields mà adapter thực sự cần và không tự lấy dữ liệu
từ private side để bù thiếu public metadata.

### 8.6. Git state tại thời điểm bàn giao

Trước khi tạo file này, branch là `main...origin/main` và đã có một user-created
untracked file:

```text
reports/data_freeze/gsm-dev-core-0.2.1-bao-cao-dataset-va-de-xuat-evaluation.vi.md
```

File đó được giữ nguyên. Tài liệu hiện tại là file mới riêng, không ghi đè công
việc của người dùng.

---

## 9. Checkpoint và định nghĩa “xong”

### 9.1. Đã hoàn thành theo artifact hiện tại

| Mốc | Trạng thái |
| --- | --- |
| DATA_G0 sources/contracts | complete theo pipeline hiện tại |
| DATA_G1 world | complete |
| DATA_G2 ledger/branches | complete |
| DATA_G3 cases/gold | complete, nhưng có audit debt ở §8 |
| DATA_G4 packages | complete |
| DATA_G5 queries | complete |
| DATA_G6 validation | complete theo validator hiện tại |
| Clean build A/B | complete |
| Logical comparison | pass, 635 files |
| Freeze `0.2.1` | complete |

### 9.2. Chưa hoàn thành

| Mốc | Trạng thái |
| --- | --- |
| Independent strengthening audit cho DFG semantics | pending/khuyến nghị |
| Document chunker/index/BM25/dense/RRF/reranker | not implemented |
| Graphiti Mode A writer | not implemented |
| Graphiti Mode B ingestion audit | historical tests có, release integration chưa làm |
| ProjectionLinks/ingestion receipts | not run |
| KG/document/hybrid retrieval adapters | not implemented |
| Candidate/selected context traces | not implemented |
| Reader/agent run trên 42 queries | not run |
| L1–L4 metrics, latency, throughput, cost | not run |
| BRG01–BRG05 | not run |
| Locked held-out test release | không tồn tại |

### 9.3. DFG không phải BRG

DFG chứng nhận source-level dataset/package/gold theo validator. BRG cần thêm:

- frozen release + pinned run config/profile/environment;
- actual document loader và Graphiti adapters/search;
- ProjectionLinks và construction conformance;
- full 42-query path trên `retrieval_full`;
- candidate/selected/reasoning separation;
- ingestion/search latency và cost instrumentation.

Không đổi gold khi baseline thất bại. Construction failure là experimental
result, không phải lý do “sửa” canonical dataset cho backend pass.

---

## 10. Hướng tiếp cận tiếp theo được khuyến nghị

### Phase A — Gia cố assurance trước BRG

Mục tiêu: giữ release frozen, nhưng bổ sung audit/tests độc lập để biết chính xác
độ tin cậy.

1. Không mutate `data/gsm-dev-core-0.2.1/`; chạy mọi audit trên copy/candidate
   hoặc read-only verifier.
2. Thay literal/tautological AUX/CF checks bằng executable fixtures đúng spec.
3. Port EX01–EX25 với full premises, source/time/isolation, không chỉ expected
   vector.
4. Thêm byte-inventory verifier read-only cho frozen manifest/certificate.
5. Kiểm proof minimality bằng cách bỏ từng atom thiết yếu; kiểm alternative proof.
6. Kiểm snapshot contents thật sự là prefix/allowlist, không chỉ count/timestamp.
7. Nếu audit tìm data/gold bug: tạo release mới; nếu chỉ tăng test assurance mà
   bytes dataset không đổi, ghi external audit report/version riêng.

### Phase B — BRG micro-path trên `debug_core`

Mục tiêu: một đường thật end-to-end nhỏ, không claim full baseline.

1. Pin run manifest, environment, profile hash và one snapshot.
2. Build document chunks giữ raw span/source/edition mapping.
3. Implement Mode A projection đầu tiên từ public structured snapshot.
4. Tạo actual ProjectionLinks sau khi chunks/nodes/edges tồn tại.
5. Chạy vài cases đại diện: Q1 document, historical Q2/Q6, hybrid Q4/Q5 và Q7.
6. Log raw candidates, eligibility filters, selected bundle, tokens, answer,
   citations, latency/calls/errors.
7. Chứng minh runtime không đọc private directories/full archive/other profile.

### Phase C — Main baselines trên `retrieval_full`

Document chain:

```text
BM25
dense multilingual
BM25 + dense via RRF
RRF + bounded reranker
```

KG chain:

```text
entity resolver
raw graph search
+ scope/valid/known eligibility
+ bounded typed expansion
```

Hybrid ablation:

```text
document-only
KG-only
hybrid candidate union
hybrid + role-aware evidence selection
```

Giữ reader/context budget cố định khi so retrieval. Giữ construction mode cố
định cho main comparison; A/B là experiment riêng.

### Phase D — Reader và error analysis

Cho cùng reader chạy ba conditions:

1. no context;
2. retrieved/selected context;
3. oracle public evidence context do evaluator dựng.

Báo:

- `Complete(C,q)` và `Complete(E,q)`;
- expected-status và typed-value accuracy;
- citations/groundedness/unsupported claims;
- fault slices theo seven branches;
- API/backend errors và unsupported cases trong denominator riêng.

### Phase E — Chỉ sau baseline mới chọn proposed improvement

Decision rule theo observed bottleneck:

| Finding | Hướng hợp lý |
| --- | --- |
| Clause không vào candidates | document retrieval improvement |
| Graph đúng nhưng bridge search hụt | bounded/structured graph retrieval |
| Mode B sai identity/time/lineage | temporal construction improvement |
| Candidate đủ nhưng context mất role | evidence selection/packing |
| Context dài do event detail | lineage-preserving profile compression |
| Graphiti contract gap có evidence | đánh giá alternative backend cùng frozen contract |

Không triển khai A-MEM/HippoRAG/KG²RAG/GraphRAG toàn stack chỉ vì literature
khuyến khích; cần một failure mechanism và metric có thể bác bỏ hypothesis.

---

## 11. Evaluation protocol cho run mới

### 11.1. L1–L4

| Layer | Metrics ưu tiên |
| --- | --- |
| L1 Retrieval | confirmed-support Recall@K, complete-proof rate, proof coverage, bridge coverage, source/version correctness, judgment coverage |
| L2 Entity/time | entity accuracy, wrong-entity, valid-time, known-time leak, wrong-window, stale, source precedence/conflict/retraction |
| L3 Context | selected complete-proof, role/provenance coverage, judged precision, redundancy, token budget, selection loss |
| L4 Answer | status accuracy, typed/numeric exact match, groundedness, citations, unsupported inference, abstention precision/recall |

### 11.2. Proof metrics

Với answerable query `q`, `Pq` là tập minimal sufficient proofs, `M(S)` là atoms
được evidence set `S` hỗ trợ đúng entity/time/source:

```text
Complete(S,q) = 1 nếu tồn tại P trong Pq sao cho P ⊆ M(S)
Coverage(S,q) = max_P |P ∩ M(S)| / |P|
```

Negative cases dùng status diagnostics, không dùng empty proof.

### 11.3. Run manifest bắt buộc

Pin ít nhất:

```text
dataset version + manifest hash
corpus profile ID/version/hash
snapshot ID, scope, known cutoff
construction mode và graph input hash
chunker/projection/index identity
retriever/reranker configs, top-k
context budget và tokenizer
reader model/prompt/version
qrels/proof/equivalence version
random seeds
package/backend versions
hardware/concurrency
```

### 11.4. Reporting discipline

- Luôn hiện planned=42, attempted, completed, scored, blocked/error.
- Báo task/track/status/fault slice breakdown.
- Không tính CI/p-value giả định 42 cases độc lập.
- Không gọi dev-tuned score là final system performance.
- Không dùng `debug_core` cho headline.
- Không báo precision/nDCG nếu judgments không đủ.
- Không trộn construction change với retrieval change trong cùng ablation.

---

## 12. Những việc tuyệt đối không làm

- Không ghi đè release frozen.
- Không crawl lại website hoặc thay pinned source bằng trang mới cùng URL.
- Không deduplicate theo title/text gần giống.
- Không bịa real policy supersession/effective interval.
- Không thêm business predicates/domains ngoài frozen schema.
- Không dùng hidden world để resolve public missing/conflict.
- Không concatenate eight branches.
- Không dùng latest timestamp làm conflict resolver.
- Không dùng float cho threshold/formulas.
- Không coi missing là false/zero/undefined.
- Không coi unreviewed document là irrelevant.
- Không export task IDs, Cxxx/D_A/Wxx aliases, fault labels, expected status hoặc
  proof hints sang public RuntimeQuery/index metadata.
- Không tạo fake chunks, Graphiti UUIDs, ProjectionLinks, receipts hoặc metrics.
- Không gọi DFG là Graphiti/retrieval/agent success.
- Không đổi gold vì baseline/proposed system không đạt.

---

## 13. File map nhanh

### Contracts và rationale

```text
AGENTS.md
docs/01_problem_and_evaluation.md
docs/02_synthetic_schema_and_data_design.md
docs/03_dataset_and_graphiti_baseline_plan.md
docs/04_benchmark_to_dataset_mapping.md
docs/05_dataset_release_spec.md
docs/research/gsm_retrieval_research.md
```

### Implementation

```text
src/gsm_memory/data/
src/gsm_memory/evaluation/
configs/datasets/gsm-dev-core-0.2.1.json
tests/unit/data/
tests/conformance/data/
tests/integration/data/
```

### Current release/evidence

```text
data/gsm-dev-core-0.2.1/
artifacts/data_builds/gsm-dev-core-0.2.1-clean-A/
artifacts/data_builds/gsm-dev-core-0.2.1-clean-B/
reports/data_freeze/gsm-dev-core-0.2.1-DFG.md
reports/data_freeze/gsm-dev-core-0.2.1-freeze-certificate.json
reports/data_freeze/gsm-dev-core-0.2.1-logical-comparison.json
reports/data_freeze/gsm-dev-core-0.2.1-bao-cao-dataset-va-de-xuat-evaluation.vi.md
reports/data_freeze/gsm-dev-core-0.2-deprecation.json
```

### Historical Graphiti conformance material

```text
tests/conformance/graphiti/
tests/support/graphiti_temporal_test_utils.py
runs/conformance/
```

Đọc kết quả lịch sử cùng exact config/run status; quota-blocked không phải
capability verdict và T2 failure của một Mode B configuration không chứng minh
mọi Graphiti mode đều sai.

---

## 14. Checklist tiếp quản cho agent mới

Trước khi code:

1. Đọc `AGENTS.md`, tài liệu 02, 05, 01 và file bàn giao này.
2. Chạy `git status`; bảo toàn file untracked/user changes.
3. Xác định task thuộc DFG assurance, BRG, baseline hay future test release.
4. Không sửa frozen data nếu task không yêu cầu version mới.
5. Kiểm public/private và snapshot/profile boundary của mọi loader.
6. Pin config/hashes trước measured run.
7. Viết test cho semantic component trước integration.
8. Khi báo kết quả, phân biệt `pass`, `fail`, `not_run`, `blocked`, `unsupported`.

Nếu nhiệm vụ là BRG, điều kiện tối thiểu trước khi tuyên bố hoàn thành:

```text
BRG01 pinned run/environment/profile
BRG02 actual document + Graphiti conformance and ProjectionLinks
BRG03 42-query retrieval_full execution
BRG04 candidate/selected/reasoning attribution
BRG05 latency/cost/receipt instrumentation
```

Nếu chỉ chạy một micro-path hoặc một profile nhỏ, báo đúng là partial/debug run.

---

## 15. Kết luận bàn giao

Project đã đi qua bước quan trọng nhất của data design: source corpus được pin,
observable-vs-private truth được tách, bitemporal ledger và fault branches được
định nghĩa, 42 dev cases có source-level gold/proofs, package 0.2.1 đã frozen và
có reproducibility artifacts.

Checkpoint tiếp theo không phải mở rộng schema hay chạy ngay một framework memory
mới. Công việc đúng thứ tự là:

1. gia cố independent validation ở các điểm còn shortcut;
2. dựng BRG micro-path thật với source→projection links;
3. chạy document/KG/hybrid baselines trên cùng frozen contract;
4. đo candidate, selection và reasoning riêng;
5. chọn tối đa một hướng cải tiến dựa trên lỗi đã quan sát;
6. tạo một future multi-world locked-test release trước khi đưa ra claim cuối.

Giữ nguyên nguyên tắc xuyên suốt: **đúng entity, đúng thời gian, đúng source và
đủ proof quan trọng hơn một câu trả lời nghe hợp lý hoặc một score tổng hợp cao.**
