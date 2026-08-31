"""工具注册表（Day4：第一个工具 get_time；升级5：OpenAI function-calling schema）"""
from datetime import datetime
from zoneinfo import ZoneInfo
from app.business_tools import ask_policy, evaluate_expense, query_expenses

def get_time(timezone: str = "Asia/Shanghai") -> str:
    """返回当前日期时间；时区不可用时退回系统本地时间"""
    try:
        tz = ZoneInfo(timezone)
    except Exception:
        tz = None
    now = datetime.now(tz)
    return f"{now.strftime('%Y-%m-%d %H:%M:%S')}（{timezone if tz else '本地时间'}）"

def add(a, b) -> str:
    """两个数字相加，支持整数和小数"""
    try:
        x, y = float(a), float(b)
    except (TypeError, ValueError):
        raise ValueError(f"参数必须是数字，收到 a={a!r}, b={b!r}")
    result = x + y
    return str(int(result)) if result.is_integer() else str(result)

# 工具注册表：名字 -> 实现函数 + 给模型看的说明
TOOLS = {
    "get_time": {
        "function": get_time,
        "description": "获取当前日期时间。可选参数 timezone（时区名，默认 Asia/Shanghai）。",
    },
    "add": {
        "function": add,
        "description": "两个数字相加。参数 a、b：要相加的数字（整数或小数）。",
    },
    "evaluate_expense": {
        "function": evaluate_expense,
        "description": (
            "校验一笔报销是否超出差旅标准。参数：type（交通/住宿/餐饮）、"
            "amount（金额数字）、city（城市名）。返回是否超标及超出金额。"
        ),
    },
    "query_expenses": {
        "function": query_expenses,
        "description": (
            "查询报销单。参数可选：type（交通/住宿/餐饮）、"
            "month（月份，格式 YYYY-MM，如 2026-07）。返回笔数和总额。"
        ),
    },
    "ask_policy": {
        "function": ask_policy,
        "description": (
            "回答企业差旅制度问题（住宿标准、交通标准、餐补、报销时限等），"
            "参数：question（制度问题文本）。"
        ),
    },
}


# 升级5：三个业务工具的标准 function-calling schema（OpenAI 原生格式），
# 可直接传给 chat.completions 的 tools= 参数；MCP server（mcp_server.py）由它定义工具。
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "evaluate_expense",
            "description": "校验一笔报销是否超出差旅标准。参数：type（交通/住宿/餐饮）、amount（金额数字）、city（城市名）。返回是否超标及超出金额。",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["交通", "住宿", "餐饮"], "description": "报销类型"},
                    "amount": {"type": "number", "description": "报销金额（元）"},
                    "city": {"type": "string", "description": "出差城市"},
                },
                "required": ["type", "amount", "city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_expenses",
            "description": "查询报销单。参数可选：type（交通/住宿/餐饮）、month（月份 YYYY-MM，如 2026-07）。返回笔数和总额。",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["交通", "住宿", "餐饮"], "description": "报销类型（可选）"},
                    "month": {"type": "string", "description": "月份，格式 YYYY-MM（可选）"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_policy",
            "description": "回答企业差旅制度问题（住宿标准、交通标准、餐补、报销时限等）。参数：question（制度问题文本）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "制度问题文本"},
                },
                "required": ["question"],
            },
        },
    },
]


def business_tool_schemas() -> list:
    """给外部调用方（Agent 客户端 / 其他服务）用的工具 schema 列表"""
    return TOOL_SCHEMAS


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
