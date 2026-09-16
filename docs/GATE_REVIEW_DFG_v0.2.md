# GSM — Review gates triển khai đến Data Freeze

Ngày: 16/09/2026. Căn cứ: bộ 01–05 đã sửa, đặc biệt 05 v0.2.0, và cây thư mục repo do người dùng cung cấp.

**Quyết định: APPROVE thiết kế với các cập nhật dưới đây.** Tám milestones phù hợp để triển khai dataset offline đến DFG. Đây là phê duyệt kế hoạch; chưa gate thực thi nào được chứng nhận PASS, và chưa kiểm tra mã nguồn/dependencies trong repo thực tế.

## 1. Những cập nhật cần áp dụng

1. **Dùng release 0.2.** Target là `data/gsm-dev-core-0.2/`, spec `gsm-dataset-release-spec-v0.2.0`, business schema vẫn 1.1. Cây repo đang ghi 0.1 là skeleton cũ; không build contract mới vào đường dẫn cũ hoặc ghi đè một release đã có dữ liệu.
2. **Gate 7 chạy V01–V10.** V10 kiểm profile/gold compatibility và unjudged handling; V09 chỉ kiểm input parity của Mode A/B, không thay actual Graphiti fidelity. SM01–SM08 cũng bắt buộc.
3. **Gate 1 có repo/version preflight.** Kiểm README, local instructions, dependency manifest/lock, code/test hiện có và raw archive. G0 ở kế hoạch này là source/corpus stage của 05; không nhầm với G0 environment/API audit trong kế hoạch Graphiti 03.
4. **Validation được viết/chạy theo từng stage.** G6 tổng hợp và kiểm tích hợp toàn bộ. Không để đến cuối mới kiểm ledger semantics, exact arithmetic hoặc profile visibility.
5. **Phân biệt định danh trước với artifact đã materialize.** G3 có thể cấp trước canonical case/query/snapshot IDs từ stable keys. FK tới files của G4/G5 chỉ được đóng sau khi các files tồn tại. Không có lý do tạo fake chunk IDs, Graphiti UUIDs hoặc ProjectionLink.
6. **Chốt manifest cuối sau G5.** G0 chốt source inventory/profile membership và normalization; manifests phụ thuộc publication refs/catalog hashes được hoàn thiện khi dependencies sẵn sàng. G4 đóng gói nguồn/visibility; manifest có RuntimeQuery hashes phải đợi G5. G6 kiểm lại toàn bộ FK/inventory/hashes trước DFG.
7. **Gate 8 có hai build độc lập và finalize rõ ràng.** Hai thư mục sạch, hai lần gọi generator từ pinned raw inputs; không copy output A sang B. So tất cả semantic outputs và input/config pins; kiểm actual byte hashes riêng. Chỉ sau DFG01–DFG06 mới đánh dấu FROZEN.

## 2. Tám gates đã sửa

Tên `DATA_G0`…`DATA_G6` dưới đây chỉ để tránh nhầm namespace khi bàn giao; tương ứng G0…G6 của 05, không đổi stage IDs trong normative spec.

| Milestone | Công việc | Điều kiện nghiệm thu tại milestone |
| --- | --- | --- |
| 1 — Preflight + foundation + DATA_G0 | Ground repo/contracts; dựng types/IDs/time/rational/serialization tối thiểu, CLI thật; inventory 224 bài, hai profiles, audited spans và definitions | Đúng phiên bản/đường dẫn; archive và sáu audited hashes khớp; 224 bài riêng, loại aggregate; profile membership 6/224; CLI inventory hoạt động, code data import được mà không cần Graphiti/API |
| 2 — DATA_G1 | World generator theo 05 §4 | Một W0; 8 drivers, 80 distinct terminal trips; typed states/reports/synthetic controls đúng recipe; deterministic IDs và exact values. Test shape/cardinality/formula primitives chạy ngay |
| 3 — DATA_G2 | Immutable ledger, observable reducer, L0 + 7 alternate branches | Đúng 8 ledgers; assert/replace/retract, authority, four clocks, atomic corrections, dependency masks/coverage đúng; commit_seq cấp trên union và giữ gaps; publications cho 224 snapshots; các temporal/revision tests pass |
| 4 — DATA_G3 | ScenarioManifest, 42 semantic cases, formulas, source gold/proof evaluator | 25 roots/32 variants/42 cases; SM checks có thể thực hiện ở stage này; gold từ visible evidence; exact formulas, minimal/alternative proofs, negative statuses đúng; IDs cho một rendering/case được cấp trước, chưa giả có rendered files |
| 5 — DATA_G4 | Canonical snapshots, public/private packaging, deterministic narratives, Mode A/B input manifests | Prefix/scope/profile views đúng; publications và source refs resolve; A/B cùng source information; graph inputs là manifests, chưa là graph/index. Cross-FK đến queries và final package hashes hoàn tất sau G5 |
| 6 — DATA_G5 | Deterministic RuntimeQuery renderer | 42 direct templates, dev=42/test=0; source/edition và conventions hợp lệ; không leak private task/status/proof; static templates không giả runtime budgets/deadline/model pins |
| 7 — DATA_G6 | Integration validation, EX01–EX25, AUX, SM01–SM08, V01–V10; final package closure | Kiểm mọi file/FK/profile/hash/schema; hand-checked fixtures độc lập với generator helpers; counterfactual/mutation checks; source-level GoldSupportLink đầy đủ. DFG06 còn chưa đạt nếu chưa có build ×2 |
| 8 — Rebuild + DFG | Build A/B sạch, compare logical hashes, finalize validation/manifest, promote candidate | Cùng pins; semantic contents khớp; tất cả required checks đã chạy; DFG01–DFG06 có evidence. Final byte inventory chính xác; manifest không hash chính nó; chỉ lúc này FROZEN |

