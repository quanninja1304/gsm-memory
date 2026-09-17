from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

from gsm_memory.data.ledger import AcceptedAssertion, payload_hash, reduce_prefix, select_fact
from gsm_memory.evaluation.formulas import auto_accept, cancel_rate, rating_condition, revenue_charge


K0 = "2026-09-16T01:00:00.000000Z"
KC = "2026-09-17T01:00:00.000000Z"
A0 = "2026-09-16T12:00:00.000000Z"
A1 = "2026-09-17T12:00:00.000000Z"
SCOPE = "scope"
WINDOWS = {
    "W": {"kind": "interval", "from": "2026-09-13T17:00:00.000000Z", "to": {"kind": "finite", "at": "2026-09-14T17:00:00.000000Z"}},
    "WW": {"kind": "interval", "from": "2026-09-06T17:00:00.000000Z", "to": {"kind": "finite", "at": "2026-09-13T17:00:00.000000Z"}},
    "WA": {"kind": "interval", "from": "2026-09-13T17:00:00.000000Z", "to": {"kind": "finite", "at": "2026-09-14T03:00:00.000000Z"}},
}
POLICY_REQUIREMENTS = {
    "revenue_charge": ("P154", {"s154.scope", "s154.region", "s154.day", "s154.revenue", "s154.charge"}),
    "auto_accept": ("P151", {"s151.scope", "s151.auto"}),
    "rating": ("P05", {"s05.rating", "s05.week", "s05.unrated"}),
    "notice_scope": ("P23", {"s23.scope"}),
    "aggregate": ("M01", {"cancel_rate_30d"}),
    "bridge": ("SYNTHETIC_RULE", {"fleet_region"}),
}


@dataclass(frozen=True)
class SemanticFixture:
    fixture_id: str
    evaluator: str
    expected_status: str
    expected_value: Any
    query_entity: str = "D1"
    window: str | None = None
    valid_at: str | None = None
    known_as_of: str = A1
    records: tuple[dict[str, Any], ...] = ()
    sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    premise_ids: tuple[str, ...] = ()


def _sources() -> dict[str, dict[str, Any]]:
    return {
        "registry": {"authority_rank": 10, "allowed_predicates": ["DRIVER_PROGRAM", "OPERATES_IN", "MEMBER_OF", "BASED_IN", "INCIDENT_STATUS"], "can_correct_source_ids": ["registry"]},
        "feed_a": {"authority_rank": 10, "allowed_predicates": ["REPORTED_MEASURE"], "can_correct_source_ids": ["feed_a"]},
        "feed_b": {"authority_rank": 10, "allowed_predicates": ["REPORTED_MEASURE"], "can_correct_source_ids": ["feed_b"]},
    }


def _interval(start: str = "2026-01-01T00:00:00.000000Z", end: str | None = None) -> dict[str, Any]:
    return {"kind": "interval", "from": start, "to": {"kind": "finite", "at": end} if end else {"kind": "unbounded"}}


def _assertion(
    assertion_id: str,
    logical_fact_id: str,
    subject_id: str,
    predicate: str,
    value: Any,
    *,
    valid: dict[str, Any] | None = None,
    qualifiers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "assertion_id": assertion_id,
        "logical_fact_id": logical_fact_id,
        "subject_id": subject_id,
        "predicate": predicate,
        "object": value,
        "qualifiers": qualifiers or {},
        "valid": valid or _interval(),
        "event_time": None,
        "source_refs": [],
    }


def _record(
    record_id: str,
    source_id: str,
    known_at: str,
    assertions: list[dict[str, Any]],
    *,
    operation: str = "assert",
    targets: list[str] | None = None,
) -> dict[str, Any]:
    row = {
        "record_id": record_id,
        "source_id": source_id,
        "scope_id": SCOPE,
        "known_at": known_at,
        "commit_seq": int(record_id.removeprefix("r").split("-", 1)[0]),
        "operation": operation,
        "target_assertion_ids": targets or [],
        "assertions": assertions,
        "raw_payload": {},
    }
    row["payload_hash"] = payload_hash(row)
    return row


def _fact_id(kind: str, entity: str, window: str | None = None) -> str:
    return f"{kind}:{entity}" + (f":{window}" if window else "")


