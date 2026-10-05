"""Mock data, sample fixtures, and mock retriever utilities for testing.

This module provides mock candidates, evidence bundles, sample graph entities,
sample policy chunks, and MockDenseRetriever/MockReaderProvider for unit and
integration tests.

THIS MODULE MUST NEVER BE IMPORTED OR ACCESSED BY RUNTIME PRODUCTION CODE.
"""

from __future__ import annotations

import hashlib
from typing import Any, Mapping, Sequence

from gsm_memory.retrieval.semantic_seed import GraphEntitySeed


# ==============================================================================
# 1. SAMPLE GRAPH ENTITIES (For Testing Semantic Seed Selection)
# ==============================================================================

SAMPLE_GRAPH_ENTITIES: list[GraphEntitySeed] = [
    GraphEntitySeed(
        entity_id="99e70ebe-18cd-57a3-a036-cf0ff1989861",
        kind="driver",
        name="Nguyễn Văn A",
        description="Tài xế Nguyễn Văn A mã nhân viên DRV-001, xe điện VinFast VF e34, hạng Kim Cương, hoạt động tại Hà Nội.",
        attributes={"driver_code": "DRV-001", "tier": "Kim Cương", "city": "Hà Nội", "vehicle_model": "VF e34"},
    ),
    GraphEntitySeed(
        entity_id="c499f934-bfe1-5509-a578-afb09cee357c",
        kind="driver",
        name="Trần Văn B",
        description="Tài xế Trần Văn B mã nhân viên DRV-002, xe điện VinFast VF 8, hạng Vàng, hoạt động tại TP Hồ Chí Minh.",
        attributes={"driver_code": "DRV-002", "tier": "Vàng", "city": "TP Hồ Chí Minh", "vehicle_model": "VF 8"},
    ),
    GraphEntitySeed(
        entity_id="3b0b7be7-b553-5d99-9528-4a07ca4f1567",
        kind="driver",
        name="Lê Thị C",
        description="Tài xế Lê Thị C mã nhân viên DRV-003, xe điện VinFast VF 5 Plus, hạng Bạc, hoạt động tại Đà Nẵng.",
        attributes={"driver_code": "DRV-003", "tier": "Bạc", "city": "Đà Nẵng", "vehicle_model": "VF 5"},
    ),
    GraphEntitySeed(
        entity_id="inc-type-tire-puncture",
        kind="incident_type",
        name="Sự cố Nổ lốp / Rách lốp xe",
        description="Sự cố kỹ thuật nổ lốp, rách vỏ bánh xe hỏng bất khả kháng trên đường, được tổng đài GSM miễn trừ trách nhiệm hủy cuốc.",
        attributes={"exemption_eligible": True, "category": "technical"},
    ),
    GraphEntitySeed(
        entity_id="inc-type-app-gps-failure",
        kind="incident_type",
        name="Lỗi Thiết bị Định vị GPS",
        description="Sự cố kỹ thuật thiết bị giám sát hành trình không bắt được tín hiệu GPS hoặc mất kết nối mạng di động 4G.",
        attributes={"exemption_eligible": False, "category": "device"},
    ),
    GraphEntitySeed(
        entity_id="inc-type-client-no-show",
        kind="incident_type",
        name="Khách Không Đến Điểm Đón",
        description="Hành khách không có mặt tại điểm hẹn đón xe quá thời gian quy định hoặc tự ý hủy chuyến đi.",
        attributes={"exemption_eligible": True, "category": "passenger"},
    ),
    GraphEntitySeed(
        entity_id="trip-105-cancelled",
        kind="trip",
        name="Chuyến xe T-105 bị hủy",
        description="Chuyến xe T-105 của tài xế Nguyễn Văn A bị hủy do sự cố hỏng xe kỹ thuật ngày 15/09/2026.",
        attributes={"status": "cancelled", "driver_id": "99e70ebe-18cd-57a3-a036-cf0ff1989861"},
    ),
]


# ==============================================================================
# 2. SAMPLE POLICY DOCUMENT CHUNKS (For Testing Document Search)
# ==============================================================================

