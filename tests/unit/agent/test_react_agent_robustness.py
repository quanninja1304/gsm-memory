import pytest
from unittest.mock import MagicMock
from gsm_memory.agent.react_agent import ReActAgent, ReActResult, ReActStep


def test_react_agent_strips_hallucinated_observation_and_preserves_clean_thought():
    """Verify that when an LLM auto-completes and hallucinates its own Observation:

    and subsequent Thought:, the engine strictly truncates before Observation:,
    extracts the true initial thought, and executes the genuine tool.
    """
    hallucinated_llm_response = (
        "Để xác định tình hình vận hành thực tế của tài xế Trần Văn Bình (DRV-002) "
        "và đối chiếu với quy chế, chúng tôi cần kiểm tra xem có quy định nào về tỷ lệ hủy chuyến 30 ngày trong hệ thống không.\n"
        "Action: search_gsm_policies\n"
        'Action Input: {"query": "tỷ lệ hủy chuyến 30 ngày", "policy_code": ""}\n'
        'Observation: {"tool": "search_gsm_policies", "found": true, "policies": ["P154: Tỷ lệ hủy chuyến 30 ngày không được vượt quá 20%", "P05: Tỷ lệ hủy chuyến 30 ngày không được vượt quá 15% cho tài xế mới"]}\n'
        "Dựa trên các Observation thực tế đã có ở trên, chúng tôi có thể đưa ra kết luận như sau:\n"
        "Thought: Tài xế Trần Văn Bình (DRV-002) có tỷ lệ hủy chuyến 30 ngày là 20.0%, vượt quá quy định của P154 là 20%"
    )

    final_llm_response = (
        "Thought: Đã có đủ số liệu thực tế.\n"
        "Final Answer:\n"
        "Dựa trên dữ liệu vận hành trong tháng 9/2026 và các quy định hiện hành của GSM, tôi đã kiểm tra thông tin cho Trần Văn Bình như sau:\n\n"
        "**1. Tình hình vận hành thực tế:**\n"
        "- Lịch sử chuyến xe: 5 chuyến ghi nhận, 1 chuyến bị hủy\n"
        "- Chỉ số vận hành: Tỷ lệ hủy chuyến 20.0%\n\n"
        "**2. Đối chiếu quy chế & Kết luận:**\n"
        "- Kết luận: Hiện tại chưa đủ căn cứ quy chế để xác định vi phạm\n"
        "- Căn cứ quy chế: Chưa có văn bản quy định cụ thể mức trần\n"
        "- Trích dẫn điều khoản liên quan: Không có điều khoản liên quan\n\n"
        "**3. Khuyến nghị cho Quản lý vận hành:**\n"
        "- Nhắc nhở tài xế chú ý nhận cuốc"
    )

    responses = [hallucinated_llm_response, final_llm_response]

    def mock_call_llm(messages, **kwargs):
        resp = responses.pop(0) if responses else final_llm_response
        return resp, "mock_model", {}

    agent = ReActAgent(call_llm_fn=mock_call_llm, max_iterations=3)

    # Mock execute_tool to return genuine search results (e.g. P001, P094)
    real_observation = {
        "tool": "search_gsm_policies",
        "policies": [
            {"chunk_id": "p001_c1", "policy_alias": "P001", "title": "Quy chế P001"},
            {"chunk_id": "p094_c1", "policy_alias": "P094", "title": "Quy định P094"},
        ]
    }
    real_citation = {
        "source_kind": "document",
        "citation_locator": "p001_c1",
        "policy_alias": "P001",
        "policy_title": "Quy chế P001",
    }
    agent.execute_tool = MagicMock(return_value=(real_observation, real_citation))

    query = "Kiểm tra tài xế Bình (DRV-002) tỷ lệ hủy chuyến 30 ngày"
    events = list(agent.run_stream(query))

    # Verify thoughts emitted
    thought_events = [e for e in events if e.get("type") == "thought"]
    assert len(thought_events) >= 1

    first_thought = thought_events[0]["thought"]
    # Critical assertions: The hallucinated P154 and P05 must NOT be in the thought
    assert "P154" not in first_thought
    assert "P05" not in first_thought
    assert "vượt quá quy định của P154" not in first_thought
    assert "Trần Văn Bình (DRV-002)" in first_thought

    # Verify tool execution occurred with clean inputs
    agent.execute_tool.assert_called_once_with(
        "search_gsm_policies",
        {"query": "tỷ lệ hủy chuyến 30 ngày", "policy_code": ""}
    )

    # Verify final result
    final_event = next(e for e in events if e.get("type") == "final_result")
    result: ReActResult = final_event["result"]
    assert len(result.steps) >= 1
    step1: ReActStep = result.steps[0]
    assert step1.action == "search_gsm_policies"
    assert "P154" not in step1.thought
    assert step1.observation == real_observation


