"""Provider-backed embeddings for the 23 reviewed Operational KG v3 nodes.

The frozen release and deterministic candidate remain provider-independent.
This module is a post-ingestion runtime enrichment: it embeds only the reviewed
description inputs, stores vectors on the corresponding Neo4j v3 nodes, creates
one cosine vector index, and verifies exact scope and metadata.
"""

from __future__ import annotations

import hashlib
import math
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from gsm_memory.data.contracts import ClosedModel
from gsm_memory.data.operational_mock import (
    build_semantic_node_inputs,
    load_operational_mock,
    verify_operational_mock_candidate,
)
from gsm_memory.data.operational_v2_contract import OperationalKGv2Contract
from gsm_memory.data.primitives import canonical_bytes

from .neo4j_operational_v2 import _credentials, _safe_identifier


class OperationalNodeEmbeddingConfig(ClosedModel):
    schema_version: Literal["gsm-operational-node-embedding-v1"]
    dataset_version: Literal["gsm-operational-mock-v0.2"]
    contract_version: Literal["gsm-operational-kg-v3-draft-1"]
    provider: Literal["qdrant_cloud"]
    model: Literal["intfloat/multilingual-e5-small"]
    dimensions: Literal[384]
    document_prefix: Literal["passage: "]
    qdrant_collection: Literal["gsm_operational_nodes_v3"]
    qdrant_vector_name: Literal["dense"]
    marker_label: Literal["GSMOperationalV3"]
    vector_property: Literal["semantic_embedding"]
    text_sha256_property: Literal["semantic_text_sha256"]
    vector_sha256_property: Literal["semantic_embedding_sha256"]
    model_property: Literal["semantic_embedding_model"]
    dimensions_property: Literal["semantic_embedding_dimensions"]
    index_name: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    similarity: Literal["cosine"]
    expected_node_counts: dict[str, int]

    @model_validator(mode="after")
    def validate_population(self) -> "OperationalNodeEmbeddingConfig":
        expected = {"Complaint": 11, "Incident": 4, "MaintenanceEvent": 8}
        if self.expected_node_counts != expected:
            raise ValueError(f"embedding population must remain fixed: {expected}")
        return self

    @classmethod
    def load(cls, path: Path | str) -> "OperationalNodeEmbeddingConfig":
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))


def _vector_sha256(vector: list[float]) -> str:
    return hashlib.sha256(canonical_bytes(vector)).hexdigest()


def _load_inputs(
    candidate: Path,
    contract_path: Path,
    config: OperationalNodeEmbeddingConfig,
) -> tuple[Any, tuple[dict[str, Any], ...]]:
    report = verify_operational_mock_candidate(candidate, contract_path=contract_path)
    if report["status"] != "pass":
        raise ValueError(f"candidate verification failed: {report['errors']}")
    dataset = load_operational_mock(candidate)
    contract = OperationalKGv2Contract.load(contract_path)
    if dataset.dataset_version != config.dataset_version:
        raise ValueError("embedding config and candidate dataset versions differ")
    if contract.contract_version != config.contract_version:
        raise ValueError("embedding config and operational contract versions differ")
    if contract.runtime_stores.neo4j.marker_label != config.marker_label:
        raise ValueError("embedding config and Neo4j marker labels differ")
    inputs = build_semantic_node_inputs(dataset)
    counts = dict(Counter(row["node_type"] for row in inputs))
    if counts != config.expected_node_counts:
        raise ValueError(f"semantic input count mismatch: {counts}")
    return dataset, inputs


