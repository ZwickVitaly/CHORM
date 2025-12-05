"""Integration test for ReplacingMergeTree with partitioning."""

import os
from datetime import date
from chorm import Table, Column, create_engine, Session, select
from chorm.types import UInt64, String, Date
from chorm.table_engines import ReplacingMergeTree


class ProductStats(Table):
    __tablename__ = "product_stats"

    id = Column(UInt64(), primary_key=True)
    city = Column(String())
    date = Column(Date())
    orders = Column(UInt64())
    version = Column(UInt64())  # For ReplacingMergeTree

    engine = ReplacingMergeTree(version_column="version")
    __order_by__ = ("id", "city", "date")
    __partition_by__ = ("city", "toYYYYMM(date)")


def main():
    print("=" * 60)
    print("CHORM Integration Test - ReplacingMergeTree")
    print("=" * 60)

    # Create engine and session
    print("\n1. Connecting to ClickHouse...")
    password = os.getenv("CLICKHOUSE_PASSWORD", "123")
    engine = create_engine("clickhouse://localhost:8123/default", username="default", password=password)
    session = Session(engine)
    print("✓ Connected successfully")

    # Generate DDL
    print("\n2. Generating DDL...")
    ddl = ProductStats.create_table(exists_ok=True)
    print("\n" + ddl)

    # Create table
    print("\n3. Creating table...")
    with engine.connect() as conn:
        conn.execute("DROP TABLE IF EXISTS product_stats")
        conn.execute(ddl)
    print("✓ Table created")

    # Verify table structure
    print("\n4. Verifying table structure...")
    with engine.connect() as conn:
        result = conn.query("DESCRIBE TABLE product_stats")
        print("\n  Columns:")
        for row in result.result_rows:
            print(f"    {row[0]}: {row[1]}")

        # Check engine
        result = conn.query("SELECT engine FROM system.tables WHERE name = 'product_stats'")
        engine_type = result.result_rows[0][0]
        print(f"\n  Engine: {engine_type}")

        # Check partitions
        result = conn.query("SELECT partition_key FROM system.tables WHERE name = 'product_stats'")
        partition_key = result.result_rows[0][0]
        print(f"  Partition Key: {partition_key}")

    # Insert historical data (multiple versions)
    print("\n5. Inserting historical data...")

    # Version 1: Initial data
    stats_v1 = [
        ProductStats(id=1, city="Moscow", date=date(2024, 1, 15), orders=100, version=1),
        ProductStats(id=1, city="Moscow", date=date(2024, 1, 16), orders=120, version=1),
        ProductStats(id=1, city="SPB", date=date(2024, 1, 15), orders=80, version=1),
    ]

    for stat in stats_v1:
        session.add(stat)
    session.commit()
    print("  ✓ Inserted version 1 (3 rows)")

    # Version 2: Updated data for some rows
    stats_v2 = [
        ProductStats(id=1, city="Moscow", date=date(2024, 1, 15), orders=105, version=2),  # Updated
        ProductStats(id=1, city="Moscow", date=date(2024, 1, 17), orders=130, version=2),  # New
    ]

    for stat in stats_v2:
        session.add(stat)
    session.commit()
    print("  ✓ Inserted version 2 (2 rows)")

    # Query data before OPTIMIZE
    print("\n6. Querying data (before OPTIMIZE)...")
    stmt = select(
        ProductStats.id, ProductStats.city, ProductStats.date, ProductStats.orders, ProductStats.version
    ).order_by(ProductStats.city, ProductStats.date)

    result = session.execute(stmt)
    rows = result.all()

    print(f"\n  Total rows: {len(rows)}")
    print("  Data:")
    for row in rows:
        print(f"    {row}")

    # Optimize table to apply ReplacingMergeTree logic
    print("\n7. Optimizing table (applying ReplacingMergeTree)...")
    with engine.connect() as conn:
        conn.execute("OPTIMIZE TABLE product_stats FINAL")
    print("  ✓ Optimization complete")

    # Query data after OPTIMIZE
    print("\n8. Querying data (after OPTIMIZE)...")
    result = session.execute(stmt)
    rows = result.all()

    print(f"\n  Total rows: {len(rows)}")
    print("  Data (should show only latest versions):")
    for row in rows:
        print(f"    {row}")

    # Verify deduplication
    print("\n9. Verifying deduplication...")
    expected_rows = 4  # Moscow 15th (v2), Moscow 16th (v1), Moscow 17th (v2), SPB 15th (v1)
    if len(rows) == expected_rows:
        print(f"  ✓ Deduplication verified ({expected_rows} unique rows)")
    else:
        print(f"  ⚠ Expected {expected_rows} rows, got {len(rows)}")

    # Check partitions
    print("\n10. Checking partitions...")
    with engine.connect() as conn:
        result = conn.query(
            "SELECT partition, rows FROM system.parts "
            "WHERE table = 'product_stats' AND active = 1 "
            "ORDER BY partition"
        )
        print("\n  Active partitions:")
        for row in result.result_rows:
            print(f"    {row[0]}: {row[1]} rows")

    # Cleanup
    print("\n11. Cleaning up...")
    with engine.connect() as conn:
        conn.execute("DROP TABLE IF EXISTS product_stats")
    print("✓ Cleanup complete")

    session.close()

    print("\n" + "=" * 60)
    print("ReplacingMergeTree test completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