def _state_records(entity: str = "D1", *, program: str = "bike_partner", region: str = "HN") -> list[dict[str, Any]]:
    return [
        _record("r1-program", "registry", K0, [_assertion("a-program", _fact_id("PROGRAM", entity), entity, "DRIVER_PROGRAM", {"type": "enum", "value": program})]),
        _record("r2-region", "registry", K0, [_assertion("a-region", _fact_id("REGION", entity), entity, "OPERATES_IN", {"type": "enum", "value": region})]),
    ]


def _measure_record(
    sequence: int,
    entity: str,
    definition: str,
    window: str,
    value: Any,
    *,
    source: str = "feed_a",
    known: str = K0,
    suffix: str = "v1",
    operation: str = "assert",
    targets: list[str] | None = None,
) -> dict[str, Any]:
    assertion_id = f"a-{definition}-{entity}-{window}-{suffix}"
    assertion = _assertion(
        assertion_id,
        _fact_id(definition, entity, window),
        entity,
        "REPORTED_MEASURE",
        value,
        valid=WINDOWS[window],
        qualifiers={"definition_id": definition, "window": window},
    )
    return _record(f"r{sequence}-{definition}-{suffix}", source, known, [] if operation == "retract" else [assertion], operation=operation, targets=targets)


def _selected(
    records: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    known: str,
    fact_id: str,
    *,
    valid_at: str | None = None,
    expected_valid: dict[str, Any] | None = None,
) -> dict[str, Any]:
    view = reduce_prefix(records, sources, known)
    if valid_at is not None:
        view = [item for item in view if _valid_at(item.payload, valid_at)]
    if expected_valid is not None:
        view = [item for item in view if item.payload["valid"] == expected_valid]
    return select_fact(view, fact_id, sources)


def _missing_or_conflict(selection: dict[str, Any]) -> tuple[str, Any] | None:
    if selection["status"] == "unresolved_conflict":
        return "unresolved_conflict", None
    if selection["status"] != "accepted":
        return "insufficient_evidence", None
    return None


