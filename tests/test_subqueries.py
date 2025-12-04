"""Tests for Subqueries functionality."""

import sys
from unittest.mock import MagicMock

# Mock clickhouse_connect
sys.modules["clickhouse_connect"] = MagicMock()

import pytest
from chorm import Table, Column, MergeTree, select
from chorm.types import UInt64, String
from chorm.sql.expression import func, exists, Identifier


class User(Table):
    __tablename__ = "users"
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    city = Column(String())
    engine = MergeTree()


class Order(Table):
    __tablename__ = "orders"
    id = Column(UInt64(), primary_key=True)
    user_id = Column(UInt64())
    amount = Column(UInt64())
    engine = MergeTree()


def test_subquery_in_where_in():
    """Test IN clause with subquery."""
    subq = select(Order.user_id).where(Order.amount > 100).subquery()
    stmt = select(User.name).where(User.id.in_(subq))

    sql = stmt.to_sql()
    assert (
        "SELECT users.name FROM users WHERE (users.id IN (SELECT orders.user_id FROM orders WHERE (orders.amount > 100)))"
        in sql
    )


def test_subquery_exists():
    """Test EXISTS clause with subquery."""
    subq = select(Order.id).where(Order.user_id == User.id)
    stmt = select(User.name).where(exists(subq))

    sql = stmt.to_sql()
    # exists() adds parens, and Select.to_sql() renders SELECT ...
    # So we get exists(SELECT ...) which corresponds to EXISTS (SELECT ...)
    assert (
        "SELECT users.name FROM users WHERE exists(SELECT orders.id FROM orders WHERE (orders.user_id = users.id))"
        in sql
    )


def test_subquery_in_from():
    """Test subquery in FROM clause."""
    subq = select(User.name, User.city).where(User.city == "Moscow").subquery("moscow_users")

    # We can't easily reference columns of the subquery yet without raw strings or Identifiers
    # But we can verify the FROM clause generation
    stmt = select(Identifier("*")).select_from(subq)

    sql = stmt.to_sql()
    assert "FROM (SELECT users.name, users.city FROM users WHERE (users.city = 'Moscow')) AS moscow_users" in sql


def test_scalar_subquery_in_select():
    """Test scalar subquery in SELECT list."""
    # Need explicit select_from because inference doesn't work through function calls yet
    subq = (
        select(func.count(Order.id))
        .select_from(Order)
        .where(Order.user_id == User.id)
        .scalar_subquery()
        .label("order_count")
    )
    stmt = select(User.name, subq).select_from(User)

    sql = stmt.to_sql()
    assert (
        "SELECT users.name, (SELECT count(orders.id) FROM orders WHERE (orders.user_id = users.id)) AS order_count FROM users"
        in sql
    )


def test_scalar_subquery_comparison():
    """Test comparison with scalar subquery."""
    # Need explicit select_from
    avg_amount = select(func.avg(Order.amount)).select_from(Order).scalar_subquery()
    stmt = select(Order.id).select_from(Order).where(Order.amount > avg_amount)

    sql = stmt.to_sql()
    assert "SELECT orders.id FROM orders WHERE (orders.amount > (SELECT avg(orders.amount) FROM orders))" in sql


def test_nested_subqueries():
    """Test subquery within subquery."""
    inner_subq = select(Order.user_id).where(Order.amount > 1000).subquery()
    outer_subq = select(User.id).where(User.id.in_(inner_subq)).subquery()
    stmt = select(User.name).where(User.id.in_(outer_subq))

    sql = stmt.to_sql()
    assert (
        "IN (SELECT users.id FROM users WHERE (users.id IN (SELECT orders.user_id FROM orders WHERE (orders.amount > 1000))))"
        in sql
    )


def test_subquery_alias():
    """Test subquery with alias."""
    subq = select(User.name).subquery("u")
    assert subq.to_sql() == "(SELECT users.name FROM users) AS u"

    subq_no_alias = select(User.name).subquery()
    assert subq_no_alias.to_sql() == "(SELECT users.name FROM users)"
