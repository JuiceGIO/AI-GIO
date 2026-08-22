package com.expenseai.approval.web;

import java.util.List;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.expenseai.approval.model.ExpenseForm;
import com.expenseai.approval.service.ApprovalService;

/** Day 24：超时未审批查询接口 */
@RestController
public class OverdueController {

	private final ApprovalService approvalService;

	public OverdueController(ApprovalService approvalService) {
		this.approvalService = approvalService;
	}

	@GetMapping("/overdue")
	public List<ExpenseForm> overdue(
			@RequestParam(name = "hours", defaultValue = "48") int hours) {
		return approvalService.listOverdue(hours);
	}
}
