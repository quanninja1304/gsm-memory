# Scripts

Thin reproducible entry points belong here:

- `data/` — build, validate, and package dataset releases.
- `experiments/` — ingest, retrieve, evaluate, and produce run manifests.

Business logic should remain in `src/gsm_memory/` so it can be tested directly.
