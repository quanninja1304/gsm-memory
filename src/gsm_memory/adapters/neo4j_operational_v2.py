"""Idempotent Neo4j persistence for the experimental Operational KG v2.

This adapter accepts only a verified materialized candidate.  It never reads
the frozen release directly, never calls a provider, and never touches nodes
outside the ``GSMOperationalV2`` marker label.
"""

from __future__ import annotations

import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from gsm_memory.data.operational_mock import (
    OperationalMockDataset,
    load_operational_mock,
    verify_operational_mock_candidate,
)
from gsm_memory.data.operational_v2_contract import OperationalKGv2Contract


MARKER_LABEL = "GSMOperationalV2"
ONTOLOGY_VERSION = "gsm-operational-kg-v2"
_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
def _safe_identifier(value: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"unsafe Neo4j identifier: {value!r}")
    return value


def _credentials(prefix: str) -> tuple[str, tuple[str, str], str | None]:
    def required(suffix: str) -> str:
        key = f"{prefix}_{suffix}"
        value = os.getenv(key)
        if not value:
            raise RuntimeError(f"missing environment variable: {key}")
        return value

    uri = required("URI")
    username = os.getenv(f"{prefix}_USERNAME") or os.getenv(f"{prefix}_USER")
    if not username:
        raise RuntimeError(f"missing environment variable: {prefix}_USERNAME")
    return uri, (username, required("PASSWORD")), os.getenv(f"{prefix}_DATABASE") or None


def _batches(rows: list[dict[str, Any]], size: int = 250) -> Iterable[list[dict[str, Any]]]:
    for offset in range(0, len(rows), size):
        yield rows[offset : offset + size]


def _expected_state(
    dataset: OperationalMockDataset,
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, dict[str, Any]]]:
    nodes = {(row["label"], row["id"]): row["props"] for row in dataset.nodes}
    edges = {row["id"]: row for row in dataset.edges}
    if len(nodes) != len(dataset.nodes) or len(edges) != len(dataset.edges):
        raise ValueError("candidate contains duplicate Neo4j identity")
    return nodes, edges


def _existing_state(
    session: Any,
    marker_label: str = MARKER_LABEL,
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, dict[str, Any]]]:
    marker_label = _safe_identifier(marker_label)
    node_rows = session.run(
        f"MATCH (n:{marker_label}) "
        "RETURN labels(n) AS labels, n.id AS id, properties(n) AS props"
    ).data()
    nodes: dict[tuple[str, str], dict[str, Any]] = {}
    for row in node_rows:
        labels = sorted(label for label in row["labels"] if label != marker_label)
        if len(labels) != 1:
            raise RuntimeError(
                f"v2 node must have exactly one business label: {row['labels']}"
            )
        key = (labels[0], row["id"])
        if key in nodes:
            raise RuntimeError(f"duplicate v2 node: {key}")
        nodes[key] = row["props"]

    edge_rows = session.run(
        f"MATCH (a:{marker_label})-[r]->(b:{marker_label}) "
        "RETURN type(r) AS type, r.id AS id, labels(a) AS start_labels, "
        "a.id AS start_id, labels(b) AS end_labels, b.id AS end_id, "
        "properties(r) AS props"
    ).data()
    edges: dict[str, dict[str, Any]] = {}
    for row in edge_rows:
        edge_id = row["id"]
        if not edge_id:
            raise RuntimeError(f"v2 relationship has no stable id: {row['type']}")
        if edge_id in edges:
            raise RuntimeError(f"duplicate v2 relationship id: {edge_id}")
        start_labels = sorted(
            label for label in row["start_labels"] if label != marker_label
        )
        end_labels = sorted(
            label for label in row["end_labels"] if label != marker_label
        )
        if len(start_labels) != 1 or len(end_labels) != 1:
            raise RuntimeError(f"invalid labels around v2 relationship: {edge_id}")
        edges[edge_id] = {
            "type": row["type"],
            "id": edge_id,
            "start_label": start_labels[0],
            "start_id": row["start_id"],
            "end_label": end_labels[0],
            "end_id": row["end_id"],
            "props": row["props"],
        }
    return nodes, edges


