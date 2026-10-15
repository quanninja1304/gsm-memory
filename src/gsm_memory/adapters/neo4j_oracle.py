"""Deterministic public-ledger oracle projection for Neo4j.

This module deliberately does not import Graphiti or any provider client.  It
materializes the public Mode A inputs with snapshot-local identities so the
result can be used to audit graph construction without leaking private gold.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import pyarrow.parquet as pq


ORACLE_SCHEMA_VERSION = "neo4j-public-ledger-oracle-v1"
EXPECTED_SNAPSHOT_COUNT = 12
_NODE_LABELS = (
    "OracleSnapshot",
    "OracleRecord",
    "OracleAssertion",
    "OracleEntity",
    "OracleValue",
)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _key(dataset_version: str, snapshot_id: str, kind: str, identity: str) -> str:
    return f"{dataset_version}:{snapshot_id}:{kind}:{identity}"


def _safe_public_path(release: Path, relative_path: str) -> Path:
    relative = PurePosixPath(relative_path)
    if (
        relative.is_absolute()
        or "\\" in relative_path
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise ValueError(f"unsafe public path: {relative_path}")
    public = (release / "public").resolve()
    path = release.joinpath(*relative.parts).resolve()
    try:
        path.relative_to(public)
    except ValueError as error:
        raise ValueError(f"oracle input is outside public release: {relative_path}") from error
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _typed_object_value(obj: dict[str, Any]) -> Any:
    value_type = obj.get("type")
    key_by_type = {
        "entity_ref": "string_value",
        "string": "string_value",
        "enum": "string_value",
        "integer": "integer_value",
        "boolean": "boolean_value",
        "rational": "rational_value",
    }
    value_key = key_by_type.get(value_type)
    if value_key is None:
        raise ValueError(f"unsupported assertion object type: {value_type!r}")
    value = obj.get(value_key)
    if value is None:
        raise ValueError(f"assertion object {value_type!r} has no {value_key}")
    return value


def _literal_identity(value_type: str, value: Any) -> str:
    return hashlib.sha256(
        f"{value_type}:{_canonical_json(value)}".encode("utf-8")
    ).hexdigest()


def _display_value(value: Any) -> str:
    if isinstance(value, dict) and set(value) == {"d", "n"}:
        return f'{value["n"]}/{value["d"]}'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    return _canonical_json(value)


def _batches(rows: list[dict[str, Any]], size: int = 500) -> Iterable[list[dict[str, Any]]]:
    for offset in range(0, len(rows), size):
        yield rows[offset : offset + size]


@dataclass(frozen=True)
class OracleProjection:
    dataset_version: str
    snapshot: dict[str, Any]
    records: list[dict[str, Any]]
    assertions: list[dict[str, Any]]
    entities: list[dict[str, Any]]
    values: list[dict[str, Any]]
    targets: list[dict[str, str]]
    projection_digest: str

    @property
    def snapshot_id(self) -> str:
        return str(self.snapshot["snapshot_id"])

    @property
    def counts(self) -> dict[str, int]:
        return {
            "records": len(self.records),
            "assertions": len(self.assertions),
            "entities": len(self.entities),
            "values": len(self.values),
            "oracle_facts": len(self.assertions),
            "revision_targets": len(self.targets),
        }


def project_snapshot(release: Path, mode_a_manifest: Path) -> OracleProjection:
    """Build a deterministic projection from one public Mode A package."""

    release = release.resolve()
    mode_a = json.loads(mode_a_manifest.read_text(encoding="utf-8"))
    if mode_a.get("mode") != "A" or mode_a.get("source_identity_preserved") is not True:
        raise ValueError(f"invalid Mode A manifest: {mode_a_manifest}")
    snapshot_id = str(mode_a["snapshot_id"])
    snapshot_dir = release / "public" / "snapshots" / snapshot_id
    snapshot = json.loads((snapshot_dir / "manifest.json").read_text(encoding="utf-8"))
    if snapshot.get("snapshot_id") != snapshot_id:
        raise ValueError(f"snapshot identity mismatch: {snapshot_id}")
    if snapshot.get("dataset_version") != release.name:
        raise ValueError(f"snapshot dataset version mismatch: {snapshot_id}")
    ledger_path = _safe_public_path(release, str(mode_a["structured_ledger"]))
    if ledger_path != (snapshot_dir / "record_ledger.parquet").resolve():
        raise ValueError(f"Mode A ledger path mismatch: {snapshot_id}")

    ledger_rows = pq.read_table(ledger_path).to_pylist()
    if snapshot.get("record_count") != len(ledger_rows):
        raise ValueError(
            f"snapshot record count mismatch: {snapshot_id}; "
            f'manifest={snapshot.get("record_count")} actual={len(ledger_rows)}'
        )
    catalog_rows = [
        json.loads(line)
        for line in (snapshot_dir / "entity_catalog.jsonl").read_text("utf-8").splitlines()
        if line.strip()
    ]
    catalog = {row["entity_id"]: row for row in catalog_rows}
    if len(catalog) != len(catalog_rows):
        raise ValueError(f"duplicate entity catalog identity: {snapshot_id}")

    dataset_version = release.name
    snapshot_key = _key(dataset_version, snapshot_id, "snapshot", snapshot_id)
    records: list[dict[str, Any]] = []
    assertions: list[dict[str, Any]] = []
    targets: list[dict[str, str]] = []
    entity_ids = set(catalog)
    values_by_key: dict[str, dict[str, Any]] = {}
    record_ids: set[str] = set()
    assertion_ids: set[str] = set()

    for record in sorted(ledger_rows, key=lambda row: row["commit_seq"]):
        record_id = str(record["record_id"])
        if record_id in record_ids:
            raise ValueError(f"duplicate record_id in snapshot {snapshot_id}: {record_id}")
        record_ids.add(record_id)
        record_key = _key(dataset_version, snapshot_id, "record", record_id)
        record_payload = {
            "record_id": record_id,
            "source_id": record["source_id"],
            "scope_id": record["scope_id"],
            "known_at": record["known_at"],
            "commit_seq": record["commit_seq"],
            "operation": record["operation"],
            "target_assertion_ids": record["target_assertion_ids"],
            "raw_payload": record["raw_payload"],
            "payload_hash": record["payload_hash"],
        }
        records.append({
            "oracle_key": record_key,
            "snapshot_key": snapshot_key,
            "dataset_version": dataset_version,
            "snapshot_id": snapshot_id,
            "record_id": record_id,
            "source_id": str(record["source_id"]),
            "scope_id": str(record["scope_id"]),
            "known_at": str(record["known_at"]),
            "commit_seq": int(record["commit_seq"]),
            "operation": str(record["operation"]),
            "target_assertion_ids_json": _canonical_json(record["target_assertion_ids"]),
            "raw_payload_json": _canonical_json(record["raw_payload"]),
            "payload_hash": str(record["payload_hash"]),
            "content_sha256": _digest(record_payload),
        })
        for target_id in record["target_assertion_ids"]:
            targets.append({
                "record_key": record_key,
                "assertion_key": _key(
                    dataset_version, snapshot_id, "assertion", str(target_id)
                ),
                "snapshot_id": snapshot_id,
            })
        for assertion in record["assertions"]:
            assertion_id = str(assertion["assertion_id"])
            if assertion_id in assertion_ids:
                raise ValueError(
                    f"duplicate assertion_id in snapshot {snapshot_id}: {assertion_id}"
                )
            assertion_ids.add(assertion_id)
            subject_id = str(assertion["subject_id"])
            entity_ids.add(subject_id)
            obj = assertion["object"]
            object_type = str(obj["type"])
            object_value = _typed_object_value(obj)
            if object_type == "entity_ref":
                object_id = str(object_value)
                entity_ids.add(object_id)
                object_key = _key(dataset_version, snapshot_id, "entity", object_id)
                object_kind = "entity"
            else:
                literal_id = _literal_identity(object_type, object_value)
                object_key = _key(dataset_version, snapshot_id, "value", literal_id)
                object_kind = "value"
                values_by_key.setdefault(object_key, {
                    "oracle_key": object_key,
                    "dataset_version": dataset_version,
                    "snapshot_id": snapshot_id,
                    "value_type": object_type,
                    "value_json": _canonical_json(object_value),
                    "display_value": _display_value(object_value),
                    "content_sha256": _digest({
                        "type": object_type,
                        "value": object_value,
                    }),
                })
            assertion_payload = {
                "assertion_id": assertion_id,
                "record_id": record_id,
                "source_id": record["source_id"],
                "known_at": record["known_at"],
                "operation": record["operation"],
                "logical_fact_id": assertion["logical_fact_id"],
                "subject_id": subject_id,
                "predicate": assertion["predicate"],
                "object": obj,
                "valid": assertion["valid"],
                "event_time": assertion["event_time"],
                "qualifiers": assertion["qualifiers"],
                "source_refs": assertion["source_refs"],
            }
            content_sha256 = _digest(assertion_payload)
            assertions.append({
                "oracle_key": _key(
                    dataset_version, snapshot_id, "assertion", assertion_id
                ),
                "record_key": record_key,
                "subject_key": _key(
                    dataset_version, snapshot_id, "entity", subject_id
                ),
                "object_key": object_key,
                "object_kind": object_kind,
                "dataset_version": dataset_version,
                "snapshot_id": snapshot_id,
                "assertion_id": assertion_id,
                "record_id": record_id,
                "source_id": str(record["source_id"]),
                "known_at": str(record["known_at"]),
                "operation": str(record["operation"]),
                "logical_fact_id": str(assertion["logical_fact_id"]),
                "subject_id": subject_id,
                "predicate": str(assertion["predicate"]),
                "object_type": object_type,
                "object_json": _canonical_json(obj),
                "valid_json": _canonical_json(assertion["valid"]),
                "event_time": assertion["event_time"],
                "qualifiers_json": _canonical_json(assertion["qualifiers"]),
                "source_refs_json": _canonical_json(assertion["source_refs"]),
                "content_sha256": content_sha256,
            })

    missing_targets = sorted({
        row["assertion_key"] for row in targets
    } - {row["oracle_key"] for row in assertions})
    if missing_targets:
        raise ValueError(
            f"revision targets are absent from snapshot {snapshot_id}: {missing_targets}"
        )

    entities: list[dict[str, Any]] = []
    for entity_id in sorted(entity_ids):
        row = catalog.get(entity_id)
        display_name = None
        entity_type = "UNCLASSIFIED_PUBLIC_ENTITY"
        semantic_code = None
        catalog_json = None
        if row is not None:
            display_name = (row.get("name") or {}).get("text")
            entity_type = str(row["entity_type"])
            semantic_code = row.get("semantic_code")
            catalog_json = _canonical_json(row)
        payload = {
            "canonical_id": entity_id,
            "display_name": display_name,
            "entity_type": entity_type,
            "semantic_code": semantic_code,
            "catalog": row,
        }
        entities.append({
            "oracle_key": _key(dataset_version, snapshot_id, "entity", entity_id),
            "dataset_version": dataset_version,
            "snapshot_id": snapshot_id,
            "canonical_id": entity_id,
            "display_name": display_name,
            "entity_type": entity_type,
            "semantic_code": semantic_code,
            "catalog_json": catalog_json,
            "content_sha256": _digest(payload),
        })

    assertions.sort(key=lambda row: row["oracle_key"])
    records.sort(key=lambda row: row["oracle_key"])
    entities.sort(key=lambda row: row["oracle_key"])
    values = sorted(values_by_key.values(), key=lambda row: row["oracle_key"])
    targets.sort(key=lambda row: (row["record_key"], row["assertion_key"]))
    projection_digest = _digest({
        "snapshot": snapshot,
        "records": [(row["oracle_key"], row["content_sha256"]) for row in records],
        "assertions": [
            (row["oracle_key"], row["content_sha256"]) for row in assertions
        ],
        "entities": [(row["oracle_key"], row["content_sha256"]) for row in entities],
        "values": [(row["oracle_key"], row["content_sha256"]) for row in values],
        "targets": targets,
    })
    return OracleProjection(
        dataset_version=dataset_version,
        snapshot={
            "oracle_key": snapshot_key,
            "dataset_version": dataset_version,
            "snapshot_id": snapshot_id,
            "world_id": str(snapshot["world_id"]),
            "ledger_id": str(snapshot["ledger_id"]),
            "scope_id": str(snapshot["scope_id"]),
            "known_as_of": str(snapshot["known_as_of"]),
            "expected_record_count": int(snapshot["record_count"]),
            "projection_digest": projection_digest,
            "content_sha256": projection_digest,
        },
        records=records,
        assertions=assertions,
        entities=entities,
        values=values,
        targets=targets,
        projection_digest=projection_digest,
    )


def load_oracle_projections(release: Path) -> list[OracleProjection]:
    mode_a_dir = release / "public" / "graph_inputs" / "mode_a"
    manifests = sorted(mode_a_dir.glob("*.json"))
    if len(manifests) != EXPECTED_SNAPSHOT_COUNT:
        raise ValueError(
            f"expected {EXPECTED_SNAPSHOT_COUNT} Mode A snapshots, found {len(manifests)}"
        )
    projections = [project_snapshot(release, path) for path in manifests]
    ids = [item.snapshot_id for item in projections]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate Mode A snapshot identity")
    return projections


def _verify_frozen_source(
    release: Path,
    certificate: Path | None = None,
    comparison: Path | None = None,
) -> dict[str, Any]:
    """Run the repository's read-only frozen verifier before projection."""

    from gsm_memory.data.frozen import verify_frozen_release

    release = release.resolve()
    repository = release.parent.parent
    certificate = certificate or (
        repository / "reports" / "data_freeze" / f"{release.name}-freeze-certificate.json"
    )
    comparison = comparison or (
        repository / "reports" / "data_freeze" / f"{release.name}-logical-comparison.json"
    )
    report = verify_frozen_release(release, certificate, comparison)
    if report["status"] != "pass":
        raise RuntimeError(f"frozen source verification failed: {report}")
    return report


