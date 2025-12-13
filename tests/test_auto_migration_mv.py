import pytest
from chorm.auto_migration import MigrationGenerator, TableDiff, ColumnDiff
from chorm.declarative import Table, Column
from chorm import MaterializedView, MergeTree
from chorm import select
from chorm.sql.expression import func
from chorm.types import UInt64
from chorm.metadata import MetaData
from unittest.mock import MagicMock

class Source(Table):
    __tablename__ = "source"
    __engine__ = MergeTree()
    id = Column(UInt64())
    val = Column(UInt64())

class View(Table):
    __tablename__ = "view"
    __engine__ = MaterializedView(to_table="target")
    __select__ = select(Source.id).select_from(Source)
    id = Column(UInt64())

def test_migration_generator_create_mv():
    # Setup
    introspector = MagicMock()
    # Mock introspecting database state: only source exists, view doesn't
    introspector.get_table_info.side_effect = lambda name, db: {"name": "source", "columns": [], "engine": "MergeTree"} if name == "source" else {}
    
    generator = MigrationGenerator(introspector)
    
    # Tables in code
    model_tables = {
        "source": Source.__table__,
        "view": View.__table__
    }
    
    # Database state: only source
    db_tables = ["source"]
    
    diffs = generator.compare_tables(model_tables, db_tables)
    
    # Should create "view"
    create_diff = next((d for d in diffs if d.table_name == "view"), None)
    assert create_diff is not None
    assert create_diff.action == "create"
    
    # Generate code
    code = generator.generate_migration_code([create_diff], "test_mig", "001", None)
    print(code)
    assert "CREATE MATERIALIZED VIEW" in code
    assert "TO target" in code

def test_migration_generator_detect_mv_change():
    # Setup
    introspector = MagicMock()
    
    # Old View state in DB
    old_query = "SELECT source.id FROM source"
    
    introspector.get_table_info.side_effect = lambda name, db: {
        "name": "view", 
        "columns": [{"name": "id", "type": "UInt64"}], 
        "engine": "MaterializedView",
        "create_query": f"CREATE MATERIALIZED VIEW view TO target AS {old_query}"
    } if name == "view" else {}
    
    generator = MigrationGenerator(introspector)
    
    # New View state in code (different query, SAME columns)
    class NewView(Table):
        __tablename__ = "view"
        __engine__ = MaterializedView(to_table="target")
        # Changed query: e.g. adding a filter or changing calculation, but output columns remain same
        # For test simplicity, let's say the query string is just different
        __select__ = select(Source.id).select_from(Source).where(Source.id > 10)
        id = Column(UInt64())
        
    model_tables = {"view": NewView.__table__}
    db_tables = ["view"]
    
    diffs = generator.compare_tables(model_tables, db_tables)
    
    alter_diff = next((d for d in diffs if d.table_name == "view"), None)
    
    if alter_diff:
        print(f"Detected action: {alter_diff.action}")
        # We expect some diff indicating query change
        # But 'action' might be 'alter' or custom.
    else:
        print("No difference detected.")
        
    assert alter_diff is not None, "Should detect MV definition change" 
