package com.expenseai.approval.service;

import java.util.List;
import java.util.Map;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import com.expenseai.approval.mq.OverdueMessageProducer;
import com.expenseai.approval.model.ApproveRequest;
import com.expenseai.approval.model.ExpenseForm;
import com.expenseai.approval.repo.ExpenseFormRepository;

/**
 * 审批状态机：与 Python 端 app/approval_flow.py 的 FLOW 完全一致；
 * 升级3：状态进入待审批时发 RabbitMQ 延迟提醒消息（事务提交后发送）。
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
	private final OverdueMessageProducer overdueMessageProducer;

	public ApprovalService(ExpenseFormRepository repository, OverdueMessageProducer overdueMessageProducer) {
		this.repository = repository;
		this.overdueMessageProducer = overdueMessageProducer;
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

	/** 升级3：消费端幂等检查——报销单当前是否仍处于待审批状态 */
	public boolean isPending(long formId) {
		return repository.findById(formId)
				.map(form -> PENDING_STATUSES.contains(form.status()))
				.orElse(false);
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
		if (PENDING_STATUSES.contains(next)) {
			// 升级3：进入待审批 → 事务提交后再发延迟提醒，避免消息先于数据可见
			TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
				@Override
				public void afterCommit() {
					overdueMessageProducer.sendDelayedCheck(form.id());
				}
			});
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