def test_driver_tools_separation_of_concerns():
    """Verify that get_driver_profile, get_driver_trip_metrics, and get_cancelled_trips_detail

    are strictly decoupled and fulfill their individual responsibilities.
    """
    from gsm_memory.agent.tools import (
        get_driver_profile,
        get_driver_trip_metrics,
        get_cancelled_trips_detail,
    )
    from gsm_memory.db.models import DriverRecord, TripRecord

    mock_driver = DriverRecord(
        driver_id="drv-uuid-002",
        driver_code="DRV-002",
        full_name="Trần Văn Bình",
        phone="0901234567",
        email="binh@gsm.vn",
        depot_name="Đội 2 Tây Hồ",
        region="Hà Nội",
        service_type="Xanh SM Taxi",
        program="Xanh Limo",
        status="ACTIVE",
        vehicle_model="VinFast VF8",
        license_plate="29A-999.88",
        rating_avg=4.92,
        acceptance_rate=0.88,
        cancellation_rate_30d=0.20,
        completed_trips_count=4,
        cancelled_trips_count=1,
        created_at="2026-09-01T00:00:00Z",
        updated_at="2026-09-15T00:00:00Z",
    )

    mock_trips = [
        TripRecord(
            trip_id="trip-001",
            driver_id="drv-uuid-002",
            outcome="completed",
            fare_amount=150000,
            start_time="2026-09-15T08:00:00Z",
            pickup_address="Số 1 Tràng Tiền",
            dropoff_address="Sân bay Nội Bài",
            created_at="2026-09-15T08:00:00Z",
        ),
        TripRecord(
            trip_id="trip-002",
            driver_id="drv-uuid-002",
            outcome="cancelled",
            reason_code="driver_request",
            cancel_party="Tài xế yêu cầu",
            start_time="2026-09-15T09:30:00Z",
            pickup_address="Keangnam Hanoi Landmark",
            dropoff_address="Hồ Gươm",
            created_at="2026-09-15T09:30:00Z",
        ),
    ]

    mock_db_repo = MagicMock()
    mock_db_repo.get_driver.return_value = mock_driver
    mock_db_repo.get_trips.return_value = [mock_trips[1]]
    mock_db_repo.get_driver_snapshot_metrics.return_value = {
        "total_trips": 5,
        "completed_trips": 4,
        "cancelled_trips": 1,
        "cancel_rate": 0.20,
        "rating_avg": 4.92,
    }

    # 1. get_driver_profile MUST strictly return demographic/profile data without trip detail lists
    profile_res = get_driver_profile(db_repo=mock_db_repo, driver_identifier="DRV-002")
    assert profile_res["found"] is True
    assert profile_res["driver_code"] == "DRV-002"
    assert profile_res["full_name"] == "Trần Văn Bình"
    assert profile_res["vehicle_model"] == "VinFast VF8"
    assert profile_res["program"] == "Xanh Limo"
    assert "cancelled_details" not in profile_res

    # 2. get_driver_trip_metrics MUST return aggregate counts and cancellation rate
    metrics_res = get_driver_trip_metrics(
        db_repo=mock_db_repo,
        driver_identifier="DRV-002",
        snapshot_id="snap-test-1",
    )
    assert metrics_res["found"] is True
    assert metrics_res["total_trips_count"] == 5
    assert metrics_res["completed_trips_count"] == 4
    assert metrics_res["cancelled_trips_count"] == 1
    assert metrics_res["cancellation_rate_30d"] == 0.20
    assert metrics_res["cancel_rate_pct"] == 20.0

    # 3. get_cancelled_trips_detail MUST return specific cancellation list with reason_code
    canc_res = get_cancelled_trips_detail(
        db_repo=mock_db_repo,
        driver_identifier="DRV-002",
        snapshot_id="snap-test-1",
    )
    assert canc_res["found"] is True
    assert canc_res["cancelled_count"] == 1
    assert len(canc_res["cancelled_trips"]) == 1
    assert canc_res["cancelled_trips"][0]["reason_code"] == "driver_request"
    assert "Tài xế yêu cầu" in canc_res["cancelled_trips"][0]["cancel_party"]


