"""Demonstration script for GSM Conversational QA Pipeline with Langfuse Tracing."""

from __future__ import annotations

import os
import sys

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure src in sys.path
sys.path.insert(0, "src")

from gsm_memory.agent.conversational_pipeline import ConversationalPipeline


def main() -> None:
    print("=" * 70)
    print("🚀 KHỞI ĐỘNG GSM CONVERSATIONAL QA PIPELINE")
    print("=" * 70)

    pipeline = ConversationalPipeline()

    # -------------------------------------------------------------------------
    # TEST CASE 1: CÂU HỎI THIẾU THÔNG TIN (Cần làm rõ Tài xế và Thời điểm)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("📌 KỊCH BẢN 1: CÂU HỎI THIẾU THÔNG TIN")
    print("=" * 70)
    query_1 = "Tôi có bị phạt do hủy chuyến xe không?"
    print(f"👉 Người dùng hỏi: \"{query_1}\"\n")

    res_1 = pipeline.execute(query_1)
    print(f"🔹 Trạng thái phản hồi: {res_1.status}")
    if res_1.status == "NEEDS_CLARIFICATION":
        print(f"🔹 Câu hỏi làm rõ của hệ thống:\n{res_1.clarification_message}")
    if res_1.trace_url:
        print(f"\n🔗 Langfuse Trace URL (Kịch bản 1): {res_1.trace_url}")

    # -------------------------------------------------------------------------
    # TEST CASE 2: CÂU HỎI ĐẦY ĐỦ THÔNG TIN (Đầy đủ Tài xế DRV-002 & Tháng 9)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("📌 KỊCH BẢN 2: CÂU HỎI ĐẦY ĐỦ THÔNG TIN (TRA CỨU VẬN HÀNH & QUY CHẾ P154)")
    print("=" * 70)
    query_2 = (
        "Tôi là tài xế Bình (mã DRV-002), trong tháng 9/2026 theo quy chế P154 "
        "tôi có bị vi phạm tiêu chuẩn do hủy chuyến không, tỷ lệ hủy chuyến của tôi là bao nhiêu?"
    )
    print(f"👉 Người dùng hỏi: \"{query_2}\"\n")

    res_2 = pipeline.execute(query_2)
    print(f"🔹 Trạng thái phản hồi: {res_2.status}")
    if res_2.subgraph:
        print(f"🔹 Kết quả mở rộng đồ thị Subgraph từ Neo4j:")
        print(f"   - Seed ID: {res_2.subgraph.seed_id}")
        print(f"   - Số lượng node thu thập được: {len(res_2.subgraph.nodes)}")
        print(f"   - Số lượng cạnh duyệt qua: {len(res_2.subgraph.edges)}")
        node_summary = {}
        for n in res_2.subgraph.nodes:
            node_summary[n.label] = node_summary.get(n.label, 0) + 1
        print(f"   - Chi tiết các loại node: {node_summary}")

    print(f"\n🔹 Câu trả lời của AI Chuyên viên GSM:\n")
    print(res_2.answer)

    print(f"\n🔹 Danh sách trích dẫn bằng chứng (Citations):")
    for i, c in enumerate(res_2.citations, 1):
        print(f"   [{i}] {c['locator']}: {c['content'][:90]}...")

    if res_2.trace_url:
        print(f"\n🔗 Langfuse Trace URL (Kịch bản 2): {res_2.trace_url}")

    print("\n" + "=" * 70)
    print("✅ HOÀN TẤT KIỂM THỬ PIPELINE TRỰC TIẾP TRÊN LANGFUSE & NEO4J")
    print("=" * 70)


if __name__ == "__main__":
    main()
