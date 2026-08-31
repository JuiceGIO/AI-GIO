-- 升级1：高频查询索引
-- approvals 表按报销单查审批留痕、按时间查超时 → 复合索引覆盖两个场景
CREATE INDEX idx_approvals_expense_form_id ON approvals(expense_form_id);
CREATE INDEX idx_approvals_created_at ON approvals(created_at);

-- 待审批列表（已提交/部门审批/财务审批）高频查询
CREATE INDEX idx_expense_forms_status ON expense_forms(status);
