"""Unit tests for WITH TOTALS functionality."""

from chorm import select, Table, Column, MergeTree, func
from chorm.types import UInt64, String


class Order(Table):
    __tablename__ = "orders"
    id = Column(UInt64(), primary_key=True)
    category = Column(String())
    amount = Column(UInt64())
    engine = MergeTree()


def test_simple_with_totals():
    """Test simple WITH TOTALS clause."""
    stmt = select(Order.category, func.sum(Order.amount)).select_from(Order).group_by(Order.category).with_totals()
    sql = stmt.to_sql()
    assert "GROUP BY orders.category WITH TOTALS" in sql


def test_with_totals_ordering():
    """Test WITH TOTALS position (after GROUP BY, before HAVING/ORDER BY)."""
    stmt = (
        select(Order.category, func.sum(Order.amount))
        .select_from(Order)
        .group_by(Order.category)
        .with_totals()
        .having(func.sum(Order.amount) > 100)
        .order_by(Order.category)
    )
    sql = stmt.to_sql()

    assert "GROUP BY orders.category WITH TOTALS HAVING" in sql
    assert "HAVING (sum(orders.amount) > 100) ORDER BY" in sql
