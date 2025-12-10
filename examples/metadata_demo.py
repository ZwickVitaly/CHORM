"""
MetaData and Schema Management Demo
===================================

This example demonstrates how to use the MetaData registry for schema management.

Key Concepts:
- Using `MetaData` to register table definitions
- Creating tables with `metadata.create_all()`
- Dropping tables with `metadata.drop_all()`
- Managing multiple metadata collections

Run: python examples/metadata_demo.py
"""

from chorm import Table, Column, MetaData, create_engine, Session, MergeTree
from chorm.types import UInt64, String, DateTime

# 1. Create a MetaData registry
metadata = MetaData()


# 2. Define tables associated with this metadata
class User(Table):
    metadata = metadata
    __tablename__ = "demo_users"
    __engine__ = MergeTree()
    
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    email = Column(String())
    created_at = Column(DateTime(), default="now()")


class AccessLog(Table):
    metadata = metadata
    __tablename__ = "demo_access_logs"
    __engine__ = MergeTree()
    
    id = Column(UInt64(), primary_key=True)
    user_id = Column(UInt64())
    path = Column(String())


def main():
    print("MetaData Demo")
    print("=============")
    
    # Create engine (connection to ClickHouse)
    engine = create_engine("clickhouse://localhost:8123/default")
    
    print("\n1. Registered tables:")
    for name in metadata.tables:
        print(f"   - {name}")
        
    # 3. Create schema
    print("\n2. Creating tables...")
    metadata.create_all(engine)
    print("   ✓ Tables created successfully")
    
    # Verify creation
    session = Session(engine)
    tables = session.execute("SHOW TABLES LIKE 'demo_%'").fetchall()
    print(f"   Tables in DB: {[t[0] for t in tables]}")
    
    # 4. Use tables
    print("\n3. Inserting data...")
    user = User(id=1, name="Alice", email="alice@example.com")
    session.add(user)
    session.commit()
    print("   ✓ Data inserted")
    
    # 5. Drop schema
    print("\n4. Dropping tables...")
    # metadata.drop_all(engine) # Uncomment to drop
    print("   (Skipping actual drop to keep data for inspection)")
    print("   Run `metadata.drop_all(engine)` to clean up.")

    session.close()


if __name__ == "__main__":
    main()
