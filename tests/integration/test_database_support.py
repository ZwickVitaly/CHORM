"""Integration tests for database support (__database__ attribute).

Tests CREATE/DROP DATABASE and TABLE operations with qualified names.
"""

import os
import pytest

# Skip if ClickHouse not available
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "123")

try:
    from chorm import create_engine, Session, Table, Column
    from chorm.types import UInt64, String
    from chorm.table_engines import MergeTree
    from chorm.sql.ddl import create_database, drop_database, drop_table
    from chorm.sql import select, insert
    
    engine = create_engine(
        f"clickhouse://{CLICKHOUSE_HOST}:8123/default",
        username="default",
        password=CLICKHOUSE_PASSWORD,
    )
    # Quick connectivity check
    with engine.connect() as conn:
        conn.execute("SELECT 1")
    CLICKHOUSE_AVAILABLE = True
except Exception:
    CLICKHOUSE_AVAILABLE = False


pytestmark = pytest.mark.skipif(
    not CLICKHOUSE_AVAILABLE,
    reason="ClickHouse not available"
)


TEST_DB_NAME = "chorm_test_db"


@pytest.fixture(scope="module")
def session():
    """Create session for tests."""
    engine = create_engine(
        f"clickhouse://{CLICKHOUSE_HOST}:8123/default",
        username="default",
        password=CLICKHOUSE_PASSWORD,
    )
    with engine.connect() as conn:
        yield Session(engine)


@pytest.fixture(scope="module", autouse=True)
def setup_test_database(session):
    """Create test database before tests, drop after."""
    # Cleanup before
    session.execute(drop_database(TEST_DB_NAME, if_exists=True).to_sql())
    
    # Create test database
    session.execute(create_database(TEST_DB_NAME, if_not_exists=True).to_sql())
    
    yield
    
    # Cleanup after
    session.execute(drop_database(TEST_DB_NAME, if_exists=True).to_sql())


class TestDatabaseDDL:
    """Test CREATE/DROP DATABASE operations."""
    
    def test_database_exists(self, session):
        """Verify test database was created."""
        result = session.execute(f"SHOW DATABASES LIKE '{TEST_DB_NAME}'")
        databases = [row[0] for row in result.all()]
        assert TEST_DB_NAME in databases
    
    def test_create_database_with_engine(self, session):
        """Test CREATE DATABASE with engine specification."""
        db_name = "chorm_test_atomic"
        session.execute(drop_database(db_name, if_exists=True).to_sql())
        
        stmt = create_database(db_name, if_not_exists=True, engine="Atomic")
        session.execute(stmt.to_sql())
        
        result = session.execute(f"SHOW DATABASES LIKE '{db_name}'")
        databases = [row[0] for row in result.all()]
        assert db_name in databases
        
        # Cleanup
        session.execute(drop_database(db_name, if_exists=True).to_sql())


class TestTableWithDatabase:
    """Test tables with __database__ attribute."""
    
    def test_create_table_with_database(self, session):
        """Test CREATE TABLE in specific database."""
        
        class TestProduct(Table):
            __tablename__ = "products"
            __database__ = TEST_DB_NAME
            __engine__ = MergeTree()
            __order_by__ = ["id"]
            
            id = Column(UInt64(), primary_key=True)
            name = Column(String())
        
        # Check qualified_name
        assert TestProduct.__table__.qualified_name == f"{TEST_DB_NAME}.products"
        
        # Drop if exists
        session.execute(drop_table(f"{TEST_DB_NAME}.products", if_exists=True).to_sql())
        
        # Create table
        ddl = TestProduct.create_table()
        assert f"CREATE TABLE {TEST_DB_NAME}.products" in ddl
        session.execute(ddl)
        
        # Verify table exists
        result = session.execute(f"SHOW TABLES FROM {TEST_DB_NAME} LIKE 'products'")
        tables = [row[0] for row in result.all()]
        assert "products" in tables
        
        # Cleanup
        session.execute(drop_table(f"{TEST_DB_NAME}.products", if_exists=True).to_sql())
    
    def test_insert_select_with_database(self, session):
        """Test INSERT and SELECT with qualified table names."""
        
        class TestItem(Table):
            __tablename__ = "items"
            __database__ = TEST_DB_NAME
            __engine__ = MergeTree()
            __order_by__ = ["id"]
            
            id = Column(UInt64(), primary_key=True)
            name = Column(String())
        
        # Create table
        session.execute(drop_table(f"{TEST_DB_NAME}.items", if_exists=True).to_sql())
        session.execute(TestItem.create_table())
        
        # Insert data
        stmt = insert(TestItem).values(id=1, name="Widget")
        assert f"INSERT INTO {TEST_DB_NAME}.items" in stmt.to_sql()
        session.execute(stmt.to_sql())
        
        # Select data
        stmt = select(TestItem.id, TestItem.name).where(TestItem.id == 1)
        sql = stmt.to_sql()
        assert f"FROM {TEST_DB_NAME}.items" in sql
        assert f"{TEST_DB_NAME}.items.id" in sql
        
        result = session.execute(sql)
        rows = result.all()
        assert len(rows) == 1
        assert rows[0][0] == 1
        assert rows[0][1] == "Widget"
        
        # Cleanup
        session.execute(drop_table(f"{TEST_DB_NAME}.items", if_exists=True).to_sql())
    
    def test_table_without_database_uses_default(self, session):
        """Test that tables without __database__ work in default database."""
        
        class DefaultTable(Table):
            __tablename__ = "test_default_table"
            __engine__ = MergeTree()
            __order_by__ = ["id"]
            
            id = Column(UInt64(), primary_key=True)
        
        # Check no database prefix
        assert DefaultTable.__table__.qualified_name == "test_default_table"
        
        ddl = DefaultTable.create_table()
        assert "CREATE TABLE test_default_table" in ddl
        assert f"{TEST_DB_NAME}" not in ddl
        
        # Create and cleanup in default database
        session.execute(drop_table("test_default_table", if_exists=True).to_sql())
        session.execute(ddl)
        session.execute(drop_table("test_default_table", if_exists=True).to_sql())


class TestDropTableProtection:
    """Test smart DROP TABLE with size protection handling."""
    
    def test_drop_table_normal(self, session):
        """Test normal DROP TABLE works."""
        
        class TempTable(Table):
            __tablename__ = "temp_drop_test"
            __database__ = TEST_DB_NAME
            __engine__ = MergeTree()
            __order_by__ = ["id"]
            
            id = Column(UInt64(), primary_key=True)
        
        # Create table
        session.execute(drop_table(f"{TEST_DB_NAME}.temp_drop_test", if_exists=True).to_sql())
        session.execute(TempTable.create_table())
        
        # Verify exists
        result = session.execute(f"SHOW TABLES FROM {TEST_DB_NAME} LIKE 'temp_drop_test'")
        assert len(result.all()) == 1
        
        # Drop table
        session.execute(drop_table(f"{TEST_DB_NAME}.temp_drop_test", if_exists=True).to_sql())
        
        # Verify gone
        result = session.execute(f"SHOW TABLES FROM {TEST_DB_NAME} LIKE 'temp_drop_test'")
        assert len(result.all()) == 0
    
    def test_drop_table_with_settings(self, session):
        """Test DROP TABLE with max_table_size_to_drop setting."""
        stmt = drop_table(f"{TEST_DB_NAME}.nonexistent", if_exists=True, max_table_size_to_drop=0)
        sql = stmt.to_sql()
        assert "max_table_size_to_drop=0" in sql


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
