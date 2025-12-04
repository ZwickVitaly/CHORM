"""Tests for TTL support in table engines."""

import pytest
from chorm.table_engines import MergeTree, ReplacingMergeTree
from chorm.types import Date, UInt64
from chorm import Table, Column


def test_mergetree_simple_ttl():
    """Test MergeTree with simple TTL."""
    engine = MergeTree(ttl="date + INTERVAL 1 MONTH")
    assert "TTL date + INTERVAL 1 MONTH" in engine.format_clause()


def test_mergetree_complex_ttl():
    """Test MergeTree with complex TTL expression."""
    ttl_expr = "date + INTERVAL 1 DAY DELETE WHERE cost > 10"
    engine = MergeTree(ttl=ttl_expr)
    assert f"TTL {ttl_expr}" in engine.format_clause()


def test_replacing_mergetree_ttl():
    """Test ReplacingMergeTree with TTL."""
    engine = ReplacingMergeTree("ver", ttl="date + INTERVAL 1 YEAR")
    clause = engine.format_clause()
    assert "ReplacingMergeTree(ver)" in clause
    assert "TTL date + INTERVAL 1 YEAR" in clause


def test_table_definition_with_ttl():
    """Test defining a table with TTL."""

    class TTLTable(Table):
        __tablename__ = "ttl_table"
        date = Column(Date())
        id = Column(UInt64())
        engine = MergeTree(ttl="date + INTERVAL 7 DAY")

    create_sql = TTLTable.create_table()
    assert "TTL date + INTERVAL 7 DAY" in create_sql


def test_modify_ttl():
    """Test ALTER TABLE MODIFY TTL."""
    from chorm import modify_ttl

    stmt = modify_ttl("my_table", "date + INTERVAL 1 MONTH")
    assert stmt.to_sql() == "ALTER TABLE my_table MODIFY TTL date + INTERVAL 1 MONTH"

    stmt_settings = modify_ttl("my_table", "date + INTERVAL 1 MONTH", max_execution_time=60)
    assert "SETTINGS max_execution_time=60" in stmt_settings.to_sql()
