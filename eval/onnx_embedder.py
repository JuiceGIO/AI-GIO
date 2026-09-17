"""用 onnxruntime + tokenizers 跑 bge 系列 embedding（不依赖 torch）。
- 分词：tokenizers.Tokenizer.from_file(tokenizer.json)
- 池化：取 [CLS]（bge 官方做法）+ L2 归一化
- 检索时给 query 加官方指令前缀（可开关，用于验证是否真的有效）
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："


class OnnxEmbedder:
    def __init__(self, model_path: str | Path, tokenizer_path: str | Path, max_length: int = 512):
        self.session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        self.tokenizer = Tokenizer.from_file(str(tokenizer_path))
        self.tokenizer.enable_padding()
        self.tokenizer.enable_truncation(max_length=max_length)
        self.input_names = {i.name for i in self.session.get_inputs()}

    def encode(self, texts: list[str], add_instruction: bool = False) -> np.ndarray:
        batch = [QUERY_INSTRUCTION + t if add_instruction else t for t in texts]
        encs = self.tokenizer.encode_batch(batch)
        ids = np.array([e.ids for e in encs], dtype=np.int64)
        mask = np.array([e.attention_mask for e in encs], dtype=np.int64)
        feed = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self.input_names:
            feed["token_type_ids"] = np.array([e.type_ids for e in encs], dtype=np.int64)
        outputs = self.session.run(None, feed)
        # 输出通常是 last_hidden_state (B, T, H)
        hidden = outputs[0]
        cls = hidden[:, 0, :]                       # bge 用 [CLS] 池化
        norms = np.linalg.norm(cls, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return (cls / norms).astype(np.float32)


def find_files(model_dir: str | Path):
    d = Path(model_dir)
    fp32 = d / "onnx__model.onnx"
    q8 = d / "onnx__model_quantized.onnx"
    tok = d / "tokenizer.json"
    return {
        "fp32": fp32 if fp32.exists() else None,
        "quantized": q8 if q8.exists() else None,
        "tokenizer": tok if tok.exists() else None,
    }
