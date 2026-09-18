from __future__ import annotations

from typing import Any

from .catalog import CaseSpec
from .ledger import AcceptedAssertion, reduce_prefix
from .locators import catalog_row_digest, source_registry_digest, source_set_digest
from .primitives import stable_id


WINDOWS = {
    "W10":("2026-09-09T17:00:00.000000Z","2026-09-10T17:00:00.000000Z"),
    "W11":("2026-09-10T17:00:00.000000Z","2026-09-11T17:00:00.000000Z"),
    "W12":("2026-09-11T17:00:00.000000Z","2026-09-12T17:00:00.000000Z"),
    "W13":("2026-09-12T17:00:00.000000Z","2026-09-13T17:00:00.000000Z"),
    "W14":("2026-09-13T17:00:00.000000Z","2026-09-14T17:00:00.000000Z"),
    "WA14":("2026-09-13T17:00:00.000000Z","2026-09-14T03:00:00.000000Z"),
    "WA15":("2026-09-14T17:00:00.000000Z","2026-09-15T03:00:00.000000Z"),
    "WW0":("2026-09-06T17:00:00.000000Z","2026-09-13T17:00:00.000000Z"),
    "WW1":("2026-08-30T17:00:00.000000Z","2026-09-06T17:00:00.000000Z"),
    "WW2":("2026-08-23T17:00:00.000000Z","2026-08-30T17:00:00.000000Z"),
}


def _clause_refs(row: dict[str, Any], names: list[str]) -> list[dict[str, Any]]:
    by_id={x["clause_id"]:x for x in row["clauses"]}
    return [{k:by_id[name][k] for k in ("clause_id","span_start","span_end","coordinate_system","content_sha256")} for name in names]


def document_locator(row: dict[str, Any], sid: str, clauses: list[str]) -> dict[str, Any]:
    return {"locator_type":"document_clause","public_snapshot_id":sid,"document_revision_id":row["document_revision_id"],"source_snapshot_id":row.get("snapshot_id"),"policy_version_id":row.get("policy_version_id"),"normalized_sha256":row["normalized_sha256"],"publication_assertion_id":row["publication_assertion_id"],"clause_refs":_clause_refs(row,clauses)}


def _valid_at(valid: dict[str, Any], at: str) -> bool:
    if valid["kind"]=="point": return valid["at"]==at
    if valid["kind"]!="interval": return True
    end=valid["to"];return valid["from"]<=at and (end["kind"]=="unbounded" or at<end["at"])


def ledger_locator(item: AcceptedAssertion, records: dict[str, dict[str, Any]], sources: dict[str, dict[str, Any]], sid: str, world_id: str, ledger_id: str, scope_id: str) -> dict[str, Any]:
    record=records[item.record_id];a=item.payload
    return {"locator_type":"ledger_assertion","public_snapshot_id":sid,"world_id":world_id,"ledger_id":ledger_id,"scope_id":scope_id,"record_id":record["record_id"],"assertion_id":a["assertion_id"],"source_id":record["source_id"],"source_registry_digest":source_registry_digest(sources[record["source_id"]]),"payload_hash":record["payload_hash"],"logical_fact_id":a["logical_fact_id"],"predicate":a["predicate"],"subject_id":a["subject_id"],"valid_extent":a["valid"],"known_at":record["known_at"],"known_to_at_prefix":item.known_to,"revision_operation":record["operation"],"target_assertion_ids":record["target_assertion_ids"]}


