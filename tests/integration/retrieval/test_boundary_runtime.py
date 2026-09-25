"""Integration tests proving strict boundaries between runtime and mock/private oracle.

Validates:
1. Mutating mock data fixtures (MOCK_CANDIDATES, SAMPLE_GRAPH_ENTITIES) produces ZERO
   change on runtime release retrieval outputs.
2. Runtime retrieval operates strictly on public release assets (chunks, entity catalog,
   Mode A snapshots) and strictly refuses or succeeds without any private oracle tree.
3. Runtime packages under `gsm_memory.retrieval` do not statically import mock test fixtures.
"""

from __future__ import annotations

import copy
import importlib
import json
from pathlib import Path
from typing import Any

import pytest

from gsm_memory.retrieval.bm25 import BM25Index
from gsm_memory.retrieval.documents import construct_chunks
from gsm_memory.retrieval.offline import (
    _document_candidates,
    computation_candidates,
    entity_catalog_candidates,
    select_public,
)
from gsm_memory.retrieval.routing import validate_public_path_safety, PublicRoutingViolationError
from tests.fixtures.mock_data import MOCK_CANDIDATES, SAMPLE_GRAPH_ENTITIES, SAMPLE_POLICY_CHUNKS


RELEASE_DIR = Path("data/gsm-dev-core-0.2.2")


def test_modifying_mock_data_does_not_change_runtime_release_results():
    """Criteria: Đổi mock data không làm thay đổi kết quả runtime release."""
    queries_path = RELEASE_DIR / "public" / "runtime_queries" / "dev.jsonl"
    all_queries = [json.loads(line) for line in queries_path.read_text("utf-8").splitlines()]
    # Choose 3 representative queries: policy lookup, driver query, and cancel_rate computation
    policy_query = all_queries[0]  # snap-154 policy lookup
    comp_query = next(q for q in all_queries if "cancel_rate_30d" in q["query"])

    chunks, _, _ = construct_chunks(RELEASE_DIR, "retrieval_full")
    index = BM25Index(chunks)

    # 1. Baseline run with unmodified mocks
    snapshot_policy = RELEASE_DIR / "public" / "snapshots" / policy_query["public_snapshot_id"]
    doc_cand_before = _document_candidates(policy_query, chunks, index, top_k=5, snapshot_dir=snapshot_policy)

    snapshot_comp = RELEASE_DIR / "public" / "snapshots" / comp_query["public_snapshot_id"]
    comp_cand_before, comp_receipt_before = computation_candidates(snapshot_comp, comp_query)
    ent_cand_before = entity_catalog_candidates(snapshot_comp, comp_query, [])

    # 2. Mutate mock data drastically
    orig_candidates = list(MOCK_CANDIDATES)
    orig_entities = list(SAMPLE_GRAPH_ENTITIES)
    orig_chunks = list(SAMPLE_POLICY_CHUNKS)
    try:
        MOCK_CANDIDATES.clear()
        MOCK_CANDIDATES.append({
            "evidence_id": "corrupted-mock-cand",
            "source_id": "corrupted",
            "source_kind": "document",
            "content": "FAKE CONTENT TO DETECT CORRUPTION",
            "source_locator": {"locator_type": "fake"},
            "score": 999.0,
            "rank": 1,
            "token_cost": 1,
        })
        SAMPLE_GRAPH_ENTITIES.clear()
        SAMPLE_POLICY_CHUNKS.clear()

        # 3. Second run with corrupted mocks
        doc_cand_after = _document_candidates(policy_query, chunks, index, top_k=5, snapshot_dir=snapshot_policy)
        comp_cand_after, comp_receipt_after = computation_candidates(snapshot_comp, comp_query)
        ent_cand_after = entity_catalog_candidates(snapshot_comp, comp_query, [])

        # 4. Assert absolute invariance
        assert doc_cand_before == doc_cand_after
        assert comp_cand_before == comp_cand_after
        assert comp_receipt_before == comp_receipt_after
        assert ent_cand_before == ent_cand_after
    finally:
        # Restore mock fixtures for subsequent tests
        MOCK_CANDIDATES.clear()
        MOCK_CANDIDATES.extend(orig_candidates)
        SAMPLE_GRAPH_ENTITIES.clear()
        SAMPLE_GRAPH_ENTITIES.extend(orig_entities)
        SAMPLE_POLICY_CHUNKS.clear()
        SAMPLE_POLICY_CHUNKS.extend(orig_chunks)


def test_runtime_refuses_private_oracle_paths():
    """Verify runtime path safety rejects any path into private/oracle or private/eval."""
    release = RELEASE_DIR.resolve()
    private_oracle = release / "private" / "oracle"

    with pytest.raises(PublicRoutingViolationError):
        validate_public_path_safety(private_oracle)


def test_no_retrieval_module_imports_mock_fixtures():
    """Ensure that no module in gsm_memory.retrieval imports test mock fixtures."""
    import gsm_memory.retrieval as ret_pkg
    pkg_dir = Path(ret_pkg.__file__).parent

    for py_file in pkg_dir.glob("*.py"):
        if py_file.name == "__pycache__":
            continue
        code = py_file.read_text(encoding="utf-8")
        assert "tests.fixtures" not in code, f"Production module {py_file.name} imports tests.fixtures"
        assert "MOCK_CANDIDATES" not in code, f"Production module {py_file.name} references MOCK_CANDIDATES"
        assert "SAMPLE_GRAPH_ENTITIES" not in code, f"Production module {py_file.name} references SAMPLE_GRAPH_ENTITIES"
        assert "SAMPLE_POLICY_CHUNKS" not in code, f"Production module {py_file.name} references SAMPLE_POLICY_CHUNKS"
