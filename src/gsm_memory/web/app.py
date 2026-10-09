"""FastAPI application for GSM Conversational QA Web Interface."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

# Ensure src in sys.path
SRC_DIR = Path(__file__).resolve().parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from gsm_memory.agent.conversational_pipeline import (
    DEFAULT_SNAPSHOT_ID,
    DRIVER_CODE_MAP,
    ConversationalPipeline,
)

app = FastAPI(
    title="GSM Memory QA Assistant API",
    description="Backend API for Taxi Xanh SM Conversational Q&A & Policy Guidance",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global pipeline instance (lazy/startup init)
pipeline: ConversationalPipeline | None = None


def get_pipeline() -> ConversationalPipeline:
    global pipeline
    if pipeline is None:
        pipeline = ConversationalPipeline()
    return pipeline


# Driver master catalogue for demo UI
KNOWN_DRIVERS = [
    {"code": "DRV-001", "name": "Nguyễn Văn An", "id": "99e70ebe-18cd-57a3-a036-cf0ff1989861"},
    {"code": "DRV-002", "name": "Trần Văn Bình", "id": "c499f934-bfe1-5509-a578-afb09cee357c"},
    {"code": "DRV-003", "name": "Lê Thị Chi", "id": "3b0b7be7-b553-5d99-9528-4a07ca4f1567"},
    {"code": "DRV-004", "name": "Phạm Quốc Dũng", "id": "cc916c6b-b168-5d8f-9023-075391ee4136"},
    {"code": "DRV-005", "name": "Hoàng Văn Minh (Đội 1)", "id": "58e68d69-f07f-580e-a4b6-91ef3801c5d7"},
    {"code": "DRV-006", "name": "Vũ Nhật Minh (Đội 2)", "id": "b8afff09-1200-5bcd-a594-6a647680f865"},
    {"code": "DRV-007", "name": "Đặng Hương Giang", "id": "42c4b074-68f7-5f04-8ea7-a3f81e35a165"},
    {"code": "DRV-008", "name": "Bùi Thu Hà", "id": "964fb4ef-1bc7-5c21-b384-25e1a1c97a8a"},
]

DEFAULT_SCENARIOS = [
    {
        "id": "scenario_1",
        "title": "Câu hỏi thiếu thông tin",
        "tag": "Cần làm rõ",
        "tag_color": "warning",
        "query": "Tôi có bị phạt do hủy chuyến xe không?",
        "desc": "Thử nghiệm cổng Clarification Gate tự động yêu cầu bổ sung Mã tài xế và Mốc thời gian.",
    },
    {
        "id": "scenario_2",
        "title": "Tài xế Bình (DRV-002)",
        "tag": "Đầy đủ thông tin",
        "tag_color": "success",
        "query": "Tôi là tài xế Bình (mã DRV-002), trong tháng 9/2026 theo quy chế P154 tôi có bị vi phạm tiêu chuẩn do hủy chuyến không, tỷ lệ hủy chuyến của tôi là bao nhiêu?",
        "desc": "Mở rộng 16 nodes từ Neo4j KG, tính cancel_rate_30d = 20% và đối chiếu với P154.",
    },
    {
        "id": "scenario_3",
        "title": "Tài xế Dũng (DRV-004)",
        "tag": "Vận hành & Đồ thị",
        "tag_color": "info",
        "query": "Tôi là tài xế Dũng (mã DRV-004), cho tôi biết tỷ lệ hủy chuyến trong tháng 9/2026 và lịch sử hoàn thành chuyến đi?",
        "desc": "Tra cứu KG chuyến đi và số liệu tính toán cho DRV-004.",
    },
    {
        "id": "scenario_4",
        "title": "Tra cứu Quy chế P154",
        "tag": "Chính sách GSM",
        "tag_color": "primary",
        "query": "Theo quy chế P154 của GSM, tiêu chuẩn đánh giá sao và quy định tính điểm chuyến đi chưa đánh giá được quy định thế nào?",
        "desc": "Truy xuất BM25 thuần túy từ kho văn bản quy chế GSM.",
    },
]


class ChatRequest(BaseModel):
    query: str
    driver_id: str | None = None
    driver_mention: str | None = None
    time_mention: str | None = None
    snapshot_id: str | None = None


@app.on_event("startup")
def startup_event() -> None:
    # Eager load pipeline in background/startup
    try:
        get_pipeline()
    except Exception as e:
        print(f"[Web Startup Error] {e}")


@app.get("/api/health")
def api_health() -> dict[str, Any]:
    pipe = get_pipeline()
    return {
        "status": "healthy",
        "release": "gsm-dev-core-0.2.2",
        "model": pipe.model_name,
        "bm25_chunks_count": len(pipe.chunks),
        "neo4j_connected": pipe.neo4j_driver is not None,
        "langfuse_connected": pipe.langfuse is not None,
        "default_snapshot_id": pipe.default_snapshot_id,
    }


@app.get("/api/drivers")
def api_drivers() -> list[dict[str, Any]]:
    return KNOWN_DRIVERS


@app.get("/api/scenarios")
def api_scenarios() -> list[dict[str, Any]]:
    return DEFAULT_SCENARIOS



def serialize_val(val: Any) -> Any:
    if isinstance(val, dict):
        return {str(k): serialize_val(v) for k, v in val.items()}
    elif isinstance(val, (list, tuple, set)):
        return [serialize_val(v) for v in val]
    elif hasattr(val, "isoformat"):
        return val.isoformat()
    elif hasattr(val, "iso_format"):
        return val.iso_format()
    elif isinstance(val, (int, float, bool, str)) or val is None:
        return val
    return str(val)


@app.post("/api/chat")
def api_chat(req: ChatRequest) -> dict[str, Any]:
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="Nội dung câu hỏi không được để trống.")

    pipe = get_pipeline()
    t_start = time.perf_counter()

    context: dict[str, Any] = {}
    if req.driver_id:
        context["driver_id"] = req.driver_id
    if req.driver_mention:
        context["driver_mention"] = req.driver_mention
    if req.time_mention:
        context["time_mention"] = req.time_mention
        context["has_time_scope"] = True
    if req.snapshot_id:
        context["snapshot_id"] = req.snapshot_id

    try:
        res = pipe.execute(req.query.strip(), context=context)
    except Exception as e:
        latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
        return {
            "status": "ERROR",
            "query": req.query,
            "answer": f"Đã xảy ra lỗi trong quá trình xử lý: {str(e)}",
            "clarification_message": None,
            "missing_slots": [],
            "slots": {},
            "citations": [],
            "subgraph": None,
            "trace_url": None,
            "latency_ms": latency_ms,
        }

    latency_ms = round((time.perf_counter() - t_start) * 1000, 2)

    # Format Subgraph if present
    subgraph_data = None
    if res.subgraph:
        subgraph_data = {
            "seed_id": res.subgraph.seed_id,
            "snapshot_id": res.subgraph.snapshot_id,
            "nodes": [
                {
                    "id": n.id,
                    "label": n.label,
                    "name": n.name,
                    "props": serialize_val(n.props),
                }
                for n in res.subgraph.nodes
            ],
            "edges": [
                {
                    "start_id": e.start_id,
                    "end_id": e.end_id,
                    "rel_type": e.rel_type,
                    "props": serialize_val(e.props),
                }
                for e in res.subgraph.edges
            ],
            "node_count": len(res.subgraph.nodes),
            "edge_count": len(res.subgraph.edges),
        }

    slots_data = {
        "intent": res.slots.intent,
        "needs_driver": res.slots.needs_driver,
        "driver_id": res.slots.driver_id,
        "driver_mention": res.slots.driver_mention,
        "is_driver_ambiguous": res.slots.is_driver_ambiguous,
        "needs_time": res.slots.needs_time,
        "has_time_scope": res.slots.has_time_scope,
        "time_mention": res.slots.time_mention,
        "snapshot_id": res.slots.snapshot_id,
        "policy_mentions": res.slots.policy_mentions,
        "missing_slots": res.slots.missing_slots,
    }

    return {
        "status": res.status,
        "query": res.query,
        "answer": res.answer,
        "clarification_message": res.clarification_message,
        "missing_slots": res.slots.missing_slots,
        "slots": slots_data,
        "citations": res.citations,
        "subgraph": subgraph_data,
        "trace_url": res.trace_url,
        "latency_ms": latency_ms,
    }


# Mount Static Files
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
