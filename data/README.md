# Data boundaries

- `raw/archives/` stores immutable source archives.
- `gsm-dev-core-0.1/` is the exact pilot public/private dataset tree defined by
  `docs/05_dataset_release_spec.md`.

A release should contain its own manifest, hashes, schema version, validation
report, and public/private access boundary. Runtime systems must consume a
selected public snapshot package rather than the full operational archive.
