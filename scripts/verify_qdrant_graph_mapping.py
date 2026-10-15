import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

from gsm_memory.agent.conversational_pipeline import ConversationalPipeline

def main():
    print("🚀 Initializing ConversationalPipeline...")
    pipeline = ConversationalPipeline()

    driver_an_id = "99e70ebe-18cd-57a3-a036-cf0ff1989861"

    print("\n" + "="*70)
    print("TEST 1: get_directed_graph_for_driver with Semantic Query (Air Conditioner)")
    print("="*70)
    graph_ac = pipeline.expand_subgraph_directed(
        driver_id=driver_an_id,
        semantic_query="tài xế từ chối bật điều hòa giữa trưa hè tiết kiệm pin",
        focus="complaints",
        limit=2,
    )
    print(f"Graph nodes count: {len(graph_ac.nodes)}, edges count: {len(graph_ac.edges)}")
    for node in graph_ac.nodes:
        if node.label == "Complaint":
            print(f" - [Complaint] {node.name}")
            print(f"   Semantic Score: {node.props.get('semantic_score')}")
            print(f"   Category: {node.props.get('category')}")
            print(f"   Desc: {node.props.get('description')[:120]}...")

    print("\n" + "="*70)
    print("TEST 2: expand_subgraph_directed with Semantic Query (Using Phone while driving)")
    print("="*70)
    graph_phone = pipeline.expand_subgraph_directed(
        driver_id=driver_an_id,
        semantic_query="gọi điện thoại tai nghe bluetooth khi đang lái xe",
        focus="complaints",
        limit=2,
    )
    print(f"Graph nodes count: {len(graph_phone.nodes)}, edges count: {len(graph_phone.edges)}")
    for node in graph_phone.nodes:
        if node.label == "Complaint":
            print(f" - [Complaint] {node.name}")
            print(f"   Semantic Score: {node.props.get('semantic_score')}")
            print(f"   Category: {node.props.get('category')}")
            print(f"   Desc: {node.props.get('description')[:120]}...")

    print("\n" + "="*70)
    print("TEST 3: expand_subgraph_directed with Semantic Query (Vehicle Minor Collision Incident)")
    print("="*70)
    graph_inc = pipeline.expand_subgraph_directed(
        driver_id=driver_an_id,
        semantic_query="xe lùi vào ngõ bị va quẹt trầy xước cản sau",
        focus="incidents",
        limit=2,
    )
    print(f"Graph nodes count: {len(graph_inc.nodes)}, edges count: {len(graph_inc.edges)}")
    for node in graph_inc.nodes:
        if node.label == "Incident":
            print(f" - [Incident] {node.name}")
            print(f"   Semantic Score: {node.props.get('semantic_score')}")
            print(f"   Type: {node.props.get('incident_type')}")
            print(f"   Desc: {node.props.get('description')[:120]}...")

    print("\n" + "="*70)
    print("TEST 4: Driver Bình (DRV-002) - Detour complaint")
    print("="*70)
    driver_binh_id = "c499f934-bfe1-5509-a578-afb09cee357c"
    graph_binh = pipeline.expand_subgraph_directed(
        driver_id=driver_binh_id,
        semantic_query="tài xế tự ý đi đường vòng trễ giờ máy bay",
        focus="complaints",
        limit=2,
    )
    for node in graph_binh.nodes:
        if node.label == "Complaint":
            print(f" - [Complaint] {node.name}")
            print(f"   Semantic Score: {node.props.get('semantic_score')}")
            print(f"   Desc: {node.props.get('description')[:120]}...")

    print("\n✅ ALL SEMANTIC RETRIEVAL TESTS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
