"""Live integration test: End-to-end 3-source hybrid retrieval with OpenRouter LLM and Langfuse tracing.

This test:
1. Takes a hybrid query requiring all 3 modalities:
   - Document: P154 (quy chế thưởng phạt, tiêu chuẩn Kim Cương).
   - Temporal KG: Driver DRV-001 (Nguyễn Văn An) trip history & events.
   - Computation: Rational cancel_rate_30d metric calculation.
2. Calls real OpenRouter LLM (meta-llama/llama-3.1-8b-instruct) for query planning.
3. Concurrently queries all 3 sources via asyncio.TaskGroup.
4. Synthesizes a grounded answer with citations using OpenRouter LLM.
5. Emits full nested traces and spans to Langfuse (https://cloud.langfuse.com).
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[3] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import pytest
from dotenv import load_dotenv

load_dotenv()

from gsm_memory.agent.reader import OpenRouterProvider, ReaderConfig, answer_query, build_prompts
from gsm_memory.retrieval.bm25 import BM25Index
from gsm_memory.retrieval.config import RetrievalConfig
from gsm_memory.retrieval.documents import ChunkConfig, construct_chunks
from gsm_memory.retrieval.planner import RetrievalPlanner
from gsm_memory.retrieval.query_analysis import parse_query_llm

API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct")
LANGFUSE_PUBLIC = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET = os.getenv("LANGFUSE_SECRET_KEY")

skip_if_missing_creds = pytest.mark.skipif(
    not (API_KEY and LANGFUSE_PUBLIC and LANGFUSE_SECRET),
    reason="OPENROUTER_API_KEY and LANGFUSE credentials must be set in .env",
)

RELEASE_DIR = Path("data/gsm-dev-core-0.2.2")


@pytest.mark.anyio
@skip_if_missing_creds
async def test_live_hybrid_retrieval_with_langfuse():
    """Execute live 3-source retrieval and verify trace publication on Langfuse."""
    from langfuse import Langfuse

    # Initialize Langfuse client
    lf = Langfuse()
    assert lf.auth_check(), "Langfuse authentication failed with current .env credentials"

    # Setup OpenRouter provider
    reader_config = ReaderConfig(provider="openrouter", model=MODEL, max_output_tokens=700)
    llm_provider = OpenRouterProvider(reader_config, api_key=API_KEY)

    # Prepare corpus & chunks (debug_core)
    chunks, _, _ = construct_chunks(RELEASE_DIR, "debug_core", ChunkConfig())
    bm25_index = BM25Index(chunks)

    # Hybrid Query: Requires Document (P154) + KG (Tài xế Bình) + Computation (cancel_rate_30d)
    snapshot_id = "d4cc0438-d831-541a-8123-ddda94ccdac8"
    snapshot_dir = RELEASE_DIR / "public" / "snapshots" / snapshot_id
    driver_id = "c499f934-bfe1-5509-a578-afb09cee357c"

    query = {
        "query_id": "langfuse-hybrid-3source-live",
        "query": (
            "Theo quy chế P154 trong snapshot snap-154-d4af28195271, "
            f"tài xế Bình (mã ID: {driver_id}) có tỷ lệ hủy chuyến trong 30 ngày qua là bao nhiêu "
            "và có bị vi phạm tiêu chuẩn quy định không?"
        ),
        "entity_refs": [driver_id],
        "public_snapshot_id": snapshot_id,
        "known_as_of": "2026-09-17T12:00:00.000000Z",
        "application_context": {
            "source_snapshot_refs": ["snap-154-d4af28195271"],
            "definition_refs": ["627ed991-2f8d-50a8-bd87-01cb73f4ca2a"],
        },
        "time_scope": {"mode": "current"},
    }

    # Root Langfuse Trace
    with lf.start_as_current_span(
        name="gsm-hybrid-3-sources-retrieval",
        input={"query": query["query"], "snapshot_id": snapshot_id},
        metadata={"release": "gsm-dev-core-0.2.2", "model": MODEL},
    ) as root_span:
        trace_url = lf.get_trace_url()

        # ----------------------------------------------------------------------
        # Step 1: LLM Query Planning
        # ----------------------------------------------------------------------
        t0 = time.perf_counter()
        with lf.start_as_current_generation(
            name="1. LLM Query Planner",
            model=MODEL,
            input=query["query"],
        ) as plan_gen:
            query_plan = parse_query_llm(
                query,
                provider=llm_provider,
                release_dir=RELEASE_DIR,
            )
            plan_gen.update(
                output={
                    "intent": query_plan.intent,
                    "modalities": query_plan.modalities,
                    "entity_refs": query_plan.entity_refs,
                    "target_metric": query_plan.computation_filters.target_metric,
                    "is_fallback": query_plan.is_fallback,
                }
            )

        # Build retrieval execution plan
        planner = RetrievalPlanner()
        ret_plan = planner.plan(query_plan, query=query)

        # Ensure all 3 modalities are activated
        ret_plan.enable_document = True
        ret_plan.enable_kg = True
        ret_plan.enable_computation = True
        if not ret_plan.target_metric:
            ret_plan.target_metric = "cancel_rate_30d"

        # ----------------------------------------------------------------------
        # Step 2: Concurrent Multi-Source Retrieval (asyncio.TaskGroup)
        # ----------------------------------------------------------------------
        with lf.start_as_current_span(
            name="2. Parallel Multi-Source Retrieval",
            input={"enabled_modalities": ["document", "kg", "computation"]},
        ) as parallel_span:
            retrieval_result = await planner.execute_async(
                plan=ret_plan,
                query=query,
                chunks=chunks,
                index=bm25_index,
                snapshot_dir=snapshot_dir,
            )
            parallel_span.update(
                output={
                    "wall_time_ms": retrieval_result.wall_time_ms,
                    "receipts": retrieval_result.receipts,
                    "candidate_counts": {
                        "document": len(retrieval_result.modality_candidates["document"]),
                        "kg": len(retrieval_result.modality_candidates["kg"]),
                        "computation": len(retrieval_result.modality_candidates["computation"]),
                        "total_candidates": len(retrieval_result.candidates),
                        "selected_evidence": len(retrieval_result.selected_evidence),
                    },
                }
            )

        # Assert all 3 sources yielded valid evidence candidates
        assert len(retrieval_result.modality_candidates["document"]) > 0, "Document retrieval should yield candidates"
        assert len(retrieval_result.modality_candidates["kg"]) > 0, "KG retrieval should yield candidates"
        assert len(retrieval_result.modality_candidates["computation"]) > 0, "Computation should yield candidates"
        assert len(retrieval_result.selected_evidence) > 0, "Evidence selector should produce selected evidence"

        # ----------------------------------------------------------------------
        # Step 3: Grounded Downstream Reader Synthesis (OpenRouter LLM)
        # ----------------------------------------------------------------------
        # Enrich computation candidate with readable fraction so the LLM reader can ground and cite it
        evidence_for_reader = []
        for item in retrieval_result.selected_evidence:
            cloned = dict(item)
            if cloned.get("source_kind") == "computation" and cloned.get("typed_value"):
                n = cloned["typed_value"]["n"]
                d = cloned["typed_value"]["d"]
                cloned["content"] = f"Kết quả tính toán tỷ lệ hủy chuyến cancel_rate_30d của tài xế là {n}/{d} (tương đương {round(n/d*100, 1)}%)."
            evidence_for_reader.append(cloned)

        with lf.start_as_current_generation(
            name="3. Grounded Reader Answer",
            model=MODEL,
            input={
                "query": query["query"],
                "selected_evidence_count": len(evidence_for_reader),
            },
        ) as reader_gen:
            try:
                answer = answer_query(
                    query,
                    evidence_for_reader,
                    provider=llm_provider,
                    config=reader_config,
                )
                reader_gen.update(
                    output={
                        "status": answer.status,
                        "answer": answer.answer,
                        "citations_count": len(answer.citations),
                        "citations": [{"id": c.evidence_id, "locator": c.locator, "quote": c.quote} for c in answer.citations],
                    }
                )
            except Exception as exc:
                system_prompt, user_prompt = build_prompts(query, retrieval_result.selected_evidence)
                raw = llm_provider.complete(system_prompt=system_prompt, user_prompt=user_prompt, response_schema={})
                print("\n[DEBUG] Raw LLM Reader Output:\n", raw)
                reader_gen.update(output={"error": str(exc), "raw_response": raw})
                raise

        root_span.update(
            output={
                "status": "success",
                "intent": ret_plan.intent,
                "sources_queried": ["document", "kg", "computation"],
                "final_answer": answer.answer,
                "citations": [c.locator for c in answer.citations],
            }
        )

    # Flush all traces to Langfuse cloud
    lf.flush()

    print("\n" + "=" * 80)
    print(">>> LANGFUSE TRACE COMPLETED SUCCESSFULLY! <<<")
    print(f"Trace URL: {trace_url}")
    print(f"Query: {query['query']}")
    print(f"Answer Status: {answer.status}")
    print(f"Final Answer:\n{answer.answer}")
    print("Citations:")
    for c in answer.citations:
        print(f" - [{c.locator}] \"{c.quote}\"")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(test_live_hybrid_retrieval_with_langfuse())
