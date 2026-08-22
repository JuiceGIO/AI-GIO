package com.expenseai.approval.schedule;

import java.time.LocalDateTime;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class ScheduledTasks {

	private static final Logger log = LoggerFactory.getLogger(ScheduledTasks.class);

	@Scheduled(fixedRate = 30000)
	public void heartbeat() {
		log.info("心跳：Java 审批服务运行中，当前时间 {}", LocalDateTime.now());
	}
}
