package com.expenseai.approval.service;

/** 报销单不存在 -> 404 */
public class NotFoundException extends RuntimeException {

	public NotFoundException(String message) {
		super(message);
	}
}
