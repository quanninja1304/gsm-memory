# GSM — Dataset Release Specification

**Spec:** `gsm-dataset-release-spec-v0.2.0` · **Ngày:** 16/09/2026  
**Release được thiết kế:** `gsm-dev-core-0.2` · **Trạng thái:** specification; chưa sinh dataset, chưa pass Data Freeze Gate.  
**Contract:** `01_problem_and_evaluation.md` → `02_synthetic_schema_and_data_design.md` v1.1 → spec này. `04_benchmark_to_dataset_mapping.md` v0.3 là methodology/design rationale.

SHA-256 của bản 02 áp dụng: `2310f80d281b0f703e4b8eb9a738ed0ef2a9b81a3d766cc25662f6f097e759f8`.

Mục tiêu là chốt một pilot **8 drivers, 80 distinct terminal trips, 42 canonical queries**, có nguồn, ledger, snapshot, proof và expected result xác định trước khi tích hợp retrieval. Spec này bổ sung evaluation metadata và quyết định đóng gói; không đổi business schema, không mở các hàng DEFER, không đổi Graphiti reference. `MUST` là điều kiện nghiệm thu; mọi sai khác với 02 phải sửa spec hoặc version contract, không tự sửa generator để che mâu thuẫn.

**Revision 0.2.0:** chốt hai corpus profiles, `retrieval_full`=224 real articles làm baseline mặc định và `debug_core`=6 làm cấu hình conformance. Audited subset=6, primary-gold source subset=4. Giữ nguyên 8 drivers/80 trips/42 semantic queries, T01–T07, bindings và operational facts/revisions; bổ sung source-publication metadata, packaging và evaluation protocol. Dataset ID/UUID namespace tăng thành `gsm-dev-core-0.2`; không ghi đè artifact/release 0.1 nếu đã tồn tại. Imported source snapshot IDs/hashes của sáu bài vẫn giữ nguyên. Đây là spec update, không phải bằng chứng generator hoặc benchmark đã chạy.

## 1. Phạm vi và thứ tự thực hiện

| Quyết định | Contract release v0.2 |
| --- | --- |
| Policy tasks | T01–T07; bindings `task_binding:B01@1.0` … `task_binding:B07@1.0` đã freeze trong 02. Không đổi binding IDs của 02 |
| Foundation | Identity, state, trip-derived metric, bridge, temporal revision, missing/conflict và synthetic policy history trong vocabulary cũ |
| Ba gold tracks | `source_grounded`, `conditional_binding`, `synthetic_control`; tách thống kê và diễn giải |
| Split | Toàn bộ 42 queries là **dev**. `test.jsonl` rỗng có chủ đích. Chưa có locked test hoặc claim về superiority |
| Ngôn ngữ | Tiếng Việt, canonical templates xác định. Không cần LLM để sinh pilot; chưa nhân paraphrases, implicit/composed queries |
| Research order | BM05 evidence-first + BM07 replay + BM03 structured-first → canonical pilot → BM02 wording diagnostic → BM01/BM06 scale-noise studies |
| Graphiti | Mode A/B nhận cùng thông tin công khai, active profile và cutoff; gold độc lập. Không cần Graphiti hoạt động để freeze dữ liệu |
| Corpus profiles | `debug_core`: 6 real snapshots cho conformance/debug; `retrieval_full`: 224 real snapshots, baseline document/hybrid mặc định khi pipeline chạy được. Cùng synthetic documents/definitions |
| Không sinh | Offers, sessions, raw revenue/rating, payroll, attendance, cohort/persona, eligibility verdicts hoặc predicates ngoài 02 |

**Pilot purpose = conformance + end-to-end debugging; not final performance estimation.** 42 queries là catalogue target được materialize và validate theo spec, không phải 42 independent statistical samples. Con số 42 chốt allocation/build checks của pilot; nó không xác lập sampling distribution, statistical power hoặc production representativeness. `Data Freeze` chứng nhận dữ liệu/proofs nhất quán, không biến catalogue thành statistical evaluation set.

Có thể báo `n_correct/n_scored` và tỷ lệ đúng **trên pilot fixtures này** để debug, kèm task/track, expected-status breakdown và blocked/error counts. Phải hiện cả mẫu số 42 planned, số thực chạy và số chấm được; không giấu API failures bằng đổi mẫu số. Không dùng “Graphiti accuracy = x%” trên catalogue này làm headline về hiệu năng chung, không tính confidence interval/p-value giả định 42 câu độc lập. Final performance estimation cần release held-out riêng, target population/query mix và estimand rõ, paired protocol, cùng uncertainty theo đơn vị độc lập thực sự. Shared histories không trở nên độc lập chỉ vì đổi scenario ID.

## 2. Nguồn và ranh giới claim

### 2.1. Corpus được pin

Release pin **224 bài riêng** từ archive của 02; không coi mọi bài là một executable policy. Kiểm inventory attachment xác nhận 224 source URLs và raw hashes khác nhau, cùng một file tổng hợp bị loại khỏi index. Sáu nhóm trùng title có trong corpus; P05/P06/P07 cùng title/ngày nhưng khác geographic scope, và có FAQ text tương đồng. Giữ near duplicates theo source identity, không deduplicate chỉ theo title/date/text.

| Nhóm nguồn thật | Số bài | Vai trò evaluator |
| --- | ---: | --- |
| P154/P151/P05/P23 | 4 | Chỉ reviewed TEXT spans cung cấp primary gold cho T01–T07 |
| P172/P26 | 2 | Đã audit, hiện là distractors; không mở decision tasks |
| Các bài còn lại | 218 | Nguồn tìm kiếm bổ sung; không executable bindings/primary gold; chưa có complete relevance judgments |

Do đó `audited subset=6`, `primary-gold source subset=4`. Giữ raw đầy đủ, kể cả unreviewed OCR. Các vai trò trong bảng là private evaluation metadata, không export thành retrieval filters. Bảng dưới pin sáu audited source hashes; G0 phải tính và ghi actual raw/normalized hashes cho cả 224 bài, không chỉ sáu bài này.

| Alias nguồn | Raw SHA-256 | Vai trò trong pilot |
| --- | --- | --- |
| P154 | `d4af281952715d325bf533c265e3b046cda622b3bd51e05d066d61b64439c033` | T01/T02; clause refs `s154.*` theo 02 §0.8 |
| P151 | `063bee7308254d5dbf4fc3c93edb0c1f902e80c3444082a83a686687d3be1368` | T03; `s151.scope`, `s151.auto` |
| P05 | `a4bc920aa65c42d81ac04e6b7594a74efc61fc7c2116bdbb1653c02ca5cecc4e` | T04/T05; reviewed FAQ TEXT spans |
| P23 | `b62fd1ddee0ca6a0a75d3ccb6dfc85156c819560c233111a3995f862006103b4` | T06/T07; `s23.scope`, `s23.date` |
| P172 | `7c3be60e90400504db49b83e2fb6eb0f745ae173d751f5b5351d3ca1f1c23c8d` | Bài cùng chương trình; không tự gán quan hệ supersession với P23 |
| P26 | `c308c04cb3de5e219c5488d8091bcfd08fea673f1007f669ba9ba065e7a01315` | Khác cohort/điều kiện; không dùng unreviewed OCR làm gold |

Archive pin là `cfe9e4555dbedf81396004c7a7d0ace52dcbb1deb758110c4aded3b6741ba9c9` theo 02. Tên file/URL/locators và imported IDs của sáu audited snapshots theo audit 02; 218 snapshot IDs mới dùng ID algorithm §3.1 với stable key `(archive_member_path,raw_sha256)`, không dùng title làm identity. Generator MUST kiểm actual bytes, không tải mới cùng URL để thay nguồn đã pin. Normalization chỉ CRLF→LF; offsets `[start,end)` theo Unicode code points, line từ 1. `captured_at` unknown khi thiếu chứng cứ; OCR-present/review_state không được biến thành measured OCR quality. Không cần review toàn bộ business clauses hoặc ảnh của 218 bài để ingest như nguồn chưa duyệt.

Logical availability của **toàn bộ 224 real snapshots** trong release này là **2026-09-16T00:00:00.000000Z**, qua `ARTIFACT_PUBLICATION` của benchmark; valid kind=not_applicable. Đây không phải ngày website xuất hiện hay policy có hiệu lực. Mỗi snapshot có một publication assertion truy vết được, do source được registry cấp quyền phát hành artifact; cùng ID/payload được chia sẻ giữa mọi ledger branch nếu visible. Các publication records bổ sung được lập trước khi gán commit_seq toàn release (§7). Giữ nguyên operational facts/revisions và conventions; không hứa giữ record count, generated IDs hoặc ledger bytes của release 0.1. Không tạo `POLICY_PUBLICATION`, supersession hoặc normative rules cho 218 bài mới.

BC01–BC07, bốn reported definitions và definition `cancel_rate_30d` là public benchmark documents, có provenance riêng. Các templates được render từ semantics trong 02, không bổ sung internal formula GSM. Core definitions/registry có logical availability 2026-07-01T00:00:00.000000Z; references tới real snapshots chỉ truy cập được sau availability của chính snapshot đó.

Synthetic controls có hai policy families: `S_BRIDGE` và `S_VERSION` (§4). Chúng được đánh dấu rõ là synthetic; chỉ những controls này có lịch `POLICY_PUBLICATION` được generator tạo. T01–T07 luôn hỏi edition được cấp theo BC07. Không hỏi “policy hiện hành” rồi dùng snapshot duy nhất làm gold mặc định.

### 2.2. Các claim được phép

| Track | Tasks | Claim đúng phạm vi |
| --- | --- | --- |
| `source_grounded` | T01/T04/T06 | Nội dung của source snapshot chỉ định |
| `conditional_binding` | T02/T03/T05/T07 | Kết luận theo rule đã chỉ định, synthetic observations và conventions công khai |
| `synthetic_control` | FND cases | Temporal/entity/aggregate/bridge correctness trong world và publication model tổng hợp |

T05 chỉ chấm `rating_condition_only`; T07 chỉ `notice_scope_only`. T02 không xác nhận wallet deduction thật; T03 không thực thi bật auto-accept. Reported revenue/AR/rating không được tự suy lineage từ 80 trips.

### 2.3. Corpus profiles và giới hạn phép đo

| Profile ID | Real articles | Shared documents trong inventory | Vai trò |
| --- | ---: | --- | --- |
| `debug_core` | 6 audited snapshots | 3 synthetic versions + 12 definitions | Conformance, debugging và micro end-to-end path |
| `retrieval_full` | 224 snapshots, bao gồm sáu bài trên | Cùng 3 synthetic versions + 12 definitions | Baseline document/hybrid mặc định sau khi pipeline chạy được |

Counts là toàn inventory, không phải số documents visible tại mọi cutoff. Raw/normalized là hai representations của cùng nguồn. Mỗi profile có version `1.0` và manifest hash; baseline comparisons dùng cùng profile, chunking, source snapshot, qrels, reader/budgets. Paired corpus diagnostic giữ mọi yếu tố đó trừ profile. Không nhân 42 semantic cases thành 84 independent samples, không tạo world/ledger branch/mutation mới chỉ vì chọn profile.

