"""Schema introspection utilities for CHORM."""

from typing import List, Dict, Any, Optional
from datetime import datetime
import clickhouse_connect
import re


class TableIntrospector:
    """Introspect ClickHouse tables to extract schema information."""

    def __init__(self, client):
        """Initialize introspector with ClickHouse client."""
        self.client = client

    def get_tables(self, database: str = "default") -> List[str]:
        """Get list of all tables in database."""
        query = """
            SELECT name 
            FROM system.tables 
            WHERE database = %(database)s 
            AND engine NOT LIKE '%View%'
            ORDER BY name
        """
        result = self.client.query(query, parameters={"database": database})
        return [row[0] for row in result.result_rows]

    def get_table_info(self, table: str, database: str = "default") -> Dict[str, Any]:
        """Get complete table information."""
        # Get table metadata
        query = """
            SELECT 
                engine,
                engine_full,
                partition_key,
                sorting_key,
                primary_key
            FROM system.tables
            WHERE database = %(database)s AND name = %(table)s
        """
        result = self.client.query(query, parameters={"database": database, "table": table})
        if not result.result_rows:
            raise ValueError(f"Table {table} not found in database {database}")

        row = result.result_rows[0]
        
        # Get columns - this can return empty list if table is Distributed or has no columns
        columns = self.get_columns(table, database)

        return {
            "name": table,
            "engine": row[0],
            "engine_full": row[1],
            "partition_key": row[2],
            "sorting_key": row[3],
            "primary_key": row[4],
            "columns": columns,
        }

    def get_columns(self, table: str, database: str = "default") -> List[Dict[str, Any]]:
        """Get column definitions for a table."""
        query = """
            SELECT 
                name,
                type,
                default_kind,
                default_expression,
                comment,
                compression_codec
            FROM system.columns
            WHERE database = %(database)s AND table = %(table)s
            ORDER BY position
        """
        result = self.client.query(query, parameters={"database": database, "table": table})

        columns = []
        for row in result.result_rows:
            columns.append(
                {
                    "name": row[0],
                    "type": row[1],
                    "default_kind": row[2],
                    "default_expression": row[3],
                    "comment": row[4],
                    "codec": row[5],
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

        self.engines_used = set()  # Track which engines are used
        self.codecs_used = set()  # Track which codecs are used

    def map_type(self, ch_type: str) -> str:
        """Map ClickHouse type to CHORM type."""
        if not ch_type:
            return "String()  # TODO: Empty type"
        
        # Normalize whitespace
        ch_type = ch_type.strip()
        
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

        # Handle AggregateFunction
        if ch_type.startswith("AggregateFunction("):
            # Parse: AggregateFunction(func_name, arg_types...)
            # Examples:
            #   AggregateFunction(sum, UInt64)
            #   AggregateFunction(anyIf, String, UInt8)
            #   AggregateFunction(quantiles(0.5, 0.9), UInt64)
            inner = ch_type[18:-1]  # Remove "AggregateFunction(" and ")"
            
            # Parse function name and arguments
            # Need to handle nested parentheses for functions like quantiles(0.5, 0.9)
            parts = []
            depth = 0
            current_part = ""
            
            for char in inner:
                if char == "(":
                    depth += 1
                    current_part += char
                elif char == ")":
                    depth -= 1
                    current_part += char
                elif char == "," and depth == 0:
                    if current_part.strip():
                        parts.append(current_part.strip())
                    current_part = ""
                else:
                    current_part += char
            
            # Add last part
            if current_part.strip():
                parts.append(current_part.strip())
            
            # First part is function name (may include parameters like quantiles(0.5, 0.9))
            # Remaining parts are argument types
            func_name = parts[0] if parts else ""
            arg_types = parts[1:] if len(parts) > 1 else []
            
            # Map argument types to CHORM types
            mapped_arg_types = [self.map_type(arg_type) for arg_type in arg_types]
            
            # Add AggregateFunction to imports (alias for AggregateFunctionType)
            self.imports.add("AggregateFunction")
            # Add func to imports for function references
            self.imports.add("func")
            # Need to import func from chorm.sql.expression, but imports are from chorm.types
            # So we'll add it to a separate imports set or handle in generate_imports
            
            # Map function name to func namespace
            # Parse function name to extract base name and parameters
            func_expr = self._map_function_to_func(func_name)
            
            # Build AggregateFunction call using func namespace
            if mapped_arg_types:
                arg_types_str = ", ".join(mapped_arg_types)
                return f'AggregateFunction({func_expr}, {arg_types_str})'
            else:
                return f'AggregateFunction({func_expr})'

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

        # Engine - use engine_full for Distributed and other engines with parameters
        engine = self._map_engine(table_info["engine"], table_info.get("engine_full"))
        lines.append(f"    __engine__ = {engine}")

        # ORDER BY
        if table_info["sorting_key"]:
            order_by = self._parse_key_expression(table_info["sorting_key"])
            lines.append(f"    __order_by__ = {order_by}")

        # PARTITION BY
        partition_key = table_info.get("partition_key")
        if partition_key and isinstance(partition_key, str) and partition_key.strip():
            # Escape single quotes in partition_key
            safe_partition_key = partition_key.replace("'", "\\'")
            lines.append(f"    __partition_by__ = '{safe_partition_key}'")

        lines.append("")

        # Columns
        for col in table_info["columns"]:
            col_type = self.map_type(col["type"])
            
            # Handle comments: column comment and TODO comments from map_type
            # Comments from map_type are already included in col_type string
            # Column comment is separate
            column_comment = f"  # {col['comment']}" if col["comment"] else ""
            
            # Handle codec
            codec_arg = ""
            if col.get("codec"):
                # ClickHouse returns CODEC(ZSTD(1)), we need to extract ZSTD(1)
                codec_val = col["codec"]
                if codec_val.startswith("CODEC(") and codec_val.endswith(")"):
                     codec_val = codec_val[6:-1]
                
                # Only add if not empty
                if codec_val:
                    # Parse codec string to Python expression
                    codec_expr = self._parse_codec_expression(codec_val)
                    if codec_expr:
                         codec_arg = f', codec={codec_expr}'
                    else:
                         codec_arg = f', codec="{codec_val}"' # Fallback to string if parsing fails or unknown
            
            # Check if col_type already has a comment (from TODO in map_type)
            if "  # TODO:" in col_type:
                # Split type expression and comment
                type_expr, todo_comment = col_type.split("  # TODO:", 1)
                todo_comment = f"  # TODO:{todo_comment}"  # Remove extra space
                # Ensure type_expr has closing paren
                if not type_expr.endswith(")"):
                    type_expr = type_expr + ")"
                # Combine: Column(type_expr, codec="...") + todo_comment + column_comment
                if column_comment:
                     lines.append(f"    {col['name']} = Column({type_expr}{codec_arg}){todo_comment}{column_comment}")
                else:
                     lines.append(f"    {col['name']} = Column({type_expr}{codec_arg}){todo_comment}")
            else:
                # No TODO comment, just use col_type as-is
                # Ensure proper closing paren
                if not col_type.endswith(")"):
                    col_type = col_type + ")"
                lines.append(f"    {col['name']} = Column({col_type}{codec_arg}){column_comment}")

        return "\n".join(lines)

    def _to_class_name(self, table_name: str) -> str:
        """Convert table name to PascalCase class name."""
        parts = table_name.replace("-", "_").split("_")
        return "".join(word.capitalize() for word in parts)

    def _map_engine(self, engine: str, engine_full: Optional[str] = None) -> str:
        """Map engine name to CHORM engine class.
        
        Args:
            engine: Engine name (e.g., "Distributed", "MergeTree")
            engine_full: Full engine definition with parameters (e.g., "Distributed(cluster, database, table)")
        """
        # Check for Distributed engine
        if engine and engine.strip() == "Distributed":
            self.engines_used.add("Distributed")
            if engine_full:
                return self._map_distributed_engine(engine_full)
            else:
                return "Distributed(cluster='...', database='...', table='...')  # TODO: engine_full missing"
        elif engine_full and engine_full.strip().startswith("Distributed("):
            # Fallback: check engine_full if engine field is inconsistent
            self.engines_used.add("Distributed")
            return self._map_distributed_engine(engine_full)
        elif engine and "MergeTree" in engine:
            if "Replacing" in engine:
                self.engines_used.add("ReplacingMergeTree")
                if engine_full and engine_full.strip().startswith("ReplacingMergeTree("):
                    return self._map_replacing_mergetree_engine(engine_full)
                return "ReplacingMergeTree()"
            elif "Summing" in engine:
                self.engines_used.add("SummingMergeTree")
                return "SummingMergeTree()"
            elif "Aggregating" in engine:
                self.engines_used.add("AggregatingMergeTree")
                return "AggregatingMergeTree()"
            elif "Collapsing" in engine:
                return "CollapsingMergeTree()"
            else:
                return "MergeTree()"
        elif engine == "Log":
            return "Log()"
        elif engine == "TinyLog":
            return "TinyLog()"
        elif engine == "StripeLog":
            return "StripeLog()"
        elif engine == "Memory":
            return "Memory()"
        elif engine == "Null":
            return "Null()"
        elif engine == "Set":
            return "Set()"
        elif engine == "Join":
            return "Join()"
        elif engine == "View":
            return "View()"
        return f"MergeTree()  # TODO: Engine: {engine}"
    
    def _map_distributed_engine(self, engine_full: str) -> str:
        """Parse Distributed engine_full and generate CHORM Distributed() call.
        
        Syntax: Distributed(cluster, database, table[, sharding_key[, policy_name]])
        
        Examples:
            "Distributed(cluster, database, table)" -> Distributed(cluster="cluster", database="database", table="table")
            "Distributed(cluster, database, table, rand())" -> Distributed(cluster="cluster", database="database", table="table", sharding_key="rand()")
        """
        if not engine_full or not engine_full.startswith("Distributed("):
            return "Distributed(cluster='...', database='...', table='...')  # TODO: Parse engine_full"
        
        # Extract content inside parentheses
        inner = engine_full[len("Distributed("):-1] if engine_full.endswith(")") else engine_full[len("Distributed("):]
        
        # Parse arguments - handle quoted strings and expressions
        args = self._parse_distributed_args(inner)
        
        # Build Distributed() call
        params = []
        if len(args) >= 1:
            params.append(f"cluster={self._quote_arg(args[0])}")
        if len(args) >= 2:
            params.append(f"database={self._quote_arg(args[1])}")
        if len(args) >= 3:
            params.append(f"table={self._quote_arg(args[2])}")
        if len(args) >= 4:
            # sharding_key - keep as expression, don't quote
            params.append(f"sharding_key={self._format_sharding_key(args[3])}")
        if len(args) >= 5:
            # policy_name
            params.append(f"policy_name={self._quote_arg(args[4])}")
        
        return f"Distributed({', '.join(params)})"
    
    def _map_replacing_mergetree_engine(self, engine_full: str) -> str:
        """Parse ReplacingMergeTree engine_full and generate CHORM ReplacingMergeTree() call.
        
        Syntax: ReplacingMergeTree([version_column])
        
        ReplacingMergeTree can have only one optional parameter - version_column.
        
        Examples:
            "ReplacingMergeTree()" -> ReplacingMergeTree()
            "ReplacingMergeTree(version)" -> ReplacingMergeTree(version_column="version")
            
        Note: engine_full may contain additional text after the engine definition
        (like ORDER BY, SETTINGS), so we need to extract only the engine part.
        """
        if not engine_full:
            return "ReplacingMergeTree()"
        
        engine_full = engine_full.strip()
        
        # Check if it starts with ReplacingMergeTree(
        if not engine_full.startswith("ReplacingMergeTree("):
            return "ReplacingMergeTree()"
        
        # Find the matching closing parenthesis for the engine definition
        # Need to handle nested parentheses if any, but ReplacingMergeTree has only one parameter
        start_idx = len("ReplacingMergeTree(")
        depth = 1
        end_idx = start_idx
        
        for i in range(start_idx, len(engine_full)):
            if engine_full[i] == '(':
                depth += 1
            elif engine_full[i] == ')':
                depth -= 1
                if depth == 0:
                    end_idx = i
                    break
        
        # Extract content inside parentheses
        inner = engine_full[start_idx:end_idx].strip()
        
        # If empty, no version column
        if not inner:
            return "ReplacingMergeTree()"
        
        # Parse version column name (should be a single column name)
        # Remove quotes if present, and take only the first part (before any spaces/comma)
        version_column = inner.strip().strip("'\"").strip()
        
        # Split by space or comma to get only the column name (ignore ORDER BY, SETTINGS, etc.)
        if ' ' in version_column:
            version_column = version_column.split()[0]
        if ',' in version_column:
            version_column = version_column.split(',')[0]
        
        version_column = version_column.strip().strip("'\"")
        
        if version_column:
            return f'ReplacingMergeTree(version_column="{version_column}")'
        
        return "ReplacingMergeTree()"
    
    def _parse_distributed_args(self, inner: str) -> List[str]:
        """Parse arguments from Distributed engine definition.
        
        Handles quoted strings and expressions like rand().
        """
        args = []
        current = ""
        depth = 0
        in_quotes = False
        quote_char = None
        
        i = 0
        while i < len(inner):
            char = inner[i]
            
            if char in ("'", '"') and (i == 0 or inner[i-1] != '\\'):
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char:
                    in_quotes = False
                    quote_char = None
                current += char
            elif not in_quotes:
                if char == '(':
                    depth += 1
                    current += char
                elif char == ')':
                    depth -= 1
                    current += char
                elif char == ',' and depth == 0:
                    args.append(current.strip())
                    current = ""
                else:
                    current += char
            else:
                current += char
            
            i += 1
        
        if current.strip():
            args.append(current.strip())
        
        return args
    
    def _quote_arg(self, arg: str) -> str:
        """Quote argument if it's a string literal, otherwise return as-is.
        
        Handles quoted strings from ClickHouse by removing quotes and re-quoting
        with repr() for proper Python string formatting.
        """
        arg = arg.strip()
        # If already quoted, extract the inner value and re-quote with repr()
        if arg.startswith("'") and arg.endswith("'"):
            # Extract inner string and re-quote
            inner = arg[1:-1]
            return repr(inner)
        elif arg.startswith('"') and arg.endswith('"'):
            # Extract inner string and re-quote
            inner = arg[1:-1]
            return repr(inner)
        # Otherwise, quote it
        return repr(arg)
    
    def _format_sharding_key(self, key: str) -> str:
        """Format sharding key - keep SQL expression as-is (always a string).
        
        sharding_key can be:
        - Column name: id
        - Function without params: rand()
        - Function with params: cityHash64(id), hash(id), intHash32(user_id)
        - Complex expression: (id + user_id) % 10
        
        Always return as Python string literal (quoted).
        """
        key = key.strip()
        # sharding_key is always a SQL expression, so keep it as a string
        return repr(key)

    def _parse_key_expression(self, expr: str) -> str:
        """Parse ORDER BY/PRIMARY KEY expression to list."""
        if not expr:
            return "[]"

        # Simple case: comma-separated column names
        parts = [p.strip() for p in expr.split(",")]
        return str(parts)
    
    def _map_function_to_func(self, func_name: str) -> str:
        """Map ClickHouse function name to func namespace expression.
        
        Examples:
            'sum' -> 'func.sum'
            'quantiles(0.5, 0.9)' -> 'func.quantiles([0.5, 0.9], "dummy")'
            'quantile(0.5)' -> 'func.quantile(0.5, "dummy")'
            'uniqExact' -> 'func.uniqExact'
        
        Args:
            func_name: Function name from ClickHouse (may include parameters)
            
        Returns:
            String expression for func namespace
        """
        # Check if function has parameters (e.g., quantiles(0.5, 0.9))
        if "(" in func_name and func_name.endswith(")"):
            # Extract base name and parameters
            base_name = func_name.split("(")[0]
            params_str = func_name[len(base_name) + 1:-1]  # Everything between ( and )
            
            # Parse parameters (comma-separated)
            params = [p.strip() for p in params_str.split(",")]
            
            # Special handling for quantiles - it takes a list as first argument
            if base_name == "quantiles":
                # Convert quantiles(0.5, 0.9) -> func.quantiles([0.5, 0.9], "dummy")
                params_list = f"[{', '.join(params)}]"
                return f'func.quantiles({params_list}, "dummy")'
            else:
                # For other functions with parameters (e.g., quantile(0.5))
                # Build func call with parameters and dummy argument
                params_str_formatted = ", ".join(params)
                return f'func.{base_name}({params_str_formatted}, "dummy")'
        else:
            # Simple function name without parameters
            # Map ClickHouse function names to func namespace
            func_map = {
                "uniqExact": "uniqExact",  # Keep as is (func.uniqExact exists)
                "anyIf": "anyIf",  # Keep as is
                "sumIf": "sumIf",
                "countIf": "countIf",
                "avgIf": "avgIf",
                "minIf": "minIf",
                "maxIf": "maxIf",
                "uniqIf": "uniqIf",
                "groupUniqArray": "groupUniqArray",  # AggregateFunction support
                "countDistinct": "countDistinct",  # AggregateFunction support
            }
            
            mapped_name = func_map.get(func_name, func_name)
            return f"func.{mapped_name}"

    def _parse_codec_expression(self, codec_str: str) -> Optional[str]:
        """Parse codec string into Python expression logic.
        
        Example: 
            "Delta(8), ZSTD(1)" -> "Delta(8) | ZSTD(1)"
            "LZ4" -> "LZ4()"
        """
        # Reuse _parse_distributed_args to split by comma respecting parens
        parts = self._parse_distributed_args(codec_str)
        if not parts:
            return None

        # Known codecs in chorm.codecs (names only)
        # Using string mapping to check validity
        known_codecs = {
            "ZSTD", "LZ4", "LZ4HC", "Delta", "DoubleDelta", 
            "Gorilla", "T64", "FPC", "NONE"
        }
        
        expr_parts = []
        for part in parts:
            part = part.strip()
            # Check structure: Name or Name(...)
            match = re.match(r"^(\w+)(?:\((.*)\))?$", part)
            if not match:
                return None # Unknown format
            
            name = match.group(1)
            args = match.group(2)
            
            if name not in known_codecs:
                return None # Unknown codec, fallback to string

            self.codecs_used.add(name)
            
            if args is not None:
                # Validate args? For now assume they are literals
                expr_parts.append(f"{name}({args})")
            else:
                # No args, instantiate as Name()
                expr_parts.append(f"{name}()")
        
        return " | ".join(expr_parts)

    def generate_imports(self) -> str:
        """Generate import statements."""
        lines = []
        lines.append("from chorm import Table, Column")

        # Type imports (filter out 'func' as it's imported separately)
        type_imports = sorted(imp for imp in self.imports if imp != "func")
        if type_imports:
            lines.append(f"from chorm.types import {', '.join(type_imports)}")

        # Func import (if needed)
        if "func" in self.imports:
            lines.append("from chorm.sql.expression import func")

        # Engine imports - collect from used engines
        engine_list = ["MergeTree"]  # Always include MergeTree
        if "Distributed" in self.engines_used:
            engine_list.append("Distributed")
        if "ReplacingMergeTree" in self.engines_used:
            engine_list.append("ReplacingMergeTree")
        if "SummingMergeTree" in self.engines_used:
            engine_list.append("SummingMergeTree")
        if "AggregatingMergeTree" in self.engines_used:
            engine_list.append("AggregatingMergeTree")
        
        
        lines.append(f"from chorm.table_engines import {', '.join(sorted(set(engine_list)))}")
        
        # Codec imports
        if self.codecs_used:
             lines.append(f"from chorm.codecs import {', '.join(sorted(self.codecs_used))}")

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
