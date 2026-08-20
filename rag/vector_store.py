"""手写向量检索库（Day11：numpy 版，原理同 Chroma）"""
import numpy as np

from rag import embedding


class VectorStore:
    """存向量 + 余弦相似度检索 top-k"""

    def __init__(self):
        self.chunks = []      # [{"title", "content"}]
        self.vocab = {}       # 词 -> 下标
        self.matrix = None    # (N, D) 归一化后的 TF 向量矩阵

    def build_index(self, chunks: list) -> None:
        self.chunks = chunks
        # 向量化时把标题拼进正文：标题是强检索特征（如「报销时限」这个词只在标题里）
        texts = [c["title"] + "\n" + c["content"] for c in chunks]
        self.vocab = embedding.build_vocab(texts)
        rows = [embedding.vectorize(t, self.vocab) for t in texts]
        self.matrix = np.array(rows, dtype=float)

    def search(self, query: str, top_k: int = 2) -> list:
        """返回 [(chunk, 相似度), ...]，只保留有重合特征的"""
        q = np.array(embedding.vectorize(query, self.vocab), dtype=float)
        scores = self.matrix @ q  # 向量都已归一化，点积 = 余弦相似度
        order = np.argsort(-scores)
        hits = []
        for idx in order:
            score = float(scores[idx])
            if score <= 0:
                break
            hits.append((self.chunks[idx], score))
            if len(hits) >= top_k:
                break
        return hits