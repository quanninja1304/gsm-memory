from __future__ import annotations

import json
import os
import platform
import shutil
import zipfile
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from .catalog import A0, AC, A1, CASES, ROOT_VARIANTS
from .contracts import ScenarioManifest
from .ledger import payload_hash
from gsm_memory.evaluation.oracle import evaluate_case
from .primitives import (
    ARCHIVE_SHA256, DATASET_VERSION, ROOT_SEED, SCHEMA_VERSION, SPEC_VERSION,
    canonical_bytes, logical_hash, rational, sha256_bytes, sha256_file, stable_id,
    utc, write_json, write_jsonl,
)

AUDITED = {
    154:("snap-154-d4af28195271","d4af281952715d325bf533c265e3b046cda622b3bd51e05d066d61b64439c033"),
    151:("snap-151-063bee730825","063bee7308254d5dbf4fc3c93edb0c1f902e80c3444082a83a686687d3be1368"),
    5:("snap-005-a4bc920aa65c","a4bc920aa65c42d81ac04e6b7594a74efc61fc7c2116bdbb1653c02ca5cecc4e"),
    23:("snap-023-b62fd1ddee0c","b62fd1ddee0ca6a0a75d3ccb6dfc85156c819560c233111a3995f862006103b4"),
    172:("snap-172-7c3be60e9040","7c3be60e90400504db49b83e2fb6eb0f745ae173d751f5b5351d3ca1f1c23c8d"),
    26:("snap-026-c308c04cb3de","c308c04cb3de5e219c5488d8091bcfd08fea673f1007f669ba9ba065e7a01315"),
}
CLAUSES = {
 154:{"s154.scope":(19,778,828),"s154.region":(17,750,776),"s154.date":(15,709,748),"s154.charge":(23,853,1097),"s154.day":(29,1224,1298),"s154.revenue":(31,1300,1404)},
 151:{"s151.scope":(15,656,705),"s151.auto":(21,767,921)},
 5:{"s05.clock":(131,6769,6921),"s05.units":(130,6641,6768),"s05.rating":(134,7363,8019),"s05.week":(135,8020,8345),"s05.unrated":(136,8346,8561)},
 23:{"s23.scope":(23,1019,1133),"s23.date":(25,1135,1187)},
}
LEDGERS = ["L0","L_NO_OPDAY","L_WRONG_DRIVER","L_CONFLICT","L_RETRACT","L_WRONG_WINDOW","L_NO_BRIDGE","L_NO_COVERAGE"]
DEFINITIONS = ["BC01","BC02","BC03","BC04","BC05","BC06","BC07","RM_REVENUE","RM_OPDAY","RM_ACCEPTANCE","RM_RATING","M01"]
PREDICATES = ["MEMBER_OF","BASED_IN","OPERATES_IN","USES_SERVICE","DRIVER_STATUS","DRIVER_CATEGORY","HAS_INCIDENT","INCIDENT_STATUS","TRIP_OUTCOME","ENTITY_NAME","POLICY_PUBLICATION","ARTIFACT_PUBLICATION","REPORTED_MEASURE","DRIVER_PROGRAM"]


def validate_build_config(config_path: Path) -> dict[str, Any]:
    if not config_path.is_file():
        raise FileNotFoundError(f"missing dataset config: {config_path}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    expected = {
        "schema_version": SCHEMA_VERSION,
        "release_spec_version": SPEC_VERSION,
        "dataset_version": DATASET_VERSION,
        "seed": ROOT_SEED,
        "source_archive_sha256": ARCHIVE_SHA256,
    }
    mismatches = {
        key: {"expected": value, "actual": config.get(key)}
        for key, value in expected.items()
        if config.get(key) != value
    }
    if mismatches:
        raise ValueError(f"dataset config identity mismatch: {mismatches}")
    return config


def _parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    def arrow_value(value: Any) -> Any:
        if isinstance(value, list):
            return [arrow_value(item) for item in value]
        if isinstance(value, dict):
            if not value:
                return {"_empty": None}
            if set(value) == {"type", "value"}:
                kind, raw = value["type"], value["value"]
                return {
                    "type": kind,
                    "boolean_value": raw if kind == "boolean" else None,
                    "integer_value": raw if kind == "integer" else None,
                    "rational_value": raw if kind == "rational" else None,
                    "string_value": raw if kind in {"enum", "entity_ref", "string"} else None,
                }
            return {key: arrow_value(item) for key, item in value.items()}
        return value
    materialized = [arrow_value(row) for row in rows]
    table = pa.Table.from_pylist(materialized) if rows else pa.table({"_empty": pa.array([], type=pa.bool_())})
    pq.write_table(table, path, compression="zstd", version="2.6", use_dictionary=False)


def source_inventory(repo: Path) -> list[dict[str, Any]]:
    archive = repo / "data/raw/archives/policy_green_sm_source.zip"
    if not archive.exists():
        raise FileNotFoundError(f"missing pinned source: {archive}")
    if sha256_file(archive) != ARCHIVE_SHA256:
        raise ValueError("pinned archive SHA-256 mismatch")
    source = repo / "external/policy_green_sm_corpus"
    files = sorted((p for p in source.glob("*.md") if not p.name.startswith("00_")), key=lambda p: int(p.name.split("_",1)[0]))
    if len(files) != 224 or (source / "00_Tong_hop_Tat_ca_Chinh_sach_Tin_tuc.md") not in list(source.glob("*.md")):
        raise ValueError("corpus must contain 224 individual articles plus aggregate")
    with zipfile.ZipFile(archive) as zf:
        zip_members = {Path(n).name: zf.read(n) for n in zf.namelist() if n.lower().endswith(".md")}
    rows=[]
    for path in files:
        alias=int(path.name.split("_",1)[0]); raw=path.read_bytes(); raw_hash=sha256_bytes(raw)
        matching=[b for name,b in zip_members.items() if name == path.name]
        if len(matching)!=1 or matching[0] != raw:
            raise ValueError(f"archive/checkout byte mismatch: {path.name}")
        if alias in AUDITED and raw_hash != AUDITED[alias][1]:
            raise ValueError(f"audited hash mismatch P{alias}")
        snapshot_id = AUDITED[alias][0] if alias in AUDITED else stable_id("source_snapshot",f"{path.name}|{raw_hash}")
        normalized=raw.decode("utf-8").replace("\r\n","\n").encode("utf-8")
        revision_id=stable_id("document_revision",f"{snapshot_id}|crlf-to-lf-v1|{sha256_bytes(normalized)}")
        rows.append({"alias":f"P{alias:03d}","article_number":alias,"snapshot_id":snapshot_id,"document_revision_id":revision_id,
                     "archive_member_path":path.name,"raw_sha256":raw_hash,"normalized_sha256":sha256_bytes(normalized),
                     "posted_date":path.name.split("_",2)[1],"review_state":"audited" if alias in AUDITED else "unreviewed",
                     "raw_bytes":raw,"normalized_bytes":normalized})
    return rows


