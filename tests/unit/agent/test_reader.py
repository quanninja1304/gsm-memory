import json

# pyrefly: ignore [missing-import]
import pytest

from gsm_memory.agent.reader import ReaderConfig, ReaderError, answer_query, build_prompts


QUERY = {
    "query_id": "public-query-1", "query": "Quy định nói gì?", "entity_refs": [],
    "time_scope": {"mode": "current"}, "known_as_of": "2026-09-17T12:00:00Z",
    "public_snapshot_id": "snapshot-public", "application_context": {"source_snapshot_refs": ["P154"]},
}
EVIDENCE = [{
    "evidence_id": "doc-1", "source_id": "P154", "source_kind": "document",
    "content": "Điều 5: Doanh số tối thiểu là 500.000 đồng.",
    "source_locator": {"locator_type": "document_clause", "document_revision_id": "P154",
                       "clause_refs": [{"clause_id": "Điều 5"}]},
}]


class FakeProvider:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls = 0

    def complete(self, *, system_prompt, user_prompt, response_schema):
        self.calls += 1
        assert "PUBLIC" in system_prompt
        assert "private/eval" not in user_prompt
        assert response_schema["properties"]["status"]["enum"] == ["answered", "insufficient_evidence", "unresolved_conflict"]
        return json.dumps(self.response, ensure_ascii=False)


def test_reader_returns_only_selected_evidence_with_auditable_citation():
    provider = FakeProvider({"status": "answered", "answer": "Mức tối thiểu là 500.000 đồng.",
                             "citations": [{"evidence_id": "doc-1", "quote": "Doanh số tối thiểu là 500.000 đồng."}]})
    result = answer_query(QUERY, EVIDENCE, provider=provider, config=ReaderConfig("fake", "fake-model"))
    assert provider.calls == 1
    assert result.status == "answered"
    assert result.citations[0].locator == "P154#Điều 5"


@pytest.mark.parametrize("response", [
    {"status": "answered", "answer": "Có căn cứ.", "citations": [{"evidence_id": "not-selected", "quote": "x"}]},
    {"status": "answered", "answer": "Có căn cứ.", "citations": [{"evidence_id": "doc-1", "quote": "bịa"}]},
    {"status": "answered", "answer": "Có căn cứ.", "citations": []},
])
def test_reader_rejects_ungrounded_or_uncited_response(response):
    with pytest.raises(ReaderError):
        answer_query(QUERY, EVIDENCE, provider=FakeProvider(response), config=ReaderConfig("fake", "fake-model"))


def test_prompt_is_public_only_and_rejects_bad_selected_evidence():
    _, prompt = build_prompts(QUERY, EVIDENCE)
    assert "doc-1" in prompt
    assert "expected_status" not in prompt
    with pytest.raises(ValueError, match="unique"):
        build_prompts(QUERY, [EVIDENCE[0], EVIDENCE[0]])


def test_reader_abstains_without_calling_provider_for_an_empty_bundle():
    provider = FakeProvider({"status": "answered", "answer": "must not be used", "citations": []})
    result = answer_query(QUERY, [], provider=provider, config=ReaderConfig("fake", "fake-model"))
    assert result.status == "insufficient_evidence"
    assert result.citations == ()
    assert provider.calls == 0


def test_reader_accepts_a_quote_with_layout_only_whitespace_variation():
    evidence = [{**EVIDENCE[0], "content": "Điều 5:\n  Doanh số tối thiểu là 500.000 đồng."}]
    provider = FakeProvider({"status": "answered", "answer": "Mức tối thiểu là 500.000 đồng.",
                             "citations": [{"evidence_id": "doc-1", "quote": "Doanh số  tối thiểu là 500.000 đồng."}]})
    result = answer_query(QUERY, evidence, provider=provider, config=ReaderConfig("fake", "fake-model"))
    assert result.citations[0].quote == "Doanh số  tối thiểu là 500.000 đồng."
