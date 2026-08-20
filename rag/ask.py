"""制度问答 v1（Day11 基础 RAG）：检索 top-k -> 拼进提示词 -> LLM 回答"""
import sys
from pathlib import Path

from llm.client import chat
from rag.chunker import chunk_markdown
from rag.vector_store import VectorStore

POLICY_FILE = Path(__file__).resolve().parent / "policy_docs" / "差旅管理制度.md"

STORE = VectorStore()
STORE.build_index(chunk_markdown(POLICY_FILE))

SYSTEM_PROMPT = """你是企业差旅制度助手。只根据提供的制度内容回答，并标注来源章节。
制度内容里没有的信息，明确说「制度中未查到」，不要编造。"""


def ask(question: str, top_k: int = 2) -> str:
    """检索最相关的制度片段，拼进提示词，交给模型回答"""
    hits = STORE.search(question, top_k=top_k)
    context = "\n\n".join(f"【{chunk['title']}】\n{chunk['content']}" for chunk, _ in hits)
    user = f"制度内容：\n{context}\n\n问题：{question}"
    return chat(system=SYSTEM_PROMPT, user=user, stream=False)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python -m rag.ask '你的问题'")
        sys.exit(1)
    print(ask(sys.argv[1]))