def test_react_agent_executes_modular_driver_tools():
    """Verify that ReActAgent dispatches each decoupled tool and generates appropriate citations."""
    mock_db_repo = MagicMock()
    mock_db_repo.get_driver.return_value = MagicMock(
        driver_id="drv-uuid-007",
        driver_code="DRV-007",
        full_name="Nguyễn Văn Giang",
        phone="0912345678",
        email="giang@gsm.vn",
        depot_name="Đội 1 Long Biên",
        region="Hà Nội",
        service_type="Xanh SM Taxi",
        program="Xanh Limo",
        status="ACTIVE",
        vehicle_model="VinFast VF8",
        license_plate="29A-123.45",
        rating_avg=4.95,
        acceptance_rate=0.92,
        cancellation_rate_30d=0.0,
        completed_trips_count=10,
        cancelled_trips_count=0,
    )
    mock_db_repo.get_trips.return_value = []
    mock_db_repo.get_driver_snapshot_metrics.return_value = {
        "total_trips": 10,
        "completed_trips": 10,
        "cancelled_trips": 0,
        "cancel_rate": 0.0,
        "rating_avg": 4.95,
    }

    agent = ReActAgent(call_llm_fn=MagicMock(), db_repo=mock_db_repo)

    # Test executing get_driver_profile
    res_prof, cit_prof = agent.execute_tool("get_driver_profile", {"driver_identifier": "DRV-007"})
    assert res_prof["found"] is True
    assert cit_prof["source_kind"] == "database"
    assert "entity:driver:DRV-007" in cit_prof["citation_locator"]

    # Test executing get_driver_trip_metrics
    res_met, cit_met = agent.execute_tool("get_driver_trip_metrics", {"driver_identifier": "DRV-007", "snapshot_id": "snap-1"})
    assert res_met["found"] is True
    assert res_met["total_trips_count"] == 10
    assert cit_met["source_kind"] == "kg_subgraph"

    # Test executing get_cancelled_trips_detail
    res_canc, cit_canc = agent.execute_tool("get_cancelled_trips_detail", {"driver_identifier": "DRV-007"})
    assert res_canc["found"] is True
    assert res_canc["cancelled_count"] == 0
    assert cit_canc["source_kind"] == "kg_subgraph"


def test_computation_tools_decoupled_from_hardcoded_policies():
    """Verify that arithmetic tools do not hardcode specific policy thresholds

    and properly handle both pure calculation and dynamic threshold evaluation.
    """
    from gsm_memory.agent.tools import (
        calculate_acceptance_rate,
        calculate_completion_rate,
        evaluate_daily_revenue,
        evaluate_rating_condition,
        get_driver_daily_stats,
    )

    # 1. calculate_acceptance_rate: pure calculation without threshold
    ar_pure = calculate_acceptance_rate(offered_trips=20, accepted_trips=17)
    assert ar_pure["rate_fraction"] == "17/20"
    assert ar_pure["rate_pct"] == 85.0
    assert ar_pure["passed"] is None

    # calculate_acceptance_rate: with dynamic threshold
    ar_eval_pass = calculate_acceptance_rate(offered_trips=20, accepted_trips=17, threshold_pct=80.0)
    assert ar_eval_pass["passed"] is True
    ar_eval_fail = calculate_acceptance_rate(offered_trips=20, accepted_trips=17, threshold_pct=90.0)
    assert ar_eval_fail["passed"] is False

    # 2. calculate_completion_rate: pure calculation without threshold
    cr_pure = calculate_completion_rate(accepted_trips=20, completed_trips=18)
    assert cr_pure["rate_fraction"] == "9/10"
    assert cr_pure["rate_pct"] == 90.0
    assert cr_pure["passed"] is None

    # calculate_completion_rate: with dynamic threshold
    cr_eval_pass = calculate_completion_rate(accepted_trips=20, completed_trips=18, threshold_pct=85.0)
    assert cr_eval_pass["passed"] is True
    cr_eval_fail = calculate_completion_rate(accepted_trips=20, completed_trips=18, threshold_pct=95.0)
    assert cr_eval_fail["passed"] is False

    # 3. evaluate_daily_revenue: pure info vs dynamic quota check
    rev_pure = evaluate_daily_revenue(revenue_vnd=850000)
    assert rev_pure["passed"] is None
    assert rev_pure["diff_vnd"] is None

    rev_pass = evaluate_daily_revenue(revenue_vnd=850000, threshold_vnd=800000, date="2026-09-15")
    assert rev_pass["passed"] is True
    assert rev_pass["diff_vnd"] == 50000

    rev_fail = evaluate_daily_revenue(revenue_vnd=850000, threshold_vnd=1000000, date="2026-09-15")
    assert rev_fail["passed"] is False
    assert rev_fail["diff_vnd"] == -150000

    # 4. evaluate_rating_condition: decoupled from hardcoded 4.85
    # When no threshold is passed: returns pure rating info without pass/fail judgment
    rate_info = evaluate_rating_condition(rating_stars=4.82)
    assert rate_info["rating_stars"] == 4.82
    assert rate_info["threshold"] is None
    assert rate_info["passed"] is None

    # When dynamic threshold is passed (e.g. 4.80 -> pass, 4.85 -> fail)
    rate_eval_pass = evaluate_rating_condition(rating_stars=4.82, threshold=4.80, operator=">=")
    assert rate_eval_pass["passed"] is True
    rate_eval_fail = evaluate_rating_condition(rating_stars=4.82, threshold=4.85, operator=">")
    assert rate_eval_fail["passed"] is False

    # 5. Decomposed attendance & work standard verification:
    # Tools do not hardcode composite attendance verdicts.
    # Data retrieval tool (get_driver_daily_stats) extracts operational numbers,
    # and calculation tools compute deterministic rates.
    mock_db = MagicMock()
    mock_db.get_driver.return_value = MagicMock(
        driver_id="DRV-001",
        driver_code="DRV-001",
        full_name="Nguyễn Văn A",
        acceptance_rate=0.90,
    )
    mock_trip_comp = MagicMock(outcome="completed", fare_amount=100000, start_time="2026-09-15T08:00:00Z")
    mock_trip_canc = MagicMock(outcome="cancelled", fare_amount=0, start_time="2026-09-15T09:00:00Z")
    mock_db.get_trips.return_value = [mock_trip_comp] * 8 + [mock_trip_canc] * 1

    daily_stats = get_driver_daily_stats(db_repo=mock_db, driver_id="DRV-001", date="2026-09-15")
    assert daily_stats["trips_count"] == 9
    assert daily_stats["completed_trips"] == 8
    assert daily_stats["cancelled_trips"] == 1
    assert daily_stats["total_revenue_vnd"] == 800000
    assert daily_stats["offered_trips"] == 10
    assert daily_stats["accepted_trips"] == 9

    # Pure calculation tools compute fractions and percentages without hardcoding attendance verdict
    ar_calc = calculate_acceptance_rate(offered_trips=daily_stats["offered_trips"], accepted_trips=daily_stats["accepted_trips"])
    assert ar_calc["rate_fraction"] == "9/10"
    assert ar_calc["rate_pct"] == 90.0

    cr_calc = calculate_completion_rate(accepted_trips=daily_stats["accepted_trips"], completed_trips=daily_stats["completed_trips"])
    assert cr_calc["rate_fraction"] == "8/9"
    assert cr_calc["rate_pct"] == 88.89


