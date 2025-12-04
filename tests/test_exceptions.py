"""Unit tests for CHORM exception handling."""

import pytest
from chorm.exceptions import (
    CHORMError,
    DatabaseError,
    DatabaseSyntaxError,
    DatabaseConnectionError,
    DatabaseAuthenticationError,
    DatabaseStorageError,
    DatabaseMemoryError,
    classify_database_error,
    QueryValidationError,
    NoResultFound,
    MultipleResultsFound,
    TypeConversionError,
    ConfigurationError,
    # Backward compatibility
    EngineConfigurationError,
    DeclarativeError,
    ConversionError,
)
from chorm.sql import select, func
from chorm.sql.expression import Identifier


class TestExceptionHierarchy:
    """Test exception inheritance structure."""

    def test_database_error_inheritance(self):
        """Verify DatabaseError hierarchy."""
        assert issubclass(DatabaseError, CHORMError)
        assert issubclass(DatabaseSyntaxError, DatabaseError)
        assert issubclass(DatabaseConnectionError, DatabaseError)

    def test_backward_compatibility(self):
        """Verify backward compatibility aliases."""
        assert issubclass(EngineConfigurationError, CHORMError)
        assert issubclass(DeclarativeError, CHORMError)
        assert issubclass(ConversionError, CHORMError)

        # Verify aliases point to new classes
        assert EngineConfigurationError is ConfigurationError
        assert DeclarativeError is ConfigurationError
        assert ConversionError is TypeConversionError


class TestDatabaseErrorClassification:
    """Test classification of ClickHouse error messages."""

    def test_classify_syntax_error(self):
        msg = "Code: 62. DB::Exception: Syntax error: failed at position 10"
        cls = classify_database_error(msg)
        assert cls is DatabaseSyntaxError

    def test_classify_unknown_identifier(self):
        msg = "Code: 47. DB::Exception: Unknown identifier: user_id"
        cls = classify_database_error(msg)
        assert cls is DatabaseSyntaxError

    def test_classify_connection_refused(self):
        msg = "Code: 210. DB::NetException: Connection refused"
        cls = classify_database_error(msg)
        assert cls is DatabaseConnectionError

    def test_classify_timeout(self):
        msg = "Code: 209. DB::NetException: Timeout exceeded"
        cls = classify_database_error(msg)
        assert cls is DatabaseConnectionError

    def test_classify_access_denied(self):
        msg = "Code: 492. DB::Exception: Access denied for user 'default'"
        cls = classify_database_error(msg)
        assert cls is DatabaseAuthenticationError

    def test_classify_storage_error(self):
        msg = "Code: 243. DB::Exception: Not enough space on disk"
        cls = classify_database_error(msg)
        assert cls is DatabaseStorageError

    def test_classify_memory_error(self):
        msg = "Code: 241. DB::Exception: Memory limit (for query) exceeded"
        cls = classify_database_error(msg)
        assert cls is DatabaseMemoryError

    def test_classify_unknown_error(self):
        msg = "Code: 999. DB::Exception: Something weird happened"
        cls = classify_database_error(msg)
        assert cls is DatabaseError


class TestQueryValidation:
    """Test query validation logic."""

    def test_having_without_group_by(self):
        """Test that HAVING without GROUP BY raises QueryValidationError."""
        stmt = select(func.count()).having(func.count() > 10)

        with pytest.raises(QueryValidationError) as exc:
            stmt.to_sql()

        assert "HAVING clause requires GROUP BY" in str(exc.value)
        assert "Hint: Add .group_by()" in str(exc.value)

    def test_valid_having_with_group_by(self):
        """Test that HAVING with GROUP BY is valid."""
        stmt = select(Identifier("city"), func.count()).group_by(Identifier("city")).having(func.count() > 10)
        sql = stmt.to_sql()
        assert "HAVING (count() > 10)" in sql
        assert "GROUP BY city" in sql


class TestWindowFunctionValidation:
    """Test validation of window functions in invalid clauses."""

    def test_window_function_in_where_raises(self):
        """Test that window function in WHERE raises QueryValidationError."""
        # row_number() over ()
        win_func = func.row_number().over()
        stmt = select(Identifier("id")).where(win_func > 1)

        with pytest.raises(QueryValidationError, match="Window functions are not allowed in WHERE"):
            stmt.to_sql()

    def test_window_function_in_group_by_raises(self):
        """Test that window function in GROUP BY raises QueryValidationError."""
        win_func = func.rank().over(order_by=Identifier("score"))
        stmt = select(Identifier("id")).group_by(win_func)

        with pytest.raises(QueryValidationError, match="Window functions are not allowed in GROUP BY"):
            stmt.to_sql()

    def test_window_function_in_having_raises(self):
        """Test that window function in HAVING raises QueryValidationError."""
        win_func = func.row_number().over()
        # Note: We need GROUP BY to avoid "HAVING requires GROUP BY" error first
        stmt = select(Identifier("id")).group_by(Identifier("id")).having(win_func > 1)

        with pytest.raises(QueryValidationError, match="Window functions are not allowed in HAVING"):
            stmt.to_sql()


class TestArrayJoinValidation:
    """Test validation of ARRAY JOIN clauses."""

    def test_array_join_requires_arguments(self):
        """Test that array_join() raises ValueError if no arguments provided."""
        stmt = select(Identifier("id"))

        with pytest.raises(ValueError, match="ARRAY JOIN requires at least one target"):
            stmt.array_join()

    def test_left_array_join_requires_arguments(self):
        """Test that left_array_join() raises ValueError if no arguments provided."""
        stmt = select(Identifier("id"))

        with pytest.raises(ValueError, match="ARRAY JOIN requires at least one target"):
            stmt.left_array_join()


class TestErrorMessages:
    """Test helpful error messages."""

    def test_no_result_found_message(self):
        err = NoResultFound("Query returned no results. Use .first() or .one_or_none() if this is expected.")
        assert "Use .first()" in str(err)

    def test_multiple_results_found_message(self):
        err = MultipleResultsFound("Query returned 2 results, expected 1. Use .first() to get the first result.")
        assert "expected 1" in str(err)
        assert "Use .first()" in str(err)
