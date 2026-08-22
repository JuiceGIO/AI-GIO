package com.expenseai.approval;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class ExpenseApprovalApplication {

	public static void main(String[] args) {
		SpringApplication.run(ExpenseApprovalApplication.class, args);
	}

}
