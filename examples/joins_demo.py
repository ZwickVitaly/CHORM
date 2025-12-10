"""Demonstration of JOIN functionality in CHORM."""

from chorm import Table, Column, MergeTree, select
from chorm.types import UInt64, String
from chorm.sql.expression import func


# Define tables
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
    product_id = Column(UInt64())
    amount = Column(UInt64())
    status = Column(String())


class Product(Table):
    __tablename__ = "products"
    __engine__ = MergeTree()
    
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    price = Column(UInt64())


def main():
    print("=" * 80)
    print("CHORM JOIN Examples")
    print("=" * 80)
    
    # Example 1: INNER JOIN
    print("\n1. INNER JOIN with ON condition:")
    stmt1 = (
        select(User.name, Order.amount)
        .select_from(User)
        .join(Order, on=User.id == Order.user_id)
        .where(Order.status == "completed")
    )
    print(stmt1.to_sql())
    
    # Example 2: LEFT JOIN
    print("\n2. LEFT JOIN:")
    stmt2 = (
        select(User.name, Order.amount)
        .select_from(User)
        .left_join(Order, on=User.id == Order.user_id)
    )
    print(stmt2.to_sql())
    
    # Example 3: USING clause
    print("\n3. INNER JOIN with USING clause:")
    stmt3 = select(User).join(Order, using=["user_id"])
    print(stmt3.to_sql())
    
    # Example 4: Multiple JOINs
    print("\n4. Multiple JOINs:")
    stmt4 = (
        select(User.name, Order.amount)
        .select_from(User)
        .join(Order, on=User.id == Order.user_id)
        .join(Product, on=Order.product_id == Product.id)
    )
    print(stmt4.to_sql())
    
    # Example 5: JOIN with complex conditions
    print("\n5. JOIN with complex AND/OR conditions:")
    stmt5 = select(User).join(
        Order, on=(User.id == Order.user_id) & (Order.status == "active")
    )
    print(stmt5.to_sql())
    
    # Example 6: CROSS JOIN
    print("\n6. CROSS JOIN:")
    stmt6 = select(User.name, Product.name).select_from(User).cross_join(Product)
    print(stmt6.to_sql())
    
    # Example 7: JOIN with GROUP BY and aggregation
    print("\n7. JOIN with aggregation:")
    stmt7 = (
        select(User.name, func.count(Order.id).label("order_count"))
        .select_from(User)
        .join(Order, on=User.id == Order.user_id)
        .group_by(User.name)
    )
    print(stmt7.to_sql())
    
    # Example 8: Mixed JOIN types
    print("\n8. Mixed JOIN types (LEFT and RIGHT):")
    stmt8 = (
        select(User.name)
        .select_from(User)
        .left_join(Order, on=User.id == Order.user_id)
    )
    print(stmt8.to_sql())
    
    # Example 9: FULL OUTER JOIN
    print("\n9. FULL OUTER JOIN:")
    stmt9 = select(User).full_join(Order, on=User.id == Order.user_id)
    print(stmt9.to_sql())
    
    # Example 10: JOIN with multiple WHERE conditions
    print("\n10. JOIN with WHERE and PREWHERE:")
    stmt10 = (
        select(User.name, Order.amount)
        .select_from(User)
        .join(Order, on=User.id == Order.user_id)
        .prewhere(User.city == "Moscow")
        .where(Order.amount > 100)
        .order_by(Order.amount)
        .limit(10)
    )
    print(stmt10.to_sql())
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
