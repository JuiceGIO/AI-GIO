"""SQLite 数据库层（Day12：四张表 + 基础读写，替换文件存储）"""
import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).resolve().parent / "data" / "expenseai.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    role TEXT NOT NULL            -- employee / manager / finance
);

CREATE TABLE IF NOT EXISTS expense_forms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER,
    type TEXT NOT NULL,
    amount REAL NOT NULL,
    date TEXT NOT NULL,
    city TEXT NOT NULL,
    invoice_no TEXT NOT NULL UNIQUE,
    check_ok INTEGER NOT NULL,
    check_messages TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT '已提交',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no TEXT NOT NULL UNIQUE,
    amount REAL NOT NULL,
    date TEXT NOT NULL,
    buyer TEXT NOT NULL,
    category TEXT NOT NULL,
    file_name TEXT,
    extracted_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expense_form_id INTEGER NOT NULL,
    approver_id INTEGER,
    action TEXT NOT NULL,          -- approve / reject
    comment TEXT,
    created_at TEXT NOT NULL
);
"""


def get_conn() -> sqlite3.Connection:
    """打开连接（row_factory 让行像 dict 一样按列名取值）"""
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """建表 + 种子员工数据（幂等：重复执行不报错、不重复插入）"""
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        count = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO employees (name, department, role) VALUES (?, ?, ?)",
                [
                    ("张三", "市场部", "employee"),
                    ("李四", "市场部", "manager"),
                    ("王五", "财务部", "finance"),
                ],
            )
        conn.commit()
    finally:
        conn.close()