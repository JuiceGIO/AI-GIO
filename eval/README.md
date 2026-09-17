# eval/ 检索与评测实验

本目录除了常规评测（`check_golden_set.py` / `evaluate.py`），还有四个**可复跑的检索实验脚本**。
它们支撑了简历与 README 里的检索数字，命令都在下方，不需要 GPU；`bge` 相关脚本用 onnxruntime + tokenizers 推理（无需 torch）。

同目录已附带本次实测的结果文件，点开即可核对数字：`rrf_k_sweep.json`、`embedding_compare.json`、`pgvector_compare.json`、`pgvector_scale.json`。

## 0. 依赖

```powershell
# 常规评测：venv 里已有依赖
.venv\Scripts\python.exe -m eval.check_golden_set
# 检索实验额外需要（项目环境已包含）：onnxruntime、tokenizers、numpy、psycopg2
```

## 1. 向量化选型实验（手写 bigram vs bge-small-zh）

```powershell
# 1) 下载 bge-small-zh-v1.5 的 ONNX 版本（约 113MB，走 hf-mirror，国内可用）
.venv\Scripts\python.exe eval\fetch_onnx_model.py models\bge-small-zh-onnx
# 2) 跑四后端对比：bigram / bge fp32（加指令、不加指令）/ bge int8
.venv\Scripts\python.exe eval\embedding_compare.py --repo . --onnx-dir models\bge-small-zh-onnx
```

实测结果（17 块语料 + 41 条 golden，本机 CPU）：

| 后端 | 维度 | 纯向量 Recall@1 | Recall@3 | NDCG@10 | P95 |
|---|---|---|---|---|---|
| bigram + TF（原实现） | 930（随语料变化） | 92.7% | **100%** | 0.967 | **0.1ms** |
| **bge-small-zh fp32 + query 指令** | **512 固定** | **95.1%** | 97.6% | **0.971** | 4.8ms |
| bge-small-zh fp32，不加指令 | 512 | 92.7% | 100% | 0.967 | 2.8ms |
| bge-small-zh int8 量化 + 指令 | 512 | 92.7% | 97.6% | 0.963 | 3.3ms |

结论：换 bge-small-zh 后纯向量 Recall@1 **92.7% → 95.1%**；bge 官方 query 指令前缀**实测有效（+2.4pt）**；int8 量化有损故用 fp32；**Recall@3 反而从 100% 掉到 97.6%**（换模型不是全面提升）。

## 2. RRF k 值扫描

```powershell
.venv\Scripts\python.exe eval\rrf_k_sweep.py --repo . --ks 1,5,10,20,60,100,1000 --pool 5,8
```

实测：k 从 1 到 1000，Recall@1/Recall@3/MRR/NDCG@10 **完全一致**（92.7% / 100% / 0.955 / 0.967）。
原因：语料只有 17 块、两路候选几乎覆盖全语料、且 34/41 条题目的答案在两条单路都排第 1 —— 融合排序由"命中几条路"决定，与 k 无关。k 真正起作用需要：语料上千块 + 候选池 50–100 + 存在单路召回的正确答案。当前取 RRF 原论文经验值 **k=60**。

## 3. 三方检索对比（numpy / pgvector 顺序扫描 / pgvector HNSW）

```powershell
docker run -d --name agentservice-pgvector -e POSTGRES_PASSWORD=postgres -p 5433:5432 pgvector/pgvector:pg16
.venv\Scripts\python.exe eval\pgvector_compare.py --repo . --dsn "postgresql://postgres:postgres@127.0.0.1:5433/postgres" --onnx-dir models\bge-small-zh-onnx
```

实测（512 维，17 块，41 条 query）：三种后端 Recall@1 都是 95.1%、NDCG@10 0.971 —— 小语料下 HNSW 与暴力检索结果一致，延迟差异来自 query 编码与数据库往返。

## 4. 规模测试（HNSW 什么时候才有用）

```powershell
.venv\Scripts\python.exe eval\pgvector_scale_test.py --repo . --dsn "postgresql://postgres:postgres@127.0.0.1:5433/postgres" --onnx-dir models\bge-small-zh-onnx --sizes 17,200,1000,3000
```

| 语料规模 | numpy 暴力 | pgvector 顺序扫描 | pgvector HNSW | HNSW 构建 | 表大小 |
|---|---|---|---|---|---|
| 17 | ~0.0ms | 1.55ms | 1.72ms | 0.02s | 168KB |
| 200 | 0.01ms | 1.88ms | 1.96ms | 0.08s | 1.1MB |
| 1000 | 0.1ms | 3.81ms | **1.67ms** | 0.21s | 5.4MB |
| 3000 | 0.17ms | 8.20ms | **1.94ms** | 0.58s | 16MB |

结论：**HNSW 的拐点在 1000 块附近**。但同一量级下 numpy 内存暴力检索仍然最快 —— pgvector 的价值是**持久化、事务、WHERE 过滤（多租户/权限）、并发访问**，而不是这个量级的速度；另外 3000 块离线编码要 108s、入库 86s，批量重建必须放离线流程。

> 说明：规模测试用"真实块 + 编号变体"合成语料，只用于测延迟与索引成本，召回指标在合成语料上无意义，故不报。

## 5. 分词对比实验（手写 bigram vs 单字 vs WordPiece）

```powershell
.venv\Scripts\python.exe eval\tokenizer_compare.py --repo . --onnx-dir models\bge-small-zh-onnx
```

| 分词方式 | 语料词表 | 查询 token 覆盖率 | 查询平均 token |
|---|---|---|---|
| 字符 bigram（原实现） | 930 | **56.8%** | 10.0 |
| 单字 unigram | 359 | 92.9% | 11.0 |
| WordPiece（bge 分词器） | 365 | **94.0%** | 12.9 |

结论：手写 bigram 有近一半查询特征在语料词表里不存在（跨词边界组合），这正是它 Recall@1 停在 92.7% 的原因之一；中文 BERT 词表以单字为主，所以 WordPiece 与单字覆盖率接近。

## 6. 采样参数实验（temperature / top_p）

```powershell
.venv\Scripts\python.exe eval\sampling_experiment.py --repo . --samples 5   # 结构化抽取（需要 .env 里的 Key）
.venv\Scripts\python.exe eval\sampling_diversity.py  --repo . --samples 10  # 开放式生成多样性
```

- 结构化抽取（发票字段，4 组配置 × 5 次）：**20 次输出完全一致**，JSON 5/5 可解析 → 强约束任务上温度几乎无影响
- 开放式生成（同一 prompt 采样 8 次）：温度 0 → **1/8 唯一**，温度 1.5 → **7/8 唯一**

结论：参数作用取决于任务；抽取链路的稳定性靠 schema + 校验 + 降级（三层兜底），不靠调温度。
