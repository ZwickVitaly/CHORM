# Connection Timeout and Configuration Guide

This guide covers how to configure connection timeouts and other advanced connection parameters in CHORM.

## Table of Contents
- [Timeout Configuration](#timeout-configuration)
- [Compression](#compression)
- [Security Settings](#security-settings)
- [Proxy Configuration](#proxy-configuration)
- [Monitoring](#monitoring)
- [Complete Examples](#complete-examples)

## Timeout Configuration

CHORM supports two types of timeouts that are passed directly to clickhouse-connect:

### Connection Timeout

Controls how long to wait when establishing the initial HTTP connection to ClickHouse.

```python
from chorm import create_engine

# Set connection timeout to 5 seconds (default: 10)
engine = create_engine(
    "clickhouse://localhost:8123/default",
    connect_timeout=5
)
```

### Send/Receive Timeout

Controls the HTTP read timeout for both sending data to and receiving data from ClickHouse.

```python
from chorm import create_engine

# Set send/receive timeout to 60 seconds (default: 300)
engine = create_engine(
    "clickhouse://localhost:8123/default",
    send_receive_timeout=60
)
```

### Combined Timeout Configuration

```python
from chorm import create_engine, Session

# Production-ready timeout configuration
engine = create_engine(
    "clickhouse://localhost:8123/default",
    connect_timeout=5,           # 5 seconds to establish connection
    send_receive_timeout=120     # 2 minutes for query execution
)

session = Session(engine)
```

## Compression

Enable compression to reduce network traffic and improve performance for large datasets.

### Boolean Compression

```python
# Enable default compression (lz4)
engine = create_engine(
    "clickhouse://localhost:8123/default",
    compress=True
)
```

### Specific Compression Algorithm

```python
# Choose specific compression algorithm
engine = create_engine(
    "clickhouse://localhost:8123/default",
    compress='zstd'  # Options: 'lz4', 'zstd', 'brotli', 'gzip'
)
```

**Compression Algorithm Comparison:**
- `lz4`: Fastest, good compression ratio (recommended for most cases)
- `zstd`: Better compression, slightly slower
- `brotli`: Best compression, slowest
- `gzip`: Widely supported, moderate performance

## Security Settings

### HTTPS/TLS Configuration

```python
from chorm import create_engine

# Enable HTTPS with certificate verification
engine = create_engine(
    "clickhouse://secure-host:8443/default",
    secure=True,
    verify=True,
    ca_cert='/path/to/ca-certificate.pem'
)
```

### Using Certifi for Certificate Verification

```python
# Use certifi package for trusted root certificates
engine = create_engine(
    "clickhouse://secure-host:8443/default",
    secure=True,
    verify=True,
    ca_cert='certifi'  # Use certifi's certificate bundle
)
```

### Client Certificate Authentication

```python
# Mutual TLS with client certificates
engine = create_engine(
    "clickhouse://secure-host:8443/default",
    secure=True,
    verify=True,
    ca_cert='/path/to/ca.pem',
    client_cert='/path/to/client-cert.pem',
    client_cert_key='/path/to/client-key.pem'
)
```

### Disable Certificate Verification (Development Only)

```python
# WARNING: Only use in development/testing!
engine = create_engine(
    "clickhouse://localhost:8443/default",
    secure=True,
    verify=False  # Skip certificate verification
)
```

## Proxy Configuration

Configure HTTP/HTTPS proxies for connecting through corporate networks.

```python
from chorm import create_engine

# HTTP proxy
engine = create_engine(
    "clickhouse://remote-host:8123/default",
    http_proxy='http://proxy.company.com:8080'
)

# HTTPS proxy
engine = create_engine(
    "clickhouse://remote-host:8443/default",
    secure=True,
    https_proxy='https://proxy.company.com:8443'
)

# Both HTTP and HTTPS proxies
engine = create_engine(
    "clickhouse://remote-host:8123/default",
    http_proxy='http://proxy.company.com:8080',
    https_proxy='https://proxy.company.com:8443'
)
```

## Monitoring

### Client Name for Query Tracking

Set a client name to track queries in ClickHouse's `system.query_log`:

```python
from chorm import create_engine

engine = create_engine(
    "clickhouse://localhost:8123/default",
    client_name='my-application-v1.0'
)

# Queries will appear in system.query_log with this client name
# Useful for monitoring and debugging in production
```

### Query Limit

Set a default LIMIT on returned rows to prevent accidentally fetching huge result sets:

```python
from chorm import create_engine

# Limit all queries to 10,000 rows by default
engine = create_engine(
    "clickhouse://localhost:8123/default",
    query_limit=10000
)

# You can still override this in individual queries
# by explicitly setting LIMIT in your SQL
```

## Complete Examples

### Production Configuration

```python
from chorm import create_engine, Session, select
from models import User

# Production-ready engine with all recommended settings
engine = create_engine(
    "clickhouse://prod-clickhouse.company.com:8443/analytics",
    # Connection settings
    username='app_user',
    password='secure_password',
    secure=True,
    
    # Timeouts
    connect_timeout=5,
    send_receive_timeout=120,
    
    # Performance
    compress='lz4',
    query_limit=100000,
    
    # Security
    verify=True,
    ca_cert='certifi',
    
    # Monitoring
    client_name='analytics-service-v2.1',
    
    # ClickHouse settings
    settings={
        'max_threads': 4,
        'max_memory_usage': 10000000000,  # 10GB
        'readonly': 1  # Read-only mode for safety
    }
)

session = Session(engine)

# Use as normal
query = select(User).where(User.active == 1)
result = session.execute(query)
users = result.all()
```

### Development Configuration

```python
from chorm import create_engine

# Development engine with relaxed settings
engine = create_engine(
    "clickhouse://localhost:8123/dev_db",
    # Shorter timeouts for faster feedback
    connect_timeout=2,
    send_receive_timeout=30,
    
    # No compression for easier debugging
    compress=False,
    
    # No query limit in development
    query_limit=0,
    
    # Client name for tracking
    client_name='dev-local'
)
```

### Async Engine Configuration

```python
from chorm import create_async_engine, AsyncSession

# Async engine with same configuration options
engine = create_async_engine(
    "clickhouse://localhost:8123/default",
    connect_timeout=5,
    send_receive_timeout=120,
    compress='lz4',
    client_name='async-worker'
)

async def fetch_users():
    async with AsyncSession(engine) as session:
        result = await session.execute(select(User))
        return result.all()
```

### High-Performance Bulk Operations

```python
from chorm import create_engine

# Optimized for bulk inserts
engine = create_engine(
    "clickhouse://localhost:8123/default",
    # Longer timeouts for large operations
    connect_timeout=10,
    send_receive_timeout=600,  # 10 minutes
    
    # Enable compression for large data transfers
    compress='lz4',
    
    # No query limit
    query_limit=0,
    
    # ClickHouse settings for bulk operations
    settings={
        'max_insert_block_size': 1048576,
        'max_threads': 8
    }
)
```

### Secure Cloud Connection

```python
from chorm import create_engine

# Connect to ClickHouse Cloud with full security
engine = create_engine(
    "clickhouse://my-instance.clickhouse.cloud:8443/default",
    username='cloud_user',
    password='cloud_password',
    
    # Security
    secure=True,
    verify=True,
    ca_cert='certifi',
    
    # Timeouts (cloud may need longer timeouts)
    connect_timeout=10,
    send_receive_timeout=300,
    
    # Performance
    compress='lz4',
    
    # Monitoring
    client_name='cloud-app-prod'
)
```

## Best Practices

1. **Always set timeouts in production**: Use reasonable values based on your query patterns
   - `connect_timeout`: 5-10 seconds
   - `send_receive_timeout`: 60-300 seconds

2. **Enable compression for production**: Reduces network traffic significantly
   - Use `compress='lz4'` for best balance of speed and compression

3. **Use client_name for monitoring**: Makes it easy to track queries in `system.query_log`

4. **Set query_limit as a safety net**: Prevents accidentally fetching millions of rows

5. **Always verify certificates in production**: Use `verify=True` with proper CA certificates

6. **Use environment variables for credentials**: Don't hardcode passwords

```python
import os
from chorm import create_engine

engine = create_engine(
    f"clickhouse://{os.getenv('CH_HOST')}:8443/default",
    username=os.getenv('CH_USER'),
    password=os.getenv('CH_PASSWORD'),
    secure=True,
    verify=True,
    ca_cert='certifi',
    connect_timeout=5,
    send_receive_timeout=120,
    compress='lz4',
    client_name=os.getenv('APP_NAME', 'chorm-app')
)
```

## Troubleshooting

### Connection Timeouts

If you're experiencing connection timeouts:

1. Increase `connect_timeout`:
   ```python
   engine = create_engine(..., connect_timeout=30)
   ```

2. Check network connectivity to ClickHouse server

3. Verify firewall rules allow connections

### Query Timeouts

If queries are timing out:

1. Increase `send_receive_timeout`:
   ```python
   engine = create_engine(..., send_receive_timeout=600)
   ```

2. Optimize your queries (use PREWHERE, proper indexes)

3. Check ClickHouse server load

### SSL/TLS Errors

If you're getting certificate verification errors:

1. Verify the CA certificate path is correct
2. Use `ca_cert='certifi'` for public certificates
3. In development only, temporarily disable verification to isolate the issue:
   ```python
   engine = create_engine(..., verify=False)  # Development only!
   ```

## Reference

All timeout and connection parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `connect_timeout` | int | 10 | Connection timeout in seconds |
| `send_receive_timeout` | int | 300 | Read timeout in seconds |
| `compress` | bool/str | False | Compression: True, False, or 'lz4'/'zstd'/'brotli'/'gzip' |
| `query_limit` | int | 0 | Default LIMIT on rows (0 = no limit) |
| `verify` | bool | True | Verify SSL certificate |
| `ca_cert` | str | None | Path to CA certificate or 'certifi' |
| `client_cert` | str | None | Path to client certificate |
| `client_cert_key` | str | None | Path to client private key |
| `http_proxy` | str | None | HTTP proxy address |
| `https_proxy` | str | None | HTTPS proxy address |
| `client_name` | str | None | Client name for query tracking |
