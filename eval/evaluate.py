"""Day19 评测：纯向量 vs 混合检索 vs 混合+重排（Recall@k）+ 回答质量

指标说明（自动近似）：
- Recall@k：正确答案所在块是否出现在检索结果前 k 名
- 混合+重排：生产管道——混合检索召回 top-8，LLM 重排后取 top-1
- faithfulness：回答是否包含 golden 关键词（基于资料的忠实度代理）
- answer relevancy：回答是否有效（没有误拒答）
"""
import json
import sys
from datetime import datetime
from pathlib import Path

from rag.ask import ask
from rag.chunker import chunk_markdown
from rag.hybrid import HybridSearch
from rag.reranker import rerank
from rag.vector_store import VectorStore

ROOT = Path(__file__).resolve().parent.parent
DOC_DIR = ROOT / "rag" / "policy_docs"
DOC_FILES = ["差旅管理制度.md", "差旅报销补充说明.md"]
GOLDEN = json.loads((ROOT / "eval" / "golden_set.json").read_text(encoding="utf-8"))
ANSWER_SAMPLE = GOLDEN[:10]  # 回答质量评测抽前 10 题，控制成本


def build_chunks():
    return [c for name in DOC_FILES for c in chunk_markdown(DOC_DIR / name)]


def is_correct(chunk, source):
    return f"{chunk['source']}·{chunk['title']}" == source


def recall_at(search_fn, top_k):
    """Recall@k：正确答案块出现在 top-k 的比例"""
    hit = 0
    for item in GOLDEN:
        if any(is_correct(c, item["source"]) for c, _ in search_fn(item["question"], top_k=top_k)):
            hit += 1
    return hit / len(GOLDEN)


def reranked_recall():
    """混合检索召回 top-8 -> LLM 重排 -> top-1 是否命中"""
    hybrid = HybridSearch(build_chunks())
    hit = 0
    for item in GOLDEN:
        candidates = hybrid.search(item["question"], top_k=8)
        ranked = rerank(item["question"], candidates)
        if ranked and is_correct(ranked[0][0], item["source"]):
            hit += 1
    return hit / len(GOLDEN)


def answer_eval(items):
    """回答质量：faithfulness（含关键词） + relevancy（没拒答）"""
    faithful = relevant = 0
    for item in items:
        reply = ask(item["question"])
        if item["keyword"] in reply:
            faithful += 1
        if "未查到" not in reply:
            relevant += 1
        print(f"  [{'✓' if item['keyword'] in reply else '✗'}] {item['question']} -> {reply[:60]}...")
    return faithful / len(items), relevant / len(items)


def main():
    chunks = build_chunks()
    vector = VectorStore()
    vector.build_index(chunks)
    hybrid = HybridSearch(chunks)

    print("=== 检索对比（41 题）===")
    v1, v3 = recall_at(vector.search, 1), recall_at(vector.search, 3)
    h1, h3 = recall_at(hybrid.search, 1), recall_at(hybrid.search, 3)
    hr1 = reranked_recall()
    print(f"纯向量: Recall@1={v1:.1%}  Recall@3={v3:.1%}")
    print(f"混合:   Recall@1={h1:.1%}  Recall@3={h3:.1%}")
    print(f"混合+重排: Recall@1={hr1:.1%}（生产管道，41 次 LLM 重排）")

    print("\n=== 回答质量（10 题抽样，混合+重排）===")
    faith, relev = answer_eval(ANSWER_SAMPLE)
    print(f"faithfulness（含关键词率）={faith:.0%}")
    print(f"answer relevancy（有效回答率）={relev:.0%}")

    report = f"""# 评测报告（Day19）

- 日期：{datetime.now():%Y-%m-%d}
- 语料：{len(DOC_FILES)} 篇（差旅管理制度 + 差旅报销补充说明），{len(chunks)} 块
- golden set：{len(GOLDEN)} 条（问题/答案/出处/关键词）
- 回答质量抽样：前 {len(ANSWER_SAMPLE)} 题

## 检索 Recall@k（正确答案块出现在 top-k 的比例）

| 系统 | Recall@1 | Recall@3 |
|---|---|---|
| 纯向量 | {v1:.1%} | {v3:.1%} |
| 混合检索（BM25+向量+RRF） | {h1:.1%} | {h3:.1%} |
| 混合+LLM 重排（生产管道） | {hr1:.1%} | - |

## 回答质量（混合+重排，自动代理指标）

| 指标 | 定义 | 数值 |
|---|---|---|
| faithfulness | 回答包含 golden 关键词 | {faith:.0%} |
| answer relevancy | 回答未误拒答 | {relev:.0%} |

## 结论

生产管道（混合检索 + LLM 重排）Recall@1 从纯向量的 {v1:.1%} 提升到 {hr1:.1%}——
重排用语义把检索排错的题纠正回来。纯检索层面混合与向量持平（{v1:.1%} vs {h1:.1%}），
因为玩具向量本质是关键词匹配；换真向量模型后，混合检索在关键词/语义互补上的优势会更明显。
"""
    out = ROOT / "docs" / "eval.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"\n[已保存] {out}")


if __name__ == "__main__":
    sys.exit(main())