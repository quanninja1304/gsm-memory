from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, TypeAdapter

from .contracts import ClosedModel
from .primitives import canonical_bytes, read_jsonl, sha256_bytes


class ClauseRef(ClosedModel):
    clause_id: str
    span_start: int
    span_end: int
    coordinate_system: Literal["unicode_codepoints_half_open"]
    content_sha256: str


class DocumentClauseLocator(ClosedModel):
    locator_type: Literal["document_clause"]
    public_snapshot_id: str
    document_revision_id: str
    source_snapshot_id: str | None
    policy_version_id: str | None
    normalized_sha256: str
    publication_assertion_id: str
    clause_refs: list[ClauseRef] = Field(min_length=1)


class LedgerAssertionLocator(ClosedModel):
    locator_type: Literal["ledger_assertion"]
    public_snapshot_id: str
    world_id: str
    ledger_id: str
    scope_id: str
    record_id: str
    assertion_id: str
    source_id: str
    source_registry_digest: str
    payload_hash: str
    logical_fact_id: str
    predicate: str
    subject_id: str
    valid_extent: dict[str, Any]
    known_at: str
    known_to_at_prefix: str | None
    revision_operation: Literal["assert", "replace", "retract"]
    target_assertion_ids: list[str]


class EntityCatalogLocator(ClosedModel):
    locator_type: Literal["entity_catalog"]
    public_snapshot_id: str
    world_id: str
    scope_id: str
    entity_id: str
    entity_type: str
    catalog_row_digest: str


class DefinitionArtifactLocator(ClosedModel):
    locator_type: Literal["definition_artifact"]
    public_snapshot_id: str
    definition_id: str
    definition_version: str
    content_sha256: str


class CoverageArtifactLocator(ClosedModel):
    locator_type: Literal["coverage_artifact"]
    public_snapshot_id: str
    branch_ledger_id: str
    world_id: str
    scope_id: str
    artifact_id: str
    artifact_revision: str
    coverage_spec_id: str
    coverage_spec_version: str
    subject_id: str
    covered_domain: dict[str, Any]
    valid_window: dict[str, Any]
    source_set_id: str
    source_set_version: str
    source_set_digest: str
    completeness_cutoff: str
    correction_policy_version: Literal["canonical_bitemporal_reducer-v1"]
    members_digest: str
    member_count: int
    coverage_content_digest_v1: str
    publication_record_id: str
    publication_assertion_id: str


SupportLocator = Annotated[
    DocumentClauseLocator | LedgerAssertionLocator | EntityCatalogLocator | DefinitionArtifactLocator | CoverageArtifactLocator,
    Field(discriminator="locator_type"),
]
LOCATOR_ADAPTER = TypeAdapter(SupportLocator)


def source_registry_digest(row: dict[str, Any]) -> str:
    return sha256_bytes(b"source-registry-v1\0" + canonical_bytes(row))


def catalog_row_digest(row: dict[str, Any]) -> str:
    return sha256_bytes(b"entity-catalog-v1\0" + canonical_bytes(row))


def source_set_digest(row: dict[str, Any]) -> str:
    return sha256_bytes(b"source-set-public-v1\0" + canonical_bytes(row))


