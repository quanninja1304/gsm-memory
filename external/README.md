# External sources

`policy_green_sm_corpus/` is ignored, read-only working source material. A fresh
clone must materialize it offline from the pinned archive rather than crawl or
download the website:

```powershell
uv run --extra dev python -m gsm_memory.data.cli materialize-sources --config configs/datasets/gsm-dev-core-0.2.1.json --output external/policy_green_sm_corpus
```

The command verifies the archive SHA-256, preserves member bytes, extracts the
224 individual articles plus the one aggregate duplicate, and refuses to
overwrite a non-empty target. The aggregate remains excluded from retrieval.
Treat the resulting directory as immutable input; do not commit it.