def _fetch_remote_rows(
    session: Any,
    marker: str,
    ids: list[str],
    config: OperationalNodeEmbeddingConfig,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    rows = session.run(
        f"UNWIND $ids AS id MATCH (n:{marker} {{id: id}}) "
        "RETURN n.id AS id, labels(n) AS labels, properties(n) AS props",
        ids=ids,
    ).data()
    by_id = {row["id"]: row for row in rows}
    unexpected = session.run(
        f"MATCH (n:{marker}) WHERE n.{config.vector_property} IS NOT NULL "
        "AND NOT n.id IN $ids "
        "RETURN n.id AS id, labels(n) AS labels ORDER BY id",
        ids=ids,
    ).data()
    return by_id, unexpected


def _classify_remote_embeddings(
    remote: dict[str, dict[str, Any]],
    inputs: tuple[dict[str, Any], ...],
    config: OperationalNodeEmbeddingConfig,
) -> dict[str, Any]:
    missing_nodes: list[str] = []
    missing_embeddings: list[str] = []
    mismatched: list[dict[str, Any]] = []
    verified: list[str] = []
    metadata_keys = (
        config.text_sha256_property,
        config.vector_sha256_property,
        config.model_property,
        config.dimensions_property,
    )
    for item in inputs:
        node_id = item["node_id"]
        row = remote.get(node_id)
        if row is None:
            missing_nodes.append(node_id)
            continue
        business_labels = [
            label for label in row["labels"] if label != config.marker_label
        ]
        if business_labels != [item["node_type"]]:
            mismatched.append({"node_id": node_id, "issues": ["node_type"]})
            continue
        props = row["props"]
        vector = props.get(config.vector_property)
        metadata_present = [props.get(key) is not None for key in metadata_keys]
        if vector is None and not any(metadata_present):
            missing_embeddings.append(node_id)
            continue
        issues: list[str] = []
        if vector is None or not isinstance(vector, list):
            issues.append("vector_missing_or_invalid")
        else:
            if len(vector) != config.dimensions:
                issues.append("dimensions")
            if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in vector):
                issues.append("non_finite_value")
            if props.get(config.vector_sha256_property) != _vector_sha256(vector):
                issues.append("vector_sha256")
        if props.get(config.text_sha256_property) != item["content_sha256"]:
            issues.append("text_sha256")
        if props.get(config.model_property) != config.model:
            issues.append("model")
        if props.get(config.dimensions_property) != config.dimensions:
            issues.append("dimension_metadata")
        if issues:
            mismatched.append({"node_id": node_id, "issues": sorted(set(issues))})
        else:
            verified.append(node_id)
    return {
        "missing_nodes": sorted(missing_nodes),
        "missing_embeddings": sorted(missing_embeddings),
        "mismatched": sorted(mismatched, key=lambda row: row["node_id"]),
        "verified": sorted(verified),
    }


def _index_state(
    session: Any,
    config: OperationalNodeEmbeddingConfig,
) -> dict[str, Any] | None:
    rows = session.run(
        "SHOW VECTOR INDEXES YIELD name, state, populationPercent, "
        "labelsOrTypes, properties "
        "WHERE name = $name "
        "RETURN name, state, populationPercent, labelsOrTypes, properties",
        name=config.index_name,
    ).data()
    return rows[0] if rows else None


def _verify_session(
    session: Any,
    inputs: tuple[dict[str, Any], ...],
    config: OperationalNodeEmbeddingConfig,
) -> dict[str, Any]:
    marker = _safe_identifier(config.marker_label)
    ids = [row["node_id"] for row in inputs]
    remote, unexpected = _fetch_remote_rows(session, marker, ids, config)
    classification = _classify_remote_embeddings(remote, inputs, config)
    index = _index_state(session, config)
    self_query: dict[str, Any] | None = None
    if index and str(index.get("state", "")).upper() == "ONLINE" and inputs:
        first = inputs[0]
        vector = remote.get(first["node_id"], {}).get("props", {}).get(
            config.vector_property
        )
        if vector:
            hits = session.run(
                "CALL db.index.vector.queryNodes($index_name, 1, $vector) "
                "YIELD node, score "
                "RETURN node.id AS node_id, score",
                index_name=config.index_name,
                vector=vector,
            ).data()
            self_query = {
                "expected_node_id": first["node_id"],
                "hits": hits,
                "pass": bool(hits and hits[0]["node_id"] == first["node_id"]),
            }
    passed = (
        not classification["missing_nodes"]
        and not classification["missing_embeddings"]
        and not classification["mismatched"]
        and not unexpected
        and index is not None
        and str(index.get("state", "")).upper() == "ONLINE"
        and self_query is not None
        and self_query["pass"]
    )
    return {
        "status": "pass" if passed else "fail",
        "expected": len(inputs),
        "verified": len(classification["verified"]),
        "missing_nodes": classification["missing_nodes"],
        "missing_embeddings": classification["missing_embeddings"],
        "mismatched": classification["mismatched"],
        "unexpected_embedded_nodes": unexpected,
        "index": index,
        "self_query": self_query,
    }


