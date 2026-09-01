"""数据库层（升级1：SQLite → PostgreSQL，保留 SQLite 本地兜底）

通过环境变量 DB_BACKEND 切换：
  DB_BACKEND=sqlite   （默认）本地 SQLite，逻辑与升级前完全一致
  DB_BACKEND=postgres 生产/联调 PostgreSQL（psycopg2 + 连接池）

PostgreSQL 连接参数：PG_HOST / PG_PORT / PG_DB / PG_USER / PG_PASSWORD。
设计原则：上层 SQL 保持 `?` 占位符，由本层在 PG 模式下翻译为 %s，
所以 expense_store / approval_flow 不需要改任何 SQL。
"""
import os
import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).resolve().parent / "data" / "expenseai.db"
BACKEND = os.getenv("DB_BACKEND", "sqlite").strip().lower()


# ============ SQLite 模式（默认，保持原逻辑） ============
SCHEMA_SQLITE = """
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


# ============ PostgreSQL 模式（升级1 目标） ============
# 与 Flyway（expense-approval/src/main/resources/db/migration）保持同一套表结构。
# 索引与 Java 端 Flyway V2 一致：approvals(expense_form_id, created_at)，
# 另加 expense_forms(status) 加速「待审批列表」。
SCHEMA_POSTGRES = """
CREATE TABLE IF NOT EXISTS employees (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    role TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS expense_forms (
    id BIGSERIAL PRIMARY KEY,
    employee_id BIGINT,
    type TEXT NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    date TEXT NOT NULL,
    city TEXT NOT NULL,
    invoice_no TEXT NOT NULL UNIQUE,
    check_ok INTEGER NOT NULL,
    check_messages TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT '已提交',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invoices (
    id BIGSERIAL PRIMARY KEY,
    invoice_no TEXT NOT NULL UNIQUE,
    amount DOUBLE PRECISION NOT NULL,
    date TEXT NOT NULL,
    buyer TEXT NOT NULL,
    category TEXT NOT NULL,
    file_name TEXT,
    extracted_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
    id BIGSERIAL PRIMARY KEY,
    expense_form_id BIGINT NOT NULL,
    approver_id BIGINT,
    action TEXT NOT NULL,
    comment TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_approvals_expense_form_id ON approvals(expense_form_id);
CREATE INDEX IF NOT EXISTS idx_approvals_created_at ON approvals(created_at);
CREATE INDEX IF NOT EXISTS idx_expense_forms_status ON expense_forms(status);
"""

SEED_EMPLOYEES = [
    ("张三", "市场部", "employee"),
    ("李四", "市场部", "manager"),
    ("王五", "财务部", "finance"),
]


# ============ 连接封装（让上层 SQL 无需区分两种数据库） ============

class _Cursor:
    """统一游标：sqlite cursor 与 psycopg2 cursor 都暴露 fetchone/fetchall/lastrowid"""

    def __init__(self, raw, lastrowid=None):
        self._raw = raw
        self.lastrowid = lastrowid

    def fetchone(self):
        return self._raw.fetchone()

    def fetchall(self):
        return self._raw.fetchall()


class _Conn:
    """统一连接：execute 时把 `?` 翻译成 %s（PG 模式），并自动补 RETURNING id。"""

    def __init__(self, raw, backend):
        self._raw = raw
        self._backend = backend

    def execute(self, sql: str, params=None):
        if self._backend == "postgres":
            pg_sql = sql.replace("?", "%s")
            is_insert = pg_sql.lstrip().upper().startswith("INSERT")
            if is_insert and "RETURNING" not in pg_sql.upper():
                pg_sql = pg_sql.rstrip().rstrip(";") + " RETURNING id"
            cur = self._raw.cursor()
            try:
                cur.execute(pg_sql, params or ())
            except Exception as e:
                # 唯一约束冲突统一成 sqlite3.IntegrityError，上层（发票号重复拦截）不用区分数据库
                if getattr(e, "sqlstate", None) == "23505":
                    raise sqlite3.IntegrityError(str(e)) from e
                raise
            lastrowid = None
            if is_insert:
                # 只对 INSERT 消费 RETURNING 行；SELECT/UPDATE 不预读，保证上层拿到完整结果
                row = cur.fetchone()
                if row is not None:
                    lastrowid = row["id"]
            return _Cursor(cur, lastrowid)
        cur = self._raw.execute(sql, params or ())
        return _Cursor(cur, cur.lastrowid)

    def executescript(self, script: str):
        if self._backend == "postgres":
            cur = self._raw.cursor()
            for statement in script.split(";"):
                statement = statement.strip()
                if statement:
                    cur.execute(statement)
            return
        self._raw.executescript(script)

    def commit(self):
        self._raw.commit()

    def rollback(self):
        self._raw.rollback()

    def close(self):
        if self._backend == "postgres":
            # 归还连接池（不真正关闭）：先回滚未提交事务，避免污染下一位使用者
            try:
                self._raw.rollback()
            except Exception:
                pass
            _pg_pool.putconn(self._raw)
        else:
            self._raw.close()


def _sqlite_conn():
    import sqlite3

    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return _Conn(conn, "sqlite")


_pg_pool = None


def _pg_pool_get():
    """懒加载 psycopg2 连接池（未安装 psycopg2 时只有 PG 模式会报错，SQLite 模式不受影响）"""
    global _pg_pool
    if _pg_pool is None:
        import psycopg2
        from psycopg2 import pool
        from psycopg2.extras import RealDictCursor

        psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
        _pg_pool = pool.ThreadedConnectionPool(
            minconn=int(os.getenv("PG_POOL_MIN", "1")),
            maxconn=int(os.getenv("PG_POOL_MAX", "10")),
            host=os.getenv("PG_HOST", "127.0.0.1"),
            port=int(os.getenv("PG_PORT", "5432")),
            dbname=os.getenv("PG_DB", "expenseai"),
            user=os.getenv("PG_USER", "expenseai"),
            password=os.getenv("PG_PASSWORD", "expenseai"),
            cursor_factory=RealDictCursor,  # 行按列名取，等价 sqlite3.Row
        )
    raw = _pg_pool.getconn()
    return _Conn(raw, "postgres"), raw


def get_conn():
    """打开连接（row_factory 让行像 dict 一样按列名取值）"""
    if BACKEND == "postgres":
        conn, raw = _pg_pool_get()
        return conn
    return _sqlite_conn()


def init_db() -> None:
    """建表 + 索引 + 种子员工数据（幂等：重复执行不报错、不重复插入）"""
    conn = get_conn()
    try:
        conn.executescript(SCHEMA_POSTGRES if BACKEND == "postgres" else SCHEMA_SQLITE)
        count = conn.execute("SELECT COUNT(*) AS cnt FROM employees").fetchone()["cnt"]
        if count == 0:
            placeholders = "(%s, %s, %s)" if BACKEND == "postgres" else "(?, ?, ?)"
            sql = f"INSERT INTO employees (name, department, role) VALUES {placeholders}"
            for emp in SEED_EMPLOYEES:
                conn.execute(sql, emp)
        conn.commit()
    finally:
        conn.close()
