"""Integration test for DDL and basic operations with real ClickHouse."""

import os
from chorm import Table, Column, create_engine, Session
from chorm.types import UInt64, String, DateTime, Array, Nullable
from chorm.table_engines import MergeTree


# Define test tables
class User(Table):
    __tablename__ = "test_users"

    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    email = Column(String())
    created_at = Column(DateTime())

    engine = MergeTree()
    __order_by__ = "id"


class Product(Table):
    __tablename__ = "test_products"

    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    price = Column(UInt64())
    tags = Column(Array(String()))
    description = Column(Nullable(String()))

    engine = MergeTree()
    __order_by__ = "id"
    __partition_by__ = "toYYYYMM(toDateTime(id))"


def main():
    print("=" * 60)
    print("CHORM Integration Test - DDL Verification")
    print("=" * 60)

    # Create engine
    print("\n1. Connecting to ClickHouse...")
    password = os.getenv("CLICKHOUSE_PASSWORD", "123")
    engine = create_engine("clickhouse://localhost:8123/default", username="default", password=password)
    print("✓ Connected successfully")

    # Test DDL generation
    print("\n2. Generating DDL statements...")
    print("\n--- User Table DDL ---")
    user_ddl = User.create_table(exists_ok=True)
    print(user_ddl)

    print("\n--- Product Table DDL ---")
    product_ddl = Product.create_table(exists_ok=True)
    print(product_ddl)

    # Execute DDL
    print("\n3. Creating tables in ClickHouse...")
    with engine.connect() as conn:
        try:
            # Drop tables if exist
            print("  - Dropping existing tables...")
            conn.execute("DROP TABLE IF EXISTS test_users")
            conn.execute("DROP TABLE IF EXISTS test_products")

            # Create tables
            print("  - Creating test_users...")
            conn.execute(user_ddl)

            print("  - Creating test_products...")
            conn.execute(product_ddl)

            print("✓ Tables created successfully")

            # Verify tables exist
            print("\n4. Verifying tables...")
            result = conn.query("SHOW TABLES LIKE 'test_%'")
            tables = [row[0] for row in result.result_rows]
            print(f"  Found tables: {tables}")

            if "test_users" in tables and "test_products" in tables:
                print("✓ All tables verified")
            else:
                print("✗ Some tables missing!")
                return

            # Check table structure
            print("\n5. Checking table structures...")

            print("\n  test_users columns:")
            result = conn.query("DESCRIBE TABLE test_users")
            for row in result.result_rows:
                print(f"    {row[0]}: {row[1]}")

            print("\n  test_products columns:")
            result = conn.query("DESCRIBE TABLE test_products")
            for row in result.result_rows:
                print(f"    {row[0]}: {row[1]}")

            print("\n✓ DDL verification complete!")

            # Cleanup
            print("\n6. Cleaning up...")
            conn.execute("DROP TABLE IF EXISTS test_users")
            conn.execute("DROP TABLE IF EXISTS test_products")
            print("✓ Cleanup complete")

        except Exception as e:
            print(f"\n✗ Error: {e}")
            raise

    print("\n" + "=" * 60)
    print("Integration test completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
