"""golden set 质检（Day18）：字段完整性 + 关键词自洽 + 章节覆盖"""
import json
import sys
from pathlib import Path

from rag.chunker import chunk_markdown

GOLDEN = Path(__file__).resolve().parent / "golden_set.json"
DOC_DIR = Path(__file__).resolve().parent.parent / "rag" / "policy_docs"
DOC_FILES = ["差旅管理制度.md", "差旅报销补充说明.md"]


def main():
    data = json.loads(GOLDEN.read_text(encoding="utf-8"))
    errors = []

    # 1) 字段完整性 + 关键词自洽
    for i, item in enumerate(data, 1):
        for field in ("question", "answer", "source", "keyword"):
            if not item.get(field):
                errors.append(f"第 {i} 条缺字段: {field}")
        if item.get("keyword") and item["keyword"] not in item["answer"]:
            errors.append(f"第 {i} 条关键词不在答案里: {item['keyword']} <- {item['answer']}")

    # 2) 章节覆盖：所有文档章节都应至少有一条 golden 覆盖
    sections = set()
    for name in DOC_FILES:
        for chunk in chunk_markdown(DOC_DIR / name):
            sections.add(f"{Path(name).stem}·{chunk['title']}")
    covered = {item["source"] for item in data}
    missing = sections - covered

    print(f"条目数: {len(data)}")
    print(f"覆盖章节: {len(covered)}/{len(sections)}")
    if missing:
        print("未覆盖章节:", *sorted(missing), sep="\n  - ")
        errors.append("存在未覆盖章节")
    if errors:
        print("\n质检发现问题：")
        for e in errors:
            print(" -", e)
        sys.exit(1)
    print("质检通过 ✅")


if __name__ == "__main__":
    main()