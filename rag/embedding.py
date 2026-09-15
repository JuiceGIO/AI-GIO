"""手写中文向量化（玩具版：字符 bigram + TF 归一化）

为什么用字符 bigram：中文没有空格分词，相邻两个字的组合是简单有效的词形特征，
比如「住宿」「标准」「500」都能成为特征。真实项目会换 jieba 分词 + 预训练向量模型。
"""
import math
from collections import Counter


def tokenize(text: str) -> list:
    """字符 bigram 分词"""
    text = text.strip()
    if len(text) <= 1:
        return [text] if text else []
    return [text[i : i + 2] for i in range(len(text) - 1)]


def build_vocab(texts: list) -> dict:
    """收集所有文本的 token，建成 词 -> 下标 的词汇表"""
    vocab = {}
    for text in texts:
        for tok in tokenize(text):
            if tok not in vocab:
                vocab[tok] = len(vocab)
    return vocab


def vectorize(text: str, vocab: dict) -> list:
    """文本 -> TF 向量（L2 归一化，让余弦相似度=点积）"""
    vec = [0.0] * len(vocab)
    for tok, count in Counter(tokenize(text)).items():
        idx = vocab.get(tok)
        if idx is not None:
            vec[idx] = float(count)
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]