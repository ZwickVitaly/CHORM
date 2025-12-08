"""Synchronous connection pooling for ClickHouse."""

from __future__ import annotations

import threading
import time
from queue import Empty, Queue
from typing import Any, Dict, Optional

import clickhouse_connect

from chorm.engine import Connection, EngineConfig


class ConnectionPool:
    """Thread-safe connection pool for ClickHouse clients.

    Manages a pool of reusable connections with overflow support and
    automatic connection recycling based on age.

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
        >>> pool = ConnectionPool(config, pool_size=10)
        >>> conn = pool.get()
        >>> try:
        ...     result = conn.query("SELECT 1")
        ... finally:
        ...     pool.return_connection(conn)
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

        # Thread-safe queue for pooled connections
        self._pool: Queue = Queue(maxsize=pool_size)

        # Track overflow connections
        self._overflow = 0
        self._overflow_lock = threading.Lock()

        # Track which connections are overflow connections
        self._overflow_connections: set = set()

        # Track connection creation times for recycling
        self._created_at: Dict[int, float] = {}
        self._created_lock = threading.Lock()

        # Pre-populate pool with connections
        for _ in range(pool_size):
            conn = self._create_connection()
            self._pool.put(conn)

    def _create_connection(self) -> Connection:
        """Create a new connection to ClickHouse.

        Returns:
            New Connection instance
        """
        client = clickhouse_connect.get_client(
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

        conn = Connection(client)

        # Track creation time for recycling
        with self._created_lock:
            self._created_at[id(conn)] = time.time()

        return conn


    def _validate_connection(self, conn: Connection) -> bool:
        """Validate that a connection is still alive.

        Executes a lightweight query (SELECT 1).

        Args:
            conn: Connection to validate

        Returns:
            True if connection is alive, False otherwise
        """
        try:
            conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    def get(self) -> Connection:
        """Get a connection from the pool.

        Attempts to get a pooled connection. If pool is empty and overflow
        limit not reached, creates a new overflow connection.

        Returns:
            Connection instance

        Raises:
            RuntimeError: If pool is exhausted and timeout exceeded
        """
        try:
            # Try to get connection from pool without blocking
            conn = self._pool.get_nowait()

            # Check if connection needs recycling
            if self._should_recycle(conn):
                conn.close()
                conn = self._create_connection()
            elif self._pre_ping and not self._validate_connection(conn):
                # Connection dead, discard and create new one
                conn.close()
                conn = self._create_connection()

            return conn

        except Empty:
            # Pool is empty, try to create overflow connection
            with self._overflow_lock:
                if self._overflow < self._max_overflow:
                    self._overflow += 1
                    overflow_conn = self._create_connection()
                    self._overflow_connections.add(id(overflow_conn))
                    return overflow_conn

            # No overflow available, wait for a connection with timeout
            try:
                conn = self._pool.get(timeout=self._timeout)

                # Check if connection needs recycling
                if self._should_recycle(conn):
                    conn.close()
                    conn = self._create_connection()
                elif self._pre_ping and not self._validate_connection(conn):
                     # Connection dead, discard and create new one
                    conn.close()
                    conn = self._create_connection()

                return conn
            except Empty:
                # Pool exhausted and timeout exceeded
                raise RuntimeError(
                    f"Connection pool exhausted (pool_size={self._pool_size}, " f"max_overflow={self._max_overflow})"
                )

    def return_connection(self, conn: Connection) -> None:
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
                with self._overflow_lock:
                    self._overflow -= 1
                self._overflow_connections.discard(conn_id)
            else:
                # Was a pooled connection, create replacement
                new_conn = self._create_connection()
                try:
                    self._pool.put_nowait(new_conn)
                except:
                    # Pool is somehow full, close the new connection
                    new_conn.close()

            # Clean up creation time tracking
            with self._created_lock:
                self._created_at.pop(conn_id, None)
        else:
            # Connection is still open
            if is_overflow:
                # Overflow connection - close it
                conn.close()
                with self._overflow_lock:
                    self._overflow -= 1
                self._overflow_connections.discard(conn_id)

                # Clean up creation time tracking
                with self._created_lock:
                    self._created_at.pop(conn_id, None)
            else:
                # Pooled connection - return to pool
                try:
                    self._pool.put_nowait(conn)
                except:
                    # Pool is full somehow, close the connection
                    conn.close()

                    # Clean up creation time tracking
                    with self._created_lock:
                        self._created_at.pop(conn_id, None)

    def _should_recycle(self, conn: Connection) -> bool:
        """Check if connection should be recycled based on age.

        Args:
            conn: Connection to check

        Returns:
            True if connection should be recycled
        """
        with self._created_lock:
            created_at = self._created_at.get(id(conn), 0)

        age = time.time() - created_at
        return age > self._recycle


    def close_all(self) -> None:
        """Close all connections in the pool.

        Drains the pool queue and closes all pooled connections.
        Does not affect overflow connections that are currently in use.
        """
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()

                # Clean up creation time tracking
                with self._created_lock:
                    self._created_at.pop(id(conn), None)
            except Empty:
                break

    @property
    def size(self) -> int:
        """Current number of connections in pool (not including overflow)."""
        return self._pool.qsize()

    @property
    def overflow(self) -> int:
        """Current number of overflow connections in use."""
        with self._overflow_lock:
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
            f"ConnectionPool(pool_size={self._pool_size}, "
            f"max_overflow={self._max_overflow}, "
            f"current_size={self.size}, "
            f"overflow={self.overflow})"
        )
