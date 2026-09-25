"""Provider-independent Mode A, hybrid, computation and selection runtime."""

from __future__ import annotations

import asyncio
import json
import statistics
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

try:
    from gsm_memory.adapters.graphiti import construct_mode_a
except (ImportError, ModuleNotFoundError):
    construct_mode_a = None  # type: ignore

from gsm_memory.retrieval.bm25 import BM25Index, RankedChunk
from gsm_memory.retrieval.documents import Chunk, ChunkConfig, canonical_hash, construct_chunks, read_jsonl


def locator_key(candidate: dict[str, Any]) -> str:
    return json.dumps(candidate["source_locator"], ensure_ascii=False,
                      sort_keys=True, separators=(",", ":"))


def hybrid_union(*pools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate only identical canonical locators; preserve modalities/sources."""
    chosen: dict[str, dict[str, Any]] = {}
    for candidate in (item for pool in pools for item in pool):
        key = locator_key(candidate)
        if key not in chosen:
            chosen[key] = candidate
    return sorted(chosen.values(), key=lambda row: (row["source_kind"], row.get("rank", 0), row["evidence_id"]))


DEFAULT_MODALITY_QUOTAS = {
    "computation": 1,
    "document": 2,
    "kg": 2,
    "entity_catalog": 1,
    "definition": 1,
    "coverage": 1,
}


def select_public(query: dict[str, Any], candidates: list[dict[str, Any]], *,
                  token_budget: int = 1800, max_items: int = 22,
                  modality_quotas: dict[str, int] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Gold-blind, modality-balanced deterministic selector with guaranteed representation.

    Enforces:
    1. Modality quotas across computation, document, definition, entity_catalog, kg, coverage.
    2. Preservation of pinned definition/document references and query entity references (bridge).
    3. Co-selection of coverage artifact when computation candidate is selected.
    4. Predicate-diverse ordering for KG candidates to avoid mono-predicate starvation.
    5. Strict public-only operation: no access to private gold, support atoms, links, roles, or expected answers.
    """
    quotas = modality_quotas or DEFAULT_MODALITY_QUOTAS
    app = query.get("application_context") or {}
    pinned = set(app.get("source_snapshot_refs", [])) | set(app.get("definition_refs", []))
    query_entity_refs = set(query.get("entity_refs") or [])

    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        buckets[candidate["source_kind"]].append(candidate)

    # Sort Document / Definition buckets: pinned first, then by score/rank
    for kind in ("document", "definition"):
        if kind in buckets:
            buckets[kind].sort(key=lambda row: (
                row.get("source_id") not in pinned,
                -row.get("score", 0.0),
                row.get("rank", 0),
                row["evidence_id"],
            ))

    # Sort Entity Catalog bucket: matching query entity refs first
    if "entity_catalog" in buckets:
        buckets["entity_catalog"].sort(key=lambda row: (
            row.get("source_id") not in query_entity_refs and row.get("source_locator", {}).get("entity_id") not in query_entity_refs,
            -row.get("score", 0.0),
            row.get("rank", 0),
            row["evidence_id"],
        ))

    # Sort KG bucket: Interleave across distinct predicates to ensure predicate diversity
    if "kg" in buckets:
        pred_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in buckets["kg"]:
            pred = row.get("predicate", "UNKNOWN")
            pred_groups[pred].append(row)
        for p_list in pred_groups.values():
            p_list.sort(key=lambda row: (-row.get("score", 0.0), row.get("rank", 0), row["evidence_id"]))

        # Interleave across predicates deterministically (alphabetical by predicate name)
        interleaved_kg: list[dict[str, Any]] = []
        pred_keys = sorted(pred_groups.keys())
        max_len = max((len(l) for l in pred_groups.values()), default=0)
        for idx in range(max_len):
            for p in pred_keys:
                if idx < len(pred_groups[p]):
                    interleaved_kg.append(pred_groups[p][idx])
        buckets["kg"] = interleaved_kg

    # Sort Computation and Coverage buckets
    for kind in ("computation", "coverage"):
        if kind in buckets:
            buckets[kind].sort(key=lambda row: (-row.get("score", 0.0), row.get("rank", 0), row["evidence_id"]))

    selected: list[dict[str, Any]] = []
    spent = 0

    # Phase 1: Guaranteed Modality Quota Allocation
    quota_order = [k for k in ("computation", "coverage", "definition", "document", "entity_catalog", "kg") if buckets[k]]
    for kind in quota_order:
        needed = quotas.get(kind, 1)
        while needed > 0 and buckets[kind] and len(selected) < max_items:
            candidate = buckets[kind][0]
            cost = candidate.get("token_cost", 1)
            if spent + cost <= token_budget:
                selected.append(buckets[kind].pop(0))
                spent += cost
                needed -= 1
            else:
                break

    # If computation was selected, ensure its matching coverage artifact is also selected if available
    comp_selected = [c for c in selected if c.get("source_kind") == "computation"]
    cov_selected = [c for c in selected if c.get("source_kind") == "coverage"]
    if comp_selected and not cov_selected and buckets["coverage"] and len(selected) < max_items:
        candidate = buckets["coverage"][0]
        cost = candidate.get("token_cost", 1)
        if spent + cost <= token_budget:
            selected.append(buckets["coverage"].pop(0))
            spent += cost

    # Phase 2: Round-robin filling for remaining slots up to max_items or token_budget
    order = [kind for kind in ("document", "definition", "entity_catalog", "kg", "coverage", "computation") if buckets[kind]]
    while order and len(selected) < max_items:
        remaining = []
        for kind in order:
            if not buckets[kind] or len(selected) >= max_items:
                continue
            candidate = buckets[kind].pop(0)
            cost = candidate.get("token_cost", 1)
            if spent + cost <= token_budget:
                selected.append(candidate)
                spent += cost
            if buckets[kind]:
                remaining.append(kind)
        order = remaining

    selected_ids = {row["evidence_id"] for row in selected}
    excluded = []
    for row in candidates:
        if row["evidence_id"] in selected_ids:
            continue
        cost = row.get("token_cost", 1)
        reason = "token_budget_exceeded" if spent + cost > token_budget else "selected_item_cap_reached"
        excluded.append({"evidence_id": row["evidence_id"], "reason": reason,
                         "source_kind": row["source_kind"], "rank": row.get("rank"),
                         "score": row.get("score"), "token_cost": cost,
                         "budget_state": {"tokens_spent": spent, "token_budget": token_budget,
                                          "selected_items": len(selected), "max_items": max_items,
                                          "candidate_would_fit_tokens": spent + cost <= token_budget}})
    return selected, excluded


def _percentile(values: list[float], fraction: float) -> float:
    """Nearest-rank percentile over a declared finite aggregation unit."""
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(fraction * (len(ordered) - 1))))
    return ordered[index]


