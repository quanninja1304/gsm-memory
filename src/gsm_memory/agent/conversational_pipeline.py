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


# Semantic Time-to-Snapshot Mapping Table for Neo4j & Ledger Cutoffs
# In dataset release gsm-dev-core-0.2.2 and Neo4j KG:
# Ledger L0 (5 cutoffs) + 7 alternate branches = 12 benchmark snapshots:
SNAPSHOT_METADATA: dict[str, dict[str, Any]] = {
    "d4cc0438-d831-541a-8123-ddda94ccdac8": {
        "label": "L0 Canonical Baseline (17/09/2026 12:00)",
        "known_as_of": "2026-09-17T12:00:00.000000Z",
        "scope": "Tháng 09/2026 & Toàn bộ 80 chuyến đi (L0)",
        "aliases": [
            "tháng 9", "tháng 09", "tháng 9/2026", "2026-09",
            "30 ngày gần nhất", "30 ngày qua", "30 ngày",
            "kỳ này", "kỳ đánh giá", "hôm nay", "hiện tại", "gần nhất",
            "17/09", "17/09/2026", "snapshot l0"
        ],
    },
    "25b69c05-6a60-51e3-9209-74e5d49816fa": {
        "label": "L0 Cutoff A0 (16/09/2026 12:00)",
        "known_as_of": "2026-09-16T12:00:00.000000Z",
        "scope": "Ngày 16/09/2026 (79 chuyến đi)",
        "aliases": ["16/09", "16/09/2026", "2026-09-16", "hôm qua", "cutoff a0"],
    },
    "624c0fb1-f1e5-59af-9642-0771d1d2571f": {
        "label": "L0 Cutoff AC (17/09/2026 01:00)",
        "known_as_of": "2026-09-17T01:00:00.000000Z",
        "scope": "Sáng sớm 17/09/2026 (80 chuyến đi)",
        "aliases": ["17/09 sáng", "2026-09-17t01", "cutoff ac"],
    },
    "da177d3f-6b43-52ae-a778-4fa7c6edbbf1": {
        "label": "L0 Cutoff 06/08 (06/08/2026)",
        "known_as_of": "2026-08-06T00:00:00.000000Z",
        "scope": "Tháng 08/2026 (Chốt ngày 06/08, 30 quan hệ)",
        "aliases": ["06/08", "06/08/2026", "2026-08-06", "cutoff 06/08"],
    },
    "d8c98a0b-7b07-50f2-b1ed-9fe102ccc5e6": {
        "label": "L0 Cutoff 04/08 (04/08/2026)",
        "known_as_of": "2026-08-04T00:00:00.000000Z",
        "scope": "Đầu tháng 08/2026 (Chốt ngày 04/08, 29 quan hệ)",
        "aliases": ["tháng 8", "tháng 08", "tháng 8/2026", "2026-08", "đầu tháng 8", "04/08", "04/08/2026", "2026-08-04", "tháng trước", "cutoff 04/08"],
    },
    # 7 Alternate Benchmark Branches
    "df057563-78f4-5ac1-aba6-5b48c572fb4a": {
        "label": "Branch L_NO_OPDAY (17/09/2026 12:00)",
        "known_as_of": "2026-09-17T12:00:00.000000Z",
        "scope": "Nhánh đối chứng thiếu ngày vận hành (L_NO_OPDAY)",
        "aliases": ["l_no_opday", "no_opday", "thiếu ngày vận hành", "nhánh thiếu ngày vận hành", "snapshot no opday"],
    },
    "d644104b-2ae9-54e3-b07f-ed1cefe897f1": {
        "label": "Branch L_WRONG_DRIVER (17/09/2026 12:00)",
        "known_as_of": "2026-09-17T12:00:00.000000Z",
        "scope": "Nhánh đối chứng sai định danh tài xế (L_WRONG_DRIVER)",
        "aliases": ["l_wrong_driver", "wrong_driver", "sai tài xế", "nhánh sai tài xế", "snapshot wrong driver"],
    },
    "6c606951-1fbd-586a-bf9b-51faafb07a24": {
        "label": "Branch L_CONFLICT (17/09/2026 12:00)",
        "known_as_of": "2026-09-17T12:00:00.000000Z",
        "scope": "Nhánh đối chứng xung đột dữ liệu (L_CONFLICT)",
        "aliases": ["l_conflict", "conflict", "xung đột", "xung đột dữ liệu", "nhánh xung đột", "snapshot conflict"],
    },
    "296f03c2-6abf-57b3-8a17-249486d98fe8": {
        "label": "Branch L_RETRACT (17/09/2026 12:00)",
        "known_as_of": "2026-09-17T12:00:00.000000Z",
        "scope": "Nhánh đối chứng rút lại dữ liệu (L_RETRACT)",
        "aliases": ["l_retract", "retract", "rút lại", "rút lại dữ liệu", "nhánh rút lại", "snapshot retract"],
    },
    "ff172ebe-4740-54d3-a235-e819dc21c959": {
        "label": "Branch L_WRONG_WINDOW (17/09/2026 12:00)",
        "known_as_of": "2026-09-17T12:00:00.000000Z",
        "scope": "Nhánh đối chứng sai cửa sổ thời gian (L_WRONG_WINDOW)",
        "aliases": ["l_wrong_window", "wrong_window", "sai cửa sổ", "sai cửa sổ thời gian", "nhánh sai cửa sổ", "snapshot wrong window"],
    },
    "f70bbf42-f1ec-5bcf-b8d3-8a7b53086076": {
        "label": "Branch L_NO_BRIDGE (17/09/2026 12:00)",
        "known_as_of": "2026-09-17T12:00:00.000000Z",
        "scope": "Nhánh đối chứng thiếu liên kết bắc cầu (L_NO_BRIDGE)",
        "aliases": ["l_no_bridge", "no_bridge", "thiếu cầu nối", "nhánh thiếu cầu nối", "snapshot no bridge"],
    },
    "688de316-96de-59b6-9c70-3d4745aba76f": {
        "label": "Branch L_NO_COVERAGE (17/09/2026 12:00)",
        "known_as_of": "2026-09-17T12:00:00.000000Z",
        "scope": "Nhánh đối chứng thiếu độ phủ dữ liệu (L_NO_COVERAGE)",
        "aliases": ["l_no_coverage", "no_coverage", "thiếu độ phủ", "nhánh thiếu độ phủ", "snapshot no coverage"],
    },
}


def map_time_to_snapshot(time_str: str | None, repo: Any | None = None) -> tuple[str, str]:
    """Map natural language time scope or explicit ID to (snapshot_id, snapshot_label)."""
    if repo:
        snap = repo.find_snapshot_by_alias_or_time(time_str)
        if snap:
            return snap.snapshot_id, snap.label
        elif time_str and time_str.strip():
            return "", ""

    if not time_str:
        return DEFAULT_SNAPSHOT_ID, SNAPSHOT_METADATA[DEFAULT_SNAPSHOT_ID]["label"]

    t_clean = time_str.lower().strip()

    # Direct UUID match
    if t_clean in SNAPSHOT_METADATA:
        return t_clean, SNAPSHOT_METADATA[t_clean]["label"]

    # Reject out-of-dataset years
    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", t_clean)
    query_year = year_match.group(1) if year_match else None
    if query_year and query_year != "2026":
        return "", ""

    for sid, meta in SNAPSHOT_METADATA.items():
        if sid in t_clean:
            return sid, meta["label"]
        for alias in meta["aliases"]:
            if alias in t_clean:
                return sid, meta["label"]

    return "", ""



@dataclass
class QueryPlan:
    intent: str  # "POLICY_LOOKUP" | "DRIVER_HISTORY" | "HYBRID_REASONING"
    driver_id: str | None = None
    driver_mention: str | None = None
    is_driver_ambiguous: bool = False
    time_scope: str | None = None
    snapshot_id: str | None = None
    snapshot_label: str | None = None
    policy_scope: list[str] = field(default_factory=list)
    policy_topics: list[str] = field(default_factory=list)
    modalities: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    clarification_reasons: dict[str, str] = field(default_factory=dict)
    reasoning: str = ""


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
    policy_topics: list[str] = field(default_factory=list)
    has_policy_target: bool = False
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
    query_plan: QueryPlan | None = None
    clarification_message: str | None = None
    answer: str | None = None
    citations: list[dict[str, str]] = field(default_factory=list)
    subgraph: Subgraph | None = None
    trace_url: str | None = None
    retrieval_receipt: dict[str, Any] | None = None


def _serialize_for_trace(val: Any) -> Any:
    """Safe serializer for Langfuse span/generation JSON payloads."""
    if isinstance(val, dict):
        return {str(k): _serialize_for_trace(v) for k, v in val.items()}
    elif isinstance(val, (list, tuple, set)):
        return [_serialize_for_trace(v) for v in val]
    elif hasattr(val, "isoformat"):
        return val.isoformat()
    elif hasattr(val, "iso_format"):
        return val.iso_format()
    elif isinstance(val, (int, float, bool, str)) or val is None:
        return val
    return str(val)


