"""Qdrant Vector Retrieval and Hybrid Search Integration for GSM Policies.

Provides:
- QdrantPolicyRetriever: Robust REST-based dense semantic retrieval against Qdrant Cloud
- HybridPolicySearcher: Combines BM25 lexical search + Qdrant dense vector search
  via Reciprocal Rank Fusion (RRF), followed by Cross-Encoder Reranking
  to select the most precise policy clauses for downstream AI.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Sequence

import requests
from dotenv import load_dotenv

from .bm25 import BM25Index
from .documents import Chunk
from .fusion import reciprocal_rank_fusion
from .nvidia_embed import NvidiaNemotronEmbedder
from .rerank import NvidiaReranker

load_dotenv()
logger = logging.getLogger(__name__)


@dataclass
class QdrantPolicyHit:
    chunk_id: str
    source_id: str
    document_revision_id: str
    title: str
    text: str
    score: float
    source_file: str = ""
    category: str = ""
    published_date: str = ""
    alias: str = ""


class QdrantPolicyRetriever:
    """Robust REST-based policy retrieval client for Qdrant Cloud/Local."""

    def __init__(
        self,
        *,
        url: str | None = None,
        api_key: str | None = None,
        collection_name: str | None = None,
        timeout: float | None = None,
        embedder: NvidiaNemotronEmbedder | None = None,
    ) -> None:
        self.url = (url or os.getenv("QDRANT_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("QDRANT_API_KEY", "")
        self.collection_name = collection_name or os.getenv("QDRANT_COLLECTION", "gsm-memory")
        timeout_env = os.getenv("QDRANT_TIMEOUT_SECONDS", "60")
        try:
            self.timeout = float(timeout if timeout is not None else timeout_env)
        except ValueError:
            self.timeout = 60.0

        self.embedder = embedder or NvidiaNemotronEmbedder()
        self._session = requests.Session()
        if self.api_key:
            self._session.headers.update({"api-key": self.api_key})
        self._session.headers.update({"Content-Type": "application/json"})
        self._available: bool | None = None

    def is_available(self) -> bool:
        """Check if Qdrant is configured and reachable."""
        if self._available is True:
            return True
        if not self.url:
            return False
        try:
            resp = self._session.get(
                f"{self.url}/collections/{self.collection_name}",
                timeout=min(self.timeout, 25.0),
            )
            if resp.status_code == 200:
                self._available = True
                return True
            return False
        except Exception as exc:
            logger.warning("Qdrant health check failed: %s", exc)
            return False

    def search(
        self,
        query: str,
        *,
        top_k: int = 10,
        score_threshold: float = 0.0,
    ) -> list[QdrantPolicyHit]:
        """Perform dense embedding search on Qdrant using Nvidia Nemotron 1B vectors."""
        if not self.is_available():
            logger.warning("Qdrant is not available, skipping dense search.")
            return []

        query_vector = self.embedder.embed_query(query)
        endpoint = f"{self.url}/collections/{self.collection_name}/points/search"

        payload: dict[str, Any] = {
            "vector": query_vector,
            "limit": top_k,
            "with_payload": True,
        }
        if score_threshold > 0:
            payload["score_threshold"] = score_threshold

        try:
            resp = self._session.post(endpoint, json=payload, timeout=self.timeout)
            if resp.status_code != 200:
                logger.error("Qdrant search error %s: %s", resp.status_code, resp.text)
                return []
            data = resp.json().get("result", [])
        except Exception as exc:
            logger.error("Error executing search on Qdrant: %s", exc)
            return []

        hits: list[QdrantPolicyHit] = []
        for p in data:
            payload_data = p.get("payload") or {}
            source_id = str(payload_data.get("source_id", ""))

            # Map numeric source_id (e.g. 21 -> P021)
            alias = ""
            if source_id.isdigit():
                alias = f"P{int(source_id):03d}"
            elif source_id.startswith("P"):
                alias = source_id

            hits.append(
                QdrantPolicyHit(
                    chunk_id=str(payload_data.get("chunk_id", p.get("id"))),
                    source_id=source_id,
                    document_revision_id=str(payload_data.get("document_revision_id", "")),
                    title=str(payload_data.get("title", "")),
                    text=str(payload_data.get("text", "")),
                    score=float(p.get("score", 0.0)),
                    source_file=str(payload_data.get("source_file", "")),
                    category=str(payload_data.get("category", "")),
                    published_date=str(payload_data.get("published_date", "")),
                    alias=alias,
                )
            )

        return hits

    def get_stats(self) -> dict[str, Any]:
        """Get collection metrics and point count."""
        if not self.is_available():
            return {"status": "unavailable", "url": self.url}
        try:
            resp = self._session.get(f"{self.url}/collections/{self.collection_name}", timeout=min(self.timeout, 25.0))
            if resp.status_code != 200:
                return {"status": "error", "code": resp.status_code}
            res = resp.json().get("result", {})
            return {
                "status": "connected",
                "collection": self.collection_name,
                "points_count": res.get("points_count", 0),
                "indexed_vectors_count": res.get("indexed_vectors_count", 0),
                "vector_size": res.get("config", {}).get("params", {}).get("vectors", {}).get("size", 2048),
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}


class HybridPolicySearcher:
    """Orchestrates Hybrid BM25 + Qdrant Dense retrieval with Cross-Encoder Reranking."""

    def __init__(
        self,
        *,
        bm25_index: BM25Index,
        chunks: list[Chunk],
        doc_catalog_meta: dict[str, dict[str, str]],
        qdrant_retriever: QdrantPolicyRetriever | None = None,
        reranker: NvidiaReranker | None = None,
        rrf_k: int = 60,
        bm25_weight: float = 0.5,
        dense_weight: float = 0.5,
    ) -> None:
        self.bm25_index = bm25_index
        self.chunks = chunks
        self.chunk_map = {c.chunk_id: c for c in chunks}
        self.doc_catalog_meta = doc_catalog_meta
        self.qdrant_retriever = qdrant_retriever or QdrantPolicyRetriever()
        self.reranker = reranker or NvidiaReranker()
        self.rrf_k = rrf_k
        self.bm25_weight = bm25_weight
        self.dense_weight = dense_weight

    def search_and_rerank(
        self,
        query: str,
        *,
        bm25_top_k: int = 12,
        dense_top_k: int = 12,
        rerank_top_n: int = 15,
        final_top_k: int = 4,
        policy_scope: list[str] | None = None,
        policy_topics: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Run Hybrid (BM25 + Qdrant) search, fuse candidates via RRF, and rerank via Cross-Encoder."""
        receipt: dict[str, Any] = {
            "query": query,
            "policy_scope": policy_scope or [],
            "policy_topics": policy_topics or [],
            "bm25": {"count": 0, "status": "pending"},
            "dense_qdrant": {"count": 0, "status": "pending"},
            "rrf_fused": {"count": 0},
            "rerank": {"count": 0, "status": "pending"},
        }

        # Formulate focused search query if policy_topics provided
        search_query = query
        if policy_topics:
            topics_clean = [t.strip() for t in policy_topics if t.strip()]
            if topics_clean:
                topics_str = " ".join(topics_clean)
                if not any(t.lower() in query.lower() for t in topics_clean):
                    search_query = f"{topics_str} {query}"

        # 1. Lexical Retrieval (BM25)
        bm25_matches = self.bm25_index.search(search_query, top_k=bm25_top_k)
        receipt["bm25"] = {"count": len(bm25_matches), "status": "completed"}

        # Build candidate pool mapping
        candidates_by_id: dict[str, dict[str, Any]] = {}
        bm25_ranked_ids: list[str] = []

        for r in bm25_matches:
            c = self.chunk_map.get(r.chunk_id)
            if not c:
                continue
            meta = self.doc_catalog_meta.get(c.document_revision_id) or self.doc_catalog_meta.get(c.source_id) or {}
            alias = meta.get("alias") or c.document_revision_id[:8]
            title = meta.get("title") or "Văn bản quy chế GSM"
            clause_str = f"#{','.join(c.clause_ids)}" if c.clause_ids else ""

            candidates_by_id[c.chunk_id] = {
                "chunk_id": c.chunk_id,
                "document_revision_id": c.document_revision_id,
                "source_id": c.source_id,
                "alias": alias,
                "title": title,
                "citation_locator": f"{alias}{clause_str}",
                "text": c.text,
                "bm25_score": float(r.score),
                "dense_score": 0.0,
                "source": "bm25",
            }
            bm25_ranked_ids.append(c.chunk_id)

        # 2. Dense Semantic Retrieval (Qdrant)
        dense_ranked_ids: list[str] = []
        qdrant_hits: list[QdrantPolicyHit] = []
        if self.qdrant_retriever.is_available():
            try:
                qdrant_hits = self.qdrant_retriever.search(search_query, top_k=dense_top_k)
                receipt["dense_qdrant"] = {
                    "count": len(qdrant_hits),
                    "status": "completed",
                    "model": "nvidia/nemotron-3-embed-1b",
                }
            except Exception as e:
                receipt["dense_qdrant"] = {"count": 0, "status": "error", "error": str(e)}
        else:
            receipt["dense_qdrant"] = {"count": 0, "status": "unavailable"}

        for hit in qdrant_hits:
            cid = hit.chunk_id
            alias = hit.alias or (
                self.doc_catalog_meta.get(hit.document_revision_id, {}).get("alias")
                or hit.source_id
            )
            title = hit.title or self.doc_catalog_meta.get(hit.document_revision_id, {}).get("title") or "Quy chế GSM"

            if cid in candidates_by_id:
                candidates_by_id[cid]["dense_score"] = float(hit.score)
                candidates_by_id[cid]["source"] = "hybrid"
                if not candidates_by_id[cid]["alias"]:
                    candidates_by_id[cid]["alias"] = alias
            else:
                candidates_by_id[cid] = {
                    "chunk_id": cid,
                    "document_revision_id": getattr(hit, "document_revision_id", ""),
                    "source_id": getattr(hit, "source_id", ""),
                    "alias": alias,
                    "title": title,
                    "citation_locator": alias or "Quy chế GSM",
                    "text": hit.text,
                    "bm25_score": 0.0,
                    "dense_score": float(hit.score),
                    "source": "qdrant_dense",
                }
            dense_ranked_ids.append(cid)

        # 3. Reciprocal Rank Fusion (RRF)
        rankings = []
        if bm25_ranked_ids:
            rankings.append(("bm25", bm25_ranked_ids))
        if dense_ranked_ids:
            rankings.append(("dense", dense_ranked_ids))

        if rankings:
            fused = reciprocal_rank_fusion(
                rankings,
                k=self.rrf_k,
                weights={"bm25": self.bm25_weight, "dense": self.dense_weight},
            )
            fused_candidates: list[dict[str, Any]] = []
            for chunk_id, rrf_score, ranks in fused:
                if chunk_id in candidates_by_id:
                    cand = dict(candidates_by_id[chunk_id])
                    cand["rrf_score"] = rrf_score
                    cand["ranks"] = ranks
                    fused_candidates.append(cand)
        else:
            fused_candidates = list(candidates_by_id.values())

        # If policy_scope is specified (e.g. ['P154', 'P005']), boost those in candidate pool
        if policy_scope:
            target_aliases = {p.strip().upper() for p in policy_scope if p.strip()}
            for cand in fused_candidates:
                if cand.get("alias", "").upper() in target_aliases:
                    cand["rrf_score"] = cand.get("rrf_score", 0.0) + 1.5

        # If policy_topics are specified, boost candidates containing topic keywords
        if policy_topics:
            topic_keywords = [t.lower().strip() for t in policy_topics if t.strip()]
            for cand in fused_candidates:
                blob = f"{cand.get('alias', '')} {cand.get('title', '')} {cand.get('text', '')}".lower()
                matches = sum(1 for kw in topic_keywords if kw in blob)
                if matches > 0:
                    cand["rrf_score"] = cand.get("rrf_score", 0.0) + (0.5 * matches)

        fused_candidates.sort(key=lambda x: -x.get("rrf_score", 0.0))

        receipt["rrf_fused"]["count"] = len(fused_candidates)

        # 4. Cross-Encoder Reranking
        to_rerank = fused_candidates[:rerank_top_n]
        reranked_candidates = list(to_rerank)

        if self.reranker and to_rerank:
            passages = [f"[{c['alias']} - {c['title']}] {c['text']}" for c in to_rerank]
            try:
                rerank_query = f"Quy chế về {' '.join(policy_topics)}: {query}" if policy_topics else query
                scores = self.reranker.rank(rerank_query, passages)
                for cand, score in zip(reranked_candidates, scores):
                    cand["rerank_score"] = score
                    cand["stage"] = "cross_encoder"

                reranked_candidates.sort(key=lambda c: -c.get("rerank_score", 0.0))
                receipt["rerank"] = {
                    "count": len(reranked_candidates),
                    "status": "completed",
                    "model": getattr(self.reranker, "model", "nvidia/llama-nemotron-rerank-vl-1b-v2"),
                }
            except Exception as e:
                logger.warning("Cross-encoder reranking failed, falling back to RRF: %s", e)
                receipt["rerank"] = {"count": 0, "status": "fallback", "error": str(e)}
                for cand in reranked_candidates:
                    cand["rerank_score"] = cand.get("rrf_score", 0.0)
        else:
            for cand in reranked_candidates:
                cand["rerank_score"] = cand.get("rrf_score", 0.0)
            receipt["rerank"] = {"count": 0, "status": "skipped"}

        # 5. Format Evidence Output for LLM Prompt and UI
        selected_candidates = reranked_candidates[:final_top_k]
        evidence_list: list[dict[str, Any]] = []

        for c in selected_candidates:
            alias = c.get("alias") or "Quy chế GSM"
            title = c.get("title") or "Văn bản quy chế GSM"
            locator = c.get("citation_locator") or alias
            evidence_list.append(
                {
                    "source_kind": "document",
                    "evidence_id": f"doc-{c['chunk_id']}",
                    "document_revision_id": c.get("document_revision_id", ""),
                    "source_id": c.get("source_id", ""),
                    "citation_locator": locator,
                    "policy_alias": alias,
                    "policy_title": title,
                    "chunk_text": c.get("text", ""),
                    "content": f"[{alias} - {title}] {c['text']}",
                    "score": float(c.get("rerank_score", c.get("rrf_score", 0.0))),
                    "retrieval_method": "hybrid_qdrant_bm25_rerank",
                    "meta": {
                        "bm25_score": c.get("bm25_score", 0.0),
                        "dense_score": c.get("dense_score", 0.0),
                        "rrf_score": c.get("rrf_score", 0.0),
                        "rerank_score": c.get("rerank_score", 0.0),
                        "source": c.get("source", "hybrid"),
                    },
                }
            )

        return evidence_list, receipt
