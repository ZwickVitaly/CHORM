"""Declarative table base for defining ClickHouse schemas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, Mapping, Sequence, Tuple, Type

if TYPE_CHECKING:
    from chorm.validators import Validator

from chorm.table_engines import TableEngine
from chorm.types import FieldType, NullableType, parse_type
from chorm.sql.expression import Expression
from chorm.ddl import format_ddl
from chorm.codecs import Codec
from chorm.metadata import MetaData
from chorm.exceptions import ConfigurationError, ValidationError, CHORMError
from chorm.validators import Validator, validate_value
from chorm.sql.selectable import Select
from chorm.table_engines import TableEngine, MaterializedView
from chorm.sql.expression import Label, Identifier

# Backward compatibility alias
DeclarativeError = ConfigurationError


def get_qualified_table_name(obj: Any) -> str:
    """Get fully qualified table name from object.
    
    Returns database.table if __database__ is set, otherwise just table name.
    Works with Table classes, TableMetadata instances, or strings.
    
    Examples:
        get_qualified_table_name(User)  # Returns "users" or "mydb.users"
        get_qualified_table_name(User.__table__)  # Same
        get_qualified_table_name("users")  # Returns "users" as-is
    """
    # If it's a string, return as-is
    if isinstance(obj, str):
        return obj
    
    # If it has __table__ with qualified_name (Table class)
    if hasattr(obj, "__table__") and hasattr(obj.__table__, "qualified_name"):
        return obj.__table__.qualified_name
    
    # If it's TableMetadata with qualified_name
    if hasattr(obj, "qualified_name"):
        return obj.qualified_name
    
    # If it has __database__ and __tablename__ (Table class)
    if hasattr(obj, "__database__") and hasattr(obj, "__tablename__"):
        database = obj.__database__
        tablename = obj.__tablename__
        if database:
            return f"{database}.{tablename}"
        return tablename or str(obj)
    
    # If it only has __tablename__
    if hasattr(obj, "__tablename__"):
        return obj.__tablename__ or str(obj)
    
    # Fallback
    return str(obj)


class Column(Expression):
    """Descriptor representing a ClickHouse table column."""

    # ... (Column implementation unchanged) ...

    def __init__(
        self,
        field_type: FieldType | str,
        *,
        primary_key: bool = False,
        nullable: bool = False,
        default: Any | None = None,
        default_factory: Callable[[], Any] | None = None,
        comment: str | None = None,
        codec: str | Codec | Sequence[Codec] | None = None,
        validators: Sequence["Validator"] | None = None,
    ) -> None:
        if isinstance(field_type, str):
            field_type = parse_type(field_type)
        if isinstance(field_type, NullableType):
            self.nullable = True
        self.field_type: FieldType = field_type
        self.primary_key = primary_key
        self.nullable = nullable or isinstance(field_type, NullableType)
        self.default = default
        self.default_factory = default_factory
        self.comment = comment
        self.codec = codec
        self.validators: tuple["Validator", ...] = tuple(validators) if validators else ()
        self.name: str | None = None

    def __set_name__(self, owner: Type["Table"], name: str) -> None:
        self.name = name
        self.table = owner

    def __get__(self, instance: "Table" | None, owner: Type["Table"]) -> Any:
        if instance is None:
            return self
        if self.name is None:
            raise AttributeError("Column not bound to class")
        if self.name not in instance.__dict__:
            instance.__dict__[self.name] = self._generate_default()
        return instance.__dict__[self.name]

    def __set__(self, instance: "Table", value: Any) -> None:
        if self.name is None:
            raise AttributeError("Column not bound to class")

        # Validate value if validators are defined
        if self.validators:
            # Check nullable first
            if value is None and not self.nullable:
                raise ValidationError(f"Column '{self.name}' is not nullable", self.name, value)

            # Apply validators if value is not None
            if value is not None:
                value = validate_value(value, self.validators, self.name)

        instance.__dict__[self.name] = value

    def _generate_default(self) -> Any:
        if self.default_factory is not None:
            return self.default_factory()
        return self.default

    @property
    def ch_type(self) -> str:
        ch_type = getattr(self.field_type, "ch_type", str(self.field_type))
        if self.nullable and not ch_type.startswith("Nullable("):
            return f"Nullable({ch_type})"
        return ch_type

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        type_repr = self.field_type.ch_type if hasattr(self.field_type, "ch_type") else repr(self.field_type)
        return f"Column({self.name!r}, {type_repr})"

    def to_sql(self, compiler: Any = None) -> str:
        if self.name is None:
            raise DeclarativeError("Column not bound to class")
        if hasattr(self, "table") and hasattr(self.table, "__table__"):
            # Use qualified_name (database.table or just table)
            return f"{self.table.__table__.qualified_name}.{self.name}"
        elif hasattr(self, "table") and hasattr(self.table, "__tablename__") and self.table.__tablename__:
            return f"{self.table.__tablename__}.{self.name}"
        return self.name


@dataclass(frozen=True, slots=True)
class ColumnInfo:
    name: str
    column: Column

    @property
    def type(self) -> FieldType:
        return self.column.field_type

    @property
    def primary_key(self) -> bool:
        return self.column.primary_key


@dataclass(frozen=True, slots=True)
class TableMetadata:
    """Collected metadata for a declarative table."""

    name: str
    columns: Tuple[ColumnInfo, ...]
    engine: TableEngine | None
    database: str | None = None  # Optional database name
    order_by: Tuple[str, ...] = ()
    partition_by: Tuple[str, ...] = ()
    sample_by: Tuple[str, ...] = ()
    ttl: str | None = None
    select_query: Any | None = None
    from_table: str | None = None
    to_table: str | None = None

    @property
    def qualified_name(self) -> str:
        """Return fully qualified name: database.table or just table."""
        if self.database:
            return f"{self.database}.{self.name}"
        return self.name

    @property
    def column_map(self) -> Dict[str, ColumnInfo]:
        return {col.name: col for col in self.columns}

    @property
    def primary_key(self) -> Tuple[ColumnInfo, ...]:
        return tuple(col for col in self.columns if col.primary_key)


class TableMeta(type):
    """Metaclass that gathers Column descriptors into table metadata."""

    def __new__(mcls, name: str, bases: Tuple[type, ...], namespace: Dict[str, Any], **kwargs: Any) -> "TableMeta":
        columns: Dict[str, Column] = {}
        engine: TableEngine | None = None
        tablename = namespace.get("__tablename__", name.lower())
        database = namespace.get("__database__", None)

        order_by = mcls._normalize_clause(namespace.get("__order_by__"))
        partition_by = mcls._normalize_clause(namespace.get("__partition_by__"))
        sample_by = mcls._normalize_clause(namespace.get("__sample_by__"))
        ttl_clause: str | None = namespace.get("__ttl__", None)
        select_query: Any | None = namespace.get("__select__", None)
        from_table: Any | None = namespace.get("__from_table__", None)
        metadata: Any | None = namespace.get("metadata", None)
        
        # Inherit metadata if not defined locally
        if metadata is None:
            for base in bases:
                if hasattr(base, "metadata"):
                    metadata = base.metadata
                    break

        if from_table is not None and not isinstance(from_table, str):
            if hasattr(from_table, "__tablename__"):
                from_table = from_table.__tablename__
            else:
                from_table = str(from_table)
        
        if select_query is None and from_table is not None:
             # AUTO-GENERATION: Generate Select object instead of string for strict compliance
             # select_query = f"SELECT * FROM {from_table}"
             # We need to construct select().select_from(from_table)
             # Note: select() without arguments implies SELECT * in CHORM? 
             # Select constructor: self._columns = [] -> to_sql() renders "SELECT *"
             # So select().select_from(...) is roughly "SELECT * FROM ..."
             select_query = Select().select_from(from_table)
        
        # Extract engine from namespace
        engine = namespace.get("__engine__")
        if engine is None:
            engine = namespace.get("engine")
        
        # Extract local columns
        for key, value in namespace.items():
            if isinstance(value, Column):
                value.name = key
                columns[key] = value

        # Strict Validation handles for Materialized Views
        to_table_ref: Any | None = namespace.get("__to_table__", None)
        to_table_name: str | None = None

        cls = super().__new__(mcls, name, bases, namespace, **kwargs)

        # Detect if we are creating a MaterializedView
        # We need to know the engine. It might be in namespace or inherited.
        # But for strict validation of attributes defined in THIS class, we check namespace/engine.
        
        # Engine resolution logic duplicated from below for validation context
        # (We strictly validate if the engine is explicitly MaterializedView OR if __to_table__ is set implies MV semantic)
        
        target_engine = engine
        if target_engine is None and bases:
             # Try to find inherited engine
             for base in bases:
                 if hasattr(base, "__table__") and base.__table__.engine:
                     target_engine = base.__table__.engine
                     break
        
        is_mv = isinstance(target_engine, MaterializedView)

        if is_mv:
            # 1. Validation: __select__ must be a Select object (if present)
            # The Pivot requires __select__ for MVs (unless we are just defining a mixin, but usually MV requires it)
            # If generated from older code, it might be string? User said "не принимаем текстом".
            # strict check:
            if select_query is not None:
                if not isinstance(select_query, Select):
                     raise ConfigurationError(
                         f"Invalid '__select__' in MaterializedView '{name}'. Must be a 'chorm.select()' object, got {type(select_query).__name__}."
                     )
            
            # 2. Validation: __to_table__ must be a Table subclass (if present)
            if to_table_ref is not None:
                # Must be a class that has TableMeta metaclass (i.e. is a Table)
                if not isinstance(to_table_ref, TableMeta):
                     raise ConfigurationError(
                         f"Invalid '__to_table__' in MaterializedView '{name}'. Must be a Table class, got {type(to_table_ref).__name__}."
                     )
                to_table_name = to_table_ref.__tablename__
            
            # 3. Column Validation
            if select_query is not None and isinstance(select_query, Select):
                # Extract columns from query
                query_cols = select_query._columns
                if not query_cols: # "SELECT *"
                     # If * is used, validation is impossible without connecting to DB.
                     # We assume user knows what they are doing OR we warn?
                     # User said "порядок и названия ... должно совпадать". 
                     # Only possible if specific columns are selected.
                     pass 
                else: 
                     # Get expected columns
                     expected_cols: Sequence[Any] = []
                     expected_source = ""
                     
                     if to_table_ref is not None:
                         # Scenario A: columns from target table
                         expected_cols = to_table_ref.__table__.columns
                         expected_source = f"target table '{to_table_ref.__name__}'"
                     else:
                         # Scenario B: columns from local definitions
                         # We need to collect valid columns from 'columns' dict (which are Column objects)
                         # We can't reuse 'columns' dict directly because it doesn't have order guaranteed like tuple?
                         # Actually dict follows insertion order in modern Python.
                         # And we should check keys.
                         # But wait, 'columns' dict only has local columns. Inherited ones?
                         # MVs usually don't inherit schema in complex ways, but let's assume local + inherited.
                         # We can't access 'inherited_columns' yet (calculated below).
                         # Let's defer this check until after 'all_columns' is resolved?
                         # Yes. We will move this block AFTER 'all_columns' resolution below.
                         pass
        
        # ... (original super().__new__ called above) ...
        # MOVED super().__new__ to START of this block to ensure CLS exists? 
        # Actually super().__new__ creates the class object.
        # But we were doing validation logic assuming we have 'namespace'.
        
        # REFACTOR: I inserted this logic BEFORE super().__new__ in the replacement block? 
        # No, I replaced the block containing `cls = super().__new__...`.


        # Inherit columns from bases if not overridden
        base_metadata: Iterable[TableMetadata] = (
            getattr(base, "__table__", None) for base in bases if hasattr(base, "__table__")
        )
        inherited_columns: Dict[str, Column] = {}
        inherited_engine: TableEngine | None = None
        
        # Also ensure metadata is set on class if resolved from base
        if metadata is not None and not "metadata" in namespace:
            cls.metadata = metadata

        for metadata_obj in base_metadata:
            if metadata_obj is None:
                continue
            for column_info in metadata_obj.columns:
                if column_info.name not in columns and column_info.name not in inherited_columns:
                    inherited_columns[column_info.name] = column_info.column
            if inherited_engine is None and metadata_obj.engine is not None:
                inherited_engine = metadata_obj.engine
            if not order_by:
                order_by = metadata_obj.order_by
            if not partition_by:
                partition_by = metadata_obj.partition_by
            if not sample_by:
                sample_by = metadata_obj.sample_by
            if ttl_clause is None:
                ttl_clause = metadata_obj.ttl
            if select_query is None:
                select_query = metadata_obj.select_query
            if from_table is None:
                from_table = metadata_obj.from_table

        all_columns = {**inherited_columns, **columns}

        # --- Strict MV Validation Logic ---
        if isinstance(engine, MaterializedView):
             # 1. Validate Types
             if select_query is not None and not isinstance(select_query, Select):
                 raise ConfigurationError(
                     f"Invalid '__select__' in MaterializedView '{name}'. Must be a 'chorm.select()' object, got {type(select_query).__name__}."
                 )
             
             if to_table_ref is not None:
                 if not isinstance(to_table_ref, TableMeta):
                     raise ConfigurationError(
                         f"Invalid '__to_table__' in MaterializedView '{name}'. Must be a Table class, got {type(to_table_ref).__name__}."
                     )
                 to_table_name = to_table_ref.__tablename__

             # 2. Validate Columns
             if select_query is not None and isinstance(select_query, Select):
                 # Get query output columns identifiers
                 query_col_names = []
                 for col in select_query._columns:
                     c_name = None
                     if hasattr(col, "alias") and col.alias:
                         c_name = col.alias
                     elif hasattr(col, "name"):
                         c_name = col.name
                     elif hasattr(col, "to_sql"):
                         # Fallback for simple expressions if no alias?
                         # e.g. Count(x) -> "count(x)".
                         # But target table has specific names.
                         # User requirement: "names (or labels) ... must match".
                         # If it's a raw function call without label, name is ambiguous.
                         pass
                     
                     if c_name is None:
                          # If we can't determine name, and strict mode is on?
                          # We can assume it might fail matching.
                          c_name = "<expr>"
                     query_col_names.append(c_name)
                 
                 # Resolve Expected Columns
                 expected_info = [] # List of (name, source)
                 expected_col_names = []

                 if to_table_ref is not None:
                     # Scenario A: Target Table
                     for col_info in to_table_ref.__table__.columns:
                         expected_col_names.append(col_info.name)
                         expected_info.append(f"'{col_info.name}'")
                     expected_source_name = f"target table '{to_table_ref.__name__}'"
                 else:
                     # Scenario B: Inner Engine (Local Columns)
                     # We use 'all_columns' keys which preserve definition order?
                     # Python dicts preserve insertion order relative to when keys were added.
                     # 'all_columns' = inherited + columns.
                     # This should match the DDL column order.
                     for c_name in all_columns.keys():
                         expected_col_names.append(c_name)
                         expected_info.append(f"'{c_name}'")
                     expected_source_name = f"MV '{name}' schema"

                 # Perform Comparison
                 # If query has '*', skip validation? User said strict. "Select * " is usually discouraged in MVs.
                 # But valid.
                 # If query cols are empty (meaning *), we skip.
                 if query_col_names and not any(n == "*" for n in query_col_names):
                     if len(query_col_names) != len(expected_col_names):
                         raise ConfigurationError(
                             f"Column count mismatch in MaterializedView '{name}'. "
                             f"Expected {len(expected_col_names)} columns from {expected_source_name} "
                             f"({', '.join(expected_info)}), but '__select__' query returns {len(query_col_names)} columns."
                         )
                     
                     for idx, (exp, got) in enumerate(zip(expected_col_names, query_col_names)):
                         if exp != got:
                            raise ConfigurationError(
                                f"Column mismatch in MaterializedView '{name}'. "
                                f"Expected column '{exp}' at index {idx} from {expected_source_name}, "
                                f"but got '{got}' from '__select__' query."
                            )

        if engine is None:
            engine = inherited_engine

        column_infos = tuple(ColumnInfo(name=col_name, column=column) for col_name, column in all_columns.items())

        cls.__table__ = TableMetadata(
            name=tablename,
            columns=column_infos,
            engine=engine,
            database=database,
            order_by=tuple(order_by),
            partition_by=tuple(partition_by),
            sample_by=tuple(sample_by),
            ttl=ttl_clause,
            select_query=select_query,
            from_table=from_table,
            to_table=to_table_name,
        )

        cls.__abstract__ = namespace.get("__abstract__", False)
        
        # Register in metadata
        if not cls.__abstract__ and metadata is not None:
            metadata.tables[tablename] = cls.__table__

        cls._decl_class_registry: Dict[str, Type["Table"]] = {}
        owner = mcls._find_registry_owner(bases)
        if owner is not None:
            owner._decl_class_registry[cls.__name__] = cls

        return cls

    @staticmethod
    def _normalize_clause(value: Any) -> Tuple[str, ...]:
        if not value:
            return ()
        if isinstance(value, str):
            return (value,)
        return tuple(value)
    
    @staticmethod
    def _find_registry_owner(bases: Tuple[type, ...]) -> Type["Table"] | None:
        for base in bases:
            if hasattr(base, "_decl_class_registry"):
                return base  # type: ignore[return-value]
        return None


class Table(metaclass=TableMeta):
    """Declarative base class for ClickHouse tables."""

    __tablename__: str | None = None
    __database__: str | None = None  # Optional: if set, uses database.table format
    __table__: TableMetadata
    __abstract__ = True
    _decl_class_registry: Dict[str, Type["Table"]] = {}
    metadata: MetaData = MetaData()

    def __init__(self, **values: Any) -> None:
        column_map = self.__table__.column_map
        unknown = set(values) - set(column_map)
        if unknown:
            raise DeclarativeError(f"Unknown columns for {self.__class__.__name__}: {sorted(unknown)}")
        for col_name, column_info in column_map.items():
            if col_name in values:
                setattr(self, col_name, values[col_name])
            else:
                # Trigger default generation via descriptor
                getattr(self, col_name)

    def validate(self) -> None:
        """Validate all column values using their validators.

        Raises:
            ValidationError: If any column validation fails

        Example:
            user = User(name="Alice", email="alice@example.com")
            user.validate()  # Validates all columns
        """
        for col_info in self.__table__.columns:
            col_name = col_info.name
            column = col_info.column
            value = getattr(self, col_name)

            # Check nullable
            if value is None and not column.nullable:
                raise ValidationError(f"Column '{col_name}' is not nullable", col_name, value)

            # Apply validators if value is not None
            if value is not None and column.validators:
                validate_value(value, column.validators, col_name)

    def to_dict(self) -> Dict[str, Any]:
        """Return a mapping of column names to values."""
        return {col.name: getattr(self, col.name) for col in self.__table__.columns}

    def __repr__(self) -> str:
        values = ", ".join(f"{k}={v!r}" for k, v in self.to_dict().items())
        return f"{self.__class__.__name__}({values})"

    @classmethod
    def _collect_tables(cls) -> Tuple[Type["Table"], ...]:
        tables: Tuple[Type["Table"], ...] = ()
        if not cls.__abstract__:
            tables += (cls,)
        for child in cls._decl_class_registry.values():
            tables += child._collect_tables()
        return tables

    @classmethod
    def create_table(cls, *, exists_ok: bool = False) -> str:
        if cls.__abstract__:
            raise DeclarativeError(f"Cannot create table for abstract class {cls.__name__}")
        if cls.__table__.engine is None:
            raise DeclarativeError(f"Table {cls.__name__} does not define an engine")


        return format_ddl(cls.__table__, if_not_exists=exists_ok)

    @classmethod
    def create_all(cls, *, exists_ok: bool = False) -> str:
        statements = [table_cls.create_table(exists_ok=exists_ok) for table_cls in cls._collect_tables()]
        return ";\n".join(statements) if statements else ""


__all__ = [
    "Column",
    "ColumnInfo",
    "DeclarativeError",
    "get_qualified_table_name",
    "Table",
    "TableMeta",
    "TableMetadata",
]
