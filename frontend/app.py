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

# ====== 自定义样式（学术 · 极简）======
st.markdown(
    """
<style>
    :root {
        --ink: #1a1a1a;
        --ink-soft: #4b5563;
        --muted: #6b7280;
        --line: #e5e7eb;
        --paper: #fcfcfa;
        --paper-soft: #f6f5f1;
        --accent: #1f3a5f;
        --accent-soft: #eef2f7;
    }

    .stApp {
        background: var(--paper);
        font-family: 'Georgia', 'Source Serif Pro', 'Songti SC', 'Noto Serif SC', serif;
    }

    /* 排版：主区使用衬线，体现学术质感 */
    .stApp, .stApp p, .stApp li {
        color: var(--ink);
        font-size: 15.5px;
        line-height: 1.75;
    }
    .stApp h1, .stApp h2, .stApp h3 {
        font-family: 'Georgia', 'Songti SC', 'Noto Serif SC', serif;
        color: var(--ink);
        letter-spacing: -0.01em;
    }

    /* 顶部标题区 —— 纸张感、细横线分隔 */
    .hero {
        padding: 18px 4px 14px 4px;
        margin-bottom: 18px;
        border-bottom: 1px solid var(--line);
    }
    .hero h1 {
        margin: 0 0 4px 0;
        font-size: 28px;
        font-weight: 600;
        color: var(--ink);
    }
    .hero .subtitle {
        margin: 0;
        font-size: 13.5px;
        color: var(--muted);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        letter-spacing: 0.02em;
    }
    .hero .meta {
        display: inline-block;
        margin-left: 10px;
        padding: 2px 8px;
        font-size: 11px;
        font-family: 'JetBrains Mono', 'SF Mono', Menlo, monospace;
        color: var(--ink-soft);
        background: var(--accent-soft);
        border-radius: 4px;
        letter-spacing: 0.04em;
    }

    /* 章节标题 */
    .section-title {
        font-size: 13px;
        font-weight: 600;
        color: var(--ink-soft);
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin: 0 0 10px 0;
        font-family: 'Inter', -apple-system, sans-serif;
    }

    /* 当前集合显示 */
    .meta-line {
        font-size: 12.5px;
        color: var(--muted);
        font-family: 'Inter', sans-serif;
        margin-bottom: 14px;
        padding-bottom: 10px;
        border-bottom: 1px dashed var(--line);
    }
    .meta-line b {
        color: var(--accent);
        font-weight: 600;
        font-family: 'JetBrains Mono', 'SF Mono', monospace;
        font-size: 12px;
    }

    /* 侧边栏 */
    section[data-testid="stSidebar"] {
        background: var(--paper-soft);
        border-right: 1px solid var(--line);
    }
    section[data-testid="stSidebar"] * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    section[data-testid="stSidebar"] .stButton button {
        width: 100%;
        border-radius: 6px;
        border: 1px solid var(--line);
        background: #ffffff;
        color: var(--ink-soft);
        font-weight: 500;
        font-size: 13.5px;
        transition: border-color 0.15s, color 0.15s;
        box-shadow: none;
    }
    section[data-testid="stSidebar"] .stButton button:hover {
        border-color: var(--accent);
        color: var(--accent);
        background: #ffffff;
    }

    /* 主操作按钮 */
    .stButton button[kind="primary"] {
        background: var(--accent);
        border: 1px solid var(--accent);
        color: #ffffff;
        font-weight: 500;
        border-radius: 6px;
        box-shadow: none;
    }
    .stButton button[kind="primary"]:hover {
        background: #16304d;
        border-color: #16304d;
    }
    .stButton button[kind="primary"]:disabled {
        background: #cfd5dd;
        border-color: #cfd5dd;
        color: #ffffff;
    }

    /* 聊天气泡：克制的线框 */
    div[data-testid="stChatMessage"] {
        background: #ffffff;
        border-radius: 8px;
        padding: 14px 20px;
        border: 1px solid var(--line);
        box-shadow: none;
        margin-bottom: 12px;
    }

    /* 输入框 */
    div[data-testid="stChatInput"] textarea {
        border-radius: 8px !important;
        border: 1px solid var(--line) !important;
        font-family: 'Georgia', 'Songti SC', serif !important;
        font-size: 15px !important;
    }

    /* 来源徽章 */
    .source-badge {
        display: inline-block;
        padding: 2px 8px;
        background: #ffffff;
        color: var(--accent);
        border: 1px solid var(--accent);
        border-radius: 3px;
        font-size: 11px;
        font-family: 'JetBrains Mono', 'SF Mono', monospace;
        margin: 2px 4px 2px 0;
    }
    .source-page {
        display: inline-block;
        padding: 1px 6px;
        background: var(--accent-soft);
        color: var(--accent);
        border-radius: 3px;
        font-size: 11px;
        font-family: 'JetBrains Mono', 'SF Mono', monospace;
        font-weight: 500;
    }

    /* 文件明细行 */
    .file-row {
        padding: 6px 10px;
        border-bottom: 1px solid var(--line);
        font-size: 12.5px;
        color: var(--ink-soft);
        display: flex;
        justify-content: space-between;
        font-family: 'Inter', sans-serif;
    }
    .file-row:last-child { border-bottom: none; }

    /* 引用面板 */
    .ref-panel {
        padding: 14px 0 0 0;
        border-left: 2px solid var(--line);
        padding-left: 20px;
    }
    .ref-panel .section-title {
        margin-bottom: 14px;
    }

    /* 隐藏默认 chrome */
    #MainMenu, footer {visibility: hidden;}
    header[data-testid="stHeader"] {background: transparent;}

    /* expander 简化 */
    div[data-testid="stExpander"] {
        border: 1px solid var(--line);
        border-radius: 6px;
        background: #ffffff;
    }
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
  <h1>AI Research Assistant</h1>
  <p class="subtitle">
    基于检索增强生成（RAG）的学术文献阅读与问答工作台
    <span class="meta">DeepSeek-V4-Pro</span>
  </p>
</div>
""",
    unsafe_allow_html=True,
)


