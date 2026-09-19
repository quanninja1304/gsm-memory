"""Small deterministic BM25 implementation used as the offline micro-baseline."""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass

from .documents import Chunk


def tokenize(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFC", text).casefold()
    return re.findall(r"[\w]+", normalized, flags=re.UNICODE)


@dataclass(frozen=True)
class RankedChunk:
    chunk_id: str
    source_id: str
    document_revision_id: str
    score: float
    rank: int
    stage: str = "bm25"


class BM25Index:
    def __init__(self, chunks: list[Chunk], *, k1: float = 1.2, b: float = 0.75):
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.terms = [Counter(tokenize(c.text)) for c in chunks]
        self.lengths = [sum(row.values()) for row in self.terms]
        self.avgdl = sum(self.lengths) / len(self.lengths) if self.lengths else 0.0
        self.df = Counter(term for row in self.terms for term in row)

    def search(self, query: str, *, top_k: int = 10, allowed_source_ids: set[str] | None = None) -> list[RankedChunk]:
        query_terms = tokenize(query)
        scored: list[tuple[float, Chunk]] = []
        total = len(self.chunks)
        for chunk, frequencies, length in zip(self.chunks, self.terms, self.lengths, strict=True):
            if allowed_source_ids is not None and chunk.source_id not in allowed_source_ids:
                continue
            score = 0.0
            for term in query_terms:
                frequency = frequencies[term]
                if not frequency:
                    continue
                idf = math.log(1.0 + (total - self.df[term] + 0.5) / (self.df[term] + 0.5))
                denominator = frequency + self.k1 * (1.0 - self.b + self.b * length / (self.avgdl or 1.0))
                score += idf * frequency * (self.k1 + 1.0) / denominator
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda pair: (-pair[0], pair[1].chunk_id))
        return [RankedChunk(c.chunk_id, c.source_id, c.document_revision_id, score, rank) for rank, (score, c) in enumerate(scored[:top_k], 1)]

    @staticmethod
    def serializable(results: list[RankedChunk]) -> list[dict[str, object]]:
        return [asdict(row) for row in results]

