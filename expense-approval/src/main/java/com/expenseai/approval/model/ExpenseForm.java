package com.expenseai.approval.model;

import java.util.List;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * 报销单视图对象，JSON 字段与 Python 端 API 保持一致（invoice_no / created_at）。
 */
public record ExpenseForm(
		long id,
		String type,
		double amount,
		String date,
		String city,
		@JsonProperty("invoice_no") String invoiceNo,
		Check check,
		String status,
		@JsonProperty("created_at") String createdAt) {

	public record Check(boolean ok, List<String> messages) {
	}
}
