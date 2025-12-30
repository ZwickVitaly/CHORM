# CHORM - ClickHouse ORM

A powerful SQLAlchemy-like ORM for ClickHouse, optimized for analytics and high-performance queries.

## Features

### Core ORM Capabilities
- **SQLAlchemy-like Syntax**: Familiar API for Python developers
- **Native ClickHouse Types**: Full support for ClickHouse-specific types (UInt64, Array, Nullable, etc.)
- **Type Safety**: Explicit type declarations for better IDE support
- **Async Support**: Full async/await support with AsyncSession
- **Query Builder**: Fluent API for Select, Insert, Update, Delete
- **Compression Codecs**: Fine-grained storage optimization via `Column(..., codec=ZSTD(1))`

### Analytics & Advanced Queries
- **Window Functions**: ROW_NUMBER, RANK, DENSE_RANK, LAG, LEAD, and aggregate window functions
- **CTEs (Common Table Expressions)**: Build complex queries with readable structure
- **JOINs**: INNER, LEFT, RIGHT, FULL, CROSS with multiple join support
- **Subqueries**: Scalar and table subqueries with IN/EXISTS support
- **Conditional Aggregations**: sumIf, countIf, avgIf for multi-metric queries

### ClickHouse-Specific Features
- **ARRAY JOIN**: Efficiently unnest and analyze array columns
- **LIMIT BY**: Top-N rows per group without window functions
- **WITH TOTALS**: Add summary rows to GROUP BY results
- **PREWHERE**: Optimize queries with early filtering
- **FINAL, SAMPLE, SETTINGS**: Full control over query execution
- **OPTIMIZE TABLE**: Manual table optimization and deduplication
- **INSERT FROM SELECT**: Efficient bulk data copying
- **Dictionaries**: External data source integration
- **EXPLAIN/ANALYZE**: Query profiling and optimization

### Multi-Database Support
- **Database Attribute**: Specify target database per table with `__database__`
- **Qualified Names**: Automatic `database.table` formatting in all SQL statements
- **Database DDL**: `CREATE DATABASE` / `DROP DATABASE` with full options
- **Smart Drop Protection**: Automatic size limit bypass with UNDROP warnings
- **Safe Migrations**: DROP DATABASE never auto-generated, explicit warnings for drops

## Installation

```bash
pip install clickhouse-chorm
```

## Quick Start

### Define Models

```python
from chorm import Table, Column, MergeTree
from chorm.types import UInt64, String

class User(Table):
    __tablename__ = "users"
    __engine__ = MergeTree()
    
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    email = Column(String())
```

### Synchronous Usage

```python
from chorm import create_engine, Session, select

# Create engine with explicit configuration (recommended)
engine = create_engine(
    host="localhost",
    port=8123,
    username="default",
    password="password",  # No URL encoding needed!
    database="default",
    connect_timeout=5,
    send_receive_timeout=120,
    compress='lz4'
)

# Or using connection URL (backward compatibility)
# engine = create_engine("clickhouse://default:password@localhost:8123/default")

# Create session
session = Session(engine)

# Insert data
user = User(id=1, name="Alice", email="alice@example.com")
session.add(user)
session.commit()

# Query data
stmt = select(User.id, User.name).where(User.id > 0)
result = session.execute(stmt)
users = result.all()
```

### Session Configuration Overrides

You can override connection parameters for a specific session without changing the global engine configuration. This is useful for long-running operations.

```python
# Create a session with a longer timeout
long_session = Session(engine, send_receive_timeout=3600)

long_session.execute("OPTIMIZE TABLE big_table FINAL")
# Uses 3600s timeout, while 'engine' defaults remain unchanged
```

### Asynchronous Usage

```python
from chorm import create_async_engine, AsyncSession

# Create async engine
engine = create_async_engine(
    host="localhost", 
    port=8123, 
    username="default", 
    password="password"
)

# Use async session
async with AsyncSession(engine) as session:
    user = User(id=1, name="Alice", email="alice@example.com")
    session.add(user)
    # Auto-commits on exit

# Query asynchronously
async with AsyncSession(engine) as session:
    stmt = select(User).where(User.id > 0)
    result = await session.execute(stmt)
    users = result.all()
```

### Schema Management with Metadata

