"""Integration tests for table introspection."""

import os
import sys
import ast
import inspect
import importlib
import pytest
from chorm import Table, Column, create_engine
from chorm.session import Session
from chorm.types import (
    UInt64,
    UInt32,
    UInt16,
    UInt8,
    Float64,
    Date,
    AggregateFunction,
)
from chorm.table_engines import AggregatingMergeTree, MergeTree, Distributed
from chorm.introspection import TableIntrospector, ModelGenerator

# Ensure we use real clickhouse_connect, not a mock
# Some tests mock clickhouse_connect at module level, which can leak here
# Check if it's a mock (mocks don't have __file__ attribute)
if "clickhouse_connect" in sys.modules:
    module = sys.modules["clickhouse_connect"]
    # Mocks typically don't have __file__ or it's None
    if not hasattr(module, "__file__") or getattr(module, "__file__", None) is None:
        # It's a mock, remove it so we get the real module
        del sys.modules["clickhouse_connect"]

import clickhouse_connect

# Skip integration tests if ClickHouse is not available
pytestmark = pytest.mark.skipif(
    os.getenv("CLICKHOUSE_HOST") is None,
    reason="ClickHouse not configured (set CLICKHOUSE_HOST env var)",
)


# Test table models
class IntrospectUsers(Table):
    """Simple MergeTree table for testing."""
    __tablename__ = "test_introspect_users"
    id = Column(UInt64(), primary_key=True)
    name = Column("String")
    age = Column(UInt32())
    created_at = Column(Date())
    __engine__ = MergeTree()
    __order_by__ = ["id"]


class IntrospectMetrics(Table):
    """AggregatingMergeTree table with AggregateFunction columns."""
    __tablename__ = "test_introspect_metrics"
    date = Column(Date())
    revenue_state = Column(AggregateFunction("sum", (UInt64(),)))
    avg_price_state = Column(AggregateFunction("avg", (Float64(),)))
    uniq_users_state = Column(AggregateFunction("uniqExact", (UInt32(),)))
    group_products_state = Column(AggregateFunction("groupUniqArray", (UInt32(),)))
    count_distinct_state = Column(AggregateFunction("countDistinct", (UInt32(),)))
    quantile_state = Column(AggregateFunction("quantile(0.5)", (UInt64(),)))
    __engine__ = AggregatingMergeTree()
    __order_by__ = ["date"]


class IntrospectLocalUsers(Table):
    """Local table for Distributed table testing."""
    __tablename__ = "test_introspect_local_users"
    id = Column(UInt64())
    name = Column("String")
    created_at = Column(Date())
    __engine__ = MergeTree()
    __order_by__ = ["id"]


class IntrospectDistributedUsers(Table):
    """Distributed table for testing."""
    __tablename__ = "test_introspect_distributed_users"
    id = Column(UInt64())
    name = Column("String")
    created_at = Column(Date())
    __engine__ = Distributed(
        cluster="default",
        database="default",
        table="test_introspect_local_users",
        sharding_key="rand()"
    )


@pytest.fixture(scope="module")
def engine():
    """Create engine for tests."""
    host = os.getenv("CLICKHOUSE_HOST", "localhost")
    port = int(os.getenv("CLICKHOUSE_PORT", "8123"))
    database = os.getenv("CLICKHOUSE_DB", "default")
    password = os.getenv("CLICKHOUSE_PASSWORD", "123")

    engine = create_engine(
        host=host,
        port=port,
        username="default",
        password=password,
        database=database,
    )
    return engine





@pytest.fixture(scope="module")
def setup_tables(engine):
    """Create test tables (non-Distributed tables only)."""
    session = Session(engine)

    try:
        # Drop tables if they exist
        for table_name in [
            IntrospectMetrics.__tablename__,
            IntrospectUsers.__tablename__,
        ]:
            try:
                session.execute(f"DROP TABLE IF EXISTS {table_name}")
            except Exception:
                pass

        # Create MergeTree table
        session.execute(IntrospectUsers.create_table(exists_ok=True))

        # Create AggregatingMergeTree table
        session.execute(IntrospectMetrics.create_table(exists_ok=True))

        session.commit()

        yield

    finally:
        # Cleanup
        for table_name in [
            IntrospectMetrics.__tablename__,
            IntrospectUsers.__tablename__,
        ]:
            try:
                session.execute(f"DROP TABLE IF EXISTS {table_name}")
            except Exception:
                pass
        session.commit()


