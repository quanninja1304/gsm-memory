from __future__ import annotations

from typing import Any

from .primitives import canonical_bytes, sha256_bytes, stable_id


def synthetic_policy_rules(ids: dict[str, str]) -> list[dict[str, Any]]:
    """Canonical private ASTs for the three approved synthetic controls."""
    return [
        {
            "rule_id": stable_id("rule", "S_BRIDGE:v1"),
            "policy_version_id": stable_id("policy_version", "S_BRIDGE:v1"),
            "policy_key": "S_BRIDGE",
            "version": "v1",
            "rule_kind": "fleet_region_without_open_incident",
            "required_region_id": ids["HCM_OLD"],
            "evaluation_time": "2026-09-15T17:00:00.000000Z",
        },
        {
            "rule_id": stable_id("rule", "S_VERSION:v1"),
            "policy_version_id": stable_id("policy_version", "S_VERSION:v1"),
            "policy_key": "S_VERSION",
            "version": "v1",
            "rule_kind": "operating_region_requirement",
            "required_region_id": ids["HN"],
        },
        {
            "rule_id": stable_id("rule", "S_VERSION:v2"),
            "policy_version_id": stable_id("policy_version", "S_VERSION:v2"),
            "policy_key": "S_VERSION",
            "version": "v2",
            "rule_kind": "operating_region_requirement",
            "required_region_id": ids["HCM_OLD"],
        },
    ]


def render_synthetic_policy(rule: dict[str, Any]) -> dict[str, Any]:
    """Render only AST fields; no case, answer, proof, or private alias is emitted."""
    version_id = rule["policy_version_id"]
    heading = f"# Synthetic control policy {version_id}\n\n"
    if rule["rule_kind"] == "fleet_region_without_open_incident":
        bodies = [
            (
                "scope",
                "A driver satisfies the fleet-region premise only when an active MEMBER_OF assertion "
                f"links the driver to a fleet whose active BASED_IN assertion is {rule['required_region_id']}.",
            ),
            (
                "exception",
                "At 2026-09-15T17:00:00.000000Z, the rule is not satisfied when the same driver has "
                "an incident membership with INCIDENT_STATUS=open. Absence requires a complete published "
                "incident-register coverage artifact for that driver and time.",
            ),
        ]
    else:
        bodies = [
            (
                "region",
                "The required active OPERATES_IN region for this policy version is "
                f"{rule['required_region_id']}.",
            )
        ]
    text = heading
    clauses = []
    for order, (kind, body) in enumerate(bodies, 1):
        start = len(text)
        text += body + "\n"
        end = start + len(body)
        clauses.append(
            {
                "clause_id": stable_id("policy_clause", f"{version_id}:{kind}"),
                "section_id": kind,
                "order": order,
                "kind": "rule",
                "span_start": start,
                "span_end": end,
                "coordinate_system": "unicode_codepoints_half_open",
                "content_sha256": sha256_bytes(canonical_bytes(body)),
                "text_review_state": "generated_from_canonical_ast",
            }
        )
    return {"text": text, "clauses": clauses, "renderer_version": "synthetic-policy-v1"}


def verify_synthetic_render(rule: dict[str, Any], rendered: dict[str, Any]) -> None:
    text = rendered["text"]
    for clause in rendered["clauses"]:
        span = text[clause["span_start"] : clause["span_end"]]
        if sha256_bytes(canonical_bytes(span)) != clause["content_sha256"]:
            raise ValueError(f"synthetic clause span mismatch: {clause['clause_id']}")
    if rule["required_region_id"] not in text:
        raise ValueError("synthetic renderer omitted required region")
    if rule["rule_kind"] == "fleet_region_without_open_incident" and "INCIDENT_STATUS=open" not in text:
        raise ValueError("synthetic renderer omitted incident exception")