def _world() -> tuple[list[dict[str,Any]],list[dict[str,Any]],list[dict[str,Any]],dict[str,str]]:
    scope=stable_id("scope","S0"); world=stable_id("world","W0")
    ids={k:stable_id("entity",k) for k in [*(f"D_{x}" for x in "ABCDEFGH"),"F1","F2","F6","F7","HN","HCM_OLD","SERVICE","I_F"]}
    names={"D_A":"An","D_B":"Bình","D_C":"Chi","D_D":"Dũng","D_E":"Minh","D_F":"Minh","D_G":"Giang","D_H":"Hà",
           "F1":"Depot Hồ Chí Minh 1","F2":"Depot Hồ Chí Minh 2","F6":"Depot Hồ Chí Minh 6","F7":"Depot Hồ Chí Minh 7","HN":"Hà Nội","HCM_OLD":"TP.HCM theo địa giới cũ","SERVICE":"Dịch vụ tổng hợp","I_F":"Sự cố F"}
    types={**{f"D_{x}":"DRIVER" for x in "ABCDEFGH"},**{f:"FLEET" for f in ["F1","F2","F6","F7"]},"HN":"REGION","HCM_OLD":"REGION","SERVICE":"SERVICE","I_F":"INCIDENT"}
    entities=[{"schema_version":SCHEMA_VERSION,"world_id":world,"entity_id":ids[k],"entity_type":types[k],"scope_id":scope,
               "existence":{"kind":"interval","from":"2026-07-01T00:00:00.000000Z","to":{"kind":"unbounded"}},
               "name":{"name_id":stable_id("name",k),"text":names[k],"kind":"display","locale":"vi-VN"}} for k in ids]
    counts=[12,10,14,14,10,10,10,0]; events=[]
    for di,n in enumerate(counts):
        driver=f"D_{chr(65+di)}"
        for j in range(n):
            when=datetime(2026,8,18,2,tzinfo=UTC)+timedelta(days=j,minutes=di)
            if driver=="D_G" and j==0: when=datetime(2026,8,20,2,tzinfo=UTC)
            outcome="cancelled" if driver=="D_B" and j in (0,1) else "completed"
            trip=stable_id("trip",f"{driver}:{j}")
            events.append({"schema_version":SCHEMA_VERSION,"world_id":world,"world_event_id":stable_id("world_event",trip),"trip_id":trip,
                           "driver_id":ids[driver],"event_type":"TRIP_OUTCOME","event_time":utc(when),"outcome":outcome,
                           "service_id":ids["SERVICE"],"region_id":ids["HN"] if driver=="D_A" else ids["HCM_OLD"],
                           "reason_code":"driver_request" if outcome=="cancelled" else "unspecified"})
    facts=[]
    fleets={"D_A":"F1","D_B":"F6","D_C":"F2","D_D":"F2","D_E":"F6","D_F":"F6","D_G":"F7","D_H":"F7"}
    for d,f in fleets.items():
        facts.extend([{"world_fact_id":stable_id("world_fact",f"program:{d}"),"world_id":world,"subject_id":ids[d],"predicate":"DRIVER_PROGRAM","object":{"type":"enum","value":"taxi_driver" if d in ("D_C","D_D") else "bike_partner"},"valid":{"kind":"interval","from":"2026-07-01T00:00:00.000000Z","to":{"kind":"unbounded"}}},
                      {"world_fact_id":stable_id("world_fact",f"member:{d}"),"world_id":world,"subject_id":ids[d],"predicate":"MEMBER_OF","object":{"type":"entity_ref","value":ids[f]},"valid":{"kind":"interval","from":"2026-07-01T00:00:00.000000Z","to":{"kind":"unbounded"}}}])
    for f in ["F1","F2","F6","F7"]:
        facts.append({"world_fact_id":stable_id("world_fact",f"based:{f}"),"world_id":world,"subject_id":ids[f],"predicate":"BASED_IN","object":{"type":"entity_ref","value":ids["HCM_OLD"]},"valid":{"kind":"interval","from":"2026-07-01T00:00:00.000000Z","to":{"kind":"unbounded"}}})
    ids.update(world=world,scope=scope)
    return entities,events,facts,ids


def _sources(ids: dict[str,str]) -> list[dict[str,Any]]:
    specs=[("registry","registry",["MEMBER_OF","BASED_IN","OPERATES_IN","DRIVER_STATUS","DRIVER_CATEGORY","ENTITY_NAME","DRIVER_PROGRAM"]),
           ("event","event_log",["TRIP_OUTCOME"]),("incident","incident_log",["HAS_INCIDENT","INCIDENT_STATUS"]),
           ("feed_a","metric_feed",["REPORTED_MEASURE"]),("feed_b","metric_feed",["REPORTED_MEASURE"]),
           ("policy","policy_publisher",["POLICY_PUBLICATION","ARTIFACT_PUBLICATION"]),("derived","derived",["ARTIFACT_PUBLICATION"])]
    rows=[]
    for alias,kind,preds in specs:
        sid=stable_id("source",alias)
        rows.append({"source_id":sid,"scope_id":ids["scope"],"source_kind":kind,"authority_rank":10,"allowed_predicates":preds,"can_correct_source_ids":[sid],"timezone":"Asia/Ho_Chi_Minh","alias":alias})
    return rows


def _assertion(key:str,subject:str,predicate:str,obj:dict[str,Any],valid:dict[str,Any],qualifiers:dict[str,Any]|None=None,event_time:str|None=None)->dict[str,Any]:
    return {"assertion_id":stable_id("assertion",key),"logical_fact_id":stable_id("logical_fact",key.split("@",1)[0]),"subject_id":subject,"predicate":predicate,"object":obj,
            "qualifiers":qualifiers or {},"valid":valid,"event_time":event_time,"source_refs":[]}


def _record(key:str,source_id:str,scope_id:str,known_at:str,operation:str,assertions:list[dict[str,Any]],targets:list[str]=[])->dict[str,Any]:
    row={"record_id":stable_id("source_record",key),"source_id":source_id,"scope_id":scope_id,"known_at":known_at,"commit_seq":0,"operation":operation,
         "target_assertion_ids":targets,"assertions":assertions,"raw_payload":{"renderer":"deterministic-source-v1"}}
    row["payload_hash"]=payload_hash(row); return row


