"""Asynchronous connection pooling for ClickHouse."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional

import clickhouse_connect

from chorm.async_engine import AsyncConnection
from chorm.engine import EngineConfig


class AsyncConnectionPool:
    """Async connection pool for ClickHouse clients.

    Manages a pool of reusable async connections with overflow support
    and automatic connection recycling based on age.

    Args:
        config: EngineConfig with connection parameters
        pool_size: Maximum number of pooled connections (default: 5)
        max_overflow: Maximum overflow connections beyond pool_size (default: 10)
        timeout: Timeout in seconds for acquiring connection (default: 30.0)
        recycle: Connection recycle time in seconds (default: 3600)
        connect_args: Additional connection arguments

    Example:
        >>> from chorm import EngineConfig
        >>> config = EngineConfig(host='localhost', port=8123)
        >>> pool = AsyncConnectionPool(config, pool_size=10)
        >>> await pool.initialize()
        >>> conn = await pool.get()
        >>> try:
        ...     result = await conn.query("SELECT 1")
        ... finally:
        ...     await pool.return_connection(conn)
    """

    def __init__(
        self,
        config: EngineConfig,
        pool_size: int = 5,
        max_overflow: int = 10,
        timeout: float = 30.0,
        recycle: int = 3600,
        pre_ping: bool = False,
        connect_args: Optional[Dict[str, Any]] = None,
    ):
        if pool_size < 1:
            raise ValueError("pool_size must be at least 1")
        if max_overflow < 0:
            raise ValueError("max_overflow must be non-negative")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if recycle <= 0:
            raise ValueError("recycle must be positive")

        self._config = config
        self._pool_size = pool_size
        self._max_overflow = max_overflow
        self._timeout = timeout
        self._recycle = recycle
        self._pre_ping = pre_ping
        self._connect_args = connect_args or {}

        # Async queue for pooled connections
        self._pool: asyncio.Queue = asyncio.Queue(maxsize=pool_size)

        # Track overflow connections
        self._overflow = 0
        self._overflow_lock = asyncio.Lock()

        # Track which connections are overflow connections
        self._overflow_connections: set = set()

        # Track connection creation times for recycling
        self._created_at: Dict[int, float] = {}

        # Initialization flag
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the pool by pre-creating connections.

        Should be called once before using the pool.
        """
        if self._initialized:
            return

        for _ in range(self._pool_size):
            conn = await self._create_connection()
            await self._pool.put(conn)

        self._initialized = True

    async def _create_connection(self) -> AsyncConnection:
        """Create a new async connection to ClickHouse.

        Returns:
            New AsyncConnection instance
        """
        client = await clickhouse_connect.get_async_client(
            host=self._config.host,
            port=self._config.port,
            username=self._config.username,
            password=self._config.password,
            database=self._config.database,
            secure=self._config.secure,
            connect_timeout=self._config.connect_timeout,
            send_receive_timeout=self._config.send_receive_timeout,
            compress=self._config.compress,
            query_limit=self._config.query_limit,
            verify=self._config.verify,
            settings=self._config.settings,
            **self._connect_args,
        )

        conn = AsyncConnection(client)

        # Track creation time for recycling
        self._created_at[id(conn)] = time.time()

        return conn

    async def _validate_connection(self, conn: AsyncConnection) -> bool:
        """Validate that a connection is still alive.

        Executes a lightweight query (SELECT 1).

        Args:
            conn: Connection to validate

        Returns:
            True if connection is alive, False otherwise
        """
        try:
            await conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    async def get(self) -> AsyncConnection:
        """Get a connection from the pool.

        Attempts to get a pooled connection. If pool is empty and overflow
        limit not reached, creates a new overflow connection.

        Returns:
            AsyncConnection instance

        Raises:
            RuntimeError: If pool is exhausted and timeout exceeded
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Try to get connection from pool without blocking
            conn = self._pool.get_nowait()

            # Check if connection needs recycling
            if self._should_recycle(conn):
                await conn.close()
                conn = await self._create_connection()
            elif self._pre_ping and not await self._validate_connection(conn):
                 # Connection dead, discard and create new one
                await conn.close()
                conn = await self._create_connection()

            return conn

        except asyncio.QueueEmpty:
            # Pool is empty, try to create overflow connection
            async with self._overflow_lock:
                if self._overflow < self._max_overflow:
                    self._overflow += 1
                    overflow_conn = await self._create_connection()
                    self._overflow_connections.add(id(overflow_conn))
                    return overflow_conn

            # No overflow available, wait for a connection with timeout
            try:
                conn = await asyncio.wait_for(self._pool.get(), timeout=self._timeout)

                # Check if connection needs recycling
                if self._should_recycle(conn):
                    await conn.close()
                    conn = await self._create_connection()
                elif self._pre_ping and not await self._validate_connection(conn):
                     # Connection dead, discard and create new one
                    await conn.close()
                    conn = await self._create_connection()

                return conn
            except asyncio.TimeoutError:
                # Pool exhausted and timeout exceeded
                raise RuntimeError(
                    f"Connection pool exhausted (pool_size={self._pool_size}, " f"max_overflow={self._max_overflow})"
                )

    async def return_connection(self, conn: AsyncConnection) -> None:
        """Return a connection to the pool.

        If connection is closed or pool is full, decrements overflow counter.
        Otherwise, returns connection to pool for reuse.

        Args:
            conn: Connection to return
        """
        # Check if this is an overflow connection
        conn_id = id(conn)
        is_overflow = conn_id in self._overflow_connections

        if conn.closed:
            # Connection is closed
            if is_overflow:
                # Was an overflow connection
                async with self._overflow_lock:
                    self._overflow -= 1
                self._overflow_connections.discard(conn_id)
            else:
                # Was a pooled connection, create replacement
                new_conn = await self._create_connection()
                try:
                    self._pool.put_nowait(new_conn)
                except asyncio.QueueFull:
                    # Pool is somehow full, close the new connection
                    await new_conn.close()

            # Clean up creation time tracking
            self._created_at.pop(conn_id, None)
        else:
            # Connection is still open
            if is_overflow:
                # Overflow connection - close it
                await conn.close()
                async with self._overflow_lock:
                    self._overflow -= 1
                self._overflow_connections.discard(conn_id)

                # Clean up creation time tracking
                self._created_at.pop(conn_id, None)
            else:
                # Pooled connection - return to pool
                try:
                    self._pool.put_nowait(conn)
                except asyncio.QueueFull:
                    # Pool is full somehow, close the connection
                    await conn.close()

                    # Clean up creation time tracking
                    self._created_at.pop(conn_id, None)

    def _should_recycle(self, conn: AsyncConnection) -> bool:
        """Check if connection should be recycled based on age.

        Args:
            conn: Connection to check

        Returns:
            True if connection should be recycled
        """
        created_at = self._created_at.get(id(conn), 0)
        age = time.time() - created_at
        return age > self._recycle

    async def close_all(self) -> None:
        """Close all connections in the pool.

        Drains the pool queue and closes all pooled connections.
        Does not affect overflow connections that are currently in use.
        """
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                await conn.close()

                # Clean up creation time tracking
                self._created_at.pop(id(conn), None)
            except asyncio.QueueEmpty:
                break

    @property
    def size(self) -> int:
        """Current number of connections in pool (not including overflow)."""
        return self._pool.qsize()

    @property
    def overflow(self) -> int:
        """Current number of overflow connections in use."""
        return self._overflow

    def get_statistics(self) -> Dict[str, Any]:
        """Get connection pool statistics.

        Returns:
            Dictionary with pool statistics:
            - pool_size: Configured pool size
            - max_overflow: Maximum overflow connections
            - current_size: Current number of connections in pool
            - overflow: Current number of overflow connections in use
            - total_connections: Total connections (pooled + overflow)
            - utilization: Pool utilization percentage (0-100)
        """
        current_size = self.size
        overflow = self.overflow
        total_connections = self._pool_size + overflow

        # Calculate utilization: how many connections are in use
        in_use = self._pool_size - current_size + overflow
        utilization = (in_use / (self._pool_size + self._max_overflow)) * 100

        return {
            "pool_size": self._pool_size,
            "max_overflow": self._max_overflow,
            "current_size": current_size,
            "overflow": overflow,
            "total_connections": total_connections,
            "connections_in_use": in_use,
            "utilization_percent": round(utilization, 2),
        }

    def __repr__(self) -> str:
        return (
            f"AsyncConnectionPool(pool_size={self._pool_size}, "
            f"max_overflow={self._max_overflow}, "
            f"current_size={self.size}, "
            f"overflow={self.overflow})"
        )
