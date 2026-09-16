"""Utilities shared by Graphiti temporal conformance fixtures.

These helpers deliberately observe Graphiti's native ``add_episode`` behavior.
They do not repair timestamps, add application-side correction logic, or treat
natural-language search output as temporal ground truth.
"""

from __future__ import annotations

import os
import warnings
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from graphiti_core import Graphiti
from graphiti_core.cross_encoder.gemini_reranker_client import GeminiRerankerClient
from graphiti_core.driver.kuzu_driver import KuzuDriver
from graphiti_core.edges import EntityEdge
from graphiti_core.embedder.gemini import GeminiEmbedder, GeminiEmbedderConfig
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.gemini_client import GeminiClient
from graphiti_core.nodes import EntityNode, EpisodicNode

warnings.filterwarnings("ignore", category=DeprecationWarning)

LLM_MODEL = "gemini-2.5-flash"
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 768
BACKEND = "KuzuDriver(:memory:)"


def utc(value: str) -> datetime:
    """Parse an ISO timestamp and normalize it to timezone-aware UTC."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def format_dt(value: datetime | None) -> str | None:
    normalized = normalize_dt(value)
    return normalized.isoformat() if normalized else None


def json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return format_dt(value)
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def resolve_api_key() -> str:
    """Resolve the Gemini key using the same environment layout as the original fixture."""
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]

    candidates = [
        Path(".env"),
        Path("../.env"),
        Path("D:/vinai/Day-3-Lab-Chatbot-vs-react-agent-E402/.env"),
        Path("D:/vinai/P-244/.env"),
    ]
    for candidate in candidates:
        if candidate.exists():
            values = dotenv_values(candidate)
            if values.get("GEMINI_API_KEY"):
                print(f"[Setup] Loaded GEMINI_API_KEY from {candidate}")
                return str(values["GEMINI_API_KEY"])
    raise RuntimeError("GEMINI_API_KEY was not found in the environment or configured .env files")


def runtime_configuration() -> dict[str, Any]:
    return {
        "graphiti_version": version("graphiti-core"),
        "kuzu_version": version("kuzu"),
        "backend": BACKEND,
        "llm_client": "GeminiClient",
        "llm_model": LLM_MODEL,
        "embedder": "GeminiEmbedder",
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dim": EMBEDDING_DIM,
        "reranker": "GeminiRerankerClient",
        "ingestion_mode": "Mode B / Graphiti.add_episode",
    }


async def build_isolated_graphiti() -> tuple[Graphiti, KuzuDriver]:
    """Create a fresh in-memory graph for exactly one fixture."""
    api_key = resolve_api_key()
    llm = GeminiClient(
        config=LLMConfig(api_key=api_key, model=LLM_MODEL, small_model=LLM_MODEL)
    )
    embedder = GeminiEmbedder(
        config=GeminiEmbedderConfig(
            api_key=api_key,
            embedding_model=EMBEDDING_MODEL,
            embedding_dim=EMBEDDING_DIM,
        )
    )
    reranker = GeminiRerankerClient(
        config=LLMConfig(api_key=api_key, model=LLM_MODEL)
    )
    driver = KuzuDriver(db=":memory:")
    # Graphiti 0.30.2 expects this value when applying driver scoping.
    driver._database = ":memory:"
    await driver.graph_ops.build_indices_and_constraints(driver)
    graphiti = Graphiti(
        graph_driver=driver,
        llm_client=llm,
        embedder=embedder,
        cross_encoder=reranker,
    )
    return graphiti, driver


def serialize_episode(episode: EpisodicNode) -> dict[str, Any]:
    return {
        "uuid": episode.uuid,
        "name": episode.name,
        "content": episode.content,
        "source": str(episode.source),
        "source_description": episode.source_description,
        "valid_at": format_dt(episode.valid_at),
        "created_at": format_dt(episode.created_at),
        "entity_edges": list(episode.entity_edges or []),
    }


def serialize_node(node: EntityNode) -> dict[str, Any]:
    return {
        "uuid": node.uuid,
        "name": node.name,
        "labels": list(node.labels or []),
        "summary": node.summary,
    }


def serialize_edge(edge: EntityEdge) -> dict[str, Any]:
    return {
        "uuid": edge.uuid,
        "source_node_uuid": edge.source_node_uuid,
        "target_node_uuid": edge.target_node_uuid,
        "name": edge.name,
        "fact": edge.fact,
        "valid_at": format_dt(edge.valid_at),
        "invalid_at": format_dt(edge.invalid_at),
        "created_at": format_dt(edge.created_at),
        "expired_at": format_dt(edge.expired_at),
        "episodes": list(edge.episodes or []),
        "attributes": json_safe(edge.attributes or {}),
    }


async def collect_graph_state(
    driver: KuzuDriver,
    group_id: str,
    stage: str,
    previous_edge_ids: set[str] | None = None,
) -> dict[str, Any]:
    episodes = await driver.episode_node_ops.get_by_group_ids(driver, [group_id])
    nodes = await driver.entity_node_ops.get_by_group_ids(driver, [group_id])
    edges = await driver.entity_edge_ops.get_by_group_ids(driver, [group_id])
    previous_edge_ids = previous_edge_ids or set()
    serialized_edges = []
    for edge in edges:
        item = serialize_edge(edge)
        item["lifecycle_observation"] = {
            "uuid_status": "reused" if edge.uuid in previous_edge_ids else "new",
            "invalidated": edge.invalid_at is not None,
            "expired": edge.expired_at is not None,
        }
        serialized_edges.append(item)
    return {
        "stage": stage,
        "episode_count": len(episodes),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "episodes": [serialize_episode(item) for item in episodes],
        "nodes": [serialize_node(item) for item in nodes],
        "edges": serialized_edges,
    }


def print_graph_state(state: dict[str, Any]) -> None:
    print("\n" + "=" * 78)
    print(f"GRAPH INSPECTION: {state['stage']}")
    print("=" * 78)
    print(
        f"episodes={state['episode_count']} nodes={state['node_count']} "
        f"edges={state['edge_count']}"
    )
    for episode in state["episodes"]:
        print(
            f"  EP {episode['uuid']} | {episode['name']} | "
            f"valid_at={episode['valid_at']} created_at={episode['created_at']}"
        )
    for node in state["nodes"]:
        print(f"  NODE {node['uuid']} | {node['name']} | labels={node['labels']}")
    for edge in state["edges"]:
        lifecycle = edge["lifecycle_observation"]
        print(
            f"  EDGE {edge['uuid']} | {edge['source_node_uuid']} -> "
            f"{edge['target_node_uuid']} | {edge['name']}"
        )
        print(f"       fact={edge['fact']!r}")
        print(
            "       "
            f"valid_at={edge['valid_at']} invalid_at={edge['invalid_at']} "
            f"created_at={edge['created_at']} expired_at={edge['expired_at']}"
        )
        print(
            f"       episodes={edge['episodes']} lifecycle={lifecycle['uuid_status']}"
            f"/invalidated={lifecycle['invalidated']}/expired={lifecycle['expired']}"
        )


async def ingest_and_inspect(
    graphiti: Graphiti,
    driver: KuzuDriver,
    group_id: str,
    episode_id: str,
    body: str,
    source_description: str,
    reference_time: datetime,
    previous_state: dict[str, Any] | None,
) -> dict[str, Any]:
    before_count = previous_state["edge_count"] if previous_state else 0
    previous_ids = (
        {edge["uuid"] for edge in previous_state["edges"]} if previous_state else set()
    )
    print(
        f"\n[{episode_id}] ingest source={source_description!r} "
        f"reference_time={format_dt(reference_time)}\n  {body}"
    )
    response = await graphiti.add_episode(
        name=episode_id,
        episode_body=body,
        source_description=source_description,
        reference_time=reference_time,
        group_id=group_id,
    )
    state = await collect_graph_state(driver, group_id, f"after {episode_id}", previous_ids)
    state["ingestion"] = {
        "episode_uuid": response.episode.uuid,
        "reference_time_argument": format_dt(reference_time),
        "edge_count_before": before_count,
        "edge_count_after": state["edge_count"],
    }
    print_graph_state(state)
    return state


def node_name_map(state: dict[str, Any]) -> dict[str, str]:
    return {node["uuid"]: node["name"] for node in state["nodes"]}


def is_positive_membership_edge(edge: dict[str, Any], state: dict[str, Any]) -> bool:
    names = node_name_map(state)
    endpoint_text = " ".join(
        [names.get(edge["source_node_uuid"], ""), names.get(edge["target_node_uuid"], "")]
    ).lower()
    text = f"{edge.get('name') or ''} {edge.get('fact') or ''}".lower()
    has_entities = (
        ("person_a" in endpoint_text and "team_b" in endpoint_text)
        or ("person_a" in text and "team_b" in text)
    )
    positive = any(token in text for token in ("join", "member", "belong"))
    negative = any(token in text for token in ("left", "leave", "never", "not_member"))
    return has_entities and positive and not negative


def interval_active(edge: dict[str, Any], at: datetime) -> bool:
    """Evaluate only valid-time fields; expired_at is not silently treated as valid_to."""
    target = normalize_dt(at)
    start = utc(edge["valid_at"]) if edge.get("valid_at") else None
    end = utc(edge["invalid_at"]) if edge.get("invalid_at") else None
    return (start is None or start <= target) and (end is None or target < end)


def membership_state(state: dict[str, Any], at: datetime) -> dict[str, Any]:
    candidates = [edge for edge in state["edges"] if is_positive_membership_edge(edge, state)]
    active = [edge for edge in candidates if interval_active(edge, at)]
    return {
        "at": format_dt(at),
        "is_member_from_valid_interval": bool(active),
        "matching_edge_ids": [edge["uuid"] for edge in candidates],
        "active_edge_ids": [edge["uuid"] for edge in active],
        "note": "expired_at was recorded but not reinterpreted as valid_to",
    }


async def run_searches(
    graphiti: Graphiti,
    group_id: str,
    queries: list[dict[str, str]],
) -> list[dict[str, Any]]:
    output = []
    for query in queries:
        print(f"\n[Search {query['id']}] {query['query']}")
        results = await graphiti.search(query["query"], group_ids=[group_id])
        serialized = [serialize_edge(edge) for edge in results]
        for edge in serialized:
            print(
                f"  {edge['uuid']} | {edge['fact']!r} | valid_at={edge['valid_at']} "
                f"invalid_at={edge['invalid_at']} expired_at={edge['expired_at']}"
            )
        output.append(
            {
                "query_id": query["id"],
                "query": query["query"],
                "result_count": len(serialized),
                "results": serialized,
                "warning": "Raw search candidates are not treated as a temporal answer.",
            }
        )
    return output


def compare_membership(
    state: dict[str, Any], expected: dict[str, bool]
) -> tuple[dict[str, Any], bool]:
    observations: dict[str, Any] = {}
    all_match = True
    for instant, expected_value in expected.items():
        observed = membership_state(state, utc(instant))
        observed["expected"] = expected_value
        observed["matches_oracle"] = observed["is_member_from_valid_interval"] == expected_value
        all_match = all_match and observed["matches_oracle"]
        observations[instant] = observed
    return observations, all_match

