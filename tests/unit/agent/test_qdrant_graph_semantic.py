"""Unit tests for Qdrant operational node embedding retrieval and graph ranking."""
from unittest.mock import MagicMock
import pytest

from gsm_memory.retrieval.qdrant import QdrantOperationalHit, QdrantPolicyRetriever
from gsm_memory.agent.tools import get_driver_incidents_and_complaints
from gsm_memory.db.models import ComplaintRecord, DriverRecord, IncidentRecord


def test_qdrant_operational_hit_creation():
    hit = QdrantOperationalHit(
        node_id="comp-001",
        kind="complaint",
        node_type="Complaint",
        driver_id="drv-001",
        driver_name="Nguyễn Văn An",
        category="service_attitude",
        name="Phản ánh thái độ cộc lốc",
        description="Khách phản ánh tài xế nói lớn tiếng gắt gỏng khi hỏi đường.",
        score=0.88,
        event_time="2026-08-20T08:00:00Z",
        trip_id="trip-001",
    )
    assert hit.node_id == "comp-001"
    assert hit.kind == "complaint"
    assert hit.score == 0.88
    assert hit.category == "service_attitude"


def test_qdrant_retriever_search_operational_nodes_mocked():
    retriever = QdrantPolicyRetriever(url="http://mock-qdrant:6333", api_key="test-key")
    retriever._available = True

    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "result": [
            {
                "id": "point-1",
                "score": 0.854,
                "payload": {
                    "node_id": "c-101",
                    "kind": "complaint",
                    "node_type": "Complaint",
                    "driver_id": "drv-001",
                    "driver_name": "Nguyễn Văn An",
                    "category": "comfort_air_conditioner",
                    "name": "Từ chối bật điều hòa",
                    "description": "Tài xế không chịu bật điều hòa giữa trưa nắng.",
                    "event_time": "2026-08-20T12:00:00Z",
                    "trip_id": "t-101",
                },
            }
        ]
    }
    mock_session.post.return_value = mock_resp
    retriever._session = mock_session

    retriever.embedder = MagicMock()
    retriever.embedder.embed_query.return_value = [0.1] * 2048

    hits = retriever.search_operational_nodes(
        query="tài xế không bật điều hòa",
        driver_id="drv-001",
        kind="complaint",
        top_k=3,
    )

    assert len(hits) == 1
    assert hits[0].node_id == "c-101"
    assert hits[0].category == "comfort_air_conditioner"
    assert hits[0].score == 0.854

    # Verify session.post was called with payload filter
    called_json = mock_session.post.call_args[1]["json"]
    assert called_json["filter"]["must"] == [
        {"key": "kind", "match": {"value": "complaint"}},
        {"key": "driver_id", "match": {"value": "drv-001"}},
    ]


def test_get_driver_incidents_and_complaints_semantic_ranking():
    """Verify tool ranks complaints/incidents by Qdrant score when semantic_query is provided."""
    mock_repo = MagicMock()
    mock_driver = DriverRecord(
        driver_id="drv-001",
        driver_code="DRV-001",
        full_name="Nguyễn Văn An",
        email="an@gsm.vn",
        phone="0901234567",
        depot_name="Hub Ba Đình",
        vehicle_model="VF e34",
        license_plate="29E-001.01",
        onboarding_date="2024-01-01",
        rating_avg=4.8,
        region="Hà Nội",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
    )
    mock_repo.get_driver.return_value = mock_driver

    # 2 complaints
    c1 = ComplaintRecord(
        complaint_id="c-unrelated",
        driver_id="drv-001",
        trip_id="t-1",
        category="route_detour",
        event_time="2026-08-20T08:00:00Z",
        name="Đi đường vòng",
        description="Khách phản ánh tài xế đi đường vòng tránh trạm thu phí.",
        created_at="2026-08-20T08:00:00Z",
    )
    c2 = ComplaintRecord(
        complaint_id="c-relevant",
        driver_id="drv-001",
        trip_id="t-2",
        category="comfort_air_conditioner",
        event_time="2026-08-21T12:00:00Z",
        name="Từ chối bật điều hòa",
        description="Tài xế từ chối bật điều hòa giữa trưa hè nóng nực.",
        created_at="2026-08-21T12:00:00Z",
    )
    mock_repo.get_complaints.return_value = [c1, c2]
    mock_repo.get_incidents.return_value = []

    # Mock pipeline with Qdrant retriever
    mock_pipeline = MagicMock()
    mock_qdrant = MagicMock()
    mock_qdrant.is_available.return_value = True
    # Qdrant assigns higher score to c-relevant
    mock_qdrant.search_operational_nodes.return_value = [
        QdrantOperationalHit(
            node_id="c-relevant",
            kind="complaint",
            node_type="Complaint",
            driver_id="drv-001",
            driver_name="Nguyễn Văn An",
            category="comfort_air_conditioner",
            name="Từ chối bật điều hòa",
            description="Tài xế từ chối bật điều hòa giữa trưa hè nóng nực.",
            score=0.92,
        ),
        QdrantOperationalHit(
            node_id="c-unrelated",
            kind="complaint",
            node_type="Complaint",
            driver_id="drv-001",
            driver_name="Nguyễn Văn An",
            category="route_detour",
            name="Đi đường vòng",
            description="Khách phản ánh tài xế đi đường vòng tránh trạm thu phí.",
            score=0.21,
        ),
    ]
    mock_pipeline.qdrant_retriever = mock_qdrant

    res = get_driver_incidents_and_complaints(
        db_repo=mock_repo,
        driver_identifier="drv-001",
        pipeline=mock_pipeline,
        semantic_query="phàn nàn nóng nực không bật máy lạnh điều hòa",
        limit=2,
    )

    assert res["found"] is True
    assert len(res["complaints"]) == 2
    # First complaint should be c-relevant because it has higher semantic score
    assert res["complaints"][0]["complaint_id"] == "c-relevant"
    assert res["complaints"][0]["semantic_score"] == 0.92
    assert res["complaints"][1]["complaint_id"] == "c-unrelated"
    assert res["complaints"][1]["semantic_score"] == 0.21
