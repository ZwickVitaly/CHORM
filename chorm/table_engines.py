"""ClickHouse table engine classes for ORM-style configuration."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple, Type

from chorm.exceptions import ConfigurationError

# Backward compatibility alias
EngineConfigurationError = ConfigurationError


class TableEngine:
    """Base class for ClickHouse table engine descriptors."""

    engine_name: str = ""
    arg_names: Tuple[str, ...] = ()
    required_args: Tuple[str, ...] = ()
    setting_names: Tuple[str, ...] = ()
    required_settings: Tuple[str, ...] = ()
    default_settings: Mapping[str, Any] = {}

    def __init__(self, *args: Any, settings: Mapping[str, Any] | None = None, **kwargs: Any) -> None:
        if not self.engine_name:
            raise TypeError("TableEngine subclasses must define engine_name")
        if args and kwargs:
            raise EngineConfigurationError(
                f"{self.__class__.__name__} expects either positional or keyword arguments, not both"
            )
        self._args = self._collect_args(args, kwargs)
        self._settings = self._collect_settings(settings or {})

    def _collect_args(self, args: Tuple[Any, ...], kwargs: Dict[str, Any]) -> Tuple[Any, ...]:
        values: list[Any] = []

        if kwargs:
            unknown = set(kwargs) - set(self.arg_names)
            if unknown:
                raise EngineConfigurationError(f"Unknown engine arguments {sorted(unknown)} for {self.engine_name}")
            for name in self.arg_names:
                values.append(kwargs.get(name))
        else:
            if len(args) > len(self.arg_names):
                raise EngineConfigurationError(
                    f"{self.engine_name} accepts at most {len(self.arg_names)} positional arguments; "
                    f"got {len(args)}"
                )
            values.extend(args)
            while len(values) < len(self.arg_names):
                values.append(None)

        for name, value in zip(self.arg_names, values):
            if name in self.required_args and value is None:
                raise EngineConfigurationError(f"Argument '{name}' is required for engine {self.engine_name}")

        return tuple(values)

    def _collect_settings(self, settings: Mapping[str, Any]) -> Dict[str, Any]:
        allowed = set(self.setting_names) | set(self.default_settings)
        unknown = set(settings) - allowed
        if unknown:
            raise EngineConfigurationError(f"Unknown settings {sorted(unknown)} for engine {self.engine_name}")

        result = dict(self.default_settings)
        result.update(settings)

        for key in self.required_settings:
            if key not in result:
                raise EngineConfigurationError(f"Setting '{key}' is required for engine {self.engine_name}")

        return result

    @property
    def args(self) -> Tuple[Any, ...]:
        """Arguments supplied to the engine, padded with ``None`` for omissions."""
        return self._args

    @property
    def settings(self) -> Dict[str, Any]:
        """Validated engine settings."""
        return dict(self._settings)

    def format_clause(self) -> str:
        """Render an ``ENGINE`` clause snippet for the current configuration."""
        args = list(self._args)
        while args and args[-1] is None:
            args.pop()
        if args:
            arg_sql = ", ".join(str(arg) for arg in args)
            clause = f"{self.engine_name}({arg_sql})"
        else:
            clause = self.engine_name

        # Add TTL clause if present (only for MergeTree family usually, but handled generically here)
        if hasattr(self, "ttl") and self.ttl:
            clause = f"{clause} TTL {self.ttl}"

        if self._settings:
            settings_sql = ", ".join(f"{key} = {self._format_setting(value)}" for key, value in self._settings.items())
            clause = f"{clause} SETTINGS {settings_sql}"

        return clause

    def _format_setting(self, value: Any) -> str:
        if isinstance(value, str):
            return repr(value)
        return str(value)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"{self.__class__.__name__}(args={self._args!r}, settings={self._settings!r})"


# --- MergeTree family -----------------------------------------------------------


class MergeTree(TableEngine):
    engine_name = "MergeTree"
    setting_names = ("index_granularity", "index_granularity_bytes", "enable_mixed_granularity_parts")

    def __init__(self, *args, ttl: str | None = None, **kwargs):
        self.ttl = ttl
        super().__init__(*args, **kwargs)


class ReplacingMergeTree(TableEngine):
    engine_name = "ReplacingMergeTree"
    arg_names = ("version_column",)
    setting_names = ("index_granularity", "index_granularity_bytes", "enable_mixed_granularity_parts")

    def __init__(self, *args, ttl: str | None = None, **kwargs):
        self.ttl = ttl
        super().__init__(*args, **kwargs)


class SummingMergeTree(TableEngine):
    engine_name = "SummingMergeTree"
    arg_names = ("columns",)
    setting_names = ("index_granularity", "index_granularity_bytes", "enable_mixed_granularity_parts")

    def __init__(self, *args, ttl: str | None = None, **kwargs):
        self.ttl = ttl
        super().__init__(*args, **kwargs)


class AggregatingMergeTree(TableEngine):
    engine_name = "AggregatingMergeTree"
    setting_names = ("index_granularity", "index_granularity_bytes", "enable_mixed_granularity_parts")

    def __init__(self, *args, ttl: str | None = None, **kwargs):
        self.ttl = ttl
        super().__init__(*args, **kwargs)


class CollapsingMergeTree(TableEngine):
    engine_name = "CollapsingMergeTree"
    arg_names = ("sign_column",)
    required_args = ("sign_column",)
    setting_names = ("index_granularity", "index_granularity_bytes", "enable_mixed_granularity_parts")

    def __init__(self, *args, ttl: str | None = None, **kwargs):
        self.ttl = ttl
        super().__init__(*args, **kwargs)


class VersionedCollapsingMergeTree(TableEngine):
    engine_name = "VersionedCollapsingMergeTree"
    arg_names = ("sign_column", "version_column")
    required_args = ("sign_column", "version_column")

    def __init__(self, *args, ttl: str | None = None, **kwargs):
        self.ttl = ttl
        super().__init__(*args, **kwargs)


class GraphiteMergeTree(TableEngine):
    engine_name = "GraphiteMergeTree"
    arg_names = ("config_element",)
    required_args = ("config_element",)

    def __init__(self, *args, ttl: str | None = None, **kwargs):
        self.ttl = ttl
        super().__init__(*args, **kwargs)


class ReplicatedMergeTree(TableEngine):
    engine_name = "ReplicatedMergeTree"
    arg_names = ("zookeeper_path", "replica_name")
    required_args = ("zookeeper_path", "replica_name")

    def __init__(self, *args, ttl: str | None = None, **kwargs):
        self.ttl = ttl
        super().__init__(*args, **kwargs)


class ReplicatedReplacingMergeTree(TableEngine):
    engine_name = "ReplicatedReplacingMergeTree"
    arg_names = ("zookeeper_path", "replica_name", "version_column")
    required_args = ("zookeeper_path", "replica_name")

    def __init__(self, *args, ttl: str | None = None, **kwargs):
        self.ttl = ttl
        super().__init__(*args, **kwargs)


class ReplicatedSummingMergeTree(TableEngine):
    engine_name = "ReplicatedSummingMergeTree"
    arg_names = ("zookeeper_path", "replica_name", "columns")
    required_args = ("zookeeper_path", "replica_name")

    def __init__(self, *args, ttl: str | None = None, **kwargs):
        self.ttl = ttl
        super().__init__(*args, **kwargs)


class ReplicatedAggregatingMergeTree(TableEngine):
    engine_name = "ReplicatedAggregatingMergeTree"
    arg_names = ("zookeeper_path", "replica_name")
    required_args = ("zookeeper_path", "replica_name")

    def __init__(self, *args, ttl: str | None = None, **kwargs):
        self.ttl = ttl
        super().__init__(*args, **kwargs)


class ReplicatedCollapsingMergeTree(TableEngine):
    engine_name = "ReplicatedCollapsingMergeTree"
    arg_names = ("zookeeper_path", "replica_name", "sign_column")
    required_args = ("zookeeper_path", "replica_name", "sign_column")

    def __init__(self, *args, ttl: str | None = None, **kwargs):
        self.ttl = ttl
        super().__init__(*args, **kwargs)


class ReplicatedVersionedCollapsingMergeTree(TableEngine):
    engine_name = "ReplicatedVersionedCollapsingMergeTree"
    arg_names = ("zookeeper_path", "replica_name", "sign_column", "version_column")
    required_args = ("zookeeper_path", "replica_name", "sign_column", "version_column")

    def __init__(self, *args, ttl: str | None = None, **kwargs):
        self.ttl = ttl
        super().__init__(*args, **kwargs)


class ReplicatedGraphiteMergeTree(TableEngine):
    engine_name = "ReplicatedGraphiteMergeTree"
    arg_names = ("zookeeper_path", "replica_name", "config_element")
    required_args = ("zookeeper_path", "replica_name", "config_element")

    def __init__(self, *args, ttl: str | None = None, **kwargs):
        self.ttl = ttl
        super().__init__(*args, **kwargs)


# --- Log engines ----------------------------------------------------------------


class Log(TableEngine):
    engine_name = "Log"


class TinyLog(TableEngine):
    engine_name = "TinyLog"


class StripeLog(TableEngine):
    engine_name = "StripeLog"


# --- Special engines ------------------------------------------------------------


class Memory(TableEngine):
    engine_name = "Memory"


class File(TableEngine):
    engine_name = "File"
    arg_names = ("format",)
    required_args = ("format",)


class Null(TableEngine):
    engine_name = "Null"


class Set(TableEngine):
    engine_name = "Set"


class Join(TableEngine):
    engine_name = "Join"


class View(TableEngine):
    engine_name = "View"


class MaterializedView(TableEngine):
    """Materialized View engine (marker).
    
    This is a special engine marker for defining Materialized Views.
    It is not a real ClickHouse table engine in the "ENGINE = ..." sense when used with "TO table",
    but serves as the configuration for generating "CREATE MATERIALIZED VIEW" statements.
    
    Syntax: MaterializedView(to_table="target_table"[, populate=True])
    """
    engine_name = "MaterializedView"
    arg_names = ("to_table",)
    
    def __init__(
        self,
        to_table: str | Any | None = None,
        engine: "TableEngine | None" = None,
        populate: bool = False,
        *args,
        **kwargs,
    ):
        # Resolve to_table if it's a class (Table model)
        if to_table is not None and not isinstance(to_table, str):
            if hasattr(to_table, "__tablename__"):
                to_table = to_table.__tablename__
            else:
                # Fallback or error? defaulting to str conversion might be risky if it's just 'Model'
                to_table = str(to_table)

        if to_table and populate:
            raise ConfigurationError(
                "Cannot use 'populate=True' with 'to_table' in MaterializedView. "
                "ClickHouse does not support POPULATE when TO table is specified."
            )
        
        if to_table and engine:
            raise ConfigurationError(
                "Cannot specify storage 'engine' when 'to_table' is used in MaterializedView. "
                "The target table determines the storage engine."
            )

        if to_table is None and engine is None:
             # Depending on use case, might default to MergeTree or fail.
             # For now, let's allow it but DDL generation might fail or use default if handled there.
             # But strictly, one should be present.
             pass

        self.to_table = to_table
        self.inner_engine = engine
        self.populate = populate
        
        # Initialize base with to_table if present, so it's stored in _args if needed, 
        # but we ignore it for formatting mostly.
        if to_table:
            super().__init__(to_table, *args, **kwargs)
        else:
            super().__init__(*args, **kwargs)



class Distributed(TableEngine):
    """Distributed table engine for distributed queries across cluster.
    
    Syntax: Distributed(cluster, database, table[, sharding_key[, policy_name]])
    
    Args:
        cluster: Cluster name (required)
        database: Remote database name (required)
        table: Remote table name (required)
        sharding_key: Sharding key expression (optional)
        policy_name: Sharding policy name (optional)
    
    Example:
        Distributed(cluster="my_cluster", database="default", table="users")
        Distributed(cluster="my_cluster", database="default", table="users", 
                   sharding_key="rand()")
    """
    engine_name = "Distributed"
    arg_names = ("cluster", "database", "table", "sharding_key", "policy_name")
    required_args = ("cluster", "database", "table")


class Kafka(TableEngine):
    engine_name = "Kafka"


class MySQL(TableEngine):
    engine_name = "MySQL"
    arg_names = ("host", "database", "table", "user", "password")
    required_args = ("host", "database", "table", "user", "password")


class PostgreSQL(TableEngine):
    engine_name = "PostgreSQL"
    arg_names = ("host", "database", "table", "user", "password")
    required_args = ("host", "database", "table", "user", "password")


class ODBC(TableEngine):
    engine_name = "ODBC"
    arg_names = ("dsn", "database", "table")
    required_args = ("dsn", "database", "table")


class JDBC(TableEngine):
    engine_name = "JDBC"
    arg_names = ("driver", "uri", "table")
    required_args = ("driver", "uri", "table")


ENGINE_CLASSES: Dict[str, Type[TableEngine]] = {
    cls.engine_name: cls
    for cls in [
        MergeTree,
        ReplacingMergeTree,
        SummingMergeTree,
        AggregatingMergeTree,
        CollapsingMergeTree,
        VersionedCollapsingMergeTree,
        GraphiteMergeTree,
        ReplicatedMergeTree,
        ReplicatedReplacingMergeTree,
        ReplicatedSummingMergeTree,
        ReplicatedAggregatingMergeTree,
        ReplicatedCollapsingMergeTree,
        ReplicatedVersionedCollapsingMergeTree,
        ReplicatedGraphiteMergeTree,
        Log,
        TinyLog,
        StripeLog,
        Memory,
        File,
        Null,
        Set,
        Join,
        View,
        MaterializedView,
        Distributed,
        Kafka,
        MySQL,
        PostgreSQL,
        ODBC,
        JDBC,
    ]
}


__all__ = [
    "AggregatingMergeTree",
    "CollapsingMergeTree",
    "Distributed",
    "EngineConfigurationError",
    "ENGINE_CLASSES",
    "File",
    "GraphiteMergeTree",
    "JDBC",
    "Join",
    "Kafka",
    "Log",
    "MaterializedView",
    "Memory",
    "MergeTree",
    "MySQL",
    "Null",
    "ODBC",
    "PostgreSQL",
    "ReplicatedAggregatingMergeTree",
    "ReplicatedCollapsingMergeTree",
    "ReplicatedGraphiteMergeTree",
    "ReplicatedMergeTree",
    "ReplicatedReplacingMergeTree",
    "ReplicatedSummingMergeTree",
    "ReplicatedVersionedCollapsingMergeTree",
    "ReplacingMergeTree",
    "Set",
    "StripeLog",
    "SummingMergeTree",
    "TableEngine",
    "TinyLog",
    "VersionedCollapsingMergeTree",
    "View",
]
