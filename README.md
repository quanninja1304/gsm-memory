# GSM Memory R&D

Repository workspace for the six-week GSM agent-memory research project. The
project evaluates document retrieval, temporal knowledge-graph retrieval,
hybrid evidence construction, and downstream agent behavior. Graphiti is the
initial graph reference baseline, not an assumed source of temporal truth.

## Repository map

| Path | Purpose |
| --- | --- |
| `docs/` | Contracts, schema, dataset specifications, research, and project notes |
| `external/` | Source checkouts kept intact; not project implementation code |
| `src/gsm_memory/` | Implementation packages for data, adapters, retrieval, evaluation, and agent integration |
| `configs/` | Versioned dataset, Graphiti, retrieval, and experiment configurations |
| `data/raw/` | Immutable source archives owned by this workspace |
| `data/gsm-dev-core-0.1/` | Exact pilot dataset-release tree specified by contract 05 |
| `tests/` | Unit, integration, fixture, and external conformance tests |
| `runs/` | Machine-readable outputs from ingestion, retrieval, and evaluation runs |
| `artifacts/` | Rebuildable indexes and graph snapshots |
| `reports/` | Human-facing tables, figures, and final analyses |
| `scripts/` | Thin entry points for data and experiment workflows |

## Source-of-truth order

1. `docs/01_problem_and_evaluation.md`
2. `docs/02_synthetic_schema_and_data_design.md`
3. `docs/05_dataset_release_spec.md`
4. `docs/04_benchmark_to_dataset_mapping.md` for methodology
5. `docs/03_dataset_and_graphiti_baseline_plan.md` for implementation sequencing

Research sources support decisions but do not override the project contract.
Raw policy material and private oracle data must never be mounted directly into
the runtime retriever.

## Offline dataset pipeline

The current `gsm-dev-core-0.2.1` data implementation is under `src/gsm_memory/data/`.
The frozen `gsm-dev-core-0.2` release is immutable but deprecated because 17
RuntimeQuery records leaked private aliases or time-scope metadata.
It is independent of Graphiti and provider credentials. The pinned Python
toolchain is managed by `uv`.

```powershell
uv sync --extra dev --extra graphiti
.venv\Scripts\python.exe -m gsm_memory.data.cli --help
.venv\Scripts\python.exe -m gsm_memory.data.cli inventory --config configs\datasets\gsm-dev-core-0.2.1.json
.venv\Scripts\python.exe -m gsm_memory.data.cli build --config configs\datasets\gsm-dev-core-0.2.1.json --output artifacts\data_builds\candidate
.venv\Scripts\python.exe -m gsm_memory.data.cli validate --candidate artifacts\data_builds\candidate
```

Build requires an empty output directory. Validation reads an existing
candidate and never regenerates source data. `compare-logical` compares the
complete declared semantic inventory, and `freeze` verifies validation and
comparison evidence before refusing any existing target.

The latest handoff status and exact commands are recorded in
`reports/data_freeze/gsm-dev-core-0.2.1-DFG.md`. Graphiti ingestion, retrieval,
embeddings, agent runs and BRG remain out of scope.