CHORM provides SQLAlchemy-like metadata for schema management:

```python
from chorm import Table, Column, MetaData, Memory
from chorm.types import UInt64, String

# Create metadata object
metadata = MetaData()

# Define tables using metadata
class User(Table):
    metadata = metadata
    __tablename__ = "users"
    __engine__ = Memory()
    
    id = Column(UInt64(), primary_key=True)
    name = Column(String())

# Create all tables associated with this metadata
metadata.create_all(engine)

# Drop all tables
metadata.drop_all(engine)
```

### Multi-Database Support

Work with tables across multiple databases:

```python
from chorm import Table, Column, create_engine, Session
from chorm.types import UInt64, String
from chorm.table_engines import MergeTree
from chorm.sql import select, insert
from chorm.sql.ddl import create_database, drop_database

# Create engine
engine = create_engine("clickhouse://localhost:8123/default")
session = Session(engine)

# Create a new database
session.execute(create_database("analytics", if_not_exists=True).to_sql())

# Define table in specific database
class Event(Table):
    __tablename__ = "events"
    __database__ = "analytics"  # <-- Target database
    __engine__ = MergeTree()
    __order_by__ = ["id"]
    
    id = Column(UInt64(), primary_key=True)
    name = Column(String())

# Create table (generates: CREATE TABLE analytics.events ...)
session.execute(Event.create_table())

# Insert (generates: INSERT INTO analytics.events ...)
session.execute(insert(Event).values(id=1, name="click").to_sql())

# Select (generates: SELECT analytics.events.id FROM analytics.events ...)
result = session.execute(select(Event.id, Event.name).to_sql())
print(result.all())

# Cleanup
session.execute(drop_database("analytics", if_exists=True).to_sql())
```

## CLI & Migrations

CHORM includes a powerful CLI (similar to Alembic) for managing database migrations.

### Initialization

Initialize a new project with the required directory structure:

```bash
chorm init
```

This creates:
- `migrations/versions/` - Directory for migration scripts
- `migrations/env.py` - Configuration script for auto-migrations
- `chorm.toml` - Configuration file

### Configuration (`chorm.toml`)

Configure your database connection and migration settings:

```toml
[chorm]
host = "localhost"
port = 8123
database = "default"
user = "default"
password = ""
secure = false

[migrations]
directory = "migrations"
table_name = "chorm_migrations"
version_style = "uuid" # Options: uuid, int, django
```

**Migration Naming Styles:**
- `uuid` (default): `e4d90..._message.py`
- `int`: `1_message.py`, `2_message.py` (sequential)
- `django`: `0001_message.py`, `0002_message.py` (padded sequential)

### Creating Migrations

Create a new empty migration file:

```bash
chorm make-migration -m "create users table"
```

### Auto-Migrations

Automatically generate migrations by comparing your models with the database.

1.  **Configure `migrations/env.py`**:
    To enable auto-discovery, import your `MetaData` object in `env.py`:

    ```python
    from chorm import MetaData
    # Import your application's metadata
    from myapp.models import metadata as target_metadata
    ```

2.  **Run Auto-Migrate**:

    ```bash
    chorm auto-migrate -m "initial schema"
    ```

    You can also point to a directory of models if not using `env.py`:
    ```bash
    chorm auto-migrate --models ./myapp/models -m "update schema"
    ```

### Applying Migrations

Apply pending migrations:

```bash
chorm migrate
```

### Managing Migrations

Show migration status:
```bash
chorm show-migrations
```

Rollback the last migration:
```bash
chorm downgrade
```

Rollback multiple steps:
```bash
chorm downgrade --steps 3
```

### Connection Pooling

CHORM supports connection pooling for improved performance in high-concurrency applications:

```python
from chorm import create_engine

# Enable connection pooling
engine = create_engine(
    "clickhouse://localhost:8123/default",
    pool_size=10,        # Maximum pooled connections
    max_overflow=20,     # Additional overflow connections
    pool_timeout=30.0,   # Connection acquisition timeout
    pool_recycle=3600    # Recycle connections after 1 hour
)

# Connections are automatically managed
with engine.connection() as conn:
    result = conn.query("SELECT * FROM users")
# Connection automatically returned to pool
```

**Async Connection Pooling:**

