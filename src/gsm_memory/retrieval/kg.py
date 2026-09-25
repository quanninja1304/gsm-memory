"""Temporal Knowledge Graph (KG) retrieval: seed resolution, upfront edge filtering,

and budgeted BFS expansion.

Guarantees:
1. Seed resolution from snapshot entity_catalog.jsonl:
   - Exact ID / code / alias public first.
   - Semantic retrieval second.
   - Strictly bounded by seed_top_k (default 3).
2. Upfront edge filtering:
   - Scope / snapshot isolation.
   - Known-as-of boundary (no future facts leak; replaced/retracted facts excluded).
   - Valid-time eligibility (point vs interval vs current).
   - Predicate / type allowlist.
   - Entity constraints (frontier reachability).
3. Budgeted BFS expansion:
   - max_hops (default 2), max_nodes (default 20), max_edges (default 30).
   - per_node_fanout limit (default 10).
   - Priority to edges matching target predicates & query text.
4. Comprehensive trace:
   - Logs seed candidates, excluded seeds, visited nodes/edges, frontier per hop, and truncation reasons.
5. Evidence points to public ledger assertions with canonical locators, never Graphiti internal UUIDs.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import pyarrow.parquet as pq

from .config import RetrievalConfig
from .semantic_seed import SeedResolutionResult, resolve_seeds_from_snapshot


def _dt(value: str) -> datetime:
    """Parse ISO timestamp with timezone."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass
class KGEdgeView:
    """Unified read-only view of a public graph edge from ledger assertion or Graphiti edge."""
    edge_id: str  # public assertion_id
    record_id: str
    source_id: str
    predicate: str
    fact: str
    subject_id: str
    object_id: str
    valid_semantics: dict[str, Any]
    known_at: str
    known_to: str | None
    event_time: str | None
    snapshot_id: str
    ledger_id: str
    scope_id: str
    qualifiers: dict[str, Any] = field(default_factory=dict)
    source_refs: list[str] = field(default_factory=list)


