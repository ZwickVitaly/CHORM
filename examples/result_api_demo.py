"""Demonstration of Result API - Flexible row access patterns in CHORM.

This example shows all the ways to access query results:
- Row objects (default) - attribute, dict, and index access
- Mappings - pure dicts
- Tuples - raw tuples
- Scalars - single column values
- Convenience methods - scalar(), first(), one()
"""

from chorm import Table, Column, MergeTree, select
from chorm.types import UInt64, String, Date
from chorm.sql.expression import func


# Define tables
class User(Table):
    __tablename__ = "users"
    __engine__ = MergeTree()
    
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    city = Column(String())
    age = Column(UInt64())


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
    print("CHORM Result API - Flexible Row Access")
    print("=" * 80)
    
    # ========================================================================
    # 1. Row Objects (Default) - SQLAlchemy-like flexibility
    # ========================================================================
    print("\n" + "=" * 80)
    print("1. Row Objects - Attribute, Dict, and Index Access")
    print("=" * 80)
    
    stmt = (
        select(
            User.city,
            func.count(User.id).label("user_count"),
            func.avg(User.age).label("avg_age")
        )
        .select_from(User)
        .group_by(User.city)
    )
    
    print("\nSQL Query:")
    print(stmt.to_sql())
    
    print("\n# Default: Returns Row objects")
    print("result = session.execute(stmt).all()")
    print("\n# Access via attributes (most readable):")
    print("for row in result:")
    print("    print(f'{row.city}: {row.user_count} users, avg age {row.avg_age}')")
    print("\n# Access via dict keys:")
    print("for row in result:")
    print("    print(f\"{row['city']}: {row['user_count']} users\")")
    print("\n# Access via index (like tuples):")
    print("for row in result:")
    print("    print(f'{row[0]}: {row[1]} users')")
    print("\n# Convert to dict or tuple:")
    print("row = result[0]")
    print("row_dict = row._asdict()  # {'city': 'Moscow', 'user_count': 2, ...}")
    print("row_tuple = row._tuple()  # ('Moscow', 2, 30.0)")
    
    # ========================================================================
    # 2. Mappings - Pure Dictionaries
    # ========================================================================
    print("\n" + "=" * 80)
    print("2. Mappings - Returns Pure Dicts")
    print("=" * 80)
    
    stmt = (
        select(
            User.name,
            func.count(Order.id).label("order_count"),
            func.sum(Order.amount).label("total_spent")
        )
        .select_from(User)
        .join(Order, on=User.id == Order.user_id)
        .group_by(User.name)
    )
    
    print("\nSQL Query:")
    print(stmt.to_sql())
    
    print("\n# Get results as dicts:")
    print("result = session.execute(stmt).mappings().all()")
    print("# Returns: [{'name': 'Alice', 'order_count': 2, 'total_spent': 300}, ...]")
    print("\nfor user_dict in result:")
    print("    print(f\"{user_dict['name']}: {user_dict['total_spent']} spent\")")
    
    # ========================================================================
    # 3. Tuples - Raw Tuples
    # ========================================================================
    print("\n" + "=" * 80)
    print("3. Tuples - Returns Raw Tuples")
    print("=" * 80)
    
    stmt = select(User.name, User.city).select_from(User)
    
    print("\nSQL Query:")
    print(stmt.to_sql())
    
    print("\n# Get results as tuples:")
    print("result = session.execute(stmt).tuples().all()")
    print("# Returns: [('Alice', 'Moscow'), ('Bob', 'SPB'), ...]")
    print("\nfor name, city in result:")
    print("    print(f'{name} from {city}')")
    
    # ========================================================================
    # 4. Scalars - Single Column Values
    # ========================================================================
    print("\n" + "=" * 80)
    print("4. Scalars - Extract Single Column")
    print("=" * 80)
    
    stmt = select(User.name, User.age).select_from(User)
    
    print("\nSQL Query:")
    print(stmt.to_sql())
    
    print("\n# Extract first column (by index):")
    print("names = session.execute(stmt).scalars(0).all()")
    print("# Returns: ['Alice', 'Bob', 'Charlie']")
    
    print("\n# Extract column by name:")
    print("ages = session.execute(stmt).scalars('age').all()")
    print("# Returns: [25, 30, 35]")
    
    # ========================================================================
    # 5. Convenience Methods
    # ========================================================================
    print("\n" + "=" * 80)
    print("5. Convenience Methods - first(), one(), scalar()")
    print("=" * 80)
    
    print("\n# Get first row:")
    stmt = select(User.name, User.city).select_from(User).limit(1)
    print(stmt.to_sql())
    print("first_row = session.execute(stmt).first()")
    print("# Returns: Row(name='Alice', city='Moscow')")
    
    print("\n# Get exactly one row (raises if 0 or >1):")
    stmt = select(User.name).select_from(User).where(User.id == 1)
    print(stmt.to_sql())
    print("user = session.execute(stmt).one()")
    print("# Returns: Row(name='Alice')")
    
    print("\n# Get single scalar value:")
    stmt = select(func.count(User.id)).select_from(User)
    print(stmt.to_sql())
    print("total = session.execute(stmt).scalar()")
    print("# Returns: 3")
    
    print("\n# Scalar with one() - ensure exactly one result:")
    stmt = select(func.max(User.age)).select_from(User)
    print(stmt.to_sql())
    print("max_age = session.execute(stmt).scalars().scalar_one()")
    print("# Returns: 35")
    
    # ========================================================================
    # 6. Real-World Example - Analytics Query
    # ========================================================================
    print("\n" + "=" * 80)
    print("6. Real-World Example - User Analytics")
    print("=" * 80)
    
    stmt = (
        select(
            User.name,
            User.city,
            func.count(Order.id).label("total_orders"),
            func.sum(Order.amount).label("total_spent"),
            func.avg(Order.amount).label("avg_order_value"),
            func.max(Order.date).label("last_order_date")
        )
        .select_from(User)
        .join(Order, on=User.id == Order.user_id)
        .where(Order.status == "completed")
        .group_by(User.name, User.city)
        .having(func.count(Order.id) > 0)
        .order_by(func.sum(Order.amount).desc())
    )
    
    print("\nSQL Query:")
    print(stmt.to_sql())
    
    print("\n# Access with Row objects (most flexible):")
    print("result = session.execute(stmt).all()")
    print("for row in result:")
    print("    print(f'''")
    print("    User: {row.name} ({row.city})")
    print("    Orders: {row.total_orders}")
    print("    Total Spent: ${row.total_spent}")
    print("    Avg Order: ${row.avg_order_value:.2f}")
    print("    Last Order: {row.last_order_date}")
    print("    ''')")
    
    # ========================================================================
    # 7. When to Use Each Pattern
    # ========================================================================
    print("\n" + "=" * 80)
    print("7. When to Use Each Access Pattern")
    print("=" * 80)
    
    print("""
┌─────────────────┬──────────────────────────────────────────────────────┐
│ Pattern         │ Use When...                                          │
├─────────────────┼──────────────────────────────────────────────────────┤
│ Row (default)   │ • Working with labeled aggregations                  │
│                 │ • Need flexible access (attribute/dict/index)        │
│                 │ • Most readable code                                 │
│                 │ • Example: row.user_count, row['city'], row[0]      │
├─────────────────┼──────────────────────────────────────────────────────┤
│ .mappings()     │ • Need pure dicts for JSON serialization            │
│                 │ • Passing to functions expecting dicts               │
│                 │ • Example: json.dumps(result.mappings().all())       │
├─────────────────┼──────────────────────────────────────────────────────┤
│ .tuples()       │ • Simple unpacking in loops                          │
│                 │ • Performance-critical code (minimal overhead)       │
│                 │ • Example: for name, city in result.tuples().all()  │
├─────────────────┼──────────────────────────────────────────────────────┤
│ .scalars()      │ • Need single column values                          │
│                 │ • Building lists/sets from query results             │
│                 │ • Example: user_ids = result.scalars('id').all()    │
├─────────────────┼──────────────────────────────────────────────────────┤
│ .scalar()       │ • Aggregation queries (COUNT, SUM, MAX, etc.)        │
│                 │ • Need single value from single row                  │
│                 │ • Example: total = session.execute(stmt).scalar()   │
└─────────────────┴──────────────────────────────────────────────────────┘
    """)
    
    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)
    print("""
CHORM's Result API provides SQLAlchemy-like flexibility:

✅ Row objects (default) - Attribute, dict, and index access
✅ Mappings - Pure dictionaries for JSON/serialization
✅ Tuples - Raw tuples for simple unpacking
✅ Scalars - Single column extraction by name or index
✅ Convenience methods - first(), one(), scalar()

Choose the pattern that makes your code most readable!
    """)


if __name__ == "__main__":
    main()
