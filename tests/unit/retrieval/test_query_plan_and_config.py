"""Unit tests for P0: QueryPlan contract, Pydantic extra='forbid' validation,

public snapshot routing, and RetrievalConfig versioning.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from gsm_memory.retrieval.config import RetrievalConfig
from gsm_memory.retrieval.query_analysis import (
    ComputationFilters,
    DocumentFilters,
    GraphFilters,
    QueryPlan,
    analyze_query,
    parse_query_llm,
    parse_query_rule_based,
)
from gsm_memory.retrieval.routing import (
    DEFAULT_PUBLIC_BASELINE_SNAPSHOT,
    PublicRoutingViolationError,
    SnapshotNotFoundError,
    resolve_public_snapshot_id,
    validate_public_path_safety,
)


RELEASE_DIR = Path("data/gsm-dev-core-0.2.2")


# ==============================================================================
# 1. TEST PYDANTIC SCHEMA: EXTRA='FORBID' AND TYPE INTEGRITY
# ==============================================================================

def test_query_plan_valid_construction():
    """Verify that a well-formed QueryPlan passes validation."""
    data = {
        "intent": "POLICY_LOOKUP",
        "modalities": ["document"],
        "entity_mentions": ["DRV-001"],
        "entity_refs": ["99e70ebe-18cd-57a3-a036-cf0ff1989861"],
        "time_scope": {"mode": "current"},
        "known_as_of": "2026-09-17T12:00:00Z",
        "public_snapshot_id": "d4cc0438-d831-541a-8123-ddda94ccdac8",
        "document_filters": {
            "pinned_documents": ["P154"],
            "target_topics": ["Kim Cương"],
            "sub_query": "Tiêu chuẩn Kim Cương",
        },
        "graph_filters": {
            "target_predicates": ["TRIP_OUTCOME"],
            "attribute_conditions": {"status": "cancelled"},
            "edge_search_text": "xe hỏng",
        },
        "computation_filters": {
            "target_metric": "cancel_rate_30d",
            "threshold_rule": "diamond_tier",
        },
        "seed_top_k": 3,
        "max_hops": 2,
        "max_nodes": 20,
        "max_edges": 30,
        "document_top_k": 10,
    }
    plan = QueryPlan.model_validate(data)
    assert plan.intent == "POLICY_LOOKUP"
    assert plan.modalities == ["document"]
    assert plan.is_fallback is False
    assert plan.fallback_reason is None


def test_query_plan_rejects_extra_root_keys():
    """Pydantic with extra='forbid' must reject unexpected extra keys."""
    data = {
        "intent": "POLICY_LOOKUP",
        "modalities": ["document"],
        "public_snapshot_id": "snap-01",
        "hallucinated_explanation": "This query asks about rules...",
    }
    with pytest.raises(ValidationError) as exc_info:
        QueryPlan.model_validate(data)
    assert "hallucinated_explanation" in str(exc_info.value)
    assert "extra_forbidden" in str(exc_info.value)


def test_query_plan_rejects_extra_submodel_keys():
    """Pydantic must reject unexpected extra keys inside nested filter sub-models."""
    # Extra key inside document_filters
    data = {
        "intent": "POLICY_LOOKUP",
        "modalities": ["document"],
        "public_snapshot_id": "snap-01",
        "document_filters": {
            "pinned_documents": ["P154"],
            "unapproved_clause": 123,
        },
    }
    with pytest.raises(ValidationError) as exc_info:
        QueryPlan.model_validate(data)
    assert "unapproved_clause" in str(exc_info.value)

    # Extra key inside graph_filters
    data_graph = {
        "intent": "DRIVER_HISTORY",
        "modalities": ["kg"],
        "public_snapshot_id": "snap-01",
        "graph_filters": {
            "unapproved_graph_option": True,
        },
    }
    with pytest.raises(ValidationError) as exc_info:
        QueryPlan.model_validate(data_graph)
    assert "unapproved_graph_option" in str(exc_info.value)


def test_query_plan_rejects_invalid_types():
    """Verify that invalid enum intents or wrong types raise ValidationError."""
    # Invalid intent string
    with pytest.raises(ValidationError):
        QueryPlan.model_validate({
            "intent": "FREEFORM_CHAT",
            "modalities": ["document"],
            "public_snapshot_id": "snap-01",
        })

    # Invalid modality
    with pytest.raises(ValidationError):
        QueryPlan.model_validate({
            "intent": "POLICY_LOOKUP",
            "modalities": ["unsupported_modality"],
            "public_snapshot_id": "snap-01",
        })

    # Invalid integer budget type
    with pytest.raises(ValidationError):
        QueryPlan.model_validate({
            "intent": "POLICY_LOOKUP",
            "modalities": ["document"],
            "public_snapshot_id": "snap-01",
            "seed_top_k": "three_seeds",
        })


# ==============================================================================
# 2. TEST LLM FALLBACK: ERROR RECOVERY & TRACE RECORDING
# ==============================================================================

class MockProviderSuccess:
    """Simulates LLM returning a valid QueryPlan JSON."""
    def complete(self, *, system_prompt: str, user_prompt: str, response_schema: dict) -> str:
        return json.dumps({
            "intent": "POLICY_LOOKUP",
            "modalities": ["document"],
            "entity_mentions": [],
            "entity_refs": [],
            "time_scope": {"mode": "current"},
            "public_snapshot_id": "d4cc0438-d831-541a-8123-ddda94ccdac8",
            "document_filters": {
                "pinned_documents": ["P154"],
                "target_topics": ["Kim Cương"],
                "sub_query": "quy chế P154",
            },
            "graph_filters": {
                "target_predicates": [],
                "attribute_conditions": {},
                "edge_search_text": "",
            },
            "computation_filters": {
                "target_metric": None,
                "threshold_rule": None,
            },
            "seed_top_k": 3,
            "max_hops": 2,
            "max_nodes": 20,
            "max_edges": 30,
            "document_top_k": 10,
        })


class MockProviderExtraKeys:
    """Simulates LLM returning extra hallucinated fields (triggers extra='forbid')."""
    def complete(self, *, system_prompt: str, user_prompt: str, response_schema: dict) -> str:
        return json.dumps({
            "intent": "POLICY_LOOKUP",
            "modalities": ["document"],
            "public_snapshot_id": "d4cc0438-d831-541a-8123-ddda94ccdac8",
            "extra_analysis": "I think the user wants to see driver tiers.",
            "unapproved_score": 0.99,
        })


class MockProviderWrongType:
    """Simulates LLM returning wrong types."""
    def complete(self, *, system_prompt: str, user_prompt: str, response_schema: dict) -> str:
        return json.dumps({
            "intent": "UNKNOWN_INTENT_TYPE",
            "modalities": ["document"],
            "public_snapshot_id": "d4cc0438-d831-541a-8123-ddda94ccdac8",
        })


class MockProviderBrokenJSON:
    """Simulates LLM outputting malformed non-JSON."""
    def complete(self, *, system_prompt: str, user_prompt: str, response_schema: dict) -> str:
        return "I am an AI, here is the answer: ```json {intent: 'POLICY_LOOKUP' "


class MockProviderNetworkError:
    """Simulates provider raising a connection or timeout error."""
    def complete(self, *, system_prompt: str, user_prompt: str, response_schema: dict) -> str:
        raise ConnectionError("Connection refused by provider API")


def test_llm_parser_success():
    query = {
        "query_id": "q-01",
        "query": "Theo quy chế P154, quy định hạng Kim Cương như thế nào?",
        "public_snapshot_id": "d4cc0438-d831-541a-8123-ddda94ccdac8",
    }
    plan = parse_query_llm(query, MockProviderSuccess(), release_dir=RELEASE_DIR)
    assert plan.is_fallback is False
    assert plan.fallback_reason is None
    assert plan.intent == "POLICY_LOOKUP"
    assert plan.trace["parser"] == "llm"
    assert "duration_ms" in plan.trace


def test_llm_parser_rejects_untrusted_snapshot_override():
    class SnapshotOverrideProvider:
        def complete(self, *, system_prompt: str, user_prompt: str, response_schema: dict) -> str:
            return json.dumps({
                "intent": "POLICY_LOOKUP", "modalities": ["document"],
                "public_snapshot_id": "not-the-trusted-snapshot",
            })

    query = {
        "query": "Quy định P154 là gì?",
        "public_snapshot_id": "d4cc0438-d831-541a-8123-ddda94ccdac8",
    }
    plan = parse_query_llm(query, SnapshotOverrideProvider(), release_dir=RELEASE_DIR)
    assert plan.is_fallback is True
    assert "trusted routing" in (plan.fallback_reason or "")


def test_llm_fallback_on_extra_keys():
    """LLM hallucinating extra keys must be rejected by extra='forbid' and fallback."""
    query = {
        "query_id": "q-01",
        "query": "Theo quy chế P154, quy định hạng Kim Cương như thế nào?",
        "public_snapshot_id": "d4cc0438-d831-541a-8123-ddda94ccdac8",
    }
    plan = parse_query_llm(query, MockProviderExtraKeys(), release_dir=RELEASE_DIR)
    assert plan.is_fallback is True
    assert plan.fallback_reason is not None
    assert "ValidationError" in plan.fallback_reason
    assert "extra_forbidden" in plan.fallback_reason
    assert plan.trace["parser"] == "fallback_rule_based"
    assert plan.intent == "POLICY_LOOKUP"
    assert "P154" in plan.document_filters.pinned_documents


def test_llm_fallback_on_wrong_type():
    """LLM returning invalid enum type must trigger ValidationError and fallback."""
    query = {
        "query_id": "q-01",
        "query": "Theo quy chế P154, quy định hạng Kim Cương như thế nào?",
        "public_snapshot_id": "d4cc0438-d831-541a-8123-ddda94ccdac8",
    }
    plan = parse_query_llm(query, MockProviderWrongType(), release_dir=RELEASE_DIR)
    assert plan.is_fallback is True
    assert "ValidationError" in plan.fallback_reason
    assert plan.intent == "POLICY_LOOKUP"


def test_llm_fallback_on_broken_json():
    """LLM returning malformed JSON must trigger JSONDecodeError and fallback."""
    query = {
        "query_id": "q-01",
        "query": "Theo quy chế P154, quy định hạng Kim Cương như thế nào?",
        "public_snapshot_id": "d4cc0438-d831-541a-8123-ddda94ccdac8",
    }
    plan = parse_query_llm(query, MockProviderBrokenJSON(), release_dir=RELEASE_DIR)
    assert plan.is_fallback is True
    assert "JSONDecodeError" in plan.fallback_reason
    assert plan.intent == "POLICY_LOOKUP"


def test_llm_fallback_on_network_error():
    """Provider network exception must trigger fallback with exact error name."""
    query = {
        "query_id": "q-01",
        "query": "Theo quy chế P154, quy định hạng Kim Cương như thế nào?",
        "public_snapshot_id": "d4cc0438-d831-541a-8123-ddda94ccdac8",
    }
    plan = parse_query_llm(query, MockProviderNetworkError(), release_dir=RELEASE_DIR)
    assert plan.is_fallback is True
    assert "ConnectionError" in plan.fallback_reason
    assert plan.intent == "POLICY_LOOKUP"


# ==============================================================================
# 3. TEST PUBLIC SNAPSHOT ROUTING AND SECURITY ISOLATION
# ==============================================================================

def test_public_path_safety_rejects_private():
    """Verifies that accessing private directories raises PublicRoutingViolationError."""
    with pytest.raises(PublicRoutingViolationError):
        validate_public_path_safety("data/gsm-dev-core-0.2.2/private/eval")

    with pytest.raises(PublicRoutingViolationError):
        validate_public_path_safety(Path("data/gsm-dev-core-0.2.2/private/oracle/gold.jsonl"))

    with pytest.raises(PublicRoutingViolationError):
        resolve_public_snapshot_id({}, release_dir="data/gsm-dev-core-0.2.2/private")


def test_resolve_public_snapshot_id_via_explicit_query():
    """Snapshot explicitly provided in query must be returned."""
    query = {"public_snapshot_id": "d4cc0438-d831-541a-8123-ddda94ccdac8"}
    sid = resolve_public_snapshot_id(query, release_dir=RELEASE_DIR)
    assert sid == "d4cc0438-d831-541a-8123-ddda94ccdac8"


def test_resolve_public_snapshot_id_via_runtime_manifest():
    """Snapshot resolved by query_id from public/runtime_manifest.json."""
    # Query with query_id routed to branch snapshot df057563-78f4-5ac1-aba6-5b48c572fb4a
    query = {"query_id": "89f98a43-5dbb-5b77-b8f1-990e8933d546"}
    sid = resolve_public_snapshot_id(query, release_dir=RELEASE_DIR)
    assert sid == "df057563-78f4-5ac1-aba6-5b48c572fb4a"


def test_resolve_public_snapshot_id_default_fallback():
    """Unrouted query falls back to canonical public baseline snapshot."""
    query = {"query": "Câu hỏi chung"}
    sid = resolve_public_snapshot_id(query, release_dir=RELEASE_DIR)
    assert sid == DEFAULT_PUBLIC_BASELINE_SNAPSHOT


def test_resolve_public_snapshot_id_nonexistent_raises():
    """Non-existent public snapshot raises SnapshotNotFoundError."""
    query = {"public_snapshot_id": "00000000-0000-0000-0000-nonexistent00"}
    with pytest.raises(SnapshotNotFoundError):
        resolve_public_snapshot_id(query, release_dir=RELEASE_DIR)


# ==============================================================================
# 4. TEST RETRIEVAL CONFIG VERSIONING AND SERIALIZATION
# ==============================================================================

def test_retrieval_config_defaults_and_hash():
    """Verify default RetrievalConfig fields and deterministic hash."""
    config = RetrievalConfig()
    assert config.config_version == "1.0.0"
    assert config.embedding_model == "nvidia/nemotron-3-embed-1b"
    assert config.chunker == "gsm-word-span-v1"
    assert config.token_budget == 1800
    assert config.rrf_k == 60

    h1 = config.config_hash()
    h2 = config.config_hash()
    assert len(h1) == 64
    assert h1 == h2


def test_retrieval_config_extra_forbid():
    """RetrievalConfig must forbid extra unapproved parameters."""
    with pytest.raises(ValidationError):
        RetrievalConfig.model_validate({"config_version": "1.0.0", "unapproved_param": 123})


def test_retrieval_config_save_load_roundtrip(tmp_path: Path):
    """RetrievalConfig save and load round-trip."""
    cfg = RetrievalConfig(token_budget=2000, document_top_k=15)
    file_path = tmp_path / "custom_retrieval.json"
    cfg.save(file_path)

    loaded = RetrievalConfig.load(file_path)
    assert loaded.token_budget == 2000
    assert loaded.document_top_k == 15
    assert loaded.config_hash() == cfg.config_hash()


def test_retrieval_config_file_exists_and_valid():
    """Ensure configs/retrieval/retrieval_v1.json exists and loads cleanly."""
    config_file = Path("configs/retrieval/retrieval_v1.json")
    assert config_file.is_file()
    cfg = RetrievalConfig.load(config_file)
    assert cfg.config_version == "1.0.0"
    assert cfg.document_top_k == 10
    assert cfg.token_budget == 1800


# ==============================================================================
# 5. ACCEPTANCE CRITERIA: ALL 42 DATASET QUERIES PRODUCE VALID QUERYPLAN
# ==============================================================================

def test_all_42_public_queries_produce_valid_query_plan():
    """Verify that every query in dev.jsonl yields a valid QueryPlan with trace."""
    queries_file = RELEASE_DIR / "public" / "runtime_queries" / "dev.jsonl"
    assert queries_file.is_file()

    with open(queries_file, encoding="utf-8") as f:
        queries = [json.loads(line) for line in f if line.strip()]

    assert len(queries) == 42, f"Expected 42 queries, found {len(queries)}"

    manifest_file = RELEASE_DIR / "public" / "runtime_manifest.json"
    manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
    routes = {r["query_id"]: r["public_snapshot_id"] for r in manifest_data["query_routes"]}

    config = RetrievalConfig.load("configs/retrieval/retrieval_v1.json")

    for i, raw_query in enumerate(queries, start=1):
        plan = analyze_query(
            raw_query,
            provider=None,  # Offline deterministic parser
            release_dir=RELEASE_DIR,
            config=config,
        )

        # 1. Must be a valid QueryPlan instance
        assert isinstance(plan, QueryPlan), f"Query {i} did not return QueryPlan"

        # 2. Intent must be one of the approved literal values
        assert plan.intent in {"POLICY_LOOKUP", "DRIVER_HISTORY", "METRIC_CHECK", "HYBRID_REASONING"}
        assert plan.query_type == plan.intent

        # 3. Modalities must be non-empty and valid
        assert len(plan.modalities) > 0
        for mod in plan.modalities:
            assert mod in {"document", "kg", "computation"}

        # 4. Public snapshot must match runtime_manifest routing exactly
        expected_sid = routes[raw_query["query_id"]]
        assert plan.public_snapshot_id == expected_sid, (
            f"Query {raw_query['query_id']} snapshot mismatch: expected {expected_sid}, got {plan.public_snapshot_id}"
        )

        # 5. Budgets must match config
        assert plan.document_top_k == config.document_top_k
        assert plan.seed_top_k == config.seed_top_k
        assert plan.max_hops == config.max_hops
        assert plan.max_nodes == config.max_nodes
        assert plan.max_edges == config.max_edges

        # 6. Must have trace and fallback reason recorded
        assert plan.is_fallback is True
        assert plan.fallback_reason == "offline_deterministic_parser"
        assert plan.trace["parser"] == "deterministic_rule_based"
        assert "duration_ms" in plan.trace
        assert plan.trace["duration_ms"] >= 0.0

        # 7. Plan must serialize cleanly to JSON and back
        dumped = plan.model_dump()
        reconstructed = QueryPlan.model_validate(dumped)
        assert reconstructed.intent == plan.intent
        assert reconstructed.public_snapshot_id == plan.public_snapshot_id
