"""Unit tests for Result API - Row class and result transformers."""

import pytest
from unittest.mock import MagicMock
from chorm.result import Row, Result, ScalarResult, MappingResult, TupleResult
from chorm.exceptions import NoResultFound, MultipleResultsFound


class TestRowClass:
    """Tests for Row class with flexible access patterns."""

    def test_row_attribute_access(self):
        """Test attribute access: row.column_name"""
        row = Row(data=(1, "Alice", "Moscow"), columns=["id", "name", "city"])

        assert row.id == 1
        assert row.name == "Alice"
        assert row.city == "Moscow"

    def test_row_dict_access(self):
        """Test dict access: row['column_name']"""
        row = Row(data=(1, "Alice", "Moscow"), columns=["id", "name", "city"])

        assert row["id"] == 1
        assert row["name"] == "Alice"
        assert row["city"] == "Moscow"

    def test_row_index_access(self):
        """Test index access: row[0]"""
        row = Row(data=(1, "Alice", "Moscow"), columns=["id", "name", "city"])

        assert row[0] == 1
        assert row[1] == "Alice"
        assert row[2] == "Moscow"

    def test_row_iteration(self):
        """Test iteration: for val in row"""
        row = Row(data=(1, "Alice", "Moscow"), columns=["id", "name", "city"])

        values = list(row)
        assert values == [1, "Alice", "Moscow"]

    def test_row_len(self):
        """Test len(row)"""
        row = Row(data=(1, "Alice", "Moscow"), columns=["id", "name", "city"])
        assert len(row) == 3

    def test_row_asdict(self):
        """Test row._asdict() returns dict"""
        row = Row(data=(1, "Alice", "Moscow"), columns=["id", "name", "city"])

        result = row._asdict()
        assert result == {"id": 1, "name": "Alice", "city": "Moscow"}
        assert isinstance(result, dict)

    def test_row_tuple(self):
        """Test row._tuple() returns tuple"""
        row = Row(data=(1, "Alice", "Moscow"), columns=["id", "name", "city"])

        result = row._tuple()
        assert result == (1, "Alice", "Moscow")
        assert isinstance(result, tuple)

    def test_row_keys(self):
        """Test row.keys() returns column names"""
        row = Row(data=(1, "Alice", "Moscow"), columns=["id", "name", "city"])

        keys = row.keys()
        assert keys == ["id", "name", "city"]

    def test_row_repr(self):
        """Test string representation"""
        row = Row(data=(1, "Alice"), columns=["id", "name"])

        repr_str = repr(row)
        assert "Row(" in repr_str
        assert "id=1" in repr_str
        assert "name='Alice'" in repr_str

    def test_row_attribute_error_for_missing_column(self):
        """Test AttributeError for non-existent column"""
        row = Row(data=(1, "Alice"), columns=["id", "name"])

        with pytest.raises(AttributeError, match="Row has no column 'age'"):
            _ = row.age

    def test_row_key_error_for_missing_column(self):
        """Test KeyError for non-existent column in dict access"""
        row = Row(data=(1, "Alice"), columns=["id", "name"])

        with pytest.raises(KeyError):
            _ = row["age"]


class TestResultMethods:
    """Tests for Result class methods."""

    def _create_mock_result_set(self, rows, columns):
        """Helper to create mock result set."""
        mock_result = MagicMock()
        mock_result.result_rows = rows
        mock_result.column_names = columns
        return mock_result

    def test_result_all_returns_rows(self):
        """Test that all() returns List[Row]"""
        mock_result = self._create_mock_result_set(rows=[(1, "Alice"), (2, "Bob")], columns=["id", "name"])

        result = Result(mock_result)
        rows = result.all()

        assert len(rows) == 2
        assert isinstance(rows[0], Row)
        assert rows[0].id == 1
        assert rows[0].name == "Alice"
        assert rows[1].id == 2
        assert rows[1].name == "Bob"

    def test_result_first_returns_row(self):
        """Test that first() returns Optional[Row]"""
        mock_result = self._create_mock_result_set(rows=[(1, "Alice"), (2, "Bob")], columns=["id", "name"])

        result = Result(mock_result)
        first_row = result.first()

        assert isinstance(first_row, Row)
        assert first_row.id == 1
        assert first_row.name == "Alice"

    def test_result_first_returns_none_when_empty(self):
        """Test that first() returns None for empty result"""
        mock_result = self._create_mock_result_set(rows=[], columns=["id", "name"])

        result = Result(mock_result)
        first_row = result.first()

        assert first_row is None

    def test_result_one_returns_single_row(self):
        """Test that one() returns single Row"""
        mock_result = self._create_mock_result_set(rows=[(1, "Alice")], columns=["id", "name"])

        result = Result(mock_result)
        row = result.one()

        assert isinstance(row, Row)
        assert row.id == 1
        assert row.name == "Alice"

    def test_result_one_raises_on_empty(self):
        """Test that one() raises NoResultFound on empty result"""
        mock_result = self._create_mock_result_set(rows=[], columns=["id", "name"])

        result = Result(mock_result)

        with pytest.raises(NoResultFound, match="Query returned no results"):
            result.one()

    def test_result_one_raises_on_multiple(self):
        """Test that one() raises MultipleResultsFound on multiple rows"""
        mock_result = self._create_mock_result_set(rows=[(1, "Alice"), (2, "Bob")], columns=["id", "name"])

        result = Result(mock_result)

        with pytest.raises(MultipleResultsFound, match="Query returned .* results"):
            result.one()

    def test_result_one_or_none(self):
        """Test one_or_none() behavior"""
        # Single row
        mock_result = self._create_mock_result_set(rows=[(1, "Alice")], columns=["id", "name"])
        result = Result(mock_result)
        row = result.one_or_none()
        assert isinstance(row, Row)
        assert row.id == 1

        # Empty result
        mock_result = self._create_mock_result_set(rows=[], columns=["id", "name"])
        result = Result(mock_result)
        assert result.one_or_none() is None

        # Multiple rows
        mock_result = self._create_mock_result_set(rows=[(1, "Alice"), (2, "Bob")], columns=["id", "name"])
        result = Result(mock_result)
        with pytest.raises(MultipleResultsFound, match="Query returned .* results"):
            result.one_or_none()


