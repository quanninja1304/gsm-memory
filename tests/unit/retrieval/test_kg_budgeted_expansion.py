"""Unit tests for P4: Knowledge Graph (KG) retrieval:

- Seed resolution from snapshot entity_catalog.jsonl:
  - Exact ID / code / alias public first.
  - Semantic retrieval second.
  - Strictly bounded by seed_top_k (e.g. 3).
  - Ambiguous entity rejection (e.g. 'Minh').
- Upfront edge filtering:
  - Scope / snapshot boundary.
  - Known-as-of boundary (no future facts leak; replaced/retracted excluded).
  - Valid-time eligibility (point vs interval vs current).
  - Predicate / type allowlist.
  - Entity constraints (reachability from frontier).
- Budgeted BFS expansion:
  - max_hops (default 2), max_nodes (default 20), max_edges (default 30).
  - per_node_fanout limit (e.g. 10).
  - Edge prioritization matching target predicates & query text.
- Full reproducible KG trace:
  - seed_candidates, excluded_seeds, visited_nodes, visited_edges, frontier_per_hop, truncation_reasons.
- Public evidence identity:
  - Points to ledger assertion locator, never Graphiti internal UUID.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from gsm_memory.retrieval.config import RetrievalConfig
from gsm_memory.retrieval.kg import (
    KGEdgeView,
    budgeted_bfs,
    filter_edge,
    load_snapshot_edges_from_parquet,
    traverse_kg,
)
from gsm_memory.retrieval.semantic_seed import (
    SeedResolutionResult,
    SemanticSeedSelector,
    resolve_seeds_from_snapshot,
)


RELEASE_DIR = Path("data/gsm-dev-core-0.2.2")
DEFAULT_SNAPSHOT_ID = "d4cc0438-d831-541a-8123-ddda94ccdac8"
SNAPSHOT_DIR = RELEASE_DIR / "public" / "snapshots" / DEFAULT_SNAPSHOT_ID


# ==============================================================================
# 1. SEED RESOLUTION: EXACT FIRST, SEMANTIC SECOND, STRICT BUDGET
# ==============================================================================

def test_seed_resolution_exact_driver_code_and_name_first():
    """Exact driver code (DRV-001) and name (An) are resolved first before semantic search."""
    res = resolve_seeds_from_snapshot(
        snapshot_dir=SNAPSHOT_DIR,
        query_text="Tài xế DRV-001 (An) có cuốc xe nào bị hủy?",
        seed_top_k=3,
    )
    assert isinstance(res, SeedResolutionResult)
    assert len(res.selected_seeds) <= 3

    # An has entity_id '99e70ebe-18cd-57a3-a036-cf0ff1989861'
    expected_an_id = "99e70ebe-18cd-57a3-a036-cf0ff1989861"
    assert expected_an_id in res.seed_ids

    # Check resolution method is exact
    an_seed = next(s for s in res.selected_seeds if s["entity_id"] == expected_an_id)
    assert an_seed["resolution_method"] in {"exact_driver_code", "exact_name"}
    assert an_seed["similarity"] == 1.0


def test_seed_resolution_rejects_ambiguous_names_from_selection():
    """Ambiguous driver name 'Minh' (matching DRV-005 and DRV-006) is rejected and logged."""
    res = resolve_seeds_from_snapshot(
        snapshot_dir=SNAPSHOT_DIR,
        query_text="Tài xế Minh có bao nhiêu ngày vận doanh?",
        seed_top_k=3,
    )
    # Neither DRV-005 nor DRV-006 should be blindly selected under ambiguous single name
    minh_ids = {
        "58e68d69-f07f-580e-a4b6-91ef3801c5d7",
        "b8afff09-1200-5bcd-a594-6a647680f865",
    }
    for sid in res.seed_ids:
        assert sid not in minh_ids, "Ambiguous entity was blindly selected!"

    # Must be logged in excluded_seeds with reason 'ambiguous_match'
    ambig_exclusions = [x for x in res.excluded_seeds if x.get("reason") == "ambiguous_match"]
    assert len(ambig_exclusions) >= 2


def test_seed_resolution_strictly_bounded_by_seed_top_k():
    """Seed resolution must never return more than seed_top_k items."""
    res_1 = resolve_seeds_from_snapshot(
        snapshot_dir=SNAPSHOT_DIR,
        query_text="An, Bình, Chi, Dũng hoạt động tại khu vực nào?",
        seed_top_k=2,
    )
    assert len(res_1.selected_seeds) == 2
    assert len(res_1.seed_ids) == 2
    # The others beyond top_k must be recorded in excluded_seeds with 'seed_budget_exceeded'
    budget_exceeded = [x for x in res_1.excluded_seeds if x.get("reason") == "seed_budget_exceeded"]
    assert len(budget_exceeded) >= 1


# ==============================================================================
# 2. UPFRONT EDGE FILTERING: TEMPORAL, SCOPE, VALID-TIME, PREDICATE
# ==============================================================================

def test_filter_edge_rejects_future_known_facts():
    """Edges known after query known_as_of must be rejected with 'future_known'."""
    manifest = json.loads((SNAPSHOT_DIR / "manifest.json").read_text("utf-8"))
    edge = KGEdgeView(
        edge_id="edge-future-01",
        record_id="rec-01",
        source_id="src-01",
        predicate="DRIVER_STATUS",
        fact="Driver is active",
        subject_id="sub-01",
        object_id="active",
        valid_semantics={"kind": "point", "at": "2026-09-15T00:00:00Z"},
        known_at="2026-09-18T00:00:00Z",  # In the future relative to known_as_of
        known_to=None,
        event_time="2026-09-15T00:00:00Z",
        snapshot_id=manifest["snapshot_id"],
        ledger_id=manifest["ledger_id"],
        scope_id=manifest["scope_id"],
    )

    query = {
        "known_as_of": "2026-09-17T12:00:00Z",
        "time_scope": {"mode": "current"},
    }

    eligible, reason = filter_edge(edge, query, manifest)
    assert eligible is False
    assert reason == "future_known"


def test_filter_edge_rejects_replaced_or_retracted_facts():
    """Edges replaced or retracted before or at known_as_of must be rejected."""
    manifest = json.loads((SNAPSHOT_DIR / "manifest.json").read_text("utf-8"))
    edge = KGEdgeView(
        edge_id="edge-retracted-01",
        record_id="rec-01",
        source_id="src-01",
        predicate="DRIVER_STATUS",
        fact="Driver is active",
        subject_id="sub-01",
        object_id="active",
        valid_semantics={"kind": "point", "at": "2026-09-10T00:00:00Z"},
        known_at="2026-09-10T00:00:00Z",
        known_to="2026-09-15T00:00:00Z",  # Retracted on 2026-09-15
        event_time="2026-09-10T00:00:00Z",
        snapshot_id=manifest["snapshot_id"],
        ledger_id=manifest["ledger_id"],
        scope_id=manifest["scope_id"],
    )

    query = {
        "known_as_of": "2026-09-17T12:00:00Z",  # Query knows as of 17th, so retraction is visible
        "time_scope": {"mode": "current"},
    }

    eligible, reason = filter_edge(edge, query, manifest)
    assert eligible is False
    assert reason == "replaced_or_retracted"


def test_filter_edge_rejects_wrong_scope_and_snapshot():
    """Edges belonging to different scope or snapshot are rejected with 'wrong_scope'."""
    manifest = json.loads((SNAPSHOT_DIR / "manifest.json").read_text("utf-8"))
    edge = KGEdgeView(
        edge_id="edge-scope-01",
        record_id="rec-01",
        source_id="src-01",
        predicate="MEMBER_OF",
        fact="Driver member of fleet",
        subject_id="sub-01",
        object_id="fleet-01",
        valid_semantics={"kind": "interval", "from": "2026-07-01T00:00:00Z"},
        known_at="2026-09-10T00:00:00Z",
        known_to=None,
        event_time=None,
        snapshot_id="wrong-snapshot-id",
        ledger_id=manifest["ledger_id"],
        scope_id=manifest["scope_id"],
    )
    query = {"known_as_of": "2026-09-17T12:00:00Z", "time_scope": {"mode": "current"}}

    eligible, reason = filter_edge(edge, query, manifest)
    assert eligible is False
    assert reason == "wrong_scope"


def test_filter_edge_valid_time_point_and_interval():
    """Verify point and interval valid-time filtering."""
    manifest = json.loads((SNAPSHOT_DIR / "manifest.json").read_text("utf-8"))
    edge_point = KGEdgeView(
        edge_id="edge-point-01",
        record_id="rec-01",
        source_id="src-01",
        predicate="TRIP_OUTCOME",
        fact="Trip completed",
        subject_id="sub-01",
        object_id="completed",
        valid_semantics={"kind": "point", "at": "2026-09-12T10:00:00Z"},
        known_at="2026-09-12T11:00:00Z",
        known_to=None,
        event_time="2026-09-12T10:00:00Z",
        snapshot_id=manifest["snapshot_id"],
        ledger_id=manifest["ledger_id"],
        scope_id=manifest["scope_id"],
    )

    # 1. Matching window
    q_match = {
        "known_as_of": "2026-09-17T12:00:00Z",
        "time_scope": {
            "mode": "interval",
            "start": "2026-09-10T00:00:00Z",
            "end": "2026-09-15T00:00:00Z",
        },
    }
    eligible, reason = filter_edge(edge_point, q_match, manifest)
    assert eligible is True
    assert reason is None

    # 2. Window out of range
    q_mismatch = {
        "known_as_of": "2026-09-17T12:00:00Z",
        "time_scope": {
            "mode": "interval",
            "start": "2026-09-13T00:00:00Z",
            "end": "2026-09-15T00:00:00Z",
        },
    }
    eligible, reason = filter_edge(edge_point, q_mismatch, manifest)
    assert eligible is False
    assert reason == "wrong_valid_window"


def test_filter_edge_predicate_allowlist():
    """Edges with unrequested predicates are rejected when target_predicates is specified."""
    manifest = json.loads((SNAPSHOT_DIR / "manifest.json").read_text("utf-8"))
    edge = KGEdgeView(
        edge_id="edge-pred-01",
        record_id="rec-01",
        source_id="src-01",
        predicate="TRIP_OUTCOME",
        fact="Trip outcome fact",
        subject_id="sub-01",
        object_id="val-01",
        valid_semantics={"kind": "point", "at": "2026-09-12T10:00:00Z"},
        known_at="2026-09-12T11:00:00Z",
        known_to=None,
        event_time="2026-09-12T10:00:00Z",
        snapshot_id=manifest["snapshot_id"],
        ledger_id=manifest["ledger_id"],
        scope_id=manifest["scope_id"],
    )
    query = {"known_as_of": "2026-09-17T12:00:00Z", "time_scope": {"mode": "current"}}

    # Disallowed predicate
    eligible, reason = filter_edge(edge, query, manifest, target_predicates=["MEMBER_OF", "OPERATES_IN"])
    assert eligible is False
    assert reason == "predicate_mismatch"

    # Allowed predicate
    eligible, reason = filter_edge(edge, query, manifest, target_predicates=["TRIP_OUTCOME", "HAS_INCIDENT"])
    assert eligible is True
    assert reason is None


# ==============================================================================
# 3. BUDGETED BFS EXPANSION: HOPS, NODES, EDGES, AND FANOUT LIMITS
# ==============================================================================

def test_budgeted_bfs_respects_graph_budgets():
    """BFS traversal strictly respects max_hops=2, max_nodes, max_edges, and per_node_fanout."""
    manifest = json.loads((SNAPSHOT_DIR / "manifest.json").read_text("utf-8"))
    edges = load_snapshot_edges_from_parquet(SNAPSHOT_DIR)

    an_driver_id = "99e70ebe-18cd-57a3-a036-cf0ff1989861"
    query = {
        "query": "Tài xế An thuộc Depot nào và có sự cố gì?",
        "known_as_of": "2026-09-17T12:00:00.000000Z",
        "time_scope": {"mode": "current"},
    }

    # Tight budgets to test truncation
    max_hops = 2
    max_nodes = 5
    max_edges = 6
    per_node_fanout = 3

    rows, trace = budgeted_bfs(
        edges=edges,
        seed_ids=[an_driver_id],
        query=query,
        snapshot=manifest,
        max_hops=max_hops,
        max_nodes=max_nodes,
        max_edges=max_edges,
        per_node_fanout=per_node_fanout,
    )

    # 1. Invariants: node and edge counts must NOT exceed budgets
    assert len(trace["visited_nodes"]) <= max_nodes
    assert len(rows) <= max_edges
    assert trace["counts"]["hops_completed"] <= max_hops

    # 2. Frontier per hop is tracked
    assert "0" in trace["frontier_per_hop"]
    assert "1" in trace["frontier_per_hop"]

    # 3. Truncation reasons are logged
    assert len(trace["truncation_reasons"]) > 0


def test_budgeted_bfs_prioritizes_target_predicates():
    """BFS traversal prioritizes edges matching target_predicates first."""
    manifest = json.loads((SNAPSHOT_DIR / "manifest.json").read_text("utf-8"))
    edges = load_snapshot_edges_from_parquet(SNAPSHOT_DIR)

    an_driver_id = "99e70ebe-18cd-57a3-a036-cf0ff1989861"
    query = {
        "query": "Tài xế An có tham gia chương trình nào?",
        "known_as_of": "2026-09-17T12:00:00.000000Z",
        "time_scope": {"mode": "current"},
    }

    rows, trace = budgeted_bfs(
        edges=edges,
        seed_ids=[an_driver_id],
        query=query,
        snapshot=manifest,
        max_hops=1,
        max_edges=10,
        target_predicates=["DRIVER_PROGRAM"],
    )

    assert len(rows) > 0
    # First candidate must match target predicate DRIVER_PROGRAM
    assert rows[0]["predicate"] == "DRIVER_PROGRAM"


# ==============================================================================
# 4. HIGH-LEVEL TRAVERSE_KG & REPRODUCIBLE TRACE
# ==============================================================================

def test_traverse_kg_end_to_end_trace_and_locators():
    """Verify traverse_kg produces reproducible results and canonical public locators."""
    query = {
        "query_id": "q-test-kg-01",
        "query": "Tài xế DRV-001 (An) thuộc Depot nào?",
        "entity_refs": ["99e70ebe-18cd-57a3-a036-cf0ff1989861"],
        "known_as_of": "2026-09-17T12:00:00.000000Z",
        "time_scope": {"mode": "current"},
    }

    cfg = RetrievalConfig(max_hops=2, max_nodes=15, max_edges=20, per_node_fanout=5)

    res1 = traverse_kg(SNAPSHOT_DIR, query, config=cfg)
    res2 = traverse_kg(SNAPSHOT_DIR, query, config=cfg)

    # 1. Deterministic reproducibility
    assert len(res1["eligible_candidates"]) == len(res2["eligible_candidates"])
    assert res1["kg_trace"]["visited_nodes"] == res2["kg_trace"]["visited_nodes"]
    assert res1["kg_trace"]["visited_edges"] == res2["kg_trace"]["visited_edges"]

    # 2. Semantic Source Identity: points to ledger assertion, NEVER Graphiti internal UUID
    for cand in res1["eligible_candidates"]:
        locator = cand["source_locator"]
        assert locator["locator_type"] == "ledger_assertion"
        assert locator["public_snapshot_id"] == DEFAULT_SNAPSHOT_ID
        assert "assertion_id" in locator
        assert "record_id" in locator
        assert "source_id" in locator
        assert not cand["assertion_id"].startswith("graphiti:")