T01–T07 vẫn cấp snapshot được hỏi. Prefilter bằng reference công khai là hợp lệ; tập policy document candidates có thể còn một bài, nhưng vẫn có nhiều chunks/clauses, definitions và KG evidence. Phải log counts trước/sau edition filtering; không gọi 224-source run này là complete document-discovery benchmark. Discovery subset bổ sung sau pilot cần query/gold/answerability review và version riêng; không tự xóa reference khỏi 42 fixtures hoặc suy current policy từ crawl.

Giữ operational graph input, construction mode và graph snapshot cố định trong paired corpus diagnostic. Không tự ingest/extract 218 bài mới thành operational facts hoặc graph scope hints; mọi policy-to-graph experiment là track riêng có construction audit. Profiles chỉ thay real document candidates; KG scalability vẫn cần entities/events/edges/revisions studies riêng.

`retrieval_full` không được dùng private `gold_bearing`, `retrieval_only`, task binding, relevance hoặc tập primary-gold sources để thu corpus về bốn/sáu bài. Neutral provenance/review_state có thể public, nhưng không đồng nghĩa relevance và không là quyền tự loại toàn bộ unreviewed sources. Runtime chỉ nhận active profile và visible source view theo §6.2; profile registry đầy đủ không được mount như một nguồn để suy gold.

## 3. Scenario, semantic case và rendering

### 3.1. Identity và quan hệ

`ScenarioManifest` là **private evaluation sidecar**, không phải entity hoặc predicate nghiệp vụ. Một root scenario chứa các biến thể của cùng tình huống; mỗi variant chọn một world/ledger branch; semantic case cố định câu hỏi nghĩa, scope và hai đồng hồ; rendering cố định cách diễn đạt.

**Exact serialization contract.** `ScenarioManifest` là closed JSON object: mọi field trong bảng đều **required**; không có optional field ở version này. Nullable chỉ ở ba fields được ghi `null` bên dưới; required khác nullable. Unknown keys bị reject, không silently ignore. `base_scenario_id` là alias suy ra bằng `scenario_id`, không serialize thêm một field trùng nghĩa.

`ID` là lowercase UUIDv5 được sinh theo thuật toán cuối §3.1. `ID[]` là JSON array unique, sắp theo thứ tự từ điển để serialization ổn định; giới hạn rỗng được ghi riêng. Imported source snapshot/version references giữ IDs của catalog đã pin, không bị ép đổi thành UUID mới. Foreign keys luôn kiểm đúng dataset/world/scope khi loại record có các keys đó.

| Field | Exact type / allowed values | Required / nullable | FK hoặc constraint |
| --- | --- | --- | --- |
| `schema_version` | string, const `1.1` | required / no | Business semantics của 02 giữ nguyên |
| `release_spec_version` | string, const `0.2.0` | required / no | Version của spec này; business schema vẫn 1.1 |
| `dataset_version` | string, const `gsm-dev-core-0.2` | required / no | Release manifest |
| `world_id` | ID | required / no | World partition tồn tại trong private oracle; core chỉ W0 |
| `scenario_id` | ID | required / no | Root identity; dùng nguyên trong QueryGold |
| `scenario_variant_id` | ID | required / no | PK `(dataset_version,scenario_variant_id)` |
| `parent_variant_id` | ID hoặc null | required / yes | FK cùng file; base=null, non-base khác null; self-parent bị cấm |
| `mutation_type` | enum `base/observation_mask/source_conflict/retraction_branch` | required / no | Closed enum cho pilot; không nhận arbitrary string |
| `mutation_spec` | Closed object được chọn theo mutation_type | required / no | Discriminated payload ở §3.3; base chỉ `{}` |
| `ledger_id` | ID | required / no | `private/eval/manifest.json:ledgers[].ledger_id`; registry ghi world/scope và ledger file path/hash |
| `scope_id` | ID | required / no | Published scope trong source registry; khớp ledger và cases |
| `gold_track` | enum `source_grounded/conditional_binding/synthetic_control` | required / no | Theo §2.2 và task mapping, không tự chọn |
| `task_id` | enum T01…T07 hoặc null | required / yes | FK `task_bindings.jsonl:task_id` nếu không null |
| `foundation_task` | enum `state/event/aggregate/bridge/entity_resolution/policy_version` hoặc null | required / yes | Chính xác một trong task_id/foundation_task khác null |
| `policy_snapshot_refs` | Array unique của `{kind,id}`, có thể rỗng | required / no | kind=`real_snapshot` → SourceDocumentSnapshot.snapshot_id; kind=`synthetic_version` → PolicyVersion.policy_version_id. id là nonempty string; object không nhận keys khác |
| `public_snapshot_refs` | ID[], minItems=1 | required / no | FK `public/snapshots/{id}/manifest.json:snapshot_id`; đúng world/ledger/scope và case cutoff |
| `semantic_case_ids` | ID[], minItems=1 | required / no | FK `semantic_cases.jsonl:semantic_case_id`; phải khớp tập cases trỏ ngược về variant |
| `query_ids` | ID[], minItems=1 | required / no | FK `query_renderings.jsonl:query_id`; khớp union renderings của semantic_case_ids |
| `split_group` | ID | required / no | FK group trong splits.jsonl; một group W0/cohort cho toàn pilot |
| `seed` | integer, const 42 | required / no | Root seed; component streams được suy ra theo §7, không ghi random seed khác vào field này |

Trong v0.2, `policy_snapshot_refs` sort theo `(kind,id)`. Mapping task/track bắt buộc: T01/T04/T06 → source_grounded; T02/T03/T05/T07 → conditional_binding; foundation_task khác null → synthetic_control. Trường null vẫn phải xuất hiện trong JSON.

Ledger registry trong private release manifest là array closed objects `{ledger_id,world_id,scope_id,record_ledger_path,record_ledger_sha256}`; ba IDs có type ID, path là nonempty relative path trong release inventory, hash là 64 lowercase hex characters. Tất cả fields required/non-null, ledger_id unique trong dataset; path/hash phải khớp ledger bytes thực. Đây là metadata để kiểm FK, không thêm một business table.

`corpus_profile_id` thuộc run configuration, không thêm vào closed ScenarioManifest hoặc mutation_type; public_snapshot_refs vẫn tham chiếu canonical visible packages (§6.2). `correction` là operation semantics trong source ledger (`replace`), **không mặc nhiên là ScenarioManifest mutation**. C009/C010/C011 đọc các prefixes của cùng L0, nên variant vẫn `base`. Chỉ khi tạo timeline thay thế mới cần branch metadata. `world_value_change`, `presentation_only` và `scale_distractor` chưa được phép serialize trong pilot này; mở sau phải version payload/schema và thêm validation, không chỉ thêm một string enum.

`SemanticCase` có `semantic_case_id`, `scenario_variant_id`, task reference, `query_intent`, entity/time/window constraints, `known_as_of`, `scope_id`, `public_snapshot_id`, `application_context_refs`, `answer_scope`, `expected_status`, `proof_refs`. `proof_refs` trỏ tới các query-bound records trong `private/eval/proofs.jsonl`; pilot chỉ có một rendering nên một proof ref/case. Fields gold/private không xuất sang RuntimeQuery.

`QueryRendering` có `query_id`, `semantic_case_id`, `style`, `template_id/version`, rendered text, public request fields và content hash. Pilot dùng `style=direct`, **một rendering/case**. Về sau paraphrases giữ case; composed hoặc false-premise chỉ được dùng khi semantics/rubric đã được kiểm riêng. Không mặc định copy gold cho câu hỏi mới.

Trong private tables có thể dùng aliases C001–C042, D_A–D_H và L0/L_* để review. Public IDs MUST opaque; không chứa task/fault/status/split. Pin ID algorithm: UUIDv5 với namespace `uuid5(NAMESPACE_URL,"urn:gsm:gsm-dev-core-0.2")`, rồi name `object_type + ":" + stable_private_key`. Không dùng Python `hash()`, position trong một list thay đổi được, hoặc Graphiti UUID làm canonical identity. Khi cùng SourceRecord xuất hiện ở nhiều branches, ID và payload/hash phải giống nhau; nội dung khác bắt buộc ID mới.

### 3.2. Mutation nào tạo world mới?

Bảng sau phân biệt semantics chung, kể cả các hướng mở rộng. Chỉ bốn mutation types của §3.1 được serialize trong pilot; những dòng khác không cấp quyền tự thêm variants hoặc fields.

| Phép biến đổi | World | Ledger/snapshot | Query/gold |
| --- | --- | --- | --- |
| Đổi wording cùng nghĩa | Giữ | Giữ | Query ID mới, cùng semantic case/proof |
| Hỏi trước/sau known-time correction | Giữ | Cùng ledger, snapshot cutoff khác | Cases khác; gold được tính lại từ từng prefix |
| Che source, thay observation bằng conflict/retraction branch | Giữ true world | Ledger ID mới; shared records bất biến | Gold observable đổi; world answer có thể giữ |
| Đổi sự thật: fleet, event outcome hoặc true rate | World ID mới | Ledger và cases tương ứng mới | Regenerate gold; giữ root/split group nếu là sibling |
| Đổi presentation position | Giữ | Giữ canonical order/clocks; ghi renderer config | Không đổi gold; v0.2 chưa nhân variants này |
| Câu hỏi chứa tiền đề sai | Giữ | Giữ; query không ghi vào memory | Có rubric sửa premise; không tạo counterfactual world |

Mask phải loại dependency closure, gồm translations, summaries và artifacts có thể tiết lộ fact đã che. Không được giữ coverage certificate vẫn cam kết đầy đủ một domain đã bị mất records. Chỉ che relation không quyết định nội dung coverage trip thì giữ certificate trip; tránh xóa toàn bộ memory vô cớ.

**Presentation position ≠ logical time.** Sort/replay SourceRecords theo `(known_at,commit_seq)` bất biến. Thay vị trí chunk trong context không cho phép đổi `known_at`, target dependencies hoặc công bố correction trước target.

### 3.3. Mutation payload schema và semantics

Các payload sau là **closed object types**; mọi field liệt kê đều required, không nullable, không extra keys. IDs tham chiếu canonical records/assertions trước projection. Arrays unique và sorted; `invariant_refs` là nonempty array các IDs trong I01–I28 của 02. Nó ghi rationale, không cho phép bỏ các validation checks không được liệt kê.

