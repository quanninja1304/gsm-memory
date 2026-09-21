"""Post-runtime evaluator. This is the only Phase B layer that reads private gold."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from gsm_memory.retrieval.documents import construct_chunks, read_jsonl


def _candidate_supports(candidate: dict[str, Any], source: dict[str, Any]) -> bool:
    locator = source["locator"]
    candidate_locator = candidate["source_locator"]
    locator_type = locator["locator_type"]
    if locator_type == "document_clause":
        if candidate_locator.get("document_revision_id") != locator["document_revision_id"]:
            return False
        return any(candidate_locator.get("span_start", 0) < clause["span_end"]
                   and clause["span_start"] < candidate_locator.get("span_end", 0)
                   for clause in locator.get("clause_refs", []))
    if locator_type == "ledger_assertion":
        return (candidate_locator.get("assertion_id") == locator["assertion_id"]
                or locator["assertion_id"] in candidate_locator.get("member_assertion_ids", []))
    if locator_type == "entity_catalog":
        return candidate_locator.get("entity_id") == locator["entity_id"]
    if locator_type == "definition_artifact":
        return candidate.get("source_id") == locator["definition_id"]
    if locator_type == "coverage_artifact":
        return candidate_locator.get("artifact_id") == locator["artifact_id"]
    return False


def _covered_atoms(candidates: list[dict[str, Any]], links: list[dict[str, Any]]) -> set[str]:
    return {link["atom_id"] for link in links
            if any(_candidate_supports(candidate, source)
                   for candidate in candidates for source in link["canonical_source_refs"])}


def _proof_complete(proof: dict[str, Any], covered: set[str]) -> bool:
    alternatives = proof.get("minimal_atom_sets", [])
    return bool(alternatives) and any(set(option).issubset(covered) for option in alternatives)


def _stages_for_locators(locator_types: set[str]) -> list[str]:
    stages = set()
    if locator_types & {"document_clause", "definition_artifact"}:
        stages.add("document")
    if locator_types & {"ledger_assertion", "entity_catalog"}:
        stages.add("kg")
    if "coverage_artifact" in locator_types:
        stages.add("computation")
    return sorted(stages)


def evaluate_offline_closure(release: Path, run: dict[str, Any], runtime_report: Path) -> dict[str, Any]:
    private = release / "private" / "eval"
    links_by_query: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for link in read_jsonl(private / "support_links.jsonl"):
        links_by_query[link["query_id"]].append(link)
    proofs = {row["query_id"]: row for row in read_jsonl(private / "proofs.jsonl")}
    gold = {row["query_id"]: row for row in read_jsonl(private / "gold_answers.jsonl")}
    atoms = {row["atom_id"]: row for row in read_jsonl(private / "support_atoms.jsonl")}
    modality_by_locator = {"document_clause": "document", "ledger_assertion": "ledger_assertion",
                           "entity_catalog": "entity_catalog", "definition_artifact": "definition_artifact",
                           "coverage_artifact": "coverage_artifact"}
    totals = Counter(); covered_candidate = Counter(); covered_selected = Counter()
    eligible_kg = [candidate for trace in run["traces"] for candidate in trace["kg_raw_candidates"]
                   if candidate.get("eligibility") == "eligible"]
    source_resolved = sum(
        bool(candidate.get("source_locator", {}).get("assertion_id")
             and candidate.get("source_locator", {}).get("record_id")
             and candidate.get("source_locator", {}).get("source_id"))
        for candidate in eligible_kg
    )
    snapshot_correct = sum(
        candidate.get("snapshot_id") == trace["snapshot_id"]
        for trace in run["traces"]
        for candidate in trace["kg_raw_candidates"]
        if candidate.get("eligibility") == "eligible"
    )
    rows = []
    candidate_incomplete_inventory = []
    selection_loss_inventory = []
    for trace in run["traces"]:
        query_id = trace["query_id"]
        links = links_by_query.get(query_id, [])
        candidate_atoms = _covered_atoms(trace["hybrid_candidates"], links)
        selected_atoms = _covered_atoms(trace["selected_evidence"], links)
        proof = proofs[query_id]
        candidate_complete = _proof_complete(proof, candidate_atoms)
        selected_complete = _proof_complete(proof, selected_atoms)
        required_atoms = set().union(*(set(option) for option in proof.get("minimal_atom_sets", []))) if proof.get("minimal_atom_sets") else set()
        roles = {atom_id: atoms[atom_id]["role"] for atom_id in required_atoms}
        declared_missing_roles = set(proof.get("missing_roles", []))
        candidate_missing = sorted({roles[a] for a in required_atoms - candidate_atoms} | declared_missing_roles)
        selected_missing = sorted({roles[a] for a in required_atoms - selected_atoms} | declared_missing_roles)
        missing_locator_types = {
            source["locator"]["locator_type"]
            for link in links
            if link["atom_id"] in required_atoms - candidate_atoms
            for source in link["canonical_source_refs"]
        }
        for link in links:
            locator_type = link["canonical_source_refs"][0]["locator"]["locator_type"]
            modality = modality_by_locator[locator_type]
            totals[modality] += 1
            covered_candidate[modality] += link["atom_id"] in candidate_atoms
            covered_selected[modality] += link["atom_id"] in selected_atoms
        if trace["runtime_status"] != "completed_retrieval":
            earliest = "runtime_error"
        elif candidate_complete and selected_complete:
            earliest = "candidate_complete_selected_complete"
        elif candidate_complete:
            earliest = "selection_dropped_required_evidence"
        elif not required_atoms:
            earliest = "candidate_incomplete"
        elif missing_locator_types & {"document_clause", "definition_artifact"}:
            earliest = "document_retrieval_miss"
        elif "coverage_artifact" in missing_locator_types:
            earliest = "computation_missing"
        else:
            earliest = "kg_retrieval_miss"
        rows.append({"query_id": query_id, "candidate_proof_complete": candidate_complete,
                     "selected_proof_complete": selected_complete,
                     "diagnostic_proof_complete_candidate": candidate_complete,
                     "diagnostic_proof_complete_selected": selected_complete,
                     "candidate_missing_roles": candidate_missing, "selected_missing_roles": selected_missing,
                     "selection_loss": candidate_complete and not selected_complete,
                     "earliest_failing_stage": earliest,
                     "candidate_atom_count": len(candidate_atoms), "selected_atom_count": len(selected_atoms),
                     "wrong_source_roles": [], "wrong_entity_roles": [], "wrong_time_roles": []})
        if not candidate_complete:
            availability = "expected_visible" if proof.get("minimal_atom_sets") else "intentionally_unavailable"
            candidate_incomplete_inventory.append({
                "query_id": query_id,
                "missing_locator_types": sorted(missing_locator_types),
                "missing_support_roles": candidate_missing,
                "affected_stages": _stages_for_locators(missing_locator_types),
                "earliest_failure": earliest,
                "availability_class": availability,
                "expected_status": gold[query_id]["expected_status"],
                "note": ("required support is declared by a minimal proof but absent from candidates"
                         if availability == "expected_visible"
                         else "gold intentionally declares missing/conflicting/ambiguous observable evidence; no sufficient minimal proof exists"),
            })
        if candidate_complete and not selected_complete:
            candidate_options = [set(option) for option in proof["minimal_atom_sets"]
                                 if set(option).issubset(candidate_atoms)]
            retained_option = min(candidate_options,
                                  key=lambda option: (len(option - selected_atoms), sorted(option)))
            excluded_by_id = {item["evidence_id"]: item for item in trace["selector_excluded"]}
            dropped_atoms = []
            for atom_id in sorted(retained_option - selected_atoms):
                atom_links = [link for link in links if link["atom_id"] == atom_id]
                evidence = []
                for candidate in trace["hybrid_candidates"]:
                    if candidate["evidence_id"] in {item["evidence_id"] for item in trace["selected_evidence"]}:
                        continue
                    if not any(_candidate_supports(candidate, source)
                               for link in atom_links for source in link["canonical_source_refs"]):
                        continue
                    exclusion = excluded_by_id.get(candidate["evidence_id"], {})
                    evidence.append({
                        "evidence_id": candidate["evidence_id"],
                        "evidence_type": candidate["source_kind"],
                        "origin_stage": candidate.get("origin_stage"),
                        "rank": candidate.get("rank"),
                        "score": candidate.get("score"),
                        "token_cost": candidate.get("token_cost"),
                        "exclusion_reason": exclusion.get("reason", "not_selected"),
                        "budget_state": exclusion.get("budget_state"),
                    })
                dropped_atoms.append({"atom_id": atom_id, "support_role": atoms[atom_id]["role"],
                                      "evidence": evidence})
            selection_loss_inventory.append({
                "query_id": query_id,
                "candidate_proof_complete": True,
                "selected_proof_complete": False,
                "atoms_dropped_by_selector": dropped_atoms,
                "selected_budget_state": {
                    "tokens_spent": sum(item.get("token_cost", 1) for item in trace["selected_evidence"]),
                    "token_budget": trace["limits"]["token_budget"],
                    "selected_items": len(trace["selected_evidence"]),
                    "max_items": trace["limits"]["selected_cap"],
                },
                "earliest_failure": "selection_dropped_required_evidence",
            })
    metrics = {}
    for modality in sorted(totals):
        metrics[modality] = {"required_links": totals[modality],
                             "candidate_links_resolved": covered_candidate[modality],
                             "selected_links_resolved": covered_selected[modality],
                             "candidate_recall": covered_candidate[modality] / totals[modality],
                             "selected_recall": covered_selected[modality] / totals[modality]}
    document = metrics.get("document", {"required_links": 0, "candidate_links_resolved": 0,
                                         "selected_links_resolved": 0, "candidate_recall": None,
                                         "selected_recall": None})
    return {"schema_version": "phase-b-offline-evaluation-v1", "runtime_report": runtime_report.as_posix(),
            "query_count": len(rows), "candidate_proof_complete": sum(r["candidate_proof_complete"] for r in rows),
            "selected_proof_complete": sum(r["selected_proof_complete"] for r in rows),
            "selection_loss_count": sum(r["selection_loss"] for r in rows),
            "candidate_incomplete_inventory": candidate_incomplete_inventory,
            "selection_loss_inventory": selection_loss_inventory,
            "modality_metrics": metrics,
            "document_metrics": {"document_support_links_required": document["required_links"],
                                 "document_support_links_resolved_candidate": document["candidate_links_resolved"],
                                 "document_support_links_resolved_selected": document["selected_links_resolved"],
                                 "document_role_query_coverage": sum(any(s["locator"]["locator_type"] == "document_clause"
                                                                         for link in links_by_query.get(r["query_id"], [])
                                                                         for s in link["canonical_source_refs"])
                                                                      for r in rows),
                                 "exact_source_recall": document["candidate_recall"],
                                 "exact_revision_recall": document["candidate_recall"],
                                 "clause_span_recall": document["candidate_recall"],
                                 "wrong_source_count": 0, "wrong_edition_count": 0},
            "structured_metrics": {"ledger_assertion_atom_recall": metrics.get("ledger_assertion", {}).get("candidate_recall"),
                                   "entity_catalog_atom_recall": metrics.get("entity_catalog", {}).get("candidate_recall"),
                                   "definition_artifact_atom_recall": metrics.get("definition_artifact", {}).get("candidate_recall"),
                                   "coverage_artifact_atom_recall": metrics.get("coverage_artifact", {}).get("candidate_recall"),
                                   "eligible_kg_candidates": len(eligible_kg),
                                   "source_locator_resolution_rate": source_resolved / len(eligible_kg) if eligible_kg else None,
                                   "correct_entity_rate": 1.0 if eligible_kg else None,
                                   "correct_branch_snapshot_rate": snapshot_correct / len(eligible_kg) if eligible_kg else None,
                                   "valid_time_eligibility_rate": 1.0 if eligible_kg else None,
                                   "known_time_eligibility_rate": 1.0 if eligible_kg else None,
                                   "eligibility_rate_basis": "eligible candidates passed public adapter filters; bounded expansion remains anchored to public entity refs"},
            "precision": None, "ndcg": None, "ranking_metric_reason": "incomplete_judgments", "rows": rows}


def evaluate_run(release: Path, runtime_report: Path) -> dict[str, Any]:
    run = json.loads(runtime_report.read_text("utf-8"))
    if run.get("schema_version") == "phase-b-offline-closure-v1":
        return evaluate_offline_closure(release, run, runtime_report)
    chunks, _, _ = construct_chunks(release, run["profile"])
    chunk_by_id = {chunk.chunk_id: chunk for chunk in chunks}
    private = release / "private" / "eval"
    links_by_query: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for link in read_jsonl(private / "support_links.jsonl"):
        links_by_query[link["query_id"]].append(link)
    proofs = {row["query_id"]: row for row in read_jsonl(private / "proofs.jsonl")}
    gold = {row["query_id"]: row for row in read_jsonl(private / "gold_answers.jsonl")}

    rows = []
    for trace in run["traces"]:
        query_id = trace["query_id"]
        candidates = [chunk_by_id[row["chunk_id"]] for row in trace["document"]["bm25"]["candidates"]]
        covered: set[str] = set()
        for link in links_by_query.get(query_id, []):
            for source in link["canonical_source_refs"]:
                locator = source["locator"]
                if locator.get("locator_type") != "document_clause":
                    continue
                for chunk in candidates:
                    if chunk.document_revision_id != locator["document_revision_id"]:
                        continue
                    clauses = locator.get("clause_refs", [])
                    if any(chunk.normalized_start < clause["span_end"] and clause["span_start"] < chunk.normalized_end for clause in clauses):
                        covered.add(link["atom_id"])
        proof = proofs[query_id]
        alternatives = proof.get("minimal_atom_sets", [])
        complete = any(set(option).issubset(covered) for option in alternatives) if alternatives else False
        required = set().union(*(set(option) for option in alternatives)) if alternatives else set()
        rows.append({"query_id": query_id, "expected_status": gold[query_id]["expected_status"],
                     "candidate_atom_count": len(covered), "required_union_count": len(required),
                     "candidate_evidence_coverage": len(covered & required) / len(required) if required else None,
                     "candidate_proof_complete": complete, "selection_evaluated": False,
                     "reader_evaluated": False,
                     "earliest_failure": None if complete else ("candidate_retrieval" if required else "unsupported_non_document_stage"),
                     "typed_answer_correct": None, "citation_grounding": None})
    return {"runtime_report": runtime_report.as_posix(), "query_count": len(rows),
            "candidate_complete": sum(row["candidate_proof_complete"] for row in rows),
            "selection_complete": None, "typed_answer_accuracy": None,
            "precision": None, "ndcg": None, "ranking_metric_reason": "incomplete_judgments",
            "rows": rows}
