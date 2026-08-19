"""大模型调用封装（Day3：流式 + 超时 + 重试 + 日志）"""
import os
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    timeout=30,        # 超过 30 秒没响应就放弃
    max_retries=2,     # 网络波动/限流时自动重试 2 次
)

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def chat(system: str, user: str, stream: bool = True) -> str:
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    start = time.perf_counter()  # 计时开始

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            stream=stream,
        )

        if not stream:
            # 非流式：直接拿完整回复
            full_text = response.choices[0].message.content
            usage = response.usage
            _log(start, tokens=usage.total_tokens if usage else None)
            return full_text

        # 流式：边生成边打印
        full_text = ""
        for chunk in response:
            piece = chunk.choices[0].delta.content
            if piece:
                print(piece, end="", flush=True)
                full_text += piece
        print()

    except Exception as e:
        print(f"\n[LLM 调用失败] {type(e).__name__}: {e}")
        raise

    _log(start)
    return full_text


def _log(start: float, tokens: int = None):
    """打印每次调用的耗时（和 token 数，如果有）"""
    elapsed = time.perf_counter() - start
    if tokens is None:
        print(f"\n[llm] 模型={MODEL} 耗时={elapsed:.2f}s")
    else:
        print(f"[llm] 模型={MODEL} 耗时={elapsed:.2f}s tokens={tokens}")


if __name__ == "__main__":
    reply = chat(
        system="你是一个企业差旅报销助手，回答要简洁专业。",
        user="你好，请用一句话介绍你自己。",
    )
    print("\n[完整回复]", reply)