def _neo4j_settings() -> dict[str, str]:
    uri = os.getenv("NEO4J_URI")
    password = os.getenv("NEO4J_PASSWORD")
    if not uri:
        raise RuntimeError("NEO4J_URI is required")
    if not password:
        raise RuntimeError("NEO4J_PASSWORD is required")
    return {
        "uri": uri,
        "user": os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME", "neo4j"),
        "password": password,
        "database": os.getenv("NEO4J_DATABASE", "neo4j"),
    }


def _constraints(session: Any) -> None:
    for label in _NODE_LABELS:
        name = f"{label.lower()}_oracle_key"
        session.run(
            f"CREATE CONSTRAINT {name} IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.oracle_key IS UNIQUE"
        ).consume()
    session.run(
        "CREATE CONSTRAINT oracle_fact_oracle_key IF NOT EXISTS "
        "FOR ()-[r:ORACLE_FACT]-() REQUIRE r.oracle_key IS UNIQUE"
    ).consume()


def _assert_existing_nodes_match(
    session: Any, label: str, rows: list[dict[str, Any]]
) -> None:
    if label not in _NODE_LABELS:
        raise ValueError(f"unsupported oracle label: {label}")
    expected = {row["oracle_key"]: row["content_sha256"] for row in rows}
    for batch in _batches(rows):
        existing = session.run(
            f"MATCH (n:{label}) WHERE n.oracle_key IN $keys "
            "RETURN n.oracle_key AS oracle_key, n.content_sha256 AS content_sha256",
            keys=[row["oracle_key"] for row in batch],
        )
        for record in existing:
            key = record["oracle_key"]
            if record["content_sha256"] != expected[key]:
                raise RuntimeError(f"immutable Oracle conflict for {label} {key}")


