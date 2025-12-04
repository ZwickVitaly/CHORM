"""Tests for ClickHouse-optimized batch operations."""

from unittest.mock import MagicMock, call

import pytest

from chorm.batch_optimized import (
    ClickHouseBatchInsert,
    ClickHouseBatchInsertFromDataFrame,
    bulk_insert,
    DEFAULT_BATCH_SIZE,
    RECOMMENDED_MIN_BATCH,
)


class TestClickHouseBatchInsert:
    """Test ClickHouseBatchInsert class."""

    def test_initialization(self):
        """Test batch insert initialization."""
        client = MagicMock()
        batch = ClickHouseBatchInsert(client, "users", ["id", "name"], batch_size=100_000)

        assert batch.table_name == "users"
        assert batch.columns == ["id", "name"]
        assert batch.batch_size == 100_000
        assert batch.total_rows == 0
        assert batch.pending_rows == 0

    def test_default_batch_size(self):
        """Test that default batch size is optimized for ClickHouse."""
        client = MagicMock()
        batch = ClickHouseBatchInsert(client, "users", ["id", "name"])

        assert batch.batch_size == DEFAULT_BATCH_SIZE
        assert batch.batch_size >= RECOMMENDED_MIN_BATCH

    def test_add_row(self):
        """Test adding a single row."""
        client = MagicMock()
        batch = ClickHouseBatchInsert(client, "users", ["id", "name"], batch_size=100_000)

        flushed = batch.add_row([1, "Alice"])

        assert flushed is False  # Batch not full
        assert batch.pending_rows == 1
        assert batch.total_rows == 1

    def test_add_row_invalid_length(self):
        """Test adding row with wrong number of columns."""
        client = MagicMock()
        batch = ClickHouseBatchInsert(client, "users", ["id", "name"])

        with pytest.raises(ValueError, match="Row has 3 values but 2 columns expected"):
            batch.add_row([1, "Alice", "extra"])

    def test_auto_flush_on_full_batch(self):
        """Test that batch auto-flushes when full."""
        client = MagicMock()
        batch = ClickHouseBatchInsert(client, "users", ["id", "name"], batch_size=2)  # Small batch for testing

        batch.add_row([1, "Alice"])
        flushed = batch.add_row([2, "Bob"])  # Should trigger flush

        assert flushed is True
        assert batch.pending_rows == 0  # Batch cleared
        assert batch.total_rows == 2
        assert batch.batches_sent == 1

        # Verify client.insert was called
        client.insert.assert_called_once()
        call_args = client.insert.call_args
        assert call_args.kwargs["table"] == "users"
        assert call_args.kwargs["column_names"] == ["id", "name"]
        # Data should have 2 rows
        assert len(call_args.kwargs["data"]) == 2

    def test_manual_flush(self):
        """Test manual flush."""
        client = MagicMock()
        batch = ClickHouseBatchInsert(client, "users", ["id", "name"], batch_size=100_000)

        batch.add_row([1, "Alice"])
        batch.add_row([2, "Bob"])

        rows_inserted = batch.flush()

        assert rows_inserted == 2
        assert batch.pending_rows == 0
        assert batch.batches_sent == 1

        client.insert.assert_called_once()

    def test_flush_empty_batch(self):
        """Test flushing empty batch."""
        client = MagicMock()
        batch = ClickHouseBatchInsert(client, "users", ["id", "name"])

        rows_inserted = batch.flush()

        assert rows_inserted == 0
        client.insert.assert_not_called()

    def test_add_rows_bulk(self):
        """Test adding multiple rows at once."""
        client = MagicMock()
        batch = ClickHouseBatchInsert(client, "users", ["id", "name"], batch_size=2)

        rows = [[1, "Alice"], [2, "Bob"], [3, "Charlie"], [4, "David"]]
        batches_flushed = batch.add_rows(rows)

        assert batches_flushed == 2  # Two full batches
        assert batch.pending_rows == 0
        assert batch.total_rows == 4
        assert batch.batches_sent == 2

    def test_finish_with_pending_rows(self):
        """Test finish flushes remaining rows."""
        client = MagicMock()
        batch = ClickHouseBatchInsert(client, "users", ["id", "name"], batch_size=100_000)

        batch.add_row([1, "Alice"])
        batch.add_row([2, "Bob"])

        stats = batch.finish()

        assert stats["total_rows"] == 2
        assert stats["batches_sent"] == 1
        assert stats["optimized"] is False
        client.insert.assert_called_once()

    def test_finish_with_optimize(self):
        """Test finish with OPTIMIZE TABLE."""
        client = MagicMock()
        batch = ClickHouseBatchInsert(client, "users", ["id", "name"], batch_size=100_000, optimize_on_finish=True)

        batch.add_row([1, "Alice"])
        stats = batch.finish()

        assert stats["optimized"] is True
        client.command.assert_called_once_with("OPTIMIZE TABLE users FINAL")

    def test_finish_empty_no_optimize(self):
        """Test finish with empty batch doesn't run OPTIMIZE."""
        client = MagicMock()
        batch = ClickHouseBatchInsert(client, "users", ["id", "name"], optimize_on_finish=True)

        stats = batch.finish()

        assert stats["total_rows"] == 0
        assert stats["optimized"] is False
        client.command.assert_not_called()

    def test_large_batch_size_recommended(self):
        """Test that large batch sizes don't trigger warnings."""
        client = MagicMock()

        # Large batch size - no warning
        batch = ClickHouseBatchInsert(client, "users", ["id", "name"], batch_size=100_000)

        assert batch.batch_size == 100_000


