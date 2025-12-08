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
from chorm.exceptions import ConfigurationError, ValidationError
from chorm.validators import Validator, validate_value

# Backward compatibility alias
DeclarativeError = ConfigurationError


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

    def to_sql(self) -> str:
        if self.name is None:
            raise DeclarativeError("Column not bound to class")
        if hasattr(self, "table") and hasattr(self.table, "__tablename__") and self.table.__tablename__:
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
    order_by: Tuple[str, ...] = ()
    partition_by: Tuple[str, ...] = ()
    sample_by: Tuple[str, ...] = ()
    ttl: str | None = None

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

        order_by = mcls._normalize_clause(namespace.get("__order_by__"))
        partition_by = mcls._normalize_clause(namespace.get("__partition_by__"))
        sample_by = mcls._normalize_clause(namespace.get("__sample_by__"))
        ttl_clause: str | None = namespace.get("__ttl__", None)

        # Handle Metadata - check namespace or inherited
        metadata = namespace.get("metadata")
        if metadata is None:
            for base in bases:
                if hasattr(base, "metadata"):
                    metadata = base.metadata
                    break

        for attr_name, attr_value in namespace.items():
            if isinstance(attr_value, Column):
                columns[attr_name] = attr_value
            elif isinstance(attr_value, TableEngine):
                if engine is not None and attr_name != "engine":
                    continue
                engine = attr_value

        cls = super().__new__(mcls, name, bases, namespace, **kwargs)

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

        all_columns = {**inherited_columns, **columns}

        if engine is None:
            engine = inherited_engine

        column_infos = tuple(ColumnInfo(name=col_name, column=column) for col_name, column in all_columns.items())

        cls.__table__ = TableMetadata(
            name=tablename,
            columns=column_infos,
            engine=engine,
            order_by=tuple(order_by),
            partition_by=tuple(partition_by),
            sample_by=tuple(sample_by),
            ttl=ttl_clause,
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
    "Table",
    "TableMeta",
    "TableMetadata",
]
