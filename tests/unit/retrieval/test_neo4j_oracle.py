from pathlib import Path

import pytest

from gsm_memory.adapters.neo4j_oracle import (
    ORACLE_SCHEMA_VERSION,
    _key,
    _literal_identity,
    _typed_object_value,
    load_oracle_projections,
)


RELEASE = Path("data/gsm-dev-core-0.2.2")


def test_public_oracle_projection_covers_all_frozen_snapshots():
    projections = load_oracle_projections(RELEASE)

    assert ORACLE_SCHEMA_VERSION == "neo4j-public-ledger-oracle-v1"
    assert len(projections) == 12
    assert len({item.snapshot_id for item in projections}) == 12
    assert sum(len(item.records) for item in projections) == 3641
    assert sum(len(item.assertions) for item in projections) == 3702
    assert sum(len(item.entities) for item in projections) == 2495
    assert sum(len(item.values) for item in projections) == 184
    assert sum(len(item.entities) + len(item.values) for item in projections) == 2679
    assert all(len(item.assertions) == item.counts["oracle_facts"] for item in projections)


def test_assertion_and_entity_keys_are_snapshot_local():
    projections = load_oracle_projections(RELEASE)
    shared_assertion_id = projections[0].assertions[0]["assertion_id"]
    containing = [
        item for item in projections
        if any(row["assertion_id"] == shared_assertion_id for row in item.assertions)
    ]

    assert len(containing) > 1
    keys = set()
    for item in containing:
        key = next(
            row["oracle_key"] for row in item.assertions
            if row["assertion_id"] == shared_assertion_id
        )
        assert item.snapshot_id in key
        keys.add(key)
    assert len(keys) == len(containing)
    assert _key("release", "snapshot-a", "entity", "driver") != _key(
        "release", "snapshot-b", "entity", "driver"
    )


def test_projection_contains_no_embedding_or_vector_properties():
    projections = load_oracle_projections(RELEASE)
    property_names = {
        key.casefold()
        for projection in projections
        for collection in (
            [projection.snapshot],
            projection.records,
            projection.assertions,
            projection.entities,
            projection.values,
        )
        for row in collection
        for key in row
    }

    assert not any("embedding" in key or "vector" in key for key in property_names)


@pytest.mark.parametrize(
    ("obj", "expected"),
    [
        ({"type": "entity_ref", "string_value": "driver-1"}, "driver-1"),
        ({"type": "enum", "string_value": "active"}, "active"),
        ({"type": "integer", "integer_value": 240000}, 240000),
        ({"type": "boolean", "boolean_value": False}, False),
        ({"type": "rational", "rational_value": {"n": 97, "d": 20}}, {"n": 97, "d": 20}),
    ],
)
def test_typed_object_value_is_exact_and_provider_independent(obj, expected):
    assert _typed_object_value(obj) == expected


def test_literal_identity_is_deterministic_and_type_sensitive():
    assert _literal_identity("integer", 1) == _literal_identity("integer", 1)
    assert _literal_identity("integer", 1) != _literal_identity("boolean", True)
    assert _literal_identity("rational", {"n": 1, "d": 2}) != _literal_identity(
        "rational", {"n": 2, "d": 4}
    )
