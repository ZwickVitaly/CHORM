"""Tests for connection context managers."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from chorm.engine import create_engine
from chorm.async_engine import create_async_engine


class TestSyncConnectionContextManager:
    """Test sync connection context manager."""

    def test_context_manager_without_pooling(self):
        """Test context manager closes connection when pooling disabled."""
        with patch("chorm.engine.clickhouse_connect.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            engine = create_engine("clickhouse://localhost:8123/default")

            with engine.connection() as conn:
                assert conn is not None
                result = conn.query("SELECT 1")

            # Connection should be closed
            mock_client.close.assert_called_once()

    def test_context_manager_with_pooling(self):
        """Test context manager returns connection to pool."""
        with patch("chorm.pool.clickhouse_connect.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            engine = create_engine("clickhouse://localhost:8123/default", pool_size=2)

            # Pool should have 2 connections
            assert engine.pool.size == 2

            with engine.connection() as conn:
                assert conn is not None
                # Pool should have 1 connection (one in use)
                assert engine.pool.size == 1

            # Connection should be returned to pool
            assert engine.pool.size == 2

    def test_context_manager_exception_handling(self):
        """Test context manager returns connection even on exception."""
        with patch("chorm.pool.clickhouse_connect.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            engine = create_engine("clickhouse://localhost:8123/default", pool_size=2)

            try:
                with engine.connection() as conn:
                    assert engine.pool.size == 1
                    raise ValueError("Test exception")
            except ValueError:
                pass

            # Connection should still be returned to pool
            assert engine.pool.size == 2

    def test_multiple_context_managers(self):
        """Test multiple concurrent context managers."""
        with patch("chorm.pool.clickhouse_connect.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            engine = create_engine("clickhouse://localhost:8123/default", pool_size=3)

            with engine.connection() as conn1:
                assert engine.pool.size == 2

                with engine.connection() as conn2:
                    assert engine.pool.size == 1
                    assert conn1 is not conn2

                # conn2 returned
                assert engine.pool.size == 2

            # conn1 returned
            assert engine.pool.size == 3


class TestAsyncConnectionContextManager:
    """Test async connection context manager."""

    @pytest.mark.asyncio
    async def test_async_context_manager_without_pooling(self):
        """Test async context manager closes connection when pooling disabled."""
        with patch("chorm.async_engine.clickhouse_connect.get_async_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.close = AsyncMock()
            mock_get_client.return_value = mock_client

            engine = create_async_engine("clickhouse://localhost:8123/default")

            async with engine.connection() as conn:
                assert conn is not None

            # Connection should be closed
            mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_context_manager_with_pooling(self):
        """Test async context manager returns connection to pool."""
        with patch("chorm.async_pool.clickhouse_connect.get_async_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.close = AsyncMock()
            mock_get_client.return_value = mock_client

            engine = create_async_engine("clickhouse://localhost:8123/default", pool_size=2)

            # Initialize pool
            await engine.pool.initialize()
            assert engine.pool.size == 2

            async with engine.connection() as conn:
                assert conn is not None
                # Pool should have 1 connection (one in use)
                assert engine.pool.size == 1

            # Connection should be returned to pool
            assert engine.pool.size == 2

    @pytest.mark.asyncio
    async def test_async_context_manager_exception_handling(self):
        """Test async context manager returns connection even on exception."""
        with patch("chorm.async_pool.clickhouse_connect.get_async_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.close = AsyncMock()
            mock_get_client.return_value = mock_client

            engine = create_async_engine("clickhouse://localhost:8123/default", pool_size=2)

            await engine.pool.initialize()

            try:
                async with engine.connection() as conn:
                    assert engine.pool.size == 1
                    raise ValueError("Test exception")
            except ValueError:
                pass

            # Connection should still be returned to pool
            assert engine.pool.size == 2

    @pytest.mark.asyncio
    async def test_async_multiple_context_managers(self):
        """Test multiple concurrent async context managers."""
        with patch("chorm.async_pool.clickhouse_connect.get_async_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.close = AsyncMock()
            mock_get_client.return_value = mock_client

            engine = create_async_engine("clickhouse://localhost:8123/default", pool_size=3)

            await engine.pool.initialize()

            async with engine.connection() as conn1:
                assert engine.pool.size == 2

                async with engine.connection() as conn2:
                    assert engine.pool.size == 1
                    assert conn1 is not conn2

                # conn2 returned
                assert engine.pool.size == 2

            # conn1 returned
            assert engine.pool.size == 3
