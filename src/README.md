# Implementation source

The Python package is `gsm_memory`.

- `data/` — generator, ledger reducer, snapshot packaging, validation.
- `adapters/` — Graphiti Mode A/Mode B, documents, and source computation.
- `retrieval/` — document, KG, hybrid retrieval, and evidence packing.
- `evaluation/` — gold matching, L1–L4 metrics, traces, error taxonomy.

Package modules should depend on public contracts, not private oracle files,
except inside explicitly evaluator-only code paths.