def _assert_existing_facts_match(session: Any, assertions: list[dict[str, Any]]) -> None:
    expected = {row["oracle_key"]: row["content_sha256"] for row in assertions}
    for batch in _batches(assertions):
        existing = session.run(
            "MATCH ()-[r:ORACLE_FACT]->() WHERE r.oracle_key IN $keys "
            "RETURN r.oracle_key AS oracle_key, r.content_sha256 AS content_sha256",
            keys=[row["oracle_key"] for row in batch],
        )
        seen: set[str] = set()
        for record in existing:
            key = record["oracle_key"]
            if key in seen:
                raise RuntimeError(f"duplicate immutable Oracle fact: {key}")
            seen.add(key)
            if record["content_sha256"] != expected[key]:
                raise RuntimeError(f"immutable Oracle conflict for fact {key}")


def _preflight_existing(session: Any, projection: OracleProjection) -> None:
    snapshot_row = [{**projection.snapshot, "state": "LOADING"}]
    _assert_existing_nodes_match(session, "OracleSnapshot", snapshot_row)
    _assert_existing_nodes_match(session, "OracleRecord", projection.records)
    _assert_existing_nodes_match(session, "OracleAssertion", projection.assertions)
    _assert_existing_nodes_match(session, "OracleEntity", projection.entities)
    _assert_existing_nodes_match(session, "OracleValue", projection.values)
    _assert_existing_facts_match(session, projection.assertions)


