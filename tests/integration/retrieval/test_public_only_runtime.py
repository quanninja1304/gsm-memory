import shutil
from pathlib import Path

from gsm_memory.benchmark import run_queries
from gsm_memory.retrieval.offline import run_offline_closure_sync


def test_runtime_succeeds_when_private_tree_is_absent(tmp_path: Path):
    source = Path("data/gsm-dev-core-0.2.2")
    release = tmp_path / "release"
    shutil.copytree(source / "public", release / "public")
    report = run_queries(release, "debug_core", tmp_path / "run.json", 3)
    assert report["query_count"] == 42
    assert report["terminal_count"] == 42
    assert not (release / "private").exists()


def test_offline_closure_emits_complete_terminal_traces_without_private_tree(
    tmp_path: Path, monkeypatch
):
    source = Path("data/gsm-dev-core-0.2.2")
    release = tmp_path / "release"
    shutil.copytree(source / "public", release / "public")

    async def graph_stub(snapshot_dir, *, search_queries, search_limit):
        return {
            "nodes": 0,
            "edges": 0,
            "episodes": 0,
            "construction_ms": 0.0,
            "repeat_write_idempotent": True,
            "projection_links": [],
            "query_results": [
                {
                    "query_id": query["query_id"],
                    "raw_candidates": [],
                    "eligible_candidates": [],
                    "excluded_candidates": [],
                    "search_latency_ms": 0.0,
                }
                for query in search_queries
            ],
        }

    monkeypatch.setattr("gsm_memory.retrieval.offline.construct_mode_a", graph_stub)
    report = run_offline_closure_sync(release, "retrieval_full")
    required = {
        "query_id", "runtime_status", "document_candidates", "kg_raw_candidates",
        "kg_candidates", "computation_candidates", "hybrid_candidates",
        "selected_evidence", "excluded_counts", "counts", "latency_ms",
        "cache_status", "limits", "truncated",
    }
    assert report["query_count"] == report["terminal_count"] == 42
    assert report["snapshot_count"] == 12
    assert report["ledger_count"] == 8
    assert report["terminal_status_counts"] == {"completed_retrieval": 42}
    assert all(required <= trace.keys() for trace in report["traces"])
    assert report["instrumentation"]["provider_calls"] == 0
    assert not (release / "private").exists()
