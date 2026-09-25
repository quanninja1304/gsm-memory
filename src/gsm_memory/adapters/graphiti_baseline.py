"""Minimal persistent Neo4j baseline using Graphiti's native public API."""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from gsm_memory.retrieval.documents import read_jsonl

LLM_MODEL = "gpt-5.5"
EMBEDDING_MODEL = "text-embedding-3-small"
RERANKER_MODEL = "gpt-4.1-nano"
INPUT_FORMAT_VERSION = "readable_v2"

EXTRACTION_INSTRUCTIONS = """
Extract only facts explicitly stated in this public ledger episode.
Treat a subject or object written as '[id=...]' as an entity; keep the canonical
ID in its name so same-name people remain distinct. Treat the stated predicate
as the relationship between the subject and object. A VALUE written with an
'[id=value:...]' marker is an explicit target entity, not metadata. Extract
exactly one relationship for every line beginning with 'Bộ ba bắt buộc',
including literal-valued predicates such as REPORTED_MEASURE, DRIVER_STATUS,
and ARTIFACT_PUBLICATION. Use the predicate shown between '--' and '-->' as the
relationship name. Preserve operation, source, known time, valid time, event
time, qualifiers, and revision targets in the fact.
Record/assertion/source IDs used only as provenance are not separate entities.
Do not infer a fact, identity, correction, or temporal interval that is absent.
""".strip()


def _datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _group_id(dataset_version: str, snapshot_id: str) -> str:
    safe_version = dataset_version.replace(".", "_").replace("-", "_")
    return f"{safe_version}_{INPUT_FORMAT_VERSION}_{snapshot_id}"


def _entity_reference(entity_id: str, entities: dict[str, dict[str, Any]]) -> str:
    entity = entities.get(entity_id)
    if entity is None:
        return f"đối tượng công khai [id={entity_id}]"
    display_name = (entity.get("name") or {}).get("text") or "không có tên"
    entity_type = entity.get("entity_type", "ENTITY")
    semantic_code = entity.get("semantic_code")
    code = f", mã={semantic_code}" if semantic_code else ""
    return f'{entity_type} "{display_name}" [id={entity_id}{code}]'


def _literal_value_text(value: dict[str, Any]) -> str:
    value_type = value.get("type")
    raw_value = value.get("value")
    if value_type == "rational" and isinstance(raw_value, dict):
        return f'{raw_value.get("n")}/{raw_value.get("d")}'
    if isinstance(raw_value, str):
        return raw_value
    return json.dumps(raw_value, ensure_ascii=False, sort_keys=True)


def _object_text(
    value: dict[str, Any],
    entities: dict[str, dict[str, Any]],
    *,
    predicate: str,
    assertion_id: str,
) -> str:
    value_type = value.get("type")
    raw_value = value.get("value")
    if value_type == "entity_ref":
        return _entity_reference(str(raw_value), entities)
    display_value = _literal_value_text(value)
    return (
        f'VALUE "{predicate} = {display_value}" '
        f'[id=value:{assertion_id}, type={value_type}]'
    )


def _valid_time_text(valid: dict[str, Any]) -> str:
    if valid.get("kind") == "point":
        return f'điểm thời gian {valid.get("at")}'
    if valid.get("kind") == "interval":
        end = valid.get("to")
        if isinstance(end, dict) and end.get("kind") == "unbounded":
            end_text = "không giới hạn"
        else:
            end_text = str(end)
        return f'khoảng [{valid.get("from")}, {end_text})'
    return json.dumps(valid, ensure_ascii=False, sort_keys=True)


