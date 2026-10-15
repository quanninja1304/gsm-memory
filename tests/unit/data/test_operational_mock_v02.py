from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from gsm_memory.data.operational_mock import (
    build_semantic_node_inputs,
    compare_operational_mock_candidates,
    generate_operational_mock,
    materialize_operational_mock,
    validate_operational_mock,
    verify_operational_mock_candidate,
)


RELEASE = Path("data/gsm-dev-core-0.2.2")
CONFIG = Path("configs/datasets/gsm-operational-mock-v0.2.json")
CONTRACT = Path("configs/benchmark/operational-kg-v3.json")
LEGACY_CONFIG = Path("configs/datasets/gsm-operational-mock-v0.1.json")
LEGACY_CONTRACT = Path("configs/benchmark/operational-kg-v2.json")


@pytest.fixture(scope="module")
def dataset():
    return generate_operational_mock(RELEASE, CONFIG, CONTRACT)


def test_v02_has_exact_minimal_projection_and_no_summary_or_shift(dataset):
    assert dataset.dataset_version == "gsm-operational-mock-v0.2"
    assert dataset.counts["nodes"] == 198
    assert dataset.counts["edges"] == 579
    assert dataset.counts["node_labels"] == {
        "Complaint": 11,
        "Driver": 8,
        "EnforcementDecision": 4,
        "Fleet": 4,
        "Incident": 5,
        "MaintenanceEvent": 8,
        "Measurement": 17,
        "PolicyAction": 4,
        "PolicyClause": 13,
        "PolicyDocument": 4,
        "PolicyRule": 4,
        "Region": 2,
        "Service": 1,
        "StateObservation": 15,
        "Trip": 80,
        "Vehicle": 8,
        "VehicleType": 2,
        "ViolationFinding": 4,
        "Zone": 4,
    }
    assert not {
        "DriverSummary",
        "FleetSummary",
        "Shift",
        "ShiftSummary",
        "ZoneSummary",
    } & set(dataset.counts["node_labels"])
    assert not {
        "CONTAINS_TRIP",
        "HAS_SUMMARY",
        "OPERATED_IN",
        "WORKED_SHIFT",
    } & set(dataset.counts["relationship_types"])


def test_v02_complaints_remain_the_frozen_experimental_checkpoint(dataset):
    complaints = [row for row in dataset.nodes if row["label"] == "Complaint"]
    edges = dataset.edges

    assert Counter(row["props"]["category"] for row in complaints) == {
        "service_attitude": 4,
        "trip_cancellation": 4,
        "fare_question": 3,
    }
    assert len({row["props"]["description"] for row in complaints}) == 11
    assert all(
        row["props"]["description"].startswith("Phản ánh mock")
        and row["props"]["name"].startswith("Phản ánh mock cho")
        for row in complaints
    )
    assert sum(row["type"] == "RECEIVED_COMPLAINT" for row in edges) == 11
    complaint_links = [
        row for row in edges
        if row["type"] == "ABOUT_TRIP" and row["start_label"] == "Complaint"
    ]
    assert len(complaint_links) == 11
    assert len({row["start_id"] for row in complaint_links}) == 11
    assert len({row["end_id"] for row in complaint_links}) == 11
    node_by_id = {row["id"]: row for row in dataset.nodes}
    for link in complaint_links:
        complaint = node_by_id[link["start_id"]]
        trip = node_by_id[link["end_id"]]
        assert trip["id"][:8] in complaint["props"]["description"]


