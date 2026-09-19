# Phase B.1 — provider-independent retrieval closure

## Summary

```text
Phase B.1 offline closure: PASS
Phase B overall: PARTIAL
release input: gsm-dev-core-0.2.2
BRG01: PASS
BRG02: BLOCKED (offline sub-gates pass; Mode B blocked_provider)
BRG03: BLOCKED (offline retrieval sub-gates pass; dense/reranker and reader blocked)
BRG04: BLOCKED (candidate/selected attribution pass; reasoning blocked_provider)
BRG05: BLOCKED (offline instrumentation pass; provider instrumentation blocked_provider)
```

This closure executes the complete provider-independent Mode A path for all 42
development queries. It does not claim reader accuracy, full BRG completion,
production readiness, or retrieval superiority.

## Integrity and isolation

- Frozen verifier: PASS, 636/636; zero missing, mismatched, or unexpected paths.
- Frozen path diff: empty.
- Manifest SHA-256: `f2eb6919d9a30541e804af5f51dc27b005f8332e8109a8eb0ddeffdc2a8d2737`.
- Comparison SHA-256: `8438acb3f0e42a41b90f547003e4eea7d1abd79e78a0261bf94018444c11ddb7`.
- Logical inventory digest: `cf738397417b7644a51fd6ed11b17b2bc5cac64ea2c9402e75707aad6452aa49`.
- Runtime reads public RuntimeQueries, the selected public snapshot and public
  corpus only. Private gold is read later by the evaluator. The private-tree-
  absent integration path passes.

## Construction and query execution

- 12/12 isolated snapshot graphs covering 8/8 ledger identities.
- Deterministic namespace includes release digest, snapshot ID, Mode A config,
  Graphiti/Kùzu versions and adapter hash.
- Each graph is cold-built; all 12 repeat-write checks pass.
- Per-snapshot graph sizes range from 19–264 nodes, 30–365 edges and 29–359
  episodes. Source ProjectionLinks remain resolvable.
- `retrieval_full`: 1,575 chunks and 1,575 document ProjectionLinks; construction
  digest `27e05a70215304b9e543a577b7eeb2f6024e171f9c199f0962537fd251ca30bf`.
- 42/42 terminal traces, all `completed_retrieval`; no silent skips.
- Pools: 621 document candidates, 2,666 raw KG candidates, 1,152 eligible
  KG/catalog candidates, four computation candidates, 1,777 hybrid candidates,
  and 504 selected evidence items.

The hybrid union deduplicates only identical canonical locators. The selector is
deterministic and public-only; it uses query text, public pins, entity/time
constraints, modality and budgets, never gold roles or proofs.

## Exact aggregate path

The runtime resolves coverage before computing, enumerates active assertions
from the complete declared public source set, and uses exact rational arithmetic.

- Non-empty population: 10 members, two cancelled, exact value `1/5`.
- Empty complete population: zero members, typed value undefined rather than 0.
- `L_NO_COVERAGE`: `missing_coverage`; it does not infer completeness from the
  ten visible trip facts and emits no computation candidate.

## Retrieval and proof metrics

The historical `7/42` BM25 number is retained only as **full-proof completeness
from BM25-only candidates**. It is not a pure document metric.

| Metric | Candidate | Selected |
| --- | ---: | ---: |
| At least one sufficient proof complete | 30/42 | 15/42 |
| Document support-link recall | 28/31 (90.32%) | 26/31 (83.87%) |
| Ledger assertion recall | 65/67 (97.01%) | 48/67 (71.64%) |
| Entity catalog recall | 3/4 (75.00%) | 1/4 (25.00%) |
| Definition artifact recall | 3/3 (100.00%) | 3/3 (100.00%) |
| Coverage artifact recall | 3/5 (60.00%) | 3/5 (60.00%) |

Selection loss is explicitly attributed for 15 queries. This is a measured
baseline limitation, not a reader failure. Candidate-incomplete cases retain
their missing roles and earliest-stage attribution in
`retrieval-full-mode-a-evaluation.json`. Correct branch/snapshot, valid-time,
known-time, public entity anchoring and source-locator resolution rates are
100% over eligible KG candidates. Precision and nDCG remain
`N/A (incomplete_judgments)`; unjudged documents are not implicit negatives.

## Instrumentation

Median per-query latency in run A was 16.290 ms document retrieval, 64.670 ms
KG search, 0.607 ms eligibility normalization, 0.002 ms computation, 0.295 ms
hybrid merge, 0.047 ms selection and 17.514 ms total pre-reader; total
pre-reader p95 was 22.790 ms. Graph construction time is recorded separately
for every snapshot. All graph caches were cold. Errors and retries were zero.

Provider calls are 0. Tokens and provider cost are N/A with reason
`provider_not_called`; reader latency is N/A with reason `reader_not_run`.

## Determinism

Two independent cold constructions produced identical logical digest:
`be01038f1cf831283c62c7a299bc07a82b770cf5cadbdd7f6bd2e2dc7b6f93fa`.
Their byte hashes differ because measured latency is intentionally retained.

- Run A SHA-256: `7641c0e3724c4fa0ec614926084fe21996ea97427588c8b3ae4bd4566372a038`.
- Run B SHA-256: `0d9c017cc0c9e9c18def4fb0ade50801a4ddd2172c5a94919fe0a12a31ec2db3`.

## Dense/reranker audit

Dense retrieval and reranking remain `BLOCKED_MODEL_ARTIFACT`. A local cache for
`keepitreal/vietnamese-sbert` revision
`a9467ef2ef47caa6448edeabfd8e5e5ce0fa2a23` exists (542,105,898 bytes), but it
is not a repository-pinned approved artifact, its cached model card declares no
license, and the locked environment lacks the transformer runtime. It was not
silently installed or mislabeled. The Graphiti hash embedder remains plumbing
only, not a semantic dense baseline.

## Verification

- Data/frozen suite: 39 passed in 41.58 seconds.
- Phase B unit/conformance/integration suite: 15 passed in 19.29 seconds.
- Final frozen verifier: PASS 636/636.
- Frozen-path diff: empty; `git diff --check`: PASS.
- Provider credentials were unset for the test and closure workflows.

## Reproduction

```powershell
$env:OPENAI_API_KEY=$null
$env:GEMINI_API_KEY=$null
$env:ANTHROPIC_API_KEY=$null
uv run --extra dev python -m gsm_memory.benchmark offline-closure --release data/gsm-dev-core-0.2.2 --profile retrieval_full --output runs/experiments/phase-b/offline-closure-a.json
uv run --extra dev python -m gsm_memory.benchmark offline-closure --release data/gsm-dev-core-0.2.2 --profile retrieval_full --output runs/experiments/phase-b/offline-closure-b.json
uv run --extra dev python -m gsm_memory.benchmark evaluate --release data/gsm-dev-core-0.2.2 --runtime-report runs/experiments/phase-b/offline-closure-a.json --output reports/benchmark_readiness/retrieval-full-mode-a-evaluation.json
```

## Remaining blockers

```text
Mode B: BLOCKED_PROVIDER
live reader/C0: BLOCKED_PROVIDER
gold-context reader control: BLOCKED_PROVIDER
reasoning attribution: BLOCKED_PROVIDER
dense/reranker: BLOCKED_MODEL_ARTIFACT
held-out test release: absent
production readiness: not claimed
scale validation: not_run
```
