"""Tests for Set Operations (UNION, INTERSECT, EXCEPT)."""

from chorm import select
from chorm.sql.expression import Identifier, Literal


def test_union():
    """Test UNION generation."""
    q1 = select(1)
    q2 = select(2)
    stmt = q1.union(q2)
    assert stmt.to_sql() == "SELECT 1 UNION SELECT 2"


def test_union_all():
    """Test UNION ALL generation."""
    q1 = select(1)
    q2 = select(2)
    stmt = q1.union_all(q2)
    assert stmt.to_sql() == "SELECT 1 UNION ALL SELECT 2"


def test_intersect():
    """Test INTERSECT generation."""
    q1 = select(1)
    q2 = select(1)
    stmt = q1.intersect(q2)
    assert stmt.to_sql() == "SELECT 1 INTERSECT SELECT 1"


def test_except():
    """Test EXCEPT generation."""
    q1 = select(1)
    q2 = select(2)
    stmt = q1.except_(q2)
    assert stmt.to_sql() == "SELECT 1 EXCEPT SELECT 2"


def test_chained_set_ops():
    """Test chained set operations."""
    q1 = select(1)
    q2 = select(2)
    q3 = select(3)
    stmt = q1.union(q2).except_(q3)
    assert stmt.to_sql() == "SELECT 1 UNION SELECT 2 EXCEPT SELECT 3"
