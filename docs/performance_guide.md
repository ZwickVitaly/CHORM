# CHORM Performance Tuning Guide

## Table of Contents
- [Query Optimization](#query-optimization)
- [Bulk Operations](#bulk-operations)
- [Table Engine Selection](#table-engine-selection)
- [Indexing Strategies](#indexing-strategies)
- [Monitoring & Profiling](#monitoring--profiling)

## Query Optimization

### Use PREWHERE for Filtering

PREWHERE is executed before reading all columns, significantly improving performance:

```python
from chorm import select, Table, Column
from chorm.types import UInt64, String, Date

# Good: Use PREWHERE for filtering
query = select(User).prewhere(User.country == 'US').where(User.active == 1)

# Less optimal: Only WHERE
query = select(User).where((User.country == 'US') & (User.active == 1))
```

### Leverage FINAL Modifier Carefully

`FINAL` forces data deduplication but impacts performance:

```python
# Use FINAL only when necessary
query = select(User).final().where(User.id == 123)

# Better: Design schema to avoid FINAL
# Use ReplacingMergeTree with proper ORDER BY
```

### Optimize Aggregations

```python
from chorm.sql.expression import func

# Good: Use specialized aggregates
query = select(
    func.uniq(User.id),  # Approximate unique count (fast)
    func.count()
).select_from(User)

# Less optimal: uniqExact (slower but precise)
query = select(func.uniqExact(User.id)).select_from(User)
```

### Use LIMIT BY for Top-N per Group

```python
# Get top 3 orders per user
query = (
    select(Order)
    .order_by(Order.user_id, Order.created_at.desc())
    .limit_by(3, Order.user_id)
)
```

## Bulk Operations

### Batch Inserts

Always use batch inserts for better performance:

```python
from chorm import Session, insert

# Good: Batch insert
users = [
    {"id": i, "name": f"User{i}", "email": f"user{i}@example.com"}
    for i in range(10000)
]
stmt = insert(User).values(users)
session.execute(stmt.to_sql())

# Bad: Individual inserts in a loop
for user in users:
    stmt = insert(User).values(user)
    session.execute(stmt.to_sql())  # Very slow!
```

### INSERT FROM SELECT

Use `INSERT FROM SELECT` for efficient data copying:

```python
from chorm import insert, select

# Efficient: Single query
source_query = select(
    SourceTable.id,
    SourceTable.name,
    SourceTable.value
).where(SourceTable.active == 1)

stmt = insert(TargetTable).from_select(source_query)
session.execute(stmt.to_sql())
```

### OPTIMIZE TABLE

Manually trigger merges for better query performance:

```python
from chorm import optimize_table

# Force final merge
stmt = optimize_table(User, final=True)
session.execute(stmt.to_sql())

# Deduplicate data
stmt = optimize_table(User, deduplicate=True, final=True)
session.execute(stmt.to_sql())

# Optimize specific partition
stmt = optimize_table(Events, partition='2024-01', final=True)
session.execute(stmt.to_sql())
```

## Table Engine Selection

### MergeTree (Default)

Best for most use cases:

```python
from chorm import Table, Column
from chorm.table_engines import MergeTree
from chorm.types import UInt64, String, DateTime

class User(Table):
    __tablename__ = "users"
    __engine__ = MergeTree()
    __order_by__ = ["id"]
    
    id = Column(UInt64())
    name = Column(String())
    created_at = Column(DateTime())
```

### ReplacingMergeTree

For data with updates (deduplication):

```python
from chorm.table_engines import ReplacingMergeTree

class User(Table):
    __tablename__ = "users"
    __engine__ = ReplacingMergeTree(ver="version")
    __order_by__ = ["id"]
    
    id = Column(UInt64())
    name = Column(String())
    version = Column(UInt64())  # Version column
```

### SummingMergeTree

For pre-aggregated data:

```python
from chorm.table_engines import SummingMergeTree

class UserStats(Table):
    __tablename__ = "user_stats"
    __engine__ = SummingMergeTree()
    __order_by__ = ["user_id", "date"]
    
    user_id = Column(UInt64())
    date = Column(Date())
    clicks = Column(UInt64())  # Will be summed
    views = Column(UInt64())   # Will be summed
```

### AggregatingMergeTree

For complex aggregations:

```python
from chorm.table_engines import AggregatingMergeTree

class UserMetrics(Table):
    __tablename__ = "user_metrics"
    __engine__ = AggregatingMergeTree()
    __order_by__ = ["user_id", "date"]
    
    user_id = Column(UInt64())
    date = Column(Date())
    # Use AggregateFunction types for state storage
```

## Indexing Strategies

### Primary Key (ORDER BY)

Choose ORDER BY carefully - it's your primary index:

```python
# Good: Queries filter by user_id first
class Order(Table):
    __order_by__ = ["user_id", "created_at"]

# Query benefits from index
query = select(Order).where(Order.user_id == 123)

# Bad: ORDER BY doesn't match query patterns
class Order(Table):
    __order_by__ = ["created_at"]  # user_id queries won't use index
```

### Secondary Indexes

Add indexes for specific query patterns:

```python
from chorm.sql.ddl import add_index

# Add minmax index for range queries
stmt = add_index(
    User,
    name="idx_created_at",
    expression="created_at",
    index_type="minmax",
    granularity=1
)
session.execute(stmt.to_sql())

# Add bloom filter for equality checks
stmt = add_index(
    User,
    name="idx_email",
    expression="email",
    index_type="bloom_filter",
    granularity=1
)
session.execute(stmt.to_sql())
```

### Partition Key

Partition by time for efficient data management:

```python
class Events(Table):
    __tablename__ = "events"
    __engine__ = MergeTree()
    __order_by__ = ["user_id", "timestamp"]
    __partition_by__ = "toYYYYMM(timestamp)"  # Monthly partitions
    
    user_id = Column(UInt64())
    timestamp = Column(DateTime())
    event_type = Column(String())
```

## Monitoring & Profiling

### EXPLAIN Queries

Analyze query execution:

```python
# Get query plan
query = select(User).where(User.country == 'US')
explain_stmt = query.explain(explain_type="PLAN")
result = session.execute(explain_stmt.to_sql())
print(result)

# Profile query execution
explain_stmt = query.analyze()  # Shortcut for EXPLAIN PIPELINE
result = session.execute(explain_stmt.to_sql())
print(result)
```

### Query Settings

Tune query execution:

```python
# Limit memory usage
query = select(User).settings(max_memory_usage=10000000000)

# Increase parallelism
query = select(User).settings(max_threads=8)

# Enable query profiling
query = select(User).settings(
    log_queries=1,
    log_query_threads=1
)
```

### System Tables

Monitor performance using system tables:

```python
# Check query log
query_log = select(Identifier("*")).select_from("system.query_log").limit(10)

# Check table sizes
parts = select(
    Identifier("table"),
    Identifier("sum(bytes)").label("size")
).select_from("system.parts").group_by(Identifier("table"))

# Monitor merges
merges = select(Identifier("*")).select_from("system.merges")
```

## Best Practices Summary

1. **Always use batch inserts** - 100x faster than individual inserts
2. **Choose ORDER BY based on query patterns** - It's your primary index
3. **Use PREWHERE for filtering** - Reduces data read
4. **Partition by time** - Enables efficient data lifecycle management
5. **Use appropriate table engine** - ReplacingMergeTree for updates, SummingMergeTree for aggregates
6. **Monitor with EXPLAIN** - Profile queries before production
7. **Leverage specialized aggregates** - uniq, topK, groupBitmap for analytics
8. **Use INSERT FROM SELECT** - More efficient than application-side data copying
9. **OPTIMIZE TABLE periodically** - Especially after bulk operations
10. **Set appropriate SETTINGS** - Control memory, threads, timeouts

## Performance Checklist

- [ ] Batch size ≥ 1000 rows for inserts
- [ ] ORDER BY matches primary query filters
- [ ] PREWHERE used for selective filtering
- [ ] Partitioning strategy defined for large tables
- [ ] Secondary indexes added for common queries
- [ ] Table engine matches use case
- [ ] Query SETTINGS configured appropriately
- [ ] EXPLAIN used to verify query plans
- [ ] Monitoring enabled (system.query_log)
- [ ] Regular OPTIMIZE TABLE scheduled
