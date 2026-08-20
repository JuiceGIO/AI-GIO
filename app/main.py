"""报销系统后端入口（Day6：POST /chat 走 Agent 循环 + 浏览器页面）"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from llm.agent import run_agent

app = FastAPI(title="企业差旅报销 AI 助手")

# 项目根目录（app/main.py 的上级），页面文件从这里取
PROJECT_ROOT = Path(__file__).resolve().parents[1]


# 请求体：POST /chat 时前端要传的格式
class ChatRequest(BaseModel):
    message: str


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