"""Tests for table-level granularity settings."""

import pytest
from chorm import Table, Column
from chorm.types import UInt64, String, DateTime
from chorm.table_engines import MergeTree, ReplacingMergeTree, SummingMergeTree


def test_index_granularity_default():
    """Test MergeTree without granularity settings (uses ClickHouse default 8192)."""

    class TestTable(Table):
        __tablename__ = "test_default"
        __engine__ = MergeTree()
        __order_by__ = ["id"]

        id = Column(UInt64())

    sql = TestTable.create_table()
    # Should not have SETTINGS clause
    assert "SETTINGS" not in sql


def test_index_granularity_custom():
    """Test custom index_granularity setting."""

    class TestTable(Table):
        __tablename__ = "test_custom_granularity"
        __engine__ = MergeTree(settings={"index_granularity": 4096})
        __order_by__ = ["id"]

        id = Column(UInt64())
        name = Column(String())

    sql = TestTable.create_table()
    assert "SETTINGS index_granularity = 4096" in sql


def test_index_granularity_bytes():
    """Test index_granularity_bytes setting."""

    class TestTable(Table):
        __tablename__ = "test_granularity_bytes"
        __engine__ = MergeTree(settings={"index_granularity_bytes": 20971520})  # 20MB
        __order_by__ = ["id"]

        id = Column(UInt64())

    sql = TestTable.create_table()
    assert "SETTINGS index_granularity_bytes = 20971520" in sql


def test_multiple_settings():
    """Test multiple granularity settings together."""

    class TestTable(Table):
        __tablename__ = "test_multiple_settings"
        __engine__ = MergeTree(
            settings={
                "index_granularity": 4096,
                "index_granularity_bytes": 10485760,  # 10MB
                "enable_mixed_granularity_parts": 1,
            }
        )
        __order_by__ = ["id"]

        id = Column(UInt64())

    sql = TestTable.create_table()
    assert "SETTINGS" in sql
    assert "index_granularity = 4096" in sql
    assert "index_granularity_bytes = 10485760" in sql
    assert "enable_mixed_granularity_parts = 1" in sql


def test_replacing_mergetree_with_granularity():
    """Test ReplacingMergeTree with custom granularity."""

    class TestTable(Table):
        __tablename__ = "test_replacing"
        __engine__ = ReplacingMergeTree(version_column="version", settings={"index_granularity": 2048})
        __order_by__ = ["id"]

        id = Column(UInt64())
        version = Column(UInt64())

    sql = TestTable.create_table()
    assert "ReplacingMergeTree(version)" in sql
    assert "SETTINGS index_granularity = 2048" in sql


def test_summing_mergetree_with_granularity():
    """Test SummingMergeTree with custom granularity."""

    class TestTable(Table):
        __tablename__ = "test_summing"
        __engine__ = SummingMergeTree(columns=("value",), settings={"index_granularity": 16384})
        __order_by__ = ["id"]

        id = Column(UInt64())
        value = Column(UInt64())

    sql = TestTable.create_table()
    assert "SummingMergeTree" in sql
    assert "SETTINGS index_granularity = 16384" in sql


def test_granularity_scenarios():
    """Test realistic granularity scenarios for different table sizes."""

    # Small table (< 1M rows): default granularity
    class SmallTable(Table):
        __tablename__ = "small_table"
        __engine__ = MergeTree()
        __order_by__ = ["id"]
        id = Column(UInt64())

    assert "SETTINGS" not in SmallTable.create_table()

    # Medium table (1M-100M rows): slightly larger granularity
    class MediumTable(Table):
        __tablename__ = "medium_table"
        __engine__ = MergeTree(settings={"index_granularity": 16384})
        __order_by__ = ["id"]
        id = Column(UInt64())

    assert "index_granularity = 16384" in MediumTable.create_table()

    # Large table (>100M rows): larger granularity for smaller index
    class LargeTable(Table):
        __tablename__ = "large_table"
        __engine__ = MergeTree(settings={"index_granularity": 32768})
        __order_by__ = ["id"]
        id = Column(UInt64())

    assert "index_granularity = 32768" in LargeTable.create_table()


def test_granularity_with_ttl():
    """Test granularity settings combined with TTL."""

    class TestTable(Table):
        __tablename__ = "test_ttl_granularity"
        __engine__ = MergeTree(ttl="created_at + INTERVAL 30 DAY", settings={"index_granularity": 4096})
        __order_by__ = ["id"]

        id = Column(UInt64())
        created_at = Column(DateTime())

    sql = TestTable.create_table()
    assert "TTL created_at + INTERVAL 30 DAY" in sql
    assert "SETTINGS index_granularity = 4096" in sql
