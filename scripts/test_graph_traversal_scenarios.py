"""Comprehensive test script for Knowledge Graph Traversal scenarios:
1. Single-type traversal (focus='complaints', focus='incidents', focus='vehicle')
   with Qdrant dense vector embedding ranking (highest-scoring nodes).
2. Multi-type traversal (focus='complaints,incidents', target_node_types=['Complaint', 'Incident'], focus='incidents,vehicle').
3. Multi-hop ReAct pattern:
   - Hop 1: query_driver_graph for incidents.
   - Hop 2: query_driver_graph for vehicle & maintenance based on Hop 1 findings.
   - Hop 3: query_driver_graph for enforcement decisions.
"""
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

from gsm_memory.agent.conversational_pipeline import ConversationalPipeline
from gsm_memory.agent.tools import query_driver_graph
from gsm_memory.agent.react_agent import ReActAgent


def run_tests():
    print("=" * 80)
    print("🚀 KHỞI TẠO HỆ THỐNG CONVERSATIONAL PIPELINE & QDRANT RETRIEVER")
    print("=" * 80)
    pipeline = ConversationalPipeline()
    driver_an_id = "99e70ebe-18cd-57a3-a036-cf0ff1989861"  # Nguyễn Văn An (DRV-001)

    # -------------------------------------------------------------------------
    # KỊCH BẢN 1: DUYỆT 1 LOẠI (SINGLE-TYPE TRAVERSAL) VỚI QDRANT RANKING
    # -------------------------------------------------------------------------
    print("\n" + "#" * 80)
    print("📌 KỊCH BẢN 1: DUYỆT 1 LOẠI (SINGLE-TYPE) - LẤY NODE ĐIỂM CAO NHẤT TỪ QDRANT")
    print("#" * 80)

    # 1.1 Duyệt chỉ Complaints với semantic_query về điều hòa
    print("\n--- [1.1] Duyệt nhánh 'complaints' với semantic_query='điều hòa' ---")
    res_comp = query_driver_graph(
        pipeline=pipeline,
        driver_id=driver_an_id,
        focus="complaints",
        semantic_query="tài xế từ chối bật điều hòa giữa trưa hè tiết kiệm pin",
        limit=2,
    )
    print(f"Node count: {res_comp['node_count']} | Edge count: {res_comp['edge_count']}")
    print(f"Phân loại node: {res_comp['node_breakdown']}")
    complaint_nodes = [nd for nd in res_comp["node_details"] if nd["label"] == "Complaint"]
    assert len(complaint_nodes) > 0, "Phải tìm thấy ít nhất 1 node Complaint!"
    top_comp = complaint_nodes[0]
    print(f"-> Node điểm cao nhất: '{top_comp['name']}'")
    print(f"   Semantic Score: {top_comp.get('semantic_score')}")
    print(f"   Mô tả: {top_comp['description'][:100]}...")
    assert "điều hòa" in top_comp["name"].lower() or "điều hòa" in top_comp["description"].lower()
    print("✅ [1.1] Duyệt 1 loại 'complaints' thành công!")

    # 1.2 Duyệt chỉ Incidents với semantic_query về va quẹt lùi xe
    print("\n--- [1.2] Duyệt nhánh 'incidents' với semantic_query='va quẹt cản sau' ---")
    res_inc = query_driver_graph(
        pipeline=pipeline,
        driver_id=driver_an_id,
        focus="incidents",
        semantic_query="xe lùi vào ngõ bị va quẹt trầy xước cản sau",
        limit=2,
    )
    print(f"Node count: {res_inc['node_count']} | Edge count: {res_inc['edge_count']}")
    print(f"Phân loại node: {res_inc['node_breakdown']}")
    incident_nodes = [nd for nd in res_inc["node_details"] if nd["label"] == "Incident"]
    assert len(incident_nodes) > 0, "Phải tìm thấy ít nhất 1 node Incident!"
    top_inc = incident_nodes[0]
    print(f"-> Node điểm cao nhất: '{top_inc['name']}'")
    print(f"   Semantic Score: {top_inc.get('semantic_score')}")
    print(f"   Mô tả: {top_inc['description'][:100]}...")
    assert "va quẹt" in top_inc["name"].lower() or "cản sau" in top_inc["description"].lower()
    print("✅ [1.2] Duyệt 1 loại 'incidents' thành công!")

    # 1.3 Duyệt chỉ Vehicle
    print("\n--- [1.3] Duyệt nhánh 'vehicle' (Phương tiện & Bảo dưỡng) ---")
    res_veh = query_driver_graph(
        pipeline=pipeline,
        driver_id=driver_an_id,
        focus="vehicle",
    )
    print(f"Node count: {res_veh['node_count']} | Edge count: {res_veh['edge_count']}")
    print(f"Phân loại node: {res_veh['node_breakdown']}")
    veh_nodes = [nd for nd in res_veh["node_details"] if nd["label"] == "Vehicle"]
    assert len(veh_nodes) > 0, "Phải tìm thấy node Vehicle!"
    print(f"-> Xe vận hành: {veh_nodes[0]['name']} (Biển số: {veh_nodes[0]['props'].get('mock_plate') or veh_nodes[0]['props'].get('license_plate')})")
    print("✅ [1.3] Duyệt 1 loại 'vehicle' thành công!")

    # -------------------------------------------------------------------------
    # KỊCH BẢN 2: DUYỆT NHIỀU LOẠI (MULTI-TYPE TRAVERSAL)
    # -------------------------------------------------------------------------
    print("\n" + "#" * 80)
    print("📌 KỊCH BẢN 2: DUYỆT NHIỀU LOẠI (MULTI-TYPE TRAVERSAL)")
    print("#" * 80)

    # 2.1 Truyền focus dạng chuỗi kết hợp: "complaints,incidents"
    print("\n--- [2.1] Duyệt kết hợp focus='complaints,incidents' với semantic_query ---")
    res_multi_1 = query_driver_graph(
        pipeline=pipeline,
        driver_id=driver_an_id,
        focus="complaints,incidents",
        semantic_query="va chạm hoặc phàn nàn dịch vụ",
        limit=2,
    )
    print(f"Node count: {res_multi_1['node_count']} | Edge count: {res_multi_1['edge_count']}")
    print(f"Phân loại node: {res_multi_1['node_breakdown']}")
    labels_1 = set(res_multi_1["node_breakdown"].keys())
    assert "Complaint" in labels_1, "Phải có Complaint trong kết quả duyệt nhiều loại!"
    assert "Incident" in labels_1, "Phải có Incident trong kết quả duyệt nhiều loại!"
    print(f"-> Số Complaint: {res_multi_1['node_breakdown'].get('Complaint')}")
    print(f"-> Số Incident: {res_multi_1['node_breakdown'].get('Incident')}")
    print("✅ [2.1] Duyệt nhiều loại 'complaints,incidents' thành công!")

    # 2.2 Truyền target_node_types=["Complaint", "Incident"]
    print("\n--- [2.2] Duyệt bằng target_node_types=['Complaint', 'Incident'] ---")
    res_multi_2 = query_driver_graph(
        pipeline=pipeline,
        driver_id=driver_an_id,
        target_node_types=["Complaint", "Incident"],
        semantic_query="thái độ phục vụ hoặc sự cố xe",
        limit=2,
    )
    labels_2 = set(res_multi_2["node_breakdown"].keys())
    assert "Complaint" in labels_2, "Phải có Complaint khi truyền target_node_types!"
    assert "Incident" in labels_2, "Phải có Incident khi truyền target_node_types!"
    print(f"Phân loại node: {res_multi_2['node_breakdown']}")
    print("✅ [2.2] Duyệt nhiều loại qua target_node_types thành công!")

    # 2.3 Truyền focus="incidents,vehicle"
    print("\n--- [2.3] Duyệt kết hợp focus='incidents,vehicle' ---")
    res_multi_3 = query_driver_graph(
        pipeline=pipeline,
        driver_id=driver_an_id,
        focus="incidents,vehicle",
        limit=2,
    )
    labels_3 = set(res_multi_3["node_breakdown"].keys())
    assert "Incident" in labels_3, "Phải có Incident!"
    assert "Vehicle" in labels_3, "Phải có Vehicle!"
    print(f"Phân loại node: {res_multi_3['node_breakdown']}")
    print("✅ [2.3] Duyệt kết hợp 'incidents,vehicle' thành công!")

    # -------------------------------------------------------------------------
    # KỊCH BẢN 3: MULTI-HOP REACT TRAVERSAL
    # (Lần 1 có thông tin sự cố, lần 2 ReAct duyệt tiếp phương tiện & bảo dưỡng)
    # -------------------------------------------------------------------------
    print("\n" + "#" * 80)
    print("📌 KỊCH BẢN 3: MULTI-HOP REACT (DUYỆT LẦN 1 CÓ THÔNG TIN -> DUYỆT LẦN 2 ĐẦU VÀO KHÁC)")
    print("#" * 80)

    react_agent = pipeline.react_agent

    print("\n>>> Bước 1: ReAct gọi query_driver_graph lần 1 để tra cứu sự cố va chạm...")
    hop1_input = {
        "driver_identifier": "Nguyễn Văn An",
        "focus": "incidents",
        "semantic_query": "va chạm cản sau lùi xe",
        "limit": 2,
    }
    obs_1, cit_1 = react_agent.execute_tool("query_driver_graph", hop1_input)
    sig_1 = react_agent._get_tool_signature("query_driver_graph", hop1_input)
    print(f"Signature lần 1: {sig_1}")
    print(f"Kết quả lần 1: Tìm thấy {obs_1.get('node_count')} nodes, {len(obs_1.get('incidents', []))} sự cố.")
    incident_found = obs_1.get("incidents", [])[0]
    print(f"-> Sự cố phát hiện: {incident_found['name']} ({incident_found['incident_type']})")
    print(f"   Nội dung: {incident_found['description'][:90]}...")

    print("\n>>> Bước 2: ReAct nhận thấy có sự cố va chạm cản sau, quyết định gọi lần 2 tra cứu 'vehicle'...")
    hop2_input = {
        "driver_identifier": "Nguyễn Văn An",
        "focus": "vehicle",
    }
    sig_2 = react_agent._get_tool_signature("query_driver_graph", hop2_input)
    print(f"Signature lần 2: {sig_2}")
    assert sig_1 != sig_2, "Signature của 2 lần gọi phải khác nhau để tránh anti-loop!"
    
    obs_2, cit_2 = react_agent.execute_tool("query_driver_graph", hop2_input)
    print(f"Kết quả lần 2: Tìm thấy {obs_2.get('node_count')} nodes.")
    vehicle_details = [nd for nd in obs_2.get("node_details", []) if nd["label"] == "Vehicle"]
    maints = [nd for nd in obs_2.get("node_details", []) if nd["label"] == "MaintenanceEvent"]
    if vehicle_details:
        print(f"-> Thông tin phương tiện: {vehicle_details[0]['name']}, Thuộc tính: {vehicle_details[0]['props']}")
    if maints:
        print(f"-> Lịch sử bảo dưỡng: {', '.join(m['name'] for m in maints)}")

    print("\n>>> Bước 3: ReAct duyệt tiếp lần 3 để kiểm tra chế tài xử lý kỷ luật (enforcement)...")
    hop3_input = {
        "driver_identifier": "Nguyễn Văn An",
        "focus": "enforcement",
    }
    sig_3 = react_agent._get_tool_signature("query_driver_graph", hop3_input)
    print(f"Signature lần 3: {sig_3}")
    obs_3, cit_3 = react_agent.execute_tool("query_driver_graph", hop3_input)
    decisions = obs_3.get("decisions", [])
    findings = obs_3.get("findings", [])
    print(f"Kết quả lần 3: {len(decisions)} quyết định chế tài, {len(findings)} biên bản thẩm định.")
    for d in decisions[:2]:
        print(f"-> Quyết định: {d['name']} (Trạng thái: {d.get('status')})")

    print("\n" + "=" * 80)
    print("🎉 TẤT CẢ CÁC KỊCH BẢN DUYỆT ĐỒ THỊ VÀ MULTI-HOP ĐÃ VƯỢT QUA XUẤT SẮC!")
    print("=" * 80)


if __name__ == "__main__":
    run_tests()
