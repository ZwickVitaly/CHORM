"""
Window Functions Demonstration for CHORM.

This script demonstrates the new window function capabilities including:
1. Basic OVER() clause
2. PARTITION BY and ORDER BY
3. Standard functions: row_number, rank, dense_rank
4. Analytic functions: lag, lead
5. Window frames (Cumulative Sum)
"""

import sys
import os

# Add project root to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from chorm import Table, Column, MergeTree, select
from chorm.types import UInt64, String, DateTime
from chorm.sql.expression import func, row_number, rank, dense_rank, lag, lead


class User(Table):
    __tablename__ = "users"
    __engine__ = MergeTree()
    
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    city = Column(String())


class Order(Table):
    __tablename__ = "orders"
    __engine__ = MergeTree()
    
    id = Column(UInt64(), primary_key=True)
    user_id = Column(UInt64())
    amount = Column(UInt64())
    date = Column(DateTime())


def demo_row_number():
    print("\n=== 1. Row Number (Pagination/Deduplication) ===")
    # Assign row number to orders per user, ordered by date
    stmt = select(
        Order.id,
        row_number().over(
            partition_by=Order.user_id,
            order_by=Order.date.desc()
        ).label("rn")
    )
    
    print("Python:")
    print('row_number().over(partition_by=Order.user_id, order_by=Order.date.desc())')
    print("\nSQL:")
    print(stmt.to_sql())


def demo_ranking():
    print("\n=== 2. Ranking (Rank vs Dense Rank) ===")
    # Rank users by total order amount (simplified for demo)
    stmt = select(
        User.name,
        rank().over(order_by=User.id.desc()).label("rank"),
        dense_rank().over(order_by=User.id.desc()).label("dense_rank")
    )
    
    print("Python:")
    print('rank().over(order_by=User.id.desc())')
    print('dense_rank().over(order_by=User.id.desc())')
    print("\nSQL:")
    print(stmt.to_sql())


def demo_lag_lead():
    print("\n=== 3. Lag and Lead (Time Series Analysis) ===")
    # Compare current order amount with previous order amount
    stmt = select(
        Order.id,
        Order.amount,
        lag(Order.amount).over(partition_by=Order.user_id, order_by=Order.date).label("prev_amount"),
        lead(Order.amount).over(partition_by=Order.user_id, order_by=Order.date).label("next_amount")
    )
    
    print("Python:")
    print('lag(Order.amount).over(partition_by=Order.user_id, order_by=Order.date)')
    print('lead(Order.amount).over(partition_by=Order.user_id, order_by=Order.date)')
    print("\nSQL:")
    print(stmt.to_sql())


def demo_cumulative_sum():
    print("\n=== 4. Cumulative Sum (Window Frames) ===")
    # Running total of amount per user
    stmt = select(
        Order.user_id,
        Order.date,
        Order.amount,
        func.sum(Order.amount).over(
            partition_by=Order.user_id,
            order_by=Order.date,
            frame="ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW"
        ).label("running_total")
    )
    
    print("Python:")
    print('func.sum(Order.amount).over(')
    print('    partition_by=Order.user_id,')
    print('    order_by=Order.date,')
    print('    frame="ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW"')
    print(')')
    print("\nSQL:")
    print(stmt.to_sql())


if __name__ == "__main__":
    print("CHORM Window Functions Demo")
    print("===========================")
    
    demo_row_number()
    demo_ranking()
    demo_lag_lead()
    demo_cumulative_sum()
