"""Comprehensive test for complex analytics queries support.

Tests multi-level nesting, CTEs, subqueries, aggregations, and labeling.
"""

from chorm import Table, Column, select, cte
from chorm.types import UInt64, String, DateTime, Decimal
from chorm.table_engines import MergeTree
from chorm.sql.expression import func, Identifier


class Order(Table):
    __tablename__ = "orders"
    __engine__ = MergeTree()
    __order_by__ = ["user_id", "created_at"]

    id = Column(UInt64())
    user_id = Column(UInt64())
    product_id = Column(UInt64())
    amount = Column(Decimal(18, 2))
    status = Column(String())
    created_at = Column(DateTime())


class User(Table):
    __tablename__ = "users"
    __engine__ = MergeTree()
    __order_by__ = ["id"]

    id = Column(UInt64())
    name = Column(String())
    country = Column(String())
    created_at = Column(DateTime())


def test_simple_aggregation_with_labels():
    """Test basic aggregation with column labeling."""
    query = (
        select(
            User.country,
            func.count().label("user_count"),
            func.sum(Order.amount).label("total_revenue"),
            func.avg(Order.amount).label("avg_order_value"),
        )
        .select_from(User)
        .join(Order, User.id == Order.user_id)
        .group_by(User.country)
        .having(func.count() > 10)
        .order_by(func.sum(Order.amount).desc())
    )

    sql = query.to_sql()
    assert "count() AS user_count" in sql
    assert "sum(orders.amount) AS total_revenue" in sql
    assert "avg(orders.amount) AS avg_order_value" in sql
    assert "GROUP BY users.country" in sql
    assert "HAVING" in sql and "count()" in sql and "> 10" in sql


def test_nested_subquery_with_aggregation():
    """Test 2-level nested subquery with aggregations."""
    # Level 1: User totals
    user_totals = (
        select(
            Order.user_id,
            func.sum(Order.amount).label("total_amount"),
            func.count().label("order_count"),
            func.avg(Order.amount).label("avg_amount"),
        )
        .select_from(Order)
        .where(Order.status == "completed")
        .group_by(Order.user_id)
        .having(func.sum(Order.amount) > 1000)
    ).subquery("user_totals")

    # Level 2: Join with users
    query = (
        select(User.name, User.country, user_totals.c.total_amount, user_totals.c.order_count, user_totals.c.avg_amount)
        .select_from(User)
        .join(user_totals, User.id == user_totals.c.user_id)
        .where(User.country == "US")
        .order_by(user_totals.c.total_amount.desc())
        .limit(10)
    )

    sql = query.to_sql()
    assert "SELECT" in sql
    assert "INNER JOIN (" in sql  # Subquery in JOIN
    assert "sum(orders.amount) AS total_amount" in sql
    assert "HAVING" in sql and "sum(orders.amount)" in sql and "1000" in sql
    assert "users.country = 'US'" in sql


def test_three_level_nested_query():
    """Test 3-level deeply nested query."""
    # Level 1: Daily aggregations
    daily = (
        select(
            Order.user_id,
            func.toDate(Order.created_at).label("date"),
            func.sum(Order.amount).label("daily_total"),
            func.count().label("daily_orders"),
        )
        .select_from(Order)
        .group_by(Order.user_id, func.toDate(Order.created_at))
    ).subquery("daily")

    # Level 2: Monthly averages from daily
    monthly = (
        select(
            daily.c.user_id,
            func.toYYYYMM(daily.c.date).label("month"),
            func.avg(daily.c.daily_total).label("avg_daily_total"),
            func.sum(daily.c.daily_orders).label("monthly_orders"),
        )
        .select_from(daily)
        .group_by(daily.c.user_id, func.toYYYYMM(daily.c.date))
    ).subquery("monthly")

    # Level 3: Final query with user info
    query = (
        select(User.name, User.country, monthly.c.month, monthly.c.avg_daily_total, monthly.c.monthly_orders)
        .select_from(User)
        .join(monthly, User.id == monthly.c.user_id)
        .where(monthly.c.avg_daily_total > 100)
        .order_by(monthly.c.avg_daily_total.desc())
    )

    sql = query.to_sql()
    # Should have 3 levels of nesting
    assert sql.count("SELECT") >= 3
    # At least one FROM ( for nested subqueries
    assert "FROM (" in sql or "JOIN (" in sql


def test_cte_with_aggregation():
    """Test CTE (WITH clause) with aggregations."""
    # Define CTE
    monthly_stats = cte(
        select(
            func.toYYYYMM(Order.created_at).label("month"),
            Order.user_id,
            func.sum(Order.amount).label("monthly_total"),
            func.avg(Order.amount).label("avg_order"),
            func.count().label("order_count"),
        )
        .select_from(Order)
        .group_by(func.toYYYYMM(Order.created_at), Order.user_id),
        name="monthly_stats",
    )

    # Use CTE in main query
    query = (
        select(
            User.name,
            monthly_stats.c.month,
            monthly_stats.c.monthly_total,
            monthly_stats.c.avg_order,
            monthly_stats.c.order_count,
        )
        .with_cte(monthly_stats)
        .select_from(User)
        .join(monthly_stats, User.id == monthly_stats.c.user_id)
        .where(monthly_stats.c.monthly_total > 500)
    )

    sql = query.to_sql()
    assert "WITH monthly_stats AS" in sql
    assert "sum(orders.amount) AS monthly_total" in sql
    assert "avg(orders.amount) AS avg_order" in sql


