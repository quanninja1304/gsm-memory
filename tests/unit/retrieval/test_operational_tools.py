from __future__ import annotations

import json
from pathlib import Path

import pytest

from gsm_memory.retrieval.operational_tools import OperationalQueryService


SNAPSHOT = Path(
    "data/gsm-dev-core-0.2.2/public/snapshots/"
    "d4cc0438-d831-541a-8123-ddda94ccdac8"
)
DRIVER_WITH_COVERAGE = "c499f934-bfe1-5509-a578-afb09cee357c"
DRIVER_EMPTY_COVERAGE = "122a3140-7c98-5136-a732-8a9566cb727d"


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def data(self):
        return self._rows


class _Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def run(self, query, **parameters):
        self.calls.append((query, parameters))
        return _Result(self.responses.pop(0))


def _coverage(driver_id: str) -> dict:
    rows = [json.loads(line) for line in (SNAPSHOT / "artifacts.jsonl").read_text("utf-8").splitlines()]
    return next(
        row
        for row in rows
        if row.get("artifact_type") == "coverage"
        and row["coverage_spec"]["subject_id"] == driver_id
        and row["coverage_spec"]["covered_domain"]["domain_id"]
        == "terminal_trip_population"
    )


def test_resolve_entity_is_exact_and_reports_ambiguity():
    resolved_session = _Session([[{"id": "d1", "name": "An", "type": "Driver"}]])
    resolved = OperationalQueryService(resolved_session).resolve_entity("An")
    assert resolved.status == "resolved"
    assert resolved.matches[0]["id"] == "d1"
    assert "$mention" in resolved_session.calls[0][0]

    ambiguous = OperationalQueryService(
        _Session([[
            {"id": "d1", "name": "Minh", "type": "Driver"},
            {"id": "d2", "name": "Minh", "type": "Driver"},
        ]])
    ).resolve_entity("Minh")
    assert ambiguous.status == "ambiguous"


def test_list_scope_is_stably_paginated_and_never_hides_truncation():
    session = _Session([
        [{"total_count": 3}],
        [
            {"id": "a", "name": "A", "description": "A", "event_time": None},
            {"id": "b", "name": "B", "description": "B", "event_time": None},
            {"id": "c", "name": "C", "description": "C", "event_time": None},
        ],
    ])
    page = OperationalQueryService(session).list_scope(
        "Region", "region-1", "Driver", page_size=2
    )
    assert page.total_count == 3
    assert [item["id"] for item in page.items] == ["a", "b"]
    assert page.next_cursor == "b"
    assert page.truncated is True
    assert "ORDER BY id LIMIT $limit" in session.calls[1][0]


def test_same_instant_in_two_timezones_normalizes_to_identical_parameters():
    contexts = [{
        "snapshot_id": "s1",
        "ledger_id": "l1",
        "known_as_of": "2026-09-17T12:00:00.000000Z",
        "record_count": 1,
    }]
    calls = []
    for valid_at in ("2026-09-13T16:30:00Z", "2026-09-13T23:30:00+07:00"):
        session = _Session([[{"total_count": 1}]])
        OperationalQueryService(session, snapshot_contexts=contexts).count_scope(
            "Fleet",
            "fleet-1",
            "Driver",
            valid_at=valid_at,
            known_at="2026-09-17T12:00:00Z",
            snapshot_id="s1",
        )
        calls.append(session.calls[0])
    assert calls[0][1]["valid_at"] == calls[1][1]["valid_at"]
    assert calls[0][1]["valid_at"] == "2026-09-13T16:30:00.000000Z"
    assert "datetime(scope_rel.valid_from)" in calls[0][0]


def test_snapshot_queries_require_catalog_and_both_time_cutoffs():
    service = OperationalQueryService(_Session([]))
    with pytest.raises(ValueError, match="snapshot catalog"):
        service.count_scope(
            "Fleet",
            "f1",
            "Driver",
            valid_at="2026-01-01T00:00:00Z",
            known_at="2026-01-01T00:00:00Z",
            snapshot_id="missing",
        )
    with pytest.raises(ValueError, match="both valid_at and known_at"):
        service.count_scope("Fleet", "f1", "Driver", valid_at="2026-01-01T00:00:00Z")


def test_every_scope_relationship_gets_snapshot_valid_and_known_filters():
    contexts = [{
        "snapshot_id": "s1",
        "ledger_id": "l1",
        "known_as_of": "2026-09-17T12:00:00Z",
        "record_count": 1,
    }]
    session = _Session([[{"total_count": 1}]])
    OperationalQueryService(session, snapshot_contexts=contexts).count_scope(
        "Region",
        "region-1",
        "Incident",
        valid_at="2026-09-17T00:00:00Z",
        known_at="2026-09-17T01:00:00Z",
        snapshot_id="s1",
    )
    query = session.calls[0][0]
    for alias in ("region_rel", "incident_rel"):
        assert f"$snapshot_id IN coalesce({alias}.visibility_snapshot_ids" in query
        assert f"datetime({alias}.valid_from)" in query
        assert f"datetime({alias}.known_from)" in query


