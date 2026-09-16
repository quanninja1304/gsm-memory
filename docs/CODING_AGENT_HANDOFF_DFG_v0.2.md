# Prompt bàn giao coding agent — GSM dataset đến DFG

Bạn là coding agent làm việc trực tiếp trong repository `memory/`. Hãy triển khai dataset generator, observable reducer, source-level gold/proof evaluator, public packaging và offline validation cho `gsm-dev-core-0.2`, rồi chạy hai clean builds và kết luận Data Freeze Gate bằng evidence thực.

Đây là yêu cầu triển khai toàn tuyến đến DFG, không chỉ lập kế hoạch, tạo skeleton hoặc hoàn thành G0. Tiếp tục qua các milestones khi đủ đầu vào; không xin xác nhận lại sau từng stage. Dừng mở rộng phạm vi khi đã hoàn tất DFG và bàn giao kết quả; Graphiti ingestion/search, retrieval baseline và agent run thuộc bước BRG sau này.

## 1. Nguồn chuẩn và cách bắt đầu

Trước khi sửa code:

1. Đọc `AGENTS.md` hoặc local instructions áp dụng nếu có, `README.md`, `docs/README.md`, các README liên quan trong `src/`, `data/`, `configs/`, `scripts/`, `tests/`, `external/`.
2. Inspect repo thực tế: files, Git state nếu có, dependency manifests/locks, Python version, code và tests đã tồn tại. Cây thư mục được cung cấp là mô tả, không là bằng chứng các module đã được implement. Dùng `rg`/`rg --files` cho tìm kiếm; đọc actual files trước khi chọn imports/APIs.
3. Đọc năm contracts bên dưới; ưu tiên exact task/dataset definitions của 02/05, không dùng bản draft hoặc planning notes pre-audit để mở scope.
4. Ghi ngắn gọn version/input findings và implementation map, sau đó bắt đầu code. Không biến preflight thành một vòng nghiên cứu benchmark mới.

| File dưới `docs/` | Version áp dụng / trách nhiệm |
| --- | --- |
| `01_problem_and_evaluation.md` | Contract v0.1.1: request/evidence/evaluation semantics, incomplete judgments |
| `02_synthetic_schema_and_data_design.md` | Business schema 1.1, document revision 1.1.1: types, predicates, clocks, bindings, formulas, proofs, EX01–EX25, I01–I28 |
| `03_dataset_and_graphiti_baseline_plan.md` | Planning revision v0.1.1: repo-grounding/logging guidance; legacy proposals không override 02/05 |
| `04_benchmark_to_dataset_mapping.md` | Design note v0.3: methodology, dev/test và interpretation limits |
| `05_dataset_release_spec.md` | Spec v0.2.0: exact files, recipes, closed sidecars, profiles, 42 cases, checks, DFG |

Gói bàn giao kèm thư mục `docs/` và `HANDOFF_MANIFEST.sha256`. Đối chiếu hashes của các bản được giao với repo. Nếu repo còn contract cũ và bản đã duyệt có trong gói, đồng bộ có diff rõ ràng, giữ các thay đổi không liên quan. Nếu có xung đột semantic hoặc thiếu bản 05 v0.2.0, ghi blocker cụ thể; không tự đoán lại contract hoặc dùng skeleton 0.1 thay thế. Không tự sửa business semantics, recipe, thresholds hoặc expected answers để tránh implementation failure.

Phiên bản bắt buộc: `schema_version=1.1`, `release_spec_version=0.2.0`, `dataset_version=gsm-dev-core-0.2`, seed=42. Namespace UUIDv5 và stable-key algorithm theo 05 §3.1/§7. Giữ imported snapshot IDs/hashes của sáu nguồn đã audit.

## 2. Repo và phạm vi chỉnh sửa

Repo có các khu vực sau; kiểm thực tế trước khi dùng:

| Khu vực | Cách sử dụng cho nhiệm vụ này |
| --- | --- |
| `external/policy_green_sm_corpus/` | Checkout nguồn, có nested Git; read-only trong nhiệm vụ này |
| `data/raw/archives/policy_green_sm_source.zip` | Archive nguồn được pin, read-only |
| `data/gsm-dev-core-0.1/` | Skeleton/release cũ; không ghi đè hoặc dùng làm output mới |
| `data/gsm-dev-core-0.2/` | Output cuối theo inventory 05 §6.1, chỉ promote sau checks |
| `src/gsm_memory/data/` | Typed data models, IDs/time/rationals/serialization, source inventory, world/ledger/reducer, cases, snapshots, render, validation, build orchestration |
| `src/gsm_memory/evaluation/` | Pure formula/proof/support matching cần cho offline gold và validation; reuse modules nếu đã có |
| `configs/datasets/` | Dataset config/recipe/pins; đề xuất `gsm-dev-core-0.2.yaml` nếu phù hợp conventions |
| `scripts/data/` | Wrappers mỏng nếu cần; tránh lặp business logic với package |
| `tests/unit/`, `tests/conformance/`, `tests/integration/` | Thêm data-only suites trong namespace riêng; không phá Graphiti suites hiện có |
| `artifacts/data_builds/` | Staging directories A/B sạch, ngoài release; đường dẫn đề xuất |
| `reports/data_freeze/` | Build/check/comparison evidence và final DFG report; đường dẫn đề xuất |

Không tạo một general-purpose `core` framework hoặc domain ngoài 02. Chọn cấu trúc file vừa đủ theo repo; không tạo hàng loạt empty modules để coi milestone đã xong. Có thể thêm `data/contracts.py`, `ids.py`, `time.py`, `serialization.py`, `corpus.py`, `world.py`, `ledger.py`, `reducer.py`, `cases.py`, `snapshots.py`, `render.py`, `validation.py`, `cli.py` khi thực sự cần; đây là mapping gợi ý, không yêu cầu một file cho mỗi tên.

Reuse dependency manifest/lock hiện có. Nếu chưa có, thiết lập packaging/data dependencies tối thiểu và pin phiên bản; không thay backend hoặc nâng Graphiti để làm data stage chạy. Code data/evaluation pure không import/init Graphiti, LLM hoặc API clients qua package-level side effects. `.venv`, user changes, nested Git và historical conformance outputs phải được bảo toàn. Không dùng credentials hoặc gọi website để tải lại policy.

## 3. Dữ liệu và invariants không được đổi

- Một W0, 8 drivers, 80 distinct terminal trips; trip events khác observation/source-record count.
- 25 scenario roots, 32 variants, 8 ledgers gồm L0 + 7 alternate branches; 42 semantic cases và một direct rendering/case; dev=42, test=0.
- T01–T07/B01–B07, AM1–AM4 và operational vocabulary của 02; không mở DEFER tasks, offers/sessions/payroll/raw revenue/raw rating hoặc verdict edges.
- `debug_core`: sáu real snapshots P154/P151/P05/P23/P172/P26. `retrieval_full`: đủ 224 bài riêng, là profile baseline mặc định khi runtime được triển khai.
- Audited subset=6; primary-gold source subset=4: chỉ reviewed TEXT spans của P154/P151/P05/P23. P172/P26 là audited distractors; 218 bài thêm không có executable bindings hoặc primary gold trong release này.
- Cùng 3 synthetic version documents và 12 definitions. Không index/count file tổng hợp như nguồn độc lập; raw và normalized là hai representations của cùng snapshot.
- Archive SHA-256 phải là `cfe9e4555dbedf81396004c7a7d0ace52dcbb1deb758110c4aded3b6741ba9c9`. Kiểm 224 members bằng actual bytes và đối chiếu sáu source hashes/locators trong 02/05; không dùng title để gộp near duplicates.
- Normalization CRLF→LF, UTF-8, source offsets theo Unicode code points, `[start,end)`, lines từ 1; không sửa policy text/threshold hoặc approve OCR ngầm. `captured_at`/OCR quality chưa có chứng cứ thì unknown theo schema.
- 224 source snapshots có benchmark availability `2026-09-16T00:00:00.000000Z` qua `ARTIFACT_PUBLICATION`; không phải normative policy effective time. Bổ sung publication records hợp lệ trước khi cấp commit_seq; không giả `POLICY_PUBLICATION` cho real snapshots.
- T01–T07 vẫn chỉ định edition/snapshot. Không bỏ reference để làm retrieval khó hơn; không thêm document-discovery tasks vào 42 cases.

