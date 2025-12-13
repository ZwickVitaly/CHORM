"""Asynchronous session management."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type, Union

from chorm.declarative import Table
from chorm.async_engine import AsyncEngine
from chorm.result import Result
from chorm.sql.dml import Delete, Insert, Update
from chorm.sql.selectable import Select


class AsyncSession:
    """Manages asynchronous persistence operations for ORM objects."""

    def __init__(self, bind: AsyncEngine) -> None:
        self.bind = bind
        self._pending_inserts: Dict[Type[Table], List[Table]] = {}

    async def execute(self, statement: Any) -> Result:
        """Execute a SQL statement asynchronously."""
        if isinstance(statement, Select):
            sql = statement.to_sql()
            # TODO: Infer model from Select statement for automatic mapping
            raw_result = await self.bind.query(sql)
            return Result(raw_result)

        elif isinstance(statement, (Insert, Update, Delete)):
            sql = statement.to_sql()
            await self.bind.execute(sql)
            return Result(None)

        else:
            # Assume raw SQL string
            # Check if it's a query or command
            sql = str(statement).strip()
            if sql.upper().startswith("SELECT") or sql.upper().startswith("WITH"):
                return Result(await self.bind.query(sql))
            else:
                await self.bind.execute(sql)
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

    async def commit(self) -> None:
        """Flush pending changes (inserts) to the database asynchronously.

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

            async with self.bind.connect() as conn:
                await conn.insert(table_name, data_tuples, column_names=column_names)

        self._pending_inserts.clear()

    def rollback(self) -> None:
        """Clear pending operations."""
        self._pending_inserts.clear()

    async def close(self) -> None:
        """Close the session."""
        self._pending_inserts.clear()

    async def query_df(self, statement: Any, parameters: Optional[Dict[str, Any]] = None) -> Any:
        """Execute a query and return a pandas DataFrame asynchronously.
        
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
            
        return await self.bind.query_df(sql, parameters=parameters)

    async def __aenter__(self) -> AsyncSession:
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Async context manager exit."""
        if exc_type is None:
            await self.commit()
        else:
            self.rollback()
        await self.close()