def test_state_tools_return_resolved_conflict_and_missing():
    resolved = OperationalQueryService(_Session([[
        {"id": "s1", "value": "active", "resolution_status": "accepted"}
    ]])).get_driver_state(
        "d1",
        state_kind="driver_status",
        valid_at="2026-01-01T00:00:00Z",
        known_at="2026-01-01T00:00:00Z",
    )
    assert (resolved.status, resolved.value) == ("resolved", "active")

    one_visible_candidate = OperationalQueryService(_Session([[
        {"id": "s1", "value": "active", "resolution_status": "unresolved_conflict"}
    ]])).get_driver_state(
        "d1",
        state_kind="driver_status",
        valid_at="2026-01-01T00:00:00Z",
        known_at="2026-01-01T00:00:00Z",
    )
    assert (one_visible_candidate.status, one_visible_candidate.value) == (
        "resolved",
        "active",
    )

    conflict = OperationalQueryService(_Session([[
        {"id": "s1", "value": "active", "resolution_status": "unresolved_conflict"},
        {"id": "s2", "value": "suspended", "resolution_status": "unresolved_conflict"},
    ]])).get_driver_state(
        "d1",
        state_kind="driver_status",
        valid_at="2026-01-01T00:00:00Z",
        known_at="2026-01-01T00:00:00Z",
    )
    assert (conflict.status, conflict.value) == ("conflict", None)

    missing = OperationalQueryService(_Session([[]])).get_incident_state(
        "i1",
        valid_at="2026-01-01T00:00:00Z",
        known_at="2026-01-01T00:00:00Z",
    )
    assert (missing.status, missing.value) == ("missing", None)


def test_driver_context_filters_all_edges_and_returns_driver_states():
    session = _Session([
        [{"id": "d1", "name": "An", "description": "Driver"}],
        [{"id": "t1", "name": "Trip", "description": "Trip"}],
        [],
        [],
        [{"id": "s1", "state_kind": "driver_status", "value": "active"}],
        [{"id": "v1", "name": "Vehicle", "description": "Vehicle"}],
    ])
    result = OperationalQueryService(session).get_driver_context("d1", per_type_limit=20)
    assert result["status"] == "pass"
    assert result["trips"][0]["id"] == "t1"
    assert result["states"][0]["value"] == "active"
    assert len(session.calls) == 6
    assert all("LIMIT $limit" in call[0] for call in session.calls[1:])
    assert all("known_from" in call[0] for call in session.calls[1:])


def test_cancel_rate_verifies_coverage_artifact_and_uses_exact_rational():
    coverage = _coverage(DRIVER_WITH_COVERAGE)
    rows = [
        {"id": member_id, "outcome": "cancelled" if index < 2 else "completed"}
        for index, member_id in enumerate(sorted(coverage["member_ids"]))
    ]
    result = OperationalQueryService(_Session([rows])).compute_cancel_rate_30d(
        DRIVER_WITH_COVERAGE,
        window_start="2026-08-17T00:00:00+07:00",
        window_end="2026-09-16T00:00:00+07:00",
        snapshot_dir=SNAPSHOT,
    )
    assert result.status == "answerable"
    assert (result.cancelled_count, result.completed_count) == (2, 8)
    assert (result.numerator, result.denominator, result.value) == (1, 5, "1/5")


def test_cancel_rate_missing_coverage_is_not_reported_as_zero(tmp_path):
    (tmp_path / "manifest.json").write_text(
        json.dumps({
            "snapshot_id": "s1",
            "known_as_of": "2026-09-17T12:00:00Z",
        }),
        encoding="utf-8",
    )
    (tmp_path / "artifacts.jsonl").write_text("", encoding="utf-8")
    result = OperationalQueryService(_Session([])).compute_cancel_rate_30d(
        "d1",
        window_start="2026-01-01T00:00:00Z",
        window_end="2026-01-31T00:00:00Z",
        snapshot_dir=tmp_path,
    )
    assert result.status == "insufficient_evidence"
    assert result.coverage == "missing"
    assert result.cancelled_count is None
    assert result.completed_count is None


def test_cancel_rate_zero_population_is_undefined_not_zero():
    result = OperationalQueryService(_Session([[]])).compute_cancel_rate_30d(
        DRIVER_EMPTY_COVERAGE,
        window_start="2026-08-17T00:00:00+07:00",
        window_end="2026-09-16T00:00:00+07:00",
        snapshot_dir=SNAPSHOT,
    )
    assert result.status == "undefined"
    assert result.denominator == 0
    assert result.value is None


def test_cancel_rate_rejects_non_30_day_or_naive_windows():
    service = OperationalQueryService(_Session([]))
    with pytest.raises(ValueError, match="exact 30-day"):
        service.compute_cancel_rate_30d(
            DRIVER_WITH_COVERAGE,
            window_start="2026-01-01T00:00:00Z",
            window_end="2026-01-30T00:00:00Z",
            snapshot_dir=SNAPSHOT,
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        service.compute_cancel_rate_30d(
            DRIVER_WITH_COVERAGE,
            window_start="2026-01-01T00:00:00",
            window_end="2026-01-31T00:00:00",
            snapshot_dir=SNAPSHOT,
        )
