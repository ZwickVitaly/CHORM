"""Tests for CHORM validation system."""

import pytest
import re

from chorm.exceptions import ValidationError
from chorm.validators import (
    Validator,
    RangeValidator,
    LengthValidator,
    RegexValidator,
    EmailValidator,
    InValidator,
    NotInValidator,
    CustomValidator,
    validate_value,
)
from chorm.declarative import Table, Column
from chorm.types import Int32, String, Float64
from chorm.table_engines import MergeTree


# ============================================================================
# Base Validator Tests
# ============================================================================


class TestValidator:
    def test_validator_base_class(self):
        """Test that Validator base class raises NotImplementedError."""
        validator = Validator()
        with pytest.raises(NotImplementedError):
            validator("test", "column")


# ============================================================================
# RangeValidator Tests
# ============================================================================


class TestRangeValidator:
    def test_range_validator_min_max(self):
        """Test RangeValidator with both min and max."""
        validator = RangeValidator(min_value=0, max_value=100)

        # Valid values
        assert validator(50, "age") == 50
        assert validator(0, "age") == 0
        assert validator(100, "age") == 100

        # Invalid values
        with pytest.raises(ValidationError) as exc_info:
            validator(-1, "age")
        assert "less than minimum" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            validator(101, "age")
        assert "greater than maximum" in str(exc_info.value)

    def test_range_validator_min_only(self):
        """Test RangeValidator with only min."""
        validator = RangeValidator(min_value=0)

        assert validator(100, "value") == 100
        assert validator(0, "value") == 0

        with pytest.raises(ValidationError):
            validator(-1, "value")

    def test_range_validator_max_only(self):
        """Test RangeValidator with only max."""
        validator = RangeValidator(max_value=100)

        assert validator(50, "value") == 50
        assert validator(100, "value") == 100

        with pytest.raises(ValidationError):
            validator(101, "value")

    def test_range_validator_none_value(self):
        """Test RangeValidator with None value."""
        validator = RangeValidator(min_value=0, max_value=100)
        assert validator(None, "age") is None  # None is handled by nullable check

    def test_range_validator_non_numeric(self):
        """Test RangeValidator with non-numeric value."""
        validator = RangeValidator(min_value=0, max_value=100)

        with pytest.raises(ValidationError) as exc_info:
            validator("not a number", "age")
        assert "not numeric" in str(exc_info.value)

    def test_range_validator_float(self):
        """Test RangeValidator with float values."""
        validator = RangeValidator(min_value=0.0, max_value=1.0)

        assert validator(0.5, "ratio") == 0.5
        assert validator(0.0, "ratio") == 0.0
        assert validator(1.0, "ratio") == 1.0

        with pytest.raises(ValidationError):
            validator(1.5, "ratio")

    def test_range_validator_empty_args(self):
        """Test RangeValidator with no arguments."""
        with pytest.raises(ValueError, match="At least one"):
            RangeValidator()

    def test_range_validator_string_number(self):
        """Test RangeValidator with string that can be converted to number."""
        validator = RangeValidator(min_value=0, max_value=100)

        # String numbers should be converted and validated
        assert validator("50", "value") == "50"
        assert validator("0", "value") == "0"
        assert validator("100", "value") == "100"

        with pytest.raises(ValidationError):
            validator("-1", "value")

        with pytest.raises(ValidationError):
            validator("101", "value")


# ============================================================================
# LengthValidator Tests
# ============================================================================


