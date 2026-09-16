"""Graphiti 0.30.2 native-ingestion temporal conformance suite.

Run directly:
    .venv\\Scripts\\python.exe tests\\conformance\\graphiti\\test_temporal_conformance.py

The suite is diagnostic and intentionally uses live Gemini extraction. Every
fixture gets a fresh Kuzu in-memory graph. Results are written to
``runs/conformance/graphiti_temporal_conformance.json``.
"""

from __future__ import annotations

import asyncio
import argparse
import json
import re
import sys
import traceback
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable

from graphiti_core.llm_client.errors import RateLimitError

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tests.support.graphiti_temporal_test_utils import (
    build_isolated_graphiti,
    compare_membership,
    ingest_and_inspect,
    is_positive_membership_edge,
    run_searches,
    runtime_configuration,
    utc,
)

RESULT_PATH = REPOSITORY_ROOT / "runs" / "conformance" / "graphiti_temporal_conformance.json"


def result_base(test_id: str, name: str, expected: dict[str, Any]) -> dict[str, Any]:
    config = runtime_configuration()
    return {
        "test_id": test_id,
        "name": name,
        "graphiti_version": config["graphiti_version"],
        "configuration": config,
        "execution_status": "COMPLETED",
        "expected": expected,
        "observed_graph": {},
        "retrieval": {},
        "diagnostics": {},
        "verdict": "AMBIGUOUS",
        "failure_tags": [],
        "notes": [],
    }


def membership_search_queries(test_id: str, expected: dict[str, bool]) -> list[dict[str, str]]:
    return [
        {
            "id": f"{test_id}-{index}",
            "query": f"Was PERSON_A a member of TEAM_B at {instant}?",
        }
        for index, instant in enumerate(expected, 1)
    ]


def retrieved_positive_membership(search: dict[str, Any]) -> bool:
    for edge in search["results"]:
        text = f"{edge.get('name') or ''} {edge.get('fact') or ''}".lower()
        if (
            "person_a" in text
            and "team_b" in text
            and any(token in text for token in ("join", "member", "belong"))
            and not any(token in text for token in ("left", "leave", "never", "not_member"))
        ):
            return True
    return False


def classify_membership_case(
    result: dict[str, Any], final_state: dict[str, Any], expected: dict[str, bool], searches: list[dict[str, Any]]
) -> None:
    observations, construction_ok = compare_membership(final_state, expected)
    result["diagnostics"]["valid_time_checks"] = observations
    result["diagnostics"]["construction"] = "PASS" if construction_ok else "FAIL"

    # Search is only scored for positive support retrieval. A raw hit on a negative
    # temporal question is not interpreted as an affirmative answer.
    positive_query_misses = []
    for (instant, expected_value), search in zip(expected.items(), searches):
        search["oracle_expected_state"] = "MEMBER" if expected_value else "NOT_MEMBER"
        search["raw_positive_membership_hit"] = retrieved_positive_membership(search)
        if expected_value and not search["raw_positive_membership_hit"]:
            positive_query_misses.append(instant)
    if not construction_ok:
        result["verdict"] = "FAIL_CONSTRUCTION"
        result["failure_tags"] = ["I_TIME"]
        result["diagnostics"]["retrieval"] = "DOWNSTREAM_OF_WRONG_GRAPH"
    elif positive_query_misses:
        result["verdict"] = "FAIL_RETRIEVAL"
        result["diagnostics"]["retrieval"] = "MISS"
        result["notes"].append(f"Positive-support search misses: {positive_query_misses}")
    else:
        result["verdict"] = "PASS"
        result["diagnostics"]["retrieval"] = "RAW_SUPPORT_RETRIEVED"
    result["notes"].append(
        "Negative temporal questions are not scored from raw search hits because search returns candidates, not a temporal truth value."
    )


