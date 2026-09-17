# gsm-dev-core-0.2 — Data Freeze handoff

Date: 2026-09-16. Schema 1.1, release spec 0.2.0, seed 42.

## Implemented areas

- `src/gsm_memory/data/`: canonical primitives, closed sidecars, source audit,
  world/ledger/branches, reducer, case rendering, packaging, validation, logical
  comparison and freeze-safe CLI.
- `src/gsm_memory/evaluation/`: exact formulas and observable source-level
  evaluator; fixed expected cases remain an independent conformance table.
- `configs/datasets/gsm-dev-core-0.2.json`, `pyproject.toml`, `uv.lock`:
  release/source pins and Python 3.12/pyarrow/test toolchain. Existing Graphiti
  0.30.2/provider package versions are retained in the optional environment.
- `tests/unit/data`, `tests/conformance/data`, `tests/integration/data`:
  primitives, ledger revision/conflict, EX01–EX25 and clean package integration.
- `README.md` and this report: reproducible CLI commands and current gate state.

## Outcome

The corrected candidate is **VALIDATED but not promoted**. DFG01–DFG05 have
executable PASS evidence. The two corrected clean builds compare equal across
635 semantic files. Promotion/DFG06 is **BLOCKED** because
`data/gsm-dev-core-0.2/` already exists with state `FROZEN`, and freeze safety
correctly refused to overwrite it.

That existing release was produced earlier in this work and is superseded as
a candidate: a post-freeze audit found 17 RuntimeQuery texts containing
private window aliases (`W11`, `WA14`, etc.) and incorrect `current` time
scopes. Its old freeze certificate must not be used as current DFG evidence.
The corrected builds contain zero such aliases and explicit interval/point
scopes. No existing frozen bytes were changed or removed.

## Actual inventory

| Item | Count |
| --- | ---: |
| Real sources / audited / primary-gold | 224 / 6 / 4 |
| `debug_core` / `retrieval_full` members | 6 / 224 |
| Drivers / distinct terminal trips | 8 / 80 |
| Scenario roots / variants / ledgers | 25 / 32 / 8 |
| Semantic cases / direct renderings | 42 / 42 |
| Dev / test queries | 42 / 0 |
| Public snapshots / definitions / synthetic versions | 12 / 12 / 3 |
| Support atoms / proofs / support links | 110 / 42 / 110 |
| L0 source records | 359 |
| Corrected candidate physical files | 636 |

## Validation

Both corrected candidates: 56 PASS, 0 FAIL, 0 NOT_RUN before promotion.

| Group | Result |
| --- | --- |
| V01–V10 | 10/10 PASS |
| SM01–SM08 | 8/8 PASS |
| EX01–EX25 | 25/25 PASS |
| AUX_IDENTITY/TIME/EVENT/INCIDENT/REVISION/POLICY/ARTIFACT/CONTEXT/ACCESS | 9/9 PASS |
| Counterfactual checks | 4/4 PASS |
| Corrected clean-build comparison | PASS; 635 files; 0 mismatches |

## Data Freeze gates

| Gate | Status | Evidence |
| --- | --- | --- |
| DFG01 | PASS | Source archive/catalog, source hashes, profiles and reviewed roles |
| DFG02 | PASS | V01–V04 and SM01–SM08 |
| DFG03 | PASS | V05–V07, EX01–EX25, AUX and proof records |
| DFG04 | PASS | V08–V10, A/B manifests, package isolation and leakage audit |
| DFG05 | PASS | 42 dev/0 test, pins and full logical equivalence |
| DFG06 | BLOCKED | Existing frozen target cannot be overwritten safely |

Final release state: **VALIDATED candidate; not FROZEN/promoted**.

Corrected comparison evidence:
`reports/data_freeze/gsm-dev-core-0.2-final-logical-comparison.json`.
Corrected candidate:
`artifacts/data_builds/gsm-dev-core-0.2-final-A/`.

## Commands executed

All commands ran from `D:\vinai\memory` with `.venv` Python 3.12.14.

```powershell
uv lock
uv sync --extra dev --extra graphiti
.venv\Scripts\python.exe -m gsm_memory.data.cli --help
.venv\Scripts\python.exe -m gsm_memory.data.cli inventory --config configs\datasets\gsm-dev-core-0.2.json
.venv\Scripts\python.exe -m gsm_memory.data.cli build --config configs\datasets\gsm-dev-core-0.2.json --output artifacts\data_builds\gsm-dev-core-0.2-final-A
.venv\Scripts\python.exe -m gsm_memory.data.cli validate --candidate artifacts\data_builds\gsm-dev-core-0.2-final-A
.venv\Scripts\python.exe -m gsm_memory.data.cli build --config configs\datasets\gsm-dev-core-0.2.json --output artifacts\data_builds\gsm-dev-core-0.2-final-B
.venv\Scripts\python.exe -m gsm_memory.data.cli validate --candidate artifacts\data_builds\gsm-dev-core-0.2-final-B
.venv\Scripts\python.exe -m gsm_memory.data.cli compare-logical --candidate-a artifacts\data_builds\gsm-dev-core-0.2-final-A --candidate-b artifacts\data_builds\gsm-dev-core-0.2-final-B --report reports\data_freeze\gsm-dev-core-0.2-final-logical-comparison.json
.venv\Scripts\python.exe -m gsm_memory.data.cli freeze --candidate artifacts\data_builds\gsm-dev-core-0.2-final-A --comparison reports\data_freeze\gsm-dev-core-0.2-final-logical-comparison.json --target data\gsm-dev-core-0.2 --report reports\data_freeze\gsm-dev-core-0.2-final-freeze-certificate.json
.venv\Scripts\python.exe -m pytest tests\unit\data tests\conformance\data tests\integration\data -q
```

Exit status was 0 for sync, help, inventory, corrected builds, validations,
comparison and pytest (8 passed). The corrected freeze command exited 2 with
`refusing to overwrite existing target (state=FROZEN)`.

## Remaining boundary

Graphiti projection/ingestion/search, document retrieval baseline, full qrels,
embeddings, agent answers, latency and BRG were not implemented or claimed.
