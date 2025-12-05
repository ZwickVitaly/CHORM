"""Tests for conditional functions (sumIf, avgIf, etc.) in regular SELECT queries."""

import pytest
from chorm import Table, Column, select
from chorm.sql import sum_if, avg_if, count_if, min_if, max_if, uniq_if
from chorm.sql.expression import func
from chorm.types import UInt64, UInt32, String, Float64


class Orders(Table):
    __tablename__ = "orders"
    id = Column(UInt64(), primary_key=True)
    amount = Column(Float64())
    status = Column(UInt32())
    user_id = Column(UInt64())


class Users(Table):
    __tablename__ = "users"
    id = Column(UInt64(), primary_key=True)
    age = Column(UInt32())
    name = Column(String())
    active = Column(UInt32())


class TestConditionalFunctionsInSelect:
    """Test conditional functions in regular SELECT queries."""

    def test_sum_if_in_select(self):
        """Test sumIf in SELECT query."""
        stmt = select(sum_if(Orders.amount, Orders.status == 1)).select_from(Orders)
        sql = stmt.to_sql()
        assert "sumIf" in sql
        assert "orders.amount" in sql
        assert "orders.status" in sql

    def test_avg_if_in_select(self):
        """Test avgIf in SELECT query."""
        stmt = select(avg_if(Orders.amount, Orders.status == 1)).select_from(Orders)
        sql = stmt.to_sql()
        assert "avgIf" in sql
        assert "orders.amount" in sql

    def test_count_if_in_select(self):
        """Test countIf in SELECT query."""
        stmt = select(count_if(Users.age >= 18)).select_from(Users)
        sql = stmt.to_sql()
        assert "countIf" in sql
        assert "users.age" in sql

    def test_min_if_in_select(self):
        """Test minIf in SELECT query."""
        stmt = select(min_if(Orders.amount, Orders.status == 1)).select_from(Orders)
        sql = stmt.to_sql()
        assert "minIf" in sql
        assert "orders.amount" in sql

    def test_max_if_in_select(self):
        """Test maxIf in SELECT query."""
        stmt = select(max_if(Orders.amount, Orders.status == 1)).select_from(Orders)
        sql = stmt.to_sql()
        assert "maxIf" in sql
        assert "orders.amount" in sql

    def test_uniq_if_in_select(self):
        """Test uniqIf in SELECT query."""
        stmt = select(uniq_if(Orders.user_id, Orders.status == 1)).select_from(Orders)
        sql = stmt.to_sql()
        assert "uniqIf" in sql
        assert "orders.user_id" in sql

    def test_multiple_conditional_functions_in_select(self):
        """Test multiple conditional functions in one SELECT."""
        stmt = select(
            sum_if(Orders.amount, Orders.status == 1).label("completed_sum"),
            avg_if(Orders.amount, Orders.status == 1).label("completed_avg"),
            count_if(Orders.status == 1).label("completed_count"),
            min_if(Orders.amount, Orders.status == 1).label("completed_min"),
            max_if(Orders.amount, Orders.status == 1).label("completed_max"),
        ).select_from(Orders)

        sql = stmt.to_sql()
        assert "sumIf" in sql
        assert "avgIf" in sql
        assert "countIf" in sql
        assert "minIf" in sql
        assert "maxIf" in sql
        assert "AS completed_sum" in sql
        assert "AS completed_avg" in sql

    def test_conditional_functions_with_labels(self):
        """Test conditional functions with labels."""
        stmt = select(
            sum_if(Orders.amount, Orders.status == 1).label("total"),
            avg_if(Orders.amount, Orders.status == 1).label("average"),
        ).select_from(Orders)

        sql = stmt.to_sql()
        assert "AS total" in sql
        assert "AS average" in sql

    def test_conditional_functions_with_where(self):
        """Test conditional functions with WHERE clause."""
        stmt = (
            select(sum_if(Orders.amount, Orders.status == 1).label("total"))
            .select_from(Orders)
            .where(Orders.user_id == 1)
        )

        sql = stmt.to_sql()
        assert "sumIf" in sql
        assert "WHERE" in sql
        assert "orders.user_id" in sql

    def test_conditional_functions_with_group_by(self):
        """Test conditional functions with GROUP BY."""
        stmt = (
            select(
                Orders.user_id,
                sum_if(Orders.amount, Orders.status == 1).label("total"),
                count_if(Orders.status == 1).label("count"),
            )
            .select_from(Orders)
            .group_by(Orders.user_id)
        )

        sql = stmt.to_sql()
        assert "sumIf" in sql
        assert "countIf" in sql
        assert "GROUP BY" in sql

    def test_conditional_functions_through_func_namespace(self):
        """Test conditional functions accessed through func namespace."""
        stmt = select(
            func.sumIf(Orders.amount, Orders.status == 1).label("total"),
            func.avgIf(Orders.amount, Orders.status == 1).label("avg"),
            func.countIf(Orders.status == 1).label("count"),
        ).select_from(Orders)

        sql = stmt.to_sql()
        assert "sumIf" in sql
        assert "avgIf" in sql
        assert "countIf" in sql

    def test_conditional_functions_complex_conditions(self):
        """Test conditional functions with complex conditions."""
        stmt = select(
            sum_if(Orders.amount, (Orders.status == 1) & (Orders.user_id > 10)).label("total"),
            count_if((Users.age >= 18) & (Users.active == 1)).label("active_adults"),
        ).select_from(Orders)

        sql = stmt.to_sql()
        assert "sumIf" in sql
        assert "countIf" in sql
        assert "AND" in sql

    def test_conditional_functions_with_join(self):
        """Test conditional functions in queries with JOINs."""
        stmt = (
            select(
                Users.name,
                sum_if(Orders.amount, Orders.status == 1).label("total"),
            )
            .select_from(Users)
            .join(Orders, Users.id == Orders.user_id)
        )

        sql = stmt.to_sql()
        assert "sumIf" in sql
        assert "JOIN" in sql or "INNER JOIN" in sql

    def test_all_conditional_functions_work(self):
        """Test that all conditional functions work in SELECT."""
        stmt = select(
            sum_if(Orders.amount, Orders.status == 1),
            avg_if(Orders.amount, Orders.status == 1),
            count_if(Orders.status == 1),
            min_if(Orders.amount, Orders.status == 1),
            max_if(Orders.amount, Orders.status == 1),
            uniq_if(Orders.user_id, Orders.status == 1),
        ).select_from(Orders)

        sql = stmt.to_sql()
        assert "sumIf" in sql
        assert "avgIf" in sql
        assert "countIf" in sql
        assert "minIf" in sql
        assert "maxIf" in sql
        assert "uniqIf" in sql

