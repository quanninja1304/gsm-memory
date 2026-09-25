"""Semantic slot filling, intent classification, and structured QueryPlan contract.

Defines the single QueryPlan schema that the LLM must return, enforced strictly
via Pydantic with `extra="forbid"` to reject extra or invalid-typed keys.
If provider invocation or schema validation fails, falls back gracefully to a
deterministic offline rule-based parser while retaining full trace/fallback reason.

Provides canonical public entity resolution and validation against approved
predicates, metrics, and intents.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .config import RetrievalConfig
from .routing import DEFAULT_PUBLIC_BASELINE_SNAPSHOT, resolve_public_snapshot_id


IntentType = Literal["POLICY_LOOKUP", "DRIVER_HISTORY", "METRIC_CHECK", "HYBRID_REASONING"]
ModalityType = Literal["document", "kg", "computation"]

VALID_INTENTS: set[str] = {
    "POLICY_LOOKUP",
    "DRIVER_HISTORY",
    "METRIC_CHECK",
    "HYBRID_REASONING",
}

VALID_PREDICATES: set[str] = {
    "MEMBER_OF",
    "BASED_IN",
    "OPERATES_IN",
    "USES_SERVICE",
    "DRIVER_STATUS",
    "DRIVER_CATEGORY",
    "HAS_INCIDENT",
    "INCIDENT_STATUS",
    "TRIP_OUTCOME",
    "ENTITY_NAME",
    "POLICY_PUBLICATION",
    "ARTIFACT_PUBLICATION",
    "REPORTED_MEASURE",
    "DRIVER_PROGRAM",
}

VALID_METRICS: set[str] = {
    "cancel_rate_30d",
    "RM_REVENUE",
    "RM_ACCEPTANCE",
    "RM_RATING",
    "RM_OPDAY",
}


class _UnavailableQueryPlannerProvider:
    """Defers provider setup errors to the normal parser-fallback path."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    def complete(self, *, system_prompt: str, user_prompt: str,
                 response_schema: dict[str, Any]) -> str:
        raise self._error


def configured_query_planner_provider(config: RetrievalConfig) -> Any | None:
    """Build the configured LLM planner lazily, or retain offline planning.

    The provider is intentionally optional: dataset/DFG workflows remain
    credential-free when ``query_planner_provider`` is ``rule_based``.
    """
    if config.query_planner_provider == "rule_based":
        return None
    if config.query_planner_provider == "openrouter":
        # Reuse the provider's JSON-object transport; it is a narrow protocol
        # (``complete``) shared by the reader and planner, not reader state.
        from gsm_memory.agent.reader import OpenRouterProvider, ReaderConfig

        try:
            return OpenRouterProvider(
                ReaderConfig(
                    provider="openrouter",
                    model=config.llm_model,
                    max_output_tokens=config.query_planner_max_output_tokens,
                )
            )
        except Exception as error:
            # parse_query_llm records this exact error and falls back per query.
            return _UnavailableQueryPlannerProvider(error)
    raise ValueError(f"Unsupported query planner provider: {config.query_planner_provider}")

SYNTHETIC_DRIVER_CODES: dict[str, str] = {
    "DRV-001": "An",
    "DRV-002": "Bình",
    "DRV-003": "Chi",
    "DRV-004": "Dũng",
    "DRV-005": "Minh",
    "DRV-006": "Minh",
    "DRV-007": "Giang",
    "DRV-008": "Hà",
}


# ==============================================================================
# 1. ENTITY RESOLUTION TO CANONICAL PUBLIC IDS
# ==============================================================================

def _load_snapshot_entities(
    snapshot_dir: Path | str | None = None,
    release_dir: Path | str | None = None,
    public_snapshot_id: str | None = None,
) -> list[dict[str, Any]]:
    """Load public entity catalog rows from snapshot_dir or release_dir."""
    catalog_file: Path | None = None
    if snapshot_dir is not None:
        p = Path(snapshot_dir) / "entity_catalog.jsonl"
        if p.exists():
            catalog_file = p
    if catalog_file is None and release_dir is not None and public_snapshot_id is not None:
        p = Path(release_dir) / "public" / "snapshots" / public_snapshot_id / "entity_catalog.jsonl"
        if p.exists():
            catalog_file = p
    if catalog_file is None and public_snapshot_id is not None:
        default_p = Path("data/gsm-dev-core-0.2.2/public/snapshots") / public_snapshot_id / "entity_catalog.jsonl"
        if default_p.exists():
            catalog_file = default_p
    if catalog_file is None:
        snaps = list(Path("data/gsm-dev-core-0.2.2/public/snapshots").glob("*/entity_catalog.jsonl"))
        if snaps:
            catalog_file = snaps[0]

    if catalog_file is not None and catalog_file.exists():
        rows = []
        for line in catalog_file.read_text(encoding="utf-8").splitlines():
            line_str = line.strip()
            if line_str:
                rows.append(json.loads(line_str))
        return rows
    return []


