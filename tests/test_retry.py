"""Tests for retry logic with exponential backoff."""

import asyncio
import time
from unittest.mock import Mock, patch

import pytest

from chorm.retry import RetryConfig, with_retry, async_with_retry
from chorm.exceptions import DatabaseConnectionError


class TestRetryConfig:
    """Test RetryConfig configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.initial_delay == 0.1
        assert config.max_delay == 10.0
        assert config.exponential_base == 2.0
        assert config.jitter is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = RetryConfig(max_attempts=5, initial_delay=0.5, max_delay=30.0, exponential_base=3.0, jitter=False)
        assert config.max_attempts == 5
        assert config.initial_delay == 0.5
        assert config.max_delay == 30.0
        assert config.exponential_base == 3.0
        assert config.jitter is False

    def test_invalid_max_attempts(self):
        """Test validation of max_attempts."""
        with pytest.raises(ValueError, match="max_attempts must be at least 1"):
            RetryConfig(max_attempts=0)

    def test_invalid_initial_delay(self):
        """Test validation of initial_delay."""
        with pytest.raises(ValueError, match="initial_delay must be positive"):
            RetryConfig(initial_delay=0)

    def test_invalid_max_delay(self):
        """Test validation of max_delay."""
        with pytest.raises(ValueError, match="max_delay must be positive"):
            RetryConfig(max_delay=-1)

    def test_invalid_exponential_base(self):
        """Test validation of exponential_base."""
        with pytest.raises(ValueError, match="exponential_base must be greater than 1"):
            RetryConfig(exponential_base=1.0)


class TestDelayCalculation:
    """Test delay calculation with exponential backoff."""

    def test_exponential_backoff_without_jitter(self):
        """Test exponential backoff calculation without jitter."""
        config = RetryConfig(initial_delay=1.0, exponential_base=2.0, jitter=False)

        assert config.calculate_delay(0) == 1.0
        assert config.calculate_delay(1) == 2.0
        assert config.calculate_delay(2) == 4.0
        assert config.calculate_delay(3) == 8.0

    def test_exponential_backoff_with_max_delay(self):
        """Test that delay doesn't exceed max_delay."""
        config = RetryConfig(initial_delay=1.0, max_delay=5.0, exponential_base=2.0, jitter=False)

        assert config.calculate_delay(0) == 1.0
        assert config.calculate_delay(1) == 2.0
        assert config.calculate_delay(2) == 4.0
        assert config.calculate_delay(3) == 5.0  # Capped at max_delay
        assert config.calculate_delay(4) == 5.0  # Still capped

    def test_exponential_backoff_with_jitter(self):
        """Test that jitter adds randomness."""
        config = RetryConfig(initial_delay=1.0, exponential_base=2.0, jitter=True)

        # With jitter, delays should vary but be in expected range
        delay0 = config.calculate_delay(0)
        assert 0.5 <= delay0 <= 1.5  # 1.0 * (0.5 to 1.5)

        delay1 = config.calculate_delay(1)
        assert 1.0 <= delay1 <= 3.0  # 2.0 * (0.5 to 1.5)

    def test_should_retry_with_retryable_error(self):
        """Test that retryable errors trigger retry."""
        config = RetryConfig(max_attempts=3)

        # Should retry on ConnectionError
        assert config.should_retry(ConnectionError("test"), attempt=0) is True
        assert config.should_retry(ConnectionError("test"), attempt=1) is True
        assert config.should_retry(ConnectionError("test"), attempt=2) is False  # Max attempts

    def test_should_retry_with_non_retryable_error(self):
        """Test that non-retryable errors don't trigger retry."""
        config = RetryConfig(max_attempts=3)

        # Should not retry on ValueError
        assert config.should_retry(ValueError("test"), attempt=0) is False


