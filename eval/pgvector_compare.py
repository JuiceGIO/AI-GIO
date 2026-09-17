"""三方检索对比：numpy 暴力检索 vs pgvector（HNSW）vs pgvector（顺序扫描）。
用法（需要先起 pgvector 容器，见 README）：
  python eval/pgvector_compare.py --repo . --dsn "postgresql://postgres:postgres@127.0.0.1:5433/postgres" \
      --onnx-dir <bge-small-zh ONNX 目录>
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np


def metrics(scores_fn, golden, chunks, k_ndcg=10):
    hit1 = hit3 = 0
    rr = nd = 0.0
    lat = []
    for item in golden:
        t0 = time.perf_counter()
        order = scores_fn(item["question"])
        lat.append((time.perf_counter() - t0) * 1000.0)
        keys = [f"{chunks[i]['source']}·{chunks[i]['title']}" for i in order[:k_ndcg]]
        target = item["source"]
        if keys and keys[0] == target:
            hit1 += 1
        if target in keys[:3]:
            hit3 += 1
        if target in keys:
            r = keys.index(target) + 1
            rr += 1.0 / r
            nd += 1.0 / math.log2(r + 1)
    n = len(golden)
    return {"recall1": hit1 / n, "recall3": hit3 / n, "mrr": rr / n, "ndcg10": nd / n,
            "p95_ms": float(np.percentile(lat, 95))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--dsn", required=True)
    ap.add_argument("--onnx-dir", required=True)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    sys.path.insert(0, str(repo))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from onnx_embedder import OnnxEmbedder, find_files
    from rag.chunker import chunk_markdown

    import psycopg2

    files = find_files(args.onnx_dir)
    if not files["fp32"] or not files["tokenizer"]:
        raise SystemExit(f"ONNX 模型不完整：{args.onnx_dir}")
    embedder = OnnxEmbedder(files["fp32"], files["tokenizer"])

    doc_dir = repo / "rag" / "policy_docs"
    doc_files = ["差旅管理制度.md", "差旅报销补充说明.md"]
    chunks = [c for name in doc_files for c in chunk_markdown(doc_dir / name)]
    golden = json.loads((repo / "eval" / "golden_set.json").read_text(encoding="utf-8"))
    texts = [c["title"] + "\n" + c["content"] for c in chunks]
    t0 = time.perf_counter()
    doc_vecs = embedder.encode(texts)
    build_s = time.perf_counter() - t0
    dim = doc_vecs.shape[1]
    print(f"语料 {len(chunks)} 块，golden {len(golden)} 条，维度 {dim}，本地编码耗时 {build_s:.2f}s")

    results = {"chunks": len(chunks), "golden": len(golden), "dim": dim, "backends": {}}

    # 1) numpy 暴力检索
    def numpy_search(q):
        qv = embedder.encode([q], add_instruction=True)[0]
        return list(np.argsort(-(doc_vecs @ qv)))

    results["backends"]["numpy_bruteforce"] = metrics(numpy_search, golden, chunks)
    print("numpy 暴力检索:", results["backends"]["numpy_bruteforce"])

    # 2) pgvector
    conn = psycopg2.connect(args.dsn)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
    cur.execute("DROP TABLE IF EXISTS chunks")
    cur.execute(f"CREATE TABLE chunks (id int primary key, source text, title text, content text, "
                f"embedding vector({dim}))")
    for i, (c, v) in enumerate(zip(chunks, doc_vecs)):
        cur.execute("INSERT INTO chunks (id, source, title, content, embedding) VALUES (%s,%s,%s,%s,%s)",
                    (i, c["source"], c["title"], c["content"], v.tolist()))

    def pg_search_factory(index_mode: str):
        if index_mode == "hnsw":
            cur.execute("CREATE INDEX IF NOT EXISTS chunks_hnsw ON chunks USING hnsw (embedding vector_cosine_ops)")
        else:
            cur.execute("DROP INDEX IF EXISTS chunks_hnsw")

        def _search(q):
            qv = embedder.encode([q], add_instruction=True)[0].tolist()
            cur.execute("SELECT id FROM chunks ORDER BY embedding <=> %s::vector LIMIT 10", (qv,))
            return [row[0] for row in cur.fetchall()]
        return _search

    for mode in ("seqscan", "hnsw"):
        t0 = time.perf_counter()
        idx_s = 0.0
        res = metrics(pg_search_factory(mode), golden, chunks)
        idx_s = time.perf_counter() - t0
        res["index_build_s"] = round(idx_s, 3)
        results["backends"][f"pgvector_{mode}"] = res
        print(f"pgvector {mode}:", res)

    cur.execute("SELECT pg_size_pretty(pg_total_relation_size('chunks'))")
    size = cur.fetchone()[0]
    results["pg_index_size"] = size
    print("pgvector 表大小:", size)
    conn.close()

    out = Path(args.out) if args.out else Path(__file__).resolve().parent / "pgvector_compare.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("结果已写入", out)


if __name__ == "__main__":
    main()
