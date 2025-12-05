"""Integration tests for Performance & Bulk Operations."""

import os
import pytest

from chorm import Table, Column, Engine, insert, select, optimize_table
from chorm.table_engines import MergeTree
from chorm.types import UInt64, String, Date
from chorm.sql.expression import Identifier

# Skip if ClickHouse is not available
pytestmark = pytest.mark.skipif(not os.getenv("CLICKHOUSE_HOST"), reason="CLICKHOUSE_HOST environment variable not set")


class SourceTable(Table):
    __tablename__ = "perf_source_table"
    __engine__ = MergeTree()
    __order_by__ = ["id"]

    id = Column(UInt64())
    name = Column(String())
    value = Column(UInt64())
    date = Column(Date())


class TargetTable(Table):
    __tablename__ = "perf_target_table"
    __engine__ = MergeTree()
    __order_by__ = ["id"]

    id = Column(UInt64())
    name = Column(String())
    value = Column(UInt64())


@pytest.fixture
def engine():
    """Create engine for tests."""
    from chorm import create_engine

    host = os.getenv("CLICKHOUSE_HOST", "localhost")
    password = os.getenv("CLICKHOUSE_PASSWORD", "123")
    return create_engine(f"clickhouse://default:{password}@{host}:8123/default")


@pytest.fixture
def setup_tables(engine):
    """Setup test tables."""
    # Create source table
    engine.execute(SourceTable.create_table())

    # Create target table
    engine.execute(TargetTable.create_table())

    # Insert test data into source
    from datetime import date

    test_data = [
        {"id": 1, "name": "Alice", "value": 100, "date": date(2024, 1, 1)},
        {"id": 2, "name": "Bob", "value": 200, "date": date(2024, 1, 2)},
        {"id": 3, "name": "Charlie", "value": 300, "date": date(2024, 1, 3)},
        {"id": 1, "name": "Alice", "value": 100, "date": date(2024, 1, 1)},  # Duplicate
    ]

    stmt = insert(SourceTable).values(test_data)
    engine.execute(stmt.to_sql())

    yield

    # Cleanup
    engine.execute("DROP TABLE IF EXISTS perf_source_table")
    engine.execute("DROP TABLE IF EXISTS perf_target_table")


def test_optimize_table_basic(engine, setup_tables):
    """Test OPTIMIZE TABLE operation."""
    stmt = optimize_table(SourceTable)
    result = engine.execute(stmt.to_sql())
    assert result is not None


def test_optimize_table_final(engine, setup_tables):
    """Test OPTIMIZE TABLE FINAL (forces merge)."""
    stmt = optimize_table(SourceTable, final=True)
    result = engine.execute(stmt.to_sql())
    assert result is not None


def test_optimize_table_deduplicate(engine, setup_tables):
    """Test OPTIMIZE TABLE DEDUPLICATE."""
    stmt = optimize_table(SourceTable, deduplicate=True, final=True)
    # Just verify it executes without error
    engine.execute(stmt.to_sql())


def test_insert_from_select(engine, setup_tables):
    """Test INSERT FROM SELECT operation."""
    source_query = (
        select(SourceTable.id, SourceTable.name, SourceTable.value)
        .select_from(SourceTable)
        .where(SourceTable.value > 100)
    )

    stmt = insert(TargetTable).from_select(source_query)
    # Just verify it executes without error
    engine.execute(stmt.to_sql())


def test_insert_from_select_with_columns(engine, setup_tables):
    """Test INSERT FROM SELECT with explicit columns."""
    source_query = select(SourceTable.id, SourceTable.name, SourceTable.value).select_from(SourceTable).limit(2)

    stmt = insert(TargetTable).from_select(source_query, columns=["id", "name", "value"])

    result = engine.execute(stmt.to_sql())
    assert result is not None
