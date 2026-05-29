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

# ====== 自定义样式（GitHub 风 · 学术极简）======
# 注意：不要把字体规则下到 .stApp / 全局，否则会覆盖 Streamlit 的 Material Symbols
# 图标字体，导致按钮显示成 "upload"、"keyboard_double_arrow_left" 这样的字面字符串。
st.markdown(
    """
<style>
    :root {
        --ink: #1f2328;
        --ink-soft: #424a53;
        --muted: #656d76;
        --line: #d0d7de;
        --line-soft: #eaeef2;
        --canvas: #ffffff;
        --canvas-subtle: #f6f8fa;
        --accent: #0969da;          /* GitHub blue */
        --accent-soft: #ddf4ff;
        --success: #1a7f37;
        --success-soft: #dafbe1;
        --purple: #8250df;
        --purple-soft: #fbefff;
    }

    .stApp { background: var(--canvas); }

    /* 文本字体限定到具体的「文本」元素，避免污染图标 / 按钮 */
    .stApp p, .stApp li, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
    .stApp h5, .stApp h6, .stApp label, .stApp [data-testid="stMarkdownContainer"],
    div[data-testid="stChatMessage"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans",
                     "PingFang SC", "Microsoft YaHei", Helvetica, Arial, sans-serif;
        color: var(--ink);
    }
    .stApp p, .stApp li, div[data-testid="stChatMessage"] {
        font-size: 14.5px;
        line-height: 1.7;
    }

    /* 整体上移：缩小主区与侧栏顶部内边距 */
    .stApp .main .block-container,
    section.main > div.block-container,
    div[data-testid="stAppViewContainer"] > section > div.block-container {
        padding-top: 0.8rem !important;
        padding-bottom: 2rem !important;
    }
    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 1rem !important;
    }

    /* 强制保留 Material Symbols 图标字体（修复 upload / 收起侧栏按钮乱码） */
    [data-testid="stIconMaterial"],
    span.material-symbols-rounded,
    span.material-symbols-outlined,
    span.material-icons,
    button[kind] [data-testid="stIconMaterial"] {
        font-family: 'Material Symbols Rounded', 'Material Symbols Outlined',
                     'Material Icons' !important;
        font-weight: normal !important;
        font-style: normal !important;
        font-feature-settings: 'liga' !important;
    }

    /* ===== Hero 区 —— GitHub 仓库 header 风 ===== */
    .hero {
        padding: 4px 0 14px 0;
        margin-bottom: 18px;
        border-bottom: 1px solid var(--line);
    }
    .hero-title {
        display: flex;
        align-items: center;
        gap: 10px;
        margin: 0 0 6px 0;
    }
    .hero-title h1 {
        margin: 0;
        font-size: 22px;
        font-weight: 600;
        color: var(--ink);
        letter-spacing: -0.01em;
    }
    .hero-title .repo-mark {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 26px; height: 26px;
        border: 1px solid var(--line);
        border-radius: 6px;
        background: var(--canvas-subtle);
        font-size: 14px;
    }
    .hero-subtitle {
        margin: 0;
        font-size: 13px;
        color: var(--muted);
    }
    .hero-meta {
        margin-top: 8px;
        display: flex;
        gap: 6px;
        flex-wrap: wrap;
    }

    /* ===== 通用徽章（GitHub Label 风） ===== */
    .pill {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 2px 8px;
        border-radius: 999px;
        font-size: 11.5px;
        font-weight: 500;
        font-family: -apple-system, "Segoe UI", sans-serif;
        line-height: 1.6;
    }
    .pill-blue   { background: var(--accent-soft);  color: var(--accent); border: 1px solid #b6e3ff;}
    .pill-green  { background: var(--success-soft); color: var(--success); border: 1px solid #aceebb;}
    .pill-purple { background: var(--purple-soft);  color: var(--purple); border: 1px solid #ecd5ff;}
    .pill-gray   { background: var(--canvas-subtle); color: var(--ink-soft); border: 1px solid var(--line);}

    /* ===== 章节标题 ===== */
    .section-title {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 12px;
        font-weight: 600;
        color: var(--ink-soft);
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin: 0 0 10px 0;
    }
    .section-title .dot {
        display: inline-block;
        width: 6px; height: 6px;
        border-radius: 50%;
        background: var(--accent);
    }

    /* 当前集合元信息行 */
    .meta-line {
        font-size: 12.5px;
        color: var(--muted);
        margin-bottom: 14px;
        padding: 8px 12px;
        background: var(--canvas-subtle);
        border: 1px solid var(--line-soft);
        border-radius: 6px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .meta-line code {
        background: transparent;
        color: var(--accent);
        font-weight: 600;
        font-size: 12.5px;
        padding: 0;
    }

    /* ===== 侧边栏 ===== */
    section[data-testid="stSidebar"] {
        background: var(--canvas-subtle);
        border-right: 1px solid var(--line);
    }
    section[data-testid="stSidebar"] .stButton button {
        width: 100%;
        border-radius: 6px;
        border: 1px solid var(--line);
        background: var(--canvas);
        color: var(--ink);
        font-weight: 500;
        font-size: 13.5px;
        box-shadow: 0 1px 0 rgba(31,35,40,.04);
        transition: all 0.12s ease;
    }
    section[data-testid="stSidebar"] .stButton button:hover {
        background: var(--canvas-subtle);
        border-color: var(--accent);
        color: var(--accent);
    }

    /* 主操作按钮（GitHub primary green） */
    .stButton button[kind="primary"] {
        background: linear-gradient(180deg, #2da44e, #2c974b);
        border: 1px solid rgba(31,35,40,.15);
        color: #ffffff;
        font-weight: 600;
        border-radius: 6px;
        box-shadow: 0 1px 0 rgba(31,35,40,.1), inset 0 1px 0 rgba(255,255,255,.03);
    }
    .stButton button[kind="primary"]:hover {
        background: linear-gradient(180deg, #2c974b, #298e46);
    }
    .stButton button[kind="primary"]:disabled {
        background: #94d3a2;
        color: #ffffff;
    }

    /* 聊天气泡 */
    div[data-testid="stChatMessage"] {
        background: var(--canvas);
        border-radius: 8px;
        padding: 14px 18px;
        border: 1px solid var(--line);
        box-shadow: none;
        margin-bottom: 10px;
    }

    /* 输入框 */
    div[data-testid="stChatInput"] textarea {
        border-radius: 8px !important;
        border: 1px solid var(--line) !important;
        font-size: 14.5px !important;
    }
    div[data-testid="stChatInput"] textarea:focus {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 3px rgba(9,105,218,0.15) !important;
    }

    /* 来源徽章 */
    .source-badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 2px 8px;
        background: var(--accent-soft);
        color: var(--accent);
        border: 1px solid #b6e3ff;
        border-radius: 12px;
        font-size: 11.5px;
        font-weight: 500;
        margin: 2px 4px 2px 0;
    }
    .source-page {
        display: inline-block;
        padding: 1px 7px;
        background: var(--purple-soft);
        color: var(--purple);
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
        font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace;
    }

    /* 文件明细行 */
    .file-row {
        padding: 8px 10px;
        border-bottom: 1px solid var(--line-soft);
        font-size: 13px;
        color: var(--ink-soft);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .file-row:last-child { border-bottom: none; }
    .file-row .right { color: var(--muted); font-size: 12px;
        font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace; }

    /* 引用面板 */
    .ref-panel {
        padding: 8px 0 0 0;
        border-left: 2px solid var(--line);
        padding-left: 18px;
    }

    /* 隐藏默认 chrome */
    #MainMenu, footer {visibility: hidden;}
    header[data-testid="stHeader"] {background: transparent;}

    /* expander */
    div[data-testid="stExpander"] {
        border: 1px solid var(--line);
        border-radius: 6px;
        background: var(--canvas);
    }
    div[data-testid="stExpander"] summary {
        font-size: 13px !important;
        color: var(--ink-soft);
    }

    /* radio 紧凑化 */
    div[data-testid="stRadio"] label {
        font-size: 13px !important;
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


def fetch_documents(collection: str) -> dict:
    try:
        r = api_get(f"/collection/{collection}/documents")
        r.raise_for_status()
        return r.json()
    except Exception:
        return {"documents": [], "document_count": 0, "total_chunks": 0}


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
  <div class="hero-title">
    <span class="repo-mark">📖</span>
    <h1>AI Research Assistant</h1>
  </div>
  <p class="hero-subtitle">基于检索增强生成（RAG）的学术文献阅读与问答工作台</p>
  <div class="hero-meta">
    <span class="pill pill-blue">⚡ DeepSeek-V4-Pro</span>
    <span class="pill pill-green">🧩 Semantic Chunking</span>
    <span class="pill pill-purple">🔍 ChromaDB · top-k</span>
    <span class="pill pill-gray">📚 Multi-Paper Collection</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)


# ====== Sidebar ======
with st.sidebar:
    st.markdown(
        "<p class='section-title'><span class='dot'></span>📥 文献入库</p>",
        unsafe_allow_html=True,
    )

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
        "🚀  上传并入库",
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
                if f["status"] == "ok":
                    marker = "🟢"
                elif f["status"] == "skipped":
                    marker = "🟡"
                else:
                    marker = "🔴"
                detail = f"{f['chunks_count']} chunks" if f["status"] == "ok" else (f.get("error") or "")
                st.markdown(
                    f"<div class='file-row'><span>{marker}&nbsp;&nbsp;{f['filename']}</span>"
                    f"<span class='right'>{detail}</span></div>",
                    unsafe_allow_html=True,
                )

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    st.markdown(
        "<p class='section-title'><span class='dot'></span>📚 文献集合</p>",
        unsafe_allow_html=True,
    )
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

        # —— 集合内文献清单 ——
        info = fetch_documents(selected)
        docs = info.get("documents", [])
        st.markdown(
            f"<div style='font-size:12px;color:#656d76;margin:6px 0 8px 0;'>"
            f"📄 {info.get('document_count', 0)} 篇文献 · "
            f"{info.get('total_chunks', 0)} chunks</div>",
            unsafe_allow_html=True,
        )
        if docs:
            for d in docs:
                c1, c2 = st.columns([5, 1])
                with c1:
                    pages = f"· {d['pages']}p" if d.get("pages") else ""
                    st.markdown(
                        f"<div class='file-row' style='padding:6px 4px;'>"
                        f"<span>📑 {d['source']}</span>"
                        f"<span class='right'>{d['chunks']} chunks {pages}</span></div>",
                        unsafe_allow_html=True,
                    )
                with c2:
                    if st.button("✕", key=f"del_{selected}_{d['source']}", help=f"删除 {d['source']}"):
                        try:
                            api_delete(
                                f"/collection/{selected}/document",
                                params={"source": d["source"]},
                            )
                            st.toast(f"已删除 {d['source']}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"删除失败: {e}")

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        if st.button("🗑️  删除当前集合", use_container_width=True):
            try:
                api_delete(f"/collection/{selected}")
                st.success(f"已删除: {selected}")
                st.session_state.current_collection = None
                st.rerun()
            except Exception as e:
                st.error(f"删除失败: {e}")
    else:
        st.info("尚无文档，请先上传。")

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    if st.button("🧹  清空对话历史", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.last_sources = []
        st.rerun()


# ====== Main area ======
main_col, side_col = st.columns([2, 1], gap="large")

with main_col:
    st.markdown(
        "<p class='section-title'><span class='dot'></span>💬 对话</p>",
        unsafe_allow_html=True,
    )
    if st.session_state.current_collection:
        st.markdown(
            f"<div class='meta-line'>📂 当前集合 · <code>{st.session_state.current_collection}</code>"
            f"<span style='margin-left:auto'><span class='pill pill-gray'>chat history × "
            f"{len(st.session_state.chat_history)}</span></span></div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div class='meta-line'>👈 请先在左侧上传或选择集合后开始提问</div>",
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
        "<div class='ref-panel'><p class='section-title'><span class='dot'></span>🔖 引用来源</p>",
        unsafe_allow_html=True,
    )

    if not st.session_state.last_sources:
        st.markdown(
            "<p style='color:#8c959f;font-size:13px;margin-top:8px;'>"
            "💡 发起一次提问后，模型引用的原文片段将在此列出。</p>",
            unsafe_allow_html=True,
        )
    else:
        unique_files = sorted({s.get("source", "?") for s in st.session_state.last_sources})
        st.markdown(
            "<div style='margin-bottom:10px;font-size:12px;color:#656d76;'>📄 涉及文献</div>"
            + "<div>"
            + "".join(f"<span class='source-badge'>📑 {f}</span>" for f in unique_files)
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
