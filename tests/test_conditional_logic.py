"""Unit tests for ClickHouse conditional functions (if, multiIf)."""

from chorm.sql.expression import if_, multi_if, Literal, Identifier, BinaryExpression


def test_if_function():
    """Test ClickHouse if() function."""
    # Note: Strings in function calls are treated as Identifiers by default in this ORM
    # So we must use Literal for string values
    expr = if_(BinaryExpression(Identifier("x"), ">", Literal(10)), Literal("high"), Literal("low"))
    sql = expr.to_sql()
    assert sql == "if((x > 10), 'high', 'low')"


def test_multi_if_function():
    """Test ClickHouse multiIf() function."""
    # multiIf(cond1, val1, cond2, val2, else)
    expr = multi_if(
        BinaryExpression(Identifier("x"), ">", Literal(10)),
        Literal("high"),
        BinaryExpression(Identifier("x"), ">", Literal(5)),
        Literal("medium"),
        Literal("low"),
    )
    sql = expr.to_sql()
    assert sql == "multiIf((x > 10), 'high', (x > 5), 'medium', 'low')"


def test_multi_if_mixed_types():
    """Test multiIf with mixed types (columns and literals)."""
    expr = multi_if(Identifier("is_valid"), Identifier("value"), Literal(0))
    sql = expr.to_sql()
    assert sql == "multiIf(is_valid, value, 0)"
