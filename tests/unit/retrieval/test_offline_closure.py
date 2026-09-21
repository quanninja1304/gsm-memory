import json
from pathlib import Path

from gsm_memory.retrieval.bm25 import BM25Index
from gsm_memory.retrieval.documents import construct_chunks
from gsm_memory.retrieval.offline import (
    _document_candidates,
    computation_candidates,
    graph_namespace_key,
    hybrid_union,
    select_public,
)


RELEASE = Path("data/gsm-dev-core-0.2.2")


def _queries() -> dict[str, dict]:
    path = RELEASE / "public/runtime_queries/dev.jsonl"
    return {row["query_id"]: row for row in map(json.loads, path.read_text("utf-8").splitlines())}


def _candidate(evidence_id: str, kind: str, locator: dict, *, source_id: str = "source", cost: int = 10):
    return {
        "evidence_id": evidence_id,
        "source_kind": kind,
        "source_id": source_id,
        "source_locator": locator,
        "score": 1.0,
        "rank": 1,
        "token_cost": cost,
    }


def test_graph_namespace_is_stable_and_snapshot_scoped():
    first = graph_namespace_key("release", "snapshot-a", "config", "adapter")
    assert first == graph_namespace_key("release", "snapshot-a", "config", "adapter")
    assert first != graph_namespace_key("release", "snapshot-b", "config", "adapter")


def test_hybrid_union_only_deduplicates_identical_canonical_locators():
    locator = {"locator_type": "document_span", "source_id": "P154", "span_start": 1, "span_end": 2}
    duplicate = _candidate("duplicate", "document", dict(locator))
    distinct = _candidate("distinct", "kg", {"locator_type": "ledger_assertion", "assertion_id": "a1"})
    merged = hybrid_union([_candidate("original", "document", locator)], [duplicate, distinct])
    assert {row["evidence_id"] for row in merged} == {"original", "distinct"}


def test_public_selector_is_deterministic_balanced_and_preserves_pin():
    query = {"application_context": {"definition_refs": ["definition-pinned"]}}
    candidates = [
        _candidate("doc", "document", {"locator_type": "document_span", "source_id": "P1"}),
        _candidate("definition", "definition", {"locator_type": "document_span", "source_id": "definition-pinned"}, source_id="definition-pinned"),
        _candidate("kg", "kg", {"locator_type": "ledger_assertion", "assertion_id": "a1"}),
        _candidate("coverage", "coverage", {"locator_type": "coverage_artifact", "artifact_id": "c1"}),
    ]
    selected_a, excluded_a = select_public(query, candidates, token_budget=30, max_items=3)
    selected_b, excluded_b = select_public(query, candidates, token_budget=30, max_items=3)
    assert (selected_a, excluded_a) == (selected_b, excluded_b)
    assert sum(row["token_cost"] for row in selected_a) <= 30
    assert "definition" in {row["evidence_id"] for row in selected_a}
    assert len({row["source_kind"] for row in selected_a}) == 3
    assert excluded_a[0]["reason"] == "token_budget_exceeded"
    assert excluded_a[0]["budget_state"]["tokens_spent"] == 30


def test_document_retrieval_keeps_zero_overlap_public_definition_pin():
    chunks, _, _ = construct_chunks(RELEASE, "retrieval_full")
    query = _queries()["34313beb-91b2-5b88-8915-0db18aeeae8d"]
    definition_id = query["application_context"]["definition_refs"][0]
    no_overlap = dict(query, query="zzzz_no_lexical_overlap_zzzz")
    candidates = _document_candidates(no_overlap, chunks, BM25Index(chunks), 10)
    pinned = [row for row in candidates if row["source_id"] == definition_id]
    assert len(pinned) == 1
    assert pinned[0]["score"] == 0.0
    assert pinned[0]["origin_stage"] == "public_pin_fallback"
    assert pinned[0]["source_locator"]["locator_type"] == "definition_artifact"
    assert pinned[0]["source_locator"]["definition_id"] == definition_id


def test_document_retrieval_searches_snapshot_allowlisted_definitions():
    chunks, _, _ = construct_chunks(RELEASE, "retrieval_full")
    query = _queries()["25629711-39a5-56e8-ba58-2ecad56ff85e"]
    snapshot = RELEASE / "public/snapshots" / query["public_snapshot_id"]
    candidates = _document_candidates(query, chunks, BM25Index(chunks), 10, snapshot)
    definition_ids = {
        row["source_locator"]["definition_id"]
        for row in candidates
        if row["source_locator"]["locator_type"] == "definition_artifact"
    }
    assert "7f1963d7-c231-5fb8-a63c-dd3f0b120d5f" in definition_ids


def test_full_source_computation_handles_defined_empty_and_missing_coverage():
    queries = _queries()
    expectations = {
        "25629711-39a5-56e8-ba58-2ecad56ff85e": ("complete", 10, {"n": 1, "d": 5}),
        "6ec051c3-469f-58f4-a3e9-8c7887d3ce91": ("complete", 0, None),
        "2655fa70-2a5a-510a-bf59-ecbd116de3a8": ("missing_coverage", 0, None),
    }
    for query_id, (status, member_count, typed_value) in expectations.items():
        query = queries[query_id]
        snapshot = RELEASE / "public/snapshots" / query["public_snapshot_id"]
        candidates, receipt = computation_candidates(snapshot, query)
        assert receipt["status"] == status
        assert receipt["enumerated_members"] == member_count
        computations = [row for row in candidates if row["source_kind"] == "computation"]
        if status == "complete":
            assert computations[0]["typed_value"] == typed_value
            assert len(computations[0]["members"]) == member_count
        else:
            assert candidates == []
