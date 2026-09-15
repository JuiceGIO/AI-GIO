package com.expenseai.approval.web;

import java.util.List;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.expenseai.approval.model.ApproveRequest;
import com.expenseai.approval.model.ExpenseForm;
import com.expenseai.approval.service.ApprovalService;

/** 审批接口：GET /approvals + POST /approve */
@RestController
public class ApprovalController {

	private final ApprovalService approvalService;

	public ApprovalController(ApprovalService approvalService) {
		this.approvalService = approvalService;
	}

	@GetMapping("/approvals")
	public List<ExpenseForm> approvals(@RequestParam(name = "status", required = false) String status) {
		return approvalService.listApprovals(status);
	}

	@PostMapping("/approve")
	public ExpenseForm approve(@RequestBody ApproveRequest request) {
		return approvalService.approve(request);
	}
}
