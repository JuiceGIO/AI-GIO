package com.expenseai.approval.mq;

import java.nio.charset.StandardCharsets;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.AmqpException;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.core.MessageBuilder;
import org.springframework.amqp.core.MessageDeliveryMode;
import org.springframework.amqp.core.MessageProperties;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * 升级3：延迟消息生产者。
 * 报销单进入待审批状态时发送「delayMs 后再检查」的消息（单条 TTL + 持久化）。
 * RabbitMQ 不可达时发送失败只记日志，由 OverdueTask 定时兜底扫描覆盖。
 */
@Component
public class OverdueMessageProducer {

	private static final Logger log = LoggerFactory.getLogger(OverdueMessageProducer.class);

	private final RabbitTemplate rabbitTemplate;
	private final int delayMs;

	public OverdueMessageProducer(RabbitTemplate rabbitTemplate,
			@Value("${expense.reminder.delay-ms:172800000}") int delayMs) {
		this.rabbitTemplate = rabbitTemplate;
		this.delayMs = delayMs;
	}

	public void sendDelayedCheck(long formId) {
		try {
			Message message = MessageBuilder
					.withBody(String.valueOf(formId).getBytes(StandardCharsets.UTF_8))
					.setContentType(MessageProperties.CONTENT_TYPE_TEXT_PLAIN)
					.setDeliveryMode(MessageDeliveryMode.PERSISTENT) // 持久化，防重启丢消息
					.setExpiration(String.valueOf(delayMs))          // 单条 TTL：到期进死信
					.build();
			rabbitTemplate.convertAndSend(RabbitConfig.EXCHANGE, RabbitConfig.DELAY_ROUTING_KEY, message);
			log.info("已发送延迟检查消息 formId={} delayMs={}", formId, delayMs);
		} catch (AmqpException e) {
			log.warn("RabbitMQ 不可用，延迟提醒交给定时兜底扫描：{}", e.getMessage());
		}
	}
}
