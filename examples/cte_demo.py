"""
Demonstration of CTEs (Common Table Expressions) in CHORM.

This script shows how to use WITH clauses to create named temporary result sets
that can be referenced in the main query.
"""

import sys
import os

# Add project root to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from chorm import Table, Column, MergeTree, select
from chorm.types import UInt64, String, Date
from chorm.sql.expression import func, Identifier


class User(Table):
    __tablename__ = "users"
    __engine__ = MergeTree()
    
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    city = Column(String())
    active = Column(UInt64())


class Order(Table):
    __tablename__ = "orders"
    __engine__ = MergeTree()
    
    id = Column(UInt64(), primary_key=True)
    user_id = Column(UInt64())
    amount = Column(UInt64())
    date = Column(Date())


def demo_simple_cte():
    print("\n=== 1. Simple CTE ===")
    # Create a CTE for Moscow users
    cte = select(User.id, User.name).where(User.city == "Moscow").cte("moscow_users")
    
    # Use the CTE in main query
    stmt = select(Identifier("*")).select_from(Identifier("moscow_users")).with_cte(cte)
    
    print("Python:")
    print('cte = select(User.id, User.name).where(User.city == "Moscow").cte("moscow_users")')
    print('stmt = select(Identifier("*")).select_from(Identifier("moscow_users")).with_cte(cte)')
    print("\nSQL:")
    print(stmt.to_sql())


def demo_cte_with_aggregation():
    print("\n=== 2. CTE with Aggregation ===")
    # Create a CTE that aggregates orders by user
    cte = (
        select(Order.user_id, func.sum(Order.amount).label("total"))
        .group_by(Order.user_id)
        .cte("user_totals")
    )
    
    # Query users with high totals
    stmt = (
        select(Identifier("user_totals.user_id"), Identifier("user_totals.total"))
        .select_from(Identifier("user_totals"))
        .where(Identifier("user_totals.total") > 1000)
        .with_cte(cte)
    )
    
    print("Python:")
    print('cte = select(Order.user_id, func.sum(Order.amount).label("total")).group_by(Order.user_id).cte("user_totals")')
    print('stmt = select(...).select_from(Identifier("user_totals")).where(...).with_cte(cte)')
    print("\nSQL:")
    print(stmt.to_sql())


def demo_multiple_ctes():
    print("\n=== 3. Multiple CTEs ===")
    # CTE 1: Active users
    cte1 = select(User.id, User.name).where(User.active == 1).cte("active_users")
    
    # CTE 2: Recent orders
    cte2 = (
        select(Order.user_id, func.count(Order.id).label("order_count"))
        .where(Order.date >= "2024-01-01")
        .group_by(Order.user_id)
        .cte("recent_orders")
    )
    
    # Use both CTEs
    stmt = (
        select(
            Identifier("active_users.name"),
            Identifier("recent_orders.order_count")
        )
        .select_from(Identifier("active_users"))
        .join(
            Identifier("recent_orders"),
            using=["id"]  # Assuming we rename columns appropriately
        )
        .with_cte(cte1, cte2)
    )
    
    print("Python:")
    print('cte1 = select(User.id, User.name).where(User.active == 1).cte("active_users")')
    print('cte2 = select(...).group_by(Order.user_id).cte("recent_orders")')
    print('stmt = select(...).with_cte(cte1, cte2)')
    print("\nSQL:")
    print(stmt.to_sql())


def demo_cte_vs_subquery():
    print("\n=== 4. CTE vs Subquery Comparison ===")
    
    print("\n--- Using Subquery ---")
    subq = select(Order.user_id).where(Order.amount > 1000).subquery()
    stmt_subq = select(User.name).where(User.id.in_(subq))
    print(stmt_subq.to_sql())
    
    print("\n--- Using CTE (more readable for complex queries) ---")
    cte = select(Order.user_id).where(Order.amount > 1000).cte("high_value_users")
    stmt_cte = (
        select(User.name)
        .where(User.id.in_(Identifier("high_value_users")))
        .with_cte(cte)
    )
    print(stmt_cte.to_sql())


def demo_cte_with_window_function():
    print("\n=== 5. CTE with Window Function ===")
    # Create a CTE with window function
    cte = (
        select(
            Order.user_id,
            Order.amount,
            func.row_number().over(
                partition_by=Order.user_id,
                order_by=Order.amount.desc()
            ).label("rank")
        )
        .cte("ranked_orders")
    )
    
    # Get top order per user
    stmt = (
        select(Identifier("*"))
        .select_from(Identifier("ranked_orders"))
        .where(Identifier("ranked_orders.rank") == 1)
        .with_cte(cte)
    )
    
    print("Python:")
    print('cte = select(..., func.row_number().over(...).label("rank")).cte("ranked_orders")')
    print('stmt = select(*).where(rank == 1).with_cte(cte)')
    print("\nSQL:")
    print(stmt.to_sql())


if __name__ == "__main__":
    print("CHORM CTEs (Common Table Expressions) Demo")
    print("=" * 80)
    
    demo_simple_cte()
    demo_cte_with_aggregation()
    demo_multiple_ctes()
    demo_cte_vs_subquery()
    demo_cte_with_window_function()
    
    print("\n" + "=" * 80)
    print("Benefits of CTEs:")
    print("  - Improved readability for complex queries")
    print("  - Can be referenced multiple times in the same query")
    print("  - Better organization of query logic")
    print("  - Easier to debug and maintain")
    print("=" * 80)
