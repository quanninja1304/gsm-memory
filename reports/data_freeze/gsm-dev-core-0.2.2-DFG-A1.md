# Báo cáo freeze và independent assurance — gsm-dev-core-0.2.2

Ngày kiểm chứng: 2026-09-18  
Checkpoint implementation ban đầu: `75f819abae8dfeea63a136821b6b57c84156afb5`  
Schema: `1.1` · release spec: `0.2.0` · seed: `42`

## Summary

Trạng thái corrective release: **PASS**. Release `gsm-dev-core-0.2.2` đã được
freeze sau hai clean builds độc lập, logical comparison không có mismatch,
DFG01–DFG06 và A1_G1–A1_G6 đều pass. Corrective release không đổi world events,
gold answers hay task semantics; nó đóng các lỗ hổng provenance, coverage
packaging, synthetic-policy publication và independent reconstruction của
`0.2.1`.

Retrieval, Graphiti, embeddings, reranker, reader/agent và BRG không được chạy.

## Corrective changes

- Thêm ba closed `coverage_recipes` vào config `0.2.2`; members luôn được derive
  từ reduced public ledger, không sinh từ expected counts.
- Thay ba artifact dựa trên label legacy bằng source-set/spec/content identities,
  exact digests và publication assertions có payload binding đầy đủ.
- Render `S_BRIDGE:v1`, `S_VERSION:v1`, `S_VERSION:v2` từ canonical AST thành
  sanitized public documents có clause spans/hash và publication binding.
- Materialize năm closed locator types: `document_clause`, `ledger_assertion`,
  `entity_catalog`, `definition_artifact`, `coverage_artifact`.
- Hoàn tất B01–B07 với clauses, definitions, conventions, formulas,
  answer-scope, roles và typed evaluation contract.
- Thêm evaluator độc lập dùng evaluation request + binding + public snapshot +
  source locators; evaluator không đọc `gold_answers.jsonl` hoặc `CaseSpec.answer`.

## Resolved 0.2.2 identities

| Identity | Resolved ID |
| --- | --- |
| World W0 | `2e7c997a-ccf5-5a49-bc46-a6fc0cb50293` |
| Scope S0 | `427b436e-b39c-57f0-90a8-1f838a2170d1` |
| D_B | `c499f934-bfe1-5509-a578-afb09cee357c` |
| D_H | `122a3140-7c98-5136-a732-8a9566cb727d` |
| event source | `4330e39a-f5f2-5566-90c5-8ee983ca8fe3` |
| incident source | `bbd81324-2784-50ce-857b-99c0b6ad4812` |
| derived publisher | `3dcc5e8d-dbd8-5d7b-8f93-ada834da3de3` |

Public outputs contain these opaque IDs, not `D_B`, `D_H` or legacy coverage labels.

## Coverage recipes and materialization

Common publication/completeness cutoff: `2026-09-16T03:00:00.000000Z`.

| Recipe | Subject | Exact window | Members | Outcome counts |
| --- | --- | --- | ---: | --- |
| `terminal_trips_db_w30@1.0` | D_B | `[2026-08-16T17:00:00Z, 2026-09-15T17:00:00Z)` | 10 | completed=8, cancelled=2 |
| `terminal_trips_dh_w30@1.0` | D_H | `[2026-08-16T17:00:00Z, 2026-09-15T17:00:00Z)` | 0 | completed=0, cancelled=0 |
| `incidents_db_through_tm@1.0` | D_B | `[2026-07-01T00:00:00Z, 2026-09-15T17:00:00.000001Z)` | 0 | n/a |

Source sets:

| Source set | ID | Selector digest |
| --- | --- | --- |
| `terminal_trip_outcomes@1.0` | `6e9b8b30-d8b5-5173-b1ae-49062e379838` | `a5a469d873f8722114603e52b9e62645148fa27cab0bc3b0bb0497a99844e226` |
| `driver_incident_memberships@1.0` | `f5b22510-211f-50d3-a98f-fc20faee0b64` | `1c4aea474a49e0fe668b965f88342dc13caadd54ac2e52d1f36d38073f701fce` |

Coverage artifacts:

| Recipe | Artifact ID | Coverage spec ID | Content digest | Members digest | Publication record / assertion |
| --- | --- | --- | --- | --- | --- |
| D_B trips | `709c5ee2-df8e-523c-9477-46603fd35143` | `990e1a9f-897a-508b-b80f-d133969dad64` | `b8697ad082b401c02b5bfbdf7cce022029703cd07a425e3474bf1f556c1f53bc` | `715ce46c83a619ab9826f545db11d305eb237290e87ddc29e094f116ecdd1100` | `40192deb-36c5-5ca3-90f5-61c804553bf6` / `f8fb8de6-27fb-5ec1-a04d-729825e05e4f` |
| D_H trips | `203c9d37-e2c4-5798-826b-35f7ae97f39a` | `9a142a27-8239-5398-af74-8e9df3669e77` | `a329367455b25c69a47b277ca27b49659dbee74921b482f37119acf451bfa970` | `936c4e8e5df049e1f6d49a5f8955edb99290aeac255919094da1e9221759f6c0` | `9159ad0e-b0ae-55c8-aa12-4ee3fee78426` / `76cd2dc5-4839-5452-944e-07686279d77b` |
| D_B incidents | `0e4493b1-1992-5385-88cf-6211309a5458` | `e378ac93-6bee-5a17-a88f-8250bdbbfb08` | `841e4b0494473548c5969ce159f61cdf3c9d214f874559aece7a5c6273eba180` | `936c4e8e5df049e1f6d49a5f8955edb99290aeac255919094da1e9221759f6c0` | `82fac6e0-ee9a-51be-a736-c68d96a2e0ee` / `0d6aca14-a2ba-5961-8b63-69db9e8f761f` |

Hai empty artifacts có cùng members digest nhưng khác coverage content digest,
spec ID và artifact ID vì subject/domain/window khác nhau.

Old-to-new migration:

| 0.2.1 legacy artifact | 0.2.2 structured artifact |
| --- | --- |
| `coverage_db` / `28afa3ef-0535-5323-8a83-e99345c7022a` | D_B trips / `709c5ee2-df8e-523c-9477-46603fd35143` |
| `coverage_dh` / `097e9c93-eabb-5dcd-b271-a5b2afa9e734` | D_H trips / `203c9d37-e2c4-5798-826b-35f7ae97f39a` |
| `incident_db` / `75b8a22c-6d1c-526f-b817-f0f0de55a818` | D_B incidents / `0e4493b1-1992-5385-88cf-6211309a5458` |

## Five affected coverage atoms

| Case/role | New atom ID | Recipe | Result |
| --- | --- | --- | --- |
| C029 / complete_coverage | `c0eb0627-4ea8-5667-8109-5060a5481680` | D_B trips | PASS |
| C030 / incident_evidence | `fb898fd4-a994-59dc-a58f-af9dc7853085` | D_B incidents | PASS |
| C031 / incident_evidence | `90021892-7646-590b-ab07-0de28e4233ce` | D_B incidents | PASS |
| C039 / terminal_population | `5ebf1c47-bf95-5777-ab95-5e54c8059890` | D_H trips | PASS |
| C039 / complete_coverage | `c9ebe116-3801-575d-8f83-3a3a44284982` | D_H trips | PASS |

The corresponding five `0.2.1` atom IDs remain unchanged in the historical
release; all `0.2.2` IDs are derived from the new release namespace.

## Provenance closure

| Locator type | Links | Result |
| --- | ---: | --- |
| `document_clause` | 31 | PASS |
| `ledger_assertion` | 67 | PASS |
| `entity_catalog` | 4 | PASS |
| `definition_artifact` | 3 | PASS |
| `coverage_artifact` | 5 | PASS |
| **Total** | **110** | **PASS** |

Some links intentionally contain multiple exact refs (for example a ten-trip
population or two ambiguous identity candidates); the table counts semantic
support links, not individual refs. All refs resolve from their selected public
snapshot. Public-only resolution still passes after omitting the private tree.

B01–B07: **7/7 complete**. Independent reconstruction: **42/42 exact status and
typed-value matches**. The comparison step is separate from reconstruction:
the evaluator first produces results without reading gold, then validation
compares those results to frozen gold.

## Snapshot and branch assurance

- Snapshot packages: **12/12 PASS**.
- Ledger branches: **8/8 PASS**.
- `L_NO_COVERAGE` removes the D_B/W30 coverage publication and artifact
  allowlist visibility while retaining all 10 D_B trip assertions (and all 80
  trip records globally); C040 remains `insufficient_evidence`.
- Synthetic `v2` is not visible before its publication time; all document and
  artifact locators require matching publication assertions in the selected
  prefix.
- Private aliases and legacy coverage labels are absent from public JSON views.

## Counterfactual assurance

Executable tests cover subject mutation, window mutation, observed-window
rejection, allowed-source removal, non-terminal exclusion, retraction before
and after cutoff, empty-artifact swap, incident subject/scope mismatch,
incident `Tm` boundary, early cutoff, missing publication, digest mutation,
`L_NO_COVERAGE`, private-alias isolation and public-only resolution. Existing
threshold, known-time, correction/retraction, conflict, bridge, coverage and
proof counterfactual groups also remain passing.

## Semantic assurance

