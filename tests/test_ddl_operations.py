"""Unit tests for DDL operations SQL generation."""

from chorm import Column, Table
from chorm.sql.ddl import (
    drop_table,
    truncate_table,
    rename_table,
    add_column,
    drop_column,
    modify_column,
    rename_column,
    add_index,
    drop_index,
)
from chorm.types import String, UInt64, UInt8
from chorm.table_engines import MergeTree


class DDLTestTable(Table):
    __tablename__ = "test_table"

    id = Column(UInt64(), primary_key=True)
    name = Column(String())

    engine = MergeTree()


def test_drop_table_basic():
    """Test basic DROP TABLE statement."""
    stmt = drop_table(DDLTestTable)
    sql = stmt.to_sql()

    assert sql == "DROP TABLE IF EXISTS test_table"


def test_drop_table_without_if_exists():
    """Test DROP TABLE without IF EXISTS."""
    stmt = drop_table(DDLTestTable, if_exists=False)
    sql = stmt.to_sql()

    assert sql == "DROP TABLE test_table"


def test_drop_table_with_settings():
    """Test DROP TABLE with SETTINGS."""
    stmt = drop_table(DDLTestTable, max_threads=4)
    sql = stmt.to_sql()

    assert "DROP TABLE IF EXISTS test_table" in sql
    assert "SETTINGS max_threads=4" in sql


def test_drop_table_string_name():
    """Test DROP TABLE with string table name."""
    stmt = drop_table("my_table")
    sql = stmt.to_sql()

    assert sql == "DROP TABLE IF EXISTS my_table"


def test_truncate_table_basic():
    """Test basic TRUNCATE TABLE statement."""
    stmt = truncate_table(DDLTestTable)
    sql = stmt.to_sql()

    assert sql == "TRUNCATE TABLE test_table"


def test_truncate_table_if_exists():
    """Test TRUNCATE TABLE with IF EXISTS."""
    stmt = truncate_table(DDLTestTable, if_exists=True)
    sql = stmt.to_sql()

    assert sql == "TRUNCATE TABLE IF EXISTS test_table"


def test_truncate_table_with_settings():
    """Test TRUNCATE TABLE with SETTINGS."""
    stmt = truncate_table(DDLTestTable, max_threads=2)
    sql = stmt.to_sql()

    assert "TRUNCATE TABLE test_table" in sql
    assert "SETTINGS max_threads=2" in sql


def test_rename_table_basic():
    """Test basic RENAME TABLE statement."""
    stmt = rename_table(DDLTestTable, "new_table_name")
    sql = stmt.to_sql()

    assert sql == "RENAME TABLE test_table TO new_table_name"


def test_rename_table_string_names():
    """Test RENAME TABLE with string names."""
    stmt = rename_table("old_name", "new_name")
    sql = stmt.to_sql()

    assert sql == "RENAME TABLE old_name TO new_name"


def test_add_column_basic():
    """Test basic ALTER TABLE ADD COLUMN."""
    stmt = add_column(DDLTestTable, "age UInt8")
    sql = stmt.to_sql()

    assert "ALTER TABLE test_table ADD COLUMN" in sql
    assert "age UInt8" in sql


def test_add_column_if_not_exists():
    """Test ADD COLUMN with IF NOT EXISTS."""
    stmt = add_column(DDLTestTable, "email String", if_not_exists=True)
    sql = stmt.to_sql()

    assert "ADD COLUMN IF NOT EXISTS" in sql
    assert "email String" in sql


def test_add_column_after():
    """Test ADD COLUMN with AFTER clause."""
    stmt = add_column(DDLTestTable, "age UInt8", after="name")
    sql = stmt.to_sql()

    assert "age UInt8 AFTER name" in sql


def test_add_column_first():
    """Test ADD COLUMN with FIRST clause."""
    stmt = add_column(DDLTestTable, "new_id UInt64", first=True)
    sql = stmt.to_sql()

    assert "new_id UInt64 FIRST" in sql


def test_add_column_with_default():
    """Test ADD COLUMN with DEFAULT value."""
    stmt = add_column(DDLTestTable, "status String DEFAULT 'active'")
    sql = stmt.to_sql()

    assert "status String DEFAULT 'active'" in sql


def test_add_column_with_settings():
    """Test ADD COLUMN with SETTINGS."""
    stmt = add_column(DDLTestTable, "age UInt8", replication_alter_partitions_sync=2)
    sql = stmt.to_sql()

    assert "SETTINGS replication_alter_partitions_sync=2" in sql


def test_drop_column_basic():
    """Test basic ALTER TABLE DROP COLUMN."""
    stmt = drop_column(DDLTestTable, "old_field")
    sql = stmt.to_sql()

    assert sql == "ALTER TABLE test_table DROP COLUMN IF EXISTS old_field"


