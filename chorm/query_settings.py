"""ClickHouse query settings and optimization helpers.

Provides convenient presets and utilities for query optimization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class QuerySettings:
    """ClickHouse query settings.

    Provides a convenient way to manage query-level settings.

    Common Settings:
        - max_threads: Maximum threads for query execution
        - max_memory_usage: Memory limit for query
        - max_execution_time: Query timeout in seconds
        - max_rows_to_read: Maximum rows to read
        - readonly: Enable read-only mode
        - extremes: Calculate extreme values
        - use_query_cache: Enable query result cache

    Example:
        >>> settings = QuerySettings(
        ...     max_threads=4,
        ...     max_memory_usage=10_000_000_000,  # 10GB
        ...     max_execution_time=300  # 5 minutes
        ... )
        >>> sql = f"SELECT * FROM users SETTINGS {settings}"
    """

    # Performance settings
    max_threads: Optional[int] = None
    max_memory_usage: Optional[int] = None
    max_execution_time: Optional[int] = None
    max_rows_to_read: Optional[int] = None
    max_bytes_to_read: Optional[int] = None

    # Query behavior
    readonly: Optional[int] = None  # 0=off, 1=on, 2=exception on write
    extremes: Optional[int] = None  # 0=off, 1=on
    use_query_cache: Optional[bool] = None

    # Optimization hints
    optimize_read_in_order: Optional[bool] = None
    optimize_aggregation_in_order: Optional[bool] = None
    max_rows_to_group_by: Optional[int] = None
    group_by_overflow_mode: Optional[str] = None  # 'throw', 'break', 'any'

    # Custom settings
    custom: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary.

        Returns:
            Dictionary of non-None settings
        """
        result = {}

        # Standard settings
        if self.max_threads is not None:
            result["max_threads"] = self.max_threads
        if self.max_memory_usage is not None:
            result["max_memory_usage"] = self.max_memory_usage
        if self.max_execution_time is not None:
            result["max_execution_time"] = self.max_execution_time
        if self.max_rows_to_read is not None:
            result["max_rows_to_read"] = self.max_rows_to_read
        if self.max_bytes_to_read is not None:
            result["max_bytes_to_read"] = self.max_bytes_to_read

        if self.readonly is not None:
            result["readonly"] = self.readonly
        if self.extremes is not None:
            result["extremes"] = self.extremes
        if self.use_query_cache is not None:
            result["use_query_cache"] = 1 if self.use_query_cache else 0

        if self.optimize_read_in_order is not None:
            result["optimize_read_in_order"] = 1 if self.optimize_read_in_order else 0
        if self.optimize_aggregation_in_order is not None:
            result["optimize_aggregation_in_order"] = 1 if self.optimize_aggregation_in_order else 0
        if self.max_rows_to_group_by is not None:
            result["max_rows_to_group_by"] = self.max_rows_to_group_by
        if self.group_by_overflow_mode is not None:
            result["group_by_overflow_mode"] = f"'{self.group_by_overflow_mode}'"

        # Add custom settings
        result.update(self.custom)

        return result

    def __str__(self) -> str:
        """Convert to SETTINGS clause string.

        Returns:
            SETTINGS clause (without 'SETTINGS' keyword)
        """
        settings_dict = self.to_dict()
        if not settings_dict:
            return ""

        parts = []
        for key, value in settings_dict.items():
            parts.append(f"{key} = {value}")

        return ", ".join(parts)


# Common presets
SETTINGS_PRESETS = {
    "fast": QuerySettings(
        max_threads=8,
        optimize_read_in_order=True,
        optimize_aggregation_in_order=True,
    ),
    "memory_efficient": QuerySettings(
        max_threads=2,
        max_memory_usage=1_000_000_000,  # 1GB
        group_by_overflow_mode="break",
    ),
    "heavy_analytics": QuerySettings(
        max_threads=16,
        max_memory_usage=50_000_000_000,  # 50GB
        max_execution_time=3600,  # 1 hour
    ),
    "interactive": QuerySettings(
        max_threads=4,
        max_memory_usage=5_000_000_000,  # 5GB
        max_execution_time=30,  # 30 seconds
        max_rows_to_read=1_000_000,
    ),
    "readonly": QuerySettings(
        readonly=1,
        max_threads=4,
        max_execution_time=60,
    ),
    "cached": QuerySettings(
        use_query_cache=True,
        max_threads=2,
    ),
}


def get_preset(name: str) -> QuerySettings:
    """Get a predefined settings preset.

    Args:
        name: Preset name (fast, memory_efficient, heavy_analytics,
              interactive, readonly, cached)

    Returns:
        QuerySettings preset

    Raises:
        KeyError: If preset name is not found

    Example:
        >>> settings = get_preset("fast")
        >>> sql = f"SELECT * FROM users SETTINGS {settings}"
    """
    if name not in SETTINGS_PRESETS:
        available = ", ".join(SETTINGS_PRESETS.keys())
        raise KeyError(f"Unknown preset '{name}'. Available presets: {available}")

    return SETTINGS_PRESETS[name]


