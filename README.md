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

## Current implementation status

The repository currently contains planning/specification documents and a
Graphiti Mode-B temporal conformance harness. Most `src/`, config, dataset,
and evaluation paths are intentional placeholders for upcoming implementation.

No root Git repository has been initialized by this organization step.