```python
from chorm import create_async_engine

# Enable async connection pooling
engine = create_async_engine(
    "clickhouse://localhost:8123/default",
    pool_size=10,
    max_overflow=20
)

# Use async context manager
async with engine.connection() as conn:
    result = await conn.query("SELECT * FROM users")
# Connection automatically returned to pool
```

**Benefits:**
- 5-10x query throughput improvement for high-frequency queries
- Reduced connection overhead
- Thread-safe (sync) and asyncio-safe (async)
- Automatic connection recycling

See [Connection Pooling Guide](docs/pooling_guide.md) for detailed examples.

### Retry Logic with Exponential Backoff

Automatically retry failed operations with configurable backoff:

```python
from chorm import with_retry, RetryConfig

# Configure retry behavior
retry_config = RetryConfig(
    max_attempts=3,       # Maximum retry attempts
    initial_delay=0.1,    # Initial delay in seconds
    max_delay=10.0,       # Maximum delay cap
    exponential_base=2.0, # Backoff multiplier
    jitter=True           # Add random jitter
)

# Apply to any function
@with_retry(retry_config)
def fetch_critical_data():
    with engine.connection() as conn:
        return conn.query("SELECT * FROM critical_table")

# Automatically retries on transient errors
result = fetch_critical_data()
```

**Async Retry:**

```python
from chorm import async_with_retry

@async_with_retry(RetryConfig(max_attempts=5))
async def fetch_data():
    async with engine.connection() as conn:
        return await conn.query("SELECT * FROM users")

result = await fetch_data()
```

**Features:**
- Exponential backoff with jitter to avoid thundering herd
- Configurable retryable error types
- Works with connection pooling
- Automatic retry on network errors, timeouts, and memory errors

### Health Checks

Monitor ClickHouse connection health:

```python
from chorm import create_engine, HealthCheck

engine = create_engine("clickhouse://localhost:8123/default")
health = HealthCheck(engine)

# Quick ping check
if health.ping():
    print("ClickHouse is reachable")

# Detailed status
status = health.get_status()
print(f"Status: {status['status']}")           # "healthy" or "unhealthy"
print(f"Latency: {status['latency_ms']}ms")    # Response time
print(f"Version: {status['version']}")          # ClickHouse version
print(f"Uptime: {status['uptime_seconds']}s")  # Server uptime

# Server information
info = health.get_server_info()
print(f"Database: {info['current_database']}")
print(f"Memory: {info['used_memory']} / {info['total_memory']}")
```

**Async Health Checks:**

```python
from chorm import create_async_engine, AsyncHealthCheck

engine = create_async_engine("clickhouse://localhost:8123/default")
health = AsyncHealthCheck(engine)

# Async health check
if await health.ping():
    status = await health.get_status()
    print(f"Latency: {status['latency_ms']}ms")
```

**Use Cases:**
- Kubernetes liveness/readiness probes
- Load balancer health checks
- Monitoring and alerting
- Circuit breaker implementations

### Query Execution Metrics

Track and analyze query performance:

```python
from chorm import MetricsCollector, enable_global_metrics

# Create metrics collector
collector = MetricsCollector(
    slow_query_threshold_ms=500.0,  # Queries >500ms are "slow"
    log_all_queries=False            # Only log slow queries
)

# Measure query execution
with collector.measure("SELECT * FROM users WHERE active = 1") as metrics:
    result = session.execute(query)

# Get summary statistics
summary = collector.get_summary()
print(f"Total queries: {summary['total_queries']}")
print(f"Average duration: {summary['avg_duration_ms']:.2f}ms")
print(f"Slow queries: {summary['slow_queries']}")

# Get percentiles
percentiles = collector.get_percentiles([50, 90, 95, 99])
print(f"P95: {percentiles['p95']:.2f}ms")

# Get slow queries
slow_queries = collector.get_slow_queries()
for metric in slow_queries:
    print(f"Slow: {metric.sql[:50]} - {metric.duration_ms:.2f}ms")
```

**Global Metrics:**

```python
# Enable global metrics collection
collector = enable_global_metrics(slow_query_threshold_ms=500.0)

# All queries are now tracked automatically
with collector.measure("SELECT 1"):
    result = session.execute(query)

# Get summary
summary = collector.get_summary()
```

