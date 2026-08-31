package com.expenseai.approval.mq;

import org.springframework.amqp.core.Binding;
import org.springframework.amqp.core.BindingBuilder;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.core.QueueBuilder;
import org.springframework.amqp.core.TopicExchange;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * 升级3：RabbitMQ 延迟队列（TTL + 死信）配置。
 *
 * 链路：producer → expenseai.exchange(topic) → expenseai.overdue.delay
 *       →(单条消息 TTL 48h 到期)→ 死信 → expenseai.dlx → expenseai.overdue.dead
 *       → OverdueConsumer 检查状态（仍待审批→告警，否则忽略=幂等）。
 * 与 Python 端 mq.py 的队列/交换机声明保持一致（声明幂等，重复声明无副作用）。
 */
@Configuration
public class RabbitConfig {

	public static final String EXCHANGE = "expenseai.exchange";
	public static final String DELAY_QUEUE = "expenseai.overdue.delay";
	public static final String DELAY_ROUTING_KEY = "overdue.delay";

	public static final String DLX = "expenseai.dlx";
	public static final String DEAD_QUEUE = "expenseai.overdue.dead";
	public static final String DEAD_ROUTING_KEY = "overdue.dead";

	@Bean
	public TopicExchange overdueExchange() {
		return new TopicExchange(EXCHANGE, true, false);
	}

	/** 延迟队列：消息到期后进死信交换机（TTL 用单条消息 expiration 控制，生产端设置） */
	@Bean
	public Queue delayQueue() {
		return QueueBuilder.durable(DELAY_QUEUE)
				.deadLetterExchange(DLX)
				.deadLetterRoutingKey(DEAD_ROUTING_KEY)
				.build();
	}

	@Bean
	public Queue deadQueue() {
		return QueueBuilder.durable(DEAD_QUEUE).build();
	}

	@Bean
	public TopicExchange overdueDlx() {
		return new TopicExchange(DLX, true, false);
	}

	@Bean
	public Binding delayBinding() {
		return BindingBuilder.bind(delayQueue()).to(overdueExchange()).with(DELAY_ROUTING_KEY);
	}

	@Bean
	public Binding deadBinding() {
		return BindingBuilder.bind(deadQueue()).to(overdueDlx()).with(DEAD_ROUTING_KEY);
	}
}