async def run_membership_fixture(
    test_id: str,
    name: str,
    episodes: list[dict[str, str]],
    expected: dict[str, bool],
) -> dict[str, Any]:
    result = result_base(test_id, name, expected)
    graphiti, driver = await build_isolated_graphiti()
    group_id = f"{test_id.lower()}_{uuid.uuid4().hex[:10]}"
    states = []
    try:
        previous = None
        for episode in episodes:
            previous = await ingest_and_inspect(
                graphiti,
                driver,
                group_id,
                episode["id"],
                episode["body"],
                episode["source"],
                utc(episode["reference_time"]),
                previous,
            )
            states.append(previous)
        searches = await run_searches(
            graphiti, group_id, membership_search_queries(test_id, expected)
        )
        result["observed_graph"] = {"group_id": group_id, "stages": states}
        result["retrieval"] = {"searches": searches}
        classify_membership_case(result, states[-1], expected, searches)
        return result
    finally:
        await graphiti.close()


async def case_t1() -> dict[str, Any]:
    return await run_membership_fixture(
        "T1",
        "Forward state transition",
        [
            {
                "id": "T1-E1",
                "body": "PERSON_A joined TEAM_B effective 2026-10-20.",
                "source": "HR source S1",
                "reference_time": "2026-10-20T12:00:00Z",
            },
            {
                "id": "T1-E2",
                "body": "PERSON_A left TEAM_B effective 2026-10-22.",
                "source": "HR source S1",
                "reference_time": "2026-10-22T12:00:00Z",
            },
        ],
        {
            "2026-10-21T12:00:00Z": True,
            "2026-10-22T12:00:00Z": False,
            "2026-10-23T12:00:00Z": False,
        },
    )


async def case_t2() -> dict[str, Any]:
    return await run_membership_fixture(
        "T2",
        "Retroactive valid_from correction",
        [
            {
                "id": "T2-E1",
                "body": "PERSON_A joined TEAM_B effective 2026-10-20.",
                "source": "HR announcement",
                "reference_time": "2026-10-20T12:00:00Z",
            },
            {
                "id": "T2-E2",
                "body": "Correction: PERSON_A actually joined TEAM_B effective 2026-10-22, not 2026-10-20.",
                "source": "HR correction",
                "reference_time": "2026-10-22T12:00:00Z",
            },
        ],
        {"2026-10-21T12:00:00Z": False, "2026-10-23T12:00:00Z": True},
    )


async def case_t3() -> dict[str, Any]:
    return await run_membership_fixture(
        "T3",
        "Retroactive correction to earlier valid_from",
        [
            {
                "id": "T3-E1",
                "body": "PERSON_A joined TEAM_B effective 2026-10-22.",
                "source": "HR announcement",
                "reference_time": "2026-10-22T12:00:00Z",
            },
            {
                "id": "T3-E2",
                "body": "Correction: PERSON_A actually joined TEAM_B effective 2026-10-20, not 2026-10-22.",
                "source": "HR correction",
                "reference_time": "2026-10-23T12:00:00Z",
            },
        ],
        {"2026-10-21T12:00:00Z": True, "2026-10-23T12:00:00Z": True},
    )


async def case_t4() -> dict[str, Any]:
    return await run_membership_fixture(
        "T4",
        "Future-effective state update",
        [
            {
                "id": "T4-E1",
                "body": "PERSON_A will join TEAM_B effective 2026-10-25.",
                "source": "Scheduled HR announcement",
                "reference_time": "2026-10-20T12:00:00Z",
            }
        ],
        {"2026-10-24T12:00:00Z": False, "2026-10-25T12:00:00Z": True},
    )


