"""
CHORM Analytics Cookbook
-----------------------

This cookbook demonstrates advanced analytics patterns using CHORM.
It covers real-world scenarios like:
1. User Cohort Analysis (Retention)
2. Event Funnel Analysis
3. Time-Series Aggregations
4. Top-N Analysis with "Other" category
"""

import os
from datetime import date, timedelta
from chorm import Table, Column, MergeTree, select, insert, create_engine, MetaData
from chorm.session import Session
from chorm.types import UInt64, String, Date, Float64, DateTime
from chorm.sql.expression import Identifier, Literal, func


metadata = MetaData()


# --- Models ---

class UserEvent(Table):
    metadata = metadata
    __tablename__ = "events_cookbook"
    __engine__ = MergeTree()
    __order_by__ = ("event_type", "timestamp")
    
    user_id = Column(UInt64())
    event_type = Column(String())  # 'signup', 'view_item', 'add_to_cart', 'purchase'
    timestamp = Column(DateTime())
    amount = Column(Float64())  # For purchases


# --- Setup ---

def get_session():
    host = os.getenv("CLICKHOUSE_HOST", "localhost")
    port = int(os.getenv("CLICKHOUSE_PORT", "8123"))
    database = os.getenv("CLICKHOUSE_DB", "default")
    
    engine = create_engine(
        host=host,
        port=port,
        username="default",
        password="",
        database=database,
    )
    return Session(engine)


def setup_data(session):
    # Using metadata to create table
    metadata.drop_all(session.engine)
    metadata.create_all(session.engine)
    
    # Generate some dummy data
    # Cohort 1: Jan 1st
    # Cohort 2: Jan 2nd
    
    events = []
    base_date = date(2024, 1, 1)
    
    # User 1: Full funnel, Cohort Jan 1
    events.append(UserEvent(user_id=1, event_type="signup", timestamp=base_date, amount=0))
    events.append(UserEvent(user_id=1, event_type="view_item", timestamp=base_date, amount=0))
    events.append(UserEvent(user_id=1, event_type="add_to_cart", timestamp=base_date, amount=0))
    events.append(UserEvent(user_id=1, event_type="purchase", timestamp=base_date, amount=100))
    
    # User 2: Drop off after view, Cohort Jan 1
    events.append(UserEvent(user_id=2, event_type="signup", timestamp=base_date, amount=0))
    events.append(UserEvent(user_id=2, event_type="view_item", timestamp=base_date, amount=0))
    
    # User 3: Full funnel, Cohort Jan 2
    next_day = base_date + timedelta(days=1)
    events.append(UserEvent(user_id=3, event_type="signup", timestamp=next_day, amount=0))
    events.append(UserEvent(user_id=3, event_type="view_item", timestamp=next_day, amount=0))
    events.append(UserEvent(user_id=3, event_type="purchase", timestamp=next_day, amount=50)) # Skipped cart (direct buy)

    # User 1 returns on Jan 2 (Retention)
    events.append(UserEvent(user_id=1, event_type="view_item", timestamp=next_day, amount=0))

    # Bulk insert using ORM session (efficient batching)
    for e in events:
        session.add(e)
    session.commit()
    print("Data setup complete.")


# --- Recipes ---

def recipe_funnel_analysis(session):
    """
    Funnel Analysis: Signup -> View Item -> Add to Cart -> Purchase
    Calculates conversion rates between steps.
    """
    print("\n--- Recipe: Funnel Analysis ---")
    
    # We use conditional aggregation (countIf) to calculate steps
    # In a real scenario, we might use window functions to ensure order, 
    # but for simple funnels, existence of event is often enough.
    
    stmt = (
        select(
            func.countIf(UserEvent.event_type == "signup").label("step1_signup"),
            func.countIf(UserEvent.event_type == "view_item").label("step2_view"),
            func.countIf(UserEvent.event_type == "add_to_cart").label("step3_cart"),
            func.countIf(UserEvent.event_type == "purchase").label("step4_purchase")
        )
        .select_from(UserEvent)
    )
    
    print(f"SQL: {stmt.to_sql()}")
    result = session.execute(stmt).one()
    
    print(f"Signups:   {result.step1_signup}")
    print(f"Views:     {result.step2_view} (Conv: {result.step2_view / result.step1_signup:.1%})")
    print(f"Carts:     {result.step3_cart} (Conv: {result.step3_cart / result.step2_view:.1%})")
    print(f"Purchases: {result.step4_purchase} (Conv: {result.step4_purchase / result.step3_cart:.1%})")


def recipe_cohort_retention(session):
    """
    Cohort Analysis: Retention by signup date.
    """
    print("\n--- Recipe: Cohort Retention ---")
    
    # 1. Define cohorts: First signup date per user
    cohorts = (
        select(
            UserEvent.user_id,
            func.min(func.toDate(UserEvent.timestamp)).label("cohort_date")
        )
        .select_from(UserEvent)
        .group_by(UserEvent.user_id)
        .cte("cohorts")
    )
    
    # 2. Join events with cohorts and calculate retention
    # We want to count unique users active on subsequent days
    
    # Note: We need to join the CTE. Currently CHORM supports CTEs in WITH clause.
    # We'll select from the CTE and join back to events.
    
    stmt = (
        select(
            Identifier("cohorts.cohort_date"),
            func.dateDiff('day', Identifier("cohorts.cohort_date"), func.toDate(UserEvent.timestamp)).label("days_since_signup"),
            func.uniq(UserEvent.user_id).label("active_users")
        )
        .select_from(Identifier("cohorts"))
        .join(UserEvent, on=Identifier("cohorts.user_id") == UserEvent.user_id)
        .with_cte(cohorts)
        .group_by(Identifier("cohorts.cohort_date"), Identifier("days_since_signup"))
        .order_by(Identifier("cohorts.cohort_date"), Identifier("days_since_signup"))
    )
    
    print(f"SQL: {stmt.to_sql()}")
    results = session.execute(stmt).all()
    
    print("Cohort Date | Day | Active Users")
    print("-" * 35)
    for row in results:
        print(f"{row.cohort_date}  | {row.days_since_signup:3} | {row.active_users}")


def recipe_top_n_with_other(session):
    """
    Top-N Analysis: Top 2 event types by volume, others grouped as 'Other'.
    This is a common visualization pattern.
    """
    print("\n--- Recipe: Top-N with 'Other' ---")
    
    # 1. Get Top N categories
    from chorm.sql.expression import Subquery
    top_n = (
        select(UserEvent.event_type)
        .select_from(UserEvent)
        .group_by(UserEvent.event_type)
        .order_by(func.count().desc())
        .limit(2)
    )
    
    # 2. Main query using the subquery
    # If event_type is in top_n, keep it, else 'Other'
    from chorm.sql.expression import if_
    
    event_type_col = UserEvent.event_type
    category_expr = if_(
        event_type_col.in_(Subquery(top_n)),
        event_type_col,
        Literal("Other")
    ).label("category")
    
    stmt = (
        select(
            category_expr,
            func.count().label("count")
        )
        .select_from(UserEvent)
        .group_by(Identifier("category"))
        .order_by(func.count().desc())
    )
    
    print(f"SQL: {stmt.to_sql()}")
    results = session.execute(stmt).all()
    
    for row in results:
        print(f"{row.category}: {row.count}")


def main():
    session = get_session()
    try:
        setup_data(session)
        recipe_funnel_analysis(session)
        recipe_cohort_retention(session)
        recipe_top_n_with_other(session)
    finally:
        session.execute(f"DROP TABLE IF EXISTS {UserEvent.__tablename__}")


if __name__ == "__main__":
    main()
