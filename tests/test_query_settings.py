"""Tests for query settings and optimization helpers."""

import pytest

from chorm.query_settings import (
    QuerySettings,
    ExecutionStats,
    QueryOptimizer,
    get_preset,
    SETTINGS_PRESETS,
)


class TestQuerySettings:
    """Test QuerySettings class."""

    def test_default_initialization(self):
        """Test creating QuerySettings with defaults."""
        settings = QuerySettings()

        assert settings.max_threads is None
        assert settings.max_memory_usage is None
        assert settings.readonly is None

    def test_custom_settings(self):
        """Test creating QuerySettings with custom values."""
        settings = QuerySettings(max_threads=8, max_memory_usage=10_000_000_000, max_execution_time=300, readonly=1)

        assert settings.max_threads == 8
        assert settings.max_memory_usage == 10_000_000_000
        assert settings.max_execution_time == 300
        assert settings.readonly == 1

    def test_to_dict(self):
        """Test converting settings to dictionary."""
        settings = QuerySettings(max_threads=4, max_memory_usage=5_000_000_000, readonly=1)

        result = settings.to_dict()

        assert result["max_threads"] == 4
        assert result["max_memory_usage"] == 5_000_000_000
        assert result["readonly"] == 1

    def test_to_dict_excludes_none(self):
        """Test that None values are excluded from dict."""
        settings = QuerySettings(max_threads=4)

        result = settings.to_dict()

        assert "max_threads" in result
        assert "max_memory_usage" not in result
        assert "readonly" not in result

    def test_to_string(self):
        """Test converting settings to SETTINGS clause string."""
        settings = QuerySettings(max_threads=4, max_execution_time=60)

        result = str(settings)

        assert "max_threads = 4" in result
        assert "max_execution_time = 60" in result

    def test_empty_settings_string(self):
        """Test that empty settings returns empty string."""
        settings = QuerySettings()

        result = str(settings)

        assert result == ""

    def test_boolean_settings(self):
        """Test boolean settings conversion."""
        settings = QuerySettings(use_query_cache=True, optimize_read_in_order=False)

        result = settings.to_dict()

        assert result["use_query_cache"] == 1
        assert result["optimize_read_in_order"] == 0

    def test_custom_settings(self):
        """Test adding custom settings."""
        settings = QuerySettings(max_threads=4, custom={"custom_setting": "value", "another_setting": 123})

        result = settings.to_dict()

        assert result["custom_setting"] == "value"
        assert result["another_setting"] == 123


class TestSettingsPresets:
    """Test predefined settings presets."""

    def test_fast_preset(self):
        """Test fast preset."""
        settings = get_preset("fast")

        assert settings.max_threads == 8
        assert settings.optimize_read_in_order is True

    def test_memory_efficient_preset(self):
        """Test memory_efficient preset."""
        settings = get_preset("memory_efficient")

        assert settings.max_threads == 2
        assert settings.max_memory_usage == 1_000_000_000
        assert settings.group_by_overflow_mode == "break"

    def test_heavy_analytics_preset(self):
        """Test heavy_analytics preset."""
        settings = get_preset("heavy_analytics")

        assert settings.max_threads == 16
        assert settings.max_memory_usage == 50_000_000_000
        assert settings.max_execution_time == 3600

    def test_interactive_preset(self):
        """Test interactive preset."""
        settings = get_preset("interactive")

        assert settings.max_threads == 4
        assert settings.max_execution_time == 30
        assert settings.max_rows_to_read == 1_000_000

    def test_readonly_preset(self):
        """Test readonly preset."""
        settings = get_preset("readonly")

        assert settings.readonly == 1
        assert settings.max_execution_time == 60

    def test_cached_preset(self):
        """Test cached preset."""
        settings = get_preset("cached")

        assert settings.use_query_cache is True

    def test_unknown_preset(self):
        """Test that unknown preset raises KeyError."""
        with pytest.raises(KeyError, match="Unknown preset"):
            get_preset("nonexistent")

    def test_all_presets_available(self):
        """Test that all presets in SETTINGS_PRESETS work."""
        for name in SETTINGS_PRESETS.keys():
            settings = get_preset(name)
            assert isinstance(settings, QuerySettings)


