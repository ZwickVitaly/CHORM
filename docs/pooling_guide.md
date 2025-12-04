# Connection Pooling Guide

CHORM supports connection pooling for both synchronous and asynchronous engines, enabling efficient connection reuse and improved performance for high-concurrency applications.

## Table of Contents

- [Overview](#overview)
- [Synchronous Connection Pooling](#synchronous-connection-pooling)
- [Asynchronous Connection Pooling](#asynchronous-connection-pooling)
- [Configuration Options](#configuration-options)
- [Best Practices](#best-practices)
- [Monitoring](#monitoring)

---

## Overview

Connection pooling reduces the overhead of establishing new ClickHouse connections by reusing existing connections from a pool. This is particularly beneficial for:

- **High-concurrency applications**: Web servers, APIs, microservices
- **Frequent short queries**: Many small queries that would otherwise create/destroy connections repeatedly
- **Resource optimization**: Limiting the number of simultaneous connections to ClickHouse

### Key Features

- **Thread-safe** (sync) and **asyncio-safe** (async) implementations
- **Configurable pool size** and **overflow connections**
- **Automatic connection recycling** based on age
- **Connection timeout** handling
- **Context manager support** for automatic cleanup

---

## Synchronous Connection Pooling

### Basic Usage

```python
from chorm import create_engine, Session

# Create engine with connection pooling
engine = create_engine(
    "clickhouse://localhost:8123/default",
    pool_size=10,        # Maximum pooled connections
    max_overflow=20,     # Additional overflow connections
    pool_timeout=30.0,   # Connection acquisition timeout (seconds)
    pool_recycle=3600    # Connection recycle time (seconds)
)

# Using context manager (recommended)
with engine.connection() as conn:
    result = conn.query("SELECT count() FROM users")
    print(result.result_rows[0][0])
# Connection automatically returned to pool

# Using with Session
session = Session(engine)
result = session.execute("SELECT * FROM users LIMIT 10")
```

### Direct Pool Access

```python
# Get connection from pool manually
conn = engine.pool.get()
try:
    result = conn.query("SELECT 1")
    print(result.result_rows)
finally:
    # Important: return connection to pool
    engine.pool.return_connection(conn)

# Check pool statistics
print(f"Pool size: {engine.pool.size}")
print(f"Overflow: {engine.pool.overflow}")

# Close all connections when done
engine.pool.close_all()
```

### Thread Safety

The sync connection pool is thread-safe and can handle concurrent requests:

```python
import threading

def worker(thread_id):
    with engine.connection() as conn:
        result = conn.query(f"SELECT {thread_id}")
        print(f"Thread {thread_id}: {result.result_rows[0][0]}")

# Run 20 concurrent queries with pool of 10 + 20 overflow
threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
for t in threads:
    t.start()
for t in threads:
    t.join()
```

---

## Asynchronous Connection Pooling

### Basic Usage

```python
import asyncio
from chorm import create_async_engine, AsyncSession

async def main():
    # Create async engine with connection pooling
    engine = create_async_engine(
        "clickhouse://localhost:8123/default",
        pool_size=10,
        max_overflow=20,
        pool_timeout=30.0,
        pool_recycle=3600
    )
    
    # Initialize pool (optional - will auto-initialize on first use)
    await engine.pool.initialize()
    
    # Using context manager (recommended)
    async with engine.connection() as conn:
        result = await conn.query("SELECT count() FROM users")
        print(result.result_rows[0][0])
    # Connection automatically returned to pool
    
    # Using with AsyncSession
    session = AsyncSession(engine)
    result = await session.execute("SELECT * FROM users LIMIT 10")
    
    # Cleanup
    await engine.pool.close_all()

asyncio.run(main())
```

### Concurrent Async Queries

```python
import asyncio
from chorm import create_async_engine

async def query_worker(engine, query_id):
    async with engine.connection() as conn:
        result = await conn.query(f"SELECT {query_id}")
        return result.result_rows[0][0]

async def main():
    engine = create_async_engine(
        "clickhouse://localhost:8123/default",
        pool_size=10,
        max_overflow=20
    )
    
    # Run 50 concurrent queries
    tasks = [query_worker(engine, i) for i in range(50)]
    results = await asyncio.gather(*tasks)
    print(f"Completed {len(results)} queries")
    
    await engine.pool.close_all()

asyncio.run(main())
```

---

## Configuration Options

### Pool Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pool_size` | int | None (disabled) | Maximum number of pooled connections |
| `max_overflow` | int | 10 | Maximum overflow connections beyond pool_size |
| `pool_timeout` | float | 30.0 | Timeout (seconds) for acquiring connection |
| `pool_recycle` | int | 3600 | Connection recycle time (seconds) |

### Example Configuration

```python
# Minimal pooling (suitable for small apps)
engine = create_engine(
    "clickhouse://localhost:8123/default",
    pool_size=3,
    max_overflow=5
)

# Moderate pooling (suitable for medium traffic)
engine = create_engine(
    "clickhouse://localhost:8123/default",
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800  # Recycle after 30 minutes
)

# Aggressive pooling (suitable for high traffic)
engine = create_engine(
    "clickhouse://localhost:8123/default",
    pool_size=50,
    max_overflow=100,
    pool_timeout=10.0,  # Shorter timeout
    pool_recycle=600    # Recycle after 10 minutes
)
```

---

## Best Practices

### 1. Choose Appropriate Pool Size

- **Small applications** (< 10 concurrent users): `pool_size=3-5`
- **Medium applications** (10-100 concurrent users): `pool_size=10-20`
- **Large applications** (100+ concurrent users): `pool_size=30-50`

### 2. Configure Overflow Carefully

Overflow connections are created when the pool is exhausted. Set `max_overflow` to handle traffic spikes:

```python
# Good: Allow 2x overflow for traffic spikes
engine = create_engine(url, pool_size=10, max_overflow=20)

# Too restrictive: May cause connection exhaustion
engine = create_engine(url, pool_size=10, max_overflow=2)

# Too permissive: May overwhelm ClickHouse server
engine = create_engine(url, pool_size=10, max_overflow=1000)
```

### 3. Always Use Context Managers

Context managers ensure connections are properly returned to the pool:

```python
# ✅ Good: Automatic connection return
with engine.connection() as conn:
    result = conn.query("SELECT 1")

# ❌ Bad: Manual management error-prone
conn = engine.pool.get()
result = conn.query("SELECT 1")
# Forgot to return connection!
```

### 4. Set Connection Recycle Time

Long-lived connections can become stale. Set `pool_recycle` based on your ClickHouse configuration:

```python
# Recycle connections after 1 hour (default)
engine = create_engine(url, pool_size=10, pool_recycle=3600)

# Recycle more frequently for unstable networks
engine = create_engine(url, pool_size=10, pool_recycle=600)  # 10 minutes
```

### 5. Clean Up on Application Shutdown

Always close all connections when your application shuts down:

```python
import atexit

engine = create_engine(url, pool_size=10)

# Register cleanup handler
atexit.register(lambda: engine.pool.close_all())
```

---

## Monitoring

### Check Pool Status

```python
# Get pool statistics
print(f"Pool size: {engine.pool.size}")         # Current pooled connections
print(f"Overflow: {engine.pool.overflow}")      # Current overflow connections
print(f"Pool representation: {engine.pool}")    # Full status

# Output:
# Pool size: 8
# Overflow: 2
# ConnectionPool(pool_size=10, max_overflow=20, current_size=8, overflow=2)
```

### Log Pool Activity

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("chorm.pool")

# Pool operations will be logged
with engine.connection() as conn:
    result = conn.query("SELECT 1")
```

### Handle Pool Exhaustion

```python
try:
    conn = engine.pool.get()
except RuntimeError as e:
    print(f"Pool exhausted: {e}")
    # Implement backoff or queue the request
```

---

## Example: Web Application with Connection Pooling

### Flask Example

```python
from flask import Flask, jsonify
from chorm import create_engine, Session

app = Flask(__name__)

# Create global engine with pooling
engine = create_engine(
    "clickhouse://localhost:8123/default",
    pool_size=20,
    max_overflow=40
)

@app.route('/users/count')
def user_count():
    with engine.connection() as conn:
        result = conn.query("SELECT count() FROM users")
        count = result.result_rows[0][0]
    return jsonify({"count": count})

@app.route('/users/<int:user_id>')
def get_user(user_id):
    session = Session(engine)
    result = session.execute(
        f"SELECT * FROM users WHERE id = {user_id}"
    )
    user = result.first()
    return jsonify(user) if user else ("Not found", 404)

# Cleanup on shutdown
@app.teardown_appcontext
def shutdown_session(exception=None):
    pass  # Session cleanup handled by context manager

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000)
    finally:
        engine.pool.close_all()
```

### FastAPI Example (Async)

```python
from fastapi import FastAPI
from chorm import create_async_engine, AsyncSession

app = FastAPI()

# Create global async engine with pooling
engine = create_async_engine(
    "clickhouse://localhost:8123/default",
    pool_size=20,
    max_overflow=40
)

@app.on_event("startup")
async def startup():
    await engine.pool.initialize()

@app.on_event("shutdown")
async def shutdown():
    await engine.pool.close_all()

@app.get('/users/count')
async def user_count():
    async with engine.connection() as conn:
        result = await conn.query("SELECT count() FROM users")
        count = result.result_rows[0][0]
    return {"count": count}

@app.get('/users/{user_id}')
async def get_user(user_id: int):
    session = AsyncSession(engine)
    result = await session.execute(
        f"SELECT * FROM users WHERE id = {user_id}"
    )
    user = result.first()
    if not user:
        raise HTTPException(status_code=404)
    return user
```

---

## Performance Comparison

### Without Pooling

```python
# Each query creates a new connection
engine = create_engine("clickhouse://localhost:8123/default")

for i in range(100):
    with engine.connection() as conn:
        conn.query("SELECT 1")
# Time: ~5-10 seconds (connection overhead)
```

### With Pooling

```python
# Connections are reused from pool
engine = create_engine(
    "clickhouse://localhost:8123/default",
    pool_size=10
)

for i in range(100):
    with engine.connection() as conn:
        conn.query("SELECT 1")
# Time: ~1-2 seconds (minimal overhead)
```

**Result**: ~5x performance improvement for high-frequency small queries!

---

## Troubleshooting

### Pool Exhaustion

**Symptom**: `RuntimeError: Connection pool exhausted`

**Solutions**:
1. Increase `pool_size` or `max_overflow`
2. Decrease `pool_timeout`
3. Ensure connections are properly returned (use context managers)
4. Check for connection leaks

### Stale Connections

**Symptom**: Queries fail with connection errors

**Solution**: Reduce `pool_recycle` time:

```python
engine = create_engine(
    url,
    pool_size=10,
    pool_recycle=600  # Recycle every 10 minutes
)
```

### High Memory Usage

**Symptom**: Application consumes too much memory

**Solution**: Reduce pool size and overflow:

```python
# Before: Too many connections
engine = create_engine(url, pool_size=100, max_overflow=200)

# After: Reasonable limits
engine = create_engine(url, pool_size=20, max_overflow=30)
```

---

## Summary

- **Enable pooling** for production applications: `create_engine(url, pool_size=10)`
- **Use context managers** to ensure proper connection return
- **Configure appropriately** based on your traffic patterns
- **Monitor pool statistics** to optimize configuration
- **Clean up** on application shutdown

For more examples, see:
- [examples/](../examples/)
- [tests/integration/test_pool_integration.py](../tests/integration/test_pool_integration.py)

