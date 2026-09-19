"""Deterministic, public-only document construction for Phase B."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

CHUNKER_VERSION = "gsm-word-span-v1"
TOKENIZER_VERSION = "unicode-word-regex-v1"
TOKEN_RE = re.compile(r"\S+")


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line]


@dataclass(frozen=True)
class ChunkConfig:
    max_tokens: int = 180
    overlap: int = 30
    chunker_version: str = CHUNKER_VERSION
    tokenizer_version: str = TOKENIZER_VERSION
    normalization: str = "frozen-normalized-utf8"

    @property
    def config_hash(self) -> str:
        return canonical_hash(asdict(self))


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    kind: str
    source_id: str
    document_revision_id: str
    profile_id: str
    normalized_start: int
    normalized_end: int
    raw_start: int
    raw_end: int
    token_count: int
    text: str
    normalized_sha256: str
    raw_sha256: str | None
    clause_ids: tuple[str, ...]
    config_hash: str


@dataclass(frozen=True)
class ProjectionLink:
    projection_kind: str
    source_kind: str
    source_id: str
    source_locator: str
    runtime_id: str
    config_hash: str


def _raw_offset(text: str, offset: int, raw_uses_crlf: bool) -> int:
    return offset + text[:offset].count("\n") if raw_uses_crlf else offset


def _spans(text: str, config: ChunkConfig) -> Iterable[tuple[int, int, int]]:
    tokens = list(TOKEN_RE.finditer(text))
    if not tokens:
        return
    step = config.max_tokens - config.overlap
    if step <= 0:
        raise ValueError("overlap must be smaller than max_tokens")
    for first in range(0, len(tokens), step):
        selected = tokens[first : first + config.max_tokens]
        if not selected:
            break
        yield selected[0].start(), selected[-1].end(), len(selected)
        if first + config.max_tokens >= len(tokens):
            break


def construct_chunks(
    release: Path, profile_id: str, config: ChunkConfig = ChunkConfig()
) -> tuple[list[Chunk], list[ProjectionLink], dict[str, Any]]:
    public = release / "public"
    if not public.is_dir() or (release / "private").exists() and public.resolve() == release.resolve():
        raise ValueError("release must expose a public directory")
    profile_path = public / "corpus_profiles" / profile_id / "manifest.json"
    profile = json.loads(profile_path.read_text("utf-8"))
    catalog = read_jsonl(public / "documents" / "catalog.jsonl")
    real_ids = set(profile["real_snapshot_ids"])
    shared_ids = set(profile["shared_document_revision_ids"])
    definition_ids = set(profile["definition_ids"])
    selected = [
        row for row in catalog
        if row["snapshot_id"] in real_ids or row["document_revision_id"] in shared_ids
    ]
    sources: list[tuple[str, str, Path, dict[str, Any]]] = []
    for row in selected:
        revision = row["document_revision_id"]
        source_id = row["snapshot_id"] or revision
        sources.append(("document", source_id, public / "documents" / "normalized" / f"{revision}.md", row))
    definition_catalog = {r["definition_id"]: r for r in read_jsonl(public / "definitions" / "catalog.jsonl")}
    for definition_id in sorted(definition_ids):
        row = definition_catalog[definition_id]
        sources.append(("definition", definition_id, public / "definitions" / f"{definition_id}.md", row))

    chunks: list[Chunk] = []
    links: list[ProjectionLink] = []
    for kind, source_id, path, row in sorted(sources, key=lambda item: (item[0], item[1])):
        data = path.read_bytes()
        text = data.decode("utf-8")
        normalized_hash = hashlib.sha256(data).hexdigest()
        expected = row.get("normalized_sha256") or row.get("content_sha256") or normalized_hash
        if normalized_hash != expected:
            raise ValueError(f"normalized hash mismatch: {path}")
        revision = row.get("document_revision_id", source_id)
        clauses = row.get("clauses", [])
        raw_uses_crlf = False
        if kind == "document":
            raw_name = row.get("snapshot_id") or revision
            raw_path = public / "documents" / "raw" / f"{raw_name}.md"
            if raw_path.exists():
                raw_data = raw_path.read_bytes()
                if row.get("raw_sha256") and hashlib.sha256(raw_data).hexdigest() != row["raw_sha256"]:
                    raise ValueError(f"raw hash mismatch: {raw_path}")
                raw_uses_crlf = b"\r\n" in raw_data
        for start, end, count in _spans(text, config):
            clause_ids = tuple(sorted(str(c["clause_id"]) for c in clauses if c.get("span_start", end) < end and c.get("span_end", start) > start))
            identity = {"revision": revision, "start": start, "end": end, "config_hash": config.config_hash}
            chunk_id = canonical_hash(identity)
            raw_start = _raw_offset(text, start, raw_uses_crlf) if kind == "document" else start
            raw_end = _raw_offset(text, end, raw_uses_crlf) if kind == "document" else end
            chunks.append(Chunk(chunk_id, kind, source_id, revision, profile_id, start, end, raw_start, raw_end, count, text[start:end], normalized_hash, row.get("raw_sha256"), clause_ids, config.config_hash))
            links.append(ProjectionLink("document_chunk", kind, source_id, path.relative_to(release).as_posix(), chunk_id, config.config_hash))
    chunks.sort(key=lambda c: c.chunk_id)
    links.sort(key=lambda link: link.runtime_id)
    inventory = {
        "profile_id": profile_id,
        "profile_version": profile["corpus_profile_version"],
        "document_count": len(selected),
        "definition_count": len(definition_ids),
        "chunk_count": len(chunks),
        "config": asdict(config),
        "config_hash": config.config_hash,
        "logical_digest": canonical_hash([asdict(c) for c in chunks]),
    }
    return chunks, links, inventory
