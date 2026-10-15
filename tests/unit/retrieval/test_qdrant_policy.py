from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("qdrant_client")

from gsm_memory.adapters.qdrant_policy import (
    PAYLOAD_INDEX_FIELDS,
    ensure_collection,
    hybrid_search,
    ingest_collection,
    inspect_collection,
    to_qdrant_point,
)
from gsm_memory.retrieval.qdrant_hybrid import build_hybrid_point_plan


RELEASE = Path("data/gsm-dev-core-0.2.2")


class FakeClient:
    def __init__(self, *, exists=False, points_count=0, dense_size=384, sparse=True):
        self.exists = exists
        self.points_count = points_count
        self.dense_size = dense_size
        self.sparse = sparse
        self.created_with = None
        self.payload_indexes = set()
        self.query_kwargs = None

    def collection_exists(self, _collection):
        return self.exists

    def get_collection(self, _collection):
        vectors = {
            "dense": SimpleNamespace(size=self.dense_size, distance="Cosine")
        }
        sparse_vectors = (
            {"sparse": SimpleNamespace(modifier="idf")} if self.sparse else {}
        )
        return SimpleNamespace(
            config=SimpleNamespace(
                params=SimpleNamespace(vectors=vectors, sparse_vectors=sparse_vectors)
            ),
            points_count=self.points_count,
            status="green",
            payload_schema={field: SimpleNamespace(data_type="keyword") for field in self.payload_indexes},
        )

    def create_collection(self, **kwargs):
        self.created_with = kwargs
        self.exists = True
        return True

    def create_payload_index(self, **kwargs):
        self.payload_indexes.add(kwargs["field_name"])
        return True

    def query_points(self, **kwargs):
        self.query_kwargs = kwargs
        return SimpleNamespace(
            points=[SimpleNamespace(id="point-1", score=0.75, payload={"chunk_id": "c1"})]
        )


@pytest.fixture(scope="module")
def debug_plan_and_points():
    return build_hybrid_point_plan(RELEASE, profile_id="debug_core")


def test_missing_collection_is_reported_without_mutation(debug_plan_and_points):
    plan, _ = debug_plan_and_points
    client = FakeClient()

    report = inspect_collection(client, plan)

    assert report["exists"] is False
    assert report["issues"] == ["collection_missing"]
    assert client.created_with is None


def test_collection_is_created_with_dense_and_sparse_schema(debug_plan_and_points):
    plan, _ = debug_plan_and_points
    client = FakeClient()

    report = ensure_collection(client, plan)

    assert report["created"] is True
    assert report["schema_valid"] is True
    assert set(client.created_with["vectors_config"]) == {"dense"}
    assert set(client.created_with["sparse_vectors_config"]) == {"sparse"}
    assert client.payload_indexes == set(PAYLOAD_INDEX_FIELDS)


def test_existing_collection_gets_missing_payload_indexes(debug_plan_and_points):
    plan, _ = debug_plan_and_points
    client = FakeClient(exists=True)

    report = ensure_collection(client, plan)

    assert report["created"] is False
    assert report["schema_valid"] is True
    assert client.payload_indexes == set(PAYLOAD_INDEX_FIELDS)


def test_incompatible_existing_collection_is_never_rewritten(debug_plan_and_points):
    plan, _ = debug_plan_and_points
    client = FakeClient(exists=True, dense_size=768, sparse=False)

    with pytest.raises(ValueError, match="schema mismatch"):
        ensure_collection(client, plan)

    assert client.created_with is None


def test_point_uses_e5_passage_prefix_and_bm25_raw_text(debug_plan_and_points):
    plan, points = debug_plan_and_points

    point = to_qdrant_point(plan, points[0])

    assert point.vector["dense"].model == "intfloat/multilingual-e5-small"
    assert point.vector["dense"].text.startswith("passage: ")
    assert point.vector["sparse"].model == "qdrant/bm25"
    assert point.vector["sparse"].text == points[0].payload["text"]


def test_persistent_ingest_rejects_partial_profile(debug_plan_and_points):
    plan, points = debug_plan_and_points

    with pytest.raises(ValueError, match="retrieval_full only"):
        ingest_collection(FakeClient(), plan, points)


def test_hybrid_search_builds_two_prefetches_and_rrf(debug_plan_and_points):
    plan, _ = debug_plan_and_points
    plan = replace(plan, profile_id="retrieval_full")
    client = FakeClient(exists=True)

    report = hybrid_search(client, plan, "quy định hủy chuyến", limit=5, prefetch_limit=20)

    kwargs = client.query_kwargs
    assert report["hits"][0]["point_id"] == "point-1"
    assert kwargs["limit"] == 5
    assert [prefetch.using for prefetch in kwargs["prefetch"]] == ["dense", "sparse"]
    assert kwargs["prefetch"][0].query.text.startswith("query: ")
    assert kwargs["prefetch"][1].query.text == "quy định hủy chuyến"
