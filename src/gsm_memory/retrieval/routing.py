"""Public Snapshot Routing for Runtime Queries.

Enforces strict isolation and public-only provenance:
1. Public snapshot selection must only use public query metadata or public manifests.
2. Absolutely NEVER touches private/ directories (oracle, eval, cases, gold_support_links).
3. Absolutely NEVER inspects corpus roles (primary-gold, distractor).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


DEFAULT_PUBLIC_BASELINE_SNAPSHOT = "d4cc0438-d831-541a-8123-ddda94ccdac8"


class PublicRoutingViolationError(RuntimeError):
    """Raised when an attempt is made to use private paths or gold roles to route snapshots."""


class SnapshotNotFoundError(RuntimeError):
    """Raised when a public snapshot is requested but cannot be found in the public release."""


def validate_public_path_safety(path: Path | str) -> None:
    """Ensure a path does not reference private directories.
    
    Raises PublicRoutingViolationError if any component of the path points to 'private'.
    """
    resolved_str = str(path).replace("\\", "/").lower()
    parts = [p.strip("/") for p in resolved_str.split("/") if p.strip("/")]
    if "private" in parts:
        raise PublicRoutingViolationError(
            f"Routing security violation: access to private directory '{path}' is strictly prohibited."
        )


def resolve_public_snapshot_id(
    query: Mapping[str, Any],
    release_dir: Path | str | None = None,
) -> str:
    """Resolve the public snapshot ID for a runtime query.

    Resolution hierarchy (100% public, gold-blind):
    1. Direct `public_snapshot_id` from the query object.
    2. Route lookup in `public/runtime_manifest.json` by `query_id`.
    3. Public snapshot matching by `known_as_of` / `access_scope` via public snapshot manifests.
    4. Default canonical public baseline snapshot (`d4cc0438-d831-541a-8123-ddda94ccdac8`).

    Safety checks:
    - Rejects any private directory path.
    - If release_dir is provided, validates that the snapshot exists in `public/snapshots/<sid>`.
    """
    if release_dir is not None:
        validate_public_path_safety(release_dir)
        release_path = Path(release_dir)
    else:
        release_path = None

    # 1. Direct explicit snapshot ID
    candidate_id = query.get("public_snapshot_id")
    if candidate_id:
        sid = str(candidate_id)
        if release_path is not None:
            snap_dir = release_path / "public" / "snapshots" / sid
            validate_public_path_safety(snap_dir)
            if not snap_dir.is_dir() or not (snap_dir / "manifest.json").is_file():
                raise SnapshotNotFoundError(
                    f"Public snapshot '{sid}' not found or missing manifest in public snapshots: {snap_dir}"
                )
        return sid

    # 2. Public runtime manifest routing by query_id
    query_id = query.get("query_id")
    if query_id and release_path is not None:
        manifest_path = release_path / "public" / "runtime_manifest.json"
        if manifest_path.is_file():
            validate_public_path_safety(manifest_path)
            try:
                manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
                for route in manifest_data.get("query_routes", []):
                    if route.get("query_id") == query_id:
                        matched_sid = route.get("public_snapshot_id")
                        if matched_sid:
                            return matched_sid
            except Exception:
                pass

    # 3. Match from public snapshot manifests if metadata (known_as_of) is provided
    known_as_of = query.get("known_as_of")
    access_scope = query.get("access_scope")
    if release_path is not None and (known_as_of or access_scope):
        snapshots_root = release_path / "public" / "snapshots"
        if snapshots_root.is_dir():
            for snap_dir in sorted(snapshots_root.iterdir()):
                if not snap_dir.is_dir():
                    continue
                manifest_file = snap_dir / "manifest.json"
                if not manifest_file.is_file():
                    continue
                try:
                    s_manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                    time_match = (known_as_of is None) or (s_manifest.get("known_as_of") == known_as_of)
                    scope_match = (access_scope is None) or (s_manifest.get("scope_id") == access_scope)
                    if time_match and scope_match:
                        return snap_dir.name
                except Exception:
                    continue

    # 4. Default public baseline
    if release_path is not None:
        baseline_dir = release_path / "public" / "snapshots" / DEFAULT_PUBLIC_BASELINE_SNAPSHOT
        if baseline_dir.is_dir() and (baseline_dir / "manifest.json").is_file():
            return DEFAULT_PUBLIC_BASELINE_SNAPSHOT

    return DEFAULT_PUBLIC_BASELINE_SNAPSHOT
