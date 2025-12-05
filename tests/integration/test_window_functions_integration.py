"""Integration tests for Window Functions functionality with real ClickHouse."""

import os
import pytest
from chorm import Table, Column, MergeTree, select, insert, create_engine
from chorm.session import Session
from chorm.types import UInt64, String, DateTime
from chorm.sql.expression import func, row_number, rank, dense_rank, lag, lead


# Skip integration tests if ClickHouse is not available
pytestmark = pytest.mark.skipif(
    os.getenv("CLICKHOUSE_HOST") is None,
    reason="ClickHouse not configured (set CLICKHOUSE_HOST env var)",
)


class User(Table):
    __tablename__ = "test_users_window"
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    department = Column(String())
    salary = Column(UInt64())
    engine = MergeTree()


class Order(Table):
    __tablename__ = "test_orders_window"
    id = Column(UInt64(), primary_key=True)
    user_id = Column(UInt64())
    amount = Column(UInt64())
    date = Column(DateTime())
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
        User(id=1, name="Alice", department="IT", salary=100000),
        User(id=2, name="Bob", department="IT", salary=90000),
        User(id=3, name="Charlie", department="HR", salary=80000),
        User(id=4, name="David", department="HR", salary=85000),
        User(id=5, name="Eve", department="IT", salary=95000),
    ]
    for user in users_data:
        session.execute(insert(User).values(**user.to_dict()))

    # Orders
    orders_data = [
        Order(id=1, user_id=1, amount=100, date="2024-01-01"),
        Order(id=2, user_id=1, amount=200, date="2024-01-02"),
        Order(id=3, user_id=1, amount=300, date="2024-01-03"),
        Order(id=4, user_id=2, amount=150, date="2024-01-01"),
        Order(id=5, user_id=2, amount=250, date="2024-01-02"),
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


def test_row_number_integration(engine, setup_tables):
    """Test ROW_NUMBER() window function."""
    session = Session(engine)

    # Rank users by salary within department
    stmt = (
        select(
            User.name,
            User.department,
            User.salary,
            func.row_number().over(partition_by=User.department, order_by=User.salary.desc()).label("rn"),
        )
        .select_from(User)
        .order_by(User.department, User.salary.desc())
    )

    result = session.execute(stmt).all()

    # HR: David (85k) -> 1, Charlie (80k) -> 2
    # IT: Alice (100k) -> 1, Eve (95k) -> 2, Bob (90k) -> 3

    results_map = {(row[0], row[1]): row[3] for row in result}

    assert results_map[("David", "HR")] == 1
    assert results_map[("Charlie", "HR")] == 2
    assert results_map[("Alice", "IT")] == 1
    assert results_map[("Eve", "IT")] == 2
    assert results_map[("Bob", "IT")] == 3


def test_rank_dense_rank_integration(engine, setup_tables):
    """Test RANK() and DENSE_RANK()."""
    session = Session(engine)

    # Add duplicate salary for testing rank
    user = User(id=6, name="Frank", department="IT", salary=90000)
    session.execute(insert(User).values(**user.to_dict()))

    stmt = (
        select(
            User.name,
            User.salary,
            func.rank().over(order_by=User.salary.desc()).label("rank"),
            func.dense_rank().over(order_by=User.salary.desc()).label("dense_rank"),
        )
        .select_from(User)
        .where(User.department == "IT")
        .order_by(User.salary.desc())
    )

    result = session.execute(stmt).all()

    # Salaries: 100k, 95k, 90k, 90k
    # Rank: 1, 2, 3, 3
    # Dense: 1, 2, 3, 3

    # Wait, rank behavior with duplicates:
    # 100k -> 1
    # 95k -> 2
    # 90k -> 3
    # 90k -> 3
    # Next would be 5 for rank, 4 for dense_rank

    # Let's check Bob and Frank (both 90k)
    ranks = {row[0]: (row[2], row[3]) for row in result}

    assert ranks["Alice"] == (1, 1)
    assert ranks["Eve"] == (2, 2)
    assert ranks["Bob"] == (3, 3)
    assert ranks["Frank"] == (3, 3)

    # Clean up extra user
    session.execute(f"ALTER TABLE {User.__tablename__} DELETE WHERE id = 6")


def test_lag_lead_integration(engine, setup_tables):
    """Test LAG() and LEAD()."""
    session = Session(engine)

    stmt = (
        select(
            Order.date,
            Order.amount,
            func.lag(Order.amount).over(partition_by=Order.user_id, order_by=Order.date).label("prev_amount"),
            func.lead(Order.amount).over(partition_by=Order.user_id, order_by=Order.date).label("next_amount"),
        )
        .select_from(Order)
        .where(Order.user_id == 1)
        .order_by(Order.date)
    )

    result = session.execute(stmt).all()

    # User 1 orders: 100 (1st), 200 (2nd), 300 (3rd)

    # Row 1: prev=None, next=200
    assert result[0][1] == 100
    assert result[0][2] is None or result[0][2] == 0  # ClickHouse might return default value for type
    assert result[0][3] == 200

    # Row 2: prev=100, next=300
    assert result[1][1] == 200
    assert result[1][2] == 100
    assert result[1][3] == 300

    # Row 3: prev=200, next=None
    assert result[2][1] == 300
    assert result[2][2] == 200
    assert result[2][3] is None or result[2][3] == 0


def test_cumulative_sum_integration(engine, setup_tables):
    """Test cumulative sum using window function."""
    session = Session(engine)

    stmt = (
        select(
            Order.date,
            Order.amount,
            func.sum(Order.amount)
            .over(
                partition_by=Order.user_id,
                order_by=Order.date,
                frame="ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW",
            )
            .label("running_total"),
        )
        .select_from(Order)
        .where(Order.user_id == 1)
        .order_by(Order.date)
    )

    result = session.execute(stmt).all()

    # User 1: 100, 200, 300
    # Running total: 100, 300, 600

    assert result[0][2] == 100
    assert result[1][2] == 300
    assert result[2][2] == 600
