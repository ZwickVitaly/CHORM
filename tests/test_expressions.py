"""Tests for SQL expression helpers."""

from chorm.sql.expression import (
    FunctionCall,
    Identifier,
    Literal,
    avg,
    coalesce,
    count,
    count_distinct,
    func,
    if_null,
    lower_utf8,
    max_,
    min_,
    null_if,
    sum_,
    to_date,
    to_datetime,
    to_decimal32,
    upper,
    upper_utf8,
)


def test_identifier_literal_coercion() -> None:
    expr = func.count("id")
    assert isinstance(expr, FunctionCall)
    assert expr.to_sql() == "count(id)"

    text_expr = func.concat("name", Literal(" "), "surname")
    assert text_expr.to_sql() == "concat(name, ' ', surname)"


def test_custom_function_name() -> None:
    expr = func("arrayJoin")("values")
    assert expr.to_sql() == "arrayJoin(values)"


def test_common_wrappers() -> None:
    assert sum_("value").to_sql() == "sum(value)"
    assert avg("value").to_sql() == "avg(value)"
    assert min_("value").to_sql() == "min(value)"
    assert max_("value").to_sql() == "max(value)"
    assert lower_utf8("name").to_sql() == "lowerUTF8(name)"
    assert upper("name").to_sql() == "upper(name)"
    assert upper_utf8("name").to_sql() == "upperUTF8(name)"
    assert coalesce("a", "b").to_sql() == "coalesce(a, b)"
    assert if_null("a", 0).to_sql() == "ifNull(a, 0)"
    assert null_if("a", 0).to_sql() == "nullIf(a, 0)"
    assert count().to_sql() == "count()"
    assert count_distinct("a").to_sql() == "countDistinct(a)"
    assert to_date("ts").to_sql() == "toDate(ts)"
    assert to_datetime("ts").to_sql() == "toDateTime(ts)"
    assert to_datetime("ts", "UTC").to_sql() == "toDateTime(ts, 'UTC')"
    assert to_decimal32("value", 2).to_sql() == "toDecimal32(value, 2)"