def render_graphiti_episode(
    record: dict[str, Any],
    entities: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
) -> str:
    """Render public Mode B data into deterministic, extraction-friendly text."""
    source_id = record["source_id"]
    source = sources.get(source_id, {})
    source_label = source.get("alias") or source.get("source_kind") or "unknown"
    lines = [
        "Bản ghi sổ cái công khai.",
        f'Mã bản ghi: {record["record_id"]}.',
        f'Nguồn: {source_label} [source_id={source_id}].',
        f'Thời điểm hệ thống biết bản ghi: {record["known_at"]}.',
        f'Thao tác: {record["operation"]}.',
    ]
    targets = record.get("target_assertion_ids") or []
    if targets:
        lines.append(
            "Các khẳng định bị thao tác này nhắm tới: " + ", ".join(targets) + "."
        )
    for index, assertion in enumerate(record.get("assertions") or [], start=1):
        subject = _entity_reference(assertion["subject_id"], entities)
        object_text = _object_text(
            assertion["object"],
            entities,
            predicate=assertion["predicate"],
            assertion_id=assertion["assertion_id"],
        )
        lines.extend([
            f'Khẳng định {index} [assertion_id={assertion["assertion_id"]}]:',
            f'Bộ ba bắt buộc: {subject} --{assertion["predicate"]}--> {object_text}.',
            f'- Chủ thể: {subject}.',
            f'- Quan hệ/vị từ: {assertion["predicate"]}.',
            f'- Đối tượng/giá trị: {object_text}.',
            f'- Thời gian hiệu lực: {_valid_time_text(assertion["valid"])}.',
            f'- Thời gian sự kiện: {assertion.get("event_time") or "không được khai báo"}.',
            "- Thuộc tính bổ sung: "
            + json.dumps(assertion.get("qualifiers") or {}, ensure_ascii=False, sort_keys=True)
            + ".",
        ])
        source_refs = assertion.get("source_refs") or []
        if source_refs:
            rendered_refs = [
                ref
                if isinstance(ref, str)
                else json.dumps(ref, ensure_ascii=False, sort_keys=True)
                for ref in source_refs
            ]
            lines.append("- Tham chiếu nguồn: " + ", ".join(rendered_refs) + ".")
    return "\n".join(lines)


def render_graphiti_query(
    query: dict[str, Any], entities: dict[str, dict[str, Any]]
) -> str:
    """Add only public structured request context to the natural-language query."""
    lines = [query["query"]]
    entity_refs = query.get("entity_refs") or []
    if entity_refs:
        lines.append(
            "Thực thể do yêu cầu chỉ định: "
            + "; ".join(_entity_reference(entity_id, entities) for entity_id in entity_refs)
            + "."
        )
    lines.append(f'Thời điểm được phép biết đến: {query["known_as_of"]}.')
    time_scope = query.get("time_scope")
    if time_scope:
        lines.append(
            "Phạm vi thời gian yêu cầu: "
            + json.dumps(time_scope, ensure_ascii=False, sort_keys=True)
            + "."
        )
    source_refs = (query.get("application_context") or {}).get("source_snapshot_refs") or []
    if source_refs:
        lines.append("Ấn bản nguồn được yêu cầu: " + ", ".join(source_refs) + ".")
    return "\n".join(lines)


