package com.expenseai.approval.model;

/** 错误响应体：{ "detail": "..." }，与 FastAPI 的 HTTPException 格式一致 */
public record ApiError(String detail) {
}