| mutation_type | Exact mutation_spec fields | Constraints và nghĩa |
| --- | --- | --- |
| `base` | Không có field: `{}` | parent=null; L0; đúng một base variant cho mỗi root |
| `observation_mask` | `seed_record_ids: ID[1..]`; `removed_record_ids: ID[1..]`; `closure_policy: const "remove_dependents"`; `invariant_refs: invariant_ID[1..]` | seed IDs và mọi removed ID thuộc parent ledger; seeds ⊆ removed. Removed set bằng seeds + dependent records cần loại theo lineage/coverage/alternative-support audit; không thêm records |
| `source_conflict` | `logical_fact_id: ID`; `removed_record_ids: ID[0..]`; `added_record_ids: ID[1..]`; `invariant_refs: invariant_ID[1..]` | logical key tồn tại ở parent; added records thuộc child và chưa ở parent. Phải tạo competing assertions khác value/status, overlap đúng window/time và cùng highest public authority tại case cutoff. Core L_CONFLICT bỏ r2, giữ r1, thêm feed-B assertion; không tạo world truth mới |
| `retraction_branch` | `target_assertion_ids: ID[1..]`; `removed_record_ids: ID[0..]`; `added_record_ids: ID[1..]`; `invariant_refs: invariant_ID[1..]` | Added commits đều là `operation=retract`, union targets bằng target_assertion_ids; không payload assertions mới. Sau khi bỏ planned replacement, targets phải active/authorized và known strictly earlier tại từng retract commit. Core L_RETRACT bỏ r2 và thêm retract r1 |

Delta được tính trên **record sets**, không chỉnh bytes tại chỗ:

\[
R_{child}=(R_{parent}\setminus R_{removed})\cup R_{added}.
\]

Với mask, added set rỗng. Với conflict/retraction, removed records chỉ gồm planned revisions của affected key và dependent records cần loại để timeline hợp lệ; không được tiện thể thay các facts không liên quan. Các source-level targets phải được expand thành record IDs xác định trước khi serialize; không lưu selector string/SQL/Python hoặc một generic patch object để runtime tự diễn giải.

`seed_record_ids` là nguồn bắt đầu mask; dependency closure đi qua revision targets, source refs, artifact dependency/source-set membership và publications. Alternative supports không có lineage trực tiếp nhưng vẫn tiết lộ fact cần được thêm vào seeds theo review. Giữ unrelated facts/coverage. Text observations, catalogs và artifact visibility được regenerate từ child ledger; không biến redaction thành một thay đổi payload của shared record. Các input source locators và closure results đủ kiểm lại delta mà không cần Graphiti IDs.

### 3.4. Uniqueness, foreign keys và parent validation

JSON shape validation không đủ kiểm DAG hoặc cross-file semantics. Validator MUST chạy các checks sau sau khi load toàn bộ sidecars, không dựa thứ tự rows trong JSONL.

| Check | Điều kiện bắt buộc |
| --- | --- |
| SM01 Shape | Đúng required/type/null/enum/closed-object contract §§3.1/3.3; reject extra keys và payload thuộc mutation khác |
| SM02 Uniqueness | Unique scenario_variant_id trong dataset; unique `(dataset_version,scenario_id,ledger_id)` trong pilot; mỗi root có đúng một base và cùng task/foundation/track |
| SM03 Parent FK | Mọi non-base parent tồn tại; khác chính node; cùng scenario_id, world_id, scope_id, task/foundation, track và split_group; child ledger khác parent. Base parent=null và ledger=L0 |
| SM04 DAG/reachability | DFS màu hoặc topological sort trên parent→child phải thăm đủ nodes, không cycle. Mỗi variant truy ngược đến đúng base cùng root; không orphan hoặc second root. Pilot §5.2 chỉ có depth 0/1 |
| SM05 Case/rendering ownership | Mỗi semantic case thuộc đúng một variant, mỗi query đúng một case; manifest lists bằng reverse-FK sets, không subset. QueryGold.scenario_id/split_group/world khớp owners |
| SM06 Snapshots/splits | public_snapshot_refs bằng tập snapshots cases thực dùng; mỗi snapshot đúng ledger/scope/world/cutoff. Policy refs bằng union refs cần của cases, không trộn real snapshot với synthetic version. Mọi query và shared history cùng split group |
| SM07 Mutation delta | Removed ⊆ parent; added không thuộc parent; disjoint sets; actual child bằng set equation. Shared record bytes/hash/commit_seq không đổi; kiểm payload-specific closure, conflict hoặc retract semantics |
| SM08 Scope/isolation | 25 roots, 32 variants, 8 ledgers, 42 cases/renderings đúng §5.2. Sidecars, mutation payloads và expected statuses chỉ private; không trộn vào retrieval metadata |

Validation report MUST có failed IDs và field path để coding agent sửa đúng lỗi. Ví dụ cần reject: unknown mutation string; omitted required nullable field; base có nonempty payload; target record không tồn tại; query thuộc hai variants; parent cycle; mask thiếu dependent publication; hoặc đổi commit_seq của một shared record. Schema/validator cho sidecar không tạo thêm business predicate và không chứng nhận actual graph conformance.

## 4. Pilot world và fixture recipe

### 4.1. Population và IDs

Core có một world W0, một scope S0, 8 drivers, 4 fleets F1/F2/F6/F7, hai regions HN/HCM_OLD, một service tổng hợp và một incident I_F. Fleets được registry công khai map tới “Depot Hồ Chí Minh 1/2/6/7”; `BASED_IN=HCM_OLD`. Không có bảng public “policy → eligible fleet IDs”. Các assignments này là fixtures tổng hợp để kiểm retrieval, không mô phỏng tính khả thi bố trí Bike/Taxi vào Depot ngoài thực tế.

| Driver alias private | Program; membership mặc định | Operating region / điểm đặc biệt | Distinct terminal trips |
| --- | --- | --- | ---: |
| D_A | bike_partner; F1 | HN; các reported-measure cases | 12 |
| D_B | bike_partner; F6 | HCM_OLD; 2 cancelled + 8 completed | 10 |
| D_C | taxi_driver; F1 → F2 | HCM_OLD; correction membership tại §4.3 | 14 |
| D_D | taxi_driver; F2 | HCM_OLD | 14 |
| D_E | bike_partner; F6 | HCM_OLD hiện tại; historical region correction | 10 |
| D_F | bike_partner; F6 | HCM_OLD; incident I_F open | 10 |
| D_G | bike_partner; F7 | HCM_OLD; future suspension và một late trip | 10 |
| D_H | bike_partner; F7 | HCM_OLD; zero-trip aggregate | 0 |
| **Tổng** | | | **80** |

D_E và D_F cùng display name “Minh”, cùng scope/fleet/current region; registry không đủ phân giải câu hỏi C032. Các drivers khác có tên khác nhau. Tất cả dùng service tổng hợp, category=standard và status=active trừ lịch D_G. Registry/program/stable assignments ban đầu có valid/known start 01/07/2026 UTC; không tự sinh null end của world thành lifetime công khai.

Trips mang IDs riêng; không thêm Trip business nodes. Trong mỗi driver, j=0…n−1: terminal event mặc định tại `2026-08-18T02:00:00Z + j days + driver_index minutes`, driver_index A=0…H=7. D_G/j=0 được đặt riêng tại `2026-08-20T02:00:00Z`. D_B/j∈{0,1} cancelled với reason `driver_request`; các trips còn lại completed với reason `unspecified`. Region theo world state tại event. Normal trip publication = event time + 1 giờ; riêng D_G/j=0 công bố tại AC. Mỗi trip chỉ có một world terminal event; source copies/revisions không tăng population.

Các fixture trên cố ý đơn giản. Không dùng chúng để suy revenue, acceptance rate hoặc rating. Core count 80 không tính event copies ở observation branches hoặc auxiliary conformance fixtures.

### 4.2. Calendar và reported values

Timestamps dưới đây là logical clocks của fixture, không wall-clock chạy thử.

| Alias | Giá trị chốt |
| --- | --- |
| A0 | `2026-09-16T12:00:00.000000Z` |
| AC | `2026-09-17T01:00:00.000000Z` — correction/retraction commit time; inclusive known_from |
| A1 | `2026-09-17T12:00:00.000000Z` |
| W10…W14 | Ngày 10…14/09/2026, local `[00:00,00:00 hôm sau)`, Asia/Ho_Chi_Minh |
| WA14, WA15 | Ngày 14/09 hoặc 15/09, local `[00:00,10:00)` |
| WW0 | Tuần local `[07/09/2026 00:00,14/09/2026 00:00)` |
| WW1 | Tuần local `[31/08/2026 00:00,07/09/2026 00:00)` |
| WW2 | Tuần local `[24/08/2026 00:00,31/08/2026 00:00)` |
| Tm / W30 | Tm=`2026-09-15T17:00:00Z` (16/09 00:00 local); W30=`[2026-08-16T17:00:00Z,Tm)` = đúng 30×24 giờ |
| Tf | `2026-09-14T03:00:00Z` (14/09 10:00 local), membership queries |

| Subject / definition | Window | Observation(s) trong L0 |
| --- | --- | --- |
| D_A / RM_OPDAY | W10 | reported=false; revenue absent có chủ đích |
| D_A / RM_OPDAY | W11/W12/W13/W14 | reported=true, một report/key |
| D_A / RM_REVENUE | W11/W12/W13 | 200000 / 280000 / 300000 VND |
| D_A / RM_REVENUE | W14 | r1=200000; r2=240000 replace r1 tại AC |
| D_B / RM_REVENUE | W11 | 200000 VND, đúng driver D_B; distractor cho D_A |
| D_A / RM_ACCEPTANCE | WA14/WA15 | 49/100 và 1/2 |
| D_A / RM_ACCEPTANCE | W14 cả ngày | 49/100; đúng value nhưng sai window cho WA14 |
| D_A / RM_RATING | WW0/WW1 | 97/20 và 49/10 stars_5 |
| D_A / RM_RATING | WW2 | explicit `undefined`, reason=no_observations; không numeric 0 |

Tất cả initial reports được publish 16/09/2026 01:00Z; updates tại AC. `valid` là đúng measurement window, `event_time=null`. D_A program/operating region phủ nguyên các ngày dùng T02. Derived metric của D_B dùng **10 distinct trips + complete coverage + public definition**, không dùng các reports trên.

### 4.3. Temporal controls, sources và branches

| Control | Recipe / kết quả bắt buộc |
| --- | --- |
| D_C membership correction | Nguồn registry lúc 01/09 công bố F1 `[01/09,15/09)` và F2 `[15/09,∞)` theo local midnight. Tại AC atomic replace cả hai thành F1 `[01/09,14/09)` và F2 `[14/09,∞)`. World truth là lịch sau correction. Tf/A0 chọn F1; Tf/A1 chọn F2 |
| D_G future status | Công bố 16/09 01:00Z: active đến `2026-09-17T17:00:00Z`, suspended từ instant đó. Replace active assertion cũ và giữ đoạn lịch sử không đổi. Query một microsecond trước/exact boundary cho hai trạng thái khác nhau |
| D_G late event | World event 20/08, source chỉ known tại AC. Trước AC không chứng minh terminal outcome; sau AC completed. Không phát complete trip coverage trước khi event đã visible |
| D_E historical correction | Nguồn 03/08 00:00Z công bố HN `[01/07,01/08)` và HCM_OLD từ 01/08; thay thế state assertion trước đó nguyên tử. 05/08 00:00Z sửa transition thành 02/08, republish cả hai segments. Tại valid=01/08 12:00Z: known=04/08 → HCM_OLD; known=06/08 → HN |
| S_BRIDGE | Synthetic rule: requires `fleet_region=HCM_OLD`; exception `incident_open=true`. Issued/known từ 01/07; một version. D_B không incident, có incident-domain complete coverage tại Tm; D_F có HAS_INCIDENT + INCIDENT_STATUS=open từ 01/09, known cùng ngày |
| S_VERSION | Synthetic family: v1 requires operating_region=HN, valid local `[01/09,15/09)`; v2 requires HCM_OLD, valid từ 15/09. V1 published trước 01/09, v2 published 10/09 với atomic revision lịch v1 nếu cần. C041 hỏi exact valid boundary 15/09 00:00 local, known=A0 → v2 |

