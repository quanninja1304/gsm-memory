"""Rank fusion for same-type document chunks only."""

from __future__ import annotations

from typing import Iterable


def reciprocal_rank_fusion(rankings: Iterable[tuple[str, list[str]]], *, k: int,
                            weights: dict[str, float]) -> list[tuple[str, float, dict[str, int]]]:
    """Fuse chunk rankings without mixing document and KG score spaces."""
    scores: dict[str, float] = {}
    ranks: dict[str, dict[str, int]] = {}
    for stage, chunk_ids in rankings:
        weight = weights.get(stage, 1.0)
        for rank, chunk_id in enumerate(chunk_ids, 1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + weight / (k + rank)
            ranks.setdefault(chunk_id, {})[stage] = rank
    return sorted(((chunk_id, score, ranks[chunk_id]) for chunk_id, score in scores.items()),
                  key=lambda row: (-row[1], row[0]))