def _ledgers(ids:dict[str,str],events:list[dict[str,Any]],sources:list[dict[str,Any]],docs:list[dict[str,Any]]) -> tuple[dict[str,list[dict[str,Any]]],dict[str,dict[str,Any]]]:
    sm={s["alias"]:s["source_id"] for s in sources}; scope=ids["scope"]; base=[]; rec={}
    unbounded={"kind":"interval","from":"2026-07-01T00:00:00.000000Z","to":{"kind":"unbounded"}}
    for d in "ABCDEFGH":
        alias=f"D_{d}"; program="taxi_driver" if alias in ("D_C","D_D") else "bike_partner"; fleet={"A":"F1","B":"F6","C":"F2","D":"F2","E":"F6","F":"F6","G":"F7","H":"F7"}[d]
        for pred,obj in [("DRIVER_PROGRAM",{"type":"enum","value":program}),("MEMBER_OF",{"type":"entity_ref","value":ids[fleet]}),("OPERATES_IN",{"type":"entity_ref","value":ids["HN"] if d=="A" else ids["HCM_OLD"]})]:
            if (alias,pred) in {("D_C","MEMBER_OF"),("D_E","OPERATES_IN")}:
                continue
            key=f"{pred}:{alias}"; base.append(_record(key,sm["registry"],scope,"2026-07-01T00:00:00.000000Z","assert",[_assertion(key,ids[alias],pred,obj,unbounded)]))
    for f in ["F1","F2","F6","F7"]:
        key=f"BASED_IN:{f}"; base.append(_record(key,sm["registry"],scope,"2026-07-01T00:00:00.000000Z","assert",[_assertion(key,ids[f],"BASED_IN",{"type":"entity_ref","value":ids["HCM_OLD"]},unbounded)]))
    # Bitemporal correction controls: each replace republishes the complete atomic schedule.
    c_old1=_assertion("MEMBER_OF:D_C@old-f1",ids["D_C"],"MEMBER_OF",{"type":"entity_ref","value":ids["F1"]},{"kind":"interval","from":"2026-08-31T17:00:00.000000Z","to":{"kind":"finite","at":"2026-09-14T17:00:00.000000Z"}})
    c_old2=_assertion("MEMBER_OF:D_C@old-f2",ids["D_C"],"MEMBER_OF",{"type":"entity_ref","value":ids["F2"]},{"kind":"interval","from":"2026-09-14T17:00:00.000000Z","to":{"kind":"unbounded"}})
    base.append(_record("MEMBER_OF:D_C@old",sm["registry"],scope,"2026-09-01T00:00:00.000000Z","assert",[c_old1,c_old2]))
    c_new1=_assertion("MEMBER_OF:D_C@new-f1",ids["D_C"],"MEMBER_OF",{"type":"entity_ref","value":ids["F1"]},{"kind":"interval","from":"2026-08-31T17:00:00.000000Z","to":{"kind":"finite","at":"2026-09-13T17:00:00.000000Z"}})
    c_new2=_assertion("MEMBER_OF:D_C@new-f2",ids["D_C"],"MEMBER_OF",{"type":"entity_ref","value":ids["F2"]},{"kind":"interval","from":"2026-09-13T17:00:00.000000Z","to":{"kind":"unbounded"}})
    base.append(_record("MEMBER_OF:D_C@correction",sm["registry"],scope,AC,"replace",[c_new1,c_new2],[c_old1["assertion_id"],c_old2["assertion_id"]]))
    e_old1=_assertion("OPERATES_IN:D_E@old-hn",ids["D_E"],"OPERATES_IN",{"type":"entity_ref","value":ids["HN"]},{"kind":"interval","from":"2026-07-01T00:00:00.000000Z","to":{"kind":"finite","at":"2026-07-31T17:00:00.000000Z"}})
    e_old2=_assertion("OPERATES_IN:D_E@old-hcm",ids["D_E"],"OPERATES_IN",{"type":"entity_ref","value":ids["HCM_OLD"]},{"kind":"interval","from":"2026-07-31T17:00:00.000000Z","to":{"kind":"unbounded"}})
    base.append(_record("OPERATES_IN:D_E@old",sm["registry"],scope,"2026-08-03T00:00:00.000000Z","assert",[e_old1,e_old2]))
    e_new1=_assertion("OPERATES_IN:D_E@new-hn",ids["D_E"],"OPERATES_IN",{"type":"entity_ref","value":ids["HN"]},{"kind":"interval","from":"2026-07-01T00:00:00.000000Z","to":{"kind":"finite","at":"2026-08-01T17:00:00.000000Z"}})
    e_new2=_assertion("OPERATES_IN:D_E@new-hcm",ids["D_E"],"OPERATES_IN",{"type":"entity_ref","value":ids["HCM_OLD"]},{"kind":"interval","from":"2026-08-01T17:00:00.000000Z","to":{"kind":"unbounded"}})
    base.append(_record("OPERATES_IN:D_E@correction",sm["registry"],scope,"2026-08-05T00:00:00.000000Z","replace",[e_new1,e_new2],[e_old1["assertion_id"],e_old2["assertion_id"]]))
    status_a=_assertion("DRIVER_STATUS:D_G@active",ids["D_G"],"DRIVER_STATUS",{"type":"enum","value":"active"},{"kind":"interval","from":"2026-07-01T00:00:00.000000Z","to":{"kind":"finite","at":"2026-09-17T17:00:00.000000Z"}})
    status_s=_assertion("DRIVER_STATUS:D_G@suspended",ids["D_G"],"DRIVER_STATUS",{"type":"enum","value":"suspended"},{"kind":"interval","from":"2026-09-17T17:00:00.000000Z","to":{"kind":"unbounded"}})
    base.append(_record("DRIVER_STATUS:D_G",sm["registry"],scope,"2026-09-16T01:00:00.000000Z","assert",[status_a,status_s]))
    incident_owner=_assertion("HAS_INCIDENT:D_F:I_F",ids["D_F"],"HAS_INCIDENT",{"type":"entity_ref","value":ids["I_F"]},unbounded)
    incident_open=_assertion("INCIDENT_STATUS:I_F",ids["I_F"],"INCIDENT_STATUS",{"type":"enum","value":"open"},{"kind":"interval","from":"2026-09-01T00:00:00.000000Z","to":{"kind":"unbounded"}})
    base.append(_record("INCIDENT:D_F",sm["incident"],scope,"2026-09-01T00:00:00.000000Z","assert",[incident_owner,incident_open]))
    for policy,version,valid_from,valid_to in [("S_BRIDGE","v1","2026-07-01T00:00:00.000000Z",None),("S_VERSION","v1","2026-08-31T17:00:00.000000Z","2026-09-14T17:00:00.000000Z"),("S_VERSION","v2","2026-09-14T17:00:00.000000Z",None)]:
        key=f"POLICY:{policy}:{version}"; valid={"kind":"interval","from":valid_from,"to":{"kind":"finite","at":valid_to} if valid_to else {"kind":"unbounded"}}
        base.append(_record(key,sm["policy"],scope,"2026-07-01T00:00:00.000000Z" if policy=="S_BRIDGE" or version=="v1" else "2026-09-10T00:00:00.000000Z","assert",[_assertion(key,stable_id("policy_version",f"{policy}:{version}"),"POLICY_PUBLICATION",{"type":"enum","value":"issued"},valid)]))
    for e in events:
        key=f"TRIP:{e['trip_id']}"; known=AC if e["driver_id"]==ids["D_G"] and e["trip_id"]==stable_id("trip","D_G:0") else utc(datetime.fromisoformat(e["event_time"].replace("Z","+00:00"))+timedelta(hours=1))
        a=_assertion(key,e["driver_id"],"TRIP_OUTCOME",{"type":"entity_ref","value":e["service_id"]},{"kind":"point","at":e["event_time"]},{"trip_id":e["trip_id"],"outcome":e["outcome"],"region_id":e["region_id"],"reason_code":e["reason_code"]},e["event_time"])
        base.append(_record(key,sm["event"],scope,known,"assert",[a]))
    windows={"W10":("2026-09-09T17:00:00.000000Z","2026-09-10T17:00:00.000000Z"),"W11":("2026-09-10T17:00:00.000000Z","2026-09-11T17:00:00.000000Z"),"W12":("2026-09-11T17:00:00.000000Z","2026-09-12T17:00:00.000000Z"),"W13":("2026-09-12T17:00:00.000000Z","2026-09-13T17:00:00.000000Z"),"W14":("2026-09-13T17:00:00.000000Z","2026-09-14T17:00:00.000000Z"),"WA14":("2026-09-13T17:00:00.000000Z","2026-09-14T03:00:00.000000Z"),"WA15":("2026-09-14T17:00:00.000000Z","2026-09-15T03:00:00.000000Z"),"WW0":("2026-09-06T17:00:00.000000Z","2026-09-13T17:00:00.000000Z"),"WW1":("2026-08-30T17:00:00.000000Z","2026-09-06T17:00:00.000000Z"),"WW2":("2026-08-23T17:00:00.000000Z","2026-08-30T17:00:00.000000Z")}
    measures=[("OPDAY","W10",False),("OPDAY","W11",True),("OPDAY","W12",True),("OPDAY","W13",True),("OPDAY","W14",True),("REVENUE","W11",200000),("REVENUE","W12",280000),("REVENUE","W13",300000),("REVENUE","W14",200000),("ACCEPTANCE","WA14",rational(49,100)),("ACCEPTANCE","WA15",rational(1,2)),("ACCEPTANCE","W14",rational(49,100)),("RATING","WW0",rational(97,20)),("RATING","WW1",rational(49,10)),("RATING","WW2","undefined")]
    for definition,w,value in measures:
        key=f"RM:{definition}:D_A:{w}"; status="undefined" if value=="undefined" else "reported"; typed={"type":"enum","value":"undefined"} if status=="undefined" else {"type":"boolean" if isinstance(value,bool) else "integer" if isinstance(value,int) else "rational","value":value}
        q={"definition_id":f"RM_{definition}","definition_version":"1.0","window_start":windows[w][0],"window_end":windows[w][1],"calendar_id":"BC01","timezone":"Asia/Ho_Chi_Minh","reported_status":status,"unit":{"OPDAY":"boolean","REVENUE":"VND","ACCEPTANCE":"fraction","RATING":"stars_5"}[definition],"undefined_reason":"no_observations" if status=="undefined" else None}
        a=_assertion(key,ids["D_A"],"REPORTED_MEASURE",typed,{"kind":"interval","from":windows[w][0],"to":{"kind":"finite","at":windows[w][1]}},q); r=_record(key,sm["feed_a"],scope,"2026-09-16T01:00:00.000000Z","assert",[a]); base.append(r); rec[key]=(r,a)
    key="RM:REVENUE:D_B:W11"; a=_assertion(key,ids["D_B"],"REPORTED_MEASURE",{"type":"integer","value":200000},{"kind":"interval","from":windows["W11"][0],"to":{"kind":"finite","at":windows["W11"][1]}},{"definition_id":"RM_REVENUE","definition_version":"1.0","window_start":windows["W11"][0],"window_end":windows["W11"][1],"calendar_id":"BC01","timezone":"Asia/Ho_Chi_Minh","reported_status":"reported","unit":"VND","undefined_reason":None}); r=_record(key,sm["feed_a"],scope,"2026-09-16T01:00:00.000000Z","assert",[a]);base.append(r);rec[key]=(r,a)
    old=rec["RM:REVENUE:D_A:W14"][1]; new=_assertion("RM:REVENUE:D_A:W14@r2",ids["D_A"],"REPORTED_MEASURE",{"type":"integer","value":240000},old["valid"],old["qualifiers"]); replacement=_record("RM:REVENUE:D_A:W14@r2",sm["feed_a"],scope,AC,"replace",[new],[old["assertion_id"]]);base.append(replacement)
    for d in docs:
        key=f"DOC:{d['snapshot_id']}"; a=_assertion(key,d["snapshot_id"],"ARTIFACT_PUBLICATION",{"type":"enum","value":"available"},{"kind":"not_applicable"},{"artifact_kind":"source_snapshot","content_sha256":d["raw_sha256"]});base.append(_record(key,sm["policy"],scope,"2026-09-16T00:00:00.000000Z","assert",[a]))
    artifacts={}
    for label,members in [("coverage_db",[e["trip_id"] for e in events if e["driver_id"]==ids["D_B"]]),("coverage_dh",[]),("incident_db",[])]:
        aid=stable_id("artifact",label); artifacts[label]={"artifact_id":aid,"artifact_type":"coverage","member_ids":sorted(members),"member_count":len(members),"complete":True,"content_hash":sha256_bytes(canonical_bytes(sorted(members)))}
        key=f"ART:{label}"; base.append(_record(key,sm["derived"],scope,"2026-09-16T03:00:00.000000Z","assert",[_assertion(key,aid,"ARTIFACT_PUBLICATION",{"type":"enum","value":"available"},{"kind":"not_applicable"},{"artifact_kind":"coverage"})])); rec[key]=(base[-1],base[-1]["assertions"][0])
    conflict=_assertion("RM:REVENUE:D_A:W14@conflict",ids["D_A"],"REPORTED_MEASURE",{"type":"integer","value":240000},old["valid"],old["qualifiers"])
    conflict_r=_record("RM:REVENUE:D_A:W14@conflict",sm["feed_b"],scope,AC,"assert",[conflict])
    retract_r=_record("RM:REVENUE:D_A:W14@retract",sm["feed_a"],scope,AC,"retract",[],[old["assertion_id"]])
    branches={name:list(base) for name in LEDGERS}
    branches["L_NO_OPDAY"]=[x for x in base if x["record_id"]!=rec["RM:OPDAY:D_A:W11"][0]["record_id"]]
    branches["L_WRONG_DRIVER"]=[x for x in base if x["record_id"]!=rec["RM:REVENUE:D_A:W11"][0]["record_id"]]
    branches["L_WRONG_WINDOW"]=[x for x in base if x["record_id"]!=rec["RM:ACCEPTANCE:D_A:WA14"][0]["record_id"]]
    branches["L_NO_BRIDGE"]=[x for x in base if x["record_id"]!=stable_id("source_record","BASED_IN:F6")]
    branches["L_NO_COVERAGE"]=[x for x in base if x["record_id"]!=rec["ART:coverage_db"][0]["record_id"]]
    branches["L_CONFLICT"]=[x for x in base if x["record_id"]!=replacement["record_id"]]+[conflict_r]
    branches["L_RETRACT"]=[x for x in base if x["record_id"]!=replacement["record_id"]]+[retract_r]
    union={r["record_id"]:r for rows in branches.values() for r in rows}
    order=sorted(union.values(),key=lambda x:(x["known_at"],x["source_id"],x["record_id"]))
    seq={r["record_id"]:i+1 for i,r in enumerate(order)}
    for name,rows in branches.items():
        branches[name]=sorted([{**r,"commit_seq":seq[r["record_id"]]} for r in rows],key=lambda r:(r["known_at"],r["commit_seq"]))
    return branches,artifacts


