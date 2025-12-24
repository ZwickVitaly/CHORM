"""Helpers for rendering ClickHouse DDL statements from metadata."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chorm.declarative import TableMetadata


def format_identifier(identifier: str) -> str:
    """Format identifier, handling qualified names (database.table).
    
    For qualified names like 'radar.products', returns as-is.
    For simple identifiers that need escaping, uses double quotes.
    """
    # If it contains a dot, it's a qualified name - don't quote
    if "." in identifier:
        return identifier
    
    if identifier.isidentifier() and identifier.lower() == identifier:
        return identifier
    return f'"{identifier}"'


def format_ddl(metadata: TableMetadata, *, if_not_exists: bool = False) -> str:
    if metadata.engine is None:
        raise ValueError(f"Table {metadata.name} does not define an engine")

    column_lines = []
    for column in metadata.columns:
        parts = [format_identifier(column.name), column.column.ch_type]
        if column.column.default is not None:
            parts.append(f"DEFAULT {column.column.default!r}")
        if column.column.codec:
            codec_val = column.column.codec
            if hasattr(codec_val, "to_sql"):
                codec_str = codec_val.to_sql()
            elif isinstance(codec_val, (list, tuple)):
                # List of codecs or strings
                items = []
                for item in codec_val:
                    if hasattr(item, "to_sql"):
                        items.append(item.to_sql())
                    else:
                        items.append(str(item))
                codec_str = ", ".join(items)
            else:
                codec_str = str(codec_val)
            parts.append(f"CODEC({codec_str})")
        column_lines.append(" ".join(parts))

    # Some engines (like Distributed, View, etc.) don't support PRIMARY KEY, ORDER BY, etc.
    engine_name = metadata.engine.engine_name
    
    if engine_name == "MaterializedView":
        from chorm.sql.ddl import create_materialized_view
        
        # Extract engine parameters
        mv_engine = metadata.engine
        
        # Try to get attributes from the engine instance or metadata
        to_table = metadata.to_table
        if not to_table:
            # Fallback to engine attribute (backward compatibility or programmatic usage)
            to_table = getattr(mv_engine, "to_table", None)
        
        if not to_table and mv_engine.args:
            # Fallback to args if to_table attribute is missing but args are present
            to_table = mv_engine.args[0]
            
        inner_engine = getattr(mv_engine, "inner_engine", None)
        populate = getattr(mv_engine, "populate", False)
        select_query = metadata.select_query or ""
        
        stmt = create_materialized_view(
            name=metadata.name,
            query=select_query,
            to_table=to_table,
            engine=inner_engine,
            populate=populate,
            if_not_exists=if_not_exists
        )
        return stmt.to_sql()

    supports_structure_clauses = engine_name not in ("Distributed", "View")
    
    clauses = []
    if supports_structure_clauses:
        if metadata.primary_key:
            column_list = ", ".join(format_identifier(col.name) for col in metadata.primary_key)
            clauses.append(f"PRIMARY KEY ({column_list})")
        if metadata.partition_by:
            clauses.append(f"PARTITION BY ({', '.join(metadata.partition_by)})")
        if metadata.order_by:
            clauses.append(f"ORDER BY ({', '.join(metadata.order_by)})")
        if metadata.sample_by:
            clauses.append(f"SAMPLE BY ({', '.join(metadata.sample_by)})")
        if metadata.ttl:
            clauses.append(f"TTL {metadata.ttl}")

    engine = metadata.engine.format_clause()
    clause_sql = metadata.engine.format_clause()

    lines = [
        f"{'CREATE TABLE IF NOT EXISTS' if if_not_exists else 'CREATE TABLE'} {format_identifier(metadata.qualified_name)} (",
        "  " + ",\n  ".join(column_lines),
    ]
    lines.append(")")
    lines.append(f"ENGINE = {clause_sql}")
    for clause in clauses:
        lines.append(clause)
    return "\n".join(lines)


__all__ = ["format_ddl"]