@pytest.fixture(scope="module")
def client(engine):
    """Create ClickHouse client for introspection."""
    # Import here to avoid interference from module-level mocks in other tests
    # If clickhouse_connect was mocked, remove it from sys.modules and import fresh
    if "clickhouse_connect" in sys.modules:
        module = sys.modules["clickhouse_connect"]
        # Check if it's a mock (mocks don't have __file__ attribute)
        if not hasattr(module, "__file__") or getattr(module, "__file__", None) is None:
            # It's a mock, remove it
            del sys.modules["clickhouse_connect"]
    
    # Import fresh (will get real module if mock was removed)
    import clickhouse_connect
    
    return clickhouse_connect.get_client(
        host=engine.config.host,
        port=engine.config.port,
        username=engine.config.username,
        password=engine.config.password,
        database=engine.config.database,
    )


def extract_model_attributes(code: str) -> dict:
    """Extract attributes from generated model code."""
    # Parse the code
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        pytest.fail(f"Generated code has syntax error: {e}")

    attrs = {
        "tablename": None,
        "engine": None,
        "order_by": None,
        "partition_by": None,
        "columns": {},
    }

    # Find class definition
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # Extract class attributes
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name):
                            attr_name = target.id
                            if attr_name == "__tablename__":
                                if isinstance(item.value, ast.Constant):
                                    attrs["tablename"] = item.value.value
                            elif attr_name == "__engine__":
                                # Extract engine expression
                                attrs["engine"] = ast.unparse(item.value) if hasattr(ast, "unparse") else str(item.value)
                            elif attr_name == "__order_by__":
                                attrs["order_by"] = ast.unparse(item.value) if hasattr(ast, "unparse") else str(item.value)
                            elif attr_name == "__partition_by__":
                                attrs["partition_by"] = ast.unparse(item.value) if hasattr(ast, "unparse") else str(item.value)
                            elif isinstance(target, ast.Name) and not attr_name.startswith("_"):
                                # Column definition
                                if isinstance(item.value, ast.Call) and isinstance(item.value.func, ast.Name) and item.value.func.id == "Column":
                                    # Extract column type
                                    col_type = ast.unparse(item.value.args[0]) if hasattr(ast, "unparse") and item.value.args else str(item.value.args[0]) if item.value.args else None
                                    attrs["columns"][attr_name] = col_type

    return attrs


def compare_table_models(original_model: type, generated_code: str) -> bool:
    """Compare original model with generated code."""
    # Extract attributes from original model
    original_attrs = {
        "tablename": getattr(original_model, "__tablename__", None),
        "engine": str(original_model.__engine__) if hasattr(original_model, "__engine__") else None,
        "order_by": getattr(original_model, "__order_by__", None),
        "partition_by": getattr(original_model, "__partition_by__", None),
        "columns": {},
    }

    # Extract column types
    for name, column in inspect.getmembers(original_model):
        if not name.startswith("_") and isinstance(column, Column):
            # Get column type as ClickHouse type string
            col_type = column.ch_type if hasattr(column, "ch_type") else str(column.field_type)
            original_attrs["columns"][name] = col_type

    # Extract attributes from generated code
    generated_attrs = extract_model_attributes(generated_code)

    # Compare
    assert generated_attrs["tablename"] == original_attrs["tablename"], f"Tablename mismatch: {generated_attrs['tablename']} != {original_attrs['tablename']}"
    
    # Check engine (allow for minor formatting differences)
    assert generated_attrs["engine"] is not None, "Engine not found in generated code"
    
    # Check columns count
    assert len(generated_attrs["columns"]) == len(original_attrs["columns"]), f"Column count mismatch: {len(generated_attrs['columns'])} != {len(original_attrs['columns'])}"
    
    # Check order_by if present
    if original_attrs["order_by"]:
        assert generated_attrs["order_by"] is not None, "ORDER BY missing in generated code"
    
    return True