async def case_t5() -> dict[str, Any]:
    expected = {
        "business_valid_at": "2026-10-20T00:00:00+00:00",
        "arrival_reference_time": "2026-10-25T12:00:00+00:00",
        "requirement": "Observe distinct business/event and arrival/reference fields without equating created_at to known_from.",
    }
    result = result_base("T5", "Late-arriving event", expected)
    graphiti, driver = await build_isolated_graphiti()
    group_id = f"t5_{uuid.uuid4().hex[:10]}"
    try:
        state = await ingest_and_inspect(
            graphiti,
            driver,
            group_id,
            "T5-E1",
            "PERSON_A joined TEAM_B effective 2026-10-20.",
            "Late HR delivery received on 2026-10-25",
            utc("2026-10-25T12:00:00Z"),
            None,
        )
        searches = await run_searches(
            graphiti,
            group_id,
            [{"id": "T5-Q1", "query": "When did PERSON_A join TEAM_B?"}],
        )
        membership_edges = [edge for edge in state["edges"] if is_positive_membership_edge(edge, state)]
        edge_valid_values = {edge["valid_at"] for edge in membership_edges}
        episode_reference_preserved = any(
            episode["valid_at"] == expected["arrival_reference_time"] for episode in state["episodes"]
        )
        valid_time_preserved = expected["business_valid_at"] in edge_valid_values
        created_values = sorted({edge["created_at"] for edge in membership_edges if edge["created_at"]})
        result["observed_graph"] = {"group_id": group_id, "stages": [state]}
        result["retrieval"] = {"searches": searches}
        result["diagnostics"] = {
            "edge_valid_time_preserved": valid_time_preserved,
            "episode_reference_time_preserved_as_valid_at": episode_reference_preserved,
            "edge_created_at_values": created_values,
            "created_at_interpretation": "Observed persistence/construction timestamp; the fixture does not establish logical known_from semantics.",
            "known_interval_available": False,
        }
        if valid_time_preserved and episode_reference_preserved:
            result["verdict"] = "PARTIAL"
            result["notes"].append(
                "Two timestamps are observable, but no logical known_from/known_to contract is exposed by this native representation."
            )
        else:
            result["verdict"] = "FAIL_TEMPORAL_REPRESENTATION"
            result["failure_tags"] = ["I_TIME"]
        return result
    finally:
        await graphiti.close()


async def case_t6() -> dict[str, Any]:
    expected_matrix = {
        "2026-10-21T12:00:00Z|2026-10-21T23:00:00Z": True,
        "2026-10-21T12:00:00Z|2026-10-26T12:00:00Z": False,
        "2026-10-23T12:00:00Z|2026-10-24T12:00:00Z": True,
        "2026-10-23T12:00:00Z|2026-10-26T12:00:00Z": True,
    }
    result = result_base("T6", "True bitemporal correction", expected_matrix)
    graphiti, driver = await build_isolated_graphiti()
    group_id = f"t6_{uuid.uuid4().hex[:10]}"
    try:
        state_before = await ingest_and_inspect(
            graphiti,
            driver,
            group_id,
            "T6-E1",
            "PERSON_A joined TEAM_B effective 2026-10-20.",
            "HR source received 2026-10-20",
            utc("2026-10-20T12:00:00Z"),
            None,
        )
        state_after = await ingest_and_inspect(
            graphiti,
            driver,
            group_id,
            "T6-E2",
            "Correction: PERSON_A actually joined TEAM_B effective 2026-10-22, not 2026-10-20.",
            "HR correction received 2026-10-25",
            utc("2026-10-25T12:00:00Z"),
            state_before,
        )
        searches = await run_searches(
            graphiti,
            group_id,
            [
                {"id": "T6-Q1", "query": "Was PERSON_A a member of TEAM_B on 2026-10-21, as known on 2026-10-21?"},
                {"id": "T6-Q2", "query": "Was PERSON_A a member of TEAM_B on 2026-10-21, as known on 2026-10-26?"},
                {"id": "T6-Q3", "query": "Was PERSON_A a member of TEAM_B on 2026-10-23, as known on 2026-10-24?"},
                {"id": "T6-Q4", "query": "Was PERSON_A a member of TEAM_B on 2026-10-23, as known on 2026-10-26?"},
            ],
        )
        before_observed, _ = compare_membership(
            state_before,
            {
                "2026-10-21T12:00:00Z": True,
                "2026-10-23T12:00:00Z": True,
            },
        )
        after_observed, after_ok = compare_membership(
            state_after,
            {
                "2026-10-21T12:00:00Z": False,
                "2026-10-23T12:00:00Z": True,
            },
        )
        result["observed_graph"] = {
            "group_id": group_id,
            "stages": [state_before, state_after],
        }
        result["retrieval"] = {
            "searches": searches,
            "known_as_of_api": "No direct known_as_of parameter was used or inferred.",
        }
        result["diagnostics"] = {
            "publication_prefix_before_correction": before_observed,
            "current_snapshot_after_correction": after_observed,
            "current_valid_time_correct": after_ok,
            "logical_known_from_to_on_assertions": False,
            "can_answer_from_one_stored_graph": False,
        }
        if after_ok:
            result["verdict"] = "PARTIAL"
            result["failure_tags"] = ["G_PROVENANCE"]
            result["notes"].append(
                "Current valid-time state is correct, but historical known-as-of answers require externally retained publication-prefix snapshots."
            )
        else:
            result["verdict"] = "NOT_SUPPORTED"
            result["failure_tags"] = ["I_TIME", "I_LINEAGE", "G_STALE"]
            result["notes"].append(
                "The final graph cannot reconstruct the corrected current valid-time state, and it has no logical assertion known intervals for bitemporal queries."
            )
        return result
    finally:
        await graphiti.close()