def test_v02_incidents_are_explicit_without_mutating_frozen_incident(dataset):
    incidents = [row for row in dataset.nodes if row["label"] == "Incident"]
    synthetic = [
        row for row in incidents
        if row["props"]["source_kind"] == "synthetic_extension"
    ]
    frozen = [
        row for row in incidents
        if row["props"]["source_kind"] == "frozen_projection"
    ]
    synthetic_ids = {row["id"] for row in synthetic}

    assert len(synthetic) == 4
    assert len(frozen) == 1
    assert {row["props"]["incident_type"] for row in synthetic} == {
        "vehicle_operability",
        "pickup_not_completed",
        "service_interruption",
        "fare_review_escalation",
    }
    assert len({row["props"]["name"] for row in synthetic}) == 4
    assert len({row["props"]["description"] for row in synthetic}) == 4
    assert all(row["props"]["name"].startswith("Sự cố mock") for row in synthetic)
    synthetic_states = [
        row
        for row in dataset.nodes
        if row["label"] == "StateObservation"
        and row["props"]["source_kind"] == "synthetic_extension"
    ]
    assert {row["props"]["value"] for row in synthetic_states} == {
        "open",
        "resolved",
        "reopened",
    }
    incident_trip = [
        row for row in dataset.edges
        if row["type"] == "ABOUT_TRIP" and row["start_label"] == "Incident"
    ]
    assert {row["start_id"] for row in incident_trip} == synthetic_ids
    assert len({row["end_id"] for row in incident_trip}) == 4
    assert not any(row["start_id"] == frozen[0]["id"] for row in incident_trip)
    node_by_id = {row["id"]: row for row in dataset.nodes}
    for link in incident_trip:
        assert link["end_id"][:8] in node_by_id[link["start_id"]]["props"][
            "description"
        ]
    incident_states = [
        row
        for row in dataset.edges
        if row["type"] == "HAS_STATE" and row["start_id"] in synthetic_ids
    ]
    assert len(incident_states) == 4
    assert {row["end_id"] for row in incident_states} == {
        row["id"] for row in synthetic_states
    }


def test_v02_maintenance_has_four_concrete_types(dataset):
    events = [row for row in dataset.nodes if row["label"] == "MaintenanceEvent"]
    assert Counter(row["props"]["maintenance_type"] for row in events) == {
        "scheduled_inspection": 2,
        "battery_check": 2,
        "brake_check": 2,
        "tire_check": 2,
    }
    assert all("tổng hợp" not in row["props"]["description"] for row in events)
    assert sum(row["type"] == "UNDERWENT" for row in dataset.edges) == 8


def test_v02_keeps_policy_full_text_out_of_neo4j(dataset):
    clauses = [row for row in dataset.nodes if row["label"] == "PolicyClause"]
    assert len(clauses) == 13
    assert all("text" not in row["props"] for row in clauses)
    assert all(row["props"]["source_locator"].startswith("unicode:") for row in clauses)


def test_v02_semantic_index_selects_exactly_reviewed_free_text_nodes(dataset):
    inputs = build_semantic_node_inputs(dataset)

    assert len(inputs) == 23
    assert Counter(row["node_type"] for row in inputs) == {
        "Complaint": 11,
        "Incident": 4,
        "MaintenanceEvent": 8,
    }
    assert all(row["text"] for row in inputs)
    assert all(len(row["content_sha256"]) == 64 for row in inputs)
    assert not any(row["node_type"] == "PolicyClause" for row in inputs)


def test_v02_is_deterministic_and_legacy_digest_is_unchanged(dataset):
    repeated = generate_operational_mock(RELEASE, CONFIG, CONTRACT)
    legacy = generate_operational_mock(RELEASE, LEGACY_CONFIG, LEGACY_CONTRACT)

    assert repeated.logical_digest == dataset.logical_digest
    assert dataset.logical_digest == (
        "fee5c817cd3bff9dfeddb19579a485711166a54c2850ffeadfa25b911b0b7cae"
    )
    assert repeated.nodes == dataset.nodes
    assert repeated.edges == dataset.edges
    assert legacy.logical_digest == (
        "85471b7dcd2c3ac5b88c7af21e8e7a9f488417ba358f17fd549cdae06fa59db8"
    )


def test_v02_two_clean_candidates_compare_logically(dataset, tmp_path):
    first = tmp_path / "candidate-a"
    second = tmp_path / "candidate-b"
    materialize_operational_mock(dataset, first, contract_path=CONTRACT)
    materialize_operational_mock(
        generate_operational_mock(RELEASE, CONFIG, CONTRACT),
        second,
        contract_path=CONTRACT,
    )

    assert verify_operational_mock_candidate(first, contract_path=CONTRACT)["status"] == "pass"
    assert verify_operational_mock_candidate(second, contract_path=CONTRACT)["status"] == "pass"
    assert compare_operational_mock_candidates(first, second)["status"] == "pass"
    assert validate_operational_mock(dataset, contract_path=CONTRACT)["status"] == "pass"
