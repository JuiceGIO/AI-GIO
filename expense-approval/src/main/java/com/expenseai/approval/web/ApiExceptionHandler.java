package com.expenseai.approval.web;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import com.expenseai.approval.model.ApiError;
import com.expenseai.approval.service.IllegalTransitionException;
import com.expenseai.approval.service.NotFoundException;

/** 统一错误输出：{ "detail": "..." }，与 FastAPI HTTPException 格式一致 */
@RestControllerAdvice
public class ApiExceptionHandler {

	@ExceptionHandler(NotFoundException.class)
	@ResponseStatus(HttpStatus.NOT_FOUND)
	public ApiError notFound(NotFoundException e) {
		return new ApiError(e.getMessage());
	}

	@ExceptionHandler(IllegalTransitionException.class)
	@ResponseStatus(HttpStatus.CONFLICT)
	public ApiError illegalTransition(IllegalTransitionException e) {
		return new ApiError(e.getMessage());
	}
}
