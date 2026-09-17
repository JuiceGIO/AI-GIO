"""向量化后端对比：手写 bigram（现状） vs 预训练 Embedding（bge-small-zh-v1.5 等）。
指标：Recall@1 / Recall@3 / NDCG@10 / MRR@10 / P95 查询延迟 / 维度 / 索引大小。
同时给出「纯向量」与「向量 + BM25 + RRF」两种口径。
用法：
  python embedding_compare.py --repo "G:\\python project\\AI-GIO" [--models BAAI/bge-small-zh-v1.5] [--with-base] [--out <json>]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："


def rrf_fuse(ranked_lists, k: int, top_k: int):
    scores, first_seen, payload = {}, {}, {}
    for lst in ranked_lists:
        for rank, (chunk, _s) in enumerate(lst, start=1):
            key = f"{chunk['source']}·{chunk['title']}"
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            first_seen.setdefault(key, len(first_seen))
            payload[key] = chunk
    order = sorted(scores, key=lambda kk: (-scores[kk], first_seen[kk]))
    return [(payload[kk], scores[kk]) for kk in order[:top_k]]


def metrics(search_fn, golden, key_of, k_eval=3, k_ndcg=10):
    hit1 = hit3 = 0
    rr = nd = 0.0
    lat = []
    for item in golden:
        t0 = time.perf_counter()
        ranked = search_fn(item["question"])
        lat.append((time.perf_counter() - t0) * 1000.0)
        keys = [key_of(c) for c, _ in ranked[:k_ndcg]]
        target = item["source"]
        if keys and keys[0] == target:
            hit1 += 1
        if target in keys[:k_eval]:
            hit3 += 1
        if target in keys:
            r = keys.index(target) + 1
            rr += 1.0 / r
            nd += 1.0 / math.log2(r + 1)
    n = len(golden)
    return {
        "recall1": hit1 / n, "recall3": hit3 / n, "mrr": rr / n, "ndcg10": nd / n,
        "p95_ms": float(np.percentile(lat, 95)), "avg_ms": float(np.mean(lat)),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--models", default="BAAI/bge-small-zh-v1.5")
    ap.add_argument("--with-base", action="store_true", help="额外测 bge-base-zh-v1.5")
    ap.add_argument("--onnx-dir", default="", help="bge ONNX 模型目录（用 onnxruntime + tokenizers 推理，无需 torch）")
    ap.add_argument("--pool", type=int, default=5)
    ap.add_argument("--rrf-k", type=int, default=60)
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
    key_of = lambda c: f"{c['source']}·{c['title']}"
    corpus_texts = [c["title"] + "\n" + c["content"] for c in chunks]

    bm25 = BM25()
    bm25.build_index(chunks)

    results = {
        "corpus": {"docs": len(doc_files), "chunks": len(chunks), "golden": len(golden)},
        "pool": args.pool, "rrf_k": args.rrf_k, "query_instruction": QUERY_INSTRUCTION,
        "backends": [],
    }

    def add_backend(name, dim, index_bytes, vector_search, note=""):
        pure = metrics(lambda q: vector_search(q, 10), golden, key_of)

        def hybrid(q):
            vec = vector_search(q, args.pool)
            bm = bm25.search(q, top_k=args.pool)
            return rrf_fuse([vec, bm], k=args.rrf_k, top_k=10)

        hyb = metrics(hybrid, golden, key_of)
        entry = {"name": name, "dim": dim, "index_bytes": index_bytes, "note": note,
                 "vector_only": pure, "hybrid_rrf": hyb}
        results["backends"].append(entry)
        print(f"\n[{name}] 维度={dim} 索引={index_bytes / 1024:.1f}KB")
        print(f"   纯向量 : Recall@1={pure['recall1']:.1%} Recall@3={pure['recall3']:.1%} "
              f"MRR={pure['mrr']:.3f} NDCG@10={pure['ndcg10']:.3f} P95={pure['p95_ms']:.1f}ms")
        print(f"   +RRF   : Recall@1={hyb['recall1']:.1%} Recall@3={hyb['recall3']:.1%} "
              f"MRR={hyb['mrr']:.3f} NDCG@10={hyb['ndcg10']:.3f} P95={hyb['p95_ms']:.1f}ms")
        return entry

    # 1) 现状：手写 bigram
    store = VectorStore()
    store.build_index(chunks)
    bigram_bytes = int(store.matrix.nbytes) + sum(len(k) for k in store.vocab) * 2
    add_backend("bigram + TF（现状）", store.matrix.shape[1], bigram_bytes,
                lambda q, k: store.search(q, top_k=k), note="手写、无外部依赖、维度随语料变化")

    # 2) 预训练 Embedding（ONNX 路线，无需 torch）
    if args.onnx_dir:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from onnx_embedder import OnnxEmbedder, find_files

        files = find_files(args.onnx_dir)
        if not files["tokenizer"]:
            print(f"\n[ONNX] 缺少 tokenizer.json（{args.onnx_dir}）")
            _dump(args, results)
            return
        for tag in ("fp32", "quantized"):
            model_path = files[tag]
            if model_path is None:
                continue
            embedder = OnnxEmbedder(model_path, files["tokenizer"])
            t0 = time.perf_counter()
            doc_vecs = embedder.encode(corpus_texts)
            build_s = time.perf_counter() - t0
            dim = int(doc_vecs.shape[1])

            def search_factory(vecs, add_instruction: bool, emb=embedder):
                def _search(q, k):
                    qv = emb.encode([q], add_instruction=add_instruction)[0]
                    scores = vecs @ qv
                    order = np.argsort(-scores)[:k]
                    return [(chunks[i], float(scores[i])) for i in order]
                return _search

            base_note = f"bge-small-zh-v1.5 ONNX({tag})｜构建 {build_s:.1f}s"
            add_backend(f"bge-small-zh ONNX-{tag}（query 加指令）", dim, int(doc_vecs.nbytes),
                        search_factory(doc_vecs, True), note=base_note + "｜query 加官方指令")
            add_backend(f"bge-small-zh ONNX-{tag}（query 不加指令）", dim, int(doc_vecs.nbytes),
                        search_factory(doc_vecs, False), note=base_note + "｜对照：不加指令")
        _dump(args, results)
        return

    # 2b) 预训练 Embedding（sentence-transformers 路线，需要 torch）
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as exc:  # pragma: no cover
        print(f"\n[sentence-transformers 不可用] {exc}")
        _dump(args, results)
        return

    models = [args.models] + (["BAAI/bge-base-zh-v1.5"] if args.with_base else [])
    for model_name in models:
        t0 = time.perf_counter()
        model = SentenceTransformer(model_name)
        doc_vecs = model.encode(corpus_texts, normalize_embeddings=True, show_progress_bar=False)
        build_s = time.perf_counter() - t0
        dim = int(doc_vecs.shape[1])

        def search_factory(vecs, tag_instruction: bool):
            def _search(q, k):
                query = (QUERY_INSTRUCTION + q) if tag_instruction else q
                qv = model.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]
                scores = vecs @ qv
                order = np.argsort(-scores)[:k]
                return [(chunks[i], float(scores[i])) for i in order]
            return _search

        # 两种查询前缀口径都测：bge 官方建议检索时给 query 加指令
        note = f"{model_name}｜构建 {build_s:.1f}s｜query 前缀：{'有' if True else '无'}"
        add_backend(f"{model_name}（query 加指令）", dim, int(doc_vecs.nbytes),
                    search_factory(doc_vecs, True), note=note)
        add_backend(f"{model_name}（query 不加指令）", dim, int(doc_vecs.nbytes),
                    search_factory(doc_vecs, False), note="对照：验证前缀是否真的有用")

    _dump(args, results)


def _dump(args, results) -> None:
    out = Path(args.out) if args.out else Path(__file__).resolve().parent / "embedding_compare.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已写入 {out}")


if __name__ == "__main__":
    main()
