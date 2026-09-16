"""
===============================================================================
Graphiti Temporal Correction Baseline Test
===============================================================================

Purpose:
  Verify how Graphiti currently handles temporal correction of an existing fact:
    Episode 1: "PERSON_A joined TEAM_B starting on 2026-10-20."
    Episode 2: "Correction: PERSON_A actually joined TEAM_B starting on 2026-10-22, not 2026-10-20."

Expected Business Truth:
  2026-10-21 -> PERSON_A should NOT be considered a member of TEAM_B
  2026-10-23 -> PERSON_A SHOULD be considered a member of TEAM_B
  Conceptually: PERSON_A --MEMBER_OF--> TEAM_B with valid_from = 2026-10-22.

Setup and Run Instructions:
  1. Prerequisites:
     Install required dependencies via `uv`:
       uv pip install graphiti-core kuzu httpx google-genai python-dotenv

  2. API Keys:
     Ensure GEMINI_API_KEY (or OPENAI_API_KEY) is available in environment or in a .env file.
     The script automatically checks current directory .env, then parent project .env files.

  3. Execution:
     Run with uv / python:
       .venv\\Scripts\\python.exe tests/conformance/graphiti/test_temporal_correction.py
     or:
       uv run python tests/conformance/graphiti/test_temporal_correction.py
===============================================================================
"""

import asyncio
import os
import sys
import uuid
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Suppress Kuzu deprecation warning for clean test output
warnings.filterwarnings("ignore", category=DeprecationWarning)

from dotenv import dotenv_values

# Graphiti imports
from graphiti_core import Graphiti
from graphiti_core.driver.driver import GraphProvider
from graphiti_core.driver.kuzu_driver import KuzuDriver
from graphiti_core.embedder.gemini import GeminiEmbedder, GeminiEmbedderConfig
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.gemini_client import GeminiClient
from graphiti_core.cross_encoder.gemini_reranker_client import GeminiRerankerClient
from graphiti_core.edges import EntityEdge
from graphiti_core.nodes import EntityNode, EpisodicNode


def resolve_api_key() -> str:
    """Find a valid GEMINI_API_KEY from env or known project .env locations."""
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]

    candidate_env_paths = [
        Path(".env"),
        Path("../.env"),
        Path("D:/vinai/Day-3-Lab-Chatbot-vs-react-agent-E402/.env"),
        Path("D:/vinai/P-244/.env"),
    ]

    for p in candidate_env_paths:
        if p.exists():
            vals = dotenv_values(p)
            if vals.get("GEMINI_API_KEY"):
                print(f"[Setup] Loaded GEMINI_API_KEY from {p}")
                return str(vals["GEMINI_API_KEY"])

    raise RuntimeError(
        "GEMINI_API_KEY not found in environment or fallback .env files. "
        "Please set GEMINI_API_KEY."
    )


def format_dt(dt: datetime | None) -> str:
    if dt is None:
        return "None"
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


def print_edge_details(edge: EntityEdge, prefix: str = "  "):
    print(f"{prefix}[Edge UUID]        : {edge.uuid}")
    print(f"{prefix}[Relation Name]    : {edge.name}")
    print(f"{prefix}[Fact Text]        : {edge.fact}")
    print(f"{prefix}[Source Node UUID] : {edge.source_node_uuid}")
    print(f"{prefix}[Target Node UUID] : {edge.target_node_uuid}")
    print(f"{prefix}[valid_at]         : {format_dt(edge.valid_at)}")
    print(f"{prefix}[invalid_at]       : {format_dt(edge.invalid_at)}")
    print(f"{prefix}[created_at]       : {format_dt(edge.created_at)}")
    print(f"{prefix}[expired_at]       : {format_dt(edge.expired_at)}")
    print(f"{prefix}[episodes]         : {edge.episodes}")
    if edge.attributes:
        print(f"{prefix}[attributes]       : {edge.attributes}")


