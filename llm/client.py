"""大模型调用封装"""
import os

from dotenv import load_dotenv
from openai import OpenAI

# 读取 .env 里的配置
load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
)

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def chat(system: str, user: str, stream: bool = True) -> str:
    """发送一轮对话，返回完整回复（stream=True 时边生成边打印）"""
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        stream=stream,
    )

    if not stream:
        return response.choices[0].message.content

    # 流式：逐段打印
    full_text = ""
    for chunk in response:
        piece = chunk.choices[0].delta.content
        if piece:
            print(piece, end="", flush=True)
            full_text += piece
    print()  # 最后换行
    return full_text


if __name__ == "__main__":
    # 测试：直接运行 python llm/client.py
    reply = chat(
        system="你是一个乐于助人的助手，回答要简洁。",
        user="你好，请用一句话介绍你自己。",
    )
    print("\n[完整回复]", reply)