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


def similarity_search(vectordb, query: str, k: int | None = None) -> list[dict[str, Any]]:
    """返回 top-k 相关 chunks，结构: [{content, metadata, distance}]"""
    k = k or settings.retriever_top_k
    res = vectordb.query(query_texts=[query], n_results=k)

    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0] if res.get("distances") else [None] * len(docs)

    return [
        {"content": d, "metadata": m or {}, "distance": dist}
        for d, m, dist in zip(docs, metas, dists)
    ]


def list_collections() -> list[str]:
    return [c.name for c in _get_client().list_collections()]


def delete_collection(collection_name: str) -> None:
    collection_name = _normalize_name(collection_name)
    _get_client().delete_collection(name=collection_name)
    logger.info(f"集合 [{collection_name}] 已删除")
