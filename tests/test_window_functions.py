"""Tests for Window Functions functionality."""

import pytest
from chorm import Table, Column, MergeTree, select
from chorm.types import UInt64, String, DateTime
from chorm.sql.expression import func, row_number, rank, dense_rank, lag, lead


class User(Table):
    __tablename__ = "users"
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    city = Column(String())
    created_at = Column(DateTime())
    engine = MergeTree()


class Order(Table):
    __tablename__ = "orders"
    id = Column(UInt64(), primary_key=True)
    user_id = Column(UInt64())
    amount = Column(UInt64())
    date = Column(DateTime())
    engine = MergeTree()


def test_empty_over():
    """Test OVER () clause."""
    stmt = select(row_number().over())
    sql = stmt.to_sql()
    assert "row_number() OVER ()" in sql


def test_partition_by():
    """Test OVER (PARTITION BY ...)."""
    stmt = select(rank().over(partition_by=User.city))
    sql = stmt.to_sql()
    assert "rank() OVER (PARTITION BY users.city)" in sql


def test_order_by():
    """Test OVER (ORDER BY ...)."""
    stmt = select(dense_rank().over(order_by=User.created_at.desc()))
    sql = stmt.to_sql()
    assert "dense_rank() OVER (ORDER BY users.created_at DESC)" in sql


def test_partition_and_order():
    """Test OVER (PARTITION BY ... ORDER BY ...)."""
    stmt = select(row_number().over(partition_by=User.city, order_by=User.created_at))
    sql = stmt.to_sql()
    assert "row_number() OVER (PARTITION BY users.city ORDER BY users.created_at)" in sql


def test_multiple_partition_order():
    """Test multiple columns in PARTITION BY and ORDER BY."""
    stmt = select(row_number().over(partition_by=[User.city, User.name], order_by=[User.created_at.desc(), User.id]))
    sql = stmt.to_sql()
    assert "PARTITION BY users.city, users.name" in sql
    assert "ORDER BY users.created_at DESC, users.id" in sql


def test_frame_spec():
    """Test window frame specification."""
    stmt = select(
        func.sum(Order.amount).over(
            partition_by=Order.user_id, order_by=Order.date, frame="ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW"
        )
    )
    sql = stmt.to_sql()
    assert (
        "sum(orders.amount) OVER (PARTITION BY orders.user_id ORDER BY orders.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)"
        in sql
    )


def test_lag_lead():
    """Test lag and lead functions."""
    # lag(expr, offset, default)
    stmt_lag = select(lag(Order.amount, 1, 0).over(order_by=Order.date))
    assert "lag(orders.amount, 1, 0) OVER (ORDER BY orders.date)" in stmt_lag.to_sql()

    # lead(expr, offset) - default is optional
    stmt_lead = select(lead(Order.amount, 2).over(order_by=Order.date))
    assert "lead(orders.amount, 2) OVER (ORDER BY orders.date)" in stmt_lead.to_sql()


def test_window_function_in_select():
    """Test window function in a full SELECT statement."""
    stmt = select(User.name, row_number().over(partition_by=User.city, order_by=User.name).label("rn")).where(
        User.city == "Moscow"
    )

    sql = stmt.to_sql()
    assert "SELECT users.name, row_number() OVER (PARTITION BY users.city ORDER BY users.name) AS rn FROM users" in sql
    assert "WHERE (users.city = 'Moscow')" in sql