def _public_file(release: Path, relative_path: str) -> Path:
    public = (release / "public").resolve()
    path = (release / relative_path).resolve()
    try:
        path.relative_to(public)
    except ValueError as error:
        raise ValueError(f"Mode B path is outside the public release: {relative_path}") from error
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def load_baseline_inputs(
    release: Path,
    *,
    snapshot_id: str | None = None,
    max_episodes: int | None = None,
    max_queries: int | None = None,
) -> list[dict[str, Any]]:
    """Load public queries and the Mode B observations routed to them."""
    if max_episodes is not None and max_episodes < 1:
        raise ValueError("max_episodes must be positive")
    if max_queries is not None and max_queries < 1:
        raise ValueError("max_queries must be positive")

    queries = read_jsonl(release / "public" / "runtime_queries" / "dev.jsonl")
    if snapshot_id:
        queries = [row for row in queries if row["public_snapshot_id"] == snapshot_id]
        if not queries:
            raise ValueError(f"snapshot has no development queries: {snapshot_id}")
    if max_queries is not None:
        queries = queries[:max_queries]

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for query in queries:
        grouped[query["public_snapshot_id"]].append(query)

    inputs = []
    for routed_snapshot_id in sorted(grouped):
        manifest_path = release / "public" / "graph_inputs" / "mode_b" / f"{routed_snapshot_id}.json"
        manifest = json.loads(manifest_path.read_text("utf-8"))
        if manifest.get("mode") != "B" or manifest.get("snapshot_id") != routed_snapshot_id:
            raise ValueError(f"invalid Mode B manifest: {manifest_path}")
        observations_path = _public_file(release, manifest["text_observations"])
        snapshot_dir = observations_path.parent
        entity_rows = read_jsonl(snapshot_dir / "entity_catalog.jsonl")
        source_rows = read_jsonl(snapshot_dir / "source_registry.jsonl")
        entities = {row["entity_id"]: row for row in entity_rows}
        sources = {row["source_id"]: row for row in source_rows}
        all_observations = sorted(
            read_jsonl(observations_path), key=lambda row: row["commit_seq"]
        )
        observations = (
            all_observations[:max_episodes]
            if max_episodes is not None
            else all_observations
        )
        inputs.append({
            "snapshot_id": routed_snapshot_id,
            "group_id": _group_id(release.name, routed_snapshot_id),
            "observations_path": observations_path,
            "observations": observations,
            "all_record_ids": [row["record_id"] for row in all_observations],
            "available_episode_count": len(all_observations),
            "entities": entities,
            "sources": sources,
            "queries": grouped[routed_snapshot_id],
        })
    return inputs


def _neo4j_settings() -> dict[str, str]:
    uri = os.getenv("NEO4J_URI")
    password = os.getenv("NEO4J_PASSWORD")
    if not uri:
        raise RuntimeError("NEO4J_URI is required")
    if not password:
        raise RuntimeError("NEO4J_PASSWORD is required")
    return {
        "uri": uri,
        "user": os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME", "neo4j"),
        "password": password,
        "database": os.getenv("NEO4J_DATABASE", "neo4j"),
    }


def _build_graphiti(api_key: str, settings: dict[str, str]) -> Any:
    from graphiti_core import Graphiti
    from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
    from graphiti_core.driver.neo4j_driver import Neo4jDriver
    from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
    from graphiti_core.llm_client.config import LLMConfig
    from graphiti_core.llm_client.openai_client import OpenAIClient

    driver = Neo4jDriver(**settings)
    llm = OpenAIClient(config=LLMConfig(api_key=api_key))
    embedder = OpenAIEmbedder(config=OpenAIEmbedderConfig(api_key=api_key))
    reranker = OpenAIRerankerClient(config=LLMConfig(api_key=api_key))
    return Graphiti(
        graph_driver=driver,
        llm_client=llm,
        embedder=embedder,
        cross_encoder=reranker,
    )


async def _episodes_by_group(graphiti: Any, group_id: str) -> list[Any]:
    from graphiti_core.nodes import EpisodicNode

    try:
        return await EpisodicNode.get_by_group_ids(graphiti.driver, [group_id])
    except Exception as error:
        if error.__class__.__name__ != "GroupsEpisodesNotFoundError":
            raise
        return []


async def _prepare_database(graphiti: Any) -> None:
    """Wait for Neo4jDriver's one index-initialization task."""
    init_task = getattr(graphiti.driver, "_init_task", None)
    if init_task is not None:
        await init_task
    else:
        await graphiti.build_indices_and_constraints()


def _resume_position(
    expected_record_ids: list[str],
    existing_episodes: list[Any],
    allowed_record_ids: list[str] | None = None,
) -> int:
    """Accept an empty, complete, or exact-prefix group; reject mixed state."""
    existing_names = {episode.name for episode in existing_episodes}
    if not existing_names:
        return 0
    if len(existing_names) != len(existing_episodes):
        raise RuntimeError("Neo4j group contains duplicate episode names")
    allowed = set(allowed_record_ids or expected_record_ids)
    if not existing_names.issubset(allowed):
        raise RuntimeError("Neo4j group contains episodes outside the public Mode B input")
    if set(expected_record_ids).issubset(existing_names):
        return len(expected_record_ids)
    prefix = set(expected_record_ids[:len(existing_names)])
    if existing_names != prefix:
        raise RuntimeError(
            "Neo4j group is not an exact prefix of the public Mode B input; "
            "use a clean database or remove the affected group explicitly"
        )
    return len(existing_names)


