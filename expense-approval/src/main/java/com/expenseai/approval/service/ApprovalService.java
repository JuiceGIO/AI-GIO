package com.expenseai.approval.service;

import java.util.List;
import java.util.Map;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.expenseai.approval.model.ApproveRequest;
import com.expenseai.approval.model.ExpenseForm;
import com.expenseai.approval.repo.ExpenseFormRepository;

/**
 * 审批状态机（Day 23）：与 Python 端 app/approval_flow.py 的 FLOW 完全一致。
 * 草稿 -> 已提交 -> 部门审批 -> 财务审批 -> 已打款 -> 已归档；驳回后可重新提交。
 */
@Service
public class ApprovalService {

	private static final Map<String, Map<String, String>> FLOW = Map.of(
			"草稿", Map.of("submit", "已提交"),
			"已提交", Map.of("approve", "部门审批", "reject", "已驳回"),
			"部门审批", Map.of("approve", "财务审批", "reject", "已驳回"),
			"财务审批", Map.of("approve", "已打款", "reject", "已驳回"),
			"已打款", Map.of("archive", "已归档"),
			"已驳回", Map.of("submit", "已提交"),
			"已归档", Map.of());

	private static final List<String> PENDING_STATUSES = List.of("已提交", "部门审批", "财务审批");
	private static final DateTimeFormatter CREATED_AT_FORMAT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

	private final ExpenseFormRepository repository;

	public ApprovalService(ExpenseFormRepository repository) {
		this.repository = repository;
	}

	/** GET /approvals：默认列出待审批单；可传 ?status= 精确过滤 */
	public List<ExpenseForm> listApprovals(String status) {
		if (status != null && !status.isBlank()) {
			return repository.listByStatuses(List.of(status.trim()));
		}
		return repository.listByStatuses(PENDING_STATUSES);
	}

	/** GET /overdue：列出超过 hours 小时仍未审批的待审批单（48h 超时提醒） */
	public List<ExpenseForm> listOverdue(int hours) {
		LocalDateTime deadline = LocalDateTime.now().minusHours(hours);
		return repository.listByStatuses(PENDING_STATUSES).stream()
				.filter(form -> isCreatedBefore(form, deadline))
				.toList();
	}

	/** POST /approve：执行一次状态流转，approve/reject 写入审批留痕 */
	@Transactional
	public ExpenseForm approve(ApproveRequest req) {
		ExpenseForm form = repository.findById(req.formId())
				.orElseThrow(() -> new NotFoundException("报销单不存在"));

		String next = FLOW.getOrDefault(form.status(), Map.of()).get(req.action());
		if (next == null) {
			throw new IllegalTransitionException(
					"状态「" + form.status() + "」不允许执行「" + req.action() + "」");
		}

		repository.updateStatus(form.id(), next);
		if ("approve".equals(req.action()) || "reject".equals(req.action())) {
			repository.insertApproval(form.id(), req.action(), req.comment());
		}
		return repository.findById(form.id()).orElseThrow();
	}

	/** created_at 早于截止时间即视为超时；解析失败的单据不误报 */
	private boolean isCreatedBefore(ExpenseForm form, LocalDateTime deadline) {
		try {
			LocalDateTime createdAt = LocalDateTime.parse(form.createdAt(), CREATED_AT_FORMAT);
			return createdAt.isBefore(deadline);
		} catch (Exception e) {
			return false;
		}
	}
}