async def case_t7() -> dict[str, Any]:
    return await run_membership_fixture(
        "T7",
        "Retraction",
        [
            {
                "id": "T7-E1",
                "body": "PERSON_A joined TEAM_B effective 2026-10-20.",
                "source": "HR announcement",
                "reference_time": "2026-10-20T12:00:00Z",
            },
            {
                "id": "T7-E2",
                "body": "Correction: the previous statement that PERSON_A joined TEAM_B was incorrect. PERSON_A never joined TEAM_B.",
                "source": "HR retraction",
                "reference_time": "2026-10-24T12:00:00Z",
            },
        ],
        {"2026-10-21T12:00:00Z": False, "2026-10-23T12:00:00Z": False},
    )


async def case_t8() -> dict[str, Any]:
    expected = {
        "contract_status": "unresolved_conflict",
        "source_claims": {"S1": "2026-10-20", "S2": "2026-10-22"},
    }
    result = result_base("T8", "Conflicting independent sources", expected)
    graphiti, driver = await build_isolated_graphiti()
    group_id = f"t8_{uuid.uuid4().hex[:10]}"
    try:
        first = await ingest_and_inspect(
            graphiti,
            driver,
            group_id,
            "T8-S1",
            "PERSON_A joined TEAM_B effective 2026-10-20.",
            "Independent source S1",
            utc("2026-10-20T12:00:00Z"),
            None,
        )
        second = await ingest_and_inspect(
            graphiti,
            driver,
            group_id,
            "T8-S2",
            "PERSON_A joined TEAM_B effective 2026-10-22.",
            "Independent source S2",
            utc("2026-10-22T12:00:00Z"),
            first,
        )
        searches = await run_searches(
            graphiti,
            group_id,
            [{"id": "T8-Q1", "query": "When did PERSON_A join TEAM_B and which source supports the date?"}],
        )
        edges = [edge for edge in second["edges"] if is_positive_membership_edge(edge, second)]
        dates = sorted({edge["valid_at"] for edge in edges if edge["valid_at"]})
        provenance = sorted({episode for edge in edges for episode in edge["episodes"]})
        keeps_both_temporal_claims = len(dates) >= 2
        keeps_both_episode_links = len(provenance) >= 2
        result["observed_graph"] = {"group_id": group_id, "stages": [first, second]}
        result["retrieval"] = {"searches": searches}
        result["diagnostics"] = {
            "positive_membership_edge_count": len(edges),
            "distinct_valid_at_values": dates,
            "episode_provenance_count": len(provenance),
            "keeps_both_temporal_claims": keeps_both_temporal_claims,
            "keeps_both_episode_links": keeps_both_episode_links,
            "explicit_unresolved_conflict_state": False,
        }
        if keeps_both_temporal_claims:
            result["verdict"] = "PARTIAL"
            result["failure_tags"] = ["G_TIME_CONFLICT"]
        else:
            result["verdict"] = "FAIL_TEMPORAL_REPRESENTATION"
            result["failure_tags"] = ["I_TIME", "G_TIME_CONFLICT"]
        if keeps_both_episode_links:
            result["notes"].append("Episode provenance survived, but provenance alone does not preserve both temporal assertions.")
        result["notes"].append("No project source-authority or unresolved-conflict state is represented natively.")
        return result
    finally:
        await graphiti.close()