def _latency_statistics(traces: list[dict[str, Any]], graph_receipts: list[dict[str, Any]]) -> dict[str, Any]:
    stage_contract = {
        "document": ("query", "cold", ["document"]),
        "kg_search": ("query_search_call", "cold", ["kg_search"]),
        "eligibility_normalization": ("query", "cold", ["eligibility_normalization"]),
        "computation": ("query", "cold", ["computation"]),
        "hybrid_merge": ("query", "cold", ["hybrid_merge"]),
        "selection": ("query", "cold", ["selection"]),
        "total_pre_reader": (
            "query", "cold",
            ["document", "kg_search", "eligibility_normalization", "computation", "hybrid_merge", "selection"],
        ),
        "observed_query_assembly": (
            "query", "cold",
            ["document", "eligibility_normalization", "computation", "hybrid_merge", "selection"],
        ),
    }
    summary = {}
    for stage, (unit, cache_status, included) in stage_contract.items():
        values = [trace["latency_ms"][stage] for trace in traces]
        summary[stage] = {
            "aggregation_unit": unit,
            "denominator": len(values),
            "included_count": len(values),
            "cache_status": cache_status,
            "included_stages": included,
            "min_ms": min(values),
            "median_ms": statistics.median(values),
            "p95_ms": _percentile(values, 0.95),
            "max_ms": max(values),
            "mean_ms": sum(values) / len(values),
        }
    construction = [row["construction_ms"] for row in graph_receipts]
    summary["graph_construction"] = {
        "aggregation_unit": "snapshot_graph",
        "denominator": len(construction),
        "included_count": len(construction),
        "cache_status": "cold",
        "included_stages": ["graph_construction"],
        "min_ms": min(construction),
        "median_ms": statistics.median(construction),
        "p95_ms": _percentile(construction, 0.95),
        "max_ms": max(construction),
        "mean_ms": sum(construction) / len(construction),
    }
    return summary


