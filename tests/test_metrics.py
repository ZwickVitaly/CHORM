"""Tests for query execution metrics."""

import time
from datetime import datetime

import pytest

from chorm.metrics import (
    MetricsCollector,
    QueryMetrics,
    enable_global_metrics,
    disable_global_metrics,
    get_global_collector,
)


class TestQueryMetrics:
    """Test QueryMetrics dataclass."""

    def test_query_metrics_creation(self):
        """Test creating QueryMetrics."""
        metrics = QueryMetrics(
            sql="SELECT * FROM users", started_at=datetime.now(), duration_ms=123.45, rows_read=100, success=True
        )

        assert metrics.sql == "SELECT * FROM users"
        assert metrics.duration_ms == 123.45
        assert metrics.rows_read == 100
        assert metrics.success is True
        assert metrics.error is None

    def test_to_dict(self):
        """Test converting metrics to dictionary."""
        metrics = QueryMetrics(
            sql="SELECT 1",
            started_at=datetime(2024, 1, 1, 12, 0, 0),
            duration_ms=50.0,
            success=True,
            metadata={"tag": "test"},
        )

        result = metrics.to_dict()

        assert result["sql"] == "SELECT 1"
        assert result["duration_ms"] == 50.0
        assert result["success"] is True
        assert result["tag"] == "test"

    def test_to_dict_truncates_long_sql(self):
        """Test that long SQL is truncated in to_dict."""
        long_sql = "SELECT * FROM table WHERE " + "x = 1 AND " * 100
        metrics = QueryMetrics(sql=long_sql, started_at=datetime.now(), duration_ms=100.0)

        result = metrics.to_dict()

        assert len(result["sql"]) == 500
        assert result["sql"] == long_sql[:500]

    def test_is_slow(self):
        """Test slow query detection."""
        fast_metrics = QueryMetrics(sql="SELECT 1", started_at=datetime.now(), duration_ms=50.0)

        slow_metrics = QueryMetrics(sql="SELECT * FROM huge_table", started_at=datetime.now(), duration_ms=1500.0)

        assert fast_metrics.is_slow(1000.0) is False
        assert slow_metrics.is_slow(1000.0) is True
        assert slow_metrics.is_slow(2000.0) is False


