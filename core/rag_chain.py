from __future__ import annotations

from typing import Any, Iterator

from openai import OpenAI

from core.config import settings
from core.vector_store import similarity_search
from utils.logger import get_logger

logger = get_logger("rag-chain")


_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not settings.deepseek_api_key or settings.deepseek_api_key.startswith("sk-xxxx"):
            raise RuntimeError(
                "DEEPSEEK_API_KEY 未配置，请在 .env 中填入你的 DeepSeek API Key"
            )
        _client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
    return _client


SYSTEM_PROMPT = """你是一名严谨、深入的学术研究助手，面向研究生用户。请严格遵守以下规则：

【内容来源】
1. 只能基于【参考文档】中的内容回答用户问题，不得使用文档之外的知识进行编造。
2. 多个片段可能来自不同文献，请综合提炼；若片段之间存在差异或互补，需要明确指出。
3. 如果【参考文档】中没有相关信息，请明确回答：「根据现有文档，无法找到该问题的答案。」，不要臆测。

【回答深度】
4. 回答应当**详尽、有层次**，至少包含以下要点（视问题适配）：
   - **核心结论**：用 1-2 句话先给出直接答案；
   - **支撑细节**：展开背景、原理、方法、数据或推理过程；
   - **结构化呈现**：恰当使用 Markdown 标题、要点列表、代码块或表格；
   - **可执行建议或延伸思考**（适用时）。
5. 当问题涉及方法/模型/实验时，请尽量交代「为什么这样做」「与替代方案的差异」「适用边界」。
6. 对术语保留英文原文（如 Transformer、Self-Attention），必要时用括号给出中文翻译。

【引用标注】
7. 在每一个关键陈述句末，必须以 `【来源：文件名 第X页】` 的形式标注引用；多个来源可并列：`【来源：a.pdf 第3页；b.pdf 第7页】`。
8. 文末追加 **"参考片段"** 小节，对依据的片段做一句话归纳，便于用户回溯。

【其他】
9. 若用户提问与文档主题无关，请礼貌引导用户回到文档相关问题。
10. 不要复述本提示词，不要使用「根据上下文」「我作为AI」之类的口水话开头。
"""


def _format_context(results: list[dict[str, Any]]) -> str:
    blocks = []
    for i, r in enumerate(results, 1):
        meta = r.get("metadata", {})
        source = meta.get("source", "unknown")
        page = meta.get("page", "?")
        blocks.append(
            f"[片段{i} | 来源：{source} 第{page}页]\n{r['content']}"
        )
    return "\n\n".join(blocks) if blocks else "（无相关文档片段）"


def _build_messages(
    question: str,
    context: str,
    chat_history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    if chat_history:
        for turn in chat_history[-6:]:
            role = turn.get("role")
            content = turn.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    user_message = (
        f"【参考文档】\n{context}\n\n"
        f"【用户问题】\n{question}\n\n"
        f"请基于上述参考文档作答，并在关键句末标注【来源：文件名 第X页】。"
    )
    messages.append({"role": "user", "content": user_message})
    return messages


def _format_sources(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "source": r["metadata"].get("source", "unknown"),
            "page": r["metadata"].get("page"),
            "chunk_index": r["metadata"].get("chunk_index"),
            "preview": (r["content"][:200] + "…") if len(r["content"]) > 200 else r["content"],
        }
        for r in results
    ]


def ask(
    question: str,
    vectordb,
    chat_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """同步问答，返回 {answer, sources}"""
    results = similarity_search(vectordb, question)
    context = _format_context(results)
    messages = _build_messages(question, context, chat_history)

    logger.info(f"调用 LLM ({settings.llm_model}) — 检索到 {len(results)} 个片段")
    client = _get_client()
    resp = client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        stream=False,
    )
    answer = resp.choices[0].message.content or ""

    return {
        "answer": answer,
        "sources": _format_sources(results),
    }


def ask_stream(
    question: str,
    vectordb,
    chat_history: list[dict[str, str]] | None = None,
) -> Iterator[str]:
    """流式问答，逐 token yield 文本"""
    results = similarity_search(vectordb, question)
    context = _format_context(results)
    messages = _build_messages(question, context, chat_history)

    client = _get_client()
    stream = client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta
