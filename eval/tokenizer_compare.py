"""分词对比实验：手写字符 bigram（现状） vs 单字 unigram vs WordPiece（bge 的分词器，真实子词切分）。
指标：语料词表大小、查询 token 覆盖率（有多少 query token 能在语料词表里找到）、平均 token 数，并给出切分示例。
用法：python tokenizer_compare.py --repo <AI-GIO> --onnx-dir <bge ONNX 目录> [--out <json>]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--onnx-dir", required=True)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    sys.path.insert(0, str(repo))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from onnx_embedder import find_files
    from rag.chunker import chunk_markdown
    from rag.embedding import tokenize as bigram_tokenize
    from tokenizers import Tokenizer

    doc_dir = repo / "rag" / "policy_docs"
    chunks = [c for name in ["差旅管理制度.md", "差旅报销补充说明.md"]
              for c in chunk_markdown(doc_dir / name)]
    golden = json.loads((repo / "eval" / "golden_set.json").read_text(encoding="utf-8"))
    corpus_texts = [c["title"] + "\n" + c["content"] for c in chunks]
    queries = [g["question"] for g in golden]

    tok_path = find_files(args.onnx_dir)["tokenizer"]
    if not tok_path:
        raise SystemExit(f"缺 tokenizer.json：{args.onnx_dir}")
    wp = Tokenizer.from_file(str(tok_path))

    def unigram(text: str) -> list[str]:
        return [ch for ch in text.strip() if not ch.isspace()]

    tokenizers = {
        "字符 bigram（现状）": bigram_tokenize,
        "单字 unigram": unigram,
        "WordPiece（bge 分词器）": lambda t: wp.encode(t).tokens,
    }

    corpus_tokens = {name: [set(fn(t)) for t in corpus_texts] for name, fn in tokenizers.items()}
    vocab = {name: set().union(*sets) if sets else set() for name, sets in corpus_tokens.items()}

    print(f"语料：{len(chunks)} 块；查询：{len(queries)} 条\n")
    print(f"{'分词方式':<24}{'语料词表大小':>12}{'查询覆盖率':>12}{'查询平均 token':>15}{'块平均 token':>14}")
    rows = []
    for name, fn in tokenizers.items():
        q_tokens = [fn(q) for q in queries]
        total = sum(len(ts) for ts in q_tokens)
        hit = sum(1 for ts in q_tokens for t in ts if t in vocab[name])
        cover = hit / total if total else 0
        avg_q = total / len(q_tokens)
        avg_c = sum(len(fn(t)) for t in corpus_texts) / len(corpus_texts)
        rows.append({"tokenizer": name, "vocab": len(vocab[name]), "query_coverage": round(cover, 4),
                     "avg_query_tokens": round(avg_q, 1), "avg_chunk_tokens": round(avg_c, 1)})
        print(f"{name:<24}{len(vocab[name]):>12}{cover:>11.1%}{avg_q:>15.1f}{avg_c:>14.1f}")

    print("\n切分示例：")
    examples = ["出差前需要做什么？", "发票开具后多久要提交报销？", "紧急出差怎么办？"]
    for q in examples:
        print(f"\n  「{q}」")
        for name, fn in tokenizers.items():
            toks = fn(q)
            print(f"     {name:<22} {len(toks):>3} 个：{toks[:14]}")

    out = Path(args.out) if args.out else Path(__file__).resolve().parent / "tokenizer_compare.json"
    out.write_text(json.dumps({"chunks": len(chunks), "queries": len(queries), "rows": rows},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已写入 {out}")


if __name__ == "__main__":
    main()