def _write_snapshot(tx: Any, projection: OracleProjection) -> None:
    snapshot = {**projection.snapshot, "state": "LOADING"}
    tx.run(
        "MERGE (n:OracleSnapshot {oracle_key: $row.oracle_key}) "
        "ON CREATE SET n += $row",
        row=snapshot,
    ).consume()
    for label, rows in (
        ("OracleRecord", projection.records),
        ("OracleAssertion", projection.assertions),
        ("OracleEntity", projection.entities),
        ("OracleValue", projection.values),
    ):
        for batch in _batches(rows):
            tx.run(
                f"UNWIND $rows AS row MERGE (n:{label} {{oracle_key: row.oracle_key}}) "
                "ON CREATE SET n += row",
                rows=batch,
            ).consume()

    for batch in _batches(projection.records):
        tx.run(
            "UNWIND $rows AS row "
            "MATCH (s:OracleSnapshot {oracle_key: row.snapshot_key}) "
            "MATCH (r:OracleRecord {oracle_key: row.oracle_key}) "
            "MERGE (s)-[:CONTAINS_RECORD]->(r)",
            rows=batch,
        ).consume()
    for batch in _batches(projection.assertions):
        tx.run(
            "UNWIND $rows AS row "
            "MATCH (r:OracleRecord {oracle_key: row.record_key}) "
            "MATCH (a:OracleAssertion {oracle_key: row.oracle_key}) "
            "MATCH (s:OracleEntity {oracle_key: row.subject_key}) "
            "MERGE (r)-[:ASSERTS]->(a) "
            "MERGE (a)-[:SUBJECT]->(s)",
            rows=batch,
        ).consume()
        entity_rows = [row for row in batch if row["object_kind"] == "entity"]
        value_rows = [row for row in batch if row["object_kind"] == "value"]
        for object_label, object_rows in (
            ("OracleEntity", entity_rows),
            ("OracleValue", value_rows),
        ):
            if not object_rows:
                continue
            tx.run(
                f"UNWIND $rows AS row "
                "MATCH (a:OracleAssertion {oracle_key: row.oracle_key}) "
                f"MATCH (o:{object_label} {{oracle_key: row.object_key}}) "
                "MATCH (s:OracleEntity {oracle_key: row.subject_key}) "
                "MERGE (a)-[:OBJECT]->(o) "
                "MERGE (s)-[f:ORACLE_FACT {oracle_key: row.oracle_key}]->(o) "
                "ON CREATE SET f.dataset_version = row.dataset_version, "
                "f.snapshot_id = row.snapshot_id, f.assertion_id = row.assertion_id, "
                "f.record_id = row.record_id, f.source_id = row.source_id, "
                "f.known_at = row.known_at, f.operation = row.operation, "
                "f.logical_fact_id = row.logical_fact_id, f.predicate = row.predicate, "
                "f.subject_key = row.subject_key, f.object_key = row.object_key, "
                "f.object_type = row.object_type, f.object_json = row.object_json, "
                "f.valid_json = row.valid_json, f.event_time = row.event_time, "
                "f.qualifiers_json = row.qualifiers_json, "
                "f.source_refs_json = row.source_refs_json, "
                "f.content_sha256 = row.content_sha256",
                rows=object_rows,
            ).consume()
    for batch in _batches(projection.targets):
        tx.run(
            "UNWIND $rows AS row "
            "MATCH (r:OracleRecord {oracle_key: row.record_key}) "
            "MATCH (a:OracleAssertion {oracle_key: row.assertion_key}) "
            "MERGE (r)-[:TARGETS]->(a)",
            rows=batch,
        ).consume()


