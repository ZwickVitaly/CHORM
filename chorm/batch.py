"""Batch operation optimizations for improved performance."""

from __future__ import annotations

import logging
import warnings
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

from chorm.batch_optimized import (
    ClickHouseBatchInsert,
    ClickHouseBatchInsertFromDataFrame,
    bulk_insert as _optimized_bulk_insert,
)
from chorm.utils import escape_string

logger = logging.getLogger(__name__)


class BatchInsert:
    """Optimized batch insert operations.

    .. deprecated:: 0.1.4
        Use `chorm.batch.ClickHouseBatchInsert` for significantly better performance
        using native ClickHouse binary protocol. `BatchInsert` generates SQL strings
        which is slow and inefficient for large datasets.

    Provides efficient bulk insertion of data into ClickHouse tables.

    Args:
        table_name: Name of the table to insert into
        columns: List of column names
        batch_size: Number of rows per batch (default: 10000)
        optimize_on_finish: Run OPTIMIZE TABLE after insertion (default: False)

    Example:
        >>> batch = BatchInsert("users", ["id", "name", "email"], batch_size=5000)
        >>> batch.add_row([1, "Alice", "alice@example.com"])
        >>> batch.add_row([2, "Bob", "bob@example.com"])
        >>> sql = batch.flush()  # Get INSERT statement
    """

    def __init__(self, table_name: str, columns: List[str], batch_size: int = 10000, optimize_on_finish: bool = False):
        warnings.warn(
            "BatchInsert is deprecated and will be removed in a future version. "
            "Use chorm.batch.ClickHouseBatchInsert or chorm.batch.bulk_insert for native performance.",
            DeprecationWarning,
            stacklevel=2
        )
        self.table_name = table_name
        self.columns = columns
        self.batch_size = batch_size
        self.optimize_on_finish = optimize_on_finish

        self._rows: List[List[Any]] = []
        self._total_rows = 0

    def add_row(self, row: Sequence[Any]) -> Optional[str]:
        """Add a row to the batch.

        Args:
            row: Row data (must match columns length)

        Returns:
            INSERT SQL if batch is full, None otherwise

        Raises:
            ValueError: If row length doesn't match columns length
        """
        if len(row) != len(self.columns):
            raise ValueError(f"Row has {len(row)} values but {len(self.columns)} columns expected")

        self._rows.append(list(row))
        self._total_rows += 1

        # Check if batch is full
        if len(self._rows) >= self.batch_size:
            return self.flush()

        return None

    def add_rows(self, rows: Iterable[Sequence[Any]]) -> List[str]:
        """Add multiple rows to the batch.

        Args:
            rows: Iterable of row data

        Returns:
            List of INSERT SQL statements (one per full batch)
        """
        sqls = []

        for row in rows:
            sql = self.add_row(row)
            if sql:
                sqls.append(sql)

        return sqls

    def flush(self) -> Optional[str]:
        """Flush current batch and return INSERT SQL.

        Returns:
            INSERT SQL statement or None if no rows
        """
        if not self._rows:
            return None

        # Build INSERT statement
        columns_str = ", ".join(self.columns)

        # Format values
        values_parts = []
        for row in self._rows:
            formatted_values = []
            for value in row:
                if value is None:
                    formatted_values.append("NULL")
                elif isinstance(value, str):
                    # Robust escaping
                    formatted_values.append(f"'{escape_string(value)}'")
                elif isinstance(value, (list, tuple)):
                    # Array type
                    formatted_values.append(str(list(value)))
                else:
                    formatted_values.append(str(value))

            values_parts.append(f"({', '.join(formatted_values)})")

        values_str = ", ".join(values_parts)

        sql = f"INSERT INTO {self.table_name} ({columns_str}) VALUES {values_str}"

        # Clear batch
        self._rows.clear()

        return sql

    def finish(self) -> List[str]:
        """Finish batch operations and return remaining SQL.

        Returns:
            List of SQL statements (INSERT + optional OPTIMIZE)
        """
        sqls = []

        # Flush remaining rows
        sql = self.flush()
        if sql:
            sqls.append(sql)

        # Add OPTIMIZE if requested
        if self.optimize_on_finish:
            sqls.append(f"OPTIMIZE TABLE {self.table_name} FINAL")

        return sqls

    @property
    def total_rows(self) -> int:
        """Get total number of rows added."""
        return self._total_rows

    @property
    def pending_rows(self) -> int:
        """Get number of rows in current batch."""
        return len(self._rows)


class BatchUpdate:
    """Optimized batch update operations.

    Provides efficient bulk updates using ALTER TABLE UPDATE.

    Args:
        table_name: Name of the table to update
        batch_size: Number of updates per batch (default: 1000)

    Example:
        >>> batch = BatchUpdate("users")
        >>> batch.add_update({"name": "Alice"}, "id = 1")
        >>> batch.add_update({"name": "Bob"}, "id = 2")
        >>> sqls = batch.finish()
    """

    def __init__(self, table_name: str, batch_size: int = 1000):
        warnings.warn(
            "BatchUpdate is deprecated. For large updates, consider using proper batch logic or direct client execution.",
            DeprecationWarning,
            stacklevel=2
        )
        self.table_name = table_name
        self.batch_size = batch_size

        self._updates: List[tuple[Dict[str, Any], str]] = []

    def add_update(self, values: Dict[str, Any], where_clause: str) -> Optional[List[str]]:
        """Add an update to the batch.

        Args:
            values: Dictionary of column: value pairs
            where_clause: WHERE clause for this update

        Returns:
            List of UPDATE SQL if batch is full, None otherwise
        """
        self._updates.append((values, where_clause))

        # Check if batch is full
        if len(self._updates) >= self.batch_size:
            return self.flush()

        return None

    def flush(self) -> Optional[List[str]]:
        """Flush current batch and return UPDATE SQL.

        Returns:
            List of UPDATE SQL statements or None if no updates
        """
        if not self._updates:
            return None

        sqls = []

        for values, where_clause in self._updates:
            # Build SET clause
            set_parts = []
            for col, value in values.items():
                if value is None:
                    set_parts.append(f"{col} = NULL")
                elif isinstance(value, str):
                    set_parts.append(f"{col} = '{escape_string(value)}'")
                else:
                    set_parts.append(f"{col} = {value}")

            set_clause = ", ".join(set_parts)

            sql = f"ALTER TABLE {self.table_name} UPDATE {set_clause} WHERE {where_clause}"
            sqls.append(sql)

        # Clear batch
        self._updates.clear()

        return sqls

    def finish(self) -> List[str]:
        """Finish batch operations and return remaining SQL.

        Returns:
            List of UPDATE SQL statements
        """
        return self.flush() or []


