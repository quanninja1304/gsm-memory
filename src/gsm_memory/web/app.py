"""FastAPI application for GSM Conversational QA Web Interface with Local SQLite Database."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv()

# Ensure src in sys.path
SRC_DIR = Path(__file__).resolve().parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from gsm_memory.agent.conversational_pipeline import (
    DEFAULT_SNAPSHOT_ID,
    ConversationalPipeline,
)
from gsm_memory.db.models import (
    ChatMessageRecord,
    ChatSessionRecord,
    ContextMemoryItem,
    DatabaseStats,
    DriverRecord,
    TripRecord,
)
from gsm_memory.db.repository import LocalDatabaseRepository

app = FastAPI(
    title="GSM Memory QA Assistant API",
    description="Backend API for Taxi Xanh SM Conversational Q&A, Policy Guidance & Local Database",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global pipeline & DB repository
pipeline: ConversationalPipeline | None = None
db_repo = LocalDatabaseRepository()


def get_pipeline() -> ConversationalPipeline:
    global pipeline
    if pipeline is None:
        pipeline = ConversationalPipeline(db_repo=db_repo)
    return pipeline


# Driver master catalogue for demo UI fallback
KNOWN_DRIVERS = [
    {"code": "DRV-001", "name": "Nguyễn Văn An", "id": "99e70ebe-18cd-57a3-a036-cf0ff1989861"},
    {"code": "DRV-002", "name": "Trần Văn Bình", "id": "c499f934-bfe1-5509-a578-afb09cee357c"},
    {"code": "DRV-003", "name": "Lê Thị Chi", "id": "3b0b7be7-b553-5d99-9528-4a07ca4f1567"},
    {"code": "DRV-004", "name": "Phạm Quốc Dũng", "id": "cc916c6b-b168-5d8f-9023-075391ee4136"},
    {"code": "DRV-005", "name": "Hoàng Văn Minh (Đội 1)", "id": "58e68d69-f07f-580e-a4b6-91ef3801c5d7"},
    {"code": "DRV-006", "name": "Vũ Nhật Minh (Đội 2)", "id": "b8afff09-1200-5bcd-a594-6a647680f865"},
    {"code": "DRV-007", "name": "Đặng Hương Giang", "id": "bff953c4-63cd-58b5-82f3-d3ecac5ac17a"},
    {"code": "DRV-008", "name": "Bùi Thu Hà", "id": "122a3140-7c98-5136-a732-8a9566cb727d"},
]

DEFAULT_SCENARIOS = [
    {
        "id": "scenario_1",
        "title": "Câu hỏi thiếu thông tin",
        "tag": "Cần làm rõ",
        "tag_color": "warning",
        "query": "Kiểm tra xem tài xế có bị xử phạt do hủy chuyến xe không?",
        "desc": "Thử nghiệm cổng Clarification Gate: hệ thống tự động yêu cầu nhân viên bổ sung Mã tài xế và Mốc thời gian tra cứu.",
    },
    {
        "id": "scenario_2",
        "title": "Kiểm tra tài xế Bình (DRV-002)",
        "tag": "Đầy đủ thông tin",
        "tag_color": "success",
        "query": "Kiểm tra tài xế Bình (mã DRV-002), trong tháng 9/2026 có phát sinh hủy chuyến không, tỷ lệ hủy chuyến là bao nhiêu và đối soát theo quy tắc ứng xử GSM?",
        "desc": "Mở rộng nodes từ Neo4j KG, tính cancel_rate_30d = 20% và đối chiếu quy tắc ứng xử cho nhân viên quản lý.",
    },
    {
        "id": "scenario_3",
        "title": "Kiểm tra tài xế Dũng (DRV-004)",
        "tag": "Vận hành & Đồ thị",
        "tag_color": "info",
        "query": "Tra cứu tỷ lệ hủy chuyến trong tháng 9/2026 và lịch sử hoàn thành chuyến đi của tài xế Dũng (mã DRV-004)?",
        "desc": "Tra cứu KG chuyến đi và số liệu tính toán cho DRV-004.",
    },
    {
        "id": "scenario_4",
        "title": "Tra cứu Quy chế P154",
        "tag": "Chính sách GSM",
        "tag_color": "primary",
        "query": "Theo quy chế P154 của GSM, quy định về mức khoán doanh số tối thiểu tại Hà Nội và tỷ lệ truy thu được áp dụng thế nào?",
        "desc": "Truy xuất BM25 + Qdrant Dense từ kho văn bản quy chế GSM.",
    },
]


class ChatRequest(BaseModel):
    query: str
    session_id: str | None = None
    driver_id: str | None = None
    driver_mention: str | None = None
    time_mention: str | None = None
    snapshot_id: str | None = None
    policy_topics: list[str] | None = None


class CreateSessionRequest(BaseModel):
    title: str | None = None
    driver_id: str | None = None


class ContextMemoryUpdate(BaseModel):
    key: str
    value: str
    confidence: float = 1.0
    source: str = "manual"
    driver_id: str | None = None


@app.on_event("startup")
def startup_event() -> None:
    """Ensure database has data and eagerly warm up pipeline."""
    try:
        stats = db_repo.get_stats()
        if stats.drivers_count == 0 or stats.trips_count == 0:
            print("[Web Startup] Local database is empty, auto-seeding...")
            from gsm_memory.db.seed import seed_database
            seed_database(force_recreate=False)
            print("[Web Startup] Local database auto-seeded successfully!")
        else:
            print(f"[Web Startup] Local database ready: {stats.drivers_count} drivers, {stats.trips_count} trips, {stats.chat_sessions_count} sessions.")
    except Exception as e:
        print(f"[Web Startup DB Error] {e}")

    try:
        get_pipeline()
    except Exception as e:
        print(f"[Web Startup Pipeline Error] {e}")


@app.get("/api/health")
def api_health() -> dict[str, Any]:
    pipe = get_pipeline()
    stats = db_repo.get_stats()
    return {
        "status": "healthy",
        "release": "gsm-dev-core-0.2.2",
        "model": pipe.model_name,
        "bm25_chunks_count": len(pipe.chunks),
        "neo4j_connected": pipe.neo4j_driver is not None,
        "langfuse_connected": pipe.langfuse is not None,
        "default_snapshot_id": pipe.default_snapshot_id,
        "db": {
            "drivers_count": stats.drivers_count,
            "trips_count": stats.trips_count,
            "chat_sessions_count": stats.chat_sessions_count,
            "context_memories_count": stats.context_memories_count,
            "db_size_kb": round(stats.db_size_bytes / 1024, 1),
        },
    }


# =============================================================================
# LOCAL DATABASE API ENDPOINTS (DRIVERS, TRIPS, STATS)
# =============================================================================


@app.get("/api/db/stats")
def api_db_stats() -> dict[str, Any]:
    """Return comprehensive metrics of local SQLite database."""
    return db_repo.get_stats().model_dump()


@app.get("/api/db/snapshots")
def api_db_snapshots() -> list[dict[str, Any]]:
    """List all registered temporal snapshots."""
    snaps = db_repo.list_snapshots()
    return [s.model_dump() for s in snaps]


@app.get("/api/db/drivers")
def api_db_drivers(search: str | None = None) -> list[dict[str, Any]]:
    """List drivers with rich operational profiles and real-time metrics."""
    drivers = db_repo.get_drivers(search=search)
    return [d.model_dump() for d in drivers]


@app.get("/api/db/drivers/{driver_id}")
def api_db_driver_detail(driver_id: str) -> dict[str, Any]:
    """Get single driver profile."""
    d = db_repo.get_driver(driver_id)
    if not d:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài xế.")
    return d.model_dump()


@app.get("/api/db/drivers/{driver_id}/trips")
def api_db_driver_trips(
    driver_id: str,
    outcome: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[dict[str, Any]]:
    """List trips for a specific driver."""
    trips = db_repo.get_trips(driver_id=driver_id, outcome=outcome, limit=limit, offset=offset)
    return [t.model_dump() for t in trips]


@app.get("/api/db/trips")
def api_db_trips(
    driver_id: str | None = None,
    outcome: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[dict[str, Any]]:
    """List trips with optional filtering by driver or status."""
    trips = db_repo.get_trips(driver_id=driver_id, outcome=outcome, limit=limit, offset=offset)
    return [t.model_dump() for t in trips]


@app.get("/api/db/trips/{trip_id}")
def api_db_trip_detail(trip_id: str) -> dict[str, Any]:
    """Get detail for a specific trip."""
    t = db_repo.get_trip(trip_id)
    if not t:
        raise HTTPException(status_code=404, detail="Không tìm thấy chuyến đi.")
    return t.model_dump()


# =============================================================================
# CHAT SESSIONS & CONTEXT MEMORY ENDPOINTS
# =============================================================================


@app.get("/api/sessions")
def api_list_sessions(limit: int = Query(50, ge=1, le=100)) -> list[dict[str, Any]]:
    """List past chat sessions."""
    sessions = db_repo.list_sessions(limit=limit)
    return [s.model_dump() for s in sessions]


@app.post("/api/sessions")
def api_create_session(req: CreateSessionRequest) -> dict[str, Any]:
    """Create a new conversational session."""
    session_id = db_repo.create_session(title=req.title, driver_id=req.driver_id)
    session = db_repo.get_session(session_id)
    return session.model_dump() if session else {"session_id": session_id}


@app.get("/api/sessions/{session_id}")
def api_get_session(session_id: str) -> dict[str, Any]:
    """Retrieve full session detail including message log and context memory."""
    session = db_repo.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên hội thoại.")
    messages = db_repo.get_messages(session_id)
    context_map = db_repo.get_context(session_id)
    context_items = db_repo.get_context_items(session_id)
    return {
        "session": session.model_dump(),
        "messages": [m.model_dump() for m in messages],
        "context": context_map,
        "context_items": [ci.model_dump() for ci in context_items],
    }


@app.delete("/api/sessions/{session_id}")
def api_delete_session(session_id: str) -> dict[str, Any]:
    """Delete a chat session and all its messages/memory."""
    success = db_repo.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên hội thoại để xóa.")
    return {"success": True, "session_id": session_id}


@app.get("/api/sessions/{session_id}/context")
def api_get_session_context(session_id: str) -> dict[str, Any]:
    """View active conversational context memory for a session."""
    return {
        "context": db_repo.get_context(session_id),
        "items": [ci.model_dump() for ci in db_repo.get_context_items(session_id)],
    }


@app.post("/api/sessions/{session_id}/context")
def api_set_session_context(session_id: str, req: ContextMemoryUpdate) -> dict[str, Any]:
    """Manually update or insert a context memory slot."""
    db_repo.set_context_key(
        session_id=session_id,
        key=req.key,
        value=req.value,
        confidence=req.confidence,
        source=req.source,
        driver_id=req.driver_id,
    )
    return {
        "success": True,
        "context": db_repo.get_context(session_id),
    }


@app.delete("/api/sessions/{session_id}/context")
def api_clear_session_context(session_id: str) -> dict[str, Any]:
    """Reset context memory for a session."""
    db_repo.clear_session_context(session_id)
    return {"success": True, "message": "Đã làm mới bộ nhớ ngữ cảnh của phiên này."}


# Backward-compatible endpoints for UI
@app.get("/api/drivers")
def api_drivers() -> list[dict[str, Any]]:
    drivers = db_repo.get_drivers()
    if drivers:
        return [
            {
                "code": d.driver_code,
                "name": d.full_name,
                "id": d.driver_id,
                "phone": d.phone,
                "depot": d.depot_name,
                "vehicle": d.vehicle_model,
                "rating": d.rating_avg,
                "cancel_rate": d.cancellation_rate_30d,
                "trips_count": d.completed_trips_count + d.cancelled_trips_count,
            }
            for d in drivers
        ]
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


# =============================================================================
# CHAT EXECUTION WITH CONVERSATIONAL MEMORY & PERSISTENCE
# =============================================================================


@app.post("/api/chat")
def api_chat(req: ChatRequest) -> dict[str, Any]:
    user_query = req.query.strip() if req.query else ""
    if not user_query:
        raise HTTPException(status_code=400, detail="Nội dung câu hỏi không được để trống.")

    pipe = get_pipeline()
    t_start = time.perf_counter()

    # 1. Resolve or create chat session
    session_id = req.session_id
    if not session_id or not db_repo.get_session(session_id):
        # Auto-create session titled after the first question
        title_snippet = (user_query[:40] + "...") if len(user_query) > 40 else user_query
        session_id = db_repo.create_session(title=title_snippet, driver_id=req.driver_id)
    else:
        # Check if title was default, update if appropriate
        s = db_repo.get_session(session_id)
        if s and s.title in ("Cuộc trò chuyện mới", "New Chat") and s.messages_count == 0:
            title_snippet = (user_query[:40] + "...") if len(user_query) > 40 else user_query
            db_repo.update_session_title(session_id, title_snippet)

    # 2. Pull active context memory from SQLite
    stored_context = db_repo.get_context(session_id)

    # 3. Assemble execution context (Explicit request params override memory)
    context: dict[str, Any] = {"session_id": session_id}
    if stored_context.get("driver_id"):
        context["driver_id"] = stored_context["driver_id"]
    if stored_context.get("driver_mention"):
        context["driver_mention"] = stored_context["driver_mention"]
    if stored_context.get("time_scope"):
        context["time_mention"] = stored_context["time_scope"]
        context["has_time_scope"] = True
    if stored_context.get("snapshot_id"):
        context["snapshot_id"] = stored_context["snapshot_id"]
    if stored_context.get("policy_scope"):
        context["policy_scope"] = stored_context["policy_scope"]
    if stored_context.get("policy_topics"):
        context["policy_topics"] = stored_context["policy_topics"]

    # Explicit request params take top priority
    if req.driver_id:
        context["driver_id"] = req.driver_id
    if req.driver_mention:
        context["driver_mention"] = req.driver_mention
    if req.time_mention:
        context["time_mention"] = req.time_mention
        context["has_time_scope"] = True
    if req.snapshot_id:
        context["snapshot_id"] = req.snapshot_id
    if req.policy_topics:
        context["policy_topics"] = req.policy_topics

    # 4. Save User message to Database
    user_msg_id = db_repo.add_message(
        session_id=session_id,
        role="user",
        content=user_query,
    )

    # 5. Execute Conversational Pipeline with complete exception safety
    try:
        res = pipe.execute(user_query, context=context)
        latency_ms = round((time.perf_counter() - t_start) * 1000, 2)

        # 6. Format Subgraph & Plans for JSON serialization
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
            "policy_topics": getattr(res.slots, "policy_topics", []),
            "has_policy_target": getattr(res.slots, "has_policy_target", False),
            "missing_slots": res.slots.missing_slots,
        }

        query_plan_data = None
        if getattr(res, "query_plan", None):
            qp = res.query_plan
            query_plan_data = {
                "intent": qp.intent,
                "driver_id": qp.driver_id,
                "driver_mention": qp.driver_mention,
                "is_driver_ambiguous": qp.is_driver_ambiguous,
                "time_scope": qp.time_scope,
                "snapshot_id": qp.snapshot_id,
                "policy_scope": qp.policy_scope,
                "policy_topics": getattr(qp, "policy_topics", []),
                "modalities": qp.modalities,
                "missing_fields": qp.missing_fields,
                "clarification_reasons": qp.clarification_reasons,
                "reasoning": qp.reasoning,
            }

        # 7. Save Assistant message to Database
        bot_content = res.clarification_message if res.status == "NEEDS_CLARIFICATION" else res.answer
        bot_msg_id = db_repo.add_message(
            session_id=session_id,
            role="assistant",
            content=bot_content or "Không có nội dung phản hồi.",
            status=res.status,
            query_plan=query_plan_data,
            citations=res.citations,
            subgraph=subgraph_data,
            latency_ms=latency_ms,
        )

        # 8. Merge newly extracted slots & plan into Session Context Memory
        db_repo.merge_slots_and_plan(
            session_id=session_id,
            slots=slots_data,
            plan=query_plan_data or {},
        )

        return {
            "status": res.status,
            "session_id": session_id,
            "user_message_id": user_msg_id,
            "bot_message_id": bot_msg_id,
            "query": res.query,
            "query_plan": query_plan_data,
            "answer": res.answer,
            "clarification_message": res.clarification_message,
            "missing_slots": res.slots.missing_slots,
            "slots": slots_data,
            "citations": res.citations,
            "subgraph": subgraph_data,
            "trace_url": res.trace_url,
            "latency_ms": latency_ms,
            "active_context": db_repo.get_context(session_id),
        }
    except Exception as e:
        latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
        err_msg = f"Đã xảy ra lỗi trong quá trình xử lý: {str(e)}"
        print(f"[API Chat Error] {e}")
        bot_msg_id = db_repo.add_message(
            session_id=session_id,
            role="assistant",
            content=err_msg,
            status="ERROR",
            latency_ms=latency_ms,
        )
        return {
            "status": "ERROR",
            "session_id": session_id,
            "user_message_id": user_msg_id,
            "bot_message_id": bot_msg_id,
            "query": user_query,
            "answer": err_msg,
            "clarification_message": None,
            "missing_slots": [],
            "slots": {},
            "citations": [],
            "subgraph": None,
            "trace_url": None,
            "latency_ms": latency_ms,
            "active_context": db_repo.get_context(session_id),
        }


# Mount Static Files
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