class TestClickHouseBatchInsertFromDataFrame:
    """Test DataFrame batch insert."""

    def test_initialization(self):
        """Test DataFrame batch initialization."""
        client = MagicMock()
        batch = ClickHouseBatchInsertFromDataFrame(client, "users", batch_size=100_000)

        assert batch.table_name == "users"
        assert batch.batch_size == 100_000

    def test_insert_dataframe(self):
        """Test inserting DataFrame."""
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas not installed")

        client = MagicMock()
        batch = ClickHouseBatchInsertFromDataFrame(client, "users", batch_size=2)

        df = pd.DataFrame({"id": [1, 2, 3, 4, 5], "name": ["Alice", "Bob", "Charlie", "David", "Eve"]})

        stats = batch.insert_dataframe(df)

        assert stats["total_rows"] == 5
        assert stats["batches_sent"] == 3  # 2 + 2 + 1
        assert client.insert_df.call_count == 3

    def test_insert_dataframe_with_optimize(self):
        """Test DataFrame insert with OPTIMIZE TABLE."""
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas not installed")

        client = MagicMock()
        batch = ClickHouseBatchInsertFromDataFrame(client, "users", optimize_on_finish=True)

        df = pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})

        stats = batch.insert_dataframe(df)

        assert stats["optimized"] is True
        client.command.assert_called_once_with("OPTIMIZE TABLE users FINAL")


class TestBulkInsertFunction:
    """Test bulk_insert convenience function."""

    def test_bulk_insert_from_list(self):
        """Test bulk insert from list of lists."""
        client = MagicMock()

        data = [[1, "Alice"], [2, "Bob"], [3, "Charlie"]]
        stats = bulk_insert(client, "users", data, columns=["id", "name"], batch_size=100_000)

        assert stats["total_rows"] == 3
        assert stats["batches_sent"] == 1
        client.insert.assert_called_once()

    def test_bulk_insert_from_dataframe(self):
        """Test bulk insert from DataFrame."""
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas not installed")

        client = MagicMock()

        df = pd.DataFrame({"id": [1, 2, 3], "name": ["Alice", "Bob", "Charlie"]})

        stats = bulk_insert(client, "users", df)

        assert stats["total_rows"] == 3
        client.insert_df.assert_called()

    def test_bulk_insert_with_optimize(self):
        """Test bulk insert with OPTIMIZE TABLE."""
        client = MagicMock()

        data = [[1, "Alice"], [2, "Bob"]]
        stats = bulk_insert(client, "users", data, columns=["id", "name"], optimize_on_finish=True)

        assert stats["optimized"] is True
        client.command.assert_called_once()


class TestPerformanceRecommendations:
    """Test that performance recommendations are followed."""

    def test_default_batch_size_is_large(self):
        """Test that default batch size follows ClickHouse best practices."""
        assert DEFAULT_BATCH_SIZE >= 100_000

    def test_recommended_minimum_is_reasonable(self):
        """Test that recommended minimum is at least 10k."""
        assert RECOMMENDED_MIN_BATCH >= 10_000