class TestLengthValidator:
    def test_length_validator_min_max(self):
        """Test LengthValidator with both min and max."""
        validator = LengthValidator(min_length=1, max_length=10)

        # Valid values
        assert validator("hello", "name") == "hello"
        assert validator("a", "name") == "a"
        assert validator("1234567890", "name") == "1234567890"

        # Invalid values
        with pytest.raises(ValidationError) as exc_info:
            validator("", "name")
        assert "less than minimum" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            validator("12345678901", "name")
        assert "greater than maximum" in str(exc_info.value)

    def test_length_validator_min_only(self):
        """Test LengthValidator with only min."""
        validator = LengthValidator(min_length=5)

        assert validator("hello", "text") == "hello"
        assert validator("hello world", "text") == "hello world"

        with pytest.raises(ValidationError):
            validator("hi", "text")

    def test_length_validator_max_only(self):
        """Test LengthValidator with only max."""
        validator = LengthValidator(max_length=5)

        assert validator("hello", "text") == "hello"
        assert validator("hi", "text") == "hi"

        with pytest.raises(ValidationError):
            validator("hello world", "text")

    def test_length_validator_none_value(self):
        """Test LengthValidator with None value."""
        validator = LengthValidator(min_length=1, max_length=10)
        assert validator(None, "name") is None

    def test_length_validator_non_string(self):
        """Test LengthValidator with non-string value."""
        validator = LengthValidator(min_length=1, max_length=10)

        with pytest.raises(ValidationError) as exc_info:
            validator(123, "name")
        assert "not a string or sequence" in str(exc_info.value)

    def test_length_validator_list(self):
        """Test LengthValidator with list."""
        validator = LengthValidator(min_length=1, max_length=5)

        assert validator([1, 2, 3], "items") == [1, 2, 3]

        with pytest.raises(ValidationError):
            validator([], "items")

        with pytest.raises(ValidationError):
            validator([1, 2, 3, 4, 5, 6], "items")

    def test_length_validator_empty_args(self):
        """Test LengthValidator with no arguments."""
        with pytest.raises(ValueError, match="At least one"):
            LengthValidator()

    def test_length_validator_negative_length(self):
        """Test LengthValidator with negative length."""
        with pytest.raises(ValueError, match="non-negative"):
            LengthValidator(min_length=-1)

        with pytest.raises(ValueError, match="non-negative"):
            LengthValidator(max_length=-1)

    def test_length_validator_min_greater_than_max(self):
        """Test LengthValidator with min > max."""
        with pytest.raises(ValueError, match="cannot be greater"):
            LengthValidator(min_length=10, max_length=5)

    def test_length_validator_bytes(self):
        """Test LengthValidator with bytes."""
        validator = LengthValidator(min_length=1, max_length=10)

        assert validator(b"hello", "data") == b"hello"

        with pytest.raises(ValidationError):
            validator(b"", "data")

        with pytest.raises(ValidationError):
            validator(b"12345678901", "data")


# ============================================================================
# RegexValidator Tests
# ============================================================================


class TestRegexValidator:
    def test_regex_validator_string_pattern(self):
        """Test RegexValidator with string pattern."""
        validator = RegexValidator(r"^[a-z]+$")

        assert validator("hello", "text") == "hello"

        with pytest.raises(ValidationError) as exc_info:
            validator("Hello", "text")
        assert "does not match pattern" in str(exc_info.value)

    def test_regex_validator_compiled_pattern(self):
        """Test RegexValidator with compiled pattern."""
        pattern = re.compile(r"^\d+$")
        validator = RegexValidator(pattern)

        assert validator("123", "number") == "123"

        with pytest.raises(ValidationError):
            validator("abc", "number")

    def test_regex_validator_none_value(self):
        """Test RegexValidator with None value."""
        validator = RegexValidator(r"^\d+$")
        assert validator(None, "number") is None

    def test_regex_validator_non_string(self):
        """Test RegexValidator with non-string value."""
        validator = RegexValidator(r"^\d+$")

        with pytest.raises(ValidationError) as exc_info:
            validator(123, "number")
        assert "not a string" in str(exc_info.value)

    def test_regex_validator_flags(self):
        """Test RegexValidator with flags."""
        validator = RegexValidator(r"^[a-z]+$", flags=re.IGNORECASE)

        assert validator("Hello", "text") == "Hello"
        assert validator("hello", "text") == "hello"


# ============================================================================
# EmailValidator Tests
# ============================================================================