Milestone có thể có references đã định danh nhưng chờ artifact ở stage sau. Điều đó phải được ghi rõ, không tính một required final check chưa chạy là PASS. DRAFT/VALIDATED không phải FROZEN.

## 3. Chỉnh tối thiểu vào layout repo

| Vị trí | Quyết định |
| --- | --- |
| `docs/01_...md` đến `docs/05_...md` | Đồng bộ bộ contract đã duyệt; 05 v0.2.0 là exact dataset contract; không dùng working draft làm chuẩn |
| `data/gsm-dev-core-0.1/` | Giữ nguyên để tránh ghi đè; không dùng làm output của release 0.2 |
| `data/gsm-dev-core-0.2/` | Root release mới theo exact inventory của 05 §6.1 |
| `public/corpus_profiles/debug_core/manifest.json` và `public/corpus_profiles/retrieval_full/manifest.json` dưới release root | Hai manifests có ID/version/hash và members theo 05 §6.2 |
| `private/eval/corpus_roles.jsonl`, `relevance_protocol.json`, `relevance_judgments.jsonl` dưới release root | Private evaluation files; judgments có thể rỗng, không tạo labels giả |
| `public/graph_inputs/mode_a/`, `mode_b/` | Sửa mô tả thành input manifests nếu README đang gọi là actual projections; không chứa Graphiti output UUIDs |
| `src/gsm_memory/data/`, `evaluation/` | Đặt data pipeline và pure proof/formula evaluation; không cần general-purpose core framework mới |
| `configs/datasets/`, `scripts/data/` | Pin dataset config; CLI hoặc wrappers mỏng theo conventions thực tế |
| `tests/unit/data/`, `tests/conformance/data/`, `tests/integration/data/` | Gợi ý vị trí tests offline; reuse conventions hiện có sau preflight |
| `artifacts/data_builds/`, `reports/data_freeze/` | Gợi ý staging A/B và evidence báo cáo build; nằm ngoài frozen release, không thay benchmark runs |

Không cần thay `adapters/`, `retrieval/`, `agent/`, Graphiti backend/config hoặc kết quả conformance cũ để đạt DFG. Metadata và source records có thể tăng vì thêm corpus; operational facts/revisions và 42 case semantics giữ nguyên.

## 4. Ranh giới DFG

DFG cần sources, world/ledger, source-level gold, snapshots, static requests và executable data checks. Nó không cần Graphiti server, embeddings, reranker, external LLM, actual chunks/indexes, ingestion receipts hoặc final retrieval qrels. Không tạo placeholders giả để làm đủ inventory runtime.

`retrieval_full` vẫn là baseline mặc định sau khi pipeline hoạt động; trong nhiệm vụ này chỉ tạo và kiểm input contract của profile. `debug_core` giúp micro conformance. Đạt DFG không đồng nghĩa đạt BRG, và 42 fixtures vẫn là dev.

## 5. Kiểm tra thiết kế dễ bị bỏ sót

- Source/date/hash khác với normative policy effectiveness. 224 snapshots có logical availability đã pin, không được backdate theo posted_date hoặc file mtime.
- Gold phải dựa visible evidence; hidden world không lấp missing evidence hoặc phân xử equal-rank conflict.
- Same-name drivers, distinct trip IDs và measurement windows không bị semantic dedup. Resolve event identity/revision/conflict trước window filtering.
- Thêm corpus profile không nhân 8 ledger branches, 42 cases hoặc independent samples. Snapshot ID dùng canonical key của 05; active profile nằm trong run/index configuration.
- Runtime source allowlist là snapshot visibility ∩ active profile ∩ scope. Full corpus metadata có thể ở setup/archive nhưng không lộ future headers/IDs cho agent.
- Source gold và semantic proofs có trước runtime projection. Data-stage IDs không chứng minh graph/index objects đã tồn tại.
- Kiểm đủ T/F/U/C, false/zero/undefined/missing/conflict, strict thresholds và proof short-circuit bằng expected values độc lập.
- Hai builds cùng một bug vẫn có hash giống nhau; rebuild test không thay EX/AUX, hand arithmetic hoặc mutation tests.
- Hash comparison không được bỏ qua semantic files khó ổn định. Logical comparison và final byte integrity là hai việc khác nhau.
- Không tạo hash cycle giữa validation, manifest và comparison report; chốt thứ tự finalize trước khi coding.

## 6. Cách bàn giao

Dùng `CODING_AGENT_HANDOFF_DFG_v0.2.md` cùng năm contracts đã sửa. Coding agent có nhiệm vụ triển khai toàn bộ chuỗi đến kết quả DFG có evidence, không dừng ở skeleton hoặc kế hoạch. Nếu gặp thiếu input hoặc mâu thuẫn semantic thực sự, nêu blocker chính xác và tiếp tục phần không bị chặn; không sửa contract/gold để làm tests pass.

