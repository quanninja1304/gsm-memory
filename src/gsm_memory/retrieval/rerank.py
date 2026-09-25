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


class NvidiaReranker:
    """NVIDIA Retrieval NIM cross-encoder client; network is opt-in at call time."""

    endpoint = "https://ai.api.nvidia.com/v1/retrieval/nvidia/reranking"

    def __init__(self, *, api_key: str | None = None,
                 model: str = "nvidia/rerank-qa-mistral-4b") -> None:
        self.api_key = api_key or os.getenv("NVIDIA_API_KEY")
        self.model = model

    def rank(self, query: str, passages: Sequence[str]) -> list[float]:
        if not passages:
            return []
        if not self.api_key:
            raise RuntimeError("NVIDIA_API_KEY is required for NVIDIA reranking")
        import requests

        response = requests.post(
            self.endpoint,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"model": self.model, "query": {"text": query},
                  "passages": [{"text": text} for text in passages], "truncate": "END"},
            timeout=30,
        )
        if response.status_code != 200:
            raise RuntimeError(f"NVIDIA reranker error {response.status_code}: {response.text}")
        data = response.json().get("data", response.json().get("rankings", []))
        scores: list[float | None] = [None] * len(passages)
        for row in data:
            index = row.get("index")
            score = row.get("relevance_score", row.get("score"))
            if isinstance(index, int) and 0 <= index < len(scores) and score is not None:
                scores[index] = float(score)
        if any(score is None for score in scores):
            raise RuntimeError("NVIDIA reranker response omitted one or more passage scores")
        return [float(score) for score in scores]


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
