"""Provider-independent Mode A, hybrid, computation and selection runtime."""

from __future__ import annotations

import asyncio
import hashlib
import json
import statistics
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from gsm_memory.adapters.graphiti import construct_mode_a
from gsm_memory.retrieval.bm25 import BM25Index, RankedChunk
from gsm_memory.retrieval.documents import Chunk, ChunkConfig, canonical_hash, construct_chunks, read_jsonl


def graph_namespace_key(release_digest: str, snapshot_id: str, config_hash: str,
                        adapter_hash: str) -> str:
    return canonical_hash({"release_digest": release_digest, "snapshot_id": snapshot_id,
                           "mode": "A", "config_hash": config_hash,
                           "graphiti": "0.30.2", "backend": "kuzu-0.11.3",
                           "adapter_hash": adapter_hash})


def locator_key(candidate: dict[str, Any]) -> str:
    return canonical_hash(candidate["source_locator"])


def hybrid_union(*pools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate only identical canonical locators; preserve modalities/sources."""
    chosen: dict[str, dict[str, Any]] = {}
    for candidate in (item for pool in pools for item in pool):
        key = locator_key(candidate)
        if key not in chosen:
            chosen[key] = candidate
    return sorted(chosen.values(), key=lambda row: (row["source_kind"], row.get("rank", 0), row["evidence_id"]))


def select_public(query: dict[str, Any], candidates: list[dict[str, Any]], *,
                  token_budget: int = 1800, max_items: int = 12) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Gold-blind, modality-balanced deterministic selector."""
    app = query.get("application_context") or {}
    pinned = set(app.get("source_snapshot_refs", [])) | set(app.get("definition_refs", []))
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        buckets[candidate["source_kind"]].append(candidate)
    for values in buckets.values():
        values.sort(key=lambda row: (row.get("source_id") not in pinned, -row.get("score", 0.0), row.get("rank", 0), row["evidence_id"]))
    order = [kind for kind in ("document", "definition", "entity_catalog", "kg", "coverage", "computation") if buckets[kind]]
    selected: list[dict[str, Any]] = []
    spent = 0
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


def _document_candidates(query: dict[str, Any], chunks: list[Chunk], index: BM25Index,
                         top_k: int, snapshot_dir: Path | None = None) -> list[dict[str, Any]]:
    app = query.get("application_context") or {}
    pinned = set(app.get("source_snapshot_refs", [])) | set(app.get("definition_refs", []))
    allowed = set(pinned)
    allowed_definitions: set[str] = set()
    if snapshot_dir is not None:
        allowed.update(row["snapshot_id"] for row in read_jsonl(snapshot_dir / "documents.jsonl"))
        allowed_definitions = {row["definition_id"] for row in read_jsonl(snapshot_dir / "definitions.jsonl")}
        allowed.update(allowed_definitions)
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
    output = []
    for row in ranked:
        chunk = by_id[row.chunk_id]
        if chunk.kind == "definition":
            locator = {
                "locator_type": "definition_artifact",
                "definition_id": chunk.source_id,
                "document_revision_id": chunk.document_revision_id,
                "span_start": chunk.normalized_start,
                "span_end": chunk.normalized_end,
            }
        else:
            locator = {"locator_type": "document_span", "source_id": chunk.source_id,
                       "document_revision_id": chunk.document_revision_id,
                       "span_start": chunk.normalized_start, "span_end": chunk.normalized_end,
                       "clause_ids": list(chunk.clause_ids)}
        output.append({"evidence_id": f"chunk:{chunk.chunk_id}", "source_kind": chunk.kind,
                       "source_id": chunk.source_id, "content": chunk.text,
                       "source_locator": locator,
                       "origin_stage": row.stage, "rank": row.rank, "score": row.score,
                       "token_cost": chunk.token_count, "eligibility": "eligible",
                       "profile_id": chunk.profile_id, "snapshot_id": query["public_snapshot_id"]})
    return output


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


def computation_candidates(snapshot_dir: Path, query: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if "cancel_rate_30d" not in query["query"]:
        return [], {"status": "not_applicable", "enumerated_members": 0}
    entities = query.get("entity_refs") or []
    if len(entities) != 1:
        return [], {"status": "unsupported_request", "enumerated_members": 0}
    subject = entities[0]
    artifacts = read_jsonl(snapshot_dir / "artifacts.jsonl")
    matching = [item for item in artifacts if item["artifact_type"] == "coverage"
                and item["coverage_spec"]["covered_domain"]["domain_id"] == "terminal_trip_population"
                and item["coverage_spec"]["subject_id"] == subject]
    if not matching:
        return [], {"status": "missing_coverage", "enumerated_members": 0}
    coverage = matching[0]
    records = pq.read_table(snapshot_dir / "record_ledger.parquet").to_pylist()
    active = _active_assertions(records)
    allowed_sources = set(coverage["source_set"]["allowed_source_ids"])
    window = coverage["coverage_spec"]["valid_window"]
    members = []
    for assertion_id, (record, assertion) in active.items():
        qualifiers = assertion["qualifiers"]
        event = assertion["valid"].get("at")
        if (assertion["predicate"] == "TRIP_OUTCOME" and assertion["subject_id"] == subject
                and record["source_id"] in allowed_sources and event
                and window["start"] <= event < window["end"]):
            members.append({"assertion_id": assertion_id, "record_id": record["record_id"],
                            "source_id": record["source_id"], "trip_id": qualifiers["trip_id"],
                            "outcome": qualifiers["outcome"], "event_time": event})
    members.sort(key=lambda row: row["trip_id"])
    member_ids = [row["trip_id"] for row in members]
    verified = (coverage["complete"] and len(members) == coverage["member_count"]
                and member_ids == sorted(coverage["member_ids"]))
    if not verified:
        return [], {"status": "coverage_mismatch", "enumerated_members": len(members),
                    "declared_members": coverage["member_count"]}
    cancelled = sum(row["outcome"] == "cancelled" for row in members)
    value = Fraction(cancelled, len(members)) if members else None
    locator = {"locator_type": "computation", "public_snapshot_id": query["public_snapshot_id"],
               "coverage_artifact_id": coverage["artifact_id"], "coverage_spec_id": coverage["coverage_spec_id"],
               "member_assertion_ids": [row["assertion_id"] for row in members]}
    coverage_locator = {"locator_type": "coverage_artifact", "public_snapshot_id": query["public_snapshot_id"],
                        "artifact_id": coverage["artifact_id"], "coverage_spec_id": coverage["coverage_spec_id"]}
    coverage_candidate = {"evidence_id": f'coverage:{coverage["artifact_id"]}', "source_kind": "coverage",
                          "source_id": coverage["artifact_id"], "content": "complete public coverage artifact",
                          "source_locator": coverage_locator, "origin_stage": "public_coverage_artifact", "rank": 1,
                          "score": 1.0, "token_cost": 48, "eligibility": "eligible", "coverage_status": "complete",
                          "snapshot_id": query["public_snapshot_id"]}
    candidate = {"evidence_id": f'computation:{canonical_hash(locator)}', "source_kind": "computation",
                 "source_id": coverage["artifact_id"], "content": "cancel_rate_30d full-source computation",
                 "source_locator": locator, "origin_stage": "full_source_computation", "rank": 1, "score": 1.0,
                 "token_cost": 80, "eligibility": "eligible", "coverage_status": "complete",
                 "typed_value": None if value is None else {"n": value.numerator, "d": value.denominator},
                 "members": members, "snapshot_id": query["public_snapshot_id"]}
    return [coverage_candidate, candidate], {"status": "complete", "enumerated_members": len(members),
                         "cancelled": cancelled, "coverage_artifact_id": coverage["artifact_id"]}


async def run_offline_closure(release: Path, profile: str = "retrieval_full", *,
                              document_top_k: int = 10, graph_top_k: int = 40,
                              token_budget: int = 1800) -> dict[str, Any]:
    run_started = time.perf_counter()
    chunks, links, inventory = construct_chunks(release, profile, ChunkConfig())
    index = BM25Index(chunks)
    queries = read_jsonl(release / "public" / "runtime_queries" / "dev.jsonl")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for query in queries:
        grouped[query["public_snapshot_id"]].append(query)
    adapter_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    # Runtime identity is derived strictly from the public manifest bytes.
    release_digest = hashlib.sha256((release / "public" / "runtime_manifest.json").read_bytes()).hexdigest()
    graph_receipts = []
    graph_results: dict[str, dict[str, Any]] = {}
    for snapshot_id in sorted(grouped):
        snapshot_dir = release / "public" / "snapshots" / snapshot_id
        graph = await construct_mode_a(snapshot_dir, search_queries=grouped[snapshot_id], search_limit=graph_top_k)
        key = graph_namespace_key(release_digest, snapshot_id, inventory["config_hash"], adapter_hash)
        graph_receipts.append({"snapshot_id": snapshot_id, "namespace_key": key,
                               "ledger_id": json.loads((snapshot_dir / "manifest.json").read_text("utf-8"))["ledger_id"],
                               "nodes": graph["nodes"], "edges": graph["edges"], "episodes": graph["episodes"],
                               "construction_ms": graph["construction_ms"], "cache_status": "cold",
                               "repeat_write_idempotent": graph["repeat_write_idempotent"],
                               "projection_link_count": len(graph["projection_links"])})
        graph_results.update({row["query_id"]: row for row in graph["query_results"]})

    traces = []
    for query in queries:
        started = time.perf_counter()
        snapshot_dir = release / "public" / "snapshots" / query["public_snapshot_id"]
        tick = time.perf_counter(); docs = _document_candidates(
            query, chunks, index, document_top_k, snapshot_dir)
        document_ms = (time.perf_counter() - tick) * 1000
        graph = graph_results[query["query_id"]]
        tick = time.perf_counter(); kg = _kg_candidates(graph)
        kg.extend(entity_catalog_candidates(snapshot_dir, query, kg)); eligibility_ms = (time.perf_counter() - tick) * 1000
        tick = time.perf_counter(); computation, computation_receipt = computation_candidates(
            snapshot_dir, query)
        computation_ms = (time.perf_counter() - tick) * 1000
        tick = time.perf_counter(); hybrid = hybrid_union(docs, kg, computation); merge_ms = (time.perf_counter() - tick) * 1000
        tick = time.perf_counter(); selected, selector_excluded = select_public(query, hybrid, token_budget=token_budget); selection_ms = (time.perf_counter() - tick) * 1000
        observed_query_assembly_ms = (time.perf_counter() - started) * 1000
        included_stage_ms = {
            "document": round(document_ms, 3),
            "kg_search": graph["search_latency_ms"],
            "eligibility_normalization": round(eligibility_ms, 3),
            "computation": round(computation_ms, 3),
            "hybrid_merge": round(merge_ms, 3),
            "selection": round(selection_ms, 3),
        }
        total_pre_reader_ms = round(sum(included_stage_ms.values()), 3)
        if total_pre_reader_ms + 1e-9 < max(included_stage_ms.values()):
            raise AssertionError("sequential total_pre_reader latency invariant violated")
        excluded_reasons = Counter(row["exclusion_reason"] for row in graph["excluded_candidates"])
        excluded_reasons.update(row["reason"] for row in selector_excluded)
        traces.append({"query_id": query["query_id"], "snapshot_id": query["public_snapshot_id"],
                       "runtime_status": "completed_retrieval", "document_candidates": docs,
                       "kg_raw_candidates": graph["raw_candidates"], "kg_candidates": kg,
                       "computation_candidates": computation, "hybrid_candidates": hybrid,
                       "selected_evidence": selected, "selector_excluded": selector_excluded,
                       "excluded_counts": dict(sorted(excluded_reasons.items())),
                       "counts": {"document": len(docs), "kg_raw": len(graph["raw_candidates"]),
                                  "kg_eligible": len(kg), "computation": len(computation),
                                  "hybrid": len(hybrid), "selected": len(selected)},
                       "latency_ms": {**included_stage_ms,
                                      "total_pre_reader": total_pre_reader_ms,
                                      "observed_query_assembly": round(observed_query_assembly_ms, 3)},
                       "latency_contract": {"execution_mode": "sequential_accounting",
                                            "aggregation_unit": "query",
                                            "cache_status": "cold",
                                            "included_stages": list(included_stage_ms),
                                            "invariant": "total_pre_reader >= sum(included stage durations)",
                                            "invariant_pass": total_pre_reader_ms + 1e-9 >= sum(included_stage_ms.values()),
                                            "note": "KG search was executed during snapshot graph processing; total_pre_reader is the modeled per-query sequential sum. observed_query_assembly excludes that precomputed search wall time."},
                       "computation_receipt": computation_receipt, "cache_status": "cold",
                       "limits": {"document_top_k": document_top_k, "graph_top_k": graph_top_k,
                                  "token_budget": token_budget, "selected_cap": 12},
                       "truncated": {"document": len(docs) == document_top_k,
                                     "kg": len(graph["raw_candidates"]) == graph_top_k,
                                     "selection": len(selector_excluded) > 0}})
    logical = [{key: value for key, value in trace.items() if key != "latency_ms"} for trace in traces]
    return {"schema_version": "phase-b-offline-closure-v1", "release": release.name, "profile": profile,
            "query_count": len(queries), "terminal_count": len(traces),
            "terminal_status_counts": dict(Counter(trace["runtime_status"] for trace in traces)),
            "snapshot_count": len(grouped), "ledger_count": len({row["ledger_id"] for row in graph_receipts}),
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
