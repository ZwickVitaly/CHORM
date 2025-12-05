"""Integration tests for GROUP BY and HAVING functionality with real ClickHouse."""

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
    __tablename__ = "test_users_group_by"
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    city = Column(String())
    country = Column(String())
    engine = MergeTree()


class Order(Table):
    __tablename__ = "test_orders_group_by"
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
    # Users
    users_data = [
        User(id=1, name="Alice", city="Moscow", country="Russia"),
        User(id=2, name="Bob", city="SPB", country="Russia"),
        User(id=3, name="Charlie", city="Moscow", country="Russia"),
        User(id=4, name="David", city="London", country="UK"),
        User(id=5, name="Eve", city="London", country="UK"),
    ]
    for user in users_data:
        session.execute(insert(User).values(**user.to_dict()))

    # Orders
    orders_data = [
        Order(id=1, user_id=1, amount=100, status="completed", date="2024-01-01"),
        Order(id=2, user_id=1, amount=200, status="completed", date="2024-01-02"),
        Order(id=3, user_id=2, amount=150, status="pending", date="2024-01-03"),
        Order(id=4, user_id=3, amount=300, status="completed", date="2024-01-04"),
        Order(id=5, user_id=4, amount=500, status="failed", date="2024-01-05"),
        Order(id=6, user_id=1, amount=50, status="pending", date="2024-01-06"),
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


def test_group_by_count_integration(engine, setup_tables):
    """Test GROUP BY with COUNT."""
    session = Session(engine)

    stmt = select(User.city, func.count(User.id)).group_by(User.city).order_by(User.city)

    result = session.execute(stmt).all()

    # Expected: London: 2, Moscow: 2, SPB: 1
    # Sorted by city: London, Moscow, SPB
    assert len(result) == 3
    assert result[0][0] == "London" and result[0][1] == 2
    assert result[1][0] == "Moscow" and result[1][1] == 2
    assert result[2][0] == "SPB" and result[2][1] == 1


def test_group_by_multiple_columns_integration(engine, setup_tables):
    """Test GROUP BY with multiple columns."""
    session = Session(engine)

    stmt = (
        select(User.country, User.city, func.count(User.id))
        .group_by(User.country, User.city)
        .order_by(User.country, User.city)
    )

    result = session.execute(stmt).all()

    # Expected: Russia/Moscow: 2, Russia/SPB: 1, UK/London: 2
    assert len(result) == 3
    # Use index access for Row objects
    assert result[0][0] == "Russia" and result[0][1] == "Moscow" and result[0][2] == 2
    assert result[1][0] == "Russia" and result[1][1] == "SPB" and result[1][2] == 1
    assert result[2][0] == "UK" and result[2][1] == "London" and result[2][2] == 2


def test_having_integration(engine, setup_tables):
    """Test HAVING clause."""
    session = Session(engine)

    stmt = (
        select(User.city, func.count(User.id)).group_by(User.city).having(func.count(User.id) > 1).order_by(User.city)
    )

    result = session.execute(stmt).all()

    # Should only return cities with > 1 user (London, Moscow)
    assert len(result) == 2
    cities = {row[0] for row in result}
    assert "London" in cities
    assert "Moscow" in cities
    assert "SPB" not in cities


def test_aggregations_integration(engine, setup_tables):
    """Test various aggregation functions."""
    session = Session(engine)

    stmt = (
        select(Order.status, func.count(Order.id), func.sum(Order.amount), func.max(Order.amount))
        .group_by(Order.status)
        .order_by(Order.status)
    )

    result = session.execute(stmt).all()

    # Statuses: completed (3 orders), failed (1 order), pending (2 orders)
    # completed: 100+200+300 = 600
    # failed: 500
    # pending: 150+50 = 200

    # Build map using Row index access
    results_map = {row[0]: (row[1], row[2], row[3]) for row in result}

    assert results_map["completed"] == (3, 600, 300)
    assert results_map["failed"] == (1, 500, 500)
    assert results_map["pending"] == (2, 200, 150)


def test_group_by_expression_integration(engine, setup_tables):
    """Test GROUP BY with expression."""
    session = Session(engine)

    # Group by year-month of order date
    stmt = (
        select(func.toYYYYMM(Order.date), func.count(Order.id)).select_from(Order).group_by(func.toYYYYMM(Order.date))
    )

    result = session.execute(stmt).all()

    # All orders are in 202401
    assert len(result) == 1
    assert result[0][0] == 202401
    assert result[0][1] == 6
