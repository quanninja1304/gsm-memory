from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any

from .primitives import canonical_bytes, sha256_bytes, sha256_file
from .validation import semantic_inventory


MANIFEST_PATH = Path("private/eval/manifest.json")
VALIDATION_PATH = Path("private/eval/validation.json")


def _read_json(path: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"cannot read JSON {path}: {exc}")
        return None
    if not isinstance(value, dict):
        errors.append(f"expected JSON object: {path}")
        return None
    return value


def verify_frozen_release(
    release: Path,
    certificate_path: Path,
    comparison_path: Path,
) -> dict[str, Any]:
    """Verify a frozen release without writing or normalizing any artifact."""

    release = release.resolve()
    certificate_path = certificate_path.resolve()
    comparison_path = comparison_path.resolve()
    errors: list[str] = []
    missing: list[str] = []
    mismatched: list[dict[str, str]] = []
    unexpected: list[str] = []
    checked = 0

    manifest_path = release / MANIFEST_PATH
    validation_path = release / VALIDATION_PATH
    manifest = _read_json(manifest_path, errors)
    certificate = _read_json(certificate_path, errors)
    comparison = _read_json(comparison_path, errors)

    if manifest is None or certificate is None or comparison is None:
        return {
            "schema_version": "frozen-verification-v1",
            "status": "fail",
            "release": str(release),
            "checked": checked,
            "missing": missing,
            "mismatched": mismatched,
            "unexpected": unexpected,
            "implicated_paths": sorted({str(manifest_path), str(certificate_path), str(comparison_path)}),
            "errors": errors,
        }

    dataset_version = manifest.get("dataset_version")
    if manifest.get("state") != "FROZEN":
        errors.append(f"release state is not FROZEN: {manifest.get('state')!r}")
    if release.name != dataset_version:
        errors.append(f"release directory/version mismatch: {release.name!r} != {dataset_version!r}")
    if certificate.get("dataset_version") != dataset_version:
        errors.append("certificate dataset_version mismatch")
    if certificate.get("state") != "FROZEN":
        errors.append(f"certificate state is not FROZEN: {certificate.get('state')!r}")

    actual_manifest_hash = sha256_file(manifest_path) if manifest_path.is_file() else None
    if actual_manifest_hash != certificate.get("manifest_sha256"):
        mismatched.append({
            "path": str(manifest_path),
            "expected": str(certificate.get("manifest_sha256")),
            "actual": str(actual_manifest_hash),
        })

    actual_comparison_hash = sha256_file(comparison_path) if comparison_path.is_file() else None
    if actual_comparison_hash != certificate.get("comparison_report_sha256"):
        mismatched.append({
            "path": str(comparison_path),
            "expected": str(certificate.get("comparison_report_sha256")),
            "actual": str(actual_comparison_hash),
        })

    declared_logical_digests = {
        manifest.get("logical_inventory_digest"),
        certificate.get("logical_inventory_digest"),
        comparison.get("inventory_digest"),
    }
    if None in declared_logical_digests or len(declared_logical_digests) != 1:
        errors.append("logical inventory digest mismatch across manifest/certificate/comparison")
    actual_logical_digest = None
    try:
        actual_logical_digest = sha256_bytes(canonical_bytes(semantic_inventory(release)))
    except Exception as exc:  # Verification must report malformed JSON/Parquet, not repair or crash.
        errors.append(f"cannot compute logical inventory digest: {exc}")
    if actual_logical_digest != manifest.get("logical_inventory_digest"):
        errors.append("computed logical inventory digest does not match manifest")
    if comparison.get("status") != "pass" or comparison.get("mismatches") not in ([], None):
        errors.append("comparison report does not record a clean pass")

    inventory = manifest.get("file_inventory")
    if not isinstance(inventory, dict):
        errors.append("manifest file_inventory is not an object")
        inventory = {}
    for relative, expected_hash in sorted(inventory.items()):
        inventory_path = PurePosixPath(relative)
        if (
            inventory_path.is_absolute()
            or "\\" in relative
            or any(part in {"", ".", ".."} for part in inventory_path.parts)
        ):
            mismatched.append({"path": relative, "expected": str(expected_hash), "actual": "unsafe_path"})
            continue
        path = release.joinpath(*inventory_path.parts)
        if not path.is_file():
            missing.append(relative)
            continue
        checked += 1
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            mismatched.append({"path": relative, "expected": str(expected_hash), "actual": actual_hash})

    allowed = set(inventory) | {MANIFEST_PATH.as_posix()}
    actual_files = {
        path.relative_to(release).as_posix()
        for path in release.rglob("*")
        if path.is_file()
    } if release.is_dir() else set()
    unexpected = sorted(actual_files - allowed)

    actual_validation_hash = sha256_file(validation_path) if validation_path.is_file() else None
    if actual_validation_hash != manifest.get("validation_sha256"):
        mismatched.append({
            "path": VALIDATION_PATH.as_posix(),
            "expected": str(manifest.get("validation_sha256")),
            "actual": str(actual_validation_hash),
        })

    dfg = certificate.get("dfg")
    expected_gates = {f"DFG{i:02d}" for i in range(1, 7)}
    if not isinstance(dfg, dict) or set(dfg) != expected_gates:
        errors.append("certificate must contain exactly DFG01-DFG06")
    else:
        for gate in sorted(expected_gates):
            entry = dfg[gate]
            status = entry.get("status") if isinstance(entry, dict) else None
            if status != "pass":
                errors.append(f"{gate} is not pass: {status!r}")

    if missing:
        errors.append(f"missing {len(missing)} declared inventory files")
    if mismatched:
        errors.append(f"found {len(mismatched)} hash/identity mismatches")
    if unexpected:
        errors.append(f"found {len(unexpected)} unexpected material files")
    implicated = sorted(
        set(missing)
        | {item["path"] for item in mismatched}
        | set(unexpected)
    )
    return {
        "schema_version": "frozen-verification-v1",
        "status": "pass" if not errors else "fail",
        "release": str(release),
        "dataset_version": dataset_version,
        "checked": checked,
        "declared": len(inventory),
        "missing": missing,
        "mismatched": mismatched,
        "unexpected": unexpected,
        "manifest_sha256": actual_manifest_hash,
        "comparison_sha256": actual_comparison_hash,
        "logical_inventory_digest": actual_logical_digest,
        "validation_sha256": actual_validation_hash,
        "dfg": dfg,
        "implicated_paths": implicated,
        "errors": errors,
    }
