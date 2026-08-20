"""制度文档切块（Day11：按章节切，Day15 再对比其他策略）"""
import re
from pathlib import Path


def chunk_markdown(path: str) -> list:
    """按「## 第X章」标题切块，返回 [{"title": ..., "content": ...}]"""
    text = Path(path).read_text(encoding="utf-8")
    # 用标题做分隔：re.split 带捕获组时，奇数位是标题，偶数位是内容
    parts = re.split(r"(?m)^##\s+(.+)$", text)
    chunks = []
    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        content = parts[i + 1].strip()
        if content:
            chunks.append({"title": title, "content": content})
    return chunks