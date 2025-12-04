"""Tests for EXPLAIN statement support."""

from chorm import select
from chorm.sql.explain import Explain
from chorm.sql.expression import Identifier, Literal


def test_explain_ast():
    """Test EXPLAIN AST generation."""
    stmt = select(1).explain(explain_type="AST")
    assert isinstance(stmt, Explain)
    assert stmt.to_sql() == "EXPLAIN AST SELECT 1"


def test_explain_syntax():
    """Test EXPLAIN SYNTAX generation."""
    stmt = select(1).explain(explain_type="SYNTAX")
    assert stmt.to_sql() == "EXPLAIN SYNTAX SELECT 1"


def test_explain_plan():
    """Test EXPLAIN PLAN generation."""
    stmt = select(1).explain(explain_type="PLAN")
    assert stmt.to_sql() == "EXPLAIN PLAN SELECT 1"


def test_explain_pipeline():
    """Test EXPLAIN PIPELINE generation."""
    stmt = select(1).explain(explain_type="PIPELINE")
    assert stmt.to_sql() == "EXPLAIN PIPELINE SELECT 1"


def test_explain_with_settings():
    """Test EXPLAIN with settings."""
    stmt = select(1).explain(explain_type="AST", header=1, description=0)
    assert stmt.to_sql() == "EXPLAIN AST header=1, description=0 SELECT 1"


def test_explain_complex_query():
    """Test EXPLAIN on a complex query."""
    stmt = select(Identifier("x")).select_from("table").where(Identifier("x") > 1).explain()
    assert stmt.to_sql() == "EXPLAIN AST SELECT x FROM table WHERE (x > 1)"


def test_analyze():
    """Test analyze() helper."""
    stmt = select(1).analyze()
    assert isinstance(stmt, Explain)
    assert stmt.to_sql() == "EXPLAIN PIPELINE SELECT 1"
