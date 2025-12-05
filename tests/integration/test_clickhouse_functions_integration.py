"""Integration tests for ClickHouse-specific functions with real ClickHouse."""

import os
import pytest
from chorm import Table, Column, MergeTree, select, insert, create_engine
from chorm.session import Session
from chorm.types import UInt64, String, Date, Float64, Array
from chorm.sql.expression import (
    func,
    uniq,
    median,
    quantile,
    group_array,
    stddev_pop,
    var_pop,
    corr,
    to_start_of_month,
    date_diff,
    now,
    today,
    concat,
    substring,
    position,
    length,
)


# Skip integration tests if ClickHouse is not available
pytestmark = pytest.mark.skipif(
    os.getenv("CLICKHOUSE_HOST") is None,
    reason="ClickHouse not configured (set CLICKHOUSE_HOST env var)",
)


class User(Table):
    __tablename__ = "test_users_ch_functions"
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    email = Column(String())
    age = Column(UInt64())
    city = Column(String())
    tags = Column(Array(String()))
    engine = MergeTree()


class Order(Table):
    __tablename__ = "test_orders_ch_functions"
    id = Column(UInt64(), primary_key=True)
    user_id = Column(UInt64())
    amount = Column(Float64())
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
        User(id=1, name="Alice Smith", email="alice@example.com", age=25, city="Moscow", tags=["vip", "premium"]),
        User(id=2, name="Bob Jones", email="bob@test.com", age=30, city="SPB", tags=["regular"]),
        User(id=3, name="Charlie Brown", email="charlie@example.com", age=35, city="Moscow", tags=["vip"]),
        User(id=4, name="David Wilson", email="david@test.com", age=28, city="London", tags=["premium"]),
        User(id=5, name="Eve Davis", email="eve@example.com", age=32, city="London", tags=["regular", "vip"]),
    ]
    for user in users_data:
        session.execute(insert(User).values(**user.to_dict()))

    orders_data = [
        Order(id=1, user_id=1, amount=100.50, date="2024-01-15"),
        Order(id=2, user_id=1, amount=200.75, date="2024-02-20"),
        Order(id=3, user_id=2, amount=150.25, date="2024-01-10"),
        Order(id=4, user_id=3, amount=300.00, date="2024-03-05"),
        Order(id=5, user_id=4, amount=500.50, date="2024-01-20"),
        Order(id=6, user_id=1, amount=50.00, date="2024-02-15"),
        Order(id=7, user_id=2, amount=175.75, date="2024-03-10"),
        Order(id=8, user_id=5, amount=225.25, date="2024-02-25"),
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


def test_aggregation_functions(engine, setup_tables):
    """Test uniq, median, groupArray with real data."""
    session = Session(engine)

    stmt = select(
        func.count(Order.id).label("total_orders"),
        uniq(Order.user_id).label("unique_users"),
        median(Order.amount).label("median_amount"),
        group_array(Order.id).label("order_ids"),
    ).select_from(Order)

    result = session.execute(stmt).first()

    assert result.total_orders == 8
    assert result.unique_users == 5  # 5 different users
    assert 150 < result.median_amount < 200  # Median of amounts
    assert len(result.order_ids) == 8  # All order IDs collected


def test_median_and_stats(engine, setup_tables):
    """Test median and statistical functions."""
    session = Session(engine)

    stmt = select(
        median(Order.amount).label("median_amount"),
        func.avg(Order.amount).label("avg_amount"),
        stddev_pop(Order.amount).label("stddev"),
        var_pop(Order.amount).label("variance"),
    ).select_from(Order)

    result = session.execute(stmt).first()

    assert result.median_amount > 0
    assert result.avg_amount > 0
    assert result.stddev > 0
    # Variance = stddev^2
    assert abs(result.variance - result.stddev**2) < 0.01


def test_date_functions(engine, setup_tables):
    """Test toStartOfMonth, dateDiff, now."""
    session = Session(engine)

    stmt = (
        select(
            to_start_of_month(Order.date).label("month"),
            func.count(Order.id).label("order_count"),
            func.sum(Order.amount).label("monthly_total"),
        )
        .select_from(Order)
        .group_by(to_start_of_month(Order.date))
        .order_by(to_start_of_month(Order.date))
    )

    result = session.execute(stmt).all()

    # Should have 3 months (Jan, Feb, Mar 2024)
    assert len(result) == 3

    # Test dateDiff with now
    stmt2 = select(Order.date, date_diff("day", Order.date, today()).label("days_ago")).select_from(Order).limit(1)

    result2 = session.execute(stmt2).first()
    assert result2.days_ago > 0  # Order is in the past


def test_string_functions(engine, setup_tables):
    """Test substring and length functions."""
    session = Session(engine)

    stmt = (
        select(
            User.name,
            substring(User.email, 1, 5).label("email_prefix"),
            length(User.name).label("name_length"),
            length(User.email).label("email_length"),
        )
        .select_from(User)
        .where(User.id == 1)
    )

    result = session.execute(stmt).first()

    assert result.email_prefix == "alice"
    assert result.name_length == len("Alice Smith")
    assert result.email_length == len("alice@example.com")


def test_statistical_functions(engine, setup_tables):
    """Test stddevPop, varPop, corr."""
    session = Session(engine)

    stmt = select(
        func.avg(User.age).label("avg_age"),
        stddev_pop(User.age).label("stddev_age"),
        var_pop(User.age).label("var_age"),
    ).select_from(User)

    result = session.execute(stmt).first()

    assert 25 < result.avg_age < 35
    assert result.stddev_age > 0
    assert result.var_age > 0
    # Variance = stddev^2
    assert abs(result.var_age - result.stddev_age**2) < 0.01

    # Test correlation between age and order amount
    stmt2 = (
        select(corr(User.age, Order.amount).label("correlation"))
        .select_from(User)
        .join(Order, on=User.id == Order.user_id)
    )

    result2 = session.execute(stmt2).first()
    # Correlation should be between -1 and 1
    assert -1 <= result2.correlation <= 1