async def build_isolated_graphiti(group_id: str) -> tuple[Graphiti, KuzuDriver]:
    """Initialize a fresh isolated Graphiti instance using Kuzu in-memory driver."""
    api_key = resolve_api_key()
    llm = GeminiClient(
        config=LLMConfig(api_key=api_key, model="gemini-2.5-flash", small_model="gemini-2.5-flash")
    )
    embedder = GeminiEmbedder(
        config=GeminiEmbedderConfig(
            api_key=api_key, embedding_model="gemini-embedding-001", embedding_dim=768
        )
    )
    reranker = GeminiRerankerClient(
        config=LLMConfig(api_key=api_key, model="gemini-2.5-flash")
    )

    driver = KuzuDriver(db=":memory:")
    # Ensure driver._database is set to avoid AttributeError in Graphiti scoping
    driver._database = ":memory:"
    # Ensure Kuzu fulltext search indices are built
    await driver.graph_ops.build_indices_and_constraints(driver)

    graphiti = Graphiti(
        graph_driver=driver,
        llm_client=llm,
        embedder=embedder,
        cross_encoder=reranker,
    )
    return graphiti, driver


async def inspect_graph_state(driver: KuzuDriver, group_id: str, stage_name: str):
    """Inspect and print raw graph representations (episodes, nodes, edges)."""
    print("\n" + "=" * 70)
    print(f" GRAPH INSPECTION: {stage_name}")
    print("=" * 70)

    # 1. Episodes
    episodes: list[EpisodicNode] = await driver.episode_node_ops.get_by_group_ids(driver, [group_id])
    print(f"\n--- Episodic Nodes ({len(episodes)}) ---")
    for ep in episodes:
        print(f"  * Episode UUID : {ep.uuid}")
        print(f"    Name         : {ep.name}")
        print(f"    Content      : {ep.content}")
        print(f"    Source       : {ep.source_description} ({ep.source})")
        print(f"    valid_at     : {format_dt(ep.valid_at)}")
        print(f"    created_at   : {format_dt(ep.created_at)}")
        print(f"    entity_edges : {ep.entity_edges}")

    # 2. Entity Nodes
    nodes: list[EntityNode] = await driver.entity_node_ops.get_by_group_ids(driver, [group_id])
    print(f"\n--- Entity Nodes ({len(nodes)}) ---")
    for n in nodes:
        print(f"  * Node UUID    : {n.uuid}")
        print(f"    Name         : {n.name}")
        print(f"    Labels       : {n.labels}")
        print(f"    Summary      : {n.summary}")

    # 3. Entity Edges (Facts)
    edges: list[EntityEdge] = await driver.entity_edge_ops.get_by_group_ids(driver, [group_id])
    print(f"\n--- Entity Edges / Facts ({len(edges)}) ---")
    for i, e in enumerate(edges, 1):
        print(f"\n  [Edge #{i}]")
        print_edge_details(e, prefix="    ")

    return episodes, nodes, edges


def evaluate_membership_on_date(edges: list[EntityEdge], target_date: datetime) -> tuple[bool, list[str]]:
    """
    Evaluate whether edges assert membership on a given target date.
    Temporal condition for active fact:
      valid_at <= target_date AND (invalid_at is None OR invalid_at > target_date)
    """
    matching_explanations = []
    is_member = False

    target_utc = target_date.replace(tzinfo=timezone.utc) if target_date.tzinfo is None else target_date

    for e in edges:
        # Check if edge relates PERSON_A and TEAM_B
        fact_lower = (e.fact or "").lower()
        name_lower = (e.name or "").lower()
        if "person_a" in fact_lower and "team_b" in fact_lower:
            valid_from = e.valid_at.replace(tzinfo=timezone.utc) if (e.valid_at and e.valid_at.tzinfo is None) else e.valid_at
            valid_until = e.invalid_at.replace(tzinfo=timezone.utc) if (e.invalid_at and e.invalid_at.tzinfo is None) else e.invalid_at

            is_active = True
            reason = []
            if valid_from:
                if valid_from > target_utc:
                    is_active = False
                    reason.append(f"valid_at ({format_dt(valid_from)}) > target ({format_dt(target_utc)})")
                else:
                    reason.append(f"valid_at ({format_dt(valid_from)}) <= target")
            else:
                reason.append("valid_at is None")

            if valid_until:
                if valid_until <= target_utc:
                    is_active = False
                    reason.append(f"invalid_at ({format_dt(valid_until)}) <= target ({format_dt(target_utc)})")
                else:
                    reason.append(f"invalid_at ({format_dt(valid_until)}) > target")
            else:
                reason.append("invalid_at is None (Open-ended/Present)")

            status_str = "ACTIVE" if is_active else "INACTIVE"
            matching_explanations.append(
                f"Edge {e.uuid[:8]} ('{e.fact}'): {status_str} [Reason: {', '.join(reason)}]"
            )
            if is_active:
                is_member = True

    return is_member, matching_explanations