class TestWithRetry:
    """Test @with_retry decorator."""

    def test_success_on_first_attempt(self):
        """Test successful execution on first attempt."""
        mock_func = Mock(return_value="success")

        @with_retry()
        def test_func():
            return mock_func()

        result = test_func()

        assert result == "success"
        assert mock_func.call_count == 1

    def test_retry_on_transient_error(self):
        """Test retry on transient errors."""
        mock_func = Mock(
            side_effect=[ConnectionError("Transient error"), ConnectionError("Transient error"), "success"]
        )

        @with_retry(RetryConfig(max_attempts=3, initial_delay=0.01, jitter=False))
        def test_func():
            return mock_func()

        result = test_func()

        assert result == "success"
        assert mock_func.call_count == 3

    def test_max_attempts_exceeded(self):
        """Test that exception is raised after max attempts."""
        mock_func = Mock(side_effect=ConnectionError("Persistent error"))

        @with_retry(RetryConfig(max_attempts=3, initial_delay=0.01, jitter=False))
        def test_func():
            return mock_func()

        with pytest.raises(ConnectionError, match="Persistent error"):
            test_func()

        assert mock_func.call_count == 3

    def test_non_retryable_error(self):
        """Test that non-retryable errors are not retried."""
        mock_func = Mock(side_effect=ValueError("Non-retryable"))

        @with_retry(RetryConfig(max_attempts=3))
        def test_func():
            return mock_func()

        with pytest.raises(ValueError, match="Non-retryable"):
            test_func()

        assert mock_func.call_count == 1  # No retry

    def test_custom_retryable_errors(self):
        """Test custom retryable error types."""
        mock_func = Mock(side_effect=[DatabaseConnectionError("DB error", code=1), "success"])

        config = RetryConfig(
            max_attempts=3, initial_delay=0.01, jitter=False, retryable_errors=(DatabaseConnectionError,)
        )

        @with_retry(config)
        def test_func():
            return mock_func()

        result = test_func()

        assert result == "success"
        assert mock_func.call_count == 2

    def test_delay_timing(self):
        """Test that delays are applied correctly."""
        mock_func = Mock(side_effect=[ConnectionError("Error 1"), ConnectionError("Error 2"), "success"])

        config = RetryConfig(max_attempts=3, initial_delay=0.1, exponential_base=2.0, jitter=False)

        @with_retry(config)
        def test_func():
            return mock_func()

        start_time = time.time()
        result = test_func()
        elapsed = time.time() - start_time

        # Should have delays: 0.1s + 0.2s = 0.3s minimum
        assert result == "success"
        assert elapsed >= 0.3


class TestAsyncWithRetry:
    """Test @async_with_retry decorator."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self):
        """Test successful async execution on first attempt."""
        mock_func = Mock(return_value="success")

        @async_with_retry()
        async def test_func():
            return mock_func()

        result = await test_func()

        assert result == "success"
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_transient_error(self):
        """Test async retry on transient errors."""
        call_count = 0

        @async_with_retry(RetryConfig(max_attempts=3, initial_delay=0.01, jitter=False))
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Transient error")
            return "success"

        result = await test_func()

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_attempts_exceeded(self):
        """Test that exception is raised after max async attempts."""

        @async_with_retry(RetryConfig(max_attempts=3, initial_delay=0.01, jitter=False))
        async def test_func():
            raise ConnectionError("Persistent error")

        with pytest.raises(ConnectionError, match="Persistent error"):
            await test_func()

    @pytest.mark.asyncio
    async def test_non_retryable_error(self):
        """Test that non-retryable errors are not retried in async."""
        call_count = 0

        @async_with_retry(RetryConfig(max_attempts=3))
        async def test_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Non-retryable")

        with pytest.raises(ValueError, match="Non-retryable"):
            await test_func()

        assert call_count == 1  # No retry

    @pytest.mark.asyncio
    async def test_concurrent_retries(self):
        """Test multiple concurrent async retries."""
        call_counts = {"func1": 0, "func2": 0}

        @async_with_retry(RetryConfig(max_attempts=3, initial_delay=0.01, jitter=False))
        async def test_func1():
            call_counts["func1"] += 1
            if call_counts["func1"] < 2:
                raise ConnectionError("Error")
            return "success1"

        @async_with_retry(RetryConfig(max_attempts=3, initial_delay=0.01, jitter=False))
        async def test_func2():
            call_counts["func2"] += 1
            if call_counts["func2"] < 3:
                raise ConnectionError("Error")
            return "success2"

        results = await asyncio.gather(test_func1(), test_func2())

        assert results == ["success1", "success2"]
        assert call_counts["func1"] == 2
        assert call_counts["func2"] == 3

    @pytest.mark.asyncio
    async def test_async_delay_timing(self):
        """Test that async delays are applied correctly."""
        call_count = 0

        config = RetryConfig(max_attempts=3, initial_delay=0.1, exponential_base=2.0, jitter=False)

        @async_with_retry(config)
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Error")
            return "success"

        start_time = time.time()
        result = await test_func()
        elapsed = time.time() - start_time

        # Should have delays: 0.1s + 0.2s = 0.3s minimum
        assert result == "success"
        assert elapsed >= 0.3
