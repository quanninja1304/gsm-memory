"""Versioned retrieval configuration pinning models, chunker, RRF, and budgets."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class RetrievalConfig(BaseModel):
    """Pinned, reproducible configuration for hybrid retrieval and context selection.

    Pins:
    - Embedding model and reader/reranker models
    - Chunker specifications (token window, overlap, tokenizer)
    - Fusion weights and RRF smoothing constant
    - Top-k retrieval budgets for documents, KG, and dense search
    - Graph traversal bounds (hops, nodes, edges)
    - Deterministic token budget and modality quotas
    """

    model_config = ConfigDict(extra="forbid")

    # Versioning
    config_version: str = "1.0.0"
    description: str = "Canonical pinned retrieval configuration for GSM Agent Phase B"

    # Models
    embedding_model: str = "nvidia/nemotron-3-embed-1b"
    llm_model: str = "google/gemini-2.5-flash"
    query_planner_provider: Literal["rule_based", "openrouter"] = "rule_based"
    query_planner_max_output_tokens: int = 900
    reranker_model: str | None = None
    dense_index_path: str | None = None

    # Chunker
    chunker: str = "gsm-word-span-v1"
    tokenizer: str = "unicode-word-regex-v1"
    max_tokens: int = 180
    overlap: int = 30

    # RRF (Reciprocal Rank Fusion)
    rrf_k: int = 60
    bm25_weight: float = 0.5
    dense_weight: float = 0.5

    # Top-K Limits
    document_top_k: int = 10
    dense_top_k: int = 10
    bm25_top_k: int = 10
    rerank_top_n: int = 20
    kg_top_k: int = 40
    seed_top_k: int = 3

    # Graph Budgets
    max_hops: int = 2
    max_nodes: int = 20
    max_edges: int = 30
    per_node_fanout: int = 10

    # Token & Selection Budgets
    token_budget: int = 1800
    max_selected_items: int = 22
    modality_quotas: dict[str, int] = Field(
        default_factory=lambda: {
            "computation": 1,
            "document": 2,
            "kg": 2,
            "entity_catalog": 1,
            "definition": 1,
            "coverage": 1,
        }
    )
    # Modality Deadlines and Timeouts (milliseconds)
    document_timeout_ms: float = 5000.0
    kg_timeout_ms: float = 5000.0
    computation_timeout_ms: float = 5000.0
    overall_timeout_ms: float = 15000.0

    def config_hash(self) -> str:
        """Deterministic SHA-256 fingerprint of the canonical configuration."""
        canonical_json = json.dumps(self.model_dump(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def dense_index_config_hash(self) -> str:
        """Fingerprint only inputs that define dense-vector compatibility.

        The artifact file path, query budgets and reranker must not invalidate a
        prebuilt index; corpus membership is bound separately by the index.
        """
        identity = {
            "config_version": self.config_version,
            "embedding_model": self.embedding_model,
            "chunker": self.chunker,
            "tokenizer": self.tokenizer,
            "max_tokens": self.max_tokens,
            "overlap": self.overlap,
        }
        return hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

    def save(self, path: Path | str) -> None:
        """Persist configuration to a formatted JSON file."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.model_dump(), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path | str) -> RetrievalConfig:
        """Load and validate configuration from a JSON file."""
        target = Path(path)
        data = json.loads(target.read_text(encoding="utf-8"))
        return cls.model_validate(data)
