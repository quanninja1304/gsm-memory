"""Grounded downstream reader for public ``RuntimeQuery`` evidence bundles.

This module deliberately has no dependency on the private evaluation tree.  A
provider is called only through an injected client; the OpenAI adapter imports
the SDK lazily so offline dataset and retrieval workflows remain credential and
network independent.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence


ALLOWED_STATUSES = frozenset({"answered", "insufficient_evidence", "unresolved_conflict"})


class ReaderError(RuntimeError):
    """Raised when a provider response cannot be accepted as grounded output."""


class ReaderProvider(Protocol):
    """Minimal provider seam, intentionally easy to replace with a test fake."""

    def complete(self, *, system_prompt: str, user_prompt: str,
                 response_schema: Mapping[str, Any]) -> str: ...


@dataclass(frozen=True)
class ReaderConfig:
    provider: str
    model: str
    max_output_tokens: int = 700


@dataclass(frozen=True)
class EvidenceCitation:
    evidence_id: str
    locator: str
    quote: str


@dataclass(frozen=True)
class ReaderAnswer:
    status: str
    answer: str
    citations: tuple[EvidenceCitation, ...]
    model: str
    provider: str


def _citation_locator(item: Mapping[str, Any]) -> str:
    """Render an auditable public locator; never expose a retrieval-unit ID as source truth."""
    locator = item.get("source_locator") or {}
    kind = locator.get("locator_type")
    if kind == "document_clause":
        revision = locator.get("document_revision_id", item.get("source_id", "unknown-document"))
        clauses = locator.get("clause_refs") or []
        if clauses:
            labels = ",".join(str(clause.get("clause_id", clause.get("label", "span"))) for clause in clauses)
            return f"{revision}#{labels}"
        return str(revision)
    if kind == "ledger_assertion":
        return f"assertion:{locator.get('assertion_id', item.get('source_id', 'unknown'))}"
    if kind == "entity_catalog":
        return f"entity:{locator.get('entity_id', item.get('source_id', 'unknown'))}"
    if kind == "coverage_artifact":
        return f"coverage:{locator.get('artifact_id', item.get('source_id', 'unknown'))}"
    if kind == "computation":
        return f"computation:{locator.get('coverage_artifact_id', item.get('source_id', 'unknown'))}"
    return str(item.get("source_id", item["evidence_id"]))


def _public_evidence(selected_evidence: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for item in selected_evidence:
        evidence_id = item.get("evidence_id")
        content = item.get("content")
        if not isinstance(evidence_id, str) or not evidence_id or evidence_id in seen:
            raise ValueError("selected evidence requires unique non-empty evidence_id values")
        if not isinstance(content, str) or not content.strip():
            raise ValueError(f"selected evidence {evidence_id!r} has no textual content")
        seen.add(evidence_id)
        # Only fields already present in the selected public runtime item are serialized.
        output.append({"evidence_id": evidence_id, "citation_locator": _citation_locator(item),
                       "source_kind": item.get("source_kind", "unknown"), "content": content})
    return output


def _normalize_whitespace(text: str) -> str:
    """Normalize layout-only variation without changing the quoted source in output."""
    return " ".join(text.split())


def response_json_schema() -> dict[str, Any]:
    """Portable JSON Schema used with providers that support structured output."""
    return {
        "type": "object", "additionalProperties": False,
        "required": ["status", "answer", "citations"],
        "properties": {
            "status": {"type": "string", "enum": sorted(ALLOWED_STATUSES)},
            "answer": {"type": "string", "minLength": 1},
            "citations": {
                "type": "array",
                "items": {"type": "object", "additionalProperties": False,
                          "required": ["evidence_id", "quote"],
                          "properties": {"evidence_id": {"type": "string", "minLength": 1},
                                         "quote": {"type": "string", "minLength": 1}}},
            },
        },
    }


SYSTEM_PROMPT = """You are the GSM evidence reader. Answer only from the supplied PUBLIC evidence.
Never use background knowledge, infer missing facts, or treat a retrieval score as evidence.
Every factual answer must cite one or more supplied evidence IDs and include an exact, contiguous
quote from that item. Preserve dates, times, numbers, fractions, entities, policy editions, and
source locators exactly as supplied. If the bundle cannot establish the requested conclusion,
return status insufficient_evidence. If the bundle contains unresolved equally authoritative
contradictions, return status unresolved_conflict. For either abstention, explain only the visible
gap or contradiction and still cite the evidence that demonstrates it. Return JSON matching the schema."""


def build_prompts(query: Mapping[str, Any], selected_evidence: Sequence[Mapping[str, Any]]) -> tuple[str, str]:
    """Build a reproducible public-only prompt; reject malformed RuntimeQuery input."""
    question = query.get("query")
    query_id = query.get("query_id")
    if not isinstance(question, str) or not question.strip() or not isinstance(query_id, str) or not query_id:
        raise ValueError("RuntimeQuery requires non-empty query_id and query")
    evidence = _public_evidence(selected_evidence)
    payload = {
        "runtime_query": {
            "query_id": query_id, "query": question,
            "entity_refs": query.get("entity_refs", []), "time_scope": query.get("time_scope"),
            "known_as_of": query.get("known_as_of"), "public_snapshot_id": query.get("public_snapshot_id"),
            "application_context": query.get("application_context", {}),
        },
        "selected_evidence": evidence,
        "citation_rule": "Each citation must use an evidence_id above and a contiguous quote copied exactly from its content.",
    }
    return SYSTEM_PROMPT, json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _parse_and_validate(raw: str, evidence: Sequence[Mapping[str, Any]], config: ReaderConfig) -> ReaderAnswer:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ReaderError("reader returned invalid JSON") from exc
    if not isinstance(value, dict) or set(value) != {"status", "answer", "citations"}:
        raise ReaderError("reader response does not match the closed response contract")
    status, answer, citations = value["status"], value["answer"], value["citations"]
    if status not in ALLOWED_STATUSES or not isinstance(answer, str) or not answer.strip() or not isinstance(citations, list):
        raise ReaderError("reader response has invalid status, answer, or citations")
    by_id = {item["evidence_id"]: item for item in evidence}
    parsed: list[EvidenceCitation] = []
    for citation in citations:
        if not isinstance(citation, dict) or set(citation) != {"evidence_id", "quote"}:
            raise ReaderError("each citation must contain only evidence_id and quote")
        evidence_id, quote = citation["evidence_id"], citation["quote"]
        if not isinstance(evidence_id, str) or not isinstance(quote, str) or not quote:
            raise ReaderError("citation fields must be non-empty strings")
        item = by_id.get(evidence_id)
        if item is None:
            raise ReaderError(f"citation refers to non-selected evidence {evidence_id!r}")
        if _normalize_whitespace(quote) not in _normalize_whitespace(item["content"]):
            raise ReaderError(f"citation quote is not grounded in selected evidence {evidence_id!r}")
        parsed.append(EvidenceCitation(evidence_id=evidence_id, locator=item["citation_locator"], quote=quote))
    if not parsed:
        raise ReaderError("reader must cite selected evidence, including for abstentions")
    return ReaderAnswer(status=status, answer=answer.strip(), citations=tuple(parsed),
                        model=config.model, provider=config.provider)


class OpenAIResponsesProvider:
    """Optional OpenAI Responses adapter; imported only for an actual live reader call."""

    def __init__(self, config: ReaderConfig, *, api_key: str | None = None) -> None:
        if config.provider != "openai":
            raise ValueError("OpenAIResponsesProvider requires provider='openai'")
        self._config = config
        self._api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY")
        if not self._api_key:
            raise ReaderError("OPENAI_API_KEY is required for the OpenAI reader")

    def complete(self, *, system_prompt: str, user_prompt: str,
                 response_schema: Mapping[str, Any]) -> str:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - depends on optional install
            raise ReaderError("install the project's graphiti extra to use the OpenAI reader") from exc
        client = OpenAI(api_key=self._api_key)
        response = client.responses.create(
            model=self._config.model, instructions=system_prompt, input=user_prompt,
            max_output_tokens=self._config.max_output_tokens, store=False,
            text={"format": {"type": "json_schema", "name": "gsm_reader_answer",
                              "strict": True, "schema": dict(response_schema)}},
        )
        output = getattr(response, "output_text", None)
        if not isinstance(output, str) or not output:
            raise ReaderError("OpenAI returned no text output")
        return output


def answer_query(query: Mapping[str, Any], selected_evidence: Sequence[Mapping[str, Any]], *,
                 provider: ReaderProvider, config: ReaderConfig) -> ReaderAnswer:
    """Call a configured provider and accept only citation-verifiable public output."""
    system_prompt, user_prompt = build_prompts(query, selected_evidence)
    evidence = _public_evidence(selected_evidence)
    if not evidence:
        # With no public evidence, generation can add no support and is needless provider exposure.
        return ReaderAnswer(status="insufficient_evidence",
                            answer="Không có bằng chứng công khai nào được chọn cho yêu cầu này.",
                            citations=(), model=config.model, provider=config.provider)
    raw = provider.complete(system_prompt=system_prompt, user_prompt=user_prompt,
                            response_schema=response_json_schema())
    return _parse_and_validate(raw, evidence, config)
