# AI-GIO（本地项目名：ExpenseAI）

> 企业差旅报销系统 + AI 制度问答助手（生产级 RAG）——第 1 周完成：能对话、会调用工具的 Agent 骨架

## 项目简介（一句话）

员工提交差旅报销单、上传电子发票 → AI 自动抽取发票字段、校验差旅标准 → 多级审批（部门 → 财务）→ 打款归档；员工随时用自然语言问差旅制度，制度问答做到生产级 RAG（混合检索 + 重排 + 引用 + 拒答 + 评测对比）。

## 当前进度（第 1 周）

| Day | 内容 | 状态 |
|---|---|---|
| Day 1 | LLM 客户端封装（流式输出） | ✅ |
| Day 2 | FastAPI 接口（GET / + POST /chat） | ✅ |
| Day 3 | 超时 + 重试 + 日志 | ✅ |
| Day 4 | 手写 ReAct 循环 + get_time 工具 | ✅ |
| Day 5 | add 工具 + 错误回喂 + 5 步上限 + 时间幻觉修复 | ✅ |
| Day 6 | Agent 挂到 Web（POST /chat 走循环 + 浏览器页面） | ✅ |
| Day 7 | 周记 + README + 架构草图 | ✅ |

## 技术栈

- Python 3.10 + FastAPI + uvicorn
- OpenAI SDK（兼容 DeepSeek 等，base_url 外置）
- SQLite（第 2 周接入）
- Java 21 + Spring Boot（第 4 周：审批状态机 + 定时提醒）

## 架构草图（第 1 周版，后面每周细化）

```
浏览器（static/index.html）
      ↓ fetch POST /chat
FastAPI 接口层（app/main.py）
      ↓ run_agent()
ReAct 循环（llm/agent.py）
      ├── 模型调用（llm/client.py：流式 / 超时 / 重试 / 日志）
      └── 工具执行（llm/tools.py：get_time、add）
```

## 目录结构

```
app/       FastAPI 接口层（路由、请求校验）
llm/       模型调用层 + Agent 循环 + 工具注册表
static/    浏览器页面
docs/      日志与复盘
.env       密钥配置（不入库）
```

## 启动方式

```powershell
.venv\Scripts\uvicorn app.main:app --reload
```

浏览器打开 http://127.0.0.1:8000 即可对话（试试「现在几点？」「12345 + 67890 等于多少？」）。

## 下周（第 2 周）预告

发票抽取 → 报销单提交 → 差标校验 → 制度问答 v1 → SQLite 数据库 → 审批状态机 → Agent 接业务。