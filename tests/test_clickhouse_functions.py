"""Unit tests for ClickHouse-specific function wrappers."""

import pytest
from chorm.sql.expression import (
    # Aggregation functions
    uniq,
    uniq_exact,
    quantile,
    quantiles,
    median,
    group_array,
    stddev_pop,
    var_pop,
    corr,
    # Date/Time functions
    to_start_of_month,
    to_start_of_week,
    to_start_of_day,
    date_diff,
    now,
    today,
    # String functions
    concat,
    substring,
    position,
    length,
    # For testing
    Identifier,
    Literal,
)


class TestAggregationFunctions:
    """Tests for ClickHouse aggregation functions."""

    def test_uniq(self):
        """Test uniq() SQL generation."""
        expr = uniq(Identifier("user_id"))
        assert expr.to_sql() == "uniq(user_id)"

    def test_uniq_multiple_args(self):
        """Test uniq() with multiple arguments."""
        expr = uniq(Identifier("user_id"), Identifier("session_id"))
        assert expr.to_sql() == "uniq(user_id, session_id)"

    def test_uniq_exact(self):
        """Test uniqExact() SQL generation."""
        expr = uniq_exact(Identifier("user_id"))
        assert expr.to_sql() == "uniqExact(user_id)"

    def test_quantile(self):
        """Test quantile() SQL generation."""
        expr = quantile(0.95, Identifier("amount"))
        assert expr.to_sql() == "quantile(0.95, amount)"

    def test_quantiles(self):
        """Test quantiles() SQL generation."""
        expr = quantiles([0.25, 0.5, 0.75], Identifier("amount"))
        # Note: list will be converted to Literal
        assert "quantiles" in expr.to_sql()
        assert "amount" in expr.to_sql()

    def test_median(self):
        """Test median() SQL generation."""
        expr = median(Identifier("amount"))
        assert expr.to_sql() == "median(amount)"

    def test_group_array(self):
        """Test groupArray() SQL generation."""
        expr = group_array(Identifier("name"))
        assert expr.to_sql() == "groupArray(name)"

    def test_group_array_with_max_size(self):
        """Test groupArray() with max size parameter (ignored in SQL)."""
        # max_size parameter is accepted but not used in SQL generation
        # For limited arrays, use arraySlice(groupArray(expr), 1, max_size)
        expr = group_array(Identifier("name"), 100)
        assert expr.to_sql() == "groupArray(name)"

    def test_stddev_pop(self):
        """Test stddevPop() SQL generation."""
        expr = stddev_pop(Identifier("amount"))
        assert expr.to_sql() == "stddevPop(amount)"

    def test_var_pop(self):
        """Test varPop() SQL generation."""
        expr = var_pop(Identifier("amount"))
        assert expr.to_sql() == "varPop(amount)"

    def test_corr(self):
        """Test corr() SQL generation."""
        expr = corr(Identifier("age"), Identifier("amount"))
        assert expr.to_sql() == "corr(age, amount)"


class TestDateTimeFunctions:
    """Tests for ClickHouse date/time functions."""

    def test_to_start_of_month(self):
        """Test toStartOfMonth() SQL generation."""
        expr = to_start_of_month(Identifier("order_date"))
        assert expr.to_sql() == "toStartOfMonth(order_date)"

    def test_to_start_of_week(self):
        """Test toStartOfWeek() SQL generation."""
        expr = to_start_of_week(Identifier("order_date"))
        assert expr.to_sql() == "toStartOfWeek(order_date, 0)"

    def test_to_start_of_week_with_mode(self):
        """Test toStartOfWeek() with custom mode."""
        expr = to_start_of_week(Identifier("order_date"), 1)
        assert expr.to_sql() == "toStartOfWeek(order_date, 1)"

    def test_to_start_of_day(self):
        """Test toStartOfDay() SQL generation."""
        expr = to_start_of_day(Identifier("created_at"))
        assert expr.to_sql() == "toStartOfDay(created_at)"

    def test_date_diff(self):
        """Test dateDiff() SQL generation."""
        expr = date_diff("day", Identifier("start_date"), Identifier("end_date"))
        assert expr.to_sql() == "dateDiff('day', start_date, end_date)"

    def test_date_diff_different_units(self):
        """Test dateDiff() with different time units."""
        units = ["day", "month", "year", "hour", "minute", "second"]
        for unit in units:
            expr = date_diff(unit, Identifier("start"), Identifier("end"))
            assert f"dateDiff('{unit}'" in expr.to_sql()

    def test_now(self):
        """Test now() SQL generation."""
        expr = now()
        assert expr.to_sql() == "now()"

    def test_today(self):
        """Test today() SQL generation."""
        expr = today()
        assert expr.to_sql() == "today()"


class TestStringFunctions:
    """Tests for ClickHouse string functions."""

    def test_concat(self):
        """Test concat() SQL generation."""
        expr = concat(Identifier("first_name"), Literal(" "), Identifier("last_name"))
        assert expr.to_sql() == "concat(first_name, ' ', last_name)"

    def test_concat_multiple_args(self):
        """Test concat() with many arguments."""
        expr = concat(Identifier("a"), Identifier("b"), Identifier("c"), Identifier("d"))
        assert expr.to_sql() == "concat(a, b, c, d)"

    def test_substring_with_length(self):
        """Test substring() with length."""
        expr = substring(Identifier("email"), 1, 5)
        assert expr.to_sql() == "substring(email, 1, 5)"

    def test_substring_without_length(self):
        """Test substring() without length."""
        expr = substring(Identifier("email"), 10)
        assert expr.to_sql() == "substring(email, 10)"

    def test_position(self):
        """Test position() SQL generation."""
        expr = position(Identifier("email"), Literal("@"))
        assert expr.to_sql() == "position(email, '@')"

    def test_length(self):
        """Test length() SQL generation."""
        expr = length(Identifier("name"))
        assert expr.to_sql() == "length(name)"


class TestFunctionComposition:
    """Tests for composing multiple functions."""

    def test_nested_functions(self):
        """Test nesting ClickHouse functions."""
        # median(toStartOfMonth(order_date))
        expr = median(to_start_of_month(Identifier("order_date")))
        assert "median" in expr.to_sql()
        assert "toStartOfMonth" in expr.to_sql()

    def test_function_with_label(self):
        """Test function with label."""
        expr = uniq(Identifier("user_id")).label("unique_users")
        assert expr.to_sql() == "uniq(user_id) AS unique_users"

    def test_date_diff_with_now(self):
        """Test dateDiff with now()."""
        expr = date_diff("day", Identifier("created_at"), now())
        assert "dateDiff('day', created_at, now())" in expr.to_sql()
