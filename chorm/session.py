"""Session management."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type, Union

from chorm.declarative import Table
from chorm.engine import Engine
from chorm.result import Result
from chorm.sql.dml import Delete, Insert, Update
from chorm.sql.selectable import Select


class Session:
    """Manages persistence operations for ORM objects."""

    def __init__(self, bind: Engine) -> None:
        self.bind = bind
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
            sql = statement.to_sql()
            # TODO: Infer model from Select statement for automatic mapping
            # Note: Select.to_sql() inlines values, so parameters might not be used if passed here
            # But if statement is a raw string with %(param)s, parameters will work.
            if parameters:
                 raw_result = self.bind.query(sql, parameters=parameters)
            else:
                 raw_result = self.bind.query(sql)
            return Result(raw_result)

        elif isinstance(statement, (Insert, Update, Delete)):
            sql = statement.to_sql()
            if parameters:
                self.bind.execute(sql, parameters=parameters)
            else:
                self.bind.execute(sql)
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
                    return Result(self.bind.query(sql, parameters=parameters))
                return Result(self.bind.query(sql))
            else:
                if parameters:
                    self.bind.execute(sql, parameters=parameters)
                else:
                    self.bind.execute(sql)
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
        """Flush pending changes (inserts) to the database.

        Validates all pending instances before committing.

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

            with self.bind.connect() as conn:
                conn.insert(table_name, data_tuples, column_names=column_names)

        self._pending_inserts.clear()

    def rollback(self) -> None:
        """Clear pending operations."""
        self._pending_inserts.clear()

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
            sql = statement.to_sql()
        else:
            sql = str(statement)
            
        return self.bind.query_df(sql, parameters=parameters)
