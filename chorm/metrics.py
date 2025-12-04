"""Query execution metrics and monitoring."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class QueryMetrics:
    """Metrics for a single query execution.

    Attributes:
        sql: SQL query text (truncated to 500 chars)
        started_at: Query start timestamp
        duration_ms: Execution time in milliseconds
        rows_read: Number of rows read (if available)
        bytes_read: Number of bytes read (if available)
        success: Whether query succeeded
        error: Error message if query failed
        metadata: Additional metadata (tags, context, etc.)
    """

    sql: str
    started_at: datetime
    duration_ms: float
    rows_read: Optional[int] = None
    bytes_read: Optional[int] = None
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary.

        Returns:
            Dictionary representation of metrics
        """
        return {
            "sql": self.sql[:500],  # Truncate long queries
            "started_at": self.started_at.isoformat(),
            "duration_ms": self.duration_ms,
            "rows_read": self.rows_read,
            "bytes_read": self.bytes_read,
            "success": self.success,
            "error": self.error,
            **self.metadata,
        }

    def is_slow(self, threshold_ms: float) -> bool:
        """Check if query is slow based on threshold.

        Args:
            threshold_ms: Threshold in milliseconds

        Returns:
            True if query duration exceeds threshold
        """
        return self.duration_ms > threshold_ms


