"""Tests for partition operations."""

import pytest
from chorm import (
    detach_partition,
    attach_partition,
    drop_partition,
    fetch_partition,
)


def test_detach_partition():
    """Test DETACH PARTITION."""
    stmt = detach_partition("my_table", "202301")
    assert stmt.to_sql() == "ALTER TABLE my_table DETACH PARTITION '202301'"

    stmt_int = detach_partition("my_table", 202301)
    assert stmt_int.to_sql() == "ALTER TABLE my_table DETACH PARTITION 202301"


def test_attach_partition():
    """Test ATTACH PARTITION."""
    stmt = attach_partition("my_table", "202301")
    assert stmt.to_sql() == "ALTER TABLE my_table ATTACH PARTITION '202301'"


def test_drop_partition():
    """Test DROP PARTITION."""
    stmt = drop_partition("my_table", "202301")
    assert stmt.to_sql() == "ALTER TABLE my_table DROP PARTITION '202301'"

    stmt_settings = drop_partition("my_table", "202301", replication_alter_partitions_sync=2)
    assert "SETTINGS replication_alter_partitions_sync=2" in stmt_settings.to_sql()


def test_fetch_partition():
    """Test FETCH PARTITION."""
    stmt = fetch_partition("my_table", "202301", "/clickhouse/tables/shard2/table")
    assert stmt.to_sql() == "ALTER TABLE my_table FETCH PARTITION '202301' FROM '/clickhouse/tables/shard2/table'"
