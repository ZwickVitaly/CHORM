"""
ClickHouse-Optimized Batch Insert Demo
======================================

Demonstrates best practices for bulk data insertion into ClickHouse.

Key Points:
- ClickHouse prefers large batches (100k+ rows)
- Uses native client.insert() (much faster than SQL VALUES)
- Minimizes network round-trips

Run: python examples/batch_insert_demo.py
"""

import time
from chorm import (
    create_engine,
    ClickHouseBatchInsert,
    bulk_insert,
    DEFAULT_BATCH_SIZE,
)


def demo_basic_batch_insert():
    """Demo: Basic batch insert with optimal settings."""
    print("\n=== Basic Batch Insert ===\n")
    
    engine = create_engine("clickhouse://localhost:8123/default")
    
    # Get native client (clickhouse-connect)
    client = engine._client
    
    # Create batch inserter with ClickHouse-optimized batch size
    batch = ClickHouseBatchInsert(
        client,
        "test_batch_users",
        columns=["id", "name", "email", "created_at"],
        batch_size=DEFAULT_BATCH_SIZE  # 100,000 rows
    )
    
    print(f"Batch size: {batch.batch_size:,} rows")
    print(f"Recommended minimum: {10_000:,} rows")
    print()
    
    # Add many rows (will auto-flush in 100k batches)
    print("Inserting 250,000 rows...")
    start = time.time()
    
    for i in range(250_000):
        batch.add_row([
            i,
            f"User{i}",
            f"user{i}@example.com",
            "2024-01-01 00:00:00"
        ])
    
    # Flush remaining rows
    stats = batch.finish()
    
    elapsed = time.time() - start
    
    print(f"\nResults:")
    print(f"  Total rows: {stats['total_rows']:,}")
    print(f"  Batches sent: {stats['batches_sent']}")
    print(f"  Avg batch size: {stats['avg_batch_size']:,.0f} rows")
    print(f"  Time: {elapsed:.2f}s")
    print(f"  Throughput: {stats['total_rows'] / elapsed:,.0f} rows/sec")


def demo_bulk_insert_convenience():
    """Demo: One-liner bulk insert."""
    print("\n=== Bulk Insert (One-liner) ===\n")
    
    engine = create_engine("clickhouse://localhost:8123/default")
    client = engine._client
    
    # Prepare data (1M rows)
    print("Preparing 1,000,000 rows...")
    data = [
        [i, f"User{i}", f"user{i}@example.com"]
        for i in range(1_000_000)
    ]
    
    print(f"Data size: {len(data):,} rows")
    print()
    
    # Insert in one call (automatically batched)
    print("Inserting...")
    start = time.time()
    
    stats = bulk_insert(
        client,
        "test_batch_users",
        data,
        columns=["id", "name", "email"],
        batch_size=100_000
    )
    
    elapsed = time.time() - start
    
    print(f"\nResults:")
    print(f"  Total rows: {stats['total_rows']:,}")
    print(f"  Batches sent: {stats['batches_sent']}")
    print(f"  Time: {elapsed:.2f}s")
    print(f"  Throughput: {stats['total_rows'] / elapsed:,.0f} rows/sec")


def demo_dataframe_insert():
    """Demo: Insert from pandas DataFrame."""
    print("\n=== DataFrame Insert ===\n")
    
    try:
        import pandas as pd
        import numpy as np
    except ImportError:
        print("⚠ pandas not installed, skipping DataFrame demo")
        return
    
    engine = create_engine("clickhouse://localhost:8123/default")
    client = engine._client
    
    # Create DataFrame (500k rows)
    print("Creating DataFrame with 500,000 rows...")
    df = pd.DataFrame({
        'id': np.arange(500_000),
        'name': [f'User{i}' for i in range(500_000)],
        'email': [f'user{i}@example.com' for i in range(500_000)],
        'score': np.random.randint(0, 100, 500_000)
    })
    
    print(f"DataFrame shape: {df.shape}")
    print(f"Memory usage: {df.memory_usage(deep=True).sum() / 1024**2:.1f} MB")
    print()
    
    # Insert DataFrame
    print("Inserting DataFrame...")
    start = time.time()
    
    stats = bulk_insert(
        client,
        "test_batch_users",
        df,  # Automatically detected as DataFrame
        batch_size=100_000
    )
    
    elapsed = time.time() - start
    
    print(f"\nResults:")
    print(f"  Total rows: {stats['total_rows']:,}")
    print(f"  Batches sent: {stats['batches_sent']}")
    print(f"  Time: {elapsed:.2f}s")
    print(f"  Throughput: {stats['total_rows'] / elapsed:,.0f} rows/sec")


