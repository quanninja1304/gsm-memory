"""Unit tests verifying Langfuse v4 instrumentation and observation-first tracing model."""

from unittest.mock import MagicMock, patch
import pytest

from gsm_memory.agent.conversational_pipeline import (
    ConversationalPipeline,
    PipelineResponse,
    QueryPlan,
    SlotExtractionResult,
    Subgraph,
)


def test_langfuse_v4_instrumentation_flow():
    """Verify that ConversationalPipeline invokes Langfuse v4 observations, propagation, and flushing."""
    pipeline = ConversationalPipeline.__new__(ConversationalPipeline)
    pipeline.model_name = "test-model"
    pipeline.chunks = []
    pipeline.bm25_index = None
    pipeline.default_snapshot_id = "snap-test"

    # Mock Langfuse client and observation context managers
    mock_lf = MagicMock()
    mock_root_span = MagicMock()
    mock_child_span = MagicMock()
    mock_gen_span = MagicMock()

    mock_lf.start_as_current_observation.return_value.__enter__.return_value = mock_root_span
    mock_lf.get_trace_url.return_value = "https://cloud.langfuse.com/test-trace"

    def child_obs_side_effect(*args, **kwargs):
        as_type = kwargs.get("as_type", "span")
        cm = MagicMock()
        if as_type == "generation":
            cm.__enter__.return_value = mock_gen_span
        else:
            cm.__enter__.return_value = mock_child_span
        return cm

    mock_root_span.start_as_current_observation.side_effect = child_obs_side_effect
    pipeline.langfuse = mock_lf

    # Mock pipeline stages
    dummy_plan = QueryPlan(
        intent="POLICY_QA",
        driver_id="drv-1",
        driver_mention="Tài xế A",
        is_driver_ambiguous=False,
        time_scope="tháng 9/2026",
        snapshot_id="snap-test",
        policy_scope=["P154"],
        modalities=["document"],
        missing_fields=[],
        clarification_reasons={},
        reasoning="All valid",
    )
    pipeline.plan_query = MagicMock(return_value=dummy_plan)
    pipeline.expand_subgraph_bfs = MagicMock(
        return_value=Subgraph(seed_id="drv-1", snapshot_id="snap-test", nodes=[], edges=[])
    )
    pipeline.gather_multi_source_evidence = MagicMock(return_value=[])
    pipeline.build_reader_prompts = MagicMock(return_value=("System prompt", "User prompt"))
    pipeline.generate_grounded_answer = MagicMock(
        return_value=(
            "Answer text",
            [{"locator": "P154#Điều 1", "quote": "Quote text"}],
            {"model_used": "test-model", "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}},
        )
    )

    with patch("langfuse.propagate_attributes") as mock_propagate:
        mock_propagate.return_value.__enter__.return_value = None

        resp = pipeline.execute("Test question", context={"session_id": "sess-123", "driver_id": "drv-1"})

        assert isinstance(resp, PipelineResponse)
        assert resp.status == "ANSWERED"
        assert resp.trace_url == "https://cloud.langfuse.com/test-trace"

        # 1. Verify propagate_attributes was called with correlating session and trace attributes
        mock_propagate.assert_called_once()
        propagate_kwargs = mock_propagate.call_args.kwargs
        assert propagate_kwargs["trace_name"] == "gsm-conversational-qa-pipeline"
        assert propagate_kwargs["session_id"] == "sess-123"
        assert propagate_kwargs["metadata"]["driver_id"] == "drv-1"
        assert propagate_kwargs["metadata"]["release"] == "gsm-dev-core-0.2.2"

        # 2. Verify root observation started with as_type="span"
        mock_lf.start_as_current_observation.assert_called_once()
        root_call_kwargs = mock_lf.start_as_current_observation.call_args.kwargs
        assert root_call_kwargs["name"] == "gsm-conversational-qa-pipeline"
        assert root_call_kwargs["as_type"] == "span"
        assert root_call_kwargs["input"]["query"] == "Test question"

        # 3. Verify child observations started on root_span
        assert mock_root_span.start_as_current_observation.call_count == 5

        # 4. Verify generation observation updated with usage_details (v4 schema)
        mock_gen_span.update.assert_called_once()
        gen_update_kwargs = mock_gen_span.update.call_args.kwargs
        assert "usage_details" in gen_update_kwargs
        assert gen_update_kwargs["usage_details"] == {"input": 10, "output": 20, "total": 30}

        # 5. Verify root span updated with final output
        mock_root_span.update.assert_called_once()
        root_update_kwargs = mock_root_span.update.call_args.kwargs
        assert root_update_kwargs["output"]["status"] == "ANSWERED"

        # 6. Verify flush called
        mock_lf.flush.assert_called_once()


def test_langfuse_v4_clarification_gate_flushing():
    """Verify that when clarification is needed, flush() is still called before returning."""
    pipeline = ConversationalPipeline.__new__(ConversationalPipeline)
    pipeline.model_name = "test-model"
    pipeline.chunks = []
    pipeline.bm25_index = None
    pipeline.default_snapshot_id = "snap-test"

    mock_lf = MagicMock()
    mock_root_span = MagicMock()
    mock_child_span = MagicMock()

    mock_lf.start_as_current_observation.return_value.__enter__.return_value = mock_root_span
    mock_root_span.start_as_current_observation.return_value.__enter__.return_value = mock_child_span
    pipeline.langfuse = mock_lf

    dummy_plan = QueryPlan(
        intent="POLICY_QA",
        driver_id=None,
        driver_mention=None,
        is_driver_ambiguous=False,
        time_scope=None,
        snapshot_id="snap-test",
        policy_scope=[],
        modalities=["document"],
        missing_fields=["driver_id", "time_scope"],
        clarification_reasons={"driver_id": "Thiếu tài xế", "time_scope": "Thiếu thời điểm"},
        reasoning="Cần hỏi thêm",
    )
    pipeline.plan_query = MagicMock(return_value=dummy_plan)
    pipeline.build_clarification_message = MagicMock(return_value="Xin vui lòng cho biết mã tài xế.")

    with patch("langfuse.propagate_attributes") as mock_propagate:
        mock_propagate.return_value.__enter__.return_value = None

        resp = pipeline.execute("Câu hỏi thiếu thông tin")

        assert resp.status == "NEEDS_CLARIFICATION"
        assert resp.clarification_message == "Xin vui lòng cho biết mã tài xế."
        # Verify flush was called on clarification exit
        mock_lf.flush.assert_called_once()
