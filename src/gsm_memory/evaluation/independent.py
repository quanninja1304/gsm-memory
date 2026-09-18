from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from typing import Any

from gsm_memory.data.locators import resolve_public_locator
from gsm_memory.data.primitives import read_jsonl
from .formulas import auto_accept, cancel_rate, rating_condition, revenue_charge


def _assertions(release: Path, sid: str, refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows=read_jsonl(release/f"public/snapshots/{sid}/text_observations.jsonl")
    values={a["assertion_id"]:a for r in rows for a in r["assertions"]}
    return [values[ref["locator"]["assertion_id"]] for ref in refs if ref["locator"]["locator_type"]=="ledger_assertion"]


def _artifact(release: Path, sid: str, refs: list[dict[str, Any]]) -> dict[str, Any] | None:
    artifacts={x["artifact_id"]:x for x in read_jsonl(release/f"public/snapshots/{sid}/artifacts.jsonl")}
    for ref in refs:
        if ref["locator"]["locator_type"]=="coverage_artifact": return artifacts[ref["locator"]["artifact_id"]]
    return None


def _active_value(assertions: list[dict[str, Any]]) -> tuple[str, Any]:
    if not assertions: return "missing",None
    values={json.dumps(x["object"],sort_keys=True) for x in assertions}
    if len(values)>1:return "unresolved_conflict",None
    return "accepted",assertions[0]["object"]["value"]


def reconstruct_release(release: Path) -> list[dict[str, Any]]:
    """Reconstruct outcomes from requests, public snapshots, locators, and frozen bindings.

    GoldAnswer rows and CaseSpec expected values are deliberately not read.
    """
    cases=read_jsonl(release/"private/eval/semantic_cases.jsonl")
    atoms={x["atom_id"]:x for x in read_jsonl(release/"private/eval/support_atoms.jsonl")}
    links=read_jsonl(release/"private/eval/support_links.jsonl")
    links_by_query:dict[str,dict[str,list[dict[str,Any]]]]={}
    for link in links:
        role=atoms[link["atom_id"]]["role"]
        links_by_query.setdefault(link["query_id"],{})[role]=link["canonical_source_refs"]
        for ref in link["canonical_source_refs"]: resolve_public_locator(release,ref["locator"])
    bindings={x["task_id"]:x for x in read_jsonl(release/"private/oracle/task_bindings.jsonl")}
    renderings={x["semantic_case_id"]:x for x in read_jsonl(release/"private/eval/query_renderings.jsonl")}
    results=[]
    for case in cases:
        query_id=renderings[case["semantic_case_id"]]["query_id"];sid=case["public_snapshot_id"];roles=links_by_query.get(query_id,{})
        request=case["evaluation_request"];operation=request["operation"];status="answerable";value:Any=None
        binding=bindings.get(case.get("task_id"));contract=binding["evaluation_contract"] if binding else {}
        if operation=="document_extract":
            values=contract["extract_values"];selected={key:values[key] for key in request["fields"]};value=next(iter(selected.values())) if len(selected)==1 else selected
        elif operation=="revenue_charge":
            day_status,day=_active_value(_assertions(release,sid,roles.get("operating_day",[])))
            if day_status!="accepted":status="insufficient_evidence"
            elif day is False:value={"verdict":"not_applicable","amount":None}
            else:
                revenue_status,revenue=_active_value(_assertions(release,sid,roles.get("reported_revenue",[])))
                if revenue_status=="unresolved_conflict":status="unresolved_conflict"
                elif revenue_status!="accepted":status="insufficient_evidence"
                else:value=revenue_charge(revenue)
        elif operation=="auto_accept":
            report_status,reported=_active_value(_assertions(release,sid,roles.get("reported_acceptance",[])))
            if report_status!="accepted":status="insufficient_evidence"
            else:
                condition=auto_accept(contract["eligible_program"],Fraction(reported["n"],reported["d"]));value={"condition_met":condition}
                if condition:value["until"]=contract["action_until_literal"]
        elif operation=="rating_condition":
            assertion=_assertions(release,sid,roles.get("reported_rating",[]))
            report_status,reported=_active_value(assertion)
            if report_status!="accepted" or not assertion or assertion[0]["object"]["type"]!="rational":status="insufficient_evidence"
            else:value=rating_condition(Fraction(reported["n"],reported["d"]))
        elif operation=="notice_scope":
            pstatus,program=_active_value(_assertions(release,sid,roles.get("driver_program",[])))
            if pstatus!="accepted":status="insufficient_evidence"
            elif program!=contract["eligible_program"]:value=False
            else:
                mstatus,fleet=_active_value(_assertions(release,sid,roles.get("membership",[])))
                if mstatus!="accepted":status="insufficient_evidence"
                else:value=fleet in contract["listed_fleet_ids"]
        elif operation=="cancel_rate":
            coverage=_artifact(release,sid,roles.get("complete_coverage",[]))
            population=_artifact(release,sid,roles.get("terminal_population",[]))
            if coverage is None and population is None:status="insufficient_evidence"
            else:
                artifact=population or coverage
                if artifact["member_count"]==0:value={"metric_status":"undefined","value":None}
                elif coverage is None:status="insufficient_evidence"
                else:
                    events=_assertions(release,sid,roles.get("terminal_population",[]));cancelled=sum(x["qualifiers"]["outcome"]=="cancelled" for x in events);completed=sum(x["qualifiers"]["outcome"]=="completed" for x in events);rate=cancel_rate(cancelled,completed);value={"n":rate.numerator,"d":rate.denominator}
        elif operation=="bridge_rule":
            fleet_status,fleet=_active_value(_assertions(release,sid,roles.get("membership",[])))
            region_status,region=_active_value(_assertions(release,sid,roles.get("fleet_region",[])))
            if fleet_status!="accepted" or region_status!="accepted":status="insufficient_evidence"
            else:
                incident_artifact=_artifact(release,sid,roles.get("incident_evidence",[]));incident_assertions=_assertions(release,sid,roles.get("incident_evidence",[]))
                if incident_artifact is not None:has_open=False
                elif incident_assertions:has_open=any(x["predicate"]=="INCIDENT_STATUS" and x["object"]["value"]=="open" for x in incident_assertions)
                else:status="insufficient_evidence";has_open=False
                if status=="answerable":value=not has_open
        elif operation=="entity_resolution":
            candidates=roles.get("candidate_identity",[]);status="ambiguous_request" if len(candidates)>1 else "answerable";value=None if len(candidates)>1 else candidates[0]["source_id"]
        elif operation=="state_at":
            state_status,state=_active_value(_assertions(release,sid,roles.get("state_assertion",[])))
            if state_status!="accepted":status="insufficient_evidence"
            elif request["predicate"]=="OPERATES_IN":
                entities={x["entity_id"]:x for x in read_jsonl(release/f"public/snapshots/{sid}/entity_catalog.jsonl")};value=entities[state]["semantic_code"]
            else:value=state
        elif operation=="event_outcome":
            assertions=_assertions(release,sid,roles.get("terminal_event",[]))
            if not assertions:status="insufficient_evidence"
            else:value=assertions[0]["qualifiers"]["outcome"]
        elif operation=="policy_version":
            assertions=_assertions(release,sid,roles.get("policy_publication",[]))
            if not assertions:status="insufficient_evidence"
            else:
                revision=assertions[0]["qualifiers"]["document_revision_id"]
                docs={x["document_revision_id"]:x for x in read_jsonl(release/f"public/snapshots/{sid}/documents.jsonl")};doc=docs[revision]
                text=(release/f"public/documents/normalized/{revision}.md").read_text(encoding="utf-8")
                entities=read_jsonl(release/f"public/snapshots/{sid}/entity_catalog.jsonl");region=next(x["semantic_code"] for x in entities if x.get("semantic_code") and x["entity_id"] in text)
                value={"version":doc["version_label"],"region":region}
        else: raise ValueError(f"unsupported independent operation: {operation}")
        results.append({"query_id":query_id,"semantic_case_id":case["semantic_case_id"],"status":status,"typed_value":value,"operation":operation,"resolved_roles":sorted(roles)})
    return results
