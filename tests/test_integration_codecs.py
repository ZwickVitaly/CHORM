import pytest
import pytest
import sys
# Ensure we use real clickhouse_connect, not a mock
if "clickhouse_connect" in sys.modules:
    module = sys.modules["clickhouse_connect"]
    # Mocks typically don't have __file__ or it's None
    if not hasattr(module, "__file__") or getattr(module, "__file__", None) is None:
        del sys.modules["clickhouse_connect"]
import clickhouse_connect
import os
import uuid
from chorm import Table, Column, MergeTree, create_engine
from chorm.types import UInt64, String, Float64
from chorm.codecs import Delta, ZSTD, LZ4, DoubleDelta, Gorilla
from chorm.introspection import TableIntrospector, ModelGenerator

# Use same env vars as other tests
HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
DB = os.getenv("CLICKHOUSE_DB", "default")
USER = os.getenv("CLICKHOUSE_USER", "default")
PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "123")

@pytest.fixture(scope="module")
def client():
    client = clickhouse_connect.get_client(
        host=HOST, port=PORT, database=DB, username=USER, password=PASSWORD
    )
    yield client
    client.close()

@pytest.fixture(scope="module")
def engine():
    return create_engine(
        host=HOST, port=PORT, database=DB, username=USER, password=PASSWORD
    )

def test_codec_lifecycle(client, engine):
    table_name = f"test_codec_integration_{uuid.uuid4().hex}"
    
    # 1. Define Model
    class PhysicsData(Table):
        __tablename__ = table_name
        __engine__ = MergeTree()
        __order_by__ = ["timestamp"]
        
        timestamp = Column(UInt64(), codec=Delta(8) | ZSTD(1))
        temperature = Column(Float64(), codec=Gorilla() | LZ4())
        device_id = Column(String(), codec=ZSTD(3))

    # 2. Create Table
    # Drop if exists (cleanup)
    client.command(f"DROP TABLE IF EXISTS {table_name}")
    
    # Generate and execute DDL
    # Generate and execute DDL
    ddl = PhysicsData.create_table()
    client.command(ddl)
    
    # Wait for metadata propagation
    import time
    time.sleep(1)
    
    try:
        # 3. Verify in System Tables
        # Get current database to be sure
        current_db = client.query("SELECT currentDatabase()").result_rows[0][0]
        print(f"DEBUG: Current Database: {current_db}")

        # Check compression_codec in system.columns
        result = client.query(f"""
            SELECT name, compression_codec 
            FROM system.columns 
            WHERE table = '{table_name}' AND database = '{current_db}'
            ORDER BY name
        """)
        
        columns_codecs = {row[0]: row[1] for row in result.result_rows}
        
        # Note: ClickHouse canonicalizes codecs, e.g. Delta(8) might become Delta and ZSTD(1) might become ZSTD(1)
        # We check for substring presence as exact string match depends on CH version
        print(f"DEBUG: Actual codecs in DB: {columns_codecs}")
        
        assert "Delta" in columns_codecs["timestamp"]
        assert "ZSTD" in columns_codecs["timestamp"]
        
        assert "Gorilla" in columns_codecs["temperature"]
        assert "LZ4" in columns_codecs["temperature"]

        assert "ZSTD" in columns_codecs["device_id"]

        # 4. Introspect
        introspector = TableIntrospector(client)
        table_info = introspector.get_table_info(table_name, current_db)
        
        generator = ModelGenerator()
        code = generator.generate_file([table_info])
        
        print(f"DEBUG: Generated Code:\n{code}")
        
        # 5. Verify Generated Code
        assert "from chorm.codecs import" in code
        assert "Delta" in code
        assert "ZSTD" in code
        assert "Gorilla" in code
        assert "LZ4" in code
        
        # Check specific field definitions
        # timestamp
        # Logic matches Delta(8) | ZSTD(1) or similar. 
        # Since we parse what CH returns, and CH returns "CODEC(Delta(8), ZSTD(1))", 
        # our parser should produce "Delta(8) | ZSTD(1)"
        
        # Use simple string check for presence of piped codecs
        assert "codec=Delta" in code
        assert "| ZSTD" in code  # Pipeline structure
        
        assert "codec=Gorilla" in code
        assert "| LZ4" in code

    finally:
        # Cleanup
        client.command(f"DROP TABLE IF EXISTS {table_name}")
