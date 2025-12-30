"""Session management."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type, Union

from chorm.declarative import Table
from chorm.engine import Engine
from chorm.result import Result
from chorm.sql.dml import Delete, Insert, Update
from chorm.sql.selectable import Select


class Session:
    """Manages persistence operations for ORM objects.
    
    Note: This is NOT a transactional session. ClickHouse is an OLAP database
    and does not support traditional ACID transactions for most operations.
    
    - `commit()` flushes pending inserts to the database (no rollback possible)
    - `clear()` discards pending inserts from memory (does not affect database)
    """

    def __init__(self, bind: Engine, **kwargs: Any) -> None:
        self.bind = bind
        self._connect_overrides = kwargs
        self._pending_inserts: Dict[Type[Table], List[Table]] = {}

    def execute(self, statement: Any, parameters: Optional[Dict[str, Any]] = None) -> Result:
        """Execute a SQL statement.
        
        Args:
            statement: SQL statement (string or selectable/DML object)
            parameters: Optional dictionary of parameters for the query
            
        Returns:
            Result object
        """
        if isinstance(statement, Select):
            sql, compiled_params = self.bind.compile(statement)
            
            final_params = compiled_params
            if parameters:
                final_params = compiled_params.copy()
                final_params.update(parameters)

            raw_result = self.bind.query(sql, parameters=final_params, **self._connect_overrides)
            return Result(raw_result)

        elif isinstance(statement, (Insert, Update, Delete)):
            sql, compiled_params = self.bind.compile(statement)

            final_params = compiled_params
            if parameters:
                final_params = compiled_params.copy()
                final_params.update(parameters)

            self.bind.execute(sql, parameters=final_params, **self._connect_overrides)
            return Result(None)

        else:
            # Assume raw SQL string
            # Check if it's a query or command
            sql = str(statement).strip()
            upper_sql = sql.upper()
            if (
                upper_sql.startswith("SELECT")
                or upper_sql.startswith("WITH")
                or upper_sql.startswith("SHOW")
                or upper_sql.startswith("DESCRIBE")
                or upper_sql.startswith("EXPLAIN")
            ):
                if parameters:
                    return Result(self.bind.query(sql, parameters=parameters, **self._connect_overrides))
                return Result(self.bind.query(sql, **self._connect_overrides))
            else:
                if parameters:
                    self.bind.execute(sql, parameters=parameters, **self._connect_overrides)
                else:
                    self.bind.execute(sql, **self._connect_overrides)
                return Result(None)

    def add(self, instance: Table) -> None:
        """Add an instance to the session for pending insertion.

        Validates the instance before adding it to the session.

        Raises:
            ValidationError: If instance validation fails
        """
        # Validate instance before adding
        instance.validate()

        model_cls = type(instance)
        if model_cls not in self._pending_inserts:
            self._pending_inserts[model_cls] = []
        self._pending_inserts[model_cls].append(instance)

    def commit(self) -> None:
        """Flush pending inserts to the database.

        Note: This is not a database transaction. Once data is inserted,
        it cannot be rolled back. Use `clear()` before `commit()` to discard.

        Validates all pending instances before inserting.

        Raises:
            ValidationError: If any instance validation fails
        """
        # Validate all instances before committing
        for model_cls, instances in self._pending_inserts.items():
            for instance in instances:
                instance.validate()

        for model_cls, instances in self._pending_inserts.items():
            if not instances:
                continue

            table_name = model_cls.__tablename__
            if not table_name:
                continue

            # Get column names from metadata to ensure order
            column_names = [col.name for col in model_cls.__table__.columns]

            # Prepare data as list of tuples
            data_tuples = []
            for instance in instances:
                row = []
                for col_name in column_names:
                    val = getattr(instance, col_name)
                    # TODO: Handle type conversion if needed (e.g. Enums, UUIDs)
                    # clickhouse-connect handles many types, but custom types might need help.
                    # chorm.types.FieldType.to_clickhouse could be used here.

                    # For now, rely on clickhouse-connect's conversion
                    row.append(val)
                data_tuples.append(row)

            # Pass connect overrides when getting connection for insert
            with self.bind.connect(**self._connect_overrides) as conn:
                conn.insert(table_name, data_tuples, column_names=column_names, **self._connect_overrides)

        self._pending_inserts.clear()

    def clear(self) -> None:
        """Clear pending inserts from memory.
        
        This does NOT rollback any database changes - ClickHouse inserts
        are immediate and cannot be rolled back. This only discards
        objects added via `add()` that haven't been committed yet.
        """
        self._pending_inserts.clear()

    def rollback(self) -> None:
        """Alias for `clear()`. Kept for SQLAlchemy compatibility.
        
        Note: This does NOT rollback database changes.
        """
        self.clear()

    def close(self) -> None:
        """Close the session."""
        self._pending_inserts.clear()

    def query_df(self, statement: Any, parameters: Optional[Dict[str, Any]] = None) -> Any:
        """Execute a query and return a pandas DataFrame.
        
        Args:
            statement: SQL statement (string or selectable object)
            parameters: Optional dictionary of parameters
            
        Returns:
            pandas.DataFrame
        """
        if isinstance(statement, Select):
            sql, compiled_params = self.bind.compile(statement)
            final_params = compiled_params
            if parameters:
                final_params = compiled_params.copy()
                final_params.update(parameters)
        else:
            sql = str(statement)
            final_params = parameters
            
        return self.bind.query_df(sql, parameters=final_params, **self._connect_overrides)
