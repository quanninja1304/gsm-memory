"""Deterministic source manifest for the Qdrant native-hybrid policy index.

This module performs no network calls and creates no embeddings.  It binds the
frozen public chunks to stable Qdrant point IDs and payloads so later dense and
sparse upserts can be verified against one immutable source plan.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

from gsm_memory.data.operational_v2_contract import OperationalKGv2Contract

from .documents import Chunk, ChunkConfig, canonical_hash, construct_chunks


SCHEMA_VERSION = "gsm-qdrant-native-hybrid-plan-v1"
POINT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "urn:gsm-memory:qdrant-policy-points:v2")
REQUIRED_VECTOR_NAMES = ("dense", "sparse")


@dataclass(frozen=True)
class HybridPointPlan:
    point_id: str
    required_vector_names: tuple[str, str]
    payload: dict[str, Any]


@dataclass(frozen=True)
class HybridCollectionPlan:
    schema_version: str
    collection: str
    dataset_version: str
    profile_id: str
    profile_version: str
    corpus_manifest_sha256: str
    chunk_config_hash: str
    chunk_logical_digest: str
    point_logical_digest: str
    point_count: int
    query_mode: str
    fusion: str
    dense_model: str | None
    sparse_model: str | None
    dense_dimensions: int
    dense_document_prefix: str
    dense_query_prefix: str
    sparse_document_prefix: str
    sparse_query_prefix: str


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def point_id_for_chunk(dataset_version: str, chunk_id: str) -> str:
    """Return a profile-independent UUIDv5 for one immutable source chunk."""

    return str(uuid.uuid5(POINT_NAMESPACE, f"{dataset_version}:{chunk_id}"))


def _point_payload(dataset_version: str, chunk: Chunk, config: ChunkConfig) -> dict[str, Any]:
    return {
        "chunk_id": chunk.chunk_id,
        "chunk_kind": chunk.kind,
        "clause_ids": list(chunk.clause_ids),
        "content_sha256": _sha256(chunk.text.encode("utf-8")),
        "dataset_version": dataset_version,
        "document_content_sha256": chunk.normalized_sha256,
        "document_id": chunk.source_id,
        "document_revision_id": chunk.document_revision_id,
        "normalized_end": chunk.normalized_end,
        "normalized_start": chunk.normalized_start,
        "profile_id": chunk.profile_id,
        "raw_end": chunk.raw_end,
        "raw_sha256": chunk.raw_sha256,
        "raw_start": chunk.raw_start,
        "text": chunk.text,
        "token_count": chunk.token_count,
        "chunker_version": config.chunker_version,
        "tokenizer_version": config.tokenizer_version,
    }


def build_hybrid_point_plan(
    release: Path,
    *,
    profile_id: str = "retrieval_full",
    contract_path: Path = Path("configs/benchmark/operational-kg-v3-r2.json"),
    chunk_config: ChunkConfig = ChunkConfig(),
) -> tuple[HybridCollectionPlan, tuple[HybridPointPlan, ...]]:
    """Build a deterministic, offline Qdrant upsert plan from public chunks."""

    release = release.resolve()
    contract = OperationalKGv2Contract.load(contract_path)
    if release.name != contract.source_release:
        raise ValueError(
            f"contract source release {contract.source_release!r} does not match {release.name!r}"
        )
    chunks, _, inventory = construct_chunks(release, profile_id, chunk_config)
    profile_path = release / "public" / "corpus_profiles" / profile_id / "manifest.json"
    profile_hash = _sha256(profile_path.read_bytes())

    points = tuple(
        HybridPointPlan(
            point_id=point_id_for_chunk(release.name, chunk.chunk_id),
            required_vector_names=REQUIRED_VECTOR_NAMES,
            payload=_point_payload(release.name, chunk, chunk_config),
        )
        for chunk in sorted(chunks, key=lambda row: row.chunk_id)
    )
    point_ids = [point.point_id for point in points]
    if len(point_ids) != len(set(point_ids)):
        raise ValueError("duplicate deterministic Qdrant point ID")

    required_payload = set(contract.runtime_stores.qdrant.payload_join_keys)
    for point in points:
        missing = required_payload - point.payload.keys()
        if missing:
            raise ValueError(f"Qdrant point {point.point_id} is missing payload keys: {sorted(missing)}")
        uuid.UUID(point.point_id)

    vectors = {vector.name: vector for vector in contract.runtime_stores.qdrant.vectors}
    dense_dimensions = vectors["dense"].dimensions
    if dense_dimensions is None:
        raise ValueError("dense dimensions are required before building a Qdrant plan")
    chunk_rows: Sequence[dict[str, Any]] = [asdict(chunk) for chunk in chunks]
    point_rows: Sequence[dict[str, Any]] = [asdict(point) for point in points]
    plan = HybridCollectionPlan(
        schema_version=SCHEMA_VERSION,
        collection=contract.runtime_stores.qdrant.collection,
        dataset_version=release.name,
        profile_id=profile_id,
        profile_version=inventory["profile_version"],
        corpus_manifest_sha256=profile_hash,
        chunk_config_hash=canonical_hash(asdict(chunk_config)),
        chunk_logical_digest=canonical_hash(chunk_rows),
        point_logical_digest=canonical_hash(point_rows),
        point_count=len(points),
        query_mode=contract.runtime_stores.qdrant.query_mode,
        fusion=contract.runtime_stores.qdrant.fusion,
        dense_model=vectors["dense"].model,
        sparse_model=vectors["sparse"].model,
        dense_dimensions=dense_dimensions,
        dense_document_prefix=vectors["dense"].document_prefix,
        dense_query_prefix=vectors["dense"].query_prefix,
        sparse_document_prefix=vectors["sparse"].document_prefix,
        sparse_query_prefix=vectors["sparse"].query_prefix,
    )
    return plan, points


def write_hybrid_point_plan(
    path: Path | str,
    plan: HybridCollectionPlan,
    points: Sequence[HybridPointPlan],
) -> None:
    """Write a rebuildable run artifact; this is never part of a frozen release."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "plan": asdict(plan),
        "points": [asdict(point) for point in points],
    }
    target.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
