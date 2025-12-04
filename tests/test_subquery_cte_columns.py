"""Unit tests for Subquery and CTE column access (.c attribute)."""

import pytest
from chorm import select, func, cte
from chorm.sql.expression import Identifier, Label
from chorm.declarative import Table, Column
from chorm.types import UInt32, String


# Test models
class User(Table):
    __tablename__ = "users"

    id = Column(UInt32(), primary_key=True)
    name = Column(String())
    city = Column(String())


class Order(Table):
    __tablename__ = "orders"

    id = Column(UInt32(), primary_key=True)
    user_id = Column(UInt32())
    amount = Column(UInt32())


class TestSubqueryColumnAccess:
    """Test .c attribute for Subquery objects."""

    def test_subquery_c_attribute_labeled_columns(self):
        """Test accessing labeled columns via .c attribute."""
        # Create subquery with labeled columns
        subq = select(User.id, func.count().label("user_count")).group_by(User.id).subquery("user_stats")

        # Access columns via .c
        assert isinstance(subq.c.id, Identifier)
        assert isinstance(subq.c.user_count, Identifier)
        assert subq.c.id.to_sql() == "user_stats.id"
        assert subq.c.user_count.to_sql() == "user_stats.user_count"

    def test_subquery_c_attribute_unlabeled_columns(self):
        """Test accessing table columns via .c attribute."""
        subq = select(User.id, User.name).subquery("u")

        # Access columns via .c
        assert isinstance(subq.c.id, Identifier)
        assert isinstance(subq.c.name, Identifier)
        assert subq.c.id.to_sql() == "u.id"
        assert subq.c.name.to_sql() == "u.name"

    def test_subquery_c_attribute_getitem(self):
        """Test accessing columns via subq.c['name']."""
        subq = select(User.id, func.sum(Order.amount).label("total")).subquery("totals")

        # Access via item notation
        assert subq.c["id"].to_sql() == "totals.id"
        assert subq.c["total"].to_sql() == "totals.total"

    def test_subquery_c_attribute_contains(self):
        """Test checking if column exists in subquery."""
        subq = select(User.id, User.name.label("username")).subquery("u")

        # Check known columns
        assert "id" in subq.c
        assert "username" in subq.c

        # Check unknown column
        assert "nonexistent" not in subq.c

    def test_subquery_c_attribute_keys(self):
        """Test listing available columns."""
        subq = select(User.id, User.name, func.count().label("cnt")).subquery("stats")

        keys = subq.c.keys()
        assert "id" in keys
        assert "name" in keys
        assert "cnt" in keys
        assert len(keys) == 3

    def test_subquery_c_dynamic_column_access(self):
        """Test accessing columns not explicitly in SELECT (for SELECT *)."""
        subq = select(User.id, User.name).subquery("u")

        # Access a column that wasn't explicitly selected
        # This should still work for SELECT * scenarios
        dynamic_col = subq.c.city
        assert isinstance(dynamic_col, Identifier)
        assert dynamic_col.to_sql() == "u.city"

    def test_two_level_subquery_nesting(self):
        """Test 2-level nested subqueries with .c attribute."""
        # Level 1: Daily aggregates
        daily = (
            select(Order.user_id, func.sum(Order.amount).label("daily_total")).group_by(Order.user_id).subquery("daily")
        )

        # Level 2: Use daily.c to reference columns
        monthly = (
            select(daily.c.user_id, func.avg(daily.c.daily_total).label("avg_daily"))
            .group_by(daily.c.user_id)
            .subquery("monthly")
        )

        # Verify SQL generation
        sql = monthly.to_sql()
        assert "daily.user_id" in sql
        assert "daily.daily_total" in sql
        assert "AS monthly" in sql

    def test_three_level_subquery_nesting(self):
        """Test 3-level nested subqueries with .c attribute."""
        # Level 1
        level1 = select(Order.user_id, func.sum(Order.amount).label("total")).group_by(Order.user_id).subquery("l1")

        # Level 2
        level2 = (
            select(level1.c.user_id, func.avg(level1.c.total).label("avg_total"))
            .group_by(level1.c.user_id)
            .subquery("l2")
        )

        # Level 3
        level3 = select(level2.c.user_id, level2.c.avg_total).where(level2.c.avg_total > 100).subquery("l3")

        # Verify SQL generation
        sql = level3.to_sql()
        assert "l2.user_id" in sql
        assert "l2.avg_total" in sql
        assert "WHERE" in sql


