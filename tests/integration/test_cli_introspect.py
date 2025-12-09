import os
import pytest
from unittest.mock import patch
from chorm.cli import introspect
from chorm.session import Session
from chorm import create_engine

# Need a simple mock arguments class
class Args:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    
    def __getattr__(self, name):
        return self.__dict__.get(name, None)

@pytest.fixture
def db_config():
    return {
        "host": os.getenv("CLICKHOUSE_HOST", "localhost"),
        "port": int(os.getenv("CLICKHOUSE_PORT", "8123")),
        "database": os.getenv("CLICKHOUSE_DB", "default"),
        "user": "default",
        "password": os.getenv("CLICKHOUSE_PASSWORD", "123")
    }

@pytest.fixture
def setup_test_table(db_config):
    # Create a test table to ensure there is something to introspect
    engine = create_engine(
        host=db_config["host"],
        port=db_config["port"],
        database=db_config["database"],
        username=db_config["user"],
        password=db_config["password"]
    )
    session = Session(engine)
    session.execute("CREATE TABLE IF NOT EXISTS test_cli_introspect (id UInt64, name String) ENGINE = MergeTree() ORDER BY id")
    yield
    session.execute("DROP TABLE IF EXISTS test_cli_introspect")

def test_cli_introspect_run(db_config, setup_test_table, tmp_path):
    # Output file path
    output_file = tmp_path / "models.py"
    
    # Mock args
    args = Args(
        host=db_config["host"],
        port=db_config["port"],
        database=db_config["database"],
        user=db_config["user"],
        password=db_config["password"],
        output=str(output_file),
        tables=None # Introspect all to trigger get_tables()
    )
    
    # Run introspect
    # This calls get_tables() internally, which tripped the bug
    introspect(args)
    
    # Check if file was created and contains our table
    assert output_file.exists()
    content = output_file.read_text()
    assert "class TestCliIntrospect(Table):" in content
    assert "id = Column(UInt64())" in content
