-- 升级1：PostgreSQL 建表（与 Python 端 db.SCHEMA_POSTGRES 保持同一套结构）
CREATE TABLE employees (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    role TEXT NOT NULL
);

CREATE TABLE expense_forms (
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

CREATE TABLE invoices (
    id BIGSERIAL PRIMARY KEY,
    invoice_no TEXT NOT NULL UNIQUE,
    amount DOUBLE PRECISION NOT NULL,
    date TEXT NOT NULL,
    buyer TEXT NOT NULL,
    category TEXT NOT NULL,
    file_name TEXT,
    extracted_at TEXT NOT NULL
);

CREATE TABLE approvals (
    id BIGSERIAL PRIMARY KEY,
    expense_form_id BIGINT NOT NULL,
    approver_id BIGINT,
    action TEXT NOT NULL,
    comment TEXT,
    created_at TEXT NOT NULL
);

-- 种子员工（与 Python 端一致：employee / manager / finance）
INSERT INTO employees (name, department, role) VALUES
    ('张三', '市场部', 'employee'),
    ('李四', '市场部', 'manager'),
    ('王五', '财务部', 'finance');
