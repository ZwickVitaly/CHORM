# CHORM Best Practices

## Table of Contents
- [Schema Design](#schema-design)
- [Query Patterns](#query-patterns)
- [Data Modeling](#data-modeling)
- [Error Handling](#error-handling)
- [Testing](#testing)

## Schema Design

### 1. Choose the Right Table Engine

```python
from chorm import Table, Column
from chorm.table_engines import MergeTree, ReplacingMergeTree, SummingMergeTree

# ✅ Good: Use MergeTree for append-only data
class Event(Table):
    __engine__ = MergeTree()
    __order_by__ = ["user_id", "timestamp"]

# ✅ Good: Use ReplacingMergeTree for data with updates
class User(Table):
    __engine__ = ReplacingMergeTree(ver="updated_at")
    __order_by__ = ["id"]

# ✅ Good: Use SummingMergeTree for metrics
class Metrics(Table):
    __engine__ = SummingMergeTree()
    __order_by__ = ["user_id", "date"]
```

### 2. Design ORDER BY for Query Patterns

```python
# ✅ Good: ORDER BY matches WHERE clauses
class Order(Table):
    __order_by__ = ["user_id", "created_at"]
    # Queries like: WHERE user_id = X AND created_at > Y

# ❌ Bad: ORDER BY doesn't match queries
class Order(Table):
    __order_by__ = ["id"]
    # But queries are: WHERE user_id = X  # Won't use index!
```

### 3. Use Appropriate Data Types

```python
from chorm.types import UInt64, String, LowCardinality, DateTime64

# ✅ Good: Use LowCardinality for enum-like columns
class Event(Table):
    event_type = Column(LowCardinality(String()))  # ~10-100 unique values
    country = Column(LowCardinality(String()))     # ~200 unique values

# ✅ Good: Use DateTime64 for millisecond precision
class Event(Table):
    timestamp = Column(DateTime64(precision=3))  # Milliseconds

# ❌ Bad: String for numeric IDs
class User(Table):
    id = Column(String())  # Should be UInt64!
```

### 4. Partition Large Tables

```python
# ✅ Good: Partition by time for lifecycle management
class Events(Table):
    __partition_by__ = "toYYYYMM(timestamp)"  # Monthly partitions
    __order_by__ = ["user_id", "timestamp"]
    
# Enables efficient partition dropping:
# ALTER TABLE events DROP PARTITION '202401'
```

## Query Patterns

### 1. Use PREWHERE for Selective Filtering

```python
from chorm import select

# ✅ Good: PREWHERE for high-selectivity filters
query = (
    select(Event)
    .prewhere(Event.country == 'US')  # Filters early
    .where(Event.event_type == 'click')
)

# ❌ Bad: All filters in WHERE
query = select(Event).where(
    (Event.country == 'US') & (Event.event_type == 'click')
)
```

### 2. Batch Operations

```python
# ✅ Good: Batch insert
users = [{"id": i, "name": f"User{i}"} for i in range(1000)]
stmt = insert(User).values(users)

# ❌ Bad: Individual inserts
for user in users:
    stmt = insert(User).values(user)  # 1000 queries!
```

### 3. Use CTEs for Readability

```python
from chorm import cte

# ✅ Good: Use CTEs for complex queries
active_users = cte(
    select(User.id).where(User.active == 1),
    name="active_users"
)

query = (
    select(Order)
    .with_cte(active_users)
    .where(Order.user_id.in_(select(active_users.c.id)))
)

# ❌ Bad: Nested subqueries
query = select(Order).where(
    Order.user_id.in_(
        select(User.id).where(User.active == 1)
    )
)
```

### 4. Leverage Window Functions

```python
from chorm.sql.expression import func

# ✅ Good: Use window functions for rankings
query = select(
    User.id,
    User.name,
    func.row_number().over(
        partition_by=[User.country],
        order_by=[User.score.desc()]
    ).label("rank")
).select_from(User)
```

## Data Modeling

### 1. Denormalize for Performance

```python
# ✅ Good: Denormalized for analytics
class OrderFact(Table):
    order_id = Column(UInt64())
    user_id = Column(UInt64())
    user_name = Column(String())      # Denormalized
    user_country = Column(String())   # Denormalized
    product_id = Column(UInt64())
    product_name = Column(String())   # Denormalized
    amount = Column(Decimal(18, 2))

# ❌ Bad: Normalized (requires JOINs)
class Order(Table):
    order_id = Column(UInt64())
    user_id = Column(UInt64())  # Requires JOIN with users
    product_id = Column(UInt64())  # Requires JOIN with products
```

### 2. Use Materialized Views for Aggregates

```python
from chorm.sql.ddl import create_materialized_view

# ✅ Good: Pre-aggregate with materialized view
mv_query = select(
    Event.user_id,
    func.toDate(Event.timestamp).label("date"),
    func.count().label("event_count"),
    func.uniq(Event.session_id).label("session_count")
).select_from(Event).group_by(
    Event.user_id,
    func.toDate(Event.timestamp)
)

stmt = create_materialized_view(
    "user_daily_stats",
    mv_query,
    engine=SummingMergeTree(),
    populate=False
)
```

### 3. Design for Time-Series Data

```python
# ✅ Good: Optimized for time-series
class Metrics(Table):
    __engine__ = MergeTree()
    __order_by__ = ["metric_name", "timestamp"]
    __partition_by__ = "toYYYYMM(timestamp)"
    __ttl__ = "timestamp + INTERVAL 90 DAY"  # Auto-cleanup
    
    metric_name = Column(LowCardinality(String()))
    timestamp = Column(DateTime())
    value = Column(Float64())
```

## Error Handling

### 1. Handle Connection Errors

```python
from chorm import create_engine, Session
from chorm.exceptions import ConnectionError

try:
    engine = create_engine("clickhouse://localhost:8123")
    session = Session(engine)
    result = session.execute("SELECT 1")
except ConnectionError as e:
    print(f"Failed to connect: {e}")
    # Implement retry logic or fallback
```

### 2. Validate Data Before Insert

```python
# ✅ Good: Validate before insert
def insert_user(user_data):
    if not user_data.get("email"):
        raise ValueError("Email is required")
    
    if user_data.get("age", 0) < 0:
        raise ValueError("Age must be positive")
    
    stmt = insert(User).values(user_data)
    session.execute(stmt.to_sql())
```

### 3. Use Transactions Carefully

```python
# ⚠️ Note: ClickHouse has limited transaction support
# Use batch operations instead

# ✅ Good: Batch insert (atomic)
stmt = insert(User).values(users_batch)
session.execute(stmt.to_sql())

# ❌ Bad: Expecting ACID transactions
# ClickHouse doesn't support traditional transactions
```

## Testing

### 1. Use Integration Tests

```python
import pytest
from chorm import create_engine, Session

@pytest.fixture
def engine():
    return create_engine("clickhouse://localhost:8123")

@pytest.fixture
def setup_table(engine):
    engine.execute(User.create_table())
    yield
    engine.execute("DROP TABLE IF EXISTS users")

def test_user_insert(engine, setup_table):
    stmt = insert(User).values({"id": 1, "name": "Test"})
    engine.execute(stmt.to_sql())
    
    result = engine.execute("SELECT count() FROM users")
    assert result[0][0] == 1
```

### 2. Test Query Generation

```python
def test_query_generation():
    query = select(User).where(User.active == 1)
    sql = query.to_sql()
    
    assert "WHERE" in sql
    assert "active = 1" in sql
```

### 3. Mock for Unit Tests

```python
from unittest.mock import Mock

def test_user_service():
    mock_session = Mock()
    mock_session.execute.return_value = [{"id": 1, "name": "Test"}]
    
    service = UserService(mock_session)
    users = service.get_active_users()
    
    assert len(users) == 1
    assert users[0]["name"] == "Test"
```

## Common Pitfalls

### ❌ Don't: Use FINAL Everywhere

```python
# ❌ Bad: FINAL on every query (slow!)
query = select(User).final()

# ✅ Good: Design schema to avoid FINAL
class User(Table):
    __engine__ = ReplacingMergeTree(ver="version")
    __order_by__ = ["id"]
```

### ❌ Don't: Ignore ORDER BY

```python
# ❌ Bad: Random ORDER BY
class Event(Table):
    __order_by__ = ["id"]  # But queries filter by user_id!

# ✅ Good: ORDER BY matches queries
class Event(Table):
    __order_by__ = ["user_id", "timestamp"]
```

### ❌ Don't: Use String for Everything

```python
# ❌ Bad: String for numeric data
class Metrics(Table):
    value = Column(String())  # Should be Float64!
    count = Column(String())  # Should be UInt64!

# ✅ Good: Appropriate types
class Metrics(Table):
    value = Column(Float64())
    count = Column(UInt64())
```

### ❌ Don't: Forget About Partitions

```python
# ❌ Bad: No partitioning for large table
class Events(Table):
    __engine__ = MergeTree()
    __order_by__ = ["timestamp"]
    # Table grows indefinitely!

# ✅ Good: Partition + TTL
class Events(Table):
    __engine__ = MergeTree()
    __order_by__ = ["timestamp"]
    __partition_by__ = "toYYYYMM(timestamp)"
    __ttl__ = "timestamp + INTERVAL 90 DAY"
```

## Quick Reference

| Task | Best Practice |
|------|---------------|
| Append-only data | `MergeTree` |
| Data with updates | `ReplacingMergeTree` |
| Pre-aggregated metrics | `SummingMergeTree` |
| Enum-like columns | `LowCardinality(String())` |
| High-selectivity filter | Use `PREWHERE` |
| Bulk insert | Batch ≥1000 rows |
| Complex query | Use CTEs |
| Time-series data | Partition by month + TTL |
| Analytics | Denormalize + Materialized Views |
| Testing | Integration tests with real ClickHouse |