Source registry có bảy nguồn tổng hợp: registry, event log, incident log, metric feed A/B, policy publisher, derived publisher. Mỗi nguồn authority_rank=10 trong predicate domain được cấp; feed A/B ngang quyền. `can_correct_source_ids` mặc định chỉ chính nguồn; không dùng publisher khác để vô hiệu report. Registry/source permissions được công bố từ 01/07. `commit_seq` tăng theo lịch generator đã pin; commits cùng timestamp phải độc lập, không sửa target cùng timestamp. Các records của publication khác domain được phép đồng thời.

Để masks không làm đổi payload của shared record, initial assert commits tách theo logical fact key: mỗi reported key/trip/relation key có record riêng. Nhiều disjoint state segments của cùng key có thể chung record; correction/replace giữ atomic segments theo 02. Che một key phải bỏ whole relevant records/dependencies, không cắt assertion ra rồi giữ record_id/hash cũ.

Core publication recipes gồm complete terminal-trip coverage cho D_B/W30 và D_H/W30, với source-set manifests lần lượt 10 và 0 trip IDs; publish 16/09 03:00Z. Complete incident-domain coverage của D_B bao phủ interval `[01/07 00:00Z,Tm+1 microsecond)`, cũng publish lúc đó, đủ chứng minh không có open incident tại Tm. Coverage không khẳng định những domains ngoài phạm vi của nó. Không xuất precomputed metric/profile trả sẵn các đáp án C029/C030; stale-artifact behavior được kiểm bằng auxiliary fixture riêng.

Full base ledger L0 chứa initial records và mọi revisions chuẩn. Bảy branches dưới đây là timeline thay thế **tách biệt**, không ingest chung vào L0:

| Ledger alias | Delta so với L0 | Cases |
| --- | --- | --- |
| L_NO_OPDAY | Mask D_A/RM_OPDAY/W11 và mọi artifact tiết lộ nó | C007 |
| L_WRONG_DRIVER | Mask D_A/RM_REVENUE/W11; giữ D_B/W11 | C008 |
| L_CONFLICT | Bỏ replacement r2; giữ r1 active; feed B assert 240000 cho D_A/W14 tại AC, ngang rank | C012 |
| L_RETRACT | Thay replacement r2 bằng retract r1 tại AC; không report khác cho key | C013 |
| L_WRONG_WINDOW | Mask D_A/RM_ACCEPTANCE/WA14; giữ report W14 cả ngày | C016 |
| L_NO_BRIDGE | Mask BASED_IN của F6 và mọi alternative public support tương đương; giữ OPERATES_IN(D_B,HCM_OLD) | C031 |
| L_NO_COVERAGE | Mask complete terminal-trip coverage của D_B/W30 và artifacts đủ để tái chứng minh completeness; giữ cả 10 trip records | C040 |

World truth giữ nguyên trong các observation branches. Hợp nhất branches để “tăng dữ liệu” là lỗi. Gold được tính bằng reducer trên ledger branch và prefix của case; không bằng latest state trong private world.

## 5. Catalog 42 canonical queries

### 5.1. Cách đọc và render

C001–C042 là **private case aliases**, không runtime IDs. Mỗi hàng tạo một SemanticCase và một QueryRendering. Placeholders `{D_A}`, `{P154}`, `{W11}`… được thay bằng opaque entity ID, snapshot reference và timestamp/window thật từ manifest; không xuất alias hoặc gold vào query. Quyết định task binding/family nằm trong private eval.

Application context của mọi T01–T07 cấp snapshot được hỏi, BC07 và phần BC/quantity definitions cần để hiểu premises. Nó nêu rõ “đọc nội dung edition được chỉ định” hoặc “đánh giá điều kiện của edition này trên dữ liệu được cấp”; không cung cấp condition truth, threshold đã tính, task ID hoặc private AST. Các từ “có thuộc nhóm”, “đạt riêng điều kiện” giới hạn claim, không hỏi full eligibility. References là source references công khai; nếu inject nội dung definitions vào context thì phải tính token/cost như evidence thông thường, không cho hidden free context.

Mặc định known=A1, ledger=L0, access_scope=S0. Cột thời gian/branch ghi mọi ngoại lệ. T02 dùng W làm measurement window và phải kiểm program/region phủ nguyên W; T03/T05 không tự chọn window gần nhất; C033/C034 chấp nhận future valid_at vì state đã được công bố. File gold ghi đầy đủ expected_status enum, kể cả answerable có verdict=false.

| Case / task / primary family | Runtime wording template | Time / branch | Expected result và evidence quyết định |
| --- | --- | --- | --- |
| C001 / T01 / Q1 | “Theo {P154}, quy định doanh số tối thiểu dành cho nhóm tài xế nào, tại khu vực nào?” | A1 | answerable: Bike partner, Hà Nội; `s154.scope + region` |
| C002 / T01 / Q1 | “Theo {P154}, ngày vận doanh được hiểu thế nào và truy thu phần doanh số thiếu được tính ra sao?” | A1 | answerable: định nghĩa ngày và `max(280000−R,0)/5` VND; `s154.day + charge` |
| C003 / T02 / Q4 | “Theo edition {P154} và conventions được cấp, khoản truy thu theo rule cho {D_A} trong {W11} là bao nhiêu?” | W11 | answerable: 16000 VND; scope/day + R=200000 + rule/definitions |
| C004 / T02 / Q4 | Như C003, thay W11 bằng W12 | W12 | answerable: 0 VND; R=280000, boundary |
| C005 / T02 / Q4 | Như C003, thay W11 bằng W13 | W13 | answerable: 0 VND; R=300000, không amount âm |
| C006 / T02 / Q4 | Như C003, thay W11 bằng W10 | W10 | answerable: not_applicable, amount=null; explicit operating_day=false + day clause; không cần R |
| C007 / T02 / Q7 | Cùng wording C003 | W11; L_NO_OPDAY | insufficient_evidence; thiếu operating-day attestation; không suy từ R hoặc trips |
| C008 / T02 / Q7 | Cùng wording C003 | W11; L_WRONG_DRIVER | insufficient_evidence; không lấy R của D_B cho D_A |
| C009 / T02 / Q6 | Như C003, thay W11 bằng W14 | W14; A0 | answerable: 16000 VND theo r1; không đọc correction tương lai |
| C010 / T02 / Q6 | Cùng wording C009 | W14; A1 | answerable: 8000 VND theo r2; r1 bị supersede |
| C011 / T02 / Q6 | Cùng wording C009 | W14; AC | answerable: 8000 VND tại inclusive known_from |
| C012 / T02 / Q7 | Cùng wording C009 | W14; L_CONFLICT | unresolved_conflict; hai top-rank reports 200000/240000; amount=null |
| C013 / T02 / Q7 | Cùng wording C009 | W14; L_RETRACT | insufficient_evidence sau retract; không suy revenue=0 |
| C014 / T03 / Q4 | “Theo riêng rule auto-accept của {P151}, {D_A} có thỏa điều kiện tại checkpoint cuối {WA14} không? Nếu có, văn bản nêu đến khi nào?” | WA14 | answerable: condition_met=true, literal “đến 23h59”; program + AR=49/100 + clause |
| C015 / T03 / Q4 | Như C014, thay WA14 bằng WA15 | WA15 | answerable: condition_met=false; AR=1/2 không dưới 1/2 |
| C016 / T03 / Q7 | Cùng wording C014 | WA14; L_WRONG_WINDOW | insufficient_evidence; full-day AR không trả lời checkpoint window |
| C017 / T04 / Q1 | “Theo FAQ {P05}, mốc thời gian nào quyết định khung giờ quy đổi điểm của chuyến?” | A1 | answerable: customer_request_time; `s05.clock` |
| C018 / T04 / Q1 | “Theo FAQ {P05}, đơn vị tính điểm cho đơn giao nhiều điểm là gì?” | A1 | answerable: completed_delivery_points; `s05.units` |
| C019 / T04 / Q1 | “Theo FAQ {P05}, không có đánh giá có bị tính 0 sao không, và kết quả thưởng giữa các tuần có cộng dồn không?” | A1 | answerable: không coi unrated là 0; các tuần độc lập, kỳ Thứ Hai–Chủ Nhật; `s05.unrated + week + rating` phần cần thiết |
| C020 / T05 / Q4 | “Theo riêng điều kiện rating trong {P05}, rating báo cáo của {D_A} trong {WW0} có đạt ngưỡng không?” | WW0 | answerable: rating_condition_met=false; 97/20 không lớn hơn 97/20 |
| C021 / T05 / Q4 | Như C020, thay WW0 bằng WW1 | WW1 | answerable: rating_condition_met=true; 49/10 > 97/20 |
| C022 / T05 / Q7 | Như C020, thay WW0 bằng WW2 | WW2 | insufficient_evidence cho so sánh; report explicit undefined/no_observations, không 0 sao |
| C023 / T06 / Q1 | “Thông báo {P23} nêu nhóm tài xế và các Depot nào trong phạm vi?” | A1 | answerable: Taxi, Depot HCM 1/6/7, HCM theo địa giới cũ; `s23.scope` |
| C024 / T06 / Q1 | “Thông báo {P23} nêu áp dụng từ kỳ lương nào?” | A1 | answerable: literal kỳ lương tháng 6/2026; không tự quy đổi UTC interval |
| C025 / T07 / Q4 | “Xét program và membership tại {Tf}, {D_C} có thuộc nhóm được nêu trong edition {P23} không?” | Tf; A0 | answerable: in_notice_scope=true; taxi_driver + MEMBER_OF F1 + registry + clause |
| C026 / T07 / Q4 | Như C025, thay D_C bằng D_D | Tf; A1 | answerable: in_notice_scope=false; F2 không trong nhóm nêu; không suy còn được thưởng |
| C027 / T07 / Q4 | Như C025, thay D_C bằng D_A | Tf; A1 | answerable: in_notice_scope=false; bike_partner, short-circuit hợp lệ |
| C028 / T07 / Q6 | Cùng wording C025 | Tf; A1 | answerable: in_notice_scope=false; corrected membership F2. C025/C028 là known-time pair |
| C029 / FND:aggregate / Q3 | “Tính chính xác cancel_rate_30d của {D_B} tại {Tm} theo definition được cấp, kèm bằng chứng population và coverage.” | W30; A1 | answerable: 1/5; 2 cancelled / 10 terminal trips, complete coverage |
| C030 / FND:bridge / Q5 | “Theo {S_BRIDGE}, {D_B} có thỏa rule tại {Tm} không? Cần bằng chứng về fleet_region và ngoại lệ.” | Tm; A1 | answerable: applies=true; MEMBER_OF→BASED_IN, clause và no-open-incident coverage |
| C031 / FND:bridge / Q7 | Cùng wording C030 | Tm; L_NO_BRIDGE | insufficient_evidence; thiếu BASED_IN, OPERATES_IN không thay thế |
| C032 / FND:entity_resolution / Q7 | “Minh thuộc Depot nào tại {Tm}?” | Tm; A1; entity_refs rỗng | ambiguous_request; D_E/D_F cùng tên, không tự chọn dù cả hai cùng fleet |
| C033 / FND:state / Q2 | “Trạng thái {D_G} tại {T_future_minus_1us} là gì theo thông tin được phép biết?” | valid=`2026-09-17T16:59:59.999999Z`; A0 | answerable: active; future-effective record chưa làm status đổi sớm |
| C034 / FND:state / Q6 | Như C033, thay instant bằng T_future | valid=`2026-09-17T17:00:00Z`; A0 | answerable: suspended; exact `[from,to)` và local midnight |
| C035 / FND:event / Q7 | “Terminal outcome của chuyến {trip_D_G_0} của {D_G} là gì?” | A0; user cung cấp trip ID | insufficient_evidence; trip chưa known, không kết luận cancelled/nonexistent |
| C036 / FND:event / Q6 | Cùng wording C035 | A1 | answerable: completed; late event source đã visible |
| C037 / FND:state / Q2 | “Operating region của {D_E} tại {T_hist} là gì theo snapshot được yêu cầu?” | valid=`2026-08-01T12:00:00Z`; known=`2026-08-04T00:00:00Z` | answerable: HCM_OLD theo source lúc đó; khác final world truth |
| C038 / FND:state / Q6 | Cùng wording C037 | cùng valid; known=`2026-08-06T00:00:00Z` | answerable: HN theo correction; lịch cũ vẫn truy vấn được ở prefix trước |
| C039 / FND:aggregate / Q3 | “cancel_rate_30d của {D_H} tại {Tm} có trạng thái và giá trị nào theo definition được cấp?” | W30; A1 | answerable: metric_status=undefined, value=null; denominator=0 được chứng minh bởi complete empty population; không numeric 0 |
| C040 / FND:aggregate / Q7 | Cùng wording C029 | W30; L_NO_COVERAGE | insufficient_evidence cho exact aggregate; 10 records không tự chứng minh đầy đủ |
| C041 / FND:policy_version / Q6 | “Tại {T_policy_boundary}, phiên bản nào của policy tổng hợp {S_VERSION} có hiệu lực, và yêu cầu operating_region nào?” | valid=`2026-09-14T17:00:00Z`; A0 | answerable: v2, HCM_OLD; issued/version/valid-time proof. Không dùng real policy history |
| C042 / FND:bridge / Q4 | Như C030, thay D_B bằng D_F | Tm; A1 | answerable: applies=false; exception clause + open incident proof đủ để bác bỏ |

Mỗi request công khai chứa thời gian và known cutoff tương ứng; không yêu cầu reader đoán từ thứ tự câu hỏi. C007/C008/C012/C013/C016/C031/C040 không nói nguồn đã bị mask. C035 có trip ID được người hỏi cung cấp; không phải agent tự được truy cập hidden world ID.

### 5.2. Root scenarios, siblings và totals

Các case trong mỗi ô dưới cùng root scenario; mỗi `(root,ledger)` có một ScenarioManifest variant. Case cùng ledger nhưng khác valid/known time vẫn cùng variant.

| Root alias private | Cases | Task/foundation | Variant ledgers |
| --- | --- | --- | --- |
| SC01 | C001–C002 | T01 | L0 |
| SC02 | C003/C007/C008 | T02, ngày W11 | L0, L_NO_OPDAY, L_WRONG_DRIVER |
| SC03 | C004 | T02, W12 | L0 |
| SC04 | C005 | T02, W13 | L0 |
| SC05 | C006 | T02, W10 | L0 |
| SC06 | C009–C013 | T02, W14 | L0, L_CONFLICT, L_RETRACT |
| SC07 | C014/C016 | T03, WA14 | L0, L_WRONG_WINDOW |
| SC08 | C015 | T03, WA15 | L0 |
| SC09 | C017–C019 | T04 | L0 |
| SC10 | C020 | T05, WW0 | L0 |
| SC11 | C021 | T05, WW1 | L0 |
| SC12 | C022 | T05, WW2 | L0 |
| SC13 | C023–C024 | T06 | L0 |
| SC14 | C025/C028 | T07, D_C | L0 |
| SC15 | C026 | T07, D_D | L0 |
| SC16 | C027 | T07, D_A | L0 |
| SC17 | C029/C040 | aggregate, D_B | L0, L_NO_COVERAGE |
| SC18 | C030/C031 | bridge, D_B | L0, L_NO_BRIDGE |
| SC19 | C032 | entity_resolution | L0 |
| SC20 | C033/C034 | state, D_G | L0 |
| SC21 | C035/C036 | event, D_G | L0 |
| SC22 | C037/C038 | state, D_E | L0 |
| SC23 | C039 | aggregate, D_H | L0 |
| SC24 | C041 | policy_version | L0 |
| SC25 | C042 | bridge, D_F | L0 |

Expected cardinalities: **25 roots, 32 ScenarioManifest rows, 42 semantic cases, 42 renderings, 8 ledger timelines, 12 public snapshot packages**. L0 có 5 cutoffs (A0, AC, A1, 04/08, 06/08); mỗi alternate ledger có một cutoff A1. Toàn bộ roots dùng chung một `split_group` của W0/cohort, split=dev. Không chia C009/C010 hoặc C025/C028 sang các splits khác, cũng không coi 25 roots là 25 observations thống kê độc lập khi cùng shared history.

| Axis | Exact composition |
| --- | --- |
| Task | T01=2; T02=11; T03=3; T04=3; T05=3; T06=2; T07=4; FND=14 |
| Gold track | source_grounded=7; conditional_binding=21; synthetic_control=14 |
| Expected status | answerable=32; insufficient_evidence=8; unresolved_conflict=1; ambiguous_request=1 |
| Primary query family | Q1=7; Q2=2; Q3=2; Q4=12; Q5=1; Q6=8; Q7=10 |

Negative/missing rows mang Q7 primary để giữ taxonomy; `secondary_tags` giữ underlying task/family và temporal/report-window/bridge/retraction facets. Pilot không cần mỗi task đủ mọi status một cách máy móc: thiếu annotation hoặc thiếu real history không là một no-answer fixture hợp lệ.

### 5.3. Công thức và proof contract

\[
F_{REV}(R)=\frac{\max(280000-R,0)}{5};\quad
F_{AUTO}(p,AR)=[p=\mathrm{bike\_partner}]\land[AR<1/2];\quad F_{RATING}(r)=[r>97/20].
\]

F_REV chỉ tính khi E = Bike program ∧ operating_region HN phủ W ∧ RM_OPDAY(W)=true được chứng minh. E=false ⇒ answerable/not_applicable, amount=null; E unknown/conflict ⇒ status tương ứng, không thực hiện phép tính. Revenue thiếu/conflict cũng chặn amount khi cần. Rational arithmetic exact; số tiền mẫu nguyên VND, không suy production rounding.

F_SCOPE = taxi_driver ∧ MEMBER_OF ∈ {những Depot được clause P23 nêu}, với registry mapping và time constraints. T05 dùng rate đã báo cáo, không suy số người đánh giá. Derived `cancel_rate_30d = N_cancelled/(N_cancelled+N_completed)` resolve trip identity/source revision trước window filter; denominator=0 ⇒ undefined, không 0.

Boolean composition dùng đúng T/F/U/C và short-circuit của 02 §13; các công thức không cho phép biến missing/conflict thành boolean false. World answer giữ riêng với answer có thể chứng minh tại known cutoff.

GoldAnswer giữ expected status, answer scope, typed value/unit, world answer riêng, missing roles/conflict groups và proof refs. Semantic proof gồm AND/OR và alternative minimal sets. Case-level semantic proof được materialize thành `EvidenceProof` có `query_id` đúng schema 02; không đổi các fields business đã freeze. Không dùng Graphiti UUID/chunk ID làm atom ID.

Answerable proof phải sound và sufficient; bỏ một atom thiết yếu khỏi mỗi minimal set làm mất sufficiency. Với short-circuit false, không bắt lấy mọi premise không còn quyết định. C039 cần definition và complete coverage/source-set manifest rỗng, **không có proof rỗng**. Cases U/C/M lưu available evidence/missing roles/conflict/candidate identities; không chấm Complete=1 vì tập yêu cầu rỗng.

`Complete(C,q)` và `Complete(E,q)` tiếp tục tách candidate retrieval và context selection theo 01/04. Negative cases có status/evidence diagnostics riêng. Traces reasoning, citations và costs thuộc run, không phải đầu vào tính gold.

## 6. Exact output files và public/private boundary

Root release là `data/gsm-dev-core-0.2/`. JSON/JSONL dùng UTF-8, LF, timestamps UTC microseconds, rationals reduced; JSONL một record/object mỗi dòng. Parquet giữ nested logical types theo 02, không serialize nested payload thành chuỗi không có schema. Dataset schema registry phải mô tả logical type và key của từng file; thứ tự row không thay source semantics.

### 6.1. Bản release offline

