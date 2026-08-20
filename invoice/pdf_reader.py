"""发票 PDF 文本提取（Day8）"""
from pypdf import PdfReader


def extract_text(pdf_path: str) -> str:
    """读取 PDF 每一页的文本并拼接"""
    reader = PdfReader(str(pdf_path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)