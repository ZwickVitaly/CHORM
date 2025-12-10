"""
Subqueries Demonstration for CHORM.

This script demonstrates the new subquery capabilities including:
1. Subqueries in WHERE clause (IN, EXISTS)
2. Subqueries in FROM clause (Derived Tables)
3. Scalar subqueries in SELECT list
4. Correlated subqueries
"""

import sys
import os

# Add project root to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from chorm import Table, Column, MergeTree, select
from chorm.types import UInt64, String
from chorm.sql.expression import func, exists, Identifier


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


def demo_subquery_in_where():
    print("\n=== 1. Subquery in WHERE (IN) ===")
    # Find users who have placed orders with amount > 1000
    subq = select(Order.user_id).where(Order.amount > 1000).subquery()
    stmt = select(User.name).where(User.id.in_(subq))
    
    print("Python:")
    print('subq = select(Order.user_id).where(Order.amount > 1000).subquery()')
    print('stmt = select(User.name).where(User.id.in_(subq))')
    print("\nSQL:")
    print(stmt.to_sql())


def demo_subquery_exists():
    print("\n=== 2. Subquery in WHERE (EXISTS) ===")
    # Find users who have at least one order
    # Correlated subquery: WHERE orders.user_id = users.id
    subq = select(Order.id).where(Order.user_id == User.id)
    stmt = select(User.name).where(exists(subq))
    
    print("Python:")
    print('subq = select(Order.id).where(Order.user_id == User.id)')
    print('stmt = select(User.name).where(exists(subq))')
    print("\nSQL:")
    print(stmt.to_sql())


def demo_subquery_in_from():
    print("\n=== 3. Subquery in FROM (Derived Table) ===")
    # Select from a subquery that filters users by city
    subq = select(User.name, User.city).where(User.city == "Moscow").subquery("moscow_users")
    stmt = select(Identifier("*")).select_from(subq)
    
    print("Python:")
    print('subq = select(User.name, User.city).where(User.city == "Moscow").subquery("moscow_users")')
    print('stmt = select(Identifier("*")).select_from(subq)')
    print("\nSQL:")
    print(stmt.to_sql())


def demo_scalar_subquery():
    print("\n=== 4. Scalar Subquery in SELECT ===")
    # Select user name and count of their orders
    # Need explicit select_from(Order) for the subquery to ensure FROM clause is generated
    subq = select(func.count(Order.id)).select_from(Order).where(Order.user_id == User.id).scalar_subquery().label("order_count")
    stmt = select(User.name, subq).select_from(User)
    
    print("Python:")
    print('subq = select(func.count(Order.id)).select_from(Order).where(Order.user_id == User.id).scalar_subquery().label("order_count")')
    print('stmt = select(User.name, subq).select_from(User)')
    print("\nSQL:")
    print(stmt.to_sql())


def demo_scalar_subquery_comparison():
    print("\n=== 5. Scalar Subquery Comparison ===")
    # Find orders with amount greater than average amount
    avg_amount = select(func.avg(Order.amount)).select_from(Order).scalar_subquery()
    stmt = select(Order.id).select_from(Order).where(Order.amount > avg_amount)
    
    print("Python:")
    print('avg_amount = select(func.avg(Order.amount)).select_from(Order).scalar_subquery()')
    print('stmt = select(Order.id).select_from(Order).where(Order.amount > avg_amount)')
    print("\nSQL:")
    print(stmt.to_sql())


if __name__ == "__main__":
    print("CHORM Subqueries Demo")
    print("=====================")
    
    demo_subquery_in_where()
    demo_subquery_exists()
    demo_subquery_in_from()
    demo_scalar_subquery()
    demo_scalar_subquery_comparison()
