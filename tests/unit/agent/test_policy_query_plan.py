"""Unit tests for Policy Query Planning, AI Understanding, and Clarification Gate."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gsm_memory.agent.conversational_pipeline import (
    DEFAULT_SNAPSHOT_ID,
    ConversationalPipeline,
    QueryPlan,
    SlotExtractionResult,
)
from gsm_memory.db.repository import LocalDatabaseRepository


@pytest.fixture
def dummy_pipeline(tmp_path: Path) -> ConversationalPipeline:
    repo = MagicMock()
    mock_driver = MagicMock()
    mock_driver.driver_id = "c499f934-bfe1-5509-a578-afb09cee357c"
    mock_driver.driver_code = "DRV-002"
    mock_driver.full_name = "Trần Văn Bình"
    mock_driver.depot_name = "Depot Hồ Chí Minh"
    mock_driver.vehicle_model = "VF e34"
    repo.get_driver_by_code.side_effect = lambda code: mock_driver if code == "DRV-002" else None
    repo.search_drivers_by_name.side_effect = lambda name: [mock_driver] if "bình" in name.lower() else []
    repo.find_driver_in_text.side_effect = lambda text: mock_driver if "bình" in str(text).lower() else None
    repo.get_driver.side_effect = lambda d_id: mock_driver if d_id == mock_driver.driver_id else None

    mock_snap = MagicMock()
    mock_snap.snapshot_id = DEFAULT_SNAPSHOT_ID
    mock_snap.label = "tháng 9/2026"
    mock_snap.known_as_of = "2026-09-17T12:00:00Z"

    def mock_find_snap(time_query=None, time_resolved=None):
        if time_resolved and "2026-08" in time_resolved:
            s_aug = MagicMock()
            s_aug.snapshot_id = "002366a5-e09e-5214-9fe4-c7fffeaf1396"
            s_aug.label = "Snapshot 8 (31/08/2026)"
            s_aug.known_as_of = "2026-08-31T23:59:59Z"
            return s_aug
        return mock_snap

    repo.find_snapshot_by_alias_or_time.side_effect = mock_find_snap
    repo.count_driver_trips.return_value = 10

    # Initialize pipeline with dummy or mocked heavy components to keep unit test fast
    pipe = ConversationalPipeline.__new__(ConversationalPipeline)
    pipe.release_dir = Path("data/gsm-dev-core-0.2.2")
    pipe.default_snapshot_id = DEFAULT_SNAPSHOT_ID
    pipe.benchmark_current_time = "2026-09-17T12:00:00Z"
    pipe.model_name = "test-model"
    pipe.openrouter_api_key = None
    pipe.nvidia_api_key = None
    pipe.nvidia_model = "test-model"
    pipe.ollama_base_url = "http://127.0.0.1:11434/v1"
    pipe.ollama_model = "qwen2.5:7b"
    pipe.openai_api_key = None
    pipe.openai_base_url = "https://api.openai.com/v1"
    pipe.openai_model = "gpt-4o-mini"
    pipe.llm_provider = "api"
    pipe.db_repo = repo
    pipe.chunks = []
    pipe.bm25_index = MagicMock()
    pipe.bm25_index.search.return_value = []
    pipe.doc_catalog_meta = {}
    pipe.hybrid_searcher = MagicMock()
    pipe.hybrid_searcher.search_hybrid.return_value = ([], {})
    pipe.neo4j_driver = None
    pipe.langfuse = None
    pipe._call_llm = MagicMock(return_value=(
        "Dựa trên các quy định đã được đối soát, mức khoán doanh số áp dụng theo P154.",
        "test-model",
        {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
    ))
    return pipe


def test_generic_policy_query_triggers_clarification(dummy_pipeline: ConversationalPipeline) -> None:
    """When user asks a vague/generic policy question without code or topic, clarification is required."""
    query = "Cho tôi hỏi về chính sách của công ty áp dụng thế nào?"
    plan = dummy_pipeline.plan_query(query)

    assert plan.intent == "POLICY_LOOKUP"
    assert "policy_target" in plan.missing_fields
    assert "Tên/Mã văn bản quy chế" in plan.clarification_reasons["policy_target"]
    assert "Chủ đề/Nội dung" in plan.clarification_reasons["policy_target"]

    msg = dummy_pipeline.build_clarification_message(plan)
    assert "Tên/Mã văn bản quy chế" in msg


def test_policy_query_with_specific_code_passes_gate(dummy_pipeline: ConversationalPipeline) -> None:
    """When user specifies a policy code like P154, gate passes without missing_fields."""
    query = "Theo quy chế P154 của GSM, mức khoán doanh số tại Hà Nội được quy định như thế nào?"
    plan = dummy_pipeline.plan_query(query)

    assert plan.intent == "POLICY_LOOKUP"
    assert "P154" in plan.policy_scope
    assert "policy_target" not in plan.missing_fields
    assert len(plan.missing_fields) == 0


def test_policy_query_with_specific_topic_passes_gate(dummy_pipeline: ConversationalPipeline) -> None:
    """When user specifies a policy topic like 'tỷ lệ hủy chuyến' without code, gate passes."""
    query = "Quy định về tỷ lệ hủy chuyến của GSM áp dụng cho tài xế như thế nào?"
    plan = dummy_pipeline.plan_query(query)

    assert plan.intent == "POLICY_LOOKUP"
    assert any("hủy chuyến" in t for t in plan.policy_topics)
    assert "policy_target" not in plan.missing_fields
    assert len(plan.missing_fields) == 0


def test_followup_resolution_with_policy_topic(dummy_pipeline: ConversationalPipeline) -> None:
    """When user first asks vaguely and then provides a topic in context, plan resolves."""
    # Turn 1: Vague query
    query1 = "Chính sách GSM quy định ra sao?"
    plan1 = dummy_pipeline.plan_query(query1)
    assert "policy_target" in plan1.missing_fields

    # Turn 2: User supplies topic
    context = {"policy_topics": ["mức khoán doanh số"]}
    query2 = "Về mức khoán doanh số"
    plan2 = dummy_pipeline.plan_query(query2, context=context)
    assert plan2.intent == "POLICY_LOOKUP"
    assert "policy_target" not in plan2.missing_fields
    assert "mức khoán doanh số" in plan2.policy_topics


def test_api_chat_policy_clarification_and_context(
    monkeypatch: pytest.MonkeyPatch, dummy_pipeline: ConversationalPipeline
) -> None:
    """End-to-end integration via FastAPI TestClient."""
    from fastapi.testclient import TestClient
    from gsm_memory.web.app import app
    import gsm_memory.web.app as web_app

    monkeypatch.setattr(web_app, "get_pipeline", lambda: dummy_pipeline)
    client = TestClient(app)

    # 1. Ask generic policy query
    resp1 = client.post("/api/chat", json={"query": "Cho tôi xem chính sách công ty"})
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["status"] == "NEEDS_CLARIFICATION"
    assert "policy_target" in data1["missing_slots"]
    session_id = data1["session_id"]

    # Check that context memory saved pending_clarification
    ctx1 = client.get(f"/api/sessions/{session_id}/context").json()["context"]
    assert "policy_target" in ctx1.get("pending_clarification", "")

    # 2. Reply with topic in the same session
    resp2 = client.post("/api/chat", json={"session_id": session_id, "query": "Quy chế về mức khoán doanh số P154"})
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["status"] == "ANSWERED"
    assert "P154" in (data2["query_plan"]["policy_scope"] or [])
    assert any("mức khoán" in t for t in (data2["query_plan"]["policy_topics"] or []))

    # Check context memory updated with policy_topics and policy_scope
    ctx2 = client.get(f"/api/sessions/{session_id}/context").json()["context"]
    assert "policy_topics" in ctx2
    assert "P154" in ctx2.get("policy_scope", "")


def test_api_chat_stream_sse_events(
    monkeypatch: pytest.MonkeyPatch, dummy_pipeline: ConversationalPipeline
) -> None:
    """Test POST /api/chat/stream yields real-time SSE events for plan, agent, and final results."""
    from fastapi.testclient import TestClient
    from gsm_memory.web.app import app
    import gsm_memory.web.app as web_app
    import json

    monkeypatch.setattr(web_app, "get_pipeline", lambda: dummy_pipeline)
    client = TestClient(app)

    # 1. Test clarification streaming
    resp = client.post("/api/chat/stream", json={"query": "Cho tôi xem chính sách công ty"})
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    events = []
    for line in resp.text.split("\n\n"):
        line = line.strip()
        if line.startswith("data:"):
            events.append(json.loads(line[5:].strip()))

    event_types = [e["type"] for e in events]
    assert "plan_start" in event_types
    assert "plan_done" in event_types
    assert "clarification" in event_types
    assert "done" in event_types

    # 2. Test query proceeding through pipeline
    resp2 = client.post(
        "/api/chat/stream",
        json={"query": "Kiểm tra tài xế Bình (DRV-002) trong tháng 9/2026 có vi phạm chính sách hủy chuyến không"},
    )
    assert resp2.status_code == 200
    events2 = []
    for line in resp2.text.split("\n\n"):
        line = line.strip()
        if line.startswith("data:"):
            events2.append(json.loads(line[5:].strip()))

    types2 = [e["type"] for e in events2]
    assert "plan_start" in types2
    assert "plan_done" in types2
    assert "agent_start" in types2
    assert "final_result" in types2
    assert "done" in types2

    final = [e for e in events2 if e["type"] == "final_result"][0]
    assert final["status"] == "ANSWERED"
    assert "answer" in final
    assert "plan" in final
    assert "query_plan" in final


def test_hybrid_compliance_without_policy_topic_triggers_clarification(dummy_pipeline: ConversationalPipeline) -> None:
    """When user asks to check driver compliance but does not specify a policy code or topic, clarification is required."""
    query = "Kiểm tra tài xế Bình (mã DRV-002), trong tháng 9/2026 có vi phạm chính sách không"
    plan = dummy_pipeline.plan_query(query)

    assert plan.intent == "HYBRID_REASONING"
    assert "policy_target" in plan.missing_fields
    assert "Quy chế nào" in plan.clarification_reasons["policy_target"]

    msg = dummy_pipeline.build_clarification_message(plan)
    assert "chính xác" in msg
    assert "Quy chế nào" in msg
    assert "1. Kết luận nghiệp vụ" not in msg


def test_hybrid_compliance_with_cancel_topic_answers_naturally(dummy_pipeline: ConversationalPipeline) -> None:
    """When user specifies driver, time, and topic 'hủy chuyến', query passes gate and produces natural grounded response."""
    query = "Kiểm tra tài xế Bình (mã DRV-002), trong tháng 9/2026 có vi phạm chính sách hủy chuyến không"
    plan = dummy_pipeline.plan_query(query)

    assert plan.intent == "HYBRID_REASONING"
    assert any("hủy chuyến" in t for t in plan.policy_topics)
    assert "policy_target" not in plan.missing_fields
    assert "driver_id" not in plan.missing_fields

    # Verify natural answer generation (no rigid 4-numbered sections)
    slots = dummy_pipeline.analyze_query(query)
    evidence = [
        {
            "source_kind": "computation",
            "citation_locator": "computation:cancel_rate_30d",
            "content": "cancel_rate_30d = 2/10 (20.0%)",
        },
        {
            "source_kind": "document",
            "citation_locator": "P221",
            "policy_alias": "P221",
            "policy_title": "QUY TẮC ỨNG XỬ GREEN SM BIKE",
            "content": "Tỷ lệ hủy chuyến hàng tuần cao hơn quy định bị áp dụng chế tài.",
        },
    ]
    ans = dummy_pipeline._build_deterministic_grounded_answer(query, slots, evidence)

    # Must NOT have rigid bureaucratic headings
    assert "1. Kết luận nghiệp vụ:" not in ans
    assert "2. Số liệu vận hành thực tế:" not in ans
    assert "3. Căn cứ quy chế GSM & Tiêu chuẩn vận hành:" not in ans
    assert "4. Đề xuất / Khuyến nghị" not in ans

    # Must contain natural informative sections
    assert "Dựa trên dữ liệu vận hành" in ans
    assert "Tình hình vận hành thực tế:" in ans
    assert "Đối chiếu quy chế & Kết luận:" in ans


def test_policy_lookup_isolates_driver_context_and_gives_policy_breakdown(dummy_pipeline: ConversationalPipeline) -> None:
    """When previous turn had driver in context, asking general policy question isolates driver context."""
    context = {
        "driver_id": "c499f934-bfe1-5509-a578-afb09cee357c",
        "driver_mention": "Trần Văn Bình (DRV-002)",
        "time_scope": "tháng 9/2026",
    }
    query = "các chính sách về vi phạm hủy chuyến"
    plan = dummy_pipeline.plan_query(query, context=context)

    # Must be recognized as pure POLICY_LOOKUP
    assert plan.intent == "POLICY_LOOKUP"
    assert plan.driver_id is None
    assert plan.driver_mention is None
    # Time is always available: auto-filled with latest snapshot when user does not specify time
    assert plan.time_scope is not None
    assert plan.modalities == ["document"]
    assert any("hủy chuyến" in t for t in plan.policy_topics)

    # Test grounded policy answer generation
    slots = SlotExtractionResult(
        intent="POLICY_LOOKUP",
        needs_driver=False,
        driver_id=None,
        driver_mention=None,
        needs_time=False,
        policy_topics=plan.policy_topics,
    )
    doc_evidence = [
        {
            "source_kind": "document",
            "citation_locator": "P001",
            "policy_alias": "P001",
            "policy_title": "Bộ Quy tắc Ứng xử GSM",
            "content": "Tài xế có hành vi hủy chuyến sai quy định hoặc tỷ lệ hủy vượt mức sẽ bị trừ điểm đánh giá hoặc tạm khóa tài khoản.",
        }
    ]
    ans = dummy_pipeline._build_deterministic_grounded_answer(query, slots, doc_evidence)

    # Must NOT contain previous driver report
    assert "Trần Văn Bình" not in ans
    assert "Tình hình vận hành thực tế:" not in ans
    assert "Lịch sử chuyến xe:" not in ans
    # Must contain policy breakdown
    assert "Quy định chung về hành vi hủy chuyến" in ans or "P001" in ans


def test_gather_multi_source_evidence_returns_up_to_5_chunks_preserving_code_and_title(dummy_pipeline: ConversationalPipeline) -> None:
    """Verify gather_multi_source_evidence retrieves up to 5 chunks and sends only chunk text with preserved policy code & title."""
    from gsm_memory.agent.conversational_pipeline import Subgraph

    mock_chunks = [
        {
            "evidence_id": f"doc-chunk_{i}",
            "chunk_id": f"chunk_{i}",
            "policy_alias": f"P{150 + i}",
            "policy_title": f"Quy chế số {i}",
            "chunk_text": f"Nội dung điều khoản số {i} về quy định vận hành GSM.",
            "score": 0.9 - (i * 0.1),
        }
        for i in range(1, 8)  # 7 chunks returned by searcher
    ]
    dummy_pipeline.hybrid_searcher.search_and_rerank = MagicMock(return_value=(mock_chunks, {}))

    slots = SlotExtractionResult(
        intent="POLICY_LOOKUP",
        needs_driver=False,
        needs_time=False,
        policy_topics=["quy tắc vận hành"],
    )
    subgraph = Subgraph(seed_id="test", snapshot_id=DEFAULT_SNAPSHOT_ID, nodes=[], edges=[])

    evidence = dummy_pipeline.gather_multi_source_evidence("chính sách vận hành", slots, subgraph)
    doc_evidence = [e for e in evidence if e.get("source_kind") == "document"]

    # Must contain exactly 5 chunks (top 5 out of 7)
    assert len(doc_evidence) == 5

    # Each chunk must preserve policy code, policy title, and only send chunk text
    for i, e in enumerate(doc_evidence, 1):
        assert e["policy_alias"] == f"P{150 + i}"
        assert e["policy_title"] == f"Quy chế số {i}"
        assert e["citation_locator"] == f"[P{150 + i}] Quy chế số {i}"
        assert e["full_content"] == f"Nội dung điều khoản số {i} về quy định vận hành GSM."
        assert f"P{150 + i}" in e["content"]
        assert f"Quy chế số {i}" in e["content"]


def test_case_1_driver_history_without_time_autofills_latest_snapshot_and_runs(dummy_pipeline: ConversationalPipeline) -> None:
    """Case 1: Asking about driver only (no time, no policy).
    - Intent is DRIVER_HISTORY.
    - Policy is NOT required (does not block on policy_target).
    - Time is auto-filled with latest snapshot.
    - Runs without blocking (missing_fields == []).
    """
    query = "Tài xế DRV-002 đã thực hiện bao nhiêu chuyến xe và tỷ lệ hủy ra sao?"
    plan = dummy_pipeline.plan_query(query)

    assert plan.intent == "DRIVER_HISTORY"
    assert plan.driver_id == "c499f934-bfe1-5509-a578-afb09cee357c"
    assert "DRV-002" in (plan.driver_mention or "")
    assert plan.time_scope is not None
    assert plan.snapshot_id is not None
    assert "policy_target" not in plan.missing_fields
    assert "time_scope" not in plan.missing_fields
    assert len(plan.missing_fields) == 0


def test_case_2_policy_lookup_without_time_autofills_latest_snapshot_and_runs(dummy_pipeline: ConversationalPipeline) -> None:
    """Case 2: Asking about policy only (no time, no driver).
    - Intent is POLICY_LOOKUP.
    - Driver is NOT required (does not block on driver_id).
    - Time is auto-filled with latest snapshot.
    - Runs without blocking (missing_fields == []).
    """
    query = "Quy chế P154 của GSM quy định về mức khoán và tỷ lệ chia sẻ doanh số như thế nào?"
    plan = dummy_pipeline.plan_query(query)

    assert plan.intent == "POLICY_LOOKUP"
    assert plan.driver_id is None
    assert "P154" in plan.policy_scope
    assert plan.time_scope is not None
    assert plan.snapshot_id is not None
    assert "driver_id" not in plan.missing_fields
    assert "time_scope" not in plan.missing_fields
    assert len(plan.missing_fields) == 0


def test_case_3_hybrid_reasoning_without_time_autofills_latest_snapshot_and_runs(dummy_pipeline: ConversationalPipeline) -> None:
    """Case 3: Asking about both driver and policy compliance (no time specified).
    - Intent is HYBRID_REASONING.
    - Driver is resolved.
    - Policy target is resolved from query.
    - Time is auto-filled with latest snapshot.
    - Runs without blocking (missing_fields == []).
    """
    query = "Kiểm tra tài xế DRV-002 có vi phạm quy định hủy chuyến không?"
    plan = dummy_pipeline.plan_query(query)

    assert plan.intent == "HYBRID_REASONING"
    assert plan.driver_id == "c499f934-bfe1-5509-a578-afb09cee357c"
    assert any("hủy chuyến" in t for t in plan.policy_topics)
    assert plan.time_scope is not None
    assert plan.snapshot_id is not None
    assert "driver_id" not in plan.missing_fields
    assert "policy_target" not in plan.missing_fields
    assert "time_scope" not in plan.missing_fields
    assert len(plan.missing_fields) == 0


def test_exact_date_extraction_with_typo_and_august_snapshot(dummy_pipeline: ConversationalPipeline) -> None:
    """Verify that a query mentioning '17/8/1026' preserves the exact day and resolves to August snapshot."""
    query = "kiểm tra xem tài xế bình trong tháng 17/8/1026 có vi phạm chính sách hủy chuyến không"
    plan = dummy_pipeline.plan_query(query)

    assert plan.intent == "HYBRID_REASONING"
    assert plan.driver_id == "c499f934-bfe1-5509-a578-afb09cee357c"
    # Must preserve exact day 17, not collapse to month only
    assert "17/08/2026" in str(plan.time_scope) or "17" in str(plan.time_scope)
    assert plan.time_resolved == "2026-08-17"
    # Must select August snapshot (Snapshot 8: 002366a5...), NOT September baseline (8b1426b6...)
    assert plan.snapshot_id == "002366a5-e09e-5214-9fe4-c7fffeaf1396"
    assert len(plan.missing_fields) == 0


def test_repository_august_month_snapshot_selection() -> None:
    """Verify that find_snapshot_by_alias_or_time selects August snapshot for 2026-08."""
    from gsm_memory.db.repository import LocalDatabaseRepository
    repo = LocalDatabaseRepository()
    snap = repo.find_snapshot_by_alias_or_time(time_resolved="2026-08")
    assert snap is not None
    # Must be Snapshot 8 (latest in August), not September baseline
    assert snap.snapshot_id == "002366a5-e09e-5214-9fe4-c7fffeaf1396"
    assert "2026-08" in snap.known_as_of


def test_greeting_intent_returns_clean_answered(dummy_pipeline: ConversationalPipeline) -> None:
    """Greetings should be recognized as GREETING intent and answered immediately with a helpful introduction."""
    greetings = ["Xin chào bạn", "Chào bot", "Hello", "Bạn có thể giúp gì cho tôi?"]
    for q in greetings:
        plan = dummy_pipeline.plan_query(q)
        assert plan.intent == "GREETING"
        assert len(plan.missing_fields) == 0

        res = dummy_pipeline.execute(q)
        assert res.status == "ANSWERED"
        assert "GSM" in res.answer
        assert "tài xế" in res.answer.lower() or "chính sách" in res.answer.lower()


def test_out_of_scope_guard_refuses_off_topic(dummy_pipeline: ConversationalPipeline) -> None:
    """Out-of-scope queries (weather, recipes, coding, politics) should be intercepted by domain guard."""
    off_topics = [
        "Thời tiết hôm nay tại Hà Nội thế nào?",
        "Chỉ cho tôi cách nấu món phở bò Nam Định ngon",
        "Viết giúp tôi một bài thơ về mùa thu lãng mạn",
        "Hướng dẫn lập trình ứng dụng React với TypeScript",
        "Giá vàng hôm nay tăng hay giảm bao nhiêu",
    ]
    for q in off_topics:
        plan = dummy_pipeline.plan_query(q)
        assert plan.intent == "OUT_OF_SCOPE"
        assert len(plan.missing_fields) == 0

        res = dummy_pipeline.execute(q)
        assert res.status == "ANSWERED"
        assert "chỉ hỗ trợ" in res.answer.lower() or "phạm vi" in res.answer.lower() or "gsm" in res.answer.lower()
        # Ensure it does not attempt to search policy or ask for missing driver
        assert "Tên/Mã văn bản quy chế" not in res.answer
        assert "Vui lòng cung cấp" not in res.answer


def test_in_scope_queries_not_blocked_by_guard(dummy_pipeline: ConversationalPipeline) -> None:
    """Legitimate GSM driver, policy, and compliance queries must not be falsely blocked by the domain guard."""
    valid_queries = [
        "Tài xế DRV-002 đã hoàn thành bao nhiêu chuyến xe?",
        "Tỷ lệ hủy chuyến của tài xế Bình trong tháng 9 ra sao?",
        "Quy chế P154 quy định mức khoán doanh số như thế nào?",
        "Chính sách thưởng doanh số của GSM áp dụng thế nào?",
        "Hành vi hủy cuốc xe sai quy định bị xử lý ra sao?",
    ]
    for q in valid_queries:
        plan = dummy_pipeline.plan_query(q)
        assert plan.intent != "OUT_OF_SCOPE"
        assert plan.intent in ("DRIVER_HISTORY", "POLICY_LOOKUP", "HYBRID_REASONING")







