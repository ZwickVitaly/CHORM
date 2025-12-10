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
from chorm.auto_migration import ModelLoader, MigrationGenerator
from chorm.introspection import TableIntrospector, ModelGenerator


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

ENV_TEMPLATE = """
from chorm import MetaData
from chorm.engine import create_engine

# target_metadata is the MetaData object your migrations should use.
# It can be imported from your application code.
# target_metadata = myapp.models.metadata

# For auto-generation to work, you must assign this variable!
target_metadata = MetaData()

def get_engine_url():
    # Return connection URL string for CHORM
    return "clickhouse://default:@localhost:8123/default"
"""

def init_project(args):
    """Initialize a new CHORM project."""
    cwd = Path.cwd()

    # Create migrations directory
    migrations_dir = cwd / "migrations"
    versions_dir = migrations_dir / "versions"
    
    if not migrations_dir.exists():
        migrations_dir.mkdir()
        # Create versions directory
        versions_dir.mkdir()
        
        # Create __init__.py files
        (migrations_dir / "__init__.py").touch()
        (versions_dir / "__init__.py").touch()
        
        # Create env.py
        env_file = migrations_dir / "env.py"
        env_file.write_text(ENV_TEMPLATE.strip())
        
        print(f"Created migrations directory: {migrations_dir}")
        print(f"Created versions directory: {versions_dir}")
        print(f"Created env.py: {env_file}")
    else:
        if not versions_dir.exists():
             versions_dir.mkdir()
             (versions_dir / "__init__.py").touch()
             print(f"Created versions directory: {versions_dir}")
             
        env_file = migrations_dir / "env.py"
        if not env_file.exists():
             env_file.write_text(ENV_TEMPLATE.strip())
             print(f"Created env.py: {env_file}")
             
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
version_style = "uuid" # Options: uuid, int, django
"""
        config_file.write_text(config_content)
        print(f"Created configuration file: {config_file}")
    else:
        print(f"Configuration file already exists: {config_file}")


def make_migration(args):
    """Create a new migration file."""
    cwd = Path.cwd()
    config = load_config(cwd)
    migrations_config = config.get("migrations", {})
    
    # Support old structure for backward compatibility, but prefer new
    migrations_dir = cwd / migrations_config.get("directory", "migrations")
    versions_dir = migrations_dir / "versions"
    
    target_dir = versions_dir if versions_dir.exists() else migrations_dir

    if not migrations_dir.exists():
        print("Error: migrations directory not found. Run 'chorm init' first.")
        sys.exit(1)
        
    version_style = migrations_config.get("version_style", "uuid").lower()

    # Generate filename based on style
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Sanitize slug
    raw_slug = args.message.replace(" ", "_").lower() if args.message else "migration"
    # Remove any characters that aren't alphanumeric, underscore, or dash
    import re
    slug = re.sub(r'[^a-z0-9_-]', '', raw_slug)
    if not slug:
        slug = "migration"
    
    # Get existing files for sequential numbering
    existing_files = sorted([f for f in target_dir.glob("*.py") if f.name != "__init__.py"])
    
    filename = ""
    migration_id = timestamp # Default ID is timestamp unless UUID used
    
    if version_style == "uuid":
        import uuid
        migration_id = str(uuid.uuid4()).replace("-", "")
        filename = f"{migration_id}_{slug}.py"
        
    elif version_style == "int":
        # pattern: 1_slug.py
        next_rev = 1
        if existing_files:
            try:
                # Try to parse leading number
                last_name = existing_files[-1].name
                last_rev = int(last_name.split("_")[0])
                next_rev = last_rev + 1
            except ValueError:
                pass
        filename = f"{next_rev}_{slug}.py"
        migration_id = str(next_rev)
        
    elif version_style == "django":
        # pattern: 0001_slug.py
        next_rev = 1
        if existing_files:
            try:
                last_name = existing_files[-1].name
                last_rev = int(last_name.split("_")[0])
                next_rev = last_rev + 1
            except ValueError:
                pass
        filename = f"{next_rev:04d}_{slug}.py"
        migration_id = f"{next_rev:04d}"
        
    else:
        # Fallback to timestamp
        filename = f"{timestamp}_{slug}.py"
        migration_id = timestamp

    filepath = target_dir / filename

    # Determine down_revision
    down_revision = "None"
    if existing_files:
        last_file = existing_files[-1]
        # Extract ID from last file
        down_revision_id = last_file.name.split("_")[0]
        # Quote it if it's a string (UUID or Timestamp), strict int/django can use int but let's treat all as strings for safety in generated code
        down_revision = f'"{down_revision_id}"'

    # Calculate class name
    class_name = args.message.replace(" ", "").title().replace("_", "") if args.message else "NewMigration"
    if not class_name: # Handle empty message case more gracefully
         class_name = "NewMigration"
    # Ensure it starts with a letter
    if class_name[0].isdigit():
        class_name = "Migration" + class_name

    content = MIGRATION_TEMPLATE.format(
        name=args.message or "New Migration", 
        timestamp=migration_id, 
        down_revision=down_revision,
        class_name=class_name
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
    
    # Check for versions subdirectory
    versions_dir = migrations_dir / "versions"
    search_dirs = [versions_dir, migrations_dir] if versions_dir.exists() else [migrations_dir]
    
    files_to_load = []
    for d in search_dirs:
         files_to_load.extend(sorted(d.glob("*.py")))
         
    for filepath in files_to_load:
        if filepath.name == "__init__.py" or filepath.name == "env.py":
            continue

        spec = importlib.util.spec_from_file_location(filepath.stem, filepath)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find Migration subclass
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, Migration) and attr is not Migration:
                    # Store filename or relative path helps with debugging but id is key
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


def auto_migrate(args):
    """Automatically generate migration by comparing models with database."""

    cwd = Path.cwd()
    config = load_config(cwd)
    migrations_config = config.get("migrations", {})
    migrations_dir = cwd / migrations_config.get("directory", "migrations")
    versions_dir = migrations_dir / "versions"
    target_dir = versions_dir if versions_dir.exists() else migrations_dir

    if not migrations_dir.exists():
        print("Error: migrations directory not found. Run 'chorm init' first.")
        sys.exit(1)

    # 1. Load Metadata
    model_tables = {}
    
    # Check for env.py first
    env_file = migrations_dir / "env.py"
    if env_file.exists():
        print(f"Loading metadata from {env_file}...")
        spec = importlib.util.spec_from_file_location("env", env_file)
        if spec and spec.loader:
            env_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(env_module)
            if hasattr(env_module, "target_metadata") and env_module.target_metadata:
                 print(f"Found target_metadata in env.py")
                 model_tables = env_module.target_metadata.tables
            else:
                 print("Warning: target_metadata not found or empty in env.py")
    
    # If no metadata found in env.py, fall back to scanning models path (CLI arg)
    if not model_tables:
        models_path = Path(args.models) if args.models else cwd
        if not models_path.exists():
             print(f"Error: models path '{models_path}' not found.")
             sys.exit(1)
        
        print(f"Scanning for models in: {models_path}")
        loader = ModelLoader()
        loaded_classes = loader.find_all_models(models_path)
         
        if not loaded_classes:
            print(f"No Table classes found in {models_path}")
            sys.exit(1)

        for cls in loaded_classes.values():
            if hasattr(cls, "metadata") and cls.metadata:
                model_tables[cls.__tablename__] = cls.__table__
            elif hasattr(cls, "__table__"):
                 model_tables[cls.__tablename__] = cls.__table__

    if not model_tables:
         print("Error: Could not find any table metadata.")
         sys.exit(1)

    print(f"Found {len(model_tables)} table model(s): {', '.join(sorted(model_tables.keys()))}")

    # Get database connection info
    db_config = config.get("chorm", {})
    host = args.host or db_config.get("host", "localhost")
    port = args.port or db_config.get("port", 8123)
    database = args.database or db_config.get("database", "default")
    user = args.user or db_config.get("user", "default")
    password = args.password or db_config.get("password", "")

    print(f"Connecting to ClickHouse at {host}:{port}...")

    try:
        # Connect to database
        client = clickhouse_connect.get_client(
            host=host, port=port, username=user, password=password, database=database
        )

        # Get database tables
        introspector = TableIntrospector(client)
        db_tables = introspector.get_tables(database)
        print(f"Found {len(db_tables)} table(s) in database: {', '.join(sorted(db_tables)) if db_tables else '(none)'}")

        # Compare and generate diffs
        generator = MigrationGenerator(introspector, database)
        diffs = generator.compare_tables(model_tables, db_tables)

        if not diffs:
            print("\n✓ No differences found. Database is in sync with models.")
            client.close()
            return

        print(f"\nFound {len(diffs)} difference(s):")
        for diff in diffs:
            if diff.action == "create":
                print(f"  + Create table: {diff.table_name}")
            elif diff.action == "alter":
                print(f"  ~ Alter table: {diff.table_name} ({len(diff.column_diffs)} column change(s))")
            elif diff.action == "drop":
                print(f"  - Drop table: {diff.table_name}")

        # Generate migration
        version_style = migrations_config.get("version_style", "uuid").lower()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        raw_slug = args.message.replace(" ", "_").lower() if args.message else "auto_migration"
        import re
        slug = re.sub(r'[^a-z0-9_-]', '', raw_slug)
        if not slug:
            slug = "auto_migration"

        # Determine down_revision and filename
        existing_files = sorted([f for f in target_dir.glob("*.py") if f.name != "__init__.py"])
        
        filename = ""
        migration_id = timestamp 
        down_revision = "None"
        
        if existing_files:
            last_file = existing_files[-1]
            down_revision_id = last_file.name.split("_")[0]
            down_revision = f'"{down_revision_id}"'

        if version_style == "uuid":
            import uuid
            migration_id = str(uuid.uuid4()).replace("-", "")
            filename = f"{migration_id}_{slug}.py"
        elif version_style == "int":
            next_rev = 1
            if existing_files:
                try:
                    last_rev = int(existing_files[-1].name.split("_")[0])
                    next_rev = last_rev + 1
                except ValueError: pass
            filename = f"{next_rev}_{slug}.py"
            migration_id = str(next_rev)
        elif version_style == "django":
            next_rev = 1
            if existing_files:
                try:
                    last_rev = int(existing_files[-1].name.split("_")[0])
                    next_rev = last_rev + 1
                except ValueError: pass
            filename = f"{next_rev:04d}_{slug}.py"
            migration_id = f"{next_rev:04d}"
        else:
             filename = f"{timestamp}_{slug}.py"
             migration_id = timestamp

        migration_code = generator.generate_migration_code(diffs, args.message or "Auto Migration", migration_id, down_revision)

        # Write migration file
        filepath = target_dir / filename
        filepath.write_text(migration_code)

        print(f"\n✓ Created migration file: {filepath}")
        print(f"  Review and adjust the migration before applying it with 'chorm migrate'")

        client.close()

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def introspect(args):
    """Introspect database and generate model classes."""


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

    # auto-migrate command
    auto_migrate_parser = subparsers.add_parser(
        "auto-migrate", help="Automatically generate migration by comparing models with database"
    )
    auto_migrate_parser.add_argument(
        "--models", help="Path to models directory or file (default: current directory)", default=None
    )
    auto_migrate_parser.add_argument("-m", "--message", help="Migration message/name", default="auto_migration")
    auto_migrate_parser.add_argument("--host", help="ClickHouse host (default: from config or localhost)")
    auto_migrate_parser.add_argument("--port", type=int, help="ClickHouse port (default: from config or 8123)")
    auto_migrate_parser.add_argument("--database", help="Database name (default: from config or 'default')")
    auto_migrate_parser.add_argument("--user", help="Database user (default: from config or 'default')")
    auto_migrate_parser.add_argument("--password", help="Database password (default: from config or empty)")
    auto_migrate_parser.set_defaults(func=auto_migrate)

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
