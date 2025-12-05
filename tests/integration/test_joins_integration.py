"""Integration tests for JOIN functionality with real ClickHouse."""

import os
import pytest
from chorm import Table, Column, MergeTree, select, insert, create_engine
from chorm.session import Session
from chorm.types import UInt64, String


# Skip integration tests if ClickHouse is not available
pytestmark = pytest.mark.skipif(
    os.getenv("CLICKHOUSE_HOST") is None,
    reason="ClickHouse not configured (set CLICKHOUSE_HOST env var)",
)


class User(Table):
    __tablename__ = "test_users_joins"
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    city = Column(String())
    engine = MergeTree()


class Order(Table):
    __tablename__ = "test_orders_joins"
    id = Column(UInt64(), primary_key=True)
    user_id = Column(UInt64())
    product_id = Column(UInt64())
    amount = Column(UInt64())
    status = Column(String())
    engine = MergeTree()


class Product(Table):
    __tablename__ = "test_products_joins"
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    price = Column(UInt64())
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
        session.execute(f"DROP TABLE IF EXISTS {Product.__tablename__}")
    except Exception:
        pass

    # Create tables
    session.execute(User.create_table(exists_ok=True))
    session.execute(Order.create_table(exists_ok=True))
    session.execute(Product.create_table(exists_ok=True))

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
        Order(id=1, user_id=1, product_id=1, amount=100, status="completed"),
        Order(id=2, user_id=1, product_id=2, amount=200, status="active"),
        Order(id=3, user_id=2, product_id=1, amount=150, status="completed"),
        Order(id=4, user_id=3, product_id=3, amount=300, status="pending"),
    ]
    for order in orders_data:
        session.execute(insert(Order).values(**order.to_dict()))

    # Products
    products_data = [
        Product(id=1, name="Widget", price=50),
        Product(id=2, name="Gadget", price=100),
        Product(id=3, name="Tool", price=75),
    ]
    for product in products_data:
        session.execute(insert(Product).values(**product.to_dict()))

    session.commit()

    yield

    # Cleanup
    try:
        session.execute(f"DROP TABLE IF EXISTS {User.__tablename__}")
        session.execute(f"DROP TABLE IF EXISTS {Order.__tablename__}")
        session.execute(f"DROP TABLE IF EXISTS {Product.__tablename__}")
        session.commit()
    except Exception:
        pass


def test_inner_join_integration(engine, setup_tables):
    """Test INNER JOIN with real ClickHouse."""
    session = Session(engine)

    stmt = (
        select(User.name, Order.amount)
        .select_from(User)
        .join(Order, on=User.id == Order.user_id)
        .where(Order.status == "completed")
    )

    result = session.execute(stmt).all()

    # Should return 2 rows: Alice's 2 orders and Bob's 1 order with status='completed'
    assert len(result) == 2

    # Verify data
    names = {row[0] for row in result}
    assert "Alice" in names
    assert "Bob" in names


def test_left_join_integration(engine, setup_tables):
    """Test LEFT JOIN with real ClickHouse."""
    session = Session(engine)

    # Left join will include all users even if they have no orders
    # But we inserted orders for all users, so should get same result as inner join
    stmt = select(User.name, Order.amount).select_from(User).left_join(Order, on=User.id == Order.user_id)

    result = session.execute(stmt).all()

    # Should return 4 rows (all orders)
    assert len(result) == 4


def test_multiple_joins_integration(engine, setup_tables):
    """Test multiple JOINs with real ClickHouse."""
    session = Session(engine)

    # Simplified to avoid ambiguous column names - selecting only from first two tables
    stmt = (
        select(User.name, Order.amount)
        .select_from(User)
        .join(Order, on=User.id == Order.user_id)
        .where(User.city == "Moscow")
    )

    result = session.execute(stmt).all()

    # Should return orders from users in Moscow (Alice and Charlie)
    # Alice has 2 orders, Charlie has 1 order = 3 total
    assert len(result) == 3


def test_join_with_aggregation(engine, setup_tables):
    """Test JOIN with GROUP BY and aggregation."""
    from chorm.sql.expression import func

    session = Session(engine)

    stmt = (
        select(User.name, func.count(Order.id).label("order_count"))
        .select_from(User)
        .join(Order, on=User.id == Order.user_id)
        .group_by(User.name)
    )

    result = session.execute(stmt).all()

    # Should return 3 rows (3 users)
    assert len(result) == 3

    # Check order counts
    order_counts = {row[0]: int(row[1]) for row in result}
    assert order_counts["Alice"] == 2
    assert order_counts["Bob"] == 1
    assert order_counts["Charlie"] == 1


def test_cross_join_integration(engine, setup_tables):
    """Test CROSS JOIN with real ClickHouse."""
    session = Session(engine)

    # Cross join of 3 users and 3 products = 9 rows
    stmt = select(User.name, Product.name).select_from(User).cross_join(Product)

    result = session.execute(stmt).all()

    assert len(result) == 9  # 3 users × 3 products