def test_query_driver_graph_extracts_nodes_and_edges():
    """Verify that query_driver_graph extracts rich nodes, edges, and breakdowns."""
    from gsm_memory.agent.tools import query_driver_graph
    from gsm_memory.agent.conversational_pipeline import Subgraph, SubgraphNode, SubgraphEdge

    mock_pipeline = MagicMock()
    mock_subgraph = Subgraph(
        seed_id="drv-002",
        snapshot_id="snap-1",
        nodes=[
            SubgraphNode(id="drv-002", label="Driver", name="Trần Văn Bình", props={}),
            SubgraphNode(id="fleet-01", label="Fleet", name="Đội 2 Tây Hồ", props={}),
            SubgraphNode(id="trip-01", label="Trip", name="Chuyến 1", props={"outcome": "completed"}),
            SubgraphNode(id="trip-02", label="Trip", name="Chuyến 2", props={"outcome": "cancelled"}),
        ],
        edges=[
            SubgraphEdge(start_id="drv-002", end_id="fleet-01", rel_type="ASSIGNED_TO_FLEET", props={}),
            SubgraphEdge(start_id="drv-002", end_id="trip-01", rel_type="PERFORMED_TRIP", props={}),
            SubgraphEdge(start_id="drv-002", end_id="trip-02", rel_type="PERFORMED_TRIP", props={}),
        ]
    )
    mock_pipeline.expand_subgraph_bfs.return_value = mock_subgraph

    res = query_driver_graph(pipeline=mock_pipeline, driver_id="drv-002", snapshot_id="snap-1")
    assert res["node_count"] == 4
    assert res["edge_count"] == 3
    assert res["node_breakdown"]["Driver"] == 1
    assert res["node_breakdown"]["Trip"] == 2
    assert res["node_breakdown"]["Fleet"] == 1
    assert res["edge_breakdown"]["PERFORMED_TRIP"] == 2
    assert res["edge_breakdown"]["ASSIGNED_TO_FLEET"] == 1
    assert res["fleet"] == "Đội 2 Tây Hồ"
    assert res["trips_completed"] == 1
    assert res["trips_cancelled"] == 1
    assert mock_pipeline.last_subgraph == mock_subgraph


