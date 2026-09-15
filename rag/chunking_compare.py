"""切块策略对比（章节 vs 固定长度）

5 个问题分别用两套切块检索，记录命中差异，选出更适合制度文档的策略。
"""
import sys
from pathlib import Path

from rag.chunker import chunk_fixed, chunk_markdown
from rag.vector_store import VectorStore

POLICY_FILE = Path(__file__).resolve().parent / "policy_docs" / "差旅管理制度.md"

# (问题, 正确答案里应出现的关键词)
QUESTIONS = [
    ("北京住宿标准是多少？", "一线城市"),
    ("高铁能坐一等座吗？", "一等座"),
    ("报销时限是多久？", "30 天"),
    ("餐补一天多少钱？", "100 元"),
    ("虚假发票怎么处理？", "虚假发票"),
]


def run_strategy(name: str, chunks: list):
    """建索引 + 检索 5 题，返回 [(问题, 是否命中, 命中最相关块标题)]"""
    store = VectorStore()
    store.build_index(chunks)
    print(f"\n=== {name}（共 {len(chunks)} 块）===")
    rows = []
    for question, keyword in QUESTIONS:
        hits = store.search(question, top_k=3)
        hit = any(keyword in c["content"] for c, _ in hits)
        top = hits[0][0]["title"] if hits else "-"
        rows.append((question, hit, top))
        print(f"  {'✅' if hit else '❌'} {question} -> 最相关: {top}")
    return rows


def save_report(chapter_rows, fixed_rows, chapter_hits, fixed_hits):
    """把对比结果存成报告，方便复盘"""
    out = Path(__file__).resolve().parent.parent / "eval" / "chunking_report.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 切块策略对比报告",
        "",
        "| 问题 | 章节切块命中 | 固定长度命中 |",
        "|---|---|---|",
    ]
    for (q1, h1, _), (q2, h2, _) in zip(chapter_rows, fixed_rows):
        lines.append(f"| {q1} | {'是' if h1 else '否'} | {'是' if h2 else '否'} |")
    lines += [
        "",
        f"**命中率：章节切块 {chapter_hits}/5，固定长度 {fixed_hits}/5**",
        "",
        "## 结论",
        "",
        "制度文档结构清晰（有章节标题），按章节切块更优：",
        "- 每个块主题完整，检索命中即答案；",
        "- 标题参与向量化，是强检索特征；",
        "- 固定长度切块会切断句子、混入无关内容，且没有标题可依赖。",
        "",
        "固定长度切块（带重叠）作为通用兜底：",
        "- 适合没有结构的长文（新闻、聊天记录、说明文档）；",
        "- 重叠（overlap）减少语义被切断的概率。",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[已保存报告] {out}")


def main():
    text = POLICY_FILE.read_text(encoding="utf-8")

    chapter_rows = run_strategy("按章节切块", chunk_markdown(POLICY_FILE))
    fixed_rows = run_strategy("固定长度切块（200字/重叠50）", chunk_fixed(text))

    chapter_hits = sum(1 for _, hit, _ in chapter_rows if hit)
    fixed_hits = sum(1 for _, hit, _ in fixed_rows if hit)

    print(f"\n命中率：章节切块 {chapter_hits}/5，固定长度 {fixed_hits}/5")
    winner = "章节切块" if chapter_hits >= fixed_hits else "固定长度切块"
    print(f"结论：本制度文档选择「{winner}」")

    save_report(chapter_rows, fixed_rows, chapter_hits, fixed_hits)


if __name__ == "__main__":
    sys.exit(main())