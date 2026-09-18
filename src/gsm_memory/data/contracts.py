from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PolicyRef(ClosedModel):
    kind: Literal["real_snapshot", "synthetic_version"]
    id: str = Field(min_length=1)


class MaskSpec(ClosedModel):
    seed_record_ids: list[str] = Field(min_length=1)
    removed_record_ids: list[str] = Field(min_length=1)
    closure_policy: Literal["remove_dependents"]
    invariant_refs: list[str] = Field(min_length=1)


class ConflictSpec(ClosedModel):
    logical_fact_id: str
    removed_record_ids: list[str]
    added_record_ids: list[str] = Field(min_length=1)
    invariant_refs: list[str] = Field(min_length=1)


class RetractionSpec(ClosedModel):
    target_assertion_ids: list[str] = Field(min_length=1)
    removed_record_ids: list[str]
    added_record_ids: list[str] = Field(min_length=1)
    invariant_refs: list[str] = Field(min_length=1)


MutationSpec = Annotated[dict | MaskSpec | ConflictSpec | RetractionSpec, Field()]


class ScenarioManifest(ClosedModel):
    schema_version: Literal["1.1"]
    release_spec_version: Literal["0.2.0"]
    dataset_version: Literal["gsm-dev-core-0.2.2"]
    world_id: str
    scenario_id: str
    scenario_variant_id: str
    parent_variant_id: str | None
    mutation_type: Literal["base", "observation_mask", "source_conflict", "retraction_branch"]
    mutation_spec: dict
    ledger_id: str
    scope_id: str
    gold_track: Literal["source_grounded", "conditional_binding", "synthetic_control"]
    task_id: Literal["T01", "T02", "T03", "T04", "T05", "T06", "T07"] | None
    foundation_task: Literal["state", "event", "aggregate", "bridge", "entity_resolution", "policy_version"] | None
    policy_snapshot_refs: list[PolicyRef]
    public_snapshot_refs: list[str] = Field(min_length=1)
    semantic_case_ids: list[str] = Field(min_length=1)
    query_ids: list[str] = Field(min_length=1)
    split_group: str
    seed: Literal[42]

    @model_validator(mode="after")
    def validate_closed_semantics(self) -> "ScenarioManifest":
        if (self.task_id is None) == (self.foundation_task is None):
            raise ValueError("exactly one task reference is required")
        if self.mutation_type == "base":
            if self.parent_variant_id is not None or self.mutation_spec != {}:
                raise ValueError("base requires null parent and empty mutation_spec")
        else:
            if self.parent_variant_id is None:
                raise ValueError("non-base requires parent")
            cls = {"observation_mask": MaskSpec, "source_conflict": ConflictSpec, "retraction_branch": RetractionSpec}[self.mutation_type]
            cls.model_validate(self.mutation_spec)
        for values in (self.public_snapshot_refs, self.semantic_case_ids, self.query_ids):
            if values != sorted(set(values)):
                raise ValueError("ID arrays must be sorted and unique")
        return self
