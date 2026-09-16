# Configuration

- `datasets/` — generator seeds, release versions, and scale tiers.
- `graphiti/` — backend, model, ingestion mode, and projection settings.
- `retrieval/` — candidate limits, temporal filters, hops, reranking, and budgets.
- `experiments/` — composed run configurations and ablations.

Configuration files should be immutable per recorded run and referenced by hash.