### Connection Pool Statistics

Monitor pool utilization and performance:

```python
# Get pool statistics
stats = engine.pool.get_statistics()

print(f"Pool size: {stats['pool_size']}")
print(f"Connections in use: {stats['connections_in_use']}")
print(f"Overflow: {stats['overflow']}")
print(f"Utilization: {stats['utilization_percent']}%")
```

**Complete Monitoring Example:**

```python
from chorm import (
    create_engine, MetricsCollector, HealthCheck
)

# Setup with pooling
engine = create_engine(
    "clickhouse://localhost:8123/default",
    pool_size=10,
    max_overflow=20
)

# Setup monitoring
collector = MetricsCollector(slow_query_threshold_ms=500.0)
health = HealthCheck(engine)

# Check health
if health.ping():
    status = health.get_status()
    print(f"✓ Healthy - Latency: {status['latency_ms']}ms")
else:
    print("✗ Unhealthy - Cannot reach ClickHouse")

# Execute queries with metrics
with collector.measure("SELECT * FROM users"):
    with engine.connection() as conn:
        result = conn.query("SELECT * FROM users LIMIT 100")

# Monitor pool
pool_stats = engine.pool.get_statistics()
print(f"Pool utilization: {pool_stats['utilization_percent']}%")

# Check for slow queries
if collector.get_slow_queries():
    print("⚠ Slow queries detected!")
```

See [examples/monitoring_demo.py](examples/monitoring_demo.py) for complete examples.

### ClickHouse-Optimized Batch Insert

Efficiently insert large volumes of data with ClickHouse-optimized batching:

```python
from chorm import create_engine, bulk_insert

engine = create_engine("clickhouse://localhost:8123/default")
client = engine._client

# Prepare data (1M rows)
data = [
    [i, f"User{i}", f"user{i}@example.com"]
    for i in range(1_000_000)
]

# Insert with optimal batch size (100k rows)
stats = bulk_insert(
    client, "users", data,
    columns=["id", "name", "email"],
    batch_size=100_000  # ClickHouse-optimized
)

print(f"Inserted {stats['total_rows']:,} rows in {stats['batches_sent']} batches")
```

**Advanced Batch Insert:**

```python
from chorm import ClickHouseBatchInsert

# Create batch inserter
batch = ClickHouseBatchInsert(
    client,
    "users",
    columns=["id", "name", "email"],
    batch_size=100_000
)

# Add rows (auto-flushes at 100k rows)
for i in range(1_000_000):
    batch.add_row([i, f"User{i}", f"user{i}@example.com"])

# Flush remaining rows
stats = batch.finish()
```

**DataFrame Support:**

```python
import pandas as pd
from chorm import bulk_insert

df = pd.DataFrame({
    'id': range(1_000_000),
    'name': [f'User{i}' for i in range(1_000_000)]
})

# Automatically detected as DataFrame
stats = bulk_insert(client, "users", df, batch_size=100_000)
```

**Performance Features:**
- Uses native `client.insert()` (5-10x faster than SQL VALUES)
- Default batch size: 100,000 rows (ClickHouse-optimized)
- Automatic batching and flushing
- DataFrame support built-in
- Optional `OPTIMIZE TABLE` after insertion

See [examples/batch_insert_demo.py](examples/batch_insert_demo.py) for complete examples.

### Pandas Integration

CHORM integrates seamlessly with Pandas for both inserting and querying data.

**Query to DataFrame:**

```python
from chorm import select

# Synchronous Session
df = session.query_df(select(User).where(User.id > 0))

# Asynchronous Session
df = await session.query_df(select(User).where(User.id > 0))

# Using raw SQL
df = session.query_df("SELECT * FROM users WHERE id > 0")
```

**Insert from DataFrame:**