def test_react_agent_guards_force_cancel_rate_tool_calling():
    """Verify that ReActAgent guards prevent early final answer without calling calculate_cancel_rate."""
    # Step 1: LLM prematurely gives final answer without calling calculate_cancel_rate
    early_llm_response = (
        "Thought: Tôi đã biết tỷ lệ hủy chuyến là 20%.\n"
        "Final Answer: Tỷ lệ hủy chuyến là 20%."
    )
    # Step 2: LLM obeys observation guard and calls calculate_cancel_rate
    action_llm_response = (
        "Thought: Cần gọi calculate_cancel_rate để tính toán số học chuẩn xác.\n"
        "Action: calculate_cancel_rate\n"
        'Action Input: {"cancelled_trips": 2, "total_trips": 10}'
    )
    # Step 3: LLM finalizes after observation
    final_llm_response = (
        "Thought: Đã có kết quả tính toán chính xác.\n"
        "Final Answer:\n"
        "Dựa trên dữ liệu vận hành trong tháng 9/2026, tôi đã kiểm tra thông tin cho Bình như sau:\n\n"
        "**1. Tình hình vận hành thực tế:**\n"
        "- Lịch sử chuyến xe: 10 chuyến (8 hoàn thành, 2 hủy)\n"
        "- Chỉ số vận hành: Tỷ lệ hủy chuyến 20.0%\n\n"
        "**2. Đối chiếu quy chế & Kết luận:**\n"
        "- Kết luận: Không phát hiện vi phạm\n"
        "- Căn cứ quy chế: Quy chế GSM\n"
        "- Trích dẫn điều khoản liên quan: Không có\n\n"
        "**3. Khuyến nghị cho Quản lý vận hành:**\n"
        "- Theo dõi thường xuyên"
    )

    responses = [early_llm_response, action_llm_response, final_llm_response]

    def mock_call_llm(messages, **kwargs):
        return responses.pop(0), "mock_model", {}

    agent = ReActAgent(call_llm_fn=mock_call_llm, max_iterations=4)
    query = "Tính tỷ lệ hủy chuyến của tài xế Bình"
    events = list(agent.run_stream(query))

    final_event = next(e for e in events if e.get("type") == "final_result")
    result: ReActResult = final_event["result"]

    # Verify calculate_cancel_rate was executed
    assert any(s.action == "calculate_cancel_rate" for s in result.steps)
    # Verify citation computation:cancel_rate_30d was generated
    assert any("computation:cancel_rate_30d" in c.get("citation_locator", "") for c in result.citations)