SAMPLE_POLICY_CHUNKS: list[dict[str, Any]] = [
    {
        "chunk_id": "chunk-p154-sec5",
        "doc_id": "P154",
        "title": "Quy chế thưởng phạt GSM - Điều 5 Tiêu chuẩn Kim Cương",
        "content": "Điều 5: Tài xế đạt chuẩn hạng Kim Cương phải duy trì tỷ lệ nhận chuyến (AR) >= 90% và tỷ lệ hủy chuyến (CR) <= 10% trong chu kỳ 30 ngày gần nhất.",
        "clause_ref": "Điều 5",
    },
    {
        "chunk_id": "chunk-p154-sec8",
        "doc_id": "P154",
        "title": "Quy chế thưởng phạt GSM - Điều 8 Miễn trừ hỏng xe",
        "content": "Điều 8: Các chuyến đi bị hủy do lỗi xe hỏng kỹ thuật bất khả kháng được xác nhận bởi tổng đài sẽ không tính vào tỷ lệ hủy chuyến của tài xế.",
        "clause_ref": "Điều 8",
    },
    {
        "chunk_id": "chunk-p151-sec3",
        "doc_id": "P151",
        "title": "Quy chế doanh số tối thiểu GSM Hà Nội",
        "content": "Điều 3: Doanh số tối thiểu mỗi ngày vận doanh tại khu vực Hà Nội là 600.000 VNĐ.",
        "clause_ref": "Điều 3",
    },
    {
        "chunk_id": "chunk-p05-sec12",
        "doc_id": "P05",
        "title": "Chế tài xử phạt vi phạm thiết bị GPS",
        "content": "Điều 12: Hành vi không bật đèn định vị hoặc tắt thiết bị GPS giám sát hành trình bị xử phạt mức 200.000 VNĐ.",
        "clause_ref": "Điều 12",
    },
    {
        "chunk_id": "chunk-p23-sec12",
        "doc_id": "P23",
        "title": "Quy định kỷ luật an toàn phương tiện GSM",
        "content": "Điều 12: Hành vi tắt định vị xe hoặc che chắn camera an ninh bị xử phạt 500.000 VNĐ và tạm dừng nhận cuốc 24h.",
        "clause_ref": "Điều 12",
    },
]


# ==============================================================================
# 3. MOCK CANDIDATES (Input for Evidence Selection & Reranking)
# Covers all 6 source kinds: document, definition, entity_catalog, kg, coverage, computation
# ==============================================================================

