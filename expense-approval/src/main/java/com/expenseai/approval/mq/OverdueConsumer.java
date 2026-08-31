package com.expenseai.approval.mq;

import java.nio.charset.StandardCharsets;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import com.expenseai.approval.service.ApprovalService;

/**
 * 升级3：延迟消息消费端。
 * 收到「48 小时后检查」的死信消息后按状态处理：
 *  - 仍待审批 → 告警（日志 + 可扩展为站内信/邮件/webhook）
 *  - 已审批/已驳回/不存在 → 忽略（消费幂等，重复消息无副作用）
 */
@Component
public class OverdueConsumer {

	private static final Logger log = LoggerFactory.getLogger(OverdueConsumer.class);

	private final ApprovalService approvalService;
	private final int reminderHours;

	public OverdueConsumer(ApprovalService approvalService,
			@Value("${expense.reminder.hours:48}") int reminderHours) {
		this.approvalService = approvalService;
		this.reminderHours = reminderHours;
	}

	@RabbitListener(queues = RabbitConfig.DEAD_QUEUE)
	public void onDelayedCheck(Message message) {
		String body = new String(message.getBody(), StandardCharsets.UTF_8).trim();
		long formId;
		try {
			formId = Long.parseLong(body);
		} catch (NumberFormatException e) {
			log.warn("忽略非法延迟消息：{}", body);
			return;
		}

		if (approvalService.isPending(formId)) {
			log.warn("[MQ 延迟提醒] 报销单 {} 已超过 {} 小时未审批，请尽快处理", formId, reminderHours);
		} else {
			log.info("[MQ 延迟提醒] 报销单 {} 已不在待审批状态，忽略（幂等）", formId);
		}
	}
}