def _snapshot_actual(session: Any, projection: OracleProjection) -> dict[str, Any]:
    snapshot_id = projection.snapshot_id
    dataset_version = projection.dataset_version
    query = (
        "MATCH (n:{label} {{dataset_version: $dataset_version, snapshot_id: $snapshot_id}}) "
        "RETURN count(n) AS count"
    )
    counts = {
        key: session.run(
            query.format(label=label),
            dataset_version=dataset_version,
            snapshot_id=snapshot_id,
        ).single()["count"]
        for key, label in (
            ("records", "OracleRecord"),
            ("assertions", "OracleAssertion"),
            ("entities", "OracleEntity"),
            ("values", "OracleValue"),
        )
    }
    counts["oracle_facts"] = session.run(
        "MATCH ()-[r:ORACLE_FACT {dataset_version: $dataset_version, snapshot_id: $snapshot_id}]->() "
        "RETURN count(r) AS count",
        dataset_version=dataset_version,
        snapshot_id=snapshot_id,
    ).single()["count"]
    counts["revision_targets"] = session.run(
        "MATCH (r:OracleRecord {dataset_version: $dataset_version, snapshot_id: $snapshot_id})"
        "-[:TARGETS]->(:OracleAssertion) RETURN count(*) AS count",
        dataset_version=dataset_version,
        snapshot_id=snapshot_id,
    ).single()["count"]
    structural_counts = {
        "contains_record": session.run(
            "MATCH (:OracleSnapshot {dataset_version: $dataset_version, snapshot_id: $snapshot_id})"
            "-[:CONTAINS_RECORD]->(:OracleRecord) RETURN count(*) AS count",
            dataset_version=dataset_version,
            snapshot_id=snapshot_id,
        ).single()["count"],
        "asserts": session.run(
            "MATCH (:OracleRecord)-[:ASSERTS]->"
            "(:OracleAssertion {dataset_version: $dataset_version, snapshot_id: $snapshot_id}) "
            "RETURN count(*) AS count",
            dataset_version=dataset_version,
            snapshot_id=snapshot_id,
        ).single()["count"],
        "subjects": session.run(
            "MATCH (:OracleAssertion {dataset_version: $dataset_version, snapshot_id: $snapshot_id})"
            "-[:SUBJECT]->(:OracleEntity) RETURN count(*) AS count",
            dataset_version=dataset_version,
            snapshot_id=snapshot_id,
        ).single()["count"],
        "objects": session.run(
            "MATCH (:OracleAssertion {dataset_version: $dataset_version, snapshot_id: $snapshot_id})"
            "-[:OBJECT]->() RETURN count(*) AS count",
            dataset_version=dataset_version,
            snapshot_id=snapshot_id,
        ).single()["count"],
    }
    actual_assertions = {
        row["oracle_key"]: row["content_sha256"]
        for row in session.run(
            "MATCH (a:OracleAssertion {dataset_version: $dataset_version, snapshot_id: $snapshot_id}) "
            "RETURN a.oracle_key AS oracle_key, a.content_sha256 AS content_sha256",
            dataset_version=dataset_version,
            snapshot_id=snapshot_id,
        )
    }
    actual_facts = {
        row["oracle_key"]: (
            row["content_sha256"],
            row["count"],
            row["subject_key"],
            row["object_key"],
        )
        for row in session.run(
            "MATCH (s)-[r:ORACLE_FACT {dataset_version: $dataset_version, snapshot_id: $snapshot_id}]->(o) "
            "RETURN r.oracle_key AS oracle_key, r.content_sha256 AS content_sha256, "
            "s.oracle_key AS subject_key, o.oracle_key AS object_key, "
            "count(*) AS count",
            dataset_version=dataset_version,
            snapshot_id=snapshot_id,
        )
    }
    expected = {row["oracle_key"]: row for row in projection.assertions}
    expected_keys = set(expected)
    actual_keys = set(actual_assertions)
    fact_keys = set(actual_facts)
    missing = sorted(expected_keys - actual_keys | expected_keys - fact_keys)
    unexpected = sorted(actual_keys - expected_keys | fact_keys - expected_keys)
    mismatched = sorted(
        key for key in expected_keys & actual_keys
        if actual_assertions[key] != expected[key]["content_sha256"]
    )
    mismatched.extend(sorted(
        key for key in expected_keys & fact_keys
        if (
            actual_facts[key][0] != expected[key]["content_sha256"]
            or actual_facts[key][1] != 1
            or actual_facts[key][2] != expected[key]["subject_key"]
            or actual_facts[key][3] != expected[key]["object_key"]
        )
    ))
    mismatched = sorted(set(mismatched))
    expected_counts = projection.counts
    count_mismatches = {
        key: {"expected": expected_counts[key], "actual": counts[key]}
        for key in (
            "records", "assertions", "entities", "values", "oracle_facts",
            "revision_targets",
        )
        if expected_counts[key] != counts[key]
    }
    expected_structural = {
        "contains_record": expected_counts["records"],
        "asserts": expected_counts["assertions"],
        "subjects": expected_counts["assertions"],
        "objects": expected_counts["assertions"],
    }
    structural_mismatches = {
        key: {"expected": expected_structural[key], "actual": structural_counts[key]}
        for key in expected_structural
        if expected_structural[key] != structural_counts[key]
    }
    return {
        "snapshot_id": snapshot_id,
        "status": "pass" if not (
            missing or unexpected or mismatched or count_mismatches or structural_mismatches
        ) else "fail",
        "expected": expected_counts,
        "actual": counts,
        "missing": missing,
        "unexpected": unexpected,
        "mismatched": mismatched,
        "count_mismatches": count_mismatches,
        "structural_counts": structural_counts,
        "structural_mismatches": structural_mismatches,
        "projection_digest": projection.projection_digest,
    }


