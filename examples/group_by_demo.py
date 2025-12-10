"""Demonstration of GROUP BY and aggregation functionality in CHORM."""

from chorm import Table, Column, MergeTree, select
from chorm.types import UInt64, String, Date
from chorm.sql.expression import func, Identifier



# Define tables
class User(Table):
    __tablename__ = "users"
    __engine__ = MergeTree()
    
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    city = Column(String())
    country = Column(String())


class Order(Table):
    __tablename__ = "orders"
    __engine__ = MergeTree()
    
    id = Column(UInt64(), primary_key=True)
    user_id = Column(UInt64())
    amount = Column(UInt64())
    status = Column(String())
    date = Column(Date())


def main():
    print("=" * 80)
    print("CHORM GROUP BY and Aggregation Examples")
    print("=" * 80)
    
    # Example 1: Simple GROUP BY with COUNT
    print("\n1. Simple GROUP BY with COUNT:")
    stmt1 = (
        select(User.city, func.count(User.id).label("user_count"))
        .select_from(User)
        .group_by(User.city)
    )
    print(stmt1.to_sql())
    print("-- Groups users by city and counts them")
    
    # Example 2: GROUP BY with multiple aggregations
    print("\n2. GROUP BY with multiple aggregations:")
    stmt2 = (
        select(
            Order.status,
            func.count(Order.id).label("order_count"),
            func.sum(Order.amount).label("total_amount"),
            func.avg(Order.amount).label("avg_amount")
        )
        .select_from(Order)
        .group_by(Order.status)
    )
    print(stmt2.to_sql())
    print("-- Aggregates orders by status with count, sum, and average")
    
    # Example 3: GROUP BY with HAVING
    print("\n3. GROUP BY with HAVING clause:")
    stmt3 = (
        select(User.city, func.count(User.id).label("user_count"))
        .select_from(User)
        .group_by(User.city)
        .having(func.count(User.id) > 10)
    )
    print(stmt3.to_sql())
    print("-- Only shows cities with more than 10 users")
    
    # Example 4: GROUP BY with multiple columns
    print("\n4. GROUP BY with multiple columns:")
    stmt4 = (
        select(
            User.city,
            User.country,
            func.count(User.id).label("user_count")
        )
        .select_from(User)
        .group_by(User.city, User.country)
    )
    print(stmt4.to_sql())
    print("-- Groups by both city and country")
    
    # Example 5: GROUP BY with expression
    print("\n5. GROUP BY with expression (date functions):")
    stmt5 = (
        select(
            func.toYYYYMM(Order.date).label("month"),
            func.sum(Order.amount).label("monthly_total")
        )
        .select_from(Order)
        .group_by(func.toYYYYMM(Order.date))
    )
    print(stmt5.to_sql())
    print("-- Groups orders by month and calculates monthly totals")
    
    # Example 6: GROUP BY with WHERE and HAVING
    print("\n6. GROUP BY with WHERE and HAVING:")
    stmt6 = (
        select(Order.status, func.sum(Order.amount).label("total"))
        .select_from(Order)
        .where(Order.date >= "2024-01-01")
        .group_by(Order.status)
        .having(func.sum(Order.amount) > 1000)
    )
    print(stmt6.to_sql())
    print("-- Filters orders from 2024, groups by status, shows only totals > 1000")
    
    # Example 7: GROUP BY with ORDER BY
    print("\n7. GROUP BY with ORDER BY:")
    stmt7 = (
        select(User.city, func.count(User.id).label("user_count"))
        .select_from(User)
        .group_by(User.city)
        .order_by(func.count(User.id).desc())
        .limit(5)
    )
    print(stmt7.to_sql())
    print("-- Top 5 cities by user count")
    
    # Example 8: GROUP BY with JOIN
    print("\n8. GROUP BY with JOIN:")
    stmt8 = (
        select(
            User.name,
            func.count(Order.id).label("order_count"),
            func.sum(Order.amount).label("total_spent")
        )
        .select_from(User)
        .join(Order, on=User.id == Order.user_id)
        .group_by(User.name)
    )
    print(stmt8.to_sql())
    print("-- Aggregates orders per user")
    
    # Example 9: Complex HAVING with multiple conditions
    print("\n9. Complex HAVING with multiple conditions:")
    stmt9 = (
        select(
            User.city,
            func.count(User.id).label("user_count"),
            func.avg(User.id).label("avg_id")
        )
        .select_from(User)
        .group_by(User.city)
        .having(
            (func.count(User.id) > 5) & (func.avg(User.id) < 1000)
        )
    )
    print(stmt9.to_sql())
    print("-- Cities with >5 users AND average ID <1000")
    
    # Example 10: GROUP BY with DISTINCT
    print("\n10. GROUP BY with DISTINCT:")
    stmt10 = (
        select(
            User.country,
            func.count(func.distinct(User.city)).label("city_count")
        )
        .select_from(User)
        .group_by(User.country)
    )
    print(stmt10.to_sql())
    print("-- Counts distinct cities per country")
    
    # Example 11: Nested aggregations with subquery
    print("\n11. GROUP BY in subquery:")
    subq = (
        select(Order.user_id, func.sum(Order.amount).label("total"))
        .select_from(Order)
        .group_by(Order.user_id)
        .subquery("user_totals")
    )
    stmt11 = (
        select(User.name, Identifier("user_totals.total"))
        .select_from(User)
        .join(subq, on=User.id == Identifier("user_totals.user_id"))
        .where(Identifier("user_totals.total") > 500)
    )
    print(stmt11.to_sql())
    print("-- Uses GROUP BY in subquery to find high-value users")


    
    print("\n" + "=" * 80)
    print("Common Aggregation Functions:")
    print("  - func.count()     - Count rows")
    print("  - func.sum()       - Sum values")
    print("  - func.avg()       - Average")
    print("  - func.min()       - Minimum")
    print("  - func.max()       - Maximum")
    print("  - func.distinct()  - Count distinct values")
    print("=" * 80)


if __name__ == "__main__":
    main()