class TestResultTransformers:
    """Tests for Result transformers: mappings(), tuples(), scalars()."""

    def _create_mock_result_set(self, rows, columns):
        """Helper to create mock result set."""
        mock_result = MagicMock()
        mock_result.result_rows = rows
        mock_result.column_names = columns
        return mock_result

    def test_result_mappings_returns_dicts(self):
        """Test that mappings().all() returns List[dict]"""
        mock_result = self._create_mock_result_set(rows=[(1, "Alice"), (2, "Bob")], columns=["id", "name"])

        result = Result(mock_result)
        dicts = result.mappings().all()

        assert len(dicts) == 2
        assert dicts[0] == {"id": 1, "name": "Alice"}
        assert dicts[1] == {"id": 2, "name": "Bob"}

    def test_result_mappings_first(self):
        """Test mappings().first()"""
        mock_result = self._create_mock_result_set(rows=[(1, "Alice"), (2, "Bob")], columns=["id", "name"])

        result = Result(mock_result)
        first_dict = result.mappings().first()

        assert first_dict == {"id": 1, "name": "Alice"}

    def test_result_tuples_returns_tuples(self):
        """Test that tuples().all() returns List[tuple]"""
        mock_result = self._create_mock_result_set(rows=[(1, "Alice"), (2, "Bob")], columns=["id", "name"])

        result = Result(mock_result)
        tuples = result.tuples().all()

        assert len(tuples) == 2
        assert tuples[0] == (1, "Alice")
        assert tuples[1] == (2, "Bob")

    def test_result_scalars_by_index(self):
        """Test scalars(0) returns first column values"""
        mock_result = self._create_mock_result_set(
            rows=[(1, "Alice"), (2, "Bob"), (3, "Charlie")], columns=["id", "name"]
        )

        result = Result(mock_result)
        ids = result.scalars(0).all()

        assert ids == [1, 2, 3]

    def test_result_scalars_by_name(self):
        """Test scalars('column_name') returns column values"""
        mock_result = self._create_mock_result_set(
            rows=[(1, "Alice"), (2, "Bob"), (3, "Charlie")], columns=["id", "name"]
        )

        result = Result(mock_result)
        names = result.scalars("name").all()

        assert names == ["Alice", "Bob", "Charlie"]

    def test_result_scalars_invalid_column_name(self):
        """Test scalars() raises on invalid column name"""
        mock_result = self._create_mock_result_set(rows=[(1, "Alice")], columns=["id", "name"])

        result = Result(mock_result)

        with pytest.raises(ValueError, match="Column 'age' not found"):
            result.scalars("age").all()

    def test_result_scalar_returns_first_value(self):
        """Test scalar() returns first value of first row"""
        mock_result = self._create_mock_result_set(rows=[(42, "Alice"), (43, "Bob")], columns=["id", "name"])

        result = Result(mock_result)
        value = result.scalar()

        assert value == 42

    def test_result_scalar_returns_none_when_empty(self):
        """Test scalar() returns None for empty result"""
        mock_result = self._create_mock_result_set(rows=[], columns=["id"])

        result = Result(mock_result)
        value = result.scalar()

        assert value is None


class TestScalarResultMethods:
    """Tests for ScalarResult convenience methods."""

    def _create_mock_result_set(self, rows, columns):
        """Helper to create mock result set."""
        mock_result = MagicMock()
        mock_result.result_rows = rows
        mock_result.column_names = columns
        return mock_result

    def test_scalar_result_first(self):
        """Test ScalarResult.first()"""
        mock_result = self._create_mock_result_set(rows=[(1,), (2,), (3,)], columns=["count"])

        result = Result(mock_result)
        value = result.scalars().first()

        assert value == 1

    def test_scalar_result_one(self):
        """Test ScalarResult.one()"""
        mock_result = self._create_mock_result_set(rows=[(42,)], columns=["count"])

        result = Result(mock_result)
        value = result.scalars().one()

        assert value == 42

    def test_scalar_result_scalar_one(self):
        """Test ScalarResult.scalar_one() alias"""
        mock_result = self._create_mock_result_set(rows=[(42,)], columns=["count"])

        result = Result(mock_result)
        value = result.scalars().scalar_one()

        assert value == 42

    def test_scalar_result_scalar_one_or_none(self):
        """Test ScalarResult.scalar_one_or_none()"""
        # Single value
        mock_result = self._create_mock_result_set(rows=[(42,)], columns=["count"])
        result = Result(mock_result)
        assert result.scalars().scalar_one_or_none() == 42

        # Empty result
        mock_result = self._create_mock_result_set(rows=[], columns=["count"])
        result = Result(mock_result)
        assert result.scalars().scalar_one_or_none() is None
