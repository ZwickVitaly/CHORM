"""EXPLAIN statement support."""

from __future__ import annotations

from typing import Any, Dict, Optional

from chorm.sql.expression import Expression


class Explain(Expression):
    """Represents an EXPLAIN statement."""

    def __init__(
        self,
        statement: Any,
        explain_type: str = "AST",
        settings: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize EXPLAIN statement.

        Args:
            statement: The statement to explain (usually a Select)
            explain_type: Type of explanation (AST, SYNTAX, PLAN, PIPELINE, ESTIMATE, TABLE OVERRIDE)
            settings: Optional settings for the EXPLAIN clause
        """
        self.statement = statement
        self.explain_type = explain_type
        self._settings = settings or {}

    def to_sql(self) -> str:
        """Render the EXPLAIN statement to SQL."""
        sql = f"EXPLAIN {self.explain_type}"

        if self._settings:
            settings_list = []
            for k, v in self._settings.items():
                val_str = str(v)
                if isinstance(v, str):
                    val_str = f"'{v}'"
                settings_list.append(f"{k}={val_str}")
            sql += f" {', '.join(settings_list)}"

        stmt_sql = self.statement.to_sql() if hasattr(self.statement, "to_sql") else str(self.statement)
        sql += f" {stmt_sql}"

        return sql
