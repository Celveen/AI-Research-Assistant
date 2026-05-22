from __future__ import annotations

import os
from pathlib import Path

import httpx
import streamlit as st

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

st.set_page_config(
    page_title="AI Research Assistant",
    page_icon="🔬",
    layout="wide",
)


def api_get(path: str, **kw):
    return httpx.get(f"{BACKEND_URL}{path}", timeout=30, **kw)


def api_post(path: str, **kw):
    return httpx.post(f"{BACKEND_URL}{path}", timeout=120, **kw)


def api_delete(path: str, **kw):
    return httpx.delete(f"{BACKEND_URL}{path}", timeout=30, **kw)


def refresh_collections() -> list[str]:
    try:
        r = api_get("/collections")
        r.raise_for_status()
        return r.json().get("collections", [])
    except Exception as e:
        st.error(f"无法连接后端 ({BACKEND_URL}): {e}")
        return []


if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "current_collection" not in st.session_state:
    st.session_state.current_collection = None
if "last_sources" not in st.session_state:
    st.session_state.last_sources = []

st.title("🔬 AI Research Assistant")
st.caption("基于 RAG 的学术论文智能问答 · DeepSeek-V4-Pro")

with st.sidebar:
    st.header("📄 文档管理")

    uploaded = st.file_uploader(
        "上传论文 (PDF / TXT / MD / DOCX)",
        type=["pdf", "txt", "md", "docx"],
        accept_multiple_files=False,
    )
    if uploaded is not None:
        if st.button("📤 上传并处理", use_container_width=True):
            with st.spinner(f"正在解析 {uploaded.name} ..."):
                try:
                    files = {"file": (uploaded.name, uploaded.getvalue())}
                    r = api_post("/upload", files=files)
                    r.raise_for_status()
                    data = r.json()
                    st.success(data["message"])
                    st.session_state.current_collection = data["collection_name"]
                except httpx.HTTPStatusError as e:
                    st.error(f"上传失败: {e.response.text}")
                except Exception as e:
                    st.error(f"上传失败: {e}")

    st.divider()
    st.header("📚 文档集合")
    cols = refresh_collections()
    if cols:
        default_idx = (
            cols.index(st.session_state.current_collection)
            if st.session_state.current_collection in cols
            else 0
        )
        selected = st.selectbox("选择文档", cols, index=default_idx)
        st.session_state.current_collection = selected

        if st.button("🗑️ 删除当前集合", use_container_width=True):
            try:
                api_delete(f"/collection/{selected}")
                st.success(f"已删除: {selected}")
                st.session_state.current_collection = None
                st.rerun()
            except Exception as e:
                st.error(f"删除失败: {e}")
    else:
        st.info("尚无文档，请先上传。")

    st.divider()
    if st.button("🧹 清空对话历史", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.last_sources = []
        st.rerun()


main_col, side_col = st.columns([2, 1])

with main_col:
    st.subheader("💬 问答")

    for turn in st.session_state.chat_history:
        with st.chat_message(turn["role"]):
            st.markdown(turn["content"])

    question = st.chat_input("输入你的问题...")
    if question:
        if not st.session_state.current_collection:
            st.warning("请先在左侧上传文档或选择一个文档集合。")
        else:
            st.session_state.chat_history.append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)

            with st.chat_message("assistant"):
                placeholder = st.empty()
                placeholder.markdown("⏳ 思考中...")
                try:
                    r = api_post(
                        "/ask",
                        json={
                            "question": question,
                            "collection_name": st.session_state.current_collection,
                            "chat_history": st.session_state.chat_history[:-1],
                        },
                    )
                    r.raise_for_status()
                    data = r.json()
                    placeholder.markdown(data["answer"])
                    st.session_state.chat_history.append(
                        {"role": "assistant", "content": data["answer"]}
                    )
                    st.session_state.last_sources = data.get("sources", [])
                except httpx.HTTPStatusError as e:
                    placeholder.error(f"请求失败: {e.response.text}")
                except Exception as e:
                    placeholder.error(f"请求失败: {e}")

with side_col:
    st.subheader("📎 引用来源")
    if not st.session_state.last_sources:
        st.caption("发起一次提问后，这里会展示模型引用的原文片段。")
    else:
        for i, s in enumerate(st.session_state.last_sources, 1):
            with st.expander(
                f"#{i} {s.get('source', 'unknown')} · 第 {s.get('page', '?')} 页",
                expanded=(i == 1),
            ):
                st.write(s.get("preview", ""))