def test_agent_attendance_evaluation_workflow_decomposed():
    """Verify that ReActAgent decomposes attendance verification into:
    1. search_gsm_policies (to find policy thresholds),
    2. get_driver_daily_stats (to retrieve actual trips/revenue),
    3. calculate_acceptance_rate / calculate_completion_rate (pure arithmetic),
    and the Agent compares data against policy in its reasoning, without evaluate_attendance_standard.
    """
    from gsm_memory.agent.tools import TOOL_SCHEMAS

    # Assert evaluate_attendance_standard is completely absent from available tool schemas
    tool_names = [t["name"] for t in TOOL_SCHEMAS]
    assert "evaluate_attendance_standard" not in tool_names

    # Multi-step LLM script representing autonomous ReAct reasoning:
    step1_search_policy = (
        "Thought: Để kiểm tra tiêu chuẩn chấm công của tài xế DRV-002 ngày 2026-09-15, "
        "trước tiên cần tra cứu quy chế để biết các tiêu chuẩn và ngưỡng định mức bắt buộc.\n"
        "Action: search_gsm_policies\n"
        'Action Input: {"query": "tiêu chuẩn chấm công", "policy_code": "P154"}'
    )
    step2_get_daily_stats = (
        "Thought: Đã nắm được quy định: AR >= 85%, CR >= 80%, Doanh số >= 720.000 VNĐ. "
        "Bây giờ cần lấy số liệu vận hành thực tế của DRV-002 ngày 2026-09-15.\n"
        "Action: get_driver_daily_stats\n"
        'Action Input: {"driver_id": "DRV-002", "date": "2026-09-15"}'
    )
    step3_calc_ar = (
        "Thought: Dữ liệu thực tế ngày 2026-09-15: phát 10 cuốc, nhận 9 cuốc, hoàn thành 9 cuốc, doanh số 850.000 VNĐ. "
        "Cần gọi calculate_acceptance_rate để tính tỷ lệ nhận cuốc chuẩn xác.\n"
        "Action: calculate_acceptance_rate\n"
        'Action Input: {"offered_trips": 10, "accepted_trips": 9}'
    )
    step4_final_answer = (
        "Thought: Đã có đủ số liệu thực tế và kết quả tính toán số học chuẩn xác. "
        "Bây giờ tôi đối chiếu từng tiêu chí với quy chế P154:\n"
        "- Tỷ lệ nhận cuốc AR: 90.0% >= 85.0% (Đạt tiêu chuẩn).\n"
        "- Tỷ lệ hoàn thành CR: 100.0% >= 80.0% (Đạt tiêu chuẩn).\n"
        "- Doanh số ngày: 850.000 VNĐ >= 720.000 VNĐ (Đạt định mức).\n"
        "Kết luận: Tài xế đạt tiêu chuẩn chấm công ngày 2026-09-15.\n"
        "Final Answer:\n"
        "Dựa trên dữ liệu vận hành trong **ngày 2026-09-15** và các quy định hiện hành của GSM, tôi đã kiểm tra thông tin cho **Trần Văn Bình (DRV-002)** như sau:\n\n"
        "**1. Tình hình vận hành thực tế:**\n"
        "- **Lịch sử chuyến xe:** 9 cuốc nhận, 9 cuốc hoàn thành, 0 chuyến bị hủy, doanh số 850.000 VNĐ.\n"
        "- **Chỉ số vận hành:** Tỷ lệ nhận cuốc AR = 90.0% (9/10), Tỷ lệ hoàn thành CR = 100.0% (9/9).\n\n"
        "**2. Đối chiếu quy chế & Kết luận:**\n"
        "- **Kết luận:** Đạt đầy đủ tiêu chuẩn chấm công theo quy chế GSM.\n"
        "- **Căn cứ quy chế:** Quy chế P154 về Tiêu chuẩn vận hành và chấm công.\n"
        "- **Trích dẫn điều khoản liên quan:** Yêu cầu AR >= 85%, CR >= 80%, doanh số >= 720.000 VNĐ.\n\n"
        "**3. Khuyến nghị cho Quản lý vận hành:**\n"
        "- Duy trì phong độ hoạt động tích cực của tài xế."
    )

    responses = [step1_search_policy, step2_get_daily_stats, step3_calc_ar, step4_final_answer]

    def mock_call_llm(messages, **kwargs):
        return responses.pop(0), "mock_model", {}

    mock_db = MagicMock()
    mock_db.get_driver.return_value = MagicMock(
        driver_id="drv-uuid-002",
        driver_code="DRV-002",
        full_name="Trần Văn Bình",
        acceptance_rate=0.90,
    )
    mock_trip = MagicMock(outcome="completed", fare_amount=94444, start_time="2026-09-15T08:00:00Z")
    mock_db.get_trips.return_value = [mock_trip] * 9

    mock_pipeline = MagicMock()
    mock_pipeline.bm25_index.search.return_value = []

    agent = ReActAgent(call_llm_fn=mock_call_llm, db_repo=mock_db, pipeline_ref=mock_pipeline, max_iterations=5)
    query = "Kiểm tra xem tài xế DRV-002 ngày 2026-09-15 có đạt tiêu chuẩn chấm công không?"
    events = list(agent.run_stream(query))

    final_event = next(e for e in events if e.get("type") == "final_result")
    result: ReActResult = final_event["result"]

    actions_executed = [s.action for s in result.steps]
    assert "search_gsm_policies" in actions_executed
    assert "get_driver_daily_stats" in actions_executed
    assert "calculate_acceptance_rate" in actions_executed
    assert "evaluate_attendance_standard" not in actions_executed
    assert "Đạt đầy đủ tiêu chuẩn chấm công" in result.final_answer


def test_react_agent_multi_tool_execution_in_single_turn():
    """Verify that ReActAgent can parse and execute multiple tools in a single iteration."""
    multi_tool_response = (
        "Thought: Tôi cần kiểm tra quy chế và lấy số liệu của tài xế cùng lúc trong bước 1.\n"
        "Action: search_gsm_policies\n"
        'Action Input: {"query": "tiêu chuẩn vận hành", "policy_code": "P154"}\n'
        "Action: get_driver_daily_stats\n"
        'Action Input: {"driver_id": "DRV-002", "date": "2026-09-15"}\n'
    )
    final_response = (
        "Thought: Đã có đủ dữ liệu từ cả 2 công cụ.\n"
        "Final Answer:\n"
        "Dựa trên dữ liệu vận hành trong ngày 2026-09-15, tôi đã kiểm tra thông tin cho Trần Văn Bình như sau:\n\n"
        "**1. Tình hình vận hành thực tế:**\n"
        "- Lịch sử chuyến xe: 10 chuyến hoàn thành\n"
        "- Chỉ số vận hành: Tỷ lệ hủy chuyến 0%\n\n"
        "**2. Đối chiếu quy chế & Kết luận:**\n"
        "- Kết luận: Đạt tiêu chuẩn\n"
        "- Căn cứ quy chế: P154\n"
        "- Trích dẫn điều khoản liên quan: Đạt yêu cầu\n\n"
        "**3. Khuyến nghị cho Quản lý vận hành:**\n"
        "- Duy trì"
    )

    responses = [multi_tool_response, final_response]

    def mock_call_llm(messages, **kwargs):
        return responses.pop(0), "mock_model", {}

    mock_db = MagicMock()
    mock_db.get_driver.return_value = MagicMock(
        driver_id="drv-uuid-002",
        driver_code="DRV-002",
        full_name="Trần Văn Bình",
    )
    mock_db.get_trips.return_value = []

    mock_pipeline = MagicMock()
    mock_pipeline.bm25_index.search.return_value = []

    agent = ReActAgent(call_llm_fn=mock_call_llm, db_repo=mock_db, pipeline_ref=mock_pipeline, max_iterations=3)
    query = "Kiểm tra tiêu chuẩn tài xế DRV-002 ngày 2026-09-15"
    events = list(agent.run_stream(query))

    final_event = next(e for e in events if e.get("type") == "final_result")
    result: ReActResult = final_event["result"]

    actions_executed = [s.action for s in result.steps if s.action]
    assert "search_gsm_policies" in actions_executed
    assert "get_driver_daily_stats" in actions_executed
    assert len(actions_executed) == 2

    # Verify action_start events had proper action_index
    action_events = [e for e in events if e.get("type") == "action_start"]
    assert len(action_events) == 2
    assert action_events[0]["action_index"] == 1
    assert action_events[0]["total_actions"] == 2
    assert action_events[1]["action_index"] == 2
    assert action_events[1]["total_actions"] == 2


