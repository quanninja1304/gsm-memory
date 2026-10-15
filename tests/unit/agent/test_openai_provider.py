import os
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from gsm_memory.agent.conversational_pipeline import ConversationalPipeline, _current_llm_provider, _current_llm_model
from gsm_memory.web.app import app


def test_openai_provider_initialization_and_availability():
    with patch.dict(os.environ, {
        "keyOpenAI": "test-key-123",
        "base_url_openAI": "https://custom.openai.api/v1",
        "model_openAI": "gpt-4o",
    }, clear=False):
        pipe = ConversationalPipeline.__new__(ConversationalPipeline)
        pipe.openai_api_key = os.getenv("keyOpenAI")
        pipe.openai_base_url = os.getenv("base_url_openAI")
        pipe.openai_model = os.getenv("model_openAI")
        
        assert pipe.is_openai_available() is True
        assert pipe.openai_api_key == "test-key-123"
        assert pipe.openai_base_url == "https://custom.openai.api/v1"
        assert pipe.openai_model == "gpt-4o"


def test_openai_context_tokens_setup():
    pipe = ConversationalPipeline.__new__(ConversationalPipeline)
    pipe.nvidia_api_key = None
    pipe.openai_api_key = "test-key"
    pipe.openai_base_url = "https://custom.openai.api/v1"
    pipe.openai_model = "gpt-4o-mini"
    pipe.model_name = "openai:gpt-4o-mini"
    pipe.llm_provider = "openai"

    token_prov, token_mod = pipe._setup_context_tokens({"model": "openai:gpt-4o-mini"})
    assert _current_llm_provider.get() == "openai"
    assert _current_llm_model.get() == "openai:gpt-4o-mini"
    pipe._reset_context_tokens(token_prov, token_mod)


def test_api_models_endpoint_contains_openai():
    client = TestClient(app)
    response = client.get("/api/models")
    assert response.status_code == 200
    data = response.json()
    model_ids = [m["id"] for m in data.get("models", [])]
    assert any("openai:" in mid for mid in model_ids)
    assert "openai_status" in data
