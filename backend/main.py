from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from core.config import settings
from core.document_processor import SUPPORTED_EXTENSIONS, process_file
from core.rag_chain import ask
from core.vector_store import (
    add_documents,
    delete_collection,
    delete_document,
    list_collections,
    list_documents,
    load_collection,
)
from utils.logger import get_logger

logger = get_logger("backend")

app = FastAPI(
    title="AI Research Assistant",
    description="基于 RAG 的学术论文智能问答系统 (DeepSeek-V4-Pro)",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    collection_name: str = Field(..., min_length=1)
    chat_history: list[dict[str, str]] = Field(default_factory=list)


class AskResponse(BaseModel):
    answer: str
    sources: list[dict[str, Any]]
    collection_name: str


class UploadResponse(BaseModel):
    filename: str
    collection_name: str
    chunks_count: int
    message: str


class BatchUploadFileResult(BaseModel):
    filename: str
    chunks_count: int
    status: str = "ok"
    error: str | None = None


class BatchUploadResponse(BaseModel):
    collection_name: str
    total_files: int
    total_chunks: int
    files: list[BatchUploadFileResult]
    message: str


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "service": "AI Research Assistant",
        "model": settings.llm_model,
        "docs": "/docs",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)) -> UploadResponse:
    """单文件上传（保留向后兼容）：集合名取文件名（去后缀）。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="缺少文件名")

    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {ext}（支持: {sorted(SUPPORTED_EXTENSIONS)}）",
        )

    save_path = settings.upload_path / file.filename
    content = await file.read()
    save_path.write_bytes(content)
    logger.info(f"已保存上传文件: {save_path} ({len(content)} bytes)")

    try:
        chunks = process_file(save_path)
        if not chunks:
            raise HTTPException(status_code=400, detail="文档解析后无可用内容")

        collection_name = Path(file.filename).stem
        add_documents(chunks, collection_name=collection_name)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("文档处理失败")
        raise HTTPException(status_code=500, detail=f"文档处理失败: {e}")

    return UploadResponse(
        filename=file.filename,
        collection_name=collection_name,
        chunks_count=len(chunks),
        message=f"✅ 文档处理完成，共生成 {len(chunks)} 个知识块",
    )


@app.post("/upload_batch", response_model=BatchUploadResponse)
async def upload_batch(
    files: list[UploadFile] = File(...),
    collection_name: str = Form(...),
) -> BatchUploadResponse:
    """多文件批量上传：所有文件归入同一集合（支持多论文文献综述场景）。"""
    if not files:
        raise HTTPException(status_code=400, detail="未提供任何文件")
    if not collection_name.strip():
        raise HTTPException(status_code=400, detail="集合名不能为空")

    results: list[BatchUploadFileResult] = []
    total_chunks = 0

    for f in files:
        if not f.filename:
            results.append(BatchUploadFileResult(filename="(unnamed)", chunks_count=0, status="error", error="缺少文件名"))
            continue
        ext = Path(f.filename).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            results.append(BatchUploadFileResult(filename=f.filename, chunks_count=0, status="skipped", error=f"不支持的类型 {ext}"))
            continue

        try:
            save_path = settings.upload_path / f.filename
            content = await f.read()
            save_path.write_bytes(content)
            chunks = process_file(save_path)
            if not chunks:
                results.append(BatchUploadFileResult(filename=f.filename, chunks_count=0, status="skipped", error="解析后无内容"))
                continue
            add_documents(chunks, collection_name=collection_name)
            total_chunks += len(chunks)
            results.append(BatchUploadFileResult(filename=f.filename, chunks_count=len(chunks)))
        except Exception as e:
            logger.exception(f"处理 {f.filename} 失败")
            results.append(BatchUploadFileResult(filename=f.filename, chunks_count=0, status="error", error=str(e)))

    ok_count = sum(1 for r in results if r.status == "ok")
    return BatchUploadResponse(
        collection_name=collection_name,
        total_files=ok_count,
        total_chunks=total_chunks,
        files=results,
        message=f"✅ 已将 {ok_count}/{len(files)} 个文件并入集合 [{collection_name}]，共 {total_chunks} 个知识块",
    )


@app.post("/ask", response_model=AskResponse)
def ask_endpoint(req: AskRequest) -> AskResponse:
    try:
        vectordb = load_collection(req.collection_name)
    except Exception:
        raise HTTPException(status_code=404, detail=f"集合不存在: {req.collection_name}")

    try:
        result = ask(req.question, vectordb, chat_history=req.chat_history)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("问答失败")
        raise HTTPException(status_code=500, detail=f"问答失败: {e}")

    return AskResponse(
        answer=result["answer"],
        sources=result["sources"],
        collection_name=req.collection_name,
    )


@app.get("/collections")
def collections() -> dict[str, list[str]]:
    return {"collections": list_collections()}


@app.get("/collection/{name}/documents")
def collection_documents(name: str) -> dict[str, Any]:
    """列出集合内的文献清单（按文件名聚合，含 chunk 数与页数）。"""
    try:
        docs = list_documents(name)
    except Exception:
        raise HTTPException(status_code=404, detail=f"集合不存在: {name}")
    return {
        "collection_name": name,
        "document_count": len(docs),
        "total_chunks": sum(d["chunks"] for d in docs),
        "documents": docs,
    }


@app.delete("/collection/{name}/document")
def remove_document(name: str, source: str) -> dict[str, Any]:
    """从集合中删除单篇文献（按文件名）。"""
    try:
        removed = delete_document(name, source)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"删除失败: {e}")
    if removed == 0:
        raise HTTPException(status_code=404, detail=f"集合 [{name}] 中未找到文献: {source}")
    return {"message": f"已从 [{name}] 删除文献 [{source}]，移除 {removed} 个 chunk", "removed_chunks": removed}


@app.delete("/collection/{name}")
def remove_collection(name: str) -> dict[str, str]:
    try:
        delete_collection(name)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"删除失败: {e}")
    return {"message": f"集合 [{name}] 已删除"}