See [DataFrame Support](#dataframe-support) in Batch Insert section.


## Advanced Features

### Performance Operations

```python
from chorm import optimize_table, insert, select

# Optimize table (manual merge)
stmt = optimize_table(User, final=True)
session.execute(stmt.to_sql())

# Deduplicate data
stmt = optimize_table(User, deduplicate=True, final=True)
session.execute(stmt.to_sql())

# INSERT FROM SELECT (bulk data copying)
source_query = select(SourceTable.id, SourceTable.name).where(SourceTable.active == 1)
stmt = insert(TargetTable).from_select(source_query, columns=["id", "name"])
session.execute(stmt.to_sql())
```

### Advanced Aggregates

```python
from chorm.sql.expression import top_k, group_bitmap, any_last

# Top-K most frequent values
query = select(
    User.country,
    func.count().label("count")
).select_from(User).group_by(User.country).order_by(func.count().desc()).limit(10)

# Bitmap aggregation for unique counts
query = select(
    Event.date,
    group_bitmap(Event.user_id).label("unique_users")
).select_from(Event).group_by(Event.date)

# Sampling aggregates
query = select(
    User.country,
    any_last(User.last_login).label("latest_login")
).select_from(User).group_by(User.country)
```

### Dictionary Support

```python
from chorm import create_dictionary
from chorm.sql.expression import dict_get, dict_has

# Create dictionary
stmt = create_dictionary(
    "user_dict",
    "ClickHouse(HOST 'localhost' PORT 9000 USER 'default' TABLE 'users' DB 'default')",
    "HASHED",
    [("id", "UInt64"), ("name", "String"), ("country", "String")],
    lifetime=300  # Cache lifetime in seconds
)
session.execute(stmt.to_sql())

# Use dictionary in queries
query = select(
    Order.id,
    dict_get("user_dict", "name", Order.user_id).label("user_name"),
    dict_get("user_dict", "country", Order.user_id).label("user_country")
).select_from(Order)
```

### Materialized Views

CHORM provides first-class support for Materialized Views.

**Declarative Definition:**

```python
from chorm import Table, Column, MaterializedView, MergeTree, select
from chorm.types import UInt64, String

# 1. Define Source Table
class User(Table):
    __tablename__ = "users"
    __engine__ = MergeTree()
    id = Column(UInt64(), primary_key=True)
    name = Column(String())

# 2. Define Materialized View
class UserMV(Table):
    __tablename__ = "users_mv"
    # Reference the source table class directly
    __engine__ = MaterializedView(to_table=User)
    
    # Auto-generate 'SELECT * FROM users'
    __from_table__ = User
    
    # OR define custom logic
    # __select__ = select(User.id, User.name).where(User.id > 100)
    
    # Define columns if needed (introspected automatically if simple view)
```

**Introspection:**

Run `chorm introspect` to generate clean model code for existing Materialized Views, including class references and dependencies.

### Query Observability

```python
# Analyze query execution
query = select(User).where(User.country == 'US')

# Get query plan
explain_stmt = query.explain(explain_type="PLAN")
result = session.execute(explain_stmt.to_sql())

# Profile query (pipeline analysis)
explain_stmt = query.analyze()  # Shortcut for EXPLAIN PIPELINE
result = session.execute(explain_stmt.to_sql())
```

## Documentation

- **[Migration Guide](docs/migration_guide.md)** - Migrate from raw SQL to CHORM
- **[Performance Guide](docs/performance_guide.md)** - Query optimization, bulk operations, indexing strategies
- **[Best Practices](docs/best_practices.md)** - Schema design, query patterns, error handling
- **[Analytics Guide](docs/analytics_guide.md)** - Window functions, CTEs, advanced analytics

## Development

### Setup

```bash
# Clone repository
git clone https://github.com/yourusername/chorm.git
cd chorm

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

### Running Tests

Start ClickHouse with Docker Compose:

```bash
docker-compose up -d
```

Wait for ClickHouse to be ready (check with `docker-compose ps`), then run tests:

```bash
pytest
```

Stop ClickHouse:

```bash
docker-compose down
```

### Running Integration Tests

Integration tests require a running ClickHouse instance:

```bash
# Start ClickHouse
docker-compose up -d

# Wait for healthcheck
docker-compose ps

# Run all tests including integration
pytest

# Run only integration tests
pytest tests/integration/

# Stop ClickHouse
docker-compose down -v  # -v removes volumes
```

## Query Examples

### SELECT with Filters

```python
from chorm import select, func

# Simple select
stmt = select(User.id, User.name).where(User.id > 10)

# With multiple conditions
stmt = select(User).where(
    (User.id > 10) & (User.name.like("A%"))
)

# With ordering and limit
stmt = select(User).order_by(User.name).limit(10)

# With aggregation
stmt = select(func.count(User.id)).where(User.id > 0)
```

### GROUP BY and Aggregation

```python
from chorm import select, func

# Simple GROUP BY
stmt = select(User.city, func.count(User.id)).group_by(User.city)

# GROUP BY with HAVING
stmt = (
    select(User.city, func.count(User.id))
    .group_by(User.city)
    .having(func.count(User.id) > 10)
)

# Multiple aggregations
stmt = (
    select(
        User.city,
        func.count(User.id).label("count"),
        func.avg(User.age).label("avg_age")
    )
    .group_by(User.city)
)
```

### INSERT

```python
from chorm import insert

# Single insert
stmt = insert(User).values(id=1, name="Alice", email="alice@example.com")
session.execute(stmt)

# Bulk insert via session
users = [
    User(id=1, name="Alice", email="alice@example.com"),
    User(id=2, name="Bob", email="bob@example.com"),
]
for user in users:
    session.add(user)
session.commit()
```

### UPDATE (ClickHouse ALTER TABLE)

```python
from chorm import update

stmt = update(User).where(User.id == 1).values(name="Alice Updated")
session.execute(stmt)
```

### DELETE (ClickHouse ALTER TABLE)

```python
from chorm import delete

stmt = delete(User).where(User.id == 1)
session.execute(stmt)
```

## DDL Operations

CHORM provides comprehensive DDL (Data Definition Language) operations for managing database schema:

### DROP TABLE

```python
from chorm import drop_table

# Drop table with IF EXISTS
stmt = drop_table(User)
session.execute(stmt.to_sql())

# Drop without IF EXISTS
stmt = drop_table(User, if_exists=False)
session.execute(stmt.to_sql())
```

### TRUNCATE TABLE

```python
from chorm import truncate_table

# Remove all data from table
stmt = truncate_table(User)
session.execute(stmt.to_sql())
```

### ALTER TABLE - Column Operations

```python
from chorm import add_column, drop_column, modify_column, rename_column

# Add a column
stmt = add_column(User, "age UInt8", after="name")
session.execute(stmt.to_sql())

# Add column with default value
stmt = add_column(User, "status String DEFAULT 'active'")
session.execute(stmt.to_sql())

# Drop a column
stmt = drop_column(User, "old_field")
session.execute(stmt.to_sql())

# Modify column type
stmt = modify_column(User, "age UInt16")
session.execute(stmt.to_sql())

# Rename column
stmt = rename_column(User, "old_name", "new_name")
session.execute(stmt.to_sql())
```

### ALTER TABLE - Index Operations

```python
from chorm import add_index, drop_index
from chorm.sql.expression import Identifier

# Add minmax index
stmt = add_index(User, "idx_email", Identifier("email"))
session.execute(stmt.to_sql())

# Add bloom filter index
stmt = add_index(
    User, 
    "idx_name", 
    Identifier("name"),
    index_type="bloom_filter",
    granularity=4
)
session.execute(stmt.to_sql())

# Drop index
stmt = drop_index(User, "idx_email")
session.execute(stmt.to_sql())
```

### Using DDL in Migrations

DDL operations integrate seamlessly with the migration system:

```python
from chorm.migration import Migration
from chorm.session import Session
from chorm.sql.expression import Identifier

class AddUserAgeColumn(Migration):
    id = "20231203_001"
    name = "Add age column to users"
    
    def upgrade(self, session: Session) -> None:
        # Add column using helper method
        self.add_column(session, 'users', 'age UInt8', after='name')
        
        # Add index
        self.add_index(
            session, 
            'users', 
            'idx_age', 
            Identifier('age'),
            index_type='minmax'
        )
    
    def downgrade(self, session: Session) -> None:
        # Drop index first
        self.drop_index(session, 'users', 'idx_age')
        
        # Then drop column
        self.drop_column(session, 'users', 'age')
```


## ClickHouse-Specific Features

### PREWHERE Clause

```python
stmt = select(User).prewhere(User.id > 1000).where(User.name == "Alice")
```

### FINAL Modifier

```python
stmt = select(User).final()
```

### SAMPLE Clause

```python
stmt = select(User).sample(0.1)  # 10% sample
```

### SETTINGS

```python
stmt = select(User).settings(max_threads=4, max_memory_usage=10000000000)
```

## Analytics Examples

### Window Functions

```python
from chorm import window, func

# Ranking products by sales within each category
w = window(
    partition_by=[Product.category],
    order_by=[func.sum(Order.amount).desc()]
)

stmt = (
    select(
        Product.category,
        Product.name,
        func.sum(Order.amount).label('total_sales'),
        func.row_number().over(w).label('rank')
    )
    .select_from(Order)
    .join(Product, on=Order.product_id == Product.id)
    .group_by(Product.category, Product.name)
)

# Running totals
w_running = window(
    partition_by=[Order.user_id],
    order_by=[Order.created_at],
    rows_between=('UNBOUNDED PRECEDING', 'CURRENT ROW')
)

stmt = select(
    Order.id,
    Order.amount,
    func.sum(Order.amount).over(w_running).label('running_total')
).select_from(Order)
```

### CTEs (Common Table Expressions)

```python
# Multi-step analytics with CTEs
active_users = (
    select(User.id, User.name)
    .where(User.last_login > func.now() - Literal("INTERVAL 30 DAY"))
    .cte('active_users')
)

high_value_orders = (
    select(Order.user_id, func.sum(Order.amount).label('total'))
    .group_by(Order.user_id)
    .having(func.sum(Order.amount) > 1000)
    .cte('high_value')
)

stmt = (
    select(
        Identifier('active_users.name'),
        Identifier('high_value.total')
    )
    .select_from(Identifier('active_users'))
    .join(Identifier('high_value'), 
          on=Identifier('active_users.id') == Identifier('high_value.user_id'))
    .with_cte(active_users, high_value)
)
```

### ARRAY JOIN

```python
# Analyze tags from array column
stmt = (
    select(
        Product.category,
        Identifier('tag'),
        func.count().label('tag_count')
    )
    .select_from(Product)
    .array_join(Product.tags, alias='tag')
    .group_by(Product.category, Identifier('tag'))
)
```

### Conditional Aggregations

```python
from chorm import func

# Multiple metrics in one query
stmt = select(
    User.city,
    func.sumIf(Order.amount, Order.status == 'completed').label('completed_sales'),
    func.sumIf(Order.amount, Order.status == 'pending').label('pending_sales'),
    func.countIf(Order.status == 'cancelled').label('cancelled_count'),
    func.avgIf(Order.amount, Order.status == 'completed').label('avg_order')
).select_from(Order).join(User, on=Order.user_id == User.id).group_by(User.city)
```

### LIMIT BY

```python
# Top 3 orders per user
stmt = (
    select(Order.user_id, Order.id, Order.amount)
    .select_from(Order)
    .order_by(Order.amount.desc())
    .limit_by(3, Order.user_id)
)
```

## Table Engines

CHORM supports all major ClickHouse table engines. Choose the right engine based on your use case:

### MergeTree Family

**MergeTree** - Default engine for most use cases:
```python
from chorm import MergeTree

class User(Table):
    __tablename__ = "users"
    __engine__ = MergeTree()
    # ORDER BY is required for MergeTree
```

**ReplacingMergeTree** - For data with updates (deduplication):
```python
from chorm import ReplacingMergeTree

class User(Table):
    __tablename__ = "users"
    __engine__ = ReplacingMergeTree(version_column="updated_at")
    # Keeps only the latest version based on version_column
```

**SummingMergeTree** - For pre-aggregated metrics:
```python
from chorm import SummingMergeTree

class Metrics(Table):
    __tablename__ = "metrics"
    __engine__ = SummingMergeTree(columns=["value", "count"])
    # Automatically sums numeric columns during merges
```

**AggregatingMergeTree** - For pre-aggregated data with aggregate functions:
```python
from chorm import AggregatingMergeTree

class AggregatedStats(Table):
    __tablename__ = "aggregated_stats"
    __engine__ = AggregatingMergeTree()
    # Stores pre-computed aggregates
```

**CollapsingMergeTree** - For data with sign-based updates:
```python
from chorm import CollapsingMergeTree

class Events(Table):
    __tablename__ = "events"
    __engine__ = CollapsingMergeTree(sign_column="sign")
    # sign=1 for insert, sign=-1 for delete
```

**VersionedCollapsingMergeTree** - CollapsingMergeTree with versioning:
```python
from chorm import VersionedCollapsingMergeTree

class Events(Table):
    __tablename__ = "events"
    __engine__ = VersionedCollapsingMergeTree(sign_column="sign", version_column="version")
```

**GraphiteMergeTree** - For Graphite metrics:
```python
from chorm import GraphiteMergeTree

class GraphiteData(Table):
    __tablename__ = "graphite"
    __engine__ = GraphiteMergeTree(config_element="graphite_rollup")
```

### Replicated Engines

All MergeTree engines have replicated versions for high availability:

```python
from chorm import (
    ReplicatedMergeTree,
    ReplicatedReplacingMergeTree,
    ReplicatedSummingMergeTree,
    ReplicatedAggregatingMergeTree,
    ReplicatedCollapsingMergeTree,
    ReplicatedVersionedCollapsingMergeTree,
    ReplicatedGraphiteMergeTree
)

class ReplicatedUser(Table):
    __tablename__ = "users"
    __engine__ = ReplicatedMergeTree(
        zookeeper_path="/clickhouse/tables/users",
        replica_name="replica1"
    )
```

### Log Engines

For small tables and temporary data:

```python
from chorm import Log, TinyLog, StripeLog

# Log - General purpose log engine
class TempData(Table):
    __tablename__ = "temp"
    __engine__ = Log()

# TinyLog - Minimal overhead
class SmallTable(Table):
    __tablename__ = "small"
    __engine__ = TinyLog()

# StripeLog - Better for writes
class WriteHeavy(Table):
    __tablename__ = "writes"
    __engine__ = StripeLog()
```

### Special Engines

**Memory** - In-memory storage:
```python
from chorm import Memory

class Cache(Table):
    __tablename__ = "cache"
    __engine__ = Memory()
```

**Distributed** - Distributed tables across cluster:
```python
from chorm import Distributed

class DistributedUser(Table):
    __tablename__ = "users_distributed"
    __engine__ = Distributed(
        cluster="my_cluster",
        database="default",
        table="users"
    )
```

**Kafka** - Kafka integration:
```python
from chorm import Kafka

class KafkaEvents(Table):
    __tablename__ = "kafka_events"
    __engine__ = Kafka()
```

**External Data Sources:**
```python
from chorm import MySQL, PostgreSQL, ODBC, JDBC

# MySQL
class MySQLTable(Table):
    __engine__ = MySQL(
        host="mysql.example.com",
        database="db",
        table="table",
        user="user",
        password="pass"
    )

# PostgreSQL
class PostgresTable(Table):
    __engine__ = PostgreSQL(
        host="postgres.example.com",
        database="db",
        table="table",
        user="user",
        password="pass"
    )
```

**Other Engines:**
- `File` - File-based storage
- `Null` - Discards writes, returns empty reads
- `Set` - Set data structure
- `Join` - Join table for JOIN operations
- `View` - Materialized view

See [Best Practices Guide](docs/best_practices.md) for guidance on choosing the right engine.

## ClickHouse-Specific Features

## Type System

CHORM supports all ClickHouse types:

```python
from chorm.types import (
    # Integers
    UInt8, UInt16, UInt32, UInt64,
    Int8, Int16, Int32, Int64,
    
    # Floats
    Float32, Float64,
    
    # Strings
    String, FixedString,
    
    # Dates
    Date, DateTime,
    
    # Special
    UUID, Decimal, JSON,
    
    # Composite
    Array, Nullable, Map, Tuple, LowCardinality
)

class Event(Table):
    __tablename__ = "events"
    __engine__ = MergeTree()
    
    id = Column(UInt64(), primary_key=True)
    tags = Column(Array(String()))
    metadata = Column(Map(String(), String()))
    optional_field = Column(Nullable(String()))
```

## Documentation

- **[Analytics Guide](docs/analytics_guide.md)** - Patterns for cohort analysis, funnels, time-series, and more
- **[Performance Guide](docs/performance.md)** - Optimization tips and best practices
- **[Examples](examples/)** - Working code examples for all features

## License

MIT

## Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests.
