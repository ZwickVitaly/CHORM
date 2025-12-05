"""Integration tests for ClickHouse conditional and array functions."""

import os
import pytest
from chorm import Table, Column, MergeTree, select, insert, create_engine
from chorm.session import Session
from chorm.types import UInt64, String, Float64, Array
from chorm.sql.expression import func, sum_if, count_if, avg_if, group_uniq_array, sum_array, avg_array


# Skip integration tests if ClickHouse is not available
pytestmark = pytest.mark.skipif(
    os.getenv("CLICKHOUSE_HOST") is None,
    reason="ClickHouse not configured (set CLICKHOUSE_HOST env var)",
)


class Order(Table):
    __tablename__ = "test_orders_conditional"
    id = Column(UInt64(), primary_key=True)
    user_id = Column(UInt64())
    amount = Column(Float64())
    status = Column(String())
    engine = MergeTree()


class User(Table):
    __tablename__ = "test_users_conditional"
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    tags = Column(Array(String()))
    scores = Column(Array(UInt64()))
    engine = MergeTree()


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
    """Create test tables and insert data."""
    session = Session(engine)

    # Drop tables if they exist
    try:
        session.execute(f"DROP TABLE IF EXISTS {Order.__tablename__}")
        session.execute(f"DROP TABLE IF EXISTS {User.__tablename__}")
    except Exception:
        pass

    # Create tables
    session.execute(Order.create_table(exists_ok=True))
    session.execute(User.create_table(exists_ok=True))

    # Insert test data
    orders_data = [
        Order(id=1, user_id=1, amount=100.0, status="completed"),
        Order(id=2, user_id=1, amount=200.0, status="completed"),
        Order(id=3, user_id=2, amount=150.0, status="pending"),
        Order(id=4, user_id=3, amount=300.0, status="completed"),
        Order(id=5, user_id=4, amount=500.0, status="failed"),
        Order(id=6, user_id=1, amount=50.0, status="pending"),
    ]
    for order in orders_data:
        session.execute(insert(Order).values(**order.to_dict()))

    users_data = [
        User(id=1, name="Alice", tags=["vip", "premium"], scores=[90, 85, 95]),
        User(id=2, name="Bob", tags=["regular"], scores=[70, 75]),
        User(id=3, name="Charlie", tags=["vip"], scores=[88, 92, 90, 94]),
        User(id=4, name="David", tags=["vip", "premium"], scores=[95, 98]),  # Same tags as Alice
    ]
    for user in users_data:
        session.execute(insert(User).values(**user.to_dict()))

    session.commit()

    yield

    # Cleanup
    try:
        session.execute(f"DROP TABLE IF EXISTS {Order.__tablename__}")
        session.execute(f"DROP TABLE IF EXISTS {User.__tablename__}")
        session.commit()
    except Exception:
        pass


def test_conditional_aggregations(engine, setup_tables):
    """Test sumIf, countIf, avgIf with real data."""
    session = Session(engine)

    stmt = select(
        sum_if(Order.amount, Order.status == "completed").label("completed_total"),
        sum_if(Order.amount, Order.status == "pending").label("pending_total"),
        count_if(Order.status == "completed").label("completed_count"),
        count_if(Order.status == "failed").label("failed_count"),
        avg_if(Order.amount, Order.status == "completed").label("completed_avg"),
    ).select_from(Order)

    result = session.execute(stmt).first()

    # 3 completed orders: 100 + 200 + 300 = 600
    assert result.completed_total == 600.0
    # 2 pending orders: 150 + 50 = 200
    assert result.pending_total == 200.0
    # 3 completed orders
    assert result.completed_count == 3
    # 1 failed order
    assert result.failed_count == 1
    # Average of completed: 600 / 3 = 200
    assert result.completed_avg == 200.0


def test_group_uniq_array(engine, setup_tables):
    """Test groupUniqArray to collect unique values."""
    session = Session(engine)

    stmt = select(
        func.count(User.id).label("user_count"), group_uniq_array(User.tags).label("all_unique_tags")
    ).select_from(User)

    result = session.execute(stmt).first()

    assert result.user_count == 4
    # groupUniqArray on Array(String) returns Array(Array(String))
    # Alice and David have identical tags ["vip", "premium"], so they should be deduplicated
    unique_tags_arrays = result.all_unique_tags

    # Should have 3 unique arrays: ["vip", "premium"], ["regular"], ["vip"]
    assert len(unique_tags_arrays) == 3

    # Verify the specific arrays exist
    assert ["vip", "premium"] in unique_tags_arrays
    assert ["regular"] in unique_tags_arrays
    assert ["vip"] in unique_tags_arrays


def test_array_functions(engine, setup_tables):
    """Test arraySum and arrayAvg with array columns."""
    session = Session(engine)

    stmt = (
        select(User.name, sum_array(User.scores).label("total_score"), avg_array(User.scores).label("avg_score"))
        .select_from(User)
        .where(User.id == 1)
    )

    result = session.execute(stmt).first()

    assert result.name == "Alice"
    # Alice scores: [90, 85, 95] -> sum = 270
    assert result.total_score == 270
    # Average: 270 / 3 = 90
    assert result.avg_score == 90.0
