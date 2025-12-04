"""Tests for CTEs (Common Table Expressions) functionality."""

import sys
from unittest.mock import MagicMock

# Mock clickhouse_connect
sys.modules["clickhouse_connect"] = MagicMock()

import pytest
from chorm import Table, Column, MergeTree, select
from chorm.types import UInt64, String
from chorm.sql.expression import func, Identifier


class User(Table):
    __tablename__ = "users"
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    city = Column(String())
    active = Column(UInt64())
    engine = MergeTree()


class Order(Table):
    __tablename__ = "orders"
    id = Column(UInt64(), primary_key=True)
    user_id = Column(UInt64())
    amount = Column(UInt64())
    engine = MergeTree()


def test_simple_cte():
    """Test creating a simple CTE."""
    cte = select(User.id, User.name).where(User.city == "Moscow").cte("moscow_users")

    # CTE should render as "name AS (SELECT ...)"
    cte_sql = cte.to_sql()
    assert "moscow_users AS (SELECT users.id, users.name FROM users WHERE (users.city = 'Moscow'))" in cte_sql


def test_cte_in_query():
    """Test using a CTE in a query."""
    cte = select(User.id, User.name).where(User.city == "Moscow").cte("moscow_users")
    stmt = select(Identifier("*")).select_from(Identifier("moscow_users")).with_cte(cte)

    sql = stmt.to_sql()
    assert "WITH moscow_users AS (SELECT users.id, users.name FROM users WHERE (users.city = 'Moscow'))" in sql
    assert "SELECT * FROM moscow_users" in sql


def test_multiple_ctes():
    """Test multiple CTEs in one query."""
    cte1 = select(User.id).where(User.active == 1).cte("active_users")
    cte2 = select(Order.user_id, func.sum(Order.amount).label("total")).group_by(Order.user_id).cte("user_totals")

    stmt = (
        select(Identifier("active_users.id"), Identifier("user_totals.total"))
        .select_from(Identifier("active_users"))
        .join(Identifier("user_totals"), on=Identifier("active_users.id") == Identifier("user_totals.user_id"))
        .with_cte(cte1, cte2)
    )

    sql = stmt.to_sql()
    assert "WITH active_users AS" in sql
    assert "user_totals AS" in sql
    assert sql.index("active_users AS") < sql.index("user_totals AS")


def test_cte_with_aggregation():
    """Test CTE with GROUP BY and aggregation."""
    cte = (
        select(Order.user_id, func.count(Order.id).label("order_count"))
        .group_by(Order.user_id)
        .cte("user_order_counts")
    )

    cte_sql = cte.to_sql()
    assert "user_order_counts AS" in cte_sql
    assert "GROUP BY orders.user_id" in cte_sql


def test_cte_with_join():
    """Test CTE that contains a JOIN."""
    cte = select(User.name, Order.amount).select_from(User).join(Order, on=User.id == Order.user_id).cte("user_orders")

    cte_sql = cte.to_sql()
    assert "user_orders AS" in cte_sql
    assert "INNER JOIN orders" in cte_sql


def test_cte_with_where_and_order():
    """Test CTE with WHERE and ORDER BY."""
    cte = select(User.id, User.name).where(User.active == 1).order_by(User.name.asc()).limit(10).cte("top_active_users")

    cte_sql = cte.to_sql()
    assert "top_active_users AS" in cte_sql
    assert "WHERE (users.active = 1)" in cte_sql
    assert "ORDER BY users.name ASC" in cte_sql
    assert "LIMIT 10" in cte_sql


def test_cte_referenced_multiple_times():
    """Test that a CTE can be referenced multiple times in the main query."""
    cte = select(User.id, User.name).where(User.active == 1).cte("active_users")

    # Use the CTE twice in a self-join scenario
    stmt = (
        select(Identifier("a.id"), Identifier("a.name"), Identifier("b.name").label("other_name"))
        .select_from(Identifier("active_users").label("a"))
        .cross_join(Identifier("active_users").label("b"))
        .with_cte(cte)
    )

    sql = stmt.to_sql()
    assert "WITH active_users AS" in sql
    # CTE should only be defined once in WITH clause
    assert sql.count("WITH active_users AS") == 1
    # But can be referenced multiple times in FROM/JOIN
    assert "FROM active_users AS a" in sql
    assert "CROSS JOIN active_users AS b" in sql


def test_nested_cte_reference():
    """Test CTE that could reference another CTE (order matters)."""
    cte1 = select(User.id, User.name).where(User.active == 1).cte("active_users")
    cte2 = (
        select(Identifier("active_users.id"), func.count().label("cnt"))
        .select_from(Identifier("active_users"))
        .group_by(Identifier("active_users.id"))
        .cte("user_counts")
    )

    stmt = select(Identifier("*")).select_from(Identifier("user_counts")).with_cte(cte1, cte2)

    sql = stmt.to_sql()
    # CTEs should be in order
    assert sql.index("active_users AS") < sql.index("user_counts AS")


def test_cte_with_distinct():
    """Test CTE with DISTINCT."""
    cte = select(User.city).distinct().cte("unique_cities")
    stmt = select(Identifier("*")).select_from(Identifier("unique_cities")).with_cte(cte)

    sql = stmt.to_sql()
    assert "WITH unique_cities AS (SELECT DISTINCT users.city FROM users)" in sql
