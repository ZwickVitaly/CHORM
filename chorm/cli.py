"""Command-line interface for CHORM."""

import argparse
import os
import sys
import tomllib
import importlib.util
import clickhouse_connect
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from chorm.migration import Migration, MigrationManager
from chorm.session import Session
from chorm.engine import create_engine

MIGRATION_TEMPLATE = """\"\"\"Migration: {name}

Created: {timestamp}
Down Revision: {down_revision}
\"\"\"

from chorm.migration import Migration
from chorm.session import Session


class {class_name}(Migration):
    id = \"{timestamp}\"
    name = \"{name}\"
    down_revision = {down_revision}

    def upgrade(self, session: Session) -> None:
        \"\"\"Apply the migration.\"\"\"
        # Example DDL operations:
        
        # Add a column
        # self.add_column(session, 'users', 'age UInt8', after='name')
        
        # Drop a column
        # self.drop_column(session, 'users', 'old_field')
        
        # Modify column type
        # self.modify_column(session, 'users', 'age UInt16')
        
        # Rename column
        # self.rename_column(session, 'users', 'old_name', 'new_name')
        
        # Add index
        # from chorm.sql.expression import Identifier
        # self.add_index(session, 'users', 'idx_email', Identifier('email'), index_type='bloom_filter')
        
        # Raw SQL
        # session.execute("CREATE TABLE IF NOT EXISTS example (...)")
        
        pass

    def downgrade(self, session: Session) -> None:
        \"\"\"Revert the migration.\"\"\"
        # Reverse the operations from upgrade()
        
        # Drop index
        # self.drop_index(session, 'users', 'idx_email')
        
        # Rename column back
        # self.rename_column(session, 'users', 'new_name', 'old_name')
        
        # Drop added column
        # self.drop_column(session, 'users', 'age')
        
        pass
"""


def init_project(args):
    """Initialize a new CHORM project."""
    cwd = Path.cwd()

    # Create migrations directory
    migrations_dir = cwd / "migrations"
    if not migrations_dir.exists():
        migrations_dir.mkdir()
        # Create __init__.py to make it a package
        (migrations_dir / "__init__.py").touch()
        print(f"Created migrations directory: {migrations_dir}")
    else:
        print(f"Migrations directory already exists: {migrations_dir}")

    # Create chorm.toml config template
    config_file = cwd / "chorm.toml"
    if not config_file.exists():
        config_content = """[chorm]
# Database connection settings
host = "localhost"
port = 8123
database = "default"
user = "default"
password = ""
secure = false

[migrations]
directory = "migrations"
table_name = "chorm_migrations"
"""
        config_file.write_text(config_content)
        print(f"Created configuration file: {config_file}")
        print(f"Configuration file already exists: {config_file}")


def make_migration(args):
    """Create a new migration file."""
    cwd = Path.cwd()
    migrations_dir = cwd / "migrations"

    if not migrations_dir.exists():
        print("Error: migrations directory not found. Run 'chorm init' first.")
        sys.exit(1)

    # Generate timestamp ID
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = args.message.replace(" ", "_").lower() if args.message else "migration"
    filename = f"{timestamp}_{name}.py"
    filepath = migrations_dir / filename

    # Determine down_revision (simplistic: just look at latest file)
    # In a real system, we'd parse the files or check the DB.
    # For now, let's just use "None" or find the latest file by name.
    existing_files = sorted([f for f in migrations_dir.glob("*.py") if f.name != "__init__.py"])
    down_revision = "None"
    if existing_files:
        # Assuming filename starts with timestamp
        last_file = existing_files[-1]
        down_revision = last_file.name.split("_")[0]

    content = MIGRATION_TEMPLATE.format(
        name=args.message or "New Migration", timestamp=timestamp, down_revision=down_revision
    )

    filepath.write_text(content)
    print(f"Created migration file: {filepath}")


def load_config(cwd: Path) -> Dict[str, Any]:
    """Load configuration from chorm.toml."""
    config_file = cwd / "chorm.toml"
    if not config_file.exists():
        print("Error: chorm.toml not found. Run 'chorm init' first.")
        sys.exit(1)

    with open(config_file, "rb") as f:
        return tomllib.load(f)


