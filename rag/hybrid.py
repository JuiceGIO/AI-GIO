"""混合检索：向量 + BM25 + RRF 融合"""
from rag.bm25 import BM25
from rag.vector_store import VectorStore


def rrf_fuse(*ranked_lists, k: int = 60, top_k: int = 3) -> list:
    """Reciprocal Rank Fusion：多个排序列表按名次融合
    每个列表里第 rank 名得 1/(k+rank) 分，跨列表累加，按总分重排。
    好处：不看具体分数只看名次，两种检索的分数尺度不同也能公平融合。
    """
    scores = {}
    chunk_by_id = {}
    for ranked in ranked_lists:
        for rank, (chunk, _) in enumerate(ranked, start=1):
            cid = id(chunk)
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
            chunk_by_id[cid] = chunk
    order = sorted(scores, key=scores.get, reverse=True)
    return [(chunk_by_id[cid], scores[cid]) for cid in order[:top_k]]


class HybridSearch:
    """双路检索：向量抓语义、BM25 抓关键词，RRF 融合"""

    def __init__(self, chunks: list):
        self.chunks = chunks
        self.vector = VectorStore()
        self.vector.build_index(chunks)
        self.bm25 = BM25()
        self.bm25.build_index(chunks)

    def search(self, query: str, top_k: int = 3) -> list:
        # 每路多取一些，融合后再截断，避免某一路的次选被漏掉
        vec_hits = self.vector.search(query, top_k=max(top_k * 2, 5))
        bm25_hits = self.bm25.search(query, top_k=max(top_k * 2, 5))
        return rrf_fuse(vec_hits, bm25_hits, top_k=top_k)