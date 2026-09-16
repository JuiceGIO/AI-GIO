# AGENTS.md · AI-GIO（ExpenseAI）

本文件是本仓库对 AI 编程助手（Codex / Cursor / Claude Code 等）的约束说明，同时也给人类协作者提供快速上下文。
**改代码前先读这里；与本文冲突的做法一律以本文为准。**

## 1. 技术栈与分层约定

| 层 | 目录 | 职责 | 禁止 |
|---|---|---|---|
| 接口层 | `app/` | FastAPI 路由、Gradio 界面、审批流转编排 | 不直接写 SQL；不复制规则表 |
| 检索层 | `rag/` | 切块 → 向量/BM25 → RRF 融合 → LLM 重排 → 引用与拒答 | 唯一入口 `rag/ask.py`，其它模块不得自己拼检索链路 |
| 抽取层 | `invoice/` | PDF 取文本 + LLM 字段抽取 | 不绕过校验直接入库（发票号「应用层查重 + DB UNIQUE」是双保险） |
| 规则层 | `rules/travel_rules.py` | 差标规则（住宿分档 / 交通 / 餐补） | 不在业务代码里写死规则常量 |
| 工具层 | `llm/tools.py` + `mcp_server.py` | Function Calling schema 与 MCP 暴露 | schema 单一来源，禁止两处各写一份 |
| Java 业务层 | `expense-approval/` | 审批状态机、事务、超时提醒 | Python 不直接 UPDATE 状态字段，只走 `db.py` 或 Java `/approve` |
| 中间件 | `cache.py` / `mq.py` | Redis 缓存、RabbitMQ 延迟消息 | 必须保留不可用时的降级（直查 / 定时兜底） |

## 2. 禁止事项（硬约束）

- **不动评测口径**：`eval/golden_set.json` 与 `eval/evaluate.py` 的指标定义不得随手改；改口径要单独提交，并同步更新 `docs/eval.md` 的基线。
- **重排必须用完整片段**：历史上为省 token 把候选截断到 120 字，丢掉「其他城市 300 元」这类关键约束，Recall@1 反而下降——禁止再引入截断优化。
- **不删校验与兜底**：发票号查重双保险、三层确定性兜底（字段格式 / 金额税额交叉 / 低置信转人工）不得移除。
- **不提交敏感文件与产物**：`.env`、`data/*.db`、`*.bak`、`wheelhouse/`、`.tools/`、缓存文件。
- **不写没有实测过的数字**；不伪造提交时间。

## 3. 常用命令

```powershell
# Python 服务（对话 + 报销接口 + /docs，:8000）
.venv\Scripts\uvicorn app.main:app --reload

# Gradio 界面（员工端 + 审批端，:7860）
.venv\Scripts\python.exe -m app.gradio_ui

# 制度问答评测（41 条 golden：先质检再跑对比）
.venv\Scripts\python.exe -m eval.check_golden_set
.venv\Scripts\python.exe -m eval.evaluate

# Java 审批服务（Spring Boot 4，Maven Wrapper 免装 Maven，:8080）
cd expense-approval; .\mvnw.cmd spring-boot:run

# 容器一键编排（PostgreSQL + Redis + RabbitMQ + 三服务）
docker compose up -d --build
```

## 4. 上下文丢失后必须重读的文件

1. `eval/golden_set.json` —— 评测口径（41 条，覆盖制度文档 17 个章节）。
2. `rag/ask.py` —— 检索链路唯一入口（混合检索 + 重排 + 引用 + 拒答阈值 5.0）。
3. `llm/tools.py` —— 工具 schema 单一来源（同时供 Function Calling 与 MCP 使用）。
4. `expense-approval/src/main/java/com/expenseai/approval/` —— 审批状态机与合法跳转。
5. `docs/eval.md`、`README.md` —— 指标结论与对外口径（Recall@1 92.7% → 95.1% 等）。
