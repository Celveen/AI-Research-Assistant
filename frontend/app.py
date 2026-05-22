from __future__ import annotations

import os
import re

import httpx
import streamlit as st

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

st.set_page_config(
    page_title="AI Research Assistant",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ====== 自定义样式 ======
st.markdown(
    """
<style>
    /* 主背景渐变 */
    .stApp {
        background: linear-gradient(135deg, #f5f7fa 0%, #eef2f7 100%);
    }

    /* 标题区 */
    .hero {
        padding: 20px 28px;
        border-radius: 16px;
        background: linear-gradient(120deg, #4f46e5 0%, #7c3aed 50%, #ec4899 100%);
        color: #ffffff;
        margin-bottom: 18px;
        box-shadow: 0 8px 24px rgba(79, 70, 229, 0.18);
    }
    .hero h1 {
        margin: 0 0 6px 0;
        font-size: 26px;
        font-weight: 700;
        color: #fff;
    }
    .hero p {
        margin: 0;
        opacity: 0.92;
        font-size: 13px;
    }

    /* 卡片 */
    .card {
        background: #ffffff;
        border-radius: 14px;
        padding: 18px 20px;
        box-shadow: 0 2px 12px rgba(15, 23, 42, 0.06);
        border: 1px solid #e5e7eb;
        margin-bottom: 14px;
    }
    .card h3 {
        margin: 0 0 12px 0;
        font-size: 15px;
        color: #1e293b;
        font-weight: 600;
    }

    /* 侧边栏 */
    section[data-testid="stSidebar"] {
        background: #ffffff;
        border-right: 1px solid #e5e7eb;
    }
    section[data-testid="stSidebar"] .stButton button {
        width: 100%;
        border-radius: 10px;
        border: 1px solid #e5e7eb;
        background: #f8fafc;
        color: #334155;
        font-weight: 500;
        transition: all 0.15s ease;
    }
    section[data-testid="stSidebar"] .stButton button:hover {
        background: #4f46e5;
        color: white;
        border-color: #4f46e5;
        transform: translateY(-1px);
    }

    /* 主按钮 */
    .stButton button[kind="primary"] {
        background: linear-gradient(120deg, #4f46e5, #7c3aed);
        border: none;
        color: white;
        font-weight: 600;
        border-radius: 10px;
    }

    /* 聊天气泡 */
    div[data-testid="stChatMessage"] {
        background: #ffffff;
        border-radius: 14px;
        padding: 14px 18px;
        box-shadow: 0 1px 8px rgba(15, 23, 42, 0.05);
        border: 1px solid #eef0f4;
        margin-bottom: 8px;
    }

    /* 输入框 */
    div[data-testid="stChatInput"] textarea {
        border-radius: 14px !important;
        border: 1px solid #e5e7eb !important;
    }

    /* 来源徽章 */
    .source-badge {
        display: inline-block;
        padding: 2px 10px;
        background: #ede9fe;
        color: #6d28d9;
        border-radius: 999px;
        font-size: 11px;
        font-weight: 600;
        margin-right: 6px;
    }
    .source-page {
        display: inline-block;
        padding: 2px 8px;
        background: #fce7f3;
        color: #be185d;
        border-radius: 999px;
        font-size: 11px;
        font-weight: 600;
    }

    /* 文件状态行 */
    .file-row {
        padding: 6px 10px;
        border-radius: 8px;
        background: #f8fafc;
        margin: 4px 0;
        font-size: 13px;
        display: flex;
        justify-content: space-between;
    }

    /* hide streamlit default chrome */
    #MainMenu, footer {visibility: hidden;}
    header[data-testid="stHeader"] {background: transparent;}
</style>
""",
    unsafe_allow_html=True,
)


# ====== HTTP helpers ======
def api_get(path: str, **kw):
    return httpx.get(f"{BACKEND_URL}{path}", timeout=30, **kw)


def api_post(path: str, **kw):
    return httpx.post(f"{BACKEND_URL}{path}", timeout=180, **kw)


def api_delete(path: str, **kw):
    return httpx.delete(f"{BACKEND_URL}{path}", timeout=30, **kw)


def refresh_collections() -> list[str]:
    try:
        r = api_get("/collections")
        r.raise_for_status()
        return sorted(r.json().get("collections", []))
    except Exception as e:
        st.error(f"无法连接后端 ({BACKEND_URL}): {e}")
        return []


def normalize_name(name: str) -> str:
    n = re.sub(r"[^A-Za-z0-9_-]", "_", name).strip("_-") or "doc"
    if len(n) < 3:
        n = (n + "_doc")[:63]
    return n[:63]


# ====== Session state ======
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "current_collection" not in st.session_state:
    st.session_state.current_collection = None
if "last_sources" not in st.session_state:
    st.session_state.last_sources = []
if "upload_log" not in st.session_state:
    st.session_state.upload_log = []


# ====== Hero header ======
st.markdown(
    """
<div class="hero">
  <h1>🔬 AI Research Assistant</h1>
  <p>基于 RAG 的学术论文智能问答 · DeepSeek-V4-Pro · 支持多论文同集合检索</p>
</div>
""",
    unsafe_allow_html=True,
)


# ====== Sidebar ======
with st.sidebar:
    st.markdown("### 📤 批量上传文献")

    existing = refresh_collections()
    mode = st.radio(
        "归入集合",
        ["🆕 新建集合", "➕ 追加到已有集合"],
        horizontal=False,
        label_visibility="collapsed",
    )

    if mode.startswith("🆕"):
        coll_input = st.text_input(
            "集合名称",
            value="my_review",
            help="同一集合下的多篇论文会被合并检索，适合做文献综述。仅允许英文/数字/下划线/连字符。",
        )
        target_collection = normalize_name(coll_input)
        if coll_input and target_collection != coll_input:
            st.caption(f"已规范化为：`{target_collection}`")
    else:
        if not existing:
            st.info("当前还没有集合，请先新建一个。")
            target_collection = None
        else:
            target_collection = st.selectbox("选择已有集合", existing)

    uploaded_files = st.file_uploader(
        "选择文件（可多选）",
        type=["pdf", "txt", "md", "docx"],
        accept_multiple_files=True,
    )

    if uploaded_files:
        st.caption(f"已选择 **{len(uploaded_files)}** 个文件")

    upload_disabled = not (uploaded_files and target_collection)
    if st.button(
        "🚀 上传并入库",
        type="primary",
        use_container_width=True,
        disabled=upload_disabled,
    ):
        with st.spinner(f"正在处理 {len(uploaded_files)} 个文件..."):
            try:
                files_payload = [
                    ("files", (f.name, f.getvalue(), f.type or "application/octet-stream"))
                    for f in uploaded_files
                ]
                r = api_post(
                    "/upload_batch",
                    files=files_payload,
                    data={"collection_name": target_collection},
                )
                r.raise_for_status()
                data = r.json()
                st.success(data["message"])
                st.session_state.current_collection = data["collection_name"]
                st.session_state.upload_log = data["files"]
            except httpx.HTTPStatusError as e:
                st.error(f"上传失败: {e.response.text}")
            except Exception as e:
                st.error(f"上传失败: {e}")

    if st.session_state.upload_log:
        with st.expander("📋 最近一次上传明细", expanded=False):
            for f in st.session_state.upload_log:
                icon = "✅" if f["status"] == "ok" else ("⚠️" if f["status"] == "skipped" else "❌")
                detail = f"{f['chunks_count']} chunks" if f["status"] == "ok" else (f.get("error") or "")
                st.markdown(
                    f"<div class='file-row'><span>{icon} {f['filename']}</span>"
                    f"<span style='color:#64748b'>{detail}</span></div>",
                    unsafe_allow_html=True,
                )

    st.divider()
    st.markdown("### 📚 文档集合")
    existing = refresh_collections()
    if existing:
        default_idx = (
            existing.index(st.session_state.current_collection)
            if st.session_state.current_collection in existing
            else 0
        )
        selected = st.selectbox(
            "当前提问的集合",
            existing,
            index=default_idx,
            key="active_collection_select",
        )
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


# ====== Main area ======
main_col, side_col = st.columns([2, 1], gap="large")

with main_col:
    st.markdown(
        "<div class='card'><h3>💬 与你的文献对话</h3>"
        + (
            f"<div style='color:#64748b;font-size:13px'>当前集合：<b style='color:#4f46e5'>{st.session_state.current_collection}</b></div>"
            if st.session_state.current_collection
            else "<div style='color:#94a3b8;font-size:13px'>请先在左侧选择或上传集合</div>"
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    for turn in st.session_state.chat_history:
        avatar = "🧑‍🔬" if turn["role"] == "user" else "🤖"
        with st.chat_message(turn["role"], avatar=avatar):
            st.markdown(turn["content"])

    question = st.chat_input("提问任何关于这些文献的问题，例如：这些论文的方法有何异同？")
    if question:
        if not st.session_state.current_collection:
            st.warning("请先在左侧上传文档或选择一个文档集合。")
        else:
            st.session_state.chat_history.append({"role": "user", "content": question})
            with st.chat_message("user", avatar="🧑‍🔬"):
                st.markdown(question)

            with st.chat_message("assistant", avatar="🤖"):
                placeholder = st.empty()
                placeholder.markdown("⏳ 正在检索文献并思考...")
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
    st.markdown(
        "<div class='card'><h3>📎 引用来源</h3></div>",
        unsafe_allow_html=True,
    )

    if not st.session_state.last_sources:
        st.caption("发起一次提问后，这里会展示模型引用的原文片段。")
    else:
        unique_files = sorted({s.get("source", "?") for s in st.session_state.last_sources})
        st.markdown(
            "**涉及文件：** "
            + " ".join(
                f"<span class='source-badge'>{f}</span>" for f in unique_files
            ),
            unsafe_allow_html=True,
        )
        st.write("")

        for i, s in enumerate(st.session_state.last_sources, 1):
            label = f"#{i} · {s.get('source', '?')} · 第 {s.get('page', '?')} 页"
            with st.expander(label, expanded=(i == 1)):
                st.markdown(
                    f"<span class='source-page'>page {s.get('page', '?')}</span>",
                    unsafe_allow_html=True,
                )
                st.write(s.get("preview", ""))
