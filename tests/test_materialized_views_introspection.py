
import unittest
import sys
from unittest.mock import MagicMock

# Mock clickhouse_connect before importing chorm
mock_cc = MagicMock()
sys.modules["clickhouse_connect"] = mock_cc

from chorm import Table, Column, select
from chorm.types import UInt64, String
from chorm.table_engines import MergeTree, MaterializedView
from chorm.declarative import TableMeta
from chorm.ddl import format_ddl
from chorm.introspection import ModelGenerator
from chorm.sql.selectable import Select

# 1. Define base table
class User(Table):
    __tablename__ = "users"
    __engine__ = MergeTree()
    id = Column(UInt64(), primary_key=True)
    name = Column(String())

# 2. Define MV with class references (Strict API)
class UserMV(Table):
    __tablename__ = "users_mv"
    __engine__ = MaterializedView()
    __to_table__ = User # Class reference
    __from_table__ = User # Class reference, auto-generates select
    # __select__ is auto-generated as Select().select_from(User)

class TestMVIntrospection(unittest.TestCase):
    def test_mv_strict_api_and_introspection(self):
        """Test strict declarative API and introspection."""
        
        # 1. Check Declarative State
        # --------------------------
        mv_table = UserMV.__table__
        
        # Check to_table resolution
        self.assertEqual(mv_table.to_table, "users")
        
        # Check select query generation (Must be Select object now)
        stmt = mv_table.select_query
        self.assertIsInstance(stmt, Select)
        self.assertEqual(stmt.to_sql(), "SELECT * FROM users")
        
        # Check DDL generation
        ddl = format_ddl(mv_table)
        # Expected: CREATE MATERIALIZED VIEW users_mv TO "users" AS SELECT * FROM users
        self.assertIn('CREATE MATERIALIZED VIEW', ddl)
        self.assertIn('users_mv', ddl)
        # to_table "users" might be quoted or not depending on impl
        self.assertTrue('TO "users"' in ddl or 'TO users' in ddl)
        self.assertIn('AS SELECT * FROM users', ddl)

        # 2. Test Introspection
        # ---------------------
        generator = ModelGenerator()
        
        tables_info = [
            {
                "name": "users",
                "engine": "MergeTree",
                "engine_full": "MergeTree()",
                "partition_key": "",
                "sorting_key": "id",
                "primary_key": "id",
                "create_query": "CREATE TABLE users ...",
                "columns": [
                    {"name": "id", "type": "UInt64", "default_kind": "", "default_expression": "", "comment": "", "codec": ""},
                    {"name": "name", "type": "String", "default_kind": "", "default_expression": "", "comment": "", "codec": ""}
                ]
            },
            {
                "name": "users_mv",
                "engine": "MaterializedView",
                # Introspection sees the raw CREATE statement
                "create_query": "CREATE MATERIALIZED VIEW users_mv TO users AS SELECT * FROM users",
                "partition_key": "",
                "sorting_key": "id",
                "primary_key": "id",
                "columns": [] 
            }
        ]
        
        # Generate file content
        code = generator.generate_file(tables_info)
        
        # Check that Users class is generated before UserMV (implied by sort)
        self.assertLess(code.find("class Users(Table):"), code.find("class UsersMv(Table):"))
        
        # Check generated MV code
        # Should use Users class reference in to_table (strict requirement)
        self.assertIn('__to_table__ = Users', code)
        self.assertIn('__engine__ = MaterializedView()', code)

    def test_from_table_string(self):
        """Test __from_table__ with string."""
        class SimpleMV(Table):
            __tablename__ = "simple_mv"
            __engine__ = MaterializedView()
            # Scenario B requires columns.
            dummy = Column(UInt64())
            
            __from_table__ = "source"
        
        stmt = SimpleMV.__table__.select_query
        self.assertIsInstance(stmt, Select)
        self.assertEqual(stmt.to_sql(), "SELECT * FROM source")
