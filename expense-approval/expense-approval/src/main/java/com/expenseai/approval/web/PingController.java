package com.expenseai.approval.web;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class PingController {

	@GetMapping("/ping")
	public PingResponse ping() {
		return new PingResponse("ok", "expense-approval",
				LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME));
	}

	public record PingResponse(String status, String service, String time) {
	}
}
