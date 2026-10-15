from __future__ import annotations

from pathlib import Path

from gsm_memory.adapters.neo4j_operational_embeddings import (
    OperationalNodeEmbeddingConfig,
    _classify_remote_embeddings,
    _vector_sha256,
)
from gsm_memory.data.operational_mock import (
    build_semantic_node_inputs,
    generate_operational_mock,
)


CONFIG = Path("configs/benchmark/operational-node-embedding-v1.json")


def _inputs():
    dataset = generate_operational_mock(
        Path("data/gsm-dev-core-0.2.2"),
        Path("configs/datasets/gsm-operational-mock-v0.2.json"),
        Path("configs/benchmark/operational-kg-v3.json"),
    )
    return build_semantic_node_inputs(dataset)


def test_embedding_config_and_population_are_fixed():
    config = OperationalNodeEmbeddingConfig.load(CONFIG)
    inputs = _inputs()

    assert config.provider == "qdrant_cloud"
    assert config.model == "intfloat/multilingual-e5-small"
    assert config.dimensions == 384
    assert config.marker_label == "GSMOperationalV3"
    assert len(inputs) == 23


def test_embedding_classifier_identifies_all_missing_without_false_mismatch():
    config = OperationalNodeEmbeddingConfig.load(CONFIG)
    inputs = _inputs()
    remote = {
        item["node_id"]: {
            "id": item["node_id"],
            "labels": [config.marker_label, item["node_type"]],
            "props": {"id": item["node_id"]},
        }
        for item in inputs
    }

    report = _classify_remote_embeddings(remote, inputs, config)

    assert len(report["missing_embeddings"]) == 23
    assert report["missing_nodes"] == []
    assert report["mismatched"] == []
    assert report["verified"] == []


def test_embedding_classifier_verifies_vector_and_provenance_hashes():
    config = OperationalNodeEmbeddingConfig.load(CONFIG)
    inputs = _inputs()
    vector = [0.0] * config.dimensions
    remote = {
        item["node_id"]: {
            "id": item["node_id"],
            "labels": [config.marker_label, item["node_type"]],
            "props": {
                "id": item["node_id"],
                config.vector_property: vector,
                config.text_sha256_property: item["content_sha256"],
                config.vector_sha256_property: _vector_sha256(vector),
                config.model_property: config.model,
                config.dimensions_property: config.dimensions,
            },
        }
        for item in inputs
    }

    report = _classify_remote_embeddings(remote, inputs, config)

    assert len(report["verified"]) == 23
    assert report["missing_embeddings"] == []
    assert report["mismatched"] == []

    first = inputs[0]["node_id"]
    remote[first]["props"][config.text_sha256_property] = "0" * 64
    changed = _classify_remote_embeddings(remote, inputs, config)
    assert changed["mismatched"] == [
        {"node_id": first, "issues": ["text_sha256"]}
    ]
