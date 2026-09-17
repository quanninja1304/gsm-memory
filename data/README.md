# Data boundaries

- `raw/archives/` stores immutable source archives.
- `gsm-dev-core-0.2.1/` is the current frozen corrective release.
- `gsm-dev-core-0.2/` is immutable but deprecated because its public query
  records leaked private metadata; do not use it for new experiments.

A release should contain its own manifest, hashes, schema version, validation
report, and public/private access boundary. Runtime systems must consume a
selected public snapshot package rather than the full operational archive.
Candidate validation may write inside a staging candidate. Frozen verification
must use `verify-frozen` and is strictly read-only.
