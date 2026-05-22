from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fitz
from docx import Document as DocxDocument

from core.config import settings
from utils.logger import get_logger

logger = get_logger("document-processor")


@dataclass
class Chunk:
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx"}


def _read_pdf(path: Path) -> list[tuple[int, str]]:
    pages: list[tuple[int, str]] = []
    with fitz.open(path) as doc:
        for i, page in enumerate(doc, start=1):
            text = page.get_text("text") or ""
            if text.strip():
                pages.append((i, text))
    return pages


def _read_txt(path: Path) -> list[tuple[int, str]]:
    return [(1, path.read_text(encoding="utf-8", errors="ignore"))]


def _read_docx(path: Path) -> list[tuple[int, str]]:
    doc = DocxDocument(str(path))
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return [(1, text)]


_SEPARATORS = ["\n\n", "\n", "。", ".", "！", "？", "!", "?", " ", ""]


def _split_recursive(text: str, chunk_size: int, separators: list[str]) -> list[str]:
    """简化版 RecursiveCharacterTextSplitter：按分隔符优先级递归切分至 <= chunk_size。"""
    if len(text) <= chunk_size:
        return [text] if text else []

    sep = ""
    for s in separators:
        if s == "" or s in text:
            sep = s
            break

    if sep == "":
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    pieces = text.split(sep)
    remaining = [s for s in separators[separators.index(sep) + 1 :]]
    out: list[str] = []
    for p in pieces:
        chunk = p + (sep if sep != "\n\n" else "")
        if len(chunk) <= chunk_size:
            out.append(chunk)
        else:
            out.extend(_split_recursive(chunk, chunk_size, remaining or [""]))
    return out


def _merge_with_overlap(pieces: list[str], chunk_size: int, overlap: int) -> list[str]:
    """将细碎 pieces 合并到接近 chunk_size，并保留相邻 overlap 重叠。"""
    merged: list[str] = []
    buf = ""
    for p in pieces:
        if not p.strip():
            continue
        if len(buf) + len(p) <= chunk_size:
            buf += p
        else:
            if buf:
                merged.append(buf)
            if overlap > 0 and merged:
                tail = merged[-1][-overlap:]
                buf = tail + p
            else:
                buf = p
    if buf.strip():
        merged.append(buf)
    return merged


def _split_text(text: str) -> list[str]:
    pieces = _split_recursive(text, settings.chunk_size, _SEPARATORS)
    return _merge_with_overlap(pieces, settings.chunk_size, settings.chunk_overlap)


def process_file(path: str | Path) -> list[Chunk]:
    """Parse a file into chunks. Each chunk carries source/page/chunk_index metadata."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"不支持的文件类型: {ext}（支持: {sorted(SUPPORTED_EXTENSIONS)}）")

    logger.info(f"开始解析 {path.name} ({ext})")

    if ext == ".pdf":
        pages = _read_pdf(path)
    elif ext == ".docx":
        pages = _read_docx(path)
    else:
        pages = _read_txt(path)

    chunks: list[Chunk] = []
    global_idx = 0

    for page_num, page_text in pages:
        for piece in _split_text(page_text):
            piece = piece.strip()
            if not piece:
                continue
            chunks.append(
                Chunk(
                    content=piece,
                    metadata={
                        "source": path.name,
                        "page": page_num,
                        "chunk_index": global_idx,
                    },
                )
            )
            global_idx += 1

    logger.info(f"{path.name} 解析完成，共 {len(chunks)} 个 chunk")
    return chunks