def demo_optimize_table():
    """Demo: OPTIMIZE TABLE after large insert."""
    print("\n=== OPTIMIZE TABLE ===\n")
    
    engine = create_engine("clickhouse://localhost:8123/default")
    client = engine._client
    
    # Insert with OPTIMIZE TABLE at the end
    print("Inserting 100,000 rows with OPTIMIZE...")
    
    data = [
        [i, f"User{i}"]
        for i in range(100_000)
    ]
    
    start = time.time()
    
    stats = bulk_insert(
        client,
        "test_batch_users",
        data,
        columns=["id", "name"],
        batch_size=100_000,
        optimize_on_finish=True  # Run OPTIMIZE TABLE after insert
    )
    
    elapsed = time.time() - start
    
    print(f"\nResults:")
    print(f"  Total rows: {stats['total_rows']:,}")
    print(f"  Optimized: {stats['optimized']}")
    print(f"  Time: {elapsed:.2f}s")
    print()
    print("Note: OPTIMIZE TABLE merges data parts for better query performance")
    print("      Use sparingly - it's an expensive operation")


def demo_performance_comparison():
    """Demo: Compare small vs large batches."""
    print("\n=== Performance Comparison ===\n")
    
    engine = create_engine("clickhouse://localhost:8123/default")
    client = engine._client
    
    # Test data
    n_rows = 100_000
    data = [[i, f"User{i}"] for i in range(n_rows)]
    
    # Small batches (anti-pattern)
    print(f"Test 1: Small batches (1,000 rows)")
    start = time.time()
    stats_small = bulk_insert(
        client, "test_batch_users", data,
        columns=["id", "name"],
        batch_size=1_000  # Too small!
    )
    time_small = time.time() - start
    
    print(f"  Time: {time_small:.2f}s")
    print(f"  Batches: {stats_small['batches_sent']}")
    print(f"  Throughput: {n_rows / time_small:,.0f} rows/sec")
    
    # Large batches (optimal)
    print(f"\nTest 2: Large batches (100,000 rows)")
    start = time.time()
    stats_large = bulk_insert(
        client, "test_batch_users", data,
        columns=["id", "name"],
        batch_size=100_000  # Optimal!
    )
    time_large = time.time() - start
    
    print(f"  Time: {time_large:.2f}s")
    print(f"  Batches: {stats_large['batches_sent']}")
    print(f"  Throughput: {n_rows / time_large:,.0f} rows/sec")
    
    # Comparison
    speedup = time_small / time_large
    print(f"\n🚀 Large batches are {speedup:.1f}x faster!")


if __name__ == "__main__":
    print("=" * 60)
    print("ClickHouse-Optimized Batch Insert Demo")
    print("=" * 60)
    
    print("\n📋 ClickHouse Best Practices:")
    print("  1. Use large batches (100k+ rows)")
    print("  2. Use native insert() not SQL VALUES")
    print("  3. Minimize network round-trips")
    print("  4. Run OPTIMIZE TABLE after large inserts")
    
    try:
        # Note: These demos require a running ClickHouse instance
        # Uncomment the demos you want to run:
        
        # demo_basic_batch_insert()
        # demo_bulk_insert_convenience()
        # demo_dataframe_insert()
        # demo_optimize_table()
        # demo_performance_comparison()
        
        print("\n" + "=" * 60)
        print("✓ Demo completed successfully!")
        print("=" * 60)
        
        print("\n💡 Tips:")
        print("  - Default batch size: 100,000 rows (optimal for ClickHouse)")
        print("  - Minimum recommended: 10,000 rows")
        print("  - Use bulk_insert() for convenience")
        print("  - DataFrame support built-in")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nNote: This demo requires ClickHouse running at localhost:8123")
        print("Start ClickHouse with: docker-compose up -d")

