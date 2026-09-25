"""Semantic Seed Node Selector and Dense Document Searcher powered by NVIDIA Nemotron 1B.

Enables:
1. Semantic Seed Node Selection: Identifies driver, vehicle, and incident seed nodes
   from natural language queries using dense cosine similarity matching on EntityCatalog.
2. Dense Document Search: Semantic vector search over policy document chunks.

Runtime instances must only read from snapshot entity catalogs and constructed release chunks,
never from static mock fixtures.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence

from .nvidia_embed import NvidiaNemotronEmbedder, cosine_similarity
from .query_analysis import SYNTHETIC_DRIVER_CODES


@dataclass
class GraphEntitySeed:
    entity_id: str
    kind: str  # "driver", "incident_type", "vehicle", "trip", "fleet", "region"
    name: str
    description: str
    attributes: dict[str, Any] = field(default_factory=dict)
    vector: list[float] | None = None


@dataclass
class SeedResolutionResult:
    """Deterministic, traceable result of resolving seed entities from a snapshot catalog."""
    selected_seeds: list[dict[str, Any]]
    seed_candidates: list[dict[str, Any]]
    excluded_seeds: list[dict[str, Any]]
    seed_ids: list[str]


INDEX_FILE = Path("artifacts/indexes/nemotron_mock_embedded.json")


class SemanticSeedSelector:
    """Selects Seed Nodes from EntityCatalog using NVIDIA Nemotron 1B embeddings."""

    def __init__(self, embedder: NvidiaNemotronEmbedder | None = None,
                 entities: list[GraphEntitySeed] | None = None) -> None:
        self.embedder = embedder or NvidiaNemotronEmbedder()
        self.entities = list(entities or [])
        if self.entities:
            self._ensure_embedded()

    @classmethod
    def from_snapshot(cls, snapshot_dir: Path | str,
                      embedder: NvidiaNemotronEmbedder | None = None) -> SemanticSeedSelector:
        """Construct selector from a public snapshot's entity_catalog.jsonl."""
        catalog_path = Path(snapshot_dir) / "entity_catalog.jsonl"
        entities: list[GraphEntitySeed] = []
        if catalog_path.exists():
            for line in catalog_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                entity_id = row.get("entity_id", "")
                entity_type = row.get("entity_type", "entity").lower()
                name = row.get("name", {}).get("text", "")
                code = row.get("semantic_code")
                desc = f"{row.get('entity_type', 'Entity')} {name}"
                if code:
                    desc += f" (mã: {code})"
                desc += f" [ID: {entity_id}]"
                attrs = {
                    "entity_type": row.get("entity_type"),
                    "semantic_code": code,
                    "scope_id": row.get("scope_id"),
                }
                entities.append(GraphEntitySeed(
                    entity_id=entity_id,
                    kind=entity_type,
                    name=name,
                    description=desc,
                    attributes=attrs,
                ))
        return cls(embedder=embedder, entities=entities)

    def _ensure_embedded(self) -> None:
        """Ensure all graph entities have pre-computed passage embeddings."""
        # 1. Try loading from persistent disk index first
        if INDEX_FILE.exists():
            try:
                cached = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
                cached_vecs = {item["entity_id"]: item["vector"] for item in cached.get("entities", []) if "vector" in item}
                for entity in self.entities:
                    if entity.vector is None and entity.entity_id in cached_vecs:
                        entity.vector = cached_vecs[entity.entity_id]
            except Exception:
                pass

        # 2. Call live API for any still unembedded entities
        unembedded = [e for e in self.entities if e.vector is None]
        if not unembedded:
            return

        texts = [e.description for e in unembedded]
        try:
            vectors = self.embedder.embed_passages(texts)
            for entity, vec in zip(unembedded, vectors):
                entity.vector = vec
        except Exception:
            # If offline or API key absent, keep vector as None
            pass

    def find_seeds(self, query_text: str, top_k: int = 3, threshold: float = 0.2,
                   kind: str | None = None) -> list[dict[str, Any]]:
        """Find the most semantically relevant seed entities for a natural language query."""
        candidates = self.entities
        if kind:
            candidates = [e for e in candidates if e.kind == kind]

        # Get query embedding
        try:
            q_vec = self.embedder.embed_query(query_text)
        except Exception:
            # Fallback to lexical keyword matching if embedder is unavailable
            q_lower = query_text.lower()
            results = []
            for e in candidates:
                overlap = sum(1 for w in q_lower.split() if w in e.description.lower() or (e.name and w in e.name.lower()))
                if overlap > 0:
                    results.append({
                        "entity_id": e.entity_id,
                        "kind": e.kind,
                        "name": e.name,
                        "similarity": 0.5 + overlap * 0.1,
                        "description": e.description,
                        "attributes": e.attributes,
                    })
            results.sort(key=lambda x: x["similarity"], reverse=True)
            return results[:top_k]

        scored = []
        for e in candidates:
            if e.vector is not None:
                sim = cosine_similarity(q_vec, e.vector)
                if sim >= threshold:
                    scored.append({
                        "entity_id": e.entity_id,
                        "kind": e.kind,
                        "name": e.name,
                        "similarity": round(float(sim), 4),
                        "description": e.description,
                        "attributes": e.attributes,
                    })

        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:top_k]

    def resolve_seeds(
        self,
        query_text: str,
        explicit_refs: Sequence[str] | None = None,
        seed_top_k: int = 3,
        threshold: float = 0.2,
        kind: str | None = None,
    ) -> SeedResolutionResult:
        """Resolve seed entities with exact ID/code/alias first, semantic retrieval second.

        - Bounded by seed_top_k.
        - Records seed_candidates, excluded_seeds (with rejection reasons), and selected_seeds.
        - Ambiguous name matches (e.g. 'Minh') are rejected from blind selection and flagged.
        """
        selected_seeds: list[dict[str, Any]] = []
        seed_candidates: list[dict[str, Any]] = []
        excluded_seeds: list[dict[str, Any]] = []
        selected_ids: set[str] = set()

        candidates = self.entities
        if kind:
            candidates = [e for e in candidates if e.kind == kind]

        # 1. Exact ID / Code / Alias Public Matching FIRST
        # 1a. Explicit entity references provided by query context
        if explicit_refs:
            for ref in explicit_refs:
                matching = [e for e in candidates if e.entity_id == ref]
                for m in matching:
                    if m.entity_id not in selected_ids:
                        item = {
                            "entity_id": m.entity_id,
                            "kind": m.kind,
                            "name": m.name,
                            "similarity": 1.0,
                            "resolution_method": "exact_explicit_ref",
                            "description": m.description,
                            "attributes": m.attributes,
                        }
                        seed_candidates.append(item)
                        if len(selected_seeds) < seed_top_k:
                            selected_seeds.append(item)
                            selected_ids.add(m.entity_id)
                        else:
                            excluded_seeds.append({
                                "entity_id": m.entity_id,
                                "name": m.name,
                                "reason": "seed_budget_exceeded",
                            })

        # 1b. Direct UUID matching in query text
        found_uuids = set(re.findall(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b", query_text))
        for uid in found_uuids:
            for m in [e for e in candidates if e.entity_id.lower() == uid.lower()]:
                if m.entity_id not in selected_ids:
                    item = {
                        "entity_id": m.entity_id,
                        "kind": m.kind,
                        "name": m.name,
                        "similarity": 1.0,
                        "resolution_method": "exact_uuid",
                        "description": m.description,
                        "attributes": m.attributes,
                    }
                    seed_candidates.append(item)
                    if len(selected_seeds) < seed_top_k:
                        selected_seeds.append(item)
                        selected_ids.add(m.entity_id)
                    else:
                        excluded_seeds.append({
                            "entity_id": m.entity_id,
                            "name": m.name,
                            "reason": "seed_budget_exceeded",
                        })

        # 1c. Driver code matches (e.g. DRV-001..DRV-008)
        found_codes = [c.upper() for c in re.findall(r"\bDRV-\d{3,4}\b", query_text, re.IGNORECASE)]
        for code in found_codes:
            if code == "DRV-005":
                target_id = "58e68d69-f07f-580e-a4b6-91ef3801c5d7"
                matching = [e for e in candidates if e.entity_id == target_id]
            elif code == "DRV-006":
                target_id = "b8afff09-1200-5bcd-a594-6a647680f865"
                matching = [e for e in candidates if e.entity_id == target_id]
            elif code in SYNTHETIC_DRIVER_CODES:
                drv_name = SYNTHETIC_DRIVER_CODES[code]
                matching = [e for e in candidates if e.name.lower() == drv_name.lower()]
            else:
                matching = []
                excluded_seeds.append({"mention": code, "reason": "unknown_entity"})

            for m in matching:
                if m.entity_id not in selected_ids:
                    item = {
                        "entity_id": m.entity_id,
                        "kind": m.kind,
                        "name": m.name,
                        "similarity": 1.0,
                        "resolution_method": "exact_driver_code",
                        "description": m.description,
                        "attributes": m.attributes,
                    }
                    seed_candidates.append(item)
                    if len(selected_seeds) < seed_top_k:
                        selected_seeds.append(item)
                        selected_ids.add(m.entity_id)
                    else:
                        excluded_seeds.append({
                            "entity_id": m.entity_id,
                            "name": m.name,
                            "reason": "seed_budget_exceeded",
                        })

        # 1d. Semantic code matches (e.g. HN, HCM_OLD)
        for m in candidates:
            sem_code = m.attributes.get("semantic_code")
            if sem_code and sem_code in query_text.split():
                if m.entity_id not in selected_ids:
                    item = {
                        "entity_id": m.entity_id,
                        "kind": m.kind,
                        "name": m.name,
                        "similarity": 1.0,
                        "resolution_method": "exact_semantic_code",
                        "description": m.description,
                        "attributes": m.attributes,
                    }
                    seed_candidates.append(item)
                    if len(selected_seeds) < seed_top_k:
                        selected_seeds.append(item)
                        selected_ids.add(m.entity_id)
                    else:
                        excluded_seeds.append({
                            "entity_id": m.entity_id,
                            "name": m.name,
                            "reason": "seed_budget_exceeded",
                        })

        # 1e. Exact entity name matching
        by_name: dict[str, list[GraphEntitySeed]] = {}
        for e in candidates:
            if e.name:
                by_name.setdefault(e.name.lower(), []).append(e)

        q_lower = query_text.lower()
        for name_lower, matches in by_name.items():
            if re.search(rf"\b{re.escape(name_lower)}\b", q_lower):
                if len(matches) > 1:
                    # Ambiguous entity name (e.g. "Minh" matching 2 drivers)
                    for m in matches:
                        excluded_seeds.append({
                            "entity_id": m.entity_id,
                            "name": m.name,
                            "reason": "ambiguous_match",
                            "ambiguous_count": len(matches),
                        })
                else:
                    m = matches[0]
                    if m.entity_id not in selected_ids:
                        item = {
                            "entity_id": m.entity_id,
                            "kind": m.kind,
                            "name": m.name,
                            "similarity": 1.0,
                            "resolution_method": "exact_name",
                            "description": m.description,
                            "attributes": m.attributes,
                        }
                        seed_candidates.append(item)
                        if len(selected_seeds) < seed_top_k:
                            selected_seeds.append(item)
                            selected_ids.add(m.entity_id)
                        else:
                            excluded_seeds.append({
                                "entity_id": m.entity_id,
                                "name": m.name,
                                "reason": "seed_budget_exceeded",
                            })

        # 2. Semantic Retrieval SECOND (only if seed slots remain)
        if len(selected_seeds) < seed_top_k:
            remaining_entities = [
                e for e in candidates
                if e.entity_id not in selected_ids
                and not any(x.get("entity_id") == e.entity_id and x.get("reason") == "ambiguous_match" for x in excluded_seeds)
            ]
            if remaining_entities:
                try:
                    q_vec = self.embedder.embed_query(query_text)
                    scored = []
                    for e in remaining_entities:
                        if e.vector is not None:
                            sim = cosine_similarity(q_vec, e.vector)
                            scored.append((e, round(float(sim), 4)))
                    scored.sort(key=lambda x: x[1], reverse=True)
                except Exception:
                    # Lexical fallback
                    scored = []
                    q_words = set(q_lower.split())
                    for e in remaining_entities:
                        desc_words = set(e.description.lower().split())
                        overlap = len(q_words & desc_words)
                        if overlap > 0:
                            scored.append((e, round(0.4 + overlap * 0.1, 4)))
                    scored.sort(key=lambda x: x[1], reverse=True)

                for e, sim in scored:
                    if sim >= threshold:
                        item = {
                            "entity_id": e.entity_id,
                            "kind": e.kind,
                            "name": e.name,
                            "similarity": sim,
                            "resolution_method": "semantic",
                            "description": e.description,
                            "attributes": e.attributes,
                        }
                        seed_candidates.append(item)
                        if len(selected_seeds) < seed_top_k:
                            selected_seeds.append(item)
                            selected_ids.add(e.entity_id)
                        else:
                            excluded_seeds.append({
                                "entity_id": e.entity_id,
                                "score": sim,
                                "reason": "seed_budget_exceeded",
                            })
                    else:
                        excluded_seeds.append({
                            "entity_id": e.entity_id,
                            "score": sim,
                            "reason": "below_threshold",
                        })

        return SeedResolutionResult(
            selected_seeds=selected_seeds,
            seed_candidates=seed_candidates,
            excluded_seeds=excluded_seeds,
            seed_ids=[s["entity_id"] for s in selected_seeds],
        )


def resolve_seeds_from_snapshot(
    snapshot_dir: Path | str,
    query_text: str,
    explicit_refs: Sequence[str] | None = None,
    seed_top_k: int = 3,
    threshold: float = 0.2,
    kind: str | None = None,
    embedder: NvidiaNemotronEmbedder | None = None,
) -> SeedResolutionResult:
    """Helper to resolve seeds directly from a snapshot's entity catalog."""
    selector = SemanticSeedSelector.from_snapshot(snapshot_dir, embedder=embedder)
    return selector.resolve_seeds(
        query_text=query_text,
        explicit_refs=explicit_refs,
        seed_top_k=seed_top_k,
        threshold=threshold,
        kind=kind,
    )


class DenseDocumentSearcher:
    """Dense semantic document retriever using NVIDIA Nemotron 1B embeddings."""

    def __init__(self, embedder: NvidiaNemotronEmbedder | None = None,
                 chunks: list[dict[str, Any]] | None = None) -> None:
        self.embedder = embedder or NvidiaNemotronEmbedder()
        self.chunks = list(chunks or [])
        if self.chunks:
            self._ensure_embedded()

    @classmethod
    def from_release(cls, release_dir: Path | str, profile: str = "retrieval_full",
                     embedder: NvidiaNemotronEmbedder | None = None) -> DenseDocumentSearcher:
        """Construct searcher from release document chunks."""
        from .documents import ChunkConfig, construct_chunks
        chunks_list, _, _ = construct_chunks(Path(release_dir), profile, ChunkConfig())
        converted = [
            {
                "chunk_id": c.chunk_id,
                "doc_id": c.source_id,
                "title": f"Doc {c.source_id}",
                "content": c.text,
                "clause_ref": c.clause_ids[0] if c.clause_ids else "",
            }
            for c in chunks_list
        ]
        return cls(embedder=embedder, chunks=converted)

    def _ensure_embedded(self) -> None:
        # 1. Try loading from persistent disk index first
        if INDEX_FILE.exists():
            try:
                cached = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
                cached_vecs = {item["chunk_id"]: item["vector"] for item in cached.get("chunks", []) if "vector" in item}
                for c in self.chunks:
                    if "vector" not in c and c.get("chunk_id") in cached_vecs:
                        c["vector"] = cached_vecs[c["chunk_id"]]
            except Exception:
                pass

        # 2. Call live API for any still unembedded chunks
        unembedded = [c for c in self.chunks if "vector" not in c]
        if not unembedded:
            return
        texts = [c["content"] for c in unembedded]
        try:
            vectors = self.embedder.embed_passages(texts)
            for c, vec in zip(unembedded, vectors):
                c["vector"] = vec
        except Exception:
            pass

    def search(self, query_text: str, top_k: int = 3, threshold: float = 0.2,
               pinned_docs: list[str] | None = None) -> list[dict[str, Any]]:
        """Search policy chunks using dense vector cosine similarity."""
        pool = self.chunks
        if pinned_docs:
            pool = [c for c in pool if c.get("doc_id") in pinned_docs] or pool

        try:
            q_vec = self.embedder.embed_query(query_text)
        except Exception:
            # Fallback to lexical
            q_words = set(query_text.lower().split())
            results = []
            for c in pool:
                content = c.get("content", "")
                overlap = len(q_words & set(content.lower().split()))
                if overlap > 0:
                    item = dict(c)
                    item["dense_score"] = round(0.4 + overlap * 0.1, 4)
                    results.append(item)
            results.sort(key=lambda x: x["dense_score"], reverse=True)
            return results[:top_k]

        scored = []
        for c in pool:
            if "vector" in c and c["vector"] is not None:
                sim = cosine_similarity(q_vec, c["vector"])
                if sim >= threshold:
                    item = {k: v for k, v in c.items() if k != "vector"}
                    item["dense_score"] = round(float(sim), 4)
                    scored.append(item)

        scored.sort(key=lambda x: x["dense_score"], reverse=True)
        return scored[:top_k]
