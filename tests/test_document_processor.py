from pathlib import Path

import pytest

from core.document_processor import SUPPORTED_EXTENSIONS, process_file


def test_supported_extensions():
    assert {".pdf", ".txt", ".md", ".docx"} <= SUPPORTED_EXTENSIONS


def test_process_txt(tmp_path: Path):
    f = tmp_path / "sample.txt"
    f.write_text("这是一个测试文档。" * 200, encoding="utf-8")

    chunks = process_file(f)
    assert len(chunks) > 0
    for c in chunks:
        assert c.metadata["source"] == "sample.txt"
        assert c.metadata["page"] == 1
        assert isinstance(c.metadata["chunk_index"], int)
        assert c.content.strip()


def test_process_markdown(tmp_path: Path):
    f = tmp_path / "note.md"
    f.write_text("# 标题\n\n段落一。\n\n段落二。" * 50, encoding="utf-8")
    chunks = process_file(f)
    assert len(chunks) > 0


def test_unsupported_extension(tmp_path: Path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"\x00\x01")
    with pytest.raises(ValueError):
        process_file(f)


def test_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        process_file(tmp_path / "nope.txt")


def test_chunk_indices_are_sequential(tmp_path: Path):
    f = tmp_path / "long.txt"
    f.write_text("段落。" * 1000, encoding="utf-8")
    chunks = process_file(f)
    indices = [c.metadata["chunk_index"] for c in chunks]
    assert indices == list(range(len(chunks)))
