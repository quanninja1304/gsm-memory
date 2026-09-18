from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from gsm_memory.data.build import _ledgers, _sources, _world, source_inventory
from gsm_memory.data.coverage import (
    CoverageConfig,
    CoverageContractError,
    coverage_digests,
    derive_coverage_members,
    resolved_source_set,
)


def _fixture():
    repo = Path(__file__).resolve().parents[3]
    config = json.loads((repo / "configs/datasets/gsm-dev-core-0.2.2.json").read_text(encoding="utf-8"))
    parsed = CoverageConfig.model_validate(
        {"coverage_contract_version": config["coverage_contract_version"], "coverage_recipes": config["coverage_recipes"]}
    )
    docs = source_inventory(repo)
    _, events, _, ids = _world()
    sources = _sources(ids)
    ledgers, _, _ = _ledgers(ids, events, sources, docs, config)
    resolved = {**ids, "W0": ids["world"], "S0": ids["scope"]}
    resolved.update({x["alias"]: x["source_id"] for x in sources})
    return parsed, ledgers["L0"], {x["source_id"]: x for x in sources}, resolved


def test_coverage_recipes_select_approved_members_and_separate_empty_scopes():
    parsed, records, sources, resolved = _fixture()
    results = {}
    for recipe in parsed.coverage_recipes:
        source_set = resolved_source_set(recipe, resolved)
        members, outcomes = derive_coverage_members(recipe, records, sources, resolved)
        results[recipe.recipe_key] = (members, outcomes, coverage_digests(recipe, members, resolved, source_set))
    assert len(results["terminal_trips_db_w30"][0]) == 10
    assert results["terminal_trips_db_w30"][1] == {"completed": 8, "cancelled": 2}
    assert results["terminal_trips_dh_w30"][0] == []
    assert results["incidents_db_through_tm"][0] == []
    dh = results["terminal_trips_dh_w30"][2]
    incidents = results["incidents_db_through_tm"][2]
    assert dh["members_digest"] == incidents["members_digest"]
    assert dh["coverage_content_digest_v1"] != incidents["coverage_content_digest_v1"]
    assert dh["artifact_id"] != incidents["artifact_id"]


def test_coverage_schema_rejects_missing_unknown_and_observed_window():
    parsed, _, _, _ = _fixture()
    raw = parsed.coverage_recipes[0].model_dump(mode="json")
    missing = copy.deepcopy(raw)
    del missing["source_set"]
    with pytest.raises(Exception):
        type(parsed.coverage_recipes[0]).model_validate(missing)
    unknown = copy.deepcopy(raw)
    unknown["case_id"] = "C029"
    with pytest.raises(Exception):
        type(parsed.coverage_recipes[0]).model_validate(unknown)
    observed = copy.deepcopy(raw)
    observed["valid_window"]["bounds"] = "observed-member-min-max"
    with pytest.raises(Exception):
        type(parsed.coverage_recipes[0]).model_validate(observed)


def test_coverage_subject_window_and_source_mutations_fail_invariants():
    parsed, records, sources, resolved = _fixture()
    recipe = parsed.coverage_recipes[0]
    wrong_subject = recipe.model_copy(update={"subject_ref": "D_H", "selector": recipe.selector.model_copy(update={"subject_equals": "D_H"})})
    with pytest.raises(CoverageContractError):
        derive_coverage_members(wrong_subject, records, sources, resolved)
    narrower = recipe.model_copy(update={"valid_window": recipe.valid_window.model_copy(update={"start": "2026-08-20T17:00:00.000000Z"})})
    with pytest.raises(CoverageContractError):
        derive_coverage_members(narrower, records, sources, resolved)
    event_id = resolved["event"]
    without_event_source = [x for x in records if x["source_id"] != event_id]
    with pytest.raises(CoverageContractError):
        derive_coverage_members(recipe, without_event_source, sources, resolved)


def test_incident_window_contains_tm_by_half_open_boundary():
    parsed, _, _, _ = _fixture()
    incident = next(x for x in parsed.coverage_recipes if x.recipe_key == "incidents_db_through_tm")
    assert incident.valid_window.start <= "2026-09-15T17:00:00.000000Z" < incident.valid_window.end
    assert incident.valid_window.end == "2026-09-15T17:00:00.000001Z"
