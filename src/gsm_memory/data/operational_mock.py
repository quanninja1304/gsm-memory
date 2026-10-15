"""Deterministic experimental dataset for GSM Operational KG v2.

The generator reads public frozen snapshot packages and reviewed TEXT locators.
It never mutates the source release and never reads private gold or task
bindings. New operational domains are explicitly synthetic and live in a
separate, versioned artifact.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

from gsm_memory.adapters.neo4j_operational import (
    project_operational_snapshot,
)
from gsm_memory.data.operational_v2_contract import OperationalKGv2Contract
from gsm_memory.data.primitives import canonical_bytes


SCHEMA_VERSION = "gsm-operational-mock-v0.1"
SUPPORTED_DATASET_VERSIONS = {
    "gsm-operational-mock-v0.1",
    "gsm-operational-mock-v0.2",
    "gsm-operational-mock-v0.3",
}
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "urn:gsm-memory:operational-mock:v0.1")


def _id(kind: str, key: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{kind}:{key}"))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timezone-aware timestamp required: {value}")
    return parsed


def _utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]


def _node(label: str, node_id: str, props: dict[str, Any]) -> dict[str, Any]:
    # Neo4j represents ``SET property = null`` by removing the property.
    # Canonical candidates therefore omit optional nulls before hashing so the
    # persisted representation can be compared exactly and idempotently.
    values = {key: value for key, value in {"id": node_id, **props}.items() if value is not None}
    if not values.get("name") or not values.get("description"):
        raise ValueError(f"{label}/{node_id} must have readable name and description")
    return {"label": label, "id": node_id, "props": values}


def _edge(
    rel_type: str,
    start_label: str,
    start_id: str,
    end_label: str,
    end_id: str,
    evidence_key: str,
    props: dict[str, Any],
) -> dict[str, Any]:
    edge_id = _id("edge", f"{rel_type}:{start_id}:{end_id}:{evidence_key}")
    return {
        "type": rel_type,
        "id": edge_id,
        "start_label": start_label,
        "start_id": start_id,
        "end_label": end_label,
        "end_id": end_id,
        "props": {
            key: value
            for key, value in {"id": edge_id, "evidence_ref": evidence_key, **props}.items()
            if value is not None
        },
    }


def _fraction(value: str) -> Fraction:
    if value == "undefined":
        raise ValueError("undefined value cannot be evaluated")
    return Fraction(value)


def _covers_window(props: dict[str, Any], start: str, end: str) -> bool:
    """Return whether one accepted interval covers the complete [start, end)."""

    if props.get("valid_kind") != "interval" or not props.get("valid_from"):
        return False
    window_start = _parse_time(start)
    window_end = _parse_time(end)
    valid_from = _parse_time(props["valid_from"])
    valid_to = _parse_time(props["valid_to"]) if props.get("valid_to") else None
    return valid_from <= window_start and (valid_to is None or window_end <= valid_to)


_STATIC_SNAPSHOT_NODE_LABELS = {
    "Driver",
    "Fleet",
    "Region",
    "Service",
    "Vehicle",
    "VehicleType",
    "Zone",
}

_STATIC_SNAPSHOT_RELATIONSHIPS = {
    "BASED_IN",
    "CONTAINS_ZONE",
    "HAS_TYPE",
    "OPERATED",
}


def _operational_snapshots(
    config: dict[str, Any], source_ledger_id: str
) -> tuple[dict[str, Any], ...]:
    """Build one ordered snapshot catalog for the operational L0 timeline."""

    timeline_id = config.get("snapshot_timeline_id")
    plans = config.get("operational_snapshots")
    if timeline_id != "L0" or not isinstance(plans, list) or len(plans) != 12:
        raise ValueError("v0.3 requires 12 ordered operational snapshots on L0")
    snapshots: list[dict[str, Any]] = []
    previous: datetime | None = None
    for expected_sequence, plan in enumerate(plans, 1):
        if plan.get("sequence") != expected_sequence:
            raise ValueError("operational snapshot sequence must be contiguous from 1")
        cutoff = _parse_time(str(plan["known_as_of"]))
        if previous is not None and cutoff <= previous:
            raise ValueError("operational snapshot cutoffs must be strictly increasing")
        previous = cutoff
        known_as_of = _utc(cutoff)
        snapshots.append(
            {
                "snapshot_id": _id(
                    "operational-snapshot",
                    f"{timeline_id}:{expected_sequence}:{known_as_of}",
                ),
                "timeline_id": timeline_id,
                "source_ledger_id": source_ledger_id,
                "sequence": expected_sequence,
                "known_as_of": known_as_of,
                "name": str(plan["name"]),
            }
        )
    return tuple(snapshots)


def _apply_operational_snapshot_visibility(
    nodes: dict[tuple[str, str], dict[str, Any]],
    edges: dict[str, dict[str, Any]],
    snapshots: tuple[dict[str, Any], ...],
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, dict[str, Any]]]:
    """Attach cumulative L0 visibility without copying nodes or relationships."""

    cutoffs = [(_parse_time(row["known_as_of"]), row["snapshot_id"]) for row in snapshots]
    all_snapshot_ids = [snapshot_id for _, snapshot_id in cutoffs]

    def visible_from(props: dict[str, Any]) -> list[str]:
        value = (
            props.get("known_from")
            or props.get("event_time")
            or props.get("effective_at")
            or props.get("ingestion_time")
        )
        if value is None:
            return list(all_snapshot_ids)
        instant = _parse_time(str(value))
        return [snapshot_id for cutoff, snapshot_id in cutoffs if instant <= cutoff]

    rewritten_edges: dict[str, dict[str, Any]] = {}
    adjacent_visibility: dict[tuple[str, str], set[str]] = defaultdict(set)
    for edge_id, row in edges.items():
        props = dict(row["props"])
        props.pop("visibility_snapshot_id", None)
        props.pop("visibility_snapshot_ids", None)
        visibility = (
            list(all_snapshot_ids)
            if row["type"] in _STATIC_SNAPSHOT_RELATIONSHIPS
            else visible_from(props)
        )
        props["visibility_snapshot_ids"] = visibility
        rewritten = {**row, "props": props}
        rewritten_edges[edge_id] = rewritten
        adjacent_visibility[(row["start_label"], row["start_id"])].update(visibility)
        adjacent_visibility[(row["end_label"], row["end_id"])].update(visibility)

    rewritten_nodes: dict[tuple[str, str], dict[str, Any]] = {}
    order = {snapshot_id: index for index, snapshot_id in enumerate(all_snapshot_ids)}
    for key, row in nodes.items():
        props = dict(row["props"])
        props.pop("visibility_snapshot_id", None)
        props.pop("visibility_snapshot_ids", None)
        if row["label"] in _STATIC_SNAPSHOT_NODE_LABELS:
            visibility = list(all_snapshot_ids)
        else:
            visibility = sorted(adjacent_visibility.get(key, ()), key=order.__getitem__)
            if not visibility:
                visibility = visible_from(props)
        props["visibility_snapshot_ids"] = visibility
        rewritten_nodes[key] = {**row, "props": props}

    # A visible relationship must never point outside the selected snapshot.
    for edge_id, row in rewritten_edges.items():
        start_visibility = set(
            rewritten_nodes[(row["start_label"], row["start_id"])]["props"][
                "visibility_snapshot_ids"
            ]
        )
        end_visibility = set(
            rewritten_nodes[(row["end_label"], row["end_id"])]["props"][
                "visibility_snapshot_ids"
            ]
        )
        props = dict(row["props"])
        props["visibility_snapshot_ids"] = [
            snapshot_id
            for snapshot_id in props["visibility_snapshot_ids"]
            if snapshot_id in start_visibility and snapshot_id in end_visibility
        ]
        rewritten_edges[edge_id] = {**row, "props": props}
    return rewritten_nodes, rewritten_edges


@dataclass(frozen=True)
class OperationalMockDataset:
    dataset_version: str
    source_release: str
    source_snapshot_id: str
    seed: int
    logical_digest: str
    nodes: tuple[dict[str, Any], ...]
    edges: tuple[dict[str, Any], ...]
    snapshots: tuple[dict[str, Any], ...] = ()

    @property
    def counts(self) -> dict[str, Any]:
        node_labels = Counter(row["label"] for row in self.nodes)
        relationship_types = Counter(row["type"] for row in self.edges)
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "node_labels": dict(sorted(node_labels.items())),
            "relationship_types": dict(sorted(relationship_types.items())),
        }


def _current_edges(edges: Iterable[dict[str, Any]], rel_type: str) -> list[dict[str, Any]]:
    return [
        edge
        for edge in edges
        if edge["type"] == rel_type
        and edge["props"].get("resolution_status") == "accepted"
        and edge["props"].get("known_to") is None
        and edge["props"].get("valid_to") is None
    ]


def _merge_config(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_config(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_config(path: Path, *, seen: set[Path] | None = None) -> dict[str, Any]:
    path = path.resolve()
    seen = set() if seen is None else seen
    if path in seen:
        raise ValueError(f"cyclic operational mock config inheritance: {path}")
    seen.add(path)
    config = json.loads(path.read_text("utf-8"))
    parent = config.pop("extends", None)
    if parent is not None:
        config = _merge_config(
            _load_config(path.parent / parent, seen=seen),
            config,
        )
    seen.remove(path)
    if config.get("dataset_version") not in SUPPORTED_DATASET_VERSIONS:
        raise ValueError(f"unsupported mock dataset version: {config.get('dataset_version')}")
    if config.get("source_release") != "gsm-dev-core-0.2.2":
        raise ValueError("operational mock must remain bound to gsm-dev-core-0.2.2")
    if config.get("seed") != 42:
        raise ValueError("operational mock root seed must remain 42")
    rule_ids = [row["id"] for row in config.get("policy_rules", [])]
    if len(rule_ids) != len(set(rule_ids)) or not rule_ids:
        raise ValueError("policy rule IDs must be non-empty and unique")
    return config


def generate_operational_mock(
    release: Path,
    config_path: Path = Path("configs/datasets/gsm-operational-mock-v0.1.json"),
    contract_path: Path = Path("configs/benchmark/operational-kg-v2.json"),
) -> OperationalMockDataset:
    """Generate the complete v2 candidate in memory without external I/O."""

    release = release.resolve()
    config = _load_config(config_path)
    contract = OperationalKGv2Contract.load(contract_path)
    dataset_version = config["dataset_version"]
    is_mvp_v02 = dataset_version == "gsm-operational-mock-v0.2"
    is_mvp_v03 = dataset_version == "gsm-operational-mock-v0.3"
    is_v3_family = is_mvp_v02 or is_mvp_v03
    materialize_shifts = config["generation"].get("materialize_shifts", True)
    materialize_summaries = config["generation"].get("materialize_summaries", True)
    expected_contract = {
        "gsm-operational-mock-v0.1": "gsm-operational-kg-v2-draft-1",
        "gsm-operational-mock-v0.2": "gsm-operational-kg-v3-draft-1",
        "gsm-operational-mock-v0.3": "gsm-operational-kg-v3-draft-2",
    }[dataset_version]
    if contract.contract_version != expected_contract:
        raise ValueError(
            f"{config['dataset_version']} requires contract {expected_contract}, "
            f"got {contract.contract_version}"
        )
    if release.name != config["source_release"] or release.name != contract.source_release:
        raise ValueError("source release identity mismatch")
    source_snapshot_id = config["source_snapshot_id"]
    baseline = project_operational_snapshot(release, source_snapshot_id)
    logical_ingestion_time = config["logical_ingestion_time"]
    if config["timezone"] != "Asia/Ho_Chi_Minh":
        raise ValueError("operational mock supports only the BC01 Asia/Ho_Chi_Minh calendar")
    # Vietnam has a fixed UTC+07:00 offset and no daylight-saving transition.
    # Using an explicit offset keeps the offline build independent of the
    # optional IANA ``tzdata`` wheel on Windows.
    business_tz = timezone(timedelta(hours=7))

    nodes: dict[tuple[str, str], dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}

    def add_node(row: dict[str, Any]) -> None:
        key = (row["label"], row["id"])
        if key in nodes and nodes[key] != row:
            raise ValueError(f"conflicting node: {key}")
        nodes[key] = row

    def add_edge(row: dict[str, Any]) -> None:
        if row["id"] in edges and edges[row["id"]] != row:
            raise ValueError(f"conflicting edge: {row['id']}")
        edges[row["id"]] = row

    snapshots: tuple[dict[str, Any], ...] = ()
    projected_nodes = list(baseline.nodes)
    projected_edges: list[tuple[dict[str, Any], tuple[str, ...], str]] = [
        (row, (source_snapshot_id,), str(row["props"]["evidence_ref"]))
        for row in baseline.edges
    ]
    if is_mvp_v03:
        source_manifest = json.loads(
            (
                release
                / "public"
                / "snapshots"
                / source_snapshot_id
                / "manifest.json"
            ).read_text("utf-8")
        )
        snapshots = _operational_snapshots(config, source_manifest["ledger_id"])

    # Store each frozen fact once and attach the snapshots in which it is visible.
    for row in projected_nodes:
        props = {
            **row["props"],
            "source_kind": "frozen_projection",
            "source_release": release.name,
            "source_snapshot_id": source_snapshot_id,
        }
        if is_mvp_v03:
            # Visibility is assigned once after the full L0 graph has been built.
            props.pop("snapshot_id", None)
        add_node(_node(row["label"], row["id"], props))
    for row, _, evidence_key in projected_edges:
        props = dict(row["props"])
        if is_mvp_v03:
            props.pop("snapshot_id", None)
        else:
            props["visibility_snapshot_id"] = props.pop("snapshot_id")
        props.update(
            source_kind="frozen_projection",
            source_release=release.name,
            ingestion_time=logical_ingestion_time,
        )
        add_edge(
            _edge(
                row["type"],
                row["start_label"],
                row["start_id"],
                row["end_label"],
                row["end_id"],
                evidence_key,
                props,
            )
        )

    base_nodes = {(row["label"], row["id"]): row for row in baseline.nodes}
    base_edges = list(baseline.edges)
    drivers = sorted(
        (row for row in baseline.nodes if row["label"] == "Driver"),
        key=lambda row: row["id"],
    )
    trips = sorted(
        (row for row in baseline.nodes if row["label"] == "Trip"),
        key=lambda row: (row["props"]["event_time"], row["id"]),
    )
    if len(drivers) != 8 or len(trips) != 80:
        raise ValueError(f"expected 8 drivers and 80 trips, got {len(drivers)} and {len(trips)}")

    performed = {
        edge["end_id"]: edge["start_id"]
        for edge in base_edges
        if edge["type"] == "PERFORMED"
        and edge["props"].get("resolution_status") == "accepted"
        and edge["props"].get("known_to") is None
    }
    trip_known_from = {
        edge["end_id"]: edge["props"]["known_from"]
        for edge in base_edges
        if edge["type"] == "PERFORMED"
        and edge["props"].get("resolution_status") == "accepted"
        and edge["props"].get("known_to") is None
    }
    trip_region = {
        edge["start_id"]: edge["end_id"]
        for edge in base_edges
        if edge["type"] == "IN_REGION"
        and edge["props"].get("resolution_status") == "accepted"
        and edge["props"].get("known_to") is None
    }
    if set(performed) != {row["id"] for row in trips} or set(trip_region) != set(performed):
        raise ValueError("every terminal trip must have one accepted driver and region")

    programs: dict[str, str] = {}
    for edge in _current_edges(base_edges, "HAS_STATE"):
        state = base_nodes[("StateObservation", edge["end_id"])]["props"]
        if state.get("state_kind") == "driver_program":
            programs[edge["start_id"]] = state["value"]
    if set(programs) != {row["id"] for row in drivers}:
        raise ValueError("every driver must have one current program")

    current_regions: dict[str, set[str]] = defaultdict(set)
    current_fleets: dict[str, set[str]] = defaultdict(set)
    for edge in _current_edges(base_edges, "OPERATES_IN"):
        current_regions[edge["start_id"]].add(edge["end_id"])
    for edge in _current_edges(base_edges, "MEMBER_OF"):
        current_fleets[edge["start_id"]].add(edge["end_id"])

    # Vehicle and type mocks, deterministically derived from public driver program.
    type_ids = {
        "bike_partner": _id("vehicle-type", "electric-motorbike"),
        "taxi_driver": _id("vehicle-type", "electric-taxi"),
    }
    type_specs = {
        "bike_partner": ("Xe máy điện", "Loại phương tiện xe máy điện tổng hợp"),
        "taxi_driver": ("Ô tô điện", "Loại phương tiện ô tô điện tổng hợp"),
    }
    for program, type_id in sorted(type_ids.items()):
        name, description = type_specs[program]
        add_node(
            _node(
                "VehicleType",
                type_id,
                {
                    "name": name,
                    "description": description,
                    "program": program,
                    "source_kind": "synthetic_extension",
                    "ingestion_time": logical_ingestion_time,
                },
            )
        )

    driver_vehicle: dict[str, str] = {}
    driver_trip_times: dict[str, list[datetime]] = defaultdict(list)
    for trip in trips:
        driver_trip_times[performed[trip["id"]]].append(_parse_time(trip["props"]["event_time"]))
    assignment_fallback = min(
        _parse_time(trip["props"]["event_time"]) for trip in trips
    ) - timedelta(days=30)
    for index, driver in enumerate(drivers, 1):
        driver_id = driver["id"]
        vehicle_id = _id("vehicle", driver_id)
        driver_vehicle[driver_id] = vehicle_id
        vehicle_name = f"Phương tiện mock {index:02d}"
        add_node(
            _node(
                "Vehicle",
                vehicle_id,
                {
                    "name": vehicle_name,
                    "description": f"Phương tiện tổng hợp được gán cho {driver['props']['name']}",
                    "mock_plate": f"MOCK-{index:03d}",
                    "source_kind": "synthetic_extension",
                    "ingestion_time": logical_ingestion_time,
                },
            )
        )
        # A driver can legitimately have no terminal trip in this public
        # snapshot (Hà is the explicit zero-activity control).  Vehicle
        # assignment remains defined without fabricating a trip for them.
        driver_times = driver_trip_times[driver_id]
        valid_from = _utc(
            min(driver_times) - timedelta(days=30)
            if driver_times
            else assignment_fallback
        )
        add_edge(
            _edge(
                "OPERATED",
                "Driver",
                driver_id,
                "Vehicle",
                vehicle_id,
                f"vehicle-assignment:{driver_id}",
                {
                    "valid_from": valid_from,
                    "known_from": logical_ingestion_time,
                    "ingestion_time": logical_ingestion_time,
                    "source_kind": "synthetic_extension",
                },
            )
        )
        add_edge(
            _edge(
                "HAS_TYPE",
                "Vehicle",
                vehicle_id,
                "VehicleType",
                type_ids[programs[driver_id]],
                f"vehicle-type:{vehicle_id}",
                {
                    "valid_from": valid_from,
                    "known_from": logical_ingestion_time,
                    "ingestion_time": logical_ingestion_time,
                    "source_kind": "synthetic_extension",
                },
            )
        )

    # Zones: two per frozen region, with deterministic trip assignment.
    zones_by_region: dict[str, list[str]] = defaultdict(list)
    regions = sorted(
        (row for row in baseline.nodes if row["label"] == "Region"),
        key=lambda row: row["id"],
    )
    for region in regions:
        for number in range(1, config["generation"]["zones_per_region"] + 1):
            zone_id = _id("zone", f"{region['id']}:{number}")
            zones_by_region[region["id"]].append(zone_id)
            add_node(
                _node(
                    "Zone",
                    zone_id,
                    {
                        "name": f"Vùng mock {number} — {region['props']['name']}",
                        "description": f"Vùng vận hành tổng hợp số {number} thuộc {region['props']['name']}",
                        "source_kind": "synthetic_extension",
                        "ingestion_time": logical_ingestion_time,
                    },
                )
            )
            add_edge(
                _edge(
                    "CONTAINS_ZONE",
                    "Region",
                    region["id"],
                    "Zone",
                    zone_id,
                    f"region-zone:{region['id']}:{number}",
                    {
                        "known_from": logical_ingestion_time,
                        "ingestion_time": logical_ingestion_time,
                        "source_kind": "synthetic_extension",
                    },
                )
            )

    trip_zones: dict[str, tuple[str, str]] = {}
    for trip in trips:
        region_zones = zones_by_region[trip_region[trip["id"]]]
        pickup_index = uuid.UUID(trip["id"]).int % len(region_zones)
        pickup = region_zones[pickup_index]
        dropoff = region_zones[(pickup_index + 1) % len(region_zones)]
        trip_zones[trip["id"]] = (pickup, dropoff)
        for rel_type, zone_id in (("PICKUP_IN", pickup), ("DROPOFF_IN", dropoff)):
            add_edge(
                _edge(
                    rel_type,
                    "Trip",
                    trip["id"],
                    "Zone",
                    zone_id,
                    f"{rel_type.lower()}:{trip['id']}",
                    {
                        "event_time": trip["props"]["event_time"],
                        "known_from": (
                            trip_known_from[trip["id"]]
                            if is_mvp_v03
                            else logical_ingestion_time
                        ),
                        "ingestion_time": logical_ingestion_time,
                        "source_kind": "synthetic_extension",
                    },
                )
            )

    # One shift per driver and local business date.
    shift_trips: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for trip in (trips if materialize_shifts else ()):
        driver_id = performed[trip["id"]]
        local_date = _parse_time(trip["props"]["event_time"]).astimezone(business_tz).date().isoformat()
        shift_trips[(driver_id, local_date)].append(trip)
    trip_shift: dict[str, str] = {}
    for (driver_id, local_date), rows in sorted(shift_trips.items()):
        times = [_parse_time(row["props"]["event_time"]) for row in rows]
        shift_id = _id("shift", f"{driver_id}:{local_date}")
        add_node(
            _node(
                "Shift",
                shift_id,
                {
                    "name": f"Ca {local_date} — {base_nodes[('Driver', driver_id)]['props']['name']}",
                    "description": f"Ca tổng hợp chứa {len(rows)} chuyến terminal trong ngày {local_date}",
                    "start_time": _utc(min(times) - timedelta(minutes=30)),
                    "end_time": _utc(max(times) + timedelta(minutes=30)),
                    "source_kind": "synthetic_extension",
                    "ingestion_time": logical_ingestion_time,
                },
            )
        )
        add_edge(
            _edge(
                "WORKED_SHIFT",
                "Driver",
                driver_id,
                "Shift",
                shift_id,
                f"driver-shift:{shift_id}",
                {
                    "valid_from": _utc(min(times) - timedelta(minutes=30)),
                    "valid_to": _utc(max(times) + timedelta(minutes=30)),
                    "known_from": logical_ingestion_time,
                    "ingestion_time": logical_ingestion_time,
                    "source_kind": "synthetic_extension",
                },
            )
        )
        shift_zone_ids: set[str] = set()
        for trip in rows:
            trip_shift[trip["id"]] = shift_id
            shift_zone_ids.update(trip_zones[trip["id"]])
            add_edge(
                _edge(
                    "CONTAINS_TRIP",
                    "Shift",
                    shift_id,
                    "Trip",
                    trip["id"],
                    f"shift-trip:{trip['id']}",
                    {
                        "event_time": trip["props"]["event_time"],
                        "known_from": logical_ingestion_time,
                        "ingestion_time": logical_ingestion_time,
                        "source_kind": "synthetic_extension",
                    },
                )
            )
        for zone_id in sorted(shift_zone_ids):
            add_edge(
                _edge(
                    "OPERATED_IN",
                    "Shift",
                    shift_id,
                    "Zone",
                    zone_id,
                    f"shift-zone:{shift_id}:{zone_id}",
                    {
                        "known_from": logical_ingestion_time,
                        "ingestion_time": logical_ingestion_time,
                        "source_kind": "synthetic_extension",
                    },
                )
            )

    # Deterministic complaints and one maintenance event per assigned vehicle.
    if is_mvp_v03:
        trip_by_id = {trip["id"]: trip for trip in trips}
        complaint_plans = config["generation"]["complaint_scenarios"]
        scenario_ids = [row["scenario_id"] for row in complaint_plans]
        scenario_trip_ids = [row["trip_id"] for row in complaint_plans]
        if len(complaint_plans) != 11:
            raise ValueError("v0.3 requires exactly 11 complaint scenarios")
        if len(set(scenario_ids)) != len(scenario_ids):
            raise ValueError("complaint scenario IDs must be unique")
        if len(set(scenario_trip_ids)) != len(scenario_trip_ids):
            raise ValueError("complaint scenario Trip links must be unique")
        if set(scenario_trip_ids) - set(trip_by_id):
            raise ValueError("complaint scenario references an unknown Trip")
    else:
        categories = config["generation"]["complaint_categories"]
        every = config["generation"]["complaint_every_nth_trip"]
        complaint_plans = [
            {
                "scenario_id": f"legacy-complaint-{index // every:02d}",
                "trip_id": trip["id"],
                "category": categories[(index // every - 1) % len(categories)],
            }
            for index, trip in enumerate(trips, 1)
            if index % every == 0
        ]

    complaint_names = {
        "service_attitude": "Phản ánh thái độ phục vụ",
        "trip_cancellation": "Phản ánh đề nghị huỷ chuyến",
        "fare_question": "Yêu cầu rà soát cước",
    }
    for plan in complaint_plans:
        trip = next(row for row in trips if row["id"] == plan["trip_id"])
        category = plan["category"]
        if category not in complaint_names:
            raise ValueError(f"unsupported complaint category: {category}")
        complaint_id = _id("complaint", trip["id"])
        event_time = _utc(_parse_time(trip["props"]["event_time"]) + timedelta(minutes=15))
        if is_mvp_v03:
            description = plan["description"]
        elif is_mvp_v02:
            description = {
                "service_attitude": (
                    f"Phản ánh mock về thái độ phục vụ trong {trip['props']['name']}. "
                    "Khách hàng yêu cầu đội vận hành rà soát cách giao tiếp; "
                    "bản ghi chưa kết luận lỗi thuộc tài xế."
                ),
                "trip_cancellation": (
                    f"Phản ánh mock về việc {trip['props']['name']} không được tiếp "
                    "tục. Kết quả cuối của chuyến được kiểm tra riêng từ node Trip; "
                    "phản ánh này không tự xác định nguyên nhân."
                ),
                "fare_question": (
                    "Phản ánh mock yêu cầu kiểm tra số tiền của "
                    f"{trip['props']['name']}. Bộ dữ liệu không cung cấp giao dịch "
                    "thanh toán nên chưa thể kết luận có thu sai."
                ),
            }[category]
        else:
            description = (
                f"Phản ánh tổng hợp nhóm {category} liên quan tới "
                f"{trip['props']['name']}"
            )
        complaint_props = {
            "name": (
                f"{complaint_names[category]} — {trip['props']['name']}"
                if is_mvp_v03
                else f"Phản ánh mock cho {trip['props']['name']}"
            ),
            "description": description,
            "category": category,
            "event_time": event_time,
            "source_kind": "synthetic_extension",
            "ingestion_time": logical_ingestion_time,
        }
        if is_mvp_v03:
            complaint_props["scenario_id"] = plan["scenario_id"]
        add_node(_node("Complaint", complaint_id, complaint_props))
        driver_id = performed[trip["id"]]
        common = {
            "event_time": event_time,
            "known_from": event_time if is_mvp_v03 else logical_ingestion_time,
            "ingestion_time": logical_ingestion_time,
            "source_kind": "synthetic_extension",
        }
        add_edge(_edge("RECEIVED_COMPLAINT", "Driver", driver_id, "Complaint", complaint_id, f"driver-complaint:{complaint_id}", common))
        add_edge(_edge("ABOUT_TRIP", "Complaint", complaint_id, "Trip", trip["id"], f"complaint-trip:{complaint_id}", common))

    if is_v3_family:
        trip_by_id = {trip["id"]: trip for trip in trips}
        seen_scenarios: set[str] = set()
        seen_incident_trips: set[str] = set()
        for scenario in config["generation"]["incident_scenarios"]:
            scenario_id = scenario["scenario_id"]
            trip_id = scenario["trip_id"]
            if scenario_id in seen_scenarios or trip_id in seen_incident_trips:
                raise ValueError("incident scenarios and trip links must be unique")
            seen_scenarios.add(scenario_id)
            seen_incident_trips.add(trip_id)
            if trip_id not in trip_by_id:
                raise ValueError(f"incident scenario references unknown Trip: {trip_id}")
            trip = trip_by_id[trip_id]
            driver_id = performed[trip_id]
            event_time = _utc(
                _parse_time(trip["props"]["event_time"])
                + timedelta(minutes=int(scenario["event_offset_minutes"]))
            )
            incident_id = _id("incident-mock", scenario_id)
            add_node(
                _node(
                    "Incident",
                    incident_id,
                    {
                        "name": (
                            scenario["name"]
                            if is_mvp_v03
                            else f"Sự cố mock {scenario_id}"
                        ),
                        "description": scenario["description"],
                        "incident_type": scenario["incident_type"],
                        "event_time": event_time,
                        "source_kind": "synthetic_extension",
                        "ingestion_time": logical_ingestion_time,
                    },
                )
            )
            common = {
                "event_time": event_time,
                "valid_from": event_time,
                "known_from": event_time if is_mvp_v03 else logical_ingestion_time,
                "ingestion_time": logical_ingestion_time,
                "source_kind": "synthetic_extension",
            }
            add_edge(
                _edge(
                    "HAS_INCIDENT",
                    "Driver",
                    driver_id,
                    "Incident",
                    incident_id,
                    f"driver-incident:{scenario_id}",
                    common,
                )
            )
            add_edge(
                _edge(
                    "ABOUT_TRIP",
                    "Incident",
                    incident_id,
                    "Trip",
                    trip_id,
                    f"incident-trip:{scenario_id}",
                    common,
                )
            )
            state_history = (
                {
                    "open": ("open",),
                    "resolved": ("open", "resolved"),
                    "reopened": ("open", "resolved", "reopened"),
                }[scenario["state"]]
                if is_mvp_v03
                else (scenario["state"],)
            )
            for state_index, state_value in enumerate(state_history):
                state_id = _id("incident-state", f"{scenario_id}:{state_value}")
                valid_from = _utc(
                    _parse_time(event_time) + timedelta(hours=state_index)
                )
                valid_to = (
                    _utc(_parse_time(event_time) + timedelta(hours=state_index + 1))
                    if state_index + 1 < len(state_history)
                    else None
                )
                known_from = valid_from if is_mvp_v03 else logical_ingestion_time
                add_node(
                    _node(
                        "StateObservation",
                        state_id,
                        {
                            "name": (
                                f"Trạng thái {state_value} của {scenario_id}"
                                if is_mvp_v03
                                else f"Trạng thái {state_value} của {scenario_id}"
                            ),
                            "description": (
                                (
                                    f"Sự cố {scenario_id} ở trạng thái {state_value} "
                                    f"từ {valid_from}"
                                    + (f" đến trước {valid_to}." if valid_to else ".")
                                )
                                if is_mvp_v03
                                else f"Trạng thái mock {state_value} của sự cố "
                                f"{scenario_id}, có hiệu lực từ {event_time}."
                            ),
                            "state_kind": "incident_status",
                            "value": state_value,
                            "source_kind": "synthetic_extension",
                            "ingestion_time": logical_ingestion_time,
                        },
                    )
                )
                add_edge(
                    _edge(
                        "HAS_STATE",
                        "Incident",
                        incident_id,
                        "StateObservation",
                        state_id,
                        (
                            f"incident-state:{scenario_id}:{state_value}"
                            if is_mvp_v03
                            else f"incident-state:{scenario_id}"
                        ),
                        {
                            **common,
                            "valid_from": valid_from,
                            "valid_to": valid_to,
                            "known_from": known_from,
                        },
                    )
                )

    maintenance_types = config["generation"].get(
        "maintenance_types", ["scheduled_inspection"]
    )
    maintenance_descriptions = {
        "scheduled_inspection": (
            "Kiểm tra định kỳ tổng quát; bản ghi mock chưa cung cấp kết luận "
            "hỏng hóc."
        ),
        "battery_check": (
            "Kiểm tra tình trạng pin của phương tiện điện; bản ghi mock không "
            "tạo phần trăm sức khỏe pin."
        ),
        "brake_check": (
            "Kiểm tra hệ thống phanh; bản ghi mock chưa kết luận đạt hoặc "
            "không đạt."
        ),
        "tire_check": (
            "Kiểm tra lốp và tình trạng hao mòn; bản ghi mock không tạo số đo "
            "độ mòn."
        ),
    }
    if any(kind not in maintenance_descriptions for kind in maintenance_types):
        raise ValueError("unknown maintenance type in operational mock config")
    for driver_index, driver in enumerate(drivers):
        driver_id = driver["id"]
        vehicle_id = driver_vehicle[driver_id]
        driver_times = driver_trip_times[driver_id]
        event_time = _utc(
            (min(driver_times) if driver_times else assignment_fallback)
            - timedelta(days=config["generation"]["maintenance_offset_days"])
        )
        maintenance_id = _id("maintenance", vehicle_id)
        maintenance_type = maintenance_types[driver_index % len(maintenance_types)]
        vehicle_name = nodes[("Vehicle", vehicle_id)]["props"]["name"]
        maintenance_name = (
            f"{maintenance_type} — {vehicle_name}"
            if is_v3_family
            else f"Kiểm tra định kỳ {vehicle_name}"
        )
        maintenance_description = (
            f"Sự kiện mock cho {vehicle_name}. "
            f"{maintenance_descriptions[maintenance_type]}"
            if is_v3_family
            else "Sự kiện bảo dưỡng định kỳ tổng hợp, không đại diện dữ liệu GSM thật"
        )
        add_node(
            _node(
                "MaintenanceEvent",
                maintenance_id,
                {
                    "name": maintenance_name,
                    "description": maintenance_description,
                    "event_time": event_time,
                    "status": "completed",
                    "maintenance_type": maintenance_type,
                    "source_kind": "synthetic_extension",
                    "ingestion_time": logical_ingestion_time,
                },
            )
        )
        add_edge(
            _edge(
                "UNDERWENT",
                "Vehicle",
                vehicle_id,
                "MaintenanceEvent",
                maintenance_id,
                f"vehicle-maintenance:{maintenance_id}",
                {
                    "event_time": event_time,
                    "known_from": (
                        event_time if is_mvp_v03 else logical_ingestion_time
                    ),
                    "ingestion_time": logical_ingestion_time,
                    "source_kind": "synthetic_extension",
                },
            )
        )

    # Reviewed policy graph from public source text only.
    catalog = {row["snapshot_id"]: row for row in _jsonl(release / "public" / "documents" / "catalog.jsonl")}
    configured_clause_ids = {
        clause_id for rule in config["policy_rules"] for clause_id in rule["clause_ids"]
    }
    clause_to_document: dict[str, str] = {}
    policy_known_from: dict[str, str] = {}
    for snapshot_id in sorted({rule["document_snapshot_id"] for rule in config["policy_rules"]}):
        document = catalog[snapshot_id]
        if document.get("review_state") != "audited":
            raise ValueError(f"policy document is not audited: {snapshot_id}")
        document_id = document["document_revision_id"]
        policy_known_from[document_id] = document["dataset_release_at"]
        text = (release / "public" / "documents" / "normalized" / f"{document_id}.md").read_text("utf-8")
        add_node(
            _node(
                "PolicyDocument",
                document_id,
                {
                    "name": f"{document['alias']} — {Path(document['archive_member_path']).stem}",
                    "description": f"Tài liệu chính sách đã pin và rà soát {document['alias']}",
                    "source_locator": f"public/documents/normalized/{document_id}.md",
                    "content_sha256": document["normalized_sha256"],
                    "source_snapshot_id": snapshot_id,
                    "posted_date": document.get("posted_date"),
                    "known_from": (
                        document["dataset_release_at"] if is_mvp_v03 else None
                    ),
                    "source_kind": "reviewed_policy",
                    "ingestion_time": logical_ingestion_time,
                },
            )
        )
        for clause in document["clauses"]:
            clause_id = clause["clause_id"]
            if clause_id not in configured_clause_ids:
                continue
            clause_text = text[clause["span_start"] : clause["span_end"]]
            # Frozen clause hashes use the repository's canonical JSON
            # serialization, not the raw UTF-8 bytes of the substring.
            if _sha256(canonical_bytes(clause_text)) != clause["content_sha256"]:
                raise ValueError(f"policy clause hash mismatch: {clause_id}")
            clause_to_document[clause_id] = document_id
            clause_props = {
                "name": f"Điều khoản {clause_id}",
                "description": (
                    f"Đoạn TEXT đã rà soát trong {document['alias']}, "
                    f"dòng {clause['line']}"
                ),
                "document_id": document_id,
                "source_locator": (
                    f"unicode:[{clause['span_start']},{clause['span_end']})"
                ),
                "content_sha256": clause["content_sha256"],
                "known_from": (
                    document["dataset_release_at"] if is_mvp_v03 else None
                ),
                "source_kind": "reviewed_policy",
                "ingestion_time": logical_ingestion_time,
            }
            if not is_v3_family:
                clause_props["text"] = clause_text
            add_node(_node("PolicyClause", clause_id, clause_props))
            add_edge(
                _edge(
                    "CONTAINS",
                    "PolicyDocument",
                    document_id,
                    "PolicyClause",
                    clause_id,
                    f"document-clause:{document_id}:{clause_id}",
                    {
                        "known_from": document["dataset_release_at"],
                        "ingestion_time": logical_ingestion_time,
                        "source_kind": "reviewed_policy",
                    },
                )
            )
    if set(clause_to_document) != configured_clause_ids:
        raise ValueError("one or more configured policy clauses are not reviewed TEXT spans")

    policy_rules = {row["id"]: row for row in config["policy_rules"]}
    for rule in config["policy_rules"]:
        action = rule["action"]
        rule_known_from = (
            policy_known_from[
                catalog[rule["document_snapshot_id"]]["document_revision_id"]
            ]
            if is_mvp_v03
            else None
        )
        rule_edge_known_from = rule_known_from or logical_ingestion_time
        add_node(
            _node(
                "PolicyAction",
                action["id"],
                {
                    "name": action["name"],
                    "description": action["description"],
                    "action_type": action["action_type"],
                    "formula": action.get("formula"),
                    "known_from": rule_known_from,
                    "review_status": "reviewed_from_pinned_text",
                    "source_kind": "reviewed_policy",
                    "ingestion_time": logical_ingestion_time,
                },
            )
        )
        add_node(
            _node(
                "PolicyRule",
                rule["id"],
                {
                    "name": rule["name"],
                    "description": rule["description"],
                    "review_status": "reviewed_from_pinned_text",
                    "rule_version": "1",
                    "metric": rule.get("metric"),
                    "operator": rule.get("operator"),
                    "threshold": rule.get("threshold"),
                    "threshold_type": rule.get("threshold_type"),
                    "unit": rule.get("unit"),
                    "required_program": rule.get("required_program"),
                    "requires_operating_day": rule.get("requires_operating_day", False),
                    "effective_from": rule.get("effective_from"),
                    "known_from": rule_known_from,
                    "evaluation_enabled": rule["evaluation_enabled"],
                    "source_snapshot_id": rule["document_snapshot_id"],
                    "source_kind": "reviewed_policy",
                    "ingestion_time": logical_ingestion_time,
                },
            )
        )
        for clause_id in rule["clause_ids"]:
            add_edge(
                _edge(
                    "DEFINED_IN",
                    "PolicyRule",
                    rule["id"],
                    "PolicyClause",
                    clause_id,
                    f"rule-clause:{rule['id']}:{clause_id}",
                    {
                        "known_from": rule_edge_known_from,
                        "ingestion_time": logical_ingestion_time,
                        "source_kind": "reviewed_policy",
                    },
                )
            )
        add_edge(
            _edge(
                "HAS_ACTION",
                "PolicyRule",
                rule["id"],
                "PolicyAction",
                action["id"],
                f"rule-action:{rule['id']}:{action['id']}",
                {
                    "known_from": rule_edge_known_from,
                    "ingestion_time": logical_ingestion_time,
                    "source_kind": "reviewed_policy",
                },
            )
        )
        scope_targets: list[tuple[str, str]] = []
        if rule.get("required_region_id"):
            scope_targets.append(("Region", rule["required_region_id"]))
        if rule.get("required_program"):
            scope_targets.append(("VehicleType", type_ids[rule["required_program"]]))
        scope_targets.extend(("Fleet", fleet_id) for fleet_id in rule.get("scope_fleet_ids", []))
        for label, target_id in scope_targets:
            add_edge(
                _edge(
                    "APPLIES_TO",
                    "PolicyRule",
                    rule["id"],
                    label,
                    target_id,
                    f"rule-scope:{rule['id']}:{label}:{target_id}",
                    {
                        "valid_from": rule.get("effective_from"),
                        "known_from": rule_edge_known_from,
                        "ingestion_time": logical_ingestion_time,
                        "source_kind": "reviewed_policy",
                    },
                )
            )

    # Deterministic findings and decisions from accepted public measurements.
    accepted_measurements: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    opdays: dict[tuple[str, str, str], bool] = {}
    accepted_program_edges: list[tuple[dict[str, Any], str]] = []
    accepted_region_edges: list[dict[str, Any]] = []
    for edge in base_edges:
        if (
            edge["props"].get("resolution_status") == "accepted"
            and edge["props"].get("known_to") is None
        ):
            if edge["type"] == "HAS_STATE":
                state = base_nodes[("StateObservation", edge["end_id"])]["props"]
                if state.get("state_kind") == "driver_program":
                    accepted_program_edges.append((edge, state["value"]))
            elif edge["type"] == "OPERATES_IN":
                accepted_region_edges.append(edge)
        if edge["type"] != "HAS_MEASUREMENT" or edge["props"].get("resolution_status") != "accepted" or edge["props"].get("known_to") is not None:
            continue
        measurement = base_nodes[("Measurement", edge["end_id"])]["props"]
        item = (edge["start_id"], measurement, edge)
        accepted_measurements.append(item)
        if measurement["definition_id"] == "RM_OPDAY" and measurement["value"] in {"true", "false"}:
            opdays[(edge["start_id"], measurement["window_start"], measurement["window_end"])] = measurement["value"] == "true"

    for rule in config["policy_rules"]:
        if not rule["evaluation_enabled"]:
            continue
        threshold = _fraction(rule["threshold"])
        for driver_id, measurement, source_edge in accepted_measurements:
            if measurement["definition_id"] != rule["metric"] or measurement["value"] == "undefined":
                continue
            window_start = measurement["window_start"]
            window_end = measurement["window_end"]
            if rule.get("effective_from") and _parse_time(window_start) < _parse_time(rule["effective_from"]):
                continue
            if rule.get("required_program") and not any(
                edge["start_id"] == driver_id
                and program == rule["required_program"]
                and _covers_window(edge["props"], window_start, window_end)
                for edge, program in accepted_program_edges
            ):
                continue
            if rule.get("required_region_id") and not any(
                edge["start_id"] == driver_id
                and edge["end_id"] == rule["required_region_id"]
                and _covers_window(edge["props"], window_start, window_end)
                for edge in accepted_region_edges
            ):
                continue
            window_key = (driver_id, window_start, window_end)
            if rule.get("requires_operating_day") and opdays.get(window_key) is not True:
                continue
            observed = _fraction(measurement["value"])
            triggered = observed < threshold if rule["operator"] == "lt" else observed > threshold
            if not triggered:
                continue
            finding_id = _id("finding", f"{rule['id']}:{measurement['id']}")
            add_node(
                _node(
                    "ViolationFinding",
                    finding_id,
                    {
                        "name": f"Kết quả {rule['name']} — {base_nodes[('Driver', driver_id)]['props']['name']}",
                        "description": f"Điều kiện {measurement['value']} {rule['operator']} {rule['threshold']} được kích hoạt từ số liệu công khai",
                        "status": "triggered",
                        "evaluation_version": "operational-mock-evaluator-v1",
                        "observed_value": measurement["value"],
                        "threshold": rule["threshold"],
                        "window_start": measurement["window_start"],
                        "window_end": measurement["window_end"],
                        "source_kind": "derived",
                        "ingestion_time": logical_ingestion_time,
                    },
                )
            )
            decision_id = _id("decision", finding_id)
            amount = None
            if rule["id"] == "policy-rule:min-daily-revenue:v1":
                amount = str((threshold - observed) / 5)
            add_node(
                _node(
                    "EnforcementDecision",
                    decision_id,
                    {
                        "name": (
                            f"Quyết định theo kết quả {finding_id[:8]}"
                            if is_mvp_v03
                            else f"Quyết định mock cho {finding_id[:8]}"
                        ),
                        "description": (
                            "Quyết định dẫn xuất từ số liệu và quy tắc đã duyệt; chỉ phục vụ kiểm thử kỹ thuật."
                            if is_mvp_v03
                            else "Quyết định tổng hợp phục vụ kiểm thử đường bằng chứng; không phải quyết định GSM thật"
                        ),
                        "status": "applied" if is_mvp_v03 else "mock_applied",
                        "effective_at": measurement["window_end"],
                        "computed_amount": amount,
                        "source_kind": "derived",
                        "ingestion_time": logical_ingestion_time,
                    },
                )
            )
            common = {
                "known_from": logical_ingestion_time,
                "ingestion_time": logical_ingestion_time,
                "source_kind": "derived",
            }
            add_edge(_edge("HAS_FINDING", "Driver", driver_id, "ViolationFinding", finding_id, f"driver-finding:{finding_id}", common))
            add_edge(_edge("EVALUATED_AGAINST", "ViolationFinding", finding_id, "PolicyRule", rule["id"], f"finding-rule:{finding_id}", common))
            add_edge(_edge("SUPPORTED_BY", "ViolationFinding", finding_id, "Measurement", measurement["id"], f"finding-measurement:{finding_id}:{measurement['id']}", {**common, "source_assertion_id": source_edge["props"]["evidence_ref"]}))
            add_edge(_edge("RECEIVED_DECISION", "Driver", driver_id, "EnforcementDecision", decision_id, f"driver-decision:{decision_id}", common))
            add_edge(_edge("BASED_ON", "EnforcementDecision", decision_id, "ViolationFinding", finding_id, f"decision-finding:{decision_id}", common))
            add_edge(_edge("APPLIES_ACTION", "EnforcementDecision", decision_id, "PolicyAction", rule["action"]["id"], f"decision-action:{decision_id}", common))

    # Summaries reduce wide operational questions without replacing raw evidence.
    pilot_window_start = min(row["props"]["event_time"] for row in trips)
    pilot_window_end = max(row["props"]["event_time"] for row in trips)

    def summary_props(name: str, description: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        ordered = sorted(rows, key=lambda row: row["props"]["event_time"])
        completed = sum(row["props"]["outcome"] == "completed" for row in ordered)
        cancelled = sum(row["props"]["outcome"].startswith("cancelled") for row in ordered)
        return {
            "name": name,
            "description": description,
            "derivation_version": "trip-summary-v1",
            "window_start": (
                ordered[0]["props"]["event_time"] if ordered else pilot_window_start
            ),
            "window_end": (
                ordered[-1]["props"]["event_time"] if ordered else pilot_window_end
            ),
            "trip_count": len(ordered),
            "completed_count": completed,
            "cancelled_count": cancelled,
            "cancel_rate_numerator": cancelled,
            "cancel_rate_denominator": len(ordered),
            "support_trip_ids": [row["id"] for row in ordered],
            "source_kind": "derived",
            "ingestion_time": logical_ingestion_time,
        }

    trips_by_driver: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trip in trips:
        trips_by_driver[performed[trip["id"]]].append(trip)
    for driver in (drivers if materialize_summaries else ()):
        summary_id = _id("driver-summary", driver["id"])
        add_node(_node("DriverSummary", summary_id, summary_props(f"Tóm tắt {driver['props']['name']}", f"Tóm tắt 80-trip pilot cho {driver['props']['name']}", trips_by_driver[driver["id"]])))
        add_edge(_edge("HAS_SUMMARY", "Driver", driver["id"], "DriverSummary", summary_id, f"driver-summary:{driver['id']}", {"known_from": logical_ingestion_time, "ingestion_time": logical_ingestion_time, "source_kind": "derived"}))

    trips_by_fleet: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for driver_id, rows in trips_by_driver.items():
        for fleet_id in current_fleets.get(driver_id, set()):
            trips_by_fleet[fleet_id].extend(rows)
    for fleet in sorted(
        (
            row
            for row in baseline.nodes
            if materialize_summaries and row["label"] == "Fleet"
        ),
        key=lambda row: row["id"],
    ):
        rows = trips_by_fleet[fleet["id"]]
        if not rows:
            continue
        summary_id = _id("fleet-summary", fleet["id"])
        add_node(_node("FleetSummary", summary_id, summary_props(f"Tóm tắt {fleet['props']['name']}", f"Tóm tắt chuyến của tài xế hiện thuộc {fleet['props']['name']}", rows)))
        add_edge(_edge("HAS_SUMMARY", "Fleet", fleet["id"], "FleetSummary", summary_id, f"fleet-summary:{fleet['id']}", {"known_from": logical_ingestion_time, "ingestion_time": logical_ingestion_time, "source_kind": "derived"}))

    trips_by_zone: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trip in trips:
        trips_by_zone[trip_zones[trip["id"]][0]].append(trip)
    for region_zones in (
        zones_by_region.values() if materialize_summaries else ()
    ):
        for zone_id in region_zones:
            rows = trips_by_zone[zone_id]
            if not rows:
                continue
            summary_id = _id("zone-summary", zone_id)
            add_node(_node("ZoneSummary", summary_id, summary_props(f"Tóm tắt {nodes[('Zone', zone_id)]['props']['name']}", "Tóm tắt chuyến theo vùng đón mock", rows)))
            add_edge(_edge("HAS_SUMMARY", "Zone", zone_id, "ZoneSummary", summary_id, f"zone-summary:{zone_id}", {"known_from": logical_ingestion_time, "ingestion_time": logical_ingestion_time, "source_kind": "derived"}))

    for (_, _), rows in sorted(shift_trips.items()):
        shift_id = trip_shift[rows[0]["id"]]
        summary_id = _id("shift-summary", shift_id)
        add_node(_node("ShiftSummary", summary_id, summary_props(f"Tóm tắt {nodes[('Shift', shift_id)]['props']['name']}", "Tóm tắt chuyến trong ca mock", rows)))
        add_edge(_edge("HAS_SUMMARY", "Shift", shift_id, "ShiftSummary", summary_id, f"shift-summary:{shift_id}", {"known_from": logical_ingestion_time, "ingestion_time": logical_ingestion_time, "source_kind": "derived"}))

    if is_v3_family:
        excluded_labels = {
            "DriverSummary",
            "FleetSummary",
            "Shift",
            "ShiftSummary",
            "ZoneSummary",
        }
        excluded_relationships = {
            "CONTAINS_TRIP",
            "HAS_SUMMARY",
            "OPERATED_IN",
            "WORKED_SHIFT",
        }
        nodes = {
            key: row for key, row in nodes.items() if row["label"] not in excluded_labels
        }
        edges = {
            edge_id: row
            for edge_id, row in edges.items()
            if row["type"] not in excluded_relationships
            and row["start_label"] not in excluded_labels
            and row["end_label"] not in excluded_labels
        }

        # Make the public projection readable without inventing new facts.
        for key, row in list(nodes.items()):
            props = dict(row["props"])
            label = row["label"]
            if is_mvp_v03 and props.get("source_kind") in {
                "synthetic_extension",
                "derived",
            }:
                for text_field in ("name", "description"):
                    if text_field in props:
                        props[text_field] = re.sub(
                            r"\bmock\b", "", str(props[text_field]), flags=re.IGNORECASE
                        )
                        props[text_field] = re.sub(r"\s+", " ", props[text_field]).strip()
            if props.get("source_kind") != "frozen_projection":
                nodes[key] = {**row, "props": props}
                continue
            if label == "Driver":
                props["description"] = (
                    f"Hồ sơ tài xế tổng hợp {props['name']}; chương trình công khai "
                    f"hiện thấy trong snapshot là {programs[row['id']]} ."
                ).replace(" .", ".")
            elif label == "Trip":
                driver_name = base_nodes[("Driver", performed[row["id"]])]["props"]["name"]
                props["description"] = (
                    f"{props['name']} của {driver_name} có kết quả terminal "
                    f"{props['outcome']} lúc {props['event_time']}."
                )
            elif label == "Fleet":
                props["description"] = f"Đội xe hoặc depot tổng hợp {props['name']}."
            elif label == "Region":
                props["description"] = f"Khu vực vận hành tổng hợp {props['name']}."
            elif label == "Service":
                props["description"] = f"Dịch vụ tổng hợp {props['name']}."
            elif label == "Incident":
                props["description"] = (
                    f"{props['name']} là sự cố frozen chỉ có danh tính và lịch sử "
                    "trạng thái; nguồn không mô tả loại, nguyên nhân hoặc Trip liên quan."
                )
            elif label == "Measurement":
                props["description"] = (
                    f"Số liệu {props['definition_id']} có giá trị {props['value']} "
                    f"{props['unit']} trong cửa sổ {props['window_start']} đến "
                    f"{props['window_end']}."
                )
            elif label == "StateObservation":
                if is_mvp_v03 and props.get("state_kind") in {
                    "driver_program",
                    "driver_status",
                }:
                    owner_edges = [
                        edge
                        for edge in edges.values()
                        if edge["type"] == "HAS_STATE"
                        and edge["end_id"] == row["id"]
                        and edge["start_label"] == "Driver"
                    ]
                    if len(owner_edges) != 1:
                        raise ValueError(
                            f"driver state must have exactly one owner: {row['id']}"
                        )
                    owner_edge = owner_edges[0]
                    driver_name = nodes[("Driver", owner_edge["start_id"])]["props"][
                        "name"
                    ]
                    valid_from = owner_edge["props"].get("valid_from")
                    valid_to = owner_edge["props"].get("valid_to")
                    known_from = owner_edge["props"].get("known_from")
                    known_to = owner_edge["props"].get("known_to")
                    interval = f"từ {valid_from}"
                    if valid_to:
                        interval += f" đến trước {valid_to}"
                    if props["state_kind"] == "driver_program":
                        props["name"] = (
                            f"Chương trình vận hành {props['value']} của {driver_name}"
                        )
                        meaning = (
                            "Đây là nhóm chương trình vận hành của tài xế, "
                            "không phải loại phương tiện."
                        )
                    else:
                        props["name"] = (
                            f"Trạng thái {props['value']} của {driver_name}"
                        )
                        meaning = "Đây là trạng thái hoạt động của tài xế."
                    visibility = f"Nguồn được biết từ {known_from}"
                    if known_to:
                        visibility += f" đến trước {known_to}"
                    props["description"] = (
                        f"{meaning} Giá trị {props['value']} có hiệu lực {interval}. "
                        f"{visibility}."
                    )
                else:
                    props["description"] = (
                        f"Quan sát trạng thái {props['state_kind']} có giá trị "
                        f"{props['value']}."
                    )
            nodes[key] = {**row, "props": props}

    if is_mvp_v03:
        nodes, edges = _apply_operational_snapshot_visibility(
            nodes, edges, snapshots
        )

    node_rows = tuple(sorted(nodes.values(), key=lambda row: (row["label"], row["id"])))
    edge_rows = tuple(sorted(edges.values(), key=lambda row: (row["type"], row["id"])))
    logical_payload = {"nodes": node_rows, "edges": edge_rows}
    if snapshots:
        logical_payload["snapshots"] = snapshots
    digest = _sha256(canonical_bytes(logical_payload))
    dataset = OperationalMockDataset(
        dataset_version=config["dataset_version"],
        source_release=release.name,
        source_snapshot_id=source_snapshot_id,
        seed=config["seed"],
        logical_digest=digest,
        nodes=node_rows,
        edges=edge_rows,
        snapshots=snapshots,
    )
    report = validate_operational_mock(dataset, contract_path=contract_path)
    if report["status"] != "pass":
        raise ValueError(f"generated operational mock is invalid: {report['errors']}")
    return dataset


def validate_operational_mock(
    dataset: OperationalMockDataset,
    *,
    contract_path: Path = Path("configs/benchmark/operational-kg-v2.json"),
) -> dict[str, Any]:
    contract = OperationalKGv2Contract.load(contract_path)
    node_specs = {row.name: row for row in contract.nodes}
    rel_specs = {row.name: row for row in contract.relationships}
    errors: list[str] = []
    nodes = {(row["label"], row["id"]): row for row in dataset.nodes}
    if len(nodes) != len(dataset.nodes):
        errors.append("duplicate_node_key")
    edge_ids = {row["id"] for row in dataset.edges}
    if len(edge_ids) != len(dataset.edges):
        errors.append("duplicate_edge_id")
    timestamp_keys = {
        "effective_at",
        "effective_from",
        "end_time",
        "event_time",
        "ingestion_time",
        "known_from",
        "known_to",
        "start_time",
        "valid_from",
        "valid_to",
        "window_end",
        "window_start",
    }

    def check_times(kind: str, identity: str, props: dict[str, Any]) -> None:
        for key in timestamp_keys & props.keys():
            value = props[key]
            if value is None:
                continue
            try:
                _parse_time(str(value))
            except ValueError:
                errors.append(f"invalid_time:{kind}:{identity}:{key}")
        for start_key, end_key in (
            ("start_time", "end_time"),
            ("window_start", "window_end"),
            ("valid_from", "valid_to"),
            ("known_from", "known_to"),
        ):
            if props.get(start_key) and props.get(end_key):
                if _parse_time(props[start_key]) > _parse_time(props[end_key]):
                    errors.append(
                        f"reversed_interval:{kind}:{identity}:{start_key}:{end_key}"
                    )

    for row in dataset.nodes:
        spec = node_specs.get(row["label"])
        if spec is None:
            errors.append(f"unknown_node_label:{row['label']}")
            continue
        missing = set(spec.required_properties) - row["props"].keys()
        if missing:
            errors.append(f"missing_node_properties:{row['label']}:{row['id']}:{sorted(missing)}")
        source_kind = row["props"].get("source_kind")
        if source_kind not in spec.allowed_origins:
            errors.append(f"source_kind_mismatch:{row['label']}:{row['id']}")
        if source_kind in {"synthetic_extension", "derived"}:
            try:
                if uuid.UUID(row["id"]).version != 5:
                    raise ValueError
            except (ValueError, AttributeError):
                errors.append(f"non_uuid5_generated_id:{row['label']}:{row['id']}")
        if source_kind != "frozen_projection" and "ingestion_time" not in row["props"]:
            errors.append(f"missing_ingestion_time:{row['label']}:{row['id']}")
        if row["label"] == "PolicyClause":
            digest = row["props"].get("content_sha256", "")
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                errors.append(f"invalid_clause_hash:{row['id']}")
        check_times("node", row["id"], row["props"])
    for row in dataset.edges:
        spec = rel_specs.get(row["type"])
        if spec is None:
            errors.append(f"unknown_relationship:{row['type']}")
            continue
        if row["start_label"] not in spec.start_types or row["end_label"] not in spec.end_types:
            errors.append(f"invalid_relationship_endpoint:{row['type']}:{row['id']}")
        if (row["start_label"], row["start_id"]) not in nodes or (row["end_label"], row["end_id"]) not in nodes:
            errors.append(f"missing_relationship_endpoint:{row['type']}:{row['id']}")
        if "ingestion_time" not in row["props"]:
            errors.append(f"missing_ingestion_time:{row['id']}")
        try:
            if uuid.UUID(row["id"]).version != 5:
                raise ValueError
        except (ValueError, AttributeError):
            errors.append(f"non_uuid5_edge_id:{row['id']}")
        check_times("edge", row["id"], row["props"])

    counts = dataset.counts["node_labels"]
    for label, expected in {"Driver": 8, "Trip": 80, "Vehicle": 8, "VehicleType": 2, "Zone": 4}.items():
        if counts.get(label) != expected:
            errors.append(f"count_mismatch:{label}:{counts.get(label)}:{expected}")
    for rel_type, expected in {"PERFORMED": 80, "CONTAINS_TRIP": 80, "PICKUP_IN": 80, "DROPOFF_IN": 80, "OPERATED": 8}.items():
        if rel_type not in rel_specs:
            continue
        actual = dataset.counts["relationship_types"].get(rel_type)
        if actual != expected:
            errors.append(f"count_mismatch:{rel_type}:{actual}:{expected}")
    if contract.contract_version in {
        "gsm-operational-kg-v3-draft-1",
        "gsm-operational-kg-v3-draft-2",
    }:
        expected_nodes = 201 if dataset.dataset_version == "gsm-operational-mock-v0.3" else 198
        expected_edges = 582 if dataset.dataset_version == "gsm-operational-mock-v0.3" else 579
        if dataset.counts["nodes"] != expected_nodes:
            errors.append(
                f"count_mismatch:nodes:{dataset.counts['nodes']}:{expected_nodes}"
            )
        if dataset.counts["edges"] != expected_edges:
            errors.append(
                f"count_mismatch:edges:{dataset.counts['edges']}:{expected_edges}"
            )
        forbidden_labels = {
            "DriverSummary",
            "FleetSummary",
            "Shift",
            "ShiftSummary",
            "ZoneSummary",
        }
        leaked_labels = forbidden_labels & set(dataset.counts["node_labels"])
        if leaked_labels:
            errors.append(f"deprecated_node_labels:{sorted(leaked_labels)}")
        if "HAS_SUMMARY" in dataset.counts["relationship_types"]:
            errors.append("deprecated_relationship:HAS_SUMMARY")
    serialized = canonical_bytes({"nodes": dataset.nodes, "edges": dataset.edges})
    if b"private/" in serialized or b"task_binding" in serialized or b'"task_id"' in serialized:
        errors.append("private_evaluation_leakage")
    if dataset.dataset_version == "gsm-operational-mock-v0.3":
        if len(dataset.snapshots) != 12:
            errors.append(f"snapshot_count_mismatch:{len(dataset.snapshots)}:12")
        snapshot_ids = [row.get("snapshot_id") for row in dataset.snapshots]
        if len(snapshot_ids) != len(set(snapshot_ids)):
            errors.append("duplicate_snapshot_id")
        required_snapshot_fields = {
            "snapshot_id",
            "timeline_id",
            "source_ledger_id",
            "sequence",
            "known_as_of",
            "name",
        }
        previous_cutoff: datetime | None = None
        for expected_sequence, row in enumerate(dataset.snapshots, 1):
            if set(row) != required_snapshot_fields:
                errors.append(f"invalid_snapshot_context:{row.get('snapshot_id')}")
            else:
                try:
                    cutoff = _parse_time(row["known_as_of"])
                    if previous_cutoff is not None and cutoff <= previous_cutoff:
                        errors.append("non_monotonic_snapshot_cutoff")
                    previous_cutoff = cutoff
                except ValueError:
                    errors.append(f"invalid_snapshot_time:{row['snapshot_id']}")
                if row["timeline_id"] != "L0":
                    errors.append(f"invalid_snapshot_timeline:{row['snapshot_id']}")
                if row["sequence"] != expected_sequence:
                    errors.append(f"invalid_snapshot_sequence:{row['snapshot_id']}")
        declared_snapshot_ids = set(snapshot_ids)
        for row in (*dataset.nodes, *dataset.edges):
            visibility = row["props"].get("visibility_snapshot_ids")
            if not isinstance(visibility, list) or not visibility:
                errors.append(f"missing_snapshot_visibility:{row['id']}")
            elif not set(visibility) <= declared_snapshot_ids:
                errors.append(f"unknown_snapshot_visibility:{row['id']}")
    logical_payload = {"nodes": dataset.nodes, "edges": dataset.edges}
    if dataset.snapshots:
        logical_payload["snapshots"] = dataset.snapshots
    recomputed = _sha256(canonical_bytes(logical_payload))
    if recomputed != dataset.logical_digest:
        errors.append("logical_digest_mismatch")
    return {
        "schema_version": "gsm-operational-mock-validation-v1",
        "status": "pass" if not errors else "fail",
        "dataset_version": dataset.dataset_version,
        "logical_digest": dataset.logical_digest,
        "counts": dataset.counts,
        "errors": errors,
    }


def materialize_operational_mock(
    dataset: OperationalMockDataset,
    output: Path,
    *,
    contract_path: Path = Path("configs/benchmark/operational-kg-v2.json"),
) -> dict[str, Any]:
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty candidate: {output}")
    output.mkdir(parents=True, exist_ok=True)
    nodes_path = output / "nodes.jsonl"
    edges_path = output / "edges.jsonl"
    nodes_path.write_bytes(b"".join(canonical_bytes(row) + b"\n" for row in dataset.nodes))
    edges_path.write_bytes(b"".join(canonical_bytes(row) + b"\n" for row in dataset.edges))
    material_paths = [nodes_path, edges_path]
    if dataset.snapshots:
        snapshots_path = output / "snapshots.jsonl"
        snapshots_path.write_bytes(
            b"".join(canonical_bytes(row) + b"\n" for row in dataset.snapshots)
        )
        material_paths.append(snapshots_path)
    validation = validate_operational_mock(dataset, contract_path=contract_path)
    validation_path = output / "validation.json"
    validation_path.write_bytes(canonical_bytes(validation) + b"\n")
    files = {
        path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path.read_bytes())}
        for path in (*material_paths, validation_path)
    }
    manifest = {
        "schema_version": dataset.dataset_version,
        "state": "CANDIDATE",
        "dataset_version": dataset.dataset_version,
        "source_release": dataset.source_release,
        "source_snapshot_id": dataset.source_snapshot_id,
        "snapshot_count": len(dataset.snapshots),
        "seed": dataset.seed,
        "logical_digest": dataset.logical_digest,
        "counts": dataset.counts,
        "files": files,
    }
    (output / "manifest.json").write_bytes(canonical_bytes(manifest) + b"\n")
    return manifest


def load_operational_mock(path: Path) -> OperationalMockDataset:
    path = path.resolve()
    manifest = json.loads((path / "manifest.json").read_text("utf-8"))
    nodes = tuple(_jsonl(path / "nodes.jsonl"))
    edges = tuple(_jsonl(path / "edges.jsonl"))
    snapshots_path = path / "snapshots.jsonl"
    snapshots = tuple(_jsonl(snapshots_path)) if snapshots_path.is_file() else ()
    dataset = OperationalMockDataset(
        dataset_version=manifest["dataset_version"],
        source_release=manifest["source_release"],
        source_snapshot_id=manifest["source_snapshot_id"],
        seed=manifest["seed"],
        logical_digest=manifest["logical_digest"],
        nodes=nodes,
        edges=edges,
        snapshots=snapshots,
    )
    return dataset


def build_semantic_node_inputs(
    dataset: OperationalMockDataset,
) -> tuple[dict[str, Any], ...]:
    """Build reviewed text inputs for the small operational-node semantic index.

    This function deliberately does not call an embedding provider and does not
    place vectors in Neo4j.  It selects only free-text occurrence nodes whose
    descriptions carry useful semantics.  Identity, status, category and time
    remain structured filters rather than being concatenated into prose.
    """

    if dataset.dataset_version not in {
        "gsm-operational-mock-v0.2",
        "gsm-operational-mock-v0.3",
    }:
        raise ValueError("semantic node inputs are defined only for mock v0.2/v0.3")
    selected: list[dict[str, Any]] = []
    for row in dataset.nodes:
        label = row["label"]
        props = row["props"]
        if label not in {"Complaint", "Incident"}:
            continue
        if props.get("source_kind") != "synthetic_extension":
            continue
        text = str(props["description"]).strip()
        if not text:
            raise ValueError(f"empty semantic text: {label}/{row['id']}")
        selected.append(
            {
                "node_id": row["id"],
                "node_type": label,
                "text": text,
                "content_sha256": _sha256(text.encode("utf-8")),
                "filters": {
                    key: props[key]
                    for key in (
                        "category",
                        "event_time",
                        "incident_type",
                        "maintenance_type",
                        "status",
                    )
                    if key in props
                },
            }
        )
    selected.sort(key=lambda item: (item["node_type"], item["node_id"]))
    counts = Counter(item["node_type"] for item in selected)
    if counts != {"Complaint": 11, "Incident": 4}:
        raise ValueError(f"unexpected semantic node population: {dict(counts)}")
    return tuple(selected)


def verify_operational_mock_candidate(
    path: Path,
    *,
    contract_path: Path = Path("configs/benchmark/operational-kg-v2.json"),
) -> dict[str, Any]:
    """Verify a materialized candidate without modifying it."""

    path = path.resolve()
    errors: list[str] = []
    manifest_path = path / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text("utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        return {
            "schema_version": "gsm-operational-mock-candidate-verification-v1",
            "status": "fail",
            "candidate": str(path),
            "errors": [f"invalid_manifest:{error}"],
        }

    if (
        manifest.get("schema_version") != manifest.get("dataset_version")
        or manifest.get("schema_version") not in SUPPORTED_DATASET_VERSIONS
    ):
        errors.append("schema_version_mismatch")
    if manifest.get("state") != "CANDIDATE":
        errors.append("state_mismatch")
    if manifest.get("source_release") != "gsm-dev-core-0.2.2":
        errors.append("source_release_mismatch")

    declared_files = manifest.get("files") or {}
    expected_files = {"nodes.jsonl", "edges.jsonl", "validation.json"}
    if manifest.get("snapshot_count"):
        expected_files.add("snapshots.jsonl")
    if set(declared_files) != expected_files:
        errors.append("file_inventory_mismatch")
    for name in sorted(expected_files):
        file_path = path / name
        if not file_path.is_file():
            errors.append(f"missing_file:{name}")
            continue
        declared = declared_files.get(name) or {}
        if file_path.stat().st_size != declared.get("bytes"):
            errors.append(f"byte_count_mismatch:{name}")
        if _sha256(file_path.read_bytes()) != declared.get("sha256"):
            errors.append(f"sha256_mismatch:{name}")

    material_files = {
        child.name for child in path.iterdir() if child.is_file()
    }
    unexpected = sorted(material_files - expected_files - {"manifest.json"})
    errors.extend(f"unexpected_file:{name}" for name in unexpected)

    validation: dict[str, Any] | None = None
    if not any(error.startswith("missing_file:") for error in errors):
        try:
            dataset = load_operational_mock(path)
            validation = validate_operational_mock(dataset, contract_path=contract_path)
            if validation["status"] != "pass":
                errors.extend(f"dataset:{error}" for error in validation["errors"])
            if dataset.logical_digest != manifest.get("logical_digest"):
                errors.append("manifest_logical_digest_mismatch")
            if dataset.counts != manifest.get("counts"):
                errors.append("manifest_counts_mismatch")
            stored_validation = json.loads((path / "validation.json").read_text("utf-8"))
            if stored_validation != validation:
                errors.append("validation_report_mismatch")
        except (KeyError, ValueError, json.JSONDecodeError) as error:
            errors.append(f"candidate_content_error:{error}")

    return {
        "schema_version": "gsm-operational-mock-candidate-verification-v1",
        "status": "pass" if not errors else "fail",
        "candidate": str(path),
        "logical_digest": manifest.get("logical_digest"),
        "counts": manifest.get("counts"),
        "validation": validation,
        "errors": errors,
    }


def compare_operational_mock_candidates(first: Path, second: Path) -> dict[str, Any]:
    a = load_operational_mock(first)
    b = load_operational_mock(second)
    mismatches: list[str] = []
    if a.logical_digest != b.logical_digest:
        mismatches.append("logical_digest")
    if a.nodes != b.nodes:
        mismatches.append("nodes")
    if a.edges != b.edges:
        mismatches.append("edges")
    if a.snapshots != b.snapshots:
        mismatches.append("snapshots")
    return {
        "schema_version": "gsm-operational-mock-comparison-v1",
        "status": "pass" if not mismatches else "fail",
        "candidate_a": str(first),
        "candidate_b": str(second),
        "logical_digest": a.logical_digest if not mismatches else None,
        "mismatches": mismatches,
    }
