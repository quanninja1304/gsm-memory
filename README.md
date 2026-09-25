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
| `data/gsm-dev-core-0.2.2/` | Current corrective release with closed provenance and independent assurance |
| `data/gsm-dev-core-0.2.1/` | Immutable superseded release; retained for audit/reproducibility |
| `data/gsm-dev-core-0.2/` | Immutable deprecated release; do not use for new experiments |
| `tests/` | Unit, integration, fixture, and external conformance tests |
| `runs/` | Machine-readable outputs from ingestion, retrieval, and evaluation runs |
| `artifacts/` | Rebuildable indexes and graph snapshots |
| `reports/` | Human-facing tables, figures, and final analyses |
| `scripts/` | Thin entry points for data and experiment workflows |

## Source-of-truth order

1. `AGENTS.md` for repository-wide operating rules and conflict handling
2. `docs/02_synthetic_schema_and_data_design.md` for business/schema semantics
3. `docs/05_dataset_release_spec.md` for exact release composition and implementation
4. `docs/01_problem_and_evaluation.md` for runtime/evaluation semantics
5. `docs/04_benchmark_to_dataset_mapping.md` for methodology
6. `docs/03_dataset_and_graphiti_baseline_plan.md` for historical planning

Research sources support decisions but do not override the project contract.
Raw policy material and private oracle data must never be mounted directly into
the runtime retriever.

## Offline dataset pipeline

The current `gsm-dev-core-0.2.2` data implementation is under
`src/gsm_memory/data/`. The frozen `gsm-dev-core-0.2` release remains immutable
but is deprecated because 17 public RuntimeQuery records leaked private aliases
or time-scope metadata. `0.2.1` also remains immutable, but is superseded because
its support links and task bindings were not sufficient for independent semantic
reconstruction. Do not use either older release for new experiments. The offline data
workflow is independent of Graphiti and provider credentials. The pinned Python
toolchain is managed by `uv`.

```powershell
uv sync --extra dev
uv run --extra dev python -m gsm_memory.data.cli materialize-sources --config configs/datasets/gsm-dev-core-0.2.2.json --output external/policy_green_sm_corpus
uv run --extra dev python -m gsm_memory.data.cli inventory --config configs/datasets/gsm-dev-core-0.2.2.json
uv run --extra dev python -m gsm_memory.data.cli build --config configs/datasets/gsm-dev-core-0.2.2.json --output artifacts/data_builds/candidate
uv run --extra dev python -m gsm_memory.data.cli validate --candidate artifacts/data_builds/candidate
uv run --extra dev python -m gsm_memory.data.cli verify-frozen --release data/gsm-dev-core-0.2.2 --certificate reports/data_freeze/gsm-dev-core-0.2.2-freeze-certificate.json --comparison reports/data_freeze/gsm-dev-core-0.2.2-logical-comparison.json
```

Source materialization verifies the pinned archive before extracting exactly
225 Markdown files and refuses a non-empty target. Build requires an empty
output directory. Candidate validation is the mutable pre-freeze workflow: it
writes the candidate's validation report. Never run it against a frozen
release. `verify-frozen` is the post-freeze, strictly read-only workflow: it
checks the certificate, manifest, comparison report, and all declared bytes
without repairing or regenerating anything. `compare-logical` compares the
complete declared semantic inventory, and `freeze` verifies validation and
comparison evidence before refusing any existing target.

The dataset handoff status and exact assurance commands are recorded in
`reports/data_freeze/gsm-dev-core-0.2.2-DFG-A1.md`.

## Benchmark readiness status

```text
Current release: gsm-dev-core-0.2.2
Phase B.1 offline closure: PASS
Phase B overall: PARTIAL
BRG01: PASS
BRG02–BRG05: BLOCKED
```

The provider-independent baseline now runs document retrieval, snapshot-isolated
Graphiti Mode A retrieval, hybrid candidate construction and deterministic
selection for all 42 development queries, followed by private post-runtime
candidate-versus-selected attribution. The immediate measured bottleneck is
proof preservation during selection: 30/42 queries are candidate-complete but
only 15/42 remain selected-complete. Mode B, the live reader/C0 and reasoning
attribution remain `BLOCKED_PROVIDER`; dense/reranker is
`BLOCKED_MODEL_ARTIFACT`. Full BRG and production readiness are not claimed.

The native Mode B Graphiti runner is implemented but has not been executed. It
uses the public snapshot narratives, Graphiti `add_episode()` and Graphiti
`search()` with OpenAI and persistent Neo4j. One Neo4j database contains an
isolated group for each public snapshot. Ingestion and search are separate so a
search never silently rebuilds or changes the graph.

Configure a local Neo4j server or Neo4j Aura connection, then start with one
bounded ingestion:

```powershell
$env:OPENAI_API_KEY = "..."
$env:NEO4J_URI = "bolt://localhost:7687"
$env:NEO4J_USER = "neo4j"
$env:NEO4J_PASSWORD = "..."
$env:NEO4J_DATABASE = "neo4j"

uv run --extra graphiti python -m gsm_memory.benchmark graphiti-ingest `
  --release data/gsm-dev-core-0.2.2 `
  --snapshot-id 25b69c05-6a60-51e3-9209-74e5d49816fa `
  --max-episodes 10 `
  --output runs/experiments/graphiti-smoke-ingestion.json

uv run --extra graphiti python -m gsm_memory.benchmark graphiti-search `
  --release data/gsm-dev-core-0.2.2 `
  --snapshot-id 25b69c05-6a60-51e3-9209-74e5d49816fa `
  --max-queries 1 `
  --allow-partial `
  --output runs/experiments/graphiti-smoke.json

uv run --extra graphiti python -m gsm_memory.benchmark evaluate `
  --release data/gsm-dev-core-0.2.2 `
  --runtime-report runs/experiments/graphiti-smoke.json `
  --output runs/experiments/graphiti-smoke-evaluation.json
```

`NEO4J_USERNAME` from an Aura-generated environment file is also accepted as
an alias for `NEO4J_USER`. Values containing spaces, such as an optional Aura
instance name, must be quoted or removed because they are not used by the
baseline.

When the bounded run succeeds, run `graphiti-ingest` without snapshot or episode
limits. The command resumes only an exact episode prefix, reuses complete groups
and rejects mixed database state. Then run `graphiti-search` without snapshot,
query or partial flags for all 42 development queries. Full ingestion may
consume substantial provider quota. Runtime code never reads the private
evaluation directory; the separate `evaluate` command reads gold only after
retrieval has finished.

```powershell
uv run --extra graphiti python -m gsm_memory.benchmark graphiti-ingest `
  --release data/gsm-dev-core-0.2.2 `
  --output runs/experiments/graphiti-full-ingestion.json

uv run --extra graphiti python -m gsm_memory.benchmark graphiti-search `
  --release data/gsm-dev-core-0.2.2 `
  --search-limit 10 `
  --output runs/experiments/graphiti-dev-42.json
```

See `reports/benchmark_readiness/phase-b-offline-closure.md` for current
metrics, corrected latency accounting, error inventories and reproduction
commands.
