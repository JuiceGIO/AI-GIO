"""审批状态机（Day13）：状态流转表 + 非法跳转拦截"""
from datetime import datetime

from app.expense_store import get_form
from db import get_conn

# 状态机定义：当前状态 -> {动作: 下一个状态}
FLOW = {
    "草稿": {"submit": "已提交"},
    "已提交": {"approve": "部门审批", "reject": "已驳回"},
    "部门审批": {"approve": "财务审批", "reject": "已驳回"},
    "财务审批": {"approve": "已打款", "reject": "已驳回"},
    "已打款": {"archive": "已归档"},
    "已驳回": {"submit": "已提交"},
    "已归档": {},  # 终态：不允许任何动作
}


class IllegalTransitionError(Exception):
    """非法状态跳转"""


def transition(form: dict, action: str, comment: str = "") -> dict:
    """执行状态流转；非法跳转抛 IllegalTransitionError"""
    current = form["status"]
    next_state = FLOW.get(current, {}).get(action)
    if next_state is None:
        raise IllegalTransitionError(f"状态「{current}」不允许执行「{action}」")

    conn = get_conn()
    try:
        conn.execute(
            "UPDATE expense_forms SET status = ? WHERE id = ?",
            (next_state, form["id"]),
        )
        if action in ("approve", "reject"):
            # 审批动作记入 approvals 表，形成审批留痕
            conn.execute(
                """INSERT INTO approvals
                   (expense_form_id, approver_id, action, comment, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    form["id"],
                    None,
                    action,
                    comment,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return get_form(form["id"])