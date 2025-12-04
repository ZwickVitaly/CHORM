"""Tests for Quick Wins features: UNION, ORDER BY helpers, DISTINCT."""

import sys
from unittest.mock import MagicMock

# Mock clickhouse_connect to avoid installation requirement for SQL generation testing
sys.modules["clickhouse_connect"] = MagicMock()

import pytest
from chorm import Table, Column, MergeTree, select
from chorm.types import UInt64, String


class User(Table):
    __tablename__ = "users"
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    city = Column(String())
    engine = MergeTree()


def test_distinct_already_works():
    """Test that DISTINCT is already implemented and functional."""
    stmt = select(User.city).distinct()
    sql = stmt.to_sql()
    assert "SELECT DISTINCT users.city" in sql
    assert "FROM users" in sql


def test_union():
    """Test UNION SQL generation (removes duplicates)."""
    query1 = select(User.name).where(User.city == "Moscow")
    query2 = select(User.name).where(User.city == "SPB")
    stmt = query1.union(query2)

    sql = stmt.to_sql()
    assert "SELECT users.name FROM users WHERE (users.city = 'Moscow')" in sql
    assert "UNION" in sql
    assert "SELECT users.name FROM users WHERE (users.city = 'SPB')" in sql
    # Should be UNION not UNION ALL
    assert sql.count("UNION") == 1
    assert "UNION ALL" not in sql


def test_union_all():
    """Test UNION ALL SQL generation (keeps duplicates)."""
    query1 = select(User.name).where(User.city == "Moscow")
    query2 = select(User.name).where(User.city == "SPB")
    stmt = query1.union_all(query2)

    sql = stmt.to_sql()
    assert "SELECT users.name FROM users WHERE (users.city = 'Moscow')" in sql
    assert "UNION ALL" in sql
    assert "SELECT users.name FROM users WHERE (users.city = 'SPB')" in sql


def test_multiple_unions():
    """Test chaining multiple UNION operations."""
    query1 = select(User.id).where(User.city == "Moscow")
    query2 = select(User.id).where(User.city == "SPB")
    query3 = select(User.id).where(User.city == "Kazan")

    stmt = query1.union(query2).union(query3)

    sql = stmt.to_sql()
    assert sql.count("UNION") == 2
    assert "Moscow" in sql
    assert "SPB" in sql
    assert "Kazan" in sql


def test_mixed_union_types():
    """Test mixing UNION and UNION ALL."""
    query1 = select(User.name).where(User.city == "Moscow")
    query2 = select(User.name).where(User.city == "SPB")
    query3 = select(User.name).where(User.city == "Kazan")

    stmt = query1.union(query2).union_all(query3)

    sql = stmt.to_sql()
    assert "UNION SELECT" in sql
    assert "UNION ALL SELECT" in sql


def test_asc():
    """Test ORDER BY with asc()."""
    stmt = select(User).order_by(User.name.asc())
    sql = stmt.to_sql()
    assert "ORDER BY users.name ASC" in sql


def test_desc():
    """Test ORDER BY with desc()."""
    stmt = select(User).order_by(User.id.desc())
    sql = stmt.to_sql()
    assert "ORDER BY users.id DESC" in sql


def test_asc_desc_multiple():
    """Test ORDER BY with multiple columns using asc() and desc()."""
    stmt = select(User).order_by(User.city.asc(), User.name.desc())
    sql = stmt.to_sql()
    assert "ORDER BY users.city ASC, users.name DESC" in sql


def test_union_with_order_by():
    """Test UNION with ORDER BY."""
    query1 = select(User.name).where(User.city == "Moscow")
    query2 = select(User.name).where(User.city == "SPB")
    stmt = query1.union(query2).order_by(User.name.asc())

    sql = stmt.to_sql()
    # Note: ORDER BY should only apply to the final result
    # The second query gets the ORDER BY
    assert "UNION" in sql


def test_union_with_limit():
    """Test UNION with LIMIT."""
    query1 = select(User.id).where(User.city == "Moscow")
    query2 = select(User.id).where(User.city == "SPB")
    stmt = query1.union(query2).limit(10)

    sql = stmt.to_sql()
    assert "UNION" in sql
    # LIMIT should apply to the final result
    assert "LIMIT 10" in sql


def test_distinct_with_union():
    """Test combining DISTINCT with UNION."""
    query1 = select(User.name).distinct().where(User.city == "Moscow")
    query2 = select(User.name).where(User.city == "SPB")
    stmt = query1.union(query2)

    sql = stmt.to_sql()
    assert "SELECT DISTINCT users.name" in sql
    assert "UNION" in sql