| Required path dưới root | Nội dung / cardinality / quyền đọc |
| --- | --- |
| `private/oracle/entities.parquet` | Entities và name histories của W0; 8 DRIVER; tagged records theo types của 02 |
| `private/oracle/events.parquet` | 80 distinct terminal WorldEvents; incident/state lifecycle theo WorldFact; không nhân events theo branch |
| `private/oracle/temporal_facts.parquet` | True states/relations/incident status; đúng final-world cardinality |
| `private/oracle/policy_rules.jsonl` | AST S_BRIDGE và S_VERSION versions; không chứa policy thật đã “render lại” |
| `private/oracle/task_bindings.jsonl` | Đúng 7 active bindings B01–B07@1.0; clauses/conventions/answer_scope từ 02 |
| `private/oracle/world_metrics.parquet` | True aggregates và event IDs; chỉ diagnostic, không lấp public missing data |
| `private/oracle/reported_values.jsonl` | Inputs reports/revisions §4.2, typed và versioned |
| `private/oracle/observation_plan.jsonl` | Source releases, branch delta/dependency masks và target lineage |
| `private/eval/scenarios.jsonl` | 32 ScenarioManifest rows, 25 root IDs |
| `private/eval/semantic_cases.jsonl` | 42 cases, unique primary keys |
| `private/eval/query_renderings.jsonl` | 42 direct renderings; templates/hash trace |
| `private/eval/queries.jsonl` | 42 QueryGold records theo 02; private family/tags và refs |
| `private/eval/gold_answers.jsonl` | 42 GoldAnswer records, statuses theo §5.2 |
| `private/eval/support_atoms.jsonl` | Deduplicated semantic atoms, không dựa text phrasing |
| `private/eval/proofs.jsonl` | Một query-bound proof record mỗi query; negative diagnostics thay empty sufficient proof |
| `private/eval/support_links.jsonl` | GoldSupportLink source IDs/versions/clause spans; private |
| `private/eval/entity_resolution.jsonl` | Gold entity candidates/constraints; C032 giữ hai ứng viên |
| `private/eval/splits.jsonl` | Một row/query: query_id, scenario_id, split_group, split=dev |
| `private/eval/policy_audit.json`, `review_manifest.json` | Audit AM1–AM4, row→binding và span review trace của nguồn đã pin |
| `private/eval/corpus_roles.jsonl` | 224 source-level rows: audited/primary-gold flags và reviewed span refs; chỉ evaluator, không relevance mặc định |
| `private/eval/relevance_judgments.jsonl` | Query/source/span judgments theo §6.6; có thể rỗng trước pooled review, không bịa qrels |
| `private/eval/relevance_protocol.json` | Protocol/version/unit/unjudged policy và qrels universe/pool provenance theo §6.6; không là retrieval output hoặc gate PASS giả |
| `private/eval/validation.json` | Machine-readable check IDs, pass/fail, expected/actual, implicated IDs và messages; không tự viết PASS trước khi chạy |
| `private/eval/manifest.json` | Release state/versions/seed/config, source/spec/code hashes, counts, file inventory, `logical_table_schemas`, ledger registry `ledgers[]` của §3.1 và validation digest |
| `public/operational/entity_catalog.jsonl`, `source_registry.jsonl` | Published registry và public authority rules; archive có history, runtime phải lọc |
| `public/operational/record_ledger.parquet` | Base L0 full timeline, immutable records theo 02 |
| `public/operational/text_observations.jsonl` | Một narrative/SourceRecord L0; giữ source ID, record ID, temporal meaning và revision targets |
| `public/operational/variants/{ledger_id}/record_ledger.parquet` | Một full alternate timeline cho mỗi 7 non-base ledgers. Không concatenate variants |
| `public/operational/variants/{ledger_id}/text_observations.jsonl` | Narratives tương ứng, cùng visible information với structured ledger branch |
| `public/operational/artifacts/{artifact_id}.json` | Immutable coverage/source-set/metric/profile artifacts được publication records tham chiếu; chỉ xuất khi có record thật |
| `public/documents/raw/{snapshot_id}.md` | 224 real snapshots, bytes không đổi; từng bài đúng archive inventory |
| `public/documents/normalized/{document_revision_id}.md` | 224 normalized real revisions + ba synthetic version documents (S_BRIDGE v1, S_VERSION v1/v2) |
| `public/documents/catalog.jsonl` | Toàn inventory snapshot/revision/version metadata, raw/normalized hashes, locators và publication refs; không task IDs/gold labels/private rule AST |
| `public/corpus_profiles/{corpus_profile_id}/manifest.json` | Đúng hai manifests `debug_core`, `retrieval_full`, shape/identity theo §6.2; archive/setup metadata, không mount toàn bộ cho runtime |
| `public/definitions/{definition_id}.md`, `catalog.jsonl` | Đúng 12 definition docs: BC01–BC07, bốn RM, một derived M01; public source provenance và IDs |
| `public/runtime_queries/dev.jsonl` | 42 static RuntimeQuery templates; fields và run-time completion ở §6.3 |
| `public/runtime_queries/test.jsonl` | File rỗng 0 bytes, manifest count=0; không copy dev sang test |
| `public/runtime_manifest.json` | Schema/release version, public file hashes, query→snapshot routing; không private scenario/mutation/gold metadata |
| `public/snapshots/{snapshot_id}/manifest.json` | Visible package identity, scope/cutoff, paths/hashes và completeness of packaging; không gold sufficiency labels |
| `public/snapshots/{snapshot_id}/record_ledger.parquet` | Chỉ prefix của đúng ledger branch tại cutoff |
| `public/snapshots/{snapshot_id}/entity_catalog.jsonl`, `source_registry.jsonl`, `text_observations.jsonl` | Chỉ registry/narratives đã được công bố trong prefix |
| `public/snapshots/{snapshot_id}/documents.jsonl`, `definitions.jsonl`, `artifacts.jsonl` | Visible catalogs/references, không liệt kê future objects. Loader chỉ cấp bytes của những refs này |
| `public/graph_inputs/mode_a/{snapshot_id}.json` | Package manifest trỏ tới structured visible files; là đầu vào adapter, chưa là Graphiti projection |
| `public/graph_inputs/mode_b/{snapshot_id}.json` | Package manifest trỏ tới narratives và nguồn công khai tương ứng; không private repair hints |

Tất cả required JSONL tables phải tồn tại, kể cả empty table hợp lệ có count=0 trong manifest. Patterns chỉ materialize theo IDs trong inventory. Corpus v0.2 chỉ gồm 224 raw articles đã pin, ba synthetic versions và 12 definitions; không thêm corpus tùy ý. Profile chọn 6 hoặc 224 real sources từ inventory này, luôn cùng shared synthetic/definition sources theo cutoff. Clause records/locators có thể nằm trong catalog nested arrays theo logical type của 02; không cần business database mới hoặc clause formalization cho 218 bài bổ sung.

### 6.2. Snapshot identity và isolation

Snapshot key = `(dataset_version,world_id,ledger_id,scope_id,known_as_of)`. ID là UUIDv5 từ canonical key; content digest ghi riêng để tránh vòng hash tự tham chiếu. Hai queries cùng key dùng chung canonical package; chỉ reuse document index khi active profile/hash và projection config cũng giống nhau. Exact manifest inventory chốt số packages từ distinct keys của catalog, không tạo một index mỗi query theo mặc định.

Prefix gồm records `known_at ≤ known_as_of` và đúng scope. Reducer suy `known_to` **chỉ từ prefix này**; historical export không được mang closing boundary mà chỉ future correction mới xác lập. Future-valid records đã known được giữ; future-known records bị loại. Public entity catalog, names, registry, docs, coverage và source-set members đều phải cùng cutoff. Source adapter không được bypass bằng đọc full ledger.

Root `public/operational/` là archive để đóng gói/replay, **không phải mount root mặc định của agent**. Runtime chỉ được đọc snapshot package được chọn và bytes của visible refs qua resolver có allowlist. Public snapshot manifest không chứa filepaths private, private task bindings hoặc danh sách missing roles. Gold/evaluator chạy ở boundary riêng.

Queries không ghi trở lại operational memory. Có thể reuse một index cho các queries cùng package/config, nhưng answers, previous gold hoặc generated conversations không được trở thành nguồn cho câu sau. State/history của một ledger branch không được chia sẻ với branch khác ngoài immutable inputs đã được manifest chỉ định.

Ràng buộc đặc biệt cho L_NO_BRIDGE: tên registry “Depot Hồ Chí Minh 6” là nhãn identity, không là authority cho relation BASED_IN hiện hành. Synthetic definition của operand `fleet_region` nêu rõ cần assignment BASED_IN có source/time. Generator phải kiểm không có alternative fact/artifact đã công bố đủ chứng minh relation bị mask.

**Profile manifest contract.** `public/corpus_profiles/{corpus_profile_id}/manifest.json` là closed object, mọi field sau required/non-null; không có field self-hash:

| Field | Type / constraint |
| --- | --- |
| `schema_version` | string const `1.1` |
| `release_spec_version` | string const `0.2.0` |
| `dataset_version` | string const `gsm-dev-core-0.2` |
| `corpus_profile_id` | enum `debug_core/retrieval_full`, khớp directory |
| `corpus_profile_version` | string const `1.0` |
| `real_snapshot_ids` | unique sorted string array; 6 audited IDs hoặc đủ 224 inventory IDs; FK SourceDocumentSnapshot |
| `shared_document_revision_ids` | unique sorted string array; đúng 3 synthetic version revisions; FK DocumentRevision |
| `definition_ids` | unique sorted string array; đúng 12 definition IDs; FK definition catalog |
| `source_catalog_sha256` | 64 lowercase hex, actual bytes của public/documents/catalog.jsonl |
| `source_archive_sha256` | 64 lowercase hex, bằng archive pin §2.1 |
| `normalization_version` | string const `crlf-to-lf-v1` |
| `counts` | closed object `{real_articles: integer, synthetic_versions: 3, definitions: 12}`; real_articles=6 hoặc 224 khớp profile và arrays |

`corpus_manifest_sha256` là SHA-256 actual manifest bytes, ghi ngoài object trong release/run inventory. Cùng ID/version nhưng khác bytes không là cùng profile release. Runtime document allowlist = **active-profile source members ∩ canonical snapshot visible source refs ∩ access scope**. Resolver-by-ID, BM25/dense indexes, reranker source expansion và caches đều thực thi cùng allowlist. Nguồn được biết nhưng bị profile loại không được bypass bằng direct read. ARTIFACT_PUBLICATION metadata trong canonical prefix không tự cấp quyền đọc bytes ngoài profile.

Full catalogs và profile manifests là archive/setup inputs của trusted loader, không là nguồn agent được đọc. Runtime chỉ nhận resolved active-profile refs đã qua cutoff; không lộ future IDs/headers, private corpus roles hoặc manifests của profile khác. Canonical package và 8 source ledgers chứa 224-source publication plan chung; chọn profile không sửa bytes, commit_seq, branch semantics hoặc public_snapshot_id. `ScenarioManifest.public_snapshot_refs` vì vậy không nhân theo profile. Các refs operational/coverage không phải policy document vẫn tuân snapshot contract cũ.

Document index/cache identity tối thiểu là `(dataset_version,public_snapshot_id,corpus_profile_id,corpus_manifest_sha256,document_projection_config_hash)`. Graph identity dùng canonical operational inputs/config, giữ nguyên trong paired document-corpus run. Không reuse document index/cache giữa hai profiles chỉ vì public_snapshot_id giống nhau. Manifest chứa sources trước khi chúng visible không có nghĩa có quyền index sớm.

### 6.3. RuntimeQuery template và run request

Không buộc Data Freeze pin model/hardware/context budget của baseline. File query chứa **static template**, chưa phải request hoàn chỉnh theo 01:

| Field | Ai cấp / quy định |
| --- | --- |
| `query_id`, `query` | Renderer; không chứa case/task/fault aliases |
| `entity_refs` | Canonical IDs người dùng/app thực sự cấp; C032 rỗng |
| `time_scope` | Chỉ modes `current/point/interval` của 01. State tại instant dùng point; measurement window dùng interval. Content-only và event-ID lookup dùng current, với benchmark current clock resolve thành known_as_of và ghi vào trace; không giả policy có hiệu lực tại ngày đó |
| `known_as_of`, `access_scope` | Explicit case cutoff và S0 |
| `application_context` | Public definitions/edition/window/answer-scope premises; không trả trước điều kiện hoặc kết quả |
| `query_type_hint` | null cho pilot; router không được đọc `primary_family` private |
| `request_id`, `context_token_budget`, `deadline`, `retrieval_config_id` | Run assembler cấp từ pinned run manifest; retrieval_config_id resolve active corpus profile/version/hash, không lấy từ gold. Deadline từ timeout budget của run, không từ logical known time. Thiếu field required hoặc profile pin phải fail validation |