# ====== Sidebar ======
with st.sidebar:
    st.markdown("<p class='section-title'>I · 文献入库</p>", unsafe_allow_html=True)

    existing = refresh_collections()
    mode = st.radio(
        "归入集合",
        ["新建集合", "追加到已有集合"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if mode == "新建集合":
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
        "上传并入库",
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
        with st.expander("最近一次上传明细", expanded=False):
            for f in st.session_state.upload_log:
                marker = "·" if f["status"] == "ok" else ("‒" if f["status"] == "skipped" else "×")
                detail = f"{f['chunks_count']} chunks" if f["status"] == "ok" else (f.get("error") or "")
                st.markdown(
                    f"<div class='file-row'><span>{marker}&nbsp;&nbsp;{f['filename']}</span>"
                    f"<span style='color:#9ca3af'>{detail}</span></div>",
                    unsafe_allow_html=True,
                )

    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
    st.markdown("<p class='section-title'>II · 文献集合</p>", unsafe_allow_html=True)
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

        if st.button("删除当前集合", use_container_width=True):
            try:
                api_delete(f"/collection/{selected}")
                st.success(f"已删除: {selected}")
                st.session_state.current_collection = None
                st.rerun()
            except Exception as e:
                st.error(f"删除失败: {e}")
    else:
        st.info("尚无文档，请先上传。")

    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
    if st.button("清空对话历史", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.last_sources = []
        st.rerun()


# ====== Main area ======
main_col, side_col = st.columns([2, 1], gap="large")

with main_col:
    st.markdown("<p class='section-title'>对话</p>", unsafe_allow_html=True)
    if st.session_state.current_collection:
        st.markdown(
            f"<div class='meta-line'>当前集合 · <b>{st.session_state.current_collection}</b></div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div class='meta-line'>请先在左侧选择或上传集合后开始提问</div>",
            unsafe_allow_html=True,
        )

    for turn in st.session_state.chat_history:
        with st.chat_message(turn["role"]):
            st.markdown(turn["content"])

    question = st.chat_input("提问任何关于这些文献的问题…")
    if question:
        if not st.session_state.current_collection:
            st.warning("请先在左侧上传文档或选择一个文档集合。")
        else:
            st.session_state.chat_history.append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)

            with st.chat_message("assistant"):
                placeholder = st.empty()
                placeholder.markdown("_正在检索文献并整理回答…_")
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
        "<div class='ref-panel'><p class='section-title'>引用来源</p>",
        unsafe_allow_html=True,
    )

    if not st.session_state.last_sources:
        st.markdown(
            "<p style='color:#9ca3af;font-size:13px;font-family:Inter,sans-serif'>"
            "发起一次提问后，模型引用的原文片段将在此列出。</p>",
            unsafe_allow_html=True,
        )
    else:
        unique_files = sorted({s.get("source", "?") for s in st.session_state.last_sources})
        st.markdown(
            "<div style='margin-bottom:14px;font-size:12px;color:#6b7280;"
            "font-family:Inter,sans-serif'>涉及文献</div>"
            + "<div>"
            + "".join(f"<span class='source-badge'>{f}</span>" for f in unique_files)
            + "</div>",
            unsafe_allow_html=True,
        )
        st.write("")

        for i, s in enumerate(st.session_state.last_sources, 1):
            label = f"[{i}] {s.get('source', '?')} · p.{s.get('page', '?')}"
            with st.expander(label, expanded=(i == 1)):
                st.markdown(
                    f"<span class='source-page'>page {s.get('page', '?')}</span>",
                    unsafe_allow_html=True,
                )
                st.write(s.get("preview", ""))

    st.markdown("</div>", unsafe_allow_html=True)