def verify_operational_node_embeddings(
    candidate: Path,
    *,
    contract_path: Path = Path("configs/benchmark/operational-kg-v3.json"),
    config_path: Path = Path(
        "configs/benchmark/operational-node-embedding-v1.json"
    ),
    env_prefix: str | None = None,
) -> dict[str, Any]:
    from neo4j import GraphDatabase

    config = OperationalNodeEmbeddingConfig.load(config_path)
    dataset, inputs = _load_inputs(candidate, contract_path, config)
    contract = OperationalKGv2Contract.load(contract_path)
    prefix = env_prefix or contract.runtime_stores.neo4j.env_prefix
    uri, auth, database = _credentials(prefix)
    driver = GraphDatabase.driver(uri, auth=auth)
    try:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            verification = _verify_session(session, inputs, config)
    finally:
        driver.close()
    return {
        "schema_version": config.schema_version,
        "status": verification["status"],
        "dataset_version": dataset.dataset_version,
        "candidate_digest": dataset.logical_digest,
        "provider": config.provider,
        "model": config.model,
        "dimensions": config.dimensions,
        "marker_label": config.marker_label,
        "verification": verification,
    }


def _qdrant_cloud_vectors(
    inputs: list[dict[str, Any]],
    config: OperationalNodeEmbeddingConfig,
) -> tuple[dict[str, list[float]], dict[str, Any]]:
    """Create/reuse a dedicated 23-point Qdrant collection and return vectors."""

    from qdrant_client import QdrantClient, models

    missing_env = [
        name for name in ("QDRANT_URL", "QDRANT_API_KEY") if not os.getenv(name)
    ]
    if missing_env:
        raise RuntimeError(
            "missing Qdrant environment variables: " + ", ".join(missing_env)
        )
    client = QdrantClient(
        url=os.environ["QDRANT_URL"],
        api_key=os.environ["QDRANT_API_KEY"],
        timeout=int(os.getenv("QDRANT_TIMEOUT_SECONDS", "60")),
        cloud_inference=True,
    )
    created_collection = False
    inference_calls = 0
    expected_ids = [row["node_id"] for row in inputs]
    try:
        if client.collection_exists(config.qdrant_collection):
            info = client.get_collection(config.qdrant_collection)
            vectors = info.config.params.vectors
            dense = vectors.get(config.qdrant_vector_name) if isinstance(vectors, dict) else None
            distance = str(getattr(getattr(dense, "distance", None), "value", getattr(dense, "distance", ""))).lower()
            if dense is None or dense.size != config.dimensions or distance != "cosine":
                raise ValueError("existing operational-node Qdrant schema mismatch")
        else:
            created = client.create_collection(
                collection_name=config.qdrant_collection,
                vectors_config={
                    config.qdrant_vector_name: models.VectorParams(
                        size=config.dimensions,
                        distance=models.Distance.COSINE,
                    )
                },
            )
            if not created:
                raise RuntimeError("Qdrant did not create operational-node collection")
            created_collection = True

        count_before = int(
            client.count(config.qdrant_collection, exact=True).count
        )
        records = client.retrieve(
            collection_name=config.qdrant_collection,
            ids=expected_ids,
            with_payload=True,
            with_vectors=[config.qdrant_vector_name],
        )
        if count_before not in {0, len(inputs)}:
            raise ValueError(
                f"operational-node Qdrant collection has {count_before} points; "
                f"expected 0 or {len(inputs)}"
            )
        if count_before == len(inputs):
            if len(records) != len(inputs):
                raise ValueError("Qdrant collection contains unexpected point identities")
            expected = {row["node_id"]: row for row in inputs}
            for record in records:
                item = expected.get(str(record.id))
                payload = record.payload or {}
                if item is None or payload.get("text_sha256") != item["content_sha256"]:
                    raise ValueError(f"Qdrant point provenance mismatch: {record.id}")
                if payload.get("model") != config.model:
                    raise ValueError(f"Qdrant point model mismatch: {record.id}")
        else:
            points = [
                models.PointStruct(
                    id=item["node_id"],
                    vector={
                        config.qdrant_vector_name: models.Document(
                            text=config.document_prefix + item["text"],
                            model=config.model,
                        )
                    },
                    payload={
                        "dataset_version": config.dataset_version,
                        "node_id": item["node_id"],
                        "node_type": item["node_type"],
                        "text": item["text"],
                        "text_sha256": item["content_sha256"],
                        "model": config.model,
                    },
                )
                for item in inputs
            ]
            client.upsert(
                collection_name=config.qdrant_collection,
                points=points,
                wait=True,
            )
            inference_calls = 1
            records = client.retrieve(
                collection_name=config.qdrant_collection,
                ids=expected_ids,
                with_payload=True,
                with_vectors=[config.qdrant_vector_name],
            )

        vectors_by_id: dict[str, list[float]] = {}
        for record in records:
            named_vectors = record.vector if isinstance(record.vector, dict) else {}
            vector = named_vectors.get(config.qdrant_vector_name)
            if hasattr(vector, "data"):
                vector = vector.data
            values = list(vector or [])
            if len(values) != config.dimensions:
                raise RuntimeError(
                    f"Qdrant vector dimension mismatch for {record.id}: {len(values)}"
                )
            if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in values):
                raise RuntimeError(f"invalid Qdrant vector values for {record.id}")
            vectors_by_id[str(record.id)] = values
        if set(vectors_by_id) != set(expected_ids):
            raise RuntimeError("Qdrant did not return the complete embedding population")
        count_after = int(client.count(config.qdrant_collection, exact=True).count)
        if count_after != len(inputs):
            raise RuntimeError(
                f"Qdrant point count mismatch: {count_after} != {len(inputs)}"
            )
        return vectors_by_id, {
            "collection": config.qdrant_collection,
            "created_collection": created_collection,
            "count_before": count_before,
            "count_after": count_after,
            "inference_calls": inference_calls,
        }
    finally:
        client.close()


