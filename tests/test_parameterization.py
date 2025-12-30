
import pytest
from datetime import date, datetime
from chorm.sql.compiler import Compiler
from chorm.sql.expression import Literal, Identifier
from chorm.sql.selectable import select
from chorm.sql.dml import insert, update, delete
from chorm.declarative import Table
from chorm.types import StringType, Int32, DateType
from chorm.declarative import Column

class User(Table):
    id = Column(Int32())
    name = Column(StringType())
    created_at = Column(DateType("Date"))

def test_compiler_basics():
    compiler = Compiler()
    p1 = compiler.add_param(123)
    p2 = compiler.add_param("test")
    
    assert p1 == "%(p_0)s"
    assert p2 == "%(p_1)s"
    assert compiler.params == {"p_0": 123, "p_1": "test"}

def test_literal_parameterization():
    compiler = Compiler()
    expr = Literal(123)
    sql = expr.to_sql(compiler)
    
    assert sql == "%(p_0)s"
    assert compiler.params == {"p_0": 123}

def test_select_parameterization():
    compiler = Compiler()
    stmt = select(User.id, User.name).where(User.id == 123, User.name == "Alice")
    
    sql = stmt.to_sql(compiler)
    
    assert "WHERE" in sql
    assert "user.id = %(p_0)s" in sql.lower() or "user.id = %(p_1)s" in sql.lower()
    
    assert 123 in compiler.params.values()
    assert "Alice" in compiler.params.values()
    assert len(compiler.params) == 2

def test_select_date_literal():
    compiler = Compiler()
    d = date(2025, 12, 30)
    stmt = select(User).where(User.created_at == d)
    
    sql = stmt.to_sql(compiler)
    
    assert 1 == len(compiler.params)
    assert d in compiler.params.values()
    # Ensure no quotes around placeholder in SQL (checking logical correctness, not exact string)
    # The placeholder itself is a string "%(p_0)s", but it shouldn't be inside quotes in SQL like '%(p_0)s'
    # Literal.to_sql returns "%(p_0)s" directly, not escaped.
    assert "%(p_0)s" in sql
    assert "'%(p_0)s'" not in sql

def test_update_parameterization():
    compiler = Compiler()
    stmt = update(User).where(User.id == 10).values(name="Bob")
    
    sql = stmt.to_sql(compiler)
    
    assert "UPDATE" in sql
    assert "name = %(p_0)s" in sql or "name = %(p_1)s" in sql
    assert "id = %(p_0)s" in sql.lower() or "id = %(p_1)s" in sql.lower()
    
    assert 10 in compiler.params.values()
    assert "Bob" in compiler.params.values()

def test_engine_compile():
    # Mock engine config not needed for compile test if we use Engine directly?
    # Engine requires config.
    from chorm.engine import Engine, EngineConfig
    
    engine = Engine(config=EngineConfig())
    stmt = select(User).where(User.id == 999)
    
    sql, params = engine.compile(stmt)
    
    assert "SELECT" in sql
    assert "%(p_0)s" in sql
    assert params == {"p_0": 999}

def test_legacy_to_sql_no_compiler():
    # Ensure calling to_sql without arguments still works (string interpolation)
    
    stmt = select(User).where(User.id == 123)
    sql = stmt.to_sql()
    
    assert "123" in sql
    assert "%(p_0)s" not in sql
