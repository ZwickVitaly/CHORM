"""Optimized batch operations for ClickHouse.

This module provides ClickHouse-optimized batch operations that leverage:
1. Native clickhouse-connect insert() method (not SQL VALUES)
2. Large batch sizes (ClickHouse prefers 100k+ rows per insert)
3. Minimal network round-trips
4. Column-oriented data format
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

logger = logging.getLogger(__name__)

# ClickHouse-optimized defaults
DEFAULT_BATCH_SIZE = 100_000  # ClickHouse handles large batches well
RECOMMENDED_MIN_BATCH = 10_000  # Minimum recommended batch size


class ClickHouseBatchInsert:
    """ClickHouse-optimized batch insert.

    Uses native clickhouse-connect client.insert() method for maximum performance.
    ClickHouse performs better with fewer large inserts than many small ones.

    Args:
        client: clickhouse-connect client instance
        table_name: Name of the table to insert into
        columns: List of column names (optional if using dict rows)
        batch_size: Rows per batch (default: 100,000)
        optimize_on_finish: Run OPTIMIZE TABLE after all inserts (default: False)

    Performance Notes:
        - ClickHouse prefers batches of 100k+ rows
        - Uses native binary protocol (much faster than SQL VALUES)
        - Minimizes network round-trips
        - Column-oriented format for efficiency

    Example:
        >>> from clickhouse_connect import get_client
        >>> client = get_client(host='localhost')
        >>>
        >>> batch = ClickHouseBatchInsert(
        ...     client, "users", ["id", "name", "email"],
        ...     batch_size=100_000
        ... )
        >>>
        >>> # Add many rows
        >>> for i in range(1_000_000):
        ...     batch.add_row([i, f"User{i}", f"user{i}@example.com"])
        >>>
        >>> # Flush remaining
        >>> batch.finish()
    """

    def __init__(
        self,
        client: Any,  # clickhouse_connect.driver.Client
        table_name: str,
        columns: Optional[List[str]] = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        optimize_on_finish: bool = False,
    ):
        self.client = client
        self.table_name = table_name
        self.columns = columns
        self.batch_size = batch_size
        self.optimize_on_finish = optimize_on_finish

        self._rows: List[List[Any]] = []
        self._total_rows = 0
        self._batches_sent = 0

        # Warn if batch size is too small
        if batch_size < RECOMMENDED_MIN_BATCH:
            logger.warning(
                f"Batch size {batch_size} is below recommended minimum "
                f"{RECOMMENDED_MIN_BATCH}. ClickHouse performs better with "
                f"larger batches (100k+ rows)."
            )

    def add_row(self, row: Sequence[Any]) -> bool:
        """Add a row to the batch.

        Args:
            row: Row data (sequence of values)

        Returns:
            True if batch was flushed, False otherwise
        """
        if self.columns and len(row) != len(self.columns):
            raise ValueError(f"Row has {len(row)} values but {len(self.columns)} columns expected")

        self._rows.append(list(row))
        self._total_rows += 1

        # Auto-flush when batch is full
        if len(self._rows) >= self.batch_size:
            self.flush()
            return True

        return False

    def add_rows(self, rows: Iterable[Sequence[Any]]) -> int:
        """Add multiple rows to the batch.

        Args:
            rows: Iterable of row data

        Returns:
            Number of batches flushed
        """
        batches_flushed = 0

        for row in rows:
            if self.add_row(row):
                batches_flushed += 1

        return batches_flushed

    def flush(self) -> int:
        """Flush current batch using native client.insert().

        Returns:
            Number of rows inserted (0 if no rows)
        """
        if not self._rows:
            return 0

        row_count = len(self._rows)

        # Make a copy of data before clearing (for thread safety)
        data_to_insert = list(self._rows)
        self._rows.clear()

        # Use native clickhouse-connect insert
        # This is MUCH faster than SQL VALUES
        self.client.insert(table=self.table_name, data=data_to_insert, column_names=self.columns)

        self._batches_sent += 1

        logger.info(f"Inserted batch #{self._batches_sent}: {row_count} rows " f"into {self.table_name}")

        return row_count

    def finish(self) -> Dict[str, Any]:
        """Finish batch operations.

        Flushes remaining rows and optionally runs OPTIMIZE TABLE.

        Returns:
            Dictionary with statistics:
            - total_rows: Total rows inserted
            - batches_sent: Number of batches sent
            - optimized: Whether OPTIMIZE TABLE was run
        """
        # Flush remaining rows
        if self._rows:
            self.flush()

        # Run OPTIMIZE TABLE if requested
        optimized = False
        if self.optimize_on_finish and self._total_rows > 0:
            logger.info(f"Running OPTIMIZE TABLE {self.table_name} FINAL")
            self.client.command(f"OPTIMIZE TABLE {self.table_name} FINAL")
            optimized = True

        stats = {
            "total_rows": self._total_rows,
            "batches_sent": self._batches_sent,
            "optimized": optimized,
            "avg_batch_size": self._total_rows / self._batches_sent if self._batches_sent > 0 else 0,
        }

        logger.info(
            f"Batch insert complete: {stats['total_rows']} rows "
            f"in {stats['batches_sent']} batches "
            f"(avg {stats['avg_batch_size']:.0f} rows/batch)"
        )

        return stats

    @property
    def total_rows(self) -> int:
        """Get total number of rows added."""
        return self._total_rows

    @property
    def pending_rows(self) -> int:
        """Get number of rows in current batch."""
        return len(self._rows)

    @property
    def batches_sent(self) -> int:
        """Get number of batches sent so far."""
        return self._batches_sent


class ClickHouseBatchInsertFromDataFrame:
    """ClickHouse-optimized batch insert from pandas DataFrame.

    Leverages clickhouse-connect's native DataFrame support for maximum performance.

    Args:
        client: clickhouse-connect client instance
        table_name: Name of the table to insert into
        batch_size: Rows per batch (default: 100,000)
        optimize_on_finish: Run OPTIMIZE TABLE after insertion (default: False)

    Example:
        >>> import pandas as pd
        >>> from clickhouse_connect import get_client
        >>>
        >>> client = get_client(host='localhost')
        >>> df = pd.DataFrame({
        ...     'id': range(1_000_000),
        ...     'name': [f'User{i}' for i in range(1_000_000)]
        ... })
        >>>
        >>> batch = ClickHouseBatchInsertFromDataFrame(
        ...     client, "users", batch_size=100_000
        ... )
        >>> batch.insert_dataframe(df)
    """

    def __init__(
        self, client: Any, table_name: str, batch_size: int = DEFAULT_BATCH_SIZE, optimize_on_finish: bool = False
    ):
        self.client = client
        self.table_name = table_name
        self.batch_size = batch_size
        self.optimize_on_finish = optimize_on_finish

        self._total_rows = 0
        self._batches_sent = 0

    def insert_dataframe(self, df: Any) -> Dict[str, Any]:
        """Insert pandas DataFrame in optimized batches.

        Args:
            df: pandas DataFrame to insert

        Returns:
            Dictionary with statistics
        """
        total_rows = len(df)

        # Insert in batches
        for i in range(0, total_rows, self.batch_size):
            batch_df = df.iloc[i : i + self.batch_size]

            # Use native DataFrame insert
            self.client.insert_df(table=self.table_name, df=batch_df)

            self._batches_sent += 1
            batch_size = len(batch_df)
            self._total_rows += batch_size

            logger.info(f"Inserted batch #{self._batches_sent}: {batch_size} rows " f"into {self.table_name}")

        # Run OPTIMIZE TABLE if requested
        optimized = False
        if self.optimize_on_finish:
            logger.info(f"Running OPTIMIZE TABLE {self.table_name} FINAL")
            self.client.command(f"OPTIMIZE TABLE {self.table_name} FINAL")
            optimized = True

        stats = {
            "total_rows": self._total_rows,
            "batches_sent": self._batches_sent,
            "optimized": optimized,
            "avg_batch_size": self._total_rows / self._batches_sent,
        }

        logger.info(f"DataFrame insert complete: {stats['total_rows']} rows " f"in {stats['batches_sent']} batches")

        return stats


def bulk_insert(
    client: Any,
    table_name: str,
    data: Union[List[List[Any]], Any],  # List of lists or DataFrame
    columns: Optional[List[str]] = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    optimize_on_finish: bool = False,
) -> Dict[str, Any]:
    """Convenience function for bulk insert.

    Automatically detects data type (list or DataFrame) and uses the appropriate method.

    Args:
        client: clickhouse-connect client instance
        table_name: Name of the table
        data: Data to insert (list of lists or pandas DataFrame)
        columns: Column names (optional for DataFrame)
        batch_size: Rows per batch (default: 100,000)
        optimize_on_finish: Run OPTIMIZE TABLE after insertion

    Returns:
        Dictionary with statistics

    Example:
        >>> from clickhouse_connect import get_client
        >>> client = get_client(host='localhost')
        >>>
        >>> # From list of lists
        >>> data = [[1, "Alice"], [2, "Bob"], ...]
        >>> stats = bulk_insert(
        ...     client, "users", data,
        ...     columns=["id", "name"],
        ...     batch_size=100_000
        ... )
        >>>
        >>> # From DataFrame
        >>> import pandas as pd
        >>> df = pd.DataFrame({'id': [1, 2], 'name': ['Alice', 'Bob']})
        >>> stats = bulk_insert(client, "users", df)
    """
    # Check if it's a DataFrame
    if hasattr(data, "iloc"):  # pandas DataFrame
        batch = ClickHouseBatchInsertFromDataFrame(
            client, table_name, batch_size=batch_size, optimize_on_finish=optimize_on_finish
        )
        return batch.insert_dataframe(data)
    else:
        # List of lists
        batch = ClickHouseBatchInsert(
            client, table_name, columns, batch_size=batch_size, optimize_on_finish=optimize_on_finish
        )
        batch.add_rows(data)
        return batch.finish()


# Performance recommendations
PERFORMANCE_TIPS = """
ClickHouse Batch Insert Performance Tips:

1. **Use Large Batches**: 100k+ rows per insert is optimal
   - Small batches (1k-10k) create overhead
   - Large batches (100k-1M) maximize throughput

2. **Use Native Insert**: client.insert() is faster than SQL
   - Avoid: INSERT INTO ... VALUES (slow)
   - Use: client.insert(table, data) (fast)

3. **Minimize Round-trips**: Accumulate data, insert in bulk
   - Bad: Insert each row individually
   - Good: Accumulate 100k rows, insert once

4. **Column-oriented Data**: ClickHouse is column-oriented
   - Consider using column format if available
   - DataFrames work well (already column-oriented)

5. **OPTIMIZE TABLE**: Run after large inserts
   - Merges parts for better query performance
   - Use sparingly (expensive operation)

6. **Async Inserts** (ClickHouse 21.11+):
   - Enable async_insert=1 in settings
   - ClickHouse batches inserts automatically
   - Good for high-frequency small inserts

Example (optimal):
    client = get_client(host='localhost')
    
    # Accumulate 1M rows
    data = []
    for i in range(1_000_000):
        data.append([i, f'value{i}'])
    
    # Insert in 100k batches
    bulk_insert(
        client, 'my_table', data,
        columns=['id', 'value'],
        batch_size=100_000
    )
"""


# Public API
__all__ = [
    "ClickHouseBatchInsert",
    "ClickHouseBatchInsertFromDataFrame",
    "bulk_insert",
    "DEFAULT_BATCH_SIZE",
    "RECOMMENDED_MIN_BATCH",
    "PERFORMANCE_TIPS",
]