def _compare_state(
    session: Any,
    dataset: OperationalMockDataset,
    marker_label: str = MARKER_LABEL,
) -> dict[str, Any]:
    expected_nodes, expected_edges = _expected_state(dataset)
    actual_nodes, actual_edges = _existing_state(session, marker_label)

    missing_nodes = sorted(
        ({"label": key[0], "id": key[1]} for key in expected_nodes.keys() - actual_nodes.keys()),
        key=lambda row: (row["label"], row["id"]),
    )
    unexpected_nodes = sorted(
        ({"label": key[0], "id": key[1]} for key in actual_nodes.keys() - expected_nodes.keys()),
        key=lambda row: (row["label"], row["id"]),
    )
    mismatched_nodes = sorted(
        (
            {"label": key[0], "id": key[1]}
            for key in expected_nodes.keys() & actual_nodes.keys()
            if actual_nodes[key] != expected_nodes[key]
        ),
        key=lambda row: (row["label"], row["id"]),
    )

    missing_edges = sorted(
        ({"type": expected_edges[key]["type"], "id": key} for key in expected_edges.keys() - actual_edges.keys()),
        key=lambda row: (row["type"], row["id"]),
    )
    unexpected_edges = sorted(
        ({"type": actual_edges[key]["type"], "id": key} for key in actual_edges.keys() - expected_edges.keys()),
        key=lambda row: (row["type"], row["id"]),
    )
    mismatched_edges = sorted(
        (
            {"type": expected_edges[key]["type"], "id": key}
            for key in expected_edges.keys() & actual_edges.keys()
            if actual_edges[key] != expected_edges[key]
        ),
        key=lambda row: (row["type"], row["id"]),
    )
    return {
        "missing_nodes": missing_nodes,
        "unexpected_nodes": unexpected_nodes,
        "mismatched_nodes": mismatched_nodes,
        "missing_edges": missing_edges,
        "unexpected_edges": unexpected_edges,
        "mismatched_edges": mismatched_edges,
    }


def _failure_count(verification: dict[str, Any]) -> int:
    return sum(len(rows) for rows in verification.values())


def _create_constraints(session: Any, marker_label: str = MARKER_LABEL) -> None:
    marker_label = _safe_identifier(marker_label)
    prefix = marker_label.lower()
    session.run(
        f"CREATE CONSTRAINT {prefix}_id IF NOT EXISTS "
        f"FOR (n:{marker_label}) REQUIRE n.id IS UNIQUE"
    ).consume()
    for suffix, properties in (
        ("name", "n.name"),
        ("trip_time_outcome", "n.event_time, n.outcome"),
        ("event_time", "n.event_time"),
        ("category", "n.category"),
        ("definition_window", "n.definition_id, n.window_start, n.window_end"),
    ):
        session.run(
            f"CREATE INDEX {prefix}_{suffix} IF NOT EXISTS "
            f"FOR (n:{marker_label}) ON ({properties})"
        ).consume()


def _insert_missing(
    session: Any,
    dataset: OperationalMockDataset,
    before: dict[str, Any],
    contract: OperationalKGv2Contract,
    marker_label: str = MARKER_LABEL,
) -> None:
    marker_label = _safe_identifier(marker_label)
    missing_node_keys = {(row["label"], row["id"]) for row in before["missing_nodes"]}
    missing_edge_ids = {row["id"] for row in before["missing_edges"]}
    node_labels = [_safe_identifier(spec.name) for spec in contract.nodes]
    relationship_types = [_safe_identifier(spec.name) for spec in contract.relationships]

    def write(tx: Any) -> None:
        for label in node_labels:
            rows = [
                row
                for row in dataset.nodes
                if row["label"] == label and (label, row["id"]) in missing_node_keys
            ]
            for batch in _batches(rows):
                tx.run(
                    f"UNWIND $rows AS row "
                    f"MERGE (n:{marker_label}:{label} {{id: row.id}}) "
                    "ON CREATE SET n += row.props",
                    rows=batch,
                ).consume()

        for rel_type in relationship_types:
            grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
            for row in dataset.edges:
                if row["type"] == rel_type and row["id"] in missing_edge_ids:
                    grouped[(row["start_label"], row["end_label"])].append(row)
            for (start_label, end_label), rows in grouped.items():
                start_label = _safe_identifier(start_label)
                end_label = _safe_identifier(end_label)
                for batch in _batches(rows):
                    tx.run(
                        f"UNWIND $rows AS row "
                        f"MATCH (a:{marker_label}:{start_label} {{id: row.start_id}}) "
                        f"MATCH (b:{marker_label}:{end_label} {{id: row.end_id}}) "
                        f"MERGE (a)-[r:{rel_type} {{id: row.id}}]->(b) "
                        "ON CREATE SET r += row.props",
                        rows=batch,
                    ).consume()

    session.execute_write(write)


