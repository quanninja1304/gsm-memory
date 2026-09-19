import json
from pathlib import Path

from gsm_memory.evaluation.runtime import evaluate_offline_closure


RELEASE = Path("data/gsm-dev-core-0.2.2")


def test_evaluator_attributes_candidate_complete_selected_incomplete():
    query_id = "34313beb-91b2-5b88-8915-0db18aeeae8d"
    links = [
        json.loads(line)
        for line in (RELEASE / "private/eval/support_links.jsonl").read_text("utf-8").splitlines()
        if json.loads(line)["query_id"] == query_id
    ]
    locator = links[0]["canonical_source_refs"][0]["locator"]
    candidate = {
        "source_id": locator.get("source_id"),
        "source_locator": {
            "locator_type": "document_span",
            "document_revision_id": locator["document_revision_id"],
            "span_start": locator["clause_refs"][0]["span_start"],
            "span_end": locator["clause_refs"][0]["span_end"],
        },
    }
    run = {
        "traces": [{
            "query_id": query_id,
            "runtime_status": "completed_retrieval",
            "snapshot_id": "d4cc0438-d831-541a-8123-ddda94ccdac8",
            "kg_raw_candidates": [],
            "hybrid_candidates": [candidate],
            "selected_evidence": [],
        }]
    }
    result = evaluate_offline_closure(RELEASE, run, Path("runtime.json"))
    assert result["query_count"] == 1
    assert result["candidate_proof_complete"] == 1
    assert result["selected_proof_complete"] == 0
    assert result["selection_loss_count"] == 1
    assert result["rows"][0]["earliest_failing_stage"] == "selection_dropped_required_evidence"
    assert result["modality_metrics"]["document"]["candidate_recall"] == 1.0
    assert result["modality_metrics"]["document"]["selected_recall"] == 0.0
