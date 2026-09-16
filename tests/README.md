# Tests

- `unit/` — deterministic component tests without external services.
- `integration/` — component-boundary and snapshot-package tests.
- `conformance/` — observed behavior of external/reference systems.
- `fixtures/` — small immutable inputs used across test layers.
- `support/` — test-only harness utilities.

Run the current Graphiti conformance harness from the repository root:

```powershell
.venv\Scripts\python.exe tests\conformance\graphiti\test_temporal_conformance.py
```

Machine-readable outputs are written under `runs/conformance/`.
