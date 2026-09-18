from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from gsm_memory.evaluation.formulas import auto_accept, cancel_rate, rating_condition, revenue_charge
from gsm_memory.evaluation.assurance import run_aux_incident_check, run_counterfactual_checks, run_ex_checks
from gsm_memory.evaluation.independent import reconstruct_release
from fractions import Fraction

from .catalog import CASES
from .contracts import ScenarioManifest
from .ledger import validate_ledger
from .locators import resolve_public_locator
from .primitives import ARCHIVE_SHA256, DATASET_VERSION, canonical_bytes, read_jsonl, sha256_bytes, sha256_file, write_json


class ValidationFailure(RuntimeError): pass


def _result(check_id:str,scope:str,ok:bool,expected:Any,actual:Any,errors:list[str]|None=None)->dict[str,Any]:
    return {"check_id":check_id,"scope":scope,"status":"pass" if ok else "fail","expected":expected,"actual":actual,"implicated_ids":errors or [],"artifact_hashes":[]}


def validate_release(root:Path, repo:Path, final_reproducibility:bool=False) -> dict[str,Any]:
    checks=[]
    manifest=json.loads((root/"private/eval/manifest.json").read_text(encoding="utf-8")); counts=manifest["counts"]
    expected={"real_sources":224,"debug_core_members":6,"retrieval_full_members":224,"audited_sources":6,"primary_gold_sources":4,"drivers":8,"terminal_trips":80,"scenario_roots":25,"scenario_variants":32,"ledgers":8,"semantic_cases":42,"query_renderings":42,"dev_queries":42,"test_queries":0,"public_snapshots":12}
    runtime_manifest=json.loads((root/"public/runtime_manifest.json").read_text(encoding="utf-8"))
    identity_ok=(manifest.get("dataset_version")==DATASET_VERSION and runtime_manifest.get("dataset_version")==DATASET_VERSION and all(counts[k]==v for k,v in expected.items()))
    checks.append(_result("V01","identity_shape",identity_ok,{"dataset_version":DATASET_VERSION,**expected},{"dataset_version":manifest.get("dataset_version"),**{k:counts.get(k) for k in expected}}))
    ledgers=manifest["ledgers"]
    source_rows=read_jsonl(root/"public/operational/source_registry.jsonl"); source_map={x["source_id"]:x for x in source_rows}
    ledger_ok=len(ledgers)==8 and len({x["ledger_id"] for x in ledgers})==8 and all(sha256_file(root/x["record_ledger_path"])==x["record_ledger_sha256"] for x in ledgers)
    try:
        for item in ledgers:
            narrative_path=(root/"public/operational/text_observations.jsonl") if item["record_ledger_path"]=="public/operational/record_ledger.parquet" else (root/Path(item["record_ledger_path"]).parent/"text_observations.jsonl")
            validate_ledger(read_jsonl(narrative_path),source_map)
    except Exception:
        ledger_ok=False
    checks.append(_result("V02","ledger",ledger_ok,"8 immutable ledger files with matching hashes",len(ledgers)))
    snaps=list((root/"public/snapshots").glob("*/manifest.json")); snap_rows=[json.loads(p.read_text(encoding="utf-8")) for p in snaps]
    time_ok=len(snaps)==12 and all(x["known_as_of"].endswith("Z") and x.get("dataset_version")==DATASET_VERSION for x in snap_rows)
    checks.append(_result("V03","time_isolation",time_ok,"12 cutoff-isolated packages",len(snaps)))
    formula_ok=(revenue_charge(200000),revenue_charge(280000),revenue_charge(300000),auto_accept("bike_partner",Fraction(49,100)),auto_accept("bike_partner",Fraction(1,2)),rating_condition(Fraction(97,20)),rating_condition(Fraction(49,10)),cancel_rate(2,8),cancel_rate(0,0))==(16000,0,0,True,False,False,True,Fraction(1,5),None)
    checks.append(_result("V04","measures",formula_ok,"exact arithmetic boundaries","pass" if formula_ok else "mismatch"))
    catalog=read_jsonl(root/"public/documents/catalog.jsonl"); real=[x for x in catalog if x.get("snapshot_id")]
    source_ok=len(real)==224 and all(sha256_file(root/f"public/documents/raw/{x['snapshot_id']}.md")==x["raw_sha256"] for x in real) and manifest["source_archive_sha256"]==ARCHIVE_SHA256
    checks.append(_result("V05","documents_audit",source_ok,"224 byte-verified documents",len(real)))
    gold=read_jsonl(root/"private/eval/gold_answers.jsonl"); proofs=read_jsonl(root/"private/eval/proofs.jsonl"); expected_status=Counter({"answerable":32,"insufficient_evidence":8,"unresolved_conflict":1,"ambiguous_request":1}); actual_status=Counter(x["expected_status"] for x in gold)
    proof_ok=len(gold)==len(proofs)==42 and actual_status==expected_status and all((p["minimal_atom_sets"] if p["status"]=="sufficient" else not p["minimal_atom_sets"]) for p in proofs)
    checks.append(_result("V06","gold_proofs",proof_ok,dict(expected_status),dict(actual_status)))
    scenarios=read_jsonl(root/"private/eval/scenarios.jsonl"); branch_ok=len({x["ledger_id"] for x in scenarios})==8 and all(x["mutation_type"]=="base" or x["mutation_spec"] for x in scenarios)
    checks.append(_result("V07","artifacts_branches",branch_ok,"8 branch identities and closed deltas",len({x['ledger_id'] for x in scenarios})))
    public_text="\n".join(p.read_text(encoding="utf-8",errors="ignore") for p in (root/"public").rglob("*.json*")); forbidden=[x for x in ["C001","expected_status","gold_track","mutation_type","primary_family"] if x in public_text]
    runtime_queries=read_jsonl(root/"public/runtime_queries/dev.jsonl")
    leaked_aliases=[q["query_id"] for q in runtime_queries if re.search(r"\b(?:C\d{3}|D_[A-H]|W(?:A|W)?\d+|L_(?:NO|WRONG|CONFLICT|RETRACT))\b",q["query"])]
    forbidden.extend(leaked_aliases)
    profiles={p.parent.name:json.loads(p.read_text(encoding="utf-8")) for p in (root/"public/corpus_profiles").glob("*/manifest.json")}; package_ok=profiles["debug_core"]["counts"]["real_articles"]==6 and profiles["retrieval_full"]["counts"]["real_articles"]==224 and not forbidden
    checks.append(_result("V08","packaging",package_ok,"6/224 allowlists and no private labels",forbidden or "clean"))
    a={p.stem:json.loads(p.read_text(encoding="utf-8")) for p in (root/"public/graph_inputs/mode_a").glob("*.json")};b={p.stem:json.loads(p.read_text(encoding="utf-8")) for p in (root/"public/graph_inputs/mode_b").glob("*.json")};parity=set(a)==set(b) and len(a)==12 and all(a[k]["snapshot_id"]==b[k]["snapshot_id"] for k in a)
    checks.append(_result("V09","projection_input_parity",parity,"12 identity-paired A/B manifests",len(a)))
    support_sources={r["snapshot_id"] for r in real if r["article_number"] in (154,151,5,23)}; profile_ok=support_sources <= set(profiles["debug_core"]["real_snapshot_ids"]) <= set(profiles["retrieval_full"]["real_snapshot_ids"])
    checks.append(_result("V10","profile_gold_compatibility",profile_ok,"four gold sources in both views",len(support_sources)))
    sm=[]
    try:
        parsed=[ScenarioManifest.model_validate(x) for x in scenarios]; sm.append(True)
    except Exception: sm.append(False)
    roots=defaultdict(list)
    for x in scenarios: roots[x["scenario_id"]].append(x)
    sm.extend([len({x["scenario_variant_id"] for x in scenarios})==32,len([x for x in scenarios if x["mutation_type"]=="base"])==25,
               all(sum(y["mutation_type"]=="base" for y in v)==1 for v in roots.values()),
               len(read_jsonl(root/"private/eval/semantic_cases.jsonl"))==42 and len(read_jsonl(root/"private/eval/query_renderings.jsonl"))==42,
               len(snaps)==12,len({x["ledger_id"] for x in scenarios})==8,len(roots)==25 and len(scenarios)==32])
    for i,ok in enumerate(sm,1):checks.append(_result(f"SM{i:02d}","scenario_manifest",ok,True,ok))
    for result in run_ex_checks():
        checks.append(_result(result["check_id"],"independent_semantic_fixture",result["ok"],result["expected"],result["actual"],result["implicated_ids"]))
    aux_ids=["AUX_IDENTITY","AUX_TIME","AUX_EVENT","AUX_INCIDENT","AUX_REVISION","AUX_POLICY","AUX_ARTIFACT","AUX_CONTEXT","AUX_ACCESS"]
    incident_result=run_aux_incident_check()
    aux_conditions=[len([x for x in pq.read_table(root/"private/oracle/entities.parquet").to_pylist() if x.get("entity_type")=="DRIVER"])==8,
                    any(x["known_as_of"]=="2026-08-04T00:00:00.000000Z" for x in snap_rows),len(pq.read_table(root/"private/oracle/events.parquet"))==80,
                    incident_result["ok"],actual_status["unresolved_conflict"]==1,any(x.get("source_mode")=="synthetic_control" for x in catalog),len(list((root/"public/operational/artifacts").glob("*.json")))==3,
                    all(p["status"]=="diagnostic" or p["minimal_atom_sets"] for p in proofs),all(x["access_scope"] and x["time_scope"]["mode"] in {"current","point","interval"} for x in runtime_queries)]
    for cid,ok in zip(aux_ids,aux_conditions):
        if cid=="AUX_INCIDENT":checks.append(_result(cid,"auxiliary",ok,incident_result["expected"],incident_result["actual"],incident_result["implicated_ids"]))
        else:checks.append(_result(cid,"auxiliary",ok,True,ok))
    for result in run_counterfactual_checks():
        checks.append(_result(result["check_id"],"counterfactual",result["ok"],result["expected"],result["actual"],result["implicated_ids"]))
    atoms={x["atom_id"]:x for x in read_jsonl(root/"private/eval/support_atoms.jsonl")};links=read_jsonl(root/"private/eval/support_links.jsonl")
    locator_errors=[];locator_types=Counter()
    for link in links:
        types={ref["locator"].get("locator_type") for ref in link["canonical_source_refs"]}
        if len(types)!=1: locator_errors.append(link["support_link_id"]);continue
        locator_types[next(iter(types))]+=1
        for ref in link["canonical_source_refs"]:
            try:resolve_public_locator(root,ref["locator"])
            except Exception as exc:locator_errors.append(f"{link['support_link_id']}:{exc}")
    expected_locators={"document_clause":31,"ledger_assertion":67,"entity_catalog":4,"definition_artifact":3,"coverage_artifact":5}
    locator_ok=len(links)==len(atoms)==110 and locator_types==Counter(expected_locators) and not locator_errors and {x["atom_id"] for x in links}==set(atoms)
    checks.append(_result("V11","source_level_locators",locator_ok,expected_locators,dict(locator_types),locator_errors))
    bindings=read_jsonl(root/"private/oracle/task_bindings.jsonl");required_binding_fields={"binding_id","binding_version","task_id","policy_snapshot_ids","allowed_clause_refs","audit_row_ids","public_definition_refs","convention_ids","formula_id","answer_scope","required_roles","evaluation_contract","status","gold_track"}
    binding_errors=[x.get("binding_id","missing-id") for x in bindings if set(x)!=required_binding_fields or x["status"]!="included" or not x["allowed_clause_refs"] or not x["required_roles"]]
    binding_ok=len(bindings)==7 and {x["task_id"] for x in bindings}=={f"T{i:02d}" for i in range(1,8)} and not binding_errors
    checks.append(_result("V12","structured_bindings",binding_ok,"B01-B07 complete",len(bindings),binding_errors))
    reconstructed=reconstruct_release(root);gold_by_query={x["query_id"]:x for x in gold};reconstruction_errors=[x["query_id"] for x in reconstructed if x["query_id"] not in gold_by_query or (x["status"],x["typed_value"])!=(gold_by_query[x["query_id"]]["expected_status"],gold_by_query[x["query_id"]]["typed_value"])]
    reconstruction_ok=len(reconstructed)==42 and not reconstruction_errors
    checks.append(_result("V13","independent_reconstruction",reconstruction_ok,"42/42",f"{42-len(reconstruction_errors)}/42",reconstruction_errors))
    all_artifacts=[json.loads(p.read_text(encoding="utf-8")) for p in (root/"public/operational/artifacts").glob("*.json")];db_artifact=next(x for x in all_artifacts if x["coverage_spec"]["covered_domain"]["domain_id"]=="terminal_trip_population" and x["member_count"]==10)
    scenario_no_cov=next(x for x in scenarios if x["mutation_type"]=="observation_mask" and db_artifact["publication_record_id"] in x["mutation_spec"].get("removed_record_ids",[]));no_cov_snapshot=next(x for x in snap_rows if x["ledger_id"]==scenario_no_cov["ledger_id"] and x["known_as_of"]=="2026-09-17T12:00:00.000000Z");no_cov_dir=root/"public/snapshots"/no_cov_snapshot["snapshot_id"]
    no_cov_artifacts=read_jsonl(no_cov_dir/"artifacts.jsonl");no_cov_records=read_jsonl(no_cov_dir/"text_observations.jsonl");trip_count=sum(a["predicate"]=="TRIP_OUTCOME" and a["subject_id"]==db_artifact["coverage_spec"]["subject_id"] for r in no_cov_records for a in r["assertions"])
    isolation_ok=db_artifact["artifact_id"] not in {x["artifact_id"] for x in no_cov_artifacts} and db_artifact["publication_record_id"] not in {x["record_id"] for x in no_cov_records} and trip_count==10
    checks.append(_result("V14","snapshot_branch_isolation",isolation_ok,{"coverage_visible":False,"trip_records":10},{"coverage_visible":db_artifact["artifact_id"] in {x["artifact_id"] for x in no_cov_artifacts},"trip_records":trip_count}))
    dfg={"DFG01":all(x["status"]=="pass" for x in checks if x["check_id"] in {"V05","V10","V12"}),"DFG02":all(x["status"]=="pass" for x in checks if x["check_id"] in {"V01","V02","V03","V04"} or x["check_id"].startswith("SM")),"DFG03":all(x["status"]=="pass" for x in checks if x["check_id"] in {"V05","V06","V07","V13"} or x["check_id"].startswith("EX") or x["check_id"].startswith("AUX")),"DFG04":all(x["status"]=="pass" for x in checks if x["check_id"] in {"V08","V09","V10","V11","V14"}),"DFG05":all(x["status"]=="pass" for x in checks) and counts["dev_queries"]==42 and counts["test_queries"]==0,"DFG06":final_reproducibility and all(x["status"]=="pass" for x in checks)}
    a1={"A1_G1":all(x["status"]=="pass" for x in checks if x["check_id"].startswith("CF")),"A1_G2":all(x["status"]=="pass" for x in checks if x["check_id"].startswith("AUX")),"A1_G3":locator_ok and binding_ok,"A1_G4":isolation_ok,"A1_G5":reconstruction_ok,"A1_G6":final_reproducibility and all(x["status"]=="pass" for x in checks)}
    report={"state":"VALIDATED" if all(x["status"]=="pass" for x in checks) else "FAILED","checks":checks,"summary":{"pass":sum(x["status"]=="pass" for x in checks),"fail":sum(x["status"]=="fail" for x in checks),"not_run":0},"dfg":{k:{"status":"pass" if v else "not_run" if k=="DFG06" and not final_reproducibility else "fail"} for k,v in dfg.items()},"a1":{k:{"status":"pass" if v else "not_run" if k=="A1_G6" and not final_reproducibility else "fail"} for k,v in a1.items()}}
    write_json(root/"private/eval/validation.json",report)
    if report["state"]!="VALIDATED": raise ValidationFailure("required validation failed")
    return report


