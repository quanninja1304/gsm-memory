"""Small, snapshot-safe Neo4j tools for GSM Operational KG v3."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field

from gsm_memory.adapters.neo4j_operational_v2 import _safe_identifier
from gsm_memory.data.primitives import canonical_bytes


ScopeType = Literal["Fleet", "Region", "Zone"]
TargetType = Literal["Driver", "Incident", "Trip"]
StateStatus = Literal["resolved", "conflict", "missing"]


class EntityResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["resolved", "ambiguous", "not_found"]
    mention: str
    matches: list[dict[str, Any]]


class PageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope_type: ScopeType
    scope_id: str
    target_type: TargetType
    total_count: int = Field(ge=0)
    returned_count: int = Field(ge=0)
    items: list[dict[str, Any]]
    next_cursor: str | None
    truncated: bool


class TemporalStateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: StateStatus
    entity_type: Literal["Driver", "Incident"]
    entity_id: str
    state_kind: str
    value: str | None
    candidates: list[dict[str, Any]]


class MetricResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["answerable", "undefined", "insufficient_evidence"]
    metric: Literal["cancel_rate_30d"] = "cancel_rate_30d"
    driver_id: str
    window_start: str
    window_end: str
    cancelled_count: int | None = Field(default=None, ge=0)
    completed_count: int | None = Field(default=None, ge=0)
    numerator: int | None
    denominator: int | None
    value: str | None
    coverage: Literal["complete", "missing"]


_SCOPE_PATHS: dict[
    tuple[ScopeType, TargetType], tuple[str, tuple[str, ...]]
] = {
    ("Region", "Driver"): (
        "(scope:Region)<-[scope_rel:OPERATES_IN]-(target:Driver)",
        ("scope_rel",),
    ),
    ("Region", "Trip"): (
        "(scope:Region)<-[scope_rel:IN_REGION]-(target:Trip)",
        ("scope_rel",),
    ),
    ("Region", "Incident"): (
        "(scope:Region)<-[region_rel:OPERATES_IN]-(:Driver)"
        "-[incident_rel:HAS_INCIDENT]->(target:Incident)",
        ("region_rel", "incident_rel"),
    ),
    ("Fleet", "Driver"): (
        "(scope:Fleet)<-[scope_rel:MEMBER_OF]-(target:Driver)",
        ("scope_rel",),
    ),
    ("Fleet", "Trip"): (
        "(scope:Fleet)<-[fleet_rel:MEMBER_OF]-(:Driver)"
        "-[trip_rel:PERFORMED]->(target:Trip)",
        ("fleet_rel", "trip_rel"),
    ),
    ("Fleet", "Incident"): (
        "(scope:Fleet)<-[fleet_rel:MEMBER_OF]-(:Driver)"
        "-[incident_rel:HAS_INCIDENT]->(target:Incident)",
        ("fleet_rel", "incident_rel"),
    ),
    ("Zone", "Driver"): (
        "(scope:Zone)<-[zone_rel:PICKUP_IN|DROPOFF_IN]-(:Trip)"
        "<-[trip_rel:PERFORMED]-(target:Driver)",
        ("zone_rel", "trip_rel"),
    ),
    ("Zone", "Trip"): (
        "(scope:Zone)<-[scope_rel:PICKUP_IN|DROPOFF_IN]-(target:Trip)",
        ("scope_rel",),
    ),
    ("Zone", "Incident"): (
        "(scope:Zone)<-[zone_rel:PICKUP_IN|DROPOFF_IN]-(:Trip)"
        "<-[trip_rel:ABOUT_TRIP]-(target:Incident)",
        ("zone_rel", "trip_rel"),
    ),
}


def _rows(result: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in result.data()]


def _utc_timestamp(value: str, field: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(UTC).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class OperationalQueryService:
    """Execute reviewed query templates; never accept raw Cypher from callers."""

    def __init__(
        self,
        session: Any,
        marker_label: str = "GSMOperationalV3Timeline",
        *,
        snapshot_contexts: Iterable[dict[str, Any]] = (),
    ) -> None:
        self.session = session
        self.marker = _safe_identifier(marker_label)
        self.snapshots = {
            row["snapshot_id"]: dict(row) for row in snapshot_contexts
        }

    @classmethod
    def from_candidate(
        cls,
        session: Any,
        candidate: Path,
        marker_label: str = "GSMOperationalV3Timeline",
    ) -> "OperationalQueryService":
        path = candidate / "snapshots.jsonl"
        contexts = _read_jsonl(path) if path.is_file() else []
        return cls(session, marker_label, snapshot_contexts=contexts)

    def resolve_entity(
        self,
        mention: str,
        *,
        allowed_types: tuple[str, ...] = ("Driver", "Fleet", "Region", "Zone"),
        snapshot_id: str | None = None,
    ) -> EntityResolution:
        clean = mention.strip()
        if not clean:
            return EntityResolution(status="not_found", mention=mention, matches=[])
        self._snapshot_context(snapshot_id)
        allowed = tuple(_safe_identifier(label) for label in allowed_types)
        query = (
            f"MATCH (n:{self.marker}) "
            "WHERE any(label IN labels(n) WHERE label IN $allowed_types) "
            "AND (n.id = $mention OR toLower(n.name) = toLower($mention)) "
            "AND ($snapshot_id IS NULL OR $snapshot_id IN "
            "coalesce(n.visibility_snapshot_ids, [])) "
            "RETURN n.id AS id, n.name AS name, "
            f"[label IN labels(n) WHERE label <> '{self.marker}'][0] AS type "
            "ORDER BY type, id LIMIT 101"
        )
        matches = _rows(
            self.session.run(
                query,
                mention=clean,
                allowed_types=list(allowed),
                snapshot_id=snapshot_id,
            )
        )
        status = "resolved" if len(matches) == 1 else "ambiguous" if matches else "not_found"
        return EntityResolution(status=status, mention=mention, matches=matches)

    def get_driver_context(
        self,
        driver_id: str,
        *,
        window_start: str | None = None,
        window_end: str | None = None,
        valid_at: str | None = None,
        known_at: str | None = None,
        snapshot_id: str | None = None,
        per_type_limit: int = 50,
    ) -> dict[str, Any]:
        if not 1 <= per_type_limit <= 100:
            raise ValueError("per_type_limit must be between 1 and 100")
        parameters = self._parameters(
            valid_at=valid_at,
            known_at=known_at,
            snapshot_id=snapshot_id,
            window_start=window_start,
            window_end=window_end,
        )
        parameters.update(driver_id=driver_id, limit=per_type_limit)
        driver_query = (
            f"MATCH (d:{self.marker}:Driver {{id: $driver_id}}) "
            "WHERE ($snapshot_id IS NULL OR $snapshot_id IN "
            "coalesce(d.visibility_snapshot_ids, [])) "
            "RETURN d.id AS id, d.name AS name, d.description AS description"
        )
        driver_rows = _rows(self.session.run(driver_query, **parameters))
        if not driver_rows:
            return {"status": "not_found", "driver_id": driver_id}

        visible = self._edge_predicate
        templates = {
            "trips": (
                f"MATCH (d:{self.marker}:Driver {{id: $driver_id}})"
                f"-[rel:PERFORMED]->(n:{self.marker}:Trip) WHERE "
                f"{visible('rel')} {self._event_window('n')} "
                "RETURN n.id AS id, n.name AS name, n.description AS description, "
                "n.event_time AS event_time, n.outcome AS outcome "
                "ORDER BY n.event_time DESC, n.id LIMIT $limit"
            ),
            "complaints": (
                f"MATCH (d:{self.marker}:Driver {{id: $driver_id}})"
                f"-[rel:RECEIVED_COMPLAINT]->(n:{self.marker}:Complaint) WHERE "
                f"{visible('rel')} {self._event_window('n')} "
                "RETURN n.id AS id, n.name AS name, n.description AS description, "
                "n.event_time AS event_time, n.category AS category "
                "ORDER BY n.event_time DESC, n.id LIMIT $limit"
            ),
            "incidents": (
                f"MATCH (d:{self.marker}:Driver {{id: $driver_id}})"
                f"-[incident_rel:HAS_INCIDENT]->(n:{self.marker}:Incident) WHERE "
                f"{visible('incident_rel')} {self._event_window('n')} "
                f"OPTIONAL MATCH (n)-[state_rel:HAS_STATE]->"
                f"(s:{self.marker}:StateObservation) WHERE {visible('state_rel')} "
                "RETURN n.id AS id, n.name AS name, n.description AS description, "
                "n.event_time AS event_time, n.incident_type AS incident_type, "
                "collect(DISTINCT s.value) AS states "
                "ORDER BY n.event_time DESC, n.id LIMIT $limit"
            ),
            "states": (
                f"MATCH (d:{self.marker}:Driver {{id: $driver_id}})"
                f"-[rel:HAS_STATE]->(n:{self.marker}:StateObservation) WHERE "
                f"{visible('rel')} "
                "RETURN n.id AS id, n.name AS name, n.description AS description, "
                "n.state_kind AS state_kind, n.value AS value "
                "ORDER BY n.state_kind, n.id LIMIT $limit"
            ),
            "vehicles": (
                f"MATCH (d:{self.marker}:Driver {{id: $driver_id}})"
                f"-[rel:OPERATED]->(n:{self.marker}:Vehicle) WHERE {visible('rel')} "
                "RETURN n.id AS id, n.name AS name, n.description AS description "
                "ORDER BY n.id LIMIT $limit"
            ),
        }
        result = {
            name: _rows(self.session.run(query, **parameters))
            for name, query in templates.items()
        }
        return {
            "status": "pass",
            "driver": driver_rows[0],
            "window_start": parameters["window_start"],
            "window_end": parameters["window_end"],
            "valid_at": parameters["valid_at"],
            "known_at": parameters["known_at"],
            "snapshot_id": snapshot_id,
            **result,
        }

    def get_driver_state(
        self,
        driver_id: str,
        *,
        state_kind: str,
        valid_at: str,
        known_at: str,
        snapshot_id: str | None = None,
    ) -> TemporalStateResult:
        return self._get_state(
            "Driver", driver_id, state_kind, valid_at, known_at, snapshot_id
        )

    def get_incident_state(
        self,
        incident_id: str,
        *,
        valid_at: str,
        known_at: str,
        snapshot_id: str | None = None,
    ) -> TemporalStateResult:
        return self._get_state(
            "Incident", incident_id, "incident_status", valid_at, known_at, snapshot_id
        )

    def _get_state(
        self,
        entity_type: Literal["Driver", "Incident"],
        entity_id: str,
        state_kind: str,
        valid_at: str,
        known_at: str,
        snapshot_id: str | None,
    ) -> TemporalStateResult:
        parameters = self._parameters(
            valid_at=valid_at, known_at=known_at, snapshot_id=snapshot_id
        )
        parameters.update(entity_id=entity_id, state_kind=state_kind)
        query = (
            f"MATCH (n:{self.marker}:{entity_type} {{id: $entity_id}})"
            f"-[rel:HAS_STATE]->(s:{self.marker}:StateObservation) "
            f"WHERE s.state_kind = $state_kind AND {self._edge_predicate('rel')} "
            "RETURN s.id AS id, s.value AS value, "
            "rel.resolution_status AS resolution_status, "
            "rel.valid_from AS valid_from, rel.valid_to AS valid_to, "
            "rel.known_from AS known_from, rel.known_to AS known_to "
            "ORDER BY s.id"
        )
        candidates = _rows(self.session.run(query, **parameters))
        values = {row["value"] for row in candidates}
        status: StateStatus
        value: str | None
        if not candidates:
            status, value = "missing", None
        elif len(values) != 1:
            status, value = "conflict", None
        else:
            status, value = "resolved", next(iter(values))
        return TemporalStateResult(
            status=status,
            entity_type=entity_type,
            entity_id=entity_id,
            state_kind=state_kind,
            value=value,
            candidates=candidates,
        )

    def count_scope(
        self,
        scope_type: ScopeType,
        scope_id: str,
        target_type: TargetType,
        *,
        window_start: str | None = None,
        window_end: str | None = None,
        valid_at: str | None = None,
        known_at: str | None = None,
        snapshot_id: str | None = None,
    ) -> int:
        parameters = self._parameters(
            valid_at=valid_at,
            known_at=known_at,
            snapshot_id=snapshot_id,
            window_start=window_start,
            window_end=window_end,
        )
        path, aliases = _SCOPE_PATHS[(scope_type, target_type)]
        predicate = " AND ".join(self._edge_predicate(alias) for alias in aliases)
        query = (
            f"MATCH {self._mark_path(path)} WHERE scope.id = $scope_id "
            f"AND {predicate} {self._target_window(target_type)} "
            "RETURN count(DISTINCT target) AS total_count"
        )
        parameters["scope_id"] = scope_id
        rows = _rows(self.session.run(query, **parameters))
        return int(rows[0]["total_count"]) if rows else 0

    def list_scope(
        self,
        scope_type: ScopeType,
        scope_id: str,
        target_type: TargetType,
        *,
        window_start: str | None = None,
        window_end: str | None = None,
        page_size: int = 20,
        cursor: str | None = None,
        valid_at: str | None = None,
        known_at: str | None = None,
        snapshot_id: str | None = None,
    ) -> PageResult:
        if not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        total = self.count_scope(
            scope_type,
            scope_id,
            target_type,
            window_start=window_start,
            window_end=window_end,
            valid_at=valid_at,
            known_at=known_at,
            snapshot_id=snapshot_id,
        )
        parameters = self._parameters(
            valid_at=valid_at,
            known_at=known_at,
            snapshot_id=snapshot_id,
            window_start=window_start,
            window_end=window_end,
        )
        path, aliases = _SCOPE_PATHS[(scope_type, target_type)]
        predicate = " AND ".join(self._edge_predicate(alias) for alias in aliases)
        query = (
            f"MATCH {self._mark_path(path)} WHERE scope.id = $scope_id "
            f"AND {predicate} {self._target_window(target_type)} "
            "AND ($cursor IS NULL OR target.id > $cursor) "
            "RETURN DISTINCT target.id AS id, target.name AS name, "
            "target.description AS description, target.event_time AS event_time "
            "ORDER BY id LIMIT $limit"
        )
        parameters.update(scope_id=scope_id, cursor=cursor, limit=page_size + 1)
        rows = _rows(self.session.run(query, **parameters))
        truncated = len(rows) > page_size
        items = rows[:page_size]
        return PageResult(
            scope_type=scope_type,
            scope_id=scope_id,
            target_type=target_type,
            total_count=total,
            returned_count=len(items),
            items=items,
            next_cursor=items[-1]["id"] if truncated and items else None,
            truncated=truncated,
        )

    def compute_cancel_rate_30d(
        self,
        driver_id: str,
        *,
        window_start: str,
        window_end: str,
        snapshot_dir: Path,
    ) -> MetricResult:
        start = _utc_timestamp(window_start, "window_start")
        end = _utc_timestamp(window_end, "window_end")
        if datetime.fromisoformat(end.replace("Z", "+00:00")) - datetime.fromisoformat(
            start.replace("Z", "+00:00")
        ) != timedelta(days=30):
            raise ValueError("cancel_rate_30d requires an exact 30-day [start, end) window")
        coverage = self._coverage(snapshot_dir, driver_id, start, end)
        if coverage is None:
            return MetricResult(
                status="insufficient_evidence",
                driver_id=driver_id,
                window_start=start,
                window_end=end,
                numerator=None,
                denominator=None,
                value=None,
                coverage="missing",
            )

        manifest = json.loads((snapshot_dir / "manifest.json").read_text("utf-8"))
        member_ids = sorted(coverage["member_ids"])
        query = (
            f"MATCH (d:{self.marker}:Driver {{id: $driver_id}})"
            f"-[rel:PERFORMED]->(t:{self.marker}:Trip) "
            "WHERE t.id IN $member_ids "
            f"AND {self._edge_predicate('rel')} "
            "AND datetime(t.event_time) >= datetime($window_start) "
            "AND datetime(t.event_time) < datetime($window_end) "
            "AND t.outcome IN ['completed', 'cancelled'] "
            "RETURN t.id AS id, t.outcome AS outcome ORDER BY t.id"
        )
        rows = _rows(
            self.session.run(
                query,
                driver_id=driver_id,
                member_ids=member_ids,
                snapshot_id=manifest["snapshot_id"],
                valid_at=end,
                known_at=_utc_timestamp(manifest["known_as_of"], "known_as_of"),
                window_start=start,
                window_end=end,
            )
        )
        if sorted(row["id"] for row in rows) != member_ids:
            return MetricResult(
                status="insufficient_evidence",
                driver_id=driver_id,
                window_start=start,
                window_end=end,
                numerator=None,
                denominator=None,
                value=None,
                coverage="missing",
            )
        cancelled = sum(row["outcome"] == "cancelled" for row in rows)
        completed = sum(row["outcome"] == "completed" for row in rows)
        denominator = cancelled + completed
        if denominator == 0:
            status, numerator, exact_denominator, value = "undefined", 0, 0, None
        else:
            rate = Fraction(cancelled, denominator)
            status = "answerable"
            numerator, exact_denominator = rate.numerator, rate.denominator
            value = f"{rate.numerator}/{rate.denominator}"
        return MetricResult(
            status=status,
            driver_id=driver_id,
            window_start=start,
            window_end=end,
            cancelled_count=cancelled,
            completed_count=completed,
            numerator=numerator,
            denominator=exact_denominator,
            value=value,
            coverage="complete",
        )

    @staticmethod
    def _coverage(
        snapshot_dir: Path, driver_id: str, window_start: str, window_end: str
    ) -> dict[str, Any] | None:
        manifest = json.loads((snapshot_dir / "manifest.json").read_text("utf-8"))
        known_as_of = _utc_timestamp(manifest["known_as_of"], "known_as_of")
        for artifact in _read_jsonl(snapshot_dir / "artifacts.jsonl"):
            spec = artifact.get("coverage_spec") or {}
            domain = spec.get("covered_domain") or {}
            window = spec.get("valid_window") or {}
            if not (
                artifact.get("artifact_type") == "coverage"
                and artifact.get("complete") is True
                and domain.get("domain_id") == "terminal_trip_population"
                and spec.get("subject_id") == driver_id
                and _utc_timestamp(window.get("start", ""), "coverage.start")
                == window_start
                and _utc_timestamp(window.get("end", ""), "coverage.end") == window_end
                and _utc_timestamp(artifact["published_at"], "published_at")
                <= known_as_of
            ):
                continue
            members = sorted(artifact.get("member_ids") or [])
            members_digest = hashlib.sha256(
                b"coverage-members-v1\0" + canonical_bytes(members)
            ).hexdigest()
            content = {
                "contract_version": "coverage-v1",
                "coverage_spec_id": artifact["coverage_spec_id"],
                "coverage_spec": spec,
                "member_ids": members,
                "member_count": len(members),
                "members_digest": members_digest,
                "complete": True,
            }
            content_digest = hashlib.sha256(
                b"coverage-content-v1\0" + canonical_bytes(content)
            ).hexdigest()
            if (
                artifact.get("member_count") != len(members)
                or artifact.get("members_digest") != members_digest
                or artifact.get("coverage_content_digest_v1") != content_digest
            ):
                raise ValueError("coverage artifact failed integrity verification")
            return artifact
        return None

    def _snapshot_context(self, snapshot_id: str | None) -> dict[str, Any] | None:
        if snapshot_id is None:
            return None
        if not self.snapshots:
            raise ValueError("snapshot catalog is required when snapshot_id is provided")
        try:
            return self.snapshots[snapshot_id]
        except KeyError as error:
            raise ValueError(f"unknown snapshot_id: {snapshot_id}") from error

    def _parameters(
        self,
        *,
        valid_at: str | None,
        known_at: str | None,
        snapshot_id: str | None,
        window_start: str | None = None,
        window_end: str | None = None,
    ) -> dict[str, Any]:
        supplied = (valid_at is not None, known_at is not None)
        if supplied[0] != supplied[1]:
            raise ValueError("historical queries require both valid_at and known_at")
        context = self._snapshot_context(snapshot_id)
        if snapshot_id is not None and not all(supplied):
            raise ValueError("snapshot queries require both valid_at and known_at")
        normalized_valid = (
            _utc_timestamp(valid_at, "valid_at") if valid_at is not None else None
        )
        normalized_known = (
            _utc_timestamp(known_at, "known_at") if known_at is not None else None
        )
        if context is not None and normalized_known is not None:
            cutoff = _utc_timestamp(context["known_as_of"], "known_as_of")
            if normalized_known > cutoff:
                raise ValueError("known_at exceeds the selected snapshot cutoff")
        normalized_start = (
            _utc_timestamp(window_start, "window_start")
            if window_start is not None
            else None
        )
        normalized_end = (
            _utc_timestamp(window_end, "window_end")
            if window_end is not None
            else None
        )
        if (normalized_start is None) != (normalized_end is None):
            raise ValueError("event windows require both window_start and window_end")
        if normalized_start is not None and normalized_start >= normalized_end:
            raise ValueError("event window must be non-empty")
        return {
            "valid_at": normalized_valid,
            "known_at": normalized_known,
            "snapshot_id": snapshot_id,
            "window_start": normalized_start,
            "window_end": normalized_end,
        }

    @staticmethod
    def _edge_predicate(alias: str) -> str:
        return (
            f"coalesce({alias}.resolution_status, 'accepted') <> 'superseded' "
            f"AND ($snapshot_id IS NULL OR $snapshot_id IN "
            f"coalesce({alias}.visibility_snapshot_ids, [])) "
            f"AND ($valid_at IS NULL OR {alias}.valid_from IS NULL OR "
            f"datetime({alias}.valid_from) <= datetime($valid_at)) "
            f"AND ($valid_at IS NULL OR {alias}.valid_to IS NULL OR "
            f"datetime($valid_at) < datetime({alias}.valid_to)) "
            f"AND ($known_at IS NULL OR {alias}.known_from IS NULL OR "
            f"datetime({alias}.known_from) <= datetime($known_at)) "
            f"AND ($known_at IS NULL OR {alias}.known_to IS NULL OR "
            f"datetime($known_at) < datetime({alias}.known_to))"
        )

    @staticmethod
    def _event_window(alias: str) -> str:
        return (
            f"AND ($window_start IS NULL OR ({alias}.event_time IS NOT NULL AND "
            f"datetime({alias}.event_time) >= datetime($window_start))) "
            f"AND ($window_end IS NULL OR ({alias}.event_time IS NOT NULL AND "
            f"datetime({alias}.event_time) < datetime($window_end)))"
        )

    def _target_window(self, target_type: TargetType) -> str:
        return "" if target_type == "Driver" else self._event_window("target")

    def _mark_path(self, path: str) -> str:
        return path.replace("(", f"(:{self.marker}").replace(
            f"(:{self.marker}scope:", f"(scope:{self.marker}:"
        ).replace(
            f"(:{self.marker}target:", f"(target:{self.marker}:"
        )
