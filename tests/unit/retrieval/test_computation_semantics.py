"""Unit tests for P5: Computation with exact rational arithmetic and correct semantics.

Verifies:
1. Planner uses computation_filters.target_metric, NOT checking literal text 'cancel_rate_30d'.
2. Computation execution:
   - Reads selected public snapshot.
   - Verifies coverage/source-set.
   - Takes full eligible population.
   - Handles retract/replace and temporal window eligibility.
   - Uses Fraction/exact rational arithmetic (n/d).
3. Evidence returned:
   - result (computation candidate with typed_value and members/provenance).
   - coverage artifact candidate.
4. Error / edge-case statuses:
   - Missing coverage -> status: 'missing_coverage', candidates: [].
   - Unresolved entity -> status: 'unresolved_entity', candidates: [].
   - Denominator zero -> metric_status: 'undefined', zero_denominator: True, typed_value: None.
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

import pytest

from gsm_memory.retrieval.bm25 import BM25Index
from gsm_memory.retrieval.documents import construct_chunks
from gsm_memory.retrieval.offline import computation_candidates
from gsm_memory.retrieval.planner import PlannedRetrievalResult, RetrievalPlanner
from gsm_memory.retrieval.query_analysis import parse_query_rule_based


RELEASE_DIR = Path("data/gsm-dev-core-0.2.2")
DEFAULT_SNAPSHOT_ID = "d4cc0438-d831-541a-8123-ddda94ccdac8"
SNAPSHOT_DIR = RELEASE_DIR / "public" / "snapshots" / DEFAULT_SNAPSHOT_ID


# ==============================================================================
# 1. PLANNER USES computation_filters.target_metric WITHOUT LITERAL CHECK
# ==============================================================================

def test_planner_uses_target_metric_without_literal_cancel_rate_30d_string():
    """Vietnamese query 'Tỷ lệ hủy của tài xế' sets target_metric='cancel_rate_30d' and enables computation."""
    binh_id = "c499f934-bfe1-5509-a578-afb09cee357c"
    q_vn = {
        "query_id": "q-vn-cancel",
        "query": "Tỷ lệ hủy của tài xế Bình tại Tm theo quy định được cấp là bao nhiêu?",
        "public_snapshot_id": DEFAULT_SNAPSHOT_ID,
        "entity_refs": [binh_id],
    }
    # Notice: query text does NOT contain the literal English substring 'cancel_rate_30d'
    assert "cancel_rate_30d" not in q_vn["query"]

    plan = parse_query_rule_based(q_vn, release_dir=RELEASE_DIR)
    assert plan.computation_filters.target_metric == "cancel_rate_30d"

    planner = RetrievalPlanner()
    ret_plan = planner.plan(plan, query=q_vn)

    assert ret_plan.enable_computation is True
    assert ret_plan.target_metric == "cancel_rate_30d"

    # Execute with planner
    chunks, _, _ = construct_chunks(RELEASE_DIR, "debug_core")
    index = BM25Index(chunks)

    result = planner.execute(
        plan=ret_plan,
        query=q_vn,
        chunks=chunks,
        index=index,
        snapshot_dir=SNAPSHOT_DIR,
    )

    # Computation was successfully executed via target_metric
    assert result.receipts["computation"]["status"] == "complete"
    assert len(result.modality_candidates["computation"]) > 0


def test_computation_candidates_direct_call_with_target_metric_param():
    """computation_candidates works when target_metric is passed explicitly."""
    binh_id = "c499f934-bfe1-5509-a578-afb09cee357c"
    query = {
        "public_snapshot_id": DEFAULT_SNAPSHOT_ID,
        "query": "Cho tôi biết con số phần trăm cuốc không hoàn thành của tài xế Bình",
        "entity_refs": [binh_id],
    }
    assert "cancel_rate_30d" not in query["query"]

    # When target_metric is None and no keywords in text -> not_applicable
    cand_none, rec_none = computation_candidates(
        snapshot_dir=SNAPSHOT_DIR,
        query=query,
        target_metric=None,
    )
    assert cand_none == []
    assert rec_none["status"] == "not_applicable"

    # When target_metric is passed as 'cancel_rate_30d' -> executes successfully
    cand_ok, rec_ok = computation_candidates(
        snapshot_dir=SNAPSHOT_DIR,
        query=query,
        target_metric="cancel_rate_30d",
    )
    assert rec_ok["status"] == "complete"
    assert len(cand_ok) == 2


# ==============================================================================
# 2. EXACT RATIONAL ARITHMETIC AND RETRACT/REPLACE HANDLING
# ==============================================================================

def test_computation_exact_rational_fraction_arithmetic():
    """Cancel rate computation uses Fraction rational arithmetic with numerator/denominator dict."""
    binh_id = "c499f934-bfe1-5509-a578-afb09cee357c"
    query = {
        "public_snapshot_id": DEFAULT_SNAPSHOT_ID,
        "query": "Tính chính xác cancel_rate_30d của tài xế tại Tm theo definition được cấp",
        "entity_refs": [binh_id],  # Bình
    }

    candidates, receipt = computation_candidates(
        snapshot_dir=SNAPSHOT_DIR,
        query=query,
        target_metric="cancel_rate_30d",
    )

    assert receipt["status"] == "complete"
    assert receipt["enumerated_members"] == 10
    assert receipt["cancelled"] == 2

    comp_cand = next(c for c in candidates if c["source_kind"] == "computation")
    typed_val = comp_cand["typed_value"]
    # 2 cancelled out of 10 terminal trips = 1/5
    assert typed_val == {"n": 1, "d": 5}
    assert Fraction(typed_val["n"], typed_val["d"]) == Fraction(2, 10)


def test_computation_returns_both_result_and_coverage_artifact():
    """Result evidence includes computation candidate with members provenance and coverage artifact candidate."""
    binh_id = "c499f934-bfe1-5509-a578-afb09cee357c"
    query = {
        "public_snapshot_id": DEFAULT_SNAPSHOT_ID,
        "query": "cancel_rate_30d",
        "entity_refs": [binh_id],  # Bình
    }

    candidates, receipt = computation_candidates(
        snapshot_dir=SNAPSHOT_DIR,
        query=query,
        target_metric="cancel_rate_30d",
    )

    kinds = {c["source_kind"] for c in candidates}
    assert "computation" in kinds
    assert "coverage" in kinds

    cov_cand = next(c for c in candidates if c["source_kind"] == "coverage")
    assert cov_cand["source_locator"]["locator_type"] == "coverage_artifact"
    assert cov_cand["coverage_status"] == "complete"

    comp_cand = next(c for c in candidates if c["source_kind"] == "computation")
    assert comp_cand["source_locator"]["locator_type"] == "computation"
    assert len(comp_cand["members"]) > 0
    # Every member has trip_id, record_id, assertion_id, and outcome
    for m in comp_cand["members"]:
        assert "trip_id" in m
        assert "outcome" in m
        assert "record_id" in m
        assert "assertion_id" in m


# ==============================================================================
# 3. EDGE CASES: UNRESOLVED ENTITY, MISSING COVERAGE, DENOMINATOR ZERO
# ==============================================================================

def test_computation_unresolved_entity_returns_explicit_status():
    """Unresolved or ambiguous entity returns status='unresolved_entity' without inferring."""
    query_unresolved = {
        "public_snapshot_id": DEFAULT_SNAPSHOT_ID,
        "query": "cancel_rate_30d của tài xế",
        "entity_refs": ["unresolved_entity"],
    }
    candidates, receipt = computation_candidates(
        snapshot_dir=SNAPSHOT_DIR,
        query=query_unresolved,
        target_metric="cancel_rate_30d",
    )
    assert candidates == []
    assert receipt["status"] == "unresolved_entity"

    # Empty entity_refs
    query_empty = {
        "public_snapshot_id": DEFAULT_SNAPSHOT_ID,
        "query": "cancel_rate_30d",
        "entity_refs": [],
    }
    candidates, receipt = computation_candidates(
        snapshot_dir=SNAPSHOT_DIR,
        query=query_empty,
        target_metric="cancel_rate_30d",
    )
    assert candidates == []
    assert receipt["status"] == "unresolved_entity"


def test_computation_missing_coverage_returns_explicit_status():
    """Snapshot without coverage artifact (e.g. L_NO_COVERAGE branch) returns status='missing_coverage'."""
    # Snapshot from L_NO_COVERAGE branch
    no_cov_snapshot_id = "688de316-96de-59b6-9c70-3d4745aba76f"
    no_cov_dir = RELEASE_DIR / "public" / "snapshots" / no_cov_snapshot_id

    query = {
        "public_snapshot_id": no_cov_snapshot_id,
        "query": "Tính chính xác cancel_rate_30d của tài xế tại Tm theo definition được cấp",
        "entity_refs": ["c499f934-bfe1-5509-a578-afb09cee357c"],
    }

    candidates, receipt = computation_candidates(
        snapshot_dir=no_cov_dir,
        query=query,
        target_metric="cancel_rate_30d",
    )
    assert candidates == []
    assert receipt["status"] == "missing_coverage"


def test_computation_denominator_zero_returns_undefined_metric_status():
    """Verified empty population (0 trips) returns metric_status='undefined', typed_value=None."""
    # Driver Hà (122a3140-7c98-5136-a732-8a9566cb727d) in C039 has complete coverage with 0 trips
    query = {
        "public_snapshot_id": DEFAULT_SNAPSHOT_ID,
        "query": "cancel_rate_30d của tài xế tại Tm có trạng thái và giá trị nào theo definition được cấp?",
        "entity_refs": ["122a3140-7c98-5136-a732-8a9566cb727d"],
    }

    candidates, receipt = computation_candidates(
        snapshot_dir=SNAPSHOT_DIR,
        query=query,
        target_metric="cancel_rate_30d",
    )

    # Status shows execution completed but denominator is zero
    assert receipt["status"] == "complete"
    assert receipt["zero_denominator"] is True
    assert receipt["metric_status"] == "undefined"
    assert receipt["enumerated_members"] == 0
    assert receipt["typed_value"] is None

    # Evidence candidates are still provided (proving coverage is complete and population empty)
    assert len(candidates) == 2
    comp_cand = next(c for c in candidates if c["source_kind"] == "computation")
    assert comp_cand["metric_status"] == "undefined"
    assert comp_cand["typed_value"] is None
    assert len(comp_cand["members"]) == 0
