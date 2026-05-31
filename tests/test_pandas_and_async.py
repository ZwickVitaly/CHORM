from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from chorm import Column, MergeTree, Session, Table, create_engine
from chorm.async_engine import create_async_engine
from chorm.async_session import AsyncSession
from chorm.result import Row
from chorm.types import Int32

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
    assert isinstance(tuples[0], tuple) or isinstance(
        tuples[0], list
    )  # clickhouse-connect might return list of lists or tuples
    assert tuples[0][0] == 1


def test_session_context_manager():
    """Test sync Session context manager commit/rollback/close logic."""
    mock_bind = MagicMock()
    session = Session(mock_bind)

    with (
        patch.object(session, "commit") as mock_commit,
        patch.object(session, "rollback") as mock_rollback,
        patch.object(session, "close") as mock_close,
    ):
        with session as s:
            assert s is session

        mock_commit.assert_called_once()
        mock_rollback.assert_not_called()
        mock_close.assert_called_once()

    # Test rollback on exception
    session = Session(mock_bind)
    with (
        patch.object(session, "commit") as mock_commit,
        patch.object(session, "rollback") as mock_rollback,
        patch.object(session, "close") as mock_close,
    ):
        with pytest.raises(ValueError):
            with session:
                raise ValueError("Oops")

        mock_commit.assert_not_called()
        mock_rollback.assert_called_once()
        mock_close.assert_called_once()


@pytest.mark.asyncio
async def test_async_session_execute_routing_and_parameters():
    """Test AsyncSession.execute query routing and parameter passing."""
    mock_bind = MagicMock()
    mock_query_result = MagicMock()
    mock_query_result.result_rows = [("result",)]
    mock_query_result.column_names = ["table"]
    mock_bind.query = AsyncMock(return_value=mock_query_result)
    mock_bind.execute = AsyncMock()

    session = AsyncSession(mock_bind)

    # 1. Test SHOW query routing
    res = await session.execute("SHOW TABLES")
    mock_bind.query.assert_called_once_with("SHOW TABLES")
    assert res.scalars().all() == ["result"]
    mock_bind.query.reset_mock()

    # 2. Test EXPLAIN query routing
    await session.execute("EXPLAIN SELECT 1")
    mock_bind.query.assert_called_once_with("EXPLAIN SELECT 1")
    mock_bind.query.reset_mock()

    # 3. Test parameter passing with raw SQL query
    params = {"id": 42}
    await session.execute("SELECT * FROM users WHERE id = %(id)s", parameters=params)
    mock_bind.query.assert_called_once_with("SELECT * FROM users WHERE id = %(id)s", parameters=params)
    mock_bind.query.reset_mock()

    # 4. Test parameter passing with raw SQL command
    await session.execute("ALTER TABLE users DELETE WHERE id = %(id)s", parameters=params)
    mock_bind.execute.assert_called_once_with("ALTER TABLE users DELETE WHERE id = %(id)s", parameters=params)


@pytest.mark.asyncio
async def test_async_session_commit():
    """Test that AsyncSession.commit() correctly uses connection() and inserts pending instances."""

    class TestUser(Table):
        __tablename__ = "test_users"
        __order_by__ = ("id",)
        __engine__ = MergeTree()

        id = Column(Int32(), primary_key=True)
        age = Column(Int32())

    mock_bind = MagicMock()
    mock_conn = AsyncMock()
    mock_conn.insert = AsyncMock()

    # The context manager returned by connection() must yield mock_conn
    mock_conn_manager = AsyncMock()
    mock_conn_manager.__aenter__.return_value = mock_conn

    mock_bind.connection.return_value = mock_conn_manager

    session = AsyncSession(mock_bind)
    user = TestUser(id=1, age=25)
    session.add(user)

    await session.commit()

    # Verify connection() was called, confirming the fix
    mock_bind.connection.assert_called_once()
    mock_conn.insert.assert_called_once_with("test_users", [[1, 25]], column_names=["id", "age"])


@pytest.mark.asyncio
async def test_async_engine_old_driver_error():
    """Test that AsyncEngine raises EngineConfigurationError if clickhouse-connect has no get_async_client."""
    from chorm import create_async_engine
    from chorm.exceptions import EngineConfigurationError

    engine = create_async_engine("clickhouse://localhost")

    with patch("chorm.async_engine.clickhouse_connect") as mock_cc:
        # Mock clickhouse_connect to act as if get_async_client does not exist
        del mock_cc.get_async_client

        with pytest.raises(EngineConfigurationError) as exc_info:
            await engine._create_client()
        assert "Asynchronous features are not supported by your clickhouse-connect installation" in str(exc_info.value)


@pytest.mark.asyncio
async def test_async_engine_missing_async_extra_error():
    """Test that AsyncEngine raises EngineConfigurationError if aiohttp or other dependency is missing (ImportError)."""
    from chorm import create_async_engine
    from chorm.exceptions import EngineConfigurationError

    engine = create_async_engine("clickhouse://localhost")

    with patch("chorm.async_engine.clickhouse_connect") as mock_cc:
        mock_cc.get_async_client.side_effect = ImportError("No module named 'aiohttp'")

        with pytest.raises(EngineConfigurationError) as exc_info:
            await engine._create_client()
        assert "Asynchronous features require the 'async' extra" in str(exc_info.value)