## 4. Tám milestones và tiêu chí hoàn thành

G0…G6 ở đây là **data pipeline trong 05**. Khi ghi progress có thể gọi DATA_G0…DATA_G6 để phân biệt với Graphiti environment gate trong 03. Mỗi stage phải có checks chạy ngay khi component xuất hiện; G6 là integration suite/final audit, không phải lúc bắt đầu viết tests.

### Milestone 1 — Repo grounding, contracts/primitives/CLI và DATA_G0

Implement typed logical shapes đúng 02/05, đặc biệt closed ScenarioManifest và mutation payloads; required khác nullable, unknown keys phải bị reject ở closed types. Serialization registry phải mô tả logical types/FKs của files, không stringify nested Parquet payloads thành opaque strings.

Implement stable IDs, exact rationals, timestamp/boundary kinds, deterministic canonical JSON và basic file/hash helpers. Không dùng Python `hash()`, filesystem enumeration order, mtime hoặc wall clock để quyết định semantic IDs/data.

CLI phải thực sự chạy được `--help` và inventory/source-validation command, không chỉ print placeholder. G0 đọc archive, xuất source inventory/locators và xác định hai profile member sets; pin definitions/audited bindings. Profile manifest có catalog hash/publication refs phụ thuộc stage sau thì giữ internal plan chưa final; hoàn thiện sau G2/G4, không ghi hash/record refs giả hoặc ghi FROZEN sớm.

Acceptance: version/path đúng; corpus inventory=224 real sources; aggregate bị loại; hashes/reviewed locators đúng; profile members=6/224; dữ liệu foundation import/test được không cần provider credentials hoặc Graphiti server.

### Milestone 2 — DATA_G1: world generator

Sinh đúng recipe 05 §4: entities, names/aliases, states, terminal trips, reports và synthetic controls. Phân biệt private world truth với public observation plan; reports không được suy giả từ 80 trips nếu contract không định nghĩa lineage đó.

Acceptance: 8 drivers/80 unique terminal trips, expected world cardinalities và fixed values đúng; repeat cùng keys/config sinh cùng IDs/logical content. Kiểm typed shapes, FK/domain constraints và exact rational primitives ở stage này.

### Milestone 3 — DATA_G2: ledger, reducer và branches

Implement immutable SourceRecord và pure reducer đọc đúng visible prefix/scope. Bảo toàn assert/replace/retract, target authorization, source precedence, valid/known clocks, inclusive/exclusive boundaries, unknown/not-applicable/unbounded distinctions và atomic partial-interval replacement. `known_to` phải suy từ prefix đang đọc, không copy future closing boundary từ full timeline.

Tạo L0 và đúng bảy alternate timelines của 05: L_NO_OPDAY, L_WRONG_DRIVER, L_CONFLICT, L_RETRACT, L_WRONG_WINDOW, L_NO_BRIDGE, L_NO_COVERAGE. Branch chỉ thay record sets/dependency closure; không mutate shared payloads, merge branches hoặc lấy hidden truth để repair missing data. Source publication plan cho 224 snapshots dùng chung với cùng IDs/payloads giữa branches khi áp dụng; chọn corpus profile không tạo branch mới.

Cấp record IDs trước; tạo union mọi planned records của L0/branches; sort theo `(known_at,source_id,record_id)` rồi cấp commit_seq một lần. Branch/prefix giữ nguyên seq kể cả gaps. Sort order không giải quyết equal-rank conflict.

Acceptance: ledger identity/temporal/precedence/branch checks pass. Kiểm exact known boundary, late/future cases, partial replacement, retraction không thành false/0, equal-rank conflict không latest-wins, unauthorized correction reject. Trip identity/revisions/conflicts phải resolve trước window filtering. Mask cập nhật dependencies/coverage và không để artifact thay thế tiết lộ fact bị che.

