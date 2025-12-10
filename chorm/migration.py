
"""Core migration logic for CHORM."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, List, Optional
from datetime import datetime

from chorm.session import Session
from chorm.sql import select, insert, delete
from chorm.sql.ddl import (
    add_column,
    drop_column,
    modify_column,
    rename_column,
    add_index,
    drop_index,
)
from chorm.sql.expression import Identifier, Literal


class Migration(ABC):
    """Base class for all migrations."""

    # Unique identifier for the migration (e.g., timestamp or UUID)
    id: str

    # Human-readable name
    name: str

    # ID of the previous migration (for dependency tracking)
    down_revision: Optional[str] = None

    @abstractmethod
    def upgrade(self, session: Session) -> None:
        """Apply the migration."""
        pass

    @abstractmethod
    def downgrade(self, session: Session) -> None:
        """Revert the migration."""
        pass

    # DDL Helper Methods
    def execute_ddl(self, session: Session, ddl_statement: any) -> None:
        """Execute a DDL statement."""
        sql = ddl_statement.to_sql() if hasattr(ddl_statement, "to_sql") else str(ddl_statement)
        session.execute(sql)

    def add_column(self, session: Session, table: any, column_def: str, **kwargs) -> None:
        """Add a column to a table.

        Args:
            session: Database session
            table: Table class or table name
            column_def: Column definition (e.g., "age UInt8" or "email String DEFAULT ''")
            **kwargs: Additional options (after, first, if_not_exists, settings)

        Example:
            self.add_column(session, User, "age UInt8", after="name")
        """

        stmt = add_column(table, column_def, **kwargs)
        self.execute_ddl(session, stmt)

    def drop_column(self, session: Session, table: any, column_name: str, **kwargs) -> None:
        """Drop a column from a table.

        Args:
            session: Database session
            table: Table class or table name
            column_name: Name of column to drop
            **kwargs: Additional options (if_exists, settings)

        Example:
            self.drop_column(session, User, "old_field")
        """

        stmt = drop_column(table, column_name, **kwargs)
        self.execute_ddl(session, stmt)

    def modify_column(self, session: Session, table: any, column_def: str, **kwargs) -> None:
        """Modify a column's type or default value.

        Args:
            session: Database session
            table: Table class or table name
            column_def: New column definition (e.g., "name String" or "age UInt16 DEFAULT 0")
            **kwargs: Additional options (if_exists, settings)

        Example:
            self.modify_column(session, User, "age UInt16")
        """

        stmt = modify_column(table, column_def, **kwargs)
        self.execute_ddl(session, stmt)

    def rename_column(self, session: Session, table: any, old_name: str, new_name: str, **kwargs) -> None:
        """Rename a column.

        Args:
            session: Database session
            table: Table class or table name
            old_name: Current column name
            new_name: New column name
            **kwargs: Additional options (if_exists, settings)

        Example:
            self.rename_column(session, User, "old_name", "new_name")
        """

        stmt = rename_column(table, old_name, new_name, **kwargs)
        self.execute_ddl(session, stmt)

    def add_index(self, session: Session, table: any, name: str, expression: any, **kwargs) -> None:
        """Add an index to a table.

        Args:
            session: Database session
            table: Table class or table name
            name: Index name
            expression: Column or expression to index
            **kwargs: Additional options (index_type, granularity, if_not_exists, settings)

        Example:
            from chorm.sql.expression import Identifier
            self.add_index(session, User, "idx_email", Identifier("email"), index_type="bloom_filter")
        """

        stmt = add_index(table, name, expression, **kwargs)
        self.execute_ddl(session, stmt)

    def drop_index(self, session: Session, table: any, name: str, **kwargs) -> None:
        """Drop an index from a table.

        Args:
            session: Database session
            table: Table class or table name
            name: Index name
            **kwargs: Additional options (if_exists, settings)

        Example:
            self.drop_index(session, User, "idx_email")
        """

        stmt = drop_index(table, name, **kwargs)
        self.execute_ddl(session, stmt)


class MigrationManager:
    """Manages migration state in the database."""

    def __init__(self, session: Session, table_name: str = "chorm_migrations"):
        self.session = session
        self.table_name = table_name

    def ensure_migration_table(self) -> None:
        """Create the migrations table if it doesn't exist."""
        # We use raw SQL for DDL for now, or we could define a Table model.
        # Using raw SQL to avoid circular dependencies or model registration issues.
        sql = f"""
        CREATE TABLE IF NOT EXISTS {self.table_name} (
            id String,
            name String,
            applied_at DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        ORDER BY applied_at
        """
        self.session.execute(sql)

    def get_applied_migrations(self) -> List[str]:
        """Get list of applied migration IDs."""
        self.ensure_migration_table()

        # Query the table and get results
        result = self.session.execute(f"SELECT id FROM {self.table_name} ORDER BY applied_at")
        # Use .all() to get Row objects, then extract the id field
        rows = result.all()
        return [row[0] for row in rows]

    @staticmethod
    def _escape_string(value: str) -> str:
        return value.replace("\\", "\\\\").replace("'", "''")

    def apply_migration(self, migration: Migration) -> None:
        """Record a migration as applied."""
        self.ensure_migration_table()

        # Use string formatting since Session.execute doesn't support params
        # Escape single quotes in name to prevent SQL injection
        safe_name = self._escape_string(migration.name)
        self.session.execute(f"INSERT INTO {self.table_name} (id, name) VALUES ('{migration.id}', '{safe_name}')")

    def unapply_migration(self, migration_id: str) -> None:
        """Remove a migration record."""
        self.ensure_migration_table()

        # ALTER TABLE DELETE is async in ClickHouse, but for lightweight usage it's okay.
        # Or we can use DELETE FROM if lightweight deletes are enabled.
        # Let's use ALTER TABLE DELETE.
        self.session.execute(f"ALTER TABLE {self.table_name} DELETE WHERE id = '{migration_id}'")
