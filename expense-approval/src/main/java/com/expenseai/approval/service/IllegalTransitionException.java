package com.expenseai.approval.service;

/** 非法状态跳转 -> 409，与 Python 端 IllegalTransitionError 对齐 */
public class IllegalTransitionException extends RuntimeException {

	public IllegalTransitionException(String message) {
		super(message);
	}
}
