package com.expenseai.approval.schedule;

import java.util.List;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import com.expenseai.approval.model.ExpenseForm;
import com.expenseai.approval.service.ApprovalService;

/** Day 24：定时扫描超过 48 小时未审批的单据并提醒 */
@Component
public class OverdueTask {

	private static final Logger log = LoggerFactory.getLogger(OverdueTask.class);

	private final ApprovalService approvalService;
	private final int reminderHours;

	public OverdueTask(ApprovalService approvalService,
			@Value("${expense.reminder.hours:48}") int reminderHours) {
		this.approvalService = approvalService;
		this.reminderHours = reminderHours;
	}

	@Scheduled(initialDelayString = "${expense.reminder.initial-delay-ms:10000}",
			fixedRateString = "${expense.reminder.interval-ms:60000}")
	public void remindOverdue() {
		List<ExpenseForm> overdue = approvalService.listOverdue(reminderHours);
		if (overdue.isEmpty()) {
			// 升级3：正常路径由 MQ 延迟消息驱动，这里只在消息丢失时兜底，避免每 60s 刷日志
			log.debug("定时兜底检查：暂无超过 {} 小时未审批的单据", reminderHours);
		} else {
			log.warn("定时兜底检查：发现 {} 张超时未审批单据，编号 {}", overdue.size(),
					overdue.stream().map(ExpenseForm::id).toList());
		}
	}
}