def _case_outputs(ids:dict[str,str],ledger_ids:dict[str,str],snapshot_ids:dict[tuple[str,str],str],docs_by_alias:dict[str,dict[str,Any]],branches:dict[str,list[dict[str,Any]]],sources:list[dict[str,Any]]) -> dict[str,list[dict[str,Any]]]:
    split_group=stable_id("split_group","W0-cohort"); cases=[];renders=[];gold=[];queries=[];proofs=[];atoms=[];links=[];splits=[]
    for spec in CASES:
        cid=stable_id("semantic_case",spec.alias); qid=stable_id("query",spec.alias); sid=snapshot_ids[(spec.ledger,spec.known)]
        taskref=spec.task or f"FND:{spec.foundation}"; intent=f"{taskref}:{spec.family}"
        cases.append({"semantic_case_id":cid,"scenario_variant_id":stable_id("scenario_variant",f"{spec.root}:{spec.ledger}"),"query_intent":intent,"task_id":spec.task,"foundation_task":spec.foundation,"known_as_of":spec.known,"scope_id":ids["scope"],"public_snapshot_id":sid,"application_context_refs":[stable_id("definition","BC07")],"answer_scope":taskref,"expected_status":spec.status,"proof_refs":[stable_id("proof",spec.alias)]})
        entity_alias = "D_A" if spec.task in ("T02","T03","T05") else "D_C" if spec.alias in {"C025","C028"} else "D_D" if spec.alias=="C026" else "D_A" if spec.alias=="C027" else "D_B" if spec.alias in {"C029","C030","C031","C040"} else "D_G" if spec.alias in {"C033","C034","C035","C036"} else "D_E" if spec.alias in {"C037","C038"} else "D_H" if spec.alias=="C039" else "D_F" if spec.alias=="C042" else None
        source_alias = "P154" if spec.task in ("T01","T02") else "P151" if spec.task=="T03" else "P005" if spec.task in ("T04","T05") else "P023" if spec.task in ("T06","T07") else None
        source_refs = [docs_by_alias[source_alias]["snapshot_id"]] if source_alias else []
        query_text=spec.text
        for label,key in (("P154","P154"),("P151","P151"),("P05","P005"),("P23","P023")):
            query_text=query_text.replace(label,docs_by_alias[key]["snapshot_id"])
        rendered_windows={"W10":("2026-09-09T17:00:00.000000Z","2026-09-10T17:00:00.000000Z"),"W11":("2026-09-10T17:00:00.000000Z","2026-09-11T17:00:00.000000Z"),"W12":("2026-09-11T17:00:00.000000Z","2026-09-12T17:00:00.000000Z"),"W13":("2026-09-12T17:00:00.000000Z","2026-09-13T17:00:00.000000Z"),"W14":("2026-09-13T17:00:00.000000Z","2026-09-14T17:00:00.000000Z"),"WA14":("2026-09-13T17:00:00.000000Z","2026-09-14T03:00:00.000000Z"),"WA15":("2026-09-14T17:00:00.000000Z","2026-09-15T03:00:00.000000Z"),"WW0":("2026-09-06T17:00:00.000000Z","2026-09-13T17:00:00.000000Z"),"WW1":("2026-08-30T17:00:00.000000Z","2026-09-06T17:00:00.000000Z"),"WW2":("2026-08-23T17:00:00.000000Z","2026-08-30T17:00:00.000000Z")}
        case_window={"C003":"W11","C004":"W12","C005":"W13","C006":"W10","C007":"W11","C008":"W11","C009":"W14","C010":"W14","C011":"W14","C012":"W14","C013":"W14","C014":"WA14","C015":"WA15","C016":"WA14","C020":"WW0","C021":"WW1","C022":"WW2"}.get(spec.alias)
        for label,(start,end) in sorted(rendered_windows.items(),key=lambda item:-len(item[0])):
            query_text=query_text.replace(label,f"[{start},{end})")
        query_text=query_text.replace("S_BRIDGE",stable_id("policy_version","S_BRIDGE:v1")).replace("S_VERSION",stable_id("policy_version","S_VERSION:v2"))
        if case_window:
            start,end=rendered_windows[case_window];time_scope={"mode":"interval","start":start,"end":end,"timezone":"Asia/Ho_Chi_Minh"}
        elif spec.alias in {"C025","C026","C027","C028"}: time_scope={"mode":"point","valid_at":"2026-09-14T03:00:00.000000Z"}
        elif spec.alias in {"C029","C039","C040"}: time_scope={"mode":"interval","start":"2026-08-16T17:00:00.000000Z","end":"2026-09-15T17:00:00.000000Z","timezone":"Asia/Ho_Chi_Minh"}
        elif spec.alias in {"C030","C031","C032","C042"}: time_scope={"mode":"point","valid_at":"2026-09-15T17:00:00.000000Z"}
        elif spec.alias in {"C033","C034"}: time_scope={"mode":"point","valid_at":"2026-09-17T16:59:59.999999Z" if spec.alias=="C033" else "2026-09-17T17:00:00.000000Z"}
        elif spec.alias in {"C037","C038"}: time_scope={"mode":"point","valid_at":"2026-08-01T12:00:00.000000Z"}
        elif spec.alias=="C041": time_scope={"mode":"point","valid_at":"2026-09-14T17:00:00.000000Z"}
        else: time_scope={"mode":"current"}
        public={"query_id":qid,"query":query_text,"entity_refs":[] if spec.alias=="C032" else ([ids[entity_alias]] if entity_alias else []),"time_scope":time_scope,"known_as_of":spec.known,"access_scope":ids["scope"],"application_context":{"definition_refs":[stable_id("definition","BC07")],"source_snapshot_refs":source_refs},"query_type_hint":None,"public_snapshot_id":sid}
        renders.append({"query_id":qid,"semantic_case_id":cid,"style":"direct","template_id":f"direct-{spec.alias}","template_version":"1.0","rendered_text":query_text,"public_request":public,"content_hash":sha256_bytes(canonical_bytes(public))})
        computed_status,computed_answer=evaluate_case(spec,branches[spec.ledger],{x["source_id"]:x for x in sources},entity_alias)
        if (computed_status,computed_answer)!=(spec.status,spec.answer):raise ValueError(f"independent expected mismatch for {spec.alias}: {(computed_status,computed_answer)} != {(spec.status,spec.answer)}")
        gold.append({"query_id":qid,"semantic_case_id":cid,"expected_status":computed_status,"typed_value":computed_answer,"unit":"VND" if spec.task=="T02" and isinstance(computed_answer,int) else None,"world_answer":spec.answer,"missing_roles":["required_evidence"] if computed_status=="insufficient_evidence" else [],"conflict_groups":["revenue"] if computed_status=="unresolved_conflict" else [],"proof_refs":[stable_id("proof",spec.alias)]})
        queries.append({"query_id":qid,"scenario_id":stable_id("scenario",spec.root),"semantic_case_id":cid,"primary_family":spec.family,"secondary_tags":[taskref],"split_group":split_group})
        if spec.task in {"T01","T04","T06"}: roles=["document_clause"]
        elif spec.task=="T02": roles=["document_rule","operating_day"] if spec.alias=="C006" else ["document_rule","driver_program","operating_region","operating_day","reported_revenue"]
        elif spec.task=="T03": roles=["document_rule","driver_program","reported_acceptance"]
        elif spec.task=="T05": roles=["document_rule","reported_rating"]
        elif spec.task=="T07": roles=["document_clause","driver_program"] if spec.alias=="C027" else ["document_clause","driver_program","membership","fleet_registry"]
        elif spec.foundation=="aggregate": roles=["metric_definition","terminal_population","complete_coverage"]
        elif spec.foundation=="bridge": roles=["synthetic_rule","membership","fleet_region","incident_evidence"]
        elif spec.foundation=="entity_resolution": roles=["candidate_identity"]
        elif spec.foundation=="state": roles=["state_assertion"]
        elif spec.foundation=="event": roles=["terminal_event"]
        else: roles=["policy_publication"]
        missing_by_case={"C007":["operating_day"],"C008":["reported_revenue"],"C013":["reported_revenue"],"C016":["reported_acceptance"],"C022":["comparable_reported_rating"],"C031":["fleet_region"],"C035":["terminal_event"],"C040":["complete_coverage"]}
        missing=missing_by_case.get(spec.alias,[]); gold[-1]["missing_roles"]=missing
        atom_ids=[]
        for role in roles:
            if role in missing: continue
            atom_id=stable_id("support_atom",f"{spec.alias}:{role}");atom_ids.append(atom_id)
            atoms.append({"atom_id":atom_id,"semantic_type":"source_support","role":role,"entity_constraints":public["entity_refs"],"time_constraints":{"known_as_of":spec.known},"source_constraints":source_refs})
            is_document=role.startswith("document")
            source_id=source_refs[0] if is_document and source_refs else sid
            links.append({"support_link_id":stable_id("support_link",f"{spec.alias}:{role}"),"atom_id":atom_id,"query_id":qid,"canonical_source_refs":[{"source_kind":"document" if is_document else "operational","source_id":source_id,"locator":{"clause_refs":[]} if is_document else {"public_snapshot_id":sid}}]})
        proofs.append({"proof_id":stable_id("proof",spec.alias),"query_id":qid,"status":"sufficient" if spec.status=="answerable" else "diagnostic","operator":"AND","minimal_atom_sets":[atom_ids] if spec.status=="answerable" else [],"available_atom_ids":atom_ids,"missing_roles":missing,"conflict_groups":gold[-1]["conflict_groups"]})
        splits.append({"query_id":qid,"scenario_id":stable_id("scenario",spec.root),"split_group":split_group,"split":"dev"})
    scenarios=[]
    by_variant=defaultdict(list)
    for s in CASES: by_variant[(s.root,s.ledger)].append(s)
    for root_num,ledgers in ROOT_VARIANTS.items():
        root=f"SC{root_num:02d}"; baseid=stable_id("scenario_variant",f"{root}:L0")
        for ledger in ledgers:
            members=by_variant[(root,ledger)]; exemplar=members[0]
            mutation="base" if ledger=="L0" else "source_conflict" if ledger=="L_CONFLICT" else "retraction_branch" if ledger=="L_RETRACT" else "observation_mask"
            if mutation=="base": ms={}
            elif mutation=="source_conflict": ms={"logical_fact_id":stable_id("logical_fact","RM:REVENUE:D_A:W14"),"removed_record_ids":[stable_id("source_record","RM:REVENUE:D_A:W14@r2")],"added_record_ids":[stable_id("source_record","RM:REVENUE:D_A:W14@conflict")],"invariant_refs":["I07"]}
            elif mutation=="retraction_branch": ms={"target_assertion_ids":[stable_id("assertion","RM:REVENUE:D_A:W14")],"removed_record_ids":[stable_id("source_record","RM:REVENUE:D_A:W14@r2")],"added_record_ids":[stable_id("source_record","RM:REVENUE:D_A:W14@retract")],"invariant_refs":["I03","I04"]}
            else:
                keys={"L_NO_OPDAY":"RM:OPDAY:D_A:W11","L_WRONG_DRIVER":"RM:REVENUE:D_A:W11","L_WRONG_WINDOW":"RM:ACCEPTANCE:D_A:WA14","L_NO_BRIDGE":"BASED_IN:F6","L_NO_COVERAGE":"ART:coverage_db"}; rid=stable_id("source_record",keys[ledger]);ms={"seed_record_ids":[rid],"removed_record_ids":[rid],"closure_policy":"remove_dependents","invariant_refs":["I10"]}
            task_source = "P154" if exemplar.task in ("T01","T02") else "P151" if exemplar.task=="T03" else "P005" if exemplar.task in ("T04","T05") else "P023" if exemplar.task in ("T06","T07") else None
            policy_refs = [{"kind":"real_snapshot","id":docs_by_alias[task_source]["snapshot_id"]}] if task_source else ([{"kind":"synthetic_version","id":stable_id("policy_version","S_BRIDGE:v1")}] if exemplar.foundation=="bridge" else [{"kind":"synthetic_version","id":stable_id("policy_version","S_VERSION:v2")}] if exemplar.foundation=="policy_version" else [])
            row={"schema_version":SCHEMA_VERSION,"release_spec_version":SPEC_VERSION,"dataset_version":DATASET_VERSION,"world_id":ids["world"],"scenario_id":stable_id("scenario",root),"scenario_variant_id":stable_id("scenario_variant",f"{root}:{ledger}"),"parent_variant_id":None if ledger=="L0" else baseid,"mutation_type":mutation,"mutation_spec":ms,"ledger_id":ledger_ids[ledger],"scope_id":ids["scope"],"gold_track":"synthetic_control" if exemplar.foundation else "source_grounded" if exemplar.task in ("T01","T04","T06") else "conditional_binding","task_id":exemplar.task,"foundation_task":exemplar.foundation,"policy_snapshot_refs":policy_refs,"public_snapshot_refs":sorted({snapshot_ids[(x.ledger,x.known)] for x in members}),"semantic_case_ids":sorted(stable_id("semantic_case",x.alias) for x in members),"query_ids":sorted(stable_id("query",x.alias) for x in members),"split_group":split_group,"seed":ROOT_SEED}
            scenarios.append(ScenarioManifest.model_validate(row).model_dump(mode="json"))
    return {"scenarios":scenarios,"semantic_cases":cases,"query_renderings":renders,"gold_answers":gold,"queries":queries,"proofs":proofs,"support_atoms":atoms,"support_links":links,"splits":splits}