MOCK_CANDIDATES: list[dict[str, Any]] = [
    # Document Chunks (Policy Articles)
    {
        "evidence_id": "cand-doc-p154-sec5",
        "source_id": "P154",
        "source_kind": "document",
        "content": "Điều 5 (Quy chế thưởng phạt GSM): Tài xế đạt chuẩn hạng Kim Cương phải duy trì tỷ lệ nhận chuyến (AR) >= 90% và tỷ lệ hủy chuyến (CR) <= 10% trong chu kỳ 30 ngày.",
        "source_locator": {
            "locator_type": "document_clause",
            "document_revision_id": "P154",
            "clause_refs": [{"clause_id": "Điều 5", "label": "Tiêu chuẩn hạng Kim Cương"}],
        },
        "score": 0.94,
        "rank": 1,
        "token_cost": 55,
    },
    {
        "evidence_id": "cand-doc-p154-sec8",
        "source_id": "P154",
        "source_kind": "document",
        "content": "Điều 8: Các chuyến đi bị hủy do lỗi xe hỏng kỹ thuật được xác nhận bởi tổng đài sẽ không tính vào tỷ lệ hủy chuyến của tài xế.",
        "source_locator": {
            "locator_type": "document_clause",
            "document_revision_id": "P154",
            "clause_refs": [{"clause_id": "Điều 8", "label": "Miễn trừ lỗi hủy"}],
        },
        "score": 0.88,
        "rank": 2,
        "token_cost": 45,
    },
    {
        "evidence_id": "cand-doc-p151-sec3",
        "source_id": "P151",
        "source_kind": "document",
        "content": "Điều 3: Doanh số tối thiểu mỗi ngày vận doanh tại khu vực Hà Nội là 600.000 VNĐ.",
        "source_locator": {
            "locator_type": "document_clause",
            "document_revision_id": "P151",
            "clause_refs": [{"clause_id": "Điều 3", "label": "Doanh số tối thiểu"}],
        },
        "score": 0.76,
        "rank": 3,
        "token_cost": 38,
    },

    # Definitions
    {
        "evidence_id": "cand-def-cr-30d",
        "source_id": "627ed991-2f8d-50a8-bd87-01cb73f4ca2a",
        "source_kind": "definition",
        "content": "Định nghĩa tỷ lệ hủy chuyến 30 ngày (cancel_rate_30d): Là tỷ số giữa tổng số chuyến tài xế hủy hợp lệ trên tổng số chuyến được phát trong 30 ngày gần nhất.",
        "source_locator": {
            "locator_type": "coverage_artifact",
            "artifact_id": "627ed991-2f8d-50a8-bd87-01cb73f4ca2a",
        },
        "score": 0.91,
        "rank": 1,
        "token_cost": 42,
    },
    {
        "evidence_id": "cand-def-opday",
        "source_id": "627ed991-2f8d-50a8-bd87-01cb73f4ca2a",
        "source_kind": "definition",
        "content": "Định nghĩa ngày vận doanh (opday): Ngày có ít nhất 1 cuốc xe hoàn thành hoặc thời gian online trên app >= 4 giờ.",
        "source_locator": {
            "locator_type": "coverage_artifact",
            "artifact_id": "627ed991-2f8d-50a8-bd87-01cb73f4ca2a",
        },
        "score": 0.72,
        "rank": 2,
        "token_cost": 35,
    },

    # Entity Catalog (Driver Profiles)
    {
        "evidence_id": "cand-ent-driver-001",
        "source_id": "99e70ebe-18cd-57a3-a036-cf0ff1989861",
        "source_kind": "entity_catalog",
        "content": "Hồ sơ tài xế: Nguyễn Văn A (Mã định danh: DRV-001), Hạng hiện tại: Vàng, Khu vực hoạt động: Hà Nội, Trạng thái: Đang hoạt động.",
        "source_locator": {
            "locator_type": "entity_catalog",
            "entity_id": "99e70ebe-18cd-57a3-a036-cf0ff1989861",
        },
        "score": 0.95,
        "rank": 1,
        "token_cost": 40,
    },

    # Temporal Knowledge Graph Edges (Trips, Incidents, Ledger assertions)
    {
        "evidence_id": "cand-kg-trip-101",
        "source_id": "edge-trip-101",
        "source_kind": "kg",
        "content": "Chuyến đi T-101 (2026-09-14 08:30:00 UTC): Khách đặt chuyến 15km, trạng thái: Hoàn thành, Doanh thu: 185.000 VNĐ, Đánh giá: 5 sao.",
        "source_locator": {
            "locator_type": "ledger_assertion",
            "assertion_id": "assert-trip-101",
        },
        "score": 0.85,
        "rank": 1,
        "token_cost": 38,
    },
    {
        "evidence_id": "cand-kg-incident-202",
        "source_id": "edge-incident-202",
        "source_kind": "kg",
        "content": "Sự cố INC-202 (2026-09-15 14:10:00 UTC): Chuyến đi T-105 bị hủy bởi tài xế do xe nổ lốp, đã có biên bản xác nhận tổng đài GSM miễn trừ trách nhiệm.",
        "source_locator": {
            "locator_type": "ledger_assertion",
            "assertion_id": "assert-incident-202",
        },
        "score": 0.89,
        "rank": 2,
        "token_cost": 44,
    },

    # Coverage Artifacts
    {
        "evidence_id": "cand-cov-drv001-sep",
        "source_id": "cov-art-001-sep2026",
        "source_kind": "coverage",
        "content": "Chứng nhận bao phủ dữ liệu (Coverage): 100% chuyến đi và sự cố của tài xế DRV-001 từ 2026-08-15 đến 2026-09-15 đã được đối soát đầy đủ vào sổ cái.",
        "source_locator": {
            "locator_type": "coverage_artifact",
            "artifact_id": "cov-art-001-sep2026",
        },
        "score": 0.82,
        "rank": 1,
        "token_cost": 36,
    },

    # Rational Exact Computations
    {
        "evidence_id": "cand-comp-cr-drv001",
        "source_id": "comp-cr-drv001",
        "source_kind": "computation",
        "content": "Kết quả tính toán chuẩn xác số học: Tỷ lệ hủy chuyến 30 ngày (cancel_rate_30d) của DRV-001 = 3/50 (tương đương 6.0%), nằm dưới ngưỡng trần quy định 10%.",
        "source_locator": {
            "locator_type": "computation",
            "coverage_artifact_id": "comp-cr-drv001",
        },
        "score": 0.96,
        "rank": 1,
        "token_cost": 45,
    },
]


# ==============================================================================
# 4. MOCK SCENARIOS (Input for Downstream Reader Agent)
# ==============================================================================