class TestMetricsCollector:
    """Test MetricsCollector class."""

    def test_collector_initialization(self):
        """Test collector initialization with default values."""
        collector = MetricsCollector()

        assert collector.enabled is True
        assert collector.slow_query_threshold_ms == 1000.0
        assert collector.log_all_queries is False
        assert len(collector.get_metrics()) == 0

    def test_collector_custom_config(self):
        """Test collector with custom configuration."""
        collector = MetricsCollector(
            enabled=False, slow_query_threshold_ms=500.0, log_all_queries=True, max_stored_metrics=100
        )

        assert collector.enabled is False
        assert collector.slow_query_threshold_ms == 500.0
        assert collector.log_all_queries is True
        assert collector.max_stored_metrics == 100

    def test_measure_context_manager_success(self):
        """Test measuring successful query execution."""
        collector = MetricsCollector()

        with collector.measure("SELECT 1") as metrics:
            time.sleep(0.01)  # Simulate query execution

        stored_metrics = collector.get_metrics()
        assert len(stored_metrics) == 1
        assert stored_metrics[0].sql == "SELECT 1"
        assert stored_metrics[0].duration_ms >= 10  # At least 10ms
        assert stored_metrics[0].success is True

    def test_measure_context_manager_failure(self):
        """Test measuring failed query execution."""
        collector = MetricsCollector()

        with pytest.raises(ValueError):
            with collector.measure("SELECT * FROM invalid"):
                raise ValueError("Query failed")

        stored_metrics = collector.get_metrics()
        assert len(stored_metrics) == 1
        assert stored_metrics[0].success is False
        assert stored_metrics[0].error == "Query failed"

    def test_measure_disabled_collector(self):
        """Test that disabled collector doesn't record metrics."""
        collector = MetricsCollector(enabled=False)

        with collector.measure("SELECT 1"):
            time.sleep(0.01)

        assert len(collector.get_metrics()) == 0

    def test_record_query_manually(self):
        """Test manually recording query metrics."""
        collector = MetricsCollector()

        collector.record_query(sql="SELECT * FROM users", duration_ms=123.45, success=True, tag="manual")

        metrics = collector.get_metrics()
        assert len(metrics) == 1
        assert metrics[0].sql == "SELECT * FROM users"
        assert metrics[0].duration_ms == 123.45
        assert metrics[0].metadata["tag"] == "manual"

    def test_get_slow_queries(self):
        """Test retrieving slow queries."""
        collector = MetricsCollector(slow_query_threshold_ms=100.0)

        collector.record_query("SELECT 1", duration_ms=50.0)
        collector.record_query("SELECT 2", duration_ms=150.0)
        collector.record_query("SELECT 3", duration_ms=200.0)

        slow_queries = collector.get_slow_queries()

        assert len(slow_queries) == 2
        assert slow_queries[0].sql == "SELECT 2"
        assert slow_queries[1].sql == "SELECT 3"

    def test_get_slow_queries_custom_threshold(self):
        """Test retrieving slow queries with custom threshold."""
        collector = MetricsCollector()

        collector.record_query("SELECT 1", duration_ms=50.0)
        collector.record_query("SELECT 2", duration_ms=150.0)
        collector.record_query("SELECT 3", duration_ms=200.0)

        slow_queries = collector.get_slow_queries(threshold_ms=100.0)

        assert len(slow_queries) == 2

    def test_get_failed_queries(self):
        """Test retrieving failed queries."""
        collector = MetricsCollector()

        collector.record_query("SELECT 1", duration_ms=50.0, success=True)
        collector.record_query("SELECT 2", duration_ms=100.0, success=False, error="Error 1")
        collector.record_query("SELECT 3", duration_ms=75.0, success=False, error="Error 2")

        failed_queries = collector.get_failed_queries()

        assert len(failed_queries) == 2
        assert failed_queries[0].sql == "SELECT 2"
        assert failed_queries[1].sql == "SELECT 3"

    def test_clear_metrics(self):
        """Test clearing stored metrics."""
        collector = MetricsCollector()

        collector.record_query("SELECT 1", duration_ms=50.0)
        collector.record_query("SELECT 2", duration_ms=100.0)

        assert len(collector.get_metrics()) == 2

        collector.clear()

        assert len(collector.get_metrics()) == 0
        summary = collector.get_summary()
        assert summary["total_queries"] == 0

    def test_get_summary(self):
        """Test getting summary statistics."""
        collector = MetricsCollector(slow_query_threshold_ms=100.0)

        collector.record_query("SELECT 1", duration_ms=50.0, success=True)
        collector.record_query("SELECT 2", duration_ms=150.0, success=True)
        collector.record_query("SELECT 3", duration_ms=200.0, success=False)

        summary = collector.get_summary()

        assert summary["total_queries"] == 3
        assert summary["successful_queries"] == 2
        assert summary["failed_queries"] == 1
        assert summary["avg_duration_ms"] == 133.33333333333334
        assert summary["min_duration_ms"] == 50.0
        assert summary["max_duration_ms"] == 200.0
        assert summary["slow_queries"] == 2

    def test_get_summary_empty(self):
        """Test getting summary with no metrics."""
        collector = MetricsCollector()

        summary = collector.get_summary()

        assert summary["total_queries"] == 0
        assert summary["avg_duration_ms"] == 0.0

    def test_get_percentiles(self):
        """Test calculating query duration percentiles."""
        collector = MetricsCollector()

        # Add 100 queries with durations 1-100ms
        for i in range(1, 101):
            collector.record_query(f"SELECT {i}", duration_ms=float(i))

        percentiles = collector.get_percentiles([50, 90, 95, 99])

        assert 48 <= percentiles["p50"] <= 52  # Around 50th percentile
        assert 88 <= percentiles["p90"] <= 92  # Around 90th percentile
        assert 93 <= percentiles["p95"] <= 97  # Around 95th percentile
        assert 97 <= percentiles["p99"] <= 100  # Around 99th percentile

    def test_get_percentiles_empty(self):
        """Test percentiles with no metrics."""
        collector = MetricsCollector()

        percentiles = collector.get_percentiles()

        assert percentiles["p50"] == 0.0
        assert percentiles["p90"] == 0.0

    def test_max_stored_metrics_limit(self):
        """Test that collector respects max_stored_metrics limit."""
        collector = MetricsCollector(max_stored_metrics=5)

        # Add 10 queries
        for i in range(10):
            collector.record_query(f"SELECT {i}", duration_ms=float(i))

        metrics = collector.get_metrics()

        # Should only keep last 5
        assert len(metrics) == 5
        assert metrics[0].sql == "SELECT 5"
        assert metrics[4].sql == "SELECT 9"

        # Total queries should still be 10
        summary = collector.get_summary()
        assert summary["total_queries"] == 10

    def test_get_metrics_with_limit(self):
        """Test getting limited number of recent metrics."""
        collector = MetricsCollector()

        for i in range(10):
            collector.record_query(f"SELECT {i}", duration_ms=float(i))

        recent = collector.get_metrics(limit=3)

        assert len(recent) == 3
        assert recent[0].sql == "SELECT 7"
        assert recent[2].sql == "SELECT 9"


class TestGlobalCollector:
    """Test global metrics collector."""

    def teardown_method(self):
        """Clean up after each test."""
        disable_global_metrics()

    def test_enable_global_metrics(self):
        """Test enabling global metrics."""
        collector = enable_global_metrics(slow_query_threshold_ms=500.0)

        assert collector is not None
        assert collector.slow_query_threshold_ms == 500.0
        assert get_global_collector() is collector

    def test_disable_global_metrics(self):
        """Test disabling global metrics."""
        enable_global_metrics()
        assert get_global_collector() is not None

        disable_global_metrics()
        assert get_global_collector() is None

    def test_get_global_collector_default(self):
        """Test getting global collector when not initialized."""
        assert get_global_collector() is None