def trip_edge_groups(state: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    groups = {"TRIP_001": [], "TRIP_002": []}
    for edge in state["edges"]:
        text = f"{edge.get('name') or ''} {edge.get('fact') or ''}"
        for trip_id in groups:
            if re.search(re.escape(trip_id), text, flags=re.IGNORECASE):
                groups[trip_id].append(edge)
    return groups


async def case_t9() -> dict[str, Any]:
    expected = {
        "distinct_business_events": ["TRIP_001", "TRIP_002"],
        "duplicate_publication": "TRIP_001 repeated without creating a third business event",
    }
    result = result_base("T9", "Repeated point events must not collapse", expected)
    graphiti, driver = await build_isolated_graphiti()
    group_id = f"t9_{uuid.uuid4().hex[:10]}"
    try:
        states = []
        previous = None
        for episode in [
            {
                "id": "T9-E1",
                "body": "On 2026-10-20, PERSON_A cancelled TRIP_001.",
                "source": "Trip event log",
                "reference_time": "2026-10-20T12:00:00Z",
            },
            {
                "id": "T9-E2",
                "body": "On 2026-10-22, PERSON_A cancelled TRIP_002.",
                "source": "Trip event log",
                "reference_time": "2026-10-22T12:00:00Z",
            },
            {
                "id": "T9-E3-DUPLICATE",
                "body": "On 2026-10-20, PERSON_A cancelled TRIP_001.",
                "source": "Duplicate publication from trip event log",
                "reference_time": "2026-10-23T12:00:00Z",
            },
        ]:
            previous = await ingest_and_inspect(
                graphiti,
                driver,
                group_id,
                episode["id"],
                episode["body"],
                episode["source"],
                utc(episode["reference_time"]),
                previous,
            )
            states.append(previous)
        searches = await run_searches(
            graphiti,
            group_id,
            [
                {"id": "T9-Q1", "query": "What happened to TRIP_001?"},
                {"id": "T9-Q2", "query": "What happened to TRIP_002?"},
            ],
        )
        after_two = trip_edge_groups(states[1])
        after_duplicate = trip_edge_groups(states[2])
        distinct_preserved = bool(after_two["TRIP_001"]) and bool(after_two["TRIP_002"])
        trip1_ids_before = {edge["uuid"] for edge in after_two["TRIP_001"]}
        trip1_ids_after = {edge["uuid"] for edge in after_duplicate["TRIP_001"]}
        duplicate_deduplicated = trip1_ids_after == trip1_ids_before
        retrieval_hits = {
            trip_id: any(
                trip_id.lower()
                in " ".join(str(edge.get(key) or "") for key in ("name", "fact")).lower()
                for search in searches
                for edge in search["results"]
            )
            for trip_id in ("TRIP_001", "TRIP_002")
        }
        result["observed_graph"] = {"group_id": group_id, "stages": states}
        result["retrieval"] = {"searches": searches, "event_id_hits": retrieval_hits}
        result["diagnostics"] = {
            "distinct_events_preserved_after_two_episodes": distinct_preserved,
            "trip_edge_ids_after_two": {
                key: [edge["uuid"] for edge in value] for key, value in after_two.items()
            },
            "trip_edge_ids_after_duplicate": {
                key: [edge["uuid"] for edge in value] for key, value in after_duplicate.items()
            },
            "duplicate_publication_deduplicated": duplicate_deduplicated,
        }
        if not distinct_preserved:
            result["verdict"] = "FAIL_CONSTRUCTION"
            result["failure_tags"] = ["I_FACT", "I_LINEAGE"]
        elif not duplicate_deduplicated:
            result["verdict"] = "PARTIAL"
            result["failure_tags"] = ["I_LINEAGE"]
        elif not all(retrieval_hits.values()):
            result["verdict"] = "FAIL_RETRIEVAL"
        else:
            result["verdict"] = "PASS"
        return result
    finally:
        await graphiti.close()


async def case_t10() -> dict[str, Any]:
    return await run_membership_fixture(
        "T10",
        "Half-open interval boundary",
        [
            {
                "id": "T10-E1",
                "body": "PERSON_A joined TEAM_B at 2026-10-20T00:00:00+00:00.",
                "source": "UTC HR event",
                "reference_time": "2026-10-20T00:00:00Z",
            },
            {
                "id": "T10-E2",
                "body": "PERSON_A left TEAM_B at 2026-10-22T00:00:00+00:00.",
                "source": "UTC HR event",
                "reference_time": "2026-10-22T00:00:00Z",
            },
        ],
        {"2026-10-21T23:59:00Z": True, "2026-10-22T00:00:00Z": False},
    )


CASES: list[tuple[str, Callable[[], Awaitable[dict[str, Any]]]]] = [
    ("T1", case_t1),
    ("T2", case_t2),
    ("T3", case_t3),
    ("T4", case_t4),
    ("T5", case_t5),
    ("T6", case_t6),
    ("T7", case_t7),
    ("T8", case_t8),
    ("T9", case_t9),
    ("T10", case_t10),
]

CASE_NAMES = {
    "T1": "Forward state transition",
    "T2": "Retroactive valid_from correction",
    "T3": "Retroactive correction to earlier valid_from",
    "T4": "Future-effective state update",
    "T5": "Late-arriving event",
    "T6": "True bitemporal correction",
    "T7": "Retraction",
    "T8": "Conflicting independent sources",
    "T9": "Repeated point events must not collapse",
    "T10": "Half-open interval boundary",
}

CASE_EXPECTATIONS: dict[str, dict[str, Any]] = {
    "T1": {
        "2026-10-21T12:00:00Z": True,
        "2026-10-22T12:00:00Z": False,
        "2026-10-23T12:00:00Z": False,
    },
    "T2": {"2026-10-21T12:00:00Z": False, "2026-10-23T12:00:00Z": True},
    "T3": {"2026-10-21T12:00:00Z": True, "2026-10-23T12:00:00Z": True},
    "T4": {"2026-10-24T12:00:00Z": False, "2026-10-25T12:00:00Z": True},
    "T5": {
        "business_valid_at": "2026-10-20T00:00:00+00:00",
        "arrival_reference_time": "2026-10-25T12:00:00+00:00",
    },
    "T6": {
        "2026-10-21T12:00:00Z|2026-10-21T23:00:00Z": True,
        "2026-10-21T12:00:00Z|2026-10-26T12:00:00Z": False,
        "2026-10-23T12:00:00Z|2026-10-24T12:00:00Z": True,
        "2026-10-23T12:00:00Z|2026-10-26T12:00:00Z": True,
    },
    "T7": {"2026-10-21T12:00:00Z": False, "2026-10-23T12:00:00Z": False},
    "T8": {
        "contract_status": "unresolved_conflict",
        "source_claims": {"S1": "2026-10-20", "S2": "2026-10-22"},
    },
    "T9": {
        "distinct_business_events": ["TRIP_001", "TRIP_002"],
        "duplicate_publication": "TRIP_001 repeated without creating a third business event",
    },
    "T10": {"2026-10-21T23:59:00Z": True, "2026-10-22T00:00:00Z": False},
}


def write_results(results: list[dict[str, Any]]) -> None:
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "suite": "Graphiti native temporal conformance",
        "configuration": runtime_configuration(),
        "result_count": len(results),
        "results": results,
    }
    RESULT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def print_summary(results: list[dict[str, Any]]) -> None:
    print("\n" + "=" * 112)
    print("TEMPORAL CONFORMANCE SUMMARY")
    print("=" * 112)
    print(
        f"{'Case':<5} {'Capability':<43} {'Run status':<20} "
        f"{'Construction':<17} {'Retrieval':<27} Verdict"
    )
    print("-" * 112)
    for result in results:
        diagnostics = result.get("diagnostics", {})
        run_status = result.get("execution_status", "COMPLETED")
        construction = diagnostics.get("construction", "OBSERVED")
        retrieval = diagnostics.get("retrieval", "OBSERVED")
        print(
            f"{result['test_id']:<5} {result['name'][:42]:<43} "
            f"{run_status:<20} {construction:<17} {retrieval:<27} {result['verdict']}"
        )
    print("=" * 112)
    print(f"Machine-readable results: {RESULT_PATH.resolve()}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases",
        default=",".join(test_id for test_id, _ in CASES),
        help="Comma-separated fixture IDs (default: T1 through T10)",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Merge selected fixture results into the existing JSON result file",
    )
    parser.add_argument(
        "--cooldown",
        type=float,
        default=0.0,
        help="Seconds to wait between fixtures to respect external API quotas",
    )
    parser.add_argument(
        "--rate-limit-retries",
        type=int,
        default=0,
        help="Rebuild and retry a fixture after a Gemini rate-limit error",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=65.0,
        help="Seconds to wait before a rate-limit retry",
    )
    return parser.parse_args()


