
import unittest
import sys
from unittest.mock import MagicMock

# Mock clickhouse_connect before importing chorm
mock_cc = MagicMock()
sys.modules["clickhouse_connect"] = mock_cc

from chorm import Table, Column, select, text
from chorm.types import UInt64, String
from chorm.table_engines import MaterializedView, MergeTree
from chorm.sql.selectable import Select
from chorm.exceptions import ConfigurationError

# Base tables
class User(Table):
    __tablename__ = "users"
    __engine__ = MergeTree()
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    age = Column(UInt64())

class TestStrictValidation(unittest.TestCase):
    def test_strict_validation_invalid_select_type(self):
        """Test that __select__ must be a Select object."""
        with self.assertRaises(ConfigurationError) as cm:
            class InvalidMV(Table):
                __tablename__ = "invalid_mv"
                __engine__ = MaterializedView()
                # String is forbidden
                __select__ = "SELECT * FROM users"
        
        self.assertIn("Must be a 'chorm.select()' object", str(cm.exception))

    def test_strict_validation_invalid_to_table_type(self):
        """Test that __to_table__ must be a Table class."""
        with self.assertRaises(ConfigurationError) as cm:
            class InvalidMV(Table):
                __tablename__ = "invalid_mv_2"
                __engine__ = MaterializedView()
                # String is forbidden
                __to_table__ = "users"
                __select__ = select(User.id).select_from(User)
                
        self.assertIn("Must be a Table class", str(cm.exception))

    def test_strict_validation_column_mismatch_to_table(self):
        """Test column mismatch when using __to_table__ (Scenario A)."""
        with self.assertRaises(ConfigurationError) as cm:
            class MismatchMV(Table):
                __tablename__ = "mismatch_mv"
                __engine__ = MaterializedView()
                __to_table__ = User
                # User has id, name, age (3 columns)
                # Query selects only id (1 column)
                __select__ = select(User.id).select_from(User)
                
        err = str(cm.exception)
        # self.assertIn("Column comparison failed", err) # Old message
        self.assertIn("Column count mismatch", err)
        self.assertIn("Expected 3 columns", err)
        self.assertIn("returns 1 columns", err)

    def test_strict_validation_column_name_mismatch(self):
        """Test specific column name/order mismatch."""
        with self.assertRaises(ConfigurationError) as cm:
            class MismatchNameMV(Table):
                __tablename__ = "mismatch_name_mv"
                __engine__ = MaterializedView()
                __to_table__ = User
                # User has: id, name, age
                # Query has: id, age, name (wrong order/names if aliases used)
                # select(User.age) -> column name is 'age'
                __select__ = select(
                    User.id,
                    User.age, # 2nd column expected 'name', got 'age'
                    User.name
                ).select_from(User)

        err = str(cm.exception)
        self.assertIn("Expected column 'name' at index 1", err)
        self.assertIn("Expected column 'name' at index 1", err)
        self.assertIn("got 'age'", err)

    def test_strict_validation_scenario_b_mismatch(self):
        """Test column mismatch when defining schema locally (Scenario B)."""
        with self.assertRaises(ConfigurationError) as cm:
            class InnerMV(Table):
                __tablename__ = "inner_mv"
                __engine__ = MaterializedView()
                
                # Local schema
                id = Column(UInt64())
                count = Column(UInt64())
                
                # Query selects only id
                __select__ = select(User.id).select_from(User)

        err = str(cm.exception)
        # self.assertIn("Column comparison failed", err)
        self.assertIn("Column count mismatch", err)
        self.assertIn("Expected 2 columns", err) # id, count
        self.assertIn("returns 1 columns", err)

    def test_strict_valid_scenario_a(self):
        """Test valid definition with strict matching (Scenario A)."""
        class ValidMV(Table):
            __tablename__ = "valid_mv_unittest"
            __engine__ = MaterializedView()
            __to_table__ = User
            
            # Must match id, name, age exactly
            __select__ = select(
                User.id,
                User.name,
                User.age
            ).select_from(User)
            
        self.assertEqual(ValidMV.__table__.to_table, "users")

    def test_strict_valid_scenario_b(self):
        """Test valid definition with strict matching (Scenario B)."""
        class ValidInnerMV(Table):
            __tablename__ = "valid_inner_mv_unittest"
            __engine__ = MaterializedView()
            
            # Define schema
            user_id = Column(UInt64())
            user_name = Column(String())
            
            # Query matching schema exactly
            # Note: We use labels to ensure names match if aliases are checked
            __select__ = select(
                User.id.label("user_id"),
                User.name.label("user_name")
            ).select_from(User)

        self.assertEqual(ValidInnerMV.__table__.columns[0].name, "user_id")
