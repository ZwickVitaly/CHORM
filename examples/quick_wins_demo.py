"""Demonstration of Quick Wins features in CHORM."""

from chorm import Table, Column, MergeTree, select, MetaData
from chorm.types import UInt64, String, DateTime


metadata = MetaData()


# Define tables
class User(Table):
    metadata = metadata
    __tablename__ = "users"
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    city = Column(String())
    created_at = Column(DateTime())
    __engine__ = MergeTree()


def main():
    print("=" * 80)
    print("CHORM Quick Wins Features")
    print("=" * 80)
    
    # Example 1: DISTINCT (already implemented!)
    print("\n1. DISTINCT (already implemented):")
    stmt1 = select(User.city).distinct()
    print(stmt1.to_sql())
    
    # Example 2: UNION (removes duplicates)
    print("\n2. UNION (removes duplicates):")
    query1 = select(User.name).where(User.city == "Moscow")
    query2 = select(User.name).where(User.city == "SPB")
    stmt2 = query1.union(query2)
    print(stmt2.to_sql())
    
    # Example 3: UNION ALL (keeps duplicates)
    print("\n3. UNION ALL (keeps all results):")
    query1 = select(User.id, User.name).where(User.city == "Moscow")
    query2 = select(User.id, User.name).where(User.city == "SPB")
    stmt3 = query1.union_all(query2)
    print(stmt3.to_sql())
    
    # Example 4: Multiple UNIONs
    print("\n4. Multiple UNION operations:")
    q1 = select(User.name).where(User.city == "Moscow")
    q2 = select(User.name).where(User.city == "SPB")
    q3 = select(User.name).where(User.city == "Kazan")
    stmt4 = q1.union(q2).union(q3)
    print(stmt4.to_sql())
    
    # Example 5: ORDER BY with asc()
    print("\n5. ORDER BY with asc():")
    stmt5 = select(User).order_by(User.name.asc())
    print(stmt5.to_sql())
    
    # Example 6: ORDER BY with desc()
    print("\n6. ORDER BY with desc():")
    stmt6 = select(User).order_by(User.created_at.desc())
    print(stmt6.to_sql())
    
    # Example 7: ORDER BY with multiple columns
    print("\n7. ORDER BY with multiple columns (mix ASC/DESC):")
    stmt7 = select(User).order_by(User.city.asc(), User.name.desc(), User.id.asc())
    print(stmt7.to_sql())
    
    # Example 8: UNION with ORDER BY
    print("\n8. UNION with ORDER BY:")
    q1 = select(User.name).where(User.city == "Moscow")
    q2 = select(User.name).where(User.city == "SPB")
    stmt8 = q1.union(q2).order_by(User.name.asc())
    print(stmt8.to_sql())
    
    # Example 9: UNION with LIMIT
    print("\n9. UNION with LIMIT:")
    q1 = select(User.id).where(User.city == "Moscow")
    q2 = select(User.id).where(User.city == "SPB")
    stmt9 = q1.union(q2).limit(10)
    print(stmt9.to_sql())
    
    # Example 10: DISTINCT with UNION
    print("\n10. DISTINCT with UNION:")
    q1 = select(User.city).distinct().where(User.name.like("A%"))
    q2 = select(User.city).where(User.name.like("B%"))
    stmt10 = q1.union(q2)
    print(stmt10.to_sql())
    
    # Example 11: Complex query with multiple features
    print("\n11. Complex query combining multiple features:")
    q1 = select(User.city, User.name).where(User.id > 100).order_by(User.name.asc())
    q2 = select(User.city, User.name).where(User.id < 10).order_by(User.name.desc())
    stmt11 = q1.union_all(q2).limit(20)
    print(stmt11.to_sql())
    
    print("\n" + "=" * 80)
    print("All Quick Wins features demonstrated successfully!")
    print("=" * 80)


if __name__ == "__main__":
    main()