def build_release(repo:Path,output:Path,config_path:Path) -> dict[str,Any]:
    validate_build_config(config_path)
    if output.exists() and any(output.iterdir()): raise FileExistsError(f"output is not empty: {output}")
    output.mkdir(parents=True,exist_ok=True)
    docs=source_inventory(repo); entities,events,facts,ids=_world(); sources=_sources(ids); branches,artifacts=_ledgers(ids,events,sources,docs)
    ledger_ids={x:stable_id("ledger",x) for x in LEDGERS}; cutoffs={"L0":[A0,AC,A1,"2026-08-04T00:00:00.000000Z","2026-08-06T00:00:00.000000Z"],**{x:[A1] for x in LEDGERS if x!="L0"}}
    snapshot_ids={(ledger,known):stable_id("public_snapshot",f"{DATASET_VERSION}|{ids['world']}|{ledger_ids[ledger]}|{ids['scope']}|{known}") for ledger,values in cutoffs.items() for known in values}
    _parquet(output/"private/oracle/entities.parquet",entities);_parquet(output/"private/oracle/events.parquet",events);_parquet(output/"private/oracle/temporal_facts.parquet",facts)
    _parquet(output/"private/oracle/world_metrics.parquet",[{"world_metric_id":stable_id("world_metric","D_B:W30"),"driver_id":ids["D_B"],"definition_id":"M01","numerator":2,"denominator":10,"value":rational(1,5)},{"world_metric_id":stable_id("world_metric","D_H:W30"),"driver_id":ids["D_H"],"definition_id":"M01","numerator":0,"denominator":0,"value":None}])
    write_jsonl(output/"private/oracle/policy_rules.jsonl",[{"rule_id":stable_id("rule","S_BRIDGE:v1"),"policy_version_id":stable_id("policy_version","S_BRIDGE:v1"),"policy_id":"S_BRIDGE","version":"v1","requires":{"fleet_region":"HCM_OLD"},"exceptions":[{"incident_open":True}]},{"rule_id":stable_id("rule","S_VERSION:v1"),"policy_version_id":stable_id("policy_version","S_VERSION:v1"),"policy_id":"S_VERSION","version":"v1","requires":{"operating_region":"HN"}},{"rule_id":stable_id("rule","S_VERSION:v2"),"policy_version_id":stable_id("policy_version","S_VERSION:v2"),"policy_id":"S_VERSION","version":"v2","requires":{"operating_region":"HCM_OLD"}}])
    bindings=[{"binding_id":f"task_binding:B{i:02d}@1.0","binding_version":"1.0","task_id":f"T{i:02d}","status":"included","gold_track":"source_grounded" if i in (1,4,6) else "conditional_binding"} for i in range(1,8)]
    reported_values=[{"record_id":r["record_id"],"assertion":a,"planned_operation":r["operation"],"known_at":r["known_at"]} for r in branches["L0"] for a in r["assertions"] if a["predicate"]=="REPORTED_MEASURE"]
    write_jsonl(output/"private/oracle/task_bindings.jsonl",bindings);write_jsonl(output/"private/oracle/reported_values.jsonl",reported_values);write_jsonl(output/"private/oracle/observation_plan.jsonl",[{"ledger_alias":x,"ledger_id":ledger_ids[x],"record_ids":[r["record_id"] for r in rows]} for x,rows in branches.items()])
    write_jsonl(output/"public/operational/entity_catalog.jsonl",entities);write_jsonl(output/"public/operational/source_registry.jsonl",sources)
    for alias,rows in branches.items():
        p=output/("public/operational/record_ledger.parquet" if alias=="L0" else f"public/operational/variants/{ledger_ids[alias]}/record_ledger.parquet");_parquet(p,rows)
        narratives=[{"record_id":r["record_id"],"source_id":r["source_id"],"scope_id":r["scope_id"],"known_at":r["known_at"],"commit_seq":r["commit_seq"],"operation":r["operation"],"target_assertion_ids":r["target_assertion_ids"],"assertions":r["assertions"],"raw_payload":r["raw_payload"],"payload_hash":r["payload_hash"],"text":f"Bản ghi nguồn {r['record_id']} công bố {len(r['assertions'])} assertion."} for r in rows]
        write_jsonl(output/("public/operational/text_observations.jsonl" if alias=="L0" else f"public/operational/variants/{ledger_ids[alias]}/text_observations.jsonl"),narratives)
    for a in artifacts.values():write_json(output/f"public/operational/artifacts/{a['artifact_id']}.json",a)
    catalog=[]; docs_by_alias={}
    for d in docs:
        (output/f"public/documents/raw/{d['snapshot_id']}.md").parent.mkdir(parents=True,exist_ok=True);(output/f"public/documents/raw/{d['snapshot_id']}.md").write_bytes(d["raw_bytes"])
        (output/f"public/documents/normalized/{d['document_revision_id']}.md").parent.mkdir(parents=True,exist_ok=True);(output/f"public/documents/normalized/{d['document_revision_id']}.md").write_bytes(d["normalized_bytes"])
        clauses=[{"clause_id":cid,"line":v[0],"span_start":v[1],"span_end":v[2],"coordinate_system":"unicode_codepoints_half_open","source_mode":"TEXT"} for cid,v in CLAUSES.get(d["article_number"],{}).items()]
        row={k:d[k] for k in ["alias","article_number","snapshot_id","document_revision_id","archive_member_path","raw_sha256","normalized_sha256","posted_date","review_state"]};row.update({"normalization_version":"crlf-to-lf-v1","captured_at":{"kind":"unknown"},"dataset_release_at":"2026-09-16T00:00:00.000000Z","clauses":clauses,"publication_assertion_id":stable_id("assertion",f"DOC:{d['snapshot_id']}")});catalog.append(row);docs_by_alias[d["alias"]]=row
    for policy,version in [("S_BRIDGE","v1"),("S_VERSION","v1"),("S_VERSION","v2")]:
        rid=stable_id("document_revision",f"{policy}:{version}"); text=f"# {policy} {version}\n\nTài liệu kiểm soát tổng hợp, không phải chính sách GSM thực.\n"; (output/f"public/documents/normalized/{rid}.md").write_text(text,encoding="utf-8",newline="\n");catalog.append({"alias":f"{policy}:{version}","snapshot_id":None,"policy_version_id":stable_id("policy_version",f"{policy}:{version}"),"document_revision_id":rid,"normalized_sha256":sha256_bytes(text.encode()),"source_mode":"synthetic_control","review_state":"generated"})
    write_jsonl(output/"public/documents/catalog.jsonl",catalog)
    definition_rows=[]
    definition_bodies={"BC01":"Ngày và tuần dùng Asia/Ho_Chi_Minh; khoảng thời gian là [from,to).","BC02":"Reported measure là giá trị nguồn đã tính; không suy raw-event lineage.","BC03":"Program và operating region phải phủ toàn measurement window.","BC04":"Checkpoint acceptance dùng đúng window được yêu cầu.","BC05":"Số học rational chính xác; không áp settlement rounding.","BC06":"Tên Depot được registry ánh xạ sang ID; tên không phải identity.","BC07":"Câu hỏi policy đọc đúng edition/snapshot được chỉ định, không suy current policy.","RM_REVENUE":"Reported revenue: integer không âm, unit VND, một driver và ngày local.","RM_OPDAY":"Reported operating day: boolean cho đúng ngày local.","RM_ACCEPTANCE":"Reported acceptance rate: rational fraction cho exact checkpoint window.","RM_RATING":"Reported weekly rating: rational stars_5 hoặc explicit undefined.","M01":"cancel_rate_30d=N_cancelled/(N_cancelled+N_completed); denominator zero là undefined; exact result cần complete coverage."}
    for name in DEFINITIONS:
        did=stable_id("definition",name); text=f"# {name}\n\n{definition_bodies[name]}\n"; (output/f"public/definitions/{did}.md").parent.mkdir(parents=True,exist_ok=True);(output/f"public/definitions/{did}.md").write_text(text,encoding="utf-8",newline="\n");definition_rows.append({"definition_id":did,"alias":name,"version":"1.0","content_sha256":sha256_bytes(text.encode()),"available_at":"2026-07-01T00:00:00.000000Z"})
    write_jsonl(output/"public/definitions/catalog.jsonl",definition_rows)
    source_catalog_hash=sha256_file(output/"public/documents/catalog.jsonl"); synthetic_ids=sorted(x["document_revision_id"] for x in catalog if x.get("source_mode")=="synthetic_control"); definition_ids=sorted(x["definition_id"] for x in definition_rows)
    for profile,members in [("debug_core",[docs_by_alias[x]["snapshot_id"] for x in ["P154","P151","P005","P023","P172","P026"]]),("retrieval_full",[x["snapshot_id"] for x in catalog if x.get("snapshot_id")])]:
        manifest={"schema_version":SCHEMA_VERSION,"release_spec_version":SPEC_VERSION,"dataset_version":DATASET_VERSION,"corpus_profile_id":profile,"corpus_profile_version":"1.0","real_snapshot_ids":sorted(members),"shared_document_revision_ids":synthetic_ids,"definition_ids":definition_ids,"source_catalog_sha256":source_catalog_hash,"source_archive_sha256":ARCHIVE_SHA256,"normalization_version":"crlf-to-lf-v1","counts":{"real_articles":len(members),"synthetic_versions":3,"definitions":12}};write_json(output/f"public/corpus_profiles/{profile}/manifest.json",manifest)
    outputs=_case_outputs(ids,ledger_ids,snapshot_ids,docs_by_alias,branches,sources)
    for name,rows in outputs.items():write_jsonl(output/f"private/eval/{name}.jsonl",rows)
    write_jsonl(output/"private/eval/entity_resolution.jsonl",[{"query_id":stable_id("query","C032"),"expected_candidate_ids":sorted([ids["D_E"],ids["D_F"]]),"expected_resolved_ids":[],"expected_status":"ambiguous_request"}])
    write_json(output/"private/eval/policy_audit.json",{"audit_id":"gsm-policy-compat-20260916-v1","amendments":["AM1","AM2","AM3","AM4"],"status":"reviewed"});write_json(output/"private/eval/review_manifest.json",{"audited_sources":6,"primary_gold_sources":4,"reviewed_text_only":True})
    roles=[{"snapshot_id":d["snapshot_id"],"audited":d["article_number"] in AUDITED,"primary_gold":d["article_number"] in {154,151,5,23},"reviewed_span_refs":sorted(CLAUSES.get(d["article_number"],{}))} for d in docs];write_jsonl(output/"private/eval/corpus_roles.jsonl",roles);write_jsonl(output/"private/eval/relevance_judgments.jsonl",[]);write_json(output/"private/eval/relevance_protocol.json",{"protocol_version":"1.0","relevance_unit":"canonical_source_span","unjudged_policy":"explicit_na","qrels_universe_description":"reviewed supports only; missing rows are unjudged","pool_run_refs":[],"pool_depth":None})
    for (ledger,known),sid in snapshot_ids.items():
        rows=[r for r in branches[ledger] if r["known_at"]<=known]; base=output/f"public/snapshots/{sid}";_parquet(base/"record_ledger.parquet",rows);write_jsonl(base/"entity_catalog.jsonl",entities);write_jsonl(base/"source_registry.jsonl",sources);write_jsonl(base/"text_observations.jsonl",[{"record_id":r["record_id"],"source_id":r["source_id"],"known_at":r["known_at"],"assertions":r["assertions"],"target_assertion_ids":r["target_assertion_ids"]} for r in rows]);visible_docs=[x for x in catalog if x.get("snapshot_id") and known>="2026-09-16T00:00:00.000000Z"];write_jsonl(base/"documents.jsonl",visible_docs);write_jsonl(base/"definitions.jsonl",definition_rows);write_jsonl(base/"artifacts.jsonl",list(artifacts.values()) if known>="2026-09-16T03:00:00.000000Z" else []);manifest={"snapshot_id":sid,"dataset_version":DATASET_VERSION,"world_id":ids["world"],"ledger_id":ledger_ids[ledger],"scope_id":ids["scope"],"known_as_of":known,"record_count":len(rows),"document_ref_count":len(visible_docs),"complete":True};write_json(base/"manifest.json",manifest);write_json(output/f"public/graph_inputs/mode_a/{sid}.json",{"snapshot_id":sid,"mode":"A","structured_ledger":f"public/snapshots/{sid}/record_ledger.parquet","source_identity_preserved":True});write_json(output/f"public/graph_inputs/mode_b/{sid}.json",{"snapshot_id":sid,"mode":"B","text_observations":f"public/snapshots/{sid}/text_observations.jsonl","source_identity_preserved":True})
    public_queries=[r["public_request"] for r in outputs["query_renderings"]];write_jsonl(output/"public/runtime_queries/dev.jsonl",public_queries);(output/"public/runtime_queries/test.jsonl").parent.mkdir(parents=True,exist_ok=True);(output/"public/runtime_queries/test.jsonl").write_bytes(b"")
    write_json(output/"public/runtime_manifest.json",{"schema_version":SCHEMA_VERSION,"release_spec_version":SPEC_VERSION,"dataset_version":DATASET_VERSION,"dev_query_count":42,"test_query_count":0,"query_routes":[{"query_id":q["query_id"],"public_snapshot_id":q["public_snapshot_id"]} for q in public_queries]})
    write_json(output/"private/eval/validation.json",{"state":"not_run","checks":[]})
    schemas={"entities.parquet":{"primary_key":"entity_id","logical_types":["Entity","NameVersion"]},"events.parquet":{"primary_key":"world_event_id","logical_types":["WorldEvent"]},"record_ledger.parquet":{"primary_key":"record_id","logical_types":["SourceRecord","AssertionPayload"]}}
    counts={"real_sources":224,"audited_sources":6,"primary_gold_sources":4,"debug_core_members":6,"retrieval_full_members":224,"drivers":8,"terminal_trips":80,"scenario_roots":25,"scenario_variants":32,"ledgers":8,"semantic_cases":42,"query_renderings":42,"dev_queries":42,"test_queries":0,"public_snapshots":12,"definitions":12,"synthetic_versions":3}
    def tree_hash(paths:list[Path])->str:
        members=[]
        for parent in paths:
            if parent.is_file(): members.append((parent.relative_to(repo).as_posix(),sha256_file(parent)))
            elif parent.exists(): members.extend((p.relative_to(repo).as_posix(),sha256_file(p)) for p in sorted(parent.rglob("*.py")))
        return sha256_bytes(canonical_bytes(sorted(members)))
    manifest={"state":"DRAFT","schema_version":SCHEMA_VERSION,"release_spec_version":SPEC_VERSION,"dataset_version":DATASET_VERSION,"seed":ROOT_SEED,"seed_algorithm":"sha256-stream-v1","config_path":str(config_path.name),"config_sha256":sha256_file(config_path),"source_archive_sha256":ARCHIVE_SHA256,"spec_02_sha256":sha256_file(repo/"docs/02_synthetic_schema_and_data_design.md"),"spec_05_sha256":sha256_file(repo/"docs/05_dataset_release_spec.md"),"implementation_sha256":tree_hash([repo/"src/gsm_memory/data",repo/"src/gsm_memory/evaluation"]),"data_test_suite_sha256":tree_hash([repo/"tests/unit/data",repo/"tests/conformance/data",repo/"tests/integration/data"]),"toolchain":{"python":platform.python_version(),"pyarrow":pa.__version__,"parquet_compression":"zstd"},"counts":counts,"logical_table_schemas":schemas,"ledgers":[{"ledger_id":ledger_ids[x],"world_id":ids["world"],"scope_id":ids["scope"],"record_ledger_path":"public/operational/record_ledger.parquet" if x=="L0" else f"public/operational/variants/{ledger_ids[x]}/record_ledger.parquet","record_ledger_sha256":sha256_file(output/("public/operational/record_ledger.parquet" if x=="L0" else f"public/operational/variants/{ledger_ids[x]}/record_ledger.parquet"))} for x in LEDGERS]}
    write_json(output/"private/eval/manifest.json",manifest);return counts