def test_drop_column_without_if_exists():
    """Test DROP COLUMN without IF EXISTS."""
    stmt = drop_column(DDLTestTable, "old_field", if_exists=False)
    sql = stmt.to_sql()

    assert sql == "ALTER TABLE test_table DROP COLUMN old_field"


def test_drop_column_with_settings():
    """Test DROP COLUMN with SETTINGS."""
    stmt = drop_column(DDLTestTable, "old_field", replication_alter_partitions_sync=1)
    sql = stmt.to_sql()

    assert "DROP COLUMN IF EXISTS old_field" in sql
    assert "SETTINGS replication_alter_partitions_sync=1" in sql


def test_modify_column_basic():
    """Test basic ALTER TABLE MODIFY COLUMN."""
    stmt = modify_column(DDLTestTable, "name String")
    sql = stmt.to_sql()

    assert "ALTER TABLE test_table MODIFY COLUMN IF EXISTS name String" in sql


def test_modify_column_without_if_exists():
    """Test MODIFY COLUMN without IF EXISTS."""
    stmt = modify_column(DDLTestTable, "id UInt64", if_exists=False)
    sql = stmt.to_sql()

    assert "ALTER TABLE test_table MODIFY COLUMN id UInt64" in sql


def test_modify_column_with_default():
    """Test MODIFY COLUMN with DEFAULT value."""
    stmt = modify_column(DDLTestTable, "age UInt8 DEFAULT 0")
    sql = stmt.to_sql()

    assert "age UInt8 DEFAULT 0" in sql


def test_rename_column_basic():
    """Test basic ALTER TABLE RENAME COLUMN."""
    stmt = rename_column(DDLTestTable, "old_name", "new_name")
    sql = stmt.to_sql()

    assert sql == "ALTER TABLE test_table RENAME COLUMN IF EXISTS old_name TO new_name"


def test_rename_column_without_if_exists():
    """Test RENAME COLUMN without IF EXISTS."""
    stmt = rename_column(DDLTestTable, "old_name", "new_name", if_exists=False)
    sql = stmt.to_sql()

    assert sql == "ALTER TABLE test_table RENAME COLUMN old_name TO new_name"


def test_rename_column_with_settings():
    """Test RENAME COLUMN with SETTINGS."""
    stmt = rename_column(DDLTestTable, "old_name", "new_name", replication_alter_partitions_sync=2)
    sql = stmt.to_sql()

    assert "RENAME COLUMN IF EXISTS old_name TO new_name" in sql
    assert "SETTINGS replication_alter_partitions_sync=2" in sql


def test_add_index_basic():
    """Test basic ALTER TABLE ADD INDEX."""
    from chorm.sql.expression import Identifier

    stmt = add_index(DDLTestTable, "idx_name", Identifier("name"))
    sql = stmt.to_sql()

    assert "ALTER TABLE test_table ADD INDEX idx_name name TYPE minmax GRANULARITY 1" in sql


def test_add_index_if_not_exists():
    """Test ADD INDEX with IF NOT EXISTS."""
    from chorm.sql.expression import Identifier

    stmt = add_index(DDLTestTable, "idx_name", Identifier("name"), if_not_exists=True)
    sql = stmt.to_sql()

    assert "ADD INDEX IF NOT EXISTS idx_name" in sql


def test_add_index_bloom_filter():
    """Test ADD INDEX with bloom_filter type."""
    from chorm.sql.expression import Identifier

    stmt = add_index(DDLTestTable, "idx_name", Identifier("name"), index_type="bloom_filter", granularity=4)
    sql = stmt.to_sql()

    assert "TYPE bloom_filter GRANULARITY 4" in sql


def test_add_index_with_settings():
    """Test ADD INDEX with SETTINGS."""
    from chorm.sql.expression import Identifier

    stmt = add_index(DDLTestTable, "idx_name", Identifier("name"), replication_alter_partitions_sync=1)
    sql = stmt.to_sql()

    assert "SETTINGS replication_alter_partitions_sync=1" in sql


def test_drop_index_basic():
    """Test basic ALTER TABLE DROP INDEX."""
    stmt = drop_index(DDLTestTable, "idx_name")
    sql = stmt.to_sql()

    assert sql == "ALTER TABLE test_table DROP INDEX IF EXISTS idx_name"


def test_drop_index_without_if_exists():
    """Test DROP INDEX without IF EXISTS."""
    stmt = drop_index(DDLTestTable, "idx_name", if_exists=False)
    sql = stmt.to_sql()

    assert sql == "ALTER TABLE test_table DROP INDEX idx_name"


def test_drop_index_with_settings():
    """Test DROP INDEX with SETTINGS."""
    stmt = drop_index(DDLTestTable, "idx_name", replication_alter_partitions_sync=2)
    sql = stmt.to_sql()

    assert "DROP INDEX IF EXISTS idx_name" in sql
    assert "SETTINGS replication_alter_partitions_sync=2" in sql
