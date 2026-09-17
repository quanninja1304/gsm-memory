import json
import zipfile
from pathlib import Path

import pytest

from gsm_memory.data.primitives import sha256_file
from gsm_memory.data.sources import AGGREGATE_NAME, materialize_sources


def source_name(index: int) -> str:
    if index == 0:
        return AGGREGATE_NAME
    return f"{index:02d}_2026-01-01_Source_{index}.md"


def make_archive(tmp_path: Path, *, count: int = 225, unsafe: bool = False) -> Path:
    archive = tmp_path / "sources.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as target:
        for index in range(count):
            target.writestr(f"PolicyGreenSM/{source_name(index)}", f"source {index}\r\n".encode())
        if unsafe:
            target.writestr("../escape.md", b"escape\r\n")
    return archive


def make_config(tmp_path: Path, archive: Path, *, expected_hash: str | None = None) -> Path:
    config = tmp_path / "config.json"
    config.write_text(json.dumps({
        "source_archive": archive.name,
        "source_archive_sha256": expected_hash or sha256_file(archive),
    }), encoding="utf-8")
    return config


def test_materialize_sources_preserves_bytes_and_is_deterministic(tmp_path):
    archive = make_archive(tmp_path)
    config = make_config(tmp_path, archive)
    out_a, out_b = tmp_path / "out-a", tmp_path / "out-b"
    result_a = materialize_sources(tmp_path, config, out_a)
    result_b = materialize_sources(tmp_path, config, out_b)
    assert result_a["markdown_files"] == 225
    assert result_a["individual_articles"] == 224
    assert result_a["aggregate_files"] == 1
    assert result_a["member_digest"] == result_b["member_digest"]
    assert [path.name for path in out_a.iterdir()] == [path.name for path in out_b.iterdir()]
    assert all((out_a / path.name).read_bytes() == path.read_bytes() for path in out_b.iterdir())
    assert (out_a / source_name(1)).read_bytes().endswith(b"\r\n")


def test_materialize_sources_rejects_missing_and_wrong_archive(tmp_path):
    missing = tmp_path / "missing.zip"
    config = make_config(tmp_path, missing, expected_hash="0" * 64)
    with pytest.raises(FileNotFoundError, match="missing pinned source archive"):
        materialize_sources(tmp_path, config, tmp_path / "out")
    archive = make_archive(tmp_path)
    config = make_config(tmp_path, archive, expected_hash="0" * 64)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        materialize_sources(tmp_path, config, tmp_path / "out")


def test_materialize_sources_rejects_path_traversal_and_incomplete_set(tmp_path):
    unsafe = make_archive(tmp_path, unsafe=True)
    config = make_config(tmp_path, unsafe)
    with pytest.raises(ValueError, match="unsafe ZIP member path"):
        materialize_sources(tmp_path, config, tmp_path / "unsafe-out")
    unsafe.unlink()
    incomplete = make_archive(tmp_path, count=224)
    config = make_config(tmp_path, incomplete)
    with pytest.raises(ValueError, match="exactly Markdown prefixes 00..224"):
        materialize_sources(tmp_path, config, tmp_path / "incomplete-out")


def test_materialize_sources_refuses_non_empty_target_without_partial_output(tmp_path):
    archive = make_archive(tmp_path)
    config = make_config(tmp_path, archive)
    output = tmp_path / "out"
    output.mkdir()
    marker = output / "user.txt"
    marker.write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError, match="non-empty"):
        materialize_sources(tmp_path, config, output)
    assert marker.read_text(encoding="utf-8") == "keep"
    assert not list(tmp_path.glob(".out.staging-*"))