class TestEmailValidator:
    def test_email_validator_valid(self):
        """Test EmailValidator with valid emails."""
        validator = EmailValidator()

        valid_emails = [
            "user@example.com",
            "test.email@domain.co.uk",
            "user+tag@example.com",
            "user_name@example-domain.com",
        ]

        for email in valid_emails:
            assert validator(email, "email") == email

    def test_email_validator_invalid(self):
        """Test EmailValidator with invalid emails."""
        validator = EmailValidator()

        invalid_emails = [
            "notanemail",
            "@example.com",
            "user@",
            "user @example.com",  # Internal space
            "user@example",  # No TLD
            "user@@example.com",  # Multiple @
            "",  # Empty string
            "   ",  # Only whitespace
        ]

        for email in invalid_emails:
            with pytest.raises(ValidationError) as exc_info:
                validator(email, "email")
            assert "not a valid email" in str(exc_info.value)

    def test_email_validator_whitespace_handling(self):
        """Test EmailValidator whitespace handling (lenient approach)."""
        validator = EmailValidator()

        # Leading/trailing whitespace should be stripped and accepted
        assert validator(" user@example.com", "email") == " user@example.com"
        assert validator("user@example.com ", "email") == "user@example.com "
        assert validator("  user@example.com  ", "email") == "  user@example.com  "

        # Internal spaces should be rejected
        with pytest.raises(ValidationError) as exc_info:
            validator("user @example.com", "email")
        assert "internal spaces" in str(exc_info.value)

    def test_email_validator_none_value(self):
        """Test EmailValidator with None value."""
        validator = EmailValidator()
        assert validator(None, "email") is None

    def test_email_validator_non_string(self):
        """Test EmailValidator with non-string value."""
        validator = EmailValidator()

        with pytest.raises(ValidationError) as exc_info:
            validator(123, "email")
        assert "not a string" in str(exc_info.value)

    def test_email_validator_edge_cases(self):
        """Test EmailValidator with edge cases."""
        validator = EmailValidator()

        # Valid edge cases
        valid_emails = [
            "a@b.co",  # Minimal valid email
            "user+tag@example.com",  # Plus sign
            "user_name@example.com",  # Underscore
            "user.name@example.com",  # Dot in local part
            "user@sub.example.com",  # Subdomain
        ]

        for email in valid_emails:
            assert validator(email, "email") == email

        # Invalid edge cases
        invalid_emails = [
            "user@",  # Missing domain
            "@example.com",  # Missing local part
            "user@domain",  # Missing TLD
            "user@@example.com",  # Double @
        ]

        for email in invalid_emails:
            with pytest.raises(ValidationError):
                validator(email, "email")


# ============================================================================
# InValidator Tests
# ============================================================================


class TestInValidator:
    def test_in_validator_valid(self):
        """Test InValidator with valid values."""
        validator = InValidator(["active", "inactive", "pending"])

        assert validator("active", "status") == "active"
        assert validator("inactive", "status") == "inactive"
        assert validator("pending", "status") == "pending"

    def test_in_validator_invalid(self):
        """Test InValidator with invalid values."""
        validator = InValidator(["active", "inactive", "pending"])

        with pytest.raises(ValidationError) as exc_info:
            validator("deleted", "status")
        assert "not in allowed choices" in str(exc_info.value)

    def test_in_validator_none_value(self):
        """Test InValidator with None value."""
        validator = InValidator(["active", "inactive"])
        assert validator(None, "status") is None

    def test_in_validator_empty_choices(self):
        """Test InValidator with empty choices."""
        with pytest.raises(ValueError, match="cannot be empty"):
            InValidator([])

    def test_in_validator_numeric(self):
        """Test InValidator with numeric values."""
        validator = InValidator([1, 2, 3])

        assert validator(1, "value") == 1
        assert validator(2, "value") == 2

        with pytest.raises(ValidationError):
            validator(4, "value")


# ============================================================================
# NotInValidator Tests
# ============================================================================


class TestNotInValidator:
    def test_not_in_validator_valid(self):
        """Test NotInValidator with valid values."""
        validator = NotInValidator(["admin", "root", "system"])

        assert validator("user", "username") == "user"
        assert validator("guest", "username") == "guest"

    def test_not_in_validator_invalid(self):
        """Test NotInValidator with invalid values."""
        validator = NotInValidator(["admin", "root", "system"])

        with pytest.raises(ValidationError) as exc_info:
            validator("admin", "username")
        assert "is in disallowed choices" in str(exc_info.value)

    def test_not_in_validator_none_value(self):
        """Test NotInValidator with None value."""
        validator = NotInValidator(["admin", "root"])
        assert validator(None, "username") is None

    def test_not_in_validator_empty_choices(self):
        """Test NotInValidator with empty choices."""
        with pytest.raises(ValueError, match="cannot be empty"):
            NotInValidator([])


# ============================================================================
# CustomValidator Tests
# ============================================================================