async def ingest_graphiti_baseline(
    release: Path,
    *,
    snapshot_id: str | None = None,
    max_episodes: int | None = None,
) -> dict[str, Any]:
    """Incrementally ingest public Mode B episodes into persistent Neo4j."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for Graphiti ingestion")
    settings = _neo4j_settings()
    inputs = load_baseline_inputs(
        release, snapshot_id=snapshot_id, max_episodes=max_episodes
    )
    graphiti = _build_graphiti(api_key, settings)
    receipts = []
    try:
        await _prepare_database(graphiti)
        from graphiti_core.nodes import EpisodeType

        for item in inputs:
            expected_ids = [row["record_id"] for row in item["observations"]]
            existing = await _episodes_by_group(graphiti, item["group_id"])
            resume_at = _resume_position(
                expected_ids, existing, item["all_record_ids"]
            )
            started = time.perf_counter()
            for record in item["observations"][resume_at:]:
                await graphiti.add_episode(
                    name=record["record_id"],
                    episode_body=render_graphiti_episode(
                        record, item["entities"], item["sources"]
                    ),
                    source_description=record["source_id"],
                    reference_time=_datetime(record["known_at"]),
                    source=EpisodeType.text,
                    group_id=item["group_id"],
                    custom_extraction_instructions=EXTRACTION_INSTRUCTIONS,
                )
            receipts.append({
                "snapshot_id": item["snapshot_id"],
                "group_id": item["group_id"],
                "existing_episode_count": len(existing),
                "ingested_episode_count": len(item["observations"]) - resume_at,
                "target_episode_count": len(item["observations"]),
                "final_episode_count": max(len(existing), len(item["observations"])),
                "available_episode_count": item["available_episode_count"],
                "ingestion_ms": round((time.perf_counter() - started) * 1000, 3),
            })
    finally:
        await graphiti.close()

    partial = bool(snapshot_id or max_episodes is not None)
    return {
        "schema_version": "graphiti-native-ingestion-v1",
        "dataset_version": release.name,
        "status": "partial" if partial else "completed",
        "provider": "openai",
        "backend": "neo4j",
        "database": settings["database"],
        "input_format_version": INPUT_FORMAT_VERSION,
        "snapshot_count": len(inputs),
        "receipts": receipts,
        "operation_counts": {
            "add_episode": sum(row["ingested_episode_count"] for row in receipts),
        },
        "provider_usage": {
            "calls": None,
            "tokens": None,
            "cost": None,
            "reason": "Graphiti client does not expose aggregate usage in this baseline",
        },
    }


def _candidate(
    edge: Any,
    rank: int,
    episode_to_record_id: dict[str, str],
    records: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    record_ids = [
        episode_to_record_id[episode_id]
        for episode_id in (edge.episodes or [])
        if episode_id in episode_to_record_id
    ]
    assertions = [
        assertion
        for record_id in record_ids
        for assertion in records[record_id].get("assertions", [])
    ]
    assertion_ids = sorted({row["assertion_id"] for row in assertions})
    exact_assertion_ids = assertion_ids if len(assertion_ids) == 1 else []
    source_ids = sorted({records[record_id]["source_id"] for record_id in record_ids})
    return {
        "evidence_id": edge.uuid,
        "source_kind": "kg",
        "content": edge.fact,
        "rank": rank,
        "score": None,
        "source_id": source_ids[0] if len(source_ids) == 1 else None,
        "source_locator": {
            "locator_type": "ledger_assertion",
            "record_id": record_ids[0] if len(record_ids) == 1 else None,
            "record_ids": record_ids,
            "assertion_id": exact_assertion_ids[0] if exact_assertion_ids else None,
            "member_assertion_ids": exact_assertion_ids,
            "source_ids": source_ids,
            "lineage_status": (
                "exact_single_assertion" if exact_assertion_ids else "ambiguous_or_missing"
            ),
        },
        "graphiti": {
            "edge_id": edge.uuid,
            "name": edge.name,
            "source_node_id": edge.source_node_uuid,
            "target_node_id": edge.target_node_uuid,
            "episode_ids": list(edge.episodes or []),
        },
    }


async def search_graphiti_baseline(
    release: Path,
    *,
    snapshot_id: str | None = None,
    max_queries: int | None = None,
    search_limit: int = 10,
    allow_partial: bool = False,
) -> dict[str, Any]:
    """Search an existing Neo4j baseline without ingesting or repairing it."""
    if search_limit < 1:
        raise ValueError("search_limit must be positive")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for Graphiti search")
    settings = _neo4j_settings()
    inputs = load_baseline_inputs(
        release, snapshot_id=snapshot_id, max_queries=max_queries
    )
    graphiti = _build_graphiti(api_key, settings)
    traces: list[dict[str, Any]] = []
    receipts = []
    try:
        await _prepare_database(graphiti)
        for item in inputs:
            episodes = await _episodes_by_group(graphiti, item["group_id"])
            expected = {row["record_id"] for row in item["observations"]}
            episode_to_record_id = {
                episode.uuid: episode.name
                for episode in episodes
                if episode.name in expected
            }
            present = set(episode_to_record_id.values())
            if not episodes:
                raise RuntimeError(
                    f'Neo4j group is not ingested: {item["group_id"]}'
                )
            if not allow_partial and present != expected:
                raise RuntimeError(
                    f'Neo4j group is incomplete: {item["group_id"]}; '
                    f"expected={len(expected)} actual={len(present)}"
                )
            records = {
                row["record_id"]: row
                for row in item["observations"]
                if row["record_id"] in present
            }
            receipts.append({
                "snapshot_id": item["snapshot_id"],
                "group_id": item["group_id"],
                "episode_count": len(present),
                "expected_episode_count": len(expected),
                "complete": present == expected,
            })
            for query in item["queries"]:
                started = time.perf_counter()
                edges = await graphiti.search(
                    render_graphiti_query(query, item["entities"]),
                    group_ids=[item["group_id"]],
                    num_results=search_limit,
                )
                traces.append({
                    "query_id": query["query_id"],
                    "snapshot_id": item["snapshot_id"],
                    "runtime_status": "completed_retrieval",
                    "candidates": [
                        _candidate(edge, rank, episode_to_record_id, records)
                        for rank, edge in enumerate(edges, start=1)
                    ],
                    "search_latency_ms": round((time.perf_counter() - started) * 1000, 3),
                })
    finally:
        await graphiti.close()

    planned_queries = len(read_jsonl(release / "public" / "runtime_queries" / "dev.jsonl"))
    partial = bool(snapshot_id or max_queries is not None or allow_partial)
    return {
        "schema_version": "graphiti-native-baseline-v1",
        "dataset_version": release.name,
        "status": "partial" if partial else "completed",
        "provider": "openai",
        "graphiti_mode": "native_add_episode_and_search",
        "backend": "neo4j",
        "database": settings["database"],
        "input_format_version": INPUT_FORMAT_VERSION,
        "models": {
            "llm": LLM_MODEL,
            "embedding": EMBEDDING_MODEL,
            "reranker": RERANKER_MODEL,
        },
        "limits": {
            "snapshot_id": snapshot_id,
            "max_queries": max_queries,
            "search_limit": search_limit,
            "allow_partial": allow_partial,
        },
        "planned_query_count": planned_queries,
        "query_count": len(traces),
        "snapshot_count": len(inputs),
        "graph_receipts": receipts,
        "operation_counts": {"search": len(traces)},
        "provider_usage": {
            "calls": None,
            "tokens": None,
            "cost": None,
            "reason": "Graphiti client does not expose aggregate usage in this baseline",
        },
        "traces": traces,
    }
