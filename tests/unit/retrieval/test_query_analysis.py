import pytest

from tests.fixtures.mock_data import MOCK_SCENARIOS
from gsm_memory.retrieval.query_analysis import (
    analyze_query,
    parse_query_llm,
    parse_query_rule_based,
)


def test_rule_based_policy_query_parsing():
    query = MOCK_SCENARIOS["policy_lookup"]["query"]
    parsed = parse_query_rule_based(query)

    assert parsed.query_type == "POLICY_LOOKUP"
    assert "P154" in parsed.document_filters.pinned_documents
    assert any("kim cương" in topic.lower() for topic in parsed.document_filters.target_topics)
    # Policy query does not trigger incident predicates
    assert "HAS_INCIDENT" not in parsed.graph_filters.target_predicates


def test_rule_based_complex_hybrid_query_parsing():
    query = MOCK_SCENARIOS["complex_driver_reasoning"]["query"]
    parsed = parse_query_rule_based(query, session_driver_id="DRV-001")

    assert parsed.query_type == "HYBRID_REASONING"
    # Document filters
    assert "P154" in parsed.document_filters.pinned_documents
    # Graph filters - targeted predicates
    assert "TRIP_OUTCOME" in parsed.graph_filters.target_predicates
    assert "HAS_INCIDENT" in parsed.graph_filters.target_predicates
    assert parsed.graph_filters.attribute_conditions.get("status") == "cancelled"
    # Computation filters
    assert parsed.computation_filters.target_metric == "cancel_rate_30d"
    # Session driver propagation
    assert "DRV-001" in parsed.entity_refs


def test_rule_based_extracts_doc_from_snap_prefix():
    query = {
        "query_id": "test-q",
        "query": "Theo snapshot snap-154-d4af28195271, quy định doanh số tối thiểu là bao nhiêu?",
    }
    parsed = parse_query_rule_based(query)
    assert "P154" in parsed.document_filters.pinned_documents
    assert parsed.query_type == "POLICY_LOOKUP"


class FakeParserProvider:
    def complete(self, *, system_prompt: str, user_prompt: str, response_schema: dict) -> str:
        return """{
            "intent": "HYBRID_REASONING",
            "modalities": ["document", "kg", "computation"],
            "entity_mentions": ["Nguyễn Văn A"],
            "entity_refs": ["99e70ebe-18cd-57a3-a036-cf0ff1989861"],
            "time_scope": {"mode": "current"},
            "known_as_of": "2026-09-17T12:00:00Z",
            "public_snapshot_id": "snap-public-01",
            "document_filters": {
                "pinned_documents": ["P154"],
                "target_topics": ["Kim Cương"],
                "sub_query": "Tiêu chuẩn Kim Cương P154"
            },
            "graph_filters": {
                "target_predicates": ["TRIP_OUTCOME", "HAS_INCIDENT"],
                "attribute_conditions": {"status": "cancelled"},
                "edge_search_text": "xe hỏng"
            },
            "computation_filters": {
                "target_metric": "cancel_rate_30d",
                "threshold_rule": "diamond_tier"
            },
            "seed_top_k": 3,
            "max_hops": 2,
            "max_nodes": 20,
            "max_edges": 30,
            "document_top_k": 10
        }"""


def test_llm_query_parsing_and_fallback():
    query = MOCK_SCENARIOS["complex_driver_reasoning"]["query"]
    provider = FakeParserProvider()
    parsed = parse_query_llm(query, provider)

    assert parsed.intent == "HYBRID_REASONING"
    assert parsed.query_type == "HYBRID_REASONING"
    assert parsed.is_fallback is False
    assert parsed.fallback_reason is None
    assert parsed.graph_filters.target_predicates == ["TRIP_OUTCOME", "HAS_INCIDENT"]
    assert parsed.computation_filters.target_metric == "cancel_rate_30d"
    assert "document" in parsed.modalities

    # Test fallback on invalid JSON
    class BrokenProvider:
        def complete(self, **kwargs):
            return "not-json"

    fallback_parsed = parse_query_llm(query, BrokenProvider())
    assert fallback_parsed.query_type == "HYBRID_REASONING"
    assert fallback_parsed.is_fallback is True
    assert fallback_parsed.fallback_reason is not None
    assert "JSONDecodeError" in fallback_parsed.fallback_reason
    assert "P154" in fallback_parsed.document_filters.pinned_documents