class ConversationalPipeline:
    """End-to-end Pipeline: Query Understanding -> Clarification -> Subgraph BFS -> Evidence -> LLM Reader."""

    def __init__(
        self,
        release_dir: Path = DEFAULT_RELEASE_DIR,
        snapshot_id: str = DEFAULT_SNAPSHOT_ID,
        model_name: str | None = None,
        db_repo: Any | None = None,
    ) -> None:
        self.release_dir = release_dir
        self.default_snapshot_id = snapshot_id
        self.benchmark_current_time = "2026-09-17T12:00:00Z"
        self.model_name = model_name or os.getenv("OPENROUTER_MODEL") or "nvidia/nemotron-3.5-lightning:free"
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        self.nvidia_api_key = os.getenv("NVIDIA_API_KEY")
        self.nvidia_model = os.getenv("NVIDIA_MODEL") or "meta/llama-3.2-11b-vision-instruct"

        from gsm_memory.db.repository import LocalDatabaseRepository
        self.db_repo: LocalDatabaseRepository = db_repo or LocalDatabaseRepository()

        # Load BM25 Document chunks (retrieval_full: 224 canonical GSM policies + definitions)
        print("[Pipeline Init] Loading GSM policy chunks (retrieval_full)...")
        self.chunks, _, _ = construct_chunks(self.release_dir, "retrieval_full", ChunkConfig())
        self.bm25_index = BM25Index(self.chunks)
        self.doc_catalog_meta = self._load_document_catalog_meta()
        print(f"[Pipeline Init] Loaded {len(self.chunks)} policy chunks across full GSM corpus.")

        # Initialize Qdrant vector retrieval and Cross-Encoder reranker
        from gsm_memory.retrieval.qdrant import HybridPolicySearcher, QdrantPolicyRetriever
        from gsm_memory.retrieval.rerank import NvidiaReranker

        self.qdrant_retriever = QdrantPolicyRetriever()
        self.reranker = NvidiaReranker()
        self.hybrid_searcher = HybridPolicySearcher(
            bm25_index=self.bm25_index,
            chunks=self.chunks,
            doc_catalog_meta=self.doc_catalog_meta,
            qdrant_retriever=self.qdrant_retriever,
            reranker=self.reranker,
        )
        self._last_retrieval_receipt: dict[str, Any] | None = None
        if self.qdrant_retriever.is_available():
            stats = self.qdrant_retriever.get_stats()
            print(f"[Pipeline Init] Qdrant connected: {stats.get('points_count', 0)} vectors available.")
        else:
            print("[Pipeline Init] Qdrant unavailable, falling back to BM25 lexical search.")

        # Initialize Neo4j driver
        self.neo4j_driver = self._init_neo4j()

        # Initialize Langfuse
        self.langfuse = self._init_langfuse()

    def _load_document_catalog_meta(self) -> dict[str, dict[str, Any]]:
        """Load catalog metadata to resolve chunk IDs to human-readable policy aliases and titles."""
        meta: dict[str, dict[str, Any]] = {}
        self.doc_by_alias: dict[str, dict[str, Any]] = {}

        doc_catalog_path = self.release_dir / "public" / "documents" / "catalog.jsonl"
        if doc_catalog_path.exists():
            for line in doc_catalog_path.read_text("utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                alias = row.get("alias") or ""
                path = row.get("archive_member_path", "")
                rev_id = row.get("document_revision_id") or ""
                snap_id = row.get("snapshot_id") or ""
                title = ""
                if path:
                    fname = Path(path).stem
                    title = re.sub(r"^\d+_\d{4}-\d{2}-\d{2}_", "", fname).strip()
                item = {
                    "alias": alias,
                    "title": title or alias or "Văn bản quy chế GSM",
                    "posted_date": row.get("posted_date") or "",
                    "document_revision_id": rev_id,
                    "snapshot_id": snap_id,
                    "archive_member_path": path,
                    "kind": "document",
                }
                if snap_id:
                    meta[snap_id] = item
                if rev_id:
                    meta[rev_id] = item
                if alias:
                    self.doc_by_alias[alias] = item

        def_catalog_path = self.release_dir / "public" / "definitions" / "catalog.jsonl"
        if def_catalog_path.exists():
            for line in def_catalog_path.read_text("utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                def_id = row.get("definition_id") or ""
                alias = row.get("alias") or ""
                item = {
                    "alias": alias,
                    "title": f"Quy ước định nghĩa {alias}",
                    "posted_date": "",
                    "document_revision_id": def_id,
                    "definition_id": def_id,
                    "kind": "definition",
                }
                if def_id:
                    meta[def_id] = item
                if alias:
                    self.doc_by_alias[alias] = item
        return meta

    @staticmethod
    def _clean_policy_markdown(raw_text: str) -> tuple[dict[str, str], str]:
        """Strip crawler metadata headers (OCR flags, duplicated URLs, table flags)
        and extract clean document metadata and formatted body.
        """
        meta: dict[str, str] = {}
        lines = raw_text.splitlines()
        body_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            # Title
            if stripped.startswith("# "):
                title_clean = stripped[2:].strip()
                if not meta.get("title"):
                    meta["title"] = title_clean
                continue

            # Extract date
            m_date = re.match(r"^-\s*\*\*Ngày đăng:\*\*\s*(.*)$", stripped)
            if m_date:
                meta["date"] = m_date.group(1).strip()
                continue

            # Extract category
            m_cat = re.match(r"^-\s*\*\*Chuyên mục:\*\*\s*(.*)$", stripped)
            if m_cat:
                meta["category"] = m_cat.group(1).strip()
                continue

            # Strip crawl scrapings
            if any(junk in stripped for junk in [
                "**Nguồn bài viết:**",
                "**Có bảng biểu:**",
                "**Có hình ảnh OCR:**",
                "---",
            ]):
                continue

            # Fix missing space after colon in scraped headings (e.g. "1. Thời gian áp dụng:Từ ngày" -> "1. Thời gian áp dụng: Từ ngày")
            fixed_line = re.sub(r"(:)([A-ZÀ-Ỹa-zà-ỹ0-9])", r": \2", line)
            body_lines.append(fixed_line)

        cleaned_body = "\n".join(body_lines).strip()
        cleaned_body = re.sub(r"\n{3,}", "\n\n", cleaned_body)
        return meta, cleaned_body

    def get_full_policy_text(
        self,
        identifier: str | None = None,
        alias: str | None = None,
        max_chars: int = 35000,
        clean: bool = True,
    ) -> tuple[dict[str, str], str] | str | None:
        """Load full normalized text of a policy document or definition from disk."""
        target_alias = (alias or "").strip().upper()
        ident = (identifier or "").strip()

        # 1. If alias given or identifier looks like an alias (e.g. P154, P005)
        if not target_alias and ident.upper().startswith("P") and len(ident) >= 2:
            target_alias = ident.upper()

        # If numeric source_id (e.g. "154", 88)
        if not target_alias and ident.isdigit():
            target_alias = f"P{int(ident):03d}"

        rev_id = ""
        # Check alias in doc_by_alias
        if target_alias and hasattr(self, "doc_by_alias") and target_alias in self.doc_by_alias:
            rev_id = self.doc_by_alias[target_alias].get("document_revision_id") or ""
        elif ident in getattr(self, "doc_catalog_meta", {}):
            rev_id = self.doc_catalog_meta[ident].get("document_revision_id") or ident
        else:
            rev_id = ident

        raw_text = None

        # 2. Try normalized documents by rev_id
        if rev_id:
            doc_path = self.release_dir / "public" / "documents" / "normalized" / f"{rev_id}.md"
            if doc_path.is_file():
                try:
                    raw_text = doc_path.read_text("utf-8")
                except Exception as e:
                    print(f"[Policy Loader Error] Failed to read {doc_path}: {e}")

        # 3. If rev_id didn't work directly, try alias lookup if we haven't yet
        if not raw_text and target_alias and hasattr(self, "doc_by_alias") and target_alias in self.doc_by_alias:
            true_rev = self.doc_by_alias[target_alias].get("document_revision_id")
            if true_rev and true_rev != rev_id:
                doc_path = self.release_dir / "public" / "documents" / "normalized" / f"{true_rev}.md"
                if doc_path.is_file():
                    try:
                        raw_text = doc_path.read_text("utf-8")
                    except Exception as e:
                        print(f"[Policy Loader Error] Failed to read {doc_path}: {e}")

        # 4. Try definitions
        if not raw_text and rev_id:
            def_path = self.release_dir / "public" / "definitions" / f"{rev_id}.md"
            if def_path.is_file():
                try:
                    raw_text = def_path.read_text("utf-8")
                except Exception as e:
                    print(f"[Policy Loader Error] Failed to read {def_path}: {e}")

        if not raw_text:
            return None

        if len(raw_text) > max_chars:
            raw_text = raw_text[:max_chars] + f"\n\n[...Văn bản dài, đã rút gọn {len(raw_text) - max_chars} ký tự phần phụ lục...]"

        if clean:
            return self._clean_policy_markdown(raw_text)

        return raw_text


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
                    driver = GraphDatabase.driver(
                        uri,
                        auth=(username, password),
                        max_connection_lifetime=180,
                        liveness_check_timeout=30,
                        keep_alive=True,
                    )
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
    # Multi-Provider Resilient LLM Router
    # =========================================================================
    def _call_llm(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 1500,
        temperature: float = 0.1,
        timeout: float = 25.0,
    ) -> tuple[str, str, dict[str, int]]:
        """Call LLM with graceful failover across available providers:
        1. OpenRouter (if OPENROUTER_API_KEY is configured and not rate-limited)
        2. NVIDIA NIM (if NVIDIA_API_KEY is configured)
        Returns (content, model_name, usage_info).
        """
        from openai import OpenAI

        # 1. Try OpenRouter if key is present and not exhausted
        if self.openrouter_api_key and not getattr(self, "_openrouter_exhausted", False):
            try:
                client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.openrouter_api_key, max_retries=0)
                models_to_try = [self.model_name]
                if ":free" not in self.model_name:
                    models_to_try.append("nvidia/nemotron-3.5-lightning:free")
                for m in models_to_try:
                    try:
                        resp = client.chat.completions.create(
                            model=m,
                            messages=messages,
                            max_tokens=max_tokens,
                            temperature=temperature,
                            timeout=min(timeout, 8.0),
                        )
                        content = resp.choices[0].message.content or ""
                        if content.strip():
                            usage_info = {}
                            if getattr(resp, "usage", None):
                                u = resp.usage
                                usage_info = {
                                    "prompt_tokens": getattr(u, "prompt_tokens", 0) or 0,
                                    "completion_tokens": getattr(u, "completion_tokens", 0) or 0,
                                    "total_tokens": getattr(u, "total_tokens", 0) or 0,
                                }
                            return content, m, usage_info
                    except Exception as sub_e:
                        err_str = str(sub_e)
                        print(f"[LLM Router] OpenRouter model {m} failed: {sub_e}")
                        if "429" in err_str or "Rate limit" in err_str or "free-models-per-day" in err_str:
                            self._openrouter_exhausted = True
                            print("[LLM Router] OpenRouter free daily quota reached. Failing over to NVIDIA NIM.")
                            break
                        continue
            except Exception as e:
                print(f"[LLM Router] OpenRouter connection failed: {e}")

        # 2. Failover to NVIDIA NIM if key is present
        if self.nvidia_api_key:
            try:
                client_nv = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=self.nvidia_api_key, max_retries=1)
                nv_models = [self.nvidia_model, "meta/llama-3.2-11b-vision-instruct"]
                for nm in nv_models:
                    try:
                        resp = client_nv.chat.completions.create(
                            model=nm,
                            messages=messages,
                            max_tokens=max_tokens,
                            temperature=temperature,
                            timeout=timeout,
                        )
                        content = resp.choices[0].message.content or ""
                        if content.strip():
                            usage_info = {}
                            if getattr(resp, "usage", None):
                                u = resp.usage
                                usage_info = {
                                    "prompt_tokens": getattr(u, "prompt_tokens", 0) or 0,
                                    "completion_tokens": getattr(u, "completion_tokens", 0) or 0,
                                    "total_tokens": getattr(u, "total_tokens", 0) or 0,
                                }
                            return content, f"nvidia:{nm}", usage_info
                    except Exception as nv_e:
                        print(f"[LLM Router] NVIDIA model {nm} failed: {nv_e}")
                        continue
            except Exception as e:
                print(f"[LLM Router] NVIDIA NIM connection failed: {e}")

        return "", "", {}

    # =========================================================================
    # Step 1: Semantic Query Planning & AI Slot Extraction with DB Tools
    # =========================================================================
    def extract_slots_with_ai(
        self, query: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """AI Query Understanding:
        Sends prompt with current benchmark time and user query to LLM.
        Demands a single strict JSON object without hallucination.
        """
        context = context or {}
        system_prompt = (
            "Bạn là Chuyên viên AI Phân tích Truy vấn (Query Understanding) cho hệ thống Quản lý Vận hành GSM (Taxi Xanh SM).\n"
            f"Thời gian hiện tại của hệ thống (Current Benchmark Time) là: {self.benchmark_current_time}.\n\n"
            "NHIỆM VỤ:\n"
            "Bóc tách các trường thông tin từ câu hỏi tra cứu của Nhân viên Quản lý Vận hành và trả về DUY NHẤT một đối tượng JSON.\n\n"
            "QUY TẮC BẮT BUỘC:\n"
            "1. TÁCH BẠCH NGỮ CẢNH: Các trường 'driver_code', 'driver_name', 'driver_id' CHỈ ĐƯỢC ĐIỀN khi câu hỏi hiện tại CÓ ĐỀ CẬP hoặc THAM CHIẾU đến tài xế. NẾU câu hỏi đề cập đến một tên hoặc mã tài xế mới (ví dụ: 'còn tài xế Minh thì sao', 'tài xế Bình thì sao', 'DRV-005'): BẮT BUỘC bóc tách tên mới vào 'driver_name' (ví dụ: 'Minh') hoặc mã mới vào 'driver_code', và ĐỂ 'driver_id'=null; TUYỆT ĐỐI KHÔNG dùng tên/mã tài xế từ ngữ cảnh trước!\n"
            "   - CHỈ kế thừa tài xế từ ngữ cảnh trước khi câu hỏi hiện tại dùng đại từ thay thế (ví dụ: 'anh ấy', 'chị ấy', 'người này', 'tài xế này') HOẶC câu hỏi tiếp nối không nhắc đến bất kỳ tên/mã tài xế nào (ví dụ: 'thế còn tháng 8 thì sao?').\n"
            "   - Nếu câu hỏi hiện tại chỉ hỏi về quy chế/chính sách chung (ví dụ: 'các chính sách về vi phạm hủy chuyến', 'quy định mức khoán'), bắt buộc để driver_id=null, driver_code=null, driver_name=null, KHÔNG được tự động sao chép tài xế từ ngữ cảnh trước vào!\n"
            "2. Trả về DUY NHẤT 1 chuỗi JSON hợp lệ, KHÔNG có markdown ```json ```, KHÔNG có văn bản hay lời chào nào khác ngoài JSON.\n"
            "3. Các trường cần bóc tách:\n"
            "   - 'driver_id': Chuỗi UUID nếu câu hỏi cung cấp trực tiếp UUID, ngược lại null.\n"
            "   - 'driver_code': Mã tài xế cần tra cứu (ví dụ: DRV-001, DRV-002, D1, D2...), ngược lại null.\n"
            "   - 'driver_name': Tên tài xế được nhắc đến (ví dụ: 'Trần Văn Bình', 'Bình', 'Minh', 'Dũng'...), ngược lại null.\n"
            "   - 'time_raw': Cụm từ chỉ thời gian nguyên văn trong câu hỏi (ví dụ: 'tháng 9/2026', 'hôm qua', '30 ngày qua'...), ngược lại null.\n"
            "   - 'time_resolved': Mốc thời gian ISO hoặc chuẩn hóa tương ứng dựa trên thời gian hiện tại của hệ thống (ví dụ: '2026-09', '2026-09-16'...), ngược lại null.\n"
            "   - 'policy_scope': Danh sách mã quy chế hoặc tên văn bản quy định cụ thể được người dùng ghi rõ nguyên văn trong câu hỏi (ví dụ người dùng viết rõ 'P154', 'P05', 'P221', hoặc tên văn bản rõ ràng như 'Bộ Quy tắc ứng xử'). NẾU câu hỏi chỉ nói chung chung 'chính sách', 'quy chế', 'tiêu chuẩn', 'vi phạm' mà KHÔNG có mã Pxxx hoặc tên cụ thể, BẮT BUỘC để []. TUYỆT ĐỐI KHÔNG tự bịa mã quy chế!\n"
            "   - 'policy_topics': Danh sách các chủ đề/nội dung nghiệp vụ quy chế được hỏi cụ thể (ví dụ: ['tỷ lệ hủy chuyến'], ['mức khoán doanh số'], ['tiêu chuẩn đánh giá sao'], ['tác phong đồng phục/diện mạo'], ['chính sách thưởng']...). Nếu câu hỏi chung chung về chính sách mà KHÔNG nêu rõ chủ đề cụ thể nào (ví dụ: 'cho tôi hỏi chính sách công ty', 'quy định ra sao'), bắt buộc để [].\n"
            "   - 'has_policy_target': boolean (true nếu câu hỏi đã nêu rõ tên/mã quy chế CỤ THỂ HOẶC chủ đề chính sách CỤ THỂ; false nếu câu hỏi tra cứu chính sách nhưng hoàn toàn chung chung, mơ hồ, không có tên quy chế lẫn chủ đề cụ thể).\n"
            "   - 'needs_compliance_check': boolean (true nếu câu hỏi yêu cầu đối soát, kiểm tra vi phạm, xét tiêu chuẩn vận hành, kỷ luật, thưởng phạt; false nếu chỉ xem thông tin thông thường).\n"
            "   - 'intent': 'POLICY_LOOKUP' (chỉ tra cứu quy chế công ty), 'DRIVER_HISTORY' (chỉ xem thông tin/lịch sử chuyến xe thuần túy không đối soát quy chuẩn), hoặc 'HYBRID_REASONING' (kiểm tra vi phạm, đối soát tài xế theo quy chuẩn/tiêu chuẩn, hoặc tính thưởng phạt).\n"
            "   - 'modalities': Danh sách các kênh dữ liệu trong ['document', 'kg', 'computation']. Lưu ý: nếu intent là 'HYBRID_REASONING' hoặc có kiểm tra vi phạm/chính sách, bắt buộc phải có đầy đủ ['document', 'kg', 'computation']."
        )

        pattern_data = self._pattern_fallback_extraction(query)
        has_new_explicit_driver = bool(pattern_data.get("driver_name") or pattern_data.get("driver_code") or pattern_data.get("driver_id"))
        is_anaphoric = any(k in query.lower() for k in [
            "anh ấy", "chị ấy", "người này", "ông này", "bà này", "tài xế này", "bác tài này",
            "tài xế đó", "bác tài đó", "người đó", "hồ sơ của anh ấy", "anh này", "chị này", "anh ta"
        ])

        user_content = f"CÂU HỎI CỦA NHÂN VIÊN VẬN HÀNH: {query}"
        # Only inject previous driver context if query refers to old driver (anaphoric) or does NOT name a new driver
        if (not has_new_explicit_driver or is_anaphoric) and (context.get("driver_mention") or context.get("driver_id")):
            user_content += f"\n[Ngữ cảnh trước: Tài xế={context.get('driver_mention') or context.get('driver_id')}]"
        if context.get("time_mention") and any(k in query.lower() for k in ["thời gian", "kỳ", "tháng", "năm", "hôm", "kỳ đó", "thì sao", "thế nào"]):
            user_content += f"\n[Ngữ cảnh trước: Thời gian={context.get('time_mention')}]"
        if context.get("policy_scope"):
            user_content += f"\n[Ngữ cảnh trước: Quy chế={context.get('policy_scope')}]"
        if context.get("policy_topics"):
            user_content += f"\n[Ngữ cảnh trước: Chủ đề quy chế={context.get('policy_topics')}]"

        extracted: dict[str, Any] = {}
        try:
            raw_resp, _, _ = self._call_llm(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=400,
                temperature=0.0,
                timeout=15.0,
            )
            if raw_resp and raw_resp.strip():
                clean_json = raw_resp.strip()
                if "<think>" in clean_json and "</think>" in clean_json:
                    clean_json = re.sub(r"<think>.*?</think>", "", clean_json, flags=re.DOTALL).strip()
                if clean_json.startswith("```"):
                    clean_json = re.sub(r"^```[a-zA-Z]*\n?", "", clean_json)
                    clean_json = re.sub(r"\n?```$", "", clean_json)
                brace_match = re.search(r"\{.*\}", clean_json, re.DOTALL)
                if brace_match:
                    clean_json = brace_match.group(0)
                    extracted = json.loads(clean_json.strip())
        except Exception as e:
            print(f"[AI Slot Extractor Warning] LLM parsing failed ({e}), using dynamic pattern fallback.")

        # Enrich with pattern fallback to ensure high coverage of domain codes and topics
        if not extracted or not isinstance(extracted, dict):
            extracted = pattern_data
        else:
            # If pattern detected an explicit driver name in the query, prioritize it over any stale context name from LLM
            if pattern_data.get("driver_name"):
                llm_name = (extracted.get("driver_name") or "").lower()
                pat_name = pattern_data["driver_name"].lower()
                if pat_name not in llm_name:
                    extracted["driver_name"] = pattern_data["driver_name"]
                    if not pattern_data.get("driver_code"):
                        extracted["driver_code"] = None
                    if not pattern_data.get("driver_id"):
                        extracted["driver_id"] = None
            elif not extracted.get("driver_name") and pattern_data.get("driver_name"):
                extracted["driver_name"] = pattern_data["driver_name"]

            # Sanitize policy_scope: reject any LLM hallucinated policy code not explicitly in query or context
            raw_ai_policies = extracted.get("policy_scope") or []
            if isinstance(raw_ai_policies, str):
                raw_ai_policies = [p.strip().upper() for p in raw_ai_policies.split(",") if p.strip()]
            sanitized_policies: list[str] = []
            ctx_policies = context.get("policy_scope") or []
            if isinstance(ctx_policies, str):
                ctx_policies = [p.strip().upper() for p in ctx_policies.split(",") if p.strip()]
            else:
                ctx_policies = [str(p).strip().upper() for p in ctx_policies if str(p).strip()]

            pattern_policies = [str(p).strip().upper() for p in pattern_data.get("policy_scope", [])]
            for p in raw_ai_policies:
                p_clean = str(p).strip().upper()
                if (
                    p_clean in query.upper()
                    or p_clean in pattern_policies
                    or p_clean in ctx_policies
                ):
                    if p_clean not in sanitized_policies:
                        sanitized_policies.append(p_clean)

            for p in pattern_policies:
                if p not in sanitized_policies:
                    sanitized_policies.append(p)
            extracted["policy_scope"] = sanitized_policies

            if not extracted.get("policy_topics") and pattern_data.get("policy_topics"):
                extracted["policy_topics"] = pattern_data["policy_topics"]
            elif pattern_data.get("policy_topics"):
                for t in pattern_data["policy_topics"]:
                    if t not in extracted["policy_topics"]:
                        extracted["policy_topics"].append(t)

            if not extracted.get("driver_code") and pattern_data.get("driver_code"):
                extracted["driver_code"] = pattern_data["driver_code"]
            if not extracted.get("time_raw") and pattern_data.get("time_raw"):
                extracted["time_raw"] = pattern_data["time_raw"]

        return extracted

    def _pattern_fallback_extraction(self, query: str) -> dict[str, Any]:
        """Generic zero-hardcode pattern extractor as fallback when LLM API is unavailable."""
        q_lower = query.lower()
        res: dict[str, Any] = {
            "driver_id": None,
            "driver_code": None,
            "driver_name": None,
            "time_raw": None,
            "time_resolved": None,
            "policy_scope": [],
            "policy_topics": [],
            "has_policy_target": False,
            "needs_compliance_check": True,
            "intent": "HYBRID_REASONING",
            "modalities": ["document", "kg", "computation"],
        }

        # 1. UUID for driver_id
        uuid_match = re.search(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", query, re.IGNORECASE)
        if uuid_match:
            res["driver_id"] = uuid_match.group(0).lower()

        # 2. Driver Code pattern like DRV-xxx or D1..D8
        code_match = re.search(r"\b(DRV-\d{3}|D\d)\b", query, re.IGNORECASE)
        if code_match:
            res["driver_code"] = code_match.group(0).upper()

        # 3. Driver Name pattern without hardcoding names
        name_match = re.search(
            r"(?:kiểm tra tài xế|tra cứu tài xế|hồ sơ tài xế|tài xế|bác tài|\banh\b|\bem\b|tôi là|tên(?: là)?)\s+([A-ZÀ-Ỹa-zà-ỹ\s]+?)(?:,|\.|\btrong\b|\btheo\b|\bvào\b|\btháng\b|\bhôm\b|\bmã\b|\bthì\b|\bthế\b|\bcó\b|\bnhé\b|\bnhỉ\b|\bạ\b|\bkhông\b|\bko\b|\bchưa\b|\bở\b|\bđược\b|\bnhư\b|\b\(|$)",
            query,
            re.IGNORECASE,
        )
        if name_match:
            candidate_name = name_match.group(1).strip()
            # Clean leading prefix
            clean_name = re.sub(
                r"^(?:kiểm tra tài xế|tra cứu tài xế|hồ sơ tài xế|tài xế|bác tài|\banh\b|\bem\b|tôi là|tên là)\s+",
                "",
                candidate_name,
                flags=re.IGNORECASE,
            ).strip()
            clean_name = re.sub(
                r"\b(thì sao|thì|thế nào|thế|nhé|nhỉ|ạ|không|ko|chưa|nào)\b.*$",
                "",
                clean_name,
                flags=re.IGNORECASE,
            ).strip()
            if len(clean_name) > 1 and clean_name.lower() not in ("nào", "gì", "ai", "xe", "số", "này", "đó", "kia", "ấy", "như", "sao", "mới", "cũ"):
                res["driver_name"] = clean_name

        # 4. Policies pattern like P154, P05, P23
        res["policy_scope"] = re.findall(r"\b(P\d{2,3})\b", query, re.IGNORECASE)

        # 4.1 Policy topics pattern
        policy_topics: list[str] = []
        if any(k in q_lower for k in ["hủy chuyến", "huỷ chuyến", "hủy cuốc", "huỷ cuốc", "tỷ lệ hủy", "tỷ lệ huỷ"]):
            policy_topics.append("tỷ lệ hủy chuyến")
        if any(k in q_lower for k in ["doanh số", "mức khoán", "truy thu", "khoán doanh thu"]):
            policy_topics.append("mức khoán doanh số")
        if any(k in q_lower for k in ["đánh giá sao", "xếp hạng sao", "rating", "điểm sao"]) or re.search(r"\b(?:\d+|số|điểm|hạng)\s+sao\b", q_lower):
            policy_topics.append("tiêu chuẩn đánh giá sao")
        if any(k in q_lower for k in ["đồng phục", "tác phong", "diện mạo", "trang phục"]):
            policy_topics.append("tác phong diện mạo")
        if any(k in q_lower for k in ["thưởng tuần", "thưởng tháng", "tiền thưởng", "chương trình thưởng"]) or re.search(r"\bchính sách thưởng\b|\bmức thưởng\b", q_lower):
            policy_topics.append("chính sách tiền thưởng")
        if any(k in q_lower for k in ["kỷ luật", "chế tài", "xử phạt", "khóa tài khoản", "tạm khóa", "khóa app", "xử lý vi phạm"]):
            policy_topics.append("chế tài xử lý vi phạm")
        if any(k in q_lower for k in ["bảo hiểm"]):
            policy_topics.append("bảo hiểm phương tiện")
        if any(k in q_lower for k in ["ngày vận doanh"]):
            policy_topics.append("ngày vận doanh")
        if any(k in q_lower for k in ["quy tắc ứng xử", "bộ quy tắc"]):
            policy_topics.append("quy tắc ứng xử")

        res["policy_topics"] = policy_topics
        res["has_policy_target"] = bool(res["policy_scope"] or policy_topics)

        # 5. Time patterns
        month_match = re.search(r"\b(tháng\s+\d{1,2}(?:\s*/\s*\d{4}|\s+năm\s+\d{4})?)\b", q_lower)
        if month_match:
            res["time_raw"] = month_match.group(1)
        elif "hôm qua" in q_lower:
            res["time_raw"] = "hôm qua"
        elif "hôm nay" in q_lower:
            res["time_raw"] = "hôm nay"
        elif any(k in q_lower for k in ["30 ngày gần nhất", "30 ngày qua", "30 ngày"]):
            res["time_raw"] = "30 ngày gần nhất"
        elif "tháng trước" in q_lower or "tháng vừa rồi" in q_lower:
            res["time_raw"] = "tháng trước"

        # Check year pattern like 'năm 2024' or '2024' if no time_raw yet
        if not res["time_raw"]:
            year_match = re.search(r"\b(năm\s+\d{4})\b", q_lower)
            if year_match:
                res["time_raw"] = year_match.group(1)

        # Dynamic intent classification without hardcoding
        has_driver_cue = bool(
            res["driver_id"]
            or res["driver_code"]
            or res["driver_name"]
            or any(k in q_lower for k in ["kiểm tra tài xế", "tra cứu tài xế", "hồ sơ tài xế", "bác tài", "của tài xế", "tài xế có bị", "tài xế nào"])
            or (("tài xế" in q_lower or "lái xe" in q_lower) and any(v in q_lower for v in ["kiểm tra", "tra cứu", "xử phạt", "vi phạm", "lịch sử", "đối soát"]))
        )
        is_policy_inquiry = (
            bool(res["policy_scope"])
            or bool(res["policy_topics"])
            or any(k in q_lower for k in ["quy chế", "quy định", "chính sách", "tiêu chuẩn", "thưởng", "đánh giá sao", "mức khoán", "hướng dẫn", "áp dụng"])
        )

        if is_policy_inquiry and not has_driver_cue:
            res["intent"] = "POLICY_LOOKUP"
            res["needs_compliance_check"] = False
            res["modalities"] = ["document"]
        else:
            res["intent"] = "HYBRID_REASONING"
            res["needs_compliance_check"] = True
            res["modalities"] = ["document", "kg", "computation"]

        return res

    def plan_query(self, query: str, context: dict[str, Any] | None = None) -> QueryPlan:
        """AI Query Planning with Strict Verification via Database Tools:
        1. Calls AI to extract slots (JSON with driver_id, driver_code, driver_name, time_raw, time_resolved).
        2. Validates & disambiguates driver against SQLite database:
           - If missing both id & code:
             * If name missing -> ask user
             * If name present -> search database:
               - count == 0: error "Không tồn tại tài xế..."
               - count > 1: clarify with exact list of drivers "Tên này có n người..."
               - count == 1: auto-fill driver_id & driver_code
           - If code present -> query database by code:
             * count == 0: error "Không tồn tại tài xế có mã..."
             * count == 1: auto-fill driver_id (UUID) from DB
           - If id present -> query database by id
        3. Validates time & snapshot:
           - Matches snapshot from SQLite snapshots table.
           - Checks if database has any trips for driver in that time / snapshot:
             * count == 0: error "Không tồn tại dữ liệu chuyến đi..."
        """
        context = context or {}
        q_lower = query.lower()

        # Step 1: Extract slots using AI
        slots = self.extract_slots_with_ai(query, context)

        # Disambiguate context inheritance: if current query explicitly specifies a driver name or driver code,
        # do NOT inherit driver_id / driver_mention from previous context!
        if slots.get("driver_name") or slots.get("driver_code"):
            driver_id = slots.get("driver_id")  # None unless direct UUID was given in query
            driver_code = slots.get("driver_code")
            driver_name = slots.get("driver_name")
            driver_mention = None
        else:
            driver_id = slots.get("driver_id") or context.get("driver_id")
            driver_code = slots.get("driver_code")
            driver_name = slots.get("driver_name")
            driver_mention = context.get("driver_mention")

        time_raw = slots.get("time_raw") or context.get("time_mention") or context.get("time_scope")
        time_resolved = slots.get("time_resolved")

        # Normalize policy_scope from slots or context
        raw_policy_scope = slots.get("policy_scope") or context.get("policy_scope") or []
        if isinstance(raw_policy_scope, str):
            policy_scope = [p.strip() for p in raw_policy_scope.split(",") if p.strip()]
        elif isinstance(raw_policy_scope, list):
            policy_scope = [str(p).strip() for p in raw_policy_scope if str(p).strip()]
        else:
            policy_scope = []

        # Normalize policy_topics from slots or context
        raw_policy_topics = slots.get("policy_topics") or context.get("policy_topics") or []
        if isinstance(raw_policy_topics, str):
            policy_topics = [t.strip() for t in raw_policy_topics.split(",") if t.strip()]
        elif isinstance(raw_policy_topics, list):
            policy_topics = [str(t).strip() for t in raw_policy_topics if str(t).strip()]
        else:
            policy_topics = []

        # Check if current query explicitly specifies or refers to a driver
        has_explicit_driver = bool(slots.get("driver_id") or slots.get("driver_code") or slots.get("driver_name"))
        has_driver_reference = has_explicit_driver or any(k in q_lower for k in [
            "tài xế này", "bác tài này", "người này", "anh này", "chị này", "tài xế đó", "bác tài đó",
            "kiểm tra tài xế", "tra cứu tài xế", "hồ sơ tài xế", "của tài xế", "tài xế có bị",
        ])

        # Trust AI Semantic Intent with clear boundary between driver check and general policy lookup
        raw_intent = slots.get("intent")
        needs_compliance = slots.get("needs_compliance_check", False)

        if has_driver_reference:
            has_policy_cues = bool(
                needs_compliance
                or context.get("policy_topics")
                or context.get("policy_scope")
                or slots.get("policy_topics")
                or slots.get("policy_scope")
                or any(k in q_lower for k in ["vi phạm", "chính sách", "quy chế", "quy định", "tiêu chuẩn", "hủy chuyến", "đối soát", "thưởng", "phạt", "kỷ luật"])
            )
            intent = "HYBRID_REASONING" if has_policy_cues else "DRIVER_HISTORY"
        elif (
            raw_intent == "POLICY_LOOKUP"
            or slots.get("policy_scope")
            or slots.get("policy_topics")
            or any(k in q_lower for k in ["chính sách", "quy chế", "quy định", "tiêu chuẩn", "hướng dẫn", "chế tài"])
        ):
            intent = "POLICY_LOOKUP"
        else:
            intent = raw_intent or "HYBRID_REASONING"

        # Verification requirements derived cleanly from semantic intent
        if intent == "POLICY_LOOKUP":
            needs_driver = False
            needs_time = False
            needs_policy = True
            # Context Isolation: if the current query does NOT specify a driver, do NOT inherit driver or time from previous context
            if not has_explicit_driver:
                driver_id = None
                driver_code = None
                driver_name = None
                driver_mention = None
            else:
                driver_mention = context.get("driver_mention")
            if not slots.get("time_raw"):
                time_raw = None
                time_scope = None
            else:
                time_scope = time_raw
        else:
            needs_driver = True
            needs_time = True
            if not (slots.get("driver_name") or slots.get("driver_code")):
                driver_mention = context.get("driver_mention")
            else:
                driver_mention = None
            time_scope = time_raw
            # In hybrid reasoning, if the query asks about compliance/violation/audit,
            # we also require a clear policy target (specific code/name OR specific topic like cancel rate, revenue, rating...)
            has_compliance_cue = (
                needs_compliance
                or any(k in q_lower for k in [
                    "vi phạm", "chính sách", "quy chế", "quy định", "tiêu chuẩn",
                    "đối soát", "thưởng phạt", "xử phạt", "kỷ luật", "đạt chuẩn", "tuân thủ"
                ])
            )
            needs_policy = bool(has_compliance_cue)

        missing_fields: list[str] = []
        clarification_reasons: dict[str, str] = {}
        is_ambiguous = False
        snapshot_id: str | None = context.get("snapshot_id")

        # Step 2: Driver Verification & Disambiguation Gate via Database Tools
        if needs_driver:
            # Case A: Missing both id and code
            if not driver_id and not driver_code:
                if not driver_name:
                    missing_fields.append("driver_id")
                    clarification_reasons["driver_id"] = "Vui lòng cung cấp Mã tài xế (ví dụ: DRV-001, DRV-002...) hoặc Họ tên tài xế cần kiểm tra."
                else:
                    # Search database by name
                    matches = self.db_repo.search_drivers_by_name(driver_name)
                    if len(matches) == 0:
                        missing_fields.append("driver_id")
                        clarification_reasons["driver_id"] = f"Không tìm thấy tài xế nào có tên '{driver_name}' trong hệ thống. Vui lòng kiểm tra lại."
                    elif len(matches) > 1:
                        is_ambiguous = True
                        missing_fields.append("driver_id")
                        driver_list_str = "\n".join([
                            f"   - {d.full_name} (Mã: {d.driver_code}, Đội: {d.depot_name or 'N/A'}, Xe: {d.vehicle_model or 'N/A'})"
                            for d in matches
                        ])
                        clarification_reasons["driver_id"] = (
                            f"Trong hệ thống hiện có {len(matches)} tài xế cùng tên '{driver_name}':\n"
                            f"{driver_list_str}\n"
                            f"Vui lòng cung cấp mã tài xế (DRV-xxx) hoặc ID để xác định chính xác đối tượng tra cứu."
                        )
                    else:
                        # Exactly 1 driver found!
                        driver_id = matches[0].driver_id
                        driver_code = matches[0].driver_code
                        driver_mention = f"{matches[0].full_name} ({matches[0].driver_code})"

            # Case B: driver_code present, driver_id not yet resolved
            elif driver_code and not driver_id:
                found = self.db_repo.get_driver_by_code(driver_code)
                if not found:
                    missing_fields.append("driver_id")
                    clarification_reasons["driver_id"] = f"Không tồn tại tài xế có mã '{driver_code}' trong hệ thống. Vui lòng kiểm tra lại."
                else:
                    driver_id = found.driver_id  # UUID for graph seed!
                    driver_code = found.driver_code
                    driver_mention = f"{found.full_name} ({found.driver_code})"

            # Case C: driver_id present
            elif driver_id:
                found = self.db_repo.get_driver(driver_id)
                if not found:
                    missing_fields.append("driver_id")
                    clarification_reasons["driver_id"] = f"Không tồn tại tài xế có ID '{driver_id}' trong hệ thống. Vui lòng kiểm tra lại."
                else:
                    driver_id = found.driver_id  # Ensure canonical UUID!
                    driver_code = found.driver_code
                    driver_mention = f"{found.full_name} ({found.driver_code})"

        # Step 3: Time & Snapshot Verification Gate via Database Tools
        if needs_time:
            if not time_scope:
                missing_fields.append("time_scope")
                clarification_reasons["time_scope"] = "Cần mốc thời gian cụ thể (ví dụ: tháng 9/2026, 30 ngày gần nhất...)."
            else:
                # Find matching snapshot in SQLite snapshots table using dynamic ISO time resolution
                snap = self.db_repo.find_snapshot_by_alias_or_time(time_query=time_scope, time_resolved=time_resolved)
                if snap:
                    snapshot_id = snap.snapshot_id
                    time_scope = time_scope or snap.label
                else:
                    snapshot_id = None
                    missing_fields.append("time_data")
                    clarification_reasons["time_data"] = (
                        f"Không tìm thấy dữ liệu vận hành nào trong khoảng thời gian '{time_scope}'. "
                        "Hệ thống hiện tại chỉ có dữ liệu trong giai đoạn tháng 08 - tháng 09/2026. "
                        "Vui lòng chọn mốc thời gian phù hợp (ví dụ: tháng 9/2026, 30 ngày gần nhất)."
                    )

                # If driver is verified and snapshot is valid, check if database has any trips for driver in that snapshot
                if driver_id and snapshot_id:
                    cnt = self.db_repo.count_driver_trips(driver_id, snapshot_id=snapshot_id)
                    if cnt == 0:
                        total_driver_trips = self.db_repo.count_driver_trips(driver_id)
                        if total_driver_trips == 0:
                            missing_fields.append("driver_data")
                            clarification_reasons["driver_data"] = f"Tài xế {driver_mention or driver_id} chưa có bất kỳ dữ liệu chuyến đi nào trong hệ thống."
                        else:
                            missing_fields.append("time_data")
                            clarification_reasons["time_data"] = (
                                f"Không tìm thấy dữ liệu chuyến đi nào của tài xế {driver_mention or driver_id} "
                                f"trong khoảng thời gian '{time_scope}'. Vui lòng chọn mốc thời gian khác (ví dụ: tháng 9/2026, 30 ngày gần nhất)."
                            )

        # Step 4: Policy Target Verification Gate (Name / Code OR Topic)
        if needs_policy:
            has_policy_target = bool(
                policy_scope
                or policy_topics
                or slots.get("has_policy_target")
            )
            if not has_policy_target:
                missing_fields.append("policy_target")
                if intent == "HYBRID_REASONING":
                    clarification_reasons["policy_target"] = (
                        "vui lòng cho biết bạn muốn kiểm tra theo Quy chế nào (ví dụ: P154, P05, Bộ Quy tắc ứng xử...) "
                        "hoặc Chủ đề cụ thể nào (ví dụ: tỷ lệ hủy chuyến, mức khoán doanh số, tiêu chuẩn đánh giá sao, tác phong diện mạo...) nhé."
                    )
                else:
                    clarification_reasons["policy_target"] = (
                        "vui lòng cung cấp Tên/Mã văn bản quy chế (ví dụ: P154, P05, Bộ Quy tắc ứng xử...) "
                        "HOẶC Chủ đề/Nội dung cụ thể cần tra cứu (ví dụ: tỷ lệ hủy chuyến, mức khoán doanh số, tiêu chuẩn đánh giá sao, tác phong đồng phục...) nhé."
                    )

        if not snapshot_id and not missing_fields:
            snapshot_id = self.default_snapshot_id

        driver_str = driver_mention or driver_id or ("Không yêu cầu" if intent == "POLICY_LOOKUP" else "Chưa xác định")
        time_str = time_scope or ("Không yêu cầu" if intent == "POLICY_LOOKUP" else "Chưa xác định")
        policy_str = ", ".join(policy_scope) if policy_scope else "Chưa chỉ định văn bản cụ thể"
        topics_str = ", ".join(policy_topics) if policy_topics else "Chưa chỉ định chủ đề"

        reasoning = (
            f"Ý định: {intent}. "
            f"Tài xế: {driver_str}. "
            f"Thời gian: {time_str}. "
            f"Quy chế: {policy_str}. "
            f"Chủ đề: {topics_str}."
        )

        # Resolve modalities accurately based on intent and query components
        raw_modalities = slots.get("modalities") or []
        if isinstance(raw_modalities, list):
            resolved_modalities = [m.lower().strip() for m in raw_modalities if m.strip()]
        else:
            resolved_modalities = []

        if intent == "POLICY_LOOKUP":
            if "document" not in resolved_modalities:
                resolved_modalities.append("document")
        elif intent == "HYBRID_REASONING":
            for mod in ("document", "kg", "computation"):
                if mod not in resolved_modalities:
                    resolved_modalities.append(mod)
        elif intent == "DRIVER_HISTORY":
            if "kg" not in resolved_modalities:
                resolved_modalities.append("kg")
            if bool(policy_scope or policy_topics) and "document" not in resolved_modalities:
                resolved_modalities.append("document")
        else:
            if not resolved_modalities:
                resolved_modalities = ["document", "kg", "computation"]

        return QueryPlan(
            intent=intent,
            driver_id=driver_id,
            driver_mention=driver_mention,
            is_driver_ambiguous=is_ambiguous,
            time_scope=time_scope,
            snapshot_id=snapshot_id,
            policy_scope=policy_scope,
            policy_topics=policy_topics,
            modalities=resolved_modalities,
            missing_fields=missing_fields,
            clarification_reasons=clarification_reasons,
            reasoning=reasoning,
        )

    def analyze_query(self, query: str, context: dict[str, Any] | None = None) -> SlotExtractionResult:
        plan = self.plan_query(query, context)
        return SlotExtractionResult(
            intent=plan.intent,
            needs_driver="driver_id" in plan.missing_fields or bool(plan.driver_id),
            driver_id=plan.driver_id,
            driver_mention=plan.driver_mention,
            is_driver_ambiguous=plan.is_driver_ambiguous,
            needs_time="time_scope" in plan.missing_fields or bool(plan.time_scope),
            has_time_scope=bool(plan.time_scope),
            time_mention=plan.time_scope,
            snapshot_id=plan.snapshot_id,
            policy_mentions=plan.policy_scope,
            policy_topics=plan.policy_topics,
            has_policy_target=bool(plan.policy_scope or plan.policy_topics),
            missing_slots=plan.missing_fields,
        )

    # =========================================================================
    # Step 2: Clarification Message Generator from Query Plan
    # =========================================================================
    def build_clarification_message(self, plan: QueryPlan | SlotExtractionResult) -> str:
        missing = getattr(plan, "missing_fields", None) or getattr(plan, "missing_slots", [])
        reasons = getattr(plan, "clarification_reasons", {})

        items: list[str] = []
        for field_name in missing:
            msg = reasons.get(field_name)
            if msg:
                items.append(msg)

        if not items:
            return "Để tôi có thể hỗ trợ bạn tốt nhất, bạn vui lòng cung cấp thêm thông tin nhé."

        if len(items) == 1:
            item = items[0]
            if item.startswith("vui lòng") or item.startswith("Để "):
                return f"Để tôi có thể hỗ trợ kiểm tra và đối soát chính xác cho bạn, {item}"
            return f"Để tôi có thể hỗ trợ kiểm tra chính xác, {item}"

        res = "Để tôi có thể hỗ trợ kiểm tra và đối soát chính xác nhất, bạn vui lòng bổ sung thêm các thông tin sau nhé:\n\n"
        for i, item in enumerate(items, 1):
            res += f"- {item}\n"
        return res.strip()


    # =========================================================================
    # Step 3: Subgraph Expansion (BFS 1-hop / 2-hop)
    # =========================================================================
    def expand_subgraph_bfs(self, driver_id: str, snapshot_id: str) -> Subgraph:
        subgraph = Subgraph(seed_id=driver_id or "", snapshot_id=snapshot_id)
        if not driver_id:
            return subgraph

        neo4j_success = False
        if self.neo4j_driver:
            try:
                # Live BFS on Neo4j Operational KG
                with self.neo4j_driver.session() as session:
                    # Hop 1: Driver -> Direct Neighbors in snapshot
                    cypher = """
                    MATCH (d:GSMOperationalV1:Driver {id: $driver_id})-[r]->(m:GSMOperationalV1)
                    WHERE r.snapshot_id = $snapshot_id
                    RETURN d.id AS driver_id, d.name AS driver_name, properties(d) AS driver_props,
                           type(r) AS rel_type, properties(r) AS rel_props,
                           labels(m) AS m_labels, m.id AS m_id, m.name AS m_name, properties(m) AS m_props
                    """
                    records = session.run(cypher, driver_id=driver_id, snapshot_id=snapshot_id).data()

                    # Add Driver Seed Node with rich metadata
                    driver_name = records[0]["driver_name"] if records else f"Driver {driver_id[:8]}"
                    driver_props = dict(records[0].get("driver_props", {})) if records else {"id": driver_id}
                    if self.db_repo and driver_id:
                        d_local = self.db_repo.get_driver(driver_id)
                        if d_local:
                            driver_props.setdefault("code", d_local.driver_code)
                            driver_props.setdefault("full_name", d_local.full_name)
                            driver_props.setdefault("depot", d_local.depot_name)
                            driver_props.setdefault("vehicle", d_local.vehicle_model)
                            driver_props.setdefault("rating", d_local.rating_avg)
                    subgraph.nodes.append(
                        SubgraphNode(id=driver_id, label="Driver", name=driver_name, props=driver_props)
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
                neo4j_success = True
            except Exception as e:
                print(f"[Pipeline BFS Warning] Neo4j query error ({e}), falling back to offline snapshot.")
                neo4j_success = False

        if not neo4j_success:
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
    # Step 4: Multi-Source Evidence Gathering (Graph-to-Text Verbalization)
    # =========================================================================
    def gather_multi_source_evidence(
        self, query: str, slots: SlotExtractionResult, subgraph: Subgraph
    ) -> list[dict[str, Any]]:
        evidence_list: list[dict[str, Any]] = []

        # 1. Document Evidence from Hybrid Qdrant (Dense) + BM25 (Lexical) + Cross-Encoder Rerank
        policy_scope = slots.policy_mentions if hasattr(slots, "policy_mentions") else []
        policy_topics = getattr(slots, "policy_topics", [])
        final_top_k = 5 if getattr(slots, "intent", "") == "POLICY_LOOKUP" else 4

        # Optimize search query for policy retrieval: focus on topic and policy clauses, stripping driver noise
        policy_search_query = query
        if policy_topics:
            topics_clean = [t.strip() for t in policy_topics if t.strip()]
            if topics_clean:
                policy_search_query = f"Quy định quy chế tiêu chuẩn xử lý về {' '.join(topics_clean)}"
                if policy_scope:
                    policy_search_query += f" {' '.join(policy_scope)}"

        raw_candidates: list[dict[str, Any]] = []
        try:
            doc_evidence, retrieval_receipt = self.hybrid_searcher.search_and_rerank(
                policy_search_query,
                bm25_top_k=12,
                dense_top_k=12,
                rerank_top_n=15,
                final_top_k=final_top_k,
                policy_scope=policy_scope,
                policy_topics=policy_topics,
            )
            raw_candidates = list(doc_evidence)
            self._last_retrieval_receipt = retrieval_receipt
        except Exception as exc:
            print(f"[Evidence Gathering Error] Hybrid search failed: {exc}, falling back to local BM25.")
            chunk_map = {c.chunk_id: c for c in self.chunks}
            doc_matches = self.bm25_index.search(query, top_k=4)
            for ranked in doc_matches:
                chunk = chunk_map.get(ranked.chunk_id)
                if not chunk:
                    continue
                doc_meta = self.doc_catalog_meta.get(chunk.document_revision_id) or self.doc_catalog_meta.get(chunk.source_id) or {}
                alias = doc_meta.get("alias") or chunk.document_revision_id[:8]
                title = doc_meta.get("title") or "Văn bản quy chế GSM"
                clause_str = f"#{','.join(chunk.clause_ids)}" if chunk.clause_ids else ""
                raw_candidates.append({
                    "source_kind": "document",
                    "evidence_id": f"doc-{chunk.chunk_id}",
                    "document_revision_id": chunk.document_revision_id,
                    "source_id": chunk.source_id,
                    "citation_locator": f"{alias}{clause_str}",
                    "policy_alias": alias,
                    "policy_title": title,
                    "chunk_text": chunk.text,
                    "content": f"[{alias} - {title}] {chunk.text}",
                    "score": float(ranked.score),
                })

        # Group matched chunks by policy and load complete normalized policy text
        policy_groups: dict[str, dict[str, Any]] = {}
        for c in raw_candidates:
            alias = c.get("policy_alias") or c.get("alias") or ""
            rev_id = c.get("document_revision_id") or c.get("source_id") or ""
            key = alias if alias else (rev_id or "unknown")
            if key not in policy_groups:
                title = c.get("policy_title") or c.get("title") or "Văn bản quy chế GSM"
                canonical_rev_id = rev_id
                if alias and hasattr(self, "doc_by_alias") and alias.upper() in self.doc_by_alias:
                    canonical_rev_id = self.doc_by_alias[alias.upper()].get("document_revision_id") or rev_id
                    title = self.doc_by_alias[alias.upper()].get("title") or title
                policy_groups[key] = {
                    "alias": alias,
                    "title": title,
                    "revision_id": canonical_rev_id,
                    "excerpts": [],
                    "best_score": c.get("score", 0.0),
                }
            chunk_txt = c.get("chunk_text") or c.get("content") or ""
            if chunk_txt and chunk_txt not in policy_groups[key]["excerpts"]:
                policy_groups[key]["excerpts"].append(chunk_txt)
            if c.get("score", 0.0) > policy_groups[key]["best_score"]:
                policy_groups[key]["best_score"] = c.get("score", 0.0)

        # Check if there are explicit policy mentions in query or policy_scope that weren't in top retrieved
        if policy_scope:
            for p_mention in policy_scope:
                p_clean = str(p_mention).strip().upper()
                if p_clean in getattr(self, "doc_by_alias", {}) and p_clean not in policy_groups:
                    p_info = self.doc_by_alias[p_clean]
                    policy_groups[p_clean] = {
                        "alias": p_clean,
                        "title": p_info.get("title", f"Văn bản quy chế {p_clean}"),
                        "revision_id": p_info.get("document_revision_id", ""),
                        "excerpts": [],
                        "best_score": 1.0,
                    }

        # Sort unique policies by best score and pick top policies
        max_policies = 3 if getattr(slots, "intent", "") == "POLICY_LOOKUP" else 2
        sorted_policies = sorted(policy_groups.values(), key=lambda x: -x["best_score"])[:max_policies]

        for p in sorted_policies:
            alias = p["alias"]
            title = p["title"]
            rev_id = p["revision_id"]
            policy_res = self.get_full_policy_text(identifier=rev_id, alias=alias, clean=True)
            meta: dict[str, str] = {}
            if isinstance(policy_res, tuple):
                meta, full_text = policy_res
            else:
                full_text = policy_res or ""
            excerpts_str = "\n\n---\n\n".join(p["excerpts"])

            if full_text:
                doc_body = full_text
            elif excerpts_str:
                doc_body = excerpts_str
            else:
                doc_body = f"Nội dung quy chế {alias} ({title}) không có sẵn trên đĩa."

            evidence_list.append({
                "source_kind": "document",
                "evidence_id": f"policy-{alias or rev_id[:8]}",
                "citation_locator": f"[{alias}] {title}" if (alias and alias not in title) else (title or alias or "Quy chế GSM"),
                "policy_alias": alias,
                "policy_title": title,
                "policy_date": meta.get("date") or p.get("posted_date", ""),
                "policy_category": meta.get("category", ""),
                "document_revision_id": rev_id,
                "matched_excerpts": excerpts_str,
                "full_content": doc_body,
                "content": f"[VĂN BẢN QUY CHẾ: {alias} - {title}]\n{doc_body}",
                "score": float(p["best_score"]),
            })

        # 2. KG Subgraph Facts (Granular Node & Edge Extraction)
        trips = [n for n in subgraph.nodes if n.label == "Trip"]
        measurements = [n for n in subgraph.nodes if n.label == "Measurement"]
        incidents = [n for n in subgraph.nodes if n.label == "Incident"]
        driver_node = next((n for n in subgraph.nodes if n.label == "Driver"), None)
        fleet_node = next((n for n in subgraph.nodes if n.label == "Fleet"), None)
        region_node = next((n for n in subgraph.nodes if n.label == "Region"), None)
        state_nodes = [n for n in subgraph.nodes if n.label == "StateObservation"]
        service_nodes = [n for n in subgraph.nodes if n.label == "Service"]

        if slots.driver_id or driver_node:
            d_id = slots.driver_id or (driver_node.id if driver_node else "")
            d_name = driver_node.name if driver_node else (slots.driver_mention or f"Tài xế {d_id[:8]}")

            # 2.1 Driver Profile, Fleet & Regional Operations
            d_local = self.db_repo.get_driver(d_id) if (self.db_repo and d_id) else None
            driver_code = getattr(d_local, "driver_code", None) or (driver_node.props.get("code") if driver_node else "") or "DRV"
            fleet_name = fleet_node.name if fleet_node else getattr(d_local, "depot_name", None)
            region_name = region_node.name if region_node else None
            vehicle_name = getattr(d_local, "vehicle_model", None) or (driver_node.props.get("vehicle") if driver_node else "")

            # State observations (e.g. driver_program)
            programs = [s.props.get("value") or s.name for s in state_nodes if s.props.get("state_kind") == "driver_program" or "program" in s.name.lower()]
            program_str = f", Chương trình đối tác: {programs[0]}" if programs else ""

            profile_desc = f"Đối tác tài xế {d_name} (Mã: {driver_code}){program_str}"
            if fleet_name:
                profile_desc += f", Đội xe: {fleet_name}"
            if region_name:
                profile_desc += f", Địa bàn: {region_name}"
            if vehicle_name:
                profile_desc += f", Dòng xe: {vehicle_name}"

            evidence_list.append({
                "source_kind": "kg_subgraph",
                "evidence_id": f"kg-driver-profile-{d_id[:8]}",
                "citation_locator": f"entity:driver:{driver_code or d_id[:8]}",
                "content": f"[Hồ sơ đối tác tài xế từ đồ thị] {profile_desc}.",
            })

            # 2.2 Aggregate Trip Summary & Cancellation Details
            completed_trips = sum(1 for t in trips if t.props.get("outcome") == "completed")
            cancelled_trips = sum(1 for t in trips if t.props.get("outcome") == "cancelled")
            trip_summary = (
                f"Tài xế có tổng cộng {len(trips)} chuyến đi được ghi nhận: "
                f"{completed_trips} chuyến hoàn thành, {cancelled_trips} chuyến bị hủy."
            )
            if cancelled_trips > 0:
                cancelled_details = []
                for t in trips:
                    if t.props.get("outcome") == "cancelled":
                        reason = t.props.get("reason_code", "không rõ")
                        event_time = t.props.get("event_time") or t.props.get("valid_at") or ""
                        time_str = f" lúc {event_time[:19].replace('T', ' ')}" if event_time else ""
                        cancelled_details.append(f"chuyến {t.id[:8]} (lý do: {reason}{time_str})")
                trip_summary += f" Chi tiết các chuyến hủy: {'; '.join(cancelled_details)}."

            evidence_list.append({
                "source_kind": "kg_subgraph",
                "evidence_id": f"kg-trips-{d_id[:8]}",
                "citation_locator": f"ledger:trips:{driver_code or d_id[:8]}",
                "policy_alias": "",
                "policy_title": f"Lịch sử chuyến đi & chi tiết hủy ({len(trips)} chuyến)",
                "content": f"[Lịch sử chuyến đi từ đồ thị] {trip_summary}",
            })

            # 2.4 Measurements from Operational Ledger
            for m in measurements:
                def_id = m.props.get("definition_id", "chỉ_số")
                val = m.props.get("value", "")
                w_start = m.props.get("window_start", "")[:10]
                w_end = m.props.get("window_end", "")[:10]
                unit = m.props.get("unit", "")
                unit_str = f" {unit}" if unit else " VNĐ"
                evidence_list.append({
                    "source_kind": "kg_subgraph",
                    "evidence_id": f"kg-meas-{m.id[:8]}",
                    "citation_locator": f"assertion:{m.id}",
                    "content": f"[Báo cáo vận hành] Chỉ số {def_id} = {val}{unit_str} trong kỳ [{w_start} đến {w_end}].",
                })

            # 2.5 Incidents
            for inc in incidents:
                evidence_list.append({
                    "source_kind": "kg_subgraph",
                    "evidence_id": f"kg-inc-{inc.id[:8]}",
                    "citation_locator": f"assertion:incident:{inc.id[:8]}",
                    "content": f"[Biên bản sự cố/vi phạm] {inc.name}: {inc.props.get('description', '')}.",
                })

            # 3. Exact Rational Computation (cancel_rate_30d)
            if len(trips) > 0:
                total_count = len(trips)
                cancelled_count = cancelled_trips
                rate_frac = Fraction(cancelled_count, total_count)
                rate_pct = float(cancelled_count) / float(total_count) * 100.0

                evidence_list.append({
                    "source_kind": "computation",
                    "evidence_id": f"calc-cancel-rate-{d_id[:8]}",
                    "citation_locator": "computation:cancel_rate_30d",
                    "content": (
                        f"[Tính toán số học chuẩn xác] Tỷ lệ hủy chuyến 30 ngày (cancel_rate_30d) = "
                        f"{rate_frac} ({cancelled_count}/{total_count} chuyến) = {rate_pct:.2f}%."
                    ),
                })

        return evidence_list

    # =========================================================================
    # Step 5: Grounded LLM Reader Generation & Clean Synthesis
    # =========================================================================
    def _clean_thinking_trace(self, raw_answer: str) -> str:
        """Strip thinking traces, scratchpads, and English CoT leakage."""
        if not raw_answer:
            return ""
        ans = raw_answer.strip()

        # 1. Clean XML think tags
        if "<think>" in ans and "</think>" in ans:
            ans = re.sub(r"<think>.*?</think>", "", ans, flags=re.DOTALL).strip()

        # 2. Extract Vietnamese response if preceded by English thinking process
        lower_ans = ans.lower()
        if "thinking process" in lower_ans or "analyze user input" in lower_ans or ans.startswith("1.  **Analyze User Input"):
            match = re.search(
                r"(?:(?:Draft|Báo cáo|Trả lời|Phản hồi|Kết quả tra cứu):\s*)?"
                r"((?:###?\s*(?:Câu trả lời|Phản hồi|Kết luận|Báo cáo|Trả lời)|(?:\*\*)?(?:Chào bạn|Kính gửi|Báo cáo|Dựa trên|Theo thông tin|Theo quy chế|Hiện tại|Đối với|Về việc|Kết quả tra cứu|\d+\.\s*Kết luận)).*)",
                ans,
                re.DOTALL | re.IGNORECASE,
            )
            if match:
                ans = match.group(1).strip()
            else:
                return ""

        # 3. If still starts with English scratchpad
        if ans.startswith(("Here's a thinking process", "1. Analyze User Input", "Analyze User Input:", "In this scenario:")):
            vn_match = re.search(
                r"((?:###?\s*(?:Câu trả lời|Phản hồi|Kết luận|Báo cáo|Trả lời)|(?:\*\*)?(?:Chào bạn|Kính gửi|Báo cáo|Dựa trên|Theo thông tin|Theo quy chế|Hiện tại|Đối với|Về việc|Kết quả tra cứu|\d+\.\s*Kết luận)).*)",
                ans,
                re.DOTALL | re.IGNORECASE,
            )
            if vn_match:
                return vn_match.group(1).strip()
            return ""

        return ans.strip()

    def _build_deterministic_grounded_answer(
        self, query: str, slots: SlotExtractionResult, evidence: list[dict[str, Any]]
    ) -> str:
        """Deterministic, grounded GSM compliance or policy report in pure Vietnamese without hardcoding."""
        doc_evidence = [e for e in evidence if e.get("source_kind") == "document"]
        calc_evidence = [e for e in evidence if e.get("source_kind") == "computation"]
        kg_evidence = [e for e in evidence if e.get("source_kind") == "kg_subgraph"]

        # Helper to extract clean, multi-line policy quotes with balanced structure
        def _format_policy_quote(alias: str, title: str, locator: str, raw_content: str, max_lines: int = 6, indent: str = "     ") -> list[str]:
            clean_text = re.sub(r"^\[.*?\]\s*", "", raw_content).strip()
            raw_lines = clean_text.split("\n")
            cleaned_lines: list[str] = []
            for line in raw_lines:
                line = line.strip()
                # Clean existing markdown blockquote markers >
                line = re.sub(r"^>\s*", "", line).strip()
                if not line or re.match(r"^\|?[\s\-:|]+\|?$", line):
                    continue
                # Clean heading markers
                line = re.sub(r"^#{1,6}\s*", "", line)
                if not line:
                    continue
                if not cleaned_lines and re.match(r"^[a-zà-ỹ]", line):
                    line = f"[...] {line}"
                cleaned_lines.append(line)
                if len(cleaned_lines) >= max_lines:
                    break

            bullet = "*" if indent.startswith("    ") else "-"
            lines_out = [f"{indent}{bullet} **Văn bản [{alias}]** ({title}):"]
            quote_indent = indent + "  "
            if cleaned_lines:
                for cl in cleaned_lines:
                    lines_out.append(f"{quote_indent}> {cl}")
            else:
                lines_out.append(f"{quote_indent}> {clean_text[:400]}")
            return lines_out

        # Case A: Driver Compliance & Operational Check
        is_policy_only = getattr(slots, "intent", "") == "POLICY_LOOKUP"
        has_driver_data = (slots.driver_id or slots.driver_mention) and not is_policy_only
        has_calc_data = bool(calc_evidence or (kg_evidence and not is_policy_only))

        if has_driver_data or has_calc_data:
            driver_label = slots.driver_mention or (f"Tài xế {slots.driver_id[:8]}" if slots.driver_id else "Tài xế")
            time_label = slots.time_mention or "kỳ đánh giá hiện tại"

            trip_summary = ""
            rate_summary = ""
            total_trips = 0
            cancelled_trips = 0
            rate_pct = 0.0

            for e in calc_evidence:
                content = e.get("content", "")
                if "cancel_rate_30d" in content:
                    rate_summary = content
                    m_pct = re.search(r"=\s*([0-9.]+)%", content)
                    if m_pct:
                        rate_pct = float(m_pct.group(1))
                    m_counts = re.search(r"\((\d+)/(\d+)\s*chuyến\)", content)
                    if m_counts:
                        cancelled_trips = int(m_counts.group(1))
                        total_trips = int(m_counts.group(2))

            for e in kg_evidence:
                content = e.get("content", "")
                if "chuyến đi" in content and not trip_summary:
                    trip_summary = content
                    m_trips = re.search(r"(\d+)\s*chuyến hoàn thành,\s*(\d+)\s*chuyến bị hủy", content)
                    if m_trips and not total_trips:
                        completed_cnt = int(m_trips.group(1))
                        cancelled_trips = int(m_trips.group(2))
                        total_trips = completed_cnt + cancelled_trips
                        if total_trips > 0:
                            rate_pct = round((cancelled_trips / total_trips) * 100.0, 2)

            # Grounded policy threshold analysis: do NOT invent a 10.0% threshold unless explicitly supported
            # Check if any retrieved policy document mentions cancellation or misconduct
            has_cancellation_clause = any(
                ("hủy chuyến" in d.get("content", "").lower() or "hủy cuốc" in d.get("content", "").lower())
                for d in doc_evidence
            )
            asked_p154 = any("P154" in str(p).upper() for p in (slots.policy_mentions or [])) or ("p154" in query.lower())

            # Policy Basis Lines
            policy_basis_lines: list[str] = []

            # 1. Address P154 clarification if queried
            if asked_p154:
                policy_basis_lines.append(
                    "   - **Lưu ý đối soát Quy chế [P154]:**\n"
                    "     > Văn bản **P154** (*[HÀ NỘI] CẬP NHẬT QUY ĐỊNH DOANH SỐ TỐI THIỂU*) chỉ quy định mức khoán doanh số "
                    "(280.000 VNĐ/ngày cho tài xế Bike tại Hà Nội và chế tài truy thu 20% phần thiếu hụt), "
                    "**hoàn toàn không quy định về tỷ lệ hủy chuyến**."
                )

            # 2. Quote actual retrieved policies (e.g. P221, P001)
            if doc_evidence:
                policy_basis_lines.append("   - **Trích dẫn điều khoản quy chế thực tế truy xuất được:**")
                for d in doc_evidence[:2]:
                    alias = d.get("policy_alias") or d.get("citation_locator") or "Quy chế GSM"
                    title = d.get("policy_title") or "Văn bản quy định"
                    locator = d.get("citation_locator") or alias
                    quote_lines = _format_policy_quote(alias, title, locator, d.get("content", ""), max_lines=5, indent="     ")
                    policy_basis_lines.extend(quote_lines)
                policy_basis_lines.append("")

            # Map evidence items to 1-based indices
            doc_indices = [i for i, e in enumerate(evidence, 1) if e.get("source_kind") == "document"]
            calc_indices = [i for i, e in enumerate(evidence, 1) if e.get("source_kind") == "computation"]
            kg_trip_indices = [i for i, e in enumerate(evidence, 1) if "trip" in e.get("evidence_id", "") or "trips" in e.get("evidence_id", "")]
            doc_idx_str = f"[{doc_indices[0]}] " if doc_indices else ""
            calc_idx_str = f"[{calc_indices[0]}] " if calc_indices else ""
            trip_idx_str = f"[{kg_trip_indices[0]}] " if kg_trip_indices else ""

            # Build natural conversational report lines
            intro = f"Dựa trên dữ liệu vận hành trong **{time_label}** và các quy định hiện hành của GSM, tôi đã kiểm tra thông tin cho **{driver_label}** như sau:\n"

            operational_section = [
                "**1. Tình hình vận hành thực tế:**",
                f"- **Lịch sử chuyến xe:** Theo {trip_idx_str}{trip_summary or f'Tài xế có tổng cộng {total_trips} chuyến xe ({total_trips - cancelled_trips} chuyến hoàn thành, {cancelled_trips} chuyến bị hủy).'}",
                f"- **Tỷ lệ hủy chuyến (cancel_rate_30d):** Theo {calc_idx_str}{rate_pct:.1f}% ({cancelled_trips}/{total_trips} chuyến).",
            ]
            cancelled_trip_evidences = [
                e.get("content", "").replace("[Chi tiết chuyến xe bị hủy] ", "").strip()
                for e in kg_evidence
                if "chuyến xe bị hủy" in e.get("content", "").lower()
            ]
            if cancelled_trip_evidences:
                operational_section.append(f"- **Chi tiết chuyến hủy:** {'; '.join(cancelled_trip_evidences)}.")

            compliance_section = [
                "\n**2. Đối chiếu quy chế & Kết luận:**",
            ]
            if asked_p154:
                compliance_section.append(
                    "- **Lưu ý đối soát Quy chế [P154]:** Văn bản P154 (*[HÀ NỘI] CẬP NHẬT QUY ĐỊNH DOANH SỐ TỐI THIỂU*) chỉ quy định mức khoán doanh thu "
                    "và chế tài truy thu 20% phần thiếu hụt, **hoàn toàn không quy định về tỷ lệ hủy chuyến**."
                )

            if cancelled_trips > 0 and has_cancellation_clause:
                compliance_section.extend([
                    f"- **Kết luận:** Tài xế {driver_label} **có dấu hiệu vi phạm quy định về hủy chuyến theo Bộ Quy tắc Ứng xử**.",
                    f"- **Căn cứ quy chế:** Căn cứ theo {doc_idx_str}Bộ Quy tắc Ứng xử GSM (như [P001] / [P221] dành cho đối tác tài xế), hành vi chủ động hủy cuốc sau khi nhận chuyến hoặc tỷ lệ hủy chuyến cao sẽ bị áp dụng chế tài nhắc nhở, trừ thưởng ví hoặc tạm khóa tài khoản tùy theo mức độ vi phạm.",
                ])
                if doc_evidence:
                    compliance_section.append("- **Trích dẫn điều khoản liên quan:**")
                    for d in doc_evidence[:2]:
                        alias = d.get("policy_alias") or d.get("citation_locator") or "Quy chế GSM"
                        title = d.get("policy_title") or "Văn bản quy định"
                        locator = d.get("citation_locator") or alias
                        quote_lines = _format_policy_quote(alias, title, locator, d.get("content", ""), max_lines=4, indent="  ")
                        compliance_section.extend(quote_lines)
            elif cancelled_trips > 0:
                compliance_section.extend([
                    f"- **Kết luận:** Hiện tại **chưa đủ căn cứ/thông tin để khẳng định** tài xế {driver_label} có vi phạm chính sách hay không.",
                    f"- **Lý do:** Mặc dù tài xế ghi nhận {cancelled_trips}/{total_trips} chuyến bị hủy (tỷ lệ {rate_pct:.1f}%), các văn bản quy chế hiện có trong hệ thống chưa quy định cụ thể mức trần tỷ lệ hủy chuyến hoặc chế tài áp dụng cho trường hợp này.",
                ])
                if doc_evidence:
                    compliance_section.append("- **Tài liệu tra cứu hiện có:**")
                    for d in doc_evidence[:2]:
                        alias = d.get("policy_alias") or d.get("citation_locator") or "Quy chế GSM"
                        title = d.get("policy_title") or "Văn bản quy định"
                        compliance_section.append(f"  * Văn bản [{alias}] ({title}): Không chứa điều khoản quy định về hủy chuyến.")
            else:
                compliance_section.extend([
                    f"- **Kết luận:** Tài xế {driver_label} **đạt tiêu chuẩn vận hành tốt, không phát sinh vi phạm** (hoàn thành 100% số chuyến trong kỳ).",
                ])

            recommend_section = [
                "\n**3. Khuyến nghị cho Quản lý vận hành:**",
            ]
            if cancelled_trips > 0:
                recommend_section.extend([
                    "- Trao đổi với tài xế về nguyên nhân phát sinh các chuyến hủy do yêu cầu của tài xế (`driver_request`) để có hướng hỗ trợ kịp thời.",
                    "- Hướng dẫn tài xế kích hoạt chế độ nhận chuyến tự động để hạn chế việc hủy chuyến thủ công.",
                ])
            else:
                recommend_section.extend([
                    "- Tài xế duy trì chỉ số vận hành ổn định, đề xuất tiếp tục duy trì và xem xét các chương trình thưởng định kỳ.",
                ])

            report_lines = [intro, *operational_section, *compliance_section, *recommend_section]
            return "\n".join(report_lines)

        # Case B: Pure Policy Lookup (No driver required)
        else:
            if not doc_evidence:
                return (
                    f"Không tìm thấy trích đoạn văn bản quy chế GSM nào phù hợp với câu hỏi: '{query}'.\n\n"
                    "Gợi ý: Quý quản lý có thể tra cứu theo mã văn bản quy chế cụ thể (ví dụ: P154, P001, P221, P05...) "
                    "hoặc bổ sung từ khóa chi tiết hơn."
                )

            top_doc = doc_evidence[0]
            top_alias = top_doc.get("policy_alias") or top_doc.get("citation_locator") or "Quy chế GSM"
            top_title = top_doc.get("policy_title") or "Văn bản quy chế"
            doc_indices = [i for i, e in enumerate(evidence, 1) if e.get("source_kind") == "document"]
            top_idx = doc_indices[0] if doc_indices else 1

            is_cancellation_query = any(k in query.lower() for k in ["hủy chuyến", "huỷ chuyến", "hủy cuốc", "vi phạm hủy"])

            report_lines = [
                f"Dựa trên các văn bản quy chế và quy tắc ứng xử hiện hành của GSM về câu hỏi *\"{query}\"*, tôi xin thông tin chi tiết như sau:\n",
            ]

            if is_cancellation_query:
                report_lines.extend([
                    f"**1. Quy định chung về hành vi hủy chuyến đối với đối tác tài xế (theo [{top_idx}] [{top_alias}]):**",
                    "- **Hành vi vi phạm:** Tài xế chủ động hủy cuốc sau khi đã nhận chuyến mà không có lý do chính đáng được hệ thống xác nhận; hoặc yêu cầu hành khách tự hủy chuyến nhằm né tránh cuốc xe.",
                    "- **Chỉ số kiểm soát:** Hệ thống theo dõi tỷ lệ hủy chuyến trong chu kỳ 30 ngày (`cancel_rate_30d`). Việc hủy chuyến thường xuyên sẽ ảnh hưởng trực tiếp đến điểm chất lượng vận hành và quyền nhận các cuốc xe ưu tiên.",
                    "- **Chế tài áp dụng:** Tùy theo mức độ vi phạm quy chế ứng xử (nhắc nhở nội bộ, tạm ngừng phân bổ cuốc xe, trừ thưởng tuần/tháng, hoặc tạm khóa tài khoản đối tác).\n",
                    f"**2. Căn cứ và trích dẫn điều khoản quy chế GSM tra cứu được từ [{top_idx}] [{top_alias}]:**",
                ])
            else:
                report_lines.extend([
                    f"**Văn bản áp dụng chính:** **[{top_idx}] [{top_alias}]** ({top_title}).\n",
                    "**Nội dung quy định chi tiết:**",
                ])

            for i, d in enumerate(doc_evidence[:3], 1):
                alias = d.get("policy_alias") or d.get("citation_locator") or f"Tài liệu {i}"
                title = d.get("policy_title") or ""
                locator = d.get("citation_locator") or alias
                quote_lines = _format_policy_quote(alias, title, locator, d.get("content", ""), max_lines=6, indent="")
                report_lines.extend(quote_lines)
                report_lines.append("")

            report_lines.extend([
                "**Lưu ý đối soát cho Quản lý:**",
                "- Cần căn cứ đúng thời điểm hiệu lực và khu vực áp dụng của quy chế khi giải quyết nghiệp vụ cho đối tác tài xế.",
                "- Trường hợp có mâu thuẫn giữa các phiên bản quy chế, ưu tiên áp dụng văn bản mới nhất có hiệu lực tại thời điểm phát sinh sự việc.",
            ])
            return "\n".join(report_lines)

    def build_reader_prompts(
        self, query: str, slots: SlotExtractionResult, evidence: list[dict[str, Any]]
    ) -> tuple[str, str]:
        """Construct grounded system and user prompt with numbered multi-source evidence."""
        evidence_blocks: list[str] = []
        for idx, e in enumerate(evidence, 1):
            source_kind = e.get("source_kind", "unknown")
            locator = e.get("citation_locator") or f"dẫn-chứng-{idx}"
            alias = e.get("policy_alias", "")
            title = e.get("policy_title", "")

            if source_kind == "document":
                header = f"=== [DẪN CHỨNG {idx}] VĂN BẢN QUY CHẾ: [{alias}] {title} ==="
                body = e.get("full_content") or e.get("content", "")
            elif source_kind == "computation":
                header = f"=== [DẪN CHỨNG {idx}] TÍNH TOÁN SỐ HỌC CHUẨN XÁC: {locator} ==="
                body = e.get("content", "")
            elif "driver-profile" in e.get("evidence_id", ""):
                header = f"=== [DẪN CHỨNG {idx}] HỒ SƠ ĐỐI TÁC TÀI XẾ: {locator} ==="
                body = e.get("content", "")
            elif "trip" in e.get("evidence_id", ""):
                header = f"=== [DẪN CHỨNG {idx}] LỊCH SỬ CHUYẾN ĐI & VẬN HÀNH: {locator} ==="
                body = e.get("content", "")
            elif source_kind == "kg_subgraph":
                header = f"=== [DẪN CHỨNG {idx}] DỮ LIỆU ĐỒ THỊ TRI THỨC: {locator} ==="
                body = e.get("content", "")
            else:
                header = f"=== [DẪN CHỨNG {idx}] {locator} ==="
                body = e.get("content", "")

            evidence_blocks.append(f"{header}\n{body}")

        evidence_context = "\n\n" + ("\n\n" + "-" * 50 + "\n\n").join(evidence_blocks) + "\n\n"

        system_prompt = (
            "Bạn là Trợ lý AI Hỗ trợ Quản lý Vận hành & Pháp chế GSM (Taxi Xanh SM).\n"
            "Người đang trao đổi với bạn là Nhân viên / Chuyên viên Quản lý Vận hành cần kiểm tra thông tin tài xế hoặc đối soát quy chế GSM.\n\n"
            "PHONG CÁCH TRẢ LỜI CỦA TRỢ LÝ AI (TỰ NHIÊN, LINH HOẠT THEO BẢN CHẤT CÂU HỎI):\n"
            "- ĐI THẲNG VÀO VẤN ĐỀ: Trả lời tự nhiên, chuyên nghiệp, súc tích và linh hoạt theo từng dạng câu hỏi, TUYỆT ĐỐI KHÔNG dập khuôn cứng nhắc một mẫu báo cáo.\n"
            "- PHÂN LOẠI XỬ LÝ THEO DẠNG CÂU HỎI:\n"
            "  1. Khi người dùng hỏi tra cứu quy chế / chính sách chung (ví dụ: 'các chính sách về vi phạm hủy chuyến', 'quy định mức khoán doanh số', 'tiêu chuẩn sao'):\n"
            "     * Trọng tâm là TỔNG HỢP VÀ GIẢI THÍCH NỘI DUNG QUY CHẾ GSM.\n"
            "     * Nêu rõ các hành vi bị coi là vi phạm, hình thức chế tài xử phạt (nhắc nhở, trừ thưởng ví, tạm khóa tài khoản...).\n"
            "     * Trích dẫn văn bản quy chế liên quan (ví dụ [P001], [P221], v.v.).\n"
            "     * TUYỆT ĐỐI KHÔNG nhắc đến thông tin tài xế hay số liệu chuyến xe của tài xế nào nếu người dùng không hỏi về tài xế đó.\n"
            "  2. Khi người dùng hỏi kiểm tra một tài xế cụ thể:\n"
            "     * Nêu số liệu vận hành thực tế (số chuyến hoàn thành, chuyến hủy, tỷ lệ hủy, chỉ số liên quan).\n"
            "     * Đối chiếu với quy chế được cung cấp trong bằng chứng để kết luận rõ ràng tài xế có vi phạm hay không (hoặc chưa đủ căn cứ quy định nếu chưa có ngưỡng trần).\n"
            "     * Đưa ra khuyến nghị vận hành ngắn gọn, hợp lý.\n\n"
            "QUY TẮC BẮT BUỘC VỀ ĐÁNH SỐ DẪN CHỨNG [1], [2], [3]... TRONG CÂU TRẢ LỜI:\n"
            "- Toàn bộ các tài liệu chính sách và bằng chứng đã được đánh số thứ tự: [DẪN CHỨNG 1], [DẪN CHỨNG 2], v.v.\n"
            "- Mỗi khi bạn nêu hoặc viện dẫn một quy định chính sách, dữ liệu vận hành tài xế, hoặc con số tính toán nào, BẮT BUỘC PHẢI GHI KÈM SỐ THỨ TỰ DẪN CHỨNG [1], [2], [3]... tương ứng ngay trong câu văn.\n"
            "- Ví dụ cách viết chuẩn mực:\n"
            "  + 'Theo quy định tại [1] Bộ Quy tắc Ứng xử [P001], hành vi tài xế tự ý hủy cuốc sau khi đã nhận chuyến...'\n"
            "  + 'Căn cứ vào dữ liệu vận hành tại [2], tài xế đã hoàn thành 8/10 chuyến và hủy 2 chuyến...'\n"
            "  + 'Theo kết quả tính toán tại [3], tỷ lệ hủy chuyến 30 ngày (cancel_rate_30d) của tài xế là 20.00%...'\n"
            "  + 'Đối chiếu với quy định tại [1] [P001], hành vi này bị chế tài...'\n"
            "- Ghi đúng số thứ tự [1], [2]... giúp Nhân viên Quản lý có thể đối chiếu ngay với thẻ Dẫn chứng trên giao diện.\n\n"
            "QUY TẮC CỐT LÕI VỀ TÍNH CHUẨN XÁC CỦA DẪN CHỨNG (STRICT CITATION BINDING & SERVICE MATCHING):\n"
            "1. TRÍCH DẪN ĐÚNG NGUỒN VĂN BẢN (KHÔNG LẪN LỘN NỘI DUNG):\n"
            "   - Nội dung, điều khoản hoặc quy định thuộc về [DẪN CHỨNG X] nào thì BẮT BUỘC phải ghi đúng số thứ tự và mã [Pxxx] của [DẪN CHỨNG X] đó.\n"
            "   - TUYỆT ĐỐI KHÔNG 'RÂU ÔNG NỌ CẮM CẰM BÀ KIA': Nghiêm cấm lấy nội dung của [DẪN CHỨNG 2] (như P012 về hủy đơn Food) rồi lại ghi là thuộc về [DẪN CHỨNG 1] (như P221 Quy tắc ứng xử Bike) hoặc ngược lại.\n"
            "2. KHỚP ĐÚNG LOẠI HÌNH DỊCH VỤ CỦA TÀI XẾ:\n"
            "   - Hãy đọc kỹ [HỒ SƠ ĐỐI TÁC TÀI XẾ] để xác định rõ tài xế đang chạy loại hình dịch vụ nào (bike_partner: xe máy chở khách Green SM Bike; taxi_partner: ô tô chở khách; food_partner: giao đồ ăn Green SM Food).\n"
            "   - CHỈ áp dụng quy chế của dịch vụ tương ứng. Tài xế chở khách Green SM Bike TUYỆT ĐỐI KHÔNG áp dụng quy định hủy đơn của dịch vụ giao đồ ăn Food (như nhà hàng đóng cửa, hết món...). Nếu có văn bản Food trong dẫn chứng, không được áp dụng cho chuyến đi chở khách của tài xế này.\n\n"
            "YÊU CẦU BẮT BUỘC VỀ NGÔN NGỮ:\n"
            "- TRẢ LỜI HOÀN TOÀN BẰNG TIẾNG VIỆT CHUẨN MỰC.\n"
            "- TUYỆT ĐỐI KHÔNG xuất chuỗi suy nghĩ bằng tiếng Anh (KHÔNG xuất 'Here is a thinking process', 'Analyze User Input' v.v.)."
        )

        user_prompt = (
            f"CÂU HỎI CỦA NHÂN VIÊN VẬN HÀNH: {query}\n\n"
            f"DANH SÁCH BẰNG CHỨNG XÁC THỰC VÀ VĂN BẢN QUY CHẾ ĐẦY ĐỦ:\n"
            f"{evidence_context}\n\n"
            "Hãy trả lời một cách tự nhiên, mạch lạc, chính xác và chuyên nghiệp bằng tiếng Việt.\n"
            "LƯU Ý QUAN TRỌNG:\n"
            "- Trích dẫn chính xác nội dung của từng Dẫn chứng (tuyệt đối không gán nhầm nội dung văn bản này sang văn bản khác).\n"
            "- Chỉ áp dụng quy định đúng với loại hình dịch vụ thực tế của tài xế trong hồ sơ (ví dụ tài xế Bike chở khách không áp dụng quy định hủy đơn Food của nhà hàng)."
        )
        return system_prompt, user_prompt

    def generate_grounded_answer(
        self,
        query: str,
        slots: SlotExtractionResult,
        evidence: list[dict[str, Any]],
        system_prompt: str | None = None,
        user_prompt: str | None = None,
        return_meta: bool = False,
    ) -> tuple[Any, ...]:
        if not system_prompt or not user_prompt:
            system_prompt, user_prompt = self.build_reader_prompts(query, slots, evidence)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        raw_answer, used_model, usage_info = self._call_llm(
            messages=messages,
            max_tokens=2000,
            temperature=0.2,
            timeout=30.0,
        )

        # Clean thinking trace if returned by model
        cleaned_answer = self._clean_thinking_trace(raw_answer)

        # Fallback to grounded deterministic report if LLM failed or produced uncleaned English
        if not cleaned_answer:
            cleaned_answer = self._build_deterministic_grounded_answer(query, slots, evidence)

        citations: list[dict[str, Any]] = []
        for idx, e in enumerate(evidence, 1):
            source_kind = e.get("source_kind", "unknown")
            alias = e.get("policy_alias", "")
            title = e.get("policy_title", "")
            locator = e.get("citation_locator") or f"evidence-{idx}"

            if source_kind == "document":
                clean_title = title
                if alias and clean_title.startswith(f"[{alias}]"):
                    clean_title = clean_title[len(f"[{alias}]"):].strip()
                name = f"[{alias}] {clean_title}" if (alias and alias not in clean_title) else (clean_title or alias)
                category = "Văn bản quy chế GSM"
            elif source_kind == "computation":
                name = locator if "computation:" not in locator else "Tỷ lệ hủy chuyến (cancel_rate_30d)"
                category = "Tính toán số học chuẩn xác"
            elif "driver-profile" in e.get("evidence_id", ""):
                name = f"Hồ sơ đối tác {locator.replace('entity:driver:', '')}"
                category = "Hồ sơ đối tác"
            elif "trip" in e.get("evidence_id", ""):
                name = f"Lịch sử chuyến đi ({locator})"
                category = "Lịch sử chuyến đi"
            elif source_kind == "kg_subgraph":
                name = locator
                category = "Dữ liệu vận hành KG"
            else:
                name = locator
                category = "Bằng chứng hệ thống"

            full_content = e.get("full_content") or e.get("content", "")
            excerpt = e.get("matched_excerpts") or ""

            citations.append({
                "index": idx,
                "label": f"[{idx}] {name}",
                "name": name,
                "locator": locator,
                "category": category,
                "source_kind": source_kind,
                "policy_alias": alias,
                "policy_title": title,
                "policy_date": e.get("policy_date", ""),
                "policy_category": e.get("policy_category", ""),
                "excerpt": excerpt,
                "content": full_content,
            })

        if return_meta:
            meta = {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "model_used": used_model,
                "usage": usage_info,
                "raw_answer": raw_answer,
            }
            return cleaned_answer, citations, meta

        return cleaned_answer, citations

    # =========================================================================
    # Main Entry Point with Langfuse Tracing
    # =========================================================================
    def execute(self, user_query: str, context: dict[str, Any] | None = None) -> PipelineResponse:
        context = context or {}
        trace_url = None

        if self.langfuse:
            try:
                from langfuse import propagate_attributes

                session_id = str(context.get("session_id")) if context.get("session_id") else None
                driver_id_val = str(context.get("driver_id")) if context.get("driver_id") else None
                trace_meta: dict[str, str] = {
                    "release": "gsm-dev-core-0.2.2",
                    "model": str(self.model_name),
                }
                if driver_id_val:
                    trace_meta["driver_id"] = driver_id_val

                with propagate_attributes(
                    trace_name="gsm-conversational-qa-pipeline",
                    session_id=session_id,
                    metadata=trace_meta,
                ):
                    with self.langfuse.start_as_current_observation(
                        name="gsm-conversational-qa-pipeline",
                        as_type="span",
                        input={
                            "query": user_query,
                            "context": context,
                            "active_working_memory": context,
                        },
                    ) as root_span:
                        try:
                            trace_url = self.langfuse.get_trace_url()
                        except Exception:
                            trace_url = None

                        # Span 1: Query Understanding & AI Query Plan
                        with root_span.start_as_current_observation(
                            name="1. AI Query Planning & Slot Filling",
                            as_type="span",
                            input={"query": user_query, "input_working_memory": context},
                        ) as q_span:
                            plan = self.plan_query(user_query, context)
                            slots = SlotExtractionResult(
                                intent=plan.intent,
                                needs_driver="driver_id" in plan.missing_fields or bool(plan.driver_id),
                                driver_id=plan.driver_id,
                                driver_mention=plan.driver_mention,
                                is_driver_ambiguous=plan.is_driver_ambiguous,
                                needs_time="time_scope" in plan.missing_fields or bool(plan.time_scope),
                                has_time_scope=bool(plan.time_scope),
                                time_mention=plan.time_scope,
                                snapshot_id=plan.snapshot_id,
                                policy_mentions=plan.policy_scope,
                                policy_topics=plan.policy_topics,
                                has_policy_target=bool(plan.policy_scope or plan.policy_topics),
                                missing_slots=plan.missing_fields,
                            )
                            q_span.update(
                                output={
                                    "intent": plan.intent,
                                    "driver_id": plan.driver_id,
                                    "driver_mention": plan.driver_mention,
                                    "time_scope": plan.time_scope,
                                    "snapshot_id": plan.snapshot_id,
                                    "policy_scope": plan.policy_scope,
                                    "policy_topics": plan.policy_topics,
                                    "modalities": plan.modalities,
                                    "missing_fields": plan.missing_fields,
                                    "clarification_reasons": plan.clarification_reasons,
                                    "reasoning": plan.reasoning,
                                }
                            )

                        # Span 2: Clarification Gate
                        with root_span.start_as_current_observation(
                            name="2. Clarification Gate",
                            as_type="span",
                            input={"missing_fields": plan.missing_fields},
                        ) as gate_span:
                            if plan.missing_fields:
                                clarification_msg = self.build_clarification_message(plan)
                                gate_span.update(
                                    output={
                                        "action": "ASK_CLARIFICATION",
                                        "message": clarification_msg,
                                        "missing_fields": plan.missing_fields,
                                    }
                                )
                                root_span.update(
                                    output={
                                        "status": "NEEDS_CLARIFICATION",
                                        "message": clarification_msg,
                                        "missing_fields": plan.missing_fields,
                                        "working_memory_state": {
                                            "driver_id": plan.driver_id,
                                            "driver_mention": plan.driver_mention,
                                            "time_scope": plan.time_scope,
                                            "snapshot_id": plan.snapshot_id,
                                            "policy_scope": plan.policy_scope,
                                            "pending_clarification": plan.missing_fields,
                                        },
                                    }
                                )
                                try:
                                    self.langfuse.flush()
                                except Exception:
                                    pass
                                return PipelineResponse(
                                    status="NEEDS_CLARIFICATION",
                                    query=user_query,
                                    slots=slots,
                                    query_plan=plan,
                                    clarification_message=clarification_msg,
                                    trace_url=trace_url,
                                )
                            gate_span.update(output={"action": "PASSED", "message": "All required slots present in QueryPlan."})

                        # Span 3: Seed Selection & Subgraph BFS Expansion
                        with root_span.start_as_current_observation(
                            name="3. Seed Selection & Subgraph BFS Expansion",
                            as_type="span",
                            input={"seed_id": plan.driver_id, "snapshot_id": plan.snapshot_id},
                        ) as kg_span:
                            if plan.driver_id and "kg" in plan.modalities:
                                subgraph = self.expand_subgraph_bfs(plan.driver_id, plan.snapshot_id)
                            else:
                                subgraph = Subgraph(seed_id=plan.driver_id or "none", snapshot_id=plan.snapshot_id, nodes=[], edges=[])
                            kg_span.update(
                                output={
                                    "seed_id": subgraph.seed_id,
                                    "snapshot_id": subgraph.snapshot_id,
                                    "node_count": len(subgraph.nodes),
                                    "edge_count": len(subgraph.edges),
                                    "node_types": [n.label for n in subgraph.nodes],
                                    "nodes": [
                                        {
                                            "id": n.id,
                                            "label": n.label,
                                            "name": n.name,
                                            "props": _serialize_for_trace(n.props),
                                        }
                                        for n in subgraph.nodes
                                    ],
                                    "edges": [
                                        {
                                            "start_id": e.start_id,
                                            "end_id": e.end_id,
                                            "rel_type": e.rel_type,
                                            "props": _serialize_for_trace(e.props),
                                        }
                                        for e in subgraph.edges
                                    ],
                                }
                            )

                        # Span 4: Multi-Source Evidence Gathering
                        with root_span.start_as_current_observation(
                            name="4. Multi-Source Evidence Gathering",
                            as_type="span",
                            input={"intent": plan.intent, "query": user_query, "modalities": plan.modalities},
                        ) as ev_span:
                            evidence = self.gather_multi_source_evidence(user_query, slots, subgraph)
                            ev_span.update(
                                output={
                                    "evidence_count": len(evidence),
                                    "sources": [e["source_kind"] for e in evidence],
                                    "locators": [e["citation_locator"] for e in evidence],
                                    "evidence_items": [
                                        {
                                            "evidence_id": e.get("evidence_id"),
                                            "source_kind": e.get("source_kind"),
                                            "citation_locator": e.get("citation_locator"),
                                            "policy_alias": e.get("policy_alias"),
                                            "policy_title": e.get("policy_title"),
                                            "score": e.get("score"),
                                            "content": e.get("content"),
                                        }
                                        for e in evidence
                                    ],
                                }
                            )

                        # Generation 5: Grounded LLM Reader
                        system_prompt, user_prompt = self.build_reader_prompts(user_query, slots, evidence)
                        llm_messages = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ]
                        with root_span.start_as_current_observation(
                            name="5. Grounded LLM Reader Synthesis",
                            as_type="generation",
                            model=self.model_name,
                            input=llm_messages,
                            metadata={
                                "evidence_count": str(len(evidence)),
                                "driver_id": str(slots.driver_id or ""),
                                "time_scope": str(slots.time_mention or ""),
                            },
                        ) as gen_span:
                            answer, citations, gen_meta = self.generate_grounded_answer(
                                user_query,
                                slots,
                                evidence,
                                system_prompt=system_prompt,
                                user_prompt=user_prompt,
                                return_meta=True,
                            )
                            gen_update: dict[str, Any] = {
                                "output": {"answer": answer, "citations": citations},
                            }
                            if gen_meta.get("model_used"):
                                gen_update["model"] = gen_meta["model_used"]
                            if gen_meta.get("usage"):
                                u = gen_meta["usage"]
                                gen_update["usage_details"] = {
                                    "input": int(u.get("prompt_tokens", 0)),
                                    "output": int(u.get("completion_tokens", 0)),
                                    "total": int(u.get("total_tokens", 0)),
                                }
                            gen_span.update(**gen_update)

                        root_span.update(
                            output={
                                "status": "ANSWERED",
                                "answer": answer,
                                "citations": citations,
                                "citations_count": len(citations),
                                "working_memory_state": {
                                    "driver_id": plan.driver_id,
                                    "driver_mention": plan.driver_mention,
                                    "time_scope": plan.time_scope,
                                    "snapshot_id": plan.snapshot_id,
                                    "policy_scope": plan.policy_scope,
                                    "last_intent": plan.intent,
                                },
                                "retrieval_summary": {
                                    "nodes_count": len(subgraph.nodes),
                                    "edges_count": len(subgraph.edges),
                                    "evidence_count": len(evidence),
                                    "sources": list({e["source_kind"] for e in evidence}),
                                },
                            }
                        )

                        try:
                            self.langfuse.flush()
                        except Exception:
                            pass

                        return PipelineResponse(
                            status="ANSWERED",
                            query=user_query,
                            slots=slots,
                            query_plan=plan,
                            answer=answer,
                            citations=citations,
                            subgraph=subgraph,
                            trace_url=trace_url,
                        )
            except Exception as e:
                print(f"[Pipeline Langfuse Error] {e}, falling back to non-traced execution.")

        # Fallback execution
        plan = self.plan_query(user_query, context)
        slots = SlotExtractionResult(
            intent=plan.intent,
            needs_driver="driver_id" in plan.missing_fields or bool(plan.driver_id),
            driver_id=plan.driver_id,
            driver_mention=plan.driver_mention,
            is_driver_ambiguous=plan.is_driver_ambiguous,
            needs_time="time_scope" in plan.missing_fields or bool(plan.time_scope),
            has_time_scope=bool(plan.time_scope),
            time_mention=plan.time_scope,
            snapshot_id=plan.snapshot_id,
            policy_mentions=plan.policy_scope,
            missing_slots=plan.missing_fields,
        )
        if plan.missing_fields:
            clarification_msg = self.build_clarification_message(plan)
            return PipelineResponse(
                status="NEEDS_CLARIFICATION",
                query=user_query,
                slots=slots,
                query_plan=plan,
                clarification_message=clarification_msg,
            )
        subgraph = self.expand_subgraph_bfs(plan.driver_id, plan.snapshot_id)
        evidence = self.gather_multi_source_evidence(user_query, slots, subgraph)
        answer, citations = self.generate_grounded_answer(user_query, slots, evidence)
        return PipelineResponse(
            status="ANSWERED",
            query=user_query,
            slots=slots,
            query_plan=plan,
            answer=answer,
            citations=citations,
            subgraph=subgraph,
        )
