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
        "evidence_id": "candidate-document",
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
    run = {
        "traces": [{
            "query_id": query_id,
            "runtime_status": "completed_retrieval",
            "snapshot_id": "d4cc0438-d831-541a-8123-ddda94ccdac8",
            "kg_raw_candidates": [],
            "hybrid_candidates": [candidate],
            "selected_evidence": [],
            "selector_excluded": [{
                "evidence_id": "candidate-document",
                "reason": "selected_item_cap_reached",
                "budget_state": {"tokens_spent": 0, "token_budget": 10,
                                 "selected_items": 0, "max_items": 0,
                                 "candidate_would_fit_tokens": False},
            }],
            "limits": {"token_budget": 10, "selected_cap": 0},
        }]
    }
    result = evaluate_offline_closure(RELEASE, run, Path("runtime.json"))
    assert result["query_count"] == 1
    assert result["candidate_proof_complete"] == 1
    assert result["selected_proof_complete"] == 0
    assert result["selection_loss_count"] == 1
    assert len(result["selection_loss_inventory"]) == 1
    dropped = result["selection_loss_inventory"][0]["atoms_dropped_by_selector"]
    assert dropped[0]["evidence"][0]["exclusion_reason"] == "selected_item_cap_reached"
    assert result["rows"][0]["earliest_failing_stage"] == "selection_dropped_required_evidence"
    assert result["modality_metrics"]["document"]["candidate_recall"] == 1.0
    assert result["modality_metrics"]["document"]["selected_recall"] == 0.0


def test_evaluator_distinguishes_intentionally_unavailable_diagnostic_case():
    query_id = "89f98a43-5dbb-5b77-b8f1-990e8933d546"
    run = {"traces": [{
        "query_id": query_id,
        "snapshot_id": "df057563-78f4-5ac1-aba6-5b48c572fb4a",
        "runtime_status": "completed_retrieval",
        "kg_raw_candidates": [],
        "hybrid_candidates": [],
        "selected_evidence": [],
        "selector_excluded": [],
        "limits": {"token_budget": 1800, "selected_cap": 12},
    }]}
    result = evaluate_offline_closure(RELEASE, run, Path("runtime.json"))
    inventory = result["candidate_incomplete_inventory"]
    assert len(inventory) == 1
    assert inventory[0]["availability_class"] == "intentionally_unavailable"
    assert inventory[0]["missing_support_roles"] == ["operating_day"]
    assert inventory[0]["expected_status"] == "insufficient_evidence"
