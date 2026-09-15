"""LLM 重排器：对召回片段打分重排 + 相关度门控"""
import json

from llm.client import chat

RERANK_PROMPT = """你是一个检索重排器。用户给出一个问题，以及若干候选片段。
请为每个片段与问题的相关度打分（0-10 分，10 表示完全相关且能直接回答问题）。
只输出 JSON 数组，按候选顺序排列，例如 [8, 3, 5]。不要输出任何解释。"""


def _parse_scores(reply: str, n: int) -> list:
    """从回复里截取第一个 JSON 数组；失败时全部给 5 分（保持原顺序）"""
    start = reply.find("[")
    if start == -1:
        return [5.0] * n
    depth = 0
    for i in range(start, len(reply)):
        if reply[i] == "[":
            depth += 1
        elif reply[i] == "]":
            depth -= 1
            if depth == 0:
                try:
                    arr = json.loads(reply[start : i + 1])
                    scores = [float(x) for x in arr]
                    return scores[:n] + [0.0] * max(0, n - len(scores))
                except Exception:
                    return [5.0] * n
    return [5.0] * n


def rerank(question: str, candidates: list) -> list:
    """对候选片段打分并重排，返回 [(chunk, score), ...] 从高到低"""
    if not candidates:
        return []
    lines = [f"问题：{question}", "", "候选片段："]
    for i, (chunk, _) in enumerate(candidates, 1):
        # 用完整片段：截断会丢关键信息（如「其他城市 300 元」在片段后半段）
        snippet = chunk["content"].replace("\n", " ")
        lines.append(f"{i}. 【{chunk['source']}·{chunk['title']}】{snippet}")
    reply = chat(system=RERANK_PROMPT, user="\n".join(lines), stream=False)

    scores = _parse_scores(reply, len(candidates))
    scored = [(chunk, s) for (chunk, _), s in zip(candidates, scores)]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored