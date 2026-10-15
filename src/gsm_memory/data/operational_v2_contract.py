"""Closed contract for the experimental GSM Operational KG v2.

The contract is deliberately separate from the frozen schema-1.1 dataset.  It
defines a future experimental projection and its runtime stores; it never
mutates or reinterprets ``gsm-dev-core-0.2.2``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from .contracts import ClosedModel


class NodeTypeSpec(ClosedModel):
    name: str = Field(min_length=1)
    origin: Literal[
        "frozen_projection",
        "synthetic_extension",
        "reviewed_policy",
        "derived",
    ]
    additional_origins: list[
        Literal[
            "frozen_projection",
            "synthetic_extension",
            "reviewed_policy",
            "derived",
        ]
    ] = Field(default_factory=list)
    required_properties: list[str] = Field(min_length=1)
    semantic_text_fields: list[str]

    @property
    def allowed_origins(self) -> set[str]:
        return {self.origin, *self.additional_origins}


class RelationshipTypeSpec(ClosedModel):
    name: str = Field(min_length=1)
    start_types: list[str] = Field(min_length=1)
    end_types: list[str] = Field(min_length=1)
    meaning: str = Field(min_length=1)


class Neo4jRuntimeSpec(ClosedModel):
    env_prefix: str = Field(pattern=r"^NEO4J_OPERATIONAL_V[0-9]+$")
    marker_label: str = Field(pattern=r"^GSMOperationalV[0-9]+[A-Za-z0-9]*$")
    identity_strategy: Literal["id_equals_canonical_id"]


class NamedVectorSpec(ClosedModel):
    name: Literal["dense", "sparse"]
    purpose: Literal["semantic_similarity", "lexical_precision"]
    model: str | None
    status: Literal[
        "pending_model_selection",
        "pending_vietnamese_validation",
        "provisional_baseline_requires_vietnamese_evaluation",
        "pinned",
    ]
    dimensions: int | None = None
    document_prefix: str = ""
    query_prefix: str = ""


class QdrantRuntimeSpec(ClosedModel):
    collection: Literal["gsm_policy_chunks_v2"]
    query_mode: Literal["native_hybrid"]
    fusion: Literal["rrf"]
    vectors: list[NamedVectorSpec] = Field(min_length=2, max_length=2)
    payload_join_keys: list[str] = Field(min_length=4)
    external_bm25_store: Literal[False]


class RuntimeStoresSpec(ClosedModel):
    neo4j: Neo4jRuntimeSpec
    qdrant: QdrantRuntimeSpec


class OperationalKGv2Contract(ClosedModel):
    contract_version: Literal[
        "gsm-operational-kg-v2-draft-1",
        "gsm-operational-kg-v3-draft-1",
        "gsm-operational-kg-v3-draft-2",
    ]
    status: Literal["experimental_extension"]
    source_release: Literal["gsm-dev-core-0.2.2"]
    source_schema_version: Literal["1.1"]
    mutates_frozen_release: Literal[False]
    purpose: Literal["evidence_retrieval_and_construction"]
    causal_inference: Literal[False]
    temporal_dimensions: list[
        Literal["event_time", "valid_time", "known_time", "ingestion_time"]
    ]
    runtime_stores: RuntimeStoresSpec
    nodes: list[NodeTypeSpec] = Field(min_length=1)
    relationships: list[RelationshipTypeSpec] = Field(min_length=1)
    excluded_node_types: list[str]
    excluded_relationship_types: list[str]

    @model_validator(mode="after")
    def validate_semantics(self) -> "OperationalKGv2Contract":
        expected_clocks = ["event_time", "valid_time", "known_time", "ingestion_time"]
        if self.temporal_dimensions != expected_clocks:
            raise ValueError("the four temporal dimensions must remain explicit and ordered")

        node_names = [node.name for node in self.nodes]
        if node_names != sorted(set(node_names)):
            raise ValueError("node names must be sorted and unique")
        node_set = set(node_names)
        common = {"id", "name", "description"}
        for node in self.nodes:
            if not common.issubset(node.required_properties):
                raise ValueError(f"{node.name} is missing readable common properties")
            if node.required_properties != sorted(set(node.required_properties)):
                raise ValueError(f"{node.name} required properties must be sorted and unique")
            if node.semantic_text_fields != sorted(set(node.semantic_text_fields)):
                raise ValueError(f"{node.name} semantic text fields must be sorted and unique")
            if node.additional_origins != sorted(set(node.additional_origins)):
                raise ValueError(f"{node.name} additional origins must be sorted and unique")
            if node.origin in node.additional_origins:
                raise ValueError(f"{node.name} repeats its primary origin")

        relationship_names = [relationship.name for relationship in self.relationships]
        if relationship_names != sorted(set(relationship_names)):
            raise ValueError("relationship names must be sorted and unique")
        for relationship in self.relationships:
            unknown = (set(relationship.start_types) | set(relationship.end_types)) - node_set
            if unknown:
                raise ValueError(
                    f"{relationship.name} references unknown node types: {sorted(unknown)}"
                )
            if relationship.start_types != sorted(set(relationship.start_types)):
                raise ValueError(f"{relationship.name} start types must be sorted and unique")
            if relationship.end_types != sorted(set(relationship.end_types)):
                raise ValueError(f"{relationship.name} end types must be sorted and unique")

        forbidden_nodes = {"GPSPoint", "InvestigationFinding", "WeatherObservation"}
        if forbidden_nodes & node_set:
            raise ValueError("GPS, weather, and causal-investigation nodes are outside scope")
        forbidden_relationships = {"CAUSES", "ELIGIBLE_FOR", "VIOLATES"}
        if forbidden_relationships & set(relationship_names):
            raise ValueError("causal or precomputed-verdict relationships are outside scope")

        qdrant = self.runtime_stores.qdrant
        vector_pairs = {(vector.name, vector.purpose) for vector in qdrant.vectors}
        if vector_pairs != {
            ("dense", "semantic_similarity"),
            ("sparse", "lexical_precision"),
        }:
            raise ValueError("Qdrant must expose one dense and one sparse named vector")
        vectors = {vector.name: vector for vector in qdrant.vectors}
        if vectors["dense"].dimensions is None or vectors["dense"].dimensions <= 0:
            raise ValueError("dense vector dimensions must be a positive integer")
        if vectors["sparse"].dimensions is not None:
            raise ValueError("sparse vector dimensions must remain implicit")
        required_join_keys = {
            "chunk_id",
            "clause_ids",
            "content_sha256",
            "dataset_version",
            "document_id",
            "document_revision_id",
        }
        if not required_join_keys.issubset(qdrant.payload_join_keys):
            raise ValueError("Qdrant payload is missing stable source/join keys")

        policy_rule = next(node for node in self.nodes if node.name == "PolicyRule")
        if policy_rule.semantic_text_fields:
            raise ValueError("PolicyRule is structured-only in the MVP")
        policy_clause = next(node for node in self.nodes if node.name == "PolicyClause")
        if self.contract_version == "gsm-operational-kg-v2-draft-1":
            if "text" not in policy_clause.semantic_text_fields:
                raise ValueError("legacy v2 requires PolicyClause text in Neo4j")
        elif policy_clause.semantic_text_fields:
            raise ValueError("v3 keeps PolicyClause semantic text only in Qdrant")
        return self

    @classmethod
    def load(cls, path: Path | str) -> "OperationalKGv2Contract":
        return cls.model_validate(cls._load_payload(Path(path).resolve(), seen=set()))

    @classmethod
    def _load_payload(cls, path: Path, *, seen: set[Path]) -> dict[str, Any]:
        """Load one explicit contract or a small versioned overlay.

        Overlays avoid copying the complete closed v2 ontology merely to remove
        deprecated node/relationship types.  They are resolved before Pydantic
        validation, so the resulting contract remains closed and standalone at
        runtime.
        """

        if path in seen:
            raise ValueError(f"cyclic operational contract inheritance: {path}")
        seen.add(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        parent = payload.pop("extends", None)
        if parent is None:
            seen.remove(path)
            return payload

        base = cls._load_payload((path.parent / parent).resolve(), seen=seen)
        node_removals = set(payload.pop("remove_nodes", []))
        relationship_removals = set(payload.pop("remove_relationships", []))
        node_overrides = payload.pop("node_overrides", {})
        relationship_overrides = payload.pop("relationship_overrides", {})

        def deep_merge(original: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
            merged = dict(original)
            for key, value in update.items():
                if isinstance(value, dict) and isinstance(merged.get(key), dict):
                    merged[key] = deep_merge(merged[key], value)
                else:
                    merged[key] = value
            return merged

        base = deep_merge(base, payload)
        nodes = []
        for row in base["nodes"]:
            if row["name"] in node_removals:
                continue
            nodes.append(deep_merge(row, node_overrides.get(row["name"], {})))
        relationships = []
        for row in base["relationships"]:
            if row["name"] in relationship_removals:
                continue
            relationships.append(
                deep_merge(row, relationship_overrides.get(row["name"], {}))
            )
        unknown_node_overrides = set(node_overrides) - {row["name"] for row in nodes}
        unknown_relationship_overrides = set(relationship_overrides) - {
            row["name"] for row in relationships
        }
        if unknown_node_overrides or unknown_relationship_overrides:
            raise ValueError(
                "unknown operational contract override: "
                f"nodes={sorted(unknown_node_overrides)}, "
                f"relationships={sorted(unknown_relationship_overrides)}"
            )
        base["nodes"] = nodes
        base["relationships"] = relationships
        seen.remove(path)
        return base
