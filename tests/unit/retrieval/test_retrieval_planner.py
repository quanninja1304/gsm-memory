"""Unit tests for P2: RetrievalPlanner, Query Analysis enum validation,

canonical entity resolution, and targeted modality selective execution.

Test matrix covers:
1. policy-only (POLICY_LOOKUP -> document only, no KG, no comp)
2. KG-only (DRIVER_HISTORY -> KG only, no doc, no comp)
3. aggregate (METRIC_CHECK -> computation + definition/KG when needed)
4. hybrid (HYBRID_REASONING -> document + KG + computation)
5. unknown entity (unknown driver code or name -> unresolved_entity)
6. ambiguous query (duplicate names like Minh -> unresolved_entity, is_ambiguous=True)
7. enum validation (strict validation on approved predicates, metrics, intents)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from gsm_memory.retrieval.bm25 import BM25Index
from gsm_memory.retrieval.config import RetrievalConfig
from gsm_memory.retrieval.documents import construct_chunks
from gsm_memory.retrieval.planner import PlannedRetrievalResult, RetrievalPlan, RetrievalPlanner
from gsm_memory.retrieval.query_analysis import (
    ComputationFilters,
    DocumentFilters,
    GraphFilters,
    QueryPlan,
    VALID_INTENTS,
    VALID_METRICS,
    VALID_PREDICATES,
    analyze_query,
    parse_query_llm,
    parse_query_rule_based,
    resolve_entity,
)


RELEASE_DIR = Path("data/gsm-dev-core-0.2.2")


# ==============================================================================
# 1. ENUM VALIDATION: PREDICATES, METRICS, INTENTS
# ==============================================================================

def test_graph_filters_rejects_unapproved_predicates():
    """GraphFilters must only accept approved Schema v1.1 predicates."""
    # Valid predicates pass
    gf = GraphFilters(target_predicates=["TRIP_OUTCOME", "HAS_INCIDENT", "DRIVER_PROGRAM"])
    assert gf.target_predicates == ["TRIP_OUTCOME", "HAS_INCIDENT", "DRIVER_PROGRAM"]

    # Unapproved predicate raises ValidationError
    with pytest.raises(ValidationError) as exc:
        GraphFilters(target_predicates=["OFFER_ACCEPTED"])
    assert "Invalid predicate 'OFFER_ACCEPTED'" in str(exc.value)

    with pytest.raises(ValidationError) as exc:
        GraphFilters(target_predicates=["GPS_TELEMETRY"])
    assert "Invalid predicate 'GPS_TELEMETRY'" in str(exc.value)


def test_computation_filters_rejects_unapproved_metrics():
    """ComputationFilters must only accept approved metrics."""
    # Valid metrics pass
    cf = ComputationFilters(target_metric="cancel_rate_30d")
    assert cf.target_metric == "cancel_rate_30d"

    cf_rev = ComputationFilters(target_metric="RM_REVENUE")
    assert cf_rev.target_metric == "RM_REVENUE"

    # Unapproved metric raises ValidationError
    with pytest.raises(ValidationError) as exc:
        ComputationFilters(target_metric="driver_lifetime_value")
    assert "Invalid metric 'driver_lifetime_value'" in str(exc.value)


def test_query_plan_rejects_unapproved_intents():
    """QueryPlan must strictly validate the 4 approved intents."""
    with pytest.raises(ValidationError):
        QueryPlan.model_validate({"intent": "CHIT_CHAT"})


# ==============================================================================
# 2. CANONICAL ENTITY RESOLUTION & AMBIGUITY / UNKNOWN ENTITY DETECTION
# ==============================================================================

def test_resolve_entity_known_driver_code_and_name():
    """Known synthetic driver code (DRV-001) and name (An) resolve to canonical UUID."""
    expected_id = "99e70ebe-18cd-57a3-a036-cf0ff1989861"

    # Mention by driver code
    assert resolve_entity("DRV-001", release_dir=RELEASE_DIR) == expected_id

    # Mention by single driver name
    assert resolve_entity("An", release_dir=RELEASE_DIR) == expected_id

    # Direct UUID returns itself
    assert resolve_entity(expected_id, release_dir=RELEASE_DIR) == expected_id


def test_resolve_entity_ambiguous_name_returns_unresolved():
    """Duplicate driver name 'Minh' (Drivers E and F) must return unresolved_entity."""
    res = resolve_entity("Minh", release_dir=RELEASE_DIR)
    assert res == "unresolved_entity"


def test_resolve_entity_unknown_code_or_name_returns_unresolved():
    """Unknown code (DRV-999) or non-existent name returns unresolved_entity."""
    assert resolve_entity("DRV-999", release_dir=RELEASE_DIR) == "unresolved_entity"
    assert resolve_entity("Người Lạ Vô Danh", release_dir=RELEASE_DIR) == "unresolved_entity"


def test_query_analysis_handles_unknown_entity_and_ambiguity():
    """Ambiguous or unknown entity sets unresolved_entities on QueryPlan."""
    # Unknown driver
    q_unknown = {"query_id": "q-unk", "query": "Tài xế DRV-999 có bao nhiêu chuyến xe bị hủy?"}
    plan_unk = parse_query_rule_based(q_unknown, release_dir=RELEASE_DIR)
    assert plan_unk.has_unresolved_entity is True
    assert "DRV-999" in plan_unk.unresolved_entities
    assert plan_unk.unresolved_entity == "unresolved_entity"

    # Ambiguous driver (Minh - C032)
    q_ambig = {"query_id": "q-ambig", "query": "Minh thuộc Depot nào tại Tm?"}
    plan_ambig = parse_query_rule_based(q_ambig, release_dir=RELEASE_DIR)
    assert plan_ambig.has_unresolved_entity is True
    assert "Minh" in plan_ambig.unresolved_entities
    assert plan_ambig.unresolved_entity == "unresolved_entity"


# ==============================================================================
# 3. RETRIEVAL PLANNER: POLICY-ONLY (POLICY_LOOKUP)
# ==============================================================================

def test_planner_policy_only():
    """POLICY_LOOKUP activates only document modality; KG and computation are disabled."""
    q_policy = {
        "query_id": "q-pol",
        "query": "Theo snapshot snap-154-d4af28195271, quy định doanh số tối thiểu là bao nhiêu?",
        "application_context": {"source_snapshot_refs": ["P154"]},
    }
    query_plan = parse_query_rule_based(q_policy, release_dir=RELEASE_DIR)
    assert query_plan.intent == "POLICY_LOOKUP"

    planner = RetrievalPlanner()
    ret_plan = planner.plan(query_plan, query=q_policy)

    assert ret_plan.enable_document is True
    assert ret_plan.enable_kg is False
    assert ret_plan.enable_computation is False
    assert ret_plan.modalities == ["document"]


# ==============================================================================
# 4. RETRIEVAL PLANNER: KG-ONLY (DRIVER_HISTORY)
# ==============================================================================

def test_planner_kg_only():
    """DRIVER_HISTORY activates only KG modality; document and computation are disabled."""
    q_kg = {
        "query_id": "q-kg",
        "query": "Tài xế An có trạng thái hoạt động thế nào?",
        "entity_refs": ["99e70ebe-18cd-57a3-a036-cf0ff1989861"],
    }
    query_plan = parse_query_rule_based(q_kg, release_dir=RELEASE_DIR)
    assert query_plan.intent == "DRIVER_HISTORY"

    planner = RetrievalPlanner()
    ret_plan = planner.plan(query_plan, query=q_kg)

    assert ret_plan.enable_document is False
    assert ret_plan.enable_kg is True
    assert ret_plan.enable_computation is False
    assert ret_plan.modalities == ["kg"]


# ==============================================================================
# 5. RETRIEVAL PLANNER: AGGREGATE / METRIC_CHECK
# ==============================================================================

def test_planner_aggregate_metric_check():
    """METRIC_CHECK activates computation; adds document for definitions if requested."""
    q_metric = {
        "query_id": "q-met",
        "query": "Tỷ lệ hủy chuyến cancel_rate_30d của tài xế An là bao nhiêu?",
        "entity_refs": ["99e70ebe-18cd-57a3-a036-cf0ff1989861"],
    }
    query_plan = parse_query_rule_based(q_metric, release_dir=RELEASE_DIR)
    assert query_plan.intent == "METRIC_CHECK"

    planner = RetrievalPlanner()
    ret_plan = planner.plan(query_plan, query=q_metric)

    assert ret_plan.enable_computation is True
    # Without definition keywords or refs, document is not needed
    assert "computation" in ret_plan.modalities


def test_planner_aggregate_with_definition():
    """METRIC_CHECK asking for definition enables document modality."""
    q_def = {
        "query_id": "q-met-def",
        "query": "Định nghĩa và tỷ lệ hủy chuyến cancel_rate_30d của tài xế An?",
        "entity_refs": ["99e70ebe-18cd-57a3-a036-cf0ff1989861"],
    }
    query_plan = parse_query_rule_based(q_def, release_dir=RELEASE_DIR)

    planner = RetrievalPlanner()
    ret_plan = planner.plan(query_plan, query=q_def)

    assert ret_plan.enable_computation is True
    assert ret_plan.enable_document is True
    assert "computation" in ret_plan.modalities
    assert "document" in ret_plan.modalities


# ==============================================================================
# 6. RETRIEVAL PLANNER: HYBRID REASONING
# ==============================================================================

def test_planner_hybrid_reasoning():
    """HYBRID_REASONING enables all three modalities: document, KG, and computation."""
    q_hybrid = {
        "query_id": "q-hyb",
        "query": "Tài xế An có cuốc xe bị hủy do hỏng xe, theo P154 có bị vượt trần tỷ lệ hủy không?",
        "entity_refs": ["99e70ebe-18cd-57a3-a036-cf0ff1989861"],
        "application_context": {"source_snapshot_refs": ["P154"]},
    }
    query_plan = parse_query_rule_based(q_hybrid, release_dir=RELEASE_DIR)
    assert query_plan.intent == "HYBRID_REASONING"

    planner = RetrievalPlanner()
    ret_plan = planner.plan(query_plan, query=q_hybrid)

    assert ret_plan.enable_document is True
    assert ret_plan.enable_kg is True
    assert ret_plan.enable_computation is True
    assert set(ret_plan.modalities) == {"document", "kg", "computation"}


# ==============================================================================
# 7. RETRIEVAL PLANNER: UNKNOWN ENTITY & AMBIGUOUS QUERY SHORT-CIRCUIT
# ==============================================================================

def test_planner_handles_ambiguous_and_unknown_entities():
    """Planner flags ambiguity and disables computation when entity cannot be resolved."""
    # 1. Ambiguous query (Minh)
    q_ambig = {"query_id": "q-ambig", "query": "Minh thuộc Depot nào tại Tm?"}
    plan_ambig = parse_query_rule_based(q_ambig, release_dir=RELEASE_DIR)
    planner = RetrievalPlanner()
    ret_plan_ambig = planner.plan(plan_ambig, query=q_ambig)

    assert ret_plan_ambig.is_ambiguous is True
    assert ret_plan_ambig.unresolved_entity == "unresolved_entity"
    # Cannot search driver KG without resolved anchor
    assert ret_plan_ambig.enable_kg is False

    # 2. Unknown driver computation (DRV-999)
    q_unk = {"query_id": "q-unk", "query": "Tỷ lệ hủy cancel_rate_30d của DRV-999 là bao nhiêu?"}
    plan_unk = parse_query_rule_based(q_unk, release_dir=RELEASE_DIR)
    ret_plan_unk = planner.plan(plan_unk, query=q_unk)

    assert ret_plan_unk.is_ambiguous is True
    # Unknown subject entity -> computation disabled
    assert ret_plan_unk.enable_computation is False


# ==============================================================================
# 8. RETRIEVAL PLANNER EXECUTION: ONLY QUERIES REQUIRED MODALITIES
# ==============================================================================

def test_planner_execute_skips_disabled_modalities():
    """Execution on a policy-only plan must never query KG or run computation."""
    q_policy = {
        "query_id": "q-pol-exec",
        "query": "Theo snapshot snap-154-d4af28195271, quy định doanh số tối thiểu?",
        "public_snapshot_id": "d4cc0438-d831-541a-8123-ddda94ccdac8",
        "application_context": {"source_snapshot_refs": ["P154"]},
    }
    chunks, _, _ = construct_chunks(RELEASE_DIR, "debug_core")
    index = BM25Index(chunks)
    snapshot_dir = RELEASE_DIR / "public" / "snapshots" / q_policy["public_snapshot_id"]

    query_plan = parse_query_rule_based(q_policy, release_dir=RELEASE_DIR)
    planner = RetrievalPlanner()
    plan = planner.plan(query_plan, query=q_policy)

    result = planner.execute(
        plan=plan,
        query=q_policy,
        chunks=chunks,
        index=index,
        snapshot_dir=snapshot_dir,
    )

    # Document was executed
    assert len(result.modality_candidates["document"]) > 0
    assert result.latency_ms["document"] > 0

    # KG was NOT executed
    assert len(result.modality_candidates["kg"]) == 0
    assert result.latency_ms["kg_search"] == 0.0

    # Computation was NOT executed
    assert len(result.modality_candidates["computation"]) == 0
    assert result.latency_ms["computation"] == 0.0
    assert result.receipts["computation"]["status"] == "skipped_by_plan"
