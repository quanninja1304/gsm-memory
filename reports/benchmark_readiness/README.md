# Phase B benchmark-readiness report

> This file preserves the initial Phase B partial checkpoint. The subsequent
> provider-independent closure is recorded in
> [`phase-b-offline-closure.md`](phase-b-offline-closure.md) and
> [`phase-b-offline-closure.json`](phase-b-offline-closure.json). The current
> machine-readable gate/sub-gate view is [`brg-report.json`](brg-report.json).

## Phase B.1 update

Phase B.1 offline closure is **PASS**: 42/42 Mode A KG, hybrid candidate and
selected-evidence traces completed across 12/12 public snapshots and 8/8 ledger
identities. Candidate-versus-selected attribution and offline instrumentation
are complete. Full Phase B remains **PARTIAL** because Mode B, live reader/C0,
reasoning attribution and provider instrumentation are `BLOCKED_PROVIDER`, while
dense/reranker remains `BLOCKED_MODEL_ARTIFACT` after the local audit.

The initial `7/42` result below means **full-proof completeness from BM25-only
candidates**. It is not a pure document-retrieval recall metric. The closure
report adds modality-aware document, ledger, catalog, definition and coverage
metrics and reports candidate completeness (30/42), selected completeness
(15/42), and selection loss (15 queries).

## Initial partial checkpoint

## Summary

```text
Phase B status: PARTIAL
release input: gsm-dev-core-0.2.2
BRG01: PASS
BRG02: BLOCKED
BRG03: BLOCKED
BRG04: BLOCKED
BRG05: BLOCKED
```

The repository now has a reproducible public-only document path, an actual
Graphiti/Kùzu Mode A micro-construction path, normalized evidence primitives,
and a separate post-runtime evaluator. This is not a full baseline: the
multilingual dense model, bounded reranker, native Mode B extraction and live
reader were unavailable, and the measured KG/hybrid paths therefore did not run.

## Environment

- HEAD: `372e4d1ada9bb0f0c604106483fa6e5fdc86b337` on `main`.
- Windows 10.0.19045 AMD64; Intel i3-1005G1 (2 cores/4 logical), about 8 GB RAM.
- Python 3.12.14 through uv 0.12.5; `uv.lock` SHA-256
  `e8c37d9053f3d03a867e7b28dcdb272fac445920d52ff0de20f4ade202d80aa9`.
- Graphiti Core 0.30.2; Kùzu 0.11.3. Kùzu is deprecated upstream.
- No OpenAI, Gemini or Anthropic credential was present.
- Dense model, semantic reranker and live reader: unavailable.
- Pinned runtime config: `configs/benchmark/phase-b-baseline.json`.
- Runtime implementation hash: `23cde91c8ae460cb0f6cb516e19db7e2488587482d9f96312a1d9d6f08b4db18`.

## Construction

`debug_core` produced 44 chunks from 9 document revisions (six real plus three
synthetic) and 12 definitions. `retrieval_full` produced 1,575 chunks from 227
document revisions (224 real plus three synthetic) and 12 definitions. Two
independent runs produced the same logical digest:
`27e05a70215304b9e543a577b7eeb2f6024e171f9c199f0962537fd251ca30bf`.

The Graphiti Mode A micro-run wrote 359 public records as 359 episodes, 364
assertion edges and 263 nodes, including two replacements and one retraction.
Custom source/time/revision attributes survived
round-trip, a repeated edge write left counts unchanged, and Graphiti indexed
search returned five source-resolvable edges. The offline hash embedder proves
search/index plumbing only; it is not claimed as a dense semantic retriever.

Mode B is `BLOCKED_PROVIDER` with zero calls and zero attempted episodes.

## Runs and evaluation

The measured `retrieval_full` BM25 run emitted 42/42 terminal traces. Dense,
fusion, reranker, full KG, hybrid and reader fields have explicit terminal
`unsupported` or `blocked_provider` states. No query was silently removed.

The separate evaluator read private gold only after runtime output was
materialized. BM25 candidate evidence completed at least one minimal proof in
7/42 cases. Precision and nDCG are `N/A (incomplete_judgments)`. Selection,
typed answer accuracy, citations and reasoning attribution remain not run.

## Instrumentation

Both construction runs record elapsed time; every query records retrieval
latency and candidate/filter counts. Provider calls, tokens, retries and actual
cost are zero because no provider request was made. Cache policy is cold,
in-memory construction with no runtime result cache.

## Integrity

- Frozen verifier: PASS, 636/636, no missing/mismatched/unexpected path.
- Runtime public-only integration test: PASS with the private tree absent.
- Frozen release bytes were not modified.

## Reproduction

```powershell
uv sync --extra dev --extra graphiti
uv run --extra dev --extra graphiti python -m gsm_memory.benchmark construct-documents --release data/gsm-dev-core-0.2.2 --profile retrieval_full --output artifacts/indexes/phase-b/retrieval_full/chunks.json
uv run --extra dev --extra graphiti python -m gsm_memory.benchmark probe-graphiti --snapshot data/gsm-dev-core-0.2.2/public/snapshots/296f03c2-6abf-57b3-8a17-249486d98fe8 --output reports/benchmark_readiness/graphiti-capability.json
uv run --extra dev --extra graphiti python -m gsm_memory.benchmark run --release data/gsm-dev-core-0.2.2 --profile retrieval_full --output runs/experiments/phase-b/retrieval-full-bm25.json --top-k 10
uv run --extra dev --extra graphiti python -m gsm_memory.benchmark evaluate --release data/gsm-dev-core-0.2.2 --runtime-report runs/experiments/phase-b/retrieval-full-bm25.json --output reports/benchmark_readiness/retrieval-full-evaluation.json
```

## Remaining limitations

```text
held-out test release: absent
external validity: limited
production readiness: not claimed
scale validation: not_run
```

## Verification results

- Frozen/data suite: 39 passed in 42.78s.
- Phase B unit/conformance/integration selection: 7 passed in 11.52s; two upstream deprecation warnings.
- Frozen verifier: 636 checked, zero missing/mismatched/unexpected.
- Frozen path diff and `git diff --check`: clean.
