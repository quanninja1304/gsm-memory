from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from gsm_memory.data.operational_mock import (
    compare_operational_mock_candidates,
    generate_operational_mock,
    materialize_operational_mock,
    validate_operational_mock,
    verify_operational_mock_candidate,
)


RELEASE = Path("data/gsm-dev-core-0.2.2")
CONFIG = Path("configs/datasets/gsm-operational-mock-v0.1.json")
CONTRACT = Path("configs/benchmark/operational-kg-v2.json")


@pytest.fixture(scope="module")
def dataset():
    return generate_operational_mock(RELEASE, CONFIG, CONTRACT)


def test_mock_v2_has_expected_core_population_and_links(dataset):
    assert dataset.dataset_version == "gsm-operational-mock-v0.1"
    assert dataset.source_release == "gsm-dev-core-0.2.2"
    assert dataset.seed == 42
    assert dataset.counts["node_labels"] | {
        "Driver": 8,
        "Trip": 80,
        "Vehicle": 8,
        "VehicleType": 2,
        "Zone": 4,
        "Complaint": 11,
        "MaintenanceEvent": 8,
        "PolicyDocument": 4,
        "PolicyRule": 4,
        "PolicyAction": 4,
        "ViolationFinding": 4,
        "EnforcementDecision": 4,
    } == dataset.counts["node_labels"]
    relationships = dataset.counts["relationship_types"]
    assert relationships["PERFORMED"] == 80
    assert relationships["CONTAINS_TRIP"] == 80
    assert relationships["PICKUP_IN"] == 80
    assert relationships["DROPOFF_IN"] == 80
    assert relationships["OPERATED"] == 8
    assert relationships["UNDERWENT"] == 8
    assert relationships["RECEIVED_COMPLAINT"] == 11


def test_mock_v2_is_deterministic_and_uses_stable_unique_ids(dataset):
    repeated = generate_operational_mock(RELEASE, CONFIG, CONTRACT)
    assert repeated.logical_digest == dataset.logical_digest
    assert repeated.nodes == dataset.nodes
    assert repeated.edges == dataset.edges
    assert len({row["id"] for row in dataset.nodes}) == len(dataset.nodes)
    assert len({row["id"] for row in dataset.edges}) == len(dataset.edges)


def test_policy_rules_have_reviewed_public_clause_provenance(dataset):
    nodes = {(row["label"], row["id"]): row for row in dataset.nodes}
    rules = [row for row in dataset.nodes if row["label"] == "PolicyRule"]
    clauses = [row for row in dataset.nodes if row["label"] == "PolicyClause"]
    defined_in = [row for row in dataset.edges if row["type"] == "DEFINED_IN"]

    assert len(rules) == 4
    assert len(clauses) == 13
    assert len(defined_in) == 13
    assert all(row["props"]["review_status"] == "reviewed_from_pinned_text" for row in rules)
    assert all(row["props"]["source_kind"] == "reviewed_policy" for row in clauses)
    assert all(len(row["props"]["content_sha256"]) == 64 for row in clauses)
    assert all((row["end_label"], row["end_id"]) in nodes for row in defined_in)
    serialized = json.dumps(
        {"nodes": dataset.nodes, "edges": dataset.edges}, ensure_ascii=False
    )
    assert "private/" not in serialized
    assert "task_binding" not in serialized
    assert '"task_id"' not in serialized


def test_findings_are_exact_and_disabled_rules_emit_none(dataset):
    nodes = {(row["label"], row["id"]): row for row in dataset.nodes}
    findings = [row for row in dataset.nodes if row["label"] == "ViolationFinding"]
    links = [row for row in dataset.edges if row["type"] == "EVALUATED_AGAINST"]
    rule_ids = Counter(row["end_id"] for row in links)

    assert len(findings) == 4
    assert {row["props"]["observed_value"] for row in findings} == {
        "200000",
        "240000",
        "49/100",
    }
    assert rule_ids == {
        "policy-rule:min-daily-revenue:v1": 2,
        "policy-rule:auto-accept-low-rate:v1": 2,
    }
    decisions = [row for row in dataset.nodes if row["label"] == "EnforcementDecision"]
    assert Counter(row["props"].get("computed_amount") for row in decisions) == {
        "16000": 1,
        "8000": 1,
        None: 2,
    }
    assert all(("PolicyRule", rule_id) in nodes for rule_id in rule_ids)


def test_zero_activity_driver_gets_zero_summary_without_fake_trip(dataset):
    summaries = [row for row in dataset.nodes if row["label"] == "DriverSummary"]
    assert len(summaries) == 8
    zero = [row for row in summaries if row["props"]["trip_count"] == 0]
    assert len(zero) == 1
    assert zero[0]["props"]["support_trip_ids"] == []
    assert zero[0]["props"]["cancel_rate_denominator"] == 0


def test_candidate_materialization_and_independent_comparison(dataset, tmp_path):
    first = tmp_path / "candidate-a"
    second = tmp_path / "candidate-b"
    materialize_operational_mock(dataset, first, contract_path=CONTRACT)
    independently_built = generate_operational_mock(RELEASE, CONFIG, CONTRACT)
    materialize_operational_mock(independently_built, second, contract_path=CONTRACT)

    assert verify_operational_mock_candidate(first, contract_path=CONTRACT)["status"] == "pass"
    assert verify_operational_mock_candidate(second, contract_path=CONTRACT)["status"] == "pass"
    assert compare_operational_mock_candidates(first, second)["status"] == "pass"
    assert (first / "nodes.jsonl").read_bytes() == (second / "nodes.jsonl").read_bytes()
    assert (first / "edges.jsonl").read_bytes() == (second / "edges.jsonl").read_bytes()


def test_candidate_verifier_detects_mutation(dataset, tmp_path):
    candidate = tmp_path / "candidate"
    materialize_operational_mock(dataset, candidate, contract_path=CONTRACT)
    with (candidate / "nodes.jsonl").open("ab") as handle:
        handle.write(b" ")

    report = verify_operational_mock_candidate(candidate, contract_path=CONTRACT)
    assert report["status"] == "fail"
    assert "byte_count_mismatch:nodes.jsonl" in report["errors"]
    assert "sha256_mismatch:nodes.jsonl" in report["errors"]


def test_materialization_refuses_non_empty_target(dataset, tmp_path):
    target = tmp_path / "occupied"
    target.mkdir()
    (target / "owned-by-user.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        materialize_operational_mock(dataset, target, contract_path=CONTRACT)


def test_generated_dataset_passes_closed_contract(dataset):
    report = validate_operational_mock(dataset, contract_path=CONTRACT)
    assert report["status"] == "pass"
    assert report["errors"] == []