def evaluate_semantic_fixture(fixture: SemanticFixture) -> tuple[str, Any]:
    """Evaluate fixture semantics without consulting fixture_id or expected fields."""

    sources = fixture.sources
    records = fixture.records
    entity = fixture.query_entity
    if fixture.context.get("scope_id", SCOPE) != SCOPE or not fixture.context.get("task_binding_valid", True):
        return "unsupported", None
    if fixture.evaluator in POLICY_REQUIREMENTS:
        expected_source, expected_clauses = POLICY_REQUIREMENTS[fixture.evaluator]
        binding = fixture.context.get("task_binding", {})
        if binding.get("source_id") != expected_source or not expected_clauses <= set(binding.get("clauses", [])):
            return "insufficient_evidence", None

    if fixture.evaluator == "revenue_charge":
        program = _selected(records, sources, fixture.known_as_of, _fact_id("PROGRAM", entity), valid_at=fixture.valid_at)
        region = _selected(records, sources, fixture.known_as_of, _fact_id("REGION", entity), valid_at=fixture.valid_at)
        for selection in (program, region):
            failure = _missing_or_conflict(selection)
            if failure:
                return failure
        if program["value"]["value"] != "bike_partner" or region["value"]["value"] != "HN":
            return "answerable", {"verdict": "not_applicable", "amount": None}
        opday = _selected(records, sources, fixture.known_as_of, _fact_id("RM_OPDAY", entity, fixture.window), expected_valid=WINDOWS[fixture.window])
        failure = _missing_or_conflict(opday)
        if failure:
            return failure
        if opday["value"]["value"] is False:
            return "answerable", {"verdict": "not_applicable", "amount": None}
        revenue = _selected(records, sources, fixture.known_as_of, _fact_id("RM_REVENUE", entity, fixture.window), expected_valid=WINDOWS[fixture.window])
        failure = _missing_or_conflict(revenue)
        if failure:
            return failure
        return "answerable", {"verdict": "applicable", "amount": revenue_charge(int(revenue["value"]["value"]))}

    if fixture.evaluator == "auto_accept":
        program = _selected(records, sources, fixture.known_as_of, _fact_id("PROGRAM", entity), valid_at=fixture.valid_at)
        report = _selected(records, sources, fixture.known_as_of, _fact_id("RM_ACCEPTANCE", entity, fixture.window), expected_valid=WINDOWS[fixture.window])
        for selection in (program, report):
            failure = _missing_or_conflict(selection)
            if failure:
                return failure
        raw = report["value"]["value"]
        met = auto_accept(program["value"]["value"], Fraction(raw["n"], raw["d"]))
        return "answerable", {"condition_met": met, "until": "23h59" if met else None}

    if fixture.evaluator == "rating":
        report = _selected(records, sources, fixture.known_as_of, _fact_id("RM_RATING", entity, fixture.window), expected_valid=WINDOWS[fixture.window])
        failure = _missing_or_conflict(report)
        if failure:
            return failure
        if report["value"]["type"] == "enum" and report["value"]["value"] == "undefined":
            return "insufficient_evidence", None
        raw = report["value"]["value"]
        return "answerable", {"rating_condition_met": rating_condition(Fraction(raw["n"], raw["d"]))}

    if fixture.evaluator == "notice_scope":
        program = _selected(records, sources, fixture.known_as_of, _fact_id("PROGRAM", entity), valid_at=fixture.valid_at)
        failure = _missing_or_conflict(program)
        if failure:
            return failure
        if program["value"]["value"] != "taxi_driver":
            return "answerable", {"in_notice_scope": False}
        membership = _selected(records, sources, fixture.known_as_of, _fact_id("MEMBER_OF", entity), valid_at=fixture.valid_at)
        failure = _missing_or_conflict(membership)
        if failure:
            return failure
        fleet = membership["value"]["value"]
        mappings = fixture.context.get("fleet_registry", {})
        if fleet not in mappings:
            return "insufficient_evidence", None
        return "answerable", {"in_notice_scope": mappings[fleet] in fixture.context["listed_depots"]}

    if fixture.evaluator == "document":
        document = fixture.context["document"]
        binding = fixture.context["binding"]
        if document["available_at"] > fixture.known_as_of:
            return "insufficient_evidence", None
        if document["source_id"] != binding["source_id"] or fixture.context["requested_clause"] not in binding["allowed_clauses"]:
            return "insufficient_evidence", None
        return "answerable", document["clauses"][fixture.context["requested_clause"]]

    if fixture.evaluator == "aggregate":
        events = [event for event in fixture.context["events"] if event["driver_id"] == entity and fixture.context["window_start"] <= event["event_time"] < fixture.context["window_end"]]
        by_trip: dict[str, str] = {}
        for event in events:
            previous = by_trip.get(event["trip_id"])
            if previous is not None and previous != event["outcome"]:
                return "unresolved_conflict", None
            by_trip[event["trip_id"]] = event["outcome"]
        coverage = fixture.context.get("coverage")
        if coverage is None or coverage.get("status") != "complete" or set(coverage.get("members", [])) != set(by_trip):
            return "insufficient_evidence", None
        cancelled = sum(value == "cancelled" for value in by_trip.values())
        completed = sum(value == "completed" for value in by_trip.values())
        value = cancel_rate(cancelled, completed)
        return "answerable", {"metric_status": "undefined" if value is None else "complete", "value": None if value is None else {"n": value.numerator, "d": value.denominator}}

    if fixture.evaluator == "bridge":
        membership = _selected(records, sources, fixture.known_as_of, _fact_id("MEMBER_OF", entity), valid_at=fixture.valid_at)
        failure = _missing_or_conflict(membership)
        if failure:
            return failure
        fleet = membership["value"]["value"]
        based = _selected(records, sources, fixture.known_as_of, _fact_id("BASED_IN", fleet), valid_at=fixture.valid_at)
        failure = _missing_or_conflict(based)
        if failure:
            return failure
        return "answerable", {"applies": based["value"]["value"] == fixture.context["required_region"]}

    raise ValueError(f"unknown fixture evaluator: {fixture.evaluator}")


def _base_revenue(window: str, revenue: int | None = None, opday: bool | None = True, *, revenue_entity: str = "D1") -> list[dict[str, Any]]:
    records = _state_records()
    if opday is not None:
        records.append(_measure_record(3, "D1", "RM_OPDAY", window, {"type": "boolean", "value": opday}))
    if revenue is not None:
        records.append(_measure_record(4, revenue_entity, "RM_REVENUE", window, {"type": "integer", "value": revenue}))
    return records