class TestCustomValidator:
    def test_custom_validator_function(self):
        """Test CustomValidator with custom function."""

        def is_positive(value, column_name=None):
            if value <= 0:
                raise ValidationError(f"{column_name} must be positive", column_name, value)
            return value

        validator = CustomValidator(is_positive)

        assert validator(1, "price") == 1
        assert validator(100, "price") == 100

        with pytest.raises(ValidationError) as exc_info:
            validator(0, "price")
        assert "must be positive" in str(exc_info.value)

    def test_custom_validator_with_error_message(self):
        """Test CustomValidator with custom error message."""

        def check(value, column_name=None):
            if value < 0:
                raise ValueError("Negative value")
            return value

        validator = CustomValidator(check, error_message="Custom validation failed")

        assert validator(1, "value") == 1

        with pytest.raises(ValidationError) as exc_info:
            validator(-1, "value")
        assert "Custom validation failed" in str(exc_info.value)

    def test_custom_validator_preserves_validation_error(self):
        """Test CustomValidator preserves ValidationError."""

        def check(value, column_name=None):
            raise ValidationError("Custom error", column_name, value)

        validator = CustomValidator(check)

        with pytest.raises(ValidationError) as exc_info:
            validator(1, "value")
        assert "Custom error" in str(exc_info.value)

    def test_custom_validator_none_value(self):
        """Test CustomValidator with None value."""

        def check_positive(value, column_name=None):
            if value is not None and value <= 0:
                raise ValidationError("Must be positive", column_name, value)
            return value

        validator = CustomValidator(check_positive)

        # None should pass through
        assert validator(None, "value") is None
        assert validator(10, "value") == 10

        with pytest.raises(ValidationError):
            validator(-5, "value")


# ============================================================================
# validate_value Tests
# ============================================================================


class TestValidateValue:
    def test_validate_value_single_validator(self):
        """Test validate_value with single validator."""
        validator = RangeValidator(0, 100)
        assert validate_value(50, [validator], "age") == 50

        with pytest.raises(ValidationError):
            validate_value(150, [validator], "age")

    def test_validate_value_multiple_validators(self):
        """Test validate_value with multiple validators."""

        def is_even(value, column_name=None):
            if value % 2 != 0:
                raise ValidationError(f"{column_name} must be even", column_name, value)
            return value

        validators = [
            RangeValidator(0, 100),
            CustomValidator(is_even),
        ]

        assert validate_value(50, validators, "value") == 50

        with pytest.raises(ValidationError):
            validate_value(51, validators, "value")  # Not even

    def test_validate_value_empty_validators(self):
        """Test validate_value with empty validators."""
        assert validate_value(50, [], "value") == 50


# ============================================================================
# Integration Tests with Table
# ============================================================================


class TestTableValidation:
    def test_table_column_validation_on_set(self):
        """Test that column validation runs on attribute set."""

        class User(Table):
            __tablename__ = "users"
            __order_by__ = ("id",)
            engine = MergeTree()

            id = Column(Int32(), primary_key=True)
            age = Column(Int32(), validators=[RangeValidator(0, 150)])
            email = Column(String(), validators=[EmailValidator()])

        user = User(id=1, age=25, email="user@example.com")
        assert user.age == 25

        # Valid value
        user.age = 30
        assert user.age == 30

        # Invalid value
        with pytest.raises(ValidationError) as exc_info:
            user.age = 200
        assert "age" in str(exc_info.value).lower()

    def test_table_validate_method(self):
        """Test Table.validate() method."""

        class User(Table):
            __tablename__ = "users"
            __order_by__ = ("id",)
            engine = MergeTree()

            id = Column(Int32(), primary_key=True)
            age = Column(Int32(), validators=[RangeValidator(0, 150)])
            email = Column(String(), validators=[EmailValidator()])

        # Valid instance
        user = User(id=1, age=25, email="user@example.com")
        user.validate()  # Should not raise

        # Invalid instance - validation happens on assignment via __set__
        with pytest.raises(ValidationError):
            user.age = 200

        # Also test validate() with invalid value set directly
        user.__dict__["age"] = 200
        with pytest.raises(ValidationError):
            user.validate()

    def test_table_validation_nullable(self):
        """Test that nullable columns allow None."""

        class User(Table):
            __tablename__ = "users"
            __order_by__ = ("id",)
            engine = MergeTree()

            id = Column(Int32(), primary_key=True)
            name = Column(String(), nullable=True, validators=[LengthValidator(1, 100)])

        user = User(id=1, name=None)
        user.validate()  # Should not raise

        user.name = "Alice"
        user.validate()  # Should not raise

    def test_table_validation_not_nullable(self):
        """Test that non-nullable columns reject None."""

        class User(Table):
            __tablename__ = "users"
            __order_by__ = ("id",)
            engine = MergeTree()

            id = Column(Int32(), primary_key=True)
            name = Column(String(), nullable=False, validators=[LengthValidator(1, 100)])

        user = User(id=1, name="Alice")
        user.validate()  # Should not raise

        # Set None directly to bypass __set__ validation
        user.__dict__["name"] = None
        with pytest.raises(ValidationError) as exc_info:
            user.validate()
        assert "not nullable" in str(exc_info.value).lower()

    def test_table_multiple_validators(self):
        """Test table with multiple validators on one column."""

        class Product(Table):
            __tablename__ = "products"
            __order_by__ = ("id",)
            engine = MergeTree()

            id = Column(Int32(), primary_key=True)
            price = Column(
                Float64(),
                validators=[
                    RangeValidator(0, 10000),
                    CustomValidator(
                        lambda v, _: (
                            v if v > 0 else (_ for _ in ()).throw(ValidationError("Price must be positive", None, v))
                        )
                    ),
                ],
            )

        product = Product(id=1, price=50.0)
        product.validate()  # Should not raise

        # Set invalid value directly to bypass __set__ validation
        product.__dict__["price"] = -10.0
        with pytest.raises(ValidationError):
            product.validate()

        product.__dict__["price"] = 20000.0
        with pytest.raises(ValidationError):
            product.validate()


