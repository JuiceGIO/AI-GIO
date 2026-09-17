"""采样多样性实验：creative 任务下 temperature 对输出多样性的影响（同 prompt 采样 N 次，统计去重后的唯一回答数）。
补充说明：结构化抽取任务上温度几乎无影响（见 sampling_experiment.py 的实测），
          参数真正起作用的是需要多样性的生成场景——本脚本用同一套 .env 配置实测。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

PROMPT = "给「企业差旅报销审批流程」起一个简短标题（不超过 12 个字），只输出标题本身，不要标点和解释。"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--samples", type=int, default=10)
    ap.add_argument("--temps", default="0.0,0.7,1.2")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    sys.path.insert(0, str(repo))
    from dotenv import load_dotenv
    from openai import OpenAI

    load_dotenv(repo / ".env")
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"),
                    base_url=os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com"),
                    timeout=60, max_retries=2)
    model = os.getenv("OPENAI_MODEL", "deepseek-chat")

    results = []
    print(f"模型：{model}｜每个温度采样 {args.samples} 次\n")
    print(f"{'temperature':>12}{'唯一输出数':>11}{'重复率':>9}{'平均延迟(ms)':>14}")
    for temp in [float(x) for x in args.temps.split(",")]:
        outs, lat = [], []
        for _ in range(args.samples):
            t0 = time.perf_counter()
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": PROMPT}],
                temperature=temp, max_tokens=32,
            )
            lat.append((time.perf_counter() - t0) * 1000)
            outs.append((resp.choices[0].message.content or "").strip())
        uniq = len(set(outs))
        dup_rate = 1 - uniq / max(len(outs), 1)
        results.append({"temperature": temp, "samples": len(outs), "unique": uniq,
                        "dup_rate": round(dup_rate, 3), "avg_ms": round(sum(lat) / len(lat)),
                        "examples": list(dict.fromkeys(outs))[:6]})
        print(f"{temp:>12}{uniq:>8}/{len(outs)}{dup_rate:>9.0%}{sum(lat)/len(lat):>14.0f}")
        print(f"             示例：{list(dict.fromkeys(outs))[:5]}")

    out = Path(args.out) if args.out else Path(__file__).resolve().parent / "sampling_diversity.json"
    out.write_text(json.dumps({"model": model, "prompt": PROMPT, "results": results},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已写入 {out}")


if __name__ == "__main__":
    main()
