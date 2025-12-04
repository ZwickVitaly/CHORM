"""Unit tests for LIMIT BY functionality."""

from chorm import select, Table, Column, MergeTree
from chorm.types import UInt64, String
from chorm.sql.expression import Identifier


class User(Table):
    __tablename__ = "users"
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    city = Column(String())
    engine = MergeTree()


def test_simple_limit_by():
    """Test simple LIMIT BY clause."""
    stmt = select(User.name, User.city).select_from(User).limit_by(5, User.city)
    sql = stmt.to_sql()
    assert "LIMIT 5 BY users.city" in sql


def test_limit_by_multiple_columns():
    """Test LIMIT BY with multiple columns."""
    stmt = select(User.name).select_from(User).limit_by(5, User.city, User.name)
    sql = stmt.to_sql()
    assert "LIMIT 5 BY users.city, users.name" in sql


def test_limit_by_with_offset():
    """Test LIMIT BY with offset."""
    stmt = select(User.name).select_from(User).limit_by(5, User.city, offset=2)
    sql = stmt.to_sql()
    assert "LIMIT 5 OFFSET 2 BY users.city" in sql


def test_limit_by_ordering():
    """Test LIMIT BY position in SQL (after LIMIT, before OFFSET/SETTINGS)."""
    stmt = select(User.name).select_from(User).limit(100).limit_by(5, User.city).offset(10)
    sql = stmt.to_sql()
    # Order: LIMIT N -> LIMIT N BY ... -> OFFSET N
    assert "LIMIT 100" in sql
    assert "LIMIT 5 BY users.city" in sql
    assert "OFFSET 10" in sql

    limit_idx = sql.index("LIMIT 100")
    limit_by_idx = sql.index("LIMIT 5 BY")
    offset_idx = sql.index("OFFSET 10")

    assert limit_idx < limit_by_idx < offset_idx
