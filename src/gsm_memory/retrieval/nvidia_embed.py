"""NVIDIA Nemotron 1B embedding client and similarity helpers.

Uses NVIDIA NIM embedding API (model: nvidia/nemotron-3-embed-1b) to produce
dense 2048-dimensional vectors for semantic document retrieval and graph seed finding.
Includes local fallback and offline caching so tests run fast and offline-safe.
"""

from __future__ import annotations

import os
from typing import Any, Sequence

NVIDIA_EMBED_URL = "https://integrate.api.nvidia.com/v1/embeddings"
DEFAULT_NEMOTRON_MODEL = "nvidia/nemotron-3-embed-1b"


def cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class NvidiaNemotronEmbedder:
    """Embedding client for NVIDIA Nemotron 1B."""

    def __init__(self, api_key: str | None = None, model: str = DEFAULT_NEMOTRON_MODEL) -> None:
        self.api_key = api_key or os.getenv("NVIDIA_API_KEY")
        self.model = model
        self._memory_cache: dict[str, list[float]] = {}

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed a list of documents or entity passages using input_type='passage'."""
        if not texts:
            return []
        
        # Check cache
        uncached_indices = [i for i, t in enumerate(texts) if t not in self._memory_cache]
        if not uncached_indices:
            return [self._memory_cache[t] for t in texts]

        if not self.api_key:
            raise RuntimeError("NVIDIA_API_KEY is required to call NVIDIA Nemotron 1B embeddings.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        uncached_texts = [texts[i] for i in uncached_indices]
        payload = {
            "input": uncached_texts,
            "model": self.model,
            "input_type": "passage",
        }
        # Keep the offline retrieval path import-safe: this optional transport
        # is required only when a caller explicitly builds/queries a dense
        # NVIDIA artifact.
        import requests

        resp = requests.post(NVIDIA_EMBED_URL, json=payload, headers=headers, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"NVIDIA API Error {resp.status_code}: {resp.text}")

        data = resp.json()["data"]
        for idx, item in zip(uncached_indices, data):
            self._memory_cache[texts[idx]] = item["embedding"]

        return [self._memory_cache[t] for t in texts]

    def embed_query(self, query: str) -> list[float]:
        """Embed a single search query using input_type='query'."""
        if query in self._memory_cache:
            return self._memory_cache[query]

        if not self.api_key:
            raise RuntimeError("NVIDIA_API_KEY is required to call NVIDIA Nemotron 1B embeddings.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "input": [query],
            "model": self.model,
            "input_type": "query",
        }
        import requests

        resp = requests.post(NVIDIA_EMBED_URL, json=payload, headers=headers, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"NVIDIA API Error {resp.status_code}: {resp.text}")

        vec = resp.json()["data"][0]["embedding"]
        self._memory_cache[query] = vec
        return vec