def resolve_public_locator(release: Path, value: dict[str, Any]) -> dict[str, Any]:
    """Resolve a closed source locator using only its selected public snapshot."""
    locator = LOCATOR_ADAPTER.validate_python(value)
    snapshot = release / "public/snapshots" / locator.public_snapshot_id
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    if manifest["snapshot_id"] != locator.public_snapshot_id:
        raise ValueError("snapshot identity mismatch")
    rows = read_jsonl(snapshot / "text_observations.jsonl")
    records = {row["record_id"]: row for row in rows}
    assertions = {
        assertion["assertion_id"]: (record, assertion)
        for record in rows
        for assertion in record["assertions"]
    }
    if isinstance(locator, DocumentClauseLocator):
        docs = {row["document_revision_id"]: row for row in read_jsonl(snapshot / "documents.jsonl")}
        row = docs.get(locator.document_revision_id)
        if row is None or row.get("normalized_sha256") != locator.normalized_sha256:
            raise ValueError("document is not visible or hash mismatches")
        if row.get("snapshot_id") != locator.source_snapshot_id or row.get("policy_version_id") != locator.policy_version_id:
            raise ValueError("document identity mismatch")
        catalog_clauses = {x["clause_id"]: x for x in row.get("clauses", [])}
        text=(release/f"public/documents/normalized/{locator.document_revision_id}.md").read_text(encoding="utf-8")
        for clause in locator.clause_refs:
            actual = catalog_clauses.get(clause.clause_id)
            if actual is None or any(actual.get(k) != getattr(clause, k) for k in ("span_start", "span_end", "coordinate_system")):
                raise ValueError("clause locator mismatch")
            if sha256_bytes(canonical_bytes(text[clause.span_start:clause.span_end])) != clause.content_sha256 or actual.get("content_sha256") != clause.content_sha256:
                raise ValueError("clause content hash mismatch")
        if locator.publication_assertion_id not in assertions:
            raise ValueError("document publication is absent from snapshot prefix")
        return {"locator_type":locator.locator_type,"resolved":True,"document_revision_id":row["document_revision_id"]}
    if isinstance(locator, LedgerAssertionLocator):
        if (manifest["world_id"],manifest["ledger_id"],manifest["scope_id"]) != (locator.world_id,locator.ledger_id,locator.scope_id):
            raise ValueError("ledger locator snapshot identity mismatch")
        pair = assertions.get(locator.assertion_id)
        if pair is None:
            raise ValueError("assertion is absent from snapshot prefix")
        record, assertion = pair
        sources = {x["source_id"]:x for x in read_jsonl(snapshot/"source_registry.jsonl")}
        checks = {
            "record_id":record["record_id"],"source_id":record["source_id"],"payload_hash":record["payload_hash"],
            "logical_fact_id":assertion["logical_fact_id"],"predicate":assertion["predicate"],"subject_id":assertion["subject_id"],
            "valid_extent":assertion["valid"],"known_at":record["known_at"],"revision_operation":record["operation"],
            "target_assertion_ids":record["target_assertion_ids"],"source_registry_digest":source_registry_digest(sources[record["source_id"]]),
        }
        for key, actual in checks.items():
            if getattr(locator,key) != actual: raise ValueError(f"ledger locator {key} mismatch")
        closing=next((r["known_at"] for r in rows if locator.assertion_id in r["target_assertion_ids"]),None)
        if locator.known_to_at_prefix!=closing: raise ValueError("ledger locator known_to_at_prefix mismatch")
        return {"locator_type":locator.locator_type,"resolved":True,"assertion_id":locator.assertion_id}
    if isinstance(locator, EntityCatalogLocator):
        if (manifest["world_id"],manifest["scope_id"]) != (locator.world_id,locator.scope_id): raise ValueError("entity scope mismatch")
        entities={x["entity_id"]:x for x in read_jsonl(snapshot/"entity_catalog.jsonl")};row=entities.get(locator.entity_id)
        if row is None or row["entity_type"]!=locator.entity_type or catalog_row_digest(row)!=locator.catalog_row_digest: raise ValueError("entity catalog mismatch")
        return {"locator_type":locator.locator_type,"resolved":True,"entity_id":locator.entity_id}
    if isinstance(locator, DefinitionArtifactLocator):
        definitions={x["definition_id"]:x for x in read_jsonl(snapshot/"definitions.jsonl")};row=definitions.get(locator.definition_id)
        if row is None or row["version"]!=locator.definition_version or row["content_sha256"]!=locator.content_sha256: raise ValueError("definition mismatch")
        return {"locator_type":locator.locator_type,"resolved":True,"definition_id":locator.definition_id}
    if (manifest["world_id"],manifest["ledger_id"],manifest["scope_id"]) != (locator.world_id,locator.branch_ledger_id,locator.scope_id): raise ValueError("coverage snapshot identity mismatch")
    artifacts={x["artifact_id"]:x for x in read_jsonl(snapshot/"artifacts.jsonl")};artifact=artifacts.get(locator.artifact_id)
    if artifact is None or not artifact.get("complete"): raise ValueError("complete coverage artifact is not visible")
    source_set=artifact["source_set"]
    expected={"artifact_revision":artifact["artifact_revision"],"coverage_spec_id":artifact["coverage_spec_id"],"coverage_spec_version":artifact["coverage_spec_version"],"subject_id":artifact["coverage_spec"]["subject_id"],"covered_domain":artifact["coverage_spec"]["covered_domain"],"valid_window":artifact["coverage_spec"]["valid_window"],"source_set_id":source_set["source_set_id"],"source_set_version":source_set["source_set_version"],"source_set_digest":source_set_digest(source_set),"completeness_cutoff":artifact["coverage_spec"]["completeness"]["known_at_lte"],"members_digest":artifact["members_digest"],"member_count":artifact["member_count"],"coverage_content_digest_v1":artifact["coverage_content_digest_v1"],"publication_record_id":artifact["publication_record_id"],"publication_assertion_id":artifact["publication_assertion_id"]}
    for key,actual in expected.items():
        if getattr(locator,key)!=actual: raise ValueError(f"coverage locator {key} mismatch")
    if locator.publication_record_id not in records or locator.publication_assertion_id not in assertions: raise ValueError("coverage publication absent")
    if records[locator.publication_record_id]["known_at"] > manifest["known_as_of"]: raise ValueError("future coverage publication")
    return {"locator_type":locator.locator_type,"resolved":True,"artifact_id":locator.artifact_id}
