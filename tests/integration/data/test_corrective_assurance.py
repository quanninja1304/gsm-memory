from __future__ import annotations

import copy
import json
import re
import shutil
from collections import Counter
from pathlib import Path

import pytest

from gsm_memory.data.build import _ledgers, _record, _sources, _world, build_release, source_inventory
from gsm_memory.data.coverage import CoverageConfig, CoverageContractError, derive_coverage_members
from gsm_memory.data.ledger import payload_hash
from gsm_memory.data.locators import resolve_public_locator
from gsm_memory.data.primitives import read_jsonl
from gsm_memory.evaluation.independent import reconstruct_release


@pytest.fixture(scope="module")
def corrective_release(tmp_path_factory):
    repo=Path(__file__).resolve().parents[3];root=tmp_path_factory.mktemp("corrective")/"candidate"
    build_release(repo,root,repo/"configs/datasets/gsm-dev-core-0.2.2.json")
    return root


def test_all_110_support_links_resolve_with_approved_distribution(corrective_release):
    atoms={x["atom_id"]:x for x in read_jsonl(corrective_release/"private/eval/support_atoms.jsonl")};links=read_jsonl(corrective_release/"private/eval/support_links.jsonl");counts=Counter()
    for link in links:
        types={ref["locator"]["locator_type"] for ref in link["canonical_source_refs"]};assert len(types)==1;counts[next(iter(types))]+=1
        for ref in link["canonical_source_refs"]:assert resolve_public_locator(corrective_release,ref["locator"])["resolved"]
    assert len(atoms)==len(links)==110
    assert counts==Counter({"document_clause":31,"ledger_assertion":67,"entity_catalog":4,"definition_artifact":3,"coverage_artifact":5})


def test_independent_reconstruction_matches_all_42_without_reading_gold_in_evaluator(corrective_release):
    actual=reconstruct_release(corrective_release);gold={x["query_id"]:x for x in read_jsonl(corrective_release/"private/eval/gold_answers.jsonl")}
    assert len(actual)==42
    assert all((x["status"],x["typed_value"])==(gold[x["query_id"]]["expected_status"],gold[x["query_id"]]["typed_value"]) for x in actual)


def test_coverage_locator_rejects_scope_swap_digest_and_missing_publication(corrective_release):
    links=read_jsonl(corrective_release/"private/eval/support_links.jsonl");locators=[r["locator"] for x in links for r in x["canonical_source_refs"] if r["locator"]["locator_type"]=="coverage_artifact"]
    empty=[x for x in locators if x["member_count"]==0];assert len(empty)==4
    swapped=copy.deepcopy(empty[0]);swapped["artifact_id"]=empty[-1]["artifact_id"]
    with pytest.raises(ValueError):resolve_public_locator(corrective_release,swapped)
    digest=copy.deepcopy(empty[0]);digest["coverage_content_digest_v1"]="0"*64
    with pytest.raises(ValueError):resolve_public_locator(corrective_release,digest)
    publication=copy.deepcopy(empty[0]);publication["publication_assertion_id"]="missing"
    with pytest.raises(ValueError):resolve_public_locator(corrective_release,publication)


def test_no_coverage_branch_removes_only_db_completeness(corrective_release):
    artifacts=[json.loads(p.read_text()) for p in (corrective_release/"public/operational/artifacts").glob("*.json")];publication=next(x["publication_record_id"] for x in artifacts if x["artifact_type"]=="coverage" and x["member_count"]==10)
    scenarios=read_jsonl(corrective_release/"private/eval/scenarios.jsonl");target=next(x for x in scenarios if publication in x["mutation_spec"].get("removed_record_ids",[]))
    snapshots=[json.loads(p.read_text()) for p in (corrective_release/"public/snapshots").glob("*/manifest.json")];manifest=next(x for x in snapshots if x["ledger_id"]==target["ledger_id"]);base=corrective_release/"public/snapshots"/manifest["snapshot_id"]
    records=read_jsonl(base/"text_observations.jsonl");removed=set(target["mutation_spec"]["removed_record_ids"])
    assert not removed & {x["record_id"] for x in records}
    assert sum(a["predicate"]=="TRIP_OUTCOME" for r in records for a in r["assertions"])==80


