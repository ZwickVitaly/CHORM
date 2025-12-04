"""
CHORM Exception Classes
-----------------------

Centralized exception hierarchy for CHORM ORM.
Provides clear error messages with helpful hints and ClickHouse error classification.
"""

from typing import Any, Type


class CHORMError(Exception):
    """Base exception for all CHORM errors."""

    pass


# ============================================================================
# Database Errors (from ClickHouse)
# ============================================================================


class DatabaseError(CHORMError):
    """Base for database-related errors from ClickHouse.

    Attributes:
        code: ClickHouse error code (if available)
    """

    def __init__(self, message: str, code: int | None = None):
        self.code = code
        super().__init__(message)


class DatabaseSyntaxError(DatabaseError):
    """SQL syntax error from ClickHouse.

    Examples:
        - Syntax error at position X
        - Unknown identifier
        - Unknown function
    """

    pass


class DatabaseConnectionError(DatabaseError):
    """Connection or network error.

    Examples:
        - Connection refused
        - Read timeout
        - Cannot read from socket
        - Too many simultaneous connections
    """

    pass


class DatabaseAuthenticationError(DatabaseError):
    """Authentication or permission error.

    Examples:
        - Access denied
        - User does not exist
        - Wrong password
    """

    pass


class DatabaseStorageError(DatabaseError):
    """Storage or disk space error.

    Examples:
        - Not enough space
        - Too many parts
        - Table is in readonly mode
    """

    pass


class DatabaseMemoryError(DatabaseError):
    """Memory limit exceeded error.

    Examples:
        - Memory limit (for query) exceeded
        - Memory limit (for user) exceeded
    """

    pass


def classify_database_error(message: str, code: int | None = None) -> Type[DatabaseError]:
    """Classify ClickHouse error by message pattern.

    Args:
        message: Error message from ClickHouse
        code: ClickHouse error code (optional)

    Returns:
        Appropriate DatabaseError subclass

    Examples:
        >>> classify_database_error("Syntax error at position 10")
        <class 'DatabaseSyntaxError'>
        >>> classify_database_error("Connection refused")
        <class 'DatabaseConnectionError'>
    """
    msg_lower = message.lower()

    # Syntax errors
    if any(
        x in msg_lower
        for x in [
            "syntax error",
            "unknown identifier",
            "unknown function",
            "unknown table",
            "unknown column",
            "invalid number of arguments",
        ]
    ):
        return DatabaseSyntaxError

    # Connection errors
    elif any(
        x in msg_lower
        for x in [
            "connection refused",
            "timeout",
            "cannot read from socket",
            "cannot connect",
            "too many simultaneous connections",
        ]
    ):
        return DatabaseConnectionError

    # Authentication errors
    elif any(
        x in msg_lower
        for x in [
            "access denied",
            "wrong password",
            "user does not exist",
            "authentication failed",
        ]
    ):
        return DatabaseAuthenticationError

    # Storage errors
    elif any(
        x in msg_lower
        for x in [
            "not enough space",
            "too many parts",
            "readonly mode",
            "read-only",
            "disk quota",
        ]
    ):
        return DatabaseStorageError

    # Memory errors
    elif "memory limit" in msg_lower:
        return DatabaseMemoryError

    # Default to base DatabaseError
    return DatabaseError


# ============================================================================
# Query Construction Errors
# ============================================================================


class QueryError(CHORMError):
    """Base for query construction errors."""

    pass


class InvalidQueryError(QueryError):
    """Query is syntactically invalid or malformed.

    Raised when building a query with invalid parameters or structure.
    """

    pass


class QueryValidationError(QueryError):
    """Query violates ClickHouse rules or best practices.

    Attributes:
        hint: Helpful suggestion for fixing the error

    Examples:
        - HAVING clause without GROUP BY
        - Window function in WHERE clause
        - Invalid LIMIT BY usage
    """

    def __init__(self, message: str, hint: str | None = None):
        self.hint = hint
        full_message = message
        if hint:
            full_message = f"{message}\nHint: {hint}"
        super().__init__(full_message)


# ============================================================================
# Result Errors
# ============================================================================


class ResultError(CHORMError):
    """Base for result-related errors."""

    pass


class NoResultFound(ResultError):
    """Expected one result, got zero.

    Raised by .one() and .scalar_one() when query returns no rows.
    """

    pass


class MultipleResultsFound(ResultError):
    """Expected one result, got multiple.

    Raised by .one() and .scalar_one() when query returns more than one row.
    """

    pass


# ============================================================================
# Type Conversion Errors
# ============================================================================


class TypeConversionError(CHORMError):
    """Failed to convert value to ClickHouse type.

    Raised when a Python value cannot be converted to the expected ClickHouse type.

    Examples:
        - String cannot be converted to Integer
        - Invalid date format
        - Value exceeds type bounds
    """

    pass


# ============================================================================
# Validation Errors
# ============================================================================


class ValidationError(CHORMError):
    """Value validation failed.

    Raised when a value does not pass column validators.

    Attributes:
        column: Column name that failed validation
        value: Value that failed validation
        message: Validation error message

    Examples:
        - Email format invalid
        - Value out of range
        - String length exceeds limit
    """

    def __init__(self, message: str, column: str | None = None, value: Any = None):
        self.column = column
        self.value = value
        full_message = message
        if column:
            full_message = f"Validation failed for column '{column}': {message}"
        super().__init__(full_message)


# ============================================================================
# Configuration Errors
# ============================================================================


class ConfigurationError(CHORMError):
    """Invalid configuration or setup.

    Examples:
        - Table engine not defined
        - Invalid engine parameters
        - Missing required table metadata
    """

    pass


# ============================================================================
# Backward Compatibility Aliases
# ============================================================================

# These aliases maintain backward compatibility with existing code
EngineConfigurationError = ConfigurationError
DeclarativeError = ConfigurationError
ConversionError = TypeConversionError


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    # Base
    "CHORMError",
    # Database errors
    "DatabaseError",
    "DatabaseSyntaxError",
    "DatabaseConnectionError",
    "DatabaseAuthenticationError",
    "DatabaseStorageError",
    "DatabaseMemoryError",
    "classify_database_error",
    # Query errors
    "QueryError",
    "InvalidQueryError",
    "QueryValidationError",
    # Result errors
    "ResultError",
    "NoResultFound",
    "MultipleResultsFound",
    # Type errors
    "TypeConversionError",
    # Validation errors
    "ValidationError",
    # Configuration errors
    "ConfigurationError",
    # Backward compatibility
    "EngineConfigurationError",
    "DeclarativeError",
    "ConversionError",
]