def ex_fixtures() -> list[SemanticFixture]:
    sources = _sources()
    fixtures: list[SemanticFixture] = []
    def add(identifier: str, evaluator: str, status: str, value: Any, *, records: list[dict[str, Any]] | None = None, window: str | None = None, context: dict[str, Any] | None = None, entity: str = "D1", known: str = A1, premises: tuple[str, ...] = ()) -> None:
        required_source, required_clauses = POLICY_REQUIREMENTS.get(evaluator, (None, set()))
        fixture_context = {
            "task_binding_valid": True,
            "scope_id": SCOPE,
            "task_binding": {"source_id": required_source, "clauses": sorted(required_clauses)},
            **(context or {}),
        }
        valid_at = WINDOWS[window]["from"] if window in WINDOWS else "2026-09-14T00:00:00.000000Z"
        fixtures.append(SemanticFixture(identifier, evaluator, status, value, entity, window, valid_at, known, tuple(records or []), sources, fixture_context, premises))

    add("EX01", "revenue_charge", "answerable", {"verdict": "applicable", "amount": 16000}, records=_base_revenue("W", 200000), window="W", premises=("entity:D1", "source:feed_a", "window:W", "program", "region", "opday", "revenue"))
    add("EX02", "revenue_charge", "answerable", {"verdict": "applicable", "amount": 0}, records=_base_revenue("W", 280000), window="W", premises=("strict-boundary",))
    add("EX03", "revenue_charge", "answerable", {"verdict": "applicable", "amount": 0}, records=_base_revenue("W", 300000), window="W", premises=("nonnegative-charge",))
    add("EX04", "revenue_charge", "answerable", {"verdict": "not_applicable", "amount": None}, records=_base_revenue("W", None, False), window="W", premises=("explicit-opday-false", "short-circuit"))
    add("EX05", "revenue_charge", "insufficient_evidence", None, records=_base_revenue("W", 200000, None), window="W", premises=("missing-opday",))
    add("EX06", "revenue_charge", "insufficient_evidence", None, records=_base_revenue("W", 200000, True, revenue_entity="D2"), window="W", premises=("wrong-entity:D2",))

    program = _state_records()[0]
    acceptance_49 = _measure_record(3, "D1", "RM_ACCEPTANCE", "WA", {"type": "rational", "value": {"n": 49, "d": 100}})
    acceptance_50 = _measure_record(3, "D1", "RM_ACCEPTANCE", "WA", {"type": "rational", "value": {"n": 1, "d": 2}})
    add("EX07", "auto_accept", "answerable", {"condition_met": True, "until": "23h59"}, records=[program, acceptance_49], window="WA", premises=("exact-window:WA", "strict-less-than"))
    add("EX08", "auto_accept", "answerable", {"condition_met": False, "until": None}, records=[program, acceptance_50], window="WA", premises=("boundary:1/2",))
    wrong_window = _measure_record(3, "D1", "RM_ACCEPTANCE", "W", {"type": "rational", "value": {"n": 49, "d": 100}})
    add("EX09", "auto_accept", "insufficient_evidence", None, records=[program, wrong_window], window="WA", premises=("wrong-window:W",))

    rating_equal = _measure_record(3, "D1", "RM_RATING", "WW", {"type": "rational", "value": {"n": 97, "d": 20}})
    rating_above = _measure_record(3, "D1", "RM_RATING", "WW", {"type": "rational", "value": {"n": 49, "d": 10}})
    rating_undefined = _measure_record(3, "D1", "RM_RATING", "WW", {"type": "enum", "value": "undefined"})
    add("EX10", "rating", "answerable", {"rating_condition_met": False}, records=[rating_equal], window="WW", premises=("boundary:97/20",))
    add("EX11", "rating", "answerable", {"rating_condition_met": True}, records=[rating_above], window="WW", premises=("exact-rational:49/10",))
    add("EX12", "rating", "insufficient_evidence", None, records=[rating_undefined], window="WW", premises=("undefined-not-zero",))

    correction_base = _base_revenue("W", None)
    initial = _measure_record(4, "D1", "RM_REVENUE", "W", {"type": "integer", "value": 200000}, suffix="r1")
    replacement = _measure_record(5, "D1", "RM_REVENUE", "W", {"type": "integer", "value": 240000}, known=KC, suffix="r2", operation="replace", targets=["a-RM_REVENUE-D1-W-r1"])
    add("EX13", "revenue_charge", "answerable", {"verdict": "applicable", "amount": 16000}, records=correction_base + [initial, replacement], window="W", known=A0, premises=("known-prefix-before-correction",))
    add("EX14", "revenue_charge", "answerable", {"verdict": "applicable", "amount": 8000}, records=correction_base + [initial, replacement], window="W", known=A1, premises=("known-prefix-after-correction",))
    add("EX15", "revenue_charge", "answerable", {"verdict": "applicable", "amount": 8000}, records=correction_base + [initial, replacement], window="W", known=KC, premises=("inclusive-known-from",))
    competing = _measure_record(5, "D1", "RM_REVENUE", "W", {"type": "integer", "value": 240000}, source="feed_b", known=KC, suffix="conflict")
    add("EX16", "revenue_charge", "unresolved_conflict", None, records=correction_base + [initial, competing], window="W", premises=("equal-authority-conflict",))
    retract = _measure_record(5, "D1", "RM_REVENUE", "W", {"type": "integer", "value": 0}, known=KC, suffix="retract", operation="retract", targets=["a-RM_REVENUE-D1-W-r1"])
    add("EX17", "revenue_charge", "insufficient_evidence", None, records=correction_base + [initial, retract], window="W", premises=("retraction-not-zero",))

    def scope_records(program_value: str, fleet: str) -> list[dict[str, Any]]:
        return [
            _record("r1-program", "registry", K0, [_assertion("a-program", _fact_id("PROGRAM", "D1"), "D1", "DRIVER_PROGRAM", {"type": "enum", "value": program_value})]),
            _record("r2-member", "registry", K0, [_assertion("a-member", _fact_id("MEMBER_OF", "D1"), "D1", "MEMBER_OF", {"type": "entity_ref", "value": fleet})]),
        ]
    scope_context = {"fleet_registry": {"F1": "Depot1", "F2": "Depot2"}, "listed_depots": ["Depot1", "Depot6", "Depot7"]}
    add("EX18", "notice_scope", "answerable", {"in_notice_scope": True}, records=scope_records("taxi_driver", "F1"), context=scope_context, premises=("P23-clause", "registry-map", "membership"))
    add("EX19", "notice_scope", "answerable", {"in_notice_scope": False}, records=scope_records("taxi_driver", "F2"), context=scope_context, premises=("nonlisted-depot",))
    add("EX20", "notice_scope", "answerable", {"in_notice_scope": False}, records=scope_records("bike_partner", "F1"), context=scope_context, premises=("program-short-circuit",))

    doc = {"source_id": "P05", "available_at": K0, "clauses": {"s05.clock": "customer_request_time", "s05.units": "completed_delivery_points"}}
    binding = {"source_id": "P05", "allowed_clauses": ["s05.clock", "s05.units"]}
    add("EX21", "document", "answerable", "customer_request_time", context={"document": doc, "binding": binding, "requested_clause": "s05.clock"}, premises=("source:P05", "binding:B04", "known-visible"))
    add("EX22", "document", "answerable", "completed_delivery_points", context={"document": doc, "binding": binding, "requested_clause": "s05.units"}, premises=("source:P05", "binding:B04", "known-visible"))

    events = [{"trip_id": f"T{i}", "driver_id": "D1", "outcome": "cancelled" if i < 2 else "completed", "event_time": f"2026-09-{i + 1:02d}T00:00:00.000000Z", "source_id": "event"} for i in range(10)]
    aggregate_context = {"events": events, "window_start": "2026-09-01T00:00:00.000000Z", "window_end": "2026-10-01T00:00:00.000000Z", "coverage": {"status": "complete", "members": [f"T{i}" for i in range(10)]}}
    add("EX23", "aggregate", "answerable", {"metric_status": "complete", "value": {"n": 1, "d": 5}}, context=aggregate_context, premises=("10-distinct-trips", "complete-coverage", "definition:M01"))

    bridge_records = [
        _record("r1-member", "registry", K0, [_assertion("a-member", _fact_id("MEMBER_OF", "D1"), "D1", "MEMBER_OF", {"type": "entity_ref", "value": "F1"})]),
        _record("r2-based", "registry", K0, [_assertion("a-based", _fact_id("BASED_IN", "F1"), "F1", "BASED_IN", {"type": "enum", "value": "B"})]),
    ]
    add("EX24", "bridge", "answerable", {"applies": True}, records=bridge_records, context={"required_region": "B"}, premises=("MEMBER_OF", "BASED_IN", "synthetic-rule"))
    add("EX25", "bridge", "insufficient_evidence", None, records=bridge_records[:1], context={"required_region": "B"}, premises=("missing-BASED_IN", "OPERATES_IN-not-equivalent"))
    return fixtures


