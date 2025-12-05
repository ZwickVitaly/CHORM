import sys
from unittest.mock import MagicMock

# Mock clickhouse_connect to avoid installation requirement for SQL generation testing
sys.modules["clickhouse_connect"] = MagicMock()

import pytest
from chorm import Table, Column, MergeTree, select, insert, update, delete
from chorm.types import UInt64, String


class User(Table):
    __tablename__ = "users"
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    engine = MergeTree()


def test_select():
    stmt = select(User.id, User.name).where(User.id > 10).order_by(User.name).limit(5)
    sql = stmt.to_sql()
    assert "SELECT users.id, users.name FROM users" in sql
    assert "WHERE (users.id > 10)" in sql
    assert "ORDER BY users.name" in sql
    assert "LIMIT 5" in sql


def test_insert():
    stmt = insert(User).values(id=1, name="Alice")
    sql = stmt.to_sql()
    assert "INSERT INTO users (id, name) VALUES (1, 'Alice')" in sql


def test_update():
    stmt = update(User).where(User.id == 1).values(name="Bob")
    sql = stmt.to_sql()
    assert "ALTER TABLE users UPDATE" in sql
    # ClickHouse ALTER TABLE UPDATE doesn't support table-qualified column names
    assert "WHERE (id = 1)" in sql


def test_delete():
    stmt = delete(User).where(User.id == 1)
    sql = stmt.to_sql()
    # ClickHouse ALTER TABLE DELETE doesn't support table-qualified column names
    assert "ALTER TABLE users DELETE WHERE (id = 1)" in sql
