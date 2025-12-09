"""Integration tests for Distributed table engine."""

import os
import pytest
from chorm import Table, Column, select, insert, create_engine
from chorm.session import Session
from chorm.types import UInt64, String, Date
from chorm.table_engines import Distributed, MergeTree
from chorm.sql.expression import func


# Skip integration tests if ClickHouse is not available
pytestmark = pytest.mark.skipif(
    os.getenv("CLICKHOUSE_HOST") is None,
    reason="ClickHouse not configured (set CLICKHOUSE_HOST env var)",
)


class LocalUsers(Table):
    """Local table on first ClickHouse instance."""
    __tablename__ = "test_local_users"
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    created_at = Column(Date())
    __engine__ = MergeTree()
    __order_by__ = ["id"]


class DistributedUsers(Table):
    """Distributed table pointing to local tables on cluster nodes."""
    __tablename__ = "test_distributed_users"
    id = Column(UInt64())
    name = Column(String())
    created_at = Column(Date())
    __engine__ = Distributed(
        cluster="default",  # Use built-in single-node 'default' cluster
        database="default",
        table="test_local_users",
        sharding_key="rand()"  # Required for INSERT with multiple shards
    )


@pytest.fixture(scope="module")
def engine():
    """Create engine for tests (single ClickHouse instance)."""
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
def setup_cluster_and_tables(engine):
    """Set up cluster configuration and create tables on single instance (loopback)."""
    session = Session(engine)

    try:
        # Check if 'default' cluster is available (it usually is)
        try:
            cluster_check = session.execute(
                "SELECT count() FROM system.clusters WHERE cluster = 'default'"
            ).scalar()
            if cluster_check == 0:
                pytest.skip("Cluster 'default' is not configured. Skipping Distributed table tests.")
        except Exception as e:
            pytest.skip(f"Failed to check cluster configuration: {e}. Skipping Distributed table tests.")

        # Drop tables if they exist
        session.execute(f"DROP TABLE IF EXISTS {DistributedUsers.__tablename__}")
        session.execute(f"DROP TABLE IF EXISTS {LocalUsers.__tablename__}")

        # Create local table 
        session.execute(LocalUsers.create_table(exists_ok=True))
        session.commit()

        # Create Distributed table pointing to local table via 'default' cluster
        try:
            session.execute(DistributedUsers.create_table(exists_ok=True))
            session.commit()
        except Exception as e:
            error_msg = str(e)
            if "CLUSTER_DOESNT_EXIST" in error_msg or "cluster" in error_msg.lower():
                pytest.skip(f"Cluster 'default' is not configured: {e}. Skipping Distributed table tests.")
            raise

        yield

    finally:
        # Cleanup
        try:
            session.execute(f"DROP TABLE IF EXISTS {DistributedUsers.__tablename__}")
            session.execute(f"DROP TABLE IF EXISTS {LocalUsers.__tablename__}")
            session.commit()
        except Exception:
            pass


def test_create_distributed_table(engine, setup_cluster_and_tables):
    """Test creating Distributed table."""
    session = Session(engine)

    # Verify Distributed table was created
    result = session.execute(
        f"SELECT engine FROM system.tables WHERE database = currentDatabase() AND name = '{DistributedUsers.__tablename__}'"
    ).all()

    assert len(result) > 0
    assert result[0][0] == "Distributed"


def test_distributed_table_structure(engine, setup_cluster_and_tables):
    """Test that Distributed table has correct structure."""
    session = Session(engine)

    # Verify columns exist
    result = session.execute(
        f"SELECT name, type FROM system.columns WHERE database = currentDatabase() AND table = '{DistributedUsers.__tablename__}' ORDER BY position"
    ).all()

    column_names = [row[0] for row in result]
    assert "id" in column_names
    assert "name" in column_names
    assert "created_at" in column_names


def test_insert_into_distributed_table(engine, setup_cluster_and_tables):
    """Test inserting data into Distributed table."""
    session = Session(engine)
    from datetime import date

    # Clear existing data
    session.execute(f"TRUNCATE TABLE IF EXISTS {DistributedUsers.__tablename__}")
    session.execute(f"TRUNCATE TABLE IF EXISTS {LocalUsers.__tablename__}")

    # Insert data via Dist table (should route to Local table)
    data = [
        LocalUsers(id=1, name="Alice", created_at=date(2024, 1, 1)),
        LocalUsers(id=2, name="Bob", created_at=date(2024, 1, 2)),
        LocalUsers(id=3, name="Charlie", created_at=date(2024, 1, 3)),
    ]

    for user in data:
        session.execute(insert(DistributedUsers).values(**user.to_dict()))
    
    session.commit()

    # Verify data was inserted
    # Note: Reads from Distributed might have slight replication delay if async, but loopback is usually immediate
    # We check the local table to be sure data arrived
    result_local = session.execute(select(func.count()).select_from(LocalUsers)).first()
    assert result_local[0] == 3

    # Check via Distributed table too
    result_dist = session.execute(select(func.count()).select_from(DistributedUsers)).first()
    assert result_dist[0] == 3


def test_select_from_distributed_table(engine, setup_cluster_and_tables):
    """Test selecting from Distributed table."""
    session = Session(engine)
    from datetime import date

    # Insert test data into Local table directly
    session.execute(f"TRUNCATE TABLE IF EXISTS {DistributedUsers.__tablename__}")
    session.execute(f"TRUNCATE TABLE IF EXISTS {LocalUsers.__tablename__}")

    data = [
        LocalUsers(id=1, name="Alice", created_at=date(2024, 1, 1)),
        LocalUsers(id=2, name="Bob", created_at=date(2024, 1, 2)),
    ]

    for user in data:
        session.execute(insert(LocalUsers).values(**user.to_dict()))
    
    session.commit()

    # Select from Distributed table
    results = session.execute(
        select(DistributedUsers.id, DistributedUsers.name, DistributedUsers.created_at)
        .select_from(DistributedUsers)
        .order_by(DistributedUsers.id)
    ).all()

    assert len(results) == 2
    assert results[0][1] == "Alice"
    assert results[1][1] == "Bob"


def test_distributed_table_with_sharding_key(engine, setup_cluster_and_tables):
    """Test Distributed table with sharding key."""
    session = Session(engine)

    # Create Distributed table with sharding key
    class DistributedUsersSharded(Table):
        __tablename__ = "test_distributed_users_sharded"
        id = Column(UInt64())
        name = Column(String())
        __engine__ = Distributed(
            cluster="default",
            database="default",
            table="test_local_users",
            sharding_key="id"
        )

    try:
        session.execute(f"DROP TABLE IF EXISTS {DistributedUsersSharded.__tablename__}")
        session.execute(DistributedUsersSharded.create_table(exists_ok=True))
        session.commit()

        # Verify table was created
        result = session.execute(
            f"SELECT engine_full FROM system.tables WHERE database = currentDatabase() AND name = '{DistributedUsersSharded.__tablename__}'"
        ).all()

        assert len(result) > 0
        engine_full = result[0][0]
        assert "default" in engine_full
        assert "id" in engine_full  # sharding key

    finally:
        try:
            session.execute(f"DROP TABLE IF EXISTS {DistributedUsersSharded.__tablename__}")
            session.commit()
        except Exception:
            pass
