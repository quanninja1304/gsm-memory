from __future__ import annotations

import hashlib
import json
import math
import uuid
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

DATASET_VERSION = "gsm-dev-core-0.2.2"
SCHEMA_VERSION = "1.1"
SPEC_VERSION = "0.2.0"
ROOT_SEED = 42
ARCHIVE_SHA256 = "cfe9e4555dbedf81396004c7a7d0ace52dcbb1deb758110c4aded3b6741ba9c9"
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, f"urn:gsm:{DATASET_VERSION}")


def stable_id(object_type: str, private_key: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{object_type}:{private_key}"))


def component_seed(stream_name: str, stable_component_id: str) -> int:
    value = f"{ROOT_SEED}|{stream_name}|{stable_component_id}".encode()
    return int.from_bytes(hashlib.sha256(value).digest()[:8], "big")


def utc(value: str | datetime) -> str:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if dt.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return dt.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def rational(n: int, d: int) -> dict[str, int]:
    if d <= 0:
        raise ValueError("rational denominator must be positive")
    g = math.gcd(n, d)
    return {"n": n // g, "d": d // g}


def as_fraction(value: dict[str, int]) -> Fraction:
    return Fraction(value["n"], value["d"])


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value))


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as stream:
        for row in rows:
            stream.write(canonical_bytes(row))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def logical_hash(rows: Iterable[dict[str, Any]], primary_key: str) -> str:
    return sha256_bytes(b"".join(canonical_bytes(row) for row in sorted(rows, key=lambda x: x[primary_key])))
