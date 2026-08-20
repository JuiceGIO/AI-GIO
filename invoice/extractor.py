"""用 LLM 从发票文本抽取结构化字段（Day8）"""
import json
import sys
from pathlib import Path

from llm.client import chat

SYSTEM_PROMPT = """你是一个发票信息抽取器。用户会给你一张电子发票的文本内容，请抽取以下字段并只输出 JSON：
{
  "amount": 价税合计金额（数字，如 602.77）,
  "date": 开票日期（格式 YYYY-MM-DD）,
  "invoice_no": 发票号码,
  "buyer": 购买方名称,
  "category": 发票类型，只允许 "交通"/"住宿"/"餐饮"/"其他"
}
要求：只输出 JSON，不要输出任何解释或多余文字。"""


def _parse_json(reply: str) -> dict:
    """容错解析：从回复里截取第一个完整 JSON 对象"""
    start = reply.find("{")
    if start == -1:
        raise ValueError(f"模型没有输出 JSON: {reply[:100]}")
    depth = 0
    for i in range(start, len(reply)):
        if reply[i] == "{":
            depth += 1
        elif reply[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(reply[start : i + 1])
    raise ValueError(f"JSON 括号不完整: {reply[start:start+100]}")


def extract_fields(text: str) -> dict:
    """发票文本 -> 字段字典"""
    reply = chat(system=SYSTEM_PROMPT, user=text, stream=False)
    return _parse_json(reply)


def run(pdf_path: str, out_dir: str = "data/invoices") -> dict:
    """完整流程：PDF -> 文本 -> 字段 -> 存 JSON 文件"""
    from invoice.pdf_reader import extract_text

    text = extract_text(pdf_path)
    fields = extract_fields(text)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    out_file = out / (Path(pdf_path).stem + ".json")
    out_file.write_text(
        json.dumps(fields, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[已保存] {out_file}")
    return fields


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python -m invoice.extractor 发票.pdf")
        sys.exit(1)
    result = run(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))