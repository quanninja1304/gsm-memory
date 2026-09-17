from gsm_memory.evaluation.assurance import (
    POLICY_REQUIREMENTS,
    WINDOWS,
    evaluate_semantic_fixture,
    ex_fixtures,
    run_aux_incident_check,
    run_counterfactual_checks,
)


def test_ex01_ex25_reference_expectations():
    fixtures=ex_fixtures()
    assert [fixture.fixture_id for fixture in fixtures]==[f"EX{i:02d}" for i in range(1,26)]
    for fixture in fixtures:
        assert fixture.premise_ids, fixture.fixture_id
        assert evaluate_semantic_fixture(fixture)==(fixture.expected_status,fixture.expected_value), fixture.fixture_id


def test_ex_fixtures_pin_normative_windows_sources_and_clauses():
    for fixture in ex_fixtures():
        if fixture.evaluator in POLICY_REQUIREMENTS:
            source_id, clauses = POLICY_REQUIREMENTS[fixture.evaluator]
            assert fixture.context["task_binding"]["source_id"] == source_id
            assert clauses <= set(fixture.context["task_binding"]["clauses"])
        if fixture.window in WINDOWS:
            measure_validity = [
                assertion["valid"]
                for record in fixture.records
                for assertion in record["assertions"]
                if assertion["predicate"] == "REPORTED_MEASURE"
            ]
            if measure_validity:
                assert all(valid in WINDOWS.values() for valid in measure_validity), fixture.fixture_id
                if not any(premise.startswith("wrong-window") for premise in fixture.premise_ids):
                    assert all(valid == WINDOWS[fixture.window] for valid in measure_validity), fixture.fixture_id


def test_aux_incident_is_executable_and_bitemporal():
    result=run_aux_incident_check()
    assert result["ok"],result
    assert [probe["value"] for probe in result["actual"]["probes"]]==["open","open","resolved","open"]
    assert result["actual"]["canonical_incident_ids"]==["I1"]
    assert result["actual"]["absence_without_coverage"]=="insufficient_evidence"


def test_counterfactuals_mutate_causal_inputs_and_change_results():
    results=run_counterfactual_checks()
    assert {item["check_id"] for item in results}=={
        "CF_THRESHOLD","CF_KNOWN_PREFIX","CF_RETRACTION","CF_EQUAL_RANK_CONFLICT",
        "CF_BRIDGE_REMOVAL","CF_COVERAGE_REMOVAL","CF_PROOF_ATOM_REMOVAL",
    }
    assert all(item["ok"] for item in results),results
    assert all(item["actual"]["before"]!=item["actual"]["after"] for item in results)
