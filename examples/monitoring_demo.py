"""
Monitoring and Observability Demo
==================================

Demonstrates CHORM's monitoring features:
- Query execution metrics
- Slow query logging
- Connection pool statistics
- Health checks

Run: python examples/monitoring_demo.py
"""

import time
import logging
from chorm import (
    create_engine,
    Session,
    select,
    MetricsCollector,
    HealthCheck,
    enable_global_metrics,
)

# Configure logging to see slow queries
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def demo_query_metrics():
    """Demo: Query execution metrics."""
    print("\n=== Query Execution Metrics ===\n")
    
    engine = create_engine("clickhouse://localhost:8123/default")
    
    # Create metrics collector
    collector = MetricsCollector(
        slow_query_threshold_ms=100.0,  # Queries >100ms are "slow"
        log_all_queries=False
    )
    
    # Execute queries with metrics
    with collector.measure("SELECT 1", tag="simple"):
        time.sleep(0.05)  # Simulate fast query
    
    with collector.measure("SELECT * FROM system.tables", tag="metadata"):
        time.sleep(0.15)  # Simulate slow query
    
    try:
        with collector.measure("SELECT * FROM nonexistent", tag="error"):
            raise Exception("Table not found")
    except Exception:
        pass
    
    # Get summary statistics
    summary = collector.get_summary()
    print(f"Total queries: {summary['total_queries']}")
    print(f"Successful: {summary['successful_queries']}")
    print(f"Failed: {summary['failed_queries']}")
    print(f"Average duration: {summary['avg_duration_ms']:.2f}ms")
    print(f"Slow queries: {summary['slow_queries']}")
    
    # Get slow queries
    slow_queries = collector.get_slow_queries()
    print(f"\nSlow queries (>{collector.slow_query_threshold_ms}ms):")
    for metrics in slow_queries:
        print(f"  - {metrics.sql[:50]} ({metrics.duration_ms:.2f}ms)")
    
    # Get percentiles
    percentiles = collector.get_percentiles([50, 90, 95, 99])
    print(f"\nPercentiles:")
    for p, duration in percentiles.items():
        print(f"  {p}: {duration:.2f}ms")


def demo_connection_pool_statistics():
    """Demo: Connection pool statistics."""
    print("\n=== Connection Pool Statistics ===\n")
    
    # Create engine with pooling
    engine = create_engine(
        "clickhouse://localhost:8123/default",
        pool_size=5,
        max_overflow=3
    )
    
    print("Initial pool state:")
    stats = engine.pool.get_statistics()
    print(f"  Pool size: {stats['pool_size']}")
    print(f"  Current size: {stats['current_size']}")
    print(f"  Connections in use: {stats['connections_in_use']}")
    print(f"  Utilization: {stats['utilization_percent']}%")
    
    # Acquire some connections
    print("\nAcquiring 3 connections...")
    conn1 = engine.pool.get()
    conn2 = engine.pool.get()
    conn3 = engine.pool.get()
    
    stats = engine.pool.get_statistics()
    print(f"  Pool size: {stats['pool_size']}")
    print(f"  Current size: {stats['current_size']}")
    print(f"  Connections in use: {stats['connections_in_use']}")
    print(f"  Utilization: {stats['utilization_percent']}%")
    
    # Return connections
    print("\nReturning connections...")
    engine.pool.return_connection(conn1)
    engine.pool.return_connection(conn2)
    engine.pool.return_connection(conn3)
    
    stats = engine.pool.get_statistics()
    print(f"  Pool size: {stats['pool_size']}")
    print(f"  Current size: {stats['current_size']}")
    print(f"  Connections in use: {stats['connections_in_use']}")
    print(f"  Utilization: {stats['utilization_percent']}%")
    
    # Cleanup
    engine.pool.close_all()


