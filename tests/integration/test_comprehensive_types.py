"""Integration test for comprehensive type coverage with MergeTree."""

import os
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID

from chorm import Table, Column, create_engine, Session, select
from chorm.types import (
    # Integers
    UInt8,
    UInt16,
    UInt32,
    UInt64,
    Int8,
    Int16,
    Int32,
    Int64,
    # Floats
    Float32,
    Float64,
    # Strings
    String,
    FixedString,
    # Dates
    Date,
    DateTime,
    # Special types
    UUID as UUIDType,
    Decimal as DecimalType,
    # Composite
    Array,
    Nullable,
    Map,
    Tuple,
)
from chorm.table_engines import MergeTree


class ComprehensiveTable(Table):
    __tablename__ = "test_comprehensive"

    # Primary key
    id = Column(UInt64(), primary_key=True)

    # Integer types
    uint8_col = Column(UInt8())
    uint16_col = Column(UInt16())
    uint32_col = Column(UInt32())
    uint64_col = Column(UInt64())
    int8_col = Column(Int8())
    int16_col = Column(Int16())
    int32_col = Column(Int32())
    int64_col = Column(Int64())

    # Float types
    float32_col = Column(Float32())
    float64_col = Column(Float64())

    # String types
    string_col = Column(String())
    fixed_string_col = Column(FixedString(10))

    # Date/Time types
    date_col = Column(Date())
    datetime_col = Column(DateTime())
    # Note: DateTime with timezone requires DateTime64 in ClickHouse
    # datetime_tz_col = Column(DateTime("UTC"))

    # Special types
    uuid_col = Column(UUIDType())
    decimal_col = Column(DecimalType(18, 2))

    # Composite types
    array_col = Column(Array(String()))
    nullable_col = Column(Nullable(String()))
    map_col = Column(Map(String(), UInt64()))
    tuple_col = Column(Tuple([String(), UInt64()]))

    engine = MergeTree()
    __order_by__ = "id"


def main():
    print("=" * 60)
    print("CHORM Integration Test - Comprehensive Type Coverage")
    print("=" * 60)

    # Create engine and session
    print("\n1. Connecting to ClickHouse...")
    password = os.getenv("CLICKHOUSE_PASSWORD", "123")
    engine = create_engine("clickhouse://localhost:8123/default", username="default", password=password)
    session = Session(engine)
    print("✓ Connected successfully")

    # Generate DDL
    print("\n2. Generating DDL...")
    ddl = ComprehensiveTable.create_table(exists_ok=True)
    print("\n" + ddl)

    # Create table
    print("\n3. Creating table...")
    with engine.connect() as conn:
        conn.execute("DROP TABLE IF EXISTS test_comprehensive")
        conn.execute(ddl)
    print("✓ Table created")

    # Verify table structure
    print("\n4. Verifying table structure...")
    with engine.connect() as conn:
        result = conn.query("DESCRIBE TABLE test_comprehensive")
        print("\n  Columns:")
        for row in result.result_rows:
            print(f"    {row[0]:<20} {row[1]}")

    # Insert test data
    print("\n5. Inserting test data...")
    test_record = ComprehensiveTable(
        id=1,
        # Integers
        uint8_col=255,
        uint16_col=65535,
        uint32_col=4294967295,
        uint64_col=18446744073709551615,
        int8_col=-128,
        int16_col=-32768,
        int32_col=-2147483648,
        int64_col=-9223372036854775808,
        # Floats
        float32_col=3.14,
        float64_col=2.718281828,
        # Strings
        string_col="Hello, ClickHouse!",
        fixed_string_col="Fixed",
        # Dates
        date_col=date(2024, 12, 2),
        datetime_col=datetime(2024, 12, 2, 1, 25, 0),
        # Special
        uuid_col=UUID("12345678-1234-5678-1234-567812345678"),
        decimal_col=Decimal("12345.67"),
        # Composite
        array_col=["tag1", "tag2", "tag3"],
        nullable_col="Not null",
        map_col={"key1": 100, "key2": 200},
        tuple_col=("value", 42),
    )

    session.add(test_record)
    session.commit()
    print("✓ Test data inserted")

    # Query and verify data
    print("\n6. Querying data...")
    stmt = select(
        ComprehensiveTable.id,
        ComprehensiveTable.datetime_col,
        ComprehensiveTable.string_col,
        ComprehensiveTable.array_col,
        ComprehensiveTable.decimal_col,
    )
    result = session.execute(stmt)
    rows = result.all()

    print(f"\n  Retrieved {len(rows)} row(s):")
    for row in rows:
        print(f"    ID: {row[0]}")
        print(f"    DateTime: {row[1]}")
        print(f"    String: {row[2]}")
        print(f"    Array: {row[3]}")
        print(f"    Decimal: {row[4]}")

    # Test DateTime specifically
    print("\n7. Testing DateTime operations...")
    with engine.connect() as conn:
        # Query raw DateTime values
        result = conn.query(
            "SELECT datetime_col, toTypeName(datetime_col), "
            "toDateTime(datetime_col, 'UTC') as datetime_utc "
            "FROM test_comprehensive WHERE id = 1"
        )
        row = result.result_rows[0]
        print(f"\n  DateTime column:")
        print(f"    Value: {row[0]}")
        print(f"    Type: {row[1]}")
        print(f"    UTC conversion: {row[2]}")

    # Test all numeric types
    print("\n8. Testing numeric types...")
    with engine.connect() as conn:
        result = conn.query(
            "SELECT uint8_col, int8_col, float32_col, float64_col, decimal_col " "FROM test_comprehensive WHERE id = 1"
        )
        row = result.result_rows[0]
        print(f"\n  UInt8: {row[0]} (max: 255)")
        print(f"  Int8: {row[1]} (min: -128)")
        print(f"  Float32: {row[2]}")
        print(f"  Float64: {row[3]}")
        print(f"  Decimal(18,2): {row[4]}")

    # Test composite types
    print("\n9. Testing composite types...")
    with engine.connect() as conn:
        result = conn.query("SELECT array_col, map_col, tuple_col " "FROM test_comprehensive WHERE id = 1")
        row = result.result_rows[0]
        print(f"\n  Array: {row[0]}")
        print(f"  Map: {row[1]}")
        print(f"  Tuple: {row[2]}")

    # Cleanup
    print("\n10. Cleaning up...")
    with engine.connect() as conn:
        conn.execute("DROP TABLE IF EXISTS test_comprehensive")
    print("✓ Cleanup complete")

    session.close()

    print("\n" + "=" * 60)
    print("Comprehensive type coverage test completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