def coverage_locator(artifact: dict[str, Any], sid: str, ledger_id: str) -> dict[str, Any]:
    spec=artifact["coverage_spec"];source_set=artifact["source_set"]
    return {"locator_type":"coverage_artifact","public_snapshot_id":sid,"branch_ledger_id":ledger_id,"world_id":spec["world_id"],"scope_id":spec["scope_id"],"artifact_id":artifact["artifact_id"],"artifact_revision":artifact["artifact_revision"],"coverage_spec_id":artifact["coverage_spec_id"],"coverage_spec_version":artifact["coverage_spec_version"],"subject_id":spec["subject_id"],"covered_domain":spec["covered_domain"],"valid_window":spec["valid_window"],"source_set_id":source_set["source_set_id"],"source_set_version":source_set["source_set_version"],"source_set_digest":source_set_digest(source_set),"completeness_cutoff":spec["completeness"]["known_at_lte"],"correction_policy_version":"canonical_bitemporal_reducer-v1","members_digest":artifact["members_digest"],"member_count":artifact["member_count"],"coverage_content_digest_v1":artifact["coverage_content_digest_v1"],"publication_record_id":artifact["publication_record_id"],"publication_assertion_id":artifact["publication_assertion_id"]}


def support_source_refs(
    spec: CaseSpec, role: str, ids: dict[str,str], sid: str, ledger_id: str,
    records: list[dict[str,Any]], sources_list: list[dict[str,Any]], docs: dict[str,dict[str,Any]],
    synthetic: dict[str,dict[str,Any]], definitions: dict[str,dict[str,Any]], artifacts: dict[str,dict[str,Any]],
) -> list[dict[str, Any]]:
    sources={x["source_id"]:x for x in sources_list};record_map={x["record_id"]:x for x in records};view=reduce_prefix(records,sources,spec.known)
    entity_alias = "D_A" if spec.task in ("T02","T03","T05") else "D_C" if spec.alias in {"C025","C028"} else "D_D" if spec.alias=="C026" else "D_A" if spec.alias=="C027" else "D_B" if spec.alias in {"C029","C030","C031","C040"} else "D_G" if spec.alias in {"C033","C034","C035","C036"} else "D_E" if spec.alias in {"C037","C038"} else "D_H" if spec.alias=="C039" else "D_F" if spec.alias=="C042" else None
    if role in {"document_clause","document_rule"}:
        alias="P154" if spec.task in ("T01","T02") else "P151" if spec.task=="T03" else "P005" if spec.task in ("T04","T05") else "P023"
        clause_map={
            "C001":["s154.scope","s154.region"],"C002":["s154.day","s154.revenue","s154.charge"],
            "C017":["s05.clock"],"C018":["s05.units"],"C019":["s05.unrated","s05.week"],
            "C023":["s23.scope"],"C024":["s23.date"],
        }
        defaults={"T02":["s154.charge"],"T03":["s151.auto"],"T05":["s05.rating"],"T07":["s23.scope"]}
        locator=document_locator(docs[alias],sid,clause_map.get(spec.alias,defaults.get(spec.task,[next(iter(docs[alias]["clauses"]))])))
        return [{"source_kind":"document","source_id":docs[alias].get("snapshot_id"),"locator":locator}]
    if role=="synthetic_rule":
        key="S_BRIDGE:v1";row=synthetic[stable_id("policy_version",key)]
        locator=document_locator(row,sid,[x["clause_id"] for x in row["clauses"]])
        return [{"source_kind":"document","source_id":row["policy_version_id"],"locator":locator}]
    if role=="metric_definition":
        row=definitions[stable_id("definition","M01")]
        locator={"locator_type":"definition_artifact","public_snapshot_id":sid,"definition_id":row["definition_id"],"definition_version":row["version"],"content_sha256":row["content_sha256"]}
        return [{"source_kind":"definition","source_id":row["definition_id"],"locator":locator}]
    if role in {"fleet_registry","candidate_identity"}:
        aliases=["D_E","D_F"] if role=="candidate_identity" else (["F1"] if spec.alias=="C025" else ["F2"])
        result=[]
        for alias in aliases:
            row=next(x for x in docs["__entities__"] if x["entity_id"]==ids[alias])
            locator={"locator_type":"entity_catalog","public_snapshot_id":sid,"world_id":ids["world"],"scope_id":ids["scope"],"entity_id":row["entity_id"],"entity_type":row["entity_type"],"catalog_row_digest":catalog_row_digest(row)}
            result.append({"source_kind":"entity_catalog","source_id":row["entity_id"],"locator":locator})
        return result
    coverage_key=None
    if role=="complete_coverage" and spec.alias=="C029": coverage_key="terminal_trips_db_w30"
    elif role in {"terminal_population","complete_coverage"} and spec.alias=="C039": coverage_key="terminal_trips_dh_w30"
    elif role=="incident_evidence" and spec.alias in {"C030","C031"}: coverage_key="incidents_db_through_tm"
    if coverage_key:
        artifact=artifacts[coverage_key];return [{"source_kind":"coverage","source_id":artifact["artifact_id"],"locator":coverage_locator(artifact,sid,ledger_id)}]

    def active(predicate: str, subject: str | None=None) -> list[AcceptedAssertion]:
        return [x for x in view if x.known_to is None and x.payload["predicate"]==predicate and (subject is None or x.payload["subject_id"]==subject)]
    selected: list[AcceptedAssertion]=[]
    if role=="driver_program": selected=active("DRIVER_PROGRAM",ids[entity_alias])
    elif role=="operating_region": selected=active("OPERATES_IN",ids[entity_alias])
    elif role in {"operating_day","reported_revenue","reported_acceptance","reported_rating"}:
        definition={"operating_day":"RM_OPDAY","reported_revenue":"RM_REVENUE","reported_acceptance":"RM_ACCEPTANCE","reported_rating":"RM_RATING"}[role]
        selected=[x for x in active("REPORTED_MEASURE",ids[entity_alias]) if x.payload["qualifiers"]["definition_id"]==definition and f"[{x.payload['qualifiers']['window_start']},{x.payload['qualifiers']['window_end']})" in spec.text.replace(" ","")]
        if not selected:
            labels=[k for k in WINDOWS if k in spec.text];selected=[x for x in active("REPORTED_MEASURE",ids[entity_alias]) if x.payload["qualifiers"]["definition_id"]==definition and labels and (x.payload["qualifiers"]["window_start"],x.payload["qualifiers"]["window_end"])==WINDOWS[labels[0]]]
    elif role=="membership":
        at="2026-09-14T03:00:00.000000Z" if spec.task=="T07" else "2026-09-15T17:00:00.000000Z"
        selected=[x for x in active("MEMBER_OF",ids[entity_alias]) if _valid_at(x.payload["valid"],at)]
    elif role=="fleet_region":
        membership=[x for x in active("MEMBER_OF",ids[entity_alias]) if _valid_at(x.payload["valid"],"2026-09-15T17:00:00.000000Z")];fleet=membership[0].payload["object"]["value"] if membership else ids["F6"];selected=active("BASED_IN",fleet)
    elif role=="incident_evidence":
        owned=active("HAS_INCIDENT",ids[entity_alias]);selected=owned
        for item in owned:selected+=active("INCIDENT_STATUS",item.payload["object"]["value"])
    elif role=="state_assertion":
        predicate="OPERATES_IN" if entity_alias=="D_E" else "DRIVER_STATUS";at="2026-08-01T12:00:00.000000Z" if entity_alias=="D_E" else ("2026-09-17T16:59:59.999999Z" if spec.alias=="C033" else "2026-09-17T17:00:00.000000Z");selected=[x for x in active(predicate,ids[entity_alias]) if _valid_at(x.payload["valid"],at)]
    elif role=="terminal_event": selected=[x for x in active("TRIP_OUTCOME",ids["D_G"]) if x.payload["qualifiers"]["trip_id"]==stable_id("trip","D_G:0")]
    elif role=="policy_publication": selected=active("POLICY_PUBLICATION",stable_id("policy_version","S_VERSION:v2"))
    elif role=="terminal_population":
        start,end=WINDOWS.get("W30",("2026-08-16T17:00:00.000000Z","2026-09-15T17:00:00.000000Z"));selected=[x for x in active("TRIP_OUTCOME",ids[entity_alias]) if start<=x.payload["valid"]["at"]<end]
    if not selected: raise ValueError(f"no public support found for {spec.alias}:{role}")
    return [{"source_kind":"operational","source_id":item.source_id,"locator":ledger_locator(item,record_map,sources,sid,ids["world"],ledger_id,ids["scope"])} for item in selected]
