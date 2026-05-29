from __future__ import annotations

import re
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils import embedding_functions

from core.config import settings
from core.document_processor import Chunk
from utils.logger import get_logger

logger = get_logger("vector-store")


_client: chromadb.PersistentClient | None = None
_embedding_fn = None


def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=str(settings.vectorstore_path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


def _get_embedding_function():
    """默认使用 ChromaDB 内置的 ONNX 嵌入 (all-MiniLM-L6-v2)，无需 torch，开箱即用。"""
    global _embedding_fn
    if _embedding_fn is None:
        _embedding_fn = embedding_functions.DefaultEmbeddingFunction()
    return _embedding_fn


def _normalize_name(name: str) -> str:
    """Chroma collection name 限制: 3-63 字符, 字母数字下划线连字符, 首尾字母数字."""
    name = re.sub(r"[^A-Za-z0-9_-]", "_", name)
    name = name.strip("_-") or "doc"
    if len(name) < 3:
        name = (name + "_doc")[:63]
    return name[:63]


def add_documents(docs: list[Chunk], collection_name: str) -> int:
    """将 chunks 写入指定集合，返回写入条数。"""
    collection_name = _normalize_name(collection_name)
    client = _get_client()
    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=_get_embedding_function(),
        metadata={"hnsw:space": "cosine"},
    )

    ids = [f"{collection_name}-{i}" for i in range(collection.count(), collection.count() + len(docs))]
    contents = [d.content for d in docs]
    metadatas = [d.metadata for d in docs]

    collection.add(ids=ids, documents=contents, metadatas=metadatas)
    logger.info(f"集合 [{collection_name}] 新增 {len(docs)} 条向量")
    return len(docs)


def load_collection(collection_name: str):
    collection_name = _normalize_name(collection_name)
    client = _get_client()
    return client.get_collection(
        name=collection_name,
        embedding_function=_get_embedding_function(),
    )


def similarity_search(
    vectordb,
    query: str,
    k: int | None = None,
    adaptive: bool | None = None,
) -> list[dict[str, Any]]:
    """语义检索，返回 [{content, metadata, distance}]，按相关度升序（distance 越小越相关）。

    两种模式：
    - 固定 k：传入 k 或 adaptive=False 时，直接返回 top-k。
    - 自适应（默认）：先捞 fetch_k 大池，再按距离阈值动态保留 [min_k, max_k] 条。
      easy 问题命中强 → 返回少而精；宽泛/弱命中问题 → 自动多召回，避免漏答。
    """
    use_adaptive = settings.retriever_adaptive if adaptive is None else adaptive

    if not use_adaptive:
        top_k = k or settings.retriever_top_k
        res = vectordb.query(query_texts=[query], n_results=top_k)
        return _pack_results(res)

    # —— 自适应：大池召回 ——
    total = vectordb.count()
    fetch_k = min(settings.retriever_fetch_k, max(total, 1))
    res = vectordb.query(query_texts=[query], n_results=fetch_k)
    pool = _pack_results(res)  # 已按 distance 升序
    return _adaptive_filter(pool)


def _pack_results(res: dict[str, Any]) -> list[dict[str, Any]]:
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0] if res.get("distances") else [None] * len(docs)
    return [
        {"content": d, "metadata": m or {}, "distance": dist}
        for d, m, dist in zip(docs, metas, dists)
    ]


def _adaptive_filter(pool: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按距离阈值过滤，并夹在 [min_k, max_k] 区间内。"""
    min_k = settings.retriever_min_k
    max_k = settings.retriever_max_k
    threshold = settings.retriever_score_threshold

    if not pool:
        return []

    # 阈值过滤（distance 为 None 时视为通过，避免后端不返回距离时全空）
    kept = [r for r in pool if r["distance"] is None or r["distance"] <= threshold]

    # 不足 min_k：兜底取最相关的 min_k 条，保证模型仍有上下文
    if len(kept) < min_k:
        kept = pool[:min_k]

    # 超过 max_k：截断
    kept = kept[:max_k]

    logger.info(
        f"自适应检索：池 {len(pool)} → 阈值≤{threshold} 命中 "
        f"{sum(1 for r in pool if r['distance'] is not None and r['distance'] <= threshold)} → "
        f"返回 {len(kept)} 条"
    )
    return kept


def list_collections() -> list[str]:
    return [c.name for c in _get_client().list_collections()]


def list_documents(collection_name: str) -> list[dict[str, Any]]:
    """列出集合内的文献清单（按文件名聚合）：[{source, chunks, pages}]。"""
    collection = load_collection(collection_name)
    data = collection.get(include=["metadatas"])
    metas = data.get("metadatas") or []

    agg: dict[str, dict[str, Any]] = {}
    for m in metas:
        if not m:
            continue
        src = m.get("source", "unknown")
        page = m.get("page")
        entry = agg.setdefault(src, {"source": src, "chunks": 0, "_pages": set()})
        entry["chunks"] += 1
        if isinstance(page, int):
            entry["_pages"].add(page)

    out = []
    for e in agg.values():
        pages = e.pop("_pages")
        e["pages"] = max(pages) if pages else None
        out.append(e)
    return sorted(out, key=lambda x: x["source"])


def delete_document(collection_name: str, source: str) -> int:
    """从集合中删除某一篇文献（其全部 chunk）。返回删除的 chunk 数。"""
    collection = load_collection(collection_name)
    before = collection.count()
    collection.delete(where={"source": source})
    removed = before - collection.count()
    logger.info(f"集合 [{_normalize_name(collection_name)}] 删除文献 [{source}]，移除 {removed} 个 chunk")
    return removed


def delete_collection(collection_name: str) -> None:
    collection_name = _normalize_name(collection_name)
    _get_client().delete_collection(name=collection_name)
    logger.info(f"集合 [{collection_name}] 已删除")
