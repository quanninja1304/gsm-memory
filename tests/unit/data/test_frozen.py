import json
import shutil
from pathlib import Path

from gsm_memory.data.frozen import verify_frozen_release
from gsm_memory.data.cli import main
from gsm_memory.data.primitives import canonical_bytes, sha256_bytes, sha256_file, write_json
from gsm_memory.data.validation import semantic_inventory


def make_frozen_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    release = tmp_path / "gsm-dev-core-test"
    payload = release / "public/payload.txt"
    validation = release / "private/eval/validation.json"
    payload.parent.mkdir(parents=True)
    validation.parent.mkdir(parents=True)
    payload.write_bytes(b"payload\n")
    write_json(validation, {"state": "VALIDATED", "checks": []})
    inventory = {
        "private/eval/validation.json": sha256_file(validation),
        "public/payload.txt": sha256_file(payload),
    }
    manifest = release / "private/eval/manifest.json"
    write_json(manifest, {
        "state": "FROZEN",
        "dataset_version": release.name,
        "logical_inventory_digest": "pending",
        "validation_sha256": sha256_file(validation),
        "file_inventory": inventory,
    })
    digest = sha256_bytes(canonical_bytes(semantic_inventory(release)))
    manifest_value = json.loads(manifest.read_text(encoding="utf-8"))
    manifest_value["logical_inventory_digest"] = digest
    write_json(manifest, manifest_value)
    comparison = tmp_path / "comparison.json"
    write_json(comparison, {
        "status": "pass",
        "mismatches": [],
        "inventory_digest": digest,
    })
    certificate = tmp_path / "certificate.json"
    write_json(certificate, {
        "dataset_version": release.name,
        "state": "FROZEN",
        "manifest_sha256": sha256_file(manifest),
        "comparison_report_sha256": sha256_file(comparison),
        "logical_inventory_digest": digest,
        "dfg": {f"DFG{i:02d}": {"status": "pass"} for i in range(1, 7)},
    })
    return release, certificate, comparison


def test_frozen_verifier_is_read_only_on_current_release():
    repo = Path(__file__).parents[3]
    release = repo / "data/gsm-dev-core-0.2.1"
    certificate = repo / "reports/data_freeze/gsm-dev-core-0.2.1-freeze-certificate.json"
    comparison = repo / "reports/data_freeze/gsm-dev-core-0.2.1-logical-comparison.json"
    protected = [
        release / "private/eval/manifest.json",
        release / "private/eval/validation.json",
        certificate,
        comparison,
    ]
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in protected}
    report = verify_frozen_release(release, certificate, comparison)
    after = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in protected}
    assert report["status"] == "pass"
    assert report["checked"] == report["declared"] == 635
    assert before == after


def test_frozen_verifier_reports_mutated_missing_and_unexpected_files(tmp_path):
    release, certificate, comparison = make_frozen_fixture(tmp_path)
    (release / "public/payload.txt").write_bytes(b"mutated\n")
    (release / "private/eval/validation.json").unlink()
    (release / "unexpected.bin").write_bytes(b"extra")
    report = verify_frozen_release(release, certificate, comparison)
    assert report["status"] == "fail"
    assert "private/eval/validation.json" in report["missing"]
    assert any(item["path"] == "public/payload.txt" for item in report["mismatched"])
    assert report["unexpected"] == ["unexpected.bin"]
    assert set(report["implicated_paths"]) >= {
        "private/eval/validation.json", "public/payload.txt", "unexpected.bin"
    }


def test_frozen_verifier_rejects_certificate_manifest_and_comparison_mismatch(tmp_path):
    release, certificate, comparison = make_frozen_fixture(tmp_path)
    cert = json.loads(certificate.read_text(encoding="utf-8"))
    cert["manifest_sha256"] = "0" * 64
    cert["comparison_report_sha256"] = "1" * 64
    cert["logical_inventory_digest"] = "2" * 64
    cert["dfg"]["DFG06"]["status"] = "not_run"
    write_json(certificate, cert)
    report = verify_frozen_release(release, certificate, comparison)
    assert report["status"] == "fail"
    assert any("logical inventory digest mismatch" in error for error in report["errors"])
    assert any("DFG06 is not pass" in error for error in report["errors"])
    assert len(report["mismatched"]) >= 2


def test_frozen_verifier_rejects_direct_manifest_and_comparison_mutation(tmp_path):
    release, certificate, comparison = make_frozen_fixture(tmp_path)
    manifest = release / "private/eval/manifest.json"
    manifest_value = json.loads(manifest.read_text(encoding="utf-8"))
    manifest_value["state"] = "VALIDATED"
    write_json(manifest, manifest_value)
    comparison_value = json.loads(comparison.read_text(encoding="utf-8"))
    comparison_value["status"] = "fail"
    comparison_value["mismatches"] = [{"path": "public/payload.txt"}]
    write_json(comparison, comparison_value)
    report = verify_frozen_release(release, certificate, comparison)
    assert report["status"] == "fail"
    assert any("release state is not FROZEN" in error for error in report["errors"])
    assert any("comparison report does not record a clean pass" in error for error in report["errors"])


def test_frozen_verifier_never_repairs_a_failure(tmp_path):
    release, certificate, comparison = make_frozen_fixture(tmp_path)
    target = release / "public/payload.txt"
    target.write_bytes(b"broken")
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in release.rglob("*") if path.is_file()}
    assert verify_frozen_release(release, certificate, comparison)["status"] == "fail"
    after = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in release.rglob("*") if path.is_file()}
    assert before == after


def test_verify_frozen_cli_returns_nonzero_on_required_failure(tmp_path, capsys):
    release, certificate, comparison = make_frozen_fixture(tmp_path)
    (release / "public/payload.txt").unlink()
    code = main([
        "verify-frozen",
        "--release", str(release),
        "--certificate", str(certificate),
        "--comparison", str(comparison),
    ])
    output = json.loads(capsys.readouterr().out)
    assert code == 2
    assert output["status"] == "fail"
    assert output["missing"] == ["public/payload.txt"]
