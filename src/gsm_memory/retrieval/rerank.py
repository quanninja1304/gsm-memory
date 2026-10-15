"""Bounded document reranking adapters.

Reranking is applied only after BM25+dense candidate fusion and only to document
chunks.  It never ranks KG edges against document chunks and never reads gold.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol, Sequence


class Reranker(Protocol):
    model: str

    def rank(self, query: str, passages: Sequence[str]) -> list[float]: ...


@dataclass(frozen=True)
class RerankResult:
    evidence_id: str
    score: float
    rank: int


DEFAULT_NVIDIA_RERANK_MODEL = "nvidia/llama-nemotron-rerank-vl-1b-v2"
DEFAULT_NVIDIA_RERANK_ENDPOINT = (
    "https://ai.api.nvidia.com/v1/retrieval/nvidia/llama-nemotron-rerank-vl-1b-v2/reranking"
)


class NvidiaReranker:
    """NVIDIA Retrieval NIM cross-encoder client; network is opt-in at call time."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = DEFAULT_NVIDIA_RERANK_MODEL,
        endpoint: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("NVIDIA_API_KEY")
        self.model = model
        if endpoint:
            self.endpoint = endpoint
        elif "nemotron" in model:
            self.endpoint = (
                "https://ai.api.nvidia.com/v1/retrieval/nvidia/llama-nemotron-rerank-vl-1b-v2/reranking"
            )
        elif "mistral" in model:
            self.endpoint = "https://ai.api.nvidia.com/v1/retrieval/nvidia/reranking"
        else:
            self.endpoint = DEFAULT_NVIDIA_RERANK_ENDPOINT

    def rank(self, query: str, passages: Sequence[str]) -> list[float]:
        if not passages:
            return []
        if not self.api_key:
            raise RuntimeError("NVIDIA_API_KEY is required for NVIDIA reranking")
        import math
        import requests

        # NVIDIA rerank supports batched passages; chunk in batches of 25 if necessary
        batch_size = 25
        all_scores: list[float] = []

        for i in range(0, len(passages), batch_size):
            batch = passages[i : i + batch_size]
            response = requests.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "query": {"text": query},
                    "passages": [{"text": text} for text in batch],
                    "truncate": "END",
                },
                timeout=30,
            )
            if response.status_code != 200:
                raise RuntimeError(f"NVIDIA reranker error {response.status_code}: {response.text}")
            
            res_json = response.json()
            data = res_json.get("data", res_json.get("rankings", []))
            batch_scores: list[float | None] = [None] * len(batch)
            for row in data:
                index = row.get("index")
                raw = row.get("relevance_score", row.get("score", row.get("logit")))
                if isinstance(index, int) and 0 <= index < len(batch_scores) and raw is not None:
                    # Convert unconstrained logit into [0, 1] probability via sigmoid
                    if "logit" in row:
                        val = 1.0 / (1.0 + math.exp(-float(raw)))
                    else:
                        val = float(raw)
                    batch_scores[index] = val
            
            # Fallback for any missing items in batch
            for idx in range(len(batch_scores)):
                if batch_scores[idx] is None:
                    batch_scores[idx] = 0.0

            all_scores.extend(batch_scores)

        return all_scores


def rerank_candidates(query: str, candidates: list[dict[str, Any]], *, reranker: Reranker,
                      top_n: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Rerank only the fused top-N document candidates and retain provenance."""
    bounded = candidates[:top_n]
    scores = reranker.rank(query, [str(row["content"]) for row in bounded])
    if len(scores) != len(bounded):
        raise RuntimeError("reranker returned a score count different from its input")
    scored = []
    for candidate, score in zip(bounded, scores, strict=True):
        row = dict(candidate)
        row["rerank_score"] = float(score)
        row["origin_stage"] = "rerank"
        scored.append(row)
    scored.sort(key=lambda row: (-row["rerank_score"], row["evidence_id"]))
    for rank, row in enumerate(scored, 1):
        row["rank"] = rank
        row["score"] = row["rerank_score"]
    untouched = candidates[top_n:]
    return scored + untouched, {"status": "completed", "model": reranker.model,
                                 "input_count": len(bounded), "output_count": len(scored)}
