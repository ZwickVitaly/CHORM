"""DDL statement construction (DROP, TRUNCATE, RENAME, ALTER TABLE)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from chorm.sql.expression import Expression, _coerce


def _get_qualified_name(obj: Any) -> str:
    """Get fully qualified table name from object.
    
    Returns database.table if configured, otherwise just table name.
    """
    if hasattr(obj, "__table__") and hasattr(obj.__table__, "qualified_name"):
        return obj.__table__.qualified_name
    if hasattr(obj, "__tablename__"):
        return obj.__tablename__
    return str(obj)


class CreateDatabase(Expression):
    """Represents a CREATE DATABASE statement.
    
    Example:
        stmt = create_database("radar", if_not_exists=True)
        session.execute(stmt.to_sql())
        # CREATE DATABASE IF NOT EXISTS radar
    """

    def __init__(
        self,
        name: str,
        if_not_exists: bool = False,
        engine: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> None:
        self.name = name
        self.if_not_exists = if_not_exists
        self.engine = engine  # e.g., "Atomic", "Replicated", "Lazy"
        self.comment = comment
        self._settings: Dict[str, Any] = {}

    def settings(self, **kwargs: Any) -> "CreateDatabase":
        """Add SETTINGS clause."""
        self._settings.update(kwargs)
        return self

    def to_sql(self) -> str:
        """Render the CREATE DATABASE statement to SQL."""
        sql = "CREATE DATABASE"
        if self.if_not_exists:
            sql += " IF NOT EXISTS"
        sql += f" {self.name}"

        if self.engine:
            sql += f" ENGINE = {self.engine}"

        if self.comment:
            sql += f" COMMENT '{self.comment}'"

        if self._settings:
            settings_list = []
            for k, v in self._settings.items():
                val_str = str(v)
                if isinstance(v, str):
                    val_str = f"'{v}'"
                settings_list.append(f"{k}={val_str}")
            sql += f" SETTINGS {', '.join(settings_list)}"

        return sql


class DropDatabase(Expression):
    """Represents a DROP DATABASE statement.
    
    Example:
        stmt = drop_database("radar", if_exists=True)
        session.execute(stmt.to_sql())
        # DROP DATABASE IF EXISTS radar
    """

    def __init__(self, name: str, if_exists: bool = True) -> None:
        self.name = name
        self.if_exists = if_exists
        self._settings: Dict[str, Any] = {}

    def settings(self, **kwargs: Any) -> "DropDatabase":
        """Add SETTINGS clause."""
        self._settings.update(kwargs)
        return self

    def to_sql(self) -> str:
        """Render the DROP DATABASE statement to SQL."""
        sql = "DROP DATABASE"
        if self.if_exists:
            sql += " IF EXISTS"
        sql += f" {self.name}"

        if self._settings:
            settings_list = []
            for k, v in self._settings.items():
                val_str = str(v)
                if isinstance(v, str):
                    val_str = f"'{v}'"
                settings_list.append(f"{k}={val_str}")
            sql += f" SETTINGS {', '.join(settings_list)}"

        return sql


class DropTable(Expression):
    """Represents a DROP TABLE statement."""

    def __init__(self, table: Any, if_exists: bool = True) -> None:
        self.table = table
        self.if_exists = if_exists
        self._settings: Dict[str, Any] = {}

    def settings(self, **kwargs: Any) -> DropTable:
        """Add SETTINGS clause."""
        self._settings.update(kwargs)
        return self

    def to_sql(self) -> str:
        """Render the DROP TABLE statement to SQL."""
        table_name = _get_qualified_name(self.table)

        sql = "DROP TABLE"
        if self.if_exists:
            sql += " IF EXISTS"
        sql += f" {table_name}"

        if self._settings:
            settings_list = []
            for k, v in self._settings.items():
                val_str = str(v)
                if isinstance(v, str):
                    val_str = f"'{v}'"
                settings_list.append(f"{k}={val_str}")
            sql += f" SETTINGS {', '.join(settings_list)}"

        return sql


class TruncateTable(Expression):
    """Represents a TRUNCATE TABLE statement."""

    def __init__(self, table: Any, if_exists: bool = False) -> None:
        self.table = table
        self.if_exists = if_exists
        self._settings: Dict[str, Any] = {}

    def settings(self, **kwargs: Any) -> TruncateTable:
        """Add SETTINGS clause."""
        self._settings.update(kwargs)
        return self

    def to_sql(self) -> str:
        """Render the TRUNCATE TABLE statement to SQL."""
        table_name = _get_qualified_name(self.table)

        sql = "TRUNCATE TABLE"
        if self.if_exists:
            sql += " IF EXISTS"
        sql += f" {table_name}"

        if self._settings:
            settings_list = []
            for k, v in self._settings.items():
                val_str = str(v)
                if isinstance(v, str):
                    val_str = f"'{v}'"
                settings_list.append(f"{k}={val_str}")
            sql += f" SETTINGS {', '.join(settings_list)}"

        return sql


class RenameTable(Expression):
    """Represents a RENAME TABLE statement."""

    def __init__(self, old_name: Union[str, Any], new_name: str) -> None:
        self.old_name = old_name
        self.new_name = new_name

    def to_sql(self) -> str:
        """Render the RENAME TABLE statement to SQL."""
        old_table_name = _get_qualified_name(self.old_name)

        return f"RENAME TABLE {old_table_name} TO {self.new_name}"


class AlterTableAddColumn(Expression):
    """Represents an ALTER TABLE ... ADD COLUMN statement."""

    def __init__(
        self,
        table: Any,
        column: Any,
        after: Optional[str] = None,
        first: bool = False,
        if_not_exists: bool = False,
    ) -> None:
        self.table = table
        self.column = column
        self.after = after
        self.first = first
        self.if_not_exists = if_not_exists
        self._settings: Dict[str, Any] = {}

    def settings(self, **kwargs: Any) -> AlterTableAddColumn:
        """Add SETTINGS clause."""
        self._settings.update(kwargs)
        return self

    def to_sql(self) -> str:
        """Render the ALTER TABLE ADD COLUMN statement to SQL."""
        table_name = _get_qualified_name(self.table)


        # Get column definition
        from chorm.declarative import Column


        if isinstance(self.column, Column):
            col_name = self.column.name
            col_type = self.column.type.ch_type

            # Build column definition
            col_def = f"{col_name} {col_type}"

            # Add DEFAULT if specified
            if self.column.default is not None:
                if isinstance(self.column.default, str):
                    col_def += f" DEFAULT '{self.column.default}'"
                else:
                    col_def += f" DEFAULT {self.column.default}"
        else:
            # Assume it's a string with full column definition
            col_def = str(self.column)

        sql = f"ALTER TABLE {table_name} ADD COLUMN"
        if self.if_not_exists:
            sql += " IF NOT EXISTS"
        sql += f" {col_def}"

        # Add positioning
        if self.first:
            sql += " FIRST"
        elif self.after:
            sql += f" AFTER {self.after}"

        if self._settings:
            settings_list = []
            for k, v in self._settings.items():
                val_str = str(v)
                if isinstance(v, str):
                    val_str = f"'{v}'"
                settings_list.append(f"{k}={val_str}")
            sql += f" SETTINGS {', '.join(settings_list)}"

        return sql


class AlterTableDropColumn(Expression):
    """Represents an ALTER TABLE ... DROP COLUMN statement."""

    def __init__(self, table: Any, column_name: str, if_exists: bool = True) -> None:
        self.table = table
        self.column_name = column_name
        self.if_exists = if_exists
        self._settings: Dict[str, Any] = {}

    def settings(self, **kwargs: Any) -> AlterTableDropColumn:
        """Add SETTINGS clause."""
        self._settings.update(kwargs)
        return self

    def to_sql(self) -> str:
        """Render the ALTER TABLE DROP COLUMN statement to SQL."""
        table_name = _get_qualified_name(self.table)

        sql = f"ALTER TABLE {table_name} DROP COLUMN"
        if self.if_exists:
            sql += " IF EXISTS"
        sql += f" {self.column_name}"

        if self._settings:
            settings_list = []
            for k, v in self._settings.items():
                val_str = str(v)
                if isinstance(v, str):
                    val_str = f"'{v}'"
                settings_list.append(f"{k}={val_str}")
            sql += f" SETTINGS {', '.join(settings_list)}"

        return sql


class AlterTableModifyColumn(Expression):
    """Represents an ALTER TABLE ... MODIFY COLUMN statement."""

    def __init__(self, table: Any, column: Any, if_exists: bool = True) -> None:
        self.table = table
        self.column = column
        self.if_exists = if_exists
        self._settings: Dict[str, Any] = {}

    def settings(self, **kwargs: Any) -> AlterTableModifyColumn:
        """Add SETTINGS clause."""
        self._settings.update(kwargs)
        return self

    def to_sql(self) -> str:
        """Render the ALTER TABLE MODIFY COLUMN statement to SQL."""
        table_name = _get_qualified_name(self.table)



        # Get column definition
        from chorm.declarative import Column

        if isinstance(self.column, Column):
            col_name = self.column.name
            col_type = self.column.type.ch_type

            # Build column definition
            col_def = f"{col_name} {col_type}"

            # Add DEFAULT if specified
            if self.column.default is not None:
                if isinstance(self.column.default, str):
                    col_def += f" DEFAULT '{self.column.default}'"
                else:
                    col_def += f" DEFAULT {self.column.default}"
        else:
            # Assume it's a string with full column definition
            col_def = str(self.column)

        sql = f"ALTER TABLE {table_name} MODIFY COLUMN"
        if self.if_exists:
            sql += " IF EXISTS"
        sql += f" {col_def}"

        if self._settings:
            settings_list = []
            for k, v in self._settings.items():
                val_str = str(v)
                if isinstance(v, str):
                    val_str = f"'{v}'"
                settings_list.append(f"{k}={val_str}")
            sql += f" SETTINGS {', '.join(settings_list)}"

        return sql


class AlterTableRenameColumn(Expression):
    """Represents an ALTER TABLE ... RENAME COLUMN statement."""

    def __init__(self, table: Any, old_name: str, new_name: str, if_exists: bool = True) -> None:
        self.table = table
        self.old_name = old_name
        self.new_name = new_name
        self.if_exists = if_exists
        self._settings: Dict[str, Any] = {}

    def settings(self, **kwargs: Any) -> AlterTableRenameColumn:
        """Add SETTINGS clause."""
        self._settings.update(kwargs)
        return self

    def to_sql(self) -> str:
        """Render the ALTER TABLE RENAME COLUMN statement to SQL."""
        table_name = _get_qualified_name(self.table)

        sql = f"ALTER TABLE {table_name} RENAME COLUMN"
        if self.if_exists:
            sql += " IF EXISTS"
        sql += f" {self.old_name} TO {self.new_name}"

        if self._settings:
            settings_list = []
            for k, v in self._settings.items():
                val_str = str(v)
                if isinstance(v, str):
                    val_str = f"'{v}'"
                settings_list.append(f"{k}={val_str}")
            sql += f" SETTINGS {', '.join(settings_list)}"

        return sql


class AlterTableAddIndex(Expression):
    """Represents an ALTER TABLE ... ADD INDEX statement."""

    def __init__(
        self,
        table: Any,
        name: str,
        expression: Any,
        index_type: str = "minmax",
        granularity: int = 1,
        if_not_exists: bool = False,
    ) -> None:
        self.table = table
        self.name = name
        self.expression = expression
        self.index_type = index_type
        self.granularity = granularity
        self.if_not_exists = if_not_exists
        self._settings: Dict[str, Any] = {}

    def settings(self, **kwargs: Any) -> AlterTableAddIndex:
        """Add SETTINGS clause."""
        self._settings.update(kwargs)
        return self

    def to_sql(self) -> str:
        """Render the ALTER TABLE ADD INDEX statement to SQL."""
        table_name = _get_qualified_name(self.table)

        # Coerce expression
        expr = _coerce(self.expression)
        expr_sql = expr.to_sql() if hasattr(expr, "to_sql") else str(self.expression)

        sql = f"ALTER TABLE {table_name} ADD INDEX"
        if self.if_not_exists:
            sql += " IF NOT EXISTS"
        sql += f" {self.name} {expr_sql} TYPE {self.index_type} GRANULARITY {self.granularity}"

        if self._settings:
            settings_list = []
            for k, v in self._settings.items():
                val_str = str(v)
                if isinstance(v, str):
                    val_str = f"'{v}'"
                settings_list.append(f"{k}={val_str}")
            sql += f" SETTINGS {', '.join(settings_list)}"

        return sql


class AlterTableDropIndex(Expression):
    """Represents an ALTER TABLE ... DROP INDEX statement."""

    def __init__(self, table: Any, name: str, if_exists: bool = True) -> None:
        self.table = table
        self.name = name
        self.if_exists = if_exists
        self._settings: Dict[str, Any] = {}

    def settings(self, **kwargs: Any) -> AlterTableDropIndex:
        """Add SETTINGS clause."""
        self._settings.update(kwargs)
        return self

    def to_sql(self) -> str:
        """Render the ALTER TABLE DROP INDEX statement to SQL."""
        table_name = _get_qualified_name(self.table)

        sql = f"ALTER TABLE {table_name} DROP INDEX"
        if self.if_exists:
            sql += " IF EXISTS"
        sql += f" {self.name}"

        if self._settings:
            settings_list = []
            for k, v in self._settings.items():
                val_str = str(v)
                if isinstance(v, str):
                    val_str = f"'{v}'"
                settings_list.append(f"{k}={val_str}")
            sql += f" SETTINGS {', '.join(settings_list)}"

        return sql


# Helper functions
def create_database(
    name: str,
    if_not_exists: bool = False,
    engine: Optional[str] = None,
    comment: Optional[str] = None,
    **settings: Any,
) -> CreateDatabase:
    """Create a CREATE DATABASE statement.
    
    Args:
        name: Database name
        if_not_exists: Add IF NOT EXISTS clause
        engine: Database engine (Atomic, Replicated, Lazy, etc.)
        comment: Optional comment
        **settings: Additional SETTINGS
        
    Example:
        stmt = create_database("radar", if_not_exists=True)
        session.execute(stmt.to_sql())
    """
    stmt = CreateDatabase(name, if_not_exists=if_not_exists, engine=engine, comment=comment)
    if settings:
        stmt.settings(**settings)
    return stmt


def drop_database(name: str, if_exists: bool = True, **settings: Any) -> DropDatabase:
    """Create a DROP DATABASE statement.
    
    Args:
        name: Database name
        if_exists: Add IF EXISTS clause (default True for safety)
        **settings: Additional SETTINGS
        
    Example:
        stmt = drop_database("radar")
        session.execute(stmt.to_sql())
    """
    stmt = DropDatabase(name, if_exists=if_exists)
    if settings:
        stmt.settings(**settings)
    return stmt


def drop_table(table: Any, if_exists: bool = True, **settings: Any) -> DropTable:
    """Create a DROP TABLE statement."""
    stmt = DropTable(table, if_exists=if_exists)
    if settings:
        stmt.settings(**settings)
    return stmt


def truncate_table(table: Any, if_exists: bool = False, **settings: Any) -> TruncateTable:
    """Create a TRUNCATE TABLE statement."""
    stmt = TruncateTable(table, if_exists=if_exists)
    if settings:
        stmt.settings(**settings)
    return stmt


def rename_table(old_name: Union[str, Any], new_name: str) -> RenameTable:
    """Create a RENAME TABLE statement."""
    return RenameTable(old_name, new_name)


def add_column(
    table: Any,
    column: Any,
    after: Optional[str] = None,
    first: bool = False,
    if_not_exists: bool = False,
    **settings: Any,
) -> AlterTableAddColumn:
    """Create an ALTER TABLE ADD COLUMN statement."""
    stmt = AlterTableAddColumn(table, column, after=after, first=first, if_not_exists=if_not_exists)
    if settings:
        stmt.settings(**settings)
    return stmt


def drop_column(table: Any, column_name: str, if_exists: bool = True, **settings: Any) -> AlterTableDropColumn:
    """Create an ALTER TABLE DROP COLUMN statement."""
    stmt = AlterTableDropColumn(table, column_name, if_exists=if_exists)
    if settings:
        stmt.settings(**settings)
    return stmt


def modify_column(table: Any, column: Any, if_exists: bool = True, **settings: Any) -> AlterTableModifyColumn:
    """Create an ALTER TABLE MODIFY COLUMN statement."""
    stmt = AlterTableModifyColumn(table, column, if_exists=if_exists)
    if settings:
        stmt.settings(**settings)
    return stmt


def rename_column(
    table: Any, old_name: str, new_name: str, if_exists: bool = True, **settings: Any
) -> AlterTableRenameColumn:
    """Create an ALTER TABLE RENAME COLUMN statement."""
    stmt = AlterTableRenameColumn(table, old_name, new_name, if_exists=if_exists)
    if settings:
        stmt.settings(**settings)
    return stmt


def add_index(
    table: Any,
    name: str,
    expression: Any,
    index_type: str = "minmax",
    granularity: int = 1,
    if_not_exists: bool = False,
    **kwargs: Any,
) -> AlterTableAddIndex:
    """Create an ALTER TABLE ADD INDEX statement.

    Args:
        table: Table class or table name
        name: Index name
        expression: Column expression for the index
        index_type: Type of index. Supported types:
            - "minmax" - Min/max index (default)
            - "set" or "set(N)" - Set index with optional max_rows parameter
            - "bloom_filter" or "bloom_filter(rate)" - Bloom filter with optional false positive rate
            - "ngrambf_v1(n, size, hash_funcs, seed)" - N-gram bloom filter
            - "tokenbf_v1(size, hash_funcs, seed)" - Token bloom filter
        granularity: Index granularity (number of granules per index block).
            Default is 1. Higher values = less precise but smaller index.
            Recommended: 1-4 for most cases, up to 8-16 for very large tables.
        if_not_exists: Add IF NOT EXISTS clause
        **kwargs: Additional SETTINGS parameters

    Examples:
        # MinMax index (good for ranges)
        add_index(User, "idx_created", User.created_at, "minmax", granularity=1)

        # Bloom filter (good for equality checks)
        add_index(User, "idx_email", User.email, "bloom_filter", granularity=1)

        # Bloom filter with custom false positive rate
        add_index(User, "idx_email", User.email, "bloom_filter(0.01)", granularity=1)

        # Set index (good for low cardinality)
        add_index(User, "idx_country", User.country, "set(100)", granularity=4)

        # Token bloom filter (good for text search)
        add_index(User, "idx_name", User.name, "tokenbf_v1(256, 3, 0)", granularity=1)

        # N-gram bloom filter (good for substring search)
        add_index(User, "idx_desc", User.description, "ngrambf_v1(4, 512, 3, 0)", granularity=2)
    """
    return AlterTableAddIndex(table, name, expression, index_type, granularity, if_not_exists).settings(**kwargs)


def drop_index(table: Any, name: str, if_exists: bool = True, **settings: Any) -> AlterTableDropIndex:
    """Create an ALTER TABLE DROP INDEX statement."""
    stmt = AlterTableDropIndex(table, name, if_exists=if_exists)
    if settings:
        stmt.settings(**settings)
    return stmt


class AlterTableModifyTTL(Expression):
    """Represents an ALTER TABLE ... MODIFY TTL statement."""

    def __init__(self, table: Any, ttl_expression: str) -> None:
        self.table = table
        self.ttl_expression = ttl_expression
        self._settings: Dict[str, Any] = {}

    def settings(self, **kwargs: Any) -> AlterTableModifyTTL:
        """Add SETTINGS clause."""
        self._settings.update(kwargs)
        return self

    def to_sql(self) -> str:
        """Render the ALTER TABLE MODIFY TTL statement to SQL."""
        table_name = _get_qualified_name(self.table)

        sql = f"ALTER TABLE {table_name} MODIFY TTL {self.ttl_expression}"

        if self._settings:
            settings_list = []
            for k, v in self._settings.items():
                val_str = str(v)
                if isinstance(v, str):
                    val_str = f"'{v}'"
                settings_list.append(f"{k}={val_str}")
            sql += f" SETTINGS {', '.join(settings_list)}"

        return sql


def modify_ttl(table: Any, ttl_expression: str, **settings: Any) -> AlterTableModifyTTL:
    """Create an ALTER TABLE MODIFY TTL statement."""
    stmt = AlterTableModifyTTL(table, ttl_expression)
    if settings:
        stmt.settings(**settings)
    return stmt


class DetachPartition(Expression):
    """Represents an ALTER TABLE ... DETACH PARTITION statement."""

    def __init__(self, table: Any, partition_id: Union[str, int]) -> None:
        self.table = table
        self.partition_id = partition_id
        self._settings: Dict[str, Any] = {}

    def settings(self, **kwargs: Any) -> DetachPartition:
        """Add SETTINGS clause."""
        self._settings.update(kwargs)
        return self

    def to_sql(self) -> str:
        """Render the DETACH PARTITION statement to SQL."""
        table_name = _get_qualified_name(self.table)

        part_val = f"'{self.partition_id}'" if isinstance(self.partition_id, str) else str(self.partition_id)
        sql = f"ALTER TABLE {table_name} DETACH PARTITION {part_val}"

        if self._settings:
            settings_list = []
            for k, v in self._settings.items():
                val_str = str(v)
                if isinstance(v, str):
                    val_str = f"'{v}'"
                settings_list.append(f"{k}={val_str}")
            sql += f" SETTINGS {', '.join(settings_list)}"

        return sql


class AttachPartition(Expression):
    """Represents an ALTER TABLE ... ATTACH PARTITION statement."""

    def __init__(self, table: Any, partition_id: Union[str, int]) -> None:
        self.table = table
        self.partition_id = partition_id
        self._settings: Dict[str, Any] = {}

    def settings(self, **kwargs: Any) -> AttachPartition:
        """Add SETTINGS clause."""
        self._settings.update(kwargs)
        return self

    def to_sql(self) -> str:
        """Render the ATTACH PARTITION statement to SQL."""
        table_name = _get_qualified_name(self.table)

        part_val = f"'{self.partition_id}'" if isinstance(self.partition_id, str) else str(self.partition_id)
        sql = f"ALTER TABLE {table_name} ATTACH PARTITION {part_val}"

        if self._settings:
            settings_list = []
            for k, v in self._settings.items():
                val_str = str(v)
                if isinstance(v, str):
                    val_str = f"'{v}'"
                settings_list.append(f"{k}={val_str}")
            sql += f" SETTINGS {', '.join(settings_list)}"

        return sql


class DropPartition(Expression):
    """Represents an ALTER TABLE ... DROP PARTITION statement."""

    def __init__(self, table: Any, partition_id: Union[str, int]) -> None:
        self.table = table
        self.partition_id = partition_id
        self._settings: Dict[str, Any] = {}

    def settings(self, **kwargs: Any) -> DropPartition:
        """Add SETTINGS clause."""
        self._settings.update(kwargs)
        return self

    def to_sql(self) -> str:
        """Render the DROP PARTITION statement to SQL."""
        table_name = _get_qualified_name(self.table)

        part_val = f"'{self.partition_id}'" if isinstance(self.partition_id, str) else str(self.partition_id)
        sql = f"ALTER TABLE {table_name} DROP PARTITION {part_val}"

        if self._settings:
            settings_list = []
            for k, v in self._settings.items():
                val_str = str(v)
                if isinstance(v, str):
                    val_str = f"'{v}'"
                settings_list.append(f"{k}={val_str}")
            sql += f" SETTINGS {', '.join(settings_list)}"

        return sql


class FetchPartition(Expression):
    """Represents an ALTER TABLE ... FETCH PARTITION statement (for replicated tables)."""

    def __init__(self, table: Any, partition_id: Union[str, int], from_path: str) -> None:
        self.table = table
        self.partition_id = partition_id
        self.from_path = from_path
        self._settings: Dict[str, Any] = {}

    def settings(self, **kwargs: Any) -> FetchPartition:
        """Add SETTINGS clause."""
        self._settings.update(kwargs)
        return self

    def to_sql(self) -> str:
        """Render the FETCH PARTITION statement to SQL."""
        table_name = _get_qualified_name(self.table)

        part_val = f"'{self.partition_id}'" if isinstance(self.partition_id, str) else str(self.partition_id)
        sql = f"ALTER TABLE {table_name} FETCH PARTITION {part_val} FROM '{self.from_path}'"

        if self._settings:
            settings_list = []
            for k, v in self._settings.items():
                val_str = str(v)
                if isinstance(v, str):
                    val_str = f"'{v}'"
                settings_list.append(f"{k}={val_str}")
            sql += f" SETTINGS {', '.join(settings_list)}"

        return sql


def detach_partition(table: Any, partition_id: Union[str, int], **settings: Any) -> DetachPartition:
    """Create an ALTER TABLE DETACH PARTITION statement."""
    stmt = DetachPartition(table, partition_id)
    if settings:
        stmt.settings(**settings)
    return stmt


def attach_partition(table: Any, partition_id: Union[str, int], **settings: Any) -> AttachPartition:
    """Create an ALTER TABLE ATTACH PARTITION statement."""
    stmt = AttachPartition(table, partition_id)
    if settings:
        stmt.settings(**settings)
    return stmt


def drop_partition(table: Any, partition_id: Union[str, int], **settings: Any) -> DropPartition:
    """Create an ALTER TABLE DROP PARTITION statement."""
    stmt = DropPartition(table, partition_id)
    if settings:
        stmt.settings(**settings)
    return stmt


def fetch_partition(table: Any, partition_id: Union[str, int], from_path: str, **settings: Any) -> FetchPartition:
    """Create an ALTER TABLE FETCH PARTITION statement."""
    stmt = FetchPartition(table, partition_id, from_path)
    if settings:
        stmt.settings(**settings)
    return stmt


class CreateMaterializedView(Expression):
    """Represents a CREATE MATERIALIZED VIEW statement."""

    def __init__(
        self,
        name: str,
        query: Any,
        to_table: Optional[Any] = None,
        engine: Optional[Any] = None,
        populate: bool = False,
        if_not_exists: bool = False,
    ) -> None:
        self.name = name
        self.query = query
        self.to_table = to_table
        self.engine = engine
        self.populate = populate
        self.if_not_exists = if_not_exists
        self._settings: Dict[str, Any] = {}

    def settings(self, **kwargs: Any) -> CreateMaterializedView:
        """Add SETTINGS clause."""
        self._settings.update(kwargs)
        return self

    def to_sql(self) -> str:
        """Render the CREATE MATERIALIZED VIEW statement to SQL."""
        sql = "CREATE MATERIALIZED VIEW"
        if self.if_not_exists:
            sql += " IF NOT EXISTS"

        sql += f" {self.name}"

        if self.to_table:
            to_name = _get_qualified_name(self.to_table)
            sql += f" TO {to_name}"
        elif self.engine:
            # Render engine clause
            engine_sql = self.engine.format_clause() if hasattr(self.engine, "format_clause") else str(self.engine)
            sql += f" ENGINE = {engine_sql}"

        if self.populate:
            sql += " POPULATE"

        # Render query
        query_sql = self.query.to_sql() if hasattr(self.query, "to_sql") else str(self.query)
        sql += f" AS {query_sql}"

        if self._settings:
            settings_list = []
            for k, v in self._settings.items():
                val_str = str(v)
                if isinstance(v, str):
                    val_str = f"'{v}'"
                settings_list.append(f"{k}={val_str}")
            sql += f" SETTINGS {', '.join(settings_list)}"

        return sql


def create_materialized_view(
    name: str,
    query: Any,
    to_table: Optional[Any] = None,
    engine: Optional[Any] = None,
    populate: bool = False,
    if_not_exists: bool = False,
    **settings: Any,
) -> CreateMaterializedView:
    """Create a CREATE MATERIALIZED VIEW statement."""
    stmt = CreateMaterializedView(
        name,
        query,
        to_table=to_table,
        engine=engine,
        populate=populate,
        if_not_exists=if_not_exists,
    )
    if settings:
        stmt.settings(**settings)
    return stmt


class OptimizeTable(Expression):
    """Represents an OPTIMIZE TABLE statement."""

    def __init__(
        self,
        table: Any,
        partition: Optional[Union[str, int]] = None,
        final: bool = False,
        deduplicate: bool = False,
    ) -> None:
        self.table = table
        self.partition = partition
        self.final = final
        self.deduplicate = deduplicate
        self._settings: Dict[str, Any] = {}

    def settings(self, **kwargs: Any) -> "OptimizeTable":
        """Add SETTINGS clause."""
        self._settings.update(kwargs)
        return self

    def to_sql(self) -> str:
        """Render the OPTIMIZE TABLE statement to SQL."""
        table_name = _get_qualified_name(self.table)

        sql = f"OPTIMIZE TABLE {table_name}"

        if self.partition is not None:
            part_val = f"'{self.partition}'" if isinstance(self.partition, str) else str(self.partition)
            sql += f" PARTITION {part_val}"

        if self.final:
            sql += " FINAL"

        if self.deduplicate:
            sql += " DEDUPLICATE"

        if self._settings:
            settings_list = []
            for k, v in self._settings.items():
                val_str = str(v)
                if isinstance(v, str):
                    val_str = f"'{v}'"
                settings_list.append(f"{k}={val_str}")
            sql += f" SETTINGS {', '.join(settings_list)}"

        return sql


def optimize_table(
    table: Any,
    partition: Optional[Union[str, int]] = None,
    final: bool = False,
    deduplicate: bool = False,
    **settings: Any,
) -> OptimizeTable:
    """Create an OPTIMIZE TABLE statement.

    Args:
        table: Table to optimize
        partition: Optional partition to optimize
        final: If True, force final merge
        deduplicate: If True, deduplicate rows
        **settings: Additional settings

    Example:
        optimize_table(User, final=True)
        optimize_table(Events, partition='2024-01', deduplicate=True)
    """
    stmt = OptimizeTable(table, partition=partition, final=final, deduplicate=deduplicate)
    if settings:
        stmt.settings(**settings)
    return stmt


class CreateDictionary(Expression):
    """Represents a CREATE DICTIONARY statement."""

    def __init__(
        self,
        name: str,
        source: str,
        layout: str,
        structure: List[tuple],
        lifetime: Optional[int] = None,
        if_not_exists: bool = False,
    ) -> None:
        """Initialize CREATE DICTIONARY statement."""
        self.name = name
        self.source = source
        self.layout = layout
        self.structure = structure
        self.lifetime = lifetime
        self.if_not_exists = if_not_exists
        self._settings: Dict[str, Any] = {}

    def settings(self, **kwargs: Any) -> "CreateDictionary":
        """Add SETTINGS clause."""
        self._settings.update(kwargs)
        return self

    def to_sql(self) -> str:
        """Render the CREATE DICTIONARY statement to SQL."""
        sql = "CREATE DICTIONARY"
        if self.if_not_exists:
            sql += " IF NOT EXISTS"

        sql += f" {self.name}"

        # Structure (columns)
        structure_parts = []
        for col_name, col_type in self.structure:
            structure_parts.append(f"{col_name} {col_type}")
        sql += f" ({', '.join(structure_parts)})"

        # Primary key (first column is typically the key)
        if self.structure:
            sql += f" PRIMARY KEY {self.structure[0][0]}"

        # Source
        sql += f" SOURCE({self.source})"

        # Layout
        sql += f" LAYOUT({self.layout}())"

        # Lifetime
        if self.lifetime is not None:
            sql += f" LIFETIME({self.lifetime})"

        if self._settings:
            settings_list = []
            for k, v in self._settings.items():
                val_str = str(v)
                if isinstance(v, str):
                    val_str = f"'{v}'"
                settings_list.append(f"{k}={val_str}")
            sql += f" SETTINGS {', '.join(settings_list)}"

        return sql


def create_dictionary(
    name: str,
    source: str,
    layout: str,
    structure: List[tuple],
    lifetime: Optional[int] = None,
    if_not_exists: bool = False,
    **settings: Any,
) -> CreateDictionary:
    """Create a CREATE DICTIONARY statement."""
    stmt = CreateDictionary(name, source, layout, structure, lifetime=lifetime, if_not_exists=if_not_exists)
    if settings:
        stmt.settings(**settings)
    return stmt


class CreateTableAsSelect(Expression):
    """Represents a CREATE TABLE ... AS SELECT statement.
    
    This is useful for creating tables with the same structure as a query result,
    optionally populating them with the query data.
    
    Examples:
        # Create empty table with structure from SELECT
        create_table_as_select("new_table", select(User.id, User.name).where(User.active == 1))
        
        # Create table with specific engine
        create_table_as_select("events_backup", select(Events), engine=MergeTree())
        
        # Create with all options
        create_table_as_select(
            "aggregated_stats",
            select(User.id, func.count()).group_by(User.id),
            engine=SummingMergeTree(),
            order_by=["id"],
            if_not_exists=True
        )
    """

    def __init__(
        self,
        name: str,
        query: Any,
        engine: Optional[Any] = None,
        order_by: Optional[List[str]] = None,
        partition_by: Optional[str] = None,
        primary_key: Optional[List[str]] = None,
        if_not_exists: bool = False,
    ) -> None:
        """Initialize CREATE TABLE AS SELECT statement.
        
        Args:
            name: Name of the table to create
            query: SELECT statement (Select object or raw SQL string)
            engine: Table engine (e.g., MergeTree(), SummingMergeTree())
            order_by: ORDER BY columns for the table (not the query)
            partition_by: PARTITION BY expression
            primary_key: PRIMARY KEY columns (defaults to order_by if not specified)
            if_not_exists: Add IF NOT EXISTS clause
        """
        self.name = name
        self.query = query
        self.engine = engine
        self.order_by = order_by
        self.partition_by = partition_by
        self.primary_key = primary_key
        self.if_not_exists = if_not_exists
        self._settings: Dict[str, Any] = {}

    def settings(self, **kwargs: Any) -> "CreateTableAsSelect":
        """Add SETTINGS clause."""
        self._settings.update(kwargs)
        return self

    def to_sql(self) -> str:
        """Render the CREATE TABLE AS SELECT statement to SQL."""
        sql = "CREATE TABLE"
        if self.if_not_exists:
            sql += " IF NOT EXISTS"

        sql += f" {self.name}"

        # Engine
        if self.engine:
            engine_sql = self.engine.format_clause() if hasattr(self.engine, "format_clause") else str(self.engine)
            sql += f" ENGINE = {engine_sql}"

        # ORDER BY
        if self.order_by:
            if len(self.order_by) == 1:
                sql += f" ORDER BY {self.order_by[0]}"
            else:
                sql += f" ORDER BY ({', '.join(self.order_by)})"

        # PARTITION BY
        if self.partition_by:
            sql += f" PARTITION BY {self.partition_by}"

        # PRIMARY KEY (if different from ORDER BY)
        if self.primary_key:
            if len(self.primary_key) == 1:
                sql += f" PRIMARY KEY {self.primary_key[0]}"
            else:
                sql += f" PRIMARY KEY ({', '.join(self.primary_key)})"

        # Settings before AS SELECT
        if self._settings:
            settings_list = []
            for k, v in self._settings.items():
                val_str = str(v)
                if isinstance(v, str):
                    val_str = f"'{v}'"
                settings_list.append(f"{k}={val_str}")
            sql += f" SETTINGS {', '.join(settings_list)}"

        # Render query
        query_sql = self.query.to_sql() if hasattr(self.query, "to_sql") else str(self.query)
        sql += f" AS {query_sql}"

        return sql


def create_table_as_select(
    name: str,
    query: Any,
    engine: Optional[Any] = None,
    order_by: Optional[List[str]] = None,
    partition_by: Optional[str] = None,
    primary_key: Optional[List[str]] = None,
    if_not_exists: bool = False,
    **settings: Any,
) -> CreateTableAsSelect:
    """Create a CREATE TABLE ... AS SELECT statement.
    
    This is useful for creating tables with the same structure as a query result,
    optionally populating them with the query data.
    
    Args:
        name: Name of the table to create
        query: SELECT statement (Select object or raw SQL string)
        engine: Table engine (e.g., MergeTree(), SummingMergeTree())
        order_by: ORDER BY columns for the table (not the query)
        partition_by: PARTITION BY expression
        primary_key: PRIMARY KEY columns (defaults to order_by if not specified)
        if_not_exists: Add IF NOT EXISTS clause
        **settings: Additional SETTINGS parameters
        
    Returns:
        CreateTableAsSelect statement object
        
    Examples:
        # Basic CTAS
        stmt = create_table_as_select("backup", select(User))
        
        # With MergeTree engine
        from chorm.table_engines import MergeTree
        stmt = create_table_as_select(
            "stats", 
            select(User.id, func.count()).group_by(User.id),
            engine=MergeTree(),
            order_by=["id"]
        )
        
        # Execute
        session.execute(stmt.to_sql())
    """
    stmt = CreateTableAsSelect(
        name,
        query,
        engine=engine,
        order_by=order_by,
        partition_by=partition_by,
        primary_key=primary_key,
        if_not_exists=if_not_exists,
    )
    if settings:
        stmt.settings(**settings)
    return stmt
