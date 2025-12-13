"""Automatic migration generation by comparing models with database state."""

from __future__ import annotations

from typing import List, Dict, Any, Set, Optional, Tuple, Type
from dataclasses import dataclass
from pathlib import Path
import importlib.util
import sys
import ast
from collections import defaultdict

from chorm.declarative import Table, TableMetadata
from chorm.introspection import TableIntrospector
from chorm.types import parse_type, FieldType
from chorm.migration import Migration
from chorm.ddl import format_ddl


@dataclass
class ColumnDiff:
    """Represents differences in a column between model and database."""

    name: str
    action: str  # 'add', 'drop', 'modify', 'rename'
    model_column: Optional[Any] = None
    db_column: Optional[Dict[str, Any]] = None
    old_name: Optional[str] = None  # For renames


@dataclass
class TableDiff:
    """Represents differences for a single table."""

    table_name: str
    action: str  # 'create', 'drop', 'alter', 'recreate'
    model_metadata: Optional[TableMetadata] = None
    db_info: Optional[Dict[str, Any]] = None
    column_diffs: List[ColumnDiff] = None
    query_modified: bool = False  # For Materialized Views

    def __post_init__(self):
        if self.column_diffs is None:
            self.column_diffs = []


class ModelLoader:
    """Load all Table classes from Python modules."""

    @staticmethod
    def find_table_classes_in_module(module_path: Path) -> List[Type[Table]]:
        """Find all Table subclasses in a Python module, utilizing metadata registry."""
        if not module_path.exists():
            return []

        # Use module name based on path to avoid conflicts
        module_name = str(module_path).replace("/", ".").replace("\\", ".").replace(".py", "")
        if module_name.startswith("."):
            module_name = module_name[1:]

        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if not spec or not spec.loader:
            return []

        module = importlib.util.module_from_spec(spec)
        # Use a unique module name to avoid conflicts
        unique_name = f"_chorm_auto_migrate_{id(module)}"
        sys.modules[unique_name] = module

        try:
            spec.loader.exec_module(module)
        except Exception:
            # Skip modules that can't be loaded
            if unique_name in sys.modules:
                del sys.modules[unique_name]
            return []

        # After loading, we can check if any tables were registered in metadata
        # But since we are loading modules dynamically, we rely on the side effect of class definition
        # which registers the table in the Metadata.
        
        # However, to be compatible with explicit returns, we can still inspect module attributes.
        table_classes = []
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, Table)
                and attr is not Table
                and not getattr(attr, "__abstract__", False)
            ):
                table_classes.append(attr)

        # Clean up
        if unique_name in sys.modules:
            del sys.modules[unique_name]

        return table_classes

    @staticmethod
    def find_all_models(models_path: Path) -> Dict[str, Type[Table]]:
        """Find all Table classes in a directory (recursively)."""
        tables: Dict[str, Type[Table]] = {}

        if not models_path.exists():
            return tables

        # Search for Python files
        for py_file in models_path.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue

            for table_class in ModelLoader.find_table_classes_in_module(py_file):
                if hasattr(table_class, "__tablename__") and table_class.__tablename__:
                    table_name = table_class.__tablename__
                    tables[table_name] = table_class

        return tables


class MigrationGenerator:
    """Generate migrations by comparing models with database state."""

    def __init__(self, introspector: TableIntrospector, database: str = "default"):
        self.introspector = introspector
        self.database = database

    def compare_tables(
        self, model_tables: Dict[str, TableMetadata], db_tables: List[str]
    ) -> List[TableDiff]:
        """Compare model tables with database tables and generate diffs."""
        db_table_set = set(db_tables)
        model_table_set = set(model_tables.keys())

        diffs: List[TableDiff] = []

        # Tables to create (in models but not in DB)
        for table_name in model_table_set - db_table_set:
            model_metadata = model_tables[table_name]
            diffs.append(
                TableDiff(
                    table_name=table_name,
                    action="create",
                    model_metadata=model_metadata,
                    column_diffs=[],
                )
            )

        # Tables to drop (in DB but not in models)
        for table_name in db_table_set - model_table_set:
            # Check if it's a migration table or system table, although introspection usually filters system tables
            if table_name == "chorm_migrations":
                continue
                
            db_info = self.introspector.get_table_info(table_name, self.database)
            diffs.append(
                TableDiff(
                    table_name=table_name,
                    action="drop",
                    db_info=db_info,
                    column_diffs=[],
                )
            )

        # Tables to alter (in both)
        for table_name in model_table_set & db_table_set:
            table_diff = self._compare_table(
                model_tables[table_name], table_name
            )
            if table_diff:
                diffs.append(table_diff)

        return diffs

    def _compare_table(self, model_metadata: TableMetadata, table_name: str) -> Optional[TableDiff]:
        """Compare a single model table with its database state."""
        db_info = self.introspector.get_table_info(table_name, self.database)

        column_diffs = self._compare_columns(model_metadata, db_info)
        
        query_modified = False
        is_mv = model_metadata.engine and model_metadata.engine.engine_name == "MaterializedView"
        is_db_mv = db_info.get("engine") == "MaterializedView"
        
        if is_mv and is_db_mv:
            # Check if query changed
            create_query = db_info.get("create_query", "")
            # Extract AS SELECT part
            import re
            select_match = re.search(r"AS\s+(SELECT.*)", create_query, re.IGNORECASE | re.DOTALL)
            db_select = select_match.group(1).strip() if select_match else ""
            
            model_select = model_metadata.select_query
            if model_select:
                 # Normalize both for comparison
                 # This is tricky as formatting/macros might differ
                 # For now, simple whitespace normalization
                 def normalize(s):
                     return " ".join(str(s).split())
                 
                 if normalize(model_select) != normalize(db_select):
                     query_modified = True

        if not column_diffs and not query_modified:
            return None  # No differences

        return TableDiff(
            table_name=table_name,
            action="recreate" if query_modified else "alter",
            model_metadata=model_metadata,
            db_info=db_info,
            column_diffs=column_diffs,
            query_modified=query_modified,
        )

    def _compare_columns(
        self, model_metadata: TableMetadata, db_info: Dict[str, Any]
    ) -> List[ColumnDiff]:
        """Compare columns between model and database."""
        diffs: List[ColumnDiff] = []

        # Build maps
        model_columns = {col.name: col for col in model_metadata.columns}
        db_columns = {col["name"]: col for col in db_info.get("columns", [])}

        model_col_names = set(model_columns.keys())
        db_col_names = set(db_columns.keys())

        # Columns to add (in model but not in DB)
        for col_name in model_col_names - db_col_names:
            diffs.append(
                ColumnDiff(
                    name=col_name,
                    action="add",
                    model_column=model_columns[col_name],
                )
            )

        # Columns to drop (in DB but not in model)
        for col_name in db_col_names - model_col_names:
            diffs.append(
                ColumnDiff(
                    name=col_name,
                    action="drop",
                    db_column=db_columns[col_name],
                )
            )

        # Columns to modify (in both, but different)
        for col_name in model_col_names & db_col_names:
            model_col = model_columns[col_name]
            db_col = db_columns[col_name]

            # Compare types
            model_type_str = model_col.column.ch_type
            db_type_str = db_col["type"]

            # Normalize types for comparison (handle nullable, etc.)
            if self._types_differ(model_type_str, db_type_str):
                diffs.append(
                    ColumnDiff(
                        name=col_name,
                        action="modify",
                        model_column=model_col,
                        db_column=db_col,
                    )
                )

        return diffs

    def _types_differ(self, model_type: str, db_type: str) -> bool:
        """Check if two ClickHouse type strings differ."""
        # Normalize for comparison
        model_type = model_type.strip().replace(" ", "")
        db_type = db_type.strip().replace(" ", "")

        # Handle Nullable behavior in ClickHouse vs CHORM
        # CHORM might explicitly say "Nullable(String)", DB says "Nullable(String)" -> Match
        # CHORM says "String" (nullable=True), DB says "Nullable(String)" -> Match logic needs to be aware of this?
        # IMPORTANT: CHORM Declarative types usually include Nullable(...) in the string if they are nullable,
        # because the type instance .to_clickhouse() includes it.
        # But let's handle the string parsing carefully.

        # Handle Nullable wrapping mismatch
        if model_type.startswith("Nullable(") and not db_type.startswith("Nullable("):
            # Compare inner types
            inner_model = model_type[9:-1]  # Remove Nullable(...)
            return inner_model != db_type
        elif db_type.startswith("Nullable(") and not model_type.startswith("Nullable("):
            inner_db = db_type[9:-1]
            return inner_db != model_type

        return model_type != db_type

    def generate_migration_code(
        self, diffs: List[TableDiff], migration_name: str, timestamp: str, down_revision: Optional[str]
    ) -> str:
        """Generate migration Python code from diffs."""
        class_name = migration_name.replace("_", "").replace(" ", "").title().replace(" ", "")
        if not class_name[0].isupper():
            class_name = class_name.capitalize()

        lines = [
            '"""Migration: {name}',
            "",
            "Created: {timestamp}",
            "Down Revision: {down_revision}",
            '"""',
            "",
            "from chorm.migration import Migration",
            "from chorm.session import Session",
            "from chorm.sql.expression import Identifier",
            "",
            "",
            "class {class_name}(Migration):",
            '    id = "{timestamp}"',
            '    name = "{name}"',
            "    down_revision = {down_revision}",
            "",
            "    def upgrade(self, session: Session) -> None:",
            '        """Apply the migration."""',
        ]

        # Generate upgrade code
        upgrade_lines = []
        for diff in diffs:
            if diff.action == "create":
                # CREATE TABLE
                upgrade_lines.append(f"        # Create table {diff.table_name}")
                # Generate DDL from metadata
                if diff.model_metadata:
                    ddl = format_ddl(diff.model_metadata, if_not_exists=True)
                    # Escape quotes in DDL and format as multiline string
                    # Replace triple quotes with escaped version
                    ddl_escaped = ddl.replace('"""', '\\"\\"\\"').replace("'''", "\\'\\'\\'")
                    upgrade_lines.append('        session.execute("""')
                    # Add each line with proper indentation
                    for ddl_line in ddl_escaped.split("\n"):
                        upgrade_lines.append(f"        {ddl_line}")
                    upgrade_lines.append('        """)')
                upgrade_lines.append("")

            elif diff.action == "recreate":
                # Recreate table (Drop + Create)
                upgrade_lines.append(f"        # Recreate table {diff.table_name} (Query changed)")
                upgrade_lines.append(f"        session.execute('DROP TABLE IF EXISTS {diff.table_name}')")
                
                if diff.model_metadata:
                    ddl = format_ddl(diff.model_metadata, if_not_exists=True)
                    # Escape quotes in DDL and format as multiline string
                    ddl_escaped = ddl.replace('"""', '\\"\\"\\"').replace("'''", "\\'\\'\\'")
                    upgrade_lines.append('        session.execute("""')
                    for ddl_line in ddl_escaped.split("\n"):
                        upgrade_lines.append(f"        {ddl_line}")
                    upgrade_lines.append('        """)')
                upgrade_lines.append("")

            elif diff.action == "drop":
                 # DROP TABLE
                upgrade_lines.append(f"        # Drop table {diff.table_name}")
                upgrade_lines.append(f"        session.execute('DROP TABLE IF EXISTS {diff.table_name}')")
                upgrade_lines.append("")

            elif diff.action == "alter":
                # ALTER TABLE operations
                upgrade_lines.append(f"        # Alter table {diff.table_name}")
                for col_diff in diff.column_diffs:
                    if col_diff.action == "add":
                        col = col_diff.model_column
                        col_def = f"{col.column.ch_type}"
                        if col.column.default is not None:
                            col_def += f" DEFAULT {col.column.default!r}"
                        # Check for codec
                        if hasattr(col.column, 'codec') and col.column.codec:
                            col_def += f" CODEC({col.column.codec})"
                        upgrade_lines.append(
                            f"        self.add_column(session, '{diff.table_name}', '{col_diff.name} {col_def}')"
                        )
                    elif col_diff.action == "drop":
                        upgrade_lines.append(
                            f"        self.drop_column(session, '{diff.table_name}', '{col_diff.name}')"
                        )
                    elif col_diff.action == "modify":
                        col = col_diff.model_column
                        col_def = f"{col.column.ch_type}"
                        # Check for codec
                        if hasattr(col.column, 'codec') and col.column.codec:
                            col_def += f" CODEC({col.column.codec})"
                        upgrade_lines.append(
                            f"        self.modify_column(session, '{diff.table_name}', '{col_diff.name} {col_def}')"
                        )

        if not upgrade_lines:
            upgrade_lines.append("        pass")

        lines.extend(upgrade_lines)
        lines.append("")
        lines.append("    def downgrade(self, session: Session) -> None:")
        lines.append('        """Revert the migration."""')

        # Generate downgrade code (reverse operations)
        downgrade_lines = []
        for diff in reversed(diffs):  # Reverse order
            if diff.action == "create":
                downgrade_lines.append(f"        # Drop table {diff.table_name}")
                downgrade_lines.append(f"        session.execute('DROP TABLE IF EXISTS {diff.table_name}')")
            
            elif diff.action == "recreate":
                # Downgrade refresh means we need to restore previous state.
                # Since we don't have the old model, we can't easily restore EXCEPT if we rely on db_info?
                # But db_info is dictionary. DDL reconstruction from introspection info is possible but hard here.
                # So we just warn or drop.
                downgrade_lines.append(f"        # TODO: Manually restore table {diff.table_name} (was recreated)")
                downgrade_lines.append(f"        session.execute('DROP TABLE IF EXISTS {diff.table_name}')")
                if diff.db_info and diff.db_info.get("create_query"):
                    create_query = diff.db_info["create_query"]
                    # Escape appropriately
                    create_query_esc = create_query.replace('"""', '\\"\\"\\"').replace("'''", "\\'\\'\\'")
                    downgrade_lines.append('        session.execute("""')
                    for ddl_line in create_query_esc.split("\n"):
                        downgrade_lines.append(f"        {ddl_line}")
                    downgrade_lines.append('        """)')

            elif diff.action == "drop":
                # Re-create table (Hard to reconstruct perfectly without model)
                downgrade_lines.append(f"        # TODO: Manually restore table {diff.table_name}")
                # We can try to provide a best-effort from db_info, but it's risky.
                # Just commenting it out or putting a placeholder is safer.
                downgrade_lines.append(f"        # session.execute('CREATE TABLE {diff.table_name} ...')")

            elif diff.action == "alter":
                downgrade_lines.append(f"        # Revert changes to table {diff.table_name}")
                for col_diff in reversed(diff.column_diffs):
                    if col_diff.action == "add":
                        downgrade_lines.append(
                            f"        self.drop_column(session, '{diff.table_name}', '{col_diff.name}')"
                        )
                    elif col_diff.action == "drop" and col_diff.db_column:
                        # Restore dropped column
                        db_type = col_diff.db_column["type"]
                        # Restore codec if available
                        if col_diff.db_column.get("codec"):
                            db_type += f" CODEC({col_diff.db_column['codec']})"
                            
                        downgrade_lines.append(
                            f"        self.add_column(session, '{diff.table_name}', '{col_diff.name} {db_type}')"
                        )
                    elif col_diff.action == "modify" and col_diff.db_column:
                        # Restore original type
                        db_type = col_diff.db_column["type"]
                        # Restore codec if available
                        if col_diff.db_column.get("codec"):
                             db_type += f" CODEC({col_diff.db_column['codec']})"

                        downgrade_lines.append(
                            f"        self.modify_column(session, '{diff.table_name}', '{col_diff.name} {db_type}')"
                        )

        if not downgrade_lines:
            downgrade_lines.append("        pass")

        lines.extend(downgrade_lines)

        # Format the template
        content = "\n".join(lines).format(
            name=migration_name,
            timestamp=timestamp,
            down_revision=down_revision or "None",
            class_name=class_name,
        )

        return content


__all__ = [
    "ModelLoader",
    "MigrationGenerator",
    "TableDiff",
    "ColumnDiff",
]

