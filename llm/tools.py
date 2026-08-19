"""工具注册表（Day4：第一个工具 get_time）"""
from datetime import datetime
from zoneinfo import ZoneInfo


def get_time(timezone: str = "Asia/Shanghai") -> str:
    """返回当前日期时间；时区不可用时退回系统本地时间"""
    try:
        tz = ZoneInfo(timezone)
    except Exception:
        tz = None
    now = datetime.now(tz)
    return f"{now.strftime('%Y-%m-%d %H:%M:%S')}（{timezone if tz else '本地时间'}）"


# 工具注册表：名字 -> 实现函数 + 给模型看的说明
TOOLS = {
    "get_time": {
        "function": get_time,
        "description": "获取当前日期时间。可选参数 timezone（时区名，默认 Asia/Shanghai）。",
    },
}


def tool_list_text() -> str:
    """把工具列表拼成给模型看的提示词"""
    return "\n".join(f"- {name}：{meta['description']}" for name, meta in TOOLS.items())


def execute_tool(name: str, args) -> tuple:
    """执行工具，返回 (结果文本, 错误文本)。错误时结果文本为 None。"""
    meta = TOOLS.get(name)
    if meta is None:
        return None, f"未知工具: {name}"

    func = meta["function"]
    try:
        if isinstance(args, dict):
            result = func(**args)
        elif isinstance(args, (list, tuple)):
            result = func(*args)
        else:
            result = func()
        return str(result), None
    except TypeError as e:
        return None, f"参数错误: {e}"
    except Exception as e:
        return None, f"执行失败: {type(e).__name__}: {e}"