@dataclass
class ExecutionStats:
    """Query execution statistics.

    Captures statistics from query execution for performance analysis.

    Attributes:
        elapsed_time: Query execution time in seconds
        rows_read: Number of rows read
        bytes_read: Number of bytes read
        rows_written: Number of rows written (for INSERT)
        bytes_written: Number of bytes written
        memory_usage: Peak memory usage in bytes
        extra: Additional statistics
    """

    elapsed_time: float = 0.0
    rows_read: int = 0
    bytes_read: int = 0
    rows_written: int = 0
    bytes_written: int = 0
    memory_usage: int = 0
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "elapsed_time": self.elapsed_time,
            "rows_read": self.rows_read,
            "bytes_read": self.bytes_read,
            "rows_written": self.rows_written,
            "bytes_written": self.bytes_written,
            "memory_usage": self.memory_usage,
            **self.extra,
        }

    def __str__(self) -> str:
        """Format statistics as string.

        Returns:
            Human-readable statistics
        """
        lines = [
            f"Execution time: {self.elapsed_time:.3f}s",
            f"Rows read: {self.rows_read:,}",
            f"Bytes read: {self.bytes_read:,}",
        ]

        if self.rows_written > 0:
            lines.append(f"Rows written: {self.rows_written:,}")
        if self.bytes_written > 0:
            lines.append(f"Bytes written: {self.bytes_written:,}")
        if self.memory_usage > 0:
            lines.append(f"Memory usage: {self.memory_usage:,} bytes")

        return "\n".join(lines)


class QueryOptimizer:
    """Query optimization helper.

    Provides utilities for analyzing and optimizing queries.

    Example:
        >>> optimizer = QueryOptimizer()
        >>>
        >>> # Get recommendations for a query
        >>> recommendations = optimizer.recommend_settings(
        ...     query_type="analytics",
        ...     estimated_rows=10_000_000,
        ...     complexity="high"
        ... )
    """

    def recommend_settings(
        self,
        query_type: str = "select",
        estimated_rows: Optional[int] = None,
        complexity: str = "medium",
        time_limit: Optional[int] = None,
    ) -> QuerySettings:
        """Recommend settings based on query characteristics.

        Args:
            query_type: Type of query (select, insert, analytics)
            estimated_rows: Estimated number of rows to process
            complexity: Query complexity (low, medium, high)
            time_limit: Maximum execution time in seconds

        Returns:
            Recommended QuerySettings

        Example:
            >>> settings = optimizer.recommend_settings(
            ...     query_type="analytics",
            ...     estimated_rows=100_000_000,
            ...     complexity="high",
            ...     time_limit=300
            ... )
        """
        settings = QuerySettings()

        # Set threads based on complexity
        if complexity == "low":
            settings.max_threads = 2
        elif complexity == "medium":
            settings.max_threads = 4
        else:  # high
            settings.max_threads = 8

        # Set memory limit based on estimated rows
        if estimated_rows:
            if estimated_rows < 1_000_000:
                settings.max_memory_usage = 1_000_000_000  # 1GB
            elif estimated_rows < 10_000_000:
                settings.max_memory_usage = 5_000_000_000  # 5GB
            else:
                settings.max_memory_usage = 20_000_000_000  # 20GB

        # Set time limit
        if time_limit:
            settings.max_execution_time = time_limit
        elif query_type == "analytics":
            settings.max_execution_time = 3600  # 1 hour
        else:
            settings.max_execution_time = 300  # 5 minutes

        # Enable optimizations for analytics
        if query_type == "analytics":
            settings.optimize_read_in_order = True
            settings.optimize_aggregation_in_order = True

        return settings

    def get_query_hint(self, hint_type: str) -> str:
        """Get SQL hint for query optimization.

        Args:
            hint_type: Type of hint (parallel, no_merge, final, etc.)

        Returns:
            SQL hint string

        Example:
            >>> hint = optimizer.get_query_hint("final")
            >>> sql = f"SELECT * FROM users {hint}"
        """
        hints = {
            "final": "FINAL",
            "sample": "SAMPLE 0.1",  # 10% sample
            "prewhere": "",  # Applied via WHERE conditions
            "parallel": "",  # Controlled via settings
        }

        return hints.get(hint_type, "")


# Public API
__all__ = [
    "QuerySettings",
    "ExecutionStats",
    "QueryOptimizer",
    "get_preset",
    "SETTINGS_PRESETS",
]
