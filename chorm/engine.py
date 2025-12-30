"""Engine primitives built on top of clickhouse-connect."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple, TYPE_CHECKING
from urllib.parse import parse_qsl, urlparse

import clickhouse_connect

if TYPE_CHECKING:
    from chorm._context_managers import _ConnectionContextManager

_TRUE_VALUES = {"1", "true", "t", "yes", "y", "on"}
_FALSE_VALUES = {"0", "false", "f", "no", "n", "off"}
_CONFIG_KEYS = {
    "host",
    "port",
    "username",
    "password",
    "database",
    "secure",
    "settings",
    "connect_timeout",
    "send_receive_timeout",
    "compress",
    "verify",
    "client_name",
    "ca_cert",
    "client_cert",
    "client_cert_key",
    "http_proxy",
    "https_proxy",
    "query_limit",
}


def _coerce_value(raw: str) -> Any:
    lowered = raw.lower()
    if lowered in _TRUE_VALUES:
        return True
    if lowered in _FALSE_VALUES:
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def _coerce_bool(raw: str) -> bool:
    lowered = raw.lower()
    if lowered in _TRUE_VALUES:
        return True
    if lowered in _FALSE_VALUES:
        return False
    raise ValueError(f"Cannot coerce value '{raw}' to boolean")


@dataclass
class EngineConfig:
    """Static connection information for building ClickHouse clients.

    Connection Parameters:
        host: ClickHouse server hostname (default: localhost)
        port: ClickHouse HTTP/HTTPS port (default: 8123)
        username: ClickHouse username (default: default)
        password: Password for authentication
        database: Default database (default: default)
        secure: Use HTTPS/TLS (default: False)
        settings: ClickHouse server settings dict

    Timeout Parameters:
        connect_timeout: HTTP connection timeout in seconds (default: 10)
        send_receive_timeout: HTTP read timeout in seconds (default: 300)

    Performance Parameters:
        compress: Enable compression - True, False, or 'lz4'/'zstd'/'brotli'/'gzip' (default: False)
        query_limit: Default LIMIT on returned rows, 0 = no limit (default: 0)

    Security Parameters:
        verify: Verify server certificate in HTTPS mode (default: True)
        ca_cert: Path to CA certificate in .pem format, or 'certifi' for certifi package
        client_cert: Path to client certificate in .pem format
        client_cert_key: Path to private key for client certificate

    Proxy Parameters:
        http_proxy: HTTP proxy address
        https_proxy: HTTPS proxy address

    Monitoring Parameters:
        client_name: Client name for query tracking in system.query_log
    """

    # Connection parameters
    host: str = "localhost"
    port: int = 8123
    username: str = "default"
    password: str = ""
    database: str = "default"
    secure: bool = False
    settings: Dict[str, Any] = field(default_factory=dict)


    # Timeout parameters (following clickhouse-connect defaults)
    connect_timeout: int = 10
    send_receive_timeout: int = 300

    # Performance parameters
    compress: bool | str = False
    query_limit: int = 0

    # Security parameters
    verify: bool = True
    ca_cert: str | None = None
    client_cert: str | None = None
    client_cert_key: str | None = None

    # Proxy parameters
    http_proxy: str | None = None
    https_proxy: str | None = None

    # Monitoring parameters
    client_name: str | None = None

    def with_overrides(self, **overrides: Any) -> "EngineConfig":
        """Return a new config with selected fields replaced."""
        merged_settings = dict(self.settings)
        if "settings" in overrides and overrides["settings"]:
            merged_settings.update(overrides["settings"])

        return EngineConfig(
            host=overrides.get("host", self.host),
            port=overrides.get("port", self.port),
            username=overrides.get("username", self.username),
            password=overrides.get("password", self.password),
            database=overrides.get("database", self.database),
            secure=overrides.get("secure", self.secure),
            settings=merged_settings,
            connect_timeout=overrides.get("connect_timeout", self.connect_timeout),
            send_receive_timeout=overrides.get("send_receive_timeout", self.send_receive_timeout),
            compress=overrides.get("compress", self.compress),
            query_limit=overrides.get("query_limit", self.query_limit),
            verify=overrides.get("verify", self.verify),
            ca_cert=overrides.get("ca_cert", self.ca_cert),
            client_cert=overrides.get("client_cert", self.client_cert),
            client_cert_key=overrides.get("client_cert_key", self.client_cert_key),
            http_proxy=overrides.get("http_proxy", self.http_proxy),
            https_proxy=overrides.get("https_proxy", self.https_proxy),
            client_name=overrides.get("client_name", self.client_name),
        )

    @classmethod
    def from_url(cls, url: str) -> Tuple["EngineConfig", Dict[str, Any]]:
        """Create a config and additional connection arguments from a DSN."""
        parsed = urlparse(url)
        if parsed.scheme not in {"clickhouse", "clickhouse+http", "clickhouse+https"}:
            raise ValueError(f"Unsupported ClickHouse URL scheme '{parsed.scheme}'")

        secure = parsed.scheme == "clickhouse+https"
        query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))

        if "secure" in query_params:
            secure = _coerce_bool(query_params.pop("secure"))

        settings: Dict[str, Any] = {}
        extra_args: Dict[str, Any] = {}
        for key, value in query_params.items():
            if key.startswith("setting."):
                settings[key.split(".", 1)[1]] = _coerce_value(value)
            else:
                extra_args[key] = _coerce_value(value)

        database = parsed.path.lstrip("/") or "default"
        default_port = 8443 if secure else 8123
        port = parsed.port or default_port

        config = cls(
            host=parsed.hostname or "localhost",
            port=port,
            username=parsed.username or "default",
            password=parsed.password or "",
            database=database,
            secure=secure,
            settings=settings,
        )

        return config, extra_args

    def __repr__(self) -> str:
        """Mask password in string representation."""
        # Create a copy of dict to modify password
        d = self.__dict__.copy()
        if d.get("password"):
            d["password"] = "******"
        
        # Format like standard dataclass repr
        field_strs = [f"{k}={repr(v)}" for k, v in d.items()]
        return f"{self.__class__.__name__}({', '.join(field_strs)})"


class Engine:
    """Factory for `clickhouse_connect.driver.client.Client` instances.

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
            from chorm.pool import ConnectionPool

            self._pool = ConnectionPool(
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
            # We need to handle potential legacy to_sql signatures if any user defined them?
            # But we are updating internal ones.
            # Python is dynamic, so we can try calling with argument.
            if hasattr(statement.to_sql, "__code__") and statement.to_sql.__code__.co_argcount > 1:
                 sql = statement.to_sql(compiler)
            else:
                 # Legacy support or simple string return
                 sql = statement.to_sql()
            
            return sql, compiler.params
            
        return str(statement), {}

    def connect(self, *, settings: Mapping[str, Any] | None = None, **overrides: Any) -> "Connection":
        """Get a connection from pool or create a new one.

        If pooling is enabled, gets connection from pool.
        Otherwise, creates a new connection.
        """
        if self._pool is not None:
            # Get from pool
            return self._pool.get()
        else:
            # Create new connection
            client = self._create_client(settings=settings, **overrides)
            return Connection(client)

    def connection(self, *, settings: Mapping[str, Any] | None = None, **overrides: Any):
        """Context manager for automatic connection cleanup.

        When pooling is enabled, automatically returns connection to pool.
        When pooling is disabled, closes the connection.

        Example:
            >>> with engine.connection() as conn:
            ...     result = conn.query("SELECT 1")
            >>> # Connection automatically returned to pool or closed
        """
        from chorm._context_managers import _ConnectionContextManager

        return _ConnectionContextManager(self, settings=settings, **overrides)

    def execute(
        self,
        sql: str,
        *,
        parameters: Mapping[str, Any] | Sequence[Any] | None = None,
        settings: Mapping[str, Any] | None = None,
        **overrides: Any,
    ) -> Any:
        """Execute a command that does not return a result set."""
        with self.connect(settings=settings, **overrides) as connection:
            return connection.execute(sql, parameters=parameters, settings=settings)

    def query(
        self,
        sql: str,
        *,
        parameters: Mapping[str, Any] | Sequence[Any] | None = None,
        settings: Mapping[str, Any] | None = None,
        **overrides: Any,
    ) -> Any:
        """Execute a query and return the ClickHouse result object."""
        with self.connect(settings=settings, **overrides) as connection:
            return connection.query(sql, parameters=parameters, settings=settings)

    def query_df(
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
        with self.connect(settings=settings, **overrides) as connection:
            return connection.query_df(sql, parameters=parameters, settings=settings)

    def _create_client(self, *, settings: Mapping[str, Any] | None = None, **overrides: Any) -> Any:
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

        return clickhouse_connect.get_client(**client_kwargs)


class Connection:
    """Thin wrapper around a ClickHouse client with context-manager helpers."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self._closed = False

    def __enter__(self) -> "Connection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @property
    def client(self) -> Any:
        return self._client

    def close(self) -> None:
        if not self._closed:
            self._client.close()
            self._closed = True

    @property
    def closed(self) -> bool:
        return self._closed

    def query(
        self,
        sql: str,
        *,
        parameters: Mapping[str, Any] | Sequence[Any] | None = None,
        settings: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        return self._client.query(sql, parameters=parameters, settings=settings, **kwargs)

    def query_df(
        self,
        sql: str,
        *,
        parameters: Mapping[str, Any] | Sequence[Any] | None = None,
        settings: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        return self._client.query_df(sql, parameters=parameters, settings=settings, **kwargs)

    def execute(
        self,
        sql: str,
        *,
        parameters: Mapping[str, Any] | Sequence[Any] | None = None,
        settings: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        return self._client.command(sql, parameters=parameters, settings=settings, **kwargs)

    def insert(
        self,
        table: str,
        data: Iterable[Sequence[Any]] | Mapping[str, Sequence[Any]],
        *,
        column_names: Sequence[str] | None = None,
        settings: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        return self._client.insert(
            table,
            data,
            column_names=column_names,
            settings=settings,
            **kwargs,
        )


def create_engine(
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
) -> Engine:
    """Create an `Engine` from an optional URL and keyword overrides.

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
        **kwargs: Additional engine configuration and connection parameters

    Returns:
        Engine instance with optional connection pooling

    Example:
        >>> # Explicit configuration
        >>> engine = create_engine(
        ...     host="localhost",
        ...     username="default",
        ...     password="password",
        ...     send_receive_timeout=60
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
        if key in _CONFIG_KEYS:
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
             # NOTE: Original logic was: if not config.password -> check env -> else "123"
             # I'll keep it mostly same but be careful about explicit empty string.
             # If user passed password="", config.password is ""
             pass
        
    # Re-eval "123" default for backward compat if it was relying on it.
    # The original logic applied "123" if config.password was empty after env check.
    if not config.password:
             config = config.with_overrides(password="123")


    merged_connect_args: Dict[str, Any] = dict(url_connect_args)
    merged_connect_args.update(extra_connect_args)
    if connect_args:
        merged_connect_args.update(connect_args)

    return Engine(
        config=config,
        connect_args=merged_connect_args,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_recycle=pool_recycle,
        pool_pre_ping=pool_pre_ping,
    )