def get_session(config: Dict[str, Any]) -> Session:
    """Create a CHORM session from config."""
    db_config = config.get("chorm", {})
    engine = create_engine(
        host=db_config.get("host", "localhost"),
        port=db_config.get("port", 8123),
        username=db_config.get("user", "default"),
        password=db_config.get("password", ""),
        database=db_config.get("database", "default"),
        secure=db_config.get("secure", False),
    )
    return Session(engine)


def load_migrations(migrations_dir: Path) -> List[Any]:
    """Load migration classes from files."""
    migrations = []
    for filepath in sorted(migrations_dir.glob("*.py")):
        if filepath.name == "__init__.py":
            continue

        spec = importlib.util.spec_from_file_location(filepath.stem, filepath)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find Migration subclass
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, Migration) and attr is not Migration:
                    migrations.append(attr())
                    break
    return migrations


def migrate(args):
    """Apply pending migrations."""
    cwd = Path.cwd()
    config = load_config(cwd)
    migrations_dir = cwd / config.get("migrations", {}).get("directory", "migrations")

    if not migrations_dir.exists():
        print(f"Error: migrations directory '{migrations_dir}' not found.")
        sys.exit(1)

    try:
        session = get_session(config)
        manager = MigrationManager(session, config.get("migrations", {}).get("table_name", "chorm_migrations"))

        applied_ids = set(manager.get_applied_migrations())
        available_migrations = load_migrations(migrations_dir)

        # Sort migrations by ID (assuming timestamp based IDs for now)
        # In a real system, we'd use topological sort based on down_revision
        available_migrations.sort(key=lambda m: m.id)

        pending_migrations = [m for m in available_migrations if m.id not in applied_ids]

        if not pending_migrations:
            print("No pending migrations.")
            return

        print(f"Found {len(pending_migrations)} pending migrations.")

        for migration in pending_migrations:
            print(f"Applying {migration.id}: {migration.name}...", end=" ")
            try:
                migration.upgrade(session)
                manager.apply_migration(migration)
                print("DONE")
            except Exception as e:
                print("FAILED")
                print(f"Error applying migration {migration.id}: {e}")
                sys.exit(1)

    except Exception as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)


def show_migrations(args):
    """Show migration status."""
    cwd = Path.cwd()
    config = load_config(cwd)
    migrations_dir = cwd / config.get("migrations", {}).get("directory", "migrations")

    if not migrations_dir.exists():
        print(f"Error: migrations directory '{migrations_dir}' not found.")
        sys.exit(1)

    try:
        session = get_session(config)
        manager = MigrationManager(session, config.get("migrations", {}).get("table_name", "chorm_migrations"))

        applied_ids = set(manager.get_applied_migrations())
        available_migrations = load_migrations(migrations_dir)

        # Sort migrations by ID
        available_migrations.sort(key=lambda m: m.id)

        if not available_migrations:
            print("No migrations found.")
            return

        print("\nMigration Status:")
        print("-" * 80)
        print(f"{'ID':<20} {'Name':<40} {'Status':<10}")
        print("-" * 80)

        for migration in available_migrations:
            status = "✓ Applied" if migration.id in applied_ids else "○ Pending"
            print(f"{migration.id:<20} {migration.name:<40} {status:<10}")

        print("-" * 80)
        pending_count = len([m for m in available_migrations if m.id not in applied_ids])
        print(f"Total: {len(available_migrations)} migrations ({len(applied_ids)} applied, {pending_count} pending)")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def downgrade(args):
    """Rollback migrations."""
    cwd = Path.cwd()
    config = load_config(cwd)
    migrations_dir = cwd / config.get("migrations", {}).get("directory", "migrations")

    if not migrations_dir.exists():
        print(f"Error: migrations directory '{migrations_dir}' not found.")
        sys.exit(1)

    try:
        session = get_session(config)
        manager = MigrationManager(session, config.get("migrations", {}).get("table_name", "chorm_migrations"))

        applied_ids = manager.get_applied_migrations()

        if not applied_ids:
            print("No migrations to rollback.")
            return

        available_migrations = load_migrations(migrations_dir)
        migrations_by_id = {m.id: m for m in available_migrations}

        # Determine how many steps to rollback
        steps = args.steps if hasattr(args, "steps") and args.steps else 1

        # Get the last N applied migrations in reverse order
        to_rollback = list(reversed(applied_ids))[:steps]

        if not to_rollback:
            print("No migrations to rollback.")
            return

        print(f"Rolling back {len(to_rollback)} migration(s)...")

        for migration_id in to_rollback:
            migration = migrations_by_id.get(migration_id)
            if not migration:
                print(f"Warning: Migration {migration_id} not found in files, skipping...")
                continue

            print(f"Rolling back {migration.id}: {migration.name}...", end=" ")
            try:
                migration.downgrade(session)
                manager.unapply_migration(migration_id)
                print("DONE")
            except Exception as e:
                print("FAILED")
                print(f"Error rolling back migration {migration.id}: {e}")
                sys.exit(1)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        print(f"Downgraded to revision: {manager.get_current_revision() or 'base'}")


