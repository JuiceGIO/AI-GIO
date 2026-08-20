"""报销系统后端入口（Day6：POST /chat 走 Agent 循环 + 浏览器页面）"""
import datetime
from db import init_db
from pathlib import Path
from typing import Literal
from rules.travel_rules import check_expense

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.expense_store import DuplicateInvoiceError, create_form, list_forms
from app.approval_flow import IllegalTransitionError, transition
from app.expense_store import DuplicateInvoiceError, create_form, get_form, list_forms
from llm.agent import run_agent

app = FastAPI(title="企业差旅报销 AI 助手")

# 启动时建表 + 种子数据（幂等，重复启动不会重复插入）
init_db()

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
    return updated