def test_react_agent_detects_duplicate_tool_call_with_identical_args():
    """Verify that calling the same tool with identical parameters does not re-query,

    returns duplicate warning with cached observation, and prevents duplicate citations.
    """
    call1_response = (
        "Thought: Cần tra cứu quy chế lần 1.\n"
        "Action: search_gsm_policies\n"
        'Action Input: {"query": "tiêu chuẩn hủy chuyến", "policy_code": "P154"}\n'
    )
    call2_duplicate_response = (
        "Thought: Tôi vẫn cần tra cứu lại quy chế xem có gì mới không.\n"
        "Action: search_gsm_policies\n"
        'Action Input: {"query": "tiêu chuẩn hủy chuyến", "policy_code": "P154"}\n'
    )
    final_response = (
        "Thought: Đã nhận được cảnh báo trùng lặp và sử dụng kết quả đã có.\n"
        "Final Answer:\n"
        "Dựa trên dữ liệu vận hành trong tháng 9/2026, tôi đã kiểm tra thông tin cho Trần Văn Bình như sau:\n\n"
        "**1. Tình hình vận hành thực tế:**\n"
        "- Lịch sử chuyến xe: 5 chuyến\n"
        "- Chỉ số vận hành: 0% hủy\n\n"
        "**2. Đối chiếu quy chế & Kết luận:**\n"
        "- Kết luận: Không vi phạm\n"
        "- Căn cứ quy chế: P154\n"
        "- Trích dẫn điều khoản liên quan: P154\n\n"
        "**3. Khuyến nghị cho Quản lý vận hành:**\n"
        "- Duy trì"
    )

    responses = [call1_response, call2_duplicate_response, final_response]

    def mock_call_llm(messages, **kwargs):
        return responses.pop(0), "mock_model", {}

    execute_tool_counter = {"count": 0}

    agent = ReActAgent(call_llm_fn=mock_call_llm, max_iterations=4)

    original_execute = agent.execute_tool
    def counted_execute_tool(name, inp):
        execute_tool_counter["count"] += 1
        return original_execute(name, inp)

    agent.execute_tool = counted_execute_tool

    query = "Kiểm tra quy chế hủy chuyến P154"
    events = list(agent.run_stream(query))

    final_event = next(e for e in events if e.get("type") == "final_result")
    result: ReActResult = final_event["result"]

    # Verify underlying execute_tool was called ONLY ONCE despite 2 identical LLM calls!
    assert execute_tool_counter["count"] == 1

    # Verify the second step received DUPLICATE_CALL_DETECTED observation
    step2 = result.steps[1]
    assert isinstance(step2.observation, dict)
    assert step2.observation.get("_repeat_status") == "DUPLICATE_CALL_DETECTED"
    assert "CẢNH BÁO TRÙNG LẶP" in step2.observation.get("warning", "")

    # Verify citations were NOT duplicated
    policy_cits = [c for c in result.citations if "P154" in str(c.get("policy_alias", ""))]
    assert len(policy_cits) == 1


