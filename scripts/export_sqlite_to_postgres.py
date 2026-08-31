"""升级1 数据搬迁：把 SQLite（data/expenseai.db）全量导入 PostgreSQL

用法（先启动 PostgreSQL，例如 docker compose up -d postgres）：
    .venv\\Scripts\\python.exe scripts\\export_sqlite_to_postgres.py

幂等性：employees/expense_forms/invoices 用 ON CONFLICT DO NOTHING 跳过已存在行；
approvals 无唯一约束，重复执行会追加重复行，因此该脚本按「一次性迁移」使用。
"""
import os
import sqlite3
from pathlib import Path

import psycopg2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SQLITE_DB = PROJECT_ROOT / "data" / "expenseai.db"

PG_CONF = dict(
    host=os.getenv("PG_HOST", "127.0.0.1"),
    port=int(os.getenv("PG_PORT", "5432")),
    dbname=os.getenv("PG_DB", "expenseai"),
    user=os.getenv("PG_USER", "expenseai"),
    password=os.getenv("PG_PASSWORD", "expenseai"),
)

TABLES = ["employees", "expense_forms", "invoices", "approvals"]


def main():
    if not SQLITE_DB.exists():
        print(f"[错误] 找不到 SQLite 数据库：{SQLITE_DB}")
        return 1

    with sqlite3.connect(SQLITE_DB) as src:
        dst = psycopg2.connect(**PG_CONF)
        try:
            with dst.cursor() as cur:
                for table in TABLES:
                    rows = src.execute(f"SELECT * FROM {table}").fetchall()
                    cols = [d[0] for d in src.description]
                    colnames = ", ".join(cols)
                    placeholders = ", ".join(["%s"] * len(cols))
                    sql = (
                        f"INSERT INTO {table} ({colnames}) VALUES ({placeholders}) "
                        "ON CONFLICT DO NOTHING"
                    )
                    cur.executemany(sql, [tuple(r) for r in rows])
                    print(f"  {table}: {len(rows)} 行")
            dst.commit()
            print("迁移完成 ✅（重复主键/唯一约束的行已自动跳过）")
        finally:
            dst.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
