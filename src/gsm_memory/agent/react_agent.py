"""ReAct (Reasoning + Acting) Agent Engine for GSM Conversational Operations.

Implements autonomous tool selection and dynamic thought-action-observation loop
for operational queries, standards verification (attendance, completion & acceptance
rates, revenue quotas), Knowledge Graph traversal, and policy retrieval.
"""

from __future__ import annotations

import difflib
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from gsm_memory.agent.tools import (
    TOOL_SCHEMAS,
    calculate_acceptance_rate,
    calculate_attendance_hours,
    calculate_cancel_rate,
    calculate_completion_rate,
    calculate_revenue_charge,
    calculate_violation_penalty_points,
    evaluate_daily_revenue,
    evaluate_rating_condition,
    get_cancelled_trips_detail,
    get_complaint_detail,
    get_driver_daily_stats,
    get_driver_incidents_and_complaints,
    get_driver_operational_stats,
    get_driver_profile,
    get_driver_trip_metrics,
    get_driver_trip_summary,
    get_incident_detail,
    get_recent_complaints,
    get_recent_incidents,
    query_driver_graph,
    search_gsm_policies,
    get_full_policy_document,
)


@dataclass
class ReActStep:
    step: int
    thought: str
    action: str | None = None
    action_input: dict[str, Any] | None = None
    observation: Any | None = None
    raw_text: str = ""


@dataclass
class ReActResult:
    query: str
    steps: list[ReActStep] = field(default_factory=list)
    final_answer: str = ""
    citations: list[dict[str, Any]] = field(default_factory=list)
    status: str = "ANSWERED"
    model_used: str = ""
    latency_ms: float = 0.0



TOOL_ALIASES: dict[str, str] = {
    # Driver profile & basic info
    "get_driver_info": "get_driver_profile",
    "get_driver_information": "get_driver_profile",
    "driver_profile": "get_driver_profile",
    "get_driver_details": "get_driver_profile",
    "lookup_driver": "get_driver_profile",
    "get_driver": "get_driver_profile",
    "driver_info": "get_driver_profile",
    "find_driver": "get_driver_profile",
    "check_driver": "get_driver_profile",
    "driver_details": "get_driver_profile",
    # Trip summary / metrics
    "get_driver_trip_summary": "get_driver_trip_summary",
    "driver_trip_summary": "get_driver_trip_summary",
    "get_trip_summary": "get_driver_trip_summary",
    "trip_summary": "get_driver_trip_summary",
    "get_driver_trip_metrics": "get_driver_trip_summary",
    "get_trip_metrics": "get_driver_trip_summary",
    "get_driver_trips": "get_driver_trip_summary",
    "trip_metrics": "get_driver_trip_summary",
    "get_trips": "get_driver_trip_summary",
    "get_driver_trips_summary": "get_driver_trip_summary",
    "driver_trip_metrics": "get_driver_trip_summary",
    "query_trips": "get_driver_trip_summary",
    "query_driver_trips": "get_driver_trip_summary",
    # Cancelled trips
    "get_cancelled_trips": "get_cancelled_trips_detail",
    "cancelled_trips_detail": "get_cancelled_trips_detail",
    "get_driver_cancellations": "get_cancelled_trips_detail",
    "get_driver_cancelled_trips": "get_cancelled_trips_detail",
    "cancelled_trips": "get_cancelled_trips_detail",
    "get_cancellation_detail": "get_cancelled_trips_detail",
    # Operational stats / daily stats
    "get_driver_operational_stats": "get_driver_operational_stats",
    "driver_operational_stats": "get_driver_operational_stats",
    "get_operational_stats": "get_driver_operational_stats",
    "operational_stats": "get_driver_operational_stats",
    "get_driver_daily_stats": "get_driver_operational_stats",
    "driver_daily_stats": "get_driver_operational_stats",
    "get_daily_stats": "get_driver_operational_stats",
    "get_driver_stats": "get_driver_operational_stats",
    "daily_stats": "get_driver_operational_stats",
    "driver_stats": "get_driver_operational_stats",
    "daily_trip_stats": "get_driver_operational_stats",
    # Incidents & Complaints
    "get_recent_incidents": "get_recent_incidents",
    "recent_incidents": "get_recent_incidents",
    "top_incidents": "get_recent_incidents",
    "driver_recent_incidents": "get_recent_incidents",
    "get_driver_incidents": "get_recent_incidents",
    "driver_incidents": "get_recent_incidents",
    "get_incidents": "get_recent_incidents",
    "get_incident_detail": "get_incident_detail",
    "incident_detail": "get_incident_detail",
    "incident_description": "get_incident_detail",
    "get_recent_complaints": "get_recent_complaints",
    "recent_complaints": "get_recent_complaints",
    "top_complaints": "get_recent_complaints",
    "driver_recent_complaints": "get_recent_complaints",
    "get_driver_complaints": "get_recent_complaints",
    "driver_complaints": "get_recent_complaints",
    "get_complaints": "get_recent_complaints",
    "get_complaint_detail": "get_complaint_detail",
    "complaint_detail": "get_complaint_detail",
    "complaint_description": "get_complaint_detail",
    "incidents_and_complaints": "get_driver_incidents_and_complaints",
    "get_driver_incidents_and_complaints": "get_driver_incidents_and_complaints",
    # Knowledge Graph
    "driver_graph": "query_driver_graph",
    "query_graph": "query_driver_graph",
    "get_driver_graph": "query_driver_graph",
    "knowledge_graph": "query_driver_graph",
    "query_knowledge_graph": "query_driver_graph",
    "search_graph": "query_driver_graph",
    "get_graph": "query_driver_graph",
    "query_kg": "query_driver_graph",
    "get_kg": "query_driver_graph",
    # Full Policy Document
    "get_full_policy_document": "get_full_policy_document",
    "get_policy": "get_full_policy_document",
    "get_policy_document": "get_full_policy_document",
    "get_full_policy": "get_full_policy_document",
    "read_policy": "get_full_policy_document",
    "read_full_policy": "get_full_policy_document",
    "get_policy_by_code": "get_full_policy_document",
    "policy_document": "get_full_policy_document",
    "get_policy_content": "get_full_policy_document",
    "get_full_policy_content": "get_full_policy_document",
    "view_policy": "get_full_policy_document",
    # Policy search
    "search_policies": "search_gsm_policies",
    "search_policy": "search_gsm_policies",
    "get_policies": "search_gsm_policies",
    "lookup_policy": "search_gsm_policies",
    "search_gsm_policy": "search_gsm_policies",
    "gsm_policies": "search_gsm_policies",
    "search_regulation": "search_gsm_policies",
    "search_regulations": "search_gsm_policies",
    "search_rules": "search_gsm_policies",
    "query_policies": "search_gsm_policies",
    "policy_search": "search_gsm_policies",
    # Cancel rate calculation
    "cancel_rate": "calculate_cancel_rate",
    "calc_cancel_rate": "calculate_cancel_rate",
    "calculate_cancellation_rate": "calculate_cancel_rate",
    "get_cancel_rate": "calculate_cancel_rate",
    # Acceptance rate
    "acceptance_rate": "calculate_acceptance_rate",
    "calc_acceptance_rate": "calculate_acceptance_rate",
    "get_acceptance_rate": "calculate_acceptance_rate",
    # Completion rate
    "completion_rate": "calculate_completion_rate",
    "calc_completion_rate": "calculate_completion_rate",
    "get_completion_rate": "calculate_completion_rate",
    # Revenue evaluation & charge
    "daily_revenue": "evaluate_daily_revenue",
    "calc_daily_revenue": "evaluate_daily_revenue",
    "check_daily_revenue": "evaluate_daily_revenue",
    "revenue_charge": "calculate_revenue_charge",
    "calc_revenue_charge": "calculate_revenue_charge",
    "calculate_charge": "calculate_revenue_charge",
    # Violation penalty points
    "penalty_points": "calculate_violation_penalty_points",
    "calculate_penalty_points": "calculate_violation_penalty_points",
    "violation_penalty_points": "calculate_violation_penalty_points",
    "calc_penalty_points": "calculate_violation_penalty_points",
    # Attendance hours
    "attendance_hours": "calculate_attendance_hours",
    "calc_attendance_hours": "calculate_attendance_hours",
    "check_attendance": "calculate_attendance_hours",
    "calculate_attendance": "calculate_attendance_hours",
    # Rating condition
    "rating_condition": "evaluate_rating_condition",
    "evaluate_rating": "evaluate_rating_condition",
    "check_rating": "evaluate_rating_condition",
}


def deduplicate_repeated_text(text: str) -> str:
    """Detect and remove degenerative repeated paragraphs/sentences from LLM outputs."""
    if not text or len(text.strip()) < 40:
        return text

    # 1. Deduplicate paragraphs (consecutive or identical within output)
    raw_paras = [p.strip() for p in text.split("\n") if p.strip()]
    if len(raw_paras) > 1:
        unique_paras: list[str] = []
        seen_norm_paras: list[str] = []
        for p in raw_paras:
            p_norm = re.sub(r"\s+", " ", p.lower().strip())
            is_dup = False
            for prev_norm in seen_norm_paras:
                if len(p_norm) > 20 and (p_norm == prev_norm or (len(prev_norm) > 35 and p_norm in prev_norm)):
                    is_dup = True
                    break
            if not is_dup:
                unique_paras.append(p)
                seen_norm_paras.append(p_norm)
    else:
        unique_paras = raw_paras

    # 2. Deduplicate repeated sentences within each paragraph
    processed_paras: list[str] = []
    for p in unique_paras:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", p) if s.strip()]
        if len(sentences) >= 2:
            clean_sentences: list[str] = []
            seen_sents: list[str] = []
            for s in sentences:
                s_norm = re.sub(r"\s+", " ", s.lower())
                # If exact repeat of immediate previous sentence or in recent 2 sentences
                if len(s_norm) > 15 and seen_sents and (s_norm == seen_sents[-1] or (len(seen_sents) >= 2 and s_norm == seen_sents[-2])):
                    continue
                seen_sents.append(s_norm)
                clean_sentences.append(s)
            p = " ".join(clean_sentences)
        processed_paras.append(p)

    return "\n\n".join(processed_paras).strip()


