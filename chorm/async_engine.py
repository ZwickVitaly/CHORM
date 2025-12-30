"""Asynchronous engine primitives built on top of clickhouse-connect."""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable, Mapping, Sequence

import clickhouse_connect

from chorm.engine import EngineConfig


_CONFIG_FIELDS = set(EngineConfig.__dataclass_fields__.keys())


class AsyncEngine:
    """Factory for `clickhouse_connect.driver.asyncclient.AsyncClient` instances.

    Supports optional connection pooling for improved performance.
    """

    def __init__(
        self,
        config: EngineConfig,
        connect_args: Mapping[str, Any] | None = None,
        pool_size: int | None = None,
        max_overflow: int | None = None,
        pool_timeout: float | None = None,
        pool_recycle: int | None = None,
        pool_pre_ping: bool = False,
    ) -> None:
        self._config = config
        self._connect_args = dict(connect_args or {})

        # Connection pooling (optional)
        self._pool = None
        if pool_size is not None:
            from chorm.async_pool import AsyncConnectionPool

            self._pool = AsyncConnectionPool(
                config=config,
                pool_size=pool_size,
                max_overflow=max_overflow or 10,
                timeout=pool_timeout or 30.0,
                recycle=pool_recycle or 3600,
                pre_ping=pool_pre_ping,
                connect_args=self._connect_args,
            )



    @property
    def config(self) -> EngineConfig:
        return self._config

    @property
    def pool(self):
        """Return the connection pool if pooling is enabled."""
        return self._pool

    def compile(self, statement: Any) -> Tuple[str, Dict[str, Any]]:
        """Compile a statement into SQL and parameters.
        
        Args:
            statement: SQL statement (string or selectable object)
            
        Returns:
            Tuple of (sql, parameters)
        """
        from chorm.sql.compiler import Compiler
        
        if hasattr(statement, "to_sql"):
            compiler = Compiler()
            # If statement has to_sql, use compiler
            if hasattr(statement.to_sql, "__code__") and statement.to_sql.__code__.co_argcount > 1:
                 sql = statement.to_sql(compiler)
            else:
                 sql = statement.to_sql()
            
            return sql, compiler.params
            
        return str(statement), {}

    def connect(
        self,
        *,
        settings: Mapping[str, Any] | None = None,
        **overrides: Any,
    ) -> AsyncConnection:
        """Get a connection from pool or create a new one.

        If pooling is enabled, gets connection from pool.
        Otherwise, creates a new connection.

        Note: Pool must be initialized before use. Call await engine.pool.initialize()
        or let it auto-initialize on first get().
        """
        if self._pool is not None:
            # Note: get() is async, but we return the coroutine
            # Caller must await it
            # This is a sync method returning AsyncConnection, not a coroutine
            # We need to make this work properly
            raise RuntimeError(
                "Cannot use connect() with pooling enabled. "
                "Use 'async with engine.connection()' or call pool methods directly."
            )
        else:
            # Create new connection
            client = self._create_client(settings=settings, **overrides)
            return AsyncConnection(client)

    def connection(self, *, settings: Mapping[str, Any] | None = None, **overrides: Any):
        """Async context manager for automatic connection cleanup.

        When pooling is enabled, automatically returns connection to pool.
        When pooling is disabled, closes the connection.

        Example:
            >>> async with engine.connection() as conn:
            ...     result = await conn.query("SELECT 1")
            >>> # Connection automatically returned to pool or closed
        """
        from chorm._context_managers import _AsyncConnectionContextManager

        return _AsyncConnectionContextManager(self, settings=settings, **overrides)

    async def execute(
        self,
        sql: str,
        *,
        parameters: Mapping[str, Any] | Sequence[Any] | None = None,
        settings: Mapping[str, Any] | None = None,
        **overrides: Any,
    ) -> Any:
        """Execute a statement that does not return a result set."""
        async with self.connection(settings=settings, **overrides) as connection:
            return await connection.execute(sql, parameters=parameters, settings=settings)

    async def query(
        self,
        sql: str,
        *,
        parameters: Mapping[str, Any] | Sequence[Any] | None = None,
        settings: Mapping[str, Any] | None = None,
        **overrides: Any,
    ) -> Any:
        """Execute a query and return the ClickHouse result object."""
        async with self.connection(settings=settings, **overrides) as connection:
            return await connection.query(sql, parameters=parameters, settings=settings)

    async def query_df(
        self,
        sql: str,
        *,
        parameters: Mapping[str, Any] | Sequence[Any] | None = None,
        settings: Mapping[str, Any] | None = None,
        **overrides: Any,
    ) -> Any:
        """Execute a query and return a pandas DataFrame.
        
        Requires pandas to be installed.
        """
        async with self.connection(settings=settings, **overrides) as connection:
            return await connection.query_df(sql, parameters=parameters, settings=settings)

    async def _create_connection(
        self,
        *,
        settings: Mapping[str, Any] | None = None,
        **overrides: Any,
    ) -> "AsyncConnection":
        """Create a new async connection."""
        client = await self._create_client(settings=settings, **overrides)
        return AsyncConnection(client)

    async def _create_client(
        self,
        *,
        settings: Mapping[str, Any] | None = None,
        **overrides: Any,
    ) -> Any:
        client_kwargs = {
            "host": self._config.host,
            "port": self._config.port,
            "username": self._config.username,
            "password": self._config.password,
            "database": self._config.database,
            "secure": self._config.secure,
            # Timeout parameters
            "connect_timeout": self._config.connect_timeout,
            "send_receive_timeout": self._config.send_receive_timeout,
            # Performance parameters
            "compress": self._config.compress,
            "query_limit": self._config.query_limit,
            # Security parameters
            "verify": self._config.verify,
        }

        # Add optional parameters only if set
        if self._config.ca_cert is not None:
            client_kwargs["ca_cert"] = self._config.ca_cert
        if self._config.client_cert is not None:
            client_kwargs["client_cert"] = self._config.client_cert
        if self._config.client_cert_key is not None:
            client_kwargs["client_cert_key"] = self._config.client_cert_key
        if self._config.http_proxy is not None:
            client_kwargs["http_proxy"] = self._config.http_proxy
        if self._config.https_proxy is not None:
            client_kwargs["https_proxy"] = self._config.https_proxy
        if self._config.client_name is not None:
            client_kwargs["client_name"] = self._config.client_name

        combined_args = dict(self._connect_args)
        combined_args.update(overrides)

        merged_settings = dict(self._config.settings)
        if "settings" in combined_args:
            merged_settings.update(combined_args.pop("settings") or {})
        if settings:
            merged_settings.update(settings)
        if merged_settings:
            client_kwargs["settings"] = merged_settings

        client_kwargs.update(combined_args)

        return await clickhouse_connect.get_async_client(**client_kwargs)


