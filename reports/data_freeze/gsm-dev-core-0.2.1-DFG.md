# gsm-dev-core-0.2.1 — Data Freeze handoff

## Outcome

`gsm-dev-core-0.2.1` is frozen at `data/gsm-dev-core-0.2.1/` and supersedes
the immutable `gsm-dev-core-0.2` release. The old release is externally marked
deprecated because 17 of its 42 public RuntimeQuery renderings leaked private
aliases or time-scope labels. The corrected release has zero such findings.

The old release was not changed. Its manifest SHA-256 remains
`ce7ff9edfaf116716551f5af4907b47c66bf4bd878df0cea4d89062b808ab190`,
its freeze-certificate SHA-256 remains
`2859282953ac2dabe4187103c95431e4d6fe37b5a977d73be57aadfa4d6ae024`,
and its declared file inventory verifies without mismatches.

## Changed implementation

- Dataset config: `configs/datasets/gsm-dev-core-0.2.1.json`.
- Identity/contracts: `src/gsm_memory/data/primitives.py` and
  `src/gsm_memory/data/contracts.py`.
- Config, validation, and freeze guards: `src/gsm_memory/data/build.py`,
  `src/gsm_memory/data/validation.py`, and `src/gsm_memory/data/cli.py`.
- Regression coverage: `tests/integration/data/test_release.py`.
- Operator documentation: `README.md` and the external deprecation record
  `reports/data_freeze/gsm-dev-core-0.2-deprecation.json`.

## Commands and exit status

All commands ran with `OPENAI_API_KEY`, `GEMINI_API_KEY`, and
`ANTHROPIC_API_KEY` unset.

```powershell
.venv\Scripts\python.exe -m gsm_memory.data.cli inventory --config configs\datasets\gsm-dev-core-0.2.1.json
.venv\Scripts\python.exe -m pytest tests\unit\data tests\conformance\data tests\integration\data -q
.venv\Scripts\python.exe -m gsm_memory.data.cli build --config configs\datasets\gsm-dev-core-0.2.1.json --output artifacts\data_builds\gsm-dev-core-0.2.1-clean-A
.venv\Scripts\python.exe -m gsm_memory.data.cli validate --candidate artifacts\data_builds\gsm-dev-core-0.2.1-clean-A
.venv\Scripts\python.exe -m gsm_memory.data.cli build --config configs\datasets\gsm-dev-core-0.2.1.json --output artifacts\data_builds\gsm-dev-core-0.2.1-clean-B
.venv\Scripts\python.exe -m gsm_memory.data.cli validate --candidate artifacts\data_builds\gsm-dev-core-0.2.1-clean-B
.venv\Scripts\python.exe -m gsm_memory.data.cli compare-logical --candidate-a artifacts\data_builds\gsm-dev-core-0.2.1-clean-A --candidate-b artifacts\data_builds\gsm-dev-core-0.2.1-clean-B --report reports\data_freeze\gsm-dev-core-0.2.1-logical-comparison.json
.venv\Scripts\python.exe -m gsm_memory.data.cli freeze --candidate artifacts\data_builds\gsm-dev-core-0.2.1-clean-A --comparison reports\data_freeze\gsm-dev-core-0.2.1-logical-comparison.json --target data\gsm-dev-core-0.2.1 --report reports\data_freeze\gsm-dev-core-0.2.1-freeze-certificate.json
```

Every listed command exited `0`. Pytest reported `9 passed`.

## Release inventory

| Invariant | Actual |
| --- | ---: |
| Canonical real documents | 224 |
| Audited / primary-gold sources | 6 / 4 |
| debug_core / retrieval_full members | 6 / 224 |
| Drivers / terminal trips | 8 / 80 |
| Scenario roots / variants | 25 / 32 |
| Ledgers / public snapshots | 8 / 12 |
| Semantic cases / direct renderings | 42 / 42 |
| Dev / test queries | 42 / 0 |

## Validation evidence

Both clean candidates passed `56/56` required checks. The final frozen
candidate contains:

| Group | Passed | Failed | Not run |
| --- | ---: | ---: | ---: |
| V01–V10 | 10 | 0 | 0 |
| SM01–SM08 | 8 | 0 | 0 |
| EX01–EX25 | 25 | 0 | 0 |
| AUX groups | 9 | 0 | 0 |
| Counterfactual checks | 4 | 0 | 0 |

| Gate | Result |
| --- | --- |
| DFG01 | PASS |
| DFG02 | PASS |
| DFG03 | PASS |
| DFG04 | PASS |
| DFG05 | PASS |
| DFG06 | PASS |

Clean-build comparison covered 635 semantic files with zero mismatches. Its
logical inventory digest is
`4ed08a35393912150ffb731946965c5adc827a403835d4c9a96e9c333df16d11`.

## Frozen identity

- State: `FROZEN`.
- Manifest SHA-256:
  `61dddfd6c9f078b9b8c8288562c6196ae28a7ece390cd6d61d03041183b515b5`.
- Comparison-report SHA-256:
  `cf1b105bd0beab4bd63cd774edf61460c49ad8ed6156ae9a734f205d5c721357`.
- Frozen file inventory: 635 files, zero hash or path mismatches.
- Pending, blocked, or unsupported DFG items: none.
- BRG, Graphiti, retrieval, embeddings, and agent evaluation: out of scope and
  not run.
