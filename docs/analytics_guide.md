# CHORM Analytics Guide

A comprehensive guide to building analytics applications with CHORM and ClickHouse.

## Table of Contents
- [Why CHORM for Analytics](#why-chorm-for-analytics)
- [Analytics Patterns](#analytics-patterns)
- [Advanced Features](#advanced-features)
- [Real-World Examples](#real-world-examples)

---

## Why CHORM for Analytics

CHORM combines SQLAlchemy's familiar API with ClickHouse's analytics power:

- **Fast aggregations** - Columnar storage optimized for analytics
- **Window functions** - Ranking, running totals, lag/lead
- **Array operations** - ARRAY JOIN for denormalization
- **Conditional aggregations** - sumIf, countIf for multi-metric queries
- **CTEs** - Complex queries with readable structure

---

## Analytics Patterns

### 1. Cohort Analysis

Track user behavior over time grouped by signup date.

```python
from chorm import select
from chorm.sql.expression import func, Identifier

# Define cohorts by first activity date
cohorts = (
    select(
        User.id,
        func.min(func.toDate(User.created_at)).label('cohort_date')
    )
    .group_by(User.id)
    .cte('cohorts')
)

# Calculate retention: active users by days since signup
stmt = (
    select(
        Identifier('cohorts.cohort_date'),
        func.dateDiff('day', Identifier('cohorts.cohort_date'), 
                     func.toDate(Activity.timestamp)).label('days_since_signup'),
        func.uniq(Activity.user_id).label('active_users')
    )
    .select_from(Identifier('cohorts'))
    .join(Activity, on=Identifier('cohorts.id') == Activity.user_id)
    .with_cte(cohorts)
    .group_by(Identifier('cohorts.cohort_date'), Identifier('days_since_signup'))
    .order_by(Identifier('cohorts.cohort_date'), Identifier('days_since_signup'))
)

results = session.execute(stmt).all()
for row in results:
    print(f"Cohort {row.cohort_date}, Day {row.days_since_signup}: {row.active_users} users")
```

### 2. Funnel Analysis

Measure conversion rates through multi-step processes.

```python
from chorm.sql.expression import func

# Calculate funnel steps using conditional aggregations
stmt = select(
    func.countIf(Event.event_type == 'signup').label('step1_signup'),
    func.countIf(Event.event_type == 'view_product').label('step2_view'),
    func.countIf(Event.event_type == 'add_to_cart').label('step3_cart'),
    func.countIf(Event.event_type == 'purchase').label('step4_purchase')
).select_from(Event)

result = session.execute(stmt).one()

# Calculate conversion rates
print(f"Signup → View: {result.step2_view / result.step1_signup:.1%}")
print(f"View → Cart: {result.step3_cart / result.step2_view:.1%}")
print(f"Cart → Purchase: {result.step4_purchase / result.step3_cart:.1%}")
```

### 3. Time-Series Aggregations

Analyze metrics over time periods.

```python
# Daily sales with running total
from chorm.sql.expression import window

w = window(
    order_by=[func.toDate(Order.created_at)],
    rows_between=('UNBOUNDED PRECEDING', 'CURRENT ROW')
)

stmt = select(
    func.toDate(Order.created_at).label('date'),
    func.sum(Order.amount).label('daily_sales'),
    func.sum(Order.amount).over(w).label('running_total')
).group_by(func.toDate(Order.created_at)).order_by('date')

results = session.execute(stmt).all()
for row in results:
    print(f"{row.date}: ${row.daily_sales:.2f} (Total: ${row.running_total:.2f})")
```

### 4. Top-N with "Other" Category

Group low-volume items into "Other" for cleaner visualizations.

```python
from chorm.sql.expression import if_, Subquery, Literal

# Get top 5 categories
top_categories = (
    select(Product.category)
    .group_by(Product.category)
    .order_by(func.count().desc())
    .limit(5)
)

# Classify as top category or "Other"
category_expr = if_(
    Product.category.in_(Subquery(top_categories)),
    Product.category,
    Literal('Other')
).label('display_category')

stmt = (
    select(
        category_expr,
        func.sum(Order.amount).label('total_sales')
    )
    .select_from(Order)
    .join(Product, on=Order.product_id == Product.id)
    .group_by(Identifier('display_category'))
    .order_by(func.sum(Order.amount).desc())
)

results = session.execute(stmt).all()
for row in results:
    print(f"{row.display_category}: ${row.total_sales:.2f}")
```

### 5. Ranking and Percentiles

Find top performers within groups.

```python
# Top 3 products per category by sales
w = window(
    partition_by=[Product.category],
    order_by=[func.sum(Order.amount).desc()]
)

stmt = (
    select(
        Product.category,
        Product.name,
        func.sum(Order.amount).label('sales'),
        func.row_number().over(w).label('rank')
    )
    .select_from(Order)
    .join(Product, on=Order.product_id == Product.id)
    .group_by(Product.category, Product.name)
).cte('ranked')

# Filter to top 3
stmt = (
    select(Identifier('*'))
    .select_from(Identifier('ranked'))
    .where(Identifier('rank') <= 3)
    .with_cte(stmt)
)

results = session.execute(stmt).all()
```

---

## Advanced Features

### Window Functions

CHORM supports all ClickHouse window functions.

#### Ranking Functions

```python
from chorm.sql.expression import window, func

w = window(
    partition_by=[Order.user_id],
    order_by=[Order.created_at]
)

stmt = select(
    Order.id,
    Order.user_id,
    func.row_number().over(w).label('order_number'),
    func.rank().over(w).label('rank'),
    func.dense_rank().over(w).label('dense_rank')
).select_from(Order)
```

#### Offset Functions

```python
# Compare with previous/next values
w = window(
    partition_by=[Product.category],
    order_by=[Product.created_at]
)

stmt = select(
    Product.name,
    Product.price,
    func.lag(Product.price, 1).over(w).label('prev_price'),
    func.lead(Product.price, 1).over(w).label('next_price')
).select_from(Product)
```

#### Aggregate Functions

```python
# Running totals and moving averages
w_running = window(
    partition_by=[Order.user_id],
    order_by=[Order.created_at],
    rows_between=('UNBOUNDED PRECEDING', 'CURRENT ROW')
)

w_moving = window(
    partition_by=[Order.user_id],
    order_by=[Order.created_at],
    rows_between=(3, 0)  # Last 3 rows
)

stmt = select(
    Order.id,
    Order.amount,
    func.sum(Order.amount).over(w_running).label('running_total'),
    func.avg(Order.amount).over(w_moving).label('moving_avg_3')
).select_from(Order)
```

### ARRAY JOIN

Unnest arrays for analysis.

```python
# Analyze individual tags from array column
stmt = (
    select(
        Identifier('tag'),
        func.count().label('tag_count')
    )
    .select_from(Product)
    .array_join(Product.tags, alias='tag')
    .group_by(Identifier('tag'))
    .order_by(func.count().desc())
)

results = session.execute(stmt).all()
for row in results:
    print(f"{row.tag}: {row.tag_count}")
```

### Conditional Aggregations

Calculate multiple metrics in a single query.

```python
# Sales metrics by status
stmt = select(
    Order.user_id,
    func.sumIf(Order.amount, Order.status == 'completed').label('completed_sales'),
    func.sumIf(Order.amount, Order.status == 'pending').label('pending_sales'),
    func.countIf(Order.status == 'cancelled').label('cancelled_count'),
    func.avgIf(Order.amount, Order.status == 'completed').label('avg_completed')
).group_by(Order.user_id)
```

### LIMIT BY

Get top N rows per group efficiently.

```python
# Top 3 orders per user
stmt = (
    select(Order.user_id, Order.id, Order.amount)
    .select_from(Order)
    .order_by(Order.amount.desc())
    .limit_by(3, Order.user_id)
)

results = session.execute(stmt).all()
```

### WITH TOTALS

Add summary row to GROUP BY results.

```python
# Sales by category with grand total
stmt = (
    select(
        Product.category,
        func.sum(Order.amount).label('total_sales')
    )
    .select_from(Order)
    .join(Product, on=Order.product_id == Product.id)
    .group_by(Product.category)
    .with_totals()
)

results = session.execute(stmt).all()
# Last row contains totals across all categories
```

---

## Real-World Examples

### E-Commerce Analytics

```python
# Daily sales dashboard
stmt = select(
    func.toDate(Order.created_at).label('date'),
    func.count().label('order_count'),
    func.sum(Order.amount).label('revenue'),
    func.avg(Order.amount).label('avg_order_value'),
    func.uniq(Order.user_id).label('unique_customers')
).group_by(func.toDate(Order.created_at)).order_by('date')
```

### User Behavior Tracking

```python
# Session analysis with window functions
w = window(
    partition_by=[Event.user_id],
    order_by=[Event.timestamp]
)

stmt = select(
    Event.user_id,
    Event.event_type,
    Event.timestamp,
    func.lag(Event.timestamp, 1).over(w).label('prev_event_time'),
    func.dateDiff('minute', 
                 func.lag(Event.timestamp, 1).over(w),
                 Event.timestamp).label('minutes_since_last')
).select_from(Event)
```

### Product Recommendations

```python
# Products frequently bought together
from chorm.sql.expression import Identifier

# Self-join to find product pairs
order_items_a = Order.alias('a')
order_items_b = Order.alias('b')

stmt = (
    select(
        Identifier('a.product_id').label('product_a'),
        Identifier('b.product_id').label('product_b'),
        func.count().label('times_together')
    )
    .select_from(order_items_a)
    .join(order_items_b, 
          on=(Identifier('a.order_id') == Identifier('b.order_id')) &
             (Identifier('a.product_id') < Identifier('b.product_id')))
    .group_by(Identifier('product_a'), Identifier('product_b'))
    .order_by(func.count().desc())
    .limit(10)
)
```

---

## Performance Tips for Analytics

1. **Use appropriate aggregation functions**
   - `uniq()` for approximate counts (faster)
   - `uniqExact()` only when precision is critical

2. **Leverage PREWHERE**
   - Filter on indexed columns before reading all data

3. **Optimize window frames**
   - Use bounded frames when possible
   - Avoid `UNBOUNDED FOLLOWING` if not needed

4. **Batch your queries**
   - Combine metrics in single query using conditional aggregations
   - Reduces database round-trips

5. **Consider materialized views**
   - Pre-aggregate frequently queried metrics
   - Update incrementally as new data arrives

---

## Next Steps

- Explore [examples/analytics_cookbook.py](../examples/analytics_cookbook.py) for complete working examples
- Read [Performance Guide](performance.md) for optimization tips
- Check [examples/](../examples/) for more patterns

---

## Additional Resources

- [ClickHouse Analytics Guide](https://clickhouse.com/docs/en/guides/developer/cascading-materialized-views)
- [Window Functions Reference](https://clickhouse.com/docs/en/sql-reference/window-functions)
- [CHORM Documentation](../README.md)