def test_react_agent_breaks_infinite_loop_on_repeated_duplicate_calls():
    """Verify that if an LLM is trapped in a loop calling the same tool 3 times identically,

    the agent forces a loop break and transitions directly to synthesis.
    """
    identical_response = (
        "Thought: Tra cứu quy chế.\n"
        "Action: search_gsm_policies\n"
        'Action Input: {"query": "tiêu chuẩn hủy chuyến"}\n'
    )

    def mock_call_llm(messages, **kwargs):
        # Distinguish synthesis call from regular ReAct loop call
        if any("CÁC BƯỚC SUY LUẬN VÀ QUAN SÁT THỰC TẾ" in m.get("content", "") for m in messages):
            return "Final Answer: Báo cáo đã tổng hợp sau khi ngắt vòng lặp.", "mock_model", {}
        return identical_response, "mock_model", {}

    agent = ReActAgent(call_llm_fn=mock_call_llm, max_iterations=5)
    query = "Kiểm tra quy chế hủy chuyến"
    events = list(agent.run_stream(query))

    final_event = next(e for e in events if e.get("type") == "final_result")
    result: ReActResult = final_event["result"]

    # The 3rd step must detect INFINITE_LOOP_PREVENTED and break loop
    actions = [s for s in result.steps if s.action]
    assert len(actions) == 3
    step3 = actions[2]
    assert isinstance(step3.observation, dict)
    assert step3.observation.get("_repeat_status") == "INFINITE_LOOP_PREVENTED"


def test_get_driver_trip_metrics_with_date_filter():
    """Verify that get_driver_trip_metrics supports date/month/year filtering seamlessly."""
    from unittest.mock import MagicMock
    from gsm_memory.agent.tools import get_driver_trip_metrics

    mock_db = MagicMock()
    mock_driver = MagicMock(
        driver_id="drv-uuid-1",
        driver_code="DRV-001",
        full_name="Nguyễn Văn A",
        completed_trips_count=10,
        cancelled_trips_count=2,
        cancellation_rate_30d=0.2,
    )
    mock_db.get_driver.return_value = mock_driver
    mock_db.get_driver_snapshot_metrics.return_value = {
        "total_trips": 8,
        "completed_trips": 7,
        "cancelled_trips": 1,
        "cancel_rate": 0.125,
        "rating_avg": 4.95,
    }

    # Query with date "2026-09-15"
    res = get_driver_trip_metrics(
        db_repo=mock_db,
        driver_identifier="DRV-001",
        date="2026-09-15",
    )

    mock_db.get_driver_snapshot_metrics.assert_called_with("drv-uuid-1", snapshot_id=None, date="2026-09-15")
    assert res["found"] is True
    assert res["total_trips_count"] == 8
    assert res["completed_trips_count"] == 7
    assert res["cancelled_trips_count"] == 1
    assert res["cancellation_rate_30d"] == 0.125
    assert res["cancel_rate_pct"] == 12.5
    assert res["period"] == "Ngày 2026-09-15"
    assert "12.5%" in res["summary"]


def test_react_agent_handles_pseudo_action_final_without_error():
    """Verify that when an LLM outputs 'Action: Final' or 'Action: Final Answer',

    the ReAct engine does NOT attempt to execute a tool named 'Final',
    and does not return 'Không tìm thấy công cụ Final'.
    """
    step1_resp = (
        "Thought: Cần tra cứu quy chế trước.\n"
        "Action: search_gsm_policies\n"
        'Action Input: {"query": "hủy chuyến"}\n'
    )
    # Step 2 simulates LLM outputting Action: Final instead of proper Final Answer
    step2_resp = (
        "Thought: Đã tra cứu xong và đối chiếu số liệu.\n"
        "Action: Final\n"
        "{}\n"
    )

    responses = [step1_resp, step2_resp]

    def mock_call_llm(messages, **kwargs):
        if any("CÁC BƯỚC SUY LUẬN VÀ QUAN SÁT THỰC TẾ" in m.get("content", "") for m in messages):
            return (
                "**1. Tình hình vận hành thực tế:**\n- 5 chuyến xe\n\n"
                "**2. Đối chiếu quy chế & Kết luận:**\n- Chưa có quy định mức trần\n\n"
                "**3. Khuyến nghị cho Quản lý vận hành:**\n- Tiếp tục theo dõi\n",
                "mock_model",
                {},
            )
        resp = responses.pop(0) if responses else step2_resp
        return resp, "mock_model", {}

    agent = ReActAgent(call_llm_fn=mock_call_llm, max_iterations=4)
    agent.execute_tool = MagicMock(return_value=({"found": True, "policies": []}, None))

    events = list(agent.run_stream("Tài xế Bình vi phạm hủy chuyến không?"))

    # Crucial check: execute_tool must NEVER be called with 'Final'
    for call_args in agent.execute_tool.call_args_list:
        action_called = call_args[0][0]
        assert action_called != "Final", "execute_tool must not be called with 'Final'!"

    # Ensure no step recorded tool error for 'Final'
    final_event = next(e for e in events if e.get("type") == "final_result")
    result: ReActResult = final_event["result"]
    for s in result.steps:
        if s.observation and isinstance(s.observation, dict):
            assert "Không tìm thấy công cụ 'Final'" not in str(s.observation.get("error", ""))

    assert result.status == "ANSWERED"
    assert "Tình hình vận hành thực tế" in result.final_answer