class MetricsCollector:
    """Collects and manages query execution metrics.

    Provides utilities for measuring query performance, logging slow queries,
    and gathering statistics.

    Args:
        enabled: Enable metrics collection (default: True)
        slow_query_threshold_ms: Threshold for slow query logging (default: 1000ms)
        log_all_queries: Log all queries regardless of speed (default: False)
        max_stored_metrics: Maximum number of metrics to store in memory (default: 1000)

    Example:
        >>> collector = MetricsCollector(slow_query_threshold_ms=500)
        >>> with collector.measure("SELECT * FROM users") as metrics:
        ...     result = execute_query()
        >>> summary = collector.get_summary()
        >>> print(f"Avg duration: {summary['avg_duration_ms']}ms")
    """

    def __init__(
        self,
        enabled: bool = True,
        slow_query_threshold_ms: float = 1000.0,
        log_all_queries: bool = False,
        max_stored_metrics: int = 1000,
    ):
        self.enabled = enabled
        self.slow_query_threshold_ms = slow_query_threshold_ms
        self.log_all_queries = log_all_queries
        self.max_stored_metrics = max_stored_metrics
        self._metrics: List[QueryMetrics] = []
        self._total_queries = 0
        self._total_duration_ms = 0.0

    @contextmanager
    def measure(self, sql: str, **metadata: Any):
        """Context manager to measure query execution.

        Args:
            sql: SQL query text
            **metadata: Additional metadata to attach

        Yields:
            QueryMetrics object (populated after execution)

        Example:
            >>> with collector.measure("SELECT 1", tag="test") as metrics:
            ...     result = execute_query()
            >>> print(f"Duration: {metrics.duration_ms}ms")
        """
        if not self.enabled:
            yield None
            return

        started_at = datetime.now()
        start_time = time.time()
        metrics = None

        try:
            yield metrics
            duration_ms = (time.time() - start_time) * 1000

            metrics = QueryMetrics(
                sql=sql, started_at=started_at, duration_ms=duration_ms, success=True, metadata=metadata
            )

            self._record_metrics(metrics)

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000

            metrics = QueryMetrics(
                sql=sql, started_at=started_at, duration_ms=duration_ms, success=False, error=str(e), metadata=metadata
            )

            self._record_metrics(metrics)
            raise

    def _record_metrics(self, metrics: QueryMetrics) -> None:
        """Record metrics and log if necessary.

        Args:
            metrics: QueryMetrics object to record
        """
        # Update totals
        self._total_queries += 1
        self._total_duration_ms += metrics.duration_ms

        # Store metrics (with size limit)
        if len(self._metrics) >= self.max_stored_metrics:
            # Remove oldest metrics
            self._metrics.pop(0)
        self._metrics.append(metrics)

        # Log slow queries
        if metrics.is_slow(self.slow_query_threshold_ms):
            logger.warning(f"Slow query detected ({metrics.duration_ms:.2f}ms): " f"{metrics.sql[:100]}...")

        # Log all queries if enabled
        if self.log_all_queries:
            status = "✓" if metrics.success else "✗"
            logger.info(f"Query {status} ({metrics.duration_ms:.2f}ms): " f"{metrics.sql[:100]}...")

    def record_query(
        self, sql: str, duration_ms: float, success: bool = True, error: Optional[str] = None, **metadata: Any
    ) -> None:
        """Manually record query metrics.

        Args:
            sql: SQL query text
            duration_ms: Execution duration in milliseconds
            success: Whether query succeeded
            error: Error message if failed
            **metadata: Additional metadata
        """
        if not self.enabled:
            return

        metrics = QueryMetrics(
            sql=sql, started_at=datetime.now(), duration_ms=duration_ms, success=success, error=error, metadata=metadata
        )

        self._record_metrics(metrics)

    def get_metrics(self, limit: Optional[int] = None) -> List[QueryMetrics]:
        """Get stored metrics.

        Args:
            limit: Maximum number of metrics to return (most recent)

        Returns:
            List of QueryMetrics objects
        """
        if limit is None:
            return self._metrics.copy()
        return self._metrics[-limit:]

    def get_slow_queries(self, threshold_ms: Optional[float] = None) -> List[QueryMetrics]:
        """Get slow queries.

        Args:
            threshold_ms: Threshold in milliseconds (uses default if None)

        Returns:
            List of slow QueryMetrics
        """
        threshold = threshold_ms or self.slow_query_threshold_ms
        return [m for m in self._metrics if m.is_slow(threshold)]

    def get_failed_queries(self) -> List[QueryMetrics]:
        """Get failed queries.

        Returns:
            List of failed QueryMetrics
        """
        return [m for m in self._metrics if not m.success]

    def clear(self) -> None:
        """Clear stored metrics."""
        self._metrics.clear()
        self._total_queries = 0
        self._total_duration_ms = 0.0

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics.

        Returns:
            Dictionary with summary statistics:
            - total_queries: Total number of queries
            - successful_queries: Number of successful queries
            - failed_queries: Number of failed queries
            - avg_duration_ms: Average query duration
            - min_duration_ms: Minimum query duration
            - max_duration_ms: Maximum query duration
            - slow_queries: Number of slow queries
            - total_duration_ms: Total execution time
        """
        if not self._metrics:
            return {
                "total_queries": self._total_queries,
                "successful_queries": 0,
                "failed_queries": 0,
                "avg_duration_ms": 0.0,
                "min_duration_ms": 0.0,
                "max_duration_ms": 0.0,
                "slow_queries": 0,
                "total_duration_ms": self._total_duration_ms,
            }

        successful = [m for m in self._metrics if m.success]
        failed = [m for m in self._metrics if not m.success]
        slow = [m for m in self._metrics if m.is_slow(self.slow_query_threshold_ms)]

        durations = [m.duration_ms for m in self._metrics]

        return {
            "total_queries": self._total_queries,
            "successful_queries": len(successful),
            "failed_queries": len(failed),
            "avg_duration_ms": sum(durations) / len(durations),
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
            "slow_queries": len(slow),
            "total_duration_ms": self._total_duration_ms,
        }

    def get_percentiles(self, percentiles: List[int] = [50, 90, 95, 99]) -> Dict[str, float]:
        """Get query duration percentiles.

        Args:
            percentiles: List of percentiles to calculate (default: [50, 90, 95, 99])

        Returns:
            Dictionary mapping percentile to duration in milliseconds
        """
        if not self._metrics:
            return {f"p{p}": 0.0 for p in percentiles}

        sorted_durations = sorted(m.duration_ms for m in self._metrics)
        n = len(sorted_durations)

        result = {}
        for p in percentiles:
            idx = int(n * p / 100)
            if idx >= n:
                idx = n - 1
            result[f"p{p}"] = sorted_durations[idx]

        return result


# Global metrics collector instance (optional)
_global_collector: Optional[MetricsCollector] = None


def get_global_collector() -> Optional[MetricsCollector]:
    """Get global metrics collector instance.

    Returns:
        Global MetricsCollector or None if not initialized
    """
    return _global_collector


def set_global_collector(collector: Optional[MetricsCollector]) -> None:
    """Set global metrics collector instance.

    Args:
        collector: MetricsCollector instance or None to disable
    """
    global _global_collector
    _global_collector = collector


def enable_global_metrics(slow_query_threshold_ms: float = 1000.0, log_all_queries: bool = False) -> MetricsCollector:
    """Enable global metrics collection.

    Args:
        slow_query_threshold_ms: Threshold for slow query logging
        log_all_queries: Log all queries

    Returns:
        Global MetricsCollector instance

    Example:
        >>> collector = enable_global_metrics(slow_query_threshold_ms=500)
        >>> # Metrics are now collected globally
        >>> summary = collector.get_summary()
    """
    collector = MetricsCollector(
        enabled=True, slow_query_threshold_ms=slow_query_threshold_ms, log_all_queries=log_all_queries
    )
    set_global_collector(collector)
    return collector


def disable_global_metrics() -> None:
    """Disable global metrics collection."""
    set_global_collector(None)


# Public API
__all__ = [
    "QueryMetrics",
    "MetricsCollector",
    "get_global_collector",
    "set_global_collector",
    "enable_global_metrics",
    "disable_global_metrics",
]
