"""Integration tests for CTEs (Common Table Expressions) with real ClickHouse."""

import os
import pytest
from chorm import Table, Column, MergeTree, select, insert, create_engine
from chorm.session import Session
from chorm.types import UInt64, String
from chorm.sql.expression import func, Identifier


# Skip integration tests if ClickHouse is not available
pytestmark = pytest.mark.skipif(
    os.getenv("CLICKHOUSE_HOST") is None,
    reason="ClickHouse not configured (set CLICKHOUSE_HOST env var)",
)


class User(Table):
    __tablename__ = "test_users_cte"
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    city = Column(String())
    active = Column(UInt64())
    engine = MergeTree()


class Order(Table):
    __tablename__ = "test_orders_cte"
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
        User(id=1, name="Alice", city="Moscow", active=1),
        User(id=2, name="Bob", city="SPB", active=1),
        User(id=3, name="Charlie", city="Moscow", active=0),
        User(id=4, name="David", city="SPB", active=1),
    ]
    for user in users_data:
        session.execute(insert(User).values(**user.to_dict()))

    # Orders
    orders_data = [
        Order(id=1, user_id=1, amount=1000),
        Order(id=2, user_id=1, amount=2000),
        Order(id=3, user_id=2, amount=1500),
        Order(id=4, user_id=3, amount=500),
        Order(id=5, user_id=4, amount=3000),
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


def test_cte_basic_execution(engine, setup_tables):
    """Test basic CTE execution with real ClickHouse."""
    session = Session(engine)

    # Create a CTE for Moscow users
    cte = select(User.id, User.name).where(User.city == "Moscow").cte("moscow_users")
    stmt = select(Identifier("*")).select_from(Identifier("moscow_users")).with_cte(cte)

    result = session.execute(stmt).all()

    # Should return Alice and Charlie
    assert len(result) == 2
    names = {row[1] for row in result}
    assert "Alice" in names
    assert "Charlie" in names


def test_cte_with_aggregation(engine, setup_tables):
    """Test CTE with GROUP BY and aggregation."""
    session = Session(engine)

    # Create a CTE that aggregates orders by user
    cte = select(Order.user_id, func.sum(Order.amount).label("total")).group_by(Order.user_id).cte("user_totals")

    # Query the CTE
    stmt = (
        select(Identifier("user_totals.user_id"), Identifier("user_totals.total"))
        .select_from(Identifier("user_totals"))
        .where(Identifier("user_totals.total") > 1000)
        .with_cte(cte)
    )

    result = session.execute(stmt).all()

    # Users with total > 1000: Alice (3000), Bob (1500), David (3000)
    assert len(result) == 3
    user_ids = {row[0] for row in result}
    assert 1 in user_ids  # Alice
    assert 2 in user_ids  # Bob
    assert 4 in user_ids  # David


def test_multiple_ctes(engine, setup_tables):
    """Test multiple CTEs in single query."""
    session = Session(engine)

    # CTE 1: Active users
    cte1 = select(User.id, User.name).where(User.active == 1).cte("active_users")

    # CTE 2: Moscow users
    cte2 = select(User.id, User.name).where(User.city == "Moscow").cte("moscow_users")

    # Query that uses both CTEs (UNION them)
    stmt1 = select(Identifier("*")).select_from(Identifier("active_users")).with_cte(cte1, cte2)
    stmt2 = select(Identifier("*")).select_from(Identifier("moscow_users")).with_cte(cte1, cte2)

    # Test first CTE
    result1 = session.execute(stmt1).all()
    assert len(result1) == 3  # Alice, Bob, David are active

    # Test second CTE
    result2 = session.execute(stmt2).all()
    assert len(result2) == 2  # Alice and Charlie are from Moscow


def test_cte_with_join(engine, setup_tables):
    """Test CTE that contains a JOIN."""
    session = Session(engine)

    # Create a CTE with a JOIN
    cte = (
        select(User.name, Order.amount)
        .select_from(User)
        .join(Order, on=User.id == Order.user_id)
        .where(User.active == 1)
        .cte("active_user_orders")
    )

    # Query the CTE
    stmt = (
        select(Identifier("active_user_orders.name"), func.sum(Identifier("active_user_orders.amount")).label("total"))
        .select_from(Identifier("active_user_orders"))
        .group_by(Identifier("active_user_orders.name"))
        .with_cte(cte)
    )

    result = session.execute(stmt).all()

    # Active users: Alice (3000), Bob (1500), David (3000)
    assert len(result) == 3
    totals = {row[0]: int(row[1]) for row in result}
    assert totals["Alice"] == 3000
    assert totals["Bob"] == 1500
    assert totals["David"] == 3000


def test_cte_referenced_in_where(engine, setup_tables):
    """Test CTE referenced in WHERE clause."""
    session = Session(engine)

    # CTE with high-value orders
    cte = select(Order.user_id).where(Order.amount > 2000).cte("high_value_users")

    # Find users who made high-value orders
    stmt = select(User.name).where(User.id.in_(Identifier("high_value_users"))).with_cte(cte)

    result = session.execute(stmt).all()

    # Only David has an order > 2000 (3000)
    assert len(result) == 1
    assert result[0][0] == "David"