async def main():
    print("=" * 70)
    print(" STARTING GRAPHITI TEMPORAL CORRECTION TEST")
    print("=" * 70)

    # Unique isolated group namespace
    test_group_id = f"test_corr_{uuid.uuid4().hex[:8]}"
    print(f"[Namespace] Group ID: {test_group_id}")

    graphiti, driver = await build_isolated_graphiti(test_group_id)

    try:
        # ---------------------------------------------------------------------
        # STEP 1: Ingest Episode 1 (Original fact)
        # ---------------------------------------------------------------------
        ep1_text = "PERSON_A joined TEAM_B starting on 2026-10-20."
        ep1_time = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)
        print(f"\n>>> [Step 1] Ingesting Episode 1: '{ep1_text}' (reference_time={format_dt(ep1_time)})")

        res1 = await graphiti.add_episode(
            name="Episode 1 - Initial Joining",
            episode_body=ep1_text,
            source_description="HR Announcement",
            reference_time=ep1_time,
            group_id=test_group_id,
        )
        print(f"[Step 1] Ingestion complete. Episode UUID: {res1.episode.uuid}")

        episodes_1, nodes_1, edges_1 = await inspect_graph_state(
            driver, test_group_id, "After Episode 1 (Initial Fact)"
        )

        # ---------------------------------------------------------------------
        # STEP 2: Ingest Episode 2 (Correction)
        # ---------------------------------------------------------------------
        ep2_text = "Correction: PERSON_A actually joined TEAM_B starting on 2026-10-22, not 2026-10-20."
        ep2_time = datetime(2026, 10, 22, 12, 0, 0, tzinfo=timezone.utc)
        print(f"\n>>> [Step 2] Ingesting Episode 2: '{ep2_text}' (reference_time={format_dt(ep2_time)})")

        res2 = await graphiti.add_episode(
            name="Episode 2 - Correction",
            episode_body=ep2_text,
            source_description="HR Correction Notice",
            reference_time=ep2_time,
            group_id=test_group_id,
        )
        print(f"[Step 2] Ingestion complete. Episode UUID: {res2.episode.uuid}")

        episodes_2, nodes_2, edges_2 = await inspect_graph_state(
            driver, test_group_id, "After Episode 2 (Correction)"
        )

        # ---------------------------------------------------------------------
        # STEP 3: Graphiti Retrieval Checks
        # ---------------------------------------------------------------------
        print("\n" + "=" * 70)
        print(" RETRIEVAL CHECKS VIA GRAPHITI SEARCH")
        print("=" * 70)

        query_21 = "Was PERSON_A a member of TEAM_B on 2026-10-21?"
        query_23 = "Was PERSON_A a member of TEAM_B on 2026-10-23?"

        print(f"\nQuery A: '{query_21}'")
        search_res_21 = await graphiti.search(query_21, group_ids=[test_group_id])
        print(f"Raw search returned {len(search_res_21)} edges:")
        for r in search_res_21:
            print(f"  * Fact: '{r.fact}' | valid_at: {format_dt(r.valid_at)} | invalid_at: {format_dt(r.invalid_at)} | expired_at: {format_dt(r.expired_at)}")

        print(f"\nQuery B: '{query_23}'")
        search_res_23 = await graphiti.search(query_23, group_ids=[test_group_id])
        print(f"Raw search returned {len(search_res_23)} edges:")
        for r in search_res_23:
            print(f"  * Fact: '{r.fact}' | valid_at: {format_dt(r.valid_at)} | invalid_at: {format_dt(r.invalid_at)} | expired_at: {format_dt(r.expired_at)}")

        # ---------------------------------------------------------------------
        # STEP 4: Temporal Semantics Analysis
        # ---------------------------------------------------------------------
        date_21 = datetime(2026, 10, 21, 12, 0, 0, tzinfo=timezone.utc)
        date_23 = datetime(2026, 10, 23, 12, 0, 0, tzinfo=timezone.utc)

        member_on_21, expl_21 = evaluate_membership_on_date(edges_2, date_21)
        member_on_23, expl_23 = evaluate_membership_on_date(edges_2, date_23)

        print("\n" + "=" * 70)
        print(" DETAILED TEMPORAL MECHANISM ANALYSIS")
        print("=" * 70)
        print("Checking temporal intervals from underlying graph representation:")
        print("Date 2026-10-21 evaluation:")
        for exp in expl_21:
            print(f"  {exp}")
        print(f"  -> Graph semantic result for 2026-10-21: {'IS MEMBER' if member_on_21 else 'NOT MEMBER'}")

        print("\nDate 2026-10-23 evaluation:")
        for exp in expl_23:
            print(f"  {exp}")
        print(f"  -> Graph semantic result for 2026-10-23: {'IS MEMBER' if member_on_23 else 'NOT MEMBER'}")

        # Check API capabilities
        print("\nAPI Check for Explicit Correction Mechanism:")
        explicit_correction_methods = [
            m for m in dir(Graphiti) if any(k in m.lower() for k in ["correct", "amend", "supersede", "revision"])
        ]
        if explicit_correction_methods:
            print(f"  Graphiti explicit correction methods found: {explicit_correction_methods}")
        else:
            print("  No explicit correction/amendment methods found on Graphiti class.")
            print("  Available mutation methods: add_episode, add_triplet, remove_episode.")

        # ---------------------------------------------------------------------
        # STEP 5: Final Diagnostic Summary and Verdict
        # ---------------------------------------------------------------------
        print("\n" + "=" * 70)
        print(" FINAL DIAGNOSTIC SUMMARY")
        print("=" * 70)

        ep1_facts_summary = "; ".join([f"'{e.fact}' (valid_at={format_dt(e.valid_at)}, invalid_at={format_dt(e.invalid_at)})" for e in edges_1])
        ep2_facts_summary = "; ".join([f"'{e.fact}' (valid_at={format_dt(e.valid_at)}, invalid_at={format_dt(e.invalid_at)})" for e in edges_2])

        print(f"Original extracted fact:\n  {ep1_facts_summary}\n")
        print(f"After correction:\n  {ep2_facts_summary}\n")

        # Determine verdict
        # Expected business truth:
        #   2026-10-21: NOT a member (False)
        #   2026-10-23: SHOULD be a member (True)
        # Resulting graph semantics clearly correspond to:
        #   A is a member of Team B starting from 2026-10-22, not from 2026-10-20.
        if (not member_on_21) and member_on_23:
            verdict = "PASS"
            verdict_rationale = (
                "Graphiti correctly resolved the correction by retroactively establishing "
                "that PERSON_A is only a member of TEAM_B starting from 2026-10-22, "
                "and was NOT a member on 2026-10-21."
            )
        elif member_on_21:
            verdict = "FAIL"
            verdict_rationale = (
                "Graphiti still represents PERSON_A as belonging to TEAM_B during 2026-10-20 through 2026-10-21. "
                "The correction episode was either treated as a forward state transition (setting invalid_at=2026-10-22 "
                "on the old fact, preserving validity on 2026-10-21) or kept alongside the original fact."
            )
        else:
            verdict = "AMBIGUOUS"
            verdict_rationale = (
                "The graph representation or available API did not allow establishing the temporal "
                "distinction reliably."
            )

        print(f"Graphiti representation:\n  Edge count: {len(edges_2)}. ")
        for e in edges_2:
            print(f"  - UUID {e.uuid[:8]}: '{e.fact}' | valid_at={format_dt(e.valid_at)}, invalid_at={format_dt(e.invalid_at)}, expired_at={format_dt(e.expired_at)}")
        print(f"\nObserved status for 2026-10-21:\n  {'MEMBER (Incorrect - violates expected truth)' if member_on_21 else 'NOT MEMBER (Correct)'}")
        print(f"\nObserved status for 2026-10-23:\n  {'MEMBER (Correct)' if member_on_23 else 'NOT MEMBER (Incorrect)'}")
        print(f"\nVerdict:\n{verdict}")
        print(f"\nRationale:\n{verdict_rationale}")
        print("=" * 70)

    finally:
        await graphiti.close()


if __name__ == "__main__":
    asyncio.run(main())
