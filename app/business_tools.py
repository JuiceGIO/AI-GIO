"""业务工具（Day14）：差标校验 / 报销查询 / 制度问答——给 Agent 用的手和脚"""
from app.expense_store import list_forms
from rag.ask import ask as rag_ask
from rules.travel_rules import check_expense


def evaluate_expense(type: str, amount: float, city: str) -> str:
    """差标校验：返回是否超标及超出金额"""
    result = check_expense({"type": type, "amount": float(amount), "city": city})
    if result["ok"]:
        return "该笔报销符合差旅标准，无需特殊处理。"
    return "；".join(result["messages"])


def query_expenses(type: str = None, month: str = None) -> str:
    """查报销单：可按类型/月份过滤，返回笔数和总额"""
    forms = list_forms()
    if type:
        forms = [f for f in forms if f["type"] == type]
    if month:
        forms = [f for f in forms if f["date"].startswith(month)]
    if not forms:
        return "没有符合条件的报销单。"
    total = sum(f["amount"] for f in forms)
    detail = "，".join(
        f"{f['date']} {f['city']} {f['amount']:.2f} 元（{f['status']}）" for f in forms
    )
    return f"共 {len(forms)} 笔，合计 {total:.2f} 元；明细：{detail}"


def ask_policy(question: str) -> str:
    """制度问答（走 RAG）"""
    return rag_ask(question)