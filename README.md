# AI-GIO（本地项目名：ExpenseAI）

> 企业差旅报销系统 + AI 制度问答助手（生产级 RAG）——两周完成：报销业务闭环 + 基础 RAG + 评测对比

## 项目简介（一句话）

员工提交差旅报销单、上传电子发票 → AI 自动抽取发票字段、校验差旅标准 → 多级审批（部门 → 财务）→ 打款归档；员工随时用自然语言问差旅制度，制度问答用生产级 RAG（混合检索 + 重排 + 引用 + 拒答 + 评测对比）。

## 当前进度（两周）

| 阶段 | 内容 | 状态 |
|---|---|---|
| 第 1 周（Day 1-7） | LLM 封装 → FastAPI → 手写 ReAct Agent → 网页 | ✅ |
| 第 2 周（Day 8-14） | 发票抽取 → 报销单 → 差标校验 → 基础 RAG → SQLite → 审批状态机 → Agent 接业务 | ✅ |
| 第 3 周（Day 15-21） | 切块对比 → 混合检索 → 重排/引用/拒答 → golden set → 评测对比 → Gradio 界面 → 全流程验收 | ✅ |

## 功能清单

- **员工端**：上传发票 PDF 自动抽取字段（金额/日期/发票号/抬头/类型），提交报销自动差标校验（住宿分档/交通/餐补），重复发票号拦截
- **审批端**：待审批列表 + 通过/驳回，状态机流转（草稿→已提交→部门审批→财务审批→已打款→已归档），非法跳转拦截
- **制度问答**：混合检索 + LLM 重排 + 引用出处 + 相关度拒答
- **Agent 对话**：自然语言调业务工具（差标校验/报销查询/制度问答）

## 评测数字（Day19，41 条 golden set）

| 指标 | 纯向量 | 混合+重排 |
|---|---|---|
| Recall@1 | 92.7% | **95.1%** |
| Recall@3 | 100% | 100% |
| faithfulness | - | 90~100% |
| answer relevancy | - | 90~100% |

## 技术栈

- Python 3.10 + FastAPI + uvicorn + Gradio
- OpenAI SDK（兼容 DeepSeek，base_url 外置）
- SQLite（四张表：员工/报销单/发票/审批记录）
- 手写 RAG（字符 bigram 向量 + BM25 + RRF 融合 + LLM 重排）

## 架构图（两周版）

```
浏览器（FastAPI 页面 / Gradio 界面）
      ↓
FastAPI 接口层（app/main.py）
      ├── Agent 循环（llm/agent.py）→ 模型调用（llm/client.py）
      │     └── 工具（llm/tools.py：get_time/add/业务三工具）
      ├── 报销单接口（POST /expense_forms + transition）
      └── 规则校验（rules/travel_rules.py）
            ↓
      ├── 发票抽取（invoice/：pypdf + LLM）
      ├── 制度问答（rag/：切块→混合检索→重排→引用/拒答）
      └── SQLite（db.py）
```

## 目录结构

```
app/      FastAPI 接口 + Gradio 界面 + 业务工具
llm/      模型调用层 + Agent 循环 + 工具注册表
invoice/  发票 PDF 解析 + LLM 字段抽取
rules/    差旅标准规则表（配置化）
rag/      制度问答（切块/检索/重排） + 制度文档
eval/     golden set + 评测脚本 + 对比报告
static/   FastAPI 页面
docs/     日志、周记、评测报告、验收记录
db.py     SQLite 数据库层
.env      密钥配置（不入库）
```

## 启动方式（两种界面）

FastAPI（对话 + 报销接口 + /docs）：

```powershell
pip install -r requirements.txt
.venv\Scripts\uvicorn app.main:app --reload
# http://127.0.0.1:8000
```

Gradio（员工端 + 审批端）：

```powershell
.venv\Scripts\python.exe -m app.gradio_ui
# http://127.0.0.1:7860
```

## 评测与验收

```powershell
.venv\Scripts\python.exe -m eval.check_golden_set   # 金标准质检
.venv\Scripts\python.exe -m eval.evaluate           # 评测对比（约 1-2 分钟）
```

## 下周（第 4 周）预告

Java 21 + Spring Boot 审批状态机 + 定时提醒、一键启动、演示视频、简历、README 收尾。