### Milestone 4 — DATA_G3: scenarios, semantic cases và source gold

Sinh đúng 25 roots/32 variants/42 cases của 05 §§3/5. Preallocate canonical case/query/snapshot IDs từ stable keys/cutoffs; một direct rendering/case. Điều này cho phép source-level gold tham chiếu query/snapshot identities trước G4/G5; không chứng nhận files đã tồn tại. Stage-local shape/ownership/branch checks phải pass; cross-file FK closure tới outputs chưa sinh được ghi là pending đến G4/G5/G6.

Implement formula/task evaluator và SupportAtom/EvidenceProof/GoldSupportLink theo 02. Gold được tính từ visible evidence + approved bindings/conventions; không lấy hidden world lấp thiếu hoặc chọn nguồn thắng conflict. Không viết `if case_id == Cxxx: return expected_answer` làm oracle. Expected tables/hand arithmetic của spec dùng làm independent tests, không là production output lookup.

Giữ exact arithmetic và semantics: operating-day false có thể short-circuit T02; doanh số 280000 và trên ngưỡng không âm; auto-accept dùng strict AR<1/2; rating dùng strict >97/20; T05 chỉ rating condition, T07 chỉ notice scope. Thiếu evidence, explicit undefined, zero, false và unresolved conflict khác nhau. Formula details/proof roles theo 02/05, không suy raw metric computation hoặc quyền lợi production.

Proofs phải đủ và minimal theo semantics, hỗ trợ alternatives/short-circuit hợp lệ; source/time/role constraints là bắt buộc. Negative cases có missing/conflict/identity diagnostics, không dùng empty proof để nhận sufficiency=1. GoldSupportLink trỏ canonical source/span, không giả ProjectionLink/chunk/Graphiti IDs.

Acceptance: expected results của cả 42 cases khớp independently checked expectations; record/atom/proof/source lineage đúng; stage-local SM checks pass; query/rendering/snapshot planned refs có ownership rõ.

### Milestone 5 — DATA_G4: canonical packages và Mode A/B inputs

Materialize public/private output đúng inventory 05 §6.1, source visibility và actual source-level FK. Mode A manifest trỏ structured visible inputs; Mode B manifest trỏ deterministic narratives bảo toàn cùng source IDs, facts, valid/known times và correction targets. Không gọi add_episode, model extraction, embeddings hoặc graph writer.

Snapshot key, ID và branch/cutoff theo 05 §6.2. Cùng canonical package có thể dùng cho hai profiles; effective document access là snapshot visible refs ∩ active profile ∩ scope. Full root catalogs/profile manifests là setup/archive inputs, không là runtime mount được dùng để vượt cutoff hoặc đọc profile khác. Không để leaked future IDs/headers, known_to, aliases, coverage hoặc artifacts lọt vào visible view.

Giữ corpus_roles/task bindings/private gold ngoài public views. Operational graph input giữ nguyên giữa hai profiles; không extract 218 bài thêm thành graph rules/hints. Document index/cache identity tương lai cần profile/hash theo spec, nhưng chưa tạo index/cache runtime ở DFG.

Acceptance: source packages đúng scope/cutoff; A/B source information parity được kiểm offline; same-profile/source resolver guards có tests. Manifest phụ thuộc RuntimeQuery files/hashes chưa được finalize cho đến G5. Không tạo graph UUIDs, chunks, receipts hoặc empty run artifacts để giả completed runtime.

### Milestone 6 — DATA_G5: deterministic RuntimeQuery rendering

Render đúng 42 direct templates của 05 §5, IDs đã cấp, Vietnamese text và public application context hợp lệ. Không đưa private Cxxx/task/family/fault/status/answer/proof labels, operand values cần retrieve hoặc binding AST vào RuntimeQuery.

Đây là static templates theo 05 §6.3: runtime request_id, budgets, deadline, retrieval_config/model pins thuộc run assembler sau này. Không bịa runtime values để làm data validation pass; phân biệt static template validation với full request validation. `test.jsonl` đúng 0 bytes; không copy dev sang test, không sinh paraphrases hoặc nhân cases theo profiles.

