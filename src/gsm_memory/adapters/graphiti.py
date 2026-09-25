"""Graphiti 0.30.2 deterministic Mode A adapter.

Imports are intentionally local to the graphiti extra; normal data/retrieval imports
remain offline and provider-free.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
from graphiti_core.cross_encoder.client import CrossEncoderClient
from graphiti_core.embedder.client import EmbedderClient
from graphiti_core.llm_client.client import LLMClient
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.tracer import NoOpTracer

GRAPH_NAMESPACE = uuid.UUID("5db7404e-4e8c-5a8c-a845-b07069aa6fbb")


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _uuid(kind: str, value: str) -> str:
    return str(uuid.uuid5(GRAPH_NAMESPACE, f"{kind}:{value}"))


class HashEmbedder(EmbedderClient):
    """Deterministic offline probe embedder, not a claimed semantic dense model."""

    dimension = 1024

    async def create(self, input_data: Any) -> list[float]:
        text = input_data[0] if isinstance(input_data, list) else str(input_data)
        vector = [0.0] * self.dimension
        for token in re.findall(r"\w+", text.casefold(), flags=re.UNICODE):
            bucket = int.from_bytes(hashlib.sha256(token.encode()).digest()[:4], "big") % self.dimension
            vector[bucket] += 1.0
        norm = math.sqrt(sum(item * item for item in vector)) or 1.0
        return [item / norm for item in vector]

    async def create_batch(self, inputs: list[str]) -> list[list[float]]:
        return [await self.create(item) for item in inputs]


class LexicalCrossEncoder(CrossEncoderClient):
    async def rank(self, query: str, passages: list[str]) -> list[tuple[str, float]]:
        terms = set(re.findall(r"\w+", query.casefold()))
        scored = [(p, float(len(terms & set(re.findall(r"\w+", p.casefold()))))) for p in passages]
        return sorted(scored, key=lambda row: (-row[1], row[0]))


class OfflineLLM(LLMClient):
    def __init__(self) -> None:
        super().__init__(LLMConfig(model="offline-disabled"))

    async def _generate_response(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("LLM extraction is disabled for deterministic Mode A")


@dataclass(frozen=True)
class GraphProjectionLink:
    source_kind: str
    source_id: str
    runtime_kind: str
    runtime_id: str
    snapshot_id: str


def _object_value(obj: dict[str, Any]) -> Any:
    for key in ("string_value", "integer_value", "boolean_value", "rational_value"):
        if obj.get(key) is not None:
            return obj[key]
    return None


def _eligible(edge: Any, query: dict[str, Any], snapshot: dict[str, Any]) -> tuple[bool, str | None]:
    attrs = edge.attributes
    if edge.group_id != f'{snapshot["scope_id"]}-{snapshot["snapshot_id"]}':
        return False, "wrong_scope"
    entities = set(query.get("entity_refs") or [])
    if entities and edge.source_node_uuid not in entities and edge.target_node_uuid not in entities:
        return False, "entity_mismatch"
    if _dt(attrs["known_at"]) > _dt(query["known_as_of"]):
        return False, "future_known"
    if attrs.get("known_to") and _dt(query["known_as_of"]) >= _dt(attrs["known_to"]):
        return False, "replaced_or_retracted"
    valid = attrs.get("valid_semantics") or {}
    time_scope = query.get("time_scope") or {"mode": "current"}
    mode = time_scope.get("mode")
    if mode == "current":
        return True, None
    requested_start = time_scope.get("valid_at") or time_scope.get("start")
    requested_end = time_scope.get("valid_at") or time_scope.get("end")
    if valid.get("kind") == "point":
        event = valid.get("at") or attrs.get("event_time")
        if not event:
            return False, "missing_event_time"
        event_dt = _dt(event)
        if mode == "point":
            return (event_dt == _dt(requested_start), None if event_dt == _dt(requested_start) else "wrong_valid_time")
        ok = _dt(requested_start) <= event_dt < _dt(requested_end)
        return ok, None if ok else "wrong_valid_window"
    start = valid.get("from")
    end = (valid.get("to") or {}).get("at")
    if not start:
        return True, None
    if mode == "point":
        at = _dt(requested_start)
        ok = _dt(start) <= at and (not end or at < _dt(end))
        return ok, None if ok else "wrong_valid_time"
    ok = _dt(start) < _dt(requested_end) and (not end or _dt(requested_start) < _dt(end))
    return ok, None if ok else "wrong_valid_window"


async def _search_queries(driver: Any, snapshot: dict[str, Any], roundtrip_edges: list[Any],
                          search_queries: list[dict[str, Any]], search_limit: int) -> tuple[list[str], list[dict[str, Any]]]:
    """Search one already-open graph without consulting private evaluation data."""
    if not roundtrip_edges:
        return [], [
            {"query_id": query["query_id"], "raw_candidates": [], "eligible_candidates": [],
             "excluded_candidates": [], "search_latency_ms": 0.0}
            for query in search_queries
        ]
    from graphiti_core.graphiti import GraphitiClients
    from graphiti_core.search.search import search
    from graphiti_core.search.search_config_recipes import EDGE_HYBRID_SEARCH_RRF
    from graphiti_core.search.search_filters import SearchFilters

    graph_group = f'{snapshot["scope_id"]}-{snapshot["snapshot_id"]}'
    embedder = HashEmbedder()
    clients = GraphitiClients(driver=driver, llm_client=OfflineLLM(), embedder=embedder,
                              cross_encoder=LexicalCrossEncoder(), tracer=NoOpTracer())
    probe_config = deepcopy(EDGE_HYBRID_SEARCH_RRF)
    probe_config.limit = 5
    probe = await search(clients, "driver incident policy", [graph_group], probe_config,
                         SearchFilters(), driver=driver)
    search_probe = [edge.uuid for edge in probe.edges[:5]]
    query_results: list[dict[str, Any]] = []
    for query in search_queries:
        tick = __import__("time").perf_counter()
        search_config = deepcopy(EDGE_HYBRID_SEARCH_RRF)
        search_config.limit = search_limit
        found = await search(clients, query["query"], [graph_group], search_config,
                             SearchFilters(), driver=driver)
        candidates: list[tuple[Any, int, list[str]]] = [(edge, 0, []) for edge in found.edges]
        frontier = set(query.get("entity_refs") or [])
        visited_entities = set(frontier)
        for depth in (1, 2):
            next_frontier: set[str] = set()
            for edge in roundtrip_edges:
                if edge.source_node_uuid in frontier or edge.target_node_uuid in frontier:
                    path = sorted(frontier & {edge.source_node_uuid, edge.target_node_uuid})
                    candidates.append((edge, depth, path))
                    next_frontier.update((edge.source_node_uuid, edge.target_node_uuid))
            frontier = next_frontier - visited_entities
            visited_entities.update(next_frontier)
        unique: dict[str, tuple[Any, int, list[str]]] = {}
        for edge, depth, path in candidates:
            if edge.uuid not in unique or depth < unique[edge.uuid][1]:
                unique[edge.uuid] = (edge, depth, path)
        rows = []
        ordered = sorted(unique.values(), key=lambda item: (item[1], item[0].uuid))[:80]
        for rank, (edge, depth, path) in enumerate(ordered, 1):
            eligibility_query = query if depth == 0 else {**query, "entity_refs": []}
            eligible, exclusion = _eligible(edge, eligibility_query, snapshot)
            rows.append({"graph_object_id": edge.uuid, "assertion_id": edge.uuid,
                         "record_id": edge.attributes.get("record_id"), "source_id": edge.attributes.get("source_id"),
                         "predicate": edge.name, "fact": edge.fact, "subject_id": edge.source_node_uuid,
                         "object_id": edge.target_node_uuid, "valid": edge.attributes.get("valid_semantics"),
                         "known_at": edge.attributes.get("known_at"), "snapshot_id": snapshot["snapshot_id"],
                         "ledger_id": snapshot["ledger_id"], "scope_id": snapshot["scope_id"],
                         "raw_rank": rank, "raw_score": float(search_limit - rank + 1),
                         "eligibility": "eligible" if eligible else "excluded", "exclusion_reason": exclusion,
                         "expansion_depth": depth, "expansion_path": path,
                         "source_locator": {"locator_type": "ledger_assertion",
                                            "public_snapshot_id": snapshot["snapshot_id"],
                                            "record_id": edge.attributes.get("record_id"),
                                            "assertion_id": edge.uuid,
                                            "source_id": edge.attributes.get("source_id")}})
        query_results.append({"query_id": query["query_id"], "raw_candidates": rows,
                              "eligible_candidates": [row for row in rows if row["eligibility"] == "eligible"],
                              "excluded_candidates": [row for row in rows if row["eligibility"] != "eligible"],
                              "search_latency_ms": round((__import__("time").perf_counter() - tick) * 1000, 3)})
    return search_probe, query_results


async def construct_mode_a(snapshot_dir: Path, database: str = ":memory:",
                           search_queries: list[dict[str, Any]] | None = None,
                           search_limit: int = 40) -> dict[str, Any]:
    """Write one public snapshot through Graphiti's supported node/edge APIs."""
    started = __import__("time").perf_counter()
    from graphiti_core.driver.kuzu_driver import KuzuDriver
    from graphiti_core.edges import EntityEdge
    from graphiti_core.nodes import EntityNode, EpisodeType, EpisodicNode

    snapshot = json.loads((snapshot_dir / "manifest.json").read_text("utf-8"))
    snapshot_id = snapshot["snapshot_id"]
    graph_group = f'{snapshot["scope_id"]}-{snapshot_id}'
    records = pq.read_table(snapshot_dir / "record_ledger.parquet").to_pylist()
    known_to_by_assertion = {target: record["known_at"] for record in records
                             for target in record["target_assertion_ids"]}
    driver = KuzuDriver(database)
    await driver.graph_ops.build_indices_and_constraints(driver)
    embedder = HashEmbedder()
    nodes: set[str] = set()
    edges: set[str] = set()
    episodes: set[str] = set()
    links: list[GraphProjectionLink] = []

    async def save_node(node_id: str, name: str, kind: str, group: str, created: datetime, attrs: dict[str, Any]) -> None:
        if node_id in nodes:
            return
        node = EntityNode(uuid=node_id, name=name, group_id=group, labels=[kind], created_at=created,
                          name_embedding=await embedder.create(name), summary=kind, attributes=attrs)
        await node.save(driver)
        nodes.add(node_id)

    for record in sorted(records, key=lambda row: row["commit_seq"]):
        known = _dt(record["known_at"])
        group = graph_group
        episode_id = record["record_id"]
        episode = EpisodicNode(uuid=episode_id, name=f'record:{episode_id}', group_id=group,
                               created_at=known, source=EpisodeType.json,
                               source_description=record["source_id"], content=json.dumps(record, ensure_ascii=False, sort_keys=True, default=str),
                               valid_at=known, entity_edges=[], episode_metadata={"operation": record["operation"]})
        await episode.save(driver)
        episodes.add(episode_id)
        links.append(GraphProjectionLink("record", episode_id, "episode", episode_id, snapshot_id))
        for assertion in record["assertions"]:
            subject = assertion["subject_id"]
            value = _object_value(assertion["object"])
            target = value if assertion["object"]["type"] == "entity_ref" else _uuid("value", json.dumps(value, sort_keys=True))
            await save_node(subject, subject, "Entity", group, known, {"canonical_id": subject})
            await save_node(str(target), str(value), "Value" if target != value else "Entity", group, known, {"canonical_value": value, "value_type": assertion["object"]["type"]})
            valid = assertion["valid"]
            valid_value = valid.get("at") or valid.get("from")
            # Graphiti requires a datetime; preserve unknown/atemporal semantics in
            # attributes and use the public record's known time as storage anchor.
            valid_at = _dt(valid_value) if valid_value else known
            invalid_at = _dt(valid["to"]["at"]) if valid.get("to") and valid["to"].get("at") else None
            fact = f'{subject} {assertion["predicate"]} {value}'
            edge = EntityEdge(uuid=assertion["assertion_id"], group_id=group, source_node_uuid=subject,
                              target_node_uuid=str(target), created_at=known, name=assertion["predicate"], fact=fact,
                              fact_embedding=await embedder.create(fact), episodes=[episode_id], valid_at=valid_at,
                              invalid_at=invalid_at,
                              expired_at=_dt(known_to_by_assertion[assertion["assertion_id"]])
                              if assertion["assertion_id"] in known_to_by_assertion else None,
                              reference_time=known,
                              attributes={"record_id": episode_id, "source_id": record["source_id"], "known_at": record["known_at"],
                                          "operation": record["operation"], "logical_fact_id": assertion["logical_fact_id"],
                                          "known_to": known_to_by_assertion.get(assertion["assertion_id"]),
                                          "event_time": assertion.get("event_time"), "target_assertion_ids": record["target_assertion_ids"],
                                          "valid_semantics": valid,
                                          "qualifiers": assertion["qualifiers"], "source_refs": assertion["source_refs"]})
            await edge.save(driver)
            edges.add(edge.uuid)
            links.append(GraphProjectionLink("assertion", edge.uuid, "entity_edge", edge.uuid, snapshot_id))

    roundtrip_nodes = await EntityNode.get_by_group_ids(driver, [graph_group])
    roundtrip_edges = await EntityEdge.get_by_group_ids(driver, [graph_group])
    before = (len(roundtrip_nodes), len(roundtrip_edges))
    # Repeat a representative write to prove UUID-based idempotency.
    if records and records[0]["assertions"]:
        probe = await EntityEdge.get_by_uuid(driver, records[0]["assertions"][0]["assertion_id"])
        await probe.save(driver)
    after = (len(await EntityNode.get_by_group_ids(driver, [graph_group])),
             len(await EntityEdge.get_by_group_ids(driver, [graph_group])))
    try:
        wrong_scope_count = len(await EntityEdge.get_by_group_ids(driver, ["out-of-scope"]))
    except Exception as error:
        if error.__class__.__name__ != "GroupsEdgesNotFoundError":
            raise
        wrong_scope_count = 0
    search_probe, query_results = await _search_queries(
        driver, snapshot, roundtrip_edges, search_queries or [], search_limit
    )
    await driver.close()
    assertions = [assertion for record in records for assertion in record["assertions"]]
    endpoint_pairs: dict[tuple[str, str], int] = {}
    for assertion in assertions:
        value = _object_value(assertion["object"])
        pair = (assertion["subject_id"], str(value))
        endpoint_pairs[pair] = endpoint_pairs.get(pair, 0) + 1
    return {
        "status": "pass",
        "construction_ms": round((__import__("time").perf_counter() - started) * 1000, 3),
        "backend": "kuzu",
        "snapshot_id": snapshot_id,
        "records": len(records), "nodes": len(nodes), "edges": len(edges), "episodes": len(episodes),
        "projection_links": [asdict(link) for link in links],
        "repeat_write_counts_before": before, "repeat_write_counts_after": after,
        "repeat_write_idempotent": before == after,
        "indexed_search_result_ids": search_probe,
        "indexed_search_executed": True,
        "query_results": query_results,
        "capability_matrix": {
            "custom_attributes_roundtrip": all(edge.attributes.get("record_id") and edge.attributes.get("source_id") for edge in roundtrip_edges),
            "source_lineage_edges": sum(bool(edge.attributes.get("source_id")) for edge in roundtrip_edges),
            "interval_assertions": sum(a["valid"]["kind"] == "interval" for a in assertions),
            "point_assertions": sum(a["valid"]["kind"] == "point" for a in assertions),
            "parallel_endpoint_groups": sum(count > 1 for count in endpoint_pairs.values()),
            "replace_records": sum(record["operation"] == "replace" for record in records),
            "retract_records": sum(record["operation"] == "retract" for record in records),
            "wrong_scope_result_count": wrong_scope_count
        },
        "embedding_notice": "offline hash embedder used only for capability/index plumbing; not a dense semantic baseline",
    }
