
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import pandas as pd
from chorm import create_engine, Session
from chorm.async_engine import create_async_engine
from chorm.async_session import AsyncSession
from chorm.result import Result, Row

# Mock DataFrame
MOCK_DF = pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})

class MockSyncClient:
    def query(self, *args, **kwargs):
        # Return a mock result set for query
        # Mimic structure required by Result class
        mock_res = MagicMock()
        mock_res.result_rows = [(1, "Alice"), (2, "Bob")]
        mock_res.column_names = ["id", "name"]
        return mock_res

    def command(self, *args, **kwargs):
        return None

    def query_df(self, *args, **kwargs):
        return MOCK_DF

    def close(self):
        pass

class MockAsyncClient:
    async def query(self, *args, **kwargs):
        mock_res = MagicMock()
        mock_res.result_rows = [(1, "Alice"), (2, "Bob")]
        mock_res.column_names = ["id", "name"]
        return mock_res

    async def command(self, *args, **kwargs):
        return None

    async def query_df(self, *args, **kwargs):
        return MOCK_DF

    async def close(self):
        pass

@pytest.fixture
def mock_get_client():
    with patch("chorm.engine.clickhouse_connect.get_client", return_value=MockSyncClient()) as mock:
        yield mock

@pytest.fixture
def mock_get_async_client():
    with patch("chorm.async_engine.clickhouse_connect.get_async_client", return_value=MockAsyncClient()) as mock:
        yield mock

def test_sync_pandas_export(mock_get_client):
    """Test sync engine and session query_df."""
    engine = create_engine("clickhouse://localhost")
    session = Session(engine)

    # Test Engine.query_df
    df1 = engine.query_df("SELECT * FROM users")
    assert isinstance(df1, pd.DataFrame)
    assert df1.equals(MOCK_DF)

    # Test Session.query_df
    df2 = session.query_df("SELECT * FROM users")
    assert isinstance(df2, pd.DataFrame)
    assert df2.equals(MOCK_DF)

@pytest.mark.asyncio
async def test_async_pandas_export(mock_get_async_client):
    """Test async engine and session query_df."""
    engine = create_async_engine("clickhouse://localhost")
    session = AsyncSession(engine)

    # Test AsyncEngine.query_df
    df1 = await engine.query_df("SELECT * FROM users")
    assert isinstance(df1, pd.DataFrame)
    assert df1.equals(MOCK_DF)

    # Test AsyncSession.query_df
    df2 = await session.query_df("SELECT * FROM users")
    assert isinstance(df2, pd.DataFrame)
    assert df2.equals(MOCK_DF)

@pytest.mark.asyncio
async def test_async_lazy_iteration_and_tuples(mock_get_async_client):
    """Test async session result lazy iteration and tuples access."""
    engine = create_async_engine("clickhouse://localhost")
    session = AsyncSession(engine)

    # Execute returns a Result object
    result = await session.execute("SELECT * FROM users")
    
    # 1. Test Lazy Iteration (Row objects)
    rows = []
    for row in result:
        rows.append(row)
    
    assert len(rows) == 2
    assert isinstance(rows[0], Row)
    assert rows[0].id == 1
    assert rows[0].name == "Alice"
    
    # 2. Test Tuples (Raw data)
    # Note: re-using result might depend on implementation (if iterator consumed).
    # In Result implementation, .tuples() accesses _rows directly, so it should be safe even after iteration
    # IF _rows is a list (which it is for clickhouse-connect).
    tuples = result.tuples().all()
    assert len(tuples) == 2
    assert isinstance(tuples[0], tuple) or isinstance(tuples[0], list) # clickhouse-connect might return list of lists or tuples
    assert tuples[0][0] == 1
