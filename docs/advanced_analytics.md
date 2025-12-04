# Advanced Analytics Guide

This guide demonstrates CHORM's advanced analytics capabilities, including multi-level query composition, CTEs, window functions, and complex aggregations.

## Table of Contents

- [Column Access with `.c` Attribute](#column-access-with-c-attribute)
- [Common Table Expressions (CTEs)](#common-table-expressions-ctes)
- [Window Functions](#window-functions)
- [Multi-Level Query Composition](#multi-level-query-composition)
- [Complex Analytics Patterns](#complex-analytics-patterns)
- [Best Practices](#best-practices)

---

## Column Access with `.c` Attribute

CHORM provides SQLAlchemy-style `.c` attribute for accessing columns from subqueries and CTEs.

### Basic Subquery Column Access

```python
from chorm import select, func

# Create a subquery with aggregations
user_stats = select(
    Order.user_id,
    func.sum(Order.amount).label('total_spent'),
    func.count().label('order_count'),
    func.avg(Order.amount).label('avg_order_value')
).group_by(Order.user_id).subquery('user_stats')

# Access columns using .c attribute
query = select(
    User.name,
    User.email,
    user_stats.c.total_spent,
    user_stats.c.order_count,
    user_stats.c.avg_order_value
).select_from(User).join(
    user_stats,
    User.id == user_stats.c.user_id
).where(user_stats.c.total_spent > 1000)
```

### Column Access Methods

The `.c` attribute supports multiple access patterns:

```python
subq = select(User.id, User.name).subquery('u')

# Attribute access
subq.c.id
subq.c.name

# Item access
subq.c['id']
subq.c['name']

# Check if column exists
'id' in subq.c  # True
'nonexistent' in subq.c  # False

# List available columns
subq.c.keys()  # ['id', 'name']
```

---

## Common Table Expressions (CTEs)

CTEs allow you to define reusable query fragments using the `WITH` clause.

### Basic CTE Usage

```python
from chorm import select, func, cte

# Define a CTE
active_users = cte(
    select(User.id, User.name, User.country)
    .where(User.status == 'active'),
    name='active_users'
)

# Use the CTE in main query
query = select(
    active_users.c.name,
    active_users.c.country,
    func.count(Order.id).label('order_count')
).with_cte(active_users).select_from(active_users).left_join(
    Order,
    active_users.c.id == Order.user_id
).group_by(active_users.c.name, active_users.c.country)
```

**Generated SQL:**
```sql
WITH active_users AS (
    SELECT users.id, users.name, users.country
    FROM users
    WHERE users.status = 'active'
)
SELECT active_users.name, active_users.country, count(orders.id) AS order_count
FROM active_users
LEFT JOIN orders ON active_users.id = orders.user_id
GROUP BY active_users.name, active_users.country
```

### Multiple CTEs

You can use multiple CTEs in a single query:

```python
# CTE 1: User statistics
user_stats = cte(
    select(
        User.id,
        func.count(Order.id).label('total_orders')
    ).select_from(User).left_join(
        Order,
        User.id == Order.user_id
    ).group_by(User.id),
    name='user_stats'
)

# CTE 2: Country statistics
country_stats = cte(
    select(
        User.country,
        func.count(User.id).label('user_count'),
        func.avg(func.cast(User.id, 'Float64')).label('avg_user_id')
    ).select_from(User).group_by(User.country),
    name='country_stats'
)

# Main query using both CTEs
query = select(
    User.name,
    User.country,
    user_stats.c.total_orders,
    country_stats.c.user_count
).with_cte(user_stats).with_cte(country_stats).select_from(User).join(
    user_stats,
    User.id == user_stats.c.id
).join(
    country_stats,
    User.country == country_stats.c.country
)
```

---

## Window Functions

Window functions perform calculations across a set of rows related to the current row.

### Creating Window Specifications

```python
from chorm import select, func, window

# Create a window partitioned by user_id, ordered by created_at
w = window(
    partition_by=[Order.user_id],
    order_by=[Order.created_at]
)

# Use window functions
query = select(
    Order.id,
    Order.user_id,
    Order.amount,
    Order.created_at,
    func.row_number().over(w).label('order_number'),
    func.sum(Order.amount).over(w).label('running_total'),
    func.avg(Order.amount).over(w).label('running_avg')
)
```

**Generated SQL:**
```sql
SELECT 
    orders.id,
    orders.user_id,
    orders.amount,
    orders.created_at,
    row_number() OVER (PARTITION BY orders.user_id ORDER BY orders.created_at) AS order_number,
    sum(orders.amount) OVER (PARTITION BY orders.user_id ORDER BY orders.created_at) AS running_total,
    avg(orders.amount) OVER (PARTITION BY orders.user_id ORDER BY orders.created_at) AS running_avg
FROM orders
```

### Common Window Functions

```python
# Ranking functions
func.row_number().over(w)
func.rank().over(w)
func.dense_rank().over(w)

# Offset functions
func.lag(Order.amount, 1).over(w)  # Previous row
func.lead(Order.amount, 1).over(w)  # Next row

# Aggregate functions as window functions
func.sum(Order.amount).over(w)
func.avg(Order.amount).over(w)
func.count().over(w)
func.min(Order.amount).over(w)
func.max(Order.amount).over(w)
```

### Window Frames

Specify custom window frames for fine-grained control:

```python
# Rows between 1 preceding and current row
w = window(
    partition_by=[Order.user_id],
    order_by=[Order.created_at],
    frame="ROWS BETWEEN 1 PRECEDING AND CURRENT ROW"
)

# Rows between unbounded preceding and current row
w = window(
    partition_by=[Order.user_id],
    order_by=[Order.created_at],
    frame="ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW"
)
```

---

## Multi-Level Query Composition

CHORM excels at building complex, multi-level queries with clean syntax.

### Two-Level Nesting

```python
# Level 1: User totals
user_totals = select(
    Order.user_id,
    func.sum(Order.amount).label('total_amount'),
    func.count().label('order_count')
).where(Order.status == 'completed').group_by(Order.user_id).subquery('user_totals')

# Level 2: Join with users and filter
query = select(
    User.name,
    User.country,
    user_totals.c.total_amount,
    user_totals.c.order_count
).select_from(User).join(
    user_totals,
    User.id == user_totals.c.user_id
).where(user_totals.c.total_amount > 1000).order_by(
    user_totals.c.total_amount.desc()
)
```

### Three-Level Nesting

```python
# Level 1: Daily aggregates
daily = select(
    Order.user_id,
    func.toDate(Order.created_at).label('date'),
    func.sum(Order.amount).label('daily_total'),
    func.count().label('daily_orders')
).group_by(
    Order.user_id,
    func.toDate(Order.created_at)
).subquery('daily')

# Level 2: Monthly averages
monthly = select(
    daily.c.user_id,
    func.toStartOfMonth(daily.c.date).label('month'),
    func.avg(daily.c.daily_total).label('avg_daily_total'),
    func.sum(daily.c.daily_orders).label('monthly_orders')
).group_by(
    daily.c.user_id,
    func.toStartOfMonth(daily.c.date)
).subquery('monthly')

# Level 3: Final query with user info
query = select(
    User.name,
    User.country,
    monthly.c.month,
    monthly.c.avg_daily_total,
    monthly.c.monthly_orders
).select_from(User).join(
    monthly,
    User.id == monthly.c.user_id
).where(monthly.c.avg_daily_total > 100).order_by(
    monthly.c.avg_daily_total.desc()
)
```

---

## Complex Analytics Patterns

### Pattern 1: User Cohort Analysis

```python
from chorm import select, func, cte

# Define cohorts based on first order date
cohorts = cte(
    select(
        Order.user_id,
        func.toStartOfMonth(func.min(Order.created_at)).label('cohort_month')
    ).group_by(Order.user_id),
    name='cohorts'
)

# Calculate monthly revenue by cohort
cohort_revenue = select(
    cohorts.c.cohort_month,
    func.toStartOfMonth(Order.created_at).label('order_month'),
    func.sum(Order.amount).label('revenue'),
    func.count(func.distinct(Order.user_id)).label('active_users')
).with_cte(cohorts).select_from(cohorts).join(
    Order,
    cohorts.c.user_id == Order.user_id
).group_by(
    cohorts.c.cohort_month,
    func.toStartOfMonth(Order.created_at)
)
```

### Pattern 2: Running Totals with Window Functions

```python
# Calculate running totals and month-over-month growth
w = window(
    partition_by=[User.id],
    order_by=[func.toStartOfMonth(Order.created_at)]
)

query = select(
    User.id,
    User.name,
    func.toStartOfMonth(Order.created_at).label('month'),
    func.sum(Order.amount).label('monthly_revenue'),
    func.sum(func.sum(Order.amount)).over(w).label('cumulative_revenue'),
    func.lag(func.sum(Order.amount), 1).over(w).label('prev_month_revenue')
).select_from(User).join(
    Order,
    User.id == Order.user_id
).group_by(
    User.id,
    User.name,
    func.toStartOfMonth(Order.created_at)
)
```

### Pattern 3: Top N per Group (LIMIT BY)

```python
# Get top 5 orders per user
query = select(
    Order.user_id,
    Order.id,
    Order.amount,
    Order.created_at
).order_by(
    Order.amount.desc()
).limit_by(5, Order.user_id)
```

### Pattern 4: Percentile Analysis

```python
# Calculate percentiles for order amounts
query = select(
    User.country,
    func.quantile(0.25, Order.amount).label('p25'),
    func.quantile(0.50, Order.amount).label('median'),
    func.quantile(0.75, Order.amount).label('p75'),
    func.quantile(0.95, Order.amount).label('p95')
).select_from(User).join(
    Order,
    User.id == Order.user_id
).group_by(User.country)
```

### Pattern 5: Time-Series Analysis with CTEs

```python
# Daily activity with 7-day moving average
daily_activity = cte(
    select(
        func.toDate(Order.created_at).label('date'),
        func.sum(Order.amount).label('daily_revenue'),
        func.count().label('daily_orders')
    ).group_by(func.toDate(Order.created_at)),
    name='daily_activity'
)

w = window(
    order_by=[daily_activity.c.date],
    frame="ROWS BETWEEN 6 PRECEDING AND CURRENT ROW"
)

query = select(
    daily_activity.c.date,
    daily_activity.c.daily_revenue,
    daily_activity.c.daily_orders,
    func.avg(daily_activity.c.daily_revenue).over(w).label('ma7_revenue'),
    func.avg(daily_activity.c.daily_orders).over(w).label('ma7_orders')
).with_cte(daily_activity).select_from(daily_activity)
```

---

## Best Practices

### 1. Use Meaningful Aliases

Always provide clear aliases for subqueries and CTEs:

```python
# Good
user_stats = select(...).subquery('user_stats')
monthly_revenue = cte(..., name='monthly_revenue')

# Avoid
subq = select(...).subquery()  # Uses default 'subquery' name
```

### 2. Leverage `.c` for Readability

Use the `.c` attribute instead of `Identifier` for cleaner code:

```python
# Good
query = select(subq.c.total, subq.c.count)

# Avoid
from chorm.sql.expression import Identifier
query = select(Identifier('subq.total'), Identifier('subq.count'))
```

### 3. Break Complex Queries into Steps

For very complex queries, build them step by step:

```python
# Step 1: Base aggregation
daily = select(...).subquery('daily')

# Step 2: Intermediate calculation
monthly = select(...).subquery('monthly')

# Step 3: Final result
final = select(...)
```

### 4. Use CTEs for Reusability

If you reference the same subquery multiple times, use a CTE:

```python
# Good - CTE is evaluated once
active_users = cte(select(...), name='active_users')
query = select(...).with_cte(active_users).select_from(active_users).join(...)

# Less efficient - subquery might be evaluated multiple times
active_users_subq = select(...).subquery('active_users')
```

### 5. Combine Window Functions with Aggregations

Window functions can be used alongside GROUP BY:

```python
query = select(
    User.country,
    func.sum(Order.amount).label('country_total'),
    func.sum(func.sum(Order.amount)).over(
        window(order_by=[func.sum(Order.amount).desc()])
    ).label('running_total')
).select_from(User).join(
    Order,
    User.id == Order.user_id
).group_by(User.country)
```

### 6. Use ClickHouse-Specific Features

Take advantage of ClickHouse optimizations:

```python
# Use PREWHERE for filtering on primary key columns
query = select(User).prewhere(User.id > 1000).where(User.status == 'active')

# Use FINAL for ReplacingMergeTree tables
query = select(User).final()

# Use SAMPLE for approximate queries on large datasets
query = select(User).sample(0.1)  # 10% sample
```

### 7. Test Query Performance

Always test complex queries with `EXPLAIN`:

```python
query = select(...)
explain = query.explain(explain_type='PLAN')
result = session.execute(explain.to_sql())
print(result.fetchall())
```

---

## Complete Example: E-commerce Analytics Dashboard

Here's a complete example combining multiple advanced features:

```python
from chorm import select, func, cte, window

# CTE 1: User lifetime metrics
user_lifetime = cte(
    select(
        Order.user_id,
        func.min(Order.created_at).label('first_order_date'),
        func.max(Order.created_at).label('last_order_date'),
        func.sum(Order.amount).label('lifetime_value'),
        func.count().label('total_orders')
    ).group_by(Order.user_id),
    name='user_lifetime'
)

# CTE 2: Monthly user activity
monthly_activity = cte(
    select(
        Order.user_id,
        func.toStartOfMonth(Order.created_at).label('month'),
        func.sum(Order.amount).label('monthly_spend'),
        func.count().label('monthly_orders')
    ).group_by(
        Order.user_id,
        func.toStartOfMonth(Order.created_at)
    ),
    name='monthly_activity'
)

# Window for ranking users
w_rank = window(
    order_by=[user_lifetime.c.lifetime_value.desc()]
)

# Final dashboard query
dashboard = select(
    User.id,
    User.name,
    User.email,
    User.country,
    user_lifetime.c.first_order_date,
    user_lifetime.c.last_order_date,
    user_lifetime.c.lifetime_value,
    user_lifetime.c.total_orders,
    func.row_number().over(w_rank).label('value_rank'),
    func.if_(
        user_lifetime.c.lifetime_value > 10000,
        'VIP',
        func.if_(
            user_lifetime.c.lifetime_value > 1000,
            'Premium',
            'Standard'
        )
    ).label('segment')
).with_cte(user_lifetime).with_cte(monthly_activity).select_from(User).join(
    user_lifetime,
    User.id == user_lifetime.c.user_id
).where(user_lifetime.c.total_orders > 0).order_by(
    user_lifetime.c.lifetime_value.desc()
).limit(100)

# Execute
result = session.execute(dashboard.to_sql())
for row in result:
    print(f"{row.name}: ${row.lifetime_value} ({row.segment})")
```

---

## Additional Resources

- [ClickHouse Window Functions Documentation](https://clickhouse.com/docs/en/sql-reference/window-functions/)
- [ClickHouse Aggregate Functions](https://clickhouse.com/docs/en/sql-reference/aggregate-functions/)
- [CHORM Query API Reference](../README.md#query-api)
- [CHORM Examples](../examples/)

---

## Summary

CHORM provides powerful tools for complex analytics:

- ✅ **`.c` attribute** for clean column access
- ✅ **CTEs** for reusable query fragments
- ✅ **Window functions** for advanced calculations
- ✅ **Multi-level nesting** for complex transformations
- ✅ **ClickHouse-specific optimizations** (PREWHERE, FINAL, SAMPLE, etc.)

These features combine to make CHORM the most powerful ORM for ClickHouse analytics workloads.
