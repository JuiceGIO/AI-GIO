"""报销单存储层（换成 SQLite；升级1：SQL 保持 ? 占位符，由 db 层适配 PG）"""
import json
import sqlite3
from datetime import datetime

from db import get_conn
from mq import publish_delayed_overdue_check


class DuplicateInvoiceError(Exception):
    """发票号重复"""


def _row_to_form(row) -> dict:
    """数据库行 -> 接口要的 dict（保持 API 返回结构不变）"""
    return {
        "id": row["id"],
        "type": row["type"],
        "amount": row["amount"],
        "date": row["date"],
        "city": row["city"],
        "invoice_no": row["invoice_no"],
        "check": {
            "ok": bool(row["check_ok"]),
            "messages": json.loads(row["check_messages"]),
        },
        "status": row["status"],
        "created_at": row["created_at"],
    }


def create_form(data: dict) -> dict:
    """创建报销单；发票号重复抛 DuplicateInvoiceError"""
    check = data.get("check", {"ok": True, "messages": []})
    status = data.get("status", "草稿")
    conn = get_conn()
    try:
        try:
            cur = conn.execute(
                """INSERT INTO expense_forms
                   (type, amount, date, city, invoice_no, check_ok, check_messages, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    data["type"],
                    data["amount"],
                    data["date"],
                    data["city"],
                    data["invoice_no"],
                    1 if check["ok"] else 0,
                    json.dumps(check["messages"], ensure_ascii=False),
                    status,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            # UNIQUE 约束兜底：发票号重复
            raise DuplicateInvoiceError(data["invoice_no"])
        row = conn.execute(
            "SELECT * FROM expense_forms WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        form = _row_to_form(row)
        if status in ("已提交", "部门审批", "财务审批"):
            # 直接以待审批状态创建时，同样发延迟提醒消息
            publish_delayed_overdue_check(form["id"])
        return form
    finally:
        conn.close()


def list_forms() -> list:
    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM expense_forms ORDER BY id").fetchall()
        return [_row_to_form(r) for r in rows]
    finally:
        conn.close()

def get_form(form_id: int):
    """按 id 查报销单；不存在返回 None"""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM expense_forms WHERE id = ?", (form_id,)
        ).fetchone()
        return _row_to_form(row) if row else None
    finally:
        conn.close()