def ingest_operational_v2(
    candidate: Path,
    *,
    contract_path: Path = Path("configs/benchmark/operational-kg-v2.json"),
    env_prefix: str | None = None,
) -> dict[str, Any]:
    from neo4j import GraphDatabase

    candidate_report = verify_operational_mock_candidate(
        candidate, contract_path=contract_path
    )
    if candidate_report["status"] != "pass":
        return {
            "status": "fail",
            "stage": "candidate_verification",
            "candidate_verification": candidate_report,
        }
    dataset = load_operational_mock(candidate)
    contract = OperationalKGv2Contract.load(contract_path)
    marker_label = contract.runtime_stores.neo4j.marker_label
    env_prefix = env_prefix or contract.runtime_stores.neo4j.env_prefix
    uri, auth, database = _credentials(env_prefix)
    driver = GraphDatabase.driver(uri, auth=auth)
    try:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            _create_constraints(session, marker_label)
            before = _compare_state(session, dataset, marker_label)
            conflicts = (
                before["unexpected_nodes"]
                + before["mismatched_nodes"]
                + before["unexpected_edges"]
                + before["mismatched_edges"]
            )
            if conflicts:
                return {
                    "status": "fail",
                    "stage": "preflight",
                    "candidate_digest": dataset.logical_digest,
                    "verification": before,
                }
            _insert_missing(session, dataset, before, contract, marker_label)
            after = _compare_state(session, dataset, marker_label)
    finally:
        driver.close()

    return {
        "status": "pass" if _failure_count(after) == 0 else "fail",
        "ontology_version": contract.contract_version,
        "marker_label": marker_label,
        "dataset_version": dataset.dataset_version,
        "candidate_digest": dataset.logical_digest,
        "projection_counts": dataset.counts,
        "created_nodes": len(before["missing_nodes"]),
        "created_edges": len(before["missing_edges"]),
        "unchanged_nodes": len(dataset.nodes) - len(before["missing_nodes"]),
        "unchanged_edges": len(dataset.edges) - len(before["missing_edges"]),
        "verification": after,
    }


def verify_operational_v2(
    candidate: Path,
    *,
    contract_path: Path = Path("configs/benchmark/operational-kg-v2.json"),
    env_prefix: str | None = None,
) -> dict[str, Any]:
    from neo4j import GraphDatabase

    candidate_report = verify_operational_mock_candidate(
        candidate, contract_path=contract_path
    )
    if candidate_report["status"] != "pass":
        return {
            "status": "fail",
            "stage": "candidate_verification",
            "candidate_verification": candidate_report,
        }
    dataset = load_operational_mock(candidate)
    contract = OperationalKGv2Contract.load(contract_path)
    marker_label = contract.runtime_stores.neo4j.marker_label
    env_prefix = env_prefix or contract.runtime_stores.neo4j.env_prefix
    uri, auth, database = _credentials(env_prefix)
    driver = GraphDatabase.driver(uri, auth=auth)
    try:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            verification = _compare_state(session, dataset, marker_label)
    finally:
        driver.close()
    return {
        "status": "pass" if _failure_count(verification) == 0 else "fail",
        "ontology_version": contract.contract_version,
        "marker_label": marker_label,
        "dataset_version": dataset.dataset_version,
        "candidate_digest": dataset.logical_digest,
        "projection_counts": dataset.counts,
        "verification": verification,
    }


