"""Tests for utility functions (String, Date)."""

from chorm import select
from chorm.sql.expression import (
    trim,
    ltrim,
    rtrim,
    replace,
    split_by_char,
    to_year,
    to_month,
    to_day,
    add_days,
    add_months,
    Identifier,
    Literal,
)


def test_string_functions():
    """Test string utility functions."""
    assert trim(Literal(" s ")).to_sql() == "trim(' s ')"
    assert ltrim(Literal(" s ")).to_sql() == "ltrim(' s ')"
    assert rtrim(Literal(" s ")).to_sql() == "rtrim(' s ')"
    assert (
        replace(Literal("hello world"), Literal("world"), Literal("clickhouse")).to_sql()
        == "replaceAll('hello world', 'world', 'clickhouse')"
    )
    assert split_by_char(Literal(","), Literal("a,b,c")).to_sql() == "splitByChar(',', 'a,b,c')"


def test_date_functions():
    """Test date utility functions."""
    date_col = Identifier("date")
    assert to_year(date_col).to_sql() == "toYear(date)"
    assert to_month(date_col).to_sql() == "toMonth(date)"
    assert to_day(date_col).to_sql() == "toDayOfMonth(date)"
    assert add_days(date_col, 7).to_sql() == "addDays(date, 7)"
    assert add_months(date_col, 1).to_sql() == "addMonths(date, 1)"
