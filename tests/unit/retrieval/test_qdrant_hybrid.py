import uuid
from pathlib import Path

from gsm_memory.retrieval.qdrant_hybrid import (
    REQUIRED_VECTOR_NAMES,
    build_hybrid_point_plan,
    point_id_for_chunk,
)


RELEASE = Path("data/gsm-dev-core-0.2.2")


def test_qdrant_hybrid_plan_is_deterministic_and_uses_one_collection():
    first_plan, first_points = build_hybrid_point_plan(RELEASE, profile_id="debug_core")
    second_plan, second_points = build_hybrid_point_plan(RELEASE, profile_id="debug_core")

    assert first_plan == second_plan
    assert first_points == second_points
    assert first_plan.collection == "gsm_policy_chunks_v2"
    assert first_plan.query_mode == "native_hybrid"
    assert first_plan.fusion == "rrf"
    assert first_plan.point_count == len(first_points) > 0
    assert first_plan.dense_model == "intfloat/multilingual-e5-small"
    assert first_plan.dense_dimensions == 384
    assert first_plan.dense_document_prefix == "passage: "
    assert first_plan.dense_query_prefix == "query: "
    assert first_plan.sparse_model == "qdrant/bm25"


def test_qdrant_hybrid_points_require_dense_and_sparse_vectors():
    _, points = build_hybrid_point_plan(RELEASE, profile_id="debug_core")

    assert all(point.required_vector_names == REQUIRED_VECTOR_NAMES for point in points)
    assert all(uuid.UUID(point.point_id).version == 5 for point in points)


def test_qdrant_hybrid_payload_preserves_source_and_clause_lineage():
    _, points = build_hybrid_point_plan(RELEASE, profile_id="debug_core")
    required = {
        "chunk_id",
        "clause_ids",
        "content_sha256",
        "dataset_version",
        "document_id",
        "document_revision_id",
        "text",
    }

    assert all(required <= point.payload.keys() for point in points)
    assert all(point.payload["dataset_version"] == RELEASE.name for point in points)
    assert all(isinstance(point.payload["clause_ids"], list) for point in points)
    assert any(point.payload["clause_ids"] for point in points)


def test_qdrant_hybrid_point_ids_do_not_depend_on_profile_membership():
    first = point_id_for_chunk(RELEASE.name, "same-immutable-chunk")
    second = point_id_for_chunk(RELEASE.name, "same-immutable-chunk")

    assert first == second
    assert uuid.UUID(first).version == 5