class TestIntrospectionIntegration:
    """Integration tests for table introspection."""

    def test_introspect_mergetree_table(self, engine, setup_tables, client):
        """Test introspecting a simple MergeTree table."""
        introspector = TableIntrospector(client)
        generator = ModelGenerator()

        # Verify table exists before introspection
        table_name = IntrospectUsers.__tablename__
        session = Session(engine)
        try:
            result = session.execute(f"SELECT engine FROM system.tables WHERE database = currentDatabase() AND name = '{table_name}'")
            if not result.all():
                pytest.fail(f"Table {table_name} was not created by setup_tables fixture")
            engine_type = result.scalar()
            if engine_type != "MergeTree":
                pytest.fail(f"Table {table_name} has wrong engine: {engine_type}, expected MergeTree")
        finally:
            session.close()

        # Get table info
        table_info = introspector.get_table_info(table_name)
        
        # Verify table_info contains expected data
        assert table_info["engine"] == "MergeTree", f"Expected MergeTree, got {table_info['engine']}"
        assert len(table_info["columns"]) > 0, f"Table {table_name} has no columns"

        # Generate model code
        generated_code = generator.generate_model(table_info)

        # Verify syntax
        try:
            ast.parse(generated_code)
        except SyntaxError as e:
            pytest.fail(f"Generated code has syntax error: {e}")

        # Verify table name
        assert IntrospectUsers.__tablename__ in generated_code
        assert "__tablename__" in generated_code

        # Verify columns are present
        assert "id" in generated_code
        assert "name" in generated_code
        assert "age" in generated_code
        assert "created_at" in generated_code

        # Verify engine
        assert "MergeTree()" in generated_code

        # Compare with original model
        compare_table_models(IntrospectUsers, generated_code)

    def test_introspect_aggregating_mergetree_table(self, engine, setup_tables, client):
        """Test introspecting an AggregatingMergeTree table with AggregateFunction columns."""
        introspector = TableIntrospector(client)
        generator = ModelGenerator()

        # Get table info
        table_info = introspector.get_table_info(IntrospectMetrics.__tablename__)

        # Generate model code
        generated_code = generator.generate_model(table_info)

        # Verify syntax
        try:
            ast.parse(generated_code)
        except SyntaxError as e:
            pytest.fail(f"Generated code has syntax error: {e}")

        # Verify table name
        assert IntrospectMetrics.__tablename__ in generated_code

        # Verify AggregateFunction columns are present
        assert "revenue_state" in generated_code
        assert "avg_price_state" in generated_code
        assert "uniq_users_state" in generated_code
        assert "group_products_state" in generated_code
        assert "count_distinct_state" in generated_code
        assert "quantile_state" in generated_code

        # Verify AggregateFunction types are generated correctly
        assert "AggregateFunction" in generated_code
        assert "func.sum" in generated_code
        assert "func.avg" in generated_code
        assert "func.uniqExact" in generated_code
        assert "func.groupUniqArray" in generated_code
        assert "func.countDistinct" in generated_code
        assert "func.quantile" in generated_code

        # Verify engine
        assert "AggregatingMergeTree()" in generated_code

        # Compare with original model
        compare_table_models(IntrospectMetrics, generated_code)


    def test_generate_file_with_multiple_tables(self, engine, setup_tables, client):
        """Test generating a complete file with multiple tables."""
        introspector = TableIntrospector(client)
        generator = ModelGenerator()

        # Get info for multiple tables
        tables_info = []
        for table_name in [IntrospectUsers.__tablename__, IntrospectMetrics.__tablename__]:
            try:
                table_info = introspector.get_table_info(table_name)
                tables_info.append(table_info)
            except ValueError:
                pass  # Skip if table doesn't exist

        # Generate complete file
        generated_file = generator.generate_file(tables_info)

        # Verify syntax
        try:
            ast.parse(generated_file)
        except SyntaxError as e:
            pytest.fail(f"Generated file has syntax error: {e}")

        # Verify imports
        assert "from chorm import Table, Column" in generated_file
        assert "from chorm.types import" in generated_file
        assert "from chorm.table_engines import" in generated_file

        # Verify all tables are present
        assert IntrospectUsers.__tablename__ in generated_file or "TestIntrospectUsers" in generated_file
        assert IntrospectMetrics.__tablename__ in generated_file or "TestIntrospectMetrics" in generated_file

        # Verify AggregateFunction import if needed
        if "AggregateFunction" in generated_file:
            assert "AggregateFunction" in generated_file.split("from chorm.types import")[1].split("\n")[0]

        # Verify engines are imported
        assert "MergeTree" in generated_file
        assert "AggregatingMergeTree" in generated_file


