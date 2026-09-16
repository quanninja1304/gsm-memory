# Run outputs

Every experiment run should have a unique directory and retain its manifest,
ingestion receipts, projection links, traces, metrics, and failure state.
Changing configuration creates a new run; do not overwrite earlier evidence.

- `conformance/` — reference-system audits.
- `experiments/` — baseline, ablation, scale, and final frozen comparisons.
