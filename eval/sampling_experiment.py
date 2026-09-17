"""采样参数实验：同一抽取任务下，temperature / top_p 对输出稳定性与 JSON 可解析率的影响。
用项目自带的 llm/client.py 调真实模型（DeepSeek），跑 N 次/配置。
用法：python sampling_experiment.py --repo <AI-GIO> [--samples 5]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

SYSTEM = "你是发票信息抽取助手。只输出 JSON，不要解释。字段：amount(数字)、date(YYYY-MM-DD)、invoice_no(字符串)、title(字符串)。"
INVOICE = """电子发票（增值税普通发票）
发票代码：044001911211  发票号码：18820066
开票日期：2026-08-29
购买方名称：深圳市某某科技有限公司
价税合计（大写）：壹仟贰佰捌拾元整   （小写）￥1280.00
货物或应税劳务名称：住宿服务
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--samples", type=int, default=5)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    sys.path.insert(0, str(repo))
    # 注意：项目的 llm/client.py 封装没有暴露采样参数，这里直接用同一套 .env 配置调 OpenAI 兼容接口，
    # 目的是把 temperature / top_p 显式打开做对照（封装层默认参数无法比较）。
    from dotenv import load_dotenv
    from openai import OpenAI
    import os

    load_dotenv(repo / ".env")
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com"),
        timeout=60,
        max_retries=2,
    )
    MODEL = os.getenv("OPENAI_MODEL", "deepseek-chat")

    def call_llm(temperature: float, top_p: float) -> str:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": INVOICE}],
            temperature=temperature,
            top_p=top_p,
            max_tokens=200,
        )
        return resp.choices[0].message.content or ""

    configs = [(0.0, 1.0), (0.7, 1.0), (1.2, 1.0), (0.7, 0.5)]
    results = []
    print(f"模型：{MODEL}｜每种配置采样 {args.samples} 次\n")
    print(f"{'temperature':>12}{'top_p':>7}{'JSON 可解析':>12}{'字段全一致':>11}{'平均延迟(ms)':>14}")
    for temp, top_p in configs:
        parsed_ok = 0
        outputs = []
        lat = []
        for _ in range(args.samples):
            t0 = time.perf_counter()
            reply = call_llm(temp, top_p)
            lat.append((time.perf_counter() - t0) * 1000)
            block = re.search(r"\{.*\}", reply or "", re.S)
            try:
                obj = json.loads(block.group(0)) if block else None
            except Exception:
                obj = None
            if obj:
                parsed_ok += 1
                outputs.append({k: obj.get(k) for k in ("amount", "date", "invoice_no", "title")})
        consistent = 0
        if outputs:
            first = outputs[0]
            consistent = 1 if all(o == first for o in outputs) else 0
        row = {"temperature": temp, "top_p": top_p, "json_ok": parsed_ok, "samples": args.samples,
               "all_fields_consistent": bool(consistent),
               "avg_ms": round(sum(lat) / len(lat), 0),
               "example": outputs[0] if outputs else None}
        results.append(row)
        print(f"{temp:>12}{top_p:>7}{parsed_ok:>7}/{args.samples}{'是' if consistent else '否':>11}{row['avg_ms']:>14.0f}")

    out = Path(args.out) if args.out else Path(__file__).resolve().parent / "sampling_experiment.json"
    out.write_text(json.dumps({"model": MODEL, "invoice": INVOICE.strip(), "results": results},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已写入 {out}")
    print("首个配置的输出示例：", json.dumps(results[0]["example"], ensure_ascii=False))


if __name__ == "__main__":
    main()
