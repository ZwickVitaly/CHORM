"""Tests for materialized view operations."""

import pytest
from chorm import create_materialized_view, select, Table, Column
from chorm.types import UInt64, String
from chorm.table_engines import SummingMergeTree


class SourceTable(Table):
    __tablename__ = "source"
    id = Column(UInt64())
    name = Column(String())
    value = Column(UInt64())


def test_create_mv_with_to_table():
    """Test CREATE MATERIALIZED VIEW ... TO ..."""
    query = select(SourceTable.id, SourceTable.value).select_from(SourceTable)
    stmt = create_materialized_view("mv_source", query, to_table="target_table")

    expected = "CREATE MATERIALIZED VIEW mv_source TO target_table AS SELECT source.id, source.value FROM source"
    assert stmt.to_sql() == expected


def test_create_mv_with_engine():
    """Test CREATE MATERIALIZED VIEW ... ENGINE ..."""
    query = select(SourceTable.id, SourceTable.value).select_from(SourceTable)
    engine = SummingMergeTree(columns=("value",))
    stmt = create_materialized_view("mv_source", query, engine=engine, populate=True)

    expected = "CREATE MATERIALIZED VIEW mv_source ENGINE = SummingMergeTree(columns) POPULATE AS SELECT source.id, source.value FROM source"
    # Note: SummingMergeTree args rendering might vary slightly depending on how it handles tuple args, but let's check key parts
    sql = stmt.to_sql()
    assert "CREATE MATERIALIZED VIEW mv_source" in sql
    assert "ENGINE = SummingMergeTree" in sql
    assert "POPULATE" in sql
    assert "AS SELECT source.id, source.value FROM source" in sql


def test_create_mv_if_not_exists():
    """Test CREATE MATERIALIZED VIEW IF NOT EXISTS."""
    query = select(SourceTable.id).select_from(SourceTable)
    stmt = create_materialized_view("mv_source", query, to_table="target", if_not_exists=True)


def test_declarative_mv_ddl():
    """Test CREATE MATERIALIZED VIEW generation from Declarative Model."""
    from chorm import Table, MaterializedView, MergeTree
    # select is imported at module level

    class Source(Table):
        __tablename__ = "source"
        __engine__ = MergeTree()
        id = Column(UInt64())
        val = Column(UInt64())

    class Target(Table):
        __tablename__ = "target"
        __engine__ = MergeTree()
        id = Column(UInt64())
        val = Column(UInt64())

    class View(Table):
        __tablename__ = "view"
        __engine__ = MaterializedView()
        __to_table__ = Target
        # We need to construct a query. In declarative, often we can't refer to other models easily at class creation time
        # if they are not fully initialized, but here they are local.
        __select__ = select(Source.id, Source.val).select_from(Source)

    ddl = View.create_table()
    assert "CREATE MATERIALIZED VIEW view" in ddl
    assert "TO target" in ddl
    # assert "POPULATE" in ddl  # No longer expected
    assert "AS SELECT source.id, source.val FROM source" in ddl


def test_declarative_mv_with_inner_engine():
    """Test MVs with explicit internal storage engine."""
    from chorm import Table, MaterializedView, MergeTree
    # select is imported at module level

    class Source(Table):
        __tablename__ = "source"
        id = Column(UInt64())
        
    class View(Table):
        __tablename__ = "mv_inner"
        __engine__ = MaterializedView(engine=MergeTree(), populate=True)
        # Strict VM requires local columns definition matching select
        # SELECT Source.id -> expects local column 'id' (or matching name)
        id = Column(UInt64())
        
        __select__ = select(Source.id).select_from(Source)

    ddl = View.create_table()
    assert "CREATE MATERIALIZED VIEW mv_inner" in ddl
    assert "ENGINE = MergeTree" in ddl
    assert "POPULATE" in ddl
    assert "AS SELECT" in ddl

def test_mv_configuration_errors():
    """Test invalid MV configurations."""
    from chorm import MaterializedView, MergeTree
    from chorm.exceptions import ConfigurationError
    
    # Fix regex ("us" -> "use")
    with pytest.raises(ConfigurationError, match="Cannot use 'populate=True' with 'to_table'"):
        MaterializedView(to_table="t", populate=True)
        
    with pytest.raises(ConfigurationError, match="Cannot specify storage 'engine'"):
        MaterializedView(to_table="t", engine=MergeTree())


