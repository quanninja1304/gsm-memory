from pathlib import Path

import pytest
from pydantic import ValidationError

from gsm_memory.data.operational_v2_contract import OperationalKGv2Contract


CONTRACT_PATH = Path("configs/benchmark/operational-kg-v2.json")
MVP_CONTRACT_PATH = Path("configs/benchmark/operational-kg-v3.json")
TIMELINE_CONTRACT_PATH = Path("configs/benchmark/operational-kg-v3-r2.json")


def test_operational_v2_contract_is_closed_and_keeps_frozen_source_immutable():
    contract = OperationalKGv2Contract.load(CONTRACT_PATH)

    assert contract.status == "experimental_extension"
    assert contract.source_release == "gsm-dev-core-0.2.2"
    assert contract.mutates_frozen_release is False
    assert contract.purpose == "evidence_retrieval_and_construction"
    assert contract.causal_inference is False


def test_operational_v2_uses_only_neo4j_and_qdrant_native_hybrid():
    contract = OperationalKGv2Contract.load(CONTRACT_PATH)
    qdrant = contract.runtime_stores.qdrant

    assert contract.runtime_stores.neo4j.env_prefix == "NEO4J_OPERATIONAL_V2"
    assert qdrant.collection == "gsm_policy_chunks_v2"
    assert qdrant.query_mode == "native_hybrid"
    assert qdrant.fusion == "rrf"
    assert qdrant.external_bm25_store is False
    assert {(row.name, row.purpose) for row in qdrant.vectors} == {
        ("dense", "semantic_similarity"),
        ("sparse", "lexical_precision"),
    }
    vectors = {row.name: row for row in qdrant.vectors}
    assert vectors["dense"].model == "intfloat/multilingual-e5-small"
    assert vectors["dense"].dimensions == 384
    assert vectors["dense"].document_prefix == "passage: "
    assert vectors["dense"].query_prefix == "query: "
    assert vectors["sparse"].model == "qdrant/bm25"
    assert vectors["sparse"].dimensions is None


def test_operational_v2_policy_clause_is_semantic_and_rule_is_structured():
    contract = OperationalKGv2Contract.load(CONTRACT_PATH)
    nodes = {node.name: node for node in contract.nodes}

    assert nodes["PolicyClause"].semantic_text_fields == ["text"]
    assert nodes["PolicyRule"].semantic_text_fields == []
    assert {"PolicyDocument", "PolicyClause", "PolicyRule", "PolicyAction"} <= set(nodes)


def test_operational_v2_rejects_causal_or_weather_scope():
    payload = OperationalKGv2Contract.load(CONTRACT_PATH).model_dump()
    payload["nodes"].append({
        "name": "WeatherObservation",
        "origin": "synthetic_extension",
        "required_properties": ["description", "id", "name"],
        "semantic_text_fields": ["description"],
    })
    payload["nodes"] = sorted(payload["nodes"], key=lambda row: row["name"])

    with pytest.raises(ValidationError, match="outside scope"):
        OperationalKGv2Contract.model_validate(payload)


def test_operational_v2_relationship_endpoints_are_declared_nodes():
    contract = OperationalKGv2Contract.load(CONTRACT_PATH)
    node_names = {node.name for node in contract.nodes}

    for relationship in contract.relationships:
        assert set(relationship.start_types) <= node_names
        assert set(relationship.end_types) <= node_names


def test_operational_v3_overlay_removes_summary_and_synthetic_shift_types():
    contract = OperationalKGv2Contract.load(MVP_CONTRACT_PATH)
    node_names = {node.name for node in contract.nodes}
    relationship_names = {row.name for row in contract.relationships}

    assert contract.contract_version == "gsm-operational-kg-v3-draft-1"
    assert contract.runtime_stores.neo4j.env_prefix == "NEO4J_OPERATIONAL_V3"
    assert contract.runtime_stores.neo4j.marker_label == "GSMOperationalV3"
    assert not {
        "DriverSummary",
        "FleetSummary",
        "Shift",
        "ShiftSummary",
        "ZoneSummary",
    } & node_names
    assert not {
        "CONTAINS_TRIP",
        "HAS_SUMMARY",
        "OPERATED_IN",
        "WORKED_SHIFT",
    } & relationship_names


def test_operational_v3_keeps_policy_text_in_qdrant_and_expands_incident_path():
    contract = OperationalKGv2Contract.load(MVP_CONTRACT_PATH)
    nodes = {node.name: node for node in contract.nodes}
    relationships = {row.name: row for row in contract.relationships}

    assert nodes["PolicyClause"].semantic_text_fields == []
    assert "text" not in nodes["PolicyClause"].required_properties
    assert nodes["Incident"].allowed_origins == {
        "frozen_projection",
        "synthetic_extension",
    }
    assert nodes["StateObservation"].allowed_origins == {
        "frozen_projection",
        "synthetic_extension",
    }
    assert relationships["ABOUT_TRIP"].start_types == ["Complaint", "Incident"]


def test_operational_v3_timeline_uses_an_isolated_neo4j_namespace():
    contract = OperationalKGv2Contract.load(TIMELINE_CONTRACT_PATH)

    assert contract.contract_version == "gsm-operational-kg-v3-draft-2"
    assert contract.runtime_stores.neo4j.env_prefix == "NEO4J_OPERATIONAL_V3"
    assert contract.runtime_stores.neo4j.marker_label == "GSMOperationalV3Timeline"
