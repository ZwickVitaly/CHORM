"""Tests for enhanced ClickHouse index support."""

import pytest
from chorm import Table, Column
from chorm.types import UInt64, String, DateTime
from chorm.table_engines import MergeTree
from chorm.sql.ddl import add_index
from chorm.sql.expression import Identifier


class IndexTestTable(Table):
    __tablename__ = "index_test_table"
    __engine__ = MergeTree()
    __order_by__ = ["id"]

    id = Column(UInt64())
    email = Column(String())
    name = Column(String())
    country = Column(String())
    description = Column(String())
    created_at = Column(DateTime())


def test_minmax_index():
    """Test minmax index creation."""
    stmt = add_index(IndexTestTable, "idx_created", Identifier("created_at"), "minmax", granularity=1)
    sql = stmt.to_sql()

    assert "ALTER TABLE index_test_table ADD INDEX idx_created" in sql
    assert "TYPE minmax" in sql
    assert "GRANULARITY 1" in sql


def test_bloom_filter_default():
    """Test bloom_filter index with default parameters."""
    stmt = add_index(IndexTestTable, "idx_email", Identifier("email"), "bloom_filter", granularity=1)
    sql = stmt.to_sql()

    assert "TYPE bloom_filter" in sql
    assert "GRANULARITY 1" in sql


def test_bloom_filter_with_rate():
    """Test bloom_filter index with custom false positive rate."""
    stmt = add_index(IndexTestTable, "idx_email", Identifier("email"), "bloom_filter(0.01)", granularity=1)
    sql = stmt.to_sql()

    assert "TYPE bloom_filter(0.01)" in sql
    assert "GRANULARITY 1" in sql


def test_set_index_default():
    """Test set index without parameters."""
    stmt = add_index(IndexTestTable, "idx_country", Identifier("country"), "set", granularity=2)
    sql = stmt.to_sql()

    assert "TYPE set" in sql
    assert "GRANULARITY 2" in sql


def test_set_index_with_max_rows():
    """Test set index with max_rows parameter."""
    stmt = add_index(IndexTestTable, "idx_country", Identifier("country"), "set(100)", granularity=4)
    sql = stmt.to_sql()

    assert "TYPE set(100)" in sql
    assert "GRANULARITY 4" in sql


def test_tokenbf_v1_index():
    """Test tokenbf_v1 index for text search."""
    stmt = add_index(IndexTestTable, "idx_name", Identifier("name"), "tokenbf_v1(256, 3, 0)", granularity=1)
    sql = stmt.to_sql()

    assert "TYPE tokenbf_v1(256, 3, 0)" in sql
    assert "GRANULARITY 1" in sql


def test_ngrambf_v1_index():
    """Test ngrambf_v1 index for substring search."""
    stmt = add_index(IndexTestTable, "idx_desc", Identifier("description"), "ngrambf_v1(4, 512, 3, 0)", granularity=2)
    sql = stmt.to_sql()

    assert "TYPE ngrambf_v1(4, 512, 3, 0)" in sql
    assert "GRANULARITY 2" in sql


def test_index_if_not_exists():
    """Test IF NOT EXISTS clause."""
    stmt = add_index(
        IndexTestTable, "idx_email", Identifier("email"), "bloom_filter", granularity=1, if_not_exists=True
    )
    sql = stmt.to_sql()

    assert "IF NOT EXISTS" in sql


def test_index_with_settings():
    """Test index with SETTINGS clause."""
    stmt = add_index(
        IndexTestTable,
        "idx_email",
        Identifier("email"),
        "bloom_filter",
        granularity=1,
        replication_alter_partitions_sync=1,
    )
    sql = stmt.to_sql()

    assert "SETTINGS replication_alter_partitions_sync=1" in sql


def test_granularity_values():
    """Test different granularity values."""
    # Granularity 1 (most precise)
    stmt1 = add_index(IndexTestTable, "idx1", Identifier("id"), "minmax", granularity=1)
    assert "GRANULARITY 1" in stmt1.to_sql()

    # Granularity 4 (medium)
    stmt2 = add_index(IndexTestTable, "idx2", Identifier("country"), "set(100)", granularity=4)
    assert "GRANULARITY 4" in stmt2.to_sql()

    # Granularity 8 (less precise, smaller index)
    stmt3 = add_index(IndexTestTable, "idx3", Identifier("description"), "ngrambf_v1(4, 512, 3, 0)", granularity=8)
    assert "GRANULARITY 8" in stmt3.to_sql()

    # Granularity 16 (very large tables)
    stmt4 = add_index(IndexTestTable, "idx4", Identifier("name"), "tokenbf_v1(256, 3, 0)", granularity=16)
    assert "GRANULARITY 16" in stmt4.to_sql()


def test_index_on_expression():
    """Test index on expression (not just column)."""
    from chorm.sql.expression import func

    # Index on function result
    expr = func.lower(Identifier("email"))
    stmt = add_index(IndexTestTable, "idx_email_lower", expr, "bloom_filter", granularity=1)
    sql = stmt.to_sql()

    assert "lower(email)" in sql.lower()
    assert "TYPE bloom_filter" in sql


def test_multiple_indexes_scenario():
    """Test realistic scenario with multiple indexes."""
    # Small table: all granularity=1
    idx1 = add_index(IndexTestTable, "idx_email", Identifier("email"), "bloom_filter", granularity=1)
    idx2 = add_index(IndexTestTable, "idx_created", Identifier("created_at"), "minmax", granularity=1)

    assert "GRANULARITY 1" in idx1.to_sql()
    assert "GRANULARITY 1" in idx2.to_sql()

    # Large table: varied granularity
    idx3 = add_index(IndexTestTable, "idx_country", Identifier("country"), "set(200)", granularity=4)
    idx4 = add_index(
        IndexTestTable, "idx_desc_ngrams", Identifier("description"), "ngrambf_v1(4, 1024, 3, 0)", granularity=8
    )

    assert "GRANULARITY 4" in idx3.to_sql()
    assert "GRANULARITY 8" in idx4.to_sql()
