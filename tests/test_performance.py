"""Tests for Performance & Bulk Operations."""

from chorm import select, insert
from chorm.sql.ddl import optimize_table
from chorm.sql.expression import Identifier


def test_optimize_table_basic():
    """Test basic OPTIMIZE TABLE."""
    stmt = optimize_table("users")
    assert stmt.to_sql() == "OPTIMIZE TABLE users"


def test_optimize_table_final():
    """Test OPTIMIZE TABLE FINAL."""
    stmt = optimize_table("users", final=True)
    assert stmt.to_sql() == "OPTIMIZE TABLE users FINAL"


def test_optimize_table_deduplicate():
    """Test OPTIMIZE TABLE DEDUPLICATE."""
    stmt = optimize_table("users", deduplicate=True)
    assert stmt.to_sql() == "OPTIMIZE TABLE users DEDUPLICATE"


def test_optimize_table_partition():
    """Test OPTIMIZE TABLE with partition."""
    stmt = optimize_table("events", partition="2024-01")
    assert stmt.to_sql() == "OPTIMIZE TABLE events PARTITION '2024-01'"


def test_optimize_table_all_options():
    """Test OPTIMIZE TABLE with all options."""
    stmt = optimize_table("events", partition="2024-01", final=True, deduplicate=True)
    assert stmt.to_sql() == "OPTIMIZE TABLE events PARTITION '2024-01' FINAL DEDUPLICATE"


def test_insert_from_select():
    """Test INSERT FROM SELECT."""
    source_query = select(Identifier("col1"), Identifier("col2")).select_from("source_table")
    stmt = insert("target_table").from_select(source_query, columns=["col1", "col2"])
    assert stmt.to_sql() == "INSERT INTO target_table (col1, col2) SELECT col1, col2 FROM source_table"


def test_insert_from_select_no_columns():
    """Test INSERT FROM SELECT without column specification."""
    source_query = select(Identifier("*")).select_from("source_table")
    stmt = insert("target_table").from_select(source_query)
    assert stmt.to_sql() == "INSERT INTO target_table SELECT * FROM source_table"


def test_insert_from_select_with_where():
    """Test INSERT FROM SELECT with WHERE clause."""
    from chorm.sql.expression import Literal, BinaryExpression

    condition = BinaryExpression(Identifier("active"), "=", Literal(1))
    source_query = select(Identifier("col1"), Identifier("col2")).select_from("source").where(condition)
    stmt = insert("target").from_select(source_query)
    assert stmt.to_sql() == "INSERT INTO target SELECT col1, col2 FROM source WHERE (active = 1)"
