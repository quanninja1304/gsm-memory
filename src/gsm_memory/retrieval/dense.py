"""Versioned dense document index over public document chunks.

The index is an explicit BRG artifact.  It is never created implicitly by a
runtime query, and its identity binds the corpus profile, chunk configuration
and embedding model so an index cannot be reused for a different corpus.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol, Sequence

from .documents import Chunk, canonical_hash
from .nvidia_embed import cosine_similarity


class PassageEmbedder(Protocol):
    model: str

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, query: str) -> list[float]: ...


@dataclass(frozen=True)
class DenseIndexIdentity:
    schema_version: str
    profile_id: str
    profile_version: str
    chunk_config_hash: str
    chunk_logical_digest: str
    embedding_model: str
    dimension: int


@dataclass(frozen=True)
class DenseRankedChunk:
    chunk_id: str
    score: float
    rank: int
    stage: str = "dense"


class DenseIndexError(RuntimeError):
    """A dense artifact is missing, malformed, or incompatible with a query."""


class DenseChunkIndex:
    def __init__(self, identity: DenseIndexIdentity, vectors: dict[str, list[float]]) -> None:
        if not vectors:
            raise DenseIndexError("dense index contains no vectors")
        if any(len(vector) != identity.dimension for vector in vectors.values()):
            raise DenseIndexError("dense index vector dimension does not match its manifest")
        self.identity = identity
        self.vectors = vectors

    @classmethod
    def build(cls, chunks: Sequence[Chunk], *, embedder: PassageEmbedder,
              chunk_config_hash: str, profile_version: str) -> "DenseChunkIndex":
        if not chunks:
            raise DenseIndexError("cannot build a dense index over an empty chunk set")
        vectors = embedder.embed_passages([chunk.text for chunk in chunks])
        if len(vectors) != len(chunks):
            raise DenseIndexError("embedder returned a vector count different from the chunk count")
        dimension = len(vectors[0]) if vectors else 0
        if dimension == 0 or any(len(vector) != dimension for vector in vectors):
            raise DenseIndexError("embedder returned empty or inconsistent vector dimensions")
        identity = DenseIndexIdentity(
            schema_version="gsm-dense-index-v1",
            profile_id=chunks[0].profile_id,
            profile_version=profile_version,
            chunk_config_hash=chunk_config_hash,
            chunk_logical_digest=canonical_hash([asdict(chunk) for chunk in sorted(chunks, key=lambda row: row.chunk_id)]),
            embedding_model=embedder.model,
            dimension=dimension,
        )
        return cls(identity, {chunk.chunk_id: vector for chunk, vector in zip(chunks, vectors, strict=True)})

    def save(self, path: Path | str) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {"identity": asdict(self.identity), "vectors": self.vectors}
        target.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")

    @classmethod
    def load(cls, path: Path | str, *, chunks: Sequence[Chunk],
             chunk_config_hash: str, embedding_model: str, profile_version: str) -> "DenseChunkIndex":
        source = Path(path)
        if not source.is_file():
            raise DenseIndexError(f"dense index artifact is missing: {source}")
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
            identity = DenseIndexIdentity(**payload["identity"])
            vectors = {str(key): list(value) for key, value in payload["vectors"].items()}
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise DenseIndexError(f"invalid dense index artifact: {source}") from error
        expected_digest = canonical_hash([asdict(chunk) for chunk in sorted(chunks, key=lambda row: row.chunk_id)])
        if (identity.profile_id != chunks[0].profile_id or identity.profile_version != profile_version
                or identity.chunk_config_hash != chunk_config_hash
                or identity.chunk_logical_digest != expected_digest
                or identity.embedding_model != embedding_model):
            raise DenseIndexError("dense index identity does not match the active corpus/chunker/model")
        expected_ids = {chunk.chunk_id for chunk in chunks}
        if set(vectors) != expected_ids:
            raise DenseIndexError("dense index membership does not match the active chunk inventory")
        return cls(identity, vectors)

    def search(self, query: str, *, embedder: PassageEmbedder, top_k: int,
               allowed_chunk_ids: set[str] | None = None) -> list[DenseRankedChunk]:
        if embedder.model != self.identity.embedding_model:
            raise DenseIndexError("query embedder model does not match the dense index artifact")
        query_vector = embedder.embed_query(query)
        if len(query_vector) != self.identity.dimension:
            raise DenseIndexError("query vector dimension does not match the dense index artifact")
        rows = [
            (cosine_similarity(query_vector, vector), chunk_id)
            for chunk_id, vector in self.vectors.items()
            if allowed_chunk_ids is None or chunk_id in allowed_chunk_ids
        ]
        rows.sort(key=lambda row: (-row[0], row[1]))
        return [DenseRankedChunk(chunk_id, float(score), rank)
                for rank, (score, chunk_id) in enumerate(rows[:top_k], 1)]