| Group | Pass | Fail | Not run | Notes |
| --- | ---: | ---: | ---: | --- |
| V01–V14 | 14 | 0 | 0 | Includes locators, bindings, reconstruction, branch isolation |
| SM01–SM08 | 8 | 0 | 0 | 25 roots / 32 variants / 8 ledgers |
| EX01–EX25 | 25 | 0 | 0 | Independent executable fixtures |
| AUX | 9 | 0 | 0 | Includes executable incident lifecycle checks |
| Counterfactual | 7 validator groups + corrective tests | 0 | 0 | No tautological pass |

Candidate validation summary: **63 pass, 0 fail, 0 not_run**.

| Gate | Result |
| --- | --- |
| DFG01–DFG06 | 6/6 PASS |
| A1_G1–A1_G6 | 6/6 PASS |

## Reproducibility and freeze evidence

- Clean candidate A: build PASS; validation 63/63.
- Clean candidate B: build PASS; validation 63/63.
- Logical comparison: **636 files**, mismatch **0**.
- Frozen verifier `0.2.2`: **636/636**, missing 0, mismatched 0, unexpected 0.
- Historical verifier `0.2.1`: **635/635**, missing 0, mismatched 0, unexpected 0.
- Old frozen release diff: empty.
- Provider-key independence: full data suite ran with OpenAI/Gemini/Anthropic keys unset.
- Archive SHA-256: `cfe9e4555dbedf81396004c7a7d0ace52dcbb1deb758110c4aded3b6741ba9c9`.

Frozen `0.2.2` evidence:

- manifest SHA-256: `f2eb6919d9a30541e804af5f51dc27b005f8332e8109a8eb0ddeffdc2a8d2737`;
- comparison SHA-256: `8438acb3f0e42a41b90f547003e4eea7d1abd79e78a0261bf94018444c11ddb7`;
- logical inventory digest: `cf738397417b7644a51fd6ed11b17b2bc5cac64ea2c9402e75707aad6452aa49`;
- validation SHA-256: `ec3240cf4b7c5965069cbbec894ca9ba4c432666fc1194bd03d6cc0d772f513f`.

## Commands executed

All successful commands below exited `0`:

```powershell
uv run --extra dev pytest -q tests/unit/data/test_coverage.py tests/unit/data/test_synthetic_policy.py tests/integration/data/test_corrective_assurance.py
# 13 passed

Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
Remove-Item Env:GEMINI_API_KEY -ErrorAction SilentlyContinue
Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue
uv run --extra dev pytest -q tests/unit/data tests/conformance/data tests/integration/data
# 39 passed

uv run --extra dev python -m gsm_memory.data.cli build --config configs/datasets/gsm-dev-core-0.2.2.json --output artifacts/data_builds/gsm-dev-core-0.2.2-candidate-a
uv run --extra dev python -m gsm_memory.data.cli validate --candidate artifacts/data_builds/gsm-dev-core-0.2.2-candidate-a --final-reproducibility
uv run --extra dev python -m gsm_memory.data.cli build --config configs/datasets/gsm-dev-core-0.2.2.json --output artifacts/data_builds/gsm-dev-core-0.2.2-candidate-b
uv run --extra dev python -m gsm_memory.data.cli validate --candidate artifacts/data_builds/gsm-dev-core-0.2.2-candidate-b --final-reproducibility
uv run --extra dev python -m gsm_memory.data.cli compare-logical --candidate-a artifacts/data_builds/gsm-dev-core-0.2.2-candidate-a --candidate-b artifacts/data_builds/gsm-dev-core-0.2.2-candidate-b --report reports/data_freeze/gsm-dev-core-0.2.2-logical-comparison.json
uv run --extra dev python -m gsm_memory.data.cli freeze --candidate artifacts/data_builds/gsm-dev-core-0.2.2-candidate-a --comparison reports/data_freeze/gsm-dev-core-0.2.2-logical-comparison.json --target data/gsm-dev-core-0.2.2 --report reports/data_freeze/gsm-dev-core-0.2.2-freeze-certificate.json
uv run --extra dev python -m gsm_memory.data.cli verify-frozen --release data/gsm-dev-core-0.2.2 --certificate reports/data_freeze/gsm-dev-core-0.2.2-freeze-certificate.json --comparison reports/data_freeze/gsm-dev-core-0.2.2-logical-comparison.json
uv run --extra dev python -m gsm_memory.data.cli verify-frozen --release data/gsm-dev-core-0.2.1 --certificate reports/data_freeze/gsm-dev-core-0.2.1-freeze-certificate.json --comparison reports/data_freeze/gsm-dev-core-0.2.1-logical-comparison.json
```

## Remaining limitations

- document/KG retrieval: `not_run`;
- Graphiti: `not_run`;
- embeddings/reranker/evidence selector: `not_run`;
- reader/agent: `not_run`;
- latency/cost: `not_run`;
- BRG01–BRG05: `not_run`;
- held-out test release: không tồn tại (`dev=42`, `test=0`).

Release này chứng nhận dataset/repository assurance, không chứng nhận benchmark
readiness, retrieval success hoặc model superiority.
