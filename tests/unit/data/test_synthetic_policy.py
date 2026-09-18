from gsm_memory.data.build import _world
from gsm_memory.data.synthetic import render_synthetic_policy, synthetic_policy_rules, verify_synthetic_render


def test_synthetic_policy_renderer_preserves_all_canonical_operands():
    _, _, _, ids = _world()
    rules = synthetic_policy_rules(ids)
    rendered = [render_synthetic_policy(rule) for rule in rules]
    for rule, document in zip(rules, rendered):
        verify_synthetic_render(rule, document)
        assert rule["required_region_id"] in document["text"]
        assert all(document["text"][c["span_start"]:c["span_end"]] for c in document["clauses"])
    assert "INCIDENT_STATUS=open" in rendered[0]["text"]
    assert len(rendered[0]["clauses"]) == 2
    assert [len(x["clauses"]) for x in rendered[1:]] == [1, 1]


def test_synthetic_policy_public_text_has_no_case_or_gold_hints():
    _, _, _, ids = _world()
    text = "\n".join(render_synthetic_policy(rule)["text"] for rule in synthetic_policy_rules(ids))
    for forbidden in ("C029", "C030", "C031", "C041", "C042", "expected_status", "proof_id"):
        assert forbidden not in text