Acceptance: 42 dev/0 test, template hashes ổn định, all case/rendering ownership đúng, no gold leakage; materialize các refs/FKs được lên kế hoạch ở G3 và final source/query catalogs cần thiết.

### Milestone 7 — DATA_G6: validation và package closure

Chạy **V01–V10**, **SM01–SM08**, đúng **EX01–EX25**, toàn bộ **AUX_IDENTITY/AUX_TIME/AUX_EVENT/AUX_INCIDENT/AUX_REVISION/AUX_POLICY/AUX_ARTIFACT/AUX_CONTEXT/AUX_ACCESS**, và counterfactual checks của 05 §8.

EX fixtures giữ dates/premises/isolation riêng của 02 §17.2, không ép thành byte copies của C001–C042 hoặc trộn vào root public corpus. Expected values/checks phải độc lập với implementation under test; hai bên dùng chung một helper sai không đủ chứng minh đúng. Counterfactual đổi fact quyết định phải đổi gold; đổi distractor không liên quan giữ gold; thêm future record giữ historical answer; replay cùng prefix giữ accepted view. World perturbation test dùng world khác, không mutate W0 đã đóng gói.

V09 chỉ kiểm structured/narrative inputs; actual I14 Graphiti fidelity ở BRG. V10 kiểm case/proof compatibility trong hai active views, không mở primary-gold sources và không dùng private source-role filter. `relevance_judgments.jsonl` có thể rỗng; protocol phải ghi unjudged đúng, không generate random/implicit-negative qrels. Missing full Precision/nDCG judgments không tự làm DFG fail.

Kiểm tất cả required files/FKs, arrays uniqueness/sorting, branch registry, allowlists, typed serialization, actual hashes và schema registry; manifests phụ thuộc G5 được chốt tại đây. Mọi JSONL required phải tồn tại, kể cả empty hợp lệ. Không tuyên bố release FROZEN hoặc DFG06 pass trước hai clean builds.

Acceptance: checks có `check_id`, scope, pass/fail/not_run, expected/actual, implicated IDs và artifact hashes. Required failure không chuyển thành warning. Ghi rõ phần final reproducibility chưa chạy; không dùng placeholders/PASS literals thay executable checks.

### Milestone 8 — Hai clean builds và DFG

1. Chạy build A và B từ pinned raw inputs trong hai output directories rỗng, bằng hai invocations độc lập. Cùng config/seed/code/dependency/serializer/Parquet pins. Không reuse generated ledger/gold/manifests từ build A; reuse immutable raw inputs và installed dependencies là hợp lệ.
2. Chạy complete offline validation trên từng candidate. Giữ outputs/report của từng attempt để đối chiếu; không ghi đè kết quả cũ nhằm che lỗi.
3. So input/config pins, file inventory và logical contents của tất cả semantic artifacts theo canonicalization contract: world, ledger/branches, sources/profiles, cases/gold/proofs, public packages, definitions, requests, evaluation protocol/labels. Không chỉ so counts hoặc chọn vài file đại diện.
4. Declared comparison schema phải có trước khi xem kết quả. Tables sort theo primary key, timestamps/rationals/canonical JSON theo spec. Path tuyệt đối của staging, physical timing và per-build diagnostics không được đi vào semantic data. Final validation/release certificate/report metadata có dependency order riêng; không bỏ semantic fields/files để làm hashes khớp.
5. Logical hash khác byte hash. Lưu actual byte hashes bảo vệ candidate cuối; không đòi Parquet bytes giống nhau giữa toolchains khác, nhưng nhiệm vụ này vẫn pin cùng toolchain cho hai builds. Nondeterminism của JSON/source/profile manifests phải được sửa, không che bằng cách bỏ khỏi inventory.
6. Finalization order: materialized semantic payloads → semantic inventories/logical comparison → final validation có DFG06 evidence → final manifest/state/file hashes → external release digest. Manifest không hash chính nó; validation/report không back-reference final manifest hash theo cách tạo vòng. Comparison report ngoài release có thể ghi path/digests của hai candidates; pin digest/ref cần thiết trong final report mà không tạo cycle.
7. Chỉ chuyển candidate thành `data/gsm-dev-core-0.2/` và state=FROZEN khi DFG01–DFG06 đều có evidence. Nếu output target đã tồn tại, kiểm state/identity; không ghi đè release đã frozen hoặc dữ liệu khác. Dùng staging/candidate mới và báo đúng conflict nếu không thể promote an toàn.