class ReActAgent:
    """Autonomous ReAct Agent for Multi-step Reasoning & Tool Calling."""

    def __init__(
        self,
        call_llm_fn: Callable[..., tuple[str, str, dict[str, int]]],
        pipeline_ref: Any = None,
        db_repo: Any = None,
        max_iterations: int = 50,
    ) -> None:
        self.call_llm_fn = call_llm_fn
        self.pipeline_ref = pipeline_ref
        self.db_repo = db_repo
        env_val = os.getenv("REACT_MAX_ITERATIONS")
        if env_val:
            try:
                max_iterations = int(env_val)
            except ValueError:
                pass
        self.max_iterations = max_iterations
        self.tools_schema = TOOL_SCHEMAS

    def _resolve_tool_name(self, candidate_name: str) -> str | None:
        """Resolve raw tool name or alias to canonical tool schema name."""
        if not candidate_name:
            return None
        # Strip any trailing Action Input or pipe delimiters
        cand_str = re.split(r"\s*(?:\||\-\-|\bAction Input\b)\s*", str(candidate_name), maxsplit=1, flags=re.IGNORECASE)[0].strip()
        # Strip any function call parentheses
        cand_str = re.sub(r"\(.*?\)$", "", cand_str).strip()
        cleaned = re.sub(r"[`'\"\*\s]", "", cand_str).strip().lower()
        if not cleaned or re.match(r"^(?:final(?:_answer)?|finish|done|none|complete)\b", cleaned):
            return None

        known_map = {t["name"].lower(): t["name"] for t in self.tools_schema}

        # 1. Exact match against known tools
        if cleaned in known_map:
            return known_map[cleaned]

        # 2. Match against aliases table
        if cleaned in TOOL_ALIASES:
            alias_target = TOOL_ALIASES[cleaned]
            if alias_target.lower() in known_map:
                return known_map[alias_target.lower()]

        # Normalized without accents for Vietnamese heuristics
        norm = "".join(
            c for c in unicodedata.normalize("NFD", cleaned)
            if unicodedata.category(c) != "Mn"
        ).replace("đ", "d").replace("Đ", "D")

        # 3. Substring / keyword heuristics
        if "graph" in norm or "kg" in norm or "dothi" in norm:
            return "query_driver_graph"
        if "full_policy" in norm or "read_policy" in norm or ("policy" in norm and ("doc" in norm or "full" in norm or "view" in norm or "content" in norm)) or "toanvan" in norm:
            return "get_full_policy_document"
        if "policy" in norm or "policies" in norm or "quydinh" in norm or "quyche" in norm or "chinhsach" in norm:
            return "search_gsm_policies"
        if "cancel_rate" in norm or ("cancel" in norm and "rate" in norm) or "tylehuy" in norm or "tilehuy" in norm or "huychuyen" in norm:
            if "detail" in norm or "danhsach" in norm or "chitiet" in norm:
                return "get_cancelled_trips_detail"
            return "calculate_cancel_rate"
        if "cancellation" in norm or ("cancel" in norm and "trip" in norm) or "chuyenhuy" in norm:
            return "get_cancelled_trips_detail"
        if "acceptance" in norm or "nhancuoc" in norm:
            return "calculate_acceptance_rate"
        if "completion" in norm or "hoanthanh" in norm:
            return "calculate_completion_rate"
        if "attendance" in norm or "cham_cong" in norm or "chamcong" in norm or "work_hour" in norm or "ngaycong" in norm:
            return "calculate_attendance_hours"
        if "daily_stat" in norm or ("daily" in norm and "stat" in norm) or "operational" in norm or "vanhanh" in norm:
            return "get_driver_operational_stats"
        if "trip_metric" in norm or "trip_summary" in norm or ("trip" in norm and ("metric" in norm or "summary" in norm)) or "chuyendi" in norm:
            return "get_driver_trip_summary"
        if "incident_detail" in norm or ("incident" in norm and ("detail" in norm or "desc" in norm)):
            return "get_incident_detail"
        if "complaint_detail" in norm or ("complaint" in norm and ("detail" in norm or "desc" in norm)):
            return "get_complaint_detail"
        if "recent_incident" in norm or ("incident" in norm and ("recent" in norm or "top" in norm or "list" in norm)):
            return "get_recent_incidents"
        if "recent_complaint" in norm or ("complaint" in norm and ("recent" in norm or "top" in norm or "list" in norm)):
            return "get_recent_complaints"
        if ("incident" in norm and "complaint" in norm) or "incidents_and_complaints" in norm:
            return "get_driver_incidents_and_complaints"
        if "incident" in norm or "su_co" in norm or "suco" in norm:
            return "get_recent_incidents"
        if "complaint" in norm or "khieu_nai" in norm or "khieunai" in norm or "phannan" in norm:
            return "get_recent_complaints"
        if "penalty" in norm or "violation_point" in norm or "diemphat" in norm or "chetai" in norm:
            return "calculate_violation_penalty_points"
        if "revenue_charge" in norm or "giam_tru" in norm or "giamtru" in norm:
            return "calculate_revenue_charge"
        if "revenue" in norm or "doanhso" in norm or "doanhthu" in norm:
            return "evaluate_daily_revenue"
        if "profile" in norm or "driver_info" in norm or ("driver" in norm and "info" in norm) or "hoso" in norm:
            return "get_driver_profile"

        # 4. Fuzzy match using difflib
        close_matches = difflib.get_close_matches(cleaned, list(known_map.keys()), n=1, cutoff=0.6)
        if close_matches:
            return known_map[close_matches[0]]

        return None

    def _build_tools_prompt(self) -> str:
        """Format tools description and parameter schema for the LLM system prompt."""
        lines = []
        for t in self.tools_schema:
            name = t["name"]
            desc = t["description"]
            params = t.get("parameters", {}).get("properties", {})
            param_desc = []
            for p_name, p_info in params.items():
                p_type = p_info.get("type", "string")
                p_text = p_info.get("description", "")
                param_desc.append(f"    - `{p_name}` ({p_type}): {p_text}")
            lines.append(f"- **`{name}`**: {desc}")
            if param_desc:
                lines.append("  Tham số:")
                lines.extend(param_desc)
        return "\n".join(lines)

    def _sanitize_date_arg(self, raw_date: Any) -> str | None:
        """Sanitize date argument to avoid false filtering when querying entire snapshot history."""
        if not raw_date:
            return None
        s = str(raw_date).strip()
        if not s or "snapshot" in s.lower() or "toàn kỳ" in s.lower() or s.lower() in ("none", "null"):
            return None
        ctx = getattr(self, "active_context", {}) or {}
        # If user did NOT specify a date filter in their question, strip any date matching snapshot cutoff
        if not ctx.get("user_specified_time", False):
            if s.startswith("2026-09-18") or s.startswith("18/09/2026") or s == "2026-09-15":
                return None
        return s

    def _resolve_context_args(self, action_input: dict[str, Any]) -> dict[str, Any]:
        """Auto-fill missing arguments from active context if LLM omitted them."""
        args = dict(action_input or {})
        ctx = getattr(self, "active_context", {}) or {}
        if not args.get("driver_id") and not args.get("driver_identifier"):
            if ctx.get("driver_id"):
                args["driver_id"] = ctx["driver_id"]
                args["driver_identifier"] = ctx["driver_id"]
            elif ctx.get("driver_mention"):
                args["driver_identifier"] = ctx["driver_mention"]
        if not args.get("snapshot_id") and ctx.get("snapshot_id"):
            args["snapshot_id"] = ctx["snapshot_id"]
        if not args.get("date"):
            if ctx.get("user_specified_time"):
                if ctx.get("time_resolved"):
                    args["date"] = ctx["time_resolved"]
                elif ctx.get("time_scope"):
                    args["date"] = ctx["time_scope"]
        return args

    def _get_tool_signature(self, action_name: str, args: dict[str, Any]) -> str:
        """Compute normalized canonical fingerprint of a tool call to detect redundant repetitions."""
        name_clean = str(action_name or "").strip().lower()
        clean_args: dict[str, Any] = {}
        for k, v in (args or {}).items():
            k_clean = str(k).strip().lower()
            if k_clean in ("driver_identifier", "driver_id", "driver_code"):
                clean_args["driver_identifier"] = str(v).strip().upper()
            elif k_clean == "query":
                clean_args["query"] = str(v).strip().lower()
            elif k_clean == "policy_code":
                clean_args["policy_code"] = str(v).strip().upper() if v else ""
            elif k_clean == "date":
                clean_args["date"] = str(v).strip()
            elif isinstance(v, (int, float, bool, str)):
                clean_args[k_clean] = v
            else:
                clean_args[k_clean] = str(v)
        return f"{name_clean}::{json.dumps(clean_args, sort_keys=True, ensure_ascii=False)}"

    def _extract_thought(self, raw_text: str) -> str:
        """Extract the reasoning thought before any Action header."""
        thought_match = re.search(r"(?:\*\*)?Thought(?:\*\*)?:\s*(.*?)(?=\n*(?:\*\*)?Action(?:\s*\d+)?(?:\*\*)?:\s*|\Z)", raw_text, re.DOTALL | re.IGNORECASE)
        if thought_match and thought_match.group(1).strip():
            return thought_match.group(1).strip()
        before_action = re.split(r"(?:\*\*)?Action(?:\s*\d+)?(?:\*\*)?:\s*", raw_text, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        cleaned = re.sub(r"^(?:\*\*)?Thought(?:\*\*)?:\s*", "", before_action, flags=re.IGNORECASE).strip()
        return cleaned or "Thực thi công cụ tra cứu dữ liệu từ hệ thống."

    def _parse_actions(self, raw_text: str) -> list[tuple[str, dict[str, Any]]]:
        """Parse one or multiple Action and Action Input blocks from LLM output."""
        actions: list[tuple[str, dict[str, Any]]] = []

        # 1. Check for JSON array under Actions:
        m_array = re.search(r"Actions:\s*(\[\s*\{.*?\}\s*\])", raw_text, re.DOTALL | re.IGNORECASE)
        if m_array:
            try:
                arr = json.loads(m_array.group(1))
                for item in arr:
                    if isinstance(item, dict) and "action" in item:
                        act_val = str(item["action"]).strip()
                        resolved = self._resolve_tool_name(act_val)
                        if resolved:
                            actions.append((resolved, item.get("action_input", {})))
                if actions:
                    return actions
            except Exception:
                pass

        # 2. Match all Action [i]: ... Action Input [i]: {...} blocks (separated by newline, pipe |, or markdown)
        pattern = re.compile(
            r"(?:\*\*)?Action(?:\s*\d+)?(?:\*\*)?:\s*([^\n\r\|]+?)\s*(?:\r?\n+|\||\-\-)\s*(?:\*\*)?Action Input(?:\s*\d+)?(?:\*\*)?:\s*(?:```(?:json)?\s*)?(\{.*?\})(?:\s*```)?",
            re.DOTALL | re.IGNORECASE,
        )
        matches = pattern.findall(raw_text)
        for act_str, inp_str in matches:
            act_clean = act_str.strip().strip("`'\"")
            resolved_tool = self._resolve_tool_name(act_clean)
            if not resolved_tool:
                continue

            parsed_inp: dict[str, Any] = {}
            try:
                parsed_inp = json.loads(inp_str.strip())
            except Exception:
                kv_pairs = re.findall(r'"([a-zA-Z0-9_]+)"\s*:\s*(?:\'([^\']*)\'|"([^"]*)"|(\d+)|(true|false))', inp_str, re.IGNORECASE)
                for k, s_val1, s_val2, n_val, b_val in kv_pairs:
                    s_val = s_val1 or s_val2
                    if s_val:
                        parsed_inp[k] = s_val
                    elif n_val:
                        parsed_inp[k] = int(n_val)
                    elif b_val:
                        parsed_inp[k] = (b_val.lower() == "true")

            actions.append((resolved_tool, parsed_inp))

        # 3. Fallback to single action regex if pattern found nothing but Action exists
        if not actions and re.search(r"\bAction(?:\s*\d+)?:\s*", raw_text, re.IGNORECASE):
            action_header_match = re.search(r"Action(?:\s*\d+)?:\s*(.*?)(?:\s*(?:\||\-\-|\r?\n)\s*Action Input|\r?\n|\Z)", raw_text, re.IGNORECASE)
            action_snippet = action_header_match.group(1).strip() if action_header_match else raw_text
            resolved_name = self._resolve_tool_name(action_snippet)

            input_match = re.search(r"Action Input(?:\s*\d+)?:\s*(?:```(?:json)?\s*)?(\{.*?\})(?:\s*```)?", raw_text, re.DOTALL | re.IGNORECASE)
            action_input: dict[str, Any] = {}
            if input_match:
                try:
                    action_input = json.loads(input_match.group(1).strip())
                except Exception:
                    kv_pairs = re.findall(r'"([a-zA-Z0-9_]+)"\s*:\s*(?:\'([^\']*)\'|"([^"]*)"|(\d+)|(true|false))', input_match.group(1), re.IGNORECASE)
                    for k, s_val1, s_val2, n_val, b_val in kv_pairs:
                        s_val = s_val1 or s_val2
                        if s_val:
                            action_input[k] = s_val
                        elif n_val:
                            action_input[k] = int(n_val)
                        elif b_val:
                            action_input[k] = (b_val.lower() == "true")
            if resolved_name:
                actions.append((resolved_name, action_input))

        return actions

    def execute_tool(self, action_name: str, action_input: dict[str, Any]) -> tuple[Any, dict[str, Any] | None]:
        """Dispatch tool name with parameters and generate corresponding citation."""
        name = self._resolve_tool_name(action_name) or str(action_name or "").strip()
        args = self._resolve_context_args(action_input)
        ctx = getattr(self, "active_context", {}) or {}
        citation = None

        # Guard: In pure policy queries without driver, reject hallucinated driver tools
        current_q = getattr(self, "current_query", "") or ""
        is_pure_policy_query = (
            ctx.get("intent") == "POLICY_LOOKUP"
            or (
                not ctx.get("driver_id")
                and not ctx.get("driver_mention")
                and not bool(re.search(r"\b(DRV-\d+|v2_drv_\d+|tài xế|bác tài|anh \w+|chị \w+)\b", current_q, re.IGNORECASE))
            )
        )
        driver_tools = (
            "get_driver_operational_stats",
            "get_driver_daily_stats",
            "get_driver_profile",
            "get_driver_trip_summary",
            "get_driver_trip_metrics",
            "get_cancelled_trips_detail",
            "query_driver_graph",
        )
        if is_pure_policy_query and name in driver_tools and current_q:
            return {
                "tool": name,
                "error": (
                    f"Thao tác không được phép: Câu hỏi '{current_q}' là tra cứu chính sách/quy chế chung (không có đối tượng tài xế cụ thể). "
                    f"Bạn TUYỆT ĐỐI KHÔNG ĐƯỢC tự bịa mã tài xế '{args.get('driver_id') or args.get('driver_identifier')}' "
                    "hoặc gọi công cụ thông tin tài xế. Dữ liệu văn bản quy chế đã được tải ở các bước trước. "
                    "BẮT BUỘC dừng gọi công cụ và xuất Thought + Final Answer theo Mẫu Dạng 2 ngay bây giờ."
                ),
                "_reflection_hint": "Dừng gọi công cụ tài xế. Hãy chuyển sang xuất Final Answer cho câu hỏi tra cứu chính sách theo Mẫu Dạng 2.",
                "_force_finalize": True,
            }, None

        try:
            if name == "calculate_acceptance_rate":

                thresh_pct = float(args["threshold_pct"]) if "threshold_pct" in args and args["threshold_pct"] is not None else None
                res = calculate_acceptance_rate(
                    offered_trips=int(args.get("offered_trips", 0)),
                    accepted_trips=int(args.get("accepted_trips", 0)),
                    threshold_pct=thresh_pct,
                )
                citation = {
                    "source_kind": "computation",
                    "citation_locator": "computation:acceptance_rate",
                    "policy_alias": "Tỷ lệ nhận cuốc",
                    "policy_title": "Tỷ lệ nhận cuốc (Acceptance Rate)",
                    "category": "Tính toán số học chuẩn xác",
                    "content": res.get("summary", ""),
                }
                return res, citation

            elif name == "calculate_completion_rate":
                thresh_pct = float(args["threshold_pct"]) if "threshold_pct" in args and args["threshold_pct"] is not None else None
                res = calculate_completion_rate(
                    accepted_trips=int(args.get("accepted_trips", 0)),
                    completed_trips=int(args.get("completed_trips", 0)),
                    threshold_pct=thresh_pct,
                )
                citation = {
                    "source_kind": "computation",
                    "citation_locator": "computation:completion_rate",
                    "policy_alias": "Tỷ lệ hoàn thành cuốc",
                    "policy_title": "Tỷ lệ hoàn thành cuốc (Completion Rate)",
                    "category": "Tính toán số học chuẩn xác",
                    "content": res.get("summary", ""),
                }
                return res, citation

            elif name == "evaluate_daily_revenue":
                thresh_vnd = int(args["threshold_vnd"]) if "threshold_vnd" in args and args["threshold_vnd"] is not None else None
                driver_ident = str(args.get("driver_id") or args.get("driver_identifier") or ctx.get("driver_id") or ctx.get("driver_mention") or "")
                target_snap = args.get("snapshot_id") or ctx.get("snapshot_id")
                target_date = self._sanitize_date_arg(args.get("date")) or (ctx.get("time_resolved") if ctx.get("user_specified_time") else None)
                rev_in = int(args["revenue_vnd"]) if "revenue_vnd" in args and args["revenue_vnd"] is not None else None
                res = evaluate_daily_revenue(
                    revenue_vnd=rev_in,
                    threshold_vnd=thresh_vnd,
                    date=target_date,
                    driver_id=driver_ident,
                    snapshot_id=target_snap,
                    db_repo=self.db_repo,
                )
                time_loc = f":{target_date}" if target_date else ""
                citation = {
                    "source_kind": "database" if res.get("source") == "db_trips" else "computation",
                    "citation_locator": f"ledger:revenue:{driver_ident}{time_loc}" if driver_ident else "computation:daily_revenue",
                    "policy_alias": "Định mức doanh số",
                    "policy_title": f"Kiểm tra doanh số {driver_ident or ''} {target_date or ''}".strip(),
                    "category": "Tính toán số học chuẩn xác",
                    "content": res.get("summary", ""),
                }
                return res, citation

            elif name == "calculate_cancel_rate":
                thresh_pct = float(args["threshold_pct"]) if "threshold_pct" in args and args["threshold_pct"] is not None else None
                driver_ident = args.get("driver_identifier") or args.get("driver_id") or ctx.get("driver_id") or ctx.get("driver_mention")
                target_snap = args.get("snapshot_id") or ctx.get("snapshot_id")
                target_date = self._sanitize_date_arg(args.get("date")) or (ctx.get("time_resolved") if ctx.get("user_specified_time") else None)
                c_trips = int(args.get("completed_trips", 0)) if "completed_trips" in args and args["completed_trips"] is not None else None
                c_canc = int(args.get("cancelled_trips", 0)) if "cancelled_trips" in args and args["cancelled_trips"] is not None else None
                tot_trips = int(args.get("total_trips", 0)) if "total_trips" in args and args["total_trips"] is not None else None
                res = calculate_cancel_rate(
                    cancelled_trips=c_canc,
                    total_trips=tot_trips,
                    completed_trips=c_trips,
                    threshold_pct=thresh_pct,
                    driver_identifier=driver_ident,
                    snapshot_id=target_snap,
                    date=target_date,
                    db_repo=self.db_repo,
                    pipeline=self.pipeline_ref,
                )
                citation = {
                    "source_kind": "computation",
                    "citation_locator": "computation:cancel_rate_30d",
                    "policy_alias": "Tỷ lệ hủy chuyến",
                    "policy_title": "Tỷ lệ hủy chuyến 30 ngày (cancel_rate_30d)",
                    "category": "Tính toán số học chuẩn xác",
                    "content": res.get("summary", ""),
                }
                return res, citation

            elif name == "evaluate_rating_condition":
                threshold_val = float(args["threshold"]) if "threshold" in args and args["threshold"] is not None else None
                op_val = str(args.get("operator", ">="))
                res = evaluate_rating_condition(
                    rating_stars=float(args.get("rating_stars", 5.0)),
                    threshold=threshold_val,
                    operator=op_val,
                )
                citation = {
                    "source_kind": "computation",
                    "citation_locator": "condition:rating_quality",
                    "policy_alias": "Xếp hạng sao",
                    "policy_title": "Đánh giá chất lượng dịch vụ sao khách hàng",
                    "category": "Chỉ số chất lượng",
                    "content": res.get("summary", ""),
                }
                return res, citation

            elif name == "calculate_revenue_charge":
                res = calculate_revenue_charge(
                    revenue_vnd=int(args.get("revenue_vnd", 0)),
                    program=args.get("program"),
                    operating_region=args.get("operating_region"),
                    is_operating_day=args.get("is_operating_day"),
                )
                citation = {
                    "source_kind": "computation",
                    "citation_locator": "computation:revenue_charge",
                    "policy_alias": "Giảm trừ doanh số",
                    "policy_title": "Khoản giảm trừ bảo lưu doanh thu",
                    "category": "Quy chế tài chính",
                    "content": res.get("summary", ""),
                }
                return res, citation

            elif name == "calculate_violation_penalty_points":
                pts = args.get("points", 0)
                v_cnt = int(args.get("violation_count", 0)) if "violation_count" in args and args["violation_count"] is not None else None
                r_codes = args.get("rule_codes")
                res = calculate_violation_penalty_points(
                    points=pts,
                    violation_count=v_cnt,
                    rule_codes=r_codes,
                )
                citation = {
                    "source_kind": "computation",
                    "citation_locator": "computation:penalty_points",
                    "policy_alias": "Điểm phạt & chế tài",
                    "policy_title": "Thang chế tài vi phạm quy chế GSM",
                    "category": "Quy chế xử lý vi phạm",
                    "content": res.get("summary", ""),
                }
                return res, citation

            elif name == "calculate_attendance_hours":
                h_worked = args.get("hours_worked", 0.0)
                std_h = float(args.get("standard_hours_per_day", 8.0))
                req_d = int(args["required_days"]) if "required_days" in args and args["required_days"] is not None else None
                res = calculate_attendance_hours(
                    hours_worked=h_worked,
                    standard_hours_per_day=std_h,
                    required_days=req_d,
                )
                citation = {
                    "source_kind": "computation",
                    "citation_locator": "computation:attendance_hours",
                    "policy_alias": "Ngày công & giờ trực",
                    "policy_title": "Định mức ngày công và thời gian làm việc",
                    "category": "Quy chế lao động & vận hành",
                    "content": res.get("summary", ""),
                }
                return res, citation

            elif name == "get_driver_profile":
                driver_ident = str(args.get("driver_identifier") or args.get("driver_id") or "")
                res = get_driver_profile(
                    db_repo=self.db_repo,
                    driver_identifier=driver_ident,
                )
                citation = {
                    "source_kind": "database",
                    "citation_locator": f"entity:driver:{driver_ident}",
                    "policy_alias": "Hồ sơ tài xế",
                    "policy_title": f"Hồ sơ đối tác {driver_ident}",
                    "category": "Cơ sở dữ liệu nhân sự",
                    "content": res.get("summary", ""),
                }
                return res, citation

            elif name in ("get_driver_trip_summary", "get_driver_trip_metrics"):
                driver_ident = str(args.get("driver_identifier") or args.get("driver_id") or "")
                target_snap = args.get("snapshot_id") or ctx.get("snapshot_id")
                target_date = self._sanitize_date_arg(args.get("date")) or (ctx.get("time_resolved") if ctx.get("user_specified_time") else None)
                res = get_driver_trip_summary(
                    db_repo=self.db_repo,
                    driver_identifier=driver_ident,
                    snapshot_id=target_snap,
                    date=target_date,
                    pipeline=self.pipeline_ref,
                )
                time_loc = f":{target_date}" if target_date else ""
                citation = {
                    "source_kind": "kg_subgraph",
                    "citation_locator": f"ledger:trips:metrics:{driver_ident}{time_loc}",
                    "policy_alias": "Số liệu chuyến xe",
                    "policy_title": f"Thống kê chuyến xe tài xế {driver_ident}",
                    "category": "Cơ sở dữ liệu vận hành",
                    "content": res.get("summary", ""),
                }
                return res, citation

            elif name == "get_cancelled_trips_detail":
                driver_ident = str(args.get("driver_identifier") or args.get("driver_id") or "")
                target_snap = args.get("snapshot_id") or ctx.get("snapshot_id")
                target_date = self._sanitize_date_arg(args.get("date")) or (ctx.get("time_resolved") if ctx.get("user_specified_time") else None)
                target_limit = int(args.get("limit") or 10)
                res = get_cancelled_trips_detail(
                    db_repo=self.db_repo,
                    driver_identifier=driver_ident,
                    snapshot_id=target_snap,
                    date=target_date,
                    limit=target_limit,
                    pipeline=self.pipeline_ref,
                )
                time_loc = f":{target_date}" if target_date else ""
                citation = {
                    "source_kind": "kg_subgraph",
                    "citation_locator": f"ledger:trips:cancellations:{driver_ident}{time_loc}",
                    "policy_alias": "Chi tiết chuyến hủy",
                    "policy_title": f"Danh sách chuyến hủy của tài xế {driver_ident}",
                    "category": "Cơ sở dữ liệu vận hành",
                    "content": res.get("summary", ""),
                }
                return res, citation

            elif name in ("get_driver_operational_stats", "get_driver_daily_stats"):
                target_date = self._sanitize_date_arg(args.get("date")) or (ctx.get("time_resolved") if ctx.get("user_specified_time") else None)
                target_snap = args.get("snapshot_id") or ctx.get("snapshot_id")
                driver_ident = str(args.get("driver_id") or args.get("driver_identifier") or ctx.get("driver_id") or ctx.get("driver_mention") or "")
                res = get_driver_operational_stats(
                    db_repo=self.db_repo,
                    driver_id=driver_ident,
                    date=target_date,
                    snapshot_id=target_snap,
                    pipeline=self.pipeline_ref,
                )
                citation = {
                    "source_kind": "kg_subgraph",
                    "citation_locator": f"ledger:trips:{driver_ident}:{target_date or 'all'}",
                    "policy_alias": "Số liệu vận hành",
                    "policy_title": f"Chuyến đi và doanh thu {target_date or 'Toàn kỳ'}",
                    "category": "Cơ sở dữ liệu vận hành",
                    "content": res.get("summary", ""),
                }
                return res, citation

            elif name == "get_recent_incidents":
                driver_ident = str(args.get("driver_identifier") or args.get("driver_id") or ctx.get("driver_id") or ctx.get("driver_mention") or "")
                target_snap = args.get("snapshot_id") or ctx.get("snapshot_id")
                target_date = self._sanitize_date_arg(args.get("date")) or (ctx.get("time_resolved") if ctx.get("user_specified_time") else None)
                l_limit = int(args.get("limit", 10))
                res = get_recent_incidents(
                    db_repo=self.db_repo,
                    driver_identifier=driver_ident,
                    pipeline=self.pipeline_ref,
                    snapshot_id=target_snap,
                    date=target_date,
                    limit=l_limit,
                )
                time_loc = f":{target_date}" if target_date else ""
                citation = {
                    "source_kind": "database",
                    "citation_locator": f"ledger:incidents:{driver_ident}{time_loc}",
                    "policy_alias": "Danh sách sự cố",
                    "policy_title": f"Danh sách sự cố gần nhất của tài xế {driver_ident}",
                    "category": "Cơ sở dữ liệu vận hành",
                    "content": res.get("summary", ""),
                }
                return res, citation

            elif name == "get_incident_detail":
                inc_id = str(args.get("incident_id") or args.get("id") or "")
                res = get_incident_detail(
                    incident_id=inc_id,
                    db_repo=self.db_repo,
                    pipeline=self.pipeline_ref,
                )
                citation = {
                    "source_kind": "database",
                    "citation_locator": f"ledger:incident:detail:{inc_id}",
                    "policy_alias": "Chi tiết sự cố",
                    "policy_title": f"Chi tiết biên bản sự cố {inc_id}",
                    "category": "Cơ sở dữ liệu vận hành",
                    "content": res.get("summary", ""),
                }
                return res, citation

            elif name == "get_recent_complaints":
                driver_ident = str(args.get("driver_identifier") or args.get("driver_id") or ctx.get("driver_id") or ctx.get("driver_mention") or "")
                target_snap = args.get("snapshot_id") or ctx.get("snapshot_id")
                target_date = self._sanitize_date_arg(args.get("date")) or (ctx.get("time_resolved") if ctx.get("user_specified_time") else None)
                l_limit = int(args.get("limit", 10))
                res = get_recent_complaints(
                    db_repo=self.db_repo,
                    driver_identifier=driver_ident,
                    pipeline=self.pipeline_ref,
                    snapshot_id=target_snap,
                    date=target_date,
                    limit=l_limit,
                )
                time_loc = f":{target_date}" if target_date else ""
                citation = {
                    "source_kind": "database",
                    "citation_locator": f"ledger:complaints:{driver_ident}{time_loc}",
                    "policy_alias": "Danh sách khiếu nại",
                    "policy_title": f"Danh sách khiếu nại gần nhất của tài xế {driver_ident}",
                    "category": "Cơ sở dữ liệu vận hành",
                    "content": res.get("summary", ""),
                }
                return res, citation

            elif name == "get_complaint_detail":
                cmp_id = str(args.get("complaint_id") or args.get("id") or "")
                res = get_complaint_detail(
                    complaint_id=cmp_id,
                    db_repo=self.db_repo,
                    pipeline=self.pipeline_ref,
                )
                citation = {
                    "source_kind": "database",
                    "citation_locator": f"ledger:complaint:detail:{cmp_id}",
                    "policy_alias": "Chi tiết khiếu nại",
                    "policy_title": f"Chi tiết phản ánh khiếu nại {cmp_id}",
                    "category": "Cơ sở dữ liệu vận hành",
                    "content": res.get("summary", ""),
                }
                return res, citation

            elif name == "get_driver_incidents_and_complaints":
                driver_ident = str(args.get("driver_identifier") or args.get("driver_id") or "")
                target_snap = args.get("snapshot_id") or ctx.get("snapshot_id")
                target_date = self._sanitize_date_arg(args.get("date")) or (ctx.get("time_resolved") if ctx.get("user_specified_time") else None)
                l_limit = int(args.get("limit", 20))
                res = get_driver_incidents_and_complaints(
                    db_repo=self.db_repo,
                    driver_identifier=driver_ident,
                    pipeline=self.pipeline_ref,
                    snapshot_id=target_snap,
                    date=target_date,
                    limit=l_limit,
                )
                time_loc = f":{target_date}" if target_date else ""
                citation = {
                    "source_kind": "database",
                    "citation_locator": f"ledger:incidents:{driver_ident}{time_loc}",
                    "policy_alias": "Sự cố & Khiếu nại",
                    "policy_title": f"Biên bản sự cố và phản ánh khách hàng của {driver_ident}",
                    "category": "Cơ sở dữ liệu vận hành",
                    "content": res.get("summary", ""),
                }
                return res, citation

            elif name in ("query_driver_graph", "query_graph"):
                driver_ident = str(args.get("driver_identifier") or args.get("driver_id") or args.get("driver") or args.get("driver_name") or args.get("code") or ctx.get("driver_id") or ctx.get("driver_mention") or "")
                target_snap = args.get("snapshot_id") or args.get("snapshot") or ctx.get("snapshot_id")
                target_date = self._sanitize_date_arg(args.get("date")) or (ctx.get("time_resolved") if ctx.get("user_specified_time") else None)
                target_focus = args.get("focus")
                semantic_q = args.get("semantic_query")
                limit_val = int(args.get("limit", 10)) if "limit" in args and args["limit"] is not None else 10
                t_nodes = args.get("target_node_types")
                e_types = args.get("edge_types")
                res = query_driver_graph(
                    pipeline=self.pipeline_ref,
                    driver_id=driver_ident,
                    snapshot_id=target_snap,
                    date=target_date,
                    focus=target_focus,
                    target_node_types=t_nodes,
                    edge_types=e_types,
                    semantic_query=semantic_q,
                    limit=limit_val,
                )
                focus_label = target_focus.upper() if target_focus else "ALL"
                citation = {
                    "source_kind": "kg_subgraph",
                    "citation_locator": f"kg:subgraph:{driver_ident}:{target_focus or 'all'}",
                    "policy_alias": "Đồ thị tri thức (KG)",
                    "policy_title": f"Mạng lưới nút & quan hệ của tài xế {driver_ident} (Nhánh: {focus_label})",
                    "category": "Đồ thị tri thức (Knowledge Graph)",
                    "content": res.get("summary", ""),
                }
                return res, citation

            elif name == "search_gsm_policies":
                res = search_gsm_policies(
                    pipeline=self.pipeline_ref,
                    query=str(args.get("query", "")),
                    policy_code=args.get("policy_code"),
                )
                p_list = res.get("policies", [])
                policy_citations = []
                for p in p_list:
                    policy_citations.append({
                        "source_kind": "document",
                        "citation_locator": p.get("chunk_id", "policy:gsm"),
                        "policy_alias": p.get("policy_alias") or args.get("policy_code") or "Quy chế GSM",
                        "policy_title": p.get("title") or f"Quy định liên quan {args.get('query', '')}",
                        "category": "Văn bản quy chế GSM",
                        "content": p.get("snippet", res.get("summary", "")),
                    })
                if not policy_citations:
                    fallback_alias = args.get("policy_code") or "Quy chế GSM"
                    policy_citations.append({
                        "source_kind": "document",
                        "citation_locator": f"policy:{args.get('policy_code') or 'gsm'}",
                        "policy_alias": fallback_alias,
                        "policy_title": f"Văn bản quy chế {args.get('policy_code') or args.get('query', '')}".strip(),
                        "category": "Văn bản quy chế GSM",
                        "content": res.get("summary", ""),
                    })
                return res, policy_citations

            elif name == "get_full_policy_document":
                p_code = args.get("policy_code") or ""
                m_chars = int(args.get("max_chars", 8000))
                res = get_full_policy_document(
                    pipeline=self.pipeline_ref,
                    policy_code=p_code,
                    max_chars=m_chars,
                )
                policy_citations = []
                docs_list = res.get("documents") or []
                if docs_list:
                    for d in docs_list:
                        c_code = d.get("policy_code", "")
                        d_title = d.get("title") or f"Văn bản quy chế {c_code}"
                        policy_citations.append({
                            "source_kind": "document",
                            "citation_locator": f"policy:{c_code}",
                            "policy_alias": c_code or "Quy chế GSM",
                            "policy_title": d_title,
                            "category": "Văn bản quy chế GSM toàn văn",
                            "content": f"{d_title} (Mã: {c_code})\n{d.get('content', '')[:600]}...",
                        })
                else:
                    doc_title = res.get("title") or f"Văn bản quy chế {res.get('policy_code') or p_code}"
                    policy_citations.append({
                        "source_kind": "document",
                        "citation_locator": f"policy:{res.get('policy_code') or p_code}",
                        "policy_alias": res.get("policy_code") or p_code or "Quy chế GSM",
                        "policy_title": doc_title,
                        "category": "Văn bản quy chế GSM toàn văn",
                        "content": f"{doc_title} (Mã: {res.get('policy_code') or p_code})\n{res.get('content', '')[:600]}...",
                    })
                return res, policy_citations


            else:
                known_names_str = ", ".join(f"`{t['name']}`" for t in self.tools_schema)
                return {"error": f"Không tìm thấy công cụ '{name}'. BẮT BUỘC chỉ sử dụng các công cụ trong danh sách sau: {known_names_str}."}, None

        except Exception as e:
            return {"error": f"Lỗi khi thực thi công cụ '{name}': {str(e)}"}, None

    def run_stream(self, query: str, context: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        """Run the ReAct autonomous loop and yield live step events (thoughts, actions, observations)."""
        context = context or {}
        self.active_context = context
        self.current_query = query
        tools_prompt = self._build_tools_prompt()

        system_prompt = (
            "Bạn là Trợ lý AI Quản trị & Vận hành Chuyên nghiệp của Taxi Xanh SM (GSM).\n"
            "Bạn giải quyết các câu hỏi theo mô hình ReAct (Reasoning + Acting) - suy luận nhiều bước và chủ động gọi công cụ.\n\n"
            f"DANH SÁCH CÔNG CỤ (TOOLS) BẠN CÓ QUYỀN SỬ DỤNG:\n{tools_prompt}\n\n"
            "QUY TẮC ĐỊNH DẠNG REACT (HỖ TRỢ 1 HOẶC NHIỀU CÔNG CỤ):\n"
            "Ở mỗi bước suy luận, bạn có thể gọi 1 HOẶC NHIỀU công cụ nếu các công cụ đó có thể thực hiện đồng thời hoặc độc lập (ví dụ: vừa tra cứu quy chế `search_gsm_policies`, vừa lấy số liệu tài xế `get_driver_operational_stats`, hoặc tính toán cùng lúc `calculate_acceptance_rate` và `calculate_completion_rate`).\n"
            "Cấu trúc xuất ra:\n"
            "Thought: <Suy nghĩ logic: đang cần kiểm tra thông tin gì, tại sao, và chọn công cụ nào>\n"
            "Action: <Tên công cụ 1>\n"
            "Action Input: <Tham số gọi công cụ 1 định dạng JSON thuần>\n"
            "Action: <Tên công cụ 2> (nếu cần gọi thêm công cụ khác trong cùng bước)\n"
            "Action Input: <Tham số gọi công cụ 2 định dạng JSON thuần>\n\n"
            "QUY TẮC DỪNG BẮT BUỘC:\n"
            "- DỪNG LẠI NGAY LẬP TỨC sau khi xuất xong Action Input cuối cùng của bước đó.\n"
            "- TUYỆT ĐỐI CẤM tự viết thẻ 'Observation:' hoặc tự bịa kết quả tra cứu của công cụ.\n"
            "- Hệ thống sẽ tự động thực thi từng công cụ và cung cấp kết quả 'Observation:' thực tế từ cơ sở dữ liệu ở bước tiếp theo.\n\n"
            "QUY TẮC CHỐNG LẶP CÔNG CỤ (ANTI-LOOP):\n"
            "1. TUYỆT ĐỐI KHÔNG gọi lại cùng một công cụ với cùng bộ tham số mà bạn đã gọi ở các bước trước đó. Dữ liệu trong hệ thống là cố định, kết quả trả về sẽ hoàn toàn không khác biệt và gây lãng phí vòng lặp.\n"
            "2. Khi đã có Observation từ công cụ, hãy phân tích dữ liệu đã nhận được để suy luận bước tiếp theo. Nếu muốn tìm kiếm thêm, BẮT BUỘC phải thay đổi từ khóa (query) hoặc thay đổi tham số khác.\n"
            "3. Khi đã có đủ thông tin hoặc đã gọi đủ các công cụ cần thiết, hãy tiến hành xuất Thought và Final Answer ngay, không gọi lại công cụ cũ.\n\n"
            "QUY TẮC PHÂN BIỆT RÕ RÀNG GIỮA 2 LOẠI CÂU HỎI:\n"
            "--- TRƯỜNG HỢP A: KHI CÂU HỎI LÀ TRA CỨU CHÍNH SÁCH / QUY CHẾ CHUNG (KHÔNG có tên/mã tài xế, ví dụ: 'chính sách hủy chuyến nói về gì'): ---\n"
            "  + Bước 1 (Tìm kiếm & Định vị): Gọi `search_gsm_policies` với câu hỏi để tìm chunk và xác định danh sách các mã văn bản quy chế liên quan (ví dụ: P094, P027, P017).\n"
            "  + Bước 2 (Đọc toàn văn văn bản): Gọi `get_full_policy_document` với tham số `policy_code` (hỗ trợ truyền nhiều mã cùng lúc, ví dụ: 'P094, P027, P017') để đọc toàn văn đầy đủ toàn bộ các quy chế này.\n"
            "  + Bước 3 (Kết luận): Sau khi đã có Observation từ Bước 2, bạn ĐÃ CÓ ĐỦ DỮ LIỆU. BẮT BUỘC xuất ngay Thought và Final Answer theo Mẫu Dạng 2 (Báo cáo Tra cứu Quy chế GSM).\n"
            "  + TUYỆT ĐỐI CẤM đối với Trường Hợp A: TUYỆT ĐỐI CẤM gọi bất kỳ công cụ tài xế nào (`get_driver_operational_stats`, `get_driver_profile`, `get_driver_trip_summary`, `query_driver_graph`...) và TUYỆT ĐỐI CẤM tự bịa ra mã tài xế (như DRV-002) hay ngày tháng khi người dùng không hỏi về tài xế!\n\n"
            "--- TRƯỜNG HỢP B: KHI CÂU HỎI LIÊN QUAN ĐẾN TÀI XẾ / HOẠT ĐỘNG VẬN HÀNH: ---\n"
            "  + LỰA CHỌN CÔNG CỤ ĐÚNG TRỌNG TÂM CÂU HỎI:\n"
            "    * Hỏi về hồ sơ nhân sự, thông tin tài xế, phương tiện, biển số mặc định, trạng thái: Gọi `get_driver_profile`.\n"
            "    * Hỏi về tổng hợp chuyến đi, số cuốc hoàn thành/hủy, tỷ lệ hủy, tổng quan sự cố/khiếu nại: Gọi `get_driver_trip_summary` (hoặc `get_driver_trip_metrics`).\n"
            "    * Hỏi về chi tiết danh sách chuyến bị hủy và nguyên nhân hủy: Gọi `get_cancelled_trips_detail` (mặc định lấy tối đa 10 chuyến hủy gần nhất, kèm thống kê phân loại nguyên nhân và bên hủy).\n"
            "    * Hỏi về cuốc xe (phát, nhận, hoàn thành, hủy) và doanh thu theo ngày hoặc tháng/kỳ: Gọi `get_driver_operational_stats`.\n"
            "    * Hỏi về danh sách khiếu nại/phản ánh khách hàng gần nhất: Gọi `get_recent_complaints` (hoặc `get_complaint_detail` khi cần xem chi tiết một vụ việc).\n"
            "    * Hỏi về danh sách sự cố vận hành, kỹ thuật: Gọi `get_recent_incidents` (hoặc `get_incident_detail` khi cần xem chi tiết một sự cố).\n"
            "    * Khi câu hỏi yêu cầu tra cứu đồ thị tri thức (Knowledge Graph), duyệt mạng lưới quan hệ đa thực thể hoặc tìm kiếm ngữ nghĩa theo chủ đề (focus):\n"
            "      - Khu vực, thành phố, địa bàn hoạt động hoặc zone đón/trả: Gọi `query_driver_graph(driver_identifier=..., focus='location')` -> Duyệt Driver -> Region và Driver -> Trip -> Zone.\n"
            "      - Phản ánh, khiếu nại tìm kiếm theo ngữ nghĩa sâu hoặc xác định chuyến xe bị khiếu nại: Gọi `query_driver_graph(driver_identifier=..., focus='complaints', semantic_query='...')` -> Duyệt Driver -> Complaint -> Trip.\n"
            "      - Sự cố vận hành, kỹ thuật liên kết quy chế: Gọi `query_driver_graph(driver_identifier=..., focus='incidents', semantic_query='...')` -> Duyệt Driver -> Incident -> Trip/PolicyRule.\n"
            "      - Đội xe, Hub điều hành và địa bàn: Gọi `query_driver_graph(driver_identifier=..., focus='fleet')` -> Duyệt Driver -> Fleet -> Region.\n"
            "      - Phương tiện, dòng xe, biển số, lịch sử bảo dưỡng: Gọi `query_driver_graph(driver_identifier=..., focus='vehicle')` -> Duyệt Driver -> Vehicle -> VehicleType, MaintenanceEvent.\n"
            "      - Chỉ số KPI đo lường chuẩn hóa: Gọi `query_driver_graph(driver_identifier=..., focus='kpi_metrics')` -> Duyệt Driver -> Measurement.\n"
            "      - Quyết định chế tài, biên bản xử lý kỷ luật vi phạm: Gọi `query_driver_graph(driver_identifier=..., focus='enforcement')` -> Duyệt Driver -> EnforcementDecision -> ViolationFinding -> PolicyRule.\n"
            "QUY TẮC LỰA CHỌN CÔNG CỤ ĐÚNG TRỌNG TÂM & CHỐNG GỌI TOOL THỪA:\n"
            "  + QUY TRÌNH BẮT BUỘC KHI TÍNH TOÁN CÁC CHỈ SỐ VẬN HÀNH (Tỷ lệ hủy chuyến, Tỷ lệ nhận cuốc, Tỷ lệ hoàn thành, Doanh thu):\n"
            "    * BƯỚC 1: BẮT BUỘC gọi `get_driver_trip_summary` (hoặc `get_driver_trip_metrics` / `get_driver_operational_stats`) với driver_identifier và snapshot_id để lấy số liệu thực tế từ CSDL. TUYỆT ĐỐI CẤM tự bịa ra các con số (như 5, 15, 20)!\n"
            "    * BƯỚC 2: Dùng số liệu thực tế nhận được từ Observation ở Bước 1 để gọi công cụ tính toán `calculate_cancel_rate` hoặc đối chiếu quy chế.\n"
            "    * BƯỚC 3 (ĐỐI VỚI HỦY CHUYẾN): Nếu phát hiện tài xế có chuyến bị hủy (cancelled_trips > 0), KHUYẾN NGHỊ gọi `get_cancelled_trips_detail` (mặc định lấy tối đa 10 chuyến gần nhất) để làm rõ nguyên nhân hủy (do khách hàng, lý do bất khả kháng hợp lệ theo P094 hay tài xế tự ý hủy) nhằm kết luận vi phạm chính xác và khách quan nhất.\n"
            "  + CHỈ GỌI CÁC TOOL TÍNH TOÁN/ĐỐI SOÁT (`evaluate_rating_condition`, `evaluate_daily_revenue`, `calculate_cancel_rate`, `calculate_acceptance_rate`, `calculate_completion_rate`, `calculate_revenue_charge`...) KHI VÀ CHỈ KHI câu hỏi của người dùng có yêu cầu tính toán, kiểm tra doanh số, điểm sao, tỷ lệ hủy/nhận/hoàn thành, hoặc thẩm định tiêu chuẩn thưởng/phạt/chấm công.\n"
            "  + TUYỆT ĐỐI KHÔNG tự ý gọi `evaluate_rating_condition` hay `evaluate_daily_revenue` khi người dùng chỉ hỏi về chi tiết sự việc, khiếu nại, phản ánh khách hàng, thái độ phục vụ, lý do từ chối, thông tin chuyến xe hoặc hồ sơ tài xế!\n"
            "  + NGUYÊN TẮC DỪNG SỚM (EARLY STOP): Ngay khi một công cụ (như `query_driver_graph` hoặc `get_driver_profile` hoặc `get_recent_complaints`) đã trả về đầy đủ nội dung/chi tiết để trả lời cho câu hỏi, BẮT BUỘC DỪNG GỌI THÊM CÔNG CỤ và xuất ngay Thought + Final Answer. Tuyệt đối không gọi thêm các công cụ không liên quan để kéo dài vòng lặp!\n"
            "  + NGUYÊN TẮC XỬ LÝ KHÁC BIỆT DỮ LIỆU GIỮA CÁC NGUỒN (ĐỒ THỊ VS HỒ SƠ):\n"
            "    * Nếu công cụ `query_driver_graph` và `get_driver_profile` ghi nhận thông tin khác nhau (ví dụ: Đồ thị ghi nhận xe máy điện Phương tiện 07, còn Hồ sơ nhân sự ghi nhận VinFast VF 8):\n"
            "      - TUYỆT ĐỐI KHÔNG lặp lại việc gọi các công cụ chuyến xe (`get_driver_trip_summary`) để hy vọng tìm thêm thông tin xe.\n"
            "      - BẮT BUỘC xuất Thought và Final Answer nêu rõ cả hai nguồn ghi nhận để nhân viên quản lý vận hành nắm được sự bất nhất dữ liệu và đối soát: (1) Theo đồ thị tri thức vận hành (Knowledge Graph), và (2) Theo hồ sơ nhân sự / CSDL quản lý tài xế.\n\n"
            "QUY TẮC BẮT BUỘC KHI SUY LUẬN (CHỐNG PHỎNG ĐOÁN & CHỐNG NHẢY CÓC):\n"
            "1. NGUYÊN TẮC QUAN SÁT THỰC TẾ: Mọi kết luận phải dựa trên số liệu và văn bản thực tế trong hệ thống hoặc thông tin đã có trong lịch sử trò chuyện. Với câu hỏi mới chưa có dữ liệu, phải gọi công cụ tra cứu trước khi kết luận.\n"
            "2. CÂU HỎI NỐI TIẾP (FOLLOW-UP): Nếu câu hỏi là câu hỏi nối tiếp (ví dụ: 'lý do là gì?', 'tại sao?', 'chuyến đó thế nào?') và thông tin đã có sẵn trong lịch sử trò chuyện hoặc trong kết quả truy vấn ở lượt trước, bạn ĐƯỢC PHÉP và NÊN trả lời trực tiếp ngay (Thought + Final Answer) mà KHÔNG cần gọi lại công cụ cũ.\n"
            "3. NGUYÊN TẮC PHÂN TÁCH TRÁCH NHIỆM (DECOUPLING): Các công cụ (tools) chỉ đảm nhiệm việc tìm kiếm (search), trích xuất số liệu (get_driver_operational_stats...) và tính toán số học chuẩn xác (calculate_acceptance_rate, calculate_completion_rate...). VIỆC ĐỐI CHIẾU, SO SÁNH VÀ KẾT LUẬN TIÊU CHUẨN HOÀN TOÀN DO AGENT THỰC HIỆN dựa trên việc nhìn vào điều khoản quy chế tìm được và số liệu trả về từ các công cụ.\n"
            "4. NGUYÊN TẮC ĐỐI CHIẾU PHÁP LÝ & CĂN CỨ QUY CHẾ:\n"
            "   - Khi câu hỏi có nội dung kiểm tra vi phạm / chính sách / tiêu chuẩn (hoặc bạn đã gọi công cụ `search_gsm_policies` / `get_full_policy_document`):\n"
            "     Trong Final Answer, BẮT BUỘC PHẢI CÓ PHẦN ĐỐI CHIẾU CĂN CỨ QUY CHẾ:\n"
            "     + Nêu rõ các văn bản quy chế GSM đã tra cứu từ Observation (Mã Pxxx, tên văn bản như P001, P221, P154...).\n"
            "     + Trích dẫn điều khoản / tiêu chuẩn cụ thể và đối chiếu với số liệu của tài xế để kết luận có vi phạm hay không.\n"
            "     + Nếu quy chế tìm được có phạm vi hoặc mốc thời gian khác (ví dụ: P001 áp dụng từ 09/09/2026 trong khi đang xét tháng 08/2026, hoặc P221 áp dụng cho xe máy Green SM Bike trong khi tài xế lái taxi ô tô): BẮT BUỘC giải thích rõ ràng sự khác biệt này để người quản lý nắm được.\n"
            "     + Nếu trong Observation chưa có văn bản quy chế quy định cụ thể mức trần cho trường hợp này: Nêu rõ 'Hệ thống hiện chưa tìm thấy văn bản quy chế quy định cụ thể về mức trần [chủ đề] cho đối tượng tài xế này trong kỳ'.\n"
            "     + TUYỆT ĐỐI CẤM đã tra cứu quy chế mà Final Answer lại chỉ nêu số liệu chuyến xe và đưa ra lời khuyên chung chung mà không hề nhắc đến các văn bản quy chế đã tìm được!\n"
            "   - TUYỆT ĐỐI CẤM TỰ BỊA RA MÃ QUY CHẾ: CHỈ ĐƯỢC trích dẫn mã quy chế và điều khoản nếu mã đó XUẤT HIỆN TRONG OBSERVATION thực tế từ công cụ `search_gsm_policies` hoặc `get_full_policy_document`.\n"
            "   - NẾU TÀI XẾ HOÀN TOÀN KHÔNG CÓ CHUYẾN HỦY / KHÔNG CÓ SỰ CỐ / HỒ SƠ SẠCH: Được phép khẳng định trực diện tài xế tuân thủ tốt, không phát sinh vi phạm quy chế hủy chuyến hay sự cố trong kỳ đối soát.\n"
            "   - TUYỆT ĐỐI KHÔNG tự ý kết luận 'đạt tiêu chuẩn thưởng' hoặc 'đạt KPI' nếu chưa có quy chế quy định tiêu chuẩn thưởng cho đối tượng này trong hệ thống.\n"
            "   - NẾU TÀI XẾ CÓ PHÁT SINH CHUYẾN BỊ HỦY (ví dụ: do yêu cầu của tài xế driver_request):\n"
            "     + Phải ghi nhận trung thực số chuyến bị hủy và nêu rõ nguyên nhân hủy của các chuyến gần nhất từ dữ liệu Observation.\n"
            "     + Đối chiếu với quy chế hủy chuyến hợp lệ (như Bản tin P094): Nếu lý do hủy thuộc các trường hợp bất khả kháng/hợp lệ (khách quá tải, đường ngập...) thì nêu rõ tính hợp lệ; nếu là tài xế tự ý từ chối hoặc không có lý do hợp lệ thì mới kết luận có vi phạm.\n"
            "     + Nếu không có quy chế phạt hủy chuyến: Nêu rõ chưa đủ căn cứ quy chế để kết luận vi phạm, khuyến nghị bộ phận quản lý theo dõi và trao đổi thêm với tài xế.\n"
            "5. NGUYÊN TẮC BẢO TOÀN SỐ LƯỢNG KHIẾU NẠI & SỰ CỐ:\n"
            "   - Khi câu hỏi yêu cầu thống kê hoặc kiểm tra tổng quan tình hình sự cố/khiếu nại, hãy nêu chính xác tổng số lượng thực tế theo Observation (không kết luận sai lệch chỉ vì mới xem ví dụ 3 vụ).\n"
            "   - Khi câu hỏi chỉ hỏi về một vụ việc hoặc lý do cụ thể (như 'lý do từ chối hạ nhiệt độ điều hòa là gì'), hãy tập trung trả lời TRỰC TIẾP và CHI TIẾT vào vụ việc đó, không cần ép buộc phải thống kê lại toàn bộ các chỉ số khác.\n\n"
            "NGUYÊN TẮC XUẤT FINAL ANSWER TỰ NHIÊN, CHUYÊN NGHIỆP & ĐẦY ĐỦ:\n"
            "Khi đã có đủ các dữ liệu thực tế từ công cụ (hoặc từ ngữ cảnh hội thoại), xuất ra:\n"
            "Thought: <Tổng kết ngắn gọn suy luận và thông tin đã thu thập>\n"
            "Final Answer:\n"
            "- Trả lời một cách tự nhiên, mạch lạc, trực diện và linh hoạt theo đúng câu hỏi của người dùng:\n"
            "  * Diễn đạt tự nhiên bằng văn xuôi liền mạch hoặc các gạch đầu dòng ngắn gọn, sạch sẽ. TUYỆT ĐỐI CẤM sao chép các tiêu đề câu hỏi hay biến câu trả lời thành biểu mẫu điền khuyết rập khuôn (như 'Số liệu chuyến hoàn thành: Không có...', 'Căn cứ quy chế: Không có...').\n"
            "  * TUYỆT ĐỐI CẤM rò rỉ các thuật ngữ kỹ thuật nội bộ như Observation, Action, get_cancelled_trips_detail, search_gsm_policies, tool, công cụ trong Final Answer. Hãy dùng ngôn ngữ nghiệp vụ: 'Theo dữ liệu hệ thống ghi nhận', 'Qua tra cứu lịch sử chuyến xe', 'Theo quy chế hiện hành của GSM'...\n"
            "  * Với câu hỏi ngắn, hỏi một chi tiết cụ thể: Trả lời TRỰC TIẾP, RÕ RÀNG, TỰ NHIÊN ngay từ câu đầu tiên. Cung cấp đúng thông tin người dùng cần mà KHÔNG cần ép vào mẫu báo cáo dài dòng, rập khuôn.\n"
            "  * Với câu hỏi đối soát tổng thể, thẩm định vi phạm, xét tiêu chuẩn thưởng/phạt hoặc đánh giá vận hành toàn diện: Đảm bảo ĐẦY ĐỦ các khía cạnh (Số liệu/tính toán thực tế, Đối chiếu quy chế/tiêu chuẩn, Kết luận rõ ràng & Lưu ý nghiệp vụ thiết thực nếu có) theo văn phong tự nhiên của chuyên viên quản lý vận hành.\n"
            "  * Với câu hỏi tra cứu quy chế: Tóm tắt rõ ràng nội dung điều khoản, phạm vi/đối tượng áp dụng, mức thưởng/phạt hoặc chế tài, kèm trích dẫn văn bản quy định liên quan.\n"
            "- Tuyệt đối tránh văn phong máy móc, dập khuôn. Trả lời chuyên nghiệp như một chuyên viên quản lý vận hành GSM giàu kinh nghiệm.\n"
            "- Mọi số liệu phải chính xác tuyệt đối theo Observation. Không tự bịa mã quy chế hay số liệu chuyến xe.\n"
            "- CẤM BỊA TÀI XẾ: Nếu câu hỏi chỉ tra cứu chính sách/quy chế chung mà KHÔNG có tài xế, TUYỆT ĐỐI CẤM tự bịa ra lịch sử chuyến xe hay số liệu tài xế!\n"
            "- TUYỆT ĐỐI CẤM LẶP LẠI CÂU VĂN: Không bao giờ lặp lại cùng một câu văn hay đoạn văn nhiều lần trong câu trả lời.\n"
        )


        # Domain guard check passed from pipeline
        if context.get("intent") == "GREETING":
            greeting_msg = (
                "Chào bạn! Tôi là **Trợ lý AI Quản trị Vận hành & Chính sách của GSM (Taxi Xanh SM)**.\n\n"
                "Tôi sẵn sàng hỗ trợ bạn tra cứu thông tin tài xế, dữ liệu chuyến xe, kiểm tra chỉ số KPI vận hành "
                "và đối soát các quy chế, chính sách của GSM. Hôm nay bạn cần tôi hỗ trợ thông tin gì?"
            )
            yield {
                "type": "final_result",
                "result": ReActResult(final_answer=greeting_msg, thought="Chào hỏi / xã giao", steps=[], citations=[]),
            }
            return
        elif context.get("intent") == "OUT_OF_SCOPE":
            guard_msg = (
                "Xin lỗi bạn, tôi là **Trợ lý AI chuyên biệt cho Quản trị Vận hành & Chính sách của GSM (Taxi Xanh SM)**.\n\n"
                "Hiện tại tôi chỉ hỗ trợ các nội dung thuộc phạm vi nghiệp vụ của GSM (tài xế, chuyến xe, vận hành, quy chế, chính sách). "
                "Rất tiếc tôi không thể giải đáp các câu hỏi ngoài phạm vi này. Nếu bạn có thắc mắc liên quan đến hoạt động vận hành hoặc chính sách của Taxi Xanh SM, vui lòng đặt câu hỏi cho tôi nhé!"
            )
            yield {
                "type": "final_result",
                "result": ReActResult(final_answer=guard_msg, thought="Câu hỏi ngoài phạm vi nghiệp vụ GSM", steps=[], citations=[]),
            }
            return

        scratchpad = ""
        self.call_history: dict[str, dict[str, Any]] = {}
        steps: list[ReActStep] = []
        citations: list[dict[str, Any]] = []
        final_answer = ""
        model_used = ""
        policy_guard_nudged = 0
        cancel_rate_guard_nudged = 0
        graph_guard_nudged = 0
        invalid_action_attempts = 0

        # Contextual prefix from Query Plan & working memory
        ctx_notes = []
        if context.get("driver_id") or context.get("driver_mention"):
            ctx_notes.append(f"Tài xế xác định: {context.get('driver_mention') or context.get('driver_id')}")
        if context.get("snapshot_id"):
            snap_lbl = f" ({context.get('snapshot_label')})" if context.get("snapshot_label") else ""
            ctx_notes.append(f"Snapshot xác định: {context.get('snapshot_id')}{snap_lbl}")
        u_spec_time = context.get("user_specified_time", False)
        if u_spec_time and (context.get("time_display") or context.get("time_scope") or context.get("time_resolved")):
            t_disp = context.get("time_display") or context.get("time_scope") or context.get("time_resolved")
            ctx_notes.append(f"Mốc thời gian đối soát: {t_disp}")
        else:
            ctx_notes.append("Mốc thời gian: Toàn kỳ theo Snapshot (Người dùng KHÔNG yêu cầu ngày cụ thể. TUYỆT ĐỐI KHÔNG truyền tham số 'date' vào các tool để tra cứu toàn bộ dữ liệu trong Snapshot)")
        if context.get("policy_scope"):
            p_val = context["policy_scope"]
            ctx_notes.append(f"Văn bản quy chế: {', '.join(p_val) if isinstance(p_val, list) else p_val}")
        if context.get("policy_topics"):
            t_val = context["policy_topics"]
            ctx_notes.append(f"Chủ đề trọng tâm: {', '.join(t_val) if isinstance(t_val, list) else t_val}")
        ctx_str = f"\n[Kế Hoạch Truy Vấn & Ngữ Cảnh Ban Đầu]:\n- " + "\n- ".join(ctx_notes) + "\n" if ctx_notes else ""

        yield {
            "type": "loop_start",
            "max_iterations": self.max_iterations,
            "query": query,
            "message": f"Bắt đầu chu trình ReAct Agent (tối đa {self.max_iterations} vòng lặp suy luận & gọi công cụ)...",
        }

        for iteration in range(1, self.max_iterations + 1):
            yield {
                "type": "iteration_start",
                "iteration": iteration,
                "max_iterations": self.max_iterations,
            }

            executed_actions = [s for s in steps if s.action]
            has_policy_query = any(k in query.lower() for k in ["vi phạm", "quy chế", "chính sách", "phạt", "chế tài", "đối soát", "kỷ luật", "tiêu chuẩn"])
            has_called_policy = any(s.action in ("search_gsm_policies", "get_full_policy_document") for s in steps)
            has_called_full_doc = any(s.action == "get_full_policy_document" for s in steps)
            has_called_search = any(s.action == "search_gsm_policies" for s in steps)

            all_matched_codes: list[str] = []
            for s in steps:
                if isinstance(s.observation, dict):
                    for c in s.observation.get("matched_policy_codes") or []:
                        c_up = str(c).upper()
                        if c_up not in all_matched_codes:
                            all_matched_codes.append(c_up)

            is_policy_lookup = (
                context.get("intent") == "POLICY_LOOKUP"
                or (
                    not context.get("driver_id")
                    and not context.get("driver_mention")
                    and not bool(re.search(r"\b(DRV-\d+|v2_drv_\d+|tài xế|bác tài|anh \w+|chị \w+)\b", query, re.IGNORECASE))
                )
            )

            last_was_dup = bool(steps and isinstance(steps[-1].observation, dict) and steps[-1].observation.get("_repeat_status") == "DUPLICATE_CALL_DETECTED")

            if not executed_actions:
                if is_policy_lookup:
                    escaped_q = query.replace('"', '\\"')
                    action_instruction = (
                        "Bước 1: Câu hỏi này là tra cứu chính sách/quy chế chung (không có tài xế). Hãy đưa ra Thought và Action: search_gsm_policies để tìm kiếm các đoạn quy chế liên quan và xác định mã văn bản Pxxx.\n"
                        f'Ví dụ:\nAction: search_gsm_policies\nAction Input: {{"query": "{escaped_q}"}}\n'
                        "BẮT BUỘC PHẢI GỌI CÔNG CỤ, TUYỆT ĐỐI KHÔNG xuất ra Final Answer khi chưa có Observation thực tế:"
                    )
                else:
                    time_hint = ""
                    t_val = context.get("time_display") or context.get("time_scope")
                    s_id = context.get("snapshot_id")
                    if t_val:
                        time_hint = f" (Mốc thời gian cần kiểm tra là '{t_val}'{f', snapshot {s_id}' if s_id else ''}). "
                    has_prior_history = bool(context.get("chat_history") and len(context["chat_history"]) >= 2)
                    if has_prior_history:
                        action_instruction = (
                            f"Bước 1: Đây có thể là câu hỏi nối tiếp từ lượt hội thoại trước{time_hint}. "
                            "Nếu thông tin trả lời (như lý do, chi tiết sự việc, thời gian, tên xe, biển số) đã có sẵn trong lịch sử hội thoại gần nhất, "
                            "BẮT BUỘC đưa ra ngay (Thought + Final Answer) để trả lời trực tiếp, rõ ràng cho người dùng mà KHÔNG cần gọi lại công cụ cũ. "
                            "Nếu cần tra cứu thêm dữ liệu mới chưa có, hãy đưa ra Thought và Action gọi công cụ đúng trọng tâm câu hỏi (ví dụ: get_driver_profile, get_driver_trip_summary, get_recent_complaints, get_recent_incidents, query_driver_graph...):"
                        )
                    else:
                        action_instruction = (
                            f"Bước 1: Hãy đưa ra Thought và Action để gọi công cụ tra cứu dữ liệu thực tế đầu tiên{time_hint}"
                            "BẮT BUỘC PHẢI GỌI CÔNG CỤ đúng trọng tâm câu hỏi (ví dụ: get_driver_profile khi hỏi thông tin tài xế/xe; get_driver_trip_summary / get_driver_operational_stats khi hỏi số liệu chuyến đi; get_recent_complaints / get_recent_incidents khi hỏi khiếu nại/sự cố; query_driver_graph khi tra cứu mối quan hệ đồ thị tri thức hoặc liên kết đa thực thể...), "
                            "TUYỆT ĐỐI KHÔNG xuất ra Final Answer khi chưa có Observation thực tế:"
                        )
            elif last_was_dup:
                action_instruction = (
                    "LƯU Ý ĐẶC BIỆT: Bạn vừa nhận được CẢNH BÁO TRÙNG LẶP ở bước trước vì gọi lại công cụ với cùng tham số. "
                    "Dữ liệu đã có đủ trong Observation. BẮT BUỘC KHÔNG GỌI LẠI công cụ cũ đó nữa. "
                    "Hãy sử dụng các thông tin đã thu thập để đưa ra (Thought + Final Answer) ngay bây giờ:"
                )
            elif is_policy_lookup and has_called_full_doc:
                action_instruction = (
                    "Bước tiếp theo: Bạn đã nạp thành công toàn văn văn bản quy chế từ `get_full_policy_document`. "
                    "Vì đây là câu hỏi tra cứu chính sách/quy chế chung (KHÔNG CÓ TÀI XẾ CỤ THỂ), dữ liệu trong Observation đã hoàn toàn đầy đủ. "
                    "TUYỆT ĐỐI CẤM gọi thêm bất kỳ công cụ tài xế nào (CẤM get_driver_operational_stats, get_driver_profile, query_driver_graph...). "
                    "TUYỆT ĐỐI CẤM tự bịa mã tài xế hay ngày tháng! "
                    "BẮT BUỘC bạn phải đưa ra (Thought + Final Answer) theo đúng chuẩn Báo cáo Tra cứu Quy chế GSM Mẫu Dạng 2 ngay bây giờ:"
                )
            elif is_policy_lookup and has_called_search and all_matched_codes and not has_called_full_doc:
                codes_joined = ", ".join(all_matched_codes)
                action_instruction = (
                    f"Bước 2: Từ kết quả tìm kiếm ngữ nghĩa, đã xác định các văn bản quy chế liên quan: [{codes_joined}]. "
                    f"BẮT BUỘC bạn phải gọi Action: get_full_policy_document với Action Input: {{\"policy_code\": \"{codes_joined}\"}} "
                    "để đọc toàn văn toàn bộ các văn bản này trước khi đưa ra Final Answer. "
                    "TUYỆT ĐỐI CẤM gọi các công cụ tài xế:"
                )
            elif has_policy_query and not has_called_policy:
                has_rate_obs = any(s.action in ("calculate_cancel_rate", "calculate_acceptance_rate", "calculate_completion_rate", "calculate_violation_penalty_points") for s in steps)
                has_prior_policy = bool(context.get("policy_scope") or any("P" in str(msg) for msg in context.get("chat_history", [])))
                if has_rate_obs or has_prior_policy:
                    action_instruction = (
                        "Dựa trên các Observation tính toán tỷ lệ / so khớp ngưỡng quy chế thực tế đã có ở trên (hoặc từ lịch sử trò chuyện), "
                        "bạn đã có đầy đủ căn cứ xác định vi phạm. "
                        "BẮT BUỘC đưa ra ngay (Thought + Final Answer) để trả lời kết luận rõ ràng, trực diện cho người dùng mà KHÔNG cần gọi lại công cụ cũ:"
                    )
                else:
                    action_instruction = (
                        "Bước tiếp theo: Câu hỏi này liên quan đến chính sách/quy chế/vi phạm. "
                        "BẮT BUỘC bạn phải gọi Action: search_gsm_policies (tìm theo từ khóa) hoặc get_full_policy_document (nếu đã biết mã Pxxx) để tra cứu văn bản quy chế làm căn cứ pháp lý.\n"
                        "Ví dụ:\nAction: search_gsm_policies\nAction Input: {\"query\": \"chính sách vi phạm hủy chuyến\"}\n"
                        "CHƯA ĐƯỢC xuất Final Answer khi chưa có Observation từ văn bản quy chế:"
                    )
            else:
                action_instruction = (
                    f"Dựa trên các Observation thực tế đã có ở trên (hoặc lịch sử trò chuyện), nếu đã có thông tin trả lời cho câu hỏi '{query}' "
                    "(kể cả khi các nguồn dữ liệu có sự khác biệt cần đối chiếu như Đồ thị vs Hồ sơ), hãy xuất ngay (Thought + Final Answer) "
                    "để trả lời TRỰC DIỆN, rõ ràng và trung thực cho người dùng. "
                    "Chỉ đưa ra Action gọi công cụ tiếp theo nếu thực sự còn thiếu dữ liệu cần thiết để trả lời câu hỏi."
                )


            user_prompt = (
                f"CÂU HỎI: {query}\n"
                f"{ctx_str}\n"
                f"{scratchpad}\n"
                f"{action_instruction}"
            )

            messages = [{"role": "system", "content": system_prompt}]
            raw_history = context.get("chat_history") or []
            for item in raw_history[-6:]:
                h_role = item.get("role", "user")
                h_content = str(item.get("content", "")).strip()
                if not h_content:
                    continue
                if h_role == "assistant" and len(h_content) > 1000:
                    h_content = h_content[:1000] + "\n...[Tóm lược phần còn lại của phản hồi trước]..."
                messages.append({"role": h_role, "content": h_content})
            messages.append({"role": "user", "content": user_prompt})

            raw_resp, used_m, _ = self.call_llm_fn(
                messages=messages,
                max_tokens=900,
                temperature=0.1,
                timeout=35.0,
                stop=["\nObservation:", "Observation:", "\nobservation:"],
            )
            model_used = used_m or model_used
            raw_text = raw_resp.strip()

            # Clean reasoning / thinking chatter from models like Nemotron / DeepSeek
            raw_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
            raw_text = re.sub(r"^(?:Here's a thinking process:.*?(?=\n*(?:Thought:|Action:|Final Answer:|$)))", "", raw_text, flags=re.DOTALL | re.IGNORECASE).strip()

            # Defensive truncation: LLM must NEVER output Observation or subsequent hallucinations
            if re.search(r"\bObservation:\s*", raw_text, re.IGNORECASE):
                raw_text = re.split(r"\bObservation:\s*", raw_text, maxsplit=1, flags=re.IGNORECASE)[0].strip()

            # Determine whether this step is an Action call or Final Answer
            is_pseudo_action_final = bool(re.search(r"\bAction(?:\s*\d+)?:\s*(?:Final(?:\s*Answer)?|Finish|Done|None)\b", raw_text, re.IGNORECASE))
            has_action = bool(re.search(r"\bAction:\s*", raw_text, re.IGNORECASE)) and not is_pseudo_action_final
            has_final = bool(re.search(r"\bFinal Answer:\s*", raw_text, re.IGNORECASE)) or is_pseudo_action_final
            action_pos = raw_text.lower().find("action:") if has_action else -1
            final_pos = raw_text.lower().find("final answer:") if has_final else -1

            is_action_step = has_action and (final_pos == -1 or action_pos < final_pos)

            # 1. Handle Final Answer if it precedes any Action or if no Action is present
            if not is_action_step and has_final:
                final_match = re.search(r"(?:Final Answer:|Action:\s*Final(?:\s*Answer)?[:\s]*)\s*(.*)", raw_text, re.DOTALL | re.IGNORECASE)
                if final_match:
                    executed_actions = [s for s in steps if s.action]
                    # Guard 1: Cannot finalize without calling any tool if iteration < max_iterations UNLESS prior history exists
                    has_prior_history = bool(context.get("chat_history") and len(context["chat_history"]) >= 2)
                    if not executed_actions and iteration < self.max_iterations and not has_prior_history:
                        scratchpad += (
                            f"\nThought: {raw_text}\n"
                            "Observation: Bạn chưa thực hiện bất kỳ công cụ (Action) nào để lấy dữ liệu thực tế từ hệ thống. "
                            "BẮT BUỘC phải gọi công cụ (Action: get_driver_profile, search_gsm_policies...) trước khi kết luận."
                        )
                        continue

                    # Guard 2: If query involves policy, violation, penalty, or standards, must search GSM policies
                    has_rate_obs = any(s.action in ("calculate_cancel_rate", "calculate_acceptance_rate", "calculate_completion_rate", "calculate_violation_penalty_points") for s in steps)
                    has_prior_policy = bool(context.get("policy_scope") or any("P" in str(msg) for msg in context.get("chat_history", [])))
                    if has_policy_query and not has_called_policy and not has_rate_obs and not has_prior_policy and iteration < self.max_iterations and policy_guard_nudged < 1:
                        policy_guard_nudged += 1
                        yield {
                            "type": "thought",
                            "iteration": iteration,
                            "thought": "Câu hỏi liên quan đến chính sách/vi phạm nên cần tra cứu văn bản quy chế GSM trước khi đưa ra kết luận.",
                        }
                        scratchpad += (
                            f"\nThought: {raw_text}\n"
                            "Observation: Câu hỏi liên quan đến vi phạm / quy chế / chế tài đối soát nhưng bạn chưa gọi công cụ 'search_gsm_policies' hoặc 'get_full_policy_document' để tra cứu văn bản quy chế GSM làm căn cứ pháp lý. "
                            "BẮT BUỘC phải thực hiện Action: search_gsm_policies (hoặc get_full_policy_document với mã Pxxx) trước khi đưa ra Final Answer."
                        )
                        continue

                    # Guard 3: If query involves cancel rate, check if trip metrics are fetched, then calculate
                    has_cancel_rate_query = any(k in query.lower() for k in ["tỷ lệ hủy", "tỉ lệ hủy", "cancel_rate", "hủy chuyến là bao nhiêu"])
                    has_called_cancel_rate = any(s.action == "calculate_cancel_rate" for s in steps)
                    has_called_trip_summary = any(s.action in ("get_driver_trip_summary", "get_driver_trip_metrics", "get_driver_operational_stats") for s in steps)

                    if has_cancel_rate_query and not has_called_trip_summary and not has_called_cancel_rate and iteration < self.max_iterations and cancel_rate_guard_nudged < 1:
                        cancel_rate_guard_nudged += 1
                        yield {
                            "type": "thought",
                            "iteration": iteration,
                            "thought": "Câu hỏi yêu cầu xác định tỷ lệ hủy chuyến nên cần lấy số liệu chuyến đi thực tế của tài xế từ CSDL trước.",
                        }
                        scratchpad += (
                            f"\nThought: {raw_text}\n"
                            "Observation: Câu hỏi yêu cầu xác định tỷ lệ hủy chuyến (cancel_rate_30d). "
                            "BẮT BUỘC bạn phải gọi Action: get_driver_trip_summary (hoặc get_driver_trip_metrics) với tham số {\"driver_identifier\": \"...\"} "
                            "để lấy số liệu thực tế về các chuyến xe (tổng số chuyến, hoàn thành, hủy) từ CSDL trước, TUYỆT ĐỐI CẤM tự bịa ra các con số!"
                        )
                        continue

                    if has_cancel_rate_query and not has_called_cancel_rate and iteration < self.max_iterations and cancel_rate_guard_nudged < 2:
                        cancel_rate_guard_nudged += 1
                        yield {
                            "type": "thought",
                            "iteration": iteration,
                            "thought": "Câu hỏi yêu cầu xác định tỷ lệ hủy chuyến nên cần gọi công cụ calculate_cancel_rate để tính toán số học chuẩn xác.",
                        }
                        scratchpad += (
                            f"\nThought: {raw_text}\n"
                            "Observation: Câu hỏi yêu cầu xác định tỷ lệ hủy chuyến (cancel_rate_30d). "
                            "BẮT BUỘC bạn phải gọi Action: calculate_cancel_rate với tham số {\"cancelled_trips\": <số cuốc hủy>, \"total_trips\": <tổng số cuốc>} "
                            "lấy từ kết quả quan sát thực tế (Observation) trước đó để hệ thống tính toán chuẩn xác trước khi đưa ra Final Answer."
                        )
                        continue

                    # Guard 4: If query involves knowledge graph, nodes, or edges, must execute query_driver_graph
                    has_graph_query = any(k in query.lower() for k in ["đồ thị", "kg", "node", "nút", "cạnh", "mạng lưới", "quan hệ"])
                    has_called_graph = any(s.action == "query_driver_graph" for s in steps)
                    if has_graph_query and not has_called_graph and iteration < self.max_iterations and graph_guard_nudged < 1:
                        graph_guard_nudged += 1
                        yield {
                            "type": "thought",
                            "iteration": iteration,
                            "thought": "Câu hỏi yêu cầu tra cứu từ đồ thị tri thức nên cần gọi công cụ query_driver_graph.",
                        }
                        scratchpad += (
                            f"\nThought: {raw_text}\n"
                            "Observation: Câu hỏi yêu cầu tra cứu từ đồ thị tri thức (Knowledge Graph). "
                            "BẮT BUỘC bạn phải gọi Action: query_driver_graph với Action Input: {\"driver_identifier\": \"...\"} "
                            "để trích xuất các nút và cạnh liên kết trong đồ thị trước khi đưa ra Final Answer."
                        )
                        continue

                    thought_match = re.search(r"Thought:\s*(.*?)(?=\n*(?:Final Answer:|Action:\s*Final)|\Z)", raw_text, re.DOTALL | re.IGNORECASE)
                    thought_text = thought_match.group(1).strip() if thought_match else "Đã tổng hợp đủ bằng chứng từ công cụ."
                    potential_ans = final_match.group(1).strip() if final_match else ""
                    potential_ans = re.sub(r"^(?:Thought:[^\n]*\n+|Final Answer:\s*|Action:\s*Final[^\n]*\n*)+", "", potential_ans, flags=re.IGNORECASE).strip()
                    if potential_ans in ("{}", ""):
                        potential_ans = ""

                    yield {
                        "type": "thought",
                        "iteration": iteration,
                        "thought": thought_text,
                    }

                    if is_policy_lookup:
                        has_3_sections = bool(
                            re.search(r"(?:1\.|Quy định|Tóm tắt|Nội dung|Văn bản)", potential_ans, re.IGNORECASE)
                            and re.search(r"(?:2\.|Căn cứ|Trích dẫn|Điều khoản)", potential_ans, re.IGNORECASE)
                        )
                    elif has_policy_query or has_called_policy:
                        has_policy_mention = bool(
                            re.search(r"(?:quy chế|chính sách|văn bản|điều khoản|căn cứ|P\d+|chưa có quy định|chưa có văn bản)", potential_ans, re.IGNORECASE)
                        )
                        has_driver_mention = bool(
                            re.search(r"(?:hoạt động|chuyến|vận hành|tỷ lệ|cancel_rate|số liệu)", potential_ans, re.IGNORECASE)
                        )
                        has_conclusion = bool(
                            re.search(r"(?:kết luận|đánh giá|vi phạm|chưa đủ căn cứ|xem xét)", potential_ans, re.IGNORECASE)
                        )
                        has_3_sections = has_policy_mention and has_driver_mention and has_conclusion
                    else:
                        # For driver inquiries without policy/compliance check, any substantive answer answering the question is valid
                        has_3_sections = len(potential_ans.strip()) >= 20

                    if has_3_sections or not executed_actions or iteration >= self.max_iterations:
                        final_answer = potential_ans
                        steps.append(ReActStep(
                            step=iteration,
                            thought=thought_text,
                            raw_text=raw_text,
                        ))
                        break
                    else:
                        # Final answer was emitted but is too brief/unstructured; record thought and trigger structured synthesis
                        steps.append(ReActStep(
                            step=iteration,
                            thought=thought_text,
                            raw_text=raw_text,
                        ))
                        break

            # 2. Parse Action Step
            if is_action_step:
                thought_text = self._extract_thought(raw_text)

                yield {
                    "type": "thought",
                    "iteration": iteration,
                    "thought": thought_text,
                }

                actions_to_run = self._parse_actions(raw_text)

                if not actions_to_run:
                    invalid_action_attempts += 1
                    executed_actions = [s for s in steps if s.action]
                    if (len(raw_text) > 60 and "thought" not in raw_text.lower() and executed_actions) or (invalid_action_attempts >= 2 and executed_actions):
                        logger.warning(f"Ending loop due to invalid action attempts ({invalid_action_attempts}) with existing observations in iteration {iteration}.")
                        final_answer = raw_text
                        break
                    else:
                        known_names_str = ", ".join(f"`{t['name']}`" for t in self.tools_schema)
                        scratchpad += (
                            f"\nThought: {raw_text}\n"
                            f"Observation: Tên công cụ bạn vừa đưa ra không tồn tại hoặc không hợp lệ. "
                            f"BẮT BUỘC chỉ được chọn Action từ danh sách công cụ sau:\n{known_names_str}.\n"
                            "Nếu đã có đủ thông tin từ các Observation trước, hãy xuất ngay Thought và Final Answer."
                        )
                        continue
                else:
                    invalid_action_attempts = 0

                loop_broken = False
                for act_idx, (action_name, action_input) in enumerate(actions_to_run, 1):
                    # Check for duplicate tool calls with unchanged parameters
                    resolved_args = self._resolve_context_args(action_input)
                    sig = self._get_tool_signature(action_name, resolved_args)

                    if sig in self.call_history:
                        entry = self.call_history[sig]
                        entry["count"] += 1
                        call_count = entry["count"]
                        prev_iter = entry["iteration"]
                        cached_obs = entry["observation"]

                        if call_count >= 3 or (is_policy_lookup and has_called_full_doc):
                            # Infinite loop detected! Force break loop
                            obs_result = {
                                "_repeat_status": "INFINITE_LOOP_PREVENTED",
                                "warning": (
                                    f"PHÁT HIỆN VÒNG LẶP TRÙNG LẶP: Công cụ '{action_name}' đã bị gọi lặp lại. "
                                    "Hệ thống tự động ngắt chu kỳ gọi công cụ để chuyển sang tổng hợp câu trả lời dựa trên các dữ liệu đã thu thập."
                                ),
                                "cached_data": cached_obs,
                            }
                            cit_result = None
                            loop_broken = True
                        else:
                            obs_result = {
                                "_repeat_status": "DUPLICATE_CALL_DETECTED",
                                "warning": (
                                    f"CẢNH BÁO TRÙNG LẶP: Công cụ '{action_name}' đã được thực thi trước đó ở Vòng lặp {prev_iter} "
                                    f"với cùng bộ tham số này. Dữ liệu hệ thống không thay đổi so với Observation trước đó."
                                ),
                                "instruction": (
                                    "BẮT BUỘC DỪNG GỌI LẠI CÔNG CỤ NÀY: Dữ liệu đã có đủ trong Observation trước đó. "
                                    "Bạn TUYỆT ĐỐI CẤM gọi lại cùng công cụ với cùng tham số. "
                                    "Hãy sử dụng các thông tin và dẫn chứng đã thu thập để xuất ngay Thought và Final Answer trả lời trực tiếp, rõ ràng câu hỏi của người dùng mà không cần gọi thêm công cụ."
                                ),
                                "data": cached_obs,
                            }
                            cit_result = None
                    else:
                        obs_result, cit_result = self.execute_tool(action_name, action_input)
                        if isinstance(obs_result, dict):
                            if obs_result.get("_force_finalize"):
                                loop_broken = True
                            if "error" in obs_result:

                                obs_result["_reflection_hint"] = (
                                    f"Công cụ '{action_name}' báo lỗi. Hãy kiểm tra lại tham số gọi (ví dụ: mã tài xế DRV-xxx, định dạng ngày YYYY-MM-DD), "
                                    "hoặc chuyển sang công cụ tra cứu thay thế (như get_driver_profile hoặc search_gsm_policies)."
                                )
                            elif obs_result.get("results_count") == 0 and action_name == "search_gsm_policies":
                                obs_result["_reflection_hint"] = (
                                    "Chưa tìm thấy điều khoản nào với từ khóa này. Hãy gọi lại 'search_gsm_policies' với từ khóa bao quát hơn "
                                    "(ví dụ: 'quy chế vận hành', 'quy tắc ứng xử', 'chế tài vi phạm', 'tiêu chuẩn chấm công')."
                                )
                            elif obs_result.get("status") == "no_data" or (obs_result.get("trips_count") == 0 and action_name in ("get_driver_operational_stats", "get_driver_daily_stats")):
                                obs_result["_reflection_hint"] = (
                                    "Không tìm thấy chuyến đi trong khoảng thời gian này. Hãy thử gọi 'get_driver_trip_summary' với mốc thời gian tháng hoặc snapshot để xem toàn kỳ."
                                )
                        self.call_history[sig] = {
                            "count": 1,
                            "observation": obs_result,
                            "citation": cit_result,
                            "iteration": iteration,
                        }
                        if cit_result:
                            cits_to_add = cit_result if isinstance(cit_result, list) else [cit_result]
                            for c_item in cits_to_add:
                                if c_item and not any(c.get("citation_locator") == c_item.get("citation_locator") for c in citations):
                                    c_item["index"] = len(citations) + 1
                                    citations.append(c_item)

                    # Emit action_start event
                    yield {
                        "type": "action_start",
                        "iteration": iteration,
                        "action_index": act_idx,
                        "total_actions": len(actions_to_run),
                        "action": action_name,
                        "action_input": action_input,
                        "tool": action_name,
                        "tool_input": action_input,
                    }

                    # Record step
                    step_record = ReActStep(
                        step=iteration,
                        thought=thought_text if act_idx == 1 else f"Tiếp tục thực thi công cụ {action_name}.",
                        action=action_name,
                        action_input=action_input,
                        observation=obs_result,
                        raw_text=raw_text,
                    )
                    steps.append(step_record)

                    # Emit observation event
                    yield {
                        "type": "observation",
                        "iteration": iteration,
                        "action_index": act_idx,
                        "action": action_name,
                        "tool": action_name,
                        "observation": obs_result,
                        "citation": cit_result,
                    }

                    obs_str = json.dumps(obs_result, ensure_ascii=False) if isinstance(obs_result, dict) else str(obs_result)
                    if act_idx == 1:
                        scratchpad += f"\nThought: {thought_text}\n"
                    scratchpad += (
                        f"Action: {action_name}\n"
                        f"Action Input: {json.dumps(action_input, ensure_ascii=False)}\n"
                        f"Observation: {obs_str}\n"
                    )

                    if loop_broken:
                        break

                if loop_broken:
                    break
            else:
                executed_actions = [s for s in steps if s.action]
                if len(raw_text) > 60 and "thought" not in raw_text.lower() and executed_actions:
                    final_answer = raw_text
                    break
                else:
                    scratchpad += f"\nThought: {raw_text}\nObservation: Vui lòng đưa ra Action và Action Input hợp lệ để gọi công cụ từ danh sách."
                    continue

        # 3. If loop finished without Final Answer or if Final Answer lacked 3-section format, synthesize
        # 3. If loop finished without Final Answer or if Final Answer lacked structured format, synthesize
        executed_actions = [s for s in steps if s.action]
        has_driver_aspect = bool(
            context.get("driver_id")
            or context.get("driver_mention")
            or bool(re.search(r"\b(DRV-\d+|v2_drv_\d+|tài xế|bác tài|anh \w+|chị \w+)\b", query, re.IGNORECASE))
        )
        has_policy_aspect = bool(
            context.get("intent") in ("POLICY_LOOKUP", "HYBRID_REASONING")
            or context.get("policy_topics")
            or context.get("policy_scope")
            or any(k in query.lower() for k in [
                "vi phạm", "quy chế", "chính sách", "phạt", "chế tài",
                "thưởng", "đãi ngộ", "tiêu chuẩn", "đối soát", "kỷ luật", "quy định",
                "hủy chuyến", "nghỉ việc", "đồng phục", "ứng xử"
            ])
            or any(s.action in ("search_gsm_policies", "get_full_policy_document") for s in steps)
        )

        is_pure_policy = has_policy_aspect and not has_driver_aspect
        is_pure_driver_history = has_driver_aspect and not has_policy_aspect
        is_hybrid = has_driver_aspect and has_policy_aspect

        # Check if agent already produced a substantive, valid answer in its loop
        has_substantive_answer = bool(
            final_answer
            and len(final_answer.strip()) >= 30
            and len(re.findall(r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", final_answer, re.IGNORECASE)) >= 10
        )
        if has_policy_aspect and final_answer:
            # If query has policy aspect, answer MUST reference policy or lack thereof
            if not re.search(r"(?:quy chế|chính sách|văn bản|điều khoản|căn cứ|P\d+|chưa có quy định|chưa có văn bản)", final_answer, re.IGNORECASE):
                has_substantive_answer = False

        needs_structured_synthesis = not has_substantive_answer

        if needs_structured_synthesis and executed_actions:
            yield {
                "type": "synthesis_start",
                "message": "Đang tổng hợp kết quả đối soát dữ liệu GSM...",
            }

            if is_pure_policy:
                synthesis_prompt = (
                    f"CÂU HỎI BAN ĐẦU CỦA NHÂN VIÊN VẬN HÀNH: {query}\n\n"
                    f"CÁC BƯỚC SUY LUẬN VÀ QUAN SÁT THỰC TẾ (DỮ LIỆU THU THẬP ĐƯỢC):\n{scratchpad}\n\n"
                    "YÊU CẦU TỔNG HỢP CÂU TRẢ LỜI:\n"
                    "- Dựa trên các văn bản quy chế và dữ liệu thực tế ở trên, hãy trả lời câu hỏi của người dùng một cách tự nhiên, rõ ràng, chính xác và chuyên nghiệp.\n"
                    "- Nêu rõ văn bản quy định (Mã Pxxx, tiêu đề, ngày hiệu lực), đối tượng/phạm vi áp dụng (ô tô hay xe máy), nội dung chính sách cốt lõi và trích dẫn điều khoản liên quan.\n"
                    "- Diễn đạt tự nhiên bằng văn xuôi mạch lạc, không rập khuôn mẫu bảng biểu rỗng.\n"
                    "- TUYỆT ĐỐI CẤM rò rỉ các thuật ngữ kỹ thuật nội bộ như Observation, Action, tool, công cụ trong câu trả lời. Hãy dùng ngôn ngữ nghiệp vụ: 'Theo quy chế của GSM', 'Căn cứ theo văn bản'...\n"
                    "- CẤM ẢO GIÁC MÃ QUY CHẾ: Chỉ được trích dẫn mã văn bản quy chế nếu mã đó xuất hiện trong dữ liệu thực tế từ hệ thống. TUYỆT ĐỐI KHÔNG tự bịa ra bất kỳ mã quy chế Pxxx nào không có trong dữ liệu.\n"
                    "- TUYỆT ĐỐI CẤM NHẮC ĐẾN LỊCH SỬ CHUYẾN XE, TỶ LỆ HỦY CHUYẾN HAY TÀI XẾ CỤ THỂ KHI NGƯỜI DÙNG CHỈ TRA CỨU QUY CHẾ CHUNG.\n"
                    "- Tuyệt đối tránh văn phong rập khuôn, máy móc. Cấm xuất ra các thẻ Thought: hay Final Answer:."
                )
            elif is_pure_driver_history:
                driver_info = context.get("driver_mention") or context.get("driver_id") or "tài xế"
                time_info = context.get("time_display") or context.get("time_scope") or "kỳ ghi nhận gần nhất"
                verified_notes = []
                if context.get("driver_trips_summary"):
                    verified_notes.append(f"Số liệu chuyến xe chuẩn xác từ hệ thống: {context.get('driver_trips_summary')}")
                if context.get("driver_cancel_rate") is not None:
                    verified_notes.append(f"Tỷ lệ hủy chuyến chuẩn xác: {context.get('driver_cancel_rate'):.2f}%")
                verified_str = ("\nLƯU Ý ĐẶC BIỆT VỀ SỐ LIỆU:\n- " + "\n- ".join(verified_notes) + "\nBẮT BUỘC sử dụng đúng số liệu này, TUYỆT ĐỐI CẤM tự bịa số liệu chuyến đi hay số lần hủy.\n\n") if verified_notes else ""

                synthesis_prompt = (
                    f"CÂU HỎI BAN ĐẦU CỦA NHÂN VIÊN VẬN HÀNH: {query}\n\n"
                    f"{verified_str}"
                    f"CÁC BƯỚC SUY LUẬN VÀ QUAN SÁT THỰC TẾ (DẪN CHỨNG THU THẬP ĐƯỢC TỪ HỆ THỐNG):\n{scratchpad}\n\n"
                    "YÊU CẦU TỔNG HỢP CÂU TRẢ LỜI (DỰA TRÊN CÂU HỎI VÀ DẪN CHỨNG THỰC TẾ):\n"
                    f"1. ƯU TIÊN SỐ 1 - ĐÚNG TRỌNG TÂM CÂU HỎI: Trả lời TRỰC DIỆN, CHÍNH XÁC và RÕ RÀNG vào nội dung câu hỏi '{query}'.\n"
                    "- TUYỆT ĐỐI KHÔNG TỰ Ý CHUYỂN SANG BÁO CÁO VẬN HÀNH: Nếu người dùng hỏi về phương tiện, loại xe, biển số, đội xe, địa bàn, thông tin cá nhân hay một sự việc cụ thể, BẮT BUỘC chỉ tập trung làm rõ thông tin đó. TUYỆT ĐỐI KHÔNG tự động liệt kê số chuyến xe, tỷ lệ hủy chuyến hay đánh giá đạo đức lái xe khi người dùng không hỏi.\n"
                    "- XỬ LÝ BẤT NHẤT THÔNG TIN GIỮA CÁC NGUỒN: Nếu phát hiện sự khác biệt giữa các nguồn dữ liệu (ví dụ: Đồ thị tri thức Knowledge Graph ghi nhận một phương tiện/loại xe, trong khi Hồ sơ nhân sự / CSDL quản lý ghi nhận dòng xe/biển số khác), BẮT BUỘC nêu rõ trung thực cả hai nguồn thông tin để nhân viên quản lý vận hành nắm được sự bất nhất dữ liệu và đối soát.\n"
                    "- SỐ LIỆU CHUYẾN XE & TỶ LỆ HỦY: CHỈ nêu số liệu chuyến xe (hoàn thành, hủy) và tỷ lệ hủy (cancel_rate_30d...) NẾU câu hỏi của người dùng có yêu cầu kiểm tra chuyến xe, tỷ lệ hủy hoặc đánh giá vận hành.\n"
                    "- VỀ KHIẾU NẠI & SỰ CỐ: Nếu câu hỏi yêu cầu thống kê/tổng hợp sự cố hoặc khiếu nại, hãy nêu đúng tổng số lượng thực tế theo dữ liệu thu thập được; nếu hỏi chi tiết một vụ việc thì giải thích chi tiết vụ việc đó.\n"
                    "- Diễn đạt tự nhiên bằng văn xuôi mạch lạc hoặc các gạch đầu dòng ngắn gọn. TUYỆT ĐỐI CẤM sao chép các tiêu đề câu hỏi làm biểu mẫu rỗng.\n"
                    "- TUYỆT ĐỐI CẤM rò rỉ các thuật ngữ kỹ thuật nội bộ như Observation, Action, get_cancelled_trips_detail, tool, công cụ trong câu trả lời. Hãy dùng ngôn ngữ nghiệp vụ: 'Theo dữ liệu đồ thị tri thức', 'Theo hồ sơ quản lý tài xế'...\n"
                    "- TUYỆT ĐỐI CẤM LẶP LẠI CÂU VĂN: Không bao giờ lặp lại cùng một câu văn nhiều lần.\n"
                    "- Tránh văn phong rập khuôn máy móc. Cấm xuất ra các thẻ Thought: hay Final Answer:."
                )
            else:
                driver_info = context.get("driver_mention") or context.get("driver_id") or "tài xế"
                time_info = context.get("time_display") or context.get("time_scope") or "kỳ đối soát vừa qua"

                verified_notes = []
                if context.get("driver_trips_summary"):
                    verified_notes.append(f"Số liệu chuyến xe chuẩn xác từ hệ thống: {context.get('driver_trips_summary')}")
                if context.get("driver_cancel_rate") is not None:
                    verified_notes.append(f"Tỷ lệ hủy chuyến chuẩn xác: {context.get('driver_cancel_rate'):.2f}%")
                verified_str = ("\nLƯU Ý ĐẶC BIỆT VỀ SỐ LIỆU:\n- " + "\n- ".join(verified_notes) + "\nBẮT BUỘC sử dụng đúng số liệu này, TUYỆT ĐỐI CẤM tự bịa số liệu chuyến đi hay số lần hủy.\n\n") if verified_notes else ""

                # Extract all retrieved policy references from steps
                retrieved_policies_summary = []
                for s in steps:
                    if s.action == "search_gsm_policies" and isinstance(s.observation, dict):
                        for p_item in s.observation.get("policies", []):
                            p_code = p_item.get("policy_alias") or ""
                            p_title = p_item.get("title") or ""
                            p_snip = (p_item.get("snippet") or "")[:250].strip()
                            if p_code or p_title:
                                retrieved_policies_summary.append(f"- Văn bản {p_code}: {p_title}\n  Trích lược: {p_snip}")
                    elif s.action == "get_full_policy_document" and isinstance(s.observation, dict):
                        for doc in s.observation.get("documents", []):
                            p_code = doc.get("policy_code") or ""
                            p_title = doc.get("title") or ""
                            p_eff = doc.get("posted_date") or ""
                            retrieved_policies_summary.append(f"- Toàn văn {p_code}: {p_title} (Ngày ban hành/hiệu lực: {p_eff})")
                        if s.observation.get("policy_code") and not s.observation.get("documents"):
                            p_code = s.observation.get("policy_code")
                            p_title = s.observation.get("title") or ""
                            p_eff = s.observation.get("posted_date") or ""
                            retrieved_policies_summary.append(f"- Toàn văn {p_code}: {p_title} (Ngày ban hành/hiệu lực: {p_eff})")

                policy_summary_str = ""
                if retrieved_policies_summary:
                    policy_summary_str = "DANH SÁCH VĂN BẢN QUY CHẾ ĐÃ TRA CỨU ĐƯỢC TỪ HỆ THỐNG:\n" + "\n".join(retrieved_policies_summary[:5]) + "\n\n"

                is_reward_query = any(k in query.lower() for k in ["thưởng", "khen thưởng", "đãi ngộ", "tiêu chuẩn thưởng", "xét thưởng"]) and not any(k in query.lower() for k in ["vi phạm", "xử phạt", "kỷ luật", "chế tài", "phạt"])

                if is_reward_query:
                    conclusion_instruction = (
                        "- **Về tiêu chuẩn thưởng:** Trả lời trực diện xem tài xế có đủ điều kiện xét thưởng hay chưa. "
                        "Nếu các văn bản quy chế tìm được không áp dụng cho đối tượng/khu vực/loại xe của tài xế này (ví dụ quy chế chỉ áp dụng cho KOC hoặc Depot miền Trung, trong khi tài xế là taxi tiêu chuẩn tại TP.HCM), "
                        "hoặc hệ thống chưa có văn bản quy định cụ thể về tiêu chuẩn thưởng áp dụng cho đối tượng tài xế này trong kỳ, "
                        "hãy giải thích khách quan, rõ ràng lý do. TUYỆT ĐỐI CẤM dùng từ 'vi phạm' khi trả lời câu hỏi về khen thưởng/đãi ngộ."
                    )
                    policy_basis_instruction = (
                        "- **Về căn cứ quy chế:** Nêu các văn bản quy chế GSM liên quan tra cứu được (Mã Pxxx, tiêu đề, ngày hiệu lực) và giải thích rõ phạm vi áp dụng, hoặc ghi rõ 'Chưa có văn bản quy chế quy định cụ thể về tiêu chuẩn thưởng cho đối tượng tài xế này trong hệ thống'."
                    )
                else:
                    conclusion_instruction = (
                        "- **Về kết luận vi phạm:** Trả lời trực diện người dùng xem tài xế CÓ VI PHẠM hay KHÔNG VI PHẠM:\n"
                        "  + Nếu tài xế KHÔNG có chuyến hủy, không có sự cố, không có vi phạm (hồ sơ sạch): Khẳng định rõ ràng tài xế KHÔNG VI PHẠM quy chế hủy chuyến/chính sách trong kỳ đối soát.\n"
                        "  + Nếu tài xế có chuyến hủy/sự cố nhưng văn bản quy chế tìm được chưa có hiệu lực (ví dụ: P001 hiệu lực từ 09/09/2026 trong khi sự việc xảy ra tháng 08/2026) hoặc chỉ áp dụng cho đối tượng khác (ví dụ: P221 áp dụng cho xe máy Green SM Bike trong khi tài xế lái taxi ô tô): Nêu rõ hiện tại chưa đủ căn cứ từ các văn bản quy chế đã tra cứu để kết luận chế tài áp dụng cho những sự việc này, kèm khuyến nghị hoặc lưu ý vận hành.\n"
                        "  + Nếu vi phạm rõ ràng: Khẳng định có vi phạm và nêu chế tài tương ứng theo quy định."
                    )
                    policy_basis_instruction = (
                        "- **Về căn cứ và đối chiếu quy chế GSM:**\n"
                        "  + Nếu có văn bản quy chế tìm được (Mã Pxxx, tiêu đề): Nêu rõ nội dung điều khoản liên quan, ngày ban hành/bắt đầu hiệu lực và đối tượng áp dụng (ô tô hay xe máy). Phải đối chiếu cụ thể với hành vi của tài xế.\n"
                        "  + Nếu tài xế hoàn toàn không có chuyến hủy hoặc sự cố: Nêu rõ tài xế tuân thủ tốt, không phát sinh hành vi vi phạm nên không thuộc diện bị áp dụng chế tài xử phạt theo quy định hủy chuyến của GSM.\n"
                        "  + Nếu hệ thống chưa có văn bản áp dụng cho kỳ này: Giải thích rõ ràng và tự nhiên rằng hiện tại chưa có văn bản quy chế áp dụng tại mốc thời gian đang xét."
                    )

                synthesis_prompt = (
                    f"CÂU HỎI BAN ĐẦU CỦA NHÂN VIÊN VẬN HÀNH: {query}\n\n"
                    f"{verified_str}"
                    f"{policy_summary_str}"
                    f"CÁC BƯỚC SUY LUẬN VÀ QUAN SÁT THỰC TẾ (DỮ LIỆU THU THẬP ĐƯỢC):\n{scratchpad}\n\n"
                    "YÊU CẦU TỔNG HỢP CÂU TRẢ LỜI TỰ NHIÊN & ĐẦY ĐỦ:\n"
                    f"- Dựa trên số liệu và dữ liệu thực tế tại mốc {time_info}, hãy đối soát thông tin cho {driver_info} bằng phong cách chuyên nghiệp của một chuyên viên Quản lý Vận hành GSM.\n\n"
                    "QUY TẮC BẮT BUỘC ĐỂ ĐẢM BẢO TỰ NHIÊN VÀ ĐỦ Ý:\n"
                    "1. PHONG CÁCH DIỄN ĐẠT TỰ NHIÊN (KHÔNG RẬP KHUÔN BIỂU MẪU):\n"
                    "   - Hãy hành văn tự nhiên bằng các đoạn văn nghiệp vụ mạch lạc, kết nối logic giữa các ý (hoặc sử dụng các gạch đầu dòng ngắn gọn, sạch sẽ khi cần nêu số liệu cụ thể).\n"
                    "   - TUYỆT ĐỐI CẤM sao chép các cụm từ hướng dẫn trong đề bài làm tiêu đề rỗng hay mẫu điền khuyết (như 'Số liệu chuyến hoàn thành: Không có...', 'Căn cứ và đối chiếu quy chế GSM: Không có...', 'Trả lời trực diện: Không có...').\n"
                    "   - TUYỆT ĐỐI CẤM rò rỉ các thuật ngữ kỹ thuật nội bộ như 'Observation', 'Action', 'từ công cụ get_cancelled_trips_detail', 'scratchpad', 'tool', 'công cụ' trong câu trả lời. Hãy dùng ngôn ngữ nghiệp vụ: 'Theo dữ liệu hệ thống ghi nhận', 'Qua tra cứu lịch sử chuyến xe', 'Theo quy chế hiện hành của GSM'...\n\n"
                    "2. ĐẢM BẢO ĐỦ NỘI DUNG (SỐ LIỆU / TÍNH TOÁN, QUY CHẾ / CHÍNH SÁCH, KẾT LUẬN):\n"
                    "   - VỀ SỐ LIỆU VẬN HÀNH & TÍNH TOÁN: Nếu có số liệu (chuyến hoàn thành, chuyến hủy, tỷ lệ hủy cancel_rate_30d, doanh thu, đánh giá sao, tỷ lệ nhận/hoàn thành cuốc...), hãy nêu đầy đủ các con số cụ thể và kết quả tính toán chính xác từ hệ thống. Nếu tài xế có hồ sơ sạch (0 chuyến hủy, không sự cố), hãy nêu rõ ràng rằng tài xế không có chuyến xe nào bị hủy và không phát sinh sự cố trong kỳ. Nếu tài xế có chuyến bị hủy, hãy nêu rõ số chuyến hủy và tóm tắt nguyên nhân của các chuyến hủy gần nhất (do khách hủy, lý do bất khả kháng theo quy chế P094 hay tài xế tự ý hủy) nếu có trong dữ liệu quan sát.\n"
                    "   - VỀ CĂN CỨ QUY CHẾ & CHÍNH SÁCH:\n"
                    f"     {policy_basis_instruction}\n"
                    "   - VỀ KẾT LUẬN RÕ RÀNG:\n"
                    f"     {conclusion_instruction}\n\n"
                    "- CẤM ẢO GIÁC MÃ QUY CHẾ: Chỉ được trích dẫn mã văn bản quy chế nếu mã đó xuất hiện trong danh sách văn bản đã tra cứu hoặc các bước suy luận ở trên. TUYỆT ĐỐI KHÔNG tự bịa ra bất kỳ mã quy chế Pxxx nào không có trong dữ liệu.\n"
                    "- TUYỆT ĐỐI CẤM LẶP LẠI CÂU VĂN: Không bao giờ lặp lại cùng một câu văn nhiều lần.\n"
                    "- Tránh văn phong rập khuôn, máy móc. Cấm xuất ra các thẻ Thought: hay Final Answer:."
                )
            messages = [
                {"role": "system", "content": "Bạn là Trợ lý AI Quản trị Vận hành & Chính sách của GSM (Taxi Xanh SM). Hãy trả lời trực tiếp vào nội dung một cách tự nhiên, chính xác, khách quan và chuyên nghiệp dựa trên các dữ liệu quan sát thu được. Tuyệt đối không lặp lại câu lệnh hệ thống hay lời dẫn mở đầu."},
            ]
            raw_history = context.get("chat_history") or []
            for item in raw_history[-4:]:
                h_role = item.get("role", "user")
                h_content = str(item.get("content", "")).strip()
                if not h_content:
                    continue
                if h_role == "assistant" and len(h_content) > 800:
                    h_content = h_content[:800] + "..."
                messages.append({"role": h_role, "content": h_content})
            messages.append({"role": "user", "content": synthesis_prompt})
            synth_resp, _, _ = self.call_llm_fn(messages=messages, max_tokens=1200, temperature=0.3)
            if synth_resp and len(synth_resp.strip()) > 30:
                cleaned_synth = synth_resp.strip()
                fm = re.search(r"Final Answer:\s*(.*)", cleaned_synth, re.DOTALL | re.IGNORECASE)
                if fm:
                    cleaned_synth = fm.group(1).strip()
                cleaned_synth = re.sub(r"^(?:Thought:[^\n]*\n+|Final Answer:\s*)+", "", cleaned_synth, flags=re.IGNORECASE).strip()
                cleaned_synth = re.sub(
                    r"^(?:Dưới đây là\s+)?(?:Câu trả lời|Báo cáo|Kết quả)(?:[^\n:]{0,120}):\s*",
                    "",
                    cleaned_synth,
                    flags=re.IGNORECASE,
                ).strip()
                cleaned_synth = deduplicate_repeated_text(cleaned_synth)
                final_answer = cleaned_synth

        # Sanitize technical leaks and robotic form-filling artifacts
        def _sanitize_natural_text(text: str) -> str:
            if not text:
                return text
            t = re.sub(
                r",?\s*(?:như\s+)?(?:được\s+)?ghi nhận\s+(?:trong\s+)?Observation(?:\s+từ\s+công\s+cụ\s+\w+)?",
                "",
                text,
                flags=re.IGNORECASE,
            )
            t = re.sub(r"(?:trong\s+)?Observation\s+từ\s+công\s+cụ\s+\w+", "trong dữ liệu hệ thống", t, flags=re.IGNORECASE)
            t = re.sub(r"\bObservation\b", "dữ liệu hệ thống", t, flags=re.IGNORECASE)
            t = re.sub(r"(?:từ\s+)?công\s+cụ\s+get_cancelled_trips_detail\b", "hệ thống kiểm tra chuyến hủy", t, flags=re.IGNORECASE)
            t = re.sub(r"(?:từ\s+)?công\s+cụ\s+search_gsm_policies\b", "hệ thống tra cứu quy chế", t, flags=re.IGNORECASE)
            t = re.sub(r"(?:từ\s+)?công\s+cụ\s+get_full_policy_document\b", "hệ thống văn bản quy chế", t, flags=re.IGNORECASE)
            t = re.sub(r"(?:từ\s+)?công\s+cụ\s+[a-zA-Z0-9_]+\b", "hệ thống quản trị vận hành", t, flags=re.IGNORECASE)
            t = re.sub(r"(?:^|\n)\s*Số liệu chuyến hoàn thành:\s*Không có[^\n]*", "", t, flags=re.IGNORECASE)
            t = re.sub(r"(?:^|\n)\s*Tỷ lệ hủy\s*\([^)]*\):\s*Không có[^\n]*", "", t, flags=re.IGNORECASE)
            t = re.sub(r"(?:^|\n)\s*Sự cố/khiếu nại phát sinh:\s*Không có[^\n]*", "", t, flags=re.IGNORECASE)
            t = re.sub(r"(?:^|\n)\s*Văn bản quy chế GSM tìm thấy:\s*Không có[^\n]*", "", t, flags=re.IGNORECASE)
            t = re.sub(r"(?:^|\n)\s*Giải thích hiệu lực áp dụng:\s*Không có[^\n]*", "", t, flags=re.IGNORECASE)
            t = re.sub(r"(?:^|\n)\s*Trả lời trực diện[^\n:]*:\s*", "", t, flags=re.IGNORECASE)
            t = re.sub(r"(?:^|\n)\s*Tình hình vận hành thực tế:\s*(?=\n\s*(?:Số liệu|Không|\n))", "", t, flags=re.IGNORECASE)
            t = re.sub(r"(?:^|\n)\s*Căn cứ và đối chiếu quy chế GSM:\s*(?=\n\s*(?:Không|\n))", "", t, flags=re.IGNORECASE)
            t = re.sub(r"(?:^|\n)\s*Kết luận rõ ràng:\s*(?=\n)", "", t, flags=re.IGNORECASE)
            t = re.sub(r"\n{3,}", "\n\n", t)
            return t.strip()

        if final_answer:
            final_answer = _sanitize_natural_text(final_answer)

        # Anti-ghost-policy guard: Sanitize any hallucinated policy codes Pxxx not present in citations, context or query
        if final_answer:
            valid_policy_codes: set[str] = set()
            for c in citations:
                pa = c.get("policy_alias")
                if pa:
                    valid_policy_codes.add(str(pa).upper())
                pc = c.get("policy_code")
                if pc:
                    valid_policy_codes.add(str(pc).upper())
            for s in steps:
                if isinstance(s.observation, dict):
                    if "policies" in s.observation:
                        for p_item in s.observation.get("policies", []):
                            if p_item.get("policy_alias"):
                                valid_policy_codes.add(str(p_item["policy_alias"]).upper())
                    if "matched_policy_codes" in s.observation:
                        for c in s.observation.get("matched_policy_codes", []):
                            valid_policy_codes.add(str(c).upper())
                    if s.observation.get("doc_id"):
                        valid_policy_codes.add(str(s.observation["doc_id"]).upper())
                    if s.observation.get("policy_code"):
                        valid_policy_codes.add(str(s.observation["policy_code"]).upper())
            if context.get("policy_scope"):
                p_scope = context["policy_scope"]
                if isinstance(p_scope, list):
                    valid_policy_codes |= {str(p).upper() for p in p_scope}
                elif isinstance(p_scope, str):
                    valid_policy_codes.add(p_scope.upper())
            query_policies = set(re.findall(r"\b(P\d{2,3})\b", query, re.IGNORECASE))
            valid_policy_codes |= {p.upper() for p in query_policies}

            ghost_codes = [
                p for p in set(re.findall(r"\b(P\d{2,3})\b", final_answer, re.IGNORECASE))
                if p.upper() not in valid_policy_codes
            ]
            if ghost_codes:
                print(f"[ReAct Agent] Detected ghost policy codes {ghost_codes} not in evidence citations. Sanitizing...")
                for gp in ghost_codes:
                    final_answer = re.sub(
                        rf"(?:văn bản\s+)?(?:quy chế|chính sách)\s+{gp}\b",
                        "quy chế hiện hành của GSM",
                        final_answer,
                        flags=re.IGNORECASE,
                    )
                    final_answer = re.sub(
                        rf"\b{gp}\b",
                        "quy chế hiện hành của GSM",
                        final_answer,
                    )

        if final_answer:
            final_answer = deduplicate_repeated_text(final_answer)

        result = ReActResult(
            query=query,
            steps=steps,
            final_answer=final_answer or "Không thể xác định câu trả lời sau các vòng lặp ReAct.",
            citations=citations,
            status="ANSWERED",
            model_used=model_used,
        )

        yield {
            "type": "final_result",
            "result": result,
        }

    def run(self, query: str, context: dict[str, Any] | None = None) -> ReActResult:
        """Run the ReAct autonomous loop synchronously with anti-hallucination guards."""
        res: ReActResult | None = None
        for ev in self.run_stream(query, context):
            if ev.get("type") == "final_result":
                res = ev.get("result")
        return res or ReActResult(
            query=query,
            final_answer="Không thể xác định câu trả lời sau các vòng lặp ReAct.",
            status="ERROR",
        )