def document_allowed_source_ids(query: dict[str, Any], snapshot_dir: Path | None = None) -> tuple[set[str], set[str]]:
    app = query.get("application_context") or {}
    pinned = set(app.get("source_snapshot_refs", [])) | set(app.get("definition_refs", []))
    allowed = set(pinned)
    allowed_definitions: set[str] = set()
    if snapshot_dir is not None:
        allowed.update(row["snapshot_id"] for row in read_jsonl(snapshot_dir / "documents.jsonl"))
        allowed_definitions = {row["definition_id"] for row in read_jsonl(snapshot_dir / "definitions.jsonl")}
        allowed.update(allowed_definitions)
    return allowed, allowed_definitions


def chunk_candidate(query: dict[str, Any], chunk: Chunk, *, rank: int, score: float,
                    stage: str, rank_components: dict[str, int] | None = None) -> dict[str, Any]:
    if chunk.kind == "definition":
        locator = {"locator_type": "definition_artifact", "definition_id": chunk.source_id,
                   "document_revision_id": chunk.document_revision_id, "span_start": chunk.normalized_start,
                   "span_end": chunk.normalized_end}
    else:
        locator = {"locator_type": "document_span", "source_id": chunk.source_id,
                   "document_revision_id": chunk.document_revision_id, "span_start": chunk.normalized_start,
                   "span_end": chunk.normalized_end, "clause_ids": list(chunk.clause_ids)}
    row = {"evidence_id": f"chunk:{chunk.chunk_id}", "source_kind": chunk.kind,
           "source_id": chunk.source_id, "content": chunk.text, "source_locator": locator,
           "origin_stage": stage, "rank": rank, "score": score, "token_cost": chunk.token_count,
           "eligibility": "eligible", "profile_id": chunk.profile_id,
           "snapshot_id": query["public_snapshot_id"]}
    if rank_components is not None:
        row["rank_components"] = dict(sorted(rank_components.items()))
    return row


def _document_candidates(query: dict[str, Any], chunks: list[Chunk], index: BM25Index,
                         top_k: int, snapshot_dir: Path | None = None) -> list[dict[str, Any]]:
    allowed, allowed_definitions = document_allowed_source_ids(query, snapshot_dir)
    app = query.get("application_context") or {}
    pinned = set(app.get("source_snapshot_refs", [])) | set(app.get("definition_refs", []))
    ranked_by_id = {row.chunk_id: row for row in index.search(query["query"], top_k=top_k,
                                                               allowed_source_ids=allowed or None)}
    # A public request that pins multiple editions/definitions must retain a
    # candidate from each requested source; no gold role is consulted.
    for source_id in sorted(pinned):
        source_hits = index.search(query["query"], top_k=top_k, allowed_source_ids={source_id})
        for row in source_hits:
            ranked_by_id.setdefault(row.chunk_id, row)
        # A pinned public source is itself an explicit retrieval constraint. If
        # its text has no lexical overlap with the natural-language query, keep
        # one deterministic zero-score chunk so the requested edition or
        # definition remains available to the gold-blind selector.
        if not source_hits:
            source_chunks = sorted(
                (chunk for chunk in chunks if chunk.source_id == source_id),
                key=lambda chunk: chunk.chunk_id,
            )
            if source_chunks:
                chunk = source_chunks[0]
                ranked_by_id.setdefault(
                    chunk.chunk_id,
                    RankedChunk(
                        chunk.chunk_id,
                        chunk.source_id,
                        chunk.document_revision_id,
                        0.0,
                        top_k + 1,
                        "public_pin_fallback",
                    ),
                )
    # Definitions are a separate public modality. Preserve its best lexical
    # candidates so a large document corpus cannot crowd definitions out of a
    # shared top-k heap.
    for row in index.search(query["query"], top_k=2, allowed_source_ids=allowed_definitions):
        ranked_by_id.setdefault(row.chunk_id, row)
    ranked = sorted(ranked_by_id.values(), key=lambda row: (-row.score, row.chunk_id))
    by_id = {chunk.chunk_id: chunk for chunk in chunks}
    return [chunk_candidate(query, by_id[row.chunk_id], rank=row.rank, score=row.score, stage=row.stage,
                            rank_components={"bm25": row.rank}) for row in ranked]


