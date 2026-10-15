"""Qdrant Cloud adapter for the versioned policy hybrid index.

The deterministic source plan lives in ``retrieval.qdrant_hybrid``.  This
module owns network I/O only: collection creation, idempotent upsert, strict
verification, and native dense+sparse retrieval.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any, Sequence

from gsm_memory.retrieval.qdrant_hybrid import HybridCollectionPlan, HybridPointPlan


PAYLOAD_INDEX_FIELDS = (
    "clause_ids",
    "dataset_version",
    "document_id",
    "document_revision_id",
    "profile_id",
)


@dataclass(frozen=True)
class QdrantConnectionSettings:
    url: str
    api_key: str
    collection: str
    timeout_seconds: int = 60

    @classmethod
    def from_env(cls) -> "QdrantConnectionSettings":
        required = ("QDRANT_URL", "QDRANT_API_KEY", "QDRANT_COLLECTION")
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            raise ValueError("missing Qdrant environment variables: " + ", ".join(missing))
        return cls(
            url=os.environ["QDRANT_URL"],
            api_key=os.environ["QDRANT_API_KEY"],
            collection=os.environ["QDRANT_COLLECTION"],
            timeout_seconds=int(os.getenv("QDRANT_TIMEOUT_SECONDS", "60")),
        )


def build_client(settings: QdrantConnectionSettings):
    try:
        from qdrant_client import QdrantClient
    except ImportError as exc:  # pragma: no cover - depends on optional installation
        raise RuntimeError("install the project with --extra qdrant") from exc
    return QdrantClient(
        url=settings.url,
        api_key=settings.api_key,
        timeout=settings.timeout_seconds,
        cloud_inference=True,
    )


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    raw = getattr(value, "value", value)
    return str(raw).lower()


def inspect_collection(client: Any, plan: HybridCollectionPlan) -> dict[str, Any]:
    """Return a read-only schema report for the dedicated v2 collection."""

    if not client.collection_exists(plan.collection):
        return {
            "collection": plan.collection,
            "exists": False,
            "schema_valid": False,
            "point_count": 0,
            "issues": ["collection_missing"],
        }
    info = client.get_collection(plan.collection)
    params = info.config.params
    dense_map = params.vectors if isinstance(params.vectors, dict) else {}
    sparse_map = params.sparse_vectors or {}
    dense = dense_map.get("dense")
    sparse = sparse_map.get("sparse")
    issues: list[str] = []
    if set(dense_map) != {"dense"}:
        issues.append("dense_vector_names_mismatch")
    if set(sparse_map) != {"sparse"}:
        issues.append("sparse_vector_names_mismatch")
    if dense is None or dense.size != plan.dense_dimensions:
        issues.append("dense_dimensions_mismatch")
    if dense is None or _enum_value(dense.distance) != "cosine":
        issues.append("dense_distance_mismatch")
    if sparse is None or _enum_value(sparse.modifier) != "idf":
        issues.append("sparse_modifier_mismatch")
    payload_schema = getattr(info, "payload_schema", {}) or {}
    missing_payload_indexes = [
        field for field in PAYLOAD_INDEX_FIELDS if field not in payload_schema
    ]
    issues.extend(
        f"payload_index_missing:{field}" for field in missing_payload_indexes
    )
    return {
        "collection": plan.collection,
        "exists": True,
        "schema_valid": not issues,
        "point_count": int(info.points_count or 0),
        "status": _enum_value(info.status),
        "issues": issues,
    }


def ensure_collection(client: Any, plan: HybridCollectionPlan) -> dict[str, Any]:
    """Create the collection once, or reject an incompatible existing schema."""

    from qdrant_client import models

    report = inspect_collection(client, plan)
    if report["exists"]:
        incompatible = [
            issue
            for issue in report["issues"]
            if not issue.startswith("payload_index_missing:")
        ]
        if incompatible:
            raise ValueError(f"existing Qdrant collection schema mismatch: {incompatible}")
        created = False
    else:
        created = client.create_collection(
            collection_name=plan.collection,
            vectors_config={
                "dense": models.VectorParams(
                    size=plan.dense_dimensions,
                    distance=models.Distance.COSINE,
                )
            },
            sparse_vectors_config={
                "sparse": models.SparseVectorParams(modifier=models.Modifier.IDF)
            },
        )
        if not created:
            raise RuntimeError(f"Qdrant did not create collection {plan.collection!r}")
    for field in PAYLOAD_INDEX_FIELDS:
        if f"payload_index_missing:{field}" in report["issues"] or not report["exists"]:
            client.create_payload_index(
                collection_name=plan.collection,
                field_name=field,
                field_schema=models.PayloadSchemaType.KEYWORD,
                wait=True,
            )
    verified = inspect_collection(client, plan)
    if not verified["schema_valid"]:
        raise RuntimeError(f"created Qdrant collection failed schema verification: {verified}")
    return {**verified, "created": bool(created)}


def _require_models(plan: HybridCollectionPlan) -> tuple[str, str]:
    if not plan.dense_model or not plan.sparse_model:
        raise ValueError("dense and sparse models must be pinned before Qdrant ingestion")
    return plan.dense_model, plan.sparse_model


def to_qdrant_point(plan: HybridCollectionPlan, point: HybridPointPlan):
    from qdrant_client import models

    dense_model, sparse_model = _require_models(plan)
    text = str(point.payload["text"])
    return models.PointStruct(
        id=point.point_id,
        vector={
            "dense": models.Document(
                text=plan.dense_document_prefix + text,
                model=dense_model,
            ),
            "sparse": models.Document(
                text=plan.sparse_document_prefix + text,
                model=sparse_model,
            ),
        },
        payload=point.payload,
    )


def verify_collection(
    client: Any,
    plan: HybridCollectionPlan,
    points: Sequence[HybridPointPlan],
    *,
    batch_size: int = 128,
) -> dict[str, Any]:
    """Strictly verify schema, cardinality, point IDs, lineage, and vectors."""

    schema = inspect_collection(client, plan)
    if not schema["exists"] or not schema["schema_valid"]:
        return {"status": "fail", "schema": schema, "checked": 0}
    expected = {point.point_id: point for point in points}
    seen: set[str] = set()
    mismatched: list[dict[str, Any]] = []
    stable_keys = (
        "chunk_id",
        "clause_ids",
        "content_sha256",
        "dataset_version",
        "document_id",
        "document_revision_id",
    )
    ids = sorted(expected)
    for start in range(0, len(ids), batch_size):
        records = client.retrieve(
            collection_name=plan.collection,
            ids=ids[start : start + batch_size],
            with_payload=True,
            with_vectors=["dense", "sparse"],
        )
        for record in records:
            point_id = str(record.id)
            seen.add(point_id)
            expected_point = expected[point_id]
            actual_payload = record.payload or {}
            payload_issues = [
                key
                for key in stable_keys
                if actual_payload.get(key) != expected_point.payload.get(key)
            ]
            vector_names = set(record.vector) if isinstance(record.vector, dict) else set()
            if payload_issues or vector_names != {"dense", "sparse"}:
                mismatched.append(
                    {
                        "point_id": point_id,
                        "payload_keys": payload_issues,
                        "vector_names": sorted(vector_names),
                    }
                )
    missing = sorted(set(expected) - seen)
    unexpected_count = max(0, schema["point_count"] - len(seen))
    passed = (
        schema["point_count"] == len(expected)
        and not missing
        and not mismatched
        and unexpected_count == 0
    )
    return {
        "status": "pass" if passed else "fail",
        "schema": schema,
        "expected": len(expected),
        "checked": len(seen),
        "missing": missing,
        "mismatched": mismatched,
        "unexpected_count": unexpected_count,
    }


def ingest_collection(
    client: Any,
    plan: HybridCollectionPlan,
    points: Sequence[HybridPointPlan],
    *,
    batch_size: int = 16,
) -> dict[str, Any]:
    """Idempotently upsert the complete retrieval corpus and verify it."""

    if plan.profile_id != "retrieval_full":
        raise ValueError("the persistent v2 collection accepts retrieval_full only")
    schema = ensure_collection(client, plan)
    before = int(client.count(plan.collection, exact=True).count)
    for start in range(0, len(points), batch_size):
        batch = [to_qdrant_point(plan, point) for point in points[start : start + batch_size]]
        client.upsert(collection_name=plan.collection, points=batch, wait=True)
    verification = verify_collection(client, plan, points)
    return {
        "status": verification["status"],
        "schema_version": plan.schema_version,
        "collection": plan.collection,
        "created": schema["created"],
        "before_count": before,
        "after_count": verification["schema"].get("point_count", 0),
        "upserted": len(points),
        "plan": asdict(plan),
        "verification": verification,
    }


def hybrid_search(
    client: Any,
    plan: HybridCollectionPlan,
    query_text: str,
    *,
    limit: int = 10,
    prefetch_limit: int = 50,
) -> dict[str, Any]:
    """Run native dense+sparse prefetch and reciprocal-rank fusion."""

    from qdrant_client import models

    if not query_text.strip():
        raise ValueError("query text must not be empty")
    if limit <= 0 or prefetch_limit < limit:
        raise ValueError("prefetch_limit must be greater than or equal to positive limit")
    dense_model, sparse_model = _require_models(plan)
    query_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="dataset_version",
                match=models.MatchValue(value=plan.dataset_version),
            ),
            models.FieldCondition(
                key="profile_id",
                match=models.MatchValue(value=plan.profile_id),
            ),
        ]
    )
    response = client.query_points(
        collection_name=plan.collection,
        prefetch=[
            models.Prefetch(
                query=models.Document(
                    text=plan.dense_query_prefix + query_text,
                    model=dense_model,
                ),
                using="dense",
                filter=query_filter,
                limit=prefetch_limit,
            ),
            models.Prefetch(
                query=models.Document(
                    text=plan.sparse_query_prefix + query_text,
                    model=sparse_model,
                ),
                using="sparse",
                filter=query_filter,
                limit=prefetch_limit,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    return {
        "schema_version": "gsm-qdrant-native-hybrid-search-v1",
        "collection": plan.collection,
        "query": query_text,
        "fusion": plan.fusion,
        "hits": [
            {
                "point_id": str(point.id),
                "score": point.score,
                "payload": point.payload,
            }
            for point in response.points
        ],
    }