MOCK_SCENARIOS: dict[str, dict[str, Any]] = {
    "policy_lookup": {
        "query": {
            "query_id": "mock-q-01",
            "query": "Theo quy chế thưởng phạt P154, tiêu chuẩn để duy trì hạng Kim Cương yêu cầu tỷ lệ nhận chuyến và hủy chuyến như thế nào?",
            "entity_refs": ["99e70ebe-18cd-57a3-a036-cf0ff1989861"],
            "time_scope": {"mode": "current"},
            "known_as_of": "2026-09-17T12:00:00Z",
            "public_snapshot_id": "snap-public-01",
            "application_context": {"source_snapshot_refs": ["P154"]},
        },
        "selected_evidence": [
            MOCK_CANDIDATES[0],  # P154 Điều 5
        ],
        "expected_status": "answered",
        "mock_llm_response": {
            "status": "answered",
            "answer": "Theo Điều 5 Quy chế thưởng phạt GSM (P154), để duy trì hạng Kim Cương, tài xế phải đạt tỷ lệ nhận chuyến (AR) từ 90% trở lên và tỷ lệ hủy chuyến (CR) không vượt quá 10% trong chu kỳ 30 ngày.",
            "citations": [
                {
                    "evidence_id": "cand-doc-p154-sec5",
                    "quote": "Tài xế đạt chuẩn hạng Kim Cương phải duy trì tỷ lệ nhận chuyến (AR) >= 90% và tỷ lệ hủy chuyến (CR) <= 10% trong chu kỳ 30 ngày.",
                }
            ],
        },
    },

    "complex_driver_reasoning": {
        "query": {
            "query_id": "mock-q-02",
            "query": "Tài xế Nguyễn Văn A vừa có một cuốc xe bị hủy do hỏng xe, vậy tỷ lệ hủy chuyến 30 ngày hiện tại có bị vượt trần quy định của hạng Kim Cương không?",
            "entity_refs": ["99e70ebe-18cd-57a3-a036-cf0ff1989861"],
            "time_scope": {"mode": "current"},
            "known_as_of": "2026-09-17T12:00:00Z",
            "public_snapshot_id": "snap-public-01",
            "application_context": {"source_snapshot_refs": ["P154"]},
        },
        "selected_evidence": [
            MOCK_CANDIDATES[0],  # P154 Điều 5 (Quy chế Kim Cương)
            MOCK_CANDIDATES[1],  # P154 Điều 8 (Miễn trừ lỗi hỏng xe)
            MOCK_CANDIDATES[5],  # Hồ sơ tài xế
            MOCK_CANDIDATES[7],  # Sự cố xe nổ lốp có miễn trừ
            MOCK_CANDIDATES[9],  # Computation CR = 6%
        ],
        "expected_status": "answered",
        "mock_llm_response": {
            "status": "answered",
            "answer": "Tài xế Nguyễn Văn A không bị vượt trần tỷ lệ hủy chuyến. Theo kết quả tính toán, tỷ lệ hủy chuyến 30 ngày hiện tại là 3/50 (6.0%), thấp hơn mức trần 10% quy định tại Điều 5 văn bản P154. Ngoài ra, chuyến xe bị hủy do sự cố kỹ thuật xe nổ lốp đã được tổng đài xác nhận miễn trừ theo Điều 8 văn bản P154.",
            "citations": [
                {
                    "evidence_id": "cand-doc-p154-sec5",
                    "quote": "Tài xế đạt chuẩn hạng Kim Cương phải duy trì tỷ lệ nhận chuyến (AR) >= 90% và tỷ lệ hủy chuyến (CR) <= 10% trong chu kỳ 30 ngày.",
                },
                {
                    "evidence_id": "cand-comp-cr-drv001",
                    "quote": "Tỷ lệ hủy chuyến 30 ngày (cancel_rate_30d) của DRV-001 = 3/50 (tương đương 6.0%), nằm dưới ngưỡng trần quy định 10%.",
                },
                {
                    "evidence_id": "cand-doc-p154-sec8",
                    "quote": "Các chuyến đi bị hủy do lỗi xe hỏng kỹ thuật được xác nhận bởi tổng đài sẽ không tính vào tỷ lệ hủy chuyến của tài xế.",
                },
            ],
        },
    },

    "insufficient_evidence": {
        "query": {
            "query_id": "mock-q-03",
            "query": "Tài xế Trần Văn B mã DRV-999 có đủ điều kiện nhận thưởng tuần này theo doanh số không?",
            "entity_refs": ["mock-drv-999"],
            "time_scope": {"mode": "current"},
            "known_as_of": "2026-09-17T12:00:00Z",
            "public_snapshot_id": "snap-public-01",
            "application_context": {"source_snapshot_refs": ["P154"]},
        },
        "selected_evidence": [],
        "expected_status": "insufficient_evidence",
        "mock_llm_response": {
            "status": "insufficient_evidence",
            "answer": "Hệ thống không tìm thấy dữ liệu vận hành hoặc chuyến đi của tài xế mã DRV-999 trong thời gian yêu cầu, do đó không đủ căn cứ để xác định điều kiện nhận thưởng.",
            "citations": [],
        },
    },

    "unresolved_conflict": {
        "query": {
            "query_id": "mock-q-04",
            "query": "Hạn mức phạt đối với lỗi không bật đèn định vị theo quy chế hiện hành là bao nhiêu?",
            "entity_refs": [],
            "time_scope": {"mode": "current"},
            "known_as_of": "2026-09-17T12:00:00Z",
            "public_snapshot_id": "snap-public-01",
            "application_context": {},
        },
        "selected_evidence": [
            {
                "evidence_id": "conflict-doc-a",
                "source_id": "P05",
                "source_kind": "document",
                "content": "Điều 12 (Thông báo A): Lỗi không bật đèn định vị xử phạt 200.000 VNĐ.",
                "source_locator": {"locator_type": "document_clause", "document_revision_id": "P05", "clause_refs": [{"clause_id": "Điều 12"}]},
                "score": 0.85,
                "token_cost": 25,
            },
            {
                "evidence_id": "conflict-doc-b",
                "source_id": "P23",
                "source_kind": "document",
                "content": "Điều 12 (Thông báo B): Lỗi không bật đèn định vị xử phạt 500.000 VNĐ và tạm dừng nhận cuốc 24h.",
                "source_locator": {"locator_type": "document_clause", "document_revision_id": "P23", "clause_refs": [{"clause_id": "Điều 12"}]},
                "score": 0.85,
                "token_cost": 30,
            },
        ],
        "expected_status": "unresolved_conflict",
        "mock_llm_response": {
            "status": "unresolved_conflict",
            "answer": "Có xung đột dữ liệu giữa hai văn bản quy định cùng hiệu lực: Văn bản P05 quy định phạt 200.000 VNĐ, trong khi Văn bản P23 quy định phạt 500.000 VNĐ kèm tạm dừng 24h. Cần đối soát thêm với quản lý vận hành.",
            "citations": [
                {
                    "evidence_id": "conflict-doc-a",
                    "quote": "Lỗi không bật đèn định vị xử phạt 200.000 VNĐ.",
                },
                {
                    "evidence_id": "conflict-doc-b",
                    "quote": "Lỗi không bật đèn định vị xử phạt 500.000 VNĐ và tạm dừng nhận cuốc 24h.",
                },
            ],
        },
    },
}


