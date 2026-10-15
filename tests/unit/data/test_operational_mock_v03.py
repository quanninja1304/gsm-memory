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
CONFIG = Path("configs/datasets/gsm-operational-mock-v0.3.json")
CONTRACT = Path("configs/benchmark/operational-kg-v3-r2.json")


@pytest.fixture(scope="module")
def dataset():
    return generate_operational_mock(RELEASE, CONFIG, CONTRACT)


def test_v03_keeps_the_minimal_v3_shape(dataset):
    assert dataset.dataset_version == "gsm-operational-mock-v0.3"
    assert dataset.counts["nodes"] == 201
    assert dataset.counts["edges"] == 582
    assert not {
        "DriverSummary",
        "FleetSummary",
        "Shift",
        "ShiftSummary",
        "ZoneSummary",
    } & set(dataset.counts["node_labels"])
    assert "HAS_SUMMARY" not in dataset.counts["relationship_types"]


def test_v03_complaints_are_concrete_linked_and_non_judgmental(dataset):
    complaints = [row for row in dataset.nodes if row["label"] == "Complaint"]
    assert Counter(row["props"]["category"] for row in complaints) == {
        "service_attitude": 4,
        "trip_cancellation": 4,
        "fare_question": 3,
    }
    assert len({row["props"]["scenario_id"] for row in complaints}) == 11
    assert len({row["props"]["description"] for row in complaints}) == 11
    forbidden = ("mock", "mô phỏng", "tình huống giả lập")
    assert all(
        not any(term in row["props"]["name"].lower() for term in forbidden)
        and not any(term in row["props"]["description"].lower() for term in forbidden)
        and row["props"]["source_kind"] == "synthetic_extension"
        for row in complaints
    )
    nodes = {row["id"]: row for row in dataset.nodes}
    links = [
        row
        for row in dataset.edges
        if row["type"] == "ABOUT_TRIP" and row["start_label"] == "Complaint"
    ]
    assert len(links) == 11
    for link in links:
        complaint = nodes[link["start_id"]]
        trip = nodes[link["end_id"]]
        assert trip["id"][:8] in complaint["props"]["description"]


def test_v03_marks_synthetic_data_structurally_not_in_readable_text(dataset):
    synthetic_or_derived = [
        row
        for row in dataset.nodes
        if row["props"].get("source_kind") in {"synthetic_extension", "derived"}
    ]
    forbidden = ("mock", "mô phỏng", "tình huống giả lập")
    assert synthetic_or_derived
    assert all(
        not any(
            term in (
                str(row["props"].get("name", ""))
                + " "
                + str(row["props"].get("description", ""))
            ).lower()
            for term in forbidden
        )
        for row in synthetic_or_derived
    )


def test_v03_uses_twelve_ordered_l0_snapshots_without_full_graph_copies(dataset):
    assert len(dataset.snapshots) == 12
    assert len({row["snapshot_id"] for row in dataset.snapshots}) == 12
    assert all(
        set(row)
        == {
            "snapshot_id",
            "timeline_id",
            "source_ledger_id",
            "sequence",
            "known_as_of",
            "name",
        }
        for row in dataset.snapshots
    )
    assert [row["sequence"] for row in dataset.snapshots] == list(range(1, 13))
    assert {row["timeline_id"] for row in dataset.snapshots} == {"L0"}
    assert len({row["source_ledger_id"] for row in dataset.snapshots}) == 1
    assert [row["known_as_of"] for row in dataset.snapshots] == sorted(
        row["known_as_of"] for row in dataset.snapshots
    )
    frozen_edges = [
        row
        for row in dataset.edges
        if row["props"].get("source_kind") == "frozen_projection"
    ]
    assert len(frozen_edges) == 295
    assert len(frozen_edges) < 12 * 295
    assert all(row["props"]["visibility_snapshot_ids"] for row in dataset.nodes)
    assert all(row["props"]["visibility_snapshot_ids"] for row in dataset.edges)


