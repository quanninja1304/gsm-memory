"""Thin Phase B runner. Runtime functions read public artifacts only."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from gsm_memory.retrieval import BM25Index, ChunkConfig, construct_chunks
from gsm_memory.retrieval.documents import canonical_hash, read_jsonl


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", "utf-8")


def _implementation_hash() -> str:
    package = Path(__file__).resolve().parent
    paths = [Path(__file__), *(package / "retrieval").glob("*.py"),
             package / "adapters" / "graphiti.py", package / "evaluation" / "runtime.py"]
    inventory = [(path.relative_to(package).as_posix(), canonical_hash(path.read_text("utf-8")))
                 for path in sorted(paths) if path.exists()]
    return canonical_hash(inventory)


def construct_documents(release: Path, profile: str, output: Path) -> dict[str, Any]:
    started = time.perf_counter()
    chunks, links, inventory = construct_chunks(release, profile, ChunkConfig())
    report = {**inventory, "construction_ms": round((time.perf_counter() - started) * 1000, 3),
              "chunks": [asdict(c) for c in chunks], "projection_links": [asdict(link) for link in links]}
    _write_json(output, report)
    return report


def run_queries(release: Path, profile: str, output: Path, top_k: int) -> dict[str, Any]:
    started = time.perf_counter()
    chunks, links, inventory = construct_chunks(release, profile, ChunkConfig())
    index = BM25Index(chunks)
    public = release / "public"
    queries = read_jsonl(public / "runtime_queries" / "dev.jsonl")
    traces = []
    for query in queries:
        tick = time.perf_counter()
        app = query.get("application_context") or {}
        pinned = set(app.get("source_snapshot_refs", [])) | set(app.get("definition_refs", []))
        results = index.search(query["query"], top_k=top_k, allowed_source_ids=pinned or None)
        traces.append({
            "query_id": query["query_id"], "snapshot_id": query["public_snapshot_id"], "profile_id": profile,
            "terminal_status": "completed", "document": {"bm25": {"status": "completed", "candidates": index.serializable(results)},
            "dense": {"status": "unsupported", "reason": "no pinned multilingual dense model"},
            "fusion": {"status": "unsupported", "reason": "dense prerequisite unavailable"},
            "bounded_reranker": {"status": "unsupported", "reason": "no pinned reranker model"}},
            "kg": {"status": "unsupported", "reason": "full per-snapshot graph not materialized in measured run"},
            "hybrid": {"status": "unsupported", "reason": "KG and dense baseline incomplete"},
            "reader": {"status": "blocked_provider", "reason": "no provider credential", "calls": 0, "tokens": 0, "cost_usd": 0},
            "counts": {"active_profile_documents": inventory["document_count"], "definitions": inventory["definition_count"],
                       "chunks": inventory["chunk_count"], "before_edition_filter": inventory["chunk_count"],
                       "after_edition_filter": sum(c.source_id in pinned for c in chunks) if pinned else inventory["chunk_count"],
                       "returned": len(results)},
            "judgments": {"precision": None, "ndcg": None, "reason": "incomplete_judgments", "unjudged_policy": "preserved"},
            "latency_ms": round((time.perf_counter() - tick) * 1000, 3),
        })
    report = {"release": release.name, "profile": profile, "query_count": len(queries), "terminal_count": len(traces),
              "completed": sum(t["terminal_status"] == "completed" for t in traces), "top_k": top_k,
              "config_hash": canonical_hash({"profile": profile, "top_k": top_k, "chunk": inventory["config_hash"]}),
              "implementation_hash": _implementation_hash(),
              "provider_credentials": {key: bool(os.getenv(key)) for key in ("OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY")},
              "total_ms": round((time.perf_counter() - started) * 1000, 3), "traces": traces}
    _write_json(output, report)
    return report


def preflight(output: Path) -> dict[str, Any]:
    def command(*args: str) -> str:
        return subprocess.check_output(args, text=True).strip()
    report = {"head": command("git", "rev-parse", "HEAD"), "branch": command("git", "branch", "--show-current"),
              "python": platform.python_version(), "os": platform.platform(), "machine": platform.machine(),
              "graphiti": "0.30.2", "backend": "kuzu==0.11.3 (deprecated upstream)",
              "dense_model": "unavailable", "reranker": "unavailable", "reader": "blocked_provider",
              "credentials": {key: bool(os.getenv(key)) for key in ("OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY")}}
    _write_json(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m gsm_memory.benchmark")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("preflight"); p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("construct-documents"); p.add_argument("--release", type=Path, required=True); p.add_argument("--profile", required=True); p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("probe-graphiti"); p.add_argument("--snapshot", type=Path, required=True); p.add_argument("--output", type=Path, required=True); p.add_argument("--database", default=":memory:")
    p = sub.add_parser("run"); p.add_argument("--release", type=Path, required=True); p.add_argument("--profile", required=True); p.add_argument("--output", type=Path, required=True); p.add_argument("--top-k", type=int, default=10)
    p = sub.add_parser("evaluate"); p.add_argument("--release", type=Path, required=True); p.add_argument("--runtime-report", type=Path, required=True); p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("offline-closure"); p.add_argument("--release", type=Path, required=True); p.add_argument("--profile", default="retrieval_full"); p.add_argument("--output", type=Path, required=True); p.add_argument("--document-top-k", type=int, default=10); p.add_argument("--graph-top-k", type=int, default=40); p.add_argument("--token-budget", type=int, default=1800)
    args = parser.parse_args()
    if args.command == "preflight": report = preflight(args.output)
    elif args.command == "construct-documents": report = construct_documents(args.release, args.profile, args.output)
    elif args.command == "run": report = run_queries(args.release, args.profile, args.output, args.top_k)
    elif args.command == "evaluate":
        from gsm_memory.evaluation.runtime import evaluate_run
        report = evaluate_run(args.release, args.runtime_report); _write_json(args.output, report)
    elif args.command == "offline-closure":
        from gsm_memory.retrieval.offline import run_offline_closure_sync
        report = run_offline_closure_sync(args.release, args.profile, document_top_k=args.document_top_k,
                                          graph_top_k=args.graph_top_k, token_budget=args.token_budget)
        _write_json(args.output, report)
    else:
        import asyncio
        from gsm_memory.adapters.graphiti import construct_mode_a
        report = asyncio.run(construct_mode_a(args.snapshot, args.database)); _write_json(args.output, report)
    print(json.dumps({key: value for key, value in report.items() if key not in {"chunks", "projection_links", "traces"}}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
