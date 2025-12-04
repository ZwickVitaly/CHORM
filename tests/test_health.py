"""Tests for health check utilities."""

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch

from chorm.health import HealthCheck, AsyncHealthCheck
from chorm.engine import Engine, EngineConfig


@pytest.fixture
def mock_engine():
    """Create a mock engine for testing."""
    config = EngineConfig(host="localhost", port=8123, database="default")
    engine = Mock(spec=Engine)
    engine.config = config
    return engine


@pytest.fixture
def mock_async_engine():
    """Create a mock async engine for testing."""
    from chorm.async_engine import AsyncEngine

    config = EngineConfig(host="localhost", port=8123, database="default")
    engine = Mock(spec=AsyncEngine)
    engine.config = config
    return engine


class TestHealthCheck:
    """Test HealthCheck class."""

    def test_ping_success(self, mock_engine):
        """Test successful ping."""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.result_rows = [[1]]
        mock_conn.query.return_value = mock_result

        # Properly mock context manager
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_conn)
        mock_cm.__exit__ = MagicMock(return_value=False)
        mock_engine.connection.return_value = mock_cm

        health = HealthCheck(mock_engine)
        assert health.ping() is True

    def test_ping_failure(self, mock_engine):
        """Test ping failure."""
        mock_engine.connection.side_effect = Exception("Connection failed")

        health = HealthCheck(mock_engine)
        assert health.ping() is False

    def test_get_status_healthy(self, mock_engine):
        """Test get_status when healthy."""
        mock_conn = MagicMock()

        # Mock SELECT 1 (ping)
        ping_result = MagicMock()
        ping_result.result_rows = [[1]]

        # Mock SELECT version()
        version_result = MagicMock()
        version_result.result_rows = [["21.8.10.1"]]

        # Mock SELECT uptime()
        uptime_result = MagicMock()
        uptime_result.result_rows = [[3600]]

        mock_conn.query.side_effect = [ping_result, version_result, uptime_result]

        # Properly mock context manager
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_conn)
        mock_cm.__exit__ = MagicMock(return_value=False)
        mock_engine.connection.return_value = mock_cm

        health = HealthCheck(mock_engine)
        status = health.get_status()

        assert status["status"] == "healthy"
        assert "latency_ms" in status
        assert status["version"] == "21.8.10.1"
        assert status["uptime_seconds"] == 3600
        assert status["host"] == "localhost"
        assert status["port"] == 8123
        assert status["database"] == "default"

    def test_get_status_unhealthy(self, mock_engine):
        """Test get_status when unhealthy."""
        mock_engine.connection.side_effect = Exception("Connection failed")

        health = HealthCheck(mock_engine)
        status = health.get_status()

        assert status["status"] == "unhealthy"
        assert "error" in status
        assert status["error"] == "Connection failed"
        assert status["host"] == "localhost"
        assert status["port"] == 8123

    def test_get_server_info_success(self, mock_engine):
        """Test get_server_info with successful queries."""
        mock_conn = MagicMock()

        # Mock version()
        version_result = MagicMock()
        version_result.result_rows = [["21.8.10.1"]]

        # Mock uptime()
        uptime_result = MagicMock()
        uptime_result.result_rows = [[7200]]

        # Mock currentDatabase()
        db_result = MagicMock()
        db_result.result_rows = [["default"]]

        # Mock memory query
        memory_result = MagicMock()
        memory_result.result_rows = [["32.00 GiB", "4.50 GiB"]]

        mock_conn.query.side_effect = [version_result, uptime_result, db_result, memory_result]

        # Properly mock context manager
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_conn)
        mock_cm.__exit__ = MagicMock(return_value=False)
        mock_engine.connection.return_value = mock_cm

        health = HealthCheck(mock_engine)
        info = health.get_server_info()

        assert info["version"] == "21.8.10.1"
        assert info["uptime_seconds"] == 7200
        assert info["current_database"] == "default"
        assert info["total_memory"] == "32.00 GiB"
        assert info["used_memory"] == "4.50 GiB"

    def test_get_server_info_memory_unavailable(self, mock_engine):
        """Test get_server_info when memory info is unavailable."""
        mock_conn = MagicMock()

        # Mock basic queries
        version_result = MagicMock()
        version_result.result_rows = [["21.8.10.1"]]

        uptime_result = MagicMock()
        uptime_result.result_rows = [[7200]]

        db_result = MagicMock()
        db_result.result_rows = [["default"]]

        # Memory query fails
        mock_conn.query.side_effect = [
            version_result,
            uptime_result,
            db_result,
            Exception("Memory metrics not available"),
        ]

        # Properly mock context manager
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_conn)
        mock_cm.__exit__ = MagicMock(return_value=False)
        mock_engine.connection.return_value = mock_cm

        health = HealthCheck(mock_engine)
        info = health.get_server_info()

        assert info["version"] == "21.8.10.1"
        assert info["total_memory"] == "N/A"
        assert info["used_memory"] == "N/A"

    def test_get_server_info_failure(self, mock_engine):
        """Test get_server_info with connection failure."""
        mock_engine.connection.side_effect = Exception("Connection error")

        health = HealthCheck(mock_engine)
        info = health.get_server_info()

        assert "error" in info
        assert info["error"] == "Connection error"


class TestAsyncHealthCheck:
    """Test AsyncHealthCheck class."""

    @pytest.mark.asyncio
    async def test_ping_success(self, mock_async_engine):
        """Test successful async ping."""
        mock_conn = AsyncMock()
        mock_result = MagicMock()
        mock_result.result_rows = [[1]]
        mock_conn.query.return_value = mock_result

        # Properly mock async context manager
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_conn
        mock_async_engine.connection.return_value = mock_cm

        health = AsyncHealthCheck(mock_async_engine)
        assert await health.ping() is True

    @pytest.mark.asyncio
    async def test_ping_failure(self, mock_async_engine):
        """Test async ping failure."""
        mock_async_engine.connection.side_effect = Exception("Connection failed")

        health = AsyncHealthCheck(mock_async_engine)
        assert await health.ping() is False

    @pytest.mark.asyncio
    async def test_get_status_healthy(self, mock_async_engine):
        """Test async get_status when healthy."""
        mock_conn = AsyncMock()

        # Mock SELECT 1 (ping)
        ping_result = MagicMock()
        ping_result.result_rows = [[1]]

        # Mock SELECT version()
        version_result = MagicMock()
        version_result.result_rows = [["21.8.10.1"]]

        # Mock SELECT uptime()
        uptime_result = MagicMock()
        uptime_result.result_rows = [[3600]]

        mock_conn.query.side_effect = [ping_result, version_result, uptime_result]

        # Properly mock async context manager
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_conn
        mock_async_engine.connection.return_value = mock_cm

        health = AsyncHealthCheck(mock_async_engine)
        status = await health.get_status()

        assert status["status"] == "healthy"
        assert "latency_ms" in status
        assert status["version"] == "21.8.10.1"
        assert status["uptime_seconds"] == 3600
        assert status["host"] == "localhost"
        assert status["port"] == 8123
        assert status["database"] == "default"

    @pytest.mark.asyncio
    async def test_get_status_unhealthy(self, mock_async_engine):
        """Test async get_status when unhealthy."""
        mock_async_engine.connection.side_effect = Exception("Connection failed")

        health = AsyncHealthCheck(mock_async_engine)
        status = await health.get_status()

        assert status["status"] == "unhealthy"
        assert "error" in status
        assert status["error"] == "Connection failed"
        assert status["host"] == "localhost"
        assert status["port"] == 8123

    @pytest.mark.asyncio
    async def test_get_server_info_success(self, mock_async_engine):
        """Test async get_server_info with successful queries."""
        mock_conn = AsyncMock()

        # Mock version()
        version_result = MagicMock()
        version_result.result_rows = [["21.8.10.1"]]

        # Mock uptime()
        uptime_result = MagicMock()
        uptime_result.result_rows = [[7200]]

        # Mock currentDatabase()
        db_result = MagicMock()
        db_result.result_rows = [["default"]]

        # Mock memory query
        memory_result = MagicMock()
        memory_result.result_rows = [["32.00 GiB", "4.50 GiB"]]

        mock_conn.query.side_effect = [version_result, uptime_result, db_result, memory_result]

        # Properly mock async context manager
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_conn
        mock_async_engine.connection.return_value = mock_cm

        health = AsyncHealthCheck(mock_async_engine)
        info = await health.get_server_info()

        assert info["version"] == "21.8.10.1"
        assert info["uptime_seconds"] == 7200
        assert info["current_database"] == "default"
        assert info["total_memory"] == "32.00 GiB"
        assert info["used_memory"] == "4.50 GiB"

    @pytest.mark.asyncio
    async def test_get_server_info_failure(self, mock_async_engine):
        """Test async get_server_info with connection failure."""
        mock_async_engine.connection.side_effect = Exception("Connection error")

        health = AsyncHealthCheck(mock_async_engine)
        info = await health.get_server_info()

        assert "error" in info
        assert info["error"] == "Connection error"