def test_v03_snapshot_visibility_is_cumulative_and_keeps_reference_nodes(dataset):
    snapshot_ids = [row["snapshot_id"] for row in dataset.snapshots]
    order = {snapshot_id: index for index, snapshot_id in enumerate(snapshot_ids)}
    for row in (*dataset.nodes, *dataset.edges):
        positions = [
            order[snapshot_id]
            for snapshot_id in row["props"]["visibility_snapshot_ids"]
        ]
        assert positions == list(range(positions[0], len(snapshot_ids)))

    static_labels = {
        "Driver",
        "Fleet",
        "Region",
        "Service",
        "Vehicle",
        "VehicleType",
        "Zone",
    }
    assert all(
        row["props"]["visibility_snapshot_ids"] == snapshot_ids
        for row in dataset.nodes
        if row["label"] in static_labels
    )

    policy_nodes = [
        row
        for row in dataset.nodes
        if row["label"]
        in {"PolicyAction", "PolicyClause", "PolicyDocument", "PolicyRule"}
    ]
    assert all(
        row["props"]["visibility_snapshot_ids"] == snapshot_ids[9:]
        for row in policy_nodes
    )

    trip_counts = []
    complaint_counts = []
    incident_counts = []
    for snapshot_id in snapshot_ids:
        visible = [
            row
            for row in dataset.nodes
            if snapshot_id in row["props"]["visibility_snapshot_ids"]
        ]
        trip_counts.append(sum(row["label"] == "Trip" for row in visible))
        complaint_counts.append(sum(row["label"] == "Complaint" for row in visible))
        incident_counts.append(sum(row["label"] == "Incident" for row in visible))
    assert trip_counts == sorted(trip_counts)
    assert complaint_counts == sorted(complaint_counts)
    assert incident_counts == sorted(incident_counts)
    assert trip_counts[-1] == 80
    assert complaint_counts[-1] == 11
    assert incident_counts[-1] == 5


def test_v03_incidents_are_concrete_and_preserve_frozen_incident(dataset):
    incidents = [row for row in dataset.nodes if row["label"] == "Incident"]
    synthetic = [
        row for row in incidents if row["props"]["source_kind"] == "synthetic_extension"
    ]
    frozen = [
        row for row in incidents if row["props"]["source_kind"] == "frozen_projection"
    ]
    assert len(synthetic) == 4
    assert len(frozen) == 1
    assert len({row["props"]["description"] for row in synthetic}) == 4
    assert all(
        "mock" not in row["props"]["name"].lower()
        and "mock" not in row["props"]["description"].lower()
        and "mô phỏng" not in row["props"]["description"].lower()
        for row in synthetic
    )
    nodes = {row["id"]: row for row in dataset.nodes}
    links = [
        row
        for row in dataset.edges
        if row["type"] == "ABOUT_TRIP" and row["start_label"] == "Incident"
    ]
    assert len(links) == 4
    assert all(
        nodes[link["end_id"]]["id"][:8]
        in nodes[link["start_id"]]["props"]["description"]
        for link in links
    )


def test_v03_incident_lifecycles_are_explicit_non_overlapping_intervals(dataset):
    nodes = {row["id"]: row for row in dataset.nodes}
    incident_states = {}
    for edge in dataset.edges:
        if edge["type"] != "HAS_STATE" or edge["start_label"] != "Incident":
            continue
        if nodes[edge["start_id"]]["props"].get("source_kind") != "synthetic_extension":
            continue
        incident_states.setdefault(edge["start_id"], []).append(edge)
    histories = {
        tuple(
            nodes[edge["end_id"]]["props"]["value"]
            for edge in sorted(rows, key=lambda row: row["props"]["valid_from"])
        )
        for rows in incident_states.values()
    }
    assert histories == {
        ("open",),
        ("open", "resolved"),
        ("open", "resolved", "reopened"),
    }
    for rows in incident_states.values():
        ordered = sorted(rows, key=lambda row: row["props"]["valid_from"])
        for previous, current in zip(ordered, ordered[1:]):
            assert previous["props"]["valid_to"] == current["props"]["valid_from"]
        assert all("known_to" not in row["props"] for row in ordered)


def test_v03_driver_states_are_readable_and_temporally_explicit(dataset):
    states = [
        row
        for row in dataset.nodes
        if row["label"] == "StateObservation"
        and row["props"].get("state_kind") in {"driver_program", "driver_status"}
    ]
    programs = [row for row in states if row["props"]["state_kind"] == "driver_program"]
    statuses = [row for row in states if row["props"]["state_kind"] == "driver_status"]
    assert len(programs) == 8
    assert all("Chương trình vận hành" in row["props"]["name"] for row in programs)
    assert all("không phải loại phương tiện" in row["props"]["description"] for row in programs)
    assert {row["props"]["name"] for row in statuses} == {
        "Trạng thái active của Giang",
        "Trạng thái suspended của Giang",
    }
    active = next(row for row in statuses if row["props"]["value"] == "active")
    suspended = next(row for row in statuses if row["props"]["value"] == "suspended")
    boundary = "2026-09-17T17:00:00.000000Z"
    assert f"đến trước {boundary}" in active["props"]["description"]
    assert f"từ {boundary}" in suspended["props"]["description"]


def test_v03_semantic_inputs_are_a_plan_not_vector_generation(dataset):
    inputs = build_semantic_node_inputs(dataset)
    assert len(inputs) == 23
    assert Counter(row["node_type"] for row in inputs) == {
        "Complaint": 11,
        "Incident": 4,
        "MaintenanceEvent": 8,
    }
    assert all("vector" not in row for row in inputs)


def test_v03_two_clean_candidates_are_logically_identical(dataset, tmp_path):
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
