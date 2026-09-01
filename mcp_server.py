"""升级5（可选加分）：把业务工具暴露为 MCP server

让外部 Agent / 客户端能以标准 MCP 协议调用报销/差标/问答能力：

    .venv\\Scripts\\python.exe -m mcp_server            # 默认 stdio 传输
    .venv\\Scripts\\python.exe -m mcp_server --transport sse --port 8899

需要先安装依赖：pip install fastmcp
工具定义与 llm/tools.py 的 TOOL_SCHEMAS 一一对应（MCP 自动用函数签名生成 schema）。
"""
import sys
from pathlib import Path

# 保证从任意工作目录启动（如客户端直接调脚本路径）都能 import 项目模块
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastmcp import FastMCP

from app.business_tools import ask_policy, evaluate_expense, query_expenses

mcp = FastMCP("expenseai-tools")


@mcp.tool()
def evaluate_expense_tool(type: str, amount: float, city: str) -> str:
    """校验一笔报销是否超出差旅标准。参数：type（交通/住宿/餐饮）、amount（金额数字）、city（城市名）。返回是否超标及超出金额。"""
    return evaluate_expense(type=type, amount=float(amount), city=city)


@mcp.tool()
def query_expenses_tool(type: str | None = None, month: str | None = None) -> str:
    """查询报销单。参数可选：type（交通/住宿/餐饮）、month（月份 YYYY-MM，如 2026-07）。返回笔数和总额。"""
    return query_expenses(type=type, month=month)


@mcp.tool(name="ask_policy")
def ask_policy_tool(question: str) -> str:
    """回答企业差旅制度问题（住宿标准、交通标准、餐补、报销时限等）。参数：question（制度问题文本）。"""
    return ask_policy(question)


if __name__ == "__main__":
    mcp.run()
