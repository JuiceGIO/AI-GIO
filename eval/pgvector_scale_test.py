"""规模测试：语料从 17 块扩到 3000 块，对比 numpy 暴力 / pgvector 顺序扫描 / pgvector HNSW 的延迟。
说明：扩样是"真实块 + 编号变体"的合成语料，只用于测**延迟与索引构建**趋势，
      召回质量在合成语料上没有意义（因此这里只报时延，不报 Recall）。
用法：python pgvector_scale_test.py --repo <AI-GIO> --dsn <pgvector dsn> --onnx-dir <bge ONNX> --sizes 17,200,1000,3000
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np


def encode_batched(embedder, texts, batch=64):
    out = []
    for i in range(0, len(texts), batch):
        out.append(embedder.encode(texts[i:i + batch]))
    return np.vstack(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--dsn", required=True)
    ap.add_argument("--onnx-dir", required=True)
    ap.add_argument("--sizes", default="17,200,1000,3000")
    ap.add_argument("--topk", type=int, default=10)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    sys.path.insert(0, str(repo))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from onnx_embedder import OnnxEmbedder, find_files
    from rag.chunker import chunk_markdown

    import psycopg2

    files = find_files(args.onnx_dir)
    embedder = OnnxEmbedder(files["fp32"], files["tokenizer"])

    doc_dir = repo / "rag" / "policy_docs"
    base_chunks = [c for name in ["差旅管理制度.md", "差旅报销补充说明.md"]
                   for c in chunk_markdown(doc_dir / name)]
    golden = json.loads((repo / "eval" / "golden_set.json").read_text(encoding="utf-8"))
    queries = [g["question"] for g in golden]
    q_vecs = encode_batched(embedder, queries, batch=32)

    sizes = [int(x) for x in args.sizes.split(",")]
    results = []
    conn = psycopg2.connect(args.dsn)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")

    for n in sizes:
        texts = []
        while len(texts) < n:
            for c in base_chunks:
                texts.append(f"{c['title']}（{len(texts)}）\n{c['content']}")
                if len(texts) >= n:
                    break
        t0 = time.perf_counter()
        doc_vecs = encode_batched(embedder, texts, batch=64)
        encode_s = time.perf_counter() - t0
        dim = doc_vecs.shape[1]

        # numpy 暴力
        lat = []
        for qv in q_vecs:
            t = time.perf_counter()
            np.argsort(-(doc_vecs @ qv))[:args.topk]
            lat.append((time.perf_counter() - t) * 1000)
        numpy_ms = float(np.median(lat))

        # pgvector
        cur.execute("DROP TABLE IF EXISTS scale_chunks")
        cur.execute(f"CREATE TABLE scale_chunks (id int primary key, embedding vector({dim}))")
        t0 = time.perf_counter()
        rows = [(i, v.tolist()) for i, v in enumerate(doc_vecs)]
        cur.executemany("INSERT INTO scale_chunks (id, embedding) VALUES (%s, %s)", rows)
        insert_s = time.perf_counter() - t0

        row = {"size": n, "dim": dim, "encode_all_s": round(encode_s, 2),
               "numpy_bruteforce_median_ms": round(numpy_ms, 2)}

        for mode, ddl in (("seqscan", None),
                          ("hnsw", "CREATE INDEX ON scale_chunks USING hnsw (embedding vector_cosine_ops)")):
            if ddl:
                t0 = time.perf_counter()
                cur.execute(ddl)
                row["hnsw_build_s"] = round(time.perf_counter() - t0, 2)
            else:
                cur.execute("DROP INDEX IF EXISTS scale_chunks_embedding_idx")
            lat = []
            qlist = q_vecs[: min(41, len(q_vecs))]
            for qv in qlist:
                t = time.perf_counter()
                cur.execute("SELECT id FROM scale_chunks ORDER BY embedding <=> %s::vector LIMIT %s",
                            (qv.tolist(), args.topk))
                cur.fetchall()
                lat.append((time.perf_counter() - t) * 1000)
            row[f"pgvector_{mode}_median_ms"] = round(float(np.median(lat)), 2)
            row[f"pgvector_{mode}_p95_ms"] = round(float(np.percentile(lat, 95)), 2)

        cur.execute("SELECT pg_size_pretty(pg_total_relation_size('scale_chunks'))")
        row["pg_table_size"] = cur.fetchone()[0]
        row["insert_s"] = round(insert_s, 2)
        results.append(row)
        print(json.dumps(row, ensure_ascii=False))

    conn.close()
    out = Path(args.out) if args.out else Path(__file__).resolve().parent / "pgvector_scale.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("结果已写入", out)


if __name__ == "__main__":
    main()
