"""Unit tests for directed Knowledge Graph traversal and offline semantic filtering."""
from unittest.mock import MagicMock
import pytest

from gsm_memory.agent.conversational_pipeline import (
    Subgraph,
    SubgraphNode,
    SubgraphEdge,
    calculate_text_relevance_score,
    strip_vietnamese_diacritics,
)
from gsm_memory.agent.tools import query_driver_graph


def test_strip_vietnamese_diacritics():
    assert strip_vietnamese_diacritics("Thái độ phục vụ không tốt") == "Thai do phuc vu khong tot"
    assert strip_vietnamese_diacritics("Đèn báo áp suất lốp xe") == "Den bao ap suat lop xe"
    assert strip_vietnamese_diacritics("Hà Nội") == "Ha Noi"


def test_calculate_text_relevance_score():
    query = "khách phàn nàn về thái độ thô lỗ cãi nhau"
    text1 = "Khách hàng phản ánh tài xế có thái độ thô lỗ, cãi vã lớn tiếng."
    text2 = "Xe bị thủng lốp trên đường cao tốc lúc 14h."
    text3 = ""

    score1 = calculate_text_relevance_score(query, text1)
    score2 = calculate_text_relevance_score(query, text2)
    score3 = calculate_text_relevance_score(query, text3)

    assert score1 > 0.3
    assert score2 == 0.0
    assert score3 == 0.0
    assert score1 > score2


def test_query_driver_graph_directed_location_paths():
    """Verify directed traversal on location focus returns paths to Region and Zone via Trip."""
    mock_pipeline = MagicMock()
    mock_subgraph = Subgraph(
        seed_id="drv-001",
        snapshot_id="snap-1",
        nodes=[
            SubgraphNode(id="drv-001", label="Driver", name="Nguyễn Văn An", props={"code": "DRV-001"}),
            SubgraphNode(id="reg-hn", label="Region", name="Hà Nội", props={"description": "Khu vực hoạt động miền Bắc"}),
            SubgraphNode(id="trip-01", label="Trip", name="Chuyến 01", props={"outcome": "completed", "pickup": "Hoàn Kiếm", "dropoff": "Cầu Giấy"}),
            SubgraphNode(id="zone-cg", label="Zone", name="Cầu Giấy", props={"description": "Khu vực quận Cầu Giấy"}),
        ],
        edges=[
            SubgraphEdge(start_id="drv-001", end_id="reg-hn", rel_type="OPERATES_IN", props={}),
            SubgraphEdge(start_id="drv-001", end_id="trip-01", rel_type="PERFORMED_TRIP", props={}),
            SubgraphEdge(start_id="trip-01", end_id="zone-cg", rel_type="DROPOFF_AT", props={}),
        ],
    )
    mock_pipeline.expand_subgraph_directed.return_value = mock_subgraph

    res = query_driver_graph(
        pipeline=mock_pipeline,
        driver_id="drv-001",
        focus="location",
        snapshot_id="snap-1",
    )

    assert res["node_count"] == 4
    assert res["edge_count"] == 3
    assert "Hà Nội" in res["regions"]
    assert "Cầu Giấy" in res["zones"]
    assert any("(Driver: Nguyễn Văn An) -[OPERATES_IN]-> (Region: Hà Nội)" in p for p in res["paths"])
    assert any("(Trip: Chuyến 01) -[DROPOFF_AT]-> (Zone: Cầu Giấy)" in p for p in res["paths"])
    assert any(nd["label"] == "Region" and "miền Bắc" in nd["description"] for nd in res["node_details"])
    assert "Mục tiêu: LOCATION" in res["summary"]


def test_query_driver_graph_directed_complaints_semantic_filter():
    """Verify directed traversal on complaints focus includes semantic scores and descriptions."""
    mock_pipeline = MagicMock()
    mock_subgraph = Subgraph(
        seed_id="drv-001",
        snapshot_id="snap-1",
        nodes=[
            SubgraphNode(id="drv-001", label="Driver", name="Nguyễn Văn An", props={"code": "DRV-001"}),
            SubgraphNode(
                id="comp-01",
                label="Complaint",
                name="Khiếu nại 01",
                props={
                    "category": "service_attitude",
                    "description": "Tài xế to tiếng với hành khách khi trời mưa",
                    "semantic_score": 0.85,
                },
            ),
            SubgraphNode(id="trip-01", label="Trip", name="Chuyến 01", props={"outcome": "completed"}),
        ],
        edges=[
            SubgraphEdge(start_id="drv-001", end_id="comp-01", rel_type="RECEIVED_COMPLAINT", props={}),
            SubgraphEdge(start_id="comp-01", end_id="trip-01", rel_type="ABOUT_TRIP", props={}),
        ],
    )
    mock_pipeline.expand_subgraph_directed.return_value = mock_subgraph

    res = query_driver_graph(
        pipeline=mock_pipeline,
        driver_id="drv-001",
        focus="complaints",
        semantic_query="to tiếng lớn tiếng",
        snapshot_id="snap-1",
    )

    assert len(res["complaints"]) == 1
    assert res["complaints"][0]["category"] == "service_attitude"
    assert any("(Driver: Nguyễn Văn An) -[RECEIVED_COMPLAINT]-> (Complaint: Khiếu nại 01)" in p for p in res["paths"])
    assert any("(Complaint: Khiếu nại 01) -[ABOUT_TRIP]-> (Trip: Chuyến 01)" in p for p in res["paths"])

    # Detail check
    comp_detail = next(nd for nd in res["node_details"] if nd["id"] == "comp-01")
    assert comp_detail["semantic_score"] == 0.85
    assert "to tiếng" in comp_detail["description"]
    assert "0.85" in res["summary"]


def test_query_driver_graph_multi_type_focus():
    """Verify query_driver_graph supports multi-type focus and target_node_types."""
    mock_pipeline = MagicMock()
    mock_subgraph = Subgraph(
        seed_id="drv-001",
        snapshot_id="snap-1",
        nodes=[
            SubgraphNode(id="drv-001", label="Driver", name="Nguyễn Văn An", props={"code": "DRV-001"}),
            SubgraphNode(id="comp-01", label="Complaint", name="Khiếu nại 01", props={"category": "attitude", "description": "Gắt gỏng"}),
            SubgraphNode(id="inc-01", label="Incident", name="Sự cố 01", props={"incident_type": "collision", "description": "Va quẹt"}),
        ],
        edges=[
            SubgraphEdge(start_id="drv-001", end_id="comp-01", rel_type="RECEIVED_COMPLAINT", props={}),
            SubgraphEdge(start_id="drv-001", end_id="inc-01", rel_type="HAS_INCIDENT", props={}),
        ],
    )
    mock_pipeline.expand_subgraph_directed.return_value = mock_subgraph

    res = query_driver_graph(
        pipeline=mock_pipeline,
        driver_id="drv-001",
        focus="complaints,incidents",
    )

    assert res["node_breakdown"]["Complaint"] == 1
    assert res["node_breakdown"]["Incident"] == 1
    assert len(res["complaints"]) == 1
    assert len(res["incidents"]) == 1
    assert any("(Driver: Nguyễn Văn An) -[RECEIVED_COMPLAINT]-> (Complaint: Khiếu nại 01)" in p for p in res["paths"])
    assert any("(Driver: Nguyễn Văn An) -[HAS_INCIDENT]-> (Incident: Sự cố 01)" in p for p in res["paths"])

