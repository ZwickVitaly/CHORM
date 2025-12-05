"""Integration tests for Result API with real ClickHouse."""

import os
import pytest
from chorm import Table, Column, MergeTree, select, insert, create_engine
from chorm.session import Session
from chorm.types import UInt64, String, Date
from chorm.sql.expression import func


# Skip integration tests if ClickHouse is not available
pytestmark = pytest.mark.skipif(
    os.getenv("CLICKHOUSE_HOST") is None,
    reason="ClickHouse not configured (set CLICKHOUSE_HOST env var)",
)


class User(Table):
    __tablename__ = "test_users_result_api"
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    city = Column(String())
    age = Column(UInt64())
    engine = MergeTree()


class Order(Table):
    __tablename__ = "test_orders_result_api"
    id = Column(UInt64(), primary_key=True)
    user_id = Column(UInt64())
    amount = Column(UInt64())
    status = Column(String())
    date = Column(Date())
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
        session.execute(f"DROP TABLE IF EXISTS {User.__tablename__}")
        session.execute(f"DROP TABLE IF EXISTS {Order.__tablename__}")
    except Exception:
        pass

    # Create tables
    session.execute(User.create_table(exists_ok=True))
    session.execute(Order.create_table(exists_ok=True))

    # Insert test data
    users_data = [
        User(id=1, name="Alice", city="Moscow", age=25),
        User(id=2, name="Bob", city="SPB", age=30),
        User(id=3, name="Charlie", city="Moscow", age=35),
    ]
    for user in users_data:
        session.execute(insert(User).values(**user.to_dict()))

    orders_data = [
        Order(id=1, user_id=1, amount=100, status="completed", date="2024-01-15"),
        Order(id=2, user_id=1, amount=200, status="active", date="2024-02-20"),
        Order(id=3, user_id=2, amount=150, status="completed", date="2024-01-10"),
        Order(id=4, user_id=3, amount=300, status="pending", date="2024-03-05"),
    ]
    for order in orders_data:
        session.execute(insert(Order).values(**order.to_dict()))

    session.commit()

    yield

    # Cleanup
    try:
        session.execute(f"DROP TABLE IF EXISTS {User.__tablename__}")
        session.execute(f"DROP TABLE IF EXISTS {Order.__tablename__}")
        session.commit()
    except Exception:
        pass


def test_row_access_with_aggregations(engine, setup_tables):
    """Test Row access with labeled aggregations."""
    session = Session(engine)

    stmt = (
        select(User.city, func.count(User.id).label("user_count"), func.avg(User.age).label("avg_age"))
        .select_from(User)
        .group_by(User.city)
        .order_by(User.city)
    )

    result = session.execute(stmt).all()

    # Test Row attribute access
    assert len(result) == 2  # Moscow and SPB

    moscow_row = result[0]
    assert moscow_row.city == "Moscow"
    assert moscow_row.user_count == 2
    assert moscow_row.avg_age == 30.0  # (25 + 35) / 2

    spb_row = result[1]
    assert spb_row.city == "SPB"
    assert spb_row.user_count == 1
    assert spb_row.avg_age == 30.0


def test_mappings_with_joins(engine, setup_tables):
    """Test dict access with JOIN results."""
    session = Session(engine)

    stmt = (
        select(User.name, func.count(Order.id).label("order_count"), func.sum(Order.amount).label("total_amount"))
        .select_from(User)
        .join(Order, on=User.id == Order.user_id)
        .group_by(User.name)
        .order_by(User.name)
    )

    # Use mappings() to get dicts
    result = session.execute(stmt).mappings().all()

    assert len(result) == 3
    assert isinstance(result[0], dict)

    alice_dict = result[0]
    assert alice_dict["name"] == "Alice"
    assert alice_dict["order_count"] == 2
    assert alice_dict["total_amount"] == 300


def test_scalars_with_column_names(engine, setup_tables):
    """Test scalar extraction by column name."""
    session = Session(engine)

    stmt = select(User.name, User.age).select_from(User).order_by(User.name)

    # Extract names using column name
    names = session.execute(stmt).scalars("name").all()
    assert names == ["Alice", "Bob", "Charlie"]

    # Extract ages using column name
    ages = session.execute(stmt).scalars("age").all()
    assert ages == [25, 30, 35]


def test_mixed_access_patterns(engine, setup_tables):
    """Test switching between Row/dict/tuple access."""
    session = Session(engine)

    stmt = select(User.name, User.city).select_from(User).where(User.id == 1)

    result = session.execute(stmt)

    # Access as Row (default)
    row = result.first()
    assert row.name == "Alice"
    assert row.city == "Moscow"

    # Re-execute and access as dict
    result = session.execute(stmt)
    dict_row = result.mappings().first()
    assert dict_row["name"] == "Alice"
    assert dict_row["city"] == "Moscow"

    # Re-execute and access as tuple
    result = session.execute(stmt)
    tuple_row = result.tuples().first()
    assert tuple_row == ("Alice", "Moscow")


def test_scalar_convenience_methods(engine, setup_tables):
    """Test scalar convenience methods."""
    session = Session(engine)

    # Test scalar() - get single value
    count_stmt = select(func.count(User.id)).select_from(User)
    total_users = session.execute(count_stmt).scalar()
    assert total_users == 3

    # Test scalar_one() - ensure exactly one result
    max_age_stmt = select(func.max(User.age)).select_from(User)
    max_age = session.execute(max_age_stmt).scalars().scalar_one()
    assert max_age == 35

    # Test scalar_one_or_none() - single result or None
    name_stmt = select(User.name).select_from(User).where(User.id == 1)
    name = session.execute(name_stmt).scalars().scalar_one()
    assert name == "Alice"
