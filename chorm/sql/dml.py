"""DML statement construction (Insert, Update, Delete)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union

from chorm.sql.expression import Expression, _coerce
import re


from chorm.utils import escape_string

def _escape_string(value: str) -> str:
    """Escape string value for SQL literal.
    
    DEPRECATED: Use chorm.utils.escape_string instead.
    """
    return escape_string(value)


def _get_qualified_name(obj: Any) -> str:
    """Get fully qualified table name from object.
    
    Returns database.table if configured, otherwise just table name.
    """
    if hasattr(obj, "__table__") and hasattr(obj.__table__, "qualified_name"):
        return obj.__table__.qualified_name
    if hasattr(obj, "__tablename__"):
        return obj.__tablename__
    return str(obj)


class Insert(Expression):
    """Represents an INSERT statement."""

    def __init__(self, table: Any) -> None:
        self.table = table
        self.values_list: List[Dict[str, Any]] = []
        self._select_query: Optional[Expression] = None
        self._columns: Optional[List[str]] = None
        self._settings: Dict[str, Any] = {}

    def values(self, *args: Any, **kwargs: Any) -> Insert:
        """Add values to insert."""
        if args:
            if len(args) == 1 and isinstance(args[0], (list, tuple)):
                # Bulk insert: list of dicts
                self.values_list.extend(args[0])
            elif len(args) == 1 and isinstance(args[0], dict):
                self.values_list.append(args[0])
        if kwargs:
            self.values_list.append(kwargs)
        return self

    def from_select(self, select_query: Any, columns: Optional[List[str]] = None) -> Insert:
        """Insert from SELECT query.

        Args:
            select_query: SELECT statement to insert from
            columns: Optional list of column names to insert into

        Example:
            insert(TargetTable).from_select(
                select(SourceTable.col1, SourceTable.col2).where(SourceTable.active == 1),
                columns=['col1', 'col2']
            )
        """
        self._select_query = select_query
        self._columns = columns
        return self

    def settings(self, **kwargs: Any) -> Insert:
        """Add SETTINGS clause."""
        self._settings.update(kwargs)
        return self

    def to_sql(self, compiler: Any = None) -> str:
        """Render the INSERT statement to SQL.

        Note: This is mostly for debugging or small inserts.
        ClickHouse client prefers separate data transmission.
        """
        table_name = _get_qualified_name(self.table)

        # INSERT FROM SELECT
        if self._select_query is not None:
            sql = f"INSERT INTO {table_name}"
            if self._columns:
                columns_str = ", ".join(self._columns)
                sql += f" ({columns_str})"

            query_sql = (
                self._select_query.to_sql(compiler) if hasattr(self._select_query, "to_sql") else str(self._select_query)
            )
            sql += f" {query_sql}"

            if self._settings:
                settings_list = []
                for k, v in self._settings.items():
                    val_str = str(v)
                    if isinstance(v, str):
                        val_str = f"'{_escape_string(v)}'"
                    settings_list.append(f"{k}={val_str}")
                sql += f" SETTINGS {', '.join(settings_list)}"

            return sql

        # Regular INSERT with VALUES
        if not self.values_list:
            return f"INSERT INTO {table_name} FORMAT Values"

        # Naive implementation for single batch
        # Assuming all dicts have same keys
        keys = list(self.values_list[0].keys())
        columns = ", ".join(keys)

        values_str_list = []
        for row in self.values_list:
            row_vals = []
            for k in keys:
                val = row.get(k)
                # Basic escaping or Parameterization
                if compiler is not None:
                     row_vals.append(compiler.add_param(val))
                elif isinstance(val, str):
                    row_vals.append(f"'{_escape_string(val)}'")
                elif val is None:
                    row_vals.append("NULL")
                else:
                    row_vals.append(str(val))
            values_str_list.append(f"({', '.join(row_vals)})")

        values_clause = ", ".join(values_str_list)

        sql = f"INSERT INTO {table_name} ({columns}) VALUES {values_clause}"

        if self._settings:
            settings_list = []
            for k, v in self._settings.items():
                val_str = str(v)
                if isinstance(v, str):
                    val_str = f"'{_escape_string(v)}'"
                settings_list.append(f"{k}={val_str}")
            sql += f" SETTINGS {', '.join(settings_list)}"


        return sql


class Update(Expression):
    """Represents an ALTER TABLE ... UPDATE statement."""

    def __init__(self, table: Any) -> None:
        self.table = table
        self._where_criteria: List[Expression] = []
        self._values: Dict[str, Any] = {}
        self._settings: Dict[str, Any] = {}

    def where(self, *criteria: Any) -> Update:
        """Add WHERE criteria."""
        for criterion in criteria:
            self._where_criteria.append(_coerce(criterion))
        return self

    def values(self, **kwargs: Any) -> Update:
        """Set values to update."""
        self._values.update(kwargs)
        return self

    def settings(self, **kwargs: Any) -> Update:
        """Add SETTINGS clause."""
        self._settings.update(kwargs)
        return self

    def to_sql(self, compiler: Any = None) -> str:
        """Render the UPDATE statement to SQL."""
        table_name = _get_qualified_name(self.table)

        assignments = []
        for k, v in self._values.items():
            val_expr = _coerce(v)
            assignments.append(f"{k} = {val_expr.to_sql(compiler)}")

        assignment_clause = ", ".join(assignments)

        sql = f"ALTER TABLE {table_name} UPDATE {assignment_clause}"

        if self._where_criteria:
            # ClickHouse ALTER TABLE UPDATE doesn't support table-qualified column names
            # Strip table prefix from WHERE clause
            criteria = " AND ".join(self._strip_table_prefix(c.to_sql(compiler), table_name) for c in self._where_criteria)
            sql += f" WHERE {criteria}"
        else:
            # ClickHouse requires WHERE for mutations usually, but we won't enforce it here strictly
            pass

        if self._settings:
            settings_list = []
            for k, v in self._settings.items():
                val_str = str(v)
                if isinstance(v, str):
                    val_str = f"'{_escape_string(v)}'"
                settings_list.append(f"{k}={val_str}")
            sql += f" SETTINGS {', '.join(settings_list)}"

        return sql
    
    @staticmethod
    def _strip_table_prefix(sql: str, table_name: str) -> str:
        """Strip table prefix from column references in SQL.
        
        ClickHouse ALTER TABLE UPDATE/DELETE don't support table-qualified column names.
        Converts 'table.column' to 'column' in WHERE clauses.
        """

        # Replace table.column with just column
        # Pattern: table_name.column_name (with word boundaries)
        pattern = rf'\b{re.escape(table_name)}\.(\w+)\b'
        return re.sub(pattern, r'\1', sql)


class Delete(Expression):
    """Represents an ALTER TABLE ... DELETE statement."""

    def __init__(self, table: Any) -> None:
        self.table = table
        self._where_criteria: List[Expression] = []
        self._settings: Dict[str, Any] = {}

    def where(self, *criteria: Any) -> Delete:
        """Add WHERE criteria."""
        for criterion in criteria:
            self._where_criteria.append(_coerce(criterion))
        return self

    def settings(self, **kwargs: Any) -> Delete:
        """Add SETTINGS clause."""
        self._settings.update(kwargs)
        return self

    def to_sql(self, compiler: Any = None) -> str:
        """Render the DELETE statement to SQL."""
        table_name = _get_qualified_name(self.table)

        sql = f"ALTER TABLE {table_name} DELETE"

        if self._where_criteria:
            # ClickHouse ALTER TABLE DELETE doesn't support table-qualified column names
            # Strip table prefix from WHERE clause (reuse Update's method)
            criteria = " AND ".join(Update._strip_table_prefix(c.to_sql(compiler), table_name) for c in self._where_criteria)
            sql += f" WHERE {criteria}"

        if self._settings:
            settings_list = []
            for k, v in self._settings.items():
                val_str = str(v)
                if isinstance(v, str):
                    val_str = f"'{_escape_string(v)}'"
                settings_list.append(f"{k}={val_str}")
            sql += f" SETTINGS {', '.join(settings_list)}"

        return sql


def insert(table: Any) -> Insert:
    return Insert(table)


def update(table: Any) -> Update:
    return Update(table)


def delete(table: Any) -> Delete:
    return Delete(table)