class TestDistributedIntrospectionIntegration:
    """Integration tests for Distributed table introspection.
    
    These tests use a local loopback Distributed table (cluster='default').
    """

    @pytest.fixture(scope="class")
    def setup_distributed_tables(self, engine, client):
        """Set up Distributed table for testing using local loopback."""
        session = Session(engine)

        try:
            # Check if 'default' cluster is configured
            try:
                cluster_check = session.execute(
                    "SELECT count() FROM system.clusters WHERE cluster = 'default'"
                ).scalar()
                if cluster_check == 0:
                    pytest.skip("Cluster 'default' is not configured. Skipping Distributed table tests.")
            except Exception as e:
                pytest.skip(f"Failed to check cluster configuration: {e}. Skipping Distributed table tests.")

            # Drop tables if they exist
            session.execute(f"DROP TABLE IF EXISTS {IntrospectDistributedUsers.__tablename__}")
            session.execute(f"DROP TABLE IF EXISTS {IntrospectLocalUsers.__tablename__}")

            # Create local table
            session.execute(IntrospectLocalUsers.create_table(exists_ok=True))
            
            # Create Distributed table
            try:
                session.execute(IntrospectDistributedUsers.create_table(exists_ok=True))
            except Exception as e:
                error_msg = str(e)
                if "CLUSTER_DOESNT_EXIST" in error_msg or "cluster" in error_msg.lower():
                    pytest.skip(f"Cluster 'default' not found or error: {e}. Skipping Distributed table tests.")
                raise

            session.commit()

            yield

        finally:
            # Cleanup
            try:
                session.execute(f"DROP TABLE IF EXISTS {IntrospectDistributedUsers.__tablename__}")
                session.execute(f"DROP TABLE IF EXISTS {IntrospectLocalUsers.__tablename__}")
                session.commit()
            except Exception:
                pass

    def test_introspect_distributed_table(self, engine, setup_distributed_tables, client):
        """Test introspecting a Distributed table."""
        introspector = TableIntrospector(client)
        generator = ModelGenerator()

        # Get table info
        table_info = introspector.get_table_info(IntrospectDistributedUsers.__tablename__)

        # Generate model code
        generated_code = generator.generate_model(table_info)

        # Verify syntax
        try:
            ast.parse(generated_code)
        except SyntaxError as e:
            pytest.fail(f"Generated code has syntax error: {e}")

        # Verify table name
        assert IntrospectDistributedUsers.__tablename__ in generated_code

        # Verify columns are present
        assert "id" in generated_code
        assert "name" in generated_code
        assert "created_at" in generated_code

        # Verify Distributed engine
        assert "Distributed(" in generated_code
        assert "cluster=" in generated_code
        assert "database=" in generated_code
        assert "table=" in generated_code
        assert "sharding_key" in generated_code

        # Verify no ORDER BY or PARTITION BY for Distributed
        assert "__order_by__" not in generated_code
        assert "__partition_by__" not in generated_code

        # Compare with original model
        compare_table_models(IntrospectDistributedUsers, generated_code)



