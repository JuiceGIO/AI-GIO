"""RRF k 值扫描：在 golden set 上对比不同 k 的 Recall@1 / Recall@3 / MRR@10 / NDCG@10。
只用到手写向量 + BM25 + RRF（不需要 API Key、不联网）。
用法：python rrf_k_sweep.py --repo <仓库路径>
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


def rrf_fuse(ranked_lists, k: int, top_k: int):
    scores = {}
    first_seen = {}
    payload = {}
    for lst in ranked_lists:
        for rank, (chunk, _score) in enumerate(lst, start=1):
            key = f"{chunk['source']}·{chunk['title']}"
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            first_seen.setdefault(key, len(first_seen))
            payload[key] = chunk
    order = sorted(scores, key=lambda kk: (-scores[kk], first_seen[kk]))
    return [(payload[kk], scores[kk]) for kk in order[:top_k]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--pool", default="3,5,8,10")
    ap.add_argument("--ks", default="1,3,5,10,20,60,100,200,1000")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    sys.path.insert(0, str(repo))
    from rag.bm25 import BM25
    from rag.chunker import chunk_markdown
    from rag.vector_store import VectorStore

    doc_dir = repo / "rag" / "policy_docs"
    doc_files = ["差旅管理制度.md", "差旅报销补充说明.md"]
    chunks = [c for name in doc_files for c in chunk_markdown(doc_dir / name)]
    golden = json.loads((repo / "eval" / "golden_set.json").read_text(encoding="utf-8"))
    print(f"语料：{len(doc_files)} 篇文档 → {len(chunks)} 块；评测集：{len(golden)} 条")

    vector, bm25 = VectorStore(), BM25()
    vector.build_index(chunks)
    bm25.build_index(chunks)

    def key_of(chunk) -> str:
        return f"{chunk['source']}·{chunk['title']}"

    def metrics(search_fn, k_eval: int = 3, k_ndcg: int = 10):
        hit1 = hit3 = 0
        rr_sum = 0.0
        ndcg_sum = 0.0
        for item in golden:
            ranked = search_fn(item["question"])
            keys = [key_of(c) for c, _ in ranked[:k_ndcg]]
            target = item["source"]
            if keys and keys[0] == target:
                hit1 += 1
            if target in keys[:k_eval]:
                hit3 += 1
            if target in keys:
                rank = keys.index(target) + 1
                rr_sum += 1.0 / rank
                ndcg_sum += 1.0 / math.log2(rank + 1)
        n = len(golden)
        return hit1 / n, hit3 / n, rr_sum / n, ndcg_sum / n

    def make_search(k: int, pool: int):
        def _search(q):
            vec = vector.search(q, top_k=pool)
            bm = bm25.search(q, top_k=pool)
            return rrf_fuse([vec, bm], k=k, top_k=10)
        return _search

    b1, b3, brr, bndcg = metrics(lambda q: vector.search(q, top_k=10))
    m1, m3, mrr, mndcg = metrics(lambda q: bm25.search(q, top_k=10))
    print(f"\n基线（单路 top-10）：向量 Recall@1={b1:.1%} Recall@3={b3:.1%} MRR={brr:.3f} NDCG@10={bndcg:.3f}")
    print(f"                     BM25 Recall@1={m1:.1%} Recall@3={m3:.1%} MRR={mrr:.3f} NDCG@10={mndcg:.3f}")

    # 难度分层：正确块在两条单路里分别排第几
    both_first = only_one = neither = 0
    disagree_top1 = []
    for item in golden:
        q, target = item["question"], item["source"]
        vec_keys = [key_of(c) for c, _ in vector.search(q, top_k=10)]
        bm_keys = [key_of(c) for c, _ in bm25.search(q, top_k=10)]
        v1 = vec_keys[0] if vec_keys else None
        n1 = bm_keys[0] if bm_keys else None
        if v1 != n1:
            disagree_top1.append(item)
        in_vec = target in vec_keys
        in_bm = target in bm_keys
        if in_vec and in_bm:
            if vec_keys.index(target) == 0 and bm_keys.index(target) == 0:
                both_first += 1
            else:
                only_one += 1
        elif in_vec or in_bm:
            only_one += 1
        else:
            neither += 1
    print(f"\n难度分层（41 条）：两条单路都排第 1 = {both_first} 条；只有一条路进 top-10 或排名靠后 = {only_one} 条；两路都进不了 top-10 = {neither} 条")
    print(f"两路 top-1 不一致的问题 = {len(disagree_top1)} 条（k 值只可能在这类问题上改变结果）")

    def subset_metrics(search_fn, subset, k_eval=3, k_ndcg=10):
        if not subset:
            return 0.0, 0.0, 0.0, 0.0
        hit1 = hit3 = 0
        rr = nd = 0.0
        for item in subset:
            keys = [key_of(c) for c, _ in search_fn(item["question"])[:k_ndcg]]
            t = item["source"]
            if keys and keys[0] == t:
                hit1 += 1
            if t in keys[:k_eval]:
                hit3 += 1
            if t in keys:
                r = keys.index(t) + 1
                rr += 1.0 / r
                nd += 1.0 / math.log2(r + 1)
        n = len(subset)
        return hit1 / n, hit3 / n, rr / n, nd / n

    ks = [int(x) for x in args.ks.split(",")]
    pools = [int(x) for x in args.pool.split(",")]
    rows = []
    for pool in pools:
        print(f"\n=== 融合候选池 top-{pool}（每路各取 {pool} 条）===")
        print(f"{'k':>6} | {'Recall@1':>9} | {'Recall@3':>9} | {'MRR@10':>7} | {'NDCG@10':>8}")
        for k in ks:
            r1, r3, rrr, rndcg = metrics(make_search(k, pool))
            rows.append({"pool": pool, "k": k, "recall1": round(r1, 4), "recall3": round(r3, 4),
                         "mrr": round(rrr, 4), "ndcg10": round(rndcg, 4)})
            print(f"{k:>6} | {r1:>8.1%} | {r3:>8.1%} | {rrr:>7.3f} | {rndcg:>8.3f}")

    if disagree_top1:
        print(f"\n=== 只在「两路 top-1 不一致」的 {len(disagree_top1)} 条问题上扫 k（pool=8）===")
        print(f"{'k':>6} | {'Recall@1':>9} | {'Recall@3':>9} | {'MRR@10':>7} | {'NDCG@10':>8}")
        for k in ks:
            r1, r3, rrr, rndcg = subset_metrics(make_search(k, 8), disagree_top1)
            rows.append({"subset": "disagree_top1", "pool": 8, "k": k, "recall1": round(r1, 4),
                         "recall3": round(r3, 4), "mrr": round(rrr, 4), "ndcg10": round(rndcg, 4)})
            print(f"{k:>6} | {r1:>8.1%} | {r3:>8.1%} | {rrr:>7.3f} | {rndcg:>8.3f}")
        # 只看分歧子集里"正确答案在哪条路的第几"
        for item in disagree_top1[:3]:
            q, t = item["question"], item["source"]
            vk = [key_of(c) for c, _ in vector.search(q, top_k=5)]
            bk = [key_of(c) for c, _ in bm25.search(q, top_k=5)]
            print(f"    例：{q}｜目标={t}｜向量第 {vk.index(t) + 1 if t in vk else '>5'} 位｜BM25 第 {bk.index(t) + 1 if t in bk else '>5'} 位")

    out = Path(args.out) if args.out else Path(__file__).resolve().parent / "rrf_k_sweep.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"chunks": len(chunks), "golden": len(golden), "rows": rows},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已写入 {out}")


if __name__ == "__main__":
    main()
