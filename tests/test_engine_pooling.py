"""Tests for engine integration with connection pooling."""

import pytest
from unittest.mock import MagicMock, patch

from chorm.engine import create_engine, Engine
from chorm.pool import ConnectionPool


class TestEnginePooling:
    """Test engine with connection pooling enabled."""

    def test_engine_without_pooling(self):
        """Test engine without pooling (default behavior)."""
        engine = create_engine("clickhouse://localhost:8123/default")

        assert engine.pool is None
        assert isinstance(engine, Engine)

    def test_engine_with_pooling(self):
        """Test engine with pooling enabled."""
        engine = create_engine("clickhouse://localhost:8123/default", pool_size=10)

        assert engine.pool is not None
        assert isinstance(engine.pool, ConnectionPool)
        assert engine.pool._pool_size == 10
        assert engine.pool._max_overflow == 10  # default

    def test_engine_with_custom_pool_params(self):
        """Test engine with custom pool parameters."""
        engine = create_engine(
            "clickhouse://localhost:8123/default", pool_size=5, max_overflow=15, pool_timeout=60.0, pool_recycle=7200
        )

        assert engine.pool is not None
        assert engine.pool._pool_size == 5
        assert engine.pool._max_overflow == 15
        assert engine.pool._timeout == 60.0
        assert engine.pool._recycle == 7200

    def test_connect_with_pooling(self):
        """Test connect() uses pool when pooling enabled."""
        with patch("chorm.pool.clickhouse_connect.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            engine = create_engine("clickhouse://localhost:8123/default", pool_size=2)

            # Get connection - should come from pool
            conn1 = engine.connect()
            conn2 = engine.connect()

            # Pool should have 0 connections available
            assert engine.pool.size == 0

            # Return connections
            engine.pool.return_connection(conn1)
            engine.pool.return_connection(conn2)

            # Pool should have 2 connections again
            assert engine.pool.size == 2

    def test_connect_without_pooling(self):
        """Test connect() creates new connection when pooling disabled."""
        with patch("chorm.engine.clickhouse_connect.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            engine = create_engine("clickhouse://localhost:8123/default")

            conn1 = engine.connect()
            conn2 = engine.connect()

            # Should have created 2 separate clients
            assert mock_get_client.call_count == 2

    def test_pool_configuration_passed_to_pool(self):
        """Test that engine config is passed to pool."""
        with patch("chorm.pool.clickhouse_connect.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            engine = create_engine(
                "clickhouse://localhost:8123/default",  # Use default database
                username="testuser",
                password="testpass",
                connect_timeout=5,
                pool_size=10,
            )

            assert engine.pool is not None
            assert engine.pool._config.host == "localhost"
            assert engine.pool._config.port == 8123
            assert engine.pool._config.database == "default"
            assert engine.pool._config.username == "testuser"
            assert engine.pool._config.password == "testpass"
            assert engine.pool._config.connect_timeout == 5

    def test_pool_with_valid_connect_args(self):
        """Test pool receives valid connect_args."""
        engine = create_engine(
            "clickhouse://localhost:8123/default",
            pool_size=5,
            connect_args={"client_name": "test-client"},  # Valid parameter
        )

        assert engine.pool is not None
        assert engine.pool._connect_args == {"client_name": "test-client"}


class TestEnginePoolCleanup:
    """Test pool cleanup operations."""

    def test_pool_close_all(self):
        """Test closing all pool connections."""
        with patch("chorm.pool.clickhouse_connect.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            engine = create_engine("clickhouse://localhost:8123/default", pool_size=3)

            # Close all connections
            engine.pool.close_all()

            assert engine.pool.size == 0
            assert mock_client.close.call_count >= 3
