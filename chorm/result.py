"""Result set wrappers."""

from __future__ import annotations

from typing import Any, Generic, List, Optional, Type, TypeVar, Union

from chorm.exceptions import NoResultFound, MultipleResultsFound

T = TypeVar("T")


class Row:
    """Row with attribute, dict, and index access.

    Provides flexible access to query results:
    - Attribute access: row.column_name
    - Dict access: row['column_name']
    - Index access: row[0]
    - Iteration: for val in row
    """

    def __init__(self, data: tuple, columns: list) -> None:
        self._data = data
        self._columns = columns
        self._mapping = dict(zip(columns, data))

    def __getattr__(self, name: str) -> Any:
        """Attribute access: row.column_name"""
        if name.startswith("_"):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        if name in self._mapping:
            return self._mapping[name]
        raise AttributeError(f"Row has no column '{name}'")

    def __getitem__(self, key: Union[int, str]) -> Any:
        """Dict/index access: row['column'] or row[0]"""
        if isinstance(key, int):
            return self._data[key]
        return self._mapping[key]

    def __iter__(self):
        """Iteration support: for val in row"""
        return iter(self._data)

    def __len__(self) -> int:
        """Length: len(row)"""
        return len(self._data)

    def __repr__(self) -> str:
        """String representation"""
        items = ", ".join(f"{k}={v!r}" for k, v in self._mapping.items())
        return f"Row({items})"

    def _asdict(self) -> dict:
        """Convert to dict"""
        return self._mapping.copy()

    def _tuple(self) -> tuple:
        """Convert to tuple"""
        return self._data

    def keys(self):
        """Return column names"""
        return self._columns


class Result(Generic[T]):
    """Wraps a ClickHouse query result."""

    def __init__(self, result_set: Any, model: Optional[Type[T]] = None) -> None:
        self._result_set = result_set
        self._model = model
        # Handle case where result_set might be None (e.g. DML)
        if result_set:
            self._rows = result_set.result_rows
            self._columns = result_set.column_names
        else:
            self._rows = []
            self._columns = []

    def all(self) -> List[Row]:
        """Return all rows as Row objects."""
        if self._model:
            # Map rows to model instances
            instances = []
            for row in self._rows:
                row_dict = dict(zip(self._columns, row))
                instances.append(self._model(**row_dict))
            return instances

        # Return Row objects by default
        return [Row(row, self._columns) for row in self._rows]

    def scalars(self, column: Union[int, str] = 0) -> "ScalarResult[T]":
        """Return a ScalarResult for the specified column.

        Args:
            column: Column index (int) or name (str), default 0
        """
        return ScalarResult(self, column)

    def mappings(self) -> "MappingResult":
        """Return results as dicts."""
        return MappingResult(self)

    def tuples(self) -> "TupleResult":
        """Return results as raw tuples."""
        return TupleResult(self)

    def scalar(self) -> Optional[Any]:
        """Return first value of first row or None."""
        return self.scalars().first()

    def first(self) -> Optional[Row]:
        """Return the first row or None."""
        rows = self.all()
        return rows[0] if rows else None

    def one(self) -> Row:
        """Return exactly one row or raise exception."""
        rows = self.all()
        if len(rows) == 1:
            return rows[0]
        if not rows:
            raise NoResultFound("Query returned no results. " "Use .first() or .one_or_none() if this is expected.")
        raise MultipleResultsFound(
            f"Query returned {len(rows)} results, expected 1. "
            f"Use .first() to get the first result or add .limit(1) to your query."
        )

    def one_or_none(self) -> Optional[Row]:
        """Return one row or None, raise if multiple."""
        rows = self.all()
        if len(rows) == 1:
            return rows[0]
        if not rows:
            return None
        raise MultipleResultsFound(
            f"Query returned {len(rows)} results, expected 0 or 1. "
            f"Use .first() to get the first result or add .limit(1) to your query."
        )


    def __iter__(self):
        """Yield rows lazily.

        Yields:
            Row or Model instance depending on configuration.
        """
        if self._model:
            for row in self._rows:
                row_dict = dict(zip(self._columns, row))
                yield self._model(**row_dict)
        else:
            for row in self._rows:
                yield Row(row, self._columns)