def load_existing_results() -> list[dict[str, Any]]:
    if not RESULT_PATH.exists():
        return []
    payload = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    results = list(payload.get("results", []))
    for result in results:
        result["name"] = CASE_NAMES.get(result.get("test_id"), result.get("name", "Unknown"))
        if not result.get("expected"):
            result["expected"] = CASE_EXPECTATIONS.get(result.get("test_id"), {})
        if result.get("verdict") == "AMBIGUOUS" and "RateLimitError" in result.get("error", ""):
            result["execution_status"] = "BLOCKED_RATE_LIMIT"
            result.setdefault("notes", []).append(
                "This is an infrastructure outcome, not an ambiguous Graphiti capability result."
            )
        else:
            result.setdefault("execution_status", "COMPLETED")
    return results


async def main() -> None:
    args = parse_args()
    selected_ids = {item.strip().upper() for item in args.cases.split(",") if item.strip()}
    selected_cases = [(test_id, case) for test_id, case in CASES if test_id in selected_ids]
    unknown_ids = selected_ids - {test_id for test_id, _ in CASES}
    if unknown_ids:
        raise ValueError(f"Unknown fixture IDs: {sorted(unknown_ids)}")

    print("Graphiti native temporal conformance suite")
    print(json.dumps(runtime_configuration(), indent=2))
    results: list[dict[str, Any]] = load_existing_results() if args.append else []
    result_by_id = {result["test_id"]: result for result in results}
    for case_index, (test_id, case) in enumerate(selected_cases):
        if case_index and args.cooldown:
            print(f"\n[Quota throttle] waiting {args.cooldown:.0f}s before {test_id}")
            await asyncio.sleep(args.cooldown)
        print("\n" + "#" * 112)
        print(f"START {test_id}")
        print("#" * 112)
        for attempt in range(args.rate_limit_retries + 1):
            try:
                result = await case()
                break
            except RateLimitError as exc:
                if attempt >= args.rate_limit_retries:
                    result = result_base(
                        test_id, CASE_NAMES[test_id], CASE_EXPECTATIONS[test_id]
                    )
                    result["execution_status"] = "BLOCKED_RATE_LIMIT"
                    result["verdict"] = "AMBIGUOUS"
                    result["notes"] = [f"Fixture exhausted rate-limit retries: {exc}"]
                    result["error"] = traceback.format_exc()
                    print(result["error"])
                    break
                print(
                    f"[Rate limit] {test_id} attempt {attempt + 1} failed; "
                    f"rebuilding isolated fixture after {args.retry_delay:.0f}s"
                )
                await asyncio.sleep(args.retry_delay)
            except Exception as exc:  # Keep independent fixtures running and preserve evidence.
                result = result_base(test_id, CASE_NAMES[test_id], CASE_EXPECTATIONS[test_id])
                result["execution_status"] = "ERROR"
                result["verdict"] = "AMBIGUOUS"
                result["notes"] = [f"Fixture raised {type(exc).__name__}: {exc}"]
                result["error"] = traceback.format_exc()
                print(result["error"])
                break
        result_by_id[test_id] = result
        results = [result_by_id[item_id] for item_id, _ in CASES if item_id in result_by_id]
        write_results(results)
        print(f"END {test_id}: {result['verdict']} tags={result['failure_tags']}")
    print_summary(results)


if __name__ == "__main__":
    asyncio.run(main())
