"""Health check utilities for monitoring ClickHouse connections."""

from __future__ import annotations

import time
from typing import Any, Dict

from chorm.async_engine import AsyncEngine
from chorm.engine import Engine


class HealthCheck:
    """Health check for ClickHouse connection.

    Provides utilities to check connection health, measure latency,
    and gather server information.

    Args:
        engine: Engine instance to check

    Example:
        >>> engine = create_engine("clickhouse://localhost:8123/default")
        >>> health = HealthCheck(engine)
        >>> if health.ping():
        ...     print("ClickHouse is reachable")
        >>> status = health.get_status()
        >>> print(f"Latency: {status['latency_ms']}ms")
    """

    def __init__(self, engine: Engine):
        self.engine = engine

    def ping(self, timeout: float = 5.0) -> bool:
        """Check if ClickHouse is reachable.

        Args:
            timeout: Timeout in seconds for the ping check

        Returns:
            True if ClickHouse responds, False otherwise

        Example:
            >>> health = HealthCheck(engine)
            >>> is_alive = health.ping(timeout=3.0)
        """
        try:
            with self.engine.connection() as conn:
                result = conn.query("SELECT 1")
                return result is not None and len(result.result_rows) > 0
        except Exception:
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get detailed health status including latency and server info.

        Returns:
            Dictionary with health status information:
            - status: "healthy" or "unhealthy"
            - latency_ms: Response time in milliseconds (if healthy)
            - version: ClickHouse version string (if healthy)
            - uptime_seconds: Server uptime in seconds (if healthy)
            - host: ClickHouse host
            - port: ClickHouse port
            - database: Default database
            - error: Error message (if unhealthy)

        Example:
            >>> health = HealthCheck(engine)
            >>> status = health.get_status()
            >>> if status['status'] == 'healthy':
            ...     print(f"Version: {status['version']}")
            ...     print(f"Latency: {status['latency_ms']}ms")
        """
        start_time = time.time()

        try:
            with self.engine.connection() as conn:
                # Ping to measure latency
                conn.query("SELECT 1")
                latency = time.time() - start_time

                # Get version
                version_result = conn.query("SELECT version()")
                version = version_result.result_rows[0][0] if version_result.result_rows else "unknown"

                # Get uptime
                uptime_result = conn.query("SELECT uptime()")
                uptime = uptime_result.result_rows[0][0] if uptime_result.result_rows else 0

                return {
                    "status": "healthy",
                    "latency_ms": round(latency * 1000, 2),
                    "version": version,
                    "uptime_seconds": uptime,
                    "host": self.engine.config.host,
                    "port": self.engine.config.port,
                    "database": self.engine.config.database,
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "host": self.engine.config.host,
                "port": self.engine.config.port,
                "database": self.engine.config.database,
            }

    def get_server_info(self) -> Dict[str, Any]:
        """Get comprehensive server information.

        Returns:
            Dictionary with server information including:
            - version: ClickHouse version
            - uptime_seconds: Server uptime
            - current_database: Current database
            - total_memory: Total memory available
            - used_memory: Memory currently in use

        Example:
            >>> health = HealthCheck(engine)
            >>> info = health.get_server_info()
            >>> print(f"Memory usage: {info['used_memory']} / {info['total_memory']}")
        """
        try:
            with self.engine.connection() as conn:
                info = {}

                # Version
                result = conn.query("SELECT version()")
                info["version"] = result.result_rows[0][0] if result.result_rows else "unknown"

                # Uptime
                result = conn.query("SELECT uptime()")
                info["uptime_seconds"] = result.result_rows[0][0] if result.result_rows else 0

                # Current database
                result = conn.query("SELECT currentDatabase()")
                info["current_database"] = result.result_rows[0][0] if result.result_rows else ""

                # Memory info (if available)
                try:
                    result = conn.query(
                        """
                        SELECT 
                            formatReadableSize(total_memory) as total,
                            formatReadableSize(memory_usage) as used
                        FROM system.asynchronous_metrics
                        WHERE metric IN ('TotalMemory', 'MemoryTracking')
                        LIMIT 2
                    """
                    )
                    if result.result_rows and len(result.result_rows) >= 1:
                        info["total_memory"] = result.result_rows[0][0]
                        info["used_memory"] = result.result_rows[0][1] if len(result.result_rows[0]) > 1 else "N/A"
                except Exception:
                    # Memory metrics might not be available
                    info["total_memory"] = "N/A"
                    info["used_memory"] = "N/A"

                return info
        except Exception as e:
            return {"error": str(e)}


class AsyncHealthCheck:
    """Async health check for ClickHouse connection.

    Provides async utilities to check connection health, measure latency,
    and gather server information.

    Args:
        engine: AsyncEngine instance to check

    Example:
        >>> engine = create_async_engine("clickhouse://localhost:8123/default")
        >>> health = AsyncHealthCheck(engine)
        >>> if await health.ping():
        ...     print("ClickHouse is reachable")
        >>> status = await health.get_status()
        >>> print(f"Latency: {status['latency_ms']}ms")
    """

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def ping(self, timeout: float = 5.0) -> bool:
        """Check if ClickHouse is reachable asynchronously.

        Args:
            timeout: Timeout in seconds for the ping check

        Returns:
            True if ClickHouse responds, False otherwise

        Example:
            >>> health = AsyncHealthCheck(engine)
            >>> is_alive = await health.ping(timeout=3.0)
        """
        try:
            async with self.engine.connection() as conn:
                result = await conn.query("SELECT 1")
                return result is not None and len(result.result_rows) > 0
        except Exception:
            return False

    async def get_status(self) -> Dict[str, Any]:
        """Get detailed health status including latency and server info asynchronously.

        Returns:
            Dictionary with health status information:
            - status: "healthy" or "unhealthy"
            - latency_ms: Response time in milliseconds (if healthy)
            - version: ClickHouse version string (if healthy)
            - uptime_seconds: Server uptime in seconds (if healthy)
            - host: ClickHouse host
            - port: ClickHouse port
            - database: Default database
            - error: Error message (if unhealthy)

        Example:
            >>> health = AsyncHealthCheck(engine)
            >>> status = await health.get_status()
            >>> if status['status'] == 'healthy':
            ...     print(f"Version: {status['version']}")
            ...     print(f"Latency: {status['latency_ms']}ms")
        """
        start_time = time.time()

        try:
            async with self.engine.connection() as conn:
                # Ping to measure latency
                await conn.query("SELECT 1")
                latency = time.time() - start_time

                # Get version
                version_result = await conn.query("SELECT version()")
                version = version_result.result_rows[0][0] if version_result.result_rows else "unknown"

                # Get uptime
                uptime_result = await conn.query("SELECT uptime()")
                uptime = uptime_result.result_rows[0][0] if uptime_result.result_rows else 0

                return {
                    "status": "healthy",
                    "latency_ms": round(latency * 1000, 2),
                    "version": version,
                    "uptime_seconds": uptime,
                    "host": self.engine.config.host,
                    "port": self.engine.config.port,
                    "database": self.engine.config.database,
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "host": self.engine.config.host,
                "port": self.engine.config.port,
                "database": self.engine.config.database,
            }

    async def get_server_info(self) -> Dict[str, Any]:
        """Get comprehensive server information asynchronously.

        Returns:
            Dictionary with server information including:
            - version: ClickHouse version
            - uptime_seconds: Server uptime
            - current_database: Current database
            - total_memory: Total memory available
            - used_memory: Memory currently in use

        Example:
            >>> health = AsyncHealthCheck(engine)
            >>> info = await health.get_server_info()
            >>> print(f"Memory usage: {info['used_memory']} / {info['total_memory']}")
        """
        try:
            async with self.engine.connection() as conn:
                info = {}

                # Version
                result = await conn.query("SELECT version()")
                info["version"] = result.result_rows[0][0] if result.result_rows else "unknown"

                # Uptime
                result = await conn.query("SELECT uptime()")
                info["uptime_seconds"] = result.result_rows[0][0] if result.result_rows else 0

                # Current database
                result = await conn.query("SELECT currentDatabase()")
                info["current_database"] = result.result_rows[0][0] if result.result_rows else ""

                # Memory info (if available)
                try:
                    result = await conn.query(
                        """
                        SELECT 
                            formatReadableSize(total_memory) as total,
                            formatReadableSize(memory_usage) as used
                        FROM system.asynchronous_metrics
                        WHERE metric IN ('TotalMemory', 'MemoryTracking')
                        LIMIT 2
                    """
                    )
                    if result.result_rows and len(result.result_rows) >= 1:
                        info["total_memory"] = result.result_rows[0][0]
                        info["used_memory"] = result.result_rows[0][1] if len(result.result_rows[0]) > 1 else "N/A"
                except Exception:
                    # Memory metrics might not be available
                    info["total_memory"] = "N/A"
                    info["used_memory"] = "N/A"

                return info
        except Exception as e:
            return {"error": str(e)}


# Public API
__all__ = [
    "HealthCheck",
    "AsyncHealthCheck",
]
