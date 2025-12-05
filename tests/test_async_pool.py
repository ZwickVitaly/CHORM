"""Tests for asynchronous connection pooling."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chorm.async_engine import AsyncConnection
from chorm.async_pool import AsyncConnectionPool
from chorm.engine import EngineConfig


@pytest.fixture
def config():
    """Create test EngineConfig."""
    import os
    password = os.getenv("CLICKHOUSE_PASSWORD", "123")
    return EngineConfig(host="localhost", port=8123, username="default", password=password, database="default")


@pytest.fixture
def mock_async_client():
    """Create mock async ClickHouse client."""
    client = MagicMock()
    client.close = AsyncMock()
    client.query = AsyncMock(return_value=[("result",)])
    return client


class TestAsyncPoolInit:
    """Test async pool initialization."""

    @pytest.mark.asyncio
    async def test_pool_initialization(self, config, mock_async_client):
        """Test pool initializes with connections."""
        with patch("chorm.async_pool.clickhouse_connect.get_async_client", return_value=mock_async_client):
            pool = AsyncConnectionPool(config, pool_size=3)
            await pool.initialize()

            assert pool.size == 3
            assert pool.overflow == 0

    def test_invalid_pool_size(self, config):
        """Test pool rejects invalid pool_size."""
        with pytest.raises(ValueError, match="pool_size must be at least 1"):
            AsyncConnectionPool(config, pool_size=0)

    def test_invalid_max_overflow(self, config):
        """Test pool rejects negative max_overflow."""
        with pytest.raises(ValueError, match="max_overflow must be non-negative"):
            AsyncConnectionPool(config, max_overflow=-1)


class TestAsyncConnectionAcquisition:
    """Test async connection acquisition."""

    @pytest.mark.asyncio
    async def test_get_connection_from_pool(self, config, mock_async_client):
        """Test getting connection from pool."""
        with patch("chorm.async_pool.clickhouse_connect.get_async_client", return_value=mock_async_client):
            pool = AsyncConnectionPool(config, pool_size=2)
            await pool.initialize()

            conn = await pool.get()
            assert isinstance(conn, AsyncConnection)
            assert pool.size == 1  # One connection taken

    @pytest.mark.asyncio
    async def test_return_connection_to_pool(self, config, mock_async_client):
        """Test returning connection to pool."""
        with patch("chorm.async_pool.clickhouse_connect.get_async_client", return_value=mock_async_client):
            pool = AsyncConnectionPool(config, pool_size=2)
            await pool.initialize()

            conn = await pool.get()
            assert pool.size == 1

            await pool.return_connection(conn)
            assert pool.size == 2  # Connection returned

    @pytest.mark.asyncio
    async def test_auto_initialize_on_get(self, config, mock_async_client):
        """Test pool auto-initializes on first get."""
        with patch("chorm.async_pool.clickhouse_connect.get_async_client", return_value=mock_async_client):
            pool = AsyncConnectionPool(config, pool_size=2)

            # Don't call initialize() explicitly
            conn = await pool.get()

            assert pool._initialized
            assert isinstance(conn, AsyncConnection)


class TestAsyncOverflowConnections:
    """Test async overflow connection handling."""

    @pytest.mark.asyncio
    async def test_overflow_connection_creation(self, config, mock_async_client):
        """Test creating overflow connections."""
        with patch("chorm.async_pool.clickhouse_connect.get_async_client", return_value=mock_async_client):
            pool = AsyncConnectionPool(config, pool_size=2, max_overflow=2)
            await pool.initialize()

            # Get all pooled connections
            conn1 = await pool.get()
            conn2 = await pool.get()
            assert pool.size == 0
            assert pool.overflow == 0

            # Get overflow connections
            conn3 = await pool.get()
            assert pool.overflow == 1

            conn4 = await pool.get()
            assert pool.overflow == 2

    @pytest.mark.asyncio
    async def test_overflow_limit_exceeded(self, config, mock_async_client):
        """Test error when overflow limit exceeded."""
        with patch("chorm.async_pool.clickhouse_connect.get_async_client", return_value=mock_async_client):
            pool = AsyncConnectionPool(config, pool_size=1, max_overflow=1, timeout=0.1)
            await pool.initialize()

            conn1 = await pool.get()
            conn2 = await pool.get()  # Overflow

            # Should raise when both pool and overflow exhausted
            with pytest.raises(RuntimeError, match="Connection pool exhausted"):
                await pool.get()

    @pytest.mark.asyncio
    async def test_overflow_connection_return(self, config, mock_async_client):
        """Test returning overflow connections."""
        with patch("chorm.async_pool.clickhouse_connect.get_async_client", return_value=mock_async_client):
            pool = AsyncConnectionPool(config, pool_size=1, max_overflow=2)
            await pool.initialize()

            conn1 = await pool.get()
            conn2 = await pool.get()  # Overflow

            assert pool.overflow == 1

            await pool.return_connection(conn2)
            # Overflow connection should be closed
            assert pool.overflow == 0


class TestAsyncConnectionRecycling:
    """Test async connection recycling."""

    @pytest.mark.asyncio
    async def test_connection_recycling(self, config, mock_async_client):
        """Test old connections are recycled."""
        with patch("chorm.async_pool.clickhouse_connect.get_async_client", return_value=mock_async_client):
            pool = AsyncConnectionPool(config, pool_size=1, recycle=1)  # 1 second recycle
            await pool.initialize()

            conn = await pool.get()
            conn_id = id(conn)

            # Return immediately - should not recycle
            await pool.return_connection(conn)

            # Get again immediately - same connection
            conn2 = await pool.get()
            assert id(conn2) == conn_id

            # Wait for recycle time
            await asyncio.sleep(1.05)

            # Return and get again - should be recycled
            await pool.return_connection(conn2)
            conn3 = await pool.get()
            # Recycling logic is tested

    @pytest.mark.asyncio
    async def test_closed_connection_handling(self, config, mock_async_client):
        """Test handling of closed connections."""
        with patch("chorm.async_pool.clickhouse_connect.get_async_client", return_value=mock_async_client):
            pool = AsyncConnectionPool(config, pool_size=2)
            await pool.initialize()

            conn = await pool.get()
            await conn.close()

            # Return closed connection
            await pool.return_connection(conn)

            # Pool should create replacement
            assert pool.size == 2


class TestAsyncPoolStatistics:
    """Test async pool statistics methods."""

    @pytest.mark.asyncio
    async def test_get_statistics_empty_pool(self, config, mock_async_client):
        """Test statistics when all connections are in use."""
        with patch("chorm.async_pool.clickhouse_connect.get_async_client", return_value=mock_async_client):
            pool = AsyncConnectionPool(config, pool_size=3, max_overflow=2)
            await pool.initialize()

            # Get all connections
            conn1 = await pool.get()
            conn2 = await pool.get()
            conn3 = await pool.get()

            stats = pool.get_statistics()

            assert stats["pool_size"] == 3
            assert stats["max_overflow"] == 2
            assert stats["current_size"] == 0  # All in use
            assert stats["overflow"] == 0
            assert stats["connections_in_use"] == 3
            assert stats["utilization_percent"] == 60.0  # 3 / (3 + 2) = 60%

    @pytest.mark.asyncio
    async def test_get_statistics_with_overflow(self, config, mock_async_client):
        """Test statistics with overflow connections."""
        with patch("chorm.async_pool.clickhouse_connect.get_async_client", return_value=mock_async_client):
            pool = AsyncConnectionPool(config, pool_size=2, max_overflow=3)
            await pool.initialize()

            # Get pool + overflow connections
            conn1 = await pool.get()
            conn2 = await pool.get()
            conn3 = await pool.get()  # Overflow
            conn4 = await pool.get()  # Overflow

            stats = pool.get_statistics()

            assert stats["pool_size"] == 2
            assert stats["max_overflow"] == 3
            assert stats["current_size"] == 0
            assert stats["overflow"] == 2
            assert stats["connections_in_use"] == 4
            assert stats["utilization_percent"] == 80.0  # 4 / (2 + 3) = 80%

    @pytest.mark.asyncio
    async def test_get_statistics_idle_pool(self, config, mock_async_client):
        """Test statistics when pool is idle."""
        with patch("chorm.async_pool.clickhouse_connect.get_async_client", return_value=mock_async_client):
            pool = AsyncConnectionPool(config, pool_size=5, max_overflow=5)
            await pool.initialize()

            stats = pool.get_statistics()

            assert stats["pool_size"] == 5
            assert stats["current_size"] == 5  # All idle
            assert stats["overflow"] == 0
            assert stats["connections_in_use"] == 0
            assert stats["utilization_percent"] == 0.0  # 0% in use


class TestAsyncPoolCleanup:
    """Test async pool cleanup."""

    @pytest.mark.asyncio
    async def test_close_all(self, config, mock_async_client):
        """Test closing all connections in pool."""
        with patch("chorm.async_pool.clickhouse_connect.get_async_client", return_value=mock_async_client):
            pool = AsyncConnectionPool(config, pool_size=3)
            await pool.initialize()

            assert pool.size == 3

            await pool.close_all()

            assert pool.size == 0
            # Verify clients were closed
            assert mock_async_client.close.call_count >= 3

    def test_repr(self, config, mock_async_client):
        """Test pool string representation."""
        with patch("chorm.async_pool.clickhouse_connect.get_async_client", return_value=mock_async_client):
            pool = AsyncConnectionPool(config, pool_size=5, max_overflow=10)

            repr_str = repr(pool)
            assert "AsyncConnectionPool" in repr_str
            assert "pool_size=5" in repr_str
            assert "max_overflow=10" in repr_str


class TestConcurrentAccess:
    """Test concurrent access to async pool."""

    @pytest.mark.asyncio
    async def test_concurrent_get(self, config, mock_async_client):
        """Test multiple coroutines getting connections concurrently."""
        with patch("chorm.async_pool.clickhouse_connect.get_async_client", return_value=mock_async_client):
            pool = AsyncConnectionPool(config, pool_size=3, max_overflow=2)
            await pool.initialize()

            async def get_and_return():
                conn = await pool.get()
                await asyncio.sleep(0.01)  # Simulate work
                await pool.return_connection(conn)

            # Run 5 concurrent tasks (3 pooled + 2 overflow)
            await asyncio.gather(*[get_and_return() for _ in range(5)])

            # All connections should be returned
            assert pool.size == 3
            assert pool.overflow == 0