class BatchDelete:
    """Optimized batch delete operations.

    Provides efficient bulk deletions using ALTER TABLE DELETE.

    Args:
        table_name: Name of the table to delete from
        batch_size: Number of deletes per batch (default: 1000)

    Example:
        >>> batch = BatchDelete("users")
        >>> batch.add_delete("id = 1")
        >>> batch.add_delete("id = 2")
        >>> sqls = batch.finish()
    """

    def __init__(self, table_name: str, batch_size: int = 1000):
        warnings.warn(
            "BatchDelete is deprecated. For large deletes, consider using proper batch logic or direct client execution.",
            DeprecationWarning,
            stacklevel=2
        )
        self.table_name = table_name
        self.batch_size = batch_size

        self._where_clauses: List[str] = []

    def add_delete(self, where_clause: str) -> Optional[str]:
        """Add a delete to the batch.

        Args:
            where_clause: WHERE clause for this delete

        Returns:
            DELETE SQL if batch is full, None otherwise
        """
        self._where_clauses.append(where_clause)

        # Check if batch is full
        if len(self._where_clauses) >= self.batch_size:
            return self.flush()

        return None

    def flush(self) -> Optional[str]:
        """Flush current batch and return DELETE SQL.

        Returns:
            DELETE SQL statement or None if no deletes
        """
        if not self._where_clauses:
            return None

        # Combine WHERE clauses with OR
        combined_where = " OR ".join(f"({clause})" for clause in self._where_clauses)

        sql = f"ALTER TABLE {self.table_name} DELETE WHERE {combined_where}"

        # Clear batch
        self._where_clauses.clear()

        return sql

    def finish(self) -> List[str]:
        """Finish batch operations and return remaining SQL.

        Returns:
            List of DELETE SQL statements
        """
        sql = self.flush()
        return [sql] if sql else []


def batch_insert(
    table_name: str,
    columns: List[str],
    rows: Iterable[Sequence[Any]],
    batch_size: int = 10000,
    optimize_on_finish: bool = False,
) -> List[str]:
    """Convenience function for batch insert.

    Args:
        table_name: Name of the table
        columns: List of column names
        rows: Iterable of row data
        batch_size: Number of rows per batch
        optimize_on_finish: Run OPTIMIZE TABLE after insertion

    Returns:
        List of INSERT SQL statements

    Example:
        >>> rows = [(1, "Alice"), (2, "Bob"), (3, "Charlie")]
        >>> sqls = batch_insert("users", ["id", "name"], rows)
        >>> for sql in sqls:
        ...     conn.execute(sql)
    """
    batch = BatchInsert(table_name, columns, batch_size=batch_size, optimize_on_finish=optimize_on_finish)

    sqls = batch.add_rows(rows)
    sqls.extend(batch.finish())

    return sqls


def batch_update(table_name: str, updates: Iterable[tuple[Dict[str, Any], str]], batch_size: int = 1000) -> List[str]:
    """Convenience function for batch update.

    Args:
        table_name: Name of the table
        updates: Iterable of (values_dict, where_clause) tuples
        batch_size: Number of updates per batch

    Returns:
        List of UPDATE SQL statements

    Example:
        >>> updates = [
        ...     ({"status": "active"}, "id = 1"),
        ...     ({"status": "inactive"}, "id = 2")
        ... ]
        >>> sqls = batch_update("users", updates)
    """
    batch = BatchUpdate(table_name, batch_size=batch_size)

    sqls = []
    for values, where_clause in updates:
        result = batch.add_update(values, where_clause)
        if result:
            sqls.extend(result)

    sqls.extend(batch.finish())

    return sqls


def batch_delete(table_name: str, where_clauses: Iterable[str], batch_size: int = 1000) -> List[str]:
    """Convenience function for batch delete.

    Args:
        table_name: Name of the table
        where_clauses: Iterable of WHERE clauses
        batch_size: Number of deletes per batch

    Returns:
        List of DELETE SQL statements

    Example:
        >>> where_clauses = ["id = 1", "id = 2", "id = 3"]
        >>> sqls = batch_delete("users", where_clauses)
    """
    batch = BatchDelete(table_name, batch_size=batch_size)

    sqls = []
    for where_clause in where_clauses:
        sql = batch.add_delete(where_clause)
        if sql:
            sqls.append(sql)

    sqls.extend(batch.finish())

    return sqls


# Expose optimized API
bulk_insert = _optimized_bulk_insert

__all__ = [
    "BatchInsert",
    "BatchUpdate",
    "BatchDelete",
    "batch_insert",
    "batch_update",
    "batch_delete",
    "ClickHouseBatchInsert",
    "ClickHouseBatchInsertFromDataFrame",
    "bulk_insert",
]
