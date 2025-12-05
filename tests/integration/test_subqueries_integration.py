"""Integration tests for Subqueries functionality with real ClickHouse."""

import os
import pytest
from chorm import Table, Column, MergeTree, select, insert, create_engine
from chorm.session import Session
from chorm.types import UInt64, String
from chorm.sql.expression import func, exists, Identifier


# Skip integration tests if ClickHouse is not available
pytestmark = pytest.mark.skipif(
    os.getenv("CLICKHOUSE_HOST") is None,
    reason="ClickHouse not configured (set CLICKHOUSE_HOST env var)",
)


class User(Table):
    __tablename__ = "test_users_subq"
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    city = Column(String())
    engine = MergeTree()


class Order(Table):
    __tablename__ = "test_orders_subq"
    id = Column(UInt64(), primary_key=True)
    user_id = Column(UInt64())
    amount = Column(UInt64())
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
    # Users
    users_data = [
        User(id=1, name="Alice", city="Moscow"),
        User(id=2, name="Bob", city="SPB"),
        User(id=3, name="Charlie", city="Moscow"),
    ]
    for user in users_data:
        session.execute(insert(User).values(**user.to_dict()))

    # Orders
    orders_data = [
        Order(id=1, user_id=1, amount=1000),
        Order(id=2, user_id=1, amount=2000),
        Order(id=3, user_id=2, amount=1500),
        Order(id=4, user_id=3, amount=500),
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


def test_subquery_in_where_in_integration(engine, setup_tables):
    """Test subquery in WHERE IN clause with real ClickHouse."""
    session = Session(engine)

    # Find users who have placed orders with amount > 1000
    subq = select(Order.user_id).where(Order.amount > 1000).subquery()
    stmt = select(User.name).where(User.id.in_(subq))

    result = session.execute(stmt).all()

    # Should return Alice (order 2000) and Bob (order 1500)
    assert len(result) == 2
    names = {row[0] for row in result}
    assert "Alice" in names
    assert "Bob" in names


def test_subquery_exists_integration(engine, setup_tables):
    """Test EXISTS subquery with real ClickHouse."""
    session = Session(engine)

    # Find users who have at least one order
    subq = select(Order.id).where(Order.user_id == User.id)
    stmt = select(User.name).where(exists(subq))

    result = session.execute(stmt).all()

    # All 3 users have orders
    assert len(result) == 3


def test_subquery_in_from_integration(engine, setup_tables):
    """Test subquery in FROM clause with real ClickHouse."""
    session = Session(engine)

    # Select from a subquery that filters users by city
    subq = select(User.name, User.city).where(User.city == "Moscow").subquery("moscow_users")
    stmt = select(Identifier("*")).select_from(subq)

    result = session.execute(stmt).all()

    # Should return Alice and Charlie
    assert len(result) == 2
    names = {row[0] for row in result}
    assert "Alice" in names
    assert "Charlie" in names


def test_scalar_subquery_integration(engine, setup_tables):
    """Test scalar subquery in SELECT list with real ClickHouse."""
    session = Session(engine)

    # Select user name and count of their orders
    subq = (
        select(func.count(Order.id))
        .select_from(Order)
        .where(Order.user_id == User.id)
        .scalar_subquery()
        .label("order_count")
    )
    stmt = select(User.name, subq).select_from(User)

    result = session.execute(stmt).all()

    # Verify counts
    counts = {row[0]: int(row[1]) for row in result}
    assert counts["Alice"] == 2
    assert counts["Bob"] == 1
    assert counts["Charlie"] == 1


def test_scalar_subquery_comparison_integration(engine, setup_tables):
    """Test scalar subquery in comparison with real ClickHouse."""
    session = Session(engine)

    # Find orders with amount greater than average amount
    avg_amount = select(func.avg(Order.amount)).select_from(Order).scalar_subquery()
    stmt = select(Order.id, Order.amount).select_from(Order).where(Order.amount > avg_amount)

    # Average is (1000+2000+1500+500)/4 = 1250
    # Orders > 1250 are: 2000 (id 2) and 1500 (id 3)

    result = session.execute(stmt).all()

    assert len(result) == 2
    ids = {row[0] for row in result}
    assert 2 in ids
    assert 3 in ids
