import shutil
import subprocess
from pathlib import Path

import pytest

from gsm_memory.data.frozen import verify_frozen_release


def run_git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout


def test_repository_attributes_are_explicit():
    repo = Path(__file__).parents[3]
    raw = "data/gsm-dev-core-0.2.1/public/documents/raw/snap-154-d4af28195271.md"
    normalized = "data/gsm-dev-core-0.2.1/public/documents/normalized/03d0f89e-6a2c-58ed-b60b-1ee30a63b2be.md"
    parquet = "data/gsm-dev-core-0.2.1/public/operational/record_ledger.parquet"
    archive = "data/raw/archives/policy_green_sm_source.zip"
    output = run_git("check-attr", "text", "eol", "diff", "--", raw, normalized, parquet, archive, cwd=repo)
    assert f"{raw}: text: set" in output and f"{raw}: eol: crlf" in output
    assert f"{normalized}: text: unset" in output
    assert f"{parquet}: text: unset" in output and f"{parquet}: diff: unset" in output
    assert f"{archive}: text: unset" in output and f"{archive}: diff: unset" in output


@pytest.mark.skipif(shutil.which("git") is None, reason="Git is required for checkout simulation")
def test_checkout_bytes_do_not_depend_on_core_autocrlf(tmp_path):
    project = Path(__file__).parents[3]
    source = tmp_path / "source"
    source.mkdir()
    (source / ".gitattributes").write_bytes((project / ".gitattributes").read_bytes())
    raw = source / "data/gsm-dev-core-0.2.1/public/documents/raw/example.md"
    normalized = source / "data/gsm-dev-core-0.2.1/public/documents/normalized/example.md"
    parquet = source / "data/gsm-dev-core-0.2.1/public/operational/example.parquet"
    archive = source / "data/raw/archives/example.zip"
    for path in (raw, normalized, parquet, archive):
        path.parent.mkdir(parents=True, exist_ok=True)
    raw.write_bytes(b"raw-one\r\nraw-two\r\n")
    normalized.write_bytes(b"normalized-one\nnormalized-two\n")
    parquet.write_bytes(b"PAR1\x00\r\n\xff")
    archive.write_bytes(b"PK\x03\x04\x00\r\n\xff")
    run_git("init", cwd=source)
    run_git("config", "user.email", "test@example.invalid", cwd=source)
    run_git("config", "user.name", "A0 test", cwd=source)
    run_git("add", ".", cwd=source)
    run_git("commit", "-m", "fixture", cwd=source)

    expected = {
        raw.relative_to(source): b"raw-one\r\nraw-two\r\n",
        normalized.relative_to(source): b"normalized-one\nnormalized-two\n",
        parquet.relative_to(source): b"PAR1\x00\r\n\xff",
        archive.relative_to(source): b"PK\x03\x04\x00\r\n\xff",
    }
    for setting in ("true", "false", "input"):
        checkout = tmp_path / f"checkout-{setting}"
        subprocess.run(
            ["git", "-c", f"core.autocrlf={setting}", "clone", "--no-local", str(source), str(checkout)],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        for relative, payload in expected.items():
            assert (checkout / relative).read_bytes() == payload, (setting, relative)


@pytest.mark.skipif(shutil.which("git") is None, reason="Git is required for checkout simulation")
def test_full_frozen_inventory_survives_clean_checkout(tmp_path):
    project = Path(__file__).parents[3]
    source = tmp_path / "source-full"
    source.mkdir()
    shutil.copy2(project / ".gitattributes", source / ".gitattributes")
    shutil.copytree(project / "data/gsm-dev-core-0.2.1", source / "data/gsm-dev-core-0.2.1")
    report_dir = source / "reports/data_freeze"
    report_dir.mkdir(parents=True)
    for name in (
        "gsm-dev-core-0.2.1-freeze-certificate.json",
        "gsm-dev-core-0.2.1-logical-comparison.json",
    ):
        shutil.copy2(project / "reports/data_freeze" / name, report_dir / name)
    run_git("init", cwd=source)
    run_git("config", "user.email", "test@example.invalid", cwd=source)
    run_git("config", "user.name", "A0 test", cwd=source)
    run_git("add", ".", cwd=source)
    run_git("commit", "-m", "full frozen fixture", cwd=source)

    checkout = tmp_path / "checkout-full"
    subprocess.run(
        ["git", "-c", "core.autocrlf=false", "clone", "--no-local", str(source), str(checkout)],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    report = verify_frozen_release(
        checkout / "data/gsm-dev-core-0.2.1",
        checkout / "reports/data_freeze/gsm-dev-core-0.2.1-freeze-certificate.json",
        checkout / "reports/data_freeze/gsm-dev-core-0.2.1-logical-comparison.json",
    )
    assert report["status"] == "pass", report
    assert report["checked"] == report["declared"] == 635
