import os
import pytest
from dotenv import load_dotenv

load_dotenv()

from gsm_memory.retrieval.nvidia_embed import NvidiaNemotronEmbedder, cosine_similarity
from gsm_memory.retrieval.semantic_seed import DenseDocumentSearcher, SemanticSeedSelector
from tests.fixtures.mock_data import SAMPLE_GRAPH_ENTITIES, SAMPLE_POLICY_CHUNKS

API_KEY = os.getenv("NVIDIA_API_KEY")
skip_if_no_nvidia_key = pytest.mark.skipif(not API_KEY, reason="NVIDIA_API_KEY is not set in .env")


@skip_if_no_nvidia_key
def test_nvidia_nemotron_embedding_call():
    embedder = NvidiaNemotronEmbedder(api_key=API_KEY)
    vectors = embedder.embed_passages(["Quy chế thưởng phạt GSM", "Tài xế Nguyễn Văn A"])

    assert len(vectors) == 2
    # Nemotron 1B produces 2048-dimensional vectors
    assert len(vectors[0]) == 2048
    assert len(vectors[1]) == 2048

    q_vec = embedder.embed_query("Quy định thưởng phạt tài xế")
    assert len(q_vec) == 2048

    # Cosine similarity between query and policy passage should be distinctly higher than with driver profile
    sim_policy = cosine_similarity(q_vec, vectors[0])
    sim_driver = cosine_similarity(q_vec, vectors[1])
    assert sim_policy > sim_driver


@skip_if_no_nvidia_key
def test_semantic_seed_finding_for_driver_and_incident():
    embedder = NvidiaNemotronEmbedder(api_key=API_KEY)
    selector = SemanticSeedSelector(embedder=embedder, entities=SAMPLE_GRAPH_ENTITIES)

    # 1. Natural language query referencing driver A
    driver_seeds = selector.find_seeds("Anh A lái xe VinFast ở Hà Nội", top_k=1, kind="driver")
    assert len(driver_seeds) == 1
    assert driver_seeds[0]["name"] == "Nguyễn Văn A"
    assert driver_seeds[0]["entity_id"] == "99e70ebe-18cd-57a3-a036-cf0ff1989861"

    # 2. Natural language query referencing tire puncture incident
    incident_seeds = selector.find_seeds("Xe bị rách vỏ nổ lốp bất khả kháng", top_k=1, kind="incident_type")
    assert len(incident_seeds) == 1
    assert incident_seeds[0]["entity_id"] == "inc-type-tire-puncture"
    assert incident_seeds[0]["attributes"]["exemption_eligible"] is True


@skip_if_no_nvidia_key
def test_dense_document_search_with_nemotron():
    embedder = NvidiaNemotronEmbedder(api_key=API_KEY)
    searcher = DenseDocumentSearcher(embedder=embedder, chunks=SAMPLE_POLICY_CHUNKS)

    # Search for diamond tier cancel rate regulation
    results = searcher.search("tiêu chuẩn duy trì hạng Kim Cương tỷ lệ hủy chuyến", top_k=1)
    assert len(results) == 1
    assert results[0]["chunk_id"] == "chunk-p154-sec5"
    assert results[0]["clause_ref"] == "Điều 5"

    # Search for breakdown exemption
    exempt_results = searcher.search("xe bị hỏng kỹ thuật có bị tính tỷ lệ hủy không", top_k=1)
    assert len(exempt_results) == 1
    assert exempt_results[0]["chunk_id"] == "chunk-p154-sec8"
    assert exempt_results[0]["clause_ref"] == "Điều 8"