class AsyncConnection:
    """Thin wrapper around an async ClickHouse client with context-manager helpers."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self._closed = False

    async def __aenter__(self) -> AsyncConnection:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    @property
    def client(self) -> Any:
        return self._client

    @property
    def closed(self) -> bool:
        return self._closed

    async def close(self) -> None:
        if not self._closed:
            await self._client.close()
            self._closed = True

    async def query(
        self,
        sql: str,
        *,
        parameters: Mapping[str, Any] | Sequence[Any] | None = None,
        settings: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        return await self._client.query(sql, parameters=parameters, settings=settings, **kwargs)

    async def query_df(
        self,
        sql: str,
        *,
        parameters: Mapping[str, Any] | Sequence[Any] | None = None,
        settings: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        return await self._client.query_df(sql, parameters=parameters, settings=settings, **kwargs)

    async def execute(
        self,
        sql: str,
        *,
        parameters: Mapping[str, Any] | Sequence[Any] | None = None,
        settings: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        return await self._client.command(sql, parameters=parameters, settings=settings, **kwargs)

    async def insert(
        self,
        table: str,
        data: Iterable[Sequence[Any]] | Mapping[str, Sequence[Any]],
        *,
        column_names: Sequence[str] | None = None,
        settings: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        return await self._client.insert(
            table,
            data,
            column_names=column_names,
            settings=settings,
            **kwargs,
        )


def create_async_engine(
    url: str | None = None,
    *,
    host: str | None = None,
    port: int | None = None,
    username: str | None = None,
    password: str | None = None,
    database: str | None = None,
    secure: bool | None = None,
    connect_timeout: int | None = None,
    send_receive_timeout: int | None = None,
    compress: bool | str | None = None,
    query_limit: int | None = None,
    verify: bool | None = None,
    ca_cert: str | None = None,
    client_cert: str | None = None,
    client_cert_key: str | None = None,
    http_proxy: str | None = None,
    https_proxy: str | None = None,
    client_name: str | None = None,
    connect_args: Mapping[str, Any] | None = None,
    pool_size: int | None = None,
    max_overflow: int | None = None,
    pool_timeout: float | None = None,
    pool_recycle: int | None = None,
    pool_pre_ping: bool = False,
    **kwargs: Any,
) -> AsyncEngine:
    """Create an `AsyncEngine` from an optional URL and keyword overrides.

    Args:
        url: Optional connection URL
        host: ClickHouse server hostname (default: localhost)
        port: ClickHouse HTTP/HTTPS port (default: 8123)
        username: ClickHouse username (default: default)
        password: Password for authentication
        database: Default database (default: default)
        secure: Use HTTPS/TLS (default: False)
        connect_timeout: HTTP connection timeout in seconds (default: 10)
        send_receive_timeout: HTTP read timeout in seconds (default: 300)
        compress: Enable compression - True, False, or 'lz4'/'zstd'/'brotli'/'gzip' (default: False)
        query_limit: Default LIMIT on returned rows, 0 = no limit (default: 0)
        verify: Verify server certificate in HTTPS mode (default: True)
        ca_cert: Path to CA certificate in .pem format, or 'certifi'
        client_cert: Path to client certificate in .pem format
        client_cert_key: Path to private key for client certificate
        http_proxy: HTTP proxy address
        https_proxy: HTTPS proxy address
        client_name: Client name for query tracking
        connect_args: Additional connection arguments
        pool_size: Enable pooling with this pool size (default: disabled)
        max_overflow: Maximum overflow connections (default: 10)
        pool_timeout: Connection acquisition timeout in seconds (default: 30.0)
        pool_recycle: Connection recycle time in seconds (default: 3600)
        pool_pre_ping: Enable active connection validation (default: False)
        **kwargs: Engine configuration and connection parameters

    Returns:
        AsyncEngine instance with optional connection pooling

    Example:
        >>> # Explicit configuration
        >>> engine = create_async_engine(
        ...     host="localhost",
        ...     username="default",
        ...     password="password"
        ... )
    """
    config = EngineConfig()
    url_connect_args: Dict[str, Any] = {}

    if url is not None:
        config, url_connect_args = EngineConfig.from_url(url)

    # Collect explicit overrides
    overrides: Dict[str, Any] = {}
    if host is not None: overrides["host"] = host
    if port is not None: overrides["port"] = port
    if username is not None: overrides["username"] = username
    if password is not None: overrides["password"] = password
    if database is not None: overrides["database"] = database
    if secure is not None: overrides["secure"] = secure
    if connect_timeout is not None: overrides["connect_timeout"] = connect_timeout
    if send_receive_timeout is not None: overrides["send_receive_timeout"] = send_receive_timeout
    if compress is not None: overrides["compress"] = compress
    if query_limit is not None: overrides["query_limit"] = query_limit
    if verify is not None: overrides["verify"] = verify
    if ca_cert is not None: overrides["ca_cert"] = ca_cert
    if client_cert is not None: overrides["client_cert"] = client_cert
    if client_cert_key is not None: overrides["client_cert_key"] = client_cert_key
    if http_proxy is not None: overrides["http_proxy"] = http_proxy
    if https_proxy is not None: overrides["https_proxy"] = https_proxy
    if client_name is not None: overrides["client_name"] = client_name

    # Add kwargs to overrides if they match config keys
    extra_connect_args: Dict[str, Any] = {}
    for key, value in kwargs.items():
        if key in _CONFIG_FIELDS:
            overrides[key] = value
        else:
            extra_connect_args[key] = value

    if overrides:
        config = config.with_overrides(**overrides)

    # Set default password from environment if password is empty
    if not config.password:
        env_password = os.environ.get("CLICKHOUSE_PASSWORD")
        if env_password is not None:
            config = config.with_overrides(password=env_password)
        elif not config.password and not overrides.get("password"):
            # Default to "123" only if not explicitly set to empty string and no env var
            pass
            
    if not config.password:
        config = config.with_overrides(password="123")

    merged_connect_args: Dict[str, Any] = dict(url_connect_args)
    merged_connect_args.update(extra_connect_args)
    if connect_args:
        merged_connect_args.update(connect_args)

    return AsyncEngine(
        config=config,
        connect_args=merged_connect_args,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_recycle=pool_recycle,
        pool_pre_ping=pool_pre_ping,
    )
