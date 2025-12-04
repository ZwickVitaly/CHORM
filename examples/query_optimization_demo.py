"""
Query Optimization Demo
=======================

Demonstrates ClickHouse query optimization features:
- Query settings presets
- Performance tuning
- Execution statistics

Run: python examples/query_optimization_demo.py
"""

from chorm import (
    create_engine,
    QuerySettings,
    QueryOptimizer,
    ExecutionStats,
    get_preset,
    SETTINGS_PRESETS,
)


def demo_settings_presets():
    """Demo: Using predefined settings presets."""
    print("\n=== Settings Presets ===\n")
    
    print("Available presets:")
    for name in SETTINGS_PRESETS.keys():
        print(f"  - {name}")
    
    print("\n1. Fast preset (optimized for speed):")
    fast = get_preset("fast")
    print(f"   {fast}")
    
    print("\n2. Memory efficient preset (low memory usage):")
    memory_efficient = get_preset("memory_efficient")
    print(f"   {fast}")
    
    print("\n3. Heavy analytics preset (long-running queries):")
    heavy = get_preset("heavy_analytics")
    print(f"   {heavy}")
    
    print("\n4. Interactive preset (quick responses):")
    interactive = get_preset("interactive")
    print(f"   {interactive}")


def demo_custom_settings():
    """Demo: Creating custom settings."""
    print("\n=== Custom Settings ===\n")
    
    settings = QuerySettings(
        max_threads=8,
        max_memory_usage=10_000_000_000,  # 10GB
        max_execution_time=300,  # 5 minutes
        optimize_read_in_order=True,
        use_query_cache=True
    )
    
    print("Custom settings:")
    print(f"  SETTINGS {settings}")
    
    print("\nUsage in SQL:")
    sql = f"""
    SELECT user_id, COUNT(*) as order_count
    FROM orders
    WHERE created_at >= '2024-01-01'
    GROUP BY user_id
    SETTINGS {settings}
    """
    print(sql)


def demo_query_optimizer():
    """Demo: Using QueryOptimizer for recommendations."""
    print("\n=== Query Optimizer ===\n")
    
    optimizer = QueryOptimizer()
    
    print("1. Recommendations for interactive query:")
    settings = optimizer.recommend_settings(
        query_type="select",
        estimated_rows=100_000,
        complexity="low"
    )
    print(f"   Threads: {settings.max_threads}")
    print(f"   Memory: {settings.max_memory_usage:,} bytes")
    print(f"   Timeout: {settings.max_execution_time}s")
    
    print("\n2. Recommendations for analytics query:")
    settings = optimizer.recommend_settings(
        query_type="analytics",
        estimated_rows=100_000_000,
        complexity="high",
        time_limit=3600
    )
    print(f"   Threads: {settings.max_threads}")
    print(f"   Memory: {settings.max_memory_usage:,} bytes")
    print(f"   Timeout: {settings.max_execution_time}s")
    print(f"   Optimizations: read_in_order={settings.optimize_read_in_order}")
    
    print("\n3. Query hints:")
    final_hint = optimizer.get_query_hint("final")
    sample_hint = optimizer.get_query_hint("sample")
    print(f"   FINAL hint: {final_hint}")
    print(f"   SAMPLE hint: {sample_hint}")


def demo_execution_stats():
    """Demo: Tracking execution statistics."""
    print("\n=== Execution Statistics ===\n")
    
    # Simulated stats
    stats = ExecutionStats(
        elapsed_time=2.345,
        rows_read=1_000_000,
        bytes_read=50_000_000,
        memory_usage=100_000_000
    )
    
    print("Query execution statistics:")
    print(stats)
    
    print("\nAs dictionary:")
    print(stats.to_dict())


def demo_real_world_example():
    """Demo: Real-world optimization example."""
    print("\n=== Real-World Example ===\n")
    
    # Scenario: Heavy analytics query on large dataset
    print("Scenario: Analyzing 100M orders for monthly reports")
    print()
    
    optimizer = QueryOptimizer()
    
    # Get recommendations
    settings = optimizer.recommend_settings(
        query_type="analytics",
        estimated_rows=100_000_000,
        complexity="high",
        time_limit=1800  # 30 minutes
    )
    
    # Build optimized query
    sql = f"""
    SELECT 
        toYYYYMM(order_date) as month,
        product_category,
        SUM(amount) as total_sales,
        COUNT(DISTINCT user_id) as unique_customers
    FROM orders
    WHERE order_date >= '2023-01-01'
    GROUP BY month, product_category
    ORDER BY month DESC, total_sales DESC
    SETTINGS {settings}
    """
    
    print("Optimized SQL:")
    print(sql)
    
    print("\nSettings breakdown:")
    print(f"  • Max threads: {settings.max_threads} (parallel processing)")
    print(f"  • Memory limit: {settings.max_memory_usage / 1e9:.0f}GB (prevents OOM)")
    print(f"  • Timeout: {settings.max_execution_time / 60:.0f}min (fail-fast)")
    print(f"  • Optimizations: In-order read & aggregation (faster)")


def demo_preset_comparison():
    """Demo: Compare different presets."""
    print("\n=== Preset Comparison ===\n")
    
    presets_to_compare = ["fast", "memory_efficient", "heavy_analytics", "interactive"]
    
    print(f"{'Preset':<20} {'Threads':<10} {'Memory (GB)':<15} {'Timeout (s)':<12}")
    print("-" * 60)
    
    for name in presets_to_compare:
        preset = get_preset(name)
        threads = preset.max_threads or "N/A"
        memory = f"{preset.max_memory_usage / 1e9:.1f}" if preset.max_memory_usage else "N/A"
        timeout = preset.max_execution_time or "N/A"
        
        print(f"{name:<20} {threads:<10} {memory:<15} {timeout:<12}")


def demo_settings_in_engine():
    """Demo: Using settings with CHORM engine."""
    print("\n=== Settings with CHORM Engine ===\n")
    
    engine = create_engine("clickhouse://localhost:8123/default")
    
    # Use preset
    settings = get_preset("interactive")
    
    print("Example query with settings:")
    query_sql = f"""
    SELECT * FROM users 
    WHERE active = 1 
    LIMIT 100
    SETTINGS {settings}
    """
    print(query_sql)
    
    print("\nNote: Settings are appended to the SQL query")
    print("      ClickHouse applies them at execution time")


if __name__ == "__main__":
    print("=" * 60)
    print("Query Optimization Demo")
    print("=" * 60)
    
    try:
        demo_settings_presets()
        demo_custom_settings()
        demo_query_optimizer()
        demo_execution_stats()
        demo_real_world_example()
        demo_preset_comparison()
        demo_settings_in_engine()
        
        print("\n" + "=" * 60)
        print("✓ Demo completed successfully!")
        print("=" * 60)
        
        print("\n💡 Key Takeaways:")
        print("  1. Use presets for common scenarios (fast, memory_efficient, etc.)")
        print("  2. QueryOptimizer recommends settings based on query characteristics")
        print("  3. SETTINGS clause is appended to SQL queries")
        print("  4. ExecutionStats helps track query performance")
        print("  5. Customize settings for specific use cases")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nNote: Some examples require ClickHouse connection")