def test_multiple_ctes():
    """Test multiple CTEs in single query."""
    # CTE 1: User stats
    user_stats = cte(
        select(User.id, func.count(Order.id).label("total_orders"))
        .select_from(User)
        .left_join(Order, User.id == Order.user_id)
        .group_by(User.id),
        name="user_stats",
    )

    # CTE 2: Country stats
    country_stats = cte(
        select(User.country, func.count(User.id).label("user_count")).select_from(User).group_by(User.country),
        name="country_stats",
    )

    # Main query using both CTEs
    query = (
        select(User.name, User.country, user_stats.c.total_orders, country_stats.c.user_count)
        .with_cte(user_stats)
        .with_cte(country_stats)
        .select_from(User)
        .join(user_stats, User.id == user_stats.c.id)
        .join(country_stats, User.country == country_stats.c.country)
    )

    sql = query.to_sql()
    assert "WITH user_stats AS" in sql
    assert "country_stats AS" in sql


def test_subquery_in_where_clause():
    """Test subquery in WHERE clause."""
    # Subquery: users with high total spend
    high_spenders = (
        select(Order.user_id).select_from(Order).group_by(Order.user_id).having(func.sum(Order.amount) > 5000)
    )

    # Main query
    query = select(User.name, User.country).select_from(User).where(User.id.in_(high_spenders))

    sql = query.to_sql()
    assert "WHERE" in sql and "users.id IN" in sql
    assert "sum(orders.amount)" in sql and "5000" in sql


def test_complex_analytics_pipeline():
    """Test realistic complex analytics pipeline."""
    from chorm.sql.expression import if_

    # Step 1: Daily user activity
    daily_activity = cte(
        select(
            Order.user_id,
            func.toDate(Order.created_at).label("activity_date"),
            func.sum(Order.amount).label("daily_spend"),
            func.count().label("daily_orders"),
        )
        .select_from(Order)
        .where(Order.status == "completed")
        .group_by(Order.user_id, func.toDate(Order.created_at)),
        name="daily_activity",
    )

    # Step 2: User lifetime metrics
    user_metrics = cte(
        select(
            daily_activity.c.user_id,
            func.sum(daily_activity.c.daily_spend).label("lifetime_value"),
            func.avg(daily_activity.c.daily_spend).label("avg_daily_spend"),
            func.count(daily_activity.c.activity_date).label("active_days"),
        )
        .select_from(daily_activity)
        .group_by(daily_activity.c.user_id),
        name="user_metrics",
    )

    # Step 3: Final query with user info and segmentation
    query = (
        select(
            User.name,
            User.country,
            user_metrics.c.lifetime_value,
            user_metrics.c.avg_daily_spend,
            user_metrics.c.active_days,
            if_(
                user_metrics.c.lifetime_value > 10000,
                "VIP",
                if_(user_metrics.c.lifetime_value > 1000, "Premium", "Standard"),
            ).label("segment"),
        )
        .with_cte(daily_activity)
        .with_cte(user_metrics)
        .select_from(User)
        .join(user_metrics, User.id == user_metrics.c.user_id)
        .where(user_metrics.c.active_days > 5)
        .order_by(user_metrics.c.lifetime_value.desc())
    )

    sql = query.to_sql()
    assert "WITH daily_activity AS" in sql
    assert "user_metrics AS" in sql
    assert "CASE" in sql or "if(" in sql  # Conditional logic


def test_window_functions_with_aggregation():
    """Test window functions combined with aggregations."""
    from chorm.sql.selectable import window

    w = window(partition_by=[Order.user_id], order_by=[Order.created_at])

    query = select(
        Order.user_id,
        Order.amount,
        func.row_number().over(w).label("order_number"),
        func.sum(Order.amount).over(w).label("running_total"),
        func.avg(Order.amount).over(w).label("running_avg"),
    ).select_from(Order)

    sql = query.to_sql()
    assert "row_number() OVER" in sql
    assert "sum(orders.amount) OVER" in sql
    assert "PARTITION BY orders.user_id" in sql


def test_all_features_combined():
    """Test combining all features: CTEs, subqueries, aggregations, window functions, labels."""
    from chorm.sql.selectable import window

    # CTE with aggregation
    monthly_totals = cte(
        select(
            Order.user_id, func.toYYYYMM(Order.created_at).label("month"), func.sum(Order.amount).label("monthly_total")
        )
        .select_from(Order)
        .group_by(Order.user_id, func.toYYYYMM(Order.created_at)),
        name="monthly_totals",
    )

    # Window function over CTE
    w = window(partition_by=[monthly_totals.c.user_id], order_by=[monthly_totals.c.month])

    # Subquery with window function
    ranked = (
        select(
            monthly_totals.c.user_id,
            monthly_totals.c.month,
            monthly_totals.c.monthly_total,
            func.row_number().over(w).label("month_rank"),
            func.lag(monthly_totals.c.monthly_total, 1).over(w).label("prev_month_total"),
        ).select_from(monthly_totals)
    ).subquery("ranked")

    # Final query
    query = (
        select(
            User.name,
            ranked.c.month,
            ranked.c.monthly_total,
            ranked.c.month_rank,
            ranked.c.prev_month_total,
            func.if_(
                ranked.c.prev_month_total.is_not(None),
                (ranked.c.monthly_total - ranked.c.prev_month_total) / ranked.c.prev_month_total * 100,
                None,
            ).label("growth_pct"),
        )
        .with_cte(monthly_totals)
        .select_from(User)
        .join(ranked, User.id == ranked.c.user_id)
        .where(ranked.c.month_rank <= 12)  # Last 12 months
    )

    sql = query.to_sql()
    assert "WITH monthly_totals AS" in sql
    assert "row_number() OVER" in sql
    assert "lag(" in sql
    # Subquery appears in JOIN
    assert "JOIN (" in sql
