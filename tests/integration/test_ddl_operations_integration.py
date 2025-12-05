"""Integration tests for DDL operations with live ClickHouse."""

import os
import pytest
from chorm import Table, Column, Session, create_engine
from chorm.types import UInt64, String, UInt8
from chorm.table_engines import MergeTree
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
from chorm.sql.expression import Identifier


class DDLTestUser(Table):
    __tablename__ = "ddl_test_users"

    id = Column(UInt64(), primary_key=True)
    name = Column(String())

    engine = MergeTree()
    __order_by__ = "id"


@pytest.fixture
def engine():
    """Create a test engine."""
    password = os.getenv("CLICKHOUSE_PASSWORD", "123")
    return create_engine("clickhouse://localhost:8123/default", username="default", password=password)


@pytest.fixture
def session(engine):
    """Create a test session."""
    return Session(engine)


@pytest.fixture(autouse=True)
def cleanup(session):
    """Clean up test tables before and after each test."""
    # Cleanup before test
    try:
        session.execute("DROP TABLE IF EXISTS ddl_test_users")
        session.execute("DROP TABLE IF EXISTS ddl_test_users_renamed")
    except:
        pass

    yield

    # Cleanup after test
    try:
        session.execute("DROP TABLE IF EXISTS ddl_test_users")
        session.execute("DROP TABLE IF EXISTS ddl_test_users_renamed")
    except:
        pass


def test_drop_table_integration(session):
    """Test DROP TABLE with live ClickHouse."""
    # Create table
    create_sql = DDLTestUser.create_table(exists_ok=True)
    session.execute(create_sql)

    # Verify table exists
    result = session.execute("SHOW TABLES LIKE 'ddl_test_users'")
    tables = [row[0] for row in result.all()]
    assert "ddl_test_users" in tables

    # Drop table
    stmt = drop_table(DDLTestUser)
    session.execute(stmt.to_sql())

    # Verify table is gone
    result = session.execute("SHOW TABLES LIKE 'ddl_test_users'")
    tables = [row[0] for row in result.all()]
    assert "ddl_test_users" not in tables


def test_truncate_table_integration(session):
    """Test TRUNCATE TABLE with live ClickHouse."""
    # Create table and insert data
    create_sql = DDLTestUser.create_table(exists_ok=True)
    session.execute(create_sql)
    session.execute("INSERT INTO ddl_test_users VALUES (1, 'Alice'), (2, 'Bob')")

    # Verify data exists
    result = session.execute("SELECT count() FROM ddl_test_users")
    count = result.all()[0][0]
    assert count == 2

    # Truncate table
    stmt = truncate_table(DDLTestUser)
    session.execute(stmt.to_sql())

    # Verify table is empty
    result = session.execute("SELECT count() FROM ddl_test_users")
    count = result.all()[0][0]
    assert count == 0


def test_rename_table_integration(session):
    """Test RENAME TABLE with live ClickHouse."""
    # Create table
    create_sql = DDLTestUser.create_table(exists_ok=True)
    session.execute(create_sql)

    # Rename table
    stmt = rename_table("ddl_test_users", "ddl_test_users_renamed")
    session.execute(stmt.to_sql())

    # Verify old name is gone
    result = session.execute("SHOW TABLES LIKE 'ddl_test_users'")
    tables = [row[0] for row in result.all()]
    assert "ddl_test_users" not in tables

    # Verify new name exists
    result = session.execute("SHOW TABLES LIKE 'ddl_test_users_renamed'")
    tables = [row[0] for row in result.all()]
    assert "ddl_test_users_renamed" in tables


def test_add_column_integration(session):
    """Test ADD COLUMN with live ClickHouse."""
    # Create table
    create_sql = DDLTestUser.create_table(exists_ok=True)
    session.execute(create_sql)

    # Add column
    stmt = add_column(DDLTestUser, "age UInt8", after="name")
    session.execute(stmt.to_sql())

    # Verify column exists
    result = session.execute("DESCRIBE TABLE ddl_test_users")
    columns = {row[0]: row[1] for row in result.all()}
    assert "age" in columns
    assert "UInt8" in columns["age"]


def test_drop_column_integration(session):
    """Test DROP COLUMN with live ClickHouse."""
    # Create table with extra column
    create_sql = DDLTestUser.create_table(exists_ok=True)
    session.execute(create_sql)
    session.execute("ALTER TABLE ddl_test_users ADD COLUMN temp_field String")

    # Verify column exists
    result = session.execute("DESCRIBE TABLE ddl_test_users")
    columns = [row[0] for row in result.all()]
    assert "temp_field" in columns

    # Drop column
    stmt = drop_column(DDLTestUser, "temp_field")
    session.execute(stmt.to_sql())

    # Verify column is gone
    result = session.execute("DESCRIBE TABLE ddl_test_users")
    columns = [row[0] for row in result.all()]
    assert "temp_field" not in columns


def test_modify_column_integration(session):
    """Test MODIFY COLUMN with live ClickHouse."""
    # Create table
    create_sql = DDLTestUser.create_table(exists_ok=True)
    session.execute(create_sql)
    session.execute("ALTER TABLE ddl_test_users ADD COLUMN age UInt8")

    # Modify column type
    stmt = modify_column(DDLTestUser, "age UInt16")
    session.execute(stmt.to_sql())

    # Verify column type changed
    result = session.execute("DESCRIBE TABLE ddl_test_users")
    columns = {row[0]: row[1] for row in result.all()}
    assert "age" in columns
    assert "UInt16" in columns["age"]


def test_rename_column_integration(session):
    """Test RENAME COLUMN with live ClickHouse."""
    # Create table with extra column
    create_sql = DDLTestUser.create_table(exists_ok=True)
    session.execute(create_sql)
    session.execute("ALTER TABLE ddl_test_users ADD COLUMN old_name String")

    # Rename column
    stmt = rename_column(DDLTestUser, "old_name", "new_name")
    session.execute(stmt.to_sql())

    # Verify old name is gone and new name exists
    result = session.execute("DESCRIBE TABLE ddl_test_users")
    columns = [row[0] for row in result.all()]
    assert "old_name" not in columns
    assert "new_name" in columns


def test_add_drop_index_integration(session):
    """Test ADD INDEX and DROP INDEX with live ClickHouse."""
    # Create table
    create_sql = DDLTestUser.create_table(exists_ok=True)
    session.execute(create_sql)

    # Add index
    stmt = add_index(DDLTestUser, "idx_name", Identifier("name"), index_type="minmax")
    session.execute(stmt.to_sql())

    # Verify index exists (check SHOW CREATE TABLE)
    result = session.execute("SHOW CREATE TABLE ddl_test_users")
    rows = result.all()
    assert len(rows) > 0
    create_sql = rows[0][0]
    assert "idx_name" in create_sql

    # Drop index
    stmt = drop_index(DDLTestUser, "idx_name")
    session.execute(stmt.to_sql())

    # Verify index is gone
    result = session.execute("SHOW CREATE TABLE ddl_test_users")
    create_sql = result.all()[0][0]
    assert "idx_name" not in create_sql
