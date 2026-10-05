import os
import pytest
from dotenv import load_dotenv

load_dotenv()

from gsm_memory.agent.reader import OpenRouterProvider, ReaderConfig, answer_query
from tests.fixtures.mock_data import MOCK_SCENARIOS

API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct")

skip_if_no_key = pytest.mark.skipif(not API_KEY, reason="OPENROUTER_API_KEY is not set in .env")


@skip_if_no_key
def test_openrouter_live_policy_lookup():
    config = ReaderConfig(provider="openrouter", model=MODEL)
    provider = OpenRouterProvider(config, api_key=API_KEY)
    scenario = MOCK_SCENARIOS["policy_lookup"]

    result = answer_query(scenario["query"], scenario["selected_evidence"], provider=provider, config=config)

    assert result.status == "answered"
    assert len(result.citations) >= 1
    # Check that citation is grounded in P154
    assert result.citations[0].evidence_id == "cand-doc-p154-sec5"
    assert "90%" in result.citations[0].quote or "AR" in result.citations[0].quote


@skip_if_no_key
def test_openrouter_live_complex_driver_reasoning():
    config = ReaderConfig(provider="openrouter", model=MODEL)
    provider = OpenRouterProvider(config, api_key=API_KEY)
    scenario = MOCK_SCENARIOS["complex_driver_reasoning"]

    result = answer_query(scenario["query"], scenario["selected_evidence"], provider=provider, config=config)

    assert result.status == "answered"
    assert len(result.citations) >= 1
    # Ensure evidence IDs cited come from the supplied bundle
    cited_ids = {c.evidence_id for c in result.citations}
    assert cited_ids.issubset({item["evidence_id"] for item in scenario["selected_evidence"]})


@skip_if_no_key
def test_openrouter_live_unresolved_conflict_handling():
    config = ReaderConfig(provider="openrouter", model=MODEL)
    provider = OpenRouterProvider(config, api_key=API_KEY)
    scenario = MOCK_SCENARIOS["unresolved_conflict"]

    result = answer_query(scenario["query"], scenario["selected_evidence"], provider=provider, config=config)

    assert result.status in {"unresolved_conflict", "answered"}
    assert len(result.citations) >= 1
    cited_ids = {c.evidence_id for c in result.citations}
    assert cited_ids.issubset({"conflict-doc-a", "conflict-doc-b"})