class TestCTEColumnAccess:
    """Test .c attribute for CTE objects."""

    def test_cte_c_attribute(self):
        """Test accessing CTE columns via .c attribute."""
        # Create CTE
        monthly_stats = cte(
            select(Order.user_id, func.sum(Order.amount).label("total"), func.count().label("order_count")).group_by(
                Order.user_id
            ),
            name="monthly_stats",
        )

        # Access columns via .c
        assert isinstance(monthly_stats.c.user_id, Identifier)
        assert isinstance(monthly_stats.c.total, Identifier)
        assert isinstance(monthly_stats.c.order_count, Identifier)

        assert monthly_stats.c.user_id.to_sql() == "monthly_stats.user_id"
        assert monthly_stats.c.total.to_sql() == "monthly_stats.total"
        assert monthly_stats.c.order_count.to_sql() == "monthly_stats.order_count"

    def test_cte_with_c_in_query(self):
        """Test using CTE .c attribute in a query."""
        # Create CTE
        user_totals = cte(
            select(User.id.label("user_id"), func.count().label("total_orders")).group_by(User.id), name="user_totals"
        )

        # Use CTE with .c attribute
        query = (
            select(User.name, user_totals.c.total_orders)
            .select_from(User)
            .join(user_totals, User.id == user_totals.c.user_id)
            .with_cte(user_totals)
        )

        # Verify SQL generation
        sql = query.to_sql()
        assert "WITH user_totals AS" in sql
        assert "user_totals.total_orders" in sql
        assert "user_totals.user_id" in sql

    def test_cte_c_attribute_keys(self):
        """Test listing CTE columns."""
        monthly = cte(
            select(Order.user_id, func.sum(Order.amount).label("total")).group_by(Order.user_id), name="monthly"
        )

        keys = monthly.c.keys()
        assert "user_id" in keys
        assert "total" in keys
        assert len(keys) == 2


class TestMixedCTESubquery:
    """Test mixed usage of CTEs and subqueries."""

    def test_cte_and_subquery_together(self):
        """Test using both CTE and subquery with .c attributes."""
        # Create CTE
        active_users = cte(select(User.id, User.name).where(User.city == "Moscow"), name="active_users")

        # Create subquery
        user_orders = (
            select(Order.user_id, func.count().label("order_count")).group_by(Order.user_id).subquery("user_orders")
        )

        # Use both with .c attributes
        from chorm.sql.expression import Identifier

        query = (
            select(active_users.c.name, user_orders.c.order_count)
            .select_from(Identifier("active_users"))
            .join(user_orders, active_users.c.id == user_orders.c.user_id)
            .with_cte(active_users)
        )

        # Verify SQL generation
        sql = query.to_sql()
        assert "WITH active_users AS" in sql
        assert "active_users.name" in sql
        assert "user_orders.order_count" in sql
        assert "active_users.id" in sql
        assert "user_orders.user_id" in sql


class TestSubqueryDefaultAlias:
    """Test subquery without explicit alias."""

    def test_subquery_without_alias(self):
        """Test that subquery without alias still has .c attribute."""
        subq = select(User.id, User.name).subquery()

        # Should still have .c attribute with default name
        assert hasattr(subq.c, "__getattr__")
        col = subq.c.id
        assert isinstance(col, Identifier)
        # Default alias should be "subquery"
        assert col.to_sql() == "subquery.id"


class TestColumnNamespaceEdgeCases:
    """Test edge cases for ColumnNamespace."""

    def test_underscore_attribute_raises_error(self):
        """Test that accessing underscore attributes raises AttributeError."""
        subq = select(User.id).subquery("u")

        with pytest.raises(AttributeError):
            _ = subq.c._private

    def test_empty_select_columns(self):
        """Test subquery with no explicit columns (SELECT *)."""
        # This is a bit tricky - SELECT * doesn't have explicit columns
        # But we should still be able to access .c dynamically
        subq = select().select_from(User).subquery("u")

        # Should allow dynamic access
        col = subq.c.id
        assert isinstance(col, Identifier)
        assert col.to_sql() == "u.id"
