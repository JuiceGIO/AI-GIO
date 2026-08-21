"""制度文档切块（Day11：按章节切，Day15 再对比其他策略）"""
import re
from pathlib import Path


def chunk_markdown(path: str) -> list:
    """按「## 第X章」标题切块，返回 [{"title", "content", "source"}]"""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    source = path.stem  # 文件名（不带后缀），用于引用出处
    # 用标题做分隔：re.split 带捕获组时，奇数位是标题，偶数位是内容
    parts = re.split(r"(?m)^##\s+(.+)$", text)
    chunks = []
    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        content = parts[i + 1].strip()
        if content:
            chunks.append({"title": title, "content": content, "source": source})
    return chunks


def chunk_fixed(text: str, size: int = 200, overlap: int = 50) -> list:
    """固定长度切块：按字符数切窗口，带重叠防止切断语义"""
    chunks = []
    start = 0
    while start < len(text):
        piece = text[start : start + size]
        if piece.strip():
            chunks.append({"title": f"片段 {len(chunks) + 1}", "content": piece})
        start += size - overlap
    return chunks