Acceptance: DFG report có từng DFG01–DFG06, command/execution status và evidence locators; cả hai build/check results; logical comparison; final release identity, inventory và external digest. Required fail/not_run hoặc blocker thì chưa FROZEN. Không suy BRG/production performance từ DFG.

## 5. CLI và kiểm thử cần bàn giao

Thiết kế CLI mỏng, chạy được trên môi trường repo thực tế. Nếu chưa có CLI conventions, có thể dùng `python -m gsm_memory.data.cli` với các subcommands `inventory`, `build`, `validate`, `compare-logical`, `freeze`. Đây là interface đề xuất cần implement và kiểm thật, không phải API đã tồn tại.

Các khả năng bắt buộc:

- Nhận config path và output path rõ ràng; build không âm thầm append/reuse output cũ.
- Validate một candidate đã có mà không regenerate/fix dữ liệu trong lúc chấm.
- Compare hai clean builds và xuất machine-readable diff theo file/logical key khi mismatch.
- Freeze chỉ nhận candidate/validation/comparison còn khớp hashes; không chỉ đổi string state thành FROZEN.
- Failure hoặc incomplete required checks phải có nonzero exit code và reason; subprocess exceptions không thành empty successful output.
- README ghi exact commands đã chạy, interpreter/dependencies, expected outputs và cách reproduce.

Nếu tạo data test namespaces mới, chỉ chạy các suites data cần thiết cho DFG và các import/integration checks liên quan. Không để việc chạy toàn bộ test collection kích hoạt Graphiti/Gemini provider calls. Existing Graphiti tests/results giữ nguyên; không skip data conformance để làm pytest xanh.

## 6. Cách làm việc và báo cáo

Tự quyết routine implementation choices phù hợp contract/repo; triển khai cho đến khi hoàn thành phạm vi. Gửi progress ngắn khi hoàn thành milestone hoặc phát hiện vấn đề semantic đáng kể. Nếu thiếu input/permission/dependency thật sự, ghi rõ affected stage và tiếp tục phần không bị chặn; không tuyên bố complete chỉ vì code compile.

Không mở research scope, crawl lại corpus, thêm task, đổi gold theo baseline output, gọi LLM để quyết truth hoặc dùng private oracle như runtime endpoint. Mọi source/config/code/toolchain pin phải có thật. Không bịa git commit, hashes, measured counts, DFG statuses hoặc test results.

Kết quả cuối cần có:

1. Danh sách thay đổi theo module/config/tests/docs và lý do.
2. Exact build/validate/compare/freeze commands đã chạy, exit status và evidence paths.
3. Actual inventory counts: 224 real sources, 6/224 profile members, 4 primary-gold sources, 8 drivers, 80 terminal trips, 25 roots, 32 variants, 8 ledgers, 42 dev/0 test; những record/atom/file counts khác lấy từ output thật.
4. V01–V10, SM01–SM08, EX01–EX25, chín AUX groups và counterfactual results; ghi fail/not_run/blocker đầy đủ.
5. Bảng DFG01–DFG06, comparison result và release state; final manifest/digest nếu đã FROZEN.
6. Giới hạn còn lại: chưa có Graphiti projection/ingestion/search, document baseline, full qrels hay BRG, trừ khi có nhiệm vụ riêng và evidence thực khác.

Không dừng ở bản đề xuất hoặc một bộ output mẫu không đủ 42 cases. Hoàn thành toàn bộ dataset offline và đưa ra DFG result có thể kiểm lại; nếu bị chặn thật sự, bàn giao phần đã làm cùng blocker chính xác thay vì fabricate PASS.