def run_ex_checks() -> list[dict[str, Any]]:
    results = []
    for fixture in ex_fixtures():
        actual_status, actual_value = evaluate_semantic_fixture(fixture)
        ok = actual_status == fixture.expected_status and actual_value == fixture.expected_value
        results.append({
            "check_id": fixture.fixture_id,
            "ok": ok,
            "expected": {"status": fixture.expected_status, "value": fixture.expected_value, "premise_ids": list(fixture.premise_ids)},
            "actual": {"status": actual_status, "value": actual_value},
            "implicated_ids": [] if ok else [fixture.fixture_id, *fixture.premise_ids],
        })
    return results


def _valid_at(payload: dict[str, Any], instant: str) -> bool:
    valid = payload["valid"]
    if valid["kind"] == "point":
        return valid["at"] == instant
    end = valid["to"]
    return valid["from"] <= instant and (end["kind"] == "unbounded" or instant < end["at"])


def _select_temporal(view: list[AcceptedAssertion], logical_fact_id: str, instant: str, sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    candidates = [item for item in view if item.known_to is None and item.payload["logical_fact_id"] == logical_fact_id and _valid_at(item.payload, instant)]
    if not candidates:
        return {"status": "missing"}
    rank = min(sources[item.source_id]["authority_rank"] for item in candidates)
    top = [item for item in candidates if sources[item.source_id]["authority_rank"] == rank]
    values = {str(item.payload["object"]) for item in top}
    return {"status": "unresolved_conflict"} if len(values) > 1 else {"status": "accepted", "value": top[0].payload["object"], "subject_id": top[0].payload["subject_id"]}


def run_aux_incident_check() -> dict[str, Any]:
    sources = _sources()
    old = _assertion("incident-old", "INCIDENT_STATUS:I1", "I1", "INCIDENT_STATUS", {"type": "enum", "value": "open"}, valid=_interval("2026-01-01T00:00:00.000000Z"))
    initial = _record("r1-incident", "registry", "2026-01-01T00:00:00.000000Z", [old])
    schedule = [
        _assertion("incident-open-1", "INCIDENT_STATUS:I1", "I1", "INCIDENT_STATUS", {"type": "enum", "value": "open"}, valid=_interval("2026-01-01T00:00:00.000000Z", "2026-01-02T00:00:00.000000Z")),
        _assertion("incident-resolved", "INCIDENT_STATUS:I1", "I1", "INCIDENT_STATUS", {"type": "enum", "value": "resolved"}, valid=_interval("2026-01-02T00:00:00.000000Z", "2026-01-03T00:00:00.000000Z")),
        _assertion("incident-open-2", "INCIDENT_STATUS:I1", "I1", "INCIDENT_STATUS", {"type": "enum", "value": "open"}, valid=_interval("2026-01-03T00:00:00.000000Z")),
    ]
    corrected = _record("r2-incident", "registry", "2026-01-04T00:00:00.000000Z", schedule, operation="replace", targets=["incident-old"])
    records = [initial, corrected]
    probes = [
        ("before-known-correction", "2026-01-02T12:00:00.000000Z", "2026-01-03T00:00:00.000000Z", "open"),
        ("open", "2026-01-01T12:00:00.000000Z", "2026-01-05T00:00:00.000000Z", "open"),
        ("resolved-boundary", "2026-01-02T00:00:00.000000Z", "2026-01-05T00:00:00.000000Z", "resolved"),
        ("reopened-boundary", "2026-01-03T00:00:00.000000Z", "2026-01-05T00:00:00.000000Z", "open"),
    ]
    actual = []
    identities = set()
    for name, valid_at, known, expected in probes:
        selected = _select_temporal(reduce_prefix(records, sources, known), "INCIDENT_STATUS:I1", valid_at, sources)
        identities.add(selected.get("subject_id"))
        actual.append({"probe": name, "status": selected["status"], "value": selected.get("value", {}).get("value")})
    missing_without_coverage = _select_temporal([], "INCIDENT_STATUS:I1", "2026-01-02T00:00:00.000000Z", sources)
    expected = [
        {"probe": name, "status": "accepted", "value": value}
        for name, _, _, value in probes
    ]
    ok = actual == expected and identities == {"I1"} and missing_without_coverage["status"] == "missing"
    return {
        "check_id": "AUX_INCIDENT",
        "ok": ok,
        "expected": {"probes": expected, "canonical_incident_ids": ["I1"], "absence_without_coverage": "insufficient_evidence"},
        "actual": {"probes": actual, "canonical_incident_ids": sorted(item for item in identities if item), "absence_without_coverage": "insufficient_evidence" if missing_without_coverage["status"] == "missing" else missing_without_coverage["status"]},
        "implicated_ids": [] if ok else ["I1", "incident-old", "incident-resolved", "incident-open-2"],
    }


def proof_complete(required: set[str], available: set[str]) -> bool:
    return bool(required) and required <= available


def run_counterfactual_checks() -> list[dict[str, Any]]:
    sources = _sources()
    checks: list[dict[str, Any]] = []
    def emit(identifier: str, mutation: str, before: Any, after: Any, expected_before: Any, expected_after: Any) -> None:
        ok = before == expected_before and after == expected_after and before != after
        checks.append({"check_id": identifier, "ok": ok, "expected": {"mutation": mutation, "before": expected_before, "after": expected_after}, "actual": {"before": before, "after": after}, "implicated_ids": [] if ok else [identifier]})

    f_true = next(item for item in ex_fixtures() if item.fixture_id == "EX07")
    f_boundary = next(item for item in ex_fixtures() if item.fixture_id == "EX08")
    emit("CF_THRESHOLD", "acceptance 49/100 -> 1/2", evaluate_semantic_fixture(f_true), evaluate_semantic_fixture(f_boundary), ("answerable", {"condition_met": True, "until": "23h59"}), ("answerable", {"condition_met": False, "until": None}))

    before_correction = next(item for item in ex_fixtures() if item.fixture_id == "EX13")
    after_correction = next(item for item in ex_fixtures() if item.fixture_id == "EX14")
    emit("CF_KNOWN_PREFIX", "known_as_of A0 -> A1", evaluate_semantic_fixture(before_correction), evaluate_semantic_fixture(after_correction), ("answerable", {"verdict": "applicable", "amount": 16000}), ("answerable", {"verdict": "applicable", "amount": 8000}))

    base = SemanticFixture(**{**before_correction.__dict__, "known_as_of": A0})
    retracted = next(item for item in ex_fixtures() if item.fixture_id == "EX17")
    emit("CF_RETRACTION", "append authorized retract", evaluate_semantic_fixture(base), evaluate_semantic_fixture(retracted), ("answerable", {"verdict": "applicable", "amount": 16000}), ("insufficient_evidence", None))

    conflict = next(item for item in ex_fixtures() if item.fixture_id == "EX16")
    emit("CF_EQUAL_RANK_CONFLICT", "add equal-rank competing source", evaluate_semantic_fixture(base), evaluate_semantic_fixture(conflict), ("answerable", {"verdict": "applicable", "amount": 16000}), ("unresolved_conflict", None))

    bridge_full = next(item for item in ex_fixtures() if item.fixture_id == "EX24")
    bridge_missing = next(item for item in ex_fixtures() if item.fixture_id == "EX25")
    emit("CF_BRIDGE_REMOVAL", "remove BASED_IN assertion", evaluate_semantic_fixture(bridge_full), evaluate_semantic_fixture(bridge_missing), ("answerable", {"applies": True}), ("insufficient_evidence", None))

    aggregate = next(item for item in ex_fixtures() if item.fixture_id == "EX23")
    missing_coverage = SemanticFixture(**{**aggregate.__dict__, "context": {**aggregate.context, "coverage": None}})
    emit("CF_COVERAGE_REMOVAL", "remove complete coverage certificate", evaluate_semantic_fixture(aggregate), evaluate_semantic_fixture(missing_coverage), ("answerable", {"metric_status": "complete", "value": {"n": 1, "d": 5}}), ("insufficient_evidence", None))

    required = {"rule", "identity", "operand"}
    emit("CF_PROOF_ATOM_REMOVAL", "remove required operand atom", proof_complete(required, set(required)), proof_complete(required, {"rule", "identity"}), True, False)
    return checks