def embed_operational_nodes(
    candidate: Path,
    *,
    contract_path: Path = Path("configs/benchmark/operational-kg-v3.json"),
    config_path: Path = Path(
        "configs/benchmark/operational-node-embedding-v1.json"
    ),
    env_prefix: str | None = None,
) -> dict[str, Any]:
    """Create only missing vectors; never overwrite conflicting runtime vectors."""

    from neo4j import GraphDatabase

    config = OperationalNodeEmbeddingConfig.load(config_path)
    dataset, inputs = _load_inputs(candidate, contract_path, config)
    contract = OperationalKGv2Contract.load(contract_path)
    prefix = env_prefix or contract.runtime_stores.neo4j.env_prefix
    uri, auth, database = _credentials(prefix)
    driver = GraphDatabase.driver(uri, auth=auth)
    provider_calls = 0
    provider_receipt: dict[str, Any] | None = None
    created = 0
    try:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            marker = _safe_identifier(config.marker_label)
            ids = [row["node_id"] for row in inputs]
            remote, unexpected = _fetch_remote_rows(session, marker, ids, config)
            before = _classify_remote_embeddings(remote, inputs, config)
            if before["missing_nodes"] or before["mismatched"] or unexpected:
                return {
                    "schema_version": config.schema_version,
                    "status": "fail",
                    "stage": "preflight",
                    "missing_nodes": before["missing_nodes"],
                    "mismatched": before["mismatched"],
                    "unexpected_embedded_nodes": unexpected,
                    "provider_calls": 0,
                }
            missing_ids = set(before["missing_embeddings"])
            missing_inputs = [row for row in inputs if row["node_id"] in missing_ids]
            if missing_inputs:
                # Always verify/reuse the complete fixed Qdrant population.  This
                # also makes a retry recoverable if a previous run populated
                # Qdrant but only part of the Neo4j write completed.
                vectors_by_id, provider_receipt = _qdrant_cloud_vectors(
                    list(inputs), config
                )
                provider_calls = provider_receipt["inference_calls"]
                write_rows: list[dict[str, Any]] = []
                for item in missing_inputs:
                    vector = vectors_by_id[item["node_id"]]
                    if len(vector) != config.dimensions:
                        raise RuntimeError(
                            f"embedding dimension mismatch for {item['node_id']}: "
                            f"{len(vector)} != {config.dimensions}"
                        )
                    if not all(math.isfinite(value) for value in vector):
                        raise RuntimeError(
                            f"non-finite embedding value for {item['node_id']}"
                        )
                    write_rows.append(
                        {
                            "node_id": item["node_id"],
                            "vector": vector,
                            "text_sha256": item["content_sha256"],
                            "vector_sha256": _vector_sha256(vector),
                        }
                    )

                def write(tx: Any) -> int:
                    record = tx.run(
                        f"UNWIND $rows AS row "
                        f"MATCH (n:{marker} {{id: row.node_id}}) "
                        f"WHERE n.{config.vector_property} IS NULL "
                        f"SET n.{config.vector_property} = row.vector, "
                        f"n.{config.text_sha256_property} = row.text_sha256, "
                        f"n.{config.vector_sha256_property} = row.vector_sha256, "
                        f"n.{config.model_property} = $model, "
                        f"n.{config.dimensions_property} = $dimensions "
                        "RETURN count(n) AS updated",
                        rows=write_rows,
                        model=config.model,
                        dimensions=config.dimensions,
                    ).single()
                    return int(record["updated"])

                created = session.execute_write(write)
                if created != len(write_rows):
                    raise RuntimeError(
                        f"Neo4j updated {created} nodes, expected {len(write_rows)}"
                    )
            session.run(
                f"CREATE VECTOR INDEX {config.index_name} IF NOT EXISTS "
                f"FOR (n:{marker}) ON (n.{config.vector_property}) "
                "OPTIONS {indexConfig: {"
                f"`vector.dimensions`: {config.dimensions}, "
                f"`vector.similarity_function`: '{config.similarity}'"
                "}}"
            ).consume()
            verification = _verify_session(session, inputs, config)
            for _ in range(30):
                if verification["status"] == "pass":
                    break
                if not verification["index"] or str(
                    verification["index"].get("state", "")
                ).upper() != "ONLINE":
                    time.sleep(1)
                    verification = _verify_session(session, inputs, config)
                else:
                    break
    finally:
        driver.close()
    return {
        "schema_version": config.schema_version,
        "status": verification["status"],
        "dataset_version": dataset.dataset_version,
        "candidate_digest": dataset.logical_digest,
        "provider": config.provider,
        "model": config.model,
        "dimensions": config.dimensions,
        "marker_label": config.marker_label,
        "provider_calls": provider_calls,
        "provider_receipt": provider_receipt,
        "created_embeddings": created,
        "unchanged_embeddings": len(inputs) - created,
        "verification": verification,
    }
