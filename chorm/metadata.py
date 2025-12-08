"""MetaData class for schema definitions."""

from typing import Dict, Any, Optional, TYPE_CHECKING
from chorm.ddl import format_ddl

if TYPE_CHECKING:
    from chorm.declarative import TableMetadata
    from chorm.engine import Engine
    from chorm.session import Session


class MetaData:
    """Registry for database features.
    
    Acts as a central registry for table definitions, matching SQLAlchemy's pattern.
    """

    def __init__(self) -> None:
        self.tables: Dict[str, "TableMetadata"] = {}

    def clear(self) -> None:
        """Clear all registered tables."""
        self.tables.clear()

    def create_all(self, engine: Any) -> None:
        """Create all tables stored in this metadata.

        Args:
            engine: CHORM Engine instance, Session, or clickhouse_connect Client.
        """
        for table_metadata in self.tables.values():
            ddl = format_ddl(table_metadata, if_not_exists=True)
            self._execute(engine, ddl)

    def drop_all(self, engine: Any) -> None:
        """Drop all tables stored in this metadata.
        
        Args:
             engine: CHORM Engine instance, Session, or clickhouse_connect Client.
        """
        for table_name in self.tables.keys():
            sql = f"DROP TABLE IF EXISTS {table_name}"
            self._execute(engine, sql)

    def _execute(self, engine: Any, sql: str) -> None:
        """Execute SQL on the given engine/session/client."""
        if hasattr(engine, "execute"):
            # Engine or Session
            engine.execute(sql)
        elif hasattr(engine, "command"):
            # clickhouse_connect Client
            engine.command(sql)
        else:
            raise TypeError(f"Unknown engine type: {type(engine)}")

    def __repr__(self) -> str:
        return f"MetaData(tables={list(self.tables.keys())})"
