"""报销系统后端入口"""
from fastapi import FastAPI
from pydantic import BaseModel

from llm.client import chat

app = FastAPI(title="企业差旅报销 AI 助手")


# 请求体：POST /chat 时前端要传的格式
class ChatRequest(BaseModel):
    message: str


@app.get("/")
def root():
    return {"message": "服务运行中"}


@app.post("/chat")
def chat_endpoint(req: ChatRequest):
    reply = chat(
        system="你是一个企业差旅报销助手，回答要简洁专业。",
        user=req.message,
        stream=False,
    )
    return {"reply": reply}