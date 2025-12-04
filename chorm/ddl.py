"""Helpers for rendering ClickHouse DDL statements from metadata."""

from __future__ import annotations

from chorm.declarative import TableMetadata


def format_identifier(identifier: str) -> str:
    """Double-quote identifiers to avoid collisions with reserved words."""
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
        column_lines.append(" ".join(parts))

    clauses = []
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
        f"{'CREATE TABLE IF NOT EXISTS' if if_not_exists else 'CREATE TABLE'} {format_identifier(metadata.name)} (",
        "  " + ",\n  ".join(column_lines),
    ]
    lines.append(")")
    lines.append(f"ENGINE = {clause_sql}")
    for clause in clauses:
        lines.append(clause)
    return "\n".join(lines)


__all__ = ["format_ddl"]