def demo_health_checks():
    """Demo: Health checks."""
    print("\n=== Health Checks ===\n")
    
    engine = create_engine("clickhouse://localhost:8123/default")
    health = HealthCheck(engine)
    
    # Quick ping
    print("Pinging ClickHouse...")
    if health.ping(timeout=3.0):
        print("✓ ClickHouse is reachable")
    else:
        print("✗ ClickHouse is not reachable")
        return
    
    # Get detailed status
    print("\nDetailed status:")
    status = health.get_status()
    print(f"  Status: {status['status']}")
    print(f"  Latency: {status['latency_ms']}ms")
    print(f"  Version: {status['version']}")
    print(f"  Uptime: {status['uptime_seconds']}s")
    print(f"  Host: {status['host']}:{status['port']}")
    print(f"  Database: {status['database']}")
    
    # Get server info
    print("\nServer information:")
    info = health.get_server_info()
    print(f"  Version: {info.get('version', 'N/A')}")
    print(f"  Uptime: {info.get('uptime_seconds', 'N/A')}s")
    print(f"  Database: {info.get('current_database', 'N/A')}")
    print(f"  Memory: {info.get('used_memory', 'N/A')} / {info.get('total_memory', 'N/A')}")


def demo_global_metrics():
    """Demo: Global metrics collection."""
    print("\n=== Global Metrics Collection ===\n")
    
    # Enable global metrics
    collector = enable_global_metrics(
        slow_query_threshold_ms=100.0,
        log_all_queries=True  # Log all queries
    )
    
    print("Global metrics enabled (logging all queries)")
    
    # Execute some queries
    with collector.measure("SELECT 1"):
        time.sleep(0.02)
    
    with collector.measure("SELECT count() FROM system.tables"):
        time.sleep(0.05)
    
    # Get summary
    summary = collector.get_summary()
    print(f"\nMetrics summary:")
    print(f"  Total queries: {summary['total_queries']}")
    print(f"  Average duration: {summary['avg_duration_ms']:.2f}ms")
    print(f"  Min/Max: {summary['min_duration_ms']:.2f}ms / {summary['max_duration_ms']:.2f}ms")


def demo_combined_monitoring():
    """Demo: Combined monitoring with pooling, metrics, and health."""
    print("\n=== Combined Monitoring ===\n")
    
    # Create engine with pooling
    engine = create_engine(
        "clickhouse://localhost:8123/default",
        pool_size=3,
        max_overflow=2
    )
    
    # Setup metrics and health
    collector = MetricsCollector(slow_query_threshold_ms=100.0)
    health = HealthCheck(engine)
    
    # Check health
    if not health.ping():
        print("✗ ClickHouse is not available")
        return
    
    print("✓ ClickHouse is healthy")
    
    # Execute queries with metrics and pooling
    print("\nExecuting queries with pooling and metrics...")
    for i in range(5):
        with collector.measure(f"SELECT {i}") as metrics:
            with engine.connection() as conn:
                result = conn.query(f"SELECT {i}")
    
    # Show pool statistics
    pool_stats = engine.pool.get_statistics()
    print(f"\nPool statistics:")
    print(f"  Connections in use: {pool_stats['connections_in_use']}")
    print(f"  Pool utilization: {pool_stats['utilization_percent']}%")
    
    # Show query metrics
    metrics_summary = collector.get_summary()
    print(f"\nQuery metrics:")
    print(f"  Total queries: {metrics_summary['total_queries']}")
    print(f"  Average duration: {metrics_summary['avg_duration_ms']:.2f}ms")
    print(f"  Slow queries: {metrics_summary['slow_queries']}")
    
    # Cleanup
    engine.pool.close_all()


if __name__ == "__main__":
    print("=" * 60)
    print("CHORM Monitoring & Observability Demo")
    print("=" * 60)
    
    try:
        demo_query_metrics()
        demo_connection_pool_statistics()
        demo_health_checks()
        demo_global_metrics()
        demo_combined_monitoring()
        
        print("\n" + "=" * 60)
        print("Demo completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nNote: This demo requires ClickHouse running at localhost:8123")
        print("Start ClickHouse with: docker-compose up -d")

