"""Tests for JOIN support in SQL generation."""

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


class Order(Table):
    __tablename__ = "orders"
    id = Column(UInt64(), primary_key=True)
    user_id = Column(UInt64())
    product_id = Column(UInt64())
    amount = Column(UInt64())
    status = Column(String())
    engine = MergeTree()


class Product(Table):
    __tablename__ = "products"
    id = Column(UInt64(), primary_key=True)
    product_id = Column(UInt64())
    name = Column(String())
    engine = MergeTree()


def test_inner_join():
    """Test INNER JOIN with ON condition."""
    stmt = select(User.id, User.name, Order.amount).select_from(User).join(Order, on=User.id == Order.user_id)
    sql = stmt.to_sql()
    assert "FROM users" in sql
    assert "INNER JOIN orders" in sql
    assert "ON (users.id = orders.user_id)" in sql


def test_left_join():
    """Test LEFT JOIN with ON condition."""
    stmt = select(User).left_join(Order, on=User.id == Order.user_id)
    sql = stmt.to_sql()
    assert "FROM users" in sql
    assert "LEFT JOIN orders" in sql
    assert "ON (users.id = orders.user_id)" in sql


def test_right_join():
    """Test RIGHT JOIN with ON condition."""
    stmt = select(User).right_join(Order, on=User.id == Order.user_id)
    sql = stmt.to_sql()
    assert "FROM users" in sql
    assert "RIGHT JOIN orders" in sql
    assert "ON (users.id = orders.user_id)" in sql


def test_full_join():
    """Test FULL JOIN with ON condition."""
    stmt = select(User).full_join(Order, on=User.id == Order.user_id)
    sql = stmt.to_sql()
    assert "FROM users" in sql
    assert "FULL JOIN orders" in sql
    assert "ON (users.id = orders.user_id)" in sql


def test_cross_join():
    """Test CROSS JOIN without condition."""
    stmt = select(User).cross_join(Order)
    sql = stmt.to_sql()
    assert "FROM users" in sql
    assert "CROSS JOIN orders" in sql
    # CROSS JOIN should not have ON or USING
    assert (
        "ON" not in sql.split("CROSS JOIN orders")[1].split("WHERE")[0]
        if "WHERE" in sql
        else "ON" not in sql.split("CROSS JOIN orders")[1]
    )


def test_join_using_clause():
    """Test JOIN with USING clause."""
    stmt = select(User).join(Order, using=["user_id"])
    sql = stmt.to_sql()
    assert "FROM users" in sql
    assert "INNER JOIN orders" in sql
    assert "USING (user_id)" in sql


def test_multiple_joins():
    """Test chaining multiple joins."""
    stmt = (
        select(User.name, Order.amount, Product.name)
        .select_from(User)
        .join(Order, on=User.id == Order.user_id)
        .join(Product, on=Order.product_id == Product.id)
    )
    sql = stmt.to_sql()
    assert "FROM users" in sql
    assert "INNER JOIN orders ON (users.id = orders.user_id)" in sql
    assert "INNER JOIN products ON (orders.product_id = products.id)" in sql


def test_join_with_complex_conditions():
    """Test JOIN with complex AND/OR conditions."""
    stmt = select(User).join(Order, on=(User.id == Order.user_id) & (Order.status == "active"))
    sql = stmt.to_sql()
    assert "INNER JOIN orders" in sql
    assert "ON ((users.id = orders.user_id) AND (orders.status = 'active'))" in sql


def test_join_with_or_conditions():
    """Test JOIN with OR conditions."""
    stmt = select(User).join(Order, on=(User.id == Order.user_id) | (User.city == "Moscow"))
    sql = stmt.to_sql()
    assert "INNER JOIN orders" in sql
    assert "ON ((users.id = orders.user_id) OR (users.city = 'Moscow'))" in sql


def test_join_error_no_condition():
    """Test that JOIN requires either on or using parameter."""
    with pytest.raises(ValueError, match="Either 'on' or 'using' must be provided"):
        select(User).join(Order)


def test_join_error_both_on_and_using():
    """Test that JOIN cannot have both on and using parameters."""
    with pytest.raises(ValueError, match="Cannot specify both 'on' and 'using'"):
        select(User).join(Order, on=User.id == Order.user_id, using=["user_id"])


def test_cross_join_error_with_on():
    """Test that CROSS JOIN does not accept on parameter."""
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        select(User).cross_join(Order, on=User.id == Order.user_id)


def test_join_with_table_string():
    """Test JOIN with table name as string."""
    stmt = select(User).join("orders", on=User.id == Order.user_id)
    sql = stmt.to_sql()
    assert "INNER JOIN orders" in sql


def test_mixed_joins():
    """Test mixing different join types."""
    stmt = (
        select(User)
        .left_join(Order, on=User.id == Order.user_id)
        .right_join(Product, on=Order.product_id == Product.id)
    )
    sql = stmt.to_sql()
    assert "LEFT JOIN orders" in sql
    assert "RIGHT JOIN products" in sql
