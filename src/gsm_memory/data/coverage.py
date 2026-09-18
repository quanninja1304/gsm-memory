from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .ledger import reduce_prefix
from .primitives import canonical_bytes, sha256_bytes, stable_id


class CoverageContractError(ValueError):
    pass


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CoveredDomain(ClosedModel):
    domain_id: Literal["terminal_trip_population", "driver_incident_register"]
    member_type: Literal["trip", "incident"]
    membership_predicate: Literal["TRIP_OUTCOME", "HAS_INCIDENT"]
    terminal_outcomes: list[Literal["completed", "cancelled"]] | None = None

    @model_validator(mode="after")
    def validate_domain(self) -> "CoveredDomain":
        if self.domain_id == "terminal_trip_population":
            if self.member_type != "trip" or self.membership_predicate != "TRIP_OUTCOME":
                raise ValueError("terminal-trip domain has incompatible member or predicate")
            if sorted(self.terminal_outcomes or []) != ["cancelled", "completed"]:
                raise ValueError("terminal-trip domain must enumerate both terminal outcomes")
        elif self.terminal_outcomes is not None:
            raise ValueError("incident domain must not declare terminal outcomes")
        return self


class ValidWindow(ClosedModel):
    start: str
    end: str
    bounds: Literal["[start,end)"]

    @model_validator(mode="after")
    def validate_order(self) -> "ValidWindow":
        if self.start >= self.end:
            raise ValueError("coverage window must be nonempty")
        return self


class SourceSetRecipe(ClosedModel):
    source_set_key: Literal["terminal_trip_outcomes", "driver_incident_memberships"]
    source_set_version: Literal["1.0"]
    allowed_source_refs: list[Literal["event", "incident"]] = Field(min_length=1)
    allowed_predicates: list[Literal["TRIP_OUTCOME", "HAS_INCIDENT"]] = Field(min_length=1)


class TripSelector(ClosedModel):
    selector_type: Literal["terminal_trip"] = "terminal_trip"
    subject_equals: str
    valid_kind: Literal["point"]
    valid_point_in_declared_window: Literal[True]
    require_trip_id: Literal[True]
    require_terminal_outcome: Literal[True]
    distinct_by: Literal["trip_id"]
    member_value: Literal["trip_id"]


class IncidentSelector(ClosedModel):
    selector_type: Literal["incident_membership"] = "incident_membership"
    subject_equals: str
    valid_interval_overlaps_declared_window: Literal[True]
    object_type: Literal["entity_ref"]
    member_value: Literal["object.value"]
    distinct_by: Literal["incident_id"]


Selector = Annotated[TripSelector | IncidentSelector, Field(discriminator="selector_type")]


class Completeness(ClosedModel):
    kind: Literal["closed_world_enumeration"]
    complete: Literal[True]
    known_at_lte: str
    assertion_state: Literal["active_after_reduction"]
    non_assertive_outside_declared_domain: Literal[True]


class CorrectionPolicy(ClosedModel):
    reducer: Literal["canonical_bitemporal_reducer"]
    replace: Literal["follow_authorized_target_assertions"]
    retract: Literal["exclude_retracted_assertions"]
    source_correction_authority: Literal["source_registry"]
    interval_semantics: Literal["[from,to)"]
    same_timestamp_policy: Literal["canonical_commit_seq"]


class CoveragePublication(ClosedModel):
    publisher_source_ref: Literal["derived"]
    predicate: Literal["ARTIFACT_PUBLICATION"]
    known_at: str


class CoverageRecipe(ClosedModel):
    recipe_key: str = Field(min_length=1)
    recipe_version: Literal["1.0"]
    world_ref: Literal["W0"]
    scope_ref: Literal["S0"]
    subject_ref: Literal["D_B", "D_H"]
    covered_domain: CoveredDomain
    valid_window: ValidWindow
    source_set: SourceSetRecipe
    selector: Selector
    completeness: Completeness
    correction_policy: CorrectionPolicy
    publication: CoveragePublication
    expected_member_count_for_validation: int = Field(ge=0)
    expected_outcome_counts_for_validation: dict[Literal["completed", "cancelled"], int] | None = None

    @model_validator(mode="after")
    def validate_consistency(self) -> "CoverageRecipe":
        if self.selector.subject_equals != self.subject_ref:
            raise ValueError("selector subject must match recipe subject")
        if self.completeness.known_at_lte != self.publication.known_at:
            raise ValueError("coverage cutoff and publication time must match")
        if self.covered_domain.membership_predicate not in self.source_set.allowed_predicates:
            raise ValueError("source set must allow the coverage predicate")
        trip = self.covered_domain.domain_id == "terminal_trip_population"
        if trip != isinstance(self.selector, TripSelector):
            raise ValueError("selector type must match covered domain")
        if trip and self.source_set.source_set_key != "terminal_trip_outcomes":
            raise ValueError("trip recipe must use terminal-trip source set")
        if not trip and self.source_set.source_set_key != "driver_incident_memberships":
            raise ValueError("incident recipe must use incident source set")
        if not trip and self.valid_window.end <= "2026-09-15T17:00:00.000000Z":
            raise ValueError("incident coverage must contain Tm under [start,end) semantics")
        return self


class CoverageConfig(ClosedModel):
    coverage_contract_version: Literal["coverage-v1"]
    coverage_recipes: list[CoverageRecipe] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_recipes(self) -> "CoverageConfig":
        keys = [(x.recipe_key, x.recipe_version) for x in self.coverage_recipes]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate coverage recipe")
        return self


def _overlaps(valid: dict[str, Any], window: ValidWindow) -> bool:
    if valid.get("kind") == "point":
        return window.start <= valid["at"] < window.end
    if valid.get("kind") != "interval":
        return False
    end = valid.get("to", {})
    valid_end = end.get("at") if end.get("kind") == "finite" else None
    return valid["from"] < window.end and (valid_end is None or valid_end > window.start)


def resolved_source_set(
    recipe: CoverageRecipe,
    resolved_source_ids: dict[str, str],
) -> dict[str, Any]:
    allowed = sorted(resolved_source_ids[x] for x in recipe.source_set.allowed_source_refs)
    selector_public = recipe.selector.model_dump(mode="json")
    selector_public["subject_equals"] = "resolved-at-build"
    selector_digest = sha256_bytes(b"coverage-selector-v1\0" + canonical_bytes(selector_public))
    value = {
        "contract_version": "coverage-v1",
        "source_set_version": recipe.source_set.source_set_version,
        "allowed_source_ids": allowed,
        "allowed_predicates": sorted(recipe.source_set.allowed_predicates),
        "selector_digest": selector_digest,
        "correction_policy": recipe.correction_policy.model_dump(mode="json"),
    }
    return {
        **value,
        "source_set_id": stable_id("source_set", sha256_bytes(b"coverage-source-set-v1\0" + canonical_bytes(value))),
        "selector": selector_public,
    }


def derive_coverage_members(
    recipe: CoverageRecipe,
    records: list[dict[str, Any]],
    source_registry: dict[str, dict[str, Any]],
    resolved_ids: dict[str, str],
) -> tuple[list[str], dict[str, int]]:
    subject_id = resolved_ids[recipe.subject_ref]
    allowed_sources = {resolved_ids[x] for x in recipe.source_set.allowed_source_refs}
    view = reduce_prefix(records, source_registry, recipe.completeness.known_at_lte)
    members: dict[str, str] = {}
    outcomes = {"completed": 0, "cancelled": 0}
    for item in view:
        assertion = item.payload
        if item.known_to is not None or item.source_id not in allowed_sources:
            continue
        if assertion["predicate"] != recipe.covered_domain.membership_predicate:
            continue
        if assertion["subject_id"] != subject_id or not _overlaps(assertion["valid"], recipe.valid_window):
            continue
        if isinstance(recipe.selector, TripSelector):
            if assertion["valid"].get("kind") != "point":
                continue
            trip_id = assertion.get("qualifiers", {}).get("trip_id")
            outcome = assertion.get("qualifiers", {}).get("outcome")
            if not trip_id or outcome not in set(recipe.covered_domain.terminal_outcomes or []):
                continue
            if trip_id in members:
                raise CoverageContractError(f"duplicate active trip identity: {trip_id}")
            members[trip_id] = assertion["assertion_id"]
            outcomes[outcome] += 1
        else:
            obj = assertion.get("object", {})
            if obj.get("type") != "entity_ref" or not obj.get("value"):
                continue
            member = obj["value"]
            if member in members:
                raise CoverageContractError(f"duplicate active incident identity: {member}")
            members[member] = assertion["assertion_id"]
    result = sorted(members)
    if len(result) != recipe.expected_member_count_for_validation:
        raise CoverageContractError(
            f"coverage invariant failed for {recipe.recipe_key}: expected "
            f"{recipe.expected_member_count_for_validation}, got {len(result)}"
        )
    if recipe.expected_outcome_counts_for_validation is not None:
        expected = dict(recipe.expected_outcome_counts_for_validation)
        if outcomes != expected:
            raise CoverageContractError(f"outcome invariant failed: expected {expected}, got {outcomes}")
    return result, outcomes


def coverage_digests(
    recipe: CoverageRecipe,
    members: list[str],
    resolved_ids: dict[str, str],
    source_set: dict[str, Any],
) -> dict[str, Any]:
    members_digest = sha256_bytes(b"coverage-members-v1\0" + canonical_bytes(sorted(members)))
    spec = {
        "contract_version": "coverage-v1",
        "recipe_version": recipe.recipe_version,
        "world_id": resolved_ids[recipe.world_ref],
        "scope_id": resolved_ids[recipe.scope_ref],
        "subject_id": resolved_ids[recipe.subject_ref],
        "covered_domain": recipe.covered_domain.model_dump(mode="json"),
        "valid_window": recipe.valid_window.model_dump(mode="json"),
        "source_set_id": source_set["source_set_id"],
        "source_set_version": source_set["source_set_version"],
        "selector_digest": source_set["selector_digest"],
        "completeness": recipe.completeness.model_dump(mode="json"),
        "correction_policy": recipe.correction_policy.model_dump(mode="json"),
    }
    spec_digest = sha256_bytes(b"coverage-spec-v1\0" + canonical_bytes(spec))
    coverage_spec_id = stable_id("coverage_spec", spec_digest)
    content = {
        "contract_version": "coverage-v1",
        "coverage_spec_id": coverage_spec_id,
        "coverage_spec": spec,
        "member_ids": sorted(members),
        "member_count": len(members),
        "members_digest": members_digest,
        "complete": True,
    }
    coverage_content_digest = sha256_bytes(b"coverage-content-v1\0" + canonical_bytes(content))
    return {
        **content,
        "coverage_content_digest_v1": coverage_content_digest,
        "artifact_id": stable_id("coverage_artifact", coverage_content_digest),
        "artifact_version": "1.0",
    }
