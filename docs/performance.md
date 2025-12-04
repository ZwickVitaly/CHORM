# CHORM Performance Guide

This guide covers best practices for optimizing ClickHouse queries using CHORM.

## Table of Contents
- [ClickHouse Optimization Basics](#clickhouse-optimization-basics)
- [Query Optimization Patterns](#query-optimization-patterns)
- [CHORM-Specific Tips](#chorm-specific-tips)
- [Monitoring & Profiling](#monitoring--profiling)

---

## ClickHouse Optimization Basics

### Primary Key Selection

The primary key (ORDER BY clause) is critical for query performance in ClickHouse.

**Best Practices:**
- Order columns by cardinality (low to high)
- Place frequently filtered columns first
- Consider query patterns when designing the key

```python
from chorm import Table, Column, MergeTree
from chorm.types import UInt64, String, DateTime

class Event(Table):
    __tablename__ = "events"
    
    user_id = Column(UInt64())
    event_type = Column(String())
    timestamp = Column(DateTime())
    
    # Good: Low cardinality (event_type) → Medium (user_id) → High (timestamp)
    __order_by__ = ("event_type", "user_id", "timestamp")
    
    engine = MergeTree()
```

### Partition Key Strategy

Partitions help with data management and query performance.

**Guidelines:**
- Partition by time periods (day, month, year)
- Keep partition count reasonable (< 1000)
- Align partitions with data retention policies

```python
class UserActivity(Table):
    __tablename__ = "user_activity"
    
    date = Column(Date())
    user_id = Column(UInt64())
    action = Column(String())
    
    # Partition by month for monthly data retention
    __partition_by__ = ("toYYYYMM(date)",)
    __order_by__ = ("date", "user_id")
    
    engine = MergeTree()
```

### ORDER BY Importance

The ORDER BY clause determines:
1. **Data storage order** on disk
2. **Primary index** structure
3. **Query performance** for range scans

**Impact:**
- Queries filtering on ORDER BY columns are 10-100x faster
- Non-indexed columns require full table scans

---

## Query Optimization Patterns

### PREWHERE vs WHERE

`PREWHERE` is a ClickHouse optimization that filters data before reading all columns.

**When to use PREWHERE:**
- Filtering on indexed columns
- Conditions that eliminate many rows
- Before expensive column reads

```python
from chorm import select

# Good: Filter on indexed column first
stmt = (
    select(User.id, User.name, User.metadata)
    .prewhere(User.id > 1000)  # Fast: indexed column
    .where(User.metadata.like('%premium%'))  # Slower: after PREWHERE
)

# Less optimal: No PREWHERE
stmt = select(User).where(
    (User.id > 1000) & (User.metadata.like('%premium%'))
)
```

### Using FINAL Sparingly

`FINAL` merges duplicate rows but is expensive.

**Alternatives:**
- Use `ReplacingMergeTree` with manual deduplication
- Use `GROUP BY` with `argMax()` for latest values
- Schedule background merges

```python
from chorm.sql.expression import func

# Instead of FINAL:
# stmt = select(User).final()

# Better: Manual deduplication
stmt = (
    select(
        User.id,
        func.argMax(User.name, User.updated_at).label('name'),
        func.argMax(User.email, User.updated_at).label('email')
    )
    .group_by(User.id)
)
```

### Efficient JOINs

ClickHouse performs best with dimension table JOINs.

**Best Practices:**
- Keep dimension tables small (< 10M rows)
- Use `GLOBAL` for distributed queries
- Consider denormalization for large fact tables

```python
# Good: Small dimension table
stmt = (
    select(Order.id, User.name, Order.amount)
    .select_from(Order)
    .join(User, on=Order.user_id == User.id)  # User is small
)

# Consider denormalization if User is large:
# Store user_name directly in Order table
```

### Array Operations Best Practices

Arrays are powerful but require careful usage.

**Tips:**
- Use `ARRAY JOIN` to unnest arrays efficiently
- Prefer `arrayFilter()` over multiple conditions
- Use `has()` for membership checks

```python
from chorm.sql.expression import func

# Efficient array filtering
stmt = select(
    User.id,
    func.arrayFilter(lambda x: x > 0, User.scores).label('positive_scores')
).select_from(User)

# Efficient membership check
stmt = select(User).where(
    func.has(User.tags, 'premium')
)

# ARRAY JOIN for unnesting
stmt = (
    select(User.id, Identifier('tag'))
    .select_from(User)
    .array_join(User.tags, alias='tag')
)
```

---

## CHORM-Specific Tips

### Window Functions

Window functions are powerful but can be expensive.

**Optimization:**
- Limit the window frame size
- Use `ROWS BETWEEN` for bounded windows
- Consider materialized views for repeated calculations

```python
from chorm.sql.expression import window, func

# Good: Bounded window
w = window(
    partition_by=[Order.user_id],
    order_by=[Order.timestamp],
    rows_between=('UNBOUNDED PRECEDING', 'CURRENT ROW')
)

stmt = select(
    Order.id,
    func.sum(Order.amount).over(w).label('running_total')
).select_from(Order)

# For repeated queries, consider materialized views
```

### CTE Performance

CTEs (Common Table Expressions) are inlined by ClickHouse.

**Guidelines:**
- Use CTEs for readability, not performance
- Complex CTEs may be computed multiple times
- Consider temporary tables for large intermediate results

```python
# CTE is fine for readability
active_users = (
    select(User.id)
    .where(User.last_login > func.now() - Literal("INTERVAL 30 DAY"))
    .cte('active_users')
)

stmt = (
    select(func.count())
    .select_from(Identifier('active_users'))
    .with_cte(active_users)
)
```

### Aggregation Function Selection

Choose the right aggregation function for your needs.

**Performance comparison:**
- `count()` - Fastest
- `uniq()` - Fast approximate unique count (2% error)
- `uniqExact()` - Exact but slower
- `groupArray()` - Memory intensive for large groups

```python
from chorm.sql.expression import func

# Fast approximate count
stmt = select(func.uniq(User.id)).select_from(User)

# Use exact only when necessary
stmt = select(func.uniqExact(User.id)).select_from(User)

# Limit array aggregations
stmt = (
    select(
        User.city,
        func.groupArray(User.name).label('users')
    )
    .group_by(User.city)
    .having(func.count() < 1000)  # Prevent huge arrays
)
```

### Batch Insert Strategies

Batch inserts are much faster than individual inserts.

**Best Practices:**
- Insert in batches of 10,000-100,000 rows
- Use async inserts for high throughput
- Consider `async_insert` setting

```python
from chorm import insert

# Good: Batch insert
users = [User(id=i, name=f"User{i}") for i in range(10000)]

# Insert in single batch
stmt = insert(User).values([u.to_dict() for u in users])
session.execute(stmt)

# Or use session.add() with commit batching
for user in users:
    session.add(user)
    if len(session._pending_inserts) >= 10000:
        session.commit()
session.commit()
```

---

## Monitoring & Profiling

### Using SETTINGS for Query Tuning

ClickHouse SETTINGS allow per-query optimization.

```python
# Increase parallelism
stmt = (
    select(func.count())
    .select_from(User)
    .settings(max_threads=8)
)

# Memory limits
stmt = (
    select(User)
    .settings(
        max_memory_usage=10_000_000_000,  # 10GB
        max_bytes_before_external_group_by=5_000_000_000
    )
)

# Enable query profiling
stmt = select(User).settings(log_queries=1, log_query_threads=1)
```

### Query Log Analysis

Use `system.query_log` to analyze query performance.

```python
# Find slow queries
stmt = select(
    Identifier('query'),
    Identifier('query_duration_ms'),
    Identifier('read_rows'),
    Identifier('memory_usage')
).select_from(Identifier('system.query_log')).where(
    Identifier('query_duration_ms') > 1000
).order_by(Identifier('query_duration_ms').desc()).limit(10)

results = session.execute(stmt).all()
for row in results:
    print(f"Duration: {row.query_duration_ms}ms, Rows: {row.read_rows}")
```

### Memory Usage Patterns

**Monitor:**
- Peak memory usage per query
- Memory for GROUP BY operations
- Array/Map column memory

**Optimization:**
- Use `LowCardinality` for string columns with < 10K unique values
- Limit `groupArray()` result sizes
- Use `max_memory_usage` setting

```python
from chorm.types import LowCardinality, String

class Event(Table):
    __tablename__ = "events"
    
    # Good: Low cardinality string
    event_type = Column(LowCardinality(String()))  # ~100 unique values
    
    # Regular string for high cardinality
    user_agent = Column(String())  # Millions of unique values
    
    engine = MergeTree()
```

---

## Performance Checklist

Before deploying to production:

- [ ] **Primary key** optimized for query patterns
- [ ] **Partitioning** strategy defined
- [ ] **PREWHERE** used for indexed column filters
- [ ] **FINAL** avoided or minimized
- [ ] **Batch inserts** implemented (10K+ rows)
- [ ] **Window functions** have bounded frames
- [ ] **Array operations** use appropriate functions
- [ ] **Memory limits** configured via SETTINGS
- [ ] **Query logging** enabled for monitoring
- [ ] **LowCardinality** used for appropriate columns

---

## Additional Resources

- [ClickHouse Performance Documentation](https://clickhouse.com/docs/en/operations/performance)
- [ClickHouse Query Optimization](https://clickhouse.com/docs/en/guides/improving-query-performance)
- [CHORM Examples](../examples/)
