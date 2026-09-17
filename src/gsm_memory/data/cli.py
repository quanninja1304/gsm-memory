from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from .build import build_release, source_inventory, validate_build_config
from .primitives import canonical_bytes, sha256_bytes, sha256_file, write_json
from .validation import ValidationFailure, compare_logical, semantic_inventory, validate_release


def parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(prog="python -m gsm_memory.data.cli",description="Offline gsm-dev-core-0.2.1 data pipeline")
    p.add_argument("--repo",type=Path,default=Path.cwd())
    sub=p.add_subparsers(dest="command",required=True)
    i=sub.add_parser("inventory");i.add_argument("--config",type=Path,required=True)
    b=sub.add_parser("build");b.add_argument("--config",type=Path,required=True);b.add_argument("--output",type=Path,required=True)
    v=sub.add_parser("validate");v.add_argument("--candidate",type=Path,required=True);v.add_argument("--final-reproducibility",action="store_true")
    c=sub.add_parser("compare-logical");c.add_argument("--candidate-a",type=Path,required=True);c.add_argument("--candidate-b",type=Path,required=True);c.add_argument("--report",type=Path,required=True)
    f=sub.add_parser("freeze");f.add_argument("--candidate",type=Path,required=True);f.add_argument("--comparison",type=Path,required=True);f.add_argument("--target",type=Path,required=True);f.add_argument("--report",type=Path,required=True)
    return p


def main(argv:list[str]|None=None)->int:
    args=parser().parse_args(argv);repo=args.repo.resolve()
    try:
        if args.command=="inventory":
            validate_build_config(args.config.resolve())
            rows=source_inventory(repo);print(json.dumps({"archive_verified":True,"real_articles":len(rows),"aggregate_excluded":True,"audited":sum(x["article_number"] in {154,151,5,23,172,26} for x in rows),"profiles":{"debug_core":6,"retrieval_full":224}},ensure_ascii=False,sort_keys=True));return 0
        if args.command=="build": print(json.dumps(build_release(repo,args.output.resolve(),args.config.resolve()),sort_keys=True));return 0
        if args.command=="validate":
            report=validate_release(args.candidate.resolve(),repo,args.final_reproducibility);print(json.dumps(report["summary"],sort_keys=True));return 0
        if args.command=="compare-logical":
            report=compare_logical(args.candidate_a.resolve(),args.candidate_b.resolve(),args.report.resolve());print(json.dumps({"status":report["status"],"compared_files":report["compared_files"],"mismatches":len(report["mismatches"])},sort_keys=True));return 0 if report["status"]=="pass" else 2
        if args.command=="freeze":
            candidate=args.candidate.resolve();target=args.target.resolve();comparison=json.loads(args.comparison.read_text(encoding="utf-8"))
            if comparison["status"]!="pass" or str(candidate) not in {comparison["candidate_a"],comparison["candidate_b"]}: raise ValidationFailure("comparison does not approve candidate")
            validate_release(candidate,repo,True); validation=json.loads((candidate/"private/eval/validation.json").read_text(encoding="utf-8"))
            if any(x["status"]!="pass" for x in validation["dfg"].values()): raise ValidationFailure("DFG evidence incomplete")
            candidate_manifest=json.loads((candidate/"private/eval/manifest.json").read_text(encoding="utf-8"))
            if target.name != candidate_manifest["dataset_version"]: raise ValidationFailure("freeze target name must match dataset_version")
            if target.exists():
                existing=target/"private/eval/manifest.json"
                state=json.loads(existing.read_text(encoding="utf-8"))["state"] if existing.exists() else "unknown"
                raise FileExistsError(f"refusing to overwrite existing target (state={state})")
            shutil.copytree(candidate,target)
            manifest_path=target/"private/eval/manifest.json";manifest=json.loads(manifest_path.read_text(encoding="utf-8"));manifest["state"]="FROZEN";manifest["logical_inventory_digest"]=comparison["inventory_digest"]
            files={p.relative_to(target).as_posix():sha256_file(p) for p in sorted(x for x in target.rglob("*") if x.is_file()) if p!=manifest_path};manifest["file_inventory"]=files;manifest["validation_sha256"]=sha256_file(target/"private/eval/validation.json");write_json(manifest_path,manifest)
            digest=sha256_file(manifest_path);freeze={"dataset_version":manifest["dataset_version"],"state":"FROZEN","manifest_sha256":digest,"logical_inventory_digest":comparison["inventory_digest"],"comparison_report_sha256":sha256_file(args.comparison),"dfg":validation["dfg"]};write_json(args.report,freeze);print(json.dumps(freeze,sort_keys=True));return 0
    except (ValueError,FileNotFoundError,FileExistsError,ValidationFailure) as exc:
        print(f"error: {exc}",file=sys.stderr);return 2
    return 2


if __name__=="__main__": raise SystemExit(main())
