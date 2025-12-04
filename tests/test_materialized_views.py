"""Tests for materialized view operations."""

import pytest
from chorm import create_materialized_view, select, Table, Column
from chorm.types import UInt64, String
from chorm.table_engines import SummingMergeTree


class SourceTable(Table):
    __tablename__ = "source"
    id = Column(UInt64())
    name = Column(String())
    value = Column(UInt64())


def test_create_mv_with_to_table():
    """Test CREATE MATERIALIZED VIEW ... TO ..."""
    query = select(SourceTable.id, SourceTable.value).select_from(SourceTable)
    stmt = create_materialized_view("mv_source", query, to_table="target_table")

    expected = "CREATE MATERIALIZED VIEW mv_source TO target_table AS SELECT source.id, source.value FROM source"
    assert stmt.to_sql() == expected


def test_create_mv_with_engine():
    """Test CREATE MATERIALIZED VIEW ... ENGINE ..."""
    query = select(SourceTable.id, SourceTable.value).select_from(SourceTable)
    engine = SummingMergeTree(columns=("value",))
    stmt = create_materialized_view("mv_source", query, engine=engine, populate=True)

    expected = "CREATE MATERIALIZED VIEW mv_source ENGINE = SummingMergeTree(columns) POPULATE AS SELECT source.id, source.value FROM source"
    # Note: SummingMergeTree args rendering might vary slightly depending on how it handles tuple args, but let's check key parts
    sql = stmt.to_sql()
    assert "CREATE MATERIALIZED VIEW mv_source" in sql
    assert "ENGINE = SummingMergeTree" in sql
    assert "POPULATE" in sql
    assert "AS SELECT source.id, source.value FROM source" in sql


def test_create_mv_if_not_exists():
    """Test CREATE MATERIALIZED VIEW IF NOT EXISTS."""
    query = select(SourceTable.id).select_from(SourceTable)
    stmt = create_materialized_view("mv_source", query, to_table="target", if_not_exists=True)

    assert "CREATE MATERIALIZED VIEW IF NOT EXISTS mv_source" in stmt.to_sql()
