"""Model validation system for CHORM.

Provides validators for column values, ensuring data integrity before database operations.
"""

from __future__ import annotations

import re
from typing import Any, Callable, List, Optional, Sequence, Type

from chorm.exceptions import ValidationError


# ============================================================================
# Base Validator
# ============================================================================


class Validator:
    """Base class for all validators.

    Validators are callable objects that check if a value meets certain criteria.
    They should raise ValidationError if validation fails.

    Example:
        class MyValidator(Validator):
            def __call__(self, value: Any, column_name: str | None = None) -> Any:
                if not self._check(value):
                    raise ValidationError(f"Value {value} is invalid", column_name, value)
                return value

            def _check(self, value: Any) -> bool:
                # Your validation logic
                return True
    """

    def __call__(self, value: Any, column_name: str | None = None) -> Any:
        """Validate a value.

        Args:
            value: Value to validate
            column_name: Optional column name for error messages

        Returns:
            Validated (and possibly transformed) value

        Raises:
            ValidationError: If validation fails
        """
        raise NotImplementedError("Subclasses must implement __call__")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"


# ============================================================================
# Standard Validators
# ============================================================================


class RangeValidator(Validator):
    """Validates that a numeric value is within a range.

    Args:
        min_value: Minimum allowed value (inclusive)
        max_value: Maximum allowed value (inclusive)

    Example:
        age = Column(Int32(), validators=[RangeValidator(0, 150)])
    """

    def __init__(self, min_value: float | int | None = None, max_value: float | int | None = None):
        if min_value is None and max_value is None:
            raise ValueError("At least one of min_value or max_value must be provided")
        self.min_value = min_value
        self.max_value = max_value

    def __call__(self, value: Any, column_name: str | None = None) -> Any:
        if value is None:
            return value  # None values are handled by nullable check

        try:
            num_value = float(value)
        except (ValueError, TypeError):
            raise ValidationError(f"Value {value!r} is not numeric", column_name, value)

        if self.min_value is not None and num_value < self.min_value:
            raise ValidationError(f"Value {value!r} is less than minimum {self.min_value}", column_name, value)

        if self.max_value is not None and num_value > self.max_value:
            raise ValidationError(f"Value {value!r} is greater than maximum {self.max_value}", column_name, value)

        return value

    def __repr__(self) -> str:
        parts = []
        if self.min_value is not None:
            parts.append(f"min={self.min_value}")
        if self.max_value is not None:
            parts.append(f"max={self.max_value}")
        return f"{self.__class__.__name__}({', '.join(parts)})"


class LengthValidator(Validator):
    """Validates the length of a string or sequence.

    Args:
        min_length: Minimum length (inclusive)
        max_length: Maximum length (inclusive)

    Example:
        name = Column(String(), validators=[LengthValidator(min_length=1, max_length=100)])
    """

    def __init__(self, min_length: int | None = None, max_length: int | None = None):
        if min_length is None and max_length is None:
            raise ValueError("At least one of min_length or max_length must be provided")
        if min_length is not None and min_length < 0:
            raise ValueError("min_length must be non-negative")
        if max_length is not None and max_length < 0:
            raise ValueError("max_length must be non-negative")
        if min_length is not None and max_length is not None and min_length > max_length:
            raise ValueError("min_length cannot be greater than max_length")
        self.min_length = min_length
        self.max_length = max_length

    def __call__(self, value: Any, column_name: str | None = None) -> Any:
        if value is None:
            return value  # None values are handled by nullable check

        if not isinstance(value, (str, bytes, list, tuple)):
            raise ValidationError(f"Value {value!r} is not a string or sequence", column_name, value)

        length = len(value)

        if self.min_length is not None and length < self.min_length:
            raise ValidationError(
                f"Value {value!r} length {length} is less than minimum {self.min_length}", column_name, value
            )

        if self.max_length is not None and length > self.max_length:
            raise ValidationError(
                f"Value {value!r} length {length} is greater than maximum {self.max_length}", column_name, value
            )

        return value

    def __repr__(self) -> str:
        parts = []
        if self.min_length is not None:
            parts.append(f"min_length={self.min_length}")
        if self.max_length is not None:
            parts.append(f"max_length={self.max_length}")
        return f"{self.__class__.__name__}({', '.join(parts)})"


class RegexValidator(Validator):
    """Validates that a string matches a regular expression.

    Args:
        pattern: Regular expression pattern (string or compiled regex)
        flags: Optional regex flags

    Example:
        phone = Column(String(), validators=[RegexValidator(r'^\\+?[1-9]\\d{1,14}$')])
    """

    def __init__(self, pattern: str | re.Pattern, flags: int = 0):
        if isinstance(pattern, str):
            self.pattern = re.compile(pattern, flags)
        else:
            self.pattern = pattern

    def __call__(self, value: Any, column_name: str | None = None) -> Any:
        if value is None:
            return value  # None values are handled by nullable check

        if not isinstance(value, str):
            raise ValidationError(f"Value {value!r} is not a string", column_name, value)

        if not self.pattern.match(value):
            raise ValidationError(
                f"Value {value!r} does not match pattern {self.pattern.pattern!r}", column_name, value
            )

        return value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(pattern={self.pattern.pattern!r})"


class EmailValidator(Validator):
    """Validates that a string is a valid email address.

    Uses a simple regex-based validation. For production use, consider
    using a more robust library like email-validator.

    Behavior:
        - Strips leading and trailing whitespace from input
        - Rejects emails with internal spaces
        - Returns the original value (not stripped) after validation

    Example:
        email = Column(String(), validators=[EmailValidator()])
    """

    # RFC 5322 compliant email regex (simplified)
    # Note: {2,} allows TLDs of 2+ characters (.com, .museum, etc.)
    EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

    def __call__(self, value: Any, column_name: str | None = None) -> Any:
        if value is None:
            return value  # None values are handled by nullable check

        if not isinstance(value, str):
            raise ValidationError(f"Value {value!r} is not a string", column_name, value)

        # Store original value to return later (no silent transformation)
        original_value = value

        # Strip leading/trailing whitespace for validation
        value = value.strip()

        # Basic checks
        if not value:
            raise ValidationError(
                f"Value {original_value!r} is not a valid email address (empty after strip)",
                column_name,
                original_value,
            )

        if "@" not in value:
            raise ValidationError(
                f"Value {original_value!r} is not a valid email address (missing @)", column_name, original_value
            )

        # Check for internal spaces (after stripping)
        if " " in value:
            raise ValidationError(
                f"Value {original_value!r} contains internal spaces and is not a valid email address",
                column_name,
                original_value,
            )

        # Split by @ and check parts
        parts = value.split("@")
        if len(parts) != 2:
            raise ValidationError(
                f"Value {original_value!r} is not a valid email address (multiple @ symbols)",
                column_name,
                original_value,
            )

        local, domain = parts
        if not local or not domain:
            raise ValidationError(
                f"Value {original_value!r} is not a valid email address (empty local or domain part)",
                column_name,
                original_value,
            )

        # Check domain has at least one dot
        if "." not in domain:
            raise ValidationError(
                f"Value {original_value!r} is not a valid email address (domain missing TLD)",
                column_name,
                original_value,
            )

        # Additional regex check
        if not self.EMAIL_PATTERN.match(value):
            raise ValidationError(
                f"Value {original_value!r} is not a valid email address format", column_name, original_value
            )

        # Return original value (no silent transformation)
        return original_value


class InValidator(Validator):
    """Validates that a value is in a set of allowed values.

    Args:
        choices: Sequence of allowed values

    Example:
        status = Column(String(), validators=[InValidator(['active', 'inactive', 'pending'])])
    """

    def __init__(self, choices: Sequence[Any]):
        if not choices:
            raise ValueError("choices cannot be empty")
        self.choices = tuple(choices)

    def __call__(self, value: Any, column_name: str | None = None) -> Any:
        if value is None:
            return value  # None values are handled by nullable check

        if value not in self.choices:
            raise ValidationError(f"Value {value!r} is not in allowed choices: {self.choices}", column_name, value)

        return value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(choices={self.choices})"


class NotInValidator(Validator):
    """Validates that a value is NOT in a set of disallowed values.

    Args:
        choices: Sequence of disallowed values

    Example:
        username = Column(String(), validators=[NotInValidator(['admin', 'root', 'system'])])
    """

    def __init__(self, choices: Sequence[Any]):
        if not choices:
            raise ValueError("choices cannot be empty")
        self.choices = tuple(choices)

    def __call__(self, value: Any, column_name: str | None = None) -> Any:
        if value is None:
            return value  # None values are handled by nullable check

        if value in self.choices:
            raise ValidationError(f"Value {value!r} is in disallowed choices: {self.choices}", column_name, value)

        return value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(choices={self.choices})"


class CustomValidator(Validator):
    """Wrapper for custom validation functions.

    Args:
        validator_func: Callable that takes (value, column_name) and returns validated value
        error_message: Optional custom error message template

    Example:
        def is_positive(value, column_name=None):
            if value <= 0:
                raise ValidationError(f"{column_name} must be positive", column_name, value)
            return value

        price = Column(Float64(), validators=[CustomValidator(is_positive)])
    """

    def __init__(self, validator_func: Callable[[Any, str | None], Any], error_message: str | None = None):
        self.validator_func = validator_func
        self.error_message = error_message

    def __call__(self, value: Any, column_name: str | None = None) -> Any:
        try:
            return self.validator_func(value, column_name)
        except ValidationError:
            raise
        except Exception as e:
            error_msg = self.error_message or f"Custom validation failed: {e}"
            raise ValidationError(error_msg, column_name, value) from e

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(func={self.validator_func.__name__})"


# ============================================================================
# Convenience Functions
# ============================================================================


def validate_value(value: Any, validators: Sequence[Validator], column_name: str | None = None) -> Any:
    """Apply a sequence of validators to a value.

    Args:
        value: Value to validate
        validators: Sequence of validators to apply
        column_name: Optional column name for error messages

    Returns:
        Validated value

    Raises:
        ValidationError: If any validator fails

    Example:
        validators = [RangeValidator(0, 100), CustomValidator(lambda v, _: v if v % 2 == 0 else None)]
        validated = validate_value(42, validators, "age")
    """
    result = value
    for validator in validators:
        result = validator(result, column_name)
    return result


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    # Base
    "Validator",
    # Standard validators
    "RangeValidator",
    "LengthValidator",
    "RegexValidator",
    "EmailValidator",
    "InValidator",
    "NotInValidator",
    "CustomValidator",
    # Utilities
    "validate_value",
]
