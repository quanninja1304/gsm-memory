from __future__ import annotations

from pathlib import Path

import pytest

from gsm_memory.retrieval.bm25 import BM25Index
from gsm_memory.retrieval.config import RetrievalConfig
from gsm_memory.retrieval.dense import DenseChunkIndex, DenseIndexError
from gsm_memory.retrieval.documents import ChunkConfig, construct_chunks
from gsm_memory.retrieval.planner import RetrievalPlanner
from gsm_memory.retrieval.query_analysis import parse_query_rule_based


RELEASE = Path("data/gsm-dev-core-0.2.2")


class FakeEmbedder:
    model = "test/dense-v1"

    @staticmethod
    def _vector(text: str) -> list[float]:
        terms = text.casefold().split()
        return [float(sum(term.count(letter) for term in terms)) for letter in ("a", "e", "i", "o")]

    def embed_passages(self, texts):
        return [self._vector(text) for text in texts]

    def embed_query(self, query: str):
        return self._vector(query)


class FakeReranker:
    model = "test/reranker-v1"

    def rank(self, query: str, passages):
        return [float(index) for index, _ in enumerate(passages, 1)]


class MissingCredentialEmbedder(FakeEmbedder):
    def embed_query(self, query: str):
        raise RuntimeError("NVIDIA_API_KEY is required to call embeddings")


def test_dense_index_identity_roundtrip_and_rejects_wrong_chunker(tmp_path: Path):
    chunks, _, inventory = construct_chunks(RELEASE, "debug_core", ChunkConfig())
    config = RetrievalConfig(embedding_model=FakeEmbedder.model)
    index = DenseChunkIndex.build(chunks, embedder=FakeEmbedder(), chunk_config_hash=config.dense_index_config_hash(),
                                  profile_version=inventory["profile_version"])
    artifact = tmp_path / "dense.json"
    index.save(artifact)

    loaded = DenseChunkIndex.load(artifact, chunks=chunks, chunk_config_hash=config.dense_index_config_hash(),
                                  embedding_model=FakeEmbedder.model, profile_version=inventory["profile_version"])
    assert loaded.identity.profile_id == "debug_core"
    assert len(loaded.search("quy định", embedder=FakeEmbedder(), top_k=3)) == 3

    with pytest.raises(DenseIndexError, match="identity"):
        DenseChunkIndex.load(artifact, chunks=chunks, chunk_config_hash="different",
                             embedding_model=FakeEmbedder.model, profile_version=inventory["profile_version"])


def test_dense_identity_ignores_runtime_artifact_location():
    build_config = RetrievalConfig(embedding_model=FakeEmbedder.model)
    runtime_config = RetrievalConfig(embedding_model=FakeEmbedder.model,
                                     dense_index_path="artifacts/retrieval_indexes/debug_core.json")
    assert build_config.dense_index_config_hash() == runtime_config.dense_index_config_hash()


def test_document_pipeline_fuses_same_chunk_rankings_then_reranks():
    chunks, _, inventory = construct_chunks(RELEASE, "debug_core", ChunkConfig())
    config = RetrievalConfig(embedding_model=FakeEmbedder.model, document_top_k=5,
                             dense_top_k=5, rerank_top_n=5)
    dense = DenseChunkIndex.build(chunks, embedder=FakeEmbedder(), chunk_config_hash=config.dense_index_config_hash(),
                                  profile_version=inventory["profile_version"])
    query = {
        "query_id": "p3-policy", "query": "quy định doanh số tối thiểu",
        "public_snapshot_id": "d4cc0438-d831-541a-8123-ddda94ccdac8",
        "application_context": {"source_snapshot_refs": ["P151"]},
    }
    query_plan = parse_query_rule_based(query, release_dir=RELEASE, config=config)
    plan = RetrievalPlanner(config, dense_index=dense, embedder=FakeEmbedder(), reranker=FakeReranker()).plan(query_plan, query)
    result = RetrievalPlanner(config, dense_index=dense, embedder=FakeEmbedder(), reranker=FakeReranker()).execute(
        plan, query, chunks, BM25Index(chunks), RELEASE / "public" / "snapshots" / query["public_snapshot_id"],
        document_top_k=5, token_budget=1000, max_items=10,
    )
    receipt = result.receipts["document"]["pipeline"]
    assert receipt["dense"]["status"] == "completed"
    assert receipt["reranker"]["status"] == "completed"
    assert result.modality_candidates["document"]
    assert result.modality_candidates["document"][0]["origin_stage"] == "rerank"
    assert all(row["source_kind"] in {"document", "definition"} for row in result.modality_candidates["document"])


def test_document_pipeline_reports_missing_model_artifacts_without_faking_dense():
    chunks, _, _ = construct_chunks(RELEASE, "debug_core", ChunkConfig())
    config = RetrievalConfig()
    query = {
        "query_id": "p3-no-model", "query": "quy định doanh số",
        "public_snapshot_id": "d4cc0438-d831-541a-8123-ddda94ccdac8",
        "application_context": {"source_snapshot_refs": ["P151"]},
    }
    query_plan = parse_query_rule_based(query, release_dir=RELEASE, config=config)
    planner = RetrievalPlanner(config)
    result = planner.execute(planner.plan(query_plan, query), query, chunks, BM25Index(chunks),
                             RELEASE / "public" / "snapshots" / query["public_snapshot_id"])
    assert result.receipts["document"]["pipeline"]["dense"]["status"] == "blocked_model_artifact"
    assert result.receipts["document"]["pipeline"]["reranker"]["status"] == "blocked_model_artifact"


def test_dense_provider_block_keeps_bm25_evidence():
    chunks, _, inventory = construct_chunks(RELEASE, "debug_core", ChunkConfig())
    config = RetrievalConfig(embedding_model=FakeEmbedder.model)
    dense = DenseChunkIndex.build(chunks, embedder=FakeEmbedder(), chunk_config_hash=config.dense_index_config_hash(),
                                  profile_version=inventory["profile_version"])
    query = {
        "query_id": "p3-provider-block", "query": "quy Ä‘á»‹nh doanh sá»‘",
        "public_snapshot_id": "d4cc0438-d831-541a-8123-ddda94ccdac8",
        "application_context": {"source_snapshot_refs": ["P151"]},
    }
    query_plan = parse_query_rule_based(query, release_dir=RELEASE, config=config)
    planner = RetrievalPlanner(config, dense_index=dense, embedder=MissingCredentialEmbedder())
    result = planner.execute(planner.plan(query_plan, query), query, chunks, BM25Index(chunks),
                             RELEASE / "public" / "snapshots" / query["public_snapshot_id"])
    assert result.modality_candidates["document"]
    assert result.receipts["document"]["pipeline"]["dense"]["status"] == "blocked_provider"
