from pathlib import Path

import pytest

from gsm_memory.adapters.neo4j_operational_v2 import (
    MARKER_LABEL,
    _compare_state,
    _safe_identifier,
)
from gsm_memory.data.operational_mock import generate_operational_mock


RELEASE = Path("data/gsm-dev-core-0.2.2")
CONFIG = Path("configs/datasets/gsm-operational-mock-v0.1.json")
CONTRACT = Path("configs/benchmark/operational-kg-v2.json")


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def data(self):
        return self._rows


class _Session:
    def __init__(
        self,
        dataset,
        *,
        marker=MARKER_LABEL,
        mutate_node=False,
        runtime_embedding=False,
        omit_edge=False,
    ):
        self.nodes = [
            {
                "labels": [marker, row["label"]],
                "id": row["id"],
                "props": {
                    **row["props"],
                    **(
                        {"name": "mutated"}
                        if mutate_node and index == 0
                        else {}
                    ),
                    **(
                        {
                            "semantic_embedding": [0.1, 0.2],
                            "semantic_embedding_dimensions": 2,
                            "semantic_embedding_model": "test-model",
                            "semantic_embedding_sha256": "a" * 64,
                            "semantic_text_sha256": "b" * 64,
                        }
                        if runtime_embedding and index == 0
                        else {}
                    ),
                },
            }
            for index, row in enumerate(dataset.nodes)
        ]
        edge_source = dataset.edges[1:] if omit_edge else dataset.edges
        self.edges = [
            {
                "type": row["type"],
                "id": row["id"],
                "start_labels": [marker, row["start_label"]],
                "start_id": row["start_id"],
                "end_labels": [marker, row["end_label"]],
                "end_id": row["end_id"],
                "props": row["props"],
            }
            for row in edge_source
        ]

    def run(self, query):
        return _Result(self.nodes if "RETURN labels(n)" in query else self.edges)


@pytest.fixture(scope="module")
def dataset():
    return generate_operational_mock(RELEASE, CONFIG, CONTRACT)


def test_v2_remote_comparison_accepts_exact_candidate(dataset):
    report = _compare_state(_Session(dataset), dataset)
    assert all(rows == [] for rows in report.values())


def test_candidate_comparison_rejects_runtime_embedding_properties(dataset):
    report = _compare_state(_Session(dataset, runtime_embedding=True), dataset)
    assert len(report["mismatched_nodes"]) == 1
    assert all(
        rows == []
        for name, rows in report.items()
        if name != "mismatched_nodes"
    )


def test_v2_remote_comparison_implicates_mutation_and_missing_edge(dataset):
    report = _compare_state(
        _Session(dataset, mutate_node=True, omit_edge=True), dataset
    )
    assert len(report["mismatched_nodes"]) == 1
    assert len(report["missing_edges"]) == 1
    assert report["unexpected_nodes"] == []
    assert report["unexpected_edges"] == []


def test_v2_dynamic_cypher_identifiers_are_closed():
    assert _safe_identifier("ViolationFinding") == "ViolationFinding"
    with pytest.raises(ValueError, match="unsafe Neo4j identifier"):
        _safe_identifier("Driver) MATCH (n")


def test_remote_comparison_supports_separate_v3_marker_namespace():
    dataset_v3 = generate_operational_mock(
        RELEASE,
        Path("configs/datasets/gsm-operational-mock-v0.2.json"),
        Path("configs/benchmark/operational-kg-v3.json"),
    )
    marker = "GSMOperationalV3"

    report = _compare_state(
        _Session(dataset_v3, marker=marker),
        dataset_v3,
        marker,
    )

    assert all(rows == [] for rows in report.values())
