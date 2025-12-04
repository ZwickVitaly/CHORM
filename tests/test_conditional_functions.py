"""Unit tests for ClickHouse conditional and array functions."""

import pytest
from chorm.sql.expression import (
    # Conditional functions (-If combinator)
    sum_if,
    count_if,
    avg_if,
    min_if,
    max_if,
    uniq_if,
    group_array_if,
    median_if,
    # Array functions
    group_uniq_array,
    sum_array,
    avg_array,
    array_concat,
    # For testing
    Identifier,
    Literal,
    BinaryExpression,
)


class TestConditionalFunctions:
    """Tests for -If combinator functions."""

    def test_sum_if(self):
        """Test sumIf() SQL generation."""
        condition = BinaryExpression(Identifier("status"), "=", Literal("completed"))
        expr = sum_if(Identifier("amount"), condition)
        sql = expr.to_sql()
        assert "sumIf" in sql
        assert "amount" in sql
        assert "status" in sql

    def test_count_if(self):
        """Test countIf() SQL generation."""
        condition = BinaryExpression(Identifier("age"), ">=", Literal(18))
        expr = count_if(condition)
        sql = expr.to_sql()
        assert "countIf" in sql
        assert "age" in sql
        assert "18" in sql

    def test_avg_if(self):
        """Test avgIf() SQL generation."""
        condition = BinaryExpression(Identifier("category"), "=", Literal("premium"))
        expr = avg_if(Identifier("price"), condition)
        sql = expr.to_sql()
        assert "avgIf" in sql
        assert "price" in sql
        assert "category" in sql

    def test_min_if(self):
        """Test minIf() SQL generation."""
        condition = BinaryExpression(Identifier("status"), "=", Literal("active"))
        expr = min_if(Identifier("amount"), condition)
        sql = expr.to_sql()
        assert "minIf" in sql
        assert "amount" in sql

    def test_max_if(self):
        """Test maxIf() SQL generation."""
        condition = BinaryExpression(Identifier("status"), "=", Literal("active"))
        expr = max_if(Identifier("amount"), condition)
        sql = expr.to_sql()
        assert "maxIf" in sql
        assert "amount" in sql

    def test_uniq_if(self):
        """Test uniqIf() SQL generation."""
        condition = BinaryExpression(Identifier("active"), "=", Literal(1))
        expr = uniq_if(Identifier("user_id"), condition)
        sql = expr.to_sql()
        assert "uniqIf" in sql
        assert "user_id" in sql

    def test_group_array_if(self):
        """Test groupArrayIf() SQL generation."""
        condition = BinaryExpression(Identifier("active"), "=", Literal(1))
        expr = group_array_if(Identifier("name"), condition)
        sql = expr.to_sql()
        assert "groupArrayIf" in sql
        assert "name" in sql

    def test_median_if(self):
        """Test medianIf() SQL generation."""
        condition = BinaryExpression(Identifier("status"), "=", Literal("completed"))
        expr = median_if(Identifier("amount"), condition)
        sql = expr.to_sql()
        assert "medianIf" in sql
        assert "amount" in sql


class TestArrayFunctions:
    """Tests for array functions."""

    def test_group_uniq_array(self):
        """Test groupUniqArray() SQL generation."""
        expr = group_uniq_array(Identifier("tags"))
        assert expr.to_sql() == "groupUniqArray(tags)"

    def test_sum_array(self):
        """Test arraySum() SQL generation."""
        expr = sum_array(Identifier("amounts"))
        assert expr.to_sql() == "arraySum(amounts)"

    def test_avg_array(self):
        """Test arrayAvg() SQL generation."""
        expr = avg_array(Identifier("scores"))
        assert expr.to_sql() == "arrayAvg(scores)"

    def test_array_concat(self):
        """Test arrayConcat() SQL generation."""
        expr = array_concat(Identifier("tags1"), Identifier("tags2"))
        assert expr.to_sql() == "arrayConcat(tags1, tags2)"

    def test_array_concat_multiple(self):
        """Test arrayConcat() with multiple arrays."""
        expr = array_concat(Identifier("a"), Identifier("b"), Identifier("c"))
        assert expr.to_sql() == "arrayConcat(a, b, c)"


class TestConditionalComposition:
    """Tests for composing conditional functions."""

    def test_multiple_conditional_aggregations(self):
        """Test multiple conditional aggregations in same query."""
        completed_cond = BinaryExpression(Identifier("status"), "=", Literal("completed"))
        pending_cond = BinaryExpression(Identifier("status"), "=", Literal("pending"))

        completed_sum = sum_if(Identifier("amount"), completed_cond)
        pending_sum = sum_if(Identifier("amount"), pending_cond)

        assert "sumIf" in completed_sum.to_sql()
        assert "sumIf" in pending_sum.to_sql()
        assert completed_sum.to_sql() != pending_sum.to_sql()

    def test_conditional_with_label(self):
        """Test conditional function with label."""
        condition = BinaryExpression(Identifier("age"), ">=", Literal(18))
        expr = count_if(condition).label("adults")
        sql = expr.to_sql()
        assert "countIf" in sql
        assert "AS adults" in sql

    def test_nested_conditions(self):
        """Test conditional function with complex condition."""
        cond1 = BinaryExpression(Identifier("age"), ">=", Literal(18))
        cond2 = BinaryExpression(Identifier("active"), "=", Literal(1))
        condition = BinaryExpression(cond1, "AND", cond2)
        expr = count_if(condition)
        sql = expr.to_sql()
        assert "countIf" in sql
        assert "AND" in sql

    def test_conditional_with_label(self):
        """Test conditional function with label."""
        expr = count_if(Identifier("age") >= Literal(18)).label("adults")
        sql = expr.to_sql()
        assert "countIf" in sql
        assert "AS adults" in sql

    def test_nested_conditions(self):
        """Test conditional function with complex condition."""
        condition = (Identifier("age") >= Literal(18)) & (Identifier("active") == Literal(1))
        expr = count_if(condition)
        sql = expr.to_sql()
        assert "countIf" in sql
        assert "AND" in sql
