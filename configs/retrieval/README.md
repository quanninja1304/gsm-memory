# Retrieval configurations

Document/KG candidate limits, temporal filters, traversal, reranking, and evidence budgets.

`retrieval_v1.json` enables the OpenRouter query planner. Pass it explicitly to
the offline-closure command to have the LLM produce a validated `QueryPlan`:

```powershell
uv run --extra graphiti python -m gsm_memory.benchmark offline-closure `
  --release data/gsm-dev-core-0.2.2 `
  --retrieval-config configs/retrieval/retrieval_v1.json `
  --output runs/experiments/llm-query-plan-closure.json
```

The provider requires `OPENROUTER_API_KEY`. Invalid provider output or provider
failure is recorded on the query trace and falls back to deterministic parsing;
the public snapshot and temporal request context remain application-controlled.