Với content-only query, answer_scope là nội dung edition, nên temporal check là source availability tại cutoff, không phải current normative applicability. Với event-ID lookup, tìm phiên bản của đúng event theo known cutoff, không lọc bỏ một point event chỉ vì nó khác current instant. Một policy snapshot ID được người dùng chỉ định không cho phép vượt access/availability. Package không tồn tại, field thiếu hoặc scope sai phải trả runtime error riêng, không chấm là insufficient_evidence.

### 6.4. Source-level locators và projection-level locators

| Locator / link | Dataset artifact — có trước system run | Run artifact — tạo khi build/index/run hệ thống |
| --- | --- | --- |
| Document source locator | Snapshot/document revision ID, raw/normalized hashes, clause/span, coordinate system và publication ref | Chunk ID + span mapping + chunker/tokenizer config hash sau khi chunk thực sự được tạo |
| Operational source locator | world/ledger/scope, record_id/assertion_id, source/version, payload hash và logical known/valid extents | Graphiti node/edge/episode UUID + source mapping sau khi projection thực sự được tạo |
| Artifact source locator | Artifact ID/hash, publication record, definition/window và dependency/source-set refs | Runtime computation/context unit ID và mapping tới source artifacts tương ứng |
| `GoldSupportLink` | **Private:** atom → canonical source refs/reviewed spans/equivalent supports; required để kiểm gold | Evaluator kết hợp với actual source→projection mappings khi chấm run |
| `ProjectionLink` | **Không phải required dataset artifact hoặc DFG input** | `runs/{run_id}/projection_links.jsonl`: canonical_source_id/version, projection_kind/id, locator, projection_config_hash, snapshot_id theo 02 |

Generator MUST NOT xuất fake chunk IDs, Graphiti UUIDs hoặc fabricated ProjectionLink để làm Data Freeze pass. Deterministic UUID algorithm có thể dự đoán một ID; nó không chứng minh object đã tồn tại hay giữ đúng identity/time/provenance. ProjectionLink chỉ được ghi sau bước tạo projection thực tế, có config và source refs kiểm lại được. Chunking/index build có thể diễn ra trước agent query đầu tiên; các IDs đó vẫn là run artifacts.

Canonical DocumentRevision hoặc synthetic policy text được sinh trong dataset vẫn là source artifact hợp lệ, kể cả 02 dùng từ “document projection” cho bước render AST. Ranh giới ở đây là **canonical source identity so với system-specific retrieval-unit identity**, không phải cấm mọi bước có tên projection. `public/graph_inputs/mode_a|mode_b/` chỉ là input package manifests, không chứa output UUIDs hoặc lời chứng nhận Graphiti conformance.

### 6.5. Run outputs — không thuộc Data Freeze

`runs/{run_id}/` tạo sau: `manifest.json`, `projection_links.jsonl`, `ingestion_receipts.jsonl`, `traces.jsonl`, `metrics.json`. Manifest pin git commit, dataset hash, corpus_profile_id/version/corpus_manifest_sha256, document index identity, operational graph input hash, qrels/protocol version, package/backend/model versions, embeddings, reranker, Graphiti config, budgets, top-k, hardware và concurrency. Traces ghi query/snapshot, raw candidates/scores, temporal filtering, selected context, token/call costs, latency breakdown, final answer/citations và evaluator results. Gold-enriched traces chỉ evaluator được đọc.

Chunk IDs, Graphiti UUIDs, embeddings, actual index size, wall-clock ingestion receipt và search performance không được bịa trong dataset release. Mode A/B manifests có thể hợp lệ trước khi adapters tồn tại; đó không là bằng chứng adapter conformance.

### 6.6. Relevance judgments và profile comparison

Relevance là quan hệ query–source/version/span dưới source/scope constraints, không phải nhãn cố định của document. `Unreviewed ≠ irrelevant`; cùng text nhưng sai snapshot được yêu cầu không hoàn thành proof. Với T01–T07, source-bound primary proof vẫn thuộc reviewed spans đã whitelist. Alternative support cho các atoms khác chỉ được nhận sau review đúng role/provenance; không tự thêm primary-gold source hoặc business task. Nếu review cần thay gold/proof semantics, phát hành affected-gold release mới.

`relevance_judgments.jsonl` có các fields required: `judgment_id` (ID), `query_id` (FK), `canonical_source_ref` (source/version/locator theo 02), `status` (`judged/unjudged`), `relevance` (integer 0/1/2 nếu judged, null nếu unjudged), `reason` (nonempty string), `reviewer_ref` (string khi judged, null nếu unjudged), `protocol_version` (string), `corpus_manifest_sha256` (hash của profile được review). Key `(query_id,canonical_source_ref,protocol_version,corpus_manifest_sha256)` unique; không dùng chunk ID làm semantic identity. Missing row là unjudged, không implicit negative. Source-mismatch có thể judged=0 khi request thực sự loại nguồn đó; phải ghi constraint làm căn cứ.

`relevance_protocol.json` ghi `protocol_version`, `relevance_unit=canonical_source_span`, `unjudged_policy=explicit_na`, `qrels_universe_description`, `pool_run_refs`, `pool_depth` và review/rubric provenance. Trước khi chạy retrieval, pool_run_refs rỗng, pool_depth=null và universe ghi reviewed supports hiện có; không tạo pool/chunk IDs giả. Các evaluation files này private. DFG cần protocol và source gold hợp lệ, không cần full qrels hoặc baseline retrieval.

Mặc định báo Recall/Complete/Coverage với `support_basis=reviewed_gold`, cùng giới hạn khi alternatives chưa được adjudicate; không gọi đây là exhaustive corpus recall. Nếu candidate có unresolved alternative có thể đổi kết luận proof completeness, ghi evaluation_status=unjudged thay vì chắc chắn system failure. Precision@K cần judged top-K returned positions; MRR@K cần đủ labels xác định first relevant; nDCG@K cần frozen qrels universe và ideal DCG. Metric thiếu judgments trả `N/A (incomplete_judgments)` theo 01 §8.2. Báo judged/unjudged counts, số queries đủ điều kiện chấm và mẫu số planned; không drop unjudged khỏi ranking hoặc dùng relevance=0 mặc định. Pool từ top results các baselines có thể giảm công review, nhưng phải pin pool/labels trước paired comparison; bổ sung labels sau freeze dùng annotation extension/version mới, không overwrite release.

Trace bắt buộc ghi corpus inventory counts, visible-profile document/chunk counts, policy document/chunk counts sau edition filter, raw/reranked/selected candidate counts, filter reasons, Complete(C)/Complete(E), selection loss, wrong-source/scope evidence, judgment coverage, latency/token/call/index cost. Counts trước edition filtering vẫn phải sau access/known-time eligibility; không search future corpus rồi mới lọc cho hợp lệ. Báo document/hybrid slices riêng; KG-only query không nhận credit vì tăng corpus. Reader, budget, construction mode và operational graph hash giữ cố định trong paired profile diagnostic; các runs có 42 planned cases/profile nhưng vẫn chỉ 42 semantic cases, không 84 samples độc lập.

## 7. Generator stages và reproducibility

Pipeline bắt buộc giữ thứ tự **source/binding → structured world/ledger → semantic cases/proofs → public projections → query rendering → validation/split/package**. Đây là build pipeline offline, không đổi kiến trúc runtime.

| Stage | Input → output | Completion check |
| --- | --- | --- |
| G0 Pin sources/spec | 224 raw articles + 02/05 → complete source catalog, hai profile manifests, audited spans/definition templates | Archive/raw/normalized hashes đúng; 6 audited/4 primary-gold sources; no aggregate index/no arbitrary sources; tasks T01–T07 |
| G1 Build world | Recipe §4, seed/config → entities/events/WorldFacts/reports/synthetic ASTs | 8 drivers/80 distinct trips; clean-world cardinality; exact rationals |
| G2 Publish timelines | Observation plan → L0 và 7 alternate ledgers, coverage/artifact publications, 224 snapshot availability assertions | Immutable commits; authorized publications; same operational semantics; branch closure và known cutoffs sound |
| G3 Freeze semantic cases | 25 roots/32 variants + §5 → 42 semantic cases, gold/proof/atoms/source links | Independent observable reducer + clause bindings; expected table khớp, không gọi Graphiti |
| G4 Render projections | Visible canonical records → narratives, synthetic texts, snapshot packages, A/B input manifests | Source/time/IDs/provenance preserved; real docs không rewritten; no oracle leakage |
| G5 Render requests | Semantic cases + public context → 42 direct query templates | Wording không tự cấp đáp án; case/rendering links đầy đủ; no hidden labels |
| G6 Validate and package | Tất cả outputs → split table, validation report, manifests/hashes | Data Freeze checks pass; rerun cùng config tái sinh logical content |

Pin root seed=42 và `seed_algorithm=sha256-stream-v1`: mỗi component seed là 64 bits đầu (big-endian) của SHA-256 UTF-8 chuỗi `42|stream_name|stable_component_id`. Record algorithm/code version; không phụ thuộc số threads hoặc thứ tự gọi RNG. Core recipe/templates là deterministic; seed chủ yếu giữ extension reproducible, không randomize các counts/boundaries đã chốt.

Record IDs được cấp theo stable component keys trước rendering. Tạo union của mọi planned record trong L0 và các branches, sort `(known_at,source_id,record_id)` rồi gán `commit_seq` một lần. Prefix/branch chỉ chọn subset và **giữ nguyên seq, kể cả gaps**; không renumber shared records sau mask. Replay theo `(known_at,commit_seq)`. Tie-break chỉ cho commits độc lập; không giải quyết fact conflicts bằng sort order. Targets phải known strictly earlier theo 02.

Raw file hashes dùng bytes. Logical table hash dùng rows sort theo primary key, canonical JSON keys sorted, compact separators, UTF-8, rational/UTC normalization. Pin serializer/runtime/Parquet engine versions và compression; rebuild cần logical hashes giống nhau, không bắt Parquet bytes giống giữa hai toolchain khác nhau. Release đã freeze luôn có actual byte hashes để bảo vệ artifact cụ thể. Manifest không hash chính nó trong file inventory; external release digest hash manifest bytes sau khi hoàn thiện.

Nếu phát hiện source/proof bug: sửa recipe/binding trong đúng phạm vi, regenerate affected dataset version và ghi changelog. Không sửa expected answer dựa trên output baseline/proposed, không chọn seed vì một hệ thống đạt điểm cao hơn. Stress/wording variants về sau thêm version và paired lineage; không rewrite dev release đã pin.

## 8. Validation contract

### 8.1. Checks bắt buộc cho dữ liệu

`private/eval/validation.json` có `check_id`, `scope`, `status=pass/fail/not_run`, expected/actual, error IDs và artifact hashes. Validation phải thực thi; bảng spec này không là kết quả test. Failure không được chuyển thành warning để freeze.