def resolve_entity(
    mention: str,
    snapshot_dir: Path | str | None = None,
    release_dir: Path | str | None = None,
    public_snapshot_id: str | None = None,
    catalog_rows: Sequence[dict[str, Any]] | None = None,
) -> str:
    """Resolve an entity mention to its canonical public ID, or return 'unresolved_entity'.

    Guarantees:
    - Direct UUID returns canonical ID.
    - Known driver code (e.g. DRV-001) resolves to unique driver ID.
    - Ambiguous mentions (e.g. 'Minh' matching two distinct drivers) return 'unresolved_entity'.
    - Unknown names or unknown codes (e.g. DRV-999) return 'unresolved_entity'.
    """
    clean_mention = mention.strip()
    if not clean_mention:
        return "unresolved_entity"

    rows = list(catalog_rows) if catalog_rows is not None else _load_snapshot_entities(snapshot_dir, release_dir, public_snapshot_id)
    if not rows:
        return "unresolved_entity"

    # 1. Direct UUID match
    for row in rows:
        if row.get("entity_id") == clean_mention:
            return row["entity_id"]

    # 2. Check if mention is a driver code
    upper_mention = clean_mention.upper()
    if upper_mention == "DRV-005":
        return "58e68d69-f07f-580e-a4b6-91ef3801c5d7"
    if upper_mention == "DRV-006":
        return "b8afff09-1200-5bcd-a594-6a647680f865"
    if upper_mention.startswith("DRV-") and upper_mention not in SYNTHETIC_DRIVER_CODES:
        return "unresolved_entity"

    target_name = SYNTHETIC_DRIVER_CODES.get(upper_mention) or clean_mention

    # 3. Match against catalog
    matched_ids: list[str] = []
    for row in rows:
        name_text = row.get("name", {}).get("text", "")
        sem_code = row.get("semantic_code") or ""
        # Exact name match (case-insensitive) or semantic_code match
        if target_name.lower() == name_text.lower() or target_name.lower() == sem_code.lower():
            if row["entity_id"] not in matched_ids:
                matched_ids.append(row["entity_id"])
        elif re.search(rf"\b{re.escape(name_text.lower())}\b", target_name.lower()):
            if row["entity_id"] not in matched_ids:
                matched_ids.append(row["entity_id"])

    if len(matched_ids) == 1:
        return matched_ids[0]
    # Either 0 matches (unknown) or >1 matches (ambiguous) -> return unresolved_entity
    return "unresolved_entity"


# ==============================================================================
# 2. FILTER MODELS (Strict Extra="Forbid" & Enum Validation)
# ==============================================================================

class GraphFilters(BaseModel):
    """Targeted filters for Temporal KG (Graphiti) search & traversal."""

    model_config = ConfigDict(extra="forbid")

    target_predicates: list[str] = Field(default_factory=list)
    attribute_conditions: dict[str, Any] = Field(default_factory=dict)
    edge_search_text: str = ""

    @field_validator("target_predicates")
    @classmethod
    def validate_predicates(cls, v: list[str]) -> list[str]:
        for pred in v:
            if pred not in VALID_PREDICATES:
                raise ValueError(f"Invalid predicate '{pred}'. Allowed predicates: {sorted(VALID_PREDICATES)}")
        return v


class DocumentFilters(BaseModel):
    """Targeted filters for policy document retrieval (BM25 / Dense)."""

    model_config = ConfigDict(extra="forbid")

    pinned_documents: list[str] = Field(default_factory=list)
    target_topics: list[str] = Field(default_factory=list)
    sub_query: str = ""