def query_operational_v2_smoke(
    candidate: Path,
    *,
    contract_path: Path = Path("configs/benchmark/operational-kg-v2.json"),
    env_prefix: str | None = None,
) -> dict[str, Any]:
    """Run bounded representative business traversals against the v2 graph."""

    from neo4j import GraphDatabase

    candidate_report = verify_operational_mock_candidate(
        candidate, contract_path=contract_path
    )
    if candidate_report["status"] != "pass":
        return {
            "status": "fail",
            "stage": "candidate_verification",
            "candidate_verification": candidate_report,
        }
    dataset = load_operational_mock(candidate)
    contract = OperationalKGv2Contract.load(contract_path)
    marker = _safe_identifier(contract.runtime_stores.neo4j.marker_label)
    env_prefix = env_prefix or contract.runtime_stores.neo4j.env_prefix
    uri, auth, database = _credentials(env_prefix)
    driver = GraphDatabase.driver(uri, auth=auth)
    queries = {
        "driver_trip": (
            f"MATCH (d:{marker}:Driver)-[:PERFORMED]->(t:{marker}:Trip) "
            "RETURN count(DISTINCT d) AS drivers_with_trips, count(t) AS trips"
        ),
        "complaint": (
            f"MATCH (d:{marker}:Driver)-[:RECEIVED_COMPLAINT]->"
            f"(c:{marker}:Complaint)-[:ABOUT_TRIP]->(t:{marker}:Trip) "
            "RETURN count(c) AS complaints, count(DISTINCT t) AS affected_trips"
        ),
        "maintenance": (
            f"MATCH (d:{marker}:Driver)-[:OPERATED]->(v:{marker}:Vehicle)"
            f"-[:UNDERWENT]->(m:{marker}:MaintenanceEvent) "
            "RETURN count(DISTINCT d) AS drivers, count(DISTINCT m) AS events"
        ),
        "policy_provenance": (
            f"MATCH (r:{marker}:PolicyRule)-[:DEFINED_IN]->"
            f"(c:{marker}:PolicyClause)<-[:CONTAINS]-"
            f"(p:{marker}:PolicyDocument) "
            "RETURN count(DISTINCT r) AS rules, count(DISTINCT c) AS clauses, "
            "count(DISTINCT p) AS documents"
        ),
        "finding_decision": (
            f"MATCH (d:{marker}:Driver)-[:HAS_FINDING]->"
            f"(f:{marker}:ViolationFinding)-[:EVALUATED_AGAINST]->"
            f"(r:{marker}:PolicyRule), "
            f"(d)-[:RECEIVED_DECISION]->(x:{marker}:EnforcementDecision)"
            f"-[:BASED_ON]->(f), (x)-[:APPLIES_ACTION]->(a:{marker}:PolicyAction) "
            "RETURN count(DISTINCT f) AS findings, count(DISTINCT x) AS decisions"
        ),
    }
    node_labels = set(dataset.counts["node_labels"])
    if "Shift" in node_labels:
        queries["shift_zone"] = (
            f"MATCH (d:{marker}:Driver)-[:WORKED_SHIFT]->(s:{marker}:Shift) "
            f"WHERE (s)-[:CONTAINS_TRIP]->(:{marker}:Trip) "
            f"AND (s)-[:OPERATED_IN]->(:{marker}:Zone) "
            "RETURN count(DISTINCT s) AS shifts"
        )
    if "DriverSummary" in node_labels:
        queries["driver_summary"] = (
            f"MATCH (d:{marker}:Driver)-[:HAS_SUMMARY]->"
            f"(s:{marker}:DriverSummary) "
            "RETURN count(s) AS summaries, sum(s.trip_count) AS represented_trips"
        )
    if dataset.dataset_version in {
        "gsm-operational-mock-v0.2",
        "gsm-operational-mock-v0.3",
    }:
        queries["incident_trip"] = (
            f"MATCH (d:{marker}:Driver)-[:HAS_INCIDENT]->(i:{marker}:Incident)"
            f"-[:ABOUT_TRIP]->(t:{marker}:Trip), "
            f"(i)-[:HAS_STATE]->(s:{marker}:StateObservation) "
            "WHERE i.source_kind = 'synthetic_extension' "
            "RETURN count(DISTINCT i) AS incidents, count(DISTINCT t) AS trips, "
            "count(DISTINCT s) AS states"
        )
    try:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            results = {name: session.run(query).single().data() for name, query in queries.items()}
    finally:
        driver.close()

    expected = {
        "driver_trip": {"drivers_with_trips": 7, "trips": 80},
        "complaint": {"complaints": 11, "affected_trips": 11},
        "maintenance": {"drivers": 8, "events": 8},
        "policy_provenance": {"rules": 4, "clauses": 13, "documents": 4},
        "finding_decision": {"findings": 4, "decisions": 4},
    }
    if "Shift" in node_labels:
        expected["shift_zone"] = {"shifts": dataset.counts["node_labels"]["Shift"]}
    if "DriverSummary" in node_labels:
        expected["driver_summary"] = {"summaries": 8, "represented_trips": 80}
    if dataset.dataset_version in {
        "gsm-operational-mock-v0.2",
        "gsm-operational-mock-v0.3",
    }:
        expected["incident_trip"] = {
            "incidents": 4,
            "trips": 4,
            "states": 7 if dataset.dataset_version == "gsm-operational-mock-v0.3" else 4,
        }
    mismatches = {
        name: {"expected": expected[name], "actual": result}
        for name, result in results.items()
        if result != expected[name]
    }
    return {
        "status": "pass" if not mismatches else "fail",
        "ontology_version": contract.contract_version,
        "marker_label": marker,
        "dataset_version": dataset.dataset_version,
        "candidate_digest": dataset.logical_digest,
        "results": results,
        "mismatches": mismatches,
    }
