"""制度问答（Day17 生产级三件套：重排 + 引用 + 拒答）"""
import sys
from pathlib import Path

from llm.client import chat
from rag.chunker import chunk_markdown
from rag.hybrid import HybridSearch
from rag.reranker import rerank

DOC_DIR = Path(__file__).resolve().parent / "policy_docs"
DOC_FILES = ["差旅管理制度.md", "差旅报销补充说明.md"]

STORE = HybridSearch(
    [c for name in DOC_FILES for c in chunk_markdown(DOC_DIR / name)]
)

RERANK_THRESHOLD = 5.0  # 重排分数低于它就拒答

SYSTEM_PROMPT = """你是企业差旅制度助手。只根据提供的制度内容回答，回答结尾必须标注来源，
格式：[来源：文档名·章节名]。制度内容里没有的信息，明确回答「制度中未查到，请联系行政部」，不要编造。"""


def ask(question: str, top_k: int = 2) -> str:
    """检索 -> 重排 -> 相关度门控（拒答）-> 拼提示词回答（带引用）"""
    candidates = STORE.search(question, top_k=8)
    ranked = rerank(question, candidates)

    if not ranked or ranked[0][1] < RERANK_THRESHOLD:
        return "制度中未查到相关信息，请联系行政部。"

    top = ranked[:top_k]
    context = "\n\n".join(
        f"【{chunk['source']}·{chunk['title']}】\n{chunk['content']}" for chunk, _ in top
    )
    user = f"制度内容：\n{context}\n\n问题：{question}"
    return chat(system=SYSTEM_PROMPT, user=user, stream=False)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python -m rag.ask '你的问题'")
        sys.exit(1)
    print(ask(sys.argv[1]))