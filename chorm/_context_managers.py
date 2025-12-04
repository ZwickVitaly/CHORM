"""Context manager helpers for connection pooling."""

from typing import Any, Mapping

from chorm.engine import Connection, Engine
from chorm.async_engine import AsyncConnection, AsyncEngine


class _ConnectionContextManager:
    """Context manager for automatic connection cleanup."""

    def __init__(self, engine: Engine, settings: Mapping[str, Any] | None = None, **overrides: Any):
        self._engine = engine
        self._settings = settings
        self._overrides = overrides
        self._conn = None

    def __enter__(self) -> Connection:
        self._conn = self._engine.connect(settings=self._settings, **self._overrides)
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._conn is not None:
            if self._engine.pool is not None:
                # Return to pool
                self._engine.pool.return_connection(self._conn)
            else:
                # Close connection
                self._conn.close()
        return False


class _AsyncConnectionContextManager:
    """Async context manager for automatic connection cleanup."""

    def __init__(self, engine: AsyncEngine, settings: Mapping[str, Any] | None = None, **overrides: Any):
        self._engine = engine
        self._settings = settings
        self._overrides = overrides
        self._conn = None

    async def __aenter__(self) -> AsyncConnection:
        if self._engine.pool is not None:
            # Get from pool (async)
            self._conn = await self._engine.pool.get()
        else:
            # Create new connection - need to await the async client creation
            self._conn = await self._engine._create_connection(settings=self._settings, **self._overrides)
        return self._conn

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._conn is not None:
            if self._engine.pool is not None:
                # Return to pool
                await self._engine.pool.return_connection(self._conn)
            else:
                # Close connection
                await self._conn.close()
        return False
