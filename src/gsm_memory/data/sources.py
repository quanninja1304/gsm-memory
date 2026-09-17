from __future__ import annotations

import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from .primitives import sha256_bytes, sha256_file


AGGREGATE_NAME = "00_Tong_hop_Tat_ca_Chinh_sach_Tin_tuc.md"


def _safe_member_name(name: str) -> PurePosixPath:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"unsafe ZIP member path: {name!r}")
    if path.parts[0].endswith(":"):
        raise ValueError(f"unsafe ZIP member path: {name!r}")
    return path


def _markdown_members(archive: Path) -> list[tuple[str, bytes]]:
    rows: list[tuple[str, bytes]] = []
    seen_names: set[str] = set()
    with zipfile.ZipFile(archive) as source:
        for info in source.infolist():
            safe = _safe_member_name(info.filename)
            if info.is_dir() or safe.suffix.lower() != ".md":
                continue
            basename = safe.name
            if basename in seen_names:
                raise ValueError(f"duplicate Markdown basename in archive: {basename}")
            seen_names.add(basename)
            rows.append((basename, source.read(info)))
    prefixes: list[int] = []
    for name, _ in rows:
        try:
            prefixes.append(int(name.split("_", 1)[0]))
        except (ValueError, IndexError) as exc:
            raise ValueError(f"invalid source filename: {name}") from exc
    if len(rows) != 225 or sorted(prefixes) != list(range(225)):
        raise ValueError(f"archive must contain exactly Markdown prefixes 00..224; found {len(rows)}")
    if AGGREGATE_NAME not in seen_names:
        raise ValueError("aggregate Markdown member is missing")
    return sorted(rows, key=lambda item: int(item[0].split("_", 1)[0]))


def materialize_sources(
    repo: Path,
    config_path: Path,
    output: Path,
) -> dict[str, Any]:
    """Materialize the pinned Markdown checkout without changing archive bytes."""

    config = json.loads(config_path.read_text(encoding="utf-8"))
    archive = repo / config["source_archive"]
    expected_hash = config["source_archive_sha256"]
    if not archive.is_file():
        raise FileNotFoundError(f"missing pinned source archive: {archive}")
    actual_hash = sha256_file(archive)
    if actual_hash != expected_hash:
        raise ValueError(f"pinned archive SHA-256 mismatch: expected {expected_hash}, got {actual_hash}")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError(f"refusing to overwrite non-empty target: {output}")

    members = _markdown_members(archive)
    output_parent = output.resolve().parent
    output_parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output_parent))
    try:
        for name, payload in members:
            destination = staging / name
            destination.write_bytes(payload)
            if sha256_file(destination) != sha256_bytes(payload):
                raise OSError(f"materialized byte verification failed: {name}")
        if output.exists():
            output.rmdir()  # Only an already-verified empty directory can reach here.
        os.replace(staging, output)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise

    return {
        "status": "pass",
        "archive": str(archive.resolve()),
        "archive_sha256": actual_hash,
        "output": str(output.resolve()),
        "markdown_files": len(members),
        "individual_articles": len(members) - 1,
        "aggregate_files": 1,
        "member_digest": sha256_bytes(b"".join(
            name.encode("utf-8") + b"\0" + sha256_bytes(payload).encode("ascii") + b"\n"
            for name, payload in members
        )),
    }
