"""Retry logic with exponential backoff for transient errors."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from functools import wraps
from typing import Any, Callable, Optional, Tuple, Type, TypeVar

from chorm.exceptions import DatabaseConnectionError, DatabaseMemoryError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryConfig:
    """Configuration for retry behavior with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds before first retry (default: 0.1)
        max_delay: Maximum delay between retries in seconds (default: 10.0)
        exponential_base: Base for exponential backoff calculation (default: 2.0)
        jitter: Add random jitter to delays to avoid thundering herd (default: True)
        retryable_errors: Tuple of exception types that should trigger retry

    Example:
        >>> config = RetryConfig(max_attempts=5, initial_delay=0.5)
        >>> config.calculate_delay(0)  # First retry
        0.5
        >>> config.calculate_delay(1)  # Second retry
        1.0
        >>> config.calculate_delay(2)  # Third retry
        2.0
    """

    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 0.1,
        max_delay: float = 10.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_errors: Optional[Tuple[Type[Exception], ...]] = None,
    ):
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if initial_delay <= 0:
            raise ValueError("initial_delay must be positive")
        if max_delay <= 0:
            raise ValueError("max_delay must be positive")
        if exponential_base <= 1:
            raise ValueError("exponential_base must be greater than 1")

        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

        # Default retryable errors: network and transient errors
        self.retryable_errors = retryable_errors or (
            ConnectionError,
            TimeoutError,
            OSError,
            DatabaseConnectionError,
            DatabaseMemoryError,  # Memory errors can be transient
        )

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number with exponential backoff.

        Args:
            attempt: Attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        # Calculate exponential delay
        delay = min(self.initial_delay * (self.exponential_base**attempt), self.max_delay)

        # Add jitter to avoid thundering herd problem
        if self.jitter:
            # Random factor between 0.5 and 1.5
            jitter_factor = 0.5 + random.random()
            delay = delay * jitter_factor

        return delay

    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """Check if exception should trigger a retry.

        Args:
            exception: Exception that was raised
            attempt: Current attempt number (0-indexed)

        Returns:
            True if should retry, False otherwise
        """
        # Check if we've exceeded max attempts
        if attempt >= self.max_attempts - 1:
            return False

        # Check if exception is retryable
        return isinstance(exception, self.retryable_errors)


def with_retry(config: Optional[RetryConfig] = None) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to add retry logic with exponential backoff to a function.

    Args:
        config: RetryConfig instance. If None, uses default configuration.

    Returns:
        Decorated function with retry logic

    Example:
        >>> @with_retry(RetryConfig(max_attempts=3))
        ... def fetch_data():
        ...     # May fail with transient errors
        ...     return client.query("SELECT 1")
        >>> result = fetch_data()  # Will retry on transient errors
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None

            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if config.should_retry(e, attempt):
                        delay = config.calculate_delay(attempt)
                        logger.warning(
                            f"Attempt {attempt + 1}/{config.max_attempts} failed: {e}. " f"Retrying in {delay:.2f}s..."
                        )
                        time.sleep(delay)
                    else:
                        # Non-retryable error or max attempts reached
                        raise

            # Should never reach here due to raise in loop, but for type safety
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected retry loop exit")

        return wrapper

    return decorator


def async_with_retry(config: Optional[RetryConfig] = None) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to add retry logic with exponential backoff to an async function.

    Args:
        config: RetryConfig instance. If None, uses default configuration.

    Returns:
        Decorated async function with retry logic

    Example:
        >>> @async_with_retry(RetryConfig(max_attempts=3))
        ... async def fetch_data():
        ...     # May fail with transient errors
        ...     return await client.query("SELECT 1")
        >>> result = await fetch_data()  # Will retry on transient errors
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None

            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if config.should_retry(e, attempt):
                        delay = config.calculate_delay(attempt)
                        logger.warning(
                            f"Attempt {attempt + 1}/{config.max_attempts} failed: {e}. " f"Retrying in {delay:.2f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        # Non-retryable error or max attempts reached
                        raise

            # Should never reach here due to raise in loop, but for type safety
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected retry loop exit")

        return wrapper

    return decorator


# Public API
__all__ = [
    "RetryConfig",
    "with_retry",
    "async_with_retry",
]
