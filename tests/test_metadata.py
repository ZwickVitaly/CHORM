import pytest
from unittest.mock import MagicMock
from chorm import Table, Column, MetaData
from chorm.types import UInt64, String
from chorm.table_engines import Memory

def test_metadata_registry():
    # User's MetaData
    md = MetaData()
    
    class User(Table):
        metadata = md
        __tablename__ = "users"
        id = Column(UInt64(), primary_key=True)
        name = Column(String())
        engine = Memory()
        
    class Post(Table):
        metadata = md
        __tablename__ = "posts"
        id = Column(UInt64(), primary_key=True)
        user_id = Column(UInt64())
        engine = Memory()
        
    # Check registry
    assert "users" in md.tables
    assert "posts" in md.tables
    assert md.tables["users"].name == "users"
    assert md.tables["posts"].name == "posts"

def test_metadata_create_all():
    md = MetaData()
    
    class Log(Table):
        metadata = md
        __tablename__ = "logs"
        id = Column(UInt64(), primary_key=True)
        message = Column(String())
        engine = Memory()
        
    mock_engine = MagicMock()
    md.create_all(mock_engine)
    
    # Check execution
    assert mock_engine.execute.called
    args, _ = mock_engine.execute.call_args
    assert "CREATE TABLE IF NOT EXISTS logs" in args[0]
    assert "ENGINE = Memory" in args[0]

def test_default_metadata():
    # Helper to avoid global state pollution across tests if Table.metadata is shared
    
    # We need to access the default metadata
    # Table.metadata is created at class definition level
    default_metadata = Table.metadata
    
    # It might be polluted by other tests importing Table, so we clear it
    default_metadata.clear()
    
    class DefaultTable(Table):
        __tablename__ = "default_table"
        id = Column(UInt64(), primary_key=True)
        engine = Memory()
        
    assert "default_table" in default_metadata.tables
