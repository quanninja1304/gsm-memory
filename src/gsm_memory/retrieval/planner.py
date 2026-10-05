"""RetrievalPlanner for modality-selective, proof-preserving retrieval execution.

Enforces strict modality allocation according to intent:
- POLICY_LOOKUP  -> document only (BM25 / Dense chunks)
- DRIVER_HISTORY -> KG only (Graphiti Mode A / ledger assertions + Entity Catalog)
- METRIC_CHECK   -> computation + definition/KG when needed
- HYBRID_REASONING -> all three modalities (document, KG, computation)

Ensures retrieval does not query KG or documents unconditionally.
Handles ambiguous and unknown entities with proper diagnostics and short-circuiting.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from .bm25 import BM25Index
from .config import RetrievalConfig
from .dense import DenseChunkIndex, PassageEmbedder
from .documents import Chunk
from .fusion import reciprocal_rank_fusion
from .offline import (
    _document_candidates,
    _kg_candidates,
    chunk_candidate,
    computation_candidates,
    document_allowed_source_ids,
    entity_catalog_candidates,
    hybrid_union,
    select_public,
)
from .query_analysis import IntentType, ModalityType, QueryPlan
from .rerank import Reranker, rerank_candidates


class RetrievalPlan(BaseModel):
    """Specific modality allocation and execution instructions for a query."""

    model_config = ConfigDict(extra="forbid")

    intent: IntentType
    modalities: list[ModalityType]

    enable_document: bool = False
    enable_kg: bool = False
    enable_computation: bool = False

    pinned_documents: list[str] = Field(default_factory=list)
    target_predicates: list[str] = Field(default_factory=list)
    target_metric: str | None = None
    entity_refs: list[str] = Field(default_factory=list)
    unresolved_entities: list[str] = Field(default_factory=list)
    unresolved_entity: str | None = None
    is_ambiguous: bool = False
    notes: list[str] = Field(default_factory=list)


class PlannedRetrievalResult(BaseModel):
    """Complete result of executing a planned retrieval."""

    model_config = ConfigDict(extra="forbid")

    plan: RetrievalPlan
    candidates: list[dict[str, Any]]
    selected_evidence: list[dict[str, Any]]
    selector_excluded: list[dict[str, Any]]
    modality_candidates: dict[str, list[dict[str, Any]]]
    latency_ms: dict[str, float]
    receipts: dict[str, Any] = Field(default_factory=dict)
    start_times: dict[str, float] = Field(default_factory=dict)
    wall_time_ms: float = 0.0


class RetrievalPlanner:
    """Plans and orchestrates modality-selective retrieval without unconditional searches."""

    def __init__(self, config: RetrievalConfig | None = None, *,
                 dense_index: DenseChunkIndex | None = None,
                 embedder: PassageEmbedder | None = None,
                 reranker: Reranker | None = None) -> None:
        self.config = config or RetrievalConfig()
        self.dense_index = dense_index
        self.embedder = embedder
        self.reranker = reranker

    def _document_pipeline(self, query: dict[str, Any], chunks: list[Chunk], index: BM25Index,
                           snapshot_dir: Path, top_k: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Retrieve public document chunks, fuse dense/BM25, then rerank bounded chunks."""
        bm25_candidates = _document_candidates(query, chunks, index, top_k=top_k, snapshot_dir=snapshot_dir)
        receipt: dict[str, Any] = {
            "bm25": {"status": "completed", "count": len(bm25_candidates)},
            "dense": {"status": "blocked_model_artifact", "count": 0},
            "reranker": {"status": "blocked_model_artifact", "count": 0},
        }
        if self.dense_index is None or self.embedder is None:
            return bm25_candidates, receipt

        allowed_sources, _ = document_allowed_source_ids(query, snapshot_dir)
        by_id = {chunk.chunk_id: chunk for chunk in chunks}
        allowed_ids = {chunk.chunk_id for chunk in chunks if chunk.source_id in allowed_sources}
        try:
            dense_rows = self.dense_index.search(query["query"], embedder=self.embedder,
                                                 top_k=self.config.dense_top_k,
                                                 allowed_chunk_ids=allowed_ids)
        except Exception as exc:
            # A runtime provider failure must not remove the independently
            # available lexical evidence.  The terminal receipt distinguishes
            # a missing credential from a real request/index failure.
            status = "blocked_provider" if "API_KEY" in str(exc) else "error"
            receipt["dense"] = {"status": status, "count": 0, "error": str(exc)}
            dense_rows = []
        bm25_ids = [row["evidence_id"].removeprefix("chunk:") for row in bm25_candidates]
        dense_ids = [row.chunk_id for row in dense_rows]
        if dense_rows:
            fused = reciprocal_rank_fusion(
                [("bm25", bm25_ids), ("dense", dense_ids)], k=self.config.rrf_k,
                weights={"bm25": self.config.bm25_weight, "dense": self.config.dense_weight},
            )
            documents = [
                chunk_candidate(query, by_id[chunk_id], rank=rank, score=score, stage="rrf",
                                rank_components=ranks)
                for rank, (chunk_id, score, ranks) in enumerate(fused[:top_k], 1)
            ]
            receipt["dense"] = {"status": "completed", "model": self.dense_index.identity.embedding_model,
                                "count": len(dense_rows), "index_identity": self.dense_index.identity.__dict__}
        else:
            documents = bm25_candidates
        if self.reranker is None:
            return documents, receipt
        try:
            documents, rerank_receipt = rerank_candidates(
                query["query"], documents, reranker=self.reranker, top_n=min(self.config.rerank_top_n, len(documents))
            )
            receipt["reranker"] = rerank_receipt
        except Exception as exc:
            status = "blocked_provider" if "API_KEY" in str(exc) else "error"
            receipt["reranker"] = {"status": status, "count": 0, "error": str(exc)}
        return documents, receipt

    def plan(self, query_plan: QueryPlan, query: Mapping[str, Any] | None = None) -> RetrievalPlan:
        """Create a targeted execution plan from an analyzed QueryPlan."""
        intent = query_plan.intent
        q_text = str(query.get("query", "") if query else "").lower()
        app_ctx = (query.get("application_context") or {}) if query else {}

        # 1. Ambiguity & Unresolved Entity Detection
        unresolved = list(query_plan.unresolved_entities)
        if query_plan.unresolved_entity and query_plan.unresolved_entity not in unresolved:
            unresolved.append(query_plan.unresolved_entity)
        is_ambiguous = bool(unresolved) or (intent == "DRIVER_HISTORY" and not query_plan.entity_refs)

        notes: list[str] = []
        if is_ambiguous:
            notes.append(f"Query has ambiguous or unresolved entity: {unresolved}")

        # 2. Modality Toggling Based on Intent Contract
        if intent == "POLICY_LOOKUP":
            # POLICY_LOOKUP -> document only
            enable_doc = True
            enable_kg = False
            enable_comp = False
            modalities: list[ModalityType] = ["document"]

        elif intent == "DRIVER_HISTORY":
            # DRIVER_HISTORY -> KG only
            enable_doc = False
            enable_kg = not is_ambiguous or bool(query_plan.entity_refs)
            enable_comp = False
            modalities = ["kg"]
            if is_ambiguous and not query_plan.entity_refs:
                notes.append("Ambiguous driver entity with no resolved refs; KG search disabled.")

        elif intent == "METRIC_CHECK":
            # METRIC_CHECK -> computation + definition/KG when needed
            enable_comp = not is_ambiguous or bool(query_plan.entity_refs)
            if is_ambiguous and not query_plan.entity_refs:
                notes.append("Subject entity unresolved; computation disabled.")

            # Check if definition is requested/needed
            def_refs = app_ctx.get("definition_refs") or []
            has_def_keywords = any(kw in q_text for kw in ["định nghĩa", "chu kỳ", "hiểu thế nào", "quy định", "tiêu chuẩn"])
            needs_definition = bool(def_refs) or has_def_keywords or bool(query_plan.document_filters.pinned_documents)

            # Check if KG event lookup is needed
            needs_kg = bool(query_plan.entity_refs) and any(
                kw in q_text for kw in ["sự cố", "cuốc xe", "chuyến xe", "trạng thái", "bị hủy", "hủy"]
            )

            enable_doc = needs_definition
            enable_kg = needs_kg

            modalities = []
            if enable_comp:
                modalities.append("computation")
            if enable_doc:
                modalities.append("document")
            if enable_kg:
                modalities.append("kg")
            if not modalities:
                modalities = ["computation"]

        elif intent == "HYBRID_REASONING":
            # HYBRID_REASONING -> all three
            enable_doc = True
            enable_kg = not is_ambiguous or bool(query_plan.entity_refs)
            enable_comp = not is_ambiguous or bool(query_plan.entity_refs)
            modalities = ["document"]
            if enable_kg:
                modalities.append("kg")
            if enable_comp:
                modalities.append("computation")

        else:
            enable_doc = True
            enable_kg = False
            enable_comp = False
            modalities = ["document"]

        return RetrievalPlan(
            intent=intent,
            modalities=modalities,
            enable_document=enable_doc,
            enable_kg=enable_kg,
            enable_computation=enable_comp,
            pinned_documents=list(query_plan.document_filters.pinned_documents),
            target_predicates=list(query_plan.graph_filters.target_predicates),
            target_metric=query_plan.computation_filters.target_metric,
            entity_refs=list(query_plan.entity_refs),
            unresolved_entities=unresolved,
            unresolved_entity="unresolved_entity" if unresolved else None,
            is_ambiguous=is_ambiguous,
            notes=notes,
        )

    async def execute_async(
        self,
        plan: RetrievalPlan,
        query: dict[str, Any],
        chunks: list[Chunk],
        index: BM25Index,
        snapshot_dir: Path,
        graph_result: dict[str, Any] | None = None,
        document_top_k: int = 10,
        token_budget: int = 1800,
        max_items: int = 22,
    ) -> PlannedRetrievalResult:
        """Asynchronously executes enabled retrieval modalities in parallel using asyncio.TaskGroup.

        Enforces:
        - Concurrent launch of enabled modalities (document, KG, computation)
        - Per-modality deadlines, timeouts, and auditable receipts
        - Terminal status requirement before hybrid merge
        - Wall time and branch latency instrumentation
        """
        wall_tick = time.perf_counter()
        start_times: dict[str, float] = {}
        latency_ms: dict[str, float] = {
            "document": 0.0,
            "kg_search": 0.0,
            "eligibility_normalization": 0.0,
            "computation": 0.0,
            "hybrid_merge": 0.0,
            "selection": 0.0,
            "wall_time_ms": 0.0,
            "total_pre_reader": 0.0,
        }
        receipts: dict[str, Any] = {}
        modality_candidates: dict[str, list[dict[str, Any]]] = {
            "document": [],
            "kg": [],
            "computation": [],
            "coverage": [],
            "entity_catalog": [],
        }

        docs: list[dict[str, Any]] = []
        kg_items: list[dict[str, Any]] = []
        comp_items: list[dict[str, Any]] = []

        async def _run_doc_task() -> tuple[list[dict[str, Any]], dict[str, Any], float]:
            start_times["document"] = time.perf_counter()
            deadline = time.time() + (self.config.document_timeout_ms / 1000.0)
            t0 = time.perf_counter()
            try:
                items, pipeline_receipt = await asyncio.wait_for(
                    asyncio.to_thread(self._document_pipeline, query, chunks, index, snapshot_dir, document_top_k),
                    timeout=self.config.document_timeout_ms / 1000.0,
                )
                elapsed = round((time.perf_counter() - t0) * 1000, 3)
                receipt = {"status": "completed", "count": len(items), "deadline": deadline,
                           "latency_ms": elapsed, "pipeline": pipeline_receipt}
                return items, receipt, elapsed
            except asyncio.TimeoutError:
                elapsed = round((time.perf_counter() - t0) * 1000, 3)
                receipt = {"status": "timeout", "error": f"Document search exceeded {self.config.document_timeout_ms}ms", "deadline": deadline, "latency_ms": elapsed}
                return [], receipt, elapsed
            except Exception as exc:
                elapsed = round((time.perf_counter() - t0) * 1000, 3)
                receipt = {"status": "error", "error": str(exc), "deadline": deadline, "latency_ms": elapsed}
                return [], receipt, elapsed

        async def _run_kg_task() -> tuple[list[dict[str, Any]], dict[str, Any], float, float]:
            start_times["kg"] = time.perf_counter()
            deadline = time.time() + (self.config.kg_timeout_ms / 1000.0)
            t0 = time.perf_counter()
            try:
                def _do_kg():
                    if graph_result:
                        items = _kg_candidates(graph_result)
                        trace = graph_result.get("kg_trace", {})
                    else:
                        from .kg import traverse_kg
                        res = traverse_kg(snapshot_dir, query, config=self.config)
                        items = _kg_candidates(res)
                        trace = res.get("kg_trace", {})
                    t_norm = time.perf_counter()
                    ent_cands = entity_catalog_candidates(snapshot_dir, query, items)
                    items.extend(ent_cands)
                    norm_ms = round((time.perf_counter() - t_norm) * 1000, 3)
                    return items, trace, norm_ms

                items, trace, norm_ms = await asyncio.wait_for(
                    asyncio.to_thread(_do_kg),
                    timeout=self.config.kg_timeout_ms / 1000.0,
                )
                elapsed = round((time.perf_counter() - t0) * 1000, 3)
                receipt = {"status": "completed", "count": len(items), "kg_trace": trace, "deadline": deadline, "latency_ms": elapsed}
                return items, receipt, elapsed, norm_ms
            except asyncio.TimeoutError:
                elapsed = round((time.perf_counter() - t0) * 1000, 3)
                receipt = {"status": "timeout", "error": f"KG search exceeded {self.config.kg_timeout_ms}ms", "deadline": deadline, "latency_ms": elapsed}
                return [], receipt, elapsed, 0.0
            except Exception as exc:
                elapsed = round((time.perf_counter() - t0) * 1000, 3)
                receipt = {"status": "error", "error": str(exc), "deadline": deadline, "latency_ms": elapsed}
                return [], receipt, elapsed, 0.0

        async def _run_comp_task() -> tuple[list[dict[str, Any]], dict[str, Any], float]:
            start_times["computation"] = time.perf_counter()
            deadline = time.time() + (self.config.computation_timeout_ms / 1000.0)
            t0 = time.perf_counter()
            try:
                items, rec = await asyncio.wait_for(
                    asyncio.to_thread(
                        computation_candidates,
                        snapshot_dir,
                        query,
                        target_metric=plan.target_metric,
                        entity_refs=plan.entity_refs,
                    ),
                    timeout=self.config.computation_timeout_ms / 1000.0,
                )
                elapsed = round((time.perf_counter() - t0) * 1000, 3)
                rec["deadline"] = deadline
                rec["latency_ms"] = elapsed
                return items, rec, elapsed
            except asyncio.TimeoutError:
                elapsed = round((time.perf_counter() - t0) * 1000, 3)
                rec = {"status": "timeout", "error": f"Computation exceeded {self.config.computation_timeout_ms}ms", "deadline": deadline, "latency_ms": elapsed, "enumerated_members": 0}
                return [], rec, elapsed
            except Exception as exc:
                elapsed = round((time.perf_counter() - t0) * 1000, 3)
                rec = {"status": "error", "error": str(exc), "deadline": deadline, "latency_ms": elapsed, "enumerated_members": 0}
                return [], rec, elapsed

        # Execute parallel tasks using asyncio.TaskGroup (Python 3.11+)
        doc_task = None
        kg_task = None
        comp_task = None

        async with asyncio.TaskGroup() as tg:
            if plan.enable_document:
                doc_task = tg.create_task(_run_doc_task())
            else:
                receipts["document"] = {"status": "skipped_by_plan"}

            if plan.enable_kg:
                kg_task = tg.create_task(_run_kg_task())
            else:
                receipts["kg"] = {"status": "skipped_by_plan"}

            if plan.enable_computation:
                comp_task = tg.create_task(_run_comp_task())
            else:
                receipts["computation"] = {"status": "skipped_by_plan", "enumerated_members": 0}

        # All tasks guaranteed completed or terminal at this point
        if doc_task:
            docs, doc_rec, doc_ms = doc_task.result()
            latency_ms["document"] = doc_ms
            receipts["document"] = doc_rec
            modality_candidates["document"] = docs

        if kg_task:
            kg_items, kg_rec, kg_ms, norm_ms = kg_task.result()
            latency_ms["kg_search"] = kg_ms
            latency_ms["eligibility_normalization"] = norm_ms
            receipts["kg"] = kg_rec
            modality_candidates["kg"] = kg_items

        if comp_task:
            comp_items, comp_rec, comp_ms = comp_task.result()
            latency_ms["computation"] = comp_ms
            receipts["computation"] = comp_rec
            modality_candidates["computation"] = comp_items

        # Hybrid merge deduplicates strictly by canonical source locator
        t_merge = time.perf_counter()
        candidates = hybrid_union(docs, kg_items, comp_items)
        latency_ms["hybrid_merge"] = round((time.perf_counter() - t_merge) * 1000, 3)

        # Public deterministic selection with modality quotas & proof completeness
        t_sel = time.perf_counter()
        selected, excluded = select_public(
            query,
            candidates,
            token_budget=token_budget,
            max_items=max_items,
            modality_quotas=self.config.modality_quotas,
        )
        latency_ms["selection"] = round((time.perf_counter() - t_sel) * 1000, 3)

        wall_time_ms = round((time.perf_counter() - wall_tick) * 1000, 3)
        latency_ms["wall_time_ms"] = wall_time_ms
        latency_ms["total_pre_reader"] = wall_time_ms

        return PlannedRetrievalResult(
            plan=plan,
            candidates=candidates,
            selected_evidence=selected,
            selector_excluded=excluded,
            modality_candidates=modality_candidates,
            latency_ms=latency_ms,
            receipts=receipts,
            start_times=start_times,
            wall_time_ms=wall_time_ms,
        )

    def execute(
        self,
        plan: RetrievalPlan,
        query: dict[str, Any],
        chunks: list[Chunk],
        index: BM25Index,
        snapshot_dir: Path,
        graph_result: dict[str, Any] | None = None,
        document_top_k: int = 10,
        token_budget: int = 1800,
        max_items: int = 22,
    ) -> PlannedRetrievalResult:
        """Executes retrieval modalities synchronously or in threadpool if loop already running."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(
                    asyncio.run,
                    self.execute_async(
                        plan=plan,
                        query=query,
                        chunks=chunks,
                        index=index,
                        snapshot_dir=snapshot_dir,
                        graph_result=graph_result,
                        document_top_k=document_top_k,
                        token_budget=token_budget,
                        max_items=max_items,
                    ),
                ).result()
        return asyncio.run(
            self.execute_async(
                plan=plan,
                query=query,
                chunks=chunks,
                index=index,
                snapshot_dir=snapshot_dir,
                graph_result=graph_result,
                document_top_k=document_top_k,
                token_budget=token_budget,
                max_items=max_items,
            )
        )
