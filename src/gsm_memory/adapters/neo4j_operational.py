"""Deterministic MVP operational KG projection for Neo4j.

The projection reads public frozen artifacts only.  It deliberately excludes
documents, policy artifacts, Graphiti, embeddings, and private evaluation data.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from gsm_memory.data.ledger import AcceptedAssertion, reduce_prefix
from gsm_memory.data.primitives import canonical_bytes


MARKER_LABEL = "GSMOperationalV1"
ONTOLOGY_VERSION = "gsm-operational-kg-v1"
ENTITY_LABELS = {
    "DRIVER": "Driver",
    "FLEET": "Fleet",
    "REGION": "Region",
    "SERVICE": "Service",
    "INCIDENT": "Incident",
}
NODE_LABELS = (*ENTITY_LABELS.values(), "Trip", "Measurement", "StateObservation")
DIRECT_RELATIONSHIPS = {
    "MEMBER_OF": ("Driver", "Fleet", "MEMBER_OF"),
    "BASED_IN": ("Fleet", "Region", "BASED_IN"),
    "OPERATES_IN": ("Driver", "Region", "OPERATES_IN"),
    "USES_SERVICE": ("Driver", "Service", "USES_SERVICE"),
    "HAS_INCIDENT": ("Driver", "Incident", "HAS_INCIDENT"),
}
STATE_KINDS = {
    "DRIVER_STATUS": "driver_status",
    "DRIVER_PROGRAM": "driver_program",
    "INCIDENT_STATUS": "incident_status",
}
RELATIONSHIP_TYPES = (
    *{value[2] for value in DIRECT_RELATIONSHIPS.values()},
    "PERFORMED",
    "FOR_SERVICE",
    "IN_REGION",
    "HAS_MEASUREMENT",
    "HAS_STATE",
)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]


def _without_none(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item is not None}


def _object_value(obj: dict[str, Any]) -> Any:
    if "value" in obj:
        return obj["value"]
    key = {
        "entity_ref": "string_value",
        "string": "string_value",
        "enum": "string_value",
        "integer": "integer_value",
        "boolean": "boolean_value",
        "rational": "rational_value",
    }.get(obj.get("type"))
    if key is None or obj.get(key) is None:
        raise ValueError(f"unsupported typed object: {obj!r}")
    return obj[key]


def _display_value(value: Any) -> str:
    if isinstance(value, dict) and set(value) == {"d", "n"}:
        return f'{value["n"]}/{value["d"]}'
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _valid_properties(valid: dict[str, Any]) -> dict[str, Any]:
    kind = valid["kind"]
    if kind == "point":
        return {"valid_kind": kind, "valid_at": valid["at"]}
    if kind == "interval":
        to = valid.get("to") or {}
        return {
            "valid_kind": kind,
            "valid_from": valid["from"],
            "valid_to": to.get("at") if to.get("kind") == "finite" else None,
        }
    if kind == "not_applicable":
        return {"valid_kind": kind}
    raise ValueError(f"unsupported valid kind: {kind!r}")


def _description(label: str, name: str) -> str:
    descriptions = {
        "Driver": f"Tài xế tổng hợp {name} trong bộ benchmark",
        "Fleet": f"Đội xe hoặc depot tổng hợp {name}",
        "Region": f"Khu vực tổng hợp {name}",
        "Service": f"Loại dịch vụ tổng hợp {name}",
        "Incident": f"Sự cố tổng hợp {name}",
    }
    return descriptions[label]


@dataclass(frozen=True)
class OperationalProjection:
    dataset_version: str
    snapshot_id: str
    nodes: tuple[dict[str, Any], ...]
    edges: tuple[dict[str, Any], ...]
    excluded_predicate_counts: dict[str, int]

    @property
    def counts(self) -> dict[str, Any]:
        node_counts: dict[str, int] = defaultdict(int)
        edge_counts: dict[str, int] = defaultdict(int)
        for row in self.nodes:
            node_counts[row["label"]] += 1
        for row in self.edges:
            edge_counts[row["type"]] += 1
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "node_labels": dict(sorted(node_counts.items())),
            "relationship_types": dict(sorted(edge_counts.items())),
        }


def _selected_assertions(
    view: list[AcceptedAssertion], sources: dict[str, dict[str, Any]]
) -> list[tuple[AcceptedAssertion, str]]:
    grouped: dict[str, list[AcceptedAssertion]] = defaultdict(list)
    for item in view:
        grouped[item.payload["logical_fact_id"]].append(item)
    selected: list[tuple[AcceptedAssertion, str]] = []
    for items in grouped.values():
        selected.extend((item, "superseded") for item in items if item.known_to is not None)
        active = [item for item in items if item.known_to is None]
        if not active:
            continue
        best_rank = min(sources[item.source_id]["authority_rank"] for item in active)
        top = [item for item in active if sources[item.source_id]["authority_rank"] == best_rank]
        values = {canonical_bytes(item.payload["object"]) for item in top}
        status = "unresolved_conflict" if len(values) > 1 else "accepted"
        selected.extend((item, status) for item in top)
    return sorted(selected, key=lambda pair: pair[0].payload["assertion_id"])


def project_operational_snapshot(release: Path, snapshot_id: str) -> OperationalProjection:
    release = release.resolve()
    snapshot_dir = release / "public" / "snapshots" / snapshot_id
    manifest = json.loads((snapshot_dir / "manifest.json").read_text("utf-8"))
    if manifest.get("snapshot_id") != snapshot_id or manifest.get("dataset_version") != release.name:
        raise ValueError(f"snapshot manifest mismatch: {snapshot_id}")
    # Use the canonical JSON observation form for reduction.  The Parquet
    # projection expands nullable union fields and is logically equivalent,
    # but that expanded in-memory shape is not the payload shape whose hash is
    # recorded in the immutable ledger.
    records = _jsonl(snapshot_dir / "text_observations.jsonl")
    sources_list = _jsonl(snapshot_dir / "source_registry.jsonl")
    sources = {row["source_id"]: row for row in sources_list}
    catalog_rows = _jsonl(snapshot_dir / "entity_catalog.jsonl")
    catalog = {row["entity_id"]: row for row in catalog_rows}
    if len(catalog) != len(catalog_rows):
        raise ValueError(f"duplicate entity catalog ID: {snapshot_id}")

    view = reduce_prefix(records, sources, manifest["known_as_of"])
    chosen = _selected_assertions(view, sources)
    supported = set(DIRECT_RELATIONSHIPS) | set(STATE_KINDS) | {
        "TRIP_OUTCOME",
        "REPORTED_MEASURE",
    }
    excluded: dict[str, int] = defaultdict(int)
    for item, _ in chosen:
        if item.payload["predicate"] not in supported:
            excluded[item.payload["predicate"]] += 1

    nodes: dict[tuple[str, str], dict[str, Any]] = {}
    for entity_id, row in sorted(catalog.items()):
        label = ENTITY_LABELS.get(row["entity_type"])
        if label is None:
            continue
        name = (row.get("name") or {}).get("text") or f"{label} {entity_id[:8]}"
        nodes[(label, entity_id)] = {
            "label": label,
            "id": entity_id,
            "props": {"id": entity_id, "name": name, "description": _description(label, name)},
        }

    edges: list[dict[str, Any]] = []

    def require_label(entity_id: str, expected: str) -> None:
        actual = ENTITY_LABELS.get(catalog.get(entity_id, {}).get("entity_type"))
        if actual != expected:
            raise ValueError(f"expected {expected} for {entity_id}, got {actual}")

    def add_edge(
        rel_type: str,
        start_label: str,
        start_id: str,
        end_label: str,
        end_id: str,
        item: AcceptedAssertion,
        status: str,
    ) -> None:
        assertion = item.payload
        props = {
            "snapshot_id": snapshot_id,
            "evidence_ref": assertion["assertion_id"],
            "event_time": assertion.get("event_time"),
            "known_from": item.known_from,
            "known_to": item.known_to,
            "resolution_status": status,
            **_valid_properties(assertion["valid"]),
        }
        edges.append({
            "type": rel_type,
            "start_label": start_label,
            "start_id": start_id,
            "end_label": end_label,
            "end_id": end_id,
            "props": _without_none(props),
        })

    for item, status in chosen:
        assertion = item.payload
        predicate = assertion["predicate"]
        if predicate not in supported:
            continue
        subject_id = assertion["subject_id"]
        object_value = _object_value(assertion["object"])

        if predicate in DIRECT_RELATIONSHIPS:
            start_label, end_label, rel_type = DIRECT_RELATIONSHIPS[predicate]
            require_label(subject_id, start_label)
            require_label(str(object_value), end_label)
            add_edge(rel_type, start_label, subject_id, end_label, str(object_value), item, status)
            continue

        if predicate in STATE_KINDS:
            start_label = "Incident" if predicate == "INCIDENT_STATUS" else "Driver"
            require_label(subject_id, start_label)
            state_id = assertion["assertion_id"]
            value = _display_value(object_value)
            kind = STATE_KINDS[predicate]
            nodes[("StateObservation", state_id)] = {
                "label": "StateObservation",
                "id": state_id,
                "props": {
                    "id": state_id,
                    "name": f"{kind} — {value}",
                    "description": f"Quan sát {kind}={value} của {catalog[subject_id]['name']['text']}",
                    "state_kind": kind,
                    "value": value,
                },
            }
            add_edge("HAS_STATE", start_label, subject_id, "StateObservation", state_id, item, status)
            continue

        if predicate == "REPORTED_MEASURE":
            require_label(subject_id, "Driver")
            measurement_id = assertion["assertion_id"]
            qualifiers = assertion["qualifiers"]
            value = _display_value(object_value)
            definition = qualifiers["definition_id"]
            window = f'[{qualifiers["window_start"]},{qualifiers["window_end"]})'
            nodes[("Measurement", measurement_id)] = {
                "label": "Measurement",
                "id": measurement_id,
                "props": _without_none({
                    "id": measurement_id,
                    "name": f"{definition} — {window}",
                    "description": f"{definition} được báo cáo cho {catalog[subject_id]['name']['text']} trong {window}",
                    "definition_id": definition,
                    "definition_version": qualifiers["definition_version"],
                    "value": value,
                    "value_type": assertion["object"]["type"],
                    "unit": qualifiers.get("unit"),
                    "window_start": qualifiers["window_start"],
                    "window_end": qualifiers["window_end"],
                    "reported_status": qualifiers["reported_status"],
                    "undefined_reason": qualifiers.get("undefined_reason"),
                    "calendar_id": qualifiers.get("calendar_id"),
                    "timezone": qualifiers.get("timezone"),
                }),
            }
            add_edge("HAS_MEASUREMENT", "Driver", subject_id, "Measurement", measurement_id, item, status)
            continue

        if predicate == "TRIP_OUTCOME":
            require_label(subject_id, "Driver")
            require_label(str(object_value), "Service")
            qualifiers = assertion["qualifiers"]
            trip_id = qualifiers["trip_id"]
            region_id = qualifiers["region_id"]
            require_label(region_id, "Region")
            short_id = trip_id.split("-")[0]
            nodes[("Trip", trip_id)] = {
                "label": "Trip",
                "id": trip_id,
                "props": _without_none({
                    "id": trip_id,
                    "name": f"Chuyến {short_id}",
                    "description": f'Chuyến terminal tổng hợp, kết quả {qualifiers["outcome"]}',
                    "event_time": assertion.get("event_time"),
                    "outcome": qualifiers["outcome"],
                    "reason_code": qualifiers.get("reason_code"),
                }),
            }
            add_edge("PERFORMED", "Driver", subject_id, "Trip", trip_id, item, status)
            add_edge("FOR_SERVICE", "Trip", trip_id, "Service", str(object_value), item, status)
            add_edge("IN_REGION", "Trip", trip_id, "Region", region_id, item, status)

    node_rows = tuple(sorted(nodes.values(), key=lambda row: (row["label"], row["id"])))
    edge_rows = tuple(sorted(
        edges,
        key=lambda row: (
            row["type"], row["start_id"], row["end_id"],
            row["props"]["snapshot_id"], row["props"]["evidence_ref"],
        ),
    ))
    node_keys = {(row["label"], row["id"]) for row in node_rows}
    if len(node_keys) != len(node_rows):
        raise ValueError("duplicate operational node key")
    edge_keys = {
        (row["type"], row["start_id"], row["end_id"], row["props"]["snapshot_id"], row["props"]["evidence_ref"])
        for row in edge_rows
    }
    if len(edge_keys) != len(edge_rows):
        raise ValueError("duplicate operational edge key")
    return OperationalProjection(
        dataset_version=release.name,
        snapshot_id=snapshot_id,
        nodes=node_rows,
        edges=edge_rows,
        excluded_predicate_counts=dict(sorted(excluded.items())),
    )


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
    password = required("PASSWORD")
    database = os.getenv(f"{prefix}_DATABASE") or None
    return uri, (username, password), database


def _batches(rows: list[dict[str, Any]], size: int = 250) -> Iterable[list[dict[str, Any]]]:
    for offset in range(0, len(rows), size):
        yield rows[offset : offset + size]


def _existing_state(session: Any) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[tuple[str, str, str, str, str], dict[str, Any]]]:
    node_rows = session.run(
        f"MATCH (n:{MARKER_LABEL}) RETURN labels(n) AS labels, n.id AS id, properties(n) AS props"
    ).data()
    nodes: dict[tuple[str, str], dict[str, Any]] = {}
    for row in node_rows:
        labels = [label for label in row["labels"] if label != MARKER_LABEL]
        if len(labels) != 1:
            raise RuntimeError(f"operational node must have one business label: {row['labels']}")
        key = (labels[0], row["id"])
        if key in nodes:
            raise RuntimeError(f"duplicate operational node: {key}")
        nodes[key] = row["props"]

    edge_rows = session.run(
        f"MATCH (a:{MARKER_LABEL})-[r]->(b:{MARKER_LABEL}) "
        "RETURN type(r) AS type, a.id AS start_id, b.id AS end_id, "
        "r.snapshot_id AS snapshot_id, r.evidence_ref AS evidence_ref, properties(r) AS props"
    ).data()
    edges: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for row in edge_rows:
        key = (row["type"], row["start_id"], row["end_id"], row["snapshot_id"], row["evidence_ref"])
        if key in edges:
            raise RuntimeError(f"duplicate operational edge: {key}")
        edges[key] = row["props"]
    return nodes, edges


def _compare_projection(session: Any, projection: OperationalProjection) -> dict[str, Any]:
    existing_nodes, existing_edges = _existing_state(session)
    missing_nodes: list[dict[str, str]] = []
    mismatched_nodes: list[dict[str, Any]] = []
    for row in projection.nodes:
        key = (row["label"], row["id"])
        actual = existing_nodes.get(key)
        if actual is None:
            missing_nodes.append({"label": row["label"], "id": row["id"]})
        elif any(actual.get(name) != value for name, value in row["props"].items()):
            mismatched_nodes.append({"label": row["label"], "id": row["id"]})

    missing_edges: list[dict[str, str]] = []
    mismatched_edges: list[dict[str, Any]] = []
    expected_edge_keys = set()
    for row in projection.edges:
        props = row["props"]
        key = (row["type"], row["start_id"], row["end_id"], props["snapshot_id"], props["evidence_ref"])
        expected_edge_keys.add(key)
        actual = existing_edges.get(key)
        if actual is None:
            missing_edges.append({"type": row["type"], "evidence_ref": props["evidence_ref"]})
        elif any(actual.get(name) != value for name, value in props.items()):
            mismatched_edges.append({"type": row["type"], "evidence_ref": props["evidence_ref"]})
    unexpected_edges = [
        {"type": key[0], "evidence_ref": key[4]}
        for key in existing_edges
        if key[3] == projection.snapshot_id and key not in expected_edge_keys
    ]
    return {
        "missing_nodes": missing_nodes,
        "mismatched_nodes": mismatched_nodes,
        "missing_edges": missing_edges,
        "mismatched_edges": mismatched_edges,
        "unexpected_edges": unexpected_edges,
    }


def _constraints(session: Any) -> None:
    for label in NODE_LABELS:
        session.run(
            f"CREATE CONSTRAINT gsm_operational_v1_{label.lower()}_id IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.id IS UNIQUE"
        ).consume()


def ingest_operational_snapshot(
    release: Path, snapshot_id: str, *, env_prefix: str = "NEO4J_OPERATIONAL"
) -> dict[str, Any]:
    from neo4j import GraphDatabase

    projection = project_operational_snapshot(release, snapshot_id)
    uri, auth, database = _credentials(env_prefix)
    driver = GraphDatabase.driver(uri, auth=auth)
    try:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            _constraints(session)
            before = _compare_projection(session, projection)
            if before["mismatched_nodes"] or before["mismatched_edges"] or before["unexpected_edges"]:
                return {"status": "fail", "stage": "preflight", "snapshot_id": snapshot_id, **before}

            missing_node_keys = {(row["label"], row["id"]) for row in before["missing_nodes"]}
            for label in NODE_LABELS:
                rows = [row for row in projection.nodes if row["label"] == label and (label, row["id"]) in missing_node_keys]
                for batch in _batches(rows):
                    session.run(
                        f"UNWIND $rows AS row MERGE (n:{MARKER_LABEL}:{label} {{id: row.id}}) "
                        "ON CREATE SET n += row.props",
                        rows=batch,
                    ).consume()

            missing_edge_keys = {(row["type"], row["evidence_ref"]) for row in before["missing_edges"]}
            for rel_type in RELATIONSHIP_TYPES:
                rows = [
                    row for row in projection.edges
                    if row["type"] == rel_type
                    and (rel_type, row["props"]["evidence_ref"]) in missing_edge_keys
                ]
                by_labels: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
                for row in rows:
                    by_labels[(row["start_label"], row["end_label"])].append(row)
                for (start_label, end_label), group in by_labels.items():
                    for batch in _batches(group):
                        session.run(
                            f"UNWIND $rows AS row "
                            f"MATCH (a:{MARKER_LABEL}:{start_label} {{id: row.start_id}}) "
                            f"MATCH (b:{MARKER_LABEL}:{end_label} {{id: row.end_id}}) "
                            f"MERGE (a)-[r:{rel_type} {{snapshot_id: row.props.snapshot_id, evidence_ref: row.props.evidence_ref}}]->(b) "
                            "ON CREATE SET r += row.props, r.ingested_at = datetime()",
                            rows=batch,
                        ).consume()
            after = _compare_projection(session, projection)
    finally:
        driver.close()

    failures = sum(len(after[key]) for key in (
        "missing_nodes", "mismatched_nodes", "missing_edges", "mismatched_edges", "unexpected_edges"
    ))
    return {
        "status": "pass" if failures == 0 else "fail",
        "ontology_version": ONTOLOGY_VERSION,
        "dataset_version": projection.dataset_version,
        "snapshot_id": snapshot_id,
        "projection_counts": projection.counts,
        "excluded_predicate_counts": projection.excluded_predicate_counts,
        "created_nodes": len(before["missing_nodes"]),
        "created_edges": len(before["missing_edges"]),
        "unchanged_nodes": len(projection.nodes) - len(before["missing_nodes"]),
        "unchanged_edges": len(projection.edges) - len(before["missing_edges"]),
        "verification": after,
    }


def verify_operational_snapshot(
    release: Path, snapshot_id: str, *, env_prefix: str = "NEO4J_OPERATIONAL"
) -> dict[str, Any]:
    from neo4j import GraphDatabase

    projection = project_operational_snapshot(release, snapshot_id)
    uri, auth, database = _credentials(env_prefix)
    driver = GraphDatabase.driver(uri, auth=auth)
    try:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            result = _compare_projection(session, projection)
    finally:
        driver.close()
    failures = sum(len(value) for value in result.values())
    return {
        "status": "pass" if failures == 0 else "fail",
        "ontology_version": ONTOLOGY_VERSION,
        "dataset_version": projection.dataset_version,
        "snapshot_id": snapshot_id,
        "projection_counts": projection.counts,
        "excluded_predicate_counts": projection.excluded_predicate_counts,
        "verification": result,
    }


def load_operational_projections(release: Path) -> list[OperationalProjection]:
    mode_a = release / "public" / "graph_inputs" / "mode_a"
    snapshot_ids = sorted(path.stem for path in mode_a.glob("*.json"))
    if len(snapshot_ids) != 12:
        raise ValueError(f"expected 12 Mode A snapshots, found {len(snapshot_ids)}")
    return [project_operational_snapshot(release, snapshot_id) for snapshot_id in snapshot_ids]


def _combined_projection_rows(
    projections: list[OperationalProjection],
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[tuple[str, str, str, str, str], dict[str, Any]]]:
    nodes: dict[tuple[str, str], dict[str, Any]] = {}
    edges: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for projection in projections:
        for row in projection.nodes:
            key = (row["label"], row["id"])
            previous = nodes.get(key)
            if previous is not None and previous != row["props"]:
                raise ValueError(f"node differs across snapshots: {key}")
            nodes[key] = row["props"]
        for row in projection.edges:
            props = row["props"]
            key = (
                row["type"], row["start_id"], row["end_id"],
                props["snapshot_id"], props["evidence_ref"],
            )
            if key in edges:
                raise ValueError(f"duplicate full-projection edge: {key}")
            edges[key] = props
    return nodes, edges


def _full_counts(
    nodes: dict[tuple[str, str], dict[str, Any]],
    edges: dict[tuple[str, str, str, str, str], dict[str, Any]],
) -> dict[str, Any]:
    node_labels: dict[str, int] = defaultdict(int)
    relationship_types: dict[str, int] = defaultdict(int)
    for label, _ in nodes:
        node_labels[label] += 1
    for rel_type, *_ in edges:
        relationship_types[rel_type] += 1
    return {
        "nodes": len(nodes),
        "edges": len(edges),
        "node_labels": dict(sorted(node_labels.items())),
        "relationship_types": dict(sorted(relationship_types.items())),
    }


def _compare_full_projection(session: Any, projections: list[OperationalProjection]) -> dict[str, Any]:
    expected_nodes, expected_edges = _combined_projection_rows(projections)
    actual_nodes, actual_edges = _existing_state(session)

    missing_nodes = [
        {"label": key[0], "id": key[1]} for key in expected_nodes.keys() - actual_nodes.keys()
    ]
    unexpected_nodes = [
        {"label": key[0], "id": key[1]} for key in actual_nodes.keys() - expected_nodes.keys()
    ]
    mismatched_nodes = [
        {"label": key[0], "id": key[1]}
        for key in expected_nodes.keys() & actual_nodes.keys()
        if any(actual_nodes[key].get(name) != value for name, value in expected_nodes[key].items())
    ]

    missing_edges = [
        {"type": key[0], "snapshot_id": key[3], "evidence_ref": key[4]}
        for key in expected_edges.keys() - actual_edges.keys()
    ]
    unexpected_edges = [
        {"type": key[0], "snapshot_id": key[3], "evidence_ref": key[4]}
        for key in actual_edges.keys() - expected_edges.keys()
    ]
    mismatched_edges = [
        {"type": key[0], "snapshot_id": key[3], "evidence_ref": key[4]}
        for key in expected_edges.keys() & actual_edges.keys()
        if any(actual_edges[key].get(name) != value for name, value in expected_edges[key].items())
    ]
    return {
        "missing_nodes": sorted(missing_nodes, key=lambda row: (row["label"], row["id"])),
        "unexpected_nodes": sorted(unexpected_nodes, key=lambda row: (row["label"], row["id"])),
        "mismatched_nodes": sorted(mismatched_nodes, key=lambda row: (row["label"], row["id"])),
        "missing_edges": sorted(missing_edges, key=lambda row: (row["snapshot_id"], row["type"], row["evidence_ref"])),
        "unexpected_edges": sorted(unexpected_edges, key=lambda row: (row["snapshot_id"], row["type"], row["evidence_ref"])),
        "mismatched_edges": sorted(mismatched_edges, key=lambda row: (row["snapshot_id"], row["type"], row["evidence_ref"])),
    }


def verify_all_operational_snapshots(
    release: Path, *, env_prefix: str = "NEO4J_OPERATIONAL"
) -> dict[str, Any]:
    from neo4j import GraphDatabase

    projections = load_operational_projections(release)
    expected_nodes, expected_edges = _combined_projection_rows(projections)
    uri, auth, database = _credentials(env_prefix)
    driver = GraphDatabase.driver(uri, auth=auth)
    try:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            verification = _compare_full_projection(session, projections)
    finally:
        driver.close()
    failures = sum(len(value) for value in verification.values())
    return {
        "status": "pass" if failures == 0 else "fail",
        "ontology_version": ONTOLOGY_VERSION,
        "dataset_version": release.name,
        "snapshot_count": len(projections),
        "projection_counts": _full_counts(expected_nodes, expected_edges),
        "verification": verification,
    }


def ingest_all_operational_snapshots(
    release: Path, *, env_prefix: str = "NEO4J_OPERATIONAL"
) -> dict[str, Any]:
    projections = load_operational_projections(release)
    receipts: list[dict[str, Any]] = []
    for projection in projections:
        receipt = ingest_operational_snapshot(
            release,
            projection.snapshot_id,
            env_prefix=env_prefix,
        )
        receipts.append(receipt)
        if receipt["status"] != "pass":
            return {
                "status": "fail",
                "stage": "snapshot_ingestion",
                "failed_snapshot_id": projection.snapshot_id,
                "receipts": receipts,
            }
    verification = verify_all_operational_snapshots(release, env_prefix=env_prefix)
    return {
        "status": verification["status"],
        "ontology_version": ONTOLOGY_VERSION,
        "dataset_version": release.name,
        "snapshot_count": len(projections),
        "created_nodes": sum(row["created_nodes"] for row in receipts),
        "created_edges": sum(row["created_edges"] for row in receipts),
        "unchanged_nodes": sum(row["unchanged_nodes"] for row in receipts),
        "unchanged_edges": sum(row["unchanged_edges"] for row in receipts),
        "projection_counts": verification["projection_counts"],
        "receipts": receipts,
        "verification": verification["verification"],
    }