def introspect(args):
    """Introspect database and generate model classes."""
    from chorm.introspection import TableIntrospector, ModelGenerator
    import clickhouse_connect

    # Try to load config, but don't fail if it doesn't exist
    try:
        config = load_config(Path.cwd())
        chorm_config = config.get("chorm", {})
    except:
        chorm_config = {}

    # Override with command line args or use defaults
    host = args.host or chorm_config.get("host", "localhost")
    port = args.port or chorm_config.get("port", 8123)
    database = args.database or chorm_config.get("database", "default")
    user = args.user or chorm_config.get("user", "default")
    password = args.password or chorm_config.get("password", "")

    print(f"Connecting to ClickHouse at {host}:{port}...")

    try:
        client = clickhouse_connect.get_client(
            host=host, port=port, username=user, password=password, database=database
        )
    except Exception as e:
        print(f"Error connecting to ClickHouse: {e}")
        sys.exit(1)

    # Introspect tables
    introspector = TableIntrospector(client)

    try:
        if args.tables:
            tables = [t.strip() for t in args.tables.split(",")]
        else:
            tables = introspector.get_tables(database)

        if not tables:
            print(f"No tables found in database '{database}'")
            sys.exit(0)

        print(f"Found {len(tables)} table(s): {', '.join(tables)}")
        print("Generating models...")

        # Get table info
        tables_info = []
        for table in tables:
            try:
                info = introspector.get_table_info(table, database)
                tables_info.append(info)
                print(f"  ✓ {table}")
            except Exception as e:
                print(f"  ✗ {table}: {e}")

        if not tables_info:
            print("No tables to generate models for")
            sys.exit(1)

        # Generate code
        generator = ModelGenerator()
        code = generator.generate_file(tables_info)

        # Write to file
        output_file = Path(args.output or "models.py")
        output_file.write_text(code)

        print(f"\nGenerated models written to: {output_file.absolute()}")
        print(f"Total models: {len(tables_info)}")

    except Exception as e:
        print(f"Error during introspection: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        client.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="CHORM - ClickHouse ORM CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize a new CHORM project")
    init_parser.set_defaults(func=init_project)

    # make-migration command
    make_parser = subparsers.add_parser("make-migration", help="Create a new migration file")
    make_parser.add_argument("-m", "--message", help="Migration message/name", required=True)
    make_parser.set_defaults(func=make_migration)

    # migrate command
    migrate_parser = subparsers.add_parser("migrate", help="Apply pending migrations")
    migrate_parser.set_defaults(func=migrate)

    # show-migrations command
    show_parser = subparsers.add_parser("show-migrations", help="Show migration status")
    show_parser.set_defaults(func=show_migrations)

    # downgrade command
    downgrade_parser = subparsers.add_parser("downgrade", help="Rollback migrations")
    downgrade_parser.add_argument("--steps", type=int, default=1, help="Number of migrations to rollback (default: 1)")
    downgrade_parser.set_defaults(func=downgrade)

    # introspect command
    introspect_parser = subparsers.add_parser("introspect", help="Generate models from existing database tables")
    introspect_parser.add_argument("--host", help="ClickHouse host (default: from config or localhost)")
    introspect_parser.add_argument("--port", type=int, help="ClickHouse port (default: from config or 8123)")
    introspect_parser.add_argument("--database", help="Database name (default: from config or 'default')")
    introspect_parser.add_argument("--user", help="Database user (default: from config or 'default')")
    introspect_parser.add_argument("--password", help="Database password (default: from config or empty)")
    introspect_parser.add_argument(
        "--tables", help="Comma-separated list of tables to introspect (default: all tables)"
    )
    introspect_parser.add_argument("--output", "-o", help="Output file (default: models.py)")
    introspect_parser.set_defaults(func=introspect)

    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