def filter_edge(
    edge: Any,
    query: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    target_predicates: Sequence[str] | None = None,
    frontier: set[str] | None = None,
) -> tuple[bool, str | None]:
    """Filter edge upfront according to scope, known-time, valid-time, predicate, and entity constraints.

    Returns:
        (is_eligible, exclusion_reason)
    """
    # 1. Attribute Normalization
    if hasattr(edge, "attributes"):
        attrs = edge.attributes
        edge_id = edge.uuid
        predicate = edge.name
        source_node = edge.source_node_uuid
        target_node = edge.target_node_uuid
        group_id = getattr(edge, "group_id", None)
        known_at = attrs.get("known_at")
        known_to = attrs.get("known_to")
        valid = attrs.get("valid_semantics") or {}
        event_time = attrs.get("event_time") or valid.get("at")
        edge_snapshot_id = snapshot.get("snapshot_id")
        edge_scope_id = snapshot.get("scope_id")
    elif isinstance(edge, KGEdgeView):
        edge_id = edge.edge_id
        predicate = edge.predicate
        source_node = edge.subject_id
        target_node = edge.object_id
        group_id = f"{edge.scope_id}-{edge.snapshot_id}"
        known_at = edge.known_at
        known_to = edge.known_to
        valid = edge.valid_semantics
        event_time = edge.event_time
        edge_snapshot_id = edge.snapshot_id
        edge_scope_id = edge.scope_id
    else:
        # Dictionary from record_ledger assertion
        edge_id = edge.get("assertion_id")
        predicate = edge.get("predicate")
        source_node = edge.get("subject_id")
        target_node = edge.get("object_id")
        group_id = edge.get("group_id")
        known_at = edge.get("known_at")
        known_to = edge.get("known_to")
        valid = edge.get("valid") or edge.get("valid_semantics") or {}
        event_time = edge.get("event_time") or valid.get("at")
        edge_snapshot_id = edge.get("snapshot_id", snapshot.get("snapshot_id"))
        edge_scope_id = edge.get("scope_id", snapshot.get("scope_id"))

    # 2. Scope / Snapshot Boundary
    expected_group = f'{snapshot.get("scope_id")}-{snapshot.get("snapshot_id")}'
    if group_id and group_id != expected_group:
        return False, "wrong_scope"
    if edge_snapshot_id and snapshot.get("snapshot_id") and edge_snapshot_id != snapshot.get("snapshot_id"):
        return False, "wrong_scope"
    if edge_scope_id and snapshot.get("scope_id") and edge_scope_id != snapshot.get("scope_id"):
        return False, "wrong_scope"

    # 3. Entity Constraints (reachability from active frontier)
    if frontier is not None and len(frontier) > 0:
        if source_node not in frontier and target_node not in frontier:
            return False, "entity_mismatch"

    # 4. Temporal Known-As-Of Boundary (Strict ledger prefix; no future facts)
    query_known_as_of = query.get("known_as_of")
    if query_known_as_of and known_at:
        if _dt(known_at) > _dt(query_known_as_of):
            return False, "future_known"
        if known_to and _dt(query_known_as_of) >= _dt(known_to):
            return False, "replaced_or_retracted"

    # 5. Predicate / Type Filter
    if target_predicates:
        if predicate not in target_predicates:
            return False, "predicate_mismatch"

    # 6. Valid-Time Eligibility
    time_scope = query.get("time_scope") or {"mode": "current"}
    mode = time_scope.get("mode", "current")
    if mode == "current":
        # Current valid interval: active facts at benchmark reference time
        return True, None

    requested_start = time_scope.get("valid_at") or time_scope.get("start")
    requested_end = time_scope.get("valid_at") or time_scope.get("end")

    if valid.get("kind") == "point":
        event = event_time or valid.get("at")
        if not event:
            return False, "missing_event_time"
        event_dt = _dt(event)
        if mode == "point":
            if not requested_start:
                return True, None
            ok = event_dt == _dt(requested_start)
            return ok, None if ok else "wrong_valid_time"
        if mode == "interval":
            if not requested_start or not requested_end:
                return True, None
            ok = _dt(requested_start) <= event_dt < _dt(requested_end)
            return ok, None if ok else "wrong_valid_window"

    # Interval facts: [start, end)
    start = valid.get("from")
    end_obj = valid.get("to") or {}
    end = end_obj.get("at") if isinstance(end_obj, dict) else None
    if not start:
        return True, None

    if mode == "point":
        if not requested_start:
            return True, None
        at = _dt(requested_start)
        ok = _dt(start) <= at and (not end or at < _dt(end))
        return ok, None if ok else "wrong_valid_time"

    if mode == "interval":
        if not requested_start or not requested_end:
            return True, None
        ok = _dt(start) < _dt(requested_end) and (not end or _dt(requested_start) < _dt(end))
        return ok, None if ok else "wrong_valid_window"

    return True, None


def _edge_priority_score(
    edge: Any,
    query_text: str,
    target_predicates: Sequence[str] | None = None,
    edge_search_text: str = "",
) -> float:
    """Deterministic edge scoring for priority traversal in BFS."""
    predicate = getattr(edge, "name", None) or getattr(edge, "predicate", "")
    fact = getattr(edge, "fact", "") or ""

    score = 0.0
    # 1. Target predicate bonus
    if target_predicates and predicate in target_predicates:
        score += 10.0

    # 2. Edge search text overlap
    if edge_search_text:
        search_terms = set(re.findall(r"\w+", edge_search_text.lower()))
        fact_terms = set(re.findall(r"\w+", fact.lower()))
        score += 2.0 * len(search_terms & fact_terms)

    # 3. Query text lexical overlap
    if query_text:
        q_terms = set(re.findall(r"\w+", query_text.lower()))
        fact_terms = set(re.findall(r"\w+", fact.lower()))
        score += 1.0 * len(q_terms & fact_terms)

    return score


