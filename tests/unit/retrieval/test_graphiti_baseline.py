from pathlib import Path
from types import SimpleNamespace

import pytest

from gsm_memory.adapters.graphiti_baseline import (
    INPUT_FORMAT_VERSION,
    _candidate,
    _resume_position,
    load_baseline_inputs,
    render_graphiti_episode,
    render_graphiti_query,
)


RELEASE = Path("data/gsm-dev-core-0.2.2")
SNAPSHOT = "25b69c05-6a60-51e3-9209-74e5d49816fa"


def test_load_baseline_inputs_uses_routed_public_mode_b_data():
    inputs = load_baseline_inputs(
        RELEASE, snapshot_id=SNAPSHOT, max_episodes=2, max_queries=1
    )
    assert len(inputs) == 1
    assert inputs[0]["snapshot_id"] == SNAPSHOT
    assert inputs[0]["group_id"].endswith(SNAPSHOT)
    assert len(inputs[0]["observations"]) == 2
    assert len(inputs[0]["queries"]) == 1
    assert inputs[0]["group_id"].endswith(f"{INPUT_FORMAT_VERSION}_{SNAPSHOT}")
    assert "private" not in inputs[0]["observations_path"].parts
    assert [row["commit_seq"] for row in inputs[0]["observations"]] == [1, 2]
    assert inputs[0]["entities"]["99e70ebe-18cd-57a3-a036-cf0ff1989861"]["name"]["text"] == "An"


def test_load_baseline_inputs_rejects_non_positive_limits():
    with pytest.raises(ValueError, match="max_episodes"):
        load_baseline_inputs(RELEASE, max_episodes=0)
    with pytest.raises(ValueError, match="max_queries"):
        load_baseline_inputs(RELEASE, max_queries=0)


def test_graphiti_edge_keeps_public_episode_to_assertion_lineage():
    record = {
        "record_id": "record-1",
        "source_id": "source-1",
        "assertions": [{"assertion_id": "assertion-1"}],
    }
    edge = SimpleNamespace(
        uuid="edge-1",
        name="MEMBER_OF",
        fact="driver MEMBER_OF depot",
        source_node_uuid="driver",
        target_node_uuid="depot",
        episodes=["episode-1"],
    )
    candidate = _candidate(
        edge, 1, {"episode-1": "record-1"}, {"record-1": record}
    )
    assert candidate["source_locator"]["record_id"] == "record-1"
    assert candidate["source_locator"]["assertion_id"] == "assertion-1"
    assert candidate["source_locator"]["member_assertion_ids"] == ["assertion-1"]


def test_ingestion_only_resumes_an_exact_episode_prefix():
    episodes = [SimpleNamespace(name="r1"), SimpleNamespace(name="r2")]
    assert _resume_position(["r1", "r2", "r3"], episodes) == 2
    assert _resume_position(["r1"], episodes, ["r1", "r2", "r3"]) == 1
    with pytest.raises(RuntimeError, match="exact prefix"):
        _resume_position(["r1", "r2", "r3"], [SimpleNamespace(name="r2")])


def test_episode_renderer_adds_public_names_and_preserves_temporal_provenance():
    record = {
        "record_id": "record-1",
        "source_id": "source-1",
        "known_at": "2026-09-01T00:00:00.000000Z",
        "operation": "assert",
        "target_assertion_ids": [],
        "assertions": [{
            "assertion_id": "assertion-1",
            "subject_id": "driver-1",
            "predicate": "MEMBER_OF",
            "object": {"type": "entity_ref", "value": "fleet-1"},
            "valid": {
                "kind": "interval",
                "from": "2026-08-01T00:00:00.000000Z",
                "to": {"kind": "unbounded"},
            },
            "event_time": None,
            "qualifiers": {},
            "source_refs": [{
                "document_revision_id": "revision-1",
                "clause_ids": ["clause-2", "clause-1"],
            }],
        }],
    }
    entities = {
        "driver-1": {
            "entity_type": "DRIVER",
            "name": {"text": "An"},
            "semantic_code": None,
        },
        "fleet-1": {
            "entity_type": "FLEET",
            "name": {"text": "Depot 1"},
            "semantic_code": None,
        },
    }
    text = render_graphiti_episode(
        record,
        entities,
        {"source-1": {"alias": "registry"}},
    )
    assert 'DRIVER "An" [id=driver-1]' in text
    assert "Quan hệ/vị từ: MEMBER_OF" in text
    assert 'FLEET "Depot 1" [id=fleet-1]' in text
    assert "2026-09-01T00:00:00.000000Z" in text
    assert "[2026-08-01T00:00:00.000000Z, không giới hạn)" in text
    assert "source_id=source-1" in text
    assert '"document_revision_id": "revision-1"' in text
    assert '"clause_ids": ["clause-2", "clause-1"]' in text


def test_query_renderer_uses_public_entity_context_without_gold():
    query = {
        "query": "Tài xế thuộc depot nào?",
        "entity_refs": ["driver-1"],
        "known_as_of": "2026-09-01T00:00:00.000000Z",
        "time_scope": {"mode": "point", "at": "2026-08-15T00:00:00.000000Z"},
        "application_context": {"source_snapshot_refs": ["snap-154"]},
    }
    entities = {
        "driver-1": {
            "entity_type": "DRIVER",
            "name": {"text": "An"},
            "semantic_code": None,
        }
    }
    text = render_graphiti_query(query, entities)
    assert text.startswith("Tài xế thuộc depot nào?")
    assert 'DRIVER "An" [id=driver-1]' in text
    assert "2026-09-01T00:00:00.000000Z" in text
    assert "snap-154" in text
    assert "expected" not in text
    assert "proof" not in text


@pytest.mark.parametrize(
    ("predicate", "value", "expected"),
    [
        ("DRIVER_STATUS", {"type": "enum", "value": "active"}, "DRIVER_STATUS = active"),
        (
            "ARTIFACT_PUBLICATION",
            {"type": "enum", "value": "available"},
            "ARTIFACT_PUBLICATION = available",
        ),
        ("REPORTED_MEASURE", {"type": "integer", "value": 300000}, "REPORTED_MEASURE = 300000"),
        (
            "REPORTED_MEASURE",
            {"type": "rational", "value": {"n": 97, "d": 20}},
            "REPORTED_MEASURE = 97/20",
        ),
        ("REPORTED_MEASURE", {"type": "boolean", "value": True}, "REPORTED_MEASURE = true"),
    ],
)
def test_episode_renderer_turns_literal_values_into_stable_target_entities(
    predicate, value, expected
):
    record = {
        "record_id": "record-1",
        "source_id": "source-1",
        "known_at": "2026-09-01T00:00:00.000000Z",
        "operation": "assert",
        "target_assertion_ids": [],
        "assertions": [{
            "assertion_id": "assertion-1",
            "subject_id": "driver-1",
            "predicate": predicate,
            "object": value,
            "valid": {"kind": "point", "at": "2026-09-01T00:00:00.000000Z"},
            "event_time": None,
            "qualifiers": {},
            "source_refs": [],
        }],
    }
    text = render_graphiti_episode(
        record,
        {"driver-1": {
            "entity_type": "DRIVER",
            "name": {"text": "An"},
            "semantic_code": None,
        }},
        {"source-1": {"alias": "registry"}},
    )
    assert "Bộ ba bắt buộc:" in text
    assert expected in text
    assert "[id=value:assertion-1" in text