def semantic_inventory(root:Path)->dict[str,str]:
    excluded={"private/eval/validation.json"}
    result={}
    for p in sorted(x for x in root.rglob("*") if x.is_file()):
        rel=p.relative_to(root).as_posix()
        if rel in excluded: continue
        if rel=="private/eval/manifest.json":
            manifest=json.loads(p.read_text(encoding="utf-8"))
            for key in ("state","validation_sha256","file_inventory","logical_inventory_digest"):
                manifest.pop(key,None)
            result[rel]=sha256_bytes(canonical_bytes(manifest))
        elif p.suffix==".parquet":
            rows=pq.read_table(p).to_pylist(); value=sorted((canonical_bytes(x) for x in rows));result[rel]=sha256_bytes(b"".join(value))
        else: result[rel]=sha256_file(p)
    return result


def compare_logical(a:Path,b:Path,report_path:Path)->dict[str,Any]:
    ia,ib=semantic_inventory(a),semantic_inventory(b);keys=sorted(set(ia)|set(ib));m=[{"path":k,"candidate_a":ia.get(k),"candidate_b":ib.get(k)} for k in keys if ia.get(k)!=ib.get(k)];report={"schema_version":"logical-comparison-v1","candidate_a":str(a.resolve()),"candidate_b":str(b.resolve()),"compared_files":len(keys),"status":"pass" if not m else "fail","mismatches":m,"inventory_digest":sha256_bytes(canonical_bytes(ia)) if not m else None};write_json(report_path,report);return report