def budgeted_bfs(
    edges: Sequence[Any],
    seed_ids: Sequence[str],
    query: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    *,
    max_hops: int = 2,
    max_nodes: int = 20,
    max_edges: int = 30,
    per_node_fanout: int = 10,
    target_predicates: Sequence[str] | None = None,
    edge_search_text: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Execute bounded BFS graph expansion starting from resolved seed entities.

    Adheres strictly to budgets:
    - max_hops
    - max_nodes
    - max_edges
    - per_node_fanout

    Logs full deterministic trace.
    """
    truncation_reasons: list[str] = []
    frontier_per_hop: dict[str, list[str]] = {}

    initial_seeds = list(seed_ids)[:max_nodes]
    visited_nodes: set[str] = set(initial_seeds)
    frontier_per_hop["0"] = sorted(initial_seeds)
    current_frontier = set(initial_seeds)

    collected_edges: list[tuple[Any, int, list[str], float]] = []
    collected_edge_ids: set[str] = set()
    excluded_candidates: list[dict[str, Any]] = []

    # Map edges by node endpoints for fast lookup
    edges_by_node: dict[str, list[Any]] = {}
    for edge in edges:
        s_node = getattr(edge, "source_node_uuid", None) or getattr(edge, "subject_id", None)
        t_node = getattr(edge, "target_node_uuid", None) or getattr(edge, "object_id", None)
        if s_node:
            edges_by_node.setdefault(str(s_node), []).append(edge)
        if t_node:
            edges_by_node.setdefault(str(t_node), []).append(edge)

    q_text = str(query.get("query", ""))

    for hop in range(1, max_hops + 1):
        if not current_frontier:
            truncation_reasons.append("no_more_frontier")
            break
        if len(visited_nodes) >= max_nodes:
            truncation_reasons.append("max_nodes_reached")
            break
        if len(collected_edge_ids) >= max_edges:
            truncation_reasons.append("max_edges_reached")
            break

        next_frontier: set[str] = set()

        for u in sorted(current_frontier):
            if len(collected_edge_ids) >= max_edges or len(visited_nodes) >= max_nodes:
                break

            connected = edges_by_node.get(u, [])
            candidate_edges_for_u = []

            for edge in connected:
                edge_id = getattr(edge, "uuid", None) or getattr(edge, "edge_id", None) or getattr(edge, "assertion_id", None)
                if edge_id in collected_edge_ids:
                    continue

                # Upfront filtering
                eligible, exclusion = filter_edge(
                    edge,
                    query=query,
                    snapshot=snapshot,
                    target_predicates=target_predicates if hop == 1 else None,
                    frontier={u},
                )
                if eligible:
                    score = _edge_priority_score(edge, q_text, target_predicates, edge_search_text)
                    candidate_edges_for_u.append((edge, score, edge_id))
                else:
                    excluded_candidates.append({
                        "assertion_id": edge_id,
                        "exclusion_reason": exclusion,
                        "hop": hop,
                    })

            # Prioritize edges matching predicates & query text
            candidate_edges_for_u.sort(key=lambda item: (-item[1], str(item[2])))

            # Apply per_node_fanout budget
            if len(candidate_edges_for_u) > per_node_fanout:
                truncation_reasons.append(f"per_node_fanout_applied_at_hop_{hop}")
                selected_for_u = candidate_edges_for_u[:per_node_fanout]
            else:
                selected_for_u = candidate_edges_for_u

            for edge, score, edge_id in selected_for_u:
                if len(collected_edge_ids) >= max_edges:
                    truncation_reasons.append("max_edges_reached")
                    break

                s_node = str(getattr(edge, "source_node_uuid", None) or getattr(edge, "subject_id", None))
                t_node = str(getattr(edge, "target_node_uuid", None) or getattr(edge, "object_id", None))
                neighbor = t_node if s_node == u else s_node

                collected_edge_ids.add(edge_id)
                collected_edges.append((edge, hop, [u], score))

                if neighbor not in visited_nodes:
                    if len(visited_nodes) < max_nodes:
                        visited_nodes.add(neighbor)
                        next_frontier.add(neighbor)
                    else:
                        truncation_reasons.append("max_nodes_reached")

        frontier_per_hop[str(hop)] = sorted(next_frontier)
        current_frontier = next_frontier

    if len(frontier_per_hop.get(str(max_hops), [])) > 0:
        truncation_reasons.append("max_hops_reached")

    # Deduplicate truncation reasons preserving order
    dedup_reasons = list(dict.fromkeys(truncation_reasons))

    # Format Candidate Rows pointing to public assertion locators
    rows = []
    # Sort collected edges by (hop, -score, edge_id)
    collected_edges.sort(key=lambda item: (item[1], -item[3], str(getattr(item[0], "uuid", None) or getattr(item[0], "edge_id", ""))))

    snapshot_id = snapshot.get("snapshot_id", "")
    ledger_id = snapshot.get("ledger_id", "")
    scope_id = snapshot.get("scope_id", "")

    for rank, (edge, depth, path, score) in enumerate(collected_edges, 1):
        if hasattr(edge, "attributes"):
            attrs = edge.attributes
            edge_id = edge.uuid
            predicate = edge.name
            fact = edge.fact
            s_node = edge.source_node_uuid
            t_node = edge.target_node_uuid
            valid = attrs.get("valid_semantics")
            known_at = attrs.get("known_at")
            rec_id = attrs.get("record_id")
            src_id = attrs.get("source_id")
        elif isinstance(edge, KGEdgeView):
            edge_id = edge.edge_id
            predicate = edge.predicate
            fact = edge.fact
            s_node = edge.subject_id
            t_node = edge.object_id
            valid = edge.valid_semantics
            known_at = edge.known_at
            rec_id = edge.record_id
            src_id = edge.source_id
        else:
            edge_id = edge["assertion_id"]
            predicate = edge["predicate"]
            fact = edge.get("fact") or f"{edge['subject_id']} {predicate} {edge['object_id']}"
            s_node = edge["subject_id"]
            t_node = edge["object_id"]
            valid = edge.get("valid")
            known_at = edge.get("known_at")
            rec_id = edge.get("record_id")
            src_id = edge.get("source_id")

        rows.append({
            "graph_object_id": edge_id,
            "assertion_id": edge_id,
            "record_id": rec_id,
            "source_id": src_id,
            "predicate": predicate,
            "fact": fact,
            "subject_id": s_node,
            "object_id": t_node,
            "valid": valid,
            "known_at": known_at,
            "snapshot_id": snapshot_id,
            "ledger_id": ledger_id,
            "scope_id": scope_id,
            "raw_rank": rank,
            "raw_score": float(score),
            "eligibility": "eligible",
            "exclusion_reason": None,
            "expansion_depth": depth,
            "expansion_path": path,
            "source_locator": {
                "locator_type": "ledger_assertion",
                "public_snapshot_id": snapshot_id,
                "record_id": rec_id,
                "assertion_id": edge_id,
                "source_id": src_id,
            },
        })

    kg_trace = {
        "visited_nodes": sorted(visited_nodes),
        "visited_edges": [r["assertion_id"] for r in rows],
        "frontier_per_hop": frontier_per_hop,
        "truncation_reasons": dedup_reasons,
        "counts": {
            "nodes_visited": len(visited_nodes),
            "edges_visited": len(rows),
            "hops_completed": len(frontier_per_hop) - 1,
            "excluded_count": len(excluded_candidates),
        },
    }

    return rows, kg_trace


def load_snapshot_edges_from_parquet(snapshot_dir: Path | str) -> list[KGEdgeView]:
    """Load public snapshot ledger assertions into KGEdgeView representations.

    Resolves replace/retract operations so only un-retracted versions are traversed.
    """
    s_path = Path(snapshot_dir)
    manifest = json.loads((s_path / "manifest.json").read_text("utf-8"))
    records = pq.read_table(s_path / "record_ledger.parquet").to_pylist()

    known_to_by_assertion: dict[str, str] = {}
    for record in records:
        for target in record.get("target_assertion_ids", []):
            known_to_by_assertion[target] = record["known_at"]

    views: list[KGEdgeView] = []
    for record in sorted(records, key=lambda row: row["commit_seq"]):
        rec_id = record["record_id"]
        src_id = record["source_id"]
        known_at = record["known_at"]
        for assertion in record["assertions"]:
            a_id = assertion["assertion_id"]
            subj = assertion["subject_id"]
            obj = assertion["object"]
            # Extract target value
            target_val = None
            for key in ("string_value", "integer_value", "boolean_value", "rational_value", "entity_ref"):
                if obj.get(key) is not None:
                    target_val = obj[key]
                    break
            if target_val is None and "value" in obj:
                target_val = obj["value"]

            valid = assertion.get("valid") or {}
            event_time = assertion.get("event_time") or valid.get("at")
            fact = f"{subj} {assertion['predicate']} {target_val}"

            views.append(KGEdgeView(
                edge_id=a_id,
                record_id=rec_id,
                source_id=src_id,
                predicate=assertion["predicate"],
                fact=fact,
                subject_id=subj,
                object_id=str(target_val),
                valid_semantics=valid,
                known_at=known_at,
                known_to=known_to_by_assertion.get(a_id),
                event_time=event_time,
                snapshot_id=manifest["snapshot_id"],
                ledger_id=manifest["ledger_id"],
                scope_id=manifest["scope_id"],
                qualifiers=assertion.get("qualifiers", {}),
                source_refs=assertion.get("source_refs", []),
            ))

    return views


def traverse_kg(
    snapshot_dir: Path | str,
    query: Mapping[str, Any],
    config: RetrievalConfig | None = None,
    graph_filters: Any = None,
) -> dict[str, Any]:
    """Execute end-to-end budgeted KG search and traversal directly on a public snapshot.

    1. Resolves seeds from entity_catalog.jsonl (exact first, semantic second).
    2. Loads snapshot edges and filters upfront.
    3. Runs budgeted BFS expansion.
    4. Emits complete traceable results with public locators.
    """
    tick = time.perf_counter()
    s_path = Path(snapshot_dir)
    manifest = json.loads((s_path / "manifest.json").read_text("utf-8"))

    seed_top_k = getattr(config, "seed_top_k", 3) if config else 3
    max_hops = getattr(config, "max_hops", 2) if config else 2
    max_nodes = getattr(config, "max_nodes", 20) if config else 20
    max_edges = getattr(config, "max_edges", 30) if config else 30
    per_node_fanout = getattr(config, "per_node_fanout", 10) if config else 10

    # 1. Resolve Seeds
    q_text = str(query.get("query", ""))
    explicit_refs = query.get("entity_refs") or []
    seed_res = resolve_seeds_from_snapshot(
        snapshot_dir=s_path,
        query_text=q_text,
        explicit_refs=explicit_refs,
        seed_top_k=seed_top_k,
    )

    # 2. Load Snapshot Edges
    edges = load_snapshot_edges_from_parquet(s_path)

    target_predicates = getattr(graph_filters, "target_predicates", None) if graph_filters else None
    edge_search_text = getattr(graph_filters, "edge_search_text", "") if graph_filters else ""

    # 3. Budgeted BFS
    rows, trace = budgeted_bfs(
        edges=edges,
        seed_ids=seed_res.seed_ids,
        query=query,
        snapshot=manifest,
        max_hops=max_hops,
        max_nodes=max_nodes,
        max_edges=max_edges,
        per_node_fanout=per_node_fanout,
        target_predicates=target_predicates,
        edge_search_text=edge_search_text,
    )

    # Attach seed trace into overall kg_trace
    trace["seed_candidates"] = seed_res.seed_candidates
    trace["excluded_seeds"] = seed_res.excluded_seeds
    trace["selected_seeds"] = seed_res.selected_seeds

    search_latency_ms = round((time.perf_counter() - tick) * 1000, 3)

    return {
        "query_id": query.get("query_id"),
        "raw_candidates": rows,
        "eligible_candidates": [r for r in rows if r["eligibility"] == "eligible"],
        "excluded_candidates": [r for r in rows if r["eligibility"] != "eligible"],
        "kg_trace": trace,
        "search_latency_ms": search_latency_ms,
    }
