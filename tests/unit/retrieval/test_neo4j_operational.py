from pathlib import Path

from gsm_memory.adapters.neo4j_operational import (
    MARKER_LABEL,
    ONTOLOGY_VERSION,
    _combined_projection_rows,
    load_operational_projections,
    project_operational_snapshot,
)


RELEASE = Path("data/gsm-dev-core-0.2.2")
SNAPSHOT_ID = "25b69c05-6a60-51e3-9209-74e5d49816fa"


def test_operational_projection_is_readable_and_uses_one_node_id():
    projection = project_operational_snapshot(RELEASE, SNAPSHOT_ID)

    assert MARKER_LABEL == "GSMOperationalV1"
    assert ONTOLOGY_VERSION == "gsm-operational-kg-v1"
    assert projection.nodes
    assert projection.edges
    assert all(row["props"]["id"] == row["id"] for row in projection.nodes)
    assert all("canonical_id" not in row["props"] for row in projection.nodes)
    assert all(row["props"]["name"] for row in projection.nodes)
    assert all(row["props"]["description"] for row in projection.nodes)


def test_operational_projection_has_unique_idempotency_keys():
    projection = project_operational_snapshot(RELEASE, SNAPSHOT_ID)
    node_keys = [(row["label"], row["id"]) for row in projection.nodes]
    edge_keys = [
        (
            row["type"],
            row["start_id"],
            row["end_id"],
            row["props"]["snapshot_id"],
            row["props"]["evidence_ref"],
        )
        for row in projection.edges
    ]

    assert len(node_keys) == len(set(node_keys))
    assert len(edge_keys) == len(set(edge_keys))
    assert all(row["props"]["snapshot_id"] == SNAPSHOT_ID for row in projection.edges)
    assert all(row["props"]["evidence_ref"] for row in projection.edges)


def test_operational_projection_excludes_policy_and_artifact_nodes():
    projection = project_operational_snapshot(RELEASE, SNAPSHOT_ID)
    labels = {row["label"] for row in projection.nodes}
    relationship_types = {row["type"] for row in projection.edges}

    assert "PolicyVersion" not in labels
    assert "SourceArtifact" not in labels
    assert "OracleAssertion" not in labels
    assert "PUBLISHED_AS" not in relationship_types
    assert projection.excluded_predicate_counts["ARTIFACT_PUBLICATION"] > 0
    assert projection.excluded_predicate_counts["POLICY_PUBLICATION"] > 0


def test_trip_outcome_projects_to_three_readable_edges():
    projection = project_operational_snapshot(RELEASE, SNAPSHOT_ID)
    trip_edges = [
        row for row in projection.edges
        if row["type"] in {"PERFORMED", "FOR_SERVICE", "IN_REGION"}
    ]
    evidence_roles: dict[str, set[str]] = {}
    for row in trip_edges:
        evidence_roles.setdefault(row["props"]["evidence_ref"], set()).add(row["type"])

    assert evidence_roles
    assert all(roles == {"PERFORMED", "FOR_SERVICE", "IN_REGION"} for roles in evidence_roles.values())


def test_full_projection_covers_twelve_snapshots_without_node_drift():
    projections = load_operational_projections(RELEASE)
    nodes, edges = _combined_projection_rows(projections)

    assert len(projections) == 12
    assert len({item.snapshot_id for item in projections}) == 12
    assert len(nodes) == 125
    assert len(edges) == 2997
    assert sum(key[0] == "Driver" for key in nodes) == 8
    assert sum(key[0] == "Trip" for key in nodes) == 80
    # The union contains branch-specific reported-measure assertions that do
    # not all coexist in any one snapshot.
    assert sum(key[0] == "Measurement" for key in nodes) == 18
