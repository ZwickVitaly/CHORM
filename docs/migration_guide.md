# Migration Guide: From Raw SQL to CHORM

This guide helps you migrate from raw ClickHouse SQL queries to CHORM's ORM syntax.

## Table of Contents
- [Basic Queries](#basic-queries)
- [Filtering & Conditions](#filtering--conditions)
- [Joins](#joins)
- [Aggregations](#aggregations)
- [Advanced Features](#advanced-features)
- [DDL Operations](#ddl-operations)

## Basic Queries

### SELECT *

**Raw SQL:**
```sql
SELECT * FROM users
```

**CHORM:**
```python
from chorm import select

query = select(User)
# or
query = select(User.id, User.name, User.email)
```

### SELECT with LIMIT

**Raw SQL:**
```sql
SELECT * FROM users LIMIT 10
```

**CHORM:**
```python
query = select(User).limit(10)
```

### SELECT with ORDER BY

**Raw SQL:**
```sql
SELECT * FROM users ORDER BY created_at DESC
```

**CHORM:**
```python
query = select(User).order_by(User.created_at.desc())
```

## Filtering & Conditions

### Simple WHERE

**Raw SQL:**
```sql
SELECT * FROM users WHERE country = 'US'
```

**CHORM:**
```python
query = select(User).where(User.country == 'US')
```

### Multiple Conditions (AND)

**Raw SQL:**
```sql
SELECT * FROM users WHERE country = 'US' AND active = 1
```

**CHORM:**
```python
query = select(User).where(
    (User.country == 'US') & (User.active == 1)
)
# or chain .where() calls
query = select(User).where(User.country == 'US').where(User.active == 1)
```

### OR Conditions

**Raw SQL:**
```sql
SELECT * FROM users WHERE country = 'US' OR country = 'UK'
```

**CHORM:**
```python
query = select(User).where(
    (User.country == 'US') | (User.country == 'UK')
)
```

### IN Clause

**Raw SQL:**
```sql
SELECT * FROM users WHERE country IN ('US', 'UK', 'DE')
```

**CHORM:**
```python
query = select(User).where(User.country.in_(['US', 'UK', 'DE']))
```

### LIKE Pattern

**Raw SQL:**
```sql
SELECT * FROM users WHERE email LIKE '%@gmail.com'
```

**CHORM:**
```python
query = select(User).where(User.email.like('%@gmail.com'))
```

### BETWEEN

**Raw SQL:**
```sql
SELECT * FROM events WHERE timestamp BETWEEN '2024-01-01' AND '2024-12-31'
```

**CHORM:**
```python
from datetime import datetime

query = select(Event).where(
    Event.timestamp.between(
        datetime(2024, 1, 1),
        datetime(2024, 12, 31)
    )
)
```

### PREWHERE (ClickHouse-specific)

**Raw SQL:**
```sql
SELECT * FROM events PREWHERE country = 'US' WHERE event_type = 'click'
```

**CHORM:**
```python
query = select(Event).prewhere(Event.country == 'US').where(Event.event_type == 'click')
```

## Joins

### INNER JOIN

**Raw SQL:**
```sql
SELECT u.name, o.amount
FROM users u
INNER JOIN orders o ON u.id = o.user_id
```

**CHORM:**
```python
query = (
    select(User.name, Order.amount)
    .select_from(User)
    .join(Order, User.id == Order.user_id)
)
```

### LEFT JOIN

**Raw SQL:**
```sql
SELECT u.name, o.amount
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
```

**CHORM:**
```python
query = (
    select(User.name, Order.amount)
    .select_from(User)
    .left_join(Order, User.id == Order.user_id)
)
```

### Multiple JOINs

**Raw SQL:**
```sql
SELECT u.name, o.amount, p.name as product_name
FROM users u
INNER JOIN orders o ON u.id = o.user_id
INNER JOIN products p ON o.product_id = p.id
```

**CHORM:**
```python
query = (
    select(User.name, Order.amount, Product.name.label('product_name'))
    .select_from(User)
    .join(Order, User.id == Order.user_id)
    .join(Product, Order.product_id == Product.id)
)
```

## Aggregations

### COUNT

**Raw SQL:**
```sql
SELECT COUNT(*) FROM users
```

**CHORM:**
```python
from chorm.sql.expression import func

query = select(func.count()).select_from(User)
```

### GROUP BY

**Raw SQL:**
```sql
SELECT country, COUNT(*) as user_count
FROM users
GROUP BY country
```

**CHORM:**
```python
query = (
    select(User.country, func.count().label('user_count'))
    .select_from(User)
    .group_by(User.country)
)
```

### HAVING

**Raw SQL:**
```sql
SELECT country, COUNT(*) as user_count
FROM users
GROUP BY country
HAVING COUNT(*) > 100
```

**CHORM:**
```python
query = (
    select(User.country, func.count().label('user_count'))
    .select_from(User)
    .group_by(User.country)
    .having(func.count() > 100)
)
```

### Multiple Aggregates

**Raw SQL:**
```sql
SELECT 
    country,
    COUNT(*) as user_count,
    SUM(revenue) as total_revenue,
    AVG(age) as avg_age
FROM users
GROUP BY country
```

**CHORM:**
```python
query = (
    select(
        User.country,
        func.count().label('user_count'),
        func.sum(User.revenue).label('total_revenue'),
        func.avg(User.age).label('avg_age')
    )
    .select_from(User)
    .group_by(User.country)
)
```

## Advanced Features

### Subqueries

**Raw SQL:**
```sql
SELECT * FROM users
WHERE id IN (SELECT user_id FROM orders WHERE amount > 1000)
```

**CHORM:**
```python
subquery = select(Order.user_id).where(Order.amount > 1000)
query = select(User).where(User.id.in_(subquery))
```

### CTEs (WITH clause)

**Raw SQL:**
```sql
WITH active_users AS (
    SELECT id FROM users WHERE active = 1
)
SELECT * FROM orders
WHERE user_id IN (SELECT id FROM active_users)
```

**CHORM:**
```python
from chorm import cte

active_users = cte(
    select(User.id).where(User.active == 1),
    name='active_users'
)

query = (
    select(Order)
    .with_cte(active_users)
    .where(Order.user_id.in_(select(active_users.c.id)))
)
```

### Window Functions

**Raw SQL:**
```sql
SELECT 
    user_id,
    amount,
    ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) as rn
FROM orders
```

**CHORM:**
```python
query = select(
    Order.user_id,
    Order.amount,
    func.row_number().over(
        partition_by=[Order.user_id],
        order_by=[Order.created_at.desc()]
    ).label('rn')
).select_from(Order)
```

### ARRAY JOIN

**Raw SQL:**
```sql
SELECT user_id, tag
FROM events
ARRAY JOIN tags AS tag
```

**CHORM:**
```python
query = select(Event.user_id, Identifier('tag')).select_from(Event).array_join('tags', 'tag')
```

### LIMIT BY

**Raw SQL:**
```sql
SELECT * FROM orders
ORDER BY user_id, created_at DESC
LIMIT 3 BY user_id
```

**CHORM:**
```python
query = (
    select(Order)
    .order_by(Order.user_id, Order.created_at.desc())
    .limit_by(3, Order.user_id)
)
```

### WITH TOTALS

**Raw SQL:**
```sql
SELECT country, COUNT(*) as cnt
FROM users
GROUP BY country
WITH TOTALS
```

**CHORM:**
```python
query = (
    select(User.country, func.count().label('cnt'))
    .select_from(User)
    .group_by(User.country)
    .with_totals()
)
```

### FINAL

**Raw SQL:**
```sql
SELECT * FROM users FINAL WHERE id = 123
```

**CHORM:**
```python
query = select(User).final().where(User.id == 123)
```

### SAMPLE

**Raw SQL:**
```sql
SELECT * FROM events SAMPLE 0.1
```

**CHORM:**
```python
query = select(Event).sample(0.1)
```

## DDL Operations

### CREATE TABLE

**Raw SQL:**
```sql
CREATE TABLE users (
    id UInt64,
    name String,
    email String,
    created_at DateTime
) ENGINE = MergeTree()
ORDER BY id
```

**CHORM:**
```python
from chorm import Table, Column
from chorm.types import UInt64, String, DateTime
from chorm.table_engines import MergeTree

class User(Table):
    __tablename__ = 'users'
    __engine__ = MergeTree()
    __order_by__ = ['id']
    
    id = Column(UInt64())
    name = Column(String())
    email = Column(String())
    created_at = Column(DateTime())

# Create table
engine.execute(User.create_table())
```

### DROP TABLE

**Raw SQL:**
```sql
DROP TABLE IF EXISTS users
```

**CHORM:**
```python
from chorm.sql.ddl import drop_table

stmt = drop_table(User, if_exists=True)
engine.execute(stmt.to_sql())
```

### ALTER TABLE - Add Column

**Raw SQL:**
```sql
ALTER TABLE users ADD COLUMN age UInt8
```

**CHORM:**
```python
from chorm.sql.ddl import add_column
from chorm.types import UInt8

stmt = add_column(User, 'age', UInt8())
engine.execute(stmt.to_sql())
```

### OPTIMIZE TABLE

**Raw SQL:**
```sql
OPTIMIZE TABLE users FINAL DEDUPLICATE
```

**CHORM:**
```python
from chorm import optimize_table

stmt = optimize_table(User, final=True, deduplicate=True)
engine.execute(stmt.to_sql())
```

### INSERT

**Raw SQL:**
```sql
INSERT INTO users (id, name, email) VALUES (1, 'Alice', 'alice@example.com')
```

**CHORM:**
```python
from chorm import insert

stmt = insert(User).values({
    'id': 1,
    'name': 'Alice',
    'email': 'alice@example.com'
})
engine.execute(stmt.to_sql())
```

### Batch INSERT

**Raw SQL:**
```sql
INSERT INTO users (id, name, email) VALUES 
    (1, 'Alice', 'alice@example.com'),
    (2, 'Bob', 'bob@example.com'),
    (3, 'Charlie', 'charlie@example.com')
```

**CHORM:**
```python
users = [
    {'id': 1, 'name': 'Alice', 'email': 'alice@example.com'},
    {'id': 2, 'name': 'Bob', 'email': 'bob@example.com'},
    {'id': 3, 'name': 'Charlie', 'email': 'charlie@example.com'}
]

stmt = insert(User).values(users)
engine.execute(stmt.to_sql())
```

### INSERT FROM SELECT

**Raw SQL:**
```sql
INSERT INTO target_table (id, name)
SELECT id, name FROM source_table WHERE active = 1
```

**CHORM:**
```python
source_query = select(SourceTable.id, SourceTable.name).where(SourceTable.active == 1)
stmt = insert(TargetTable).from_select(source_query, columns=['id', 'name'])
engine.execute(stmt.to_sql())
```

## Migration Checklist

- [ ] Replace raw SQL strings with CHORM query builders
- [ ] Define Table classes for all tables
- [ ] Convert WHERE clauses to `.where()` with proper operators
- [ ] Replace string concatenation with parameter binding
- [ ] Use `.label()` for column aliases
- [ ] Convert JOINs to `.join()`, `.left_join()`, etc.
- [ ] Replace aggregate functions with `func.*` calls
- [ ] Convert CTEs to `cte()` objects
- [ ] Use window functions with `.over()`
- [ ] Replace ARRAY JOIN with `.array_join()`
- [ ] Convert LIMIT BY to `.limit_by()`
- [ ] Add type hints to your code
- [ ] Write tests for migrated queries

## Common Patterns

### Pattern 1: Pagination

**Raw SQL:**
```sql
SELECT * FROM users ORDER BY id LIMIT 10 OFFSET 20
```

**CHORM:**
```python
page = 3
page_size = 10
query = select(User).order_by(User.id).limit(page_size).offset((page - 1) * page_size)
```

### Pattern 2: Conditional Filters

**Raw SQL:**
```python
sql = "SELECT * FROM users WHERE 1=1"
if country:
    sql += f" AND country = '{country}'"
if active:
    sql += " AND active = 1"
```

**CHORM:**
```python
query = select(User)
if country:
    query = query.where(User.country == country)
if active:
    query = query.where(User.active == 1)
```

### Pattern 3: Dynamic Columns

**Raw SQL:**
```python
columns = ['id', 'name']
sql = f"SELECT {', '.join(columns)} FROM users"
```

**CHORM:**
```python
columns = [User.id, User.name]
query = select(*columns).select_from(User)
```

## Tips for Migration

1. **Start Small**: Migrate one query at a time
2. **Test Thoroughly**: Compare SQL output with `query.to_sql()`
3. **Use Type Hints**: Leverage IDE autocomplete
4. **Batch Operations**: Always use batch inserts for better performance
5. **Leverage ORM Features**: Use relationships, lazy loading where appropriate
6. **Monitor Performance**: Use EXPLAIN to verify query plans
7. **Keep Raw SQL Option**: Use `.execute(raw_sql)` when needed

## Getting Help

If you encounter issues during migration:
- Check the [Best Practices Guide](best_practices.md)
- Review the [Performance Guide](performance_guide.md)
- Look at [Analytics Guide](analytics_guide.md) for complex queries
- Open an issue on GitHub with your SQL and attempted CHORM code