# ==============================================================================
# 5. MOCK DENSE RETRIEVER
# ==============================================================================

class MockDenseRetriever:
    """Mock dense retriever simulating semantic similarity scoring for tests."""

    def __init__(self, dimension: int = 128, candidates: Sequence[dict[str, Any]] | None = None) -> None:
        self.dimension = dimension
        self.corpus = list(candidates) if candidates is not None else list(MOCK_CANDIDATES)

    def embed_text(self, text: str) -> list[float]:
        raw_hash = hashlib.sha256(text.encode("utf-8")).digest()
        vec = []
        for i in range(self.dimension):
            byte_val = raw_hash[i % len(raw_hash)]
            vec.append((byte_val - 128) / 128.0)
        norm = (sum(x * x for x in vec) ** 0.5) or 1.0
        return [x / norm for x in vec]

    def similarity(self, vec_a: list[float], vec_b: list[float]) -> float:
        return sum(a * b for a, b in zip(vec_a, vec_b))

    def retrieve(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        q_vec = self.embed_text(query)
        q_words = set(query.lower().split())

        scored: list[tuple[float, dict[str, Any]]] = []
        for item in self.corpus:
            content = item.get("content", "")
            d_vec = self.embed_text(content)
            cos_sim = self.similarity(q_vec, d_vec)

            content_words = set(content.lower().split())
            overlap = len(q_words & content_words) / max(1, len(q_words))
            final_score = round(0.7 * cos_sim + 0.3 * overlap, 4)
            scored.append((final_score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for rank, (score, item) in enumerate(scored[:top_k], start=1):
            cloned = dict(item)
            cloned["dense_score"] = score
            cloned["dense_rank"] = rank
            results.append(cloned)
        return results


# ==============================================================================
# 6. MOCK READER PROVIDER
# ==============================================================================

class MockReaderProvider:
    """Mock LLM Provider for testing Reader agent."""

    def __init__(self, scenario_name: str = "complex_driver_reasoning") -> None:
        self.scenario_name = scenario_name
        self.calls = 0

    def complete(self, *, system_prompt: str, user_prompt: str, response_schema: Mapping[str, Any]) -> str:
        import json
        self.calls += 1
        scenario = MOCK_SCENARIOS.get(self.scenario_name, MOCK_SCENARIOS["complex_driver_reasoning"])
        return json.dumps(scenario["mock_llm_response"], ensure_ascii=False)