def _kg_candidates(result: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    for row in result["eligible_candidates"]:
        output.append({"evidence_id": f'kg:{row["assertion_id"]}', "source_kind": "kg",
                       "source_id": row["source_id"], "content": row["fact"],
                       "source_locator": row["source_locator"], "origin_stage": "graphiti_mode_a",
                       "rank": row["raw_rank"], "score": row["raw_score"], "token_cost": 24,
                       "eligibility": "eligible", "entity_refs": [row["subject_id"], row["object_id"]],
                       "valid": row["valid"], "known_at": row["known_at"], "predicate": row["predicate"],
                       "snapshot_id": row["snapshot_id"], "ledger_id": row["ledger_id"]})
    return output


def entity_catalog_candidates(snapshot_dir: Path, query: dict[str, Any],
                              kg_candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    requested = set(query.get("entity_refs") or [])
    for candidate in kg_candidates:
        requested.update(candidate.get("entity_refs") or [])
    rows = read_jsonl(snapshot_dir / "entity_catalog.jsonl")
    output = []
    for row in rows:
        if row["entity_id"] not in requested:
            continue
        locator = {"locator_type": "entity_catalog", "public_snapshot_id": query["public_snapshot_id"],
                   "entity_id": row["entity_id"], "scope_id": row["scope_id"]}
        output.append({"evidence_id": f'entity:{row["entity_id"]}', "source_kind": "entity_catalog",
                       "source_id": row["entity_id"], "content": json.dumps(row, ensure_ascii=False, sort_keys=True),
                       "source_locator": locator, "origin_stage": "public_entity_catalog", "rank": 1,
                       "score": 1.0, "token_cost": 24, "eligibility": "eligible",
                       "snapshot_id": query["public_snapshot_id"]})
    return sorted(output, key=lambda row: row["evidence_id"])


def _active_assertions(records: list[dict[str, Any]]) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    active: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for record in sorted(records, key=lambda row: row["commit_seq"]):
        for target in record["target_assertion_ids"]:
            active.pop(target, None)
        for assertion in record["assertions"]:
            active[assertion["assertion_id"]] = (record, assertion)
    return active


def computation_candidates(
    snapshot_dir: Path,
    query: dict[str, Any],
    *,
    target_metric: str | None = None,
    entity_refs: list[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    # 1. Target metric determination (from parameter or query filters, NOT raw string in query)
    metric = (
        target_metric
        or (query.get("computation_filters") or {}).get("target_metric")
        or query.get("target_metric")
    )
    if metric is None:
        q_lower = query.get("query", "").lower()
        if "cancel_rate" in q_lower or "tỷ lệ hủy" in q_lower or "tỷ lệ huỷ" in q_lower:
            metric = "cancel_rate_30d"

    if metric != "cancel_rate_30d":
        return [], {"status": "not_applicable", "enumerated_members": 0, "target_metric": metric}

    # 2. Entity resolution check
    entities = entity_refs if entity_refs is not None else (query.get("entity_refs") or [])
    if not entities or len(entities) != 1 or entities[0] == "unresolved_entity":
        return [], {"status": "unresolved_entity", "enumerated_members": 0, "target_metric": metric}
    subject = entities[0]

    # 3. Read public snapshot artifacts & verify coverage
    artifacts = read_jsonl(snapshot_dir / "artifacts.jsonl")
    matching = [
        item for item in artifacts
        if item["artifact_type"] == "coverage"
        and item["coverage_spec"]["covered_domain"]["domain_id"] == "terminal_trip_population"
        and item["coverage_spec"]["subject_id"] == subject
    ]
    if not matching:
        return [], {"status": "missing_coverage", "enumerated_members": 0, "target_metric": metric}
    coverage = matching[0]

    # 4. Read record ledger and resolve retract/replace & temporal eligibility
    records = pq.read_table(snapshot_dir / "record_ledger.parquet").to_pylist()
    known_as_of = query.get("known_as_of")
    if known_as_of:
        records = [r for r in records if r["known_at"] <= known_as_of]

    active = _active_assertions(records)
    allowed_sources = set(coverage["source_set"]["allowed_source_ids"])
    window = coverage["coverage_spec"]["valid_window"]

    # Gather full eligible population, deduplicated by terminal trip_id
    trips_by_id: dict[str, dict[str, Any]] = {}
    for assertion_id, (record, assertion) in active.items():
        qualifiers = assertion["qualifiers"]
        event = assertion["valid"].get("at") or assertion.get("event_time")
        trip_id = qualifiers.get("trip_id")
        outcome = qualifiers.get("outcome")
        if (
            assertion["predicate"] == "TRIP_OUTCOME"
            and assertion["subject_id"] == subject
            and record["source_id"] in allowed_sources
            and event
            and window["start"] <= event < window["end"]
            and trip_id
            and outcome in {"cancelled", "completed"}
        ):
            trips_by_id[trip_id] = {
                "assertion_id": assertion_id,
                "record_id": record["record_id"],
                "source_id": record["source_id"],
                "trip_id": trip_id,
                "outcome": outcome,
                "event_time": event,
            }

    members = sorted(trips_by_id.values(), key=lambda row: row["trip_id"])
    member_ids = [row["trip_id"] for row in members]

    verified = (
        coverage["complete"]
        and len(members) == coverage["member_count"]
        and member_ids == sorted(coverage["member_ids"])
    )
    if not verified:
        return [], {
            "status": "coverage_mismatch",
            "enumerated_members": len(members),
            "declared_members": coverage["member_count"],
            "target_metric": metric,
        }

    # 5. Exact rational arithmetic and denominator zero
    cancelled = sum(1 for row in members if row["outcome"] == "cancelled")
    total = len(members)

    if total == 0:
        value = None
        metric_status = "undefined"
        status = "complete"  # Execution complete with verified empty population
        content = "cancel_rate_30d full-source computation: undefined (denominator 0)"
    else:
        value = Fraction(cancelled, total)
        metric_status = "answerable"
        status = "complete"
        content = "cancel_rate_30d full-source computation"

    locator = {
        "locator_type": "computation",
        "public_snapshot_id": query["public_snapshot_id"],
        "coverage_artifact_id": coverage["artifact_id"],
        "coverage_spec_id": coverage["coverage_spec_id"],
        "member_assertion_ids": [row["assertion_id"] for row in members],
    }
    coverage_locator = {
        "locator_type": "coverage_artifact",
        "public_snapshot_id": query["public_snapshot_id"],
        "artifact_id": coverage["artifact_id"],
        "coverage_spec_id": coverage["coverage_spec_id"],
    }
    coverage_candidate = {
        "evidence_id": f'coverage:{coverage["artifact_id"]}',
        "source_kind": "coverage",
        "source_id": coverage["artifact_id"],
        "content": "complete public coverage artifact",
        "source_locator": coverage_locator,
        "origin_stage": "public_coverage_artifact",
        "rank": 1,
        "score": 1.0,
        "token_cost": 48,
        "eligibility": "eligible",
        "coverage_status": "complete",
        "snapshot_id": query["public_snapshot_id"],
    }
    candidate = {
        "evidence_id": f'computation:{canonical_hash(locator)}',
        "source_kind": "computation",
        "source_id": coverage["artifact_id"],
        "content": content,
        "source_locator": locator,
        "origin_stage": "full_source_computation",
        "rank": 1,
        "score": 1.0,
        "token_cost": 80,
        "eligibility": "eligible",
        "coverage_status": "complete",
        "metric_status": metric_status,
        "typed_value": None if value is None else {"n": value.numerator, "d": value.denominator},
        "members": members,
        "snapshot_id": query["public_snapshot_id"],
    }
    receipt = {
        "status": status,
        "metric_status": metric_status,
        "zero_denominator": (total == 0),
        "enumerated_members": total,
        "cancelled": cancelled,
        "coverage_artifact_id": coverage["artifact_id"],
        "target_metric": metric,
        "typed_value": None if value is None else {"n": value.numerator, "d": value.denominator},
    }
    return [coverage_candidate, candidate], receipt


async def run_offline_closure(release: Path, profile: str = "retrieval_full", *,
                              document_top_k: int = 10, graph_top_k: int = 40,
                              token_budget: int = 1800,
                              retrieval_config: Any | None = None) -> dict[str, Any]:
    """Run the public-only closure through the canonical query planner.

    Graph construction is amortized once per public snapshot. Query analysis,
    modality routing, document search, KG normalization, computation, merging,
    and selection are then executed through :class:`RetrievalPlanner`.
    """
    from gsm_memory.retrieval.config import RetrievalConfig
    from gsm_memory.retrieval.dense import DenseChunkIndex
    from gsm_memory.retrieval.nvidia_embed import NvidiaNemotronEmbedder
    from gsm_memory.retrieval.planner import RetrievalPlanner
    from gsm_memory.retrieval.query_analysis import analyze_query, configured_query_planner_provider
    from gsm_memory.retrieval.rerank import NvidiaReranker

    run_started = time.perf_counter()
    config = retrieval_config or RetrievalConfig(document_top_k=document_top_k, kg_top_k=graph_top_k,
                                                  token_budget=token_budget)
    chunks, links, inventory = construct_chunks(
        release, profile, ChunkConfig(max_tokens=config.max_tokens, overlap=config.overlap)
    )
    index = BM25Index(chunks)
    raw_queries = read_jsonl(release / "public" / "runtime_queries" / "dev.jsonl")
    embedder = None
    dense_index = None
    reranker = None
    if config.dense_index_path:
        embedder = NvidiaNemotronEmbedder(model=config.embedding_model)
        dense_index = DenseChunkIndex.load(
            config.dense_index_path, chunks=chunks, chunk_config_hash=config.dense_index_config_hash(),
            embedding_model=config.embedding_model, profile_version=inventory["profile_version"],
        )
    if config.reranker_model:
        reranker = NvidiaReranker(model=config.reranker_model)
    planner = RetrievalPlanner(config, dense_index=dense_index, embedder=embedder, reranker=reranker)
    query_planner_provider = configured_query_planner_provider(config)
    prepared: list[tuple[dict[str, Any], Any, Any]] = []
    for query in raw_queries:
        query_plan = analyze_query(
            query,
            provider=query_planner_provider,
            release_dir=release,
            config=config,
        )
        plan = planner.plan(query_plan, query)
        runtime_query = {
            **query,
            "entity_refs": plan.entity_refs,
            "graph_filters": query_plan.graph_filters.model_dump(),
            "computation_filters": query_plan.computation_filters.model_dump(),
            "seed_top_k": config.seed_top_k,
            "max_hops": config.max_hops,
            "max_nodes": config.max_nodes,
            "max_edges": config.max_edges,
            "per_node_fanout": config.per_node_fanout,
        }
        prepared.append((runtime_query, query_plan, plan))

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for query, _, plan in prepared:
        if plan.enable_kg:
            grouped[query["public_snapshot_id"]].append(query)
    graph_receipts = []
    graph_results: dict[str, dict[str, Any]] = {}
    for snapshot_id in sorted(grouped):
        if construct_mode_a is None:
            raise RuntimeError("Graphiti Mode A adapter unavailable; install graphiti extra or inject mock")
        snapshot_dir = release / "public" / "snapshots" / snapshot_id
        graph = await construct_mode_a(
            snapshot_dir, search_queries=grouped[snapshot_id], search_limit=graph_top_k
        )
        snapshot = json.loads((snapshot_dir / "manifest.json").read_text("utf-8"))
        graph_receipts.append({"snapshot_id": snapshot_id,
                               "graph_group": f'{snapshot["scope_id"]}-{snapshot_id}',
                               "ledger_id": snapshot["ledger_id"],
                               "nodes": graph["nodes"], "edges": graph["edges"], "episodes": graph["episodes"],
                               "construction_ms": graph["construction_ms"], "cache_status": "cold",
                               "repeat_write_idempotent": graph["repeat_write_idempotent"],
                               "projection_link_count": len(graph["projection_links"])})
        graph_results.update({row["query_id"]: row for row in graph["query_results"]})

    traces = []
    for query, query_plan, plan in prepared:
        snapshot_dir = release / "public" / "snapshots" / query["public_snapshot_id"]
        graph = graph_results.get(query["query_id"])
        result = await planner.execute_async(
            plan, query, chunks, index, snapshot_dir, graph_result=graph,
            document_top_k=config.document_top_k, token_budget=config.token_budget,
            max_items=config.max_selected_items,
        )
        documents = result.modality_candidates["document"]
        kg = result.modality_candidates["kg"]
        computation = result.modality_candidates["computation"]
        graph_raw = graph["raw_candidates"] if graph else []
        graph_excluded = graph["excluded_candidates"] if graph else []
        excluded_reasons = Counter(row.get("exclusion_reason") for row in graph_excluded)
        excluded_reasons.update(row["reason"] for row in result.selector_excluded)
        traces.append({"query_id": query["query_id"], "snapshot_id": query["public_snapshot_id"],
                       "runtime_status": "completed_retrieval", "query_plan": query_plan.model_dump(),
                       "retrieval_plan": plan.model_dump(), "receipts": result.receipts,
                       "document_candidates": documents, "kg_raw_candidates": graph_raw, "kg_candidates": kg,
                       "kg_trace": result.receipts.get("kg", {}).get("kg_trace", {}),
                       "computation_candidates": computation, "hybrid_candidates": result.candidates,
                       "selected_evidence": result.selected_evidence, "selector_excluded": result.selector_excluded,
                       "excluded_counts": dict(sorted(excluded_reasons.items())),
                       "counts": {"document": len(documents), "kg_raw": len(graph_raw),
                                  "kg_eligible": len(kg), "computation": len(computation),
                                  "hybrid": len(result.candidates), "selected": len(result.selected_evidence)},
                       "latency_ms": {**result.latency_ms,
                                      "observed_query_assembly": result.wall_time_ms},
                       "latency_contract": {"execution_mode": "parallel_planner",
                                            "aggregation_unit": "query",
                                            "cache_status": "cold",
                                            "included_stages": ["document", "kg_search", "eligibility_normalization", "computation", "hybrid_merge", "selection"],
                                            "invariant": "wall-clock pre-reader latency is at least each included branch latency",
                                            "invariant_pass": result.wall_time_ms + 1e-9 >= max(result.latency_ms[stage] for stage in ("document", "kg_search", "eligibility_normalization", "computation", "hybrid_merge", "selection")),
                                            "note": "Document, KG normalization and computation are launched concurrently; Graphiti construction/search is amortized per snapshot before query assembly."},
                       "computation_receipt": result.receipts.get("computation", {}), "cache_status": "cold",
                       "limits": {"document_top_k": document_top_k, "graph_top_k": graph_top_k,
                                  "token_budget": token_budget, "selected_cap": config.max_selected_items,
                                  "seed_top_k": config.seed_top_k, "max_hops": config.max_hops,
                                  "max_nodes": config.max_nodes, "max_edges": config.max_edges},
                       "truncated": {"document": len(documents) >= document_top_k,
                                     "kg": len(graph_raw) >= graph_top_k,
                                     "selection": len(result.selector_excluded) > 0}})
    logical = [{key: value for key, value in trace.items() if key != "latency_ms"} for trace in traces]
    return {"schema_version": "phase-b-offline-closure-v1", "release": release.name, "profile": profile,
            "query_count": len(prepared), "terminal_count": len(traces),
            "terminal_status_counts": dict(Counter(trace["runtime_status"] for trace in traces)),
            "snapshot_count": len({query["public_snapshot_id"] for query, _, _ in prepared}),
            "kg_snapshot_count": len(grouped),
            "kg_ledger_count": len({row["ledger_id"] for row in graph_receipts}),
            "ledger_count": len({
                json.loads((release / "public" / "snapshots" / query["public_snapshot_id"] / "manifest.json").read_text("utf-8"))["ledger_id"]
                for query, _, _ in prepared
            }),
            "graph_receipts": graph_receipts, "document_inventory": inventory,
            "projection_link_count": len(links), "traces": traces,
            "latency_statistics": _latency_statistics(traces, graph_receipts),
            "logical_digest": canonical_hash(logical),
            "instrumentation": {"total_wall_ms": round((time.perf_counter() - run_started) * 1000, 3),
                                "provider_calls": 0, "tokens": None, "token_reason": "provider_not_called",
                                "provider_cost": None, "cost_reason": "provider_not_called",
                                "reader_latency": None, "reader_reason": "reader_not_run",
                                "errors": 0, "retries": 0}}


def run_offline_closure_sync(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return asyncio.run(run_offline_closure(*args, **kwargs))
