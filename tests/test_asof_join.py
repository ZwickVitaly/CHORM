"""Tests for ASOF JOIN functionality."""

from chorm import select
from chorm.sql.expression import Identifier, Literal


def test_asof_join_basic():
    """Test basic ASOF JOIN generation."""
    stmt = (
        select(Identifier("t1.value"), Identifier("t2.value"))
        .select_from("table1")
        .asof_join("table2", on=Identifier("t1.time") >= Identifier("t2.time"))
    )
    # Note: BinaryExpression renders with parentheses
    assert stmt.to_sql() == "SELECT t1.value, t2.value FROM table1 ASOF LEFT JOIN table2 ON (t1.time >= t2.time)"


def test_asof_join_using():
    """Test ASOF JOIN with USING."""
    stmt = select(1).select_from("t1").asof_join("t2", using=["id", "time"])
    assert stmt.to_sql() == "SELECT 1 FROM t1 ASOF LEFT JOIN t2 USING (id, time)"


def test_asof_join_custom_type():
    """Test ASOF JOIN with custom type."""
    stmt = (
        select(1).select_from("t1").asof_join("t2", on=Identifier("t1.time") >= Identifier("t2.time"), type="ASOF JOIN")
    )
    assert stmt.to_sql() == "SELECT 1 FROM t1 ASOF JOIN t2 ON (t1.time >= t2.time)"