class ScalarResult(Generic[T]):
    """Result wrapper for scalar values."""

    def __init__(self, result: Result[T], column: Union[int, str] = 0) -> None:
        self._result = result
        self._column = column

    def __iter__(self):
        """Yield scalar values lazily."""
        if self._result._model:
            # If using model, iterating gives model instances, but ScalarResult specifically 
            # implies extracting a column. However, scalar() on a model query usually 
            # returns the model instance if it's the only thing selected.
            # But the original all() implementation returns model instances if model is set.
            # Let's align with all().
            for item in self._result:
                yield item
            return

        # Get column index
        if isinstance(self._column, str):
            try:
                col_idx = self._result._columns.index(self._column)
            except ValueError:
                raise ValueError(f"Column '{self._column}' not found in result")
        else:
            col_idx = self._column

        for row in self._result._rows:
            yield row[col_idx]

    def all(self) -> List[Any]:
        """Return all scalar values."""
        return list(self)

    def first(self) -> Optional[Any]:
        """Return the first scalar value."""
        # Optimized to avoid creating full iterator
        if not self._result._rows:
            return None
            
        if self._result._model:
            # Use Result.first() logic
            return self._result.first()
            
        # Get column index
        if isinstance(self._column, str):
            try:
                col_idx = self._result._columns.index(self._column)
            except ValueError:
                raise ValueError(f"Column '{self._column}' not found in result")
        else:
            col_idx = self._column
            
        return self._result._rows[0][col_idx]

    def one(self) -> Any:
        """Return exactly one scalar value."""
        rows = self._result._rows
        if len(rows) == 1:
            return self.first()
        if not rows:
            raise NoResultFound(
                "Query returned no results. " "Use .first() or .scalar_one_or_none() if this is expected."
            )
        raise MultipleResultsFound(
            f"Query returned {len(rows)} results, expected 1. " f"Use .first() or add .limit(1) to your query."
        )

    def one_or_none(self) -> Optional[Any]:
        """Return one scalar value or None."""
        rows = self._result._rows
        if len(rows) == 1:
            return self.first()
        if not rows:
            return None
        raise MultipleResultsFound(
            f"Query returned {len(rows)} results, expected 0 or 1. " f"Use .first() or add .limit(1) to your query."
        )

    def scalar(self) -> Optional[Any]:
        """Alias for first()."""
        return self.first()

    def scalar_one(self) -> Any:
        """Alias for one()."""
        return self.one()

    def scalar_one_or_none(self) -> Optional[Any]:
        """Alias for one_or_none()."""
        return self.one_or_none()


class MappingResult:
    """Result that returns dicts."""

    def __init__(self, result: Result) -> None:
        self._result = result

    def __iter__(self):
        """Yield rows as dicts lazily."""
        for row in self._result._rows:
            yield dict(zip(self._result._columns, row))

    def all(self) -> List[dict]:
        """Return all rows as dicts."""
        return list(self)

    def first(self) -> Optional[dict]:
        """Return first row as dict or None."""
        if not self._result._rows:
            return None
        return dict(zip(self._result._columns, self._result._rows[0]))

    def one(self) -> dict:
        """Return exactly one row as dict."""
        rows = self._result._rows
        if len(rows) == 1:
            return self.first()
        if not rows:
            raise NoResultFound("Query returned no results. " "Use .first() or .one_or_none() if this is expected.")
        raise MultipleResultsFound(
            f"Query returned {len(rows)} results, expected 1. " f"Use .first() or add .limit(1) to your query."
        )

    def one_or_none(self) -> Optional[dict]:
        """Return one row as dict or None."""
        rows = self._result._rows
        if len(rows) == 1:
            return self.first()
        if not rows:
            return None
        raise MultipleResultsFound(
            f"Query returned {len(rows)} results, expected 0 or 1. " f"Use .first() or add .limit(1) to your query."
        )


class TupleResult:
    """Result that returns raw tuples."""

    def __init__(self, result: Result) -> None:
        self._result = result

    def __iter__(self):
        """Yield rows as tuples lazily."""
        return iter(self._result._rows)

    def all(self) -> List[tuple]:
        """Return all rows as tuples."""
        return self._result._rows

    def first(self) -> Optional[tuple]:
        """Return first row as tuple or None."""
        return self._result._rows[0] if self._result._rows else None

    def one(self) -> tuple:
        """Return exactly one row as tuple."""
        rows = self._result._rows
        if len(rows) == 1:
            return rows[0]
        if not rows:
            raise NoResultFound("Query returned no results. " "Use .first() or .one_or_none() if this is expected.")
        raise MultipleResultsFound(
            f"Query returned {len(rows)} results, expected 1. " f"Use .first() or add .limit(1) to your query."
        )

    def one_or_none(self) -> Optional[tuple]:
        """Return one row as tuple or None."""
        rows = self._result._rows
        if len(rows) == 1:
            return rows[0]
        if not rows:
            return None
        raise MultipleResultsFound(
            f"Query returned {len(rows)} results, expected 0 or 1. " f"Use .first() or add .limit(1) to your query."
        )