def _mark_complete(session: Any, projection: OracleProjection) -> None:
    session.run(
        "MATCH (s:OracleSnapshot {oracle_key: $oracle_key}) "
        "SET s.state = 'COMPLETE'",
        oracle_key=projection.snapshot["oracle_key"],
    ).consume()


def _verify_all(session: Any, projections: list[OracleProjection]) -> dict[str, Any]:
    snapshots = [_snapshot_actual(session, projection) for projection in projections]
    expected_snapshot_keys = {item.snapshot["oracle_key"] for item in projections}
    actual_snapshots = {
        row["oracle_key"]: row["state"]
        for row in session.run(
            "MATCH (s:OracleSnapshot {dataset_version: $dataset_version}) "
            "RETURN s.oracle_key AS oracle_key, s.state AS state",
            dataset_version=projections[0].dataset_version,
        )
    }
    unexpected_snapshots = sorted(set(actual_snapshots) - expected_snapshot_keys)
    missing_snapshots = sorted(expected_snapshot_keys - set(actual_snapshots))
    incomplete_snapshots = sorted(
        key for key in expected_snapshot_keys & set(actual_snapshots)
        if actual_snapshots[key] != "COMPLETE"
    )
    expected_assertions = {
        row["oracle_key"]: projection.snapshot_id
        for projection in projections
        for row in projection.assertions
    }
    actual_assertion_rows = list(session.run(
        "MATCH (a:OracleAssertion {dataset_version: $dataset_version}) "
        "RETURN a.oracle_key AS oracle_key, a.snapshot_id AS snapshot_id",
        dataset_version=projections[0].dataset_version,
    ))
    actual_assertions = {row["oracle_key"]: row["snapshot_id"] for row in actual_assertion_rows}
    unexpected_assertions = sorted(set(actual_assertions) - set(expected_assertions))
    missing_assertions = sorted(set(expected_assertions) - set(actual_assertions))
    wrong_snapshot = sorted(
        key for key in set(expected_assertions) & set(actual_assertions)
        if expected_assertions[key] != actual_assertions[key]
    )
    actual_fact_rows = list(session.run(
        "MATCH ()-[r:ORACLE_FACT {dataset_version: $dataset_version}]->() "
        "RETURN r.oracle_key AS oracle_key, r.snapshot_id AS snapshot_id, count(*) AS count",
        dataset_version=projections[0].dataset_version,
    ))
    actual_facts = {row["oracle_key"]: row["snapshot_id"] for row in actual_fact_rows}
    unexpected_facts = sorted(set(actual_facts) - set(expected_assertions))
    missing_facts = sorted(set(expected_assertions) - set(actual_facts))
    duplicate_facts = sorted(row["oracle_key"] for row in actual_fact_rows if row["count"] != 1)
    wrong_snapshot.extend(sorted(
        key for key in set(expected_assertions) & set(actual_facts)
        if expected_assertions[key] != actual_facts[key]
    ))
    wrong_snapshot = sorted(set(wrong_snapshot))
    vector_property_count = session.run(
        "MATCH (n) WHERE (n:OracleSnapshot OR n:OracleRecord OR n:OracleAssertion "
        "OR n:OracleEntity OR n:OracleValue) "
        "AND any(k IN keys(n) WHERE toLower(k) CONTAINS 'embedding' OR toLower(k) CONTAINS 'vector') "
        "RETURN count(n) AS count"
    ).single()["count"]
    vector_property_count += session.run(
        "MATCH ()-[r:ORACLE_FACT]->() "
        "WHERE any(k IN keys(r) WHERE toLower(k) CONTAINS 'embedding' OR toLower(k) CONTAINS 'vector') "
        "RETURN count(r) AS count"
    ).single()["count"]
    totals = {
        key: sum(item["actual"][key] for item in snapshots)
        for key in ("records", "assertions", "entities", "values", "oracle_facts")
    }
    failures = [item["snapshot_id"] for item in snapshots if item["status"] != "pass"]
    status = "pass" if not (
        failures
        or missing_snapshots
        or unexpected_snapshots
        or incomplete_snapshots
        or missing_assertions
        or unexpected_assertions
        or missing_facts
        or unexpected_facts
        or duplicate_facts
        or wrong_snapshot
        or vector_property_count
    ) else "fail"
    return {
        "schema_version": ORACLE_SCHEMA_VERSION,
        "status": status,
        "dataset_version": projections[0].dataset_version,
        "snapshot_count": len(actual_snapshots),
        "expected_snapshot_count": len(projections),
        "totals": totals,
        "missing_snapshots": missing_snapshots,
        "unexpected_snapshots": unexpected_snapshots,
        "incomplete_snapshots": incomplete_snapshots,
        "failed_snapshots": failures,
        "missing_assertions": missing_assertions,
        "unexpected_assertions": unexpected_assertions,
        "missing_facts": missing_facts,
        "unexpected_facts": unexpected_facts,
        "duplicate_facts": duplicate_facts,
        "wrong_snapshot": wrong_snapshot,
        "vector_property_count": vector_property_count,
        "provider_usage": {"calls": 0, "tokens": 0, "cost_usd": 0},
        "snapshots": snapshots,
    }


