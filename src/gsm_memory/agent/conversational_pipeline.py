"""Conversational QA Pipeline with Query Understanding, Clarification,

Seed Selection, Subgraph Expansion, Multi-source Evidence, and Langfuse Tracing.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from dotenv import load_dotenv

load_dotenv()

# Ensure src is in sys.path
SRC_DIR = Path(__file__).resolve().parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fractions import Fraction

from gsm_memory.evaluation.formulas import cancel_rate
from gsm_memory.retrieval.bm25 import BM25Index
from gsm_memory.retrieval.documents import Chunk, ChunkConfig, construct_chunks


DEFAULT_RELEASE_DIR = Path("data/gsm-dev-core-0.2.2")
DEFAULT_SNAPSHOT_ID = "d4cc0438-d831-541a-8123-ddda94ccdac8"  # L0 reference snapshot as-of 2026-09-17


# Synthetic driver mappings in GSM benchmark
DRIVER_CODE_MAP: dict[str, str] = {
    "DRV-001": "99e70ebe-18cd-57a3-a036-cf0ff1989861",  # An
    "DRV-002": "c499f934-bfe1-5509-a578-afb09cee357c",  # Bình
    "DRV-003": "3b0b7be7-b553-5d99-9528-4a07ca4f1567",  # Chi
    "DRV-004": "cc916c6b-b168-5d8f-9023-075391ee4136",  # Dũng
    "DRV-005": "58e68d69-f07f-580e-a4b6-91ef3801c5d7",  # Minh (1)
    "DRV-006": "b8afff09-1200-5bcd-a594-6a647680f865",  # Minh (2)
    "DRV-007": "42c4b074-68f7-5f04-8ea7-a3f81e35a165",  # Giang
    "DRV-008": "964fb4ef-1bc7-5c21-b384-25e1a1c97a8a",  # Hà
    "D1": "99e70ebe-18cd-57a3-a036-cf0ff1989861",
    "D2": "c499f934-bfe1-5509-a578-afb09cee357c",
    "D3": "3b0b7be7-b553-5d99-9528-4a07ca4f1567",
    "D4": "cc916c6b-b168-5d8f-9023-075391ee4136",
    "D5": "58e68d69-f07f-580e-a4b6-91ef3801c5d7",
    "D6": "b8afff09-1200-5bcd-a594-6a647680f865",
    "D7": "42c4b074-68f7-5f04-8ea7-a3f81e35a165",
    "D8": "964fb4ef-1bc7-5c21-b384-25e1a1c97a8a",
}

DRIVER_NAME_MAP: dict[str, str | None] = {
    "an": "99e70ebe-18cd-57a3-a036-cf0ff1989861",
    "bình": "c499f934-bfe1-5509-a578-afb09cee357c",
    "binh": "c499f934-bfe1-5509-a578-afb09cee357c",
    "chi": "3b0b7be7-b553-5d99-9528-4a07ca4f1567",
    "dũng": "cc916c6b-b168-5d8f-9023-075391ee4136",
    "dung": "cc916c6b-b168-5d8f-9023-075391ee4136",
    "minh": None,  # Ambiguous between DRV-005 and DRV-006!
    "giang": "42c4b074-68f7-5f04-8ea7-a3f81e35a165",
    "hà": "964fb4ef-1bc7-5c21-b384-25e1a1c97a8a",
    "ha": "964fb4ef-1bc7-5c21-b384-25e1a1c97a8a",
}


@dataclass
class SlotExtractionResult:
    intent: str
    needs_driver: bool
    driver_id: str | None = None
    driver_mention: str | None = None
    is_driver_ambiguous: bool = False
    needs_time: bool = True
    has_time_scope: bool = False
    time_mention: str | None = None
    snapshot_id: str | None = None
    policy_mentions: list[str] = field(default_factory=list)
    missing_slots: list[str] = field(default_factory=list)


@dataclass
class SubgraphNode:
    id: str
    label: str
    name: str
    props: dict[str, Any]


@dataclass
class SubgraphEdge:
    start_id: str
    end_id: str
    rel_type: str
    props: dict[str, Any]


@dataclass
class Subgraph:
    seed_id: str
    snapshot_id: str
    nodes: list[SubgraphNode] = field(default_factory=list)
    edges: list[SubgraphEdge] = field(default_factory=list)


@dataclass
class PipelineResponse:
    status: str  # "ANSWERED" | "NEEDS_CLARIFICATION" | "ERROR"
    query: str
    slots: SlotExtractionResult
    clarification_message: str | None = None
    answer: str | None = None
    citations: list[dict[str, str]] = field(default_factory=list)
    subgraph: Subgraph | None = None
    trace_url: str | None = None


class ConversationalPipeline:
    """End-to-end Pipeline: Query Understanding -> Clarification -> Subgraph BFS -> Evidence -> LLM Reader."""

    def __init__(
        self,
        release_dir: Path = DEFAULT_RELEASE_DIR,
        snapshot_id: str = DEFAULT_SNAPSHOT_ID,
        model_name: str | None = None,
    ) -> None:
        self.release_dir = release_dir
        self.default_snapshot_id = snapshot_id
        self.model_name = model_name or os.getenv("OPENROUTER_MODEL") or "nvidia/nemotron-3.5-lightning:free"
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")

        # Load BM25 Document chunks
        print("[Pipeline Init] Loading GSM policy chunks (debug_core)...")
        self.chunks, _, _ = construct_chunks(self.release_dir, "debug_core", ChunkConfig())
        self.bm25_index = BM25Index(self.chunks)
        print(f"[Pipeline Init] Loaded {len(self.chunks)} policy chunks.")

        # Initialize Neo4j driver
        self.neo4j_driver = self._init_neo4j()

        # Initialize Langfuse
        self.langfuse = self._init_langfuse()

    def _init_neo4j(self) -> Any | None:
        from neo4j import GraphDatabase

        # Try NEO4J_OPERATIONAL first, then NEO4J
        creds_to_try = [
            (
                os.getenv("NEO4J_OPERATIONAL_URI") or os.getenv("NEO4J_URI"),
                os.getenv("NEO4J_OPERATIONAL_USERNAME") or os.getenv("NEO4J_USERNAME"),
                os.getenv("NEO4J_OPERATIONAL_PASSWORD"),
            ),
            (
                os.getenv("NEO4J_URI"),
                os.getenv("NEO4J_USERNAME"),
                os.getenv("NEO4J_PASSWORD"),
            ),
        ]

        for uri, username, password in creds_to_try:
            if uri and username and password:
                try:
                    driver = GraphDatabase.driver(uri, auth=(username, password))
                    driver.verify_connectivity()
                    print(f"[Pipeline Init] Connected to Neo4j successfully at {uri}.")
                    return driver
                except Exception as e:
                    pass
        print("[Pipeline Init] Neo4j connection not available, using offline graph fallback.")
        return None

    def _init_langfuse(self) -> Any | None:
        try:
            from langfuse import Langfuse

            lf = Langfuse()
            if lf.auth_check():
                print("[Pipeline Init] Langfuse initialized and authenticated.")
                return lf
            print("[Pipeline Init] Langfuse auth check failed.")
        except Exception as e:
            print(f"[Pipeline Init] Langfuse init failed: {e}")
        return None

    # =========================================================================
    # Step 1: Query Understanding & Slot Filling
    # =========================================================================
    def analyze_query(self, query: str, context: dict[str, Any] | None = None) -> SlotExtractionResult:
        context = context or {}
        q_lower = query.lower()

        # Check intent
        has_policy_kw = any(w in q_lower for w in ["quy chế", "quy định", "tiêu chuẩn", "hạng", "kim cương", "điều khoản", "p154", "p05", "p23"])
        has_driver_kw = any(w in q_lower for w in ["tôi", "tài xế", "chuyến", "hủy", "huỷ", "doanh thu", "đánh giá", "sao", "sự cố", "hỏng xe", "ar", "cr"])
        has_calc_kw = any(w in q_lower for w in ["tỷ lệ hủy", "tỷ lệ huỷ", "tỷ lệ nhận", "cancel_rate", "tính toán", "bao nhiêu %"])

        intent = "HYBRID_REASONING"
        if has_policy_kw and not has_driver_kw:
            intent = "POLICY_LOOKUP"
        elif has_driver_kw and not has_policy_kw:
            intent = "DRIVER_HISTORY"

        needs_driver = has_driver_kw or ("tôi" in q_lower) or intent in {"DRIVER_HISTORY", "HYBRID_REASONING"}
        needs_time = True

        # Extract driver
        driver_id = context.get("driver_id")
        driver_mention = context.get("driver_mention")
        is_ambiguous = False

        if not driver_id:
            # Check UUID
            uuid_match = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", query, re.IGNORECASE)
            if uuid_match:
                driver_id = uuid_match.group(0).lower()
                driver_mention = driver_id

            # Check DRV-xxx / D1..D8
            if not driver_id:
                code_match = re.search(r"\b(DRV-\d{3}|D[1-8])\b", query, re.IGNORECASE)
                if code_match:
                    code_val = code_match.group(0).upper()
                    driver_id = DRIVER_CODE_MAP.get(code_val)
                    driver_mention = code_val

            # Check Name (An, Bình, Chi, Dũng, Minh, Giang, Hà)
            if not driver_id:
                for name_key, d_id in DRIVER_NAME_MAP.items():
                    if re.search(rf"\b{name_key}\b", q_lower):
                        driver_mention = name_key.capitalize()
                        if d_id is None:
                            is_ambiguous = True
                            driver_id = None
                        else:
                            driver_id = d_id
                        break

        # Extract time / snapshot
        time_mention = context.get("time_mention")
        snapshot_id = context.get("snapshot_id")

        time_kws = ["tháng 9", "tháng 8", "tuần trước", "30 ngày", "hôm qua", "gần nhất", "kỳ này", "2026-09", "2026-08"]
        for t_kw in time_kws:
            if t_kw in q_lower:
                time_mention = t_kw
                break

        # Check explicit snapshot mention
        snap_match = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", query, re.IGNORECASE)
        if snap_match and snap_match.group(0).lower() != driver_id:
            snapshot_id = snap_match.group(0).lower()
            time_mention = f"Snapshot {snapshot_id[:8]}"

        if not snapshot_id:
            snapshot_id = self.default_snapshot_id

        has_time_scope = bool(time_mention or context.get("has_time_scope"))

        # Extract policies mentioned
        policy_mentions = re.findall(r"\b(P\d{2,3})\b", query, re.IGNORECASE)

        missing_slots: list[str] = []
        if needs_driver and (not driver_id or is_ambiguous):
            missing_slots.append("driver_id")
        if needs_time and not has_time_scope:
            missing_slots.append("time_scope")

        return SlotExtractionResult(
            intent=intent,
            needs_driver=needs_driver,
            driver_id=driver_id,
            driver_mention=driver_mention,
            is_driver_ambiguous=is_ambiguous,
            needs_time=needs_time,
            has_time_scope=has_time_scope,
            time_mention=time_mention,
            snapshot_id=snapshot_id,
            policy_mentions=policy_mentions,
            missing_slots=missing_slots,
        )

    # =========================================================================
    # Step 2: Clarification Message Generator
    # =========================================================================
    def build_clarification_message(self, slots: SlotExtractionResult) -> str:
        items: list[str] = []
        if "driver_id" in slots.missing_slots:
            if slots.is_driver_ambiguous:
                items.append(
                    f"⚠️ Trong hệ thống có 2 tài xế cùng tên '{slots.driver_mention}' (DRV-005 và DRV-006). "
                    "Vui lòng chỉ rõ mã tài xế (ví dụ: DRV-005 hoặc DRV-006)."
                )
            else:
                items.append(
                    "👤 Bạn đang tra cứu cho **Tài xế nào**? Vui lòng cung cấp Mã tài xế (ví dụ: DRV-001, D1, D2...) hoặc Tên tài xế cụ thể."
                )
        if "time_scope" in slots.missing_slots:
            items.append(
                "📅 Bạn muốn kiểm tra tại **Mốc thời gian nào** (ví dụ: tháng 9/2026, 30 ngày gần nhất, hoặc kỳ đánh giá tuần trước)?"
            )

        msg = "Để có câu trả lời chính xác và dẫn chứng đúng quy chế GSM, hệ thống cần bạn làm rõ thêm các thông tin sau:\n"
        for i, item in enumerate(items, 1):
            msg += f"{i}. {item}\n"
        return msg.strip()

    # =========================================================================
    # Step 3: Subgraph Expansion (BFS 1-hop / 2-hop)
    # =========================================================================
    def expand_subgraph_bfs(self, driver_id: str, snapshot_id: str) -> Subgraph:
        subgraph = Subgraph(seed_id=driver_id, snapshot_id=snapshot_id)

        if self.neo4j_driver:
            # Live BFS on Neo4j Operational KG
            with self.neo4j_driver.session() as session:
                # Hop 1: Driver -> Direct Neighbors in snapshot
                cypher = """
                MATCH (d:GSMOperationalV1:Driver {id: $driver_id})-[r]->(m:GSMOperationalV1)
                WHERE r.snapshot_id = $snapshot_id
                RETURN d.id AS driver_id, d.name AS driver_name,
                       type(r) AS rel_type, properties(r) AS rel_props,
                       labels(m) AS m_labels, m.id AS m_id, m.name AS m_name, properties(m) AS m_props
                """
                records = session.run(cypher, driver_id=driver_id, snapshot_id=snapshot_id).data()

                # Add Driver Seed Node
                driver_name = records[0]["driver_name"] if records else f"Driver {driver_id[:8]}"
                subgraph.nodes.append(
                    SubgraphNode(id=driver_id, label="Driver", name=driver_name, props={"id": driver_id})
                )

                seen_nodes = {driver_id}
                trip_ids: list[str] = []

                for row in records:
                    m_id = row["m_id"]
                    m_label = [l for l in row["m_labels"] if l != "GSMOperationalV1"][0]
                    if m_id not in seen_nodes:
                        seen_nodes.add(m_id)
                        subgraph.nodes.append(
                            SubgraphNode(id=m_id, label=m_label, name=row["m_name"], props=row["m_props"])
                        )
                    subgraph.edges.append(
                        SubgraphEdge(
                            start_id=driver_id,
                            end_id=m_id,
                            rel_type=row["rel_type"],
                            props=row["rel_props"],
                        )
                    )
                    if m_label == "Trip":
                        trip_ids.append(m_id)

                # Hop 2: Trip -> Service & Region
                if trip_ids:
                    cypher_hop2 = """
                    MATCH (t:GSMOperationalV1:Trip)-[r2]->(meta:GSMOperationalV1)
                    WHERE t.id IN $trip_ids AND r2.snapshot_id = $snapshot_id
                    RETURN t.id AS trip_id, type(r2) AS rel_type, properties(r2) AS rel_props,
                           labels(meta) AS meta_labels, meta.id AS meta_id, meta.name AS meta_name, properties(meta) AS meta_props
                    """
                    hop2_records = session.run(cypher_hop2, trip_ids=trip_ids[:10], snapshot_id=snapshot_id).data()
                    for row in hop2_records:
                        meta_id = row["meta_id"]
                        meta_label = [l for l in row["meta_labels"] if l != "GSMOperationalV1"][0]
                        if meta_id not in seen_nodes:
                            seen_nodes.add(meta_id)
                            subgraph.nodes.append(
                                SubgraphNode(id=meta_id, label=meta_label, name=row["meta_name"], props=row["meta_props"])
                            )
                        subgraph.edges.append(
                            SubgraphEdge(
                                start_id=row["trip_id"],
                                end_id=meta_id,
                                rel_type=row["rel_type"],
                                props=row["rel_props"],
                            )
                        )
        else:
            # Fallback to local snapshot jsonl files
            snap_file = self.release_dir / "public" / "snapshots" / snapshot_id / "text_observations.jsonl"
            if snap_file.exists():
                lines = [json.loads(l) for l in snap_file.read_text("utf-8").splitlines() if l.strip()]
                subgraph.nodes.append(SubgraphNode(id=driver_id, label="Driver", name=f"Driver {driver_id[:8]}", props={"id": driver_id}))
                for row in lines:
                    if row.get("subject_id") == driver_id:
                        assertion = row
                        obj = assertion.get("object", {})
                        val = obj.get("string_value") or obj.get("entity_ref") or "val"
                        target_id = f"obs-{assertion.get('assertion_id', '')[:8]}"
                        subgraph.nodes.append(SubgraphNode(id=target_id, label="Fact", name=str(val), props=assertion))
                        subgraph.edges.append(SubgraphEdge(start_id=driver_id, end_id=target_id, rel_type=assertion.get("predicate", "FACT"), props={"evidence_ref": assertion.get("assertion_id")}))

        return subgraph

    # =========================================================================
    # Step 4: Multi-Source Evidence Gathering
    # =========================================================================
    def gather_multi_source_evidence(
        self, query: str, slots: SlotExtractionResult, subgraph: Subgraph
    ) -> list[dict[str, Any]]:
        evidence_list: list[dict[str, Any]] = []

        # 1. Document Evidence from BM25
        chunk_map = {c.chunk_id: c for c in self.chunks}
        doc_matches = self.bm25_index.search(query, top_k=3)
        for ranked in doc_matches:
            chunk = chunk_map.get(ranked.chunk_id)
            if not chunk:
                continue
            evidence_list.append({
                "source_kind": "document",
                "evidence_id": f"doc-{chunk.chunk_id}",
                "citation_locator": f"{chunk.document_revision_id}#{','.join(chunk.clause_ids) if chunk.clause_ids else 'clause'}",
                "content": f"[Quy chế {chunk.document_revision_id}] {chunk.text}",
                "score": float(ranked.score),
            })

        # 2. KG Subgraph Facts
        trips = [n for n in subgraph.nodes if n.label == "Trip"]
        measurements = [n for n in subgraph.nodes if n.label == "Measurement"]
        incidents = [n for n in subgraph.nodes if n.label == "Incident"]

        # Summarize trips from subgraph
        completed_trips = sum(1 for t in trips if t.props.get("outcome") == "completed")
        cancelled_trips = sum(1 for t in trips if t.props.get("outcome") == "cancelled")
        trip_summary = (
            f"Tài xế có tổng cộng {len(trips)} chuyến đi được ghi nhận: "
            f"{completed_trips} chuyến hoàn thành, {cancelled_trips} chuyến bị hủy."
        )
        if cancelled_trips > 0:
            cancelled_details = [
                f"chuyến {t.id[:8]} (lý do: {t.props.get('reason_code', 'không rõ')})"
                for t in trips if t.props.get("outcome") == "cancelled"
            ]
            trip_summary += f" Chi tiết hủy: {', '.join(cancelled_details)}."

        evidence_list.append({
            "source_kind": "kg_subgraph",
            "evidence_id": f"kg-trips-{slots.driver_id[:8]}",
            "citation_locator": f"ledger:driver_trips:{slots.driver_id[:8]}",
            "content": f"[Lịch sử chuyến đi từ đồ thị] {trip_summary}",
        })

        for m in measurements:
            def_id = m.props.get("definition_id", "chỉ_số")
            val = m.props.get("value", "")
            w_start = m.props.get("window_start", "")[:10]
            w_end = m.props.get("window_end", "")[:10]
            evidence_list.append({
                "source_kind": "kg_subgraph",
                "evidence_id": f"kg-meas-{m.id[:8]}",
                "citation_locator": f"assertion:{m.id}",
                "content": f"[Báo cáo vận hành] {def_id} = {val} trong kỳ [{w_start} đến {w_end}].",
            })

        # 3. Exact Rational Computation (cancel_rate_30d)
        if len(trips) > 0 and any(w in query.lower() for w in ["tỷ lệ hủy", "tỷ lệ huỷ", "cancel_rate", "phạt"]):
            # Calculate cancel rate: cancelled / total trips
            total_count = len(trips)
            cancelled_count = cancelled_trips
            rate_frac = Fraction(cancelled_count, total_count)
            rate_pct = float(cancelled_count) / float(total_count) * 100.0

            evidence_list.append({
                "source_kind": "computation",
                "evidence_id": f"calc-cancel-rate-{slots.driver_id[:8]}",
                "citation_locator": "computation:cancel_rate_30d",
                "content": (
                    f"[Tính toán số học chuẩn xác] Tỷ lệ hủy chuyến 30 ngày (cancel_rate_30d) = "
                    f"{rate_frac} ({cancelled_count}/{total_count} chuyến) = {rate_pct:.2f}%."
                ),
            })

        return evidence_list

    # =========================================================================
    # Step 5: Grounded LLM Reader Generation
    # =========================================================================
    def generate_grounded_answer(
        self, query: str, slots: SlotExtractionResult, evidence: list[dict[str, Any]]
    ) -> tuple[str, list[dict[str, str]]]:
        evidence_context = "\n".join([f"- [{e['citation_locator']}] {e['content']}" for e in evidence])

        system_prompt = (
            "Bạn là AI Chuyên viên Pháp chế và Vận hành của GSM (Taxi Xanh SM).\n"
            "Nhiệm vụ của bạn là trả lời câu hỏi của Bác Tài dựa HOÀN TOÀN và CHẶT CHẼ trên bằng chứng được cung cấp.\n"
            "NGUYÊN TẮC BẮT BUỘC:\n"
            "1. Chỉ trả lời dựa trên bằng chứng dưới đây. Tuyệt đối không bịa đặt hoặc suy diễn ngoài bằng chứng.\n"
            "2. Trích dẫn nguồn cụ thể trong câu trả lời (ví dụ: [P154#Điều khoản] hoặc [Mã chuyến đi]).\n"
            "3. Nếu là phép tính số học, hãy dẫn chứng phân số và phần trăm chính xác.\n"
            "4. Giọng điệu chuyên nghiệp, lịch sự, ân cần hỗ trợ Bác Tài.\n"
            "5. BẮT BUỘC: Trả lời trực tiếp vào nội dung bằng tiếng Việt. KHÔNG xuất ra quá trình suy nghĩ (No chain-of-thought / No thinking process)."
        )

        user_prompt = (
            f"CÂU HỎI CỦA BÁC TÀI: {query}\n\n"
            f"BẰNG CHỨNG THỰC TẾ ĐÃ THU THẬP TỪ ĐỒ THỊ VÀ QUY CHẾ GSM:\n"
            f"{evidence_context}\n\n"
            "Hãy trả lời câu hỏi trực tiếp và trích dẫn nguồn cụ thể cho Bác Tài:"
        )

        from openai import OpenAI

        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.openrouter_api_key)
        models_to_try = [self.model_name]
        if ":free" not in self.model_name:
            models_to_try.append("nvidia/nemotron-3.5-lightning:free")

        raw_answer = ""
        last_error = None
        for m in models_to_try:
            try:
                response = client.chat.completions.create(
                    model=m,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=600,
                    temperature=0.1,
                )
                raw_answer = response.choices[0].message.content or ""
                if raw_answer:
                    break
            except Exception as e:
                last_error = e
                continue

        # Clean thinking trace if returned by model
        if "<think>" in raw_answer and "</think>" in raw_answer:
            raw_answer = re.sub(r"<think>.*?</think>", "", raw_answer, flags=re.DOTALL).strip()
        elif "Here's a thinking process:" in raw_answer or "Here is a thinking process:" in raw_answer:
            match = re.search(r"(?:###\s*(?:Câu trả lời|Phản hồi|Kết luận)|Chào Bác Tài|Chào bạn|Thưa Bác Tài|Dựa trên|Theo quy chế)(.*)", raw_answer, re.DOTALL | re.IGNORECASE)
            if match:
                raw_answer = match.group(0).strip()

        if not raw_answer:
            raw_answer = (
                f"Đã thu thập {len(evidence)} bằng chứng hợp lệ từ Đồ thị và Quy chế. "
                f"Tuy nhiên gặp lỗi khi kết nối mô hình LLM ({last_error}). Bằng chứng gồm: {evidence[0]['content']}"
            )

        citations = [
            {"locator": e["citation_locator"], "content": e["content"][:120]}
            for e in evidence
        ]
        return raw_answer, citations

    # =========================================================================
    # Main Entry Point with Langfuse Tracing
    # =========================================================================
    def execute(self, user_query: str, context: dict[str, Any] | None = None) -> PipelineResponse:
        context = context or {}
        trace_url = None

        if self.langfuse:
            try:
                with self.langfuse.start_as_current_observation(
                    name="gsm-conversational-qa-pipeline",
                    as_type="span",
                    input={"query": user_query, "context": context},
                    metadata={"release": "gsm-dev-core-0.2.2", "model": self.model_name},
                ) as root_span:
                    trace_url = self.langfuse.get_trace_url()

                    # Span 1: Query Understanding
                    with root_span.start_as_current_observation(
                        name="1. Query Understanding & Slot Filling",
                        as_type="span",
                        input={"query": user_query},
                    ) as q_span:
                        slots = self.analyze_query(user_query, context)
                        q_span.update(
                            output={
                                "intent": slots.intent,
                                "driver_id": slots.driver_id,
                                "driver_mention": slots.driver_mention,
                                "time_mention": slots.time_mention,
                                "snapshot_id": slots.snapshot_id,
                                "missing_slots": slots.missing_slots,
                            }
                        )

                    # Span 2: Clarification Gate
                    with root_span.start_as_current_observation(
                        name="2. Clarification Gate",
                        as_type="span",
                        input={"missing_slots": slots.missing_slots},
                    ) as gate_span:
                        if slots.missing_slots:
                            clarification_msg = self.build_clarification_message(slots)
                            gate_span.update(output={"action": "ASK_CLARIFICATION", "message": clarification_msg})
                            root_span.update(output={"status": "NEEDS_CLARIFICATION", "message": clarification_msg})
                            return PipelineResponse(
                                status="NEEDS_CLARIFICATION",
                                query=user_query,
                                slots=slots,
                                clarification_message=clarification_msg,
                                trace_url=trace_url,
                            )
                        gate_span.update(output={"action": "PASSED", "message": "All required slots present."})

                    # Span 3: Seed Selection & Subgraph BFS Expansion
                    with root_span.start_as_current_observation(
                        name="3. Seed Selection & Subgraph BFS Expansion",
                        as_type="span",
                        input={"seed_id": slots.driver_id, "snapshot_id": slots.snapshot_id},
                    ) as kg_span:
                        subgraph = self.expand_subgraph_bfs(slots.driver_id, slots.snapshot_id)
                        kg_span.update(
                            output={
                                "seed_id": subgraph.seed_id,
                                "node_count": len(subgraph.nodes),
                                "edge_count": len(subgraph.edges),
                                "node_types": [n.label for n in subgraph.nodes],
                            }
                        )

                    # Span 4: Multi-Source Evidence Gathering
                    with root_span.start_as_current_observation(
                        name="4. Multi-Source Evidence Gathering",
                        as_type="span",
                        input={"intent": slots.intent, "query": user_query},
                    ) as ev_span:
                        evidence = self.gather_multi_source_evidence(user_query, slots, subgraph)
                        ev_span.update(
                            output={
                                "evidence_count": len(evidence),
                                "sources": [e["source_kind"] for e in evidence],
                                "locators": [e["citation_locator"] for e in evidence],
                            }
                        )

                    # Generation 5: Grounded LLM Reader
                    with root_span.start_as_current_observation(
                        name="5. Grounded LLM Reader Synthesis",
                        as_type="generation",
                        model=self.model_name,
                        input={"query": user_query, "evidence_count": len(evidence)},
                    ) as gen_span:
                        answer, citations = self.generate_grounded_answer(user_query, slots, evidence)
                        gen_span.update(output={"answer": answer, "citations": citations})

                    root_span.update(output={"status": "ANSWERED", "answer": answer, "citations_count": len(citations)})

                    return PipelineResponse(
                        status="ANSWERED",
                        query=user_query,
                        slots=slots,
                        answer=answer,
                        citations=citations,
                        subgraph=subgraph,
                        trace_url=trace_url,
                    )
            except Exception as e:
                print(f"[Pipeline Langfuse Error] {e}, falling back to non-traced execution.")
        else:
            # Fallback without Langfuse
            slots = self.analyze_query(user_query, context)
            if slots.missing_slots:
                clarification_msg = self.build_clarification_message(slots)
                return PipelineResponse(
                    status="NEEDS_CLARIFICATION",
                    query=user_query,
                    slots=slots,
                    clarification_message=clarification_msg,
                )
            subgraph = self.expand_subgraph_bfs(slots.driver_id, slots.snapshot_id)
            evidence = self.gather_multi_source_evidence(user_query, slots, subgraph)
            answer, citations = self.generate_grounded_answer(user_query, slots, evidence)
            return PipelineResponse(
                status="ANSWERED",
                query=user_query,
                slots=slots,
                answer=answer,
                citations=citations,
                subgraph=subgraph,
            )
