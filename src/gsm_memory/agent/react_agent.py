"""ReAct (Reasoning + Acting) Agent Engine for GSM Conversational Operations.

Implements autonomous tool selection and dynamic thought-action-observation loop
for operational queries, standards verification (attendance, completion & acceptance
rates, revenue quotas), Knowledge Graph traversal, and policy retrieval.
"""

from __future__ import annotations

import json
import re
import sys
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
    calculate_cancel_rate,
    calculate_completion_rate,
    calculate_revenue_charge,
    evaluate_daily_revenue,
    evaluate_rating_condition,
    get_cancelled_trips_detail,
    get_driver_daily_stats,
    get_driver_profile,
    get_driver_trip_metrics,
    query_driver_graph,
    search_gsm_policies,
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


class ReActAgent:
    """Autonomous ReAct Agent for Multi-step Reasoning & Tool Calling."""

    def __init__(
        self,
        call_llm_fn: Callable[..., tuple[str, str, dict[str, int]]],
        pipeline_ref: Any = None,
        db_repo: Any = None,
        max_iterations: int = 5,
    ) -> None:
        self.call_llm_fn = call_llm_fn
        self.pipeline_ref = pipeline_ref
        self.db_repo = db_repo
        self.max_iterations = max_iterations
        self.tools_schema = TOOL_SCHEMAS

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
        thought_match = re.search(r"Thought:\s*(.*?)(?=\n*Action(?:\s*\d+)?:\s*|\Z)", raw_text, re.DOTALL | re.IGNORECASE)
        if thought_match and thought_match.group(1).strip():
            return thought_match.group(1).strip()
        before_action = re.split(r"\bAction(?:\s*\d+)?:\s*", raw_text, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        cleaned = re.sub(r"^Thought:\s*", "", before_action, flags=re.IGNORECASE).strip()
        return cleaned or "Thực thi công cụ tra cứu dữ liệu từ hệ thống."

    def _parse_actions(self, raw_text: str) -> list[tuple[str, dict[str, Any]]]:
        """Parse one or multiple Action and Action Input blocks from LLM output."""
        actions: list[tuple[str, dict[str, Any]]] = []
        known_names = [t["name"] for t in self.tools_schema]

        # 1. Check for JSON array under Actions:
        m_array = re.search(r"Actions:\s*(\[\s*\{.*?\}\s*\])", raw_text, re.DOTALL | re.IGNORECASE)
        if m_array:
            try:
                arr = json.loads(m_array.group(1))
                for item in arr:
                    if isinstance(item, dict) and "action" in item:
                        act_val = str(item["action"]).strip()
                        if act_val and not re.match(r"^(?:final(?:_answer)?|finish|done|none|complete)\b", act_val, re.IGNORECASE):
                            actions.append((act_val, item.get("action_input", {})))
                if actions:
                    return actions
            except Exception:
                pass

        # 2. Match all Action [i]: ... Action Input [i]: {...} blocks
        pattern = re.compile(
            r"Action(?:\s*\d+)?:\s*([^\n\r]+?)\s*(?:\r?\n)+\s*Action Input(?:\s*\d+)?:\s*(?:```(?:json)?\s*)?(\{.*?\})(?:\s*```)?",
            re.DOTALL | re.IGNORECASE,
        )
        matches = pattern.findall(raw_text)
        for act_str, inp_str in matches:
            act_clean = act_str.strip().strip("`'\"")
            if re.match(r"^(?:final(?:_answer)?|finish|done|none|complete)\b", act_clean, re.IGNORECASE):
                continue

            matched_tool = None
            for kt in known_names:
                if re.search(rf"\b{kt}\b", act_clean, re.IGNORECASE):
                    matched_tool = kt
                    break
            if not matched_tool:
                m_word = re.search(r"([a-zA-Z0-9_]{3,})", act_clean)
                if m_word:
                    candidate = m_word.group(1).strip()
                    if not re.match(r"^(?:final(?:_answer)?|finish|done|none|complete)\b", candidate, re.IGNORECASE):
                        matched_tool = candidate

            parsed_inp: dict[str, Any] = {}
            try:
                parsed_inp = json.loads(inp_str.strip())
            except Exception:
                kv_pairs = re.findall(r'"([a-zA-Z0-9_]+)"\s*:\s*(?:"([^"]*)"|(\d+)|(true|false))', inp_str, re.IGNORECASE)
                for k, s_val, n_val, b_val in kv_pairs:
                    if s_val:
                        parsed_inp[k] = s_val
                    elif n_val:
                        parsed_inp[k] = int(n_val)
                    elif b_val:
                        parsed_inp[k] = (b_val.lower() == "true")

            if matched_tool:
                actions.append((matched_tool, parsed_inp))

        # 3. Fallback to single action regex if pattern found nothing but Action exists
        if not actions and re.search(r"\bAction:\s*", raw_text, re.IGNORECASE):
            action_header_match = re.search(r"Action:\s*(.*)", raw_text, re.IGNORECASE)
            action_snippet = action_header_match.group(1) if action_header_match else raw_text
            if not re.match(r"^\s*(?:final(?:_answer)?|finish|done|none|complete)\b", action_snippet, re.IGNORECASE):
                action_name = None
                for kt in known_names:
                    if re.search(rf"\b{kt}\b", action_snippet, re.IGNORECASE):
                        action_name = kt
                        break
                if not action_name and action_header_match:
                    m_word = re.search(r"[`'\"]?([a-zA-Z0-9_]{3,})[`'\"]?", action_snippet)
                    if m_word:
                        candidate = m_word.group(1).strip()
                        if not re.match(r"^(?:final(?:_answer)?|finish|done|none|complete)\b", candidate, re.IGNORECASE):
                            action_name = candidate

                input_match = re.search(r"Action Input:\s*(?:```(?:json)?\s*)?(\{.*?\})(?:\s*```)?", raw_text, re.DOTALL | re.IGNORECASE)
                action_input: dict[str, Any] = {}
                if input_match:
                    try:
                        action_input = json.loads(input_match.group(1).strip())
                    except Exception:
                        pass
                if action_name:
                    actions.append((action_name, action_input))

        return actions

    def execute_tool(self, action_name: str, action_input: dict[str, Any]) -> tuple[Any, dict[str, Any] | None]:
        """Dispatch tool name with parameters and generate corresponding citation."""
        name = action_name.strip()
        args = self._resolve_context_args(action_input)
        ctx = getattr(self, "active_context", {}) or {}
        citation = None

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
                res = evaluate_daily_revenue(
                    revenue_vnd=int(args.get("revenue_vnd", 0)),
                    threshold_vnd=thresh_vnd,
                    date=str(args.get("date", "")),
                )
                citation = {
                    "source_kind": "computation",
                    "citation_locator": "computation:daily_revenue",
                    "policy_alias": "Định mức doanh số",
                    "policy_title": "Kiểm tra doanh số theo ngày",
                    "category": "Tính toán số học chuẩn xác",
                    "content": res.get("summary", ""),
                }
                return res, citation

            elif name == "calculate_cancel_rate":
                res = calculate_cancel_rate(
                    cancelled_trips=int(args.get("cancelled_trips", 0)),
                    total_trips=int(args.get("total_trips", 0)),
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

            elif name == "get_driver_trip_metrics":
                driver_ident = str(args.get("driver_identifier") or args.get("driver_id") or "")
                target_snap = args.get("snapshot_id") or ctx.get("snapshot_id")
                target_date = args.get("date") or ctx.get("time_resolved") or ctx.get("time_scope")
                res = get_driver_trip_metrics(
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
                target_date = args.get("date") or ctx.get("time_resolved") or ctx.get("time_scope")
                res = get_cancelled_trips_detail(
                    db_repo=self.db_repo,
                    driver_identifier=driver_ident,
                    snapshot_id=target_snap,
                    date=target_date,
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

            elif name == "get_driver_daily_stats":
                target_date = str(args.get("date") or ctx.get("time_resolved") or ctx.get("time_scope") or "2026-09-15")
                res = get_driver_daily_stats(
                    db_repo=self.db_repo,
                    driver_id=str(args.get("driver_id", "")),
                    date=target_date,
                )
                citation = {
                    "source_kind": "kg_subgraph",
                    "citation_locator": f"ledger:trips:{args.get('driver_id', '')}:{target_date}",
                    "policy_alias": "Lịch sử chuyến đi",
                    "policy_title": f"Chuyến đi thời gian {target_date}",
                    "category": "Cơ sở dữ liệu vận hành",
                    "content": res.get("summary", ""),
                }
                return res, citation

            elif name == "query_driver_graph":
                driver_ident = str(args.get("driver_identifier") or args.get("driver_id") or ctx.get("driver_id") or ctx.get("driver_mention") or "")
                target_snap = args.get("snapshot_id") or ctx.get("snapshot_id")
                res = query_driver_graph(
                    pipeline=self.pipeline_ref,
                    driver_id=driver_ident,
                    snapshot_id=target_snap,
                )
                citation = {
                    "source_kind": "kg_subgraph",
                    "citation_locator": f"kg:subgraph:{driver_ident}",
                    "policy_alias": "Đồ thị tri thức (KG)",
                    "policy_title": f"Mạng lưới nút & cạnh quan hệ của tài xế {driver_ident}",
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

            else:
                return {"error": f"Không tìm thấy công cụ '{name}'."}, None

        except Exception as e:
            return {"error": f"Lỗi khi thực thi công cụ '{name}': {str(e)}"}, None

    def run_stream(self, query: str, context: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        """Run the ReAct autonomous loop and yield live step events (thoughts, actions, observations)."""
        context = context or {}
        self.active_context = context
        tools_prompt = self._build_tools_prompt()

        system_prompt = (
            "Bạn là Trợ lý AI Quản trị & Vận hành Chuyên nghiệp của Taxi Xanh SM (GSM).\n"
            "Bạn giải quyết các câu hỏi theo mô hình ReAct (Reasoning + Acting) - suy luận nhiều bước và chủ động gọi công cụ.\n\n"
            f"DANH SÁCH CÔNG CỤ (TOOLS) BẠN CÓ QUYỀN SỬ DỤNG:\n{tools_prompt}\n\n"
            "QUY TẮC ĐỊNH DẠNG REACT (HỖ TRỢ 1 HOẶC NHIỀU CÔNG CỤ):\n"
            "Ở mỗi bước suy luận, bạn có thể gọi 1 HOẶC NHIỀU công cụ nếu các công cụ đó có thể thực hiện đồng thời hoặc độc lập (ví dụ: vừa tra cứu quy chế `search_gsm_policies`, vừa lấy số liệu tài xế `get_driver_daily_stats`, hoặc tính toán cùng lúc `calculate_acceptance_rate` và `calculate_completion_rate`).\n"
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
            "QUY TẮC BẮT BUỘC KHI SUY LUẬN (CHỐNG PHỎNG ĐOÁN & CHỐNG NHẢY CÓC):\n"
            "1. TUYỆT ĐỐI KHÔNG xuất ra Final Answer ngay ở bước đầu tiên nếu chưa có ít nhất một Observation từ công cụ tra cứu. Mọi kết luận phải dựa trên số liệu và văn bản thực tế trong hệ thống, cấm tự bịa số liệu.\n"
            "2. Khi câu hỏi liên quan đến tài xế (ví dụ: DRV-002, DRV-007, tài xế Bình, Giang...):\n"
            "   - BẮT BUỘC ưu tiên gọi `query_driver_graph` để tra cứu đồ thị tri thức (Knowledge Graph): tìm kiếm các nút thực thể (Driver, Trip, Fleet, Incident, Measurement) và các cạnh liên kết quan hệ thực tế trong đồ thị.\n"
            "   - Gọi `get_driver_profile` để tra cứu hồ sơ nhân sự, phương tiện, biển số, trạng thái hoạt động.\n"
            "   - Gọi `get_driver_trip_metrics` để lấy số cuốc hoàn thành, số cuốc hủy và tỷ lệ hủy theo ngày/tháng/năm hoặc theo snapshot.\n"
            "   - Gọi `get_cancelled_trips_detail` khi cần biết danh sách cụ thể các chuyến bị hủy và nguyên nhân hủy (theo ngày/tháng/năm hoặc snapshot).\n"
            "   - Gọi `get_driver_daily_stats` khi cần số cuốc xe và doanh thu theo một ngày cụ thể.\n"
            "3. Khi câu hỏi yêu cầu tính toán chỉ số (ĐẶC BIỆT LÀ TỶ LỆ HỦY CHUYẾN cancel_rate_30d, Tỷ lệ nhận cuốc AR, Tỷ lệ hoàn thành CR, Doanh số, Khoản bù trừ):\n"
            "   - BẮT BUỘC phải gọi công cụ tính toán tương ứng (`calculate_cancel_rate`, `calculate_acceptance_rate`, `calculate_completion_rate`, `calculate_revenue_charge`...).\n"
            "   - TUYỆT ĐỐI CẤM tự nhẩm tính hoặc tự đưa ra tỷ lệ trong Final Answer khi chưa thực hiện gọi tool tính toán chuẩn xác.\n"
            "4. Khi câu hỏi liên quan đến kiểm tra tiêu chuẩn vận hành, tiêu chuẩn chấm công (attendance), đối soát, hoặc vi phạm chính sách:\n"
            "   - BẮT BUỘC gọi `search_gsm_policies` để tra cứu văn bản quy chế gốc làm căn cứ pháp lý và lấy các tiêu chuẩn/ngưỡng định mức.\n"
            "   - NGUYÊN TẮC PHÂN TÁCH TRÁCH NHIỆM (DECOUPLING): Các công cụ (tools) chỉ đảm nhiệm việc tìm kiếm (search), trích xuất số liệu (get_driver_daily_stats...) và tính toán số học chuẩn xác (calculate_acceptance_rate, calculate_completion_rate...). VIỆC ĐỐI CHIẾU, SO SÁNH VÀ KẾT LUẬN TIÊU CHUẨN HOÀN TOÀN DO AGENT THỰC HIỆN dựa trên việc nhìn vào điều khoản quy chế tìm được và số liệu trả về từ các công cụ.\n"
            "   - Quy trình kiểm tra tiêu chuẩn chấm công/vận hành theo ngày:\n"
            "     + Bước 1: Gọi `search_gsm_policies` để tìm văn bản quy chế điều chỉnh (ví dụ: Quy chế Xanh Limo, Quy chế Xanh SM Taxi) và trích xuất các tiêu chuẩn bắt buộc (ngưỡng AR, CR, doanh số...).\n"
            "     + Bước 2: Gọi `get_driver_daily_stats` để lấy số liệu thực tế của tài xế trong ngày (số cuốc phát, nhận, hoàn thành, hủy, doanh thu).\n"
            "     + Bước 3: Gọi các tool tính toán (`calculate_acceptance_rate`, `calculate_completion_rate`...) để có tỷ lệ số học chuẩn xác.\n"
            "     + Bước 4: Agent tự đối chiếu từng chỉ số thực tế so với ngưỡng quy chế trong Thought và đưa ra kết luận chi tiết từng tiêu chí trong Final Answer.\n"
            "5. NGUYÊN TẮC ĐỐI CHIẾU PHÁP LÝ & KẾT LUẬN (QUAN TRỌNG NHẤT - CẤM ẢO GIÁC):\n"
            "   - TUYỆT ĐỐI CẤM TỰ BỊA RA MÃ QUY CHẾ: CHỈ ĐƯỢC trích dẫn mã quy chế và điều khoản nếu mã đó XUẤT HIỆN TRONG OBSERVATION thực tế từ công cụ `search_gsm_policies`. Nếu không có mã quy chế nào điều chỉnh cụ thể chủ đề này, BẮT BUỘC ghi 'Chưa có văn bản quy chế quy định cụ thể về [chủ đề]' hoặc nêu tên chung 'Bộ Quy tắc Ứng xử GSM'. TUYỆT ĐỐI KHÔNG tự bịa ra bất kỳ mã quy chế nào không có trong Observation!\n"
            "   - TUYỆT ĐỐI KHÔNG KẾT LUẬN 'đạt tiêu chuẩn' hay 'không phát sinh vi phạm' nếu KHÔNG CÓ quy chế hay tiêu chuẩn nào quy định về điều đó trong hệ thống.\n"
            "   - NẾU KHÔNG CÓ HOẶC KHÔNG TÌM THẤY VĂN BẢN QUY CHẾ điều chỉnh chủ đề được hỏi (ví dụ: không có quy định mức trần về tỷ lệ hủy chuyến):\n"
            "     + Căn cứ quy chế: Nêu rõ 'Hệ thống hiện chưa có văn bản quy chế quy định cụ thể về [chủ đề].'\n"
            "     + Kết luận: BẮT BUỘC KẾT LUẬN: 'Hiện tại chưa đủ căn cứ/cơ sở để xác định tài xế có vi phạm hay đạt tiêu chuẩn về [chủ đề], do hệ thống chưa có văn bản quy định cụ thể về mức trần hoặc chế tài áp dụng.'\n"
            "     + TUYỆT ĐỐI CẤM TỰ BỊA ra kết luận 'Đạt tiêu chuẩn vận hành tốt, không phát sinh vi phạm'.\n"
            "   - NẾU TÀI XẾ CÓ PHÁT SINH CHUYẾN BỊ HỦY (ví dụ: do yêu cầu của tài xế driver_request):\n"
            "     + Phải ghi nhận trung thực số chuyến bị hủy và lý do hủy từ dữ liệu Observation.\n"
            "     + Nếu không có quy chế phạt hủy chuyến: Nêu rõ chưa đủ căn cứ quy chế để kết luận vi phạm, khuyến nghị bộ phận quản lý theo dõi và trao đổi thêm với tài xế.\n\n"
            "TIÊU CHUẨN ĐỊNH DẠNG BẮT BUỘC CỦA FINAL ANSWER (MẪU BÁO CÁO QUẢN TRỊ GSM 3 PHẦN):\n"
            "Khi đã có đủ các Observation thực tế từ công cụ, xuất ra:\n"
            "Thought: <Tổng kết ngắn gọn nguyên nhân nhân quả và dữ liệu đã thu thập>\n"
            "Final Answer:\n"
            "Dựa trên dữ liệu vận hành trong **[Thời gian]** và các quy định hiện hành của GSM, tôi đã kiểm tra thông tin cho **[Tên tài xế] ([Mã])** như sau:\n\n"
            "**1. Tình hình vận hành thực tế:**\n"
            "- **Lịch sử chuyến xe:** [Tổng số chuyến ghi nhận: số chuyến hoàn thành, số chuyến bị hủy theo dữ liệu Observation chuẩn xác]\n"
            "- **Chỉ số vận hành:** [Tỷ lệ hủy chuyến (cancel_rate_30d), tỷ lệ hoàn thành, AR nếu có]\n\n"
            "**2. Đối chiếu quy chế & Kết luận:**\n"
            "   - **Kết luận:** [Nếu hỏi về vi phạm: nếu có vi phạm thì nêu rõ; nếu KHÔNG tìm thấy quy chế quy định cụ thể thì ghi 'Hiện tại chưa đủ căn cứ/cơ sở để khẳng định vi phạm do hệ thống chưa có văn bản quy định cụ thể về [chủ đề]'. Nếu hỏi về khen thưởng/chế độ: TUYỆT ĐỐI KHÔNG dùng từ 'vi phạm', ghi rõ 'Hiện tại chưa đủ căn cứ/cơ sở để xác định tài xế có đủ điều kiện xét thưởng hay không do hệ thống chưa có văn bản quy định cụ thể về tiêu chuẩn thưởng áp dụng cho đối tượng/khu vực của tài xế'. Chỉ ghi 'Đạt tiêu chuẩn' KHI CÓ quy chế rõ ràng và tài xế thỏa mãn 100% điều kiện của quy chế đó]\n"
            "- **Căn cứ quy chế:** [Đối chiếu văn bản quy chế GSM đã tra cứu từ search_gsm_policies, hoặc nêu rõ 'Chưa có văn bản quy chế quy định cụ thể về [chủ đề] trong hệ thống']\n"
            "- **Trích dẫn điều khoản liên quan:** [Trích đoạn nguyên văn điều khoản nếu có, hoặc ghi 'Không có điều khoản liên quan']\n\n"
            "**3. Khuyến nghị cho Quản lý vận hành:**\n"
            "- [1-2 khuyến nghị cụ thể, thiết thực cho quản lý vận hành]\n"
        )

        scratchpad = ""
        self.call_history: dict[str, dict[str, Any]] = {}
        steps: list[ReActStep] = []
        citations: list[dict[str, Any]] = []
        final_answer = ""
        model_used = ""

        # Contextual prefix from Query Plan & working memory
        ctx_notes = []
        if context.get("driver_id") or context.get("driver_mention"):
            ctx_notes.append(f"Tài xế xác định: {context.get('driver_mention') or context.get('driver_id')}")
        if context.get("snapshot_id"):
            ctx_notes.append(f"Snapshot xác định: {context.get('snapshot_id')}")
        if context.get("time_scope") or context.get("time_resolved"):
            ctx_notes.append(f"Mốc thời gian chuẩn hóa: {context.get('time_display') or context.get('time_resolved') or context.get('time_scope')}")
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
            has_called_policy = any(s.action == "search_gsm_policies" for s in steps)

            if not executed_actions:
                action_instruction = (
                    "Bước 1: Hãy đưa ra Thought và Action để gọi công cụ tra cứu dữ liệu thực tế đầu tiên. "
                    "BẮT BUỘC PHẢI GỌI CÔNG CỤ (Ưu tiên Action: query_driver_graph để mở rộng các nút & cạnh đồ thị nếu câu hỏi liên quan đến tài xế/vận hành, hoặc get_driver_profile, get_driver_trip_metrics, search_gsm_policies...), "
                    "TUYỆT ĐỐI KHÔNG xuất ra Final Answer khi chưa có Observation thực tế:"
                )
            elif has_policy_query and not has_called_policy:
                action_instruction = (
                    "Bước tiếp theo: Câu hỏi này liên quan đến chính sách/quy chế/vi phạm. "
                    "BẮT BUỘC bạn phải gọi Action: search_gsm_policies với Action Input phù hợp để tra cứu văn bản quy chế làm căn cứ pháp lý. "
                    "Ví dụ: Action: search_gsm_policies | Action Input: {\"query\": \"chính sách vi phạm hủy chuyến\"}. "
                    "CHƯA ĐƯỢC xuất Final Answer khi chưa có Observation từ search_gsm_policies:"
                )
            else:
                action_instruction = (
                    "Dựa trên các Observation thực tế đã có ở trên, hãy đưa ra bước tiếp theo (Thought + Action + Action Input) "
                    "HOẶC nếu đã có đủ căn cứ thực tế, hãy đưa ra (Thought + Final Answer) theo đúng chuẩn Báo cáo Quản trị GSM 3 phần:"
                )

            user_prompt = (
                f"CÂU HỎI: {query}\n"
                f"{ctx_str}\n"
                f"{scratchpad}\n"
                f"{action_instruction}"
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

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
                    # Guard 1: Cannot finalize without calling any tool if iteration < max_iterations
                    if not executed_actions and iteration < self.max_iterations:
                        scratchpad += (
                            f"\nThought: {raw_text}\n"
                            "Observation: Bạn chưa thực hiện bất kỳ công cụ (Action) nào để lấy dữ liệu thực tế từ hệ thống. "
                            "BẮT BUỘC phải gọi công cụ (Action: get_driver_profile, search_gsm_policies...) trước khi kết luận."
                        )
                        continue

                    # Guard 2: If query involves policy, violation, penalty, or standards, must search GSM policies
                    if has_policy_query and not has_called_policy and iteration < self.max_iterations:
                        yield {
                            "type": "thought",
                            "iteration": iteration,
                            "thought": "Câu hỏi liên quan đến chính sách/vi phạm nên cần tra cứu văn bản quy chế GSM trước khi đưa ra kết luận.",
                        }
                        scratchpad += (
                            f"\nThought: {raw_text}\n"
                            "Observation: Câu hỏi liên quan đến vi phạm / quy chế / chế tài đối soát nhưng bạn chưa gọi công cụ 'search_gsm_policies' để tra cứu văn bản quy chế GSM làm căn cứ pháp lý. "
                            "BẮT BUỘC phải thực hiện Action: search_gsm_policies với từ khóa phù hợp (ví dụ: {\"query\": \"quy tắc ứng xử vi phạm hủy chuyến xe máy bike\"}) trước khi đưa ra Final Answer."
                        )
                        continue

                    # Guard 3: If query involves cancel rate, must execute calculate_cancel_rate
                    has_cancel_rate_query = any(k in query.lower() for k in ["tỷ lệ hủy", "tỉ lệ hủy", "cancel_rate", "hủy chuyến là bao nhiêu"])
                    has_called_cancel_rate = any(s.action == "calculate_cancel_rate" for s in steps)
                    if has_cancel_rate_query and not has_called_cancel_rate and iteration < self.max_iterations:
                        yield {
                            "type": "thought",
                            "iteration": iteration,
                            "thought": "Câu hỏi yêu cầu xác định tỷ lệ hủy chuyến nên cần gọi công cụ calculate_cancel_rate để tính toán số học chuẩn xác.",
                        }
                        scratchpad += (
                            f"\nThought: {raw_text}\n"
                            "Observation: Câu hỏi yêu cầu xác định tỷ lệ hủy chuyến (cancel_rate_30d). "
                            "BẮT BUỘC bạn phải gọi Action: calculate_cancel_rate với tham số {\"cancelled_trips\": <số cuốc hủy>, \"total_trips\": <tổng số cuốc>} "
                            "từ số liệu thực tế để hệ thống tính toán chuẩn xác trước khi đưa ra Final Answer."
                        )
                        continue

                    # Guard 4: If query involves knowledge graph, nodes, or edges, must execute query_driver_graph
                    has_graph_query = any(k in query.lower() for k in ["đồ thị", "kg", "node", "nút", "cạnh", "mạng lưới", "quan hệ"])
                    has_called_graph = any(s.action == "query_driver_graph" for s in steps)
                    if has_graph_query and not has_called_graph and iteration < self.max_iterations:
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

                    has_3_sections = bool(
                        re.search(r"(?:1\.|Tình hình vận hành)", potential_ans)
                        and re.search(r"(?:2\.|Đối chiếu quy chế|Kết luận)", potential_ans)
                    )

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
                    executed_actions = [s for s in steps if s.action]
                    if len(raw_text) > 60 and "thought" not in raw_text.lower() and executed_actions:
                        final_answer = raw_text
                        break
                    else:
                        scratchpad += f"\nThought: {raw_text}\nObservation: Vui lòng đưa ra Action và Action Input hợp lệ để gọi công cụ từ danh sách."
                        continue

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

                        if call_count >= 3:
                            # Infinite loop detected! Force break loop
                            obs_result = {
                                "_repeat_status": "INFINITE_LOOP_PREVENTED",
                                "warning": (
                                    f"PHÁT HIỆN VÒNG LẶP TRÙNG LẶP: Công cụ '{action_name}' đã bị gọi lặp lại 3 lần với cùng bộ tham số. "
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
                                    "Vui lòng KHÔNG gọi lại công cụ với cùng tham số. "
                                    "Hãy sử dụng kết quả đã nhận được ở trên để đối chiếu và kết luận, "
                                    "thay đổi từ khóa/tham số nếu cần tra cứu bổ sung, hoặc đưa ra Thought và Final Answer."
                                ),
                                "data": cached_obs,
                            }
                            cit_result = None
                    else:
                        obs_result, cit_result = self.execute_tool(action_name, action_input)
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
        executed_actions = [s for s in steps if s.action]
        needs_structured_synthesis = (
            not final_answer
            or not (
                bool(re.search(r"(?:1\.|Tình hình vận hành)", final_answer))
                and bool(re.search(r"(?:2\.|Đối chiếu quy chế|Kết luận)", final_answer))
            )
        )

        if needs_structured_synthesis and executed_actions:
            yield {
                "type": "synthesis_start",
                "message": "Đang tổng hợp và đối soát dữ liệu thành Báo cáo Quản trị GSM 3 phần...",
            }

            driver_info = context.get("driver_mention") or context.get("driver_id") or "tài xế"
            time_info = context.get("time_display") or context.get("time_scope") or "kỳ đối soát vừa qua"

            verified_notes = []
            if context.get("driver_trips_summary"):
                verified_notes.append(f"Số liệu chuyến xe chuẩn xác từ hệ thống: {context.get('driver_trips_summary')}")
            if context.get("driver_cancel_rate") is not None:
                verified_notes.append(f"Tỷ lệ hủy chuyến chuẩn xác: {context.get('driver_cancel_rate'):.2f}%")
            verified_str = ("\nLƯU Ý ĐẶC BIỆT VỀ SỐ LIỆU:\n- " + "\n- ".join(verified_notes) + "\nBẮT BUỘC sử dụng đúng số liệu này, TUYỆT ĐỐI CẤM tự bịa số liệu chuyến đi hay số lần hủy.\n\n") if verified_notes else ""

            is_reward_query = any(k in query.lower() for k in ["thưởng", "khen thưởng", "đãi ngộ", "tiêu chuẩn thưởng", "xét thưởng"]) and not any(k in query.lower() for k in ["vi phạm", "xử phạt", "kỷ luật", "chế tài", "phạt"])

            if is_reward_query:
                conclusion_instruction = (
                    "- **Kết luận:** [BẮT BUỘC: Vì đây là câu hỏi về KHEN THƯỞNG/TIÊU CHUẨN ĐƯỢC THƯỞNG, TUYỆT ĐỐI CẤM dùng từ 'vi phạm'! "
                    "Nếu các văn bản quy chế tìm được không áp dụng cho đối tượng/khu vực/loại xe của tài xế này (ví dụ quy chế chỉ áp dụng cho KOC hoặc Depot miền Trung, trong khi tài xế là taxi tiêu chuẩn tại TP.HCM), "
                    "phải kết luận rõ: 'Hiện tại chưa đủ căn cứ/cơ sở để xác định tài xế có đủ điều kiện xét thưởng hay không do hệ thống chưa có văn bản quy định cụ thể về tiêu chuẩn thưởng áp dụng cho đối tượng tài xế này trong kỳ.' "
                    "TUYỆT ĐỐI KHÔNG tự ý kết luận 'đạt tiêu chuẩn thưởng' khi chưa có văn bản quy chế áp dụng cụ thể!]"
                )
                policy_basis_instruction = (
                    "- **Căn cứ quy chế:** [Nêu các văn bản quy chế GSM liên quan tra cứu được và giải thích rõ phạm vi áp dụng (ví dụ: các văn bản hiện có chỉ áp dụng cho đối tượng/khu vực khác), hoặc ghi rõ 'Chưa có văn bản quy chế quy định cụ thể về tiêu chuẩn thưởng cho đối tượng tài xế này trong hệ thống']"
                )
            else:
                conclusion_instruction = (
                    "- **Kết luận:** [BẮT BUỘC: Nếu không tìm thấy quy chế quy định cụ thể, phải kết luận 'Hiện tại chưa đủ căn cứ/cơ sở để xác định tài xế có vi phạm hay không do hệ thống chưa có văn bản quy định cụ thể về [chủ đề]'. TUYỆT ĐỐI KHÔNG kết luận 'đạt tiêu chuẩn' hoặc 'không vi phạm' khi không có quy chế hoặc khi có chuyến hủy!]"
                )
                policy_basis_instruction = (
                    "- **Căn cứ quy chế:** [Đối chiếu văn bản quy chế GSM liên quan tra cứu được, hoặc ghi rõ 'Chưa có văn bản quy chế quy định cụ thể về [chủ đề] trong hệ thống']"
                )

            synthesis_prompt = (
                f"CÂU HỎI BAN ĐẦU CỦA NHÂN VIÊN VẬN HÀNH: {query}\n\n"
                f"{verified_str}"
                f"CÁC BƯỚC SUY LUẬN VÀ QUAN SÁT THỰC TẾ (OBSERVATIONS THU ĐƯỢC TỪ CÔNG CỤ):\n{scratchpad}\n\n"
                "TIÊU CHUẨN ĐỊNH DẠNG BẮT BUỘC (MẪU BÁO CÁO QUẢN TRỊ GSM 3 PHẦN):\n"
                "Dựa trên các số liệu và quan sát thực tế ở trên, BẮT BUỘC xuất ra báo cáo đầy đủ theo đúng cấu trúc:\n"
                f"Dựa trên dữ liệu vận hành trong **{time_info}** và các quy định hiện hành của GSM, tôi đã kiểm tra thông tin cho **{driver_info}** như sau:\n\n"
                "**1. Tình hình vận hành thực tế:**\n"
                "- **Lịch sử chuyến xe:** [Nêu tổng số chuyến, số chuyến hoàn thành, số chuyến hủy theo dữ liệu Observation chuẩn xác]\n"
                "- **Chỉ số vận hành:** [Tỷ lệ hủy chuyến (cancel_rate_30d), AR, CR, doanh số nếu có]\n\n"
                "**2. Đối chiếu quy chế & Kết luận:**\n"
                f"{conclusion_instruction}\n"
                f"{policy_basis_instruction}\n"
                "- **Trích dẫn điều khoản liên quan:** [Trích dẫn điều khoản cụ thể từ Observation nếu có, hoặc ghi 'Không có điều khoản liên quan']\n\n"
                "**3. Khuyến nghị cho Quản lý vận hành:**\n"
                "- [1-2 khuyến nghị cụ thể, thiết thực cho quản lý]\n\n"
                "CẤM ẢO GIÁC MÃ QUY CHẾ: Chỉ được trích dẫn mã văn bản quy chế nếu mã đó xuất hiện trong Observation từ công cụ search_gsm_policies. TUYỆT ĐỐI KHÔNG tự bịa ra bất kỳ mã quy chế Pxxx nào không có trong Observation.\n"
                "Tuyệt đối không mở đầu xã giao. Không kết bài sáo rỗng. Cấm xuất ra các thẻ Thought: hay Final Answer:."
            )
            messages = [
                {"role": "system", "content": "Bạn là Trợ lý AI Quản trị Vận hành GSM. Hãy tổng hợp báo cáo chi tiết theo đúng cấu trúc 3 phần quy định."},
                {"role": "user", "content": synthesis_prompt},
            ]
            synth_resp, _, _ = self.call_llm_fn(messages=messages, max_tokens=1200, temperature=0.1)
            if synth_resp and len(synth_resp.strip()) > 50:
                cleaned_synth = synth_resp.strip()
                fm = re.search(r"Final Answer:\s*(.*)", cleaned_synth, re.DOTALL | re.IGNORECASE)
                if fm:
                    cleaned_synth = fm.group(1).strip()
                cleaned_synth = re.sub(r"^(?:Thought:[^\n]*\n+|Final Answer:\s*)+", "", cleaned_synth, flags=re.IGNORECASE).strip()
                final_answer = cleaned_synth

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
                if isinstance(s.observation, dict) and "policies" in s.observation:
                    for p_item in s.observation.get("policies", []):
                        if p_item.get("policy_alias"):
                            valid_policy_codes.add(str(p_item["policy_alias"]).upper())
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