def ingest_oracle(
    release: Path,
    *,
    certificate: Path | None = None,
    comparison: Path | None = None,
) -> dict[str, Any]:
    """Idempotently materialize all public snapshots and verify the result."""

    frozen = _verify_frozen_source(release, certificate, comparison)
    projections = load_oracle_projections(release)
    settings = _neo4j_settings()
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(
        settings["uri"], auth=(settings["user"], settings["password"])
    )
    try:
        driver.verify_connectivity()
        with driver.session(database=settings["database"]) as session:
            _constraints(session)
            for projection in projections:
                _preflight_existing(session, projection)
                session.execute_write(_write_snapshot, projection)
                result = _snapshot_actual(session, projection)
                if result["status"] != "pass":
                    raise RuntimeError(
                        f"Oracle snapshot verification failed: {projection.snapshot_id}: {result}"
                    )
                _mark_complete(session, projection)
            report = _verify_all(session, projections)
    finally:
        driver.close()
    report.update({
        "operation": "ingest",
        "backend": "neo4j",
        "database": settings["database"],
        "projection_mode": "deterministic_public_ledger",
        "openai_required": False,
        "embeddings_created": False,
        "frozen_source": {
            "status": frozen["status"],
            "checked": frozen["checked"],
            "manifest_sha256": frozen["manifest_sha256"],
            "logical_inventory_digest": frozen["logical_inventory_digest"],
        },
    })
    return report


def verify_oracle(
    release: Path,
    *,
    certificate: Path | None = None,
    comparison: Path | None = None,
) -> dict[str, Any]:
    """Read-only comparison of Neo4j Oracle contents with the frozen inputs."""

    frozen = _verify_frozen_source(release, certificate, comparison)
    projections = load_oracle_projections(release)
    settings = _neo4j_settings()
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(
        settings["uri"], auth=(settings["user"], settings["password"])
    )
    try:
        driver.verify_connectivity()
        with driver.session(database=settings["database"]) as session:
            report = _verify_all(session, projections)
    finally:
        driver.close()
    report.update({
        "operation": "verify",
        "backend": "neo4j",
        "database": settings["database"],
        "read_only": True,
        "openai_required": False,
        "embeddings_created": False,
        "frozen_source": {
            "status": frozen["status"],
            "checked": frozen["checked"],
            "manifest_sha256": frozen["manifest_sha256"],
            "logical_inventory_digest": frozen["logical_inventory_digest"],
        },
    })
    return report
