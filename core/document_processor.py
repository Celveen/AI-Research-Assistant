from __future__ import annotations

import re
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


"""
语义感知切块（Semantic-aware chunking）
================================================

学术文献的语义粒度天然是「段落 > 句子 > 短语」，按字符硬切容易在句中、公式中、
列表中截断，导致检索时拿到半截语义。这里采用 **段落 → 句子 → 滑窗合并** 三段式：

1. 段落优先：按空行切段，段落已是天然的语义单元；
2. 句子兜底：超长段落用中英文句末标点（。！？.!?；;）切分，**不破坏句子内部**；
3. 滑窗合并：按句贪心拼接到接近 chunk_size，且相邻 chunk 共享若干「完整尾句」
   作为重叠（而非粗暴的字符级 overlap），保留上下文又不重复半截话。
"""

_SENTENCE_END_RE = re.compile(r"(?<=[。！？!?；;\.])\s+|(?<=[。！？；])")


def _split_paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _split_sentences(paragraph: str) -> list[str]:
    """将段落切为句子；保留句末标点，避免句中断裂。"""
    raw = _SENTENCE_END_RE.split(paragraph)
    sents = [s.strip() for s in raw if s and s.strip()]
    # 兜底：若仍存在超长「句子」（例如代码、公式、长 URL），按软长度切
    out: list[str] = []
    soft_max = max(settings.chunk_size, 400)
    for s in sents:
        if len(s) <= soft_max:
            out.append(s)
        else:
            out.extend(s[i : i + soft_max] for i in range(0, len(s), soft_max))
    return out


def _semantic_chunk(text: str, chunk_size: int, overlap_chars: int) -> list[str]:
    """以「句子」为最小单元贪心打包；用尾部若干完整句作为重叠。"""
    units: list[str] = []
    for para in _split_paragraphs(text):
        if len(para) <= chunk_size:
            units.append(para)
        else:
            units.extend(_split_sentences(para))

    chunks: list[str] = []
    buf: list[str] = []
    buf_len = 0

    def flush() -> None:
        nonlocal buf, buf_len
        if buf:
            chunks.append(" ".join(buf).strip())
            buf, buf_len = [], 0

    for u in units:
        u_len = len(u)
        sep_len = 1 if buf else 0
        if buf and buf_len + sep_len + u_len > chunk_size:
            flush()
            # 取上一 chunk 末尾若干完整句作为语义重叠
            if overlap_chars > 0 and chunks:
                tail_sents = _split_sentences(chunks[-1])
                acc = 0
                tail: list[str] = []
                for s in reversed(tail_sents):
                    if acc + len(s) > overlap_chars:
                        break
                    tail.insert(0, s)
                    acc += len(s)
                if tail:
                    buf = tail[:]
                    buf_len = sum(len(s) for s in buf) + max(len(buf) - 1, 0)
        buf.append(u)
        buf_len += u_len + sep_len

    flush()
    return [c for c in chunks if c]


def _split_text(text: str) -> list[str]:
    return _semantic_chunk(text, settings.chunk_size, settings.chunk_overlap)


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
