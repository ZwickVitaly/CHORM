"""Integration test for CRUD operations with real ClickHouse."""

import os
from datetime import datetime
from chorm import Table, Column, create_engine, Session, select
from chorm.types import UInt64, String, DateTime
from chorm.table_engines import MergeTree


class User(Table):
    __tablename__ = "test_users_crud"

    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    email = Column(String())
    created_at = Column(DateTime())

    engine = MergeTree()
    __order_by__ = "id"


def main():
    print("=" * 60)
    print("CHORM Integration Test - CRUD Operations")
    print("=" * 60)

    # Create engine and session
    print("\n1. Connecting to ClickHouse...")
    password = os.getenv("CLICKHOUSE_PASSWORD", "123")
    engine = create_engine("clickhouse://localhost:8123/default", username="default", password=password)
    session = Session(engine)
    print("✓ Connected successfully")

    # Create table
    print("\n2. Creating table...")
    with engine.connect() as conn:
        conn.execute("DROP TABLE IF EXISTS test_users_crud")
        conn.execute(User.create_table())
    print("✓ Table created")

    # Test INSERT via Session.add()
    print("\n3. Inserting data via Session.add()...")
    users = [
        User(id=1, name="Alice", email="alice@example.com", created_at=datetime.now()),
        User(id=2, name="Bob", email="bob@example.com", created_at=datetime.now()),
        User(id=3, name="Charlie", email="charlie@example.com", created_at=datetime.now()),
    ]

    for user in users:
        session.add(user)

    session.commit()
    print(f"✓ Inserted {len(users)} users")

    # Test SELECT via Session.execute()
    print("\n4. Querying data...")

    # Simple select all
    print("\n  a) SELECT * FROM test_users_crud:")
    stmt = select(User.id, User.name, User.email)
    result = session.execute(stmt)
    rows = result.all()

    for row in rows:
        print(f"     {row}")

    print(f"  ✓ Retrieved {len(rows)} rows")

    # Select with WHERE
    print("\n  b) SELECT with WHERE (id > 1):")
    stmt = select(User.id, User.name).where(User.id > 1)
    result = session.execute(stmt)
    rows = result.all()

    for row in rows:
        print(f"     {row}")

    print(f"  ✓ Retrieved {len(rows)} rows")

    # Select with ORDER BY and LIMIT
    print("\n  c) SELECT with ORDER BY and LIMIT:")
    stmt = select(User.name, User.email).order_by(User.name).limit(2)
    result = session.execute(stmt)
    rows = result.all()

    for row in rows:
        print(f"     {row}")

    print(f"  ✓ Retrieved {len(rows)} rows")

    # Test aggregation
    print("\n  d) SELECT COUNT(*):")
    from chorm.sql.expression import count

    stmt = select(count())
    result = session.execute(stmt)
    count_result = result.first()
    print(f"     Total users: {count_result[0]}")

    # Test UPDATE
    print("\n5. Testing UPDATE (ALTER TABLE)...")
    from chorm import update

    stmt = update(User).where(User.id == 1).values(name="Alice Updated")
    session.execute(stmt)
    print("  ✓ Update executed")

    # Verify update
    print("\n  Verifying update:")
    stmt = select(User.id, User.name).where(User.id == 1)
    result = session.execute(stmt)
    row = result.first()
    print(f"     {row}")

    if row[1] == "Alice Updated":
        print("  ✓ Update verified")
    else:
        print("  ✗ Update failed!")

    # Test DELETE
    print("\n6. Testing DELETE (ALTER TABLE)...")
    from chorm import delete

    stmt = delete(User).where(User.id == 3)
    session.execute(stmt)
    print("  ✓ Delete executed")

    # Verify delete
    print("\n  Verifying delete:")
    stmt = select(count())
    result = session.execute(stmt)
    count_after = result.first()[0]
    print(f"     Users remaining: {count_after}")

    if count_after == 2:
        print("  ✓ Delete verified")
    else:
        print(f"  ✗ Delete failed! Expected 2, got {count_after}")

    # Cleanup
    print("\n7. Cleaning up...")
    with engine.connect() as conn:
        conn.execute("DROP TABLE IF EXISTS test_users_crud")
    print("✓ Cleanup complete")

    session.close()

    print("\n" + "=" * 60)
    print("CRUD operations test completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
