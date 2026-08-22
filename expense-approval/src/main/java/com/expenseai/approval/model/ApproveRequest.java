package com.expenseai.approval.model;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * POST /approve 请求体：form_id + 动作 + 可选意见。
 * 动作与 Python 状态机一致：submit / approve / reject / archive。
 */
public record ApproveRequest(
		@JsonProperty("form_id") long formId,
		String action,
		String comment) {

	public ApproveRequest {
		comment = comment == null ? "" : comment;
	}
}
