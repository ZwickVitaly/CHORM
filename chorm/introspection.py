"""Schema introspection utilities for CHORM."""

from typing import List, Dict, Any, Optional
from datetime import datetime
import clickhouse_connect


class TableIntrospector:
    """Introspect ClickHouse tables to extract schema information."""

    def __init__(self, client):
        """Initialize introspector with ClickHouse client."""
        self.client = client

    def get_tables(self, database: str = "default") -> List[str]:
        """Get list of all tables in database."""
        query = f"""
            SELECT name 
            FROM system.tables 
            WHERE database = '{database}' 
            AND engine NOT LIKE '%View%'
            ORDER BY name
        """
        result = self.client.query(query)
        return [row[0] for row in result.result_rows]

    def get_table_info(self, table: str, database: str = "default") -> Dict[str, Any]:
        """Get complete table information."""
        # Get table metadata
        query = f"""
            SELECT 
                engine,
                engine_full,
                partition_key,
                sorting_key,
                primary_key
            FROM system.tables
            WHERE database = '{database}' AND name = '{table}'
        """
        result = self.client.query(query)
        if not result.result_rows:
            raise ValueError(f"Table {table} not found in database {database}")

        row = result.result_rows[0]

        return {
            "name": table,
            "engine": row[0],
            "engine_full": row[1],
            "partition_key": row[2],
            "sorting_key": row[3],
            "primary_key": row[4],
            "columns": self.get_columns(table, database),
        }

    def get_columns(self, table: str, database: str = "default") -> List[Dict[str, Any]]:
        """Get column definitions for a table."""
        query = f"""
            SELECT 
                name,
                type,
                default_kind,
                default_expression,
                comment
            FROM system.columns
            WHERE database = '{database}' AND table = '{table}'
            ORDER BY position
        """
        result = self.client.query(query)

        columns = []
        for row in result.result_rows:
            columns.append(
                {
                    "name": row[0],
                    "type": row[1],
                    "default_kind": row[2],
                    "default_expression": row[3],
                    "comment": row[4],
                }
            )

        return columns