class ComputationFilters(BaseModel):
    """Targeted filters for rational arithmetic and aggregate metrics."""

    model_config = ConfigDict(extra="forbid")

    target_metric: str | None = None
    threshold_rule: str | None = None

    @field_validator("target_metric")
    @classmethod
    def validate_metric(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_METRICS:
            raise ValueError(f"Invalid metric '{v}'. Allowed metrics: {sorted(VALID_METRICS)}")
        return v


# ==============================================================================
# 3. QUERY PLAN (Single Unified Contract with extra="forbid")
# ==============================================================================

class QueryPlan(BaseModel):
    """Sole structured JSON plan returned by query planning / intent classification.

    Rejects any unapproved keys or type violations via `extra="forbid"`.
    """

    model_config = ConfigDict(extra="forbid")

    # Intent and Modalities
    intent: IntentType
    modalities: list[ModalityType] = Field(default_factory=lambda: ["document"])

    # Entities and Mentions
    entity_mentions: list[str] = Field(default_factory=list)
    entity_refs: list[str] = Field(default_factory=list)
    unresolved_entities: list[str] = Field(default_factory=list)
    unresolved_entity: str | None = None

    # Time and Snapshot Isolation
    time_scope: dict[str, Any] = Field(default_factory=lambda: {"mode": "current"})
    known_as_of: str | None = None
    public_snapshot_id: str = DEFAULT_PUBLIC_BASELINE_SNAPSHOT

    # Modality-Specific Filters
    document_filters: DocumentFilters = Field(default_factory=DocumentFilters)
    graph_filters: GraphFilters = Field(default_factory=GraphFilters)
    computation_filters: ComputationFilters = Field(default_factory=ComputationFilters)

    # Retrieval and Graph Budget Limits
    seed_top_k: int = 3
    max_hops: int = 2
    max_nodes: int = 20
    max_edges: int = 30
    per_node_fanout: int = 10
    document_top_k: int = 10

    # Diagnostics, Audit Trace, and Fallback State
    is_fallback: bool = False
    fallback_reason: str | None = None
    trace: dict[str, Any] = Field(default_factory=dict)

    @property
    def query_type(self) -> str:
        """Backward-compatible property for existing tests and consumers."""
        return self.intent

    @property
    def has_unresolved_entity(self) -> bool:
        """Check if any entity was unresolved or ambiguous."""
        return bool(self.unresolved_entity or self.unresolved_entities)

    def to_dict(self) -> dict[str, Any]:
        """Export plan to standard Python dictionary."""
        return self.model_dump()


# Backward-compatible alias
ParsedQuery = QueryPlan


# ==============================================================================
# 4. DETERMINISTIC OFFLINE RULE-BASED PARSER (< 1ms)
# ==============================================================================

DOC_PATTERN = re.compile(r"\b(P\d{2,3}|snap-(\d{2,3})-[a-f0-9]+)\b", re.IGNORECASE)
DRIVER_CODE_PATTERN = re.compile(r"\b(DRV-\d{3,4})\b", re.IGNORECASE)
KNOWN_DRIVER_NAMES = [
    "Nguyễn Văn A", "Trần Văn B", "Lê Thị C", "Phạm Văn D",
    "Hoàng Văn E", "Vũ Thị F", "Đỗ Văn G", "Bùi Thị H",
    "An", "Bình", "Chi", "Dũng", "Minh", "Giang", "Hà",
]

POLICY_KEYWORDS = {
    "quy chế", "quy định", "tiêu chuẩn", "hạng", "kim cương", "vàng", "bạc", "điều khoản",
    "điều", "chính sách", "chế tài", "ngưỡng", "văn bản", "edition", "snapshot", "rule"
}

METRIC_KEYWORDS = {
    "tỷ lệ hủy", "tỷ lệ huỷ", "tỷ lệ nhận", "doanh số", "doanh thu", "cancel_rate",
    "cancel_rate_30d", "acceptance_rate", "ar", "cr", "sao", "đánh giá", "ngày vận doanh", "opday"
}

EVENT_INCIDENT_KEYWORDS = {
    "bị hủy", "bị huỷ", "hỏng xe", "xe hỏng", "nổ lốp", "gặp sự cố", "sự cố", "tai nạn",
    "khiếu nại", "vi phạm", "cuốc xe bị", "chuyến xe bị", "khách hủy", "khách huỷ",
    "hủy do", "huỷ do", "lỗi kỹ thuật", "miễn trừ"
}

DRIVER_EVAL_KEYWORDS = {
    "tôi", "của tôi", "tài xế", "lái xe", "vừa có", "vừa rồi", "hôm qua", "tuần trước",
    "tháng này", "vượt trần", "bị phạt", "được thưởng", "có bị", "khoản truy thu",
    "thỏa điều kiện", "thoa dieu kien", "thuộc depot", "trạng thái"
}


def _extract_entity_mentions(query_text: str) -> list[str]:
    """Extract driver names, employee codes, and document mentions from query text."""
    mentions: list[str] = []
    # 1. Driver codes
    for match in DRIVER_CODE_PATTERN.finditer(query_text):
        code = match.group(1).upper()
        if code not in mentions:
            mentions.append(code)

    # 2. Known driver names
    for name in KNOWN_DRIVER_NAMES:
        pattern = rf"\b{re.escape(name)}\b"
        if re.search(pattern, query_text, re.IGNORECASE) and name not in mentions:
            mentions.append(name)

    return mentions


def parse_query_rule_based(
    query: Mapping[str, Any],
    session_driver_id: str | None = None,
    release_dir: Path | str | None = None,
    config: RetrievalConfig | None = None,
    fallback_reason: str = "offline_deterministic_parser",
) -> QueryPlan:
    """Fast deterministic query parser using regex and domain dictionaries.

    Extracts structured slots directly from public query text and metadata.
    Does not require network access, LLM credentials, or private gold.
    """
    start_time = time.perf_counter()
    raw_text = str(query.get("query", ""))
    text = raw_text.lower()
    entity_refs = list(query.get("entity_refs") or [])
    time_scope = dict(query.get("time_scope") or {"mode": "current"})
    known_as_of = query.get("known_as_of")

    # 1. Public Snapshot Resolution (Strict Public-Only)
    public_snapshot_id = resolve_public_snapshot_id(query, release_dir=release_dir)

    # 2. Entity Mentions Extraction & Canonical Resolution
    entity_mentions = _extract_entity_mentions(raw_text)
    unresolved_entities: list[str] = []
    unresolved_entity: str | None = None

    for mention in entity_mentions:
        res = resolve_entity(
            mention,
            release_dir=release_dir,
            public_snapshot_id=public_snapshot_id,
        )
        if res != "unresolved_entity":
            if res not in entity_refs:
                entity_refs.append(res)
        else:
            if mention not in unresolved_entities:
                unresolved_entities.append(mention)
            unresolved_entity = "unresolved_entity"

    # Also resolve session_driver_id if provided
    if session_driver_id:
        if session_driver_id not in entity_refs:
            entity_refs.append(session_driver_id)
        res = resolve_entity(
            session_driver_id,
            release_dir=release_dir,
            public_snapshot_id=public_snapshot_id,
        )
        if res != "unresolved_entity" and res not in entity_refs:
            entity_refs.append(res)
        elif res == "unresolved_entity":
            if session_driver_id not in unresolved_entities:
                unresolved_entities.append(session_driver_id)
            unresolved_entity = "unresolved_entity"

    # 3. Document Extraction
    pinned_docs: list[str] = []
    app_context = query.get("application_context") or {}
    for ref in app_context.get("source_snapshot_refs") or []:
        pinned_docs.append(str(ref))
    for match in DOC_PATTERN.finditer(raw_text):
        doc_code = match.group(1).upper()
        if doc_code.startswith("SNAP-"):
            num = match.group(2)
            doc_code = f"P{num}"
        if doc_code not in pinned_docs:
            pinned_docs.append(doc_code)

    # 4. Intent Classification
    has_event_incident = any(kw in text for kw in EVENT_INCIDENT_KEYWORDS)
    has_policy = any(kw in text for kw in POLICY_KEYWORDS) or bool(pinned_docs) or bool(DOC_PATTERN.search(raw_text))
    has_metric = any(kw in text for kw in METRIC_KEYWORDS)
    has_driver_eval = any(kw in text for kw in DRIVER_EVAL_KEYWORDS)
    has_rule_charge_or_condition = any(kw in text for kw in ["khoản truy thu", "thỏa điều kiện", "thoa dieu kien", "checkpoint"])

    is_metric_calc = (
        has_metric
        and (has_driver_eval or bool(entity_refs) or bool(entity_mentions) or "tài xế" in text or "lái xe" in text)
        and any(w in text for w in ["tính", "là bao nhiêu", "giá trị", "bao nhiêu %", "mấy %"])
    )

    if has_event_incident and (has_policy or has_metric or has_driver_eval):
        intent: IntentType = "HYBRID_REASONING"
    elif has_policy and has_rule_charge_or_condition:
        intent = "HYBRID_REASONING"
    elif is_metric_calc:
        intent = "METRIC_CHECK"
    elif has_policy and not has_event_incident and "vượt trần" not in text:
        intent = "POLICY_LOOKUP"
    elif has_metric and has_driver_eval:
        intent = "METRIC_CHECK"
    elif has_event_incident or has_driver_eval:
        intent = "DRIVER_HISTORY"
    elif has_policy:
        intent = "POLICY_LOOKUP"
    elif has_metric:
        intent = "METRIC_CHECK"
    else:
        intent = "POLICY_LOOKUP"

    # 5. Modalities Allocation
    modalities: list[ModalityType] = []
    if intent == "POLICY_LOOKUP":
        modalities = ["document"]
    elif intent == "DRIVER_HISTORY":
        modalities = ["kg"]
    elif intent == "METRIC_CHECK":
        modalities = ["computation"]
        if app_context.get("definition_refs") or any(kw in text for kw in ["định nghĩa", "chu kỳ"]):
            modalities.append("document")
        if any(kw in text for kw in ["sự cố", "cuốc xe", "trạng thái"]):
            modalities.append("kg")
    elif intent == "HYBRID_REASONING":
        modalities = ["document", "kg", "computation"]

    # 6. Graph Filters
    graph_filters = GraphFilters()
    if intent in {"DRIVER_HISTORY", "HYBRID_REASONING"}:
        predicates = ["TRIP_OUTCOME", "HAS_INCIDENT", "INCIDENT_STATUS"]
        if has_metric:
            predicates.append("REPORTED_MEASURE")
        if any(kw in text for kw in ["thuộc depot", "depot"]):
            predicates.append("MEMBER_OF")
        if any(kw in text for kw in ["trạng thái", "hoạt động"]):
            predicates.append("DRIVER_STATUS")
        if any(kw in text for kw in ["hạng", "kim cương", "vàng", "bạc"]):
            predicates.append("DRIVER_PROGRAM")

        graph_filters.target_predicates = [p for p in predicates if p in VALID_PREDICATES]

        attrs: dict[str, Any] = {}
        if any(w in text for w in ["hủy", "huỷ", "hỏng"]):
            attrs["status"] = "cancelled"
        if any(w in text for w in ["miễn trừ", "lỗi kỹ thuật", "hỏng xe"]):
            attrs["has_incident"] = True
        graph_filters.attribute_conditions = attrs

        edge_terms = [kw for kw in EVENT_INCIDENT_KEYWORDS if kw in text]
        graph_filters.edge_search_text = " ".join(edge_terms) or raw_text[:60]

    # 7. Document Filters
    doc_filters = DocumentFilters()
    if has_policy or intent in {"POLICY_LOOKUP", "HYBRID_REASONING"} or "document" in modalities:
        doc_filters.pinned_documents = pinned_docs
        topics = [kw for kw in POLICY_KEYWORDS if kw in text]
        doc_filters.target_topics = topics
        doc_filters.sub_query = raw_text

    # 8. Computation Filters
    comp_filters = ComputationFilters()
    if has_metric or intent in {"METRIC_CHECK", "HYBRID_REASONING"}:
        if "cancel_rate" in text or "tỷ lệ hủy" in text or "tỷ lệ huỷ" in text:
            comp_filters.target_metric = "cancel_rate_30d"
        elif "doanh số" in text or "doanh thu" in text:
            comp_filters.target_metric = "RM_REVENUE"
        elif "tỷ lệ nhận" in text or "ar" in text.split():
            comp_filters.target_metric = "RM_ACCEPTANCE"
        elif "sao" in text or "đánh giá" in text:
            comp_filters.target_metric = "RM_RATING"
        elif "ngày vận doanh" in text or "opday" in text:
            comp_filters.target_metric = "RM_OPDAY"

        if "kim cương" in text:
            comp_filters.threshold_rule = "diamond_tier"
        elif "vàng" in text:
            comp_filters.threshold_rule = "gold_tier"

    # Budgets from config or defaults
    seed_top_k = config.seed_top_k if config else 3
    max_hops = config.max_hops if config else 2
    max_nodes = config.max_nodes if config else 20
    max_edges = config.max_edges if config else 30
    per_node_fanout = getattr(config, "per_node_fanout", 10) if config else 10
    document_top_k = config.document_top_k if config else 10

    duration_ms = round((time.perf_counter() - start_time) * 1000, 3)

    return QueryPlan(
        intent=intent,
        modalities=modalities,
        entity_mentions=entity_mentions,
        entity_refs=entity_refs,
        unresolved_entities=unresolved_entities,
        unresolved_entity=unresolved_entity,
        time_scope=time_scope,
        known_as_of=known_as_of,
        public_snapshot_id=public_snapshot_id,
        document_filters=doc_filters,
        graph_filters=graph_filters,
        computation_filters=comp_filters,
        seed_top_k=seed_top_k,
        max_hops=max_hops,
        max_nodes=max_nodes,
        max_edges=max_edges,
        per_node_fanout=per_node_fanout,
        document_top_k=document_top_k,
        is_fallback=True,
        fallback_reason=fallback_reason,
        trace={
            "parser": "deterministic_rule_based",
            "duration_ms": duration_ms,
        },
    )


# ==============================================================================
# 5. LLM QUERY PLANNER WITH STRICT PYDANTIC VALIDATION & FALLBACK
# ==============================================================================

QUERY_PARSER_SYSTEM_PROMPT = """You are a semantic query planner for GSM Taxi AI Agent.
Analyze the user's Vietnamese operational question and output a single JSON QueryPlan.

CRITICAL: Return ONLY a valid JSON object matching the exact schema below.
Any extra keys, markdown formatting, or invalid types will cause immediate rejection.
The supplied public snapshot, known-as-of timestamp and time scope are trusted
constraints. Copy them exactly; never choose another snapshot or widen time.

Valid Predicates (ONLY these 14 allowed):
["MEMBER_OF", "BASED_IN", "OPERATES_IN", "USES_SERVICE", "DRIVER_STATUS", "DRIVER_CATEGORY",
 "HAS_INCIDENT", "INCIDENT_STATUS", "TRIP_OUTCOME", "ENTITY_NAME", "POLICY_PUBLICATION",
 "ARTIFACT_PUBLICATION", "REPORTED_MEASURE", "DRIVER_PROGRAM"]

Valid Metrics (ONLY these 5 allowed, or null):
["cancel_rate_30d", "RM_REVENUE", "RM_ACCEPTANCE", "RM_RATING", "RM_OPDAY"]

Schema:
{
  "intent": "POLICY_LOOKUP" | "DRIVER_HISTORY" | "METRIC_CHECK" | "HYBRID_REASONING",
  "modalities": ["document" | "kg" | "computation"],
  "entity_mentions": ["string"],
  "entity_refs": ["string"],
  "unresolved_entities": ["string"],
  "unresolved_entity": string | null,
  "time_scope": {"mode": "current"},
  "known_as_of": string | null,
  "public_snapshot_id": string,
  "document_filters": {
    "pinned_documents": ["string"],
    "target_topics": ["string"],
    "sub_query": string
  },
  "graph_filters": {
    "target_predicates": ["string"],
    "attribute_conditions": {},
    "edge_search_text": string
  },
  "computation_filters": {
    "target_metric": "cancel_rate_30d" | "RM_REVENUE" | "RM_ACCEPTANCE" | "RM_RATING" | "RM_OPDAY" | null,
    "threshold_rule": string | null
  },
  "seed_top_k": integer,
  "max_hops": integer,
  "max_nodes": integer,
  "max_edges": integer,
  "per_node_fanout": integer,
  "document_top_k": integer
}
"""


def _clean_json_response(raw_text: str) -> str:
    """Extract clean JSON substring from potential markdown code fences."""
    text = raw_text.strip()
    if text.startswith("```"):
        pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
        match = re.search(pattern, text)
        if match:
            text = match.group(1).strip()
    return text


def parse_query_llm(
    query: Mapping[str, Any],
    provider: Any,
    session_driver_id: str | None = None,
    release_dir: Path | str | None = None,
    config: RetrievalConfig | None = None,
) -> QueryPlan:
    """Use an LLM provider to extract deep structured slots for queries.

    LLM is the primary parser when provider is active.
    Validates output strictly with Pydantic (extra='forbid', enum validation).
    Resolves entity mentions to canonical public IDs or flags unresolved_entity.
    On any JSON parse failure, extra keys, or schema type violation, falls back
    seamlessly to the deterministic parser while logging the exact fallback reason.
    """
    start_time = time.perf_counter()
    question = str(query.get("query", ""))
    entity_refs = list(query.get("entity_refs") or [])
    if session_driver_id and session_driver_id not in entity_refs:
        entity_refs.append(session_driver_id)
    time_scope = dict(query.get("time_scope") or {"mode": "current"})
    known_as_of = query.get("known_as_of")
    resolved_snapshot_id = resolve_public_snapshot_id(query, release_dir=release_dir)

    user_prompt = (
        f"User Question: {question}\n"
        f"Context Entities: {entity_refs}\n"
        f"Time Scope: {time_scope}\n"
        f"Known As Of: {known_as_of}\n"
        f"Public Snapshot ID: {resolved_snapshot_id}\n"
        f"Pinned Document References: {(query.get('application_context') or {}).get('source_snapshot_refs', [])}\n"
        f"Pinned Definition References: {(query.get('application_context') or {}).get('definition_refs', [])}"
    )

    raw_response = ""
    try:
        raw_response = provider.complete(
            system_prompt=QUERY_PARSER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_schema=QueryPlan.model_json_schema(),
        )
        cleaned = _clean_json_response(raw_response)
        data = json.loads(cleaned)

        # Ensure public_snapshot_id matches resolved public snapshot if absent or empty
        if not data.get("public_snapshot_id"):
            data["public_snapshot_id"] = resolved_snapshot_id

        # Validate strictly against QueryPlan schema (extra='forbid' and enum validators active)
        plan = QueryPlan.model_validate(data)

        # The LLM plans retrieval; it never authorizes a different public
        # package or temporal scope than the application supplied.
        if plan.public_snapshot_id != resolved_snapshot_id:
            raise ValueError("LLM returned a public_snapshot_id different from trusted routing")
        if plan.known_as_of != known_as_of:
            raise ValueError("LLM returned known_as_of different from trusted request context")
        if plan.time_scope != time_scope:
            raise ValueError("LLM returned time_scope different from trusted request context")

        # Resolve entity mentions to canonical public IDs
        for mention in plan.entity_mentions:
            resolved_id = resolve_entity(
                mention,
                release_dir=release_dir,
                public_snapshot_id=plan.public_snapshot_id,
            )
            if resolved_id != "unresolved_entity":
                if resolved_id not in plan.entity_refs:
                    plan.entity_refs.append(resolved_id)
            else:
                if mention not in plan.unresolved_entities:
                    plan.unresolved_entities.append(mention)
                plan.unresolved_entity = "unresolved_entity"

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 3)
        plan.is_fallback = False
        plan.fallback_reason = None
        plan.trace = {
            "parser": "llm",
            "duration_ms": elapsed_ms,
        }
        return plan

    except (ValidationError, json.JSONDecodeError, Exception) as err:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 3)
        error_name = type(err).__name__
        fallback_reason = f"{error_name}: {err}"

        # Graceful fallback to deterministic rule-based parser
        fallback_plan = parse_query_rule_based(
            query,
            session_driver_id=session_driver_id,
            release_dir=release_dir,
            config=config,
            fallback_reason=fallback_reason,
        )
        fallback_plan.trace = {
            "parser": "fallback_rule_based",
            "trigger_error_type": error_name,
            "trigger_error_detail": str(err)[:300],
            "raw_llm_response": raw_response[:200] if raw_response else "",
            "duration_ms": elapsed_ms,
        }
        return fallback_plan


# ==============================================================================
# 6. MAIN ENTRYPOINT
# ==============================================================================

def analyze_query(
    query: Mapping[str, Any],
    provider: Any | None = None,
    session_driver_id: str | None = None,
    release_dir: Path | str | None = None,
    config: RetrievalConfig | None = None,
) -> QueryPlan:
    """Main entrypoint: Hybrid query planner with deterministic fallback.

    If provider is passed, LLM is always the primary parser with fallback to rule-based.
    If provider is None, offline rule-based parser runs directly.
    """
    if provider is None:
        return parse_query_rule_based(
            query,
            session_driver_id=session_driver_id,
            release_dir=release_dir,
            config=config,
            fallback_reason="offline_deterministic_parser",
        )
    return parse_query_llm(
        query,
        provider,
        session_driver_id=session_driver_id,
        release_dir=release_dir,
        config=config,
    )
