"""报销系统后端入口（Day6：POST /chat 走 Agent 循环 + 浏览器页面；升级2：Redis 缓存）"""
import datetime
import httpx
from db import init_db
from pathlib import Path
from typing import Literal
from rules.travel_rules import check_expense, invalidate_rules_cache, load_rules_to_cache

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.expense_store import DuplicateInvoiceError, create_form, get_form, list_forms
from app.approval_flow import IllegalTransitionError, transition
from cache import cache_delete_prefix, cache_get_json, cache_set
from llm.agent import run_agent

app = FastAPI(title="企业差旅报销 AI 助手")

# 启动时建表 + 种子数据（幂等，重复启动不会重复插入）+ 差标规则缓存预热
init_db()
load_rules_to_cache()

# ===== Day 24：Python ↔ Java 互通（Java 业务服务在 127.0.0.1:8080）=====
JAVA_BASE_URL = "http://127.0.0.1:8080"

# 升级2：审批待办 / overdue 查询缓存 30 秒，写入审批动作时主动删 key
APPROVALS_CACHE_TTL = 30
KEY_PENDING_PREFIX = "approvals:pending:"
KEY_OVERDUE_PREFIX = "overdue:"


class JavaApproveRequest(BaseModel):
    form_id: int
    action: str
    comment: str = ""


def _invalidate_pending_cache():
    """任何审批写入动作后调用：删掉待办/超时缓存，保证下一次查询读到最新"""
    cache_delete_prefix(KEY_PENDING_PREFIX)
    cache_delete_prefix(KEY_OVERDUE_PREFIX)


@app.get("/java/ping")
def java_ping():
    with httpx.Client(base_url=JAVA_BASE_URL, timeout=5) as client:
        return client.get("/ping").json()


@app.get("/java/approvals")
def java_approvals(status: str | None = None):
    cache_key = f"{KEY_PENDING_PREFIX}{status or 'pending'}"
    cached = cache_get_json(cache_key)
    if cached is not None:
        return cached
    params = {"status": status} if status else None
    with httpx.Client(base_url=JAVA_BASE_URL, timeout=5) as client:
        resp = client.get("/approvals", params=params)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    data = resp.json()
    cache_set(cache_key, data, APPROVALS_CACHE_TTL)
    return data


@app.get("/java/overdue")
def java_overdue(hours: int = 48):
    cache_key = f"{KEY_OVERDUE_PREFIX}{hours}"
    cached = cache_get_json(cache_key)
    if cached is not None:
        return cached
    with httpx.Client(base_url=JAVA_BASE_URL, timeout=5) as client:
        resp = client.get("/overdue", params={"hours": hours})
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    data = resp.json()
    cache_set(cache_key, data, APPROVALS_CACHE_TTL)
    return data


@app.post("/java/approve")
def java_approve(req: JavaApproveRequest):
    with httpx.Client(base_url=JAVA_BASE_URL, timeout=5) as client:
        resp = client.post("/approve", json=req.model_dump())
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.json().get("detail", resp.text))
    _invalidate_pending_cache()
    return resp.json()


@app.post("/admin/cache/invalidate")
def admin_cache_invalidate():
    """运维端点：主动失效全部业务缓存（差标规则 + 待办 + overdue），下次请求自动回源"""
    invalidate_rules_cache()
    _invalidate_pending_cache()
    return {"ok": True, "message": "差标规则与审批列表缓存已失效"}


# 项目根目录（app/main.py 的上级），页面文件从这里取
PROJECT_ROOT = Path(__file__).resolve().parents[1]


# 请求体：POST /chat 时前端要传的格式
class ChatRequest(BaseModel):
    message: str

class ExpenseFormRequest(BaseModel):
    """报销单请求体：字段校验交给 Pydantic"""

    type: Literal["交通", "住宿", "餐饮"]
    amount: float = Field(gt=0, description="报销金额")
    date: datetime.date
    city: str = Field(min_length=1)
    invoice_no: str = Field(min_length=1)

class TransitionRequest(BaseModel):
    """状态流转请求体：动作 + 可选审批意见"""

    action: Literal["submit", "approve", "reject", "archive"]
    comment: str = ""

@app.get("/")
def root():
    """浏览器页面：Agent 聊天界面"""
    return FileResponse(PROJECT_ROOT / "static" / "index.html")


@app.post("/chat")
def chat_endpoint(req: ChatRequest):
    """内部走 ReAct 循环：Agent 可以自己决定调用工具再回答"""
    try:
        answer, steps = run_agent(req.message, verbose=False)
        return {"reply": answer, "steps": steps}
    except Exception as e:
        return {"reply": f"服务出错了：{type(e).__name__}: {e}", "steps": 0}

@app.post("/expense_forms", status_code=201)
def create_expense_form(req: ExpenseFormRequest):
    """创建报销单；发票号重复返回 409"""
    data = req.model_dump(mode="json")
    data["check"] = check_expense(data)  # 超标自动标记并提示
    try:
        form = create_form(data)
    except DuplicateInvoiceError as e:
        raise HTTPException(status_code=409, detail=f"发票号 {e} 已存在，不能重复提交")
    _invalidate_pending_cache()
    return form


@app.get("/expense_forms")
def get_expense_forms():
    """查看所有报销单（验证用）"""
    return list_forms()

@app.post("/expense_forms/{form_id}/transition")
def transition_form(form_id: int, req: TransitionRequest):
    """审批状态流转；报销单不存在 404，非法跳转 409"""
    form = get_form(form_id)
    if form is None:
        raise HTTPException(status_code=404, detail="报销单不存在")
    try:
        updated = transition(form, req.action, req.comment)
    except IllegalTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    _invalidate_pending_cache()
    return updated