# ============================================================================
# Session Integration Tests
# ============================================================================


class TestSessionValidation:
    def test_session_add_validates(self):
        """Test that Session.add() validates instances."""
        from chorm import create_engine, Session

        class User(Table):
            __tablename__ = "users"
            __order_by__ = ("id",)
            engine = MergeTree()

            id = Column(Int32(), primary_key=True)
            age = Column(Int32(), validators=[RangeValidator(0, 150)])

        engine = create_engine("clickhouse://localhost:8123/test")
        session = Session(engine)

        # Valid instance
        user = User(id=1, age=25)
        session.add(user)  # Should not raise

        # Invalid instance - validation happens in __set__, so we need to bypass it
        user2 = User(id=2, age=25)  # Create with valid value
        user2.__dict__["age"] = 200  # Set invalid value directly
        with pytest.raises(ValidationError):
            session.add(user2)

    def test_session_commit_validates(self):
        """Test that Session.commit() validates all instances."""
        from chorm import create_engine, Session

        class User(Table):
            __tablename__ = "users"
            __order_by__ = ("id",)
            engine = MergeTree()

            id = Column(Int32(), primary_key=True)
            age = Column(Int32(), validators=[RangeValidator(0, 150)])

        engine = create_engine("clickhouse://localhost:8123/test")
        session = Session(engine)

        user1 = User(id=1, age=25)
        session.add(user1)

        user2 = User(id=2, age=30)
        session.add(user2)

        # Modify after adding (should still be validated on commit)
        # Set invalid value directly to bypass __set__ validation
        user2.__dict__["age"] = 200

        with pytest.raises(ValidationError):
            session.commit()


# ============================================================================
# Async Session Integration Tests
# ============================================================================


class TestAsyncSessionValidation:
    @pytest.mark.asyncio
    async def test_async_session_add_validates(self):
        """Test that AsyncSession.add() validates instances."""
        from chorm import create_async_engine, AsyncSession

        class User(Table):
            __tablename__ = "users"
            __order_by__ = ("id",)
            engine = MergeTree()

            id = Column(Int32(), primary_key=True)
            age = Column(Int32(), validators=[RangeValidator(0, 150)])

        engine = create_async_engine("clickhouse://localhost:8123/test")
        session = AsyncSession(engine)

        # Valid instance
        user = User(id=1, age=25)
        session.add(user)  # Should not raise

        # Invalid instance - validation happens in __set__, so we need to bypass it
        user2 = User(id=2, age=25)  # Create with valid value
        user2.__dict__["age"] = 200  # Set invalid value directly
        with pytest.raises(ValidationError):
            session.add(user2)

    @pytest.mark.asyncio
    async def test_async_session_commit_validates(self):
        """Test that AsyncSession.commit() validates all instances."""
        from chorm import create_async_engine, AsyncSession

        class User(Table):
            __tablename__ = "users"
            __order_by__ = ("id",)
            engine = MergeTree()

            id = Column(Int32(), primary_key=True)
            age = Column(Int32(), validators=[RangeValidator(0, 150)])

        engine = create_async_engine("clickhouse://localhost:8123/test")
        session = AsyncSession(engine)

        user1 = User(id=1, age=25)
        session.add(user1)

        user2 = User(id=2, age=30)
        session.add(user2)

        # Modify after adding (should still be validated on commit)
        # Set invalid value directly to bypass __set__ validation
        user2.__dict__["age"] = 200

        with pytest.raises(ValidationError):
            await session.commit()