class TestExecutionStats:
    """Test ExecutionStats class."""

    def test_default_initialization(self):
        """Test creating ExecutionStats with defaults."""
        stats = ExecutionStats()

        assert stats.elapsed_time == 0.0
        assert stats.rows_read == 0
        assert stats.bytes_read == 0

    def test_custom_stats(self):
        """Test creating ExecutionStats with custom values."""
        stats = ExecutionStats(elapsed_time=1.5, rows_read=1000, bytes_read=50000, memory_usage=1024)

        assert stats.elapsed_time == 1.5
        assert stats.rows_read == 1000
        assert stats.bytes_read == 50000
        assert stats.memory_usage == 1024

    def test_to_dict(self):
        """Test converting stats to dictionary."""
        stats = ExecutionStats(elapsed_time=2.0, rows_read=500, bytes_read=25000)

        result = stats.to_dict()

        assert result["elapsed_time"] == 2.0
        assert result["rows_read"] == 500
        assert result["bytes_read"] == 25000

    def test_to_string(self):
        """Test formatting stats as string."""
        stats = ExecutionStats(elapsed_time=1.234, rows_read=1000, bytes_read=50000)

        result = str(stats)

        assert "Execution time: 1.234s" in result
        assert "Rows read: 1,000" in result
        assert "Bytes read: 50,000" in result

    def test_extra_fields(self):
        """Test extra fields in stats."""
        stats = ExecutionStats(elapsed_time=1.0, extra={"custom_field": "value", "count": 42})

        result = stats.to_dict()

        assert result["custom_field"] == "value"
        assert result["count"] == 42


class TestQueryOptimizer:
    """Test QueryOptimizer class."""

    def test_recommend_settings_low_complexity(self):
        """Test recommendations for low complexity query."""
        optimizer = QueryOptimizer()

        settings = optimizer.recommend_settings(query_type="select", complexity="low")

        assert settings.max_threads == 2

    def test_recommend_settings_high_complexity(self):
        """Test recommendations for high complexity query."""
        optimizer = QueryOptimizer()

        settings = optimizer.recommend_settings(query_type="analytics", complexity="high")

        assert settings.max_threads == 8
        assert settings.optimize_read_in_order is True

    def test_recommend_settings_with_estimated_rows(self):
        """Test recommendations with row estimate."""
        optimizer = QueryOptimizer()

        # Small dataset
        settings_small = optimizer.recommend_settings(estimated_rows=500_000)
        assert settings_small.max_memory_usage == 1_000_000_000

        # Medium dataset
        settings_medium = optimizer.recommend_settings(estimated_rows=5_000_000)
        assert settings_medium.max_memory_usage == 5_000_000_000

        # Large dataset
        settings_large = optimizer.recommend_settings(estimated_rows=50_000_000)
        assert settings_large.max_memory_usage == 20_000_000_000

    def test_recommend_settings_with_time_limit(self):
        """Test recommendations with custom time limit."""
        optimizer = QueryOptimizer()

        settings = optimizer.recommend_settings(query_type="select", time_limit=120)

        assert settings.max_execution_time == 120

    def test_recommend_settings_analytics_defaults(self):
        """Test that analytics queries get longer timeout."""
        optimizer = QueryOptimizer()

        settings = optimizer.recommend_settings(query_type="analytics")

        assert settings.max_execution_time == 3600  # 1 hour
        assert settings.optimize_aggregation_in_order is True

    def test_get_query_hint(self):
        """Test getting query hints."""
        optimizer = QueryOptimizer()

        assert optimizer.get_query_hint("final") == "FINAL"
        assert optimizer.get_query_hint("sample") == "SAMPLE 0.1"
        assert optimizer.get_query_hint("unknown") == ""
