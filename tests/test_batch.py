"""Tests for batch operations."""

import pytest

from chorm.batch import (
    BatchInsert,
    BatchUpdate,
    BatchDelete,
    batch_insert,
    batch_update,
    batch_delete,
)


# Suppress DeprecationWarnings for legacy batch classes tested here
pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

class TestBatchInsert:
    """Test BatchInsert class."""

    def test_batch_insert_initialization(self):
        """Test BatchInsert initialization."""
        batch = BatchInsert("users", ["id", "name"], batch_size=100)

        assert batch.table_name == "users"
        assert batch.columns == ["id", "name"]
        assert batch.batch_size == 100
        assert batch.total_rows == 0
        assert batch.pending_rows == 0

    def test_add_row(self):
        """Test adding a single row."""
        batch = BatchInsert("users", ["id", "name"], batch_size=3)

        result = batch.add_row([1, "Alice"])
        assert result is None  # Batch not full yet
        assert batch.pending_rows == 1
        assert batch.total_rows == 1

    def test_add_row_invalid_length(self):
        """Test adding row with wrong number of values."""
        batch = BatchInsert("users", ["id", "name"])

        with pytest.raises(ValueError, match="Row has 3 values but 2 columns expected"):
            batch.add_row([1, "Alice", "extra"])

    def test_batch_flush_on_full(self):
        """Test that batch flushes when full."""
        batch = BatchInsert("users", ["id", "name"], batch_size=2)

        batch.add_row([1, "Alice"])
        sql = batch.add_row([2, "Bob"])  # Should trigger flush

        assert sql is not None
        assert "INSERT INTO users" in sql
        assert "Alice" in sql
        assert "Bob" in sql
        assert batch.pending_rows == 0  # Batch cleared after flush
        assert batch.total_rows == 2

    def test_flush_manually(self):
        """Test manual flush."""
        batch = BatchInsert("users", ["id", "name"])

        batch.add_row([1, "Alice"])
        batch.add_row([2, "Bob"])

        sql = batch.flush()

        assert sql is not None
        assert "INSERT INTO users (id, name) VALUES" in sql
        assert batch.pending_rows == 0

    def test_flush_empty(self):
        """Test flushing empty batch."""
        batch = BatchInsert("users", ["id", "name"])

        sql = batch.flush()

        assert sql is None

    def test_finish(self):
        """Test finish method."""
        batch = BatchInsert("users", ["id", "name"], optimize_on_finish=True)

        batch.add_row([1, "Alice"])

        sqls = batch.finish()

        assert len(sqls) == 2
        assert "INSERT INTO users" in sqls[0]
        assert "OPTIMIZE TABLE users FINAL" in sqls[1]

    def test_add_rows(self):
        """Test adding multiple rows."""
        batch = BatchInsert("users", ["id", "name"], batch_size=2)

        rows = [[1, "Alice"], [2, "Bob"], [3, "Charlie"]]
        sqls = batch.add_rows(rows)

        assert len(sqls) == 1  # One full batch
        assert batch.pending_rows == 1  # Charlie is pending
        assert batch.total_rows == 3

    def test_value_formatting(self):
        """Test proper value formatting in SQL."""
        batch = BatchInsert("test", ["id", "name", "value"])

        batch.add_row([1, "Alice", None])
        sql = batch.flush()

        assert "NULL" in sql
        assert "'Alice'" in sql


class TestBatchUpdate:
    """Test BatchUpdate class."""

    def test_batch_update_initialization(self):
        """Test BatchUpdate initialization."""
        batch = BatchUpdate("users", batch_size=100)

        assert batch.table_name == "users"
        assert batch.batch_size == 100

    def test_add_update(self):
        """Test adding a single update."""
        batch = BatchUpdate("users", batch_size=3)

        result = batch.add_update({"name": "Alice"}, "id = 1")
        assert result is None  # Batch not full yet

    def test_batch_flush_on_full(self):
        """Test that batch flushes when full."""
        batch = BatchUpdate("users", batch_size=2)

        batch.add_update({"name": "Alice"}, "id = 1")
        sqls = batch.add_update({"name": "Bob"}, "id = 2")  # Should trigger flush

        assert sqls is not None
        assert len(sqls) == 2
        assert "ALTER TABLE users UPDATE" in sqls[0]
        assert "name = 'Alice'" in sqls[0]
        assert "WHERE id = 1" in sqls[0]

    def test_flush_manually(self):
        """Test manual flush."""
        batch = BatchUpdate("users")

        batch.add_update({"name": "Alice"}, "id = 1")

        sqls = batch.flush()

        assert sqls is not None
        assert len(sqls) == 1
        assert "ALTER TABLE users UPDATE name = 'Alice' WHERE id = 1" in sqls[0]

    def test_finish(self):
        """Test finish method."""
        batch = BatchUpdate("users")

        batch.add_update({"name": "Alice"}, "id = 1")

        sqls = batch.finish()

        assert len(sqls) == 1
        assert "ALTER TABLE users UPDATE" in sqls[0]


class TestBatchDelete:
    """Test BatchDelete class."""

    def test_batch_delete_initialization(self):
        """Test BatchDelete initialization."""
        batch = BatchDelete("users", batch_size=100)

        assert batch.table_name == "users"
        assert batch.batch_size == 100

    def test_add_delete(self):
        """Test adding a single delete."""
        batch = BatchDelete("users", batch_size=3)

        result = batch.add_delete("id = 1")
        assert result is None  # Batch not full yet

    def test_batch_flush_on_full(self):
        """Test that batch flushes when full."""
        batch = BatchDelete("users", batch_size=2)

        batch.add_delete("id = 1")
        sql = batch.add_delete("id = 2")  # Should trigger flush

        assert sql is not None
        assert "ALTER TABLE users DELETE WHERE" in sql
        assert "(id = 1) OR (id = 2)" in sql

    def test_flush_manually(self):
        """Test manual flush."""
        batch = BatchDelete("users")

        batch.add_delete("id = 1")
        batch.add_delete("id = 2")

        sql = batch.flush()

        assert sql is not None
        assert "ALTER TABLE users DELETE WHERE (id = 1) OR (id = 2)" in sql

    def test_finish(self):
        """Test finish method."""
        batch = BatchDelete("users")

        batch.add_delete("id = 1")

        sqls = batch.finish()

        assert len(sqls) == 1
        assert "ALTER TABLE users DELETE WHERE" in sqls[0]


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_batch_insert_function(self):
        """Test batch_insert convenience function."""
        rows = [[1, "Alice"], [2, "Bob"]]
        sqls = batch_insert("users", ["id", "name"], rows, batch_size=1)

        assert len(sqls) == 2  # Two batches
        assert all("INSERT INTO users" in sql for sql in sqls)

    def test_batch_update_function(self):
        """Test batch_update convenience function."""
        updates = [({"name": "Alice"}, "id = 1"), ({"name": "Bob"}, "id = 2")]
        sqls = batch_update("users", updates)

        assert len(sqls) == 2
        assert all("ALTER TABLE users UPDATE" in sql for sql in sqls)

    def test_batch_delete_function(self):
        """Test batch_delete convenience function."""
        where_clauses = ["id = 1", "id = 2", "id = 3"]
        sqls = batch_delete("users", where_clauses, batch_size=2)

        assert len(sqls) == 2  # Two batches
        assert all("ALTER TABLE users DELETE WHERE" in sql for sql in sqls)
