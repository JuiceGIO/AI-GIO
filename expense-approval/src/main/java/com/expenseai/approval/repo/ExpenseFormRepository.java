package com.expenseai.approval.repo;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Optional;
import java.util.stream.Collectors;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import com.expenseai.approval.model.ExpenseForm;

import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.ObjectMapper;

/** 报销单数据访问层：只读 expense_forms + 追加 approvals 留痕 */
@Repository
public class ExpenseFormRepository {

	private static final DateTimeFormatter TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

	private final JdbcTemplate jdbc;
	private final ObjectMapper objectMapper;

	public ExpenseFormRepository(JdbcTemplate jdbc, ObjectMapper objectMapper) {
		this.jdbc = jdbc;
		this.objectMapper = objectMapper;
	}

	public Optional<ExpenseForm> findById(long id) {
		List<ExpenseForm> rows = jdbc.query(
				"SELECT * FROM expense_forms WHERE id = ?", this::mapRow, id);
		return rows.stream().findFirst();
	}

	public List<ExpenseForm> listByStatuses(List<String> statuses) {
		if (statuses.isEmpty()) {
			return List.of();
		}
		String placeholders = statuses.stream().map(s -> "?").collect(Collectors.joining(","));
		return jdbc.query(
				"SELECT * FROM expense_forms WHERE status IN (" + placeholders + ") ORDER BY id",
				this::mapRow, statuses.toArray());
	}

	public void updateStatus(long id, String status) {
		jdbc.update("UPDATE expense_forms SET status = ? WHERE id = ?", status, id);
	}

	public void insertApproval(long formId, String action, String comment) {
		jdbc.update(
				"INSERT INTO approvals (expense_form_id, approver_id, action, comment, created_at) VALUES (?, ?, ?, ?, ?)",
				formId, null, action, comment,
				LocalDateTime.now().format(TS));
	}

	private ExpenseForm mapRow(ResultSet rs, int rowNum) throws SQLException {
		return new ExpenseForm(
				rs.getLong("id"),
				rs.getString("type"),
				rs.getDouble("amount"),
				rs.getString("date"),
				rs.getString("city"),
				rs.getString("invoice_no"),
				new ExpenseForm.Check(rs.getInt("check_ok") == 1, parseMessages(rs.getString("check_messages"))),
				rs.getString("status"),
				rs.getString("created_at"));
	}

	@SuppressWarnings("unchecked")
	private List<String> parseMessages(String json) {
		if (json == null || json.isBlank()) {
			return List.of();
		}
		try {
			return objectMapper.readValue(json, new TypeReference<List<String>>() {
			});
		} catch (Exception e) {
			return List.of();
		}
	}
}