def test_public_locator_resolution_needs_no_private_tree(corrective_release,tmp_path):
    public_only=tmp_path/"release";shutil.copytree(corrective_release/"public",public_only/"public")
    link=next(x for x in read_jsonl(corrective_release/"private/eval/support_links.jsonl") if x["canonical_source_refs"][0]["locator"]["locator_type"]=="coverage_artifact")
    assert resolve_public_locator(public_only,link["canonical_source_refs"][0]["locator"])["resolved"]
    public_text="\n".join(p.read_text(encoding="utf-8",errors="ignore") for p in (public_only/"public").rglob("*.json*"))
    assert not re.search(r"\bD_[A-H]\b|coverage_db|coverage_dh|incident_db",public_text)


def _coverage_fixture():
    repo=Path(__file__).resolve().parents[3];config=json.loads((repo/"configs/datasets/gsm-dev-core-0.2.2.json").read_text());parsed=CoverageConfig.model_validate({"coverage_contract_version":config["coverage_contract_version"],"coverage_recipes":config["coverage_recipes"]});docs=source_inventory(repo);_,events,_,ids=_world();sources=_sources(ids);ledgers,_,_=_ledgers(ids,events,sources,docs,config);resolved={**ids,"W0":ids["world"],"S0":ids["scope"],**{x["alias"]:x["source_id"] for x in sources}};return parsed,ledgers["L0"],{x["source_id"]:x for x in sources},resolved


def test_coverage_cutoff_retraction_and_nonterminal_counterfactuals():
    parsed,records,sources,resolved=_coverage_fixture();recipe=parsed.coverage_recipes[0];target=next((r,a) for r in records for a in r["assertions"] if a["predicate"]=="TRIP_OUTCOME" and a["subject_id"]==resolved["D_B"])
    before=_record("CF:retract-before",resolved["event"],resolved["scope"],"2026-09-15T00:00:00.000000Z","retract",[],[target[1]["assertion_id"]]);before["commit_seq"]=max(x["commit_seq"] for x in records)+1
    expected={"completed":8,"cancelled":2};expected[target[1]["qualifiers"]["outcome"]]-=1
    nine=recipe.model_copy(update={"expected_member_count_for_validation":9,"expected_outcome_counts_for_validation":expected})
    members,_=derive_coverage_members(nine,records+[before],sources,resolved);assert target[1]["qualifiers"]["trip_id"] not in members
    after=_record("CF:retract-after",resolved["event"],resolved["scope"],"2026-09-16T04:00:00.000000Z","retract",[],[target[1]["assertion_id"]]);after["commit_seq"]=before["commit_seq"]
    assert len(derive_coverage_members(recipe,records+[after],sources,resolved)[0])==10
    mutated=copy.deepcopy(records);record=next(r for r in mutated if any(a["assertion_id"]==target[1]["assertion_id"] for a in r["assertions"]));assertion=next(a for a in record["assertions"] if a["assertion_id"]==target[1]["assertion_id"]);assertion["qualifiers"]["outcome"]="pending";record["payload_hash"]=payload_hash(record)
    with pytest.raises(CoverageContractError):derive_coverage_members(recipe,mutated,sources,resolved)
    early=recipe.model_copy(update={"completeness":recipe.completeness.model_copy(update={"known_at_lte":"2026-08-19T00:00:00.000000Z"}),"publication":recipe.publication.model_copy(update={"known_at":"2026-08-19T00:00:00.000000Z"})})
    with pytest.raises(CoverageContractError):derive_coverage_members(early,records,sources,resolved)


def test_incident_window_ending_at_tm_is_rejected():
    parsed,_,_,_=_coverage_fixture();recipe=next(x for x in parsed.coverage_recipes if x.recipe_key=="incidents_db_through_tm");raw=recipe.model_dump(mode="json");raw["valid_window"]["end"]="2026-09-15T17:00:00.000000Z"
    with pytest.raises(Exception):type(recipe).model_validate(raw)
