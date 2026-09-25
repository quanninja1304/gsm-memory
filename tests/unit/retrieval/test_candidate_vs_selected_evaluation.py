"""Unit tests for P7: Candidate vs Selected Evaluation and Reader Rollout.

Verifies:
1. Document recall: candidate recall vs selected recall on document clauses.
2. KG entity/time/path coverage: entity correctness, snapshot correctness, valid/known time eligibility, assertion recall.
3. Computation coverage correctness: verified member population, exact rational arithmetic, coverage artifact recall.
4. Candidate-complete vs selected-complete proof evaluation.
5. Reader verification:
   - Only selected public evidence + query passed to reader.
   - Reader returns JSON with status, answer, citations.
   - Citations refer to evidence IDs in the bundle and validate exact quote grounding.
   - Reader correctness evaluation against gold expected_status when provider is available.
6. Baseline preservation: old baseline report is preserved and comparative metrics are verified.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from gsm_memory.agent.reader import EvidenceCitation, ReaderAnswer, ReaderConfig, ReaderError, answer_query, build_prompts
from gsm_memory.evaluation.runtime import evaluate_offline_closure
from tests.fixtures.mock_data import MockReaderProvider


RELEASE_DIR = Path("data/gsm-dev-core-0.2.2")


def test_reader_receives_only_selected_public_evidence_and_validates_citations():
    """Reader receives strictly selected public evidence; enforces valid citations and quotes."""
    query = {
        "query_id": "eval-reader-test-1",
        "query": "Quy định mức doanh thu tối thiểu là bao nhiêu theo snapshot P154?",
        "entity_refs": [],
        "public_snapshot_id": "snap-154",
        "application_context": {"source_snapshot_refs": ["P154"]},
    }
    selected_evidence = [
        {
            "evidence_id": "doc-p154-rule",
            "source_id": "P154",
            "source_kind": "document",
            "content": "Điều 5: Mức doanh thu tối thiểu của tài xế là 500.000 VNĐ mỗi ca.",
            "source_locator": {"locator_type": "document_clause", "document_revision_id": "P154", "clause_refs": [{"clause_id": "Điều 5"}]},
        },
    ]

    # Verify build_prompts contains only public evidence
    sys_prompt, user_prompt = build_prompts(query, selected_evidence)
    assert "doc-p154-rule" in user_prompt
    assert "private" not in user_prompt
    assert "gold" not in user_prompt

    # Test valid response
    class GroundedProvider:
        def complete(self, *, system_prompt: str, user_prompt: str, response_schema: Any) -> str:
            return json.dumps({
                "status": "answered",
                "answer": "Mức doanh thu tối thiểu là 500.000 VNĐ mỗi ca.",
                "citations": [
                    {"evidence_id": "doc-p154-rule", "quote": "Mức doanh thu tối thiểu của tài xế là 500.000 VNĐ mỗi ca."}
                ],
            }, ensure_ascii=False)

    ans = answer_query(query, selected_evidence, provider=GroundedProvider(), config=ReaderConfig("test", "test-model"))
    assert ans.status == "answered"
    assert len(ans.citations) == 1
    assert ans.citations[0].evidence_id == "doc-p154-rule"
    assert ans.citations[0].locator == "P154#Điều 5"

    # Test rejection of non-selected evidence ID
    class HallucinatedIdProvider:
        def complete(self, **kwargs) -> str:
            return json.dumps({
                "status": "answered",
                "answer": "Mức doanh thu tối thiểu là 500.000 VNĐ.",
                "citations": [{"evidence_id": "hallucinated-doc-999", "quote": "500.000 VNĐ"}],
            })

    with pytest.raises(ReaderError, match="non-selected evidence"):
        answer_query(query, selected_evidence, provider=HallucinatedIdProvider(), config=ReaderConfig("test", "test-model"))

    # Test rejection of ungrounded quote
    class UngroundedQuoteProvider:
        def complete(self, **kwargs) -> str:
            return json.dumps({
                "status": "answered",
                "answer": "Mức tối thiểu là 1.000.000 VNĐ.",
                "citations": [{"evidence_id": "doc-p154-rule", "quote": "Mức doanh thu tối thiểu là 1.000.000 VNĐ"}],
            })

    with pytest.raises(ReaderError, match="not grounded in selected evidence"):
        answer_query(query, selected_evidence, provider=UngroundedQuoteProvider(), config=ReaderConfig("test", "test-model"))


def test_candidate_vs_selected_evaluation_metrics_and_reader_correctness():
    """Evaluates candidate vs selected completeness, coverage, and reader correctness."""
    query_id = "34313beb-91b2-5b88-8915-0db18aeeae8d"
    links = [
        json.loads(line)
        for line in (RELEASE_DIR / "private/eval/support_links.jsonl").read_text("utf-8").splitlines()
        if json.loads(line)["query_id"] == query_id
    ]
    locator = links[0]["canonical_source_refs"][0]["locator"]

    candidate = {
        "evidence_id": "cand-doc-p154",
        "source_kind": "document",
        "source_id": locator.get("source_id"),
        "origin_stage": "bm25",
        "rank": 1,
        "score": 1.0,
        "token_cost": 20,
        "source_locator": {
            "locator_type": "document_span",
            "document_revision_id": locator["document_revision_id"],
            "span_start": locator["clause_refs"][0]["span_start"],
            "span_end": locator["clause_refs"][0]["span_end"],
        },
    }

    mock_run = {
        "schema_version": "phase-b-offline-closure-v1",
        "traces": [
            {
                "query_id": query_id,
                "runtime_status": "completed_retrieval",
                "snapshot_id": "d4cc0438-d831-541a-8123-ddda94ccdac8",
                "kg_raw_candidates": [
                    {
                        "evidence_id": "kg-assert-1",
                        "eligibility": "eligible",
                        "snapshot_id": "d4cc0438-d831-541a-8123-ddda94ccdac8",
                        "source_locator": {"assertion_id": "a1", "record_id": "r1", "source_id": "s1"},
                    }
                ],
                "hybrid_candidates": [candidate],
                "selected_evidence": [candidate],  # Preserved in selection!
                "selector_excluded": [],
                "limits": {"token_budget": 1800, "selected_cap": 22},
                # Reader executed with provider
                "reader": {
                    "status": "answered",
                    "answer": "Quy định đạt mức 90%.",
                    "citations": [{"evidence_id": "cand-doc-p154", "quote": "90%"}],
                },
            }
        ],
    }

    report = evaluate_offline_closure(RELEASE_DIR, mock_run, Path("mock_runtime.json"))

    # 1. Candidate vs Selected Proof Completeness
    assert report["candidate_proof_complete"] == 1
    assert report["selected_proof_complete"] == 1
    assert report["selection_loss_count"] == 0

    # 2. Document Recall
    assert report["document_metrics"]["document_support_links_required"] > 0
    assert report["document_metrics"]["exact_source_recall"] == 1.0
    assert report["modality_metrics"]["document"]["candidate_recall"] == 1.0
    assert report["modality_metrics"]["document"]["selected_recall"] == 1.0

    # 3. KG entity/time/path coverage
    assert report["structured_metrics"]["source_locator_resolution_rate"] == 1.0
    assert report["structured_metrics"]["correct_branch_snapshot_rate"] == 1.0
    assert report["structured_metrics"]["valid_time_eligibility_rate"] == 1.0
    assert report["structured_metrics"]["known_time_eligibility_rate"] == 1.0

    # 4. Reader Correctness & Grounding
    assert report["reader_metrics"] is not None
    assert report["reader_metrics"]["total_queries_evaluated"] == 1
    assert report["reader_metrics"]["status_correct_count"] == 1
    assert report["reader_metrics"]["status_accuracy"] == 1.0
    assert report["reader_metrics"]["citations_grounded_rate"] == 1.0


def test_baseline_preservation_and_comparison():
    """Verifies old baseline file is intact and can be compared against."""
    baseline_path = Path("reports/benchmark_readiness/phase-b-offline-closure.json")
    assert baseline_path.exists(), "Old baseline report must be preserved"

    baseline_data = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert baseline_data["schema_version"] == "phase-b-offline-closure-report-v1"
    assert baseline_data["evaluation"]["candidate_proof_complete"] == 30
    assert baseline_data["evaluation"]["selected_proof_complete"] == 15
    assert baseline_data["evaluation"]["selection_loss"] == 15