| Check group | Invariants 02 | Required assertion |
| --- | --- | --- |
| V01 Identity/shape | I01/I02/I19/I27 | FK/types/scopes hợp lệ; SM01–SM08 của §3.4 pass; đúng 8/80/42, 25 roots/32 variants/8 ledgers; chỉ closed predicates; counts logical/physical tách nhau |
| V02 Ledger | I03/I04/I07/I23 | Old bytes bất biến, target known/active/authorized, atomic replace, unaffected intervals còn; conflict không latest-wins |
| V03 Time/isolation | I05/I06/I20 | Point/interval/unknown/unbounded phân biệt; boundary inclusive/exclusive đúng; không leak future record/catalog/known_to/document |
| V04 Measures | I08/I09/I10/I22/I24 | Unique trip identity trước window; exact reported window/version; coverage complete mới exact/absence; false/0/undefined/missing/conflict khác nhau |
| V05 Documents/audit | I12/I21/I25/I26/I28 | Đủ 224 sources, profiles đúng 6/224, audited=6/primary-gold=4; hash/span/review/availability đúng; no unreviewed OCR gold; fixed edition không current-policy claim; no fabricated supersession |
| V06 Gold/proofs | I13/I15/I16/I17 | Sufficient proofs đúng source/time/role; short-circuit hợp lệ; no empty-proof credit; hybrid không giải bằng precomputed verdict |
| V07 Artifacts/branches | I10/I11 | Mask closure không còn gold alternative; no false complete coverage; stale dependencies được đánh dấu; no hidden oracle repair |
| V08 Packaging | I06/I15/I18/I20 | Snapshot ∩ profile ∩ scope allowlist khép kín; future/other-profile sources không bypass; public request không gold roles; seeded hashes đúng; query→case→variant→prefix/profile traceable |
| V09 Projection input parity | Phần input của I14 | A/B cùng active profile/cutoff; narratives giữ ID/time/targets; paired profiles giữ operational graph input hash; chưa chứng nhận actual graph |
| V10 Profile/gold compatibility | I13/I15/I16/I17/I26 | 42 case semantics/status/proofs giữ đúng trên cả active views; primary support visible trong cả profiles khi case cho phép; no private-role filter; protocol không implicit-negative unjudged; thiếu full qrels không tự fail DFG |

Có hai cơ chế kiểm độc lập: expected fixture table/hand arithmetic và reducer/evaluator implementation. Với cả hai dùng chung một helper sai, test “evaluator bằng generator” không đủ; test boundaries/short-circuit và mutation checks phải có expected outcomes cố định từ spec. Gold sinh trước Graphiti và không dùng model judge làm nguồn chân lý duy nhất.

### 8.2. Auxiliary conformance fixtures

Port **đúng 25 EX01–EX25 của 02 §17.2** thành offline tests, mỗi fixture giữ isolation và dates/premises của ví dụ gốc. C003…C031 có thể dùng các mẫu tương tự nhưng không phải bản sao nguyên byte của EX: ví dụ release dùng W11 cho positive và W14 cho correction để chung một world. Không tính 25 tests này vào 42 queries hoặc 80 trips.

Aux fixtures nằm trong test implementation, với input hashes/expected outcomes/check IDs được ghi ở validation report. Không trộn chúng vào root release public corpus. Các fixtures ngoài EX tối thiểu sau phải có data/reference check; actual adapter/selector checks chuyển sang gate §9.2.

| Auxiliary ID | Fixture và expected check |
| --- | --- |
| AUX_IDENTITY | Same-name drivers và historical alias: không merge IDs; alias chưa published không giúp resolve historical query |
| AUX_TIME | Future effective, late event, valid/known correction split và local midnight: bảo toàn old prefix, unaffected segments; không đóng known interval bằng future knowledge |
| AUX_EVENT | Hai trips cùng subject/relation/object, duplicate observation và corrected event_time: distinct trips được giữ, duplicates không tăng count; resolve identity/conflict trước window |
| AUX_INCIDENT | Open→resolved→reopen cùng incident; same-time boundary đúng; thiếu service/incident coverage không chứng minh absence |
| AUX_REVISION | Retraction không thành false/0; equal-rank conflict giữ unresolved; lower-rank assertion không lấn higher-rank; unauthorized correction bị reject |
| AUX_POLICY | Synthetic version boundary và exception short-circuit; không infer real supersession; missing BASED_IN không thay bằng OPERATES_IN |
| AUX_ARTIFACT | Published profile/metric với dependency set cố định; correction của dependency làm artifact stale, revision có ID/publication mới; default hypotheses=false |
| AUX_CONTEXT | Offline candidate/selection sets có gold proofs: candidate complete nhưng context mất atom ⇒ Complete(C)=1, Complete(E)=0. Chưa chứng minh runtime selector/model behavior |
| AUX_ACCESS | Wrong scope/snapshot hoặc missing required request fields ⇒ explicit error; không no-answer business verdict |

Counterfactual validation trong test sandbox phải chứng minh: đổi fact quyết định đổi gold; đổi distractor không liên quan giữ gold; thêm future record giữ historical prefix; replay cùng prefix cho cùng accepted view. World perturbation tests tạo world IDs khác; không mutate W0 đã đóng gói. Test code/templates/seed và outputs hash được ghi trong manifest, không phụ thuộc trí nhớ của người viết.

## 9. Hai gates độc lập

### 9.1. Data Freeze Gate — DFG

DFG pass khi **tất cả** điều kiện dưới đây có evidence executable. Không yêu cầu baseline đạt accuracy threshold, không yêu cầu Graphiti search hoặc embedding API hoạt động. DFG chỉ kiểm **source-level locators và GoldSupportLink**; không yêu cầu ProjectionLink, chunk IDs, Graphiti UUIDs, projection existence hoặc ingestion receipts. `runs/` chưa tồn tại không làm DFG fail; generator không phải tạo file run artifacts rỗng để đủ inventory.

| ID | Điều kiện pass | Evidence cần lưu |
| --- | --- | --- |
| DFG01 | 224 sources, hai profiles, reviewed spans, definitions và bindings pin đúng | Archive/raw/normalized/profile hashes; catalog; 6-source audit/4-source primary-gold mapping |
| DFG02 | World/ledgers/scenarios/cases/renderings đúng shape và counts | V01–V04 và SM01–SM08 report; 25/32/42 relationships; 8 distinct branch timelines |
| DFG03 | Gold/status/formulas/proofs đúng 42 cases; EX/aux reference fixtures pass | V05–V07; fixed expected tests và minimal-proof checks |
| DFG04 | Snapshot/profile isolation, public/private separation và gold compatibility pass | V08–V10; no future/other-profile leakage; A/B input parity; source locators đủ; không đòi projection IDs hoặc full qrels |
| DFG05 | Split và file inventory complete; repeatable logical generation | 42 dev/0 test; all siblings same group; config/code/seed/toolchain hashes |
| DFG06 | Hai lần build sạch cùng pins cho same logical hashes; mọi required check đã run | Validation status không fail/not_run; release manifest chuyển `state=FROZEN` |

Trước DFG06, state là `DRAFT` hoặc `VALIDATED`, không dùng filename release như bằng chứng freeze. Sau pass, release immutable; sửa dữ liệu/gold dùng version mới. Frozen pilot là development fixture release, **chưa là frozen test benchmark để claim improvement**.

### 9.2. Benchmark Readiness Gate — BRG

| ID | Điều kiện pass | Phạm vi chứng nhận |
| --- | --- | --- |
| BRG01 | DFG pass; baseline/run config/profile/hash và environment được pin | Run reproducible trên đúng release; full baseline dùng retrieval_full |
| BRG02 | Document loader và deterministic Graphiti adapter/search/source links đã qua conformance bắt buộc của 02, gồm actual I14 | Mode/backend được công bố hỗ trợ contract nào; Mode B có report riêng |
| BRG03 | Có query→retrieval→evidence→agent→answer; chạy 42 requests trên retrieval_full, ghi status/metrics/judgment coverage và filtering counts | C0 có thể dùng debug_core; chỉ sáu bài chưa chứng nhận full-profile readiness; không chỉ import hoặc graph.save |
| BRG04 | Candidate vs selected context vs reasoning được đo riêng; oracle-context và failure attribution chạy được | Có thể chẩn đoán thiếu evidence, selector mất proof, hay reader sai |
| BRG05 | Ingestion/read latency, token/call cost, projection/receipt logging đúng và rate-limit/error được ghi riêng | Có instrumentation để mở stress/ablation sau pilot |

Retrieval/answer failures trên một dataset sound là kết quả thực nghiệm, không lý do đổi gold. Conformance thất bại ở một mode/capability phải ghi FAIL/UNSUPPORTED và giới hạn run được phép tuyên bố; API quota chặn là BLOCKED, không capability verdict. Không cấp BRG đầy đủ nếu adapter bắt buộc còn phá identity/time/provenance. Điều này không thu hồi DFG đã pass độc lập.

C0/micro-path được phép dùng `debug_core` để giảm thời gian debug. Document-only `retrieval_full` diagnostic có thể chạy sau DFG khi loader/scorer của nhánh document sẵn sàng, không phải chờ toàn BRG; phải ghi partial-run scope. DFG không chứng nhận search đã hoạt động. Baseline document/hybrid mặc định chuyển sang `retrieval_full` khi pipeline hoạt động; BRG đầy đủ yêu cầu profile này. Full precision/nDCG chưa chấm được vì qrels chưa đủ không tự là adapter failure; báo N/A với coverage, không claim retrieval superiority.

Sau pilot mới thêm paired query styles và scale diagnostics; sau đó tạo Small (~100 drivers/10k trips) cùng dedicated dev/test world groups và locked test manifest. Không nhân 42 paraphrases rồi gọi là 42×N samples độc lập.

## 10. Versioning và bàn giao cho coding agent

| Thành phần | Đã chốt ở spec | Cần điền từ implementation, không được bịa |
| --- | --- | --- |
| Schema/task semantics | 02 v1.1, AM1–AM4, T01–T07, 3 tracks | Không mở business fields trong generator |
| Release composition | World/ledger recipes, 42-query catalog, outputs, sidecar/FK, seed và split | Materialized opaque IDs, actual record/atom/file counts, byte/logical hashes |
| Gold/evaluator | Exact formulas, status rules, proof semantics, expected fixtures | Executable reducer/proof checker, version/commit và validation results |
| Source corpus | 224 pinned articles; debug_core=6/retrieval_full=224; audited=6/primary-gold=4; availability §2.1 | Verify full inventory/hashes, profile manifests, publications/locators; không tải mới thay bản pin, không bịa OCR quality/full qrels |
| Runtime | Graphiti reference, 01/02 request/evidence contract, independent BRG | Package/backend/model/hardware pins, budgets/top-k, timing/cost method |
| Production applicability | Không là mục tiêu chứng minh của pilot | GSM identifiers/schema/source authority thật, query mix/cardinalities/QPS/SLA/access boundaries |

Coding agent triển khai G0–G6 và DFG với cả hai profile manifests; dùng debug_core cho micro conformance, sau đó loaders/run harness trên retrieval_full cho baseline/BRG. Không cần formalize 218 bài thêm; phải kiểm metadata/visibility/gold compatibility và giữ unjudged protocol. Mọi trường chưa materialize ở cột cuối phải được ghi `pending` hoặc `not_run`, không mặc định PASS. Không cần nghiên cứu benchmark design thêm để bắt đầu build release này.
