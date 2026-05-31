"""
Column Compression Codecs Demo
==============================

This example demonstrates how to use ClickHouse Connect compression codecs
to optimize storage efficiency.

Key Concepts:
- Specifying codecs on Columns
- ZSTD, LZ4Int, Delta, DoubleDelta, Gorilla codecs
- Chaining codecs (e.g., Delta -> ZSTD)

Run: python examples/codecs_demo.py
"""

from chorm import Column, MergeTree, MetaData, Session, Table, create_engine
from chorm.codecs import LZ4, ZSTD, Delta, DoubleDelta, Gorilla
from chorm.types import Float64, String, UInt64

metadata = MetaData()

class SensorData(Table):
    metadata = metadata
    __tablename__ = "demo_sensor_data"
    __engine__ = MergeTree()

    # Time series often benefit from DoubleDelta + ZSTD
    timestamp = Column(
        UInt64(),
        primary_key=True,
        codec=DoubleDelta() | ZSTD(1)
    )

    # Monotonic IDs compress well with Delta
    reading_id = Column(
        UInt64(),
        codec=Delta(4) | LZ4()
    )

    # Floating point data optimized with Gorilla
    temperature = Column(
        Float64(),
        codec=Gorilla() | ZSTD(1)
    )

    # Raw strings with minimal compression for speed
    location = Column(
        String(),
        codec=LZ4()
    )


def main():
    print("Compression Codecs Demo")
    print("=======================")

    try:
        engine = create_engine("clickhouse://localhost:8123/default")

        print("1. Creating table with codecs...")
        metadata.create_all(engine)

        print("   DDL Generated:")
        # We can inspect the DDL via format_ddl or just check the table creation
        # Here we simulate showing the DDL structure:
        print(f"   CREATE TABLE {SensorData.__tablename__} (")
        print("     timestamp UInt64 CODEC(DoubleDelta, ZSTD(1)),")
        print("     reading_id UInt64 CODEC(Delta(4), LZ4),")
        print("     temperature Float64 CODEC(Gorilla, ZSTD(1)),")
        print("     location String CODEC(LZ4)")
        print("   ) ENGINE = MergeTree ...")

        print("\n2. Inserting sample data...")
        session = Session(engine)

        # Insert some data
        import time
        base_time = int(time.time() * 1000)

        for i in range(100):
            session.add(SensorData(
                timestamp=base_time + i * 1000,
                reading_id=i,
                temperature=20.0 + (i % 10) * 0.5,
                location="Room A"
            ))
        session.commit()
        print("   ✓ Inserted 100 rows")

        session.close()
    except Exception as e:
        print(f"Skipping demo (ClickHouse connection failed): {e}")
        print("Note: This demo requires a running ClickHouse instance.")


if __name__ == "__main__":
    main()
