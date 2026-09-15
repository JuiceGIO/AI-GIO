"""界面业务逻辑（与 gradio 解耦，便于单独测试）"""
from app.approval_flow import IllegalTransitionError, transition
from app.expense_store import DuplicateInvoiceError, create_form, get_form, list_forms
from db import init_db
from invoice.extractor import extract_fields
from invoice.pdf_reader import extract_text
from rag.ask import ask
from rules.travel_rules import check_expense

init_db()


def extract_invoice(pdf_path: str) -> dict:
    """PDF -> LLM 抽取发票字段"""
    return extract_fields(extract_text(pdf_path))


def submit_expense(fields: dict, city: str) -> str:
    """抽取字段 + 城市 -> 提交报销，返回结果文案"""
    if not fields:
        return "请先抽取发票字段。"
    if not city or not city.strip():
        return "请填写出差城市。"

    data = {
        "type": fields.get("category", ""),
        "amount": fields.get("amount"),
        "date": fields.get("date"),
        "city": city.strip(),
        "invoice_no": fields.get("invoice_no"),
    }
    if data["type"] not in ("交通", "住宿", "餐饮"):
        return f"无法识别的报销类型：{data['type']}，请人工确认。"
    if not data["amount"] or not data["invoice_no"]:
        return "抽取结果缺少金额或发票号，请人工确认。"

    data["check"] = check_expense(data)
    try:
        form = create_form(data)
    except DuplicateInvoiceError as e:
        return f"提交失败：发票号 {e} 已存在（重复报销）。"

    msgs = "；".join(form["check"]["messages"]) or "符合差标"
    head = "提交成功 ✅" if form["check"]["ok"] else "已提交，但超标，需人工复核 ⚠️"
    return (
        f"{head}\n"
        f"发票号：{form['invoice_no']}\n"
        f"金额：{form['amount']:.2f} 元\n"
        f"日期：{form['date']}\n"
        f"状态：{form['status']}\n"
        f"差标校验：{msgs}"
    )


def ask_question(question: str) -> str:
    """制度问答（带引用）"""
    if not question or not question.strip():
        return "请输入问题。"
    return ask(question.strip())


def pending_forms_text() -> str:
    """待审批列表：已提交 / 部门审批 / 财务审批 三种状态"""
    forms = [
        f for f in list_forms()
        if f["status"] in ("已提交", "部门审批", "财务审批")
    ]
    if not forms:
        return "暂无待审批报销单。"
    return "\n".join(
        f"ID {f['id']} | {f['type']} {f['amount']:.2f} 元 | "
        f"{f['date']} {f['city']} | {f['invoice_no']} | {f['status']}"
        for f in forms
    )


def do_transition(form_id: int, action: str, comment: str) -> str:
    """审批：通过/驳回，非法跳转被状态机拦截"""
    form = get_form(form_id)
    if form is None:
        return f"ID {form_id} 不存在。"
    try:
        updated = transition(form, action, comment)
    except IllegalTransitionError as e:
        return f"操作被拒绝：{e}"
    return f"操作成功：{updated['invoice_no']} 现在状态为「{updated['status']}」"