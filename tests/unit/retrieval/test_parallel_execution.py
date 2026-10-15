"""Tests for P6: Parallel execution, deadline/timeout isolation, receipts, and hybrid evidence selection.

Verifies:
1. asyncio.TaskGroup executes document, KG, and computation modalities concurrently.
2. Concurrent startup is confirmed via branch start timestamps (start_times).
3. Modality tasks have individual deadlines, timeouts, and auditable receipts.
4. Terminal status requirement: merge only occurs after all tasks complete or reach terminal status.
5. Deduplication by public canonical locator, preserving distinct chunk vs KG edge identities without summing scores.
6. Deterministic public selection preserving modality quotas, bridge, definition, coverage, and predicate diversity.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from gsm_memory.retrieval.bm25 import BM25Index
from gsm_memory.retrieval.config import RetrievalConfig
from gsm_memory.retrieval.documents import construct_chunks
from gsm_memory.retrieval.offline import hybrid_union, select_public
from gsm_memory.retrieval.planner import PlannedRetrievalResult, RetrievalPlan, RetrievalPlanner
from gsm_memory.retrieval.query_analysis import parse_query_rule_based


RELEASE_DIR = Path("data/gsm-dev-core-0.2.2")


@pytest.fixture(scope="module")
def shared_index_and_chunks():
    chunks, _, _ = construct_chunks(RELEASE_DIR, "debug_core")
    index = BM25Index(chunks)
    return chunks, index


@pytest.mark.anyio
async def test_modalities_start_concurrently_when_all_enabled(shared_index_and_chunks):
    """When document, KG, and computation are all enabled, they start concurrently."""
    chunks, index = shared_index_and_chunks
    snap_dir = RELEASE_DIR / "public" / "snapshots" / "d4cc0438-d831-541a-8123-ddda94ccdac8"

    # Query with HYBRID_REASONING intent: enables document, KG, and computation
    query = {
        "query_id": "hybrid-concurrent-test",
        "query": "Tài xế An DRV-001 có vi phạm quy định hủy chuyến theo snapshot snap-154-d4af28195271?",
        "entity_refs": ["99e70ebe-18cd-57a3-a036-cf0ff1989861"],
        "public_snapshot_id": "d4cc0438-d831-541a-8123-ddda94ccdac8",
        "application_context": {"source_snapshot_refs": ["P154"]},
    }
    query_plan = parse_query_rule_based(query, release_dir=RELEASE_DIR)
    planner = RetrievalPlanner()
    ret_plan = planner.plan(query_plan, query=query)

    # Force all three modalities to enabled to test simultaneous startup
    ret_plan.enable_document = True
    ret_plan.enable_kg = True
    ret_plan.enable_computation = True

    result = await planner.execute_async(
        plan=ret_plan,
        query=query,
        chunks=chunks,
        index=index,
        snapshot_dir=snap_dir,
    )

    # 1. Verify start_times recorded for all three modalities
    assert "document" in result.start_times
    assert "kg" in result.start_times
    assert "computation" in result.start_times

    doc_start = result.start_times["document"]
    kg_start = result.start_times["kg"]
    comp_start = result.start_times["computation"]

    # 2. Verify all three started concurrently (within 50ms of each other)
    max_delta = max(doc_start, kg_start, comp_start) - min(doc_start, kg_start, comp_start)
    assert max_delta < 0.05, f"Expected concurrent startup, got delta {max_delta * 1000:.2f}ms"

    # 3. Verify actual wall time and branch latencies are recorded
    assert result.wall_time_ms > 0.0
    assert result.latency_ms["document"] > 0.0
    assert result.latency_ms["kg_search"] > 0.0
    assert result.latency_ms["wall_time_ms"] == result.wall_time_ms

    # 4. Verify individual receipts exist
    assert result.receipts["document"]["status"] == "completed"
    assert result.receipts["kg"]["status"] == "completed"
    assert "deadline" in result.receipts["document"]
    assert "deadline" in result.receipts["kg"]


@pytest.mark.anyio
async def test_individual_modality_timeout_isolation(shared_index_and_chunks):
    """If one modality times out, other modalities complete and merge succeeds."""
    chunks, index = shared_index_and_chunks
    snap_dir = RELEASE_DIR / "public" / "snapshots" / "d4cc0438-d831-541a-8123-ddda94ccdac8"

    query = {
        "query_id": "timeout-isolation-test",
        "query": "Tài xế An DRV-001 kiểm tra quy định",
        "entity_refs": ["99e70ebe-18cd-57a3-a036-cf0ff1989861"],
        "public_snapshot_id": "d4cc0438-d831-541a-8123-ddda94ccdac8",
        "application_context": {"source_snapshot_refs": ["P154"]},
    }
    planner = RetrievalPlanner(RetrievalConfig(kg_timeout_ms=1.0))  # 1ms timeout will trigger TimeoutError
    ret_plan = RetrievalPlan(
        intent="HYBRID_REASONING",
        modalities=["document", "kg"],
        enable_document=True,
        enable_kg=True,
        enable_computation=False,
    )

    def slow_traverse(*args, **kwargs):
        time.sleep(0.05)  # 50ms > 1ms timeout
        return {"raw_candidates": []}

    with patch("gsm_memory.retrieval.kg.traverse_kg", side_effect=slow_traverse):
        result = await planner.execute_async(
            plan=ret_plan,
            query=query,
            chunks=chunks,
            index=index,
            snapshot_dir=snap_dir,
        )

    # Document completed successfully
    assert result.receipts["document"]["status"] == "completed"
    assert len(result.modality_candidates["document"]) > 0

    # KG hit timeout terminal status
    assert result.receipts["kg"]["status"] == "timeout"
    assert "exceeded" in result.receipts["kg"]["error"]

    # Hybrid merge succeeded with available items
    assert len(result.candidates) > 0


def test_hybrid_merge_deduplicates_by_canonical_locator_without_score_blending():
    """Hybrid union deduplicates by canonical source_locator; does NOT sum chunk + KG scores."""
    doc_cand = {
        "evidence_id": "doc-1",
        "source_kind": "document",
        "source_id": "P154",
        "score": 0.85,
        "rank": 1,
        "token_cost": 25,
        "source_locator": {"locator_type": "document_clause", "document_revision_id": "P154", "clause_refs": [{"clause_id": "Điều 5"}]},
    }
    # Duplicate document chunk with same locator but lower score
    doc_cand_dup = {
        "evidence_id": "doc-1-dup",
        "source_kind": "document",
        "source_id": "P154",
        "score": 0.70,
        "rank": 2,
        "token_cost": 25,
        "source_locator": {"locator_type": "document_clause", "document_revision_id": "P154", "clause_refs": [{"clause_id": "Điều 5"}]},
    }
    # KG edge referencing the same driver topic but with ledger_assertion locator
    kg_cand = {
        "evidence_id": "kg-1",
        "source_kind": "kg",
        "source_id": "rec-1",
        "score": 10.0,
        "rank": 1,
        "token_cost": 20,
        "source_locator": {"locator_type": "ledger_assertion", "assertion_id": "assert-1", "record_id": "rec-1", "source_id": "S1"},
    }

    merged = hybrid_union([doc_cand], [doc_cand_dup, kg_cand])

    # doc-1-dup was deduplicated against doc-1 (identical locator); kg-1 remains distinct
    assert len(merged) == 2
    merged_by_id = {item["evidence_id"]: item for item in merged}
    assert "doc-1" in merged_by_id
    assert "kg-1" in merged_by_id
    assert "doc-1-dup" not in merged_by_id

    # Verify score was NOT blended between chunk and KG edge
    assert merged_by_id["doc-1"]["score"] == 0.85
    assert merged_by_id["kg-1"]["score"] == 10.0


def test_public_selection_preserves_coverage_bridge_and_predicate_diversity():
    """Selection enforces modality quotas, co-selects coverage for computation, and balances KG predicates."""
    query = {
        "query_id": "q-sel-test",
        "query": "Tài xế An DRV-001 kiểm tra tỷ lệ hủy",
        "entity_refs": ["driver-an-uuid"],
        "application_context": {"definition_refs": ["def-cancel-rate"]},
    }
    candidates = [
        # Entity Catalog (bridge)
        {"evidence_id": "ent-an", "source_kind": "entity_catalog", "source_id": "driver-an-uuid", "score": 1.0, "rank": 1, "token_cost": 30, "source_locator": {"locator_type": "entity_catalog", "entity_id": "driver-an-uuid"}},
        # Definition (pinned)
        {"evidence_id": "def-1", "source_kind": "definition", "source_id": "def-cancel-rate", "score": 1.0, "rank": 1, "token_cost": 35, "source_locator": {"locator_type": "definition_artifact", "definition_id": "def-cancel-rate"}},
        # Computation
        {"evidence_id": "comp-1", "source_kind": "computation", "source_id": "cov-art-1", "score": 1.0, "rank": 1, "token_cost": 50, "source_locator": {"locator_type": "computation", "coverage_artifact_id": "cov-art-1"}},
        # Coverage artifact supporting computation
        {"evidence_id": "cov-1", "source_kind": "coverage", "source_id": "cov-art-1", "score": 1.0, "rank": 1, "token_cost": 40, "source_locator": {"locator_type": "coverage_artifact", "artifact_id": "cov-art-1"}},
        # Multiple KG assertions with different predicates: DRIVER_PROGRAM and TRIP_OUTCOME
        {"evidence_id": "kg-prog", "source_kind": "kg", "predicate": "DRIVER_PROGRAM", "source_id": "rec-p", "score": 5.0, "rank": 5, "token_cost": 20, "source_locator": {"locator_type": "ledger_assertion", "assertion_id": "a-prog"}},
        {"evidence_id": "kg-trip-1", "source_kind": "kg", "predicate": "TRIP_OUTCOME", "source_id": "rec-t1", "score": 9.0, "rank": 1, "token_cost": 20, "source_locator": {"locator_type": "ledger_assertion", "assertion_id": "a-t1"}},
        {"evidence_id": "kg-trip-2", "source_kind": "kg", "predicate": "TRIP_OUTCOME", "source_id": "rec-t2", "score": 8.0, "rank": 2, "token_cost": 20, "source_locator": {"locator_type": "ledger_assertion", "assertion_id": "a-t2"}},
    ]

    selected, excluded = select_public(query, candidates, token_budget=500, max_items=6)
    selected_ids = {item["evidence_id"] for item in selected}

    # 1. Computation and Coverage both selected (co-selection of coverage for complete proof)
    assert "comp-1" in selected_ids
    assert "cov-1" in selected_ids

    # 2. Bridge entity catalog and pinned definition both selected
    assert "ent-an" in selected_ids
    assert "def-1" in selected_ids

    # 3. Predicate diversity: DRIVER_PROGRAM is selected despite having lower score than kg-trip-1 & 2
    assert "kg-prog" in selected_ids
    assert "kg-trip-1" in selected_ids
