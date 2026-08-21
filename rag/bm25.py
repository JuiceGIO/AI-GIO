"""手写 BM25 关键词检索（Day16）

BM25 是经典的「关键词相关度」算法：词频越高越相关（但要饱和）、
越稀有的词权重越高（IDF）、文档越长惩罚越重（长度归一化）。
"""
import math
from collections import Counter

from rag.embedding import tokenize


class BM25:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1   # 词频饱和系数：词频的边际收益递减
        self.b = b     # 长度归一化强度
        self.docs = []
        self.tokens = []
        self.doc_freq = {}
        self.avgdl = 0.0
        self.n = 0

    def build_index(self, chunks: list) -> None:
        self.docs = chunks
        # 标题参与索引：和向量路一致，「报销时限」这类只在标题里的词关键词也抓得到
        self.tokens = [tokenize(c["title"] + "\n" + c["content"]) for c in chunks]
        self.n = len(self.tokens)
        self.avgdl = sum(len(t) for t in self.tokens) / max(self.n, 1)
        self.doc_freq = {}
        for toks in self.tokens:
            for tok in set(toks):
                self.doc_freq[tok] = self.doc_freq.get(tok, 0) + 1

    def idf(self, term: str) -> float:
        """逆文档频率：越稀有权重越高"""
        n = self.doc_freq.get(term, 0)
        return math.log(1 + (self.n - n + 0.5) / (n + 0.5))

    def search(self, query: str, top_k: int = 3) -> list:
        """返回 [(chunk, 分数), ...]，只保留有词项重合的"""
        q_counter = Counter(tokenize(query))
        scored = []
        for idx, toks in enumerate(self.tokens):
            f = Counter(toks)
            dl = len(toks)
            score = 0.0
            for term, qf in q_counter.items():
                tf = f.get(term, 0)
                if tf == 0:
                    continue
                # BM25 核心公式：词频饱和 + IDF + 长度归一化
                denom = tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                score += self.idf(term) * (tf * (self.k1 + 1)) / denom
            if score > 0:
                scored.append((self.docs[idx], score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]