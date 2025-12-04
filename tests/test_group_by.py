import sys
from unittest.mock import MagicMock

# Mock clickhouse_connect to avoid installation requirement for SQL generation testing
sys.modules["clickhouse_connect"] = MagicMock()

from chorm import Table, Column, MergeTree, select
from chorm.types import UInt64, String
from chorm.sql.expression import func


class User(Table):
    __tablename__ = "users"
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    city = Column(String())
    country = Column(String())
    engine = MergeTree()


class Order(Table):
    __tablename__ = "orders"
    id = Column(UInt64(), primary_key=True)
    user_id = Column(UInt64())
    amount = Column(UInt64())
    status = Column(String())
    engine = MergeTree()


def test_simple_group_by():
    """Test simple GROUP BY with single column."""
    stmt = select(User.city, func.count(User.id)).group_by(User.city)
    sql = stmt.to_sql()

    assert "GROUP BY" in sql
    assert "users.city" in sql
    assert "count(users.id)" in sql


def test_group_by_multiple_columns():
    """Test GROUP BY with multiple columns."""
    stmt = select(User.city, User.country, func.count(User.id)).group_by(User.city, User.country)
    sql = stmt.to_sql()

    assert "GROUP BY users.city, users.country" in sql


def test_group_by_with_having():
    """Test GROUP BY with HAVING clause."""
    stmt = select(User.city, func.count(User.id)).group_by(User.city).having(func.count(User.id) > 10)
    sql = stmt.to_sql()

    assert "GROUP BY users.city" in sql
    assert "HAVING" in sql
    assert "count(users.id) > 10" in sql


def test_having_multiple_conditions():
    """Test HAVING with multiple conditions."""
    stmt = (
        select(User.city, func.count(User.id), func.avg(User.id))
        .group_by(User.city)
        .having((func.count(User.id) > 5) & (func.avg(User.id) < 1000))
    )
    sql = stmt.to_sql()

    assert "HAVING ((count(users.id) > 5) AND (avg(users.id) < 1000))" in sql


def test_group_by_with_expression():
    """Test GROUP BY with expression (function call)."""
    stmt = select(func.toYYYYMM(Order.user_id), func.sum(Order.amount)).group_by(func.toYYYYMM(Order.user_id))
    sql = stmt.to_sql()

    assert "GROUP BY toYYYYMM(orders.user_id)" in sql


def test_group_by_with_where():
    """Test GROUP BY combined with WHERE clause."""
    stmt = select(Order.status, func.sum(Order.amount)).where(Order.amount > 100).group_by(Order.status)
    sql = stmt.to_sql()

    # WHERE should come before GROUP BY
    assert sql.index("WHERE") < sql.index("GROUP BY")
    assert "WHERE (orders.amount > 100)" in sql
    assert "GROUP BY orders.status" in sql


def test_group_by_with_order_by():
    """Test GROUP BY combined with ORDER BY."""
    stmt = select(User.city, func.count(User.id)).group_by(User.city).order_by(func.count(User.id).desc())
    sql = stmt.to_sql()

    # GROUP BY should come before ORDER BY
    assert sql.index("GROUP BY") < sql.index("ORDER BY")
    assert "ORDER BY count(users.id) DESC" in sql


def test_group_by_with_limit():
    """Test GROUP BY combined with LIMIT."""
    stmt = select(User.city, func.count(User.id)).group_by(User.city).limit(5)
    sql = stmt.to_sql()

    assert "GROUP BY users.city" in sql
    assert "LIMIT 5" in sql


def test_group_by_clause_order():
    """Test correct SQL clause ordering with GROUP BY."""
    stmt = (
        select(User.city, func.count(User.id))
        .where(User.country == "Russia")
        .group_by(User.city)
        .having(func.count(User.id) > 10)
        .order_by(func.count(User.id).desc())
        .limit(5)
    )
    sql = stmt.to_sql()

    # Verify correct order: WHERE < GROUP BY < HAVING < ORDER BY < LIMIT
    where_pos = sql.index("WHERE")
    group_pos = sql.index("GROUP BY")
    having_pos = sql.index("HAVING")
    order_pos = sql.index("ORDER BY")
    limit_pos = sql.index("LIMIT")

    assert where_pos < group_pos < having_pos < order_pos < limit_pos


def test_multiple_aggregations():
    """Test multiple aggregation functions in SELECT."""
    stmt = select(
        Order.status,
        func.count(Order.id).label("count"),
        func.sum(Order.amount).label("total"),
        func.avg(Order.amount).label("average"),
        func.min(Order.amount).label("min"),
        func.max(Order.amount).label("max"),
    ).group_by(Order.status)
    sql = stmt.to_sql()

    assert "count(orders.id) AS count" in sql
    assert "sum(orders.amount) AS total" in sql
    assert "avg(orders.amount) AS average" in sql
    assert "min(orders.amount) AS min" in sql
    assert "max(orders.amount) AS max" in sql
    assert "GROUP BY orders.status" in sql


def test_group_by_with_join():
    """Test GROUP BY with JOIN."""
    stmt = (
        select(User.name, func.count(Order.id))
        .select_from(User)
        .join(Order, on=User.id == Order.user_id)
        .group_by(User.name)
    )
    sql = stmt.to_sql()

    assert "INNER JOIN orders" in sql
    assert "GROUP BY users.name" in sql
    assert "count(orders.id)" in sql