class ModelGenerator:
    """Generate CHORM model code from table information."""

    TYPE_MAPPING = {
        "UInt8": "UInt8()",
        "UInt16": "UInt16()",
        "UInt32": "UInt32()",
        "UInt64": "UInt64()",
        "UInt128": "UInt128()",
        "UInt256": "UInt256()",
        "Int8": "Int8()",
        "Int16": "Int16()",
        "Int32": "Int32()",
        "Int64": "Int64()",
        "Int128": "Int128()",
        "Int256": "Int256()",
        "Float32": "Float32()",
        "Float64": "Float64()",
        "String": "String()",
        "FixedString": "FixedString",  # Needs parameter
        "Date": "Date()",
        "Date32": "Date32()",
        "DateTime": "DateTime()",
        "DateTime64": "DateTime64",  # Needs precision
        "UUID": "UUID()",
        "IPv4": "IPv4()",
        "IPv6": "IPv6()",
        "Bool": "Bool()",
        "Decimal": "Decimal",  # Needs precision/scale
    }

    def __init__(self):
        """Initialize model generator."""
        self.imports = set()

    def map_type(self, ch_type: str) -> str:
        """Map ClickHouse type to CHORM type."""
        # Handle Nullable
        if ch_type.startswith("Nullable("):
            inner = ch_type[9:-1]
            self.imports.add("Nullable")
            return f"Nullable({self.map_type(inner)})"

        # Handle Array
        if ch_type.startswith("Array("):
            inner = ch_type[6:-1]
            self.imports.add("Array")
            return f"Array({self.map_type(inner)})"

        # Handle LowCardinality
        if ch_type.startswith("LowCardinality("):
            inner = ch_type[15:-1]
            self.imports.add("LowCardinality")
            return f"LowCardinality({self.map_type(inner)})"

        # Handle Map
        if ch_type.startswith("Map("):
            parts = ch_type[4:-1].split(",", 1)
            key_type = self.map_type(parts[0].strip())
            val_type = self.map_type(parts[1].strip())
            self.imports.add("Map")
            return f"Map({key_type}, {val_type})"

        # Handle Tuple
        if ch_type.startswith("Tuple("):
            self.imports.add("Tuple")
            return f"String()  # TODO: Define Tuple structure from: {ch_type}"

        # Handle FixedString
        if ch_type.startswith("FixedString("):
            size = ch_type[12:-1]
            self.imports.add("FixedString")
            return f"FixedString({size})"

        # Handle DateTime64
        if ch_type.startswith("DateTime64("):
            precision = ch_type[11:-1].split(",")[0]
            self.imports.add("DateTime64")
            return f"DateTime64(precision={precision})"

        # Handle Decimal
        if (
            ch_type.startswith("Decimal(")
            or ch_type.startswith("Decimal32(")
            or ch_type.startswith("Decimal64(")
            or ch_type.startswith("Decimal128(")
        ):
            self.imports.add("Decimal")
            # Extract precision and scale if possible
            import re

            match = re.search(r"Decimal\d*\((\d+),\s*(\d+)\)", ch_type)
            if match:
                precision, scale = match.groups()
                return f"Decimal({precision}, {scale})"
            else:
                return f"Decimal(18, 2)  # TODO: Verify precision/scale"

        # Handle Enum
        if ch_type.startswith("Enum8(") or ch_type.startswith("Enum16("):
            self.imports.add("Enum8" if "Enum8" in ch_type else "Enum16")
            return f"String()  # TODO: Use Enum8/Enum16 with values from: {ch_type}"

        # Simple types
        base_type = ch_type.split("(")[0]
        if base_type in self.TYPE_MAPPING:
            # Add to imports
            self.imports.add(base_type)
            return self.TYPE_MAPPING[base_type]

        # Unknown type
        return f"String()  # TODO: Unknown type: {ch_type}"

    def generate_model(self, table_info: Dict[str, Any]) -> str:
        """Generate model class code for a table."""
        class_name = self._to_class_name(table_info["name"])

        lines = []
        lines.append(f"class {class_name}(Table):")
        lines.append(f"    __tablename__ = '{table_info['name']}'")

        # Engine
        engine = self._map_engine(table_info["engine"])
        lines.append(f"    __engine__ = {engine}")

        # ORDER BY
        if table_info["sorting_key"]:
            order_by = self._parse_key_expression(table_info["sorting_key"])
            lines.append(f"    __order_by__ = {order_by}")

        # PARTITION BY
        if table_info["partition_key"]:
            lines.append(f"    __partition_by__ = '{table_info['partition_key']}'")

        lines.append("")

        # Columns
        for col in table_info["columns"]:
            col_type = self.map_type(col["type"])
            comment = f"  # {col['comment']}" if col["comment"] else ""
            lines.append(f"    {col['name']} = Column({col_type}){comment}")

        return "\n".join(lines)

    def _to_class_name(self, table_name: str) -> str:
        """Convert table name to PascalCase class name."""
        parts = table_name.replace("-", "_").split("_")
        return "".join(word.capitalize() for word in parts)

    def _map_engine(self, engine: str) -> str:
        """Map engine name to CHORM engine class."""
        if "MergeTree" in engine:
            if "Replacing" in engine:
                return "ReplacingMergeTree()"
            elif "Summing" in engine:
                return "SummingMergeTree()"
            elif "Aggregating" in engine:
                return "AggregatingMergeTree()"
            elif "Collapsing" in engine:
                return "CollapsingMergeTree()"
            else:
                return "MergeTree()"
        return f"MergeTree()  # TODO: Engine: {engine}"

    def _parse_key_expression(self, expr: str) -> str:
        """Parse ORDER BY/PRIMARY KEY expression to list."""
        if not expr:
            return "[]"

        # Simple case: comma-separated column names
        parts = [p.strip() for p in expr.split(",")]
        return str(parts)

    def generate_imports(self) -> str:
        """Generate import statements."""
        lines = []
        lines.append("from chorm import Table, Column")

        # Type imports
        if self.imports:
            type_imports = sorted(self.imports)
            lines.append(f"from chorm.types import {', '.join(type_imports)}")

        # Engine imports
        lines.append("from chorm.table_engines import MergeTree, ReplacingMergeTree, SummingMergeTree")

        return "\n".join(lines)

    def generate_file(self, tables_info: List[Dict[str, Any]]) -> str:
        """Generate complete models.py file."""
        lines = []
        lines.append('"""')
        lines.append("Generated by chorm-cli introspect")
        lines.append(f'Generated at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        lines.append('"""')
        lines.append("")

        # Generate all models first to collect imports
        models = []
        for table_info in tables_info:
            models.append(self.generate_model(table_info))

        # Add imports
        lines.append(self.generate_imports())
        lines.append("")
        lines.append("")

        # Add models
        for model in models:
            lines.append(model)
            lines.append("")
            lines.append("")

        return "\n".join(lines)
