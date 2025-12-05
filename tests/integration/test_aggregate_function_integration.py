"""Integration tests for AggregateFunction with AggregatingMergeTree."""

import os
import pytest
from chorm import Table, Column, select, insert, create_engine
from chorm.session import Session
from chorm.types import (
    UInt64,
    UInt32,
    UInt8,
    Float64,
    Date,
    AggregateFunction,
)
from chorm.sql import (
    sum_state,
    sum_merge,
    avg_state,
    avg_merge,
    count_state,
    count_merge,
    uniq_state,
    uniq_merge,
    uniq_exact_state,
    uniq_exact_merge,
    quantile_state,
    quantile_merge,
    min_state,
    min_merge,
    max_state,
    max_merge,
    sum_if_state,
    sum_if_merge,
    avg_if_state,
    avg_if_merge,
)
from chorm.sql.expression import func
from chorm.table_engines import AggregatingMergeTree, MergeTree


# Skip integration tests if ClickHouse is not available
pytestmark = pytest.mark.skipif(
    os.getenv("CLICKHOUSE_HOST") is None,
    reason="ClickHouse not configured (set CLICKHOUSE_HOST env var)",
)


class Metrics(Table):
    """Table with AggregateFunction columns for testing."""
    __tablename__ = "test_metrics_aggregate"
    date = Column(Date())
    revenue_state = Column(AggregateFunction("sum", (UInt64(),)))
    avg_state = Column(AggregateFunction("avg", (Float64(),)))
    count_state = Column(AggregateFunction("count", ()))
    uniq_state = Column(AggregateFunction("uniq", (UInt64(),)))
    uniq_exact_state = Column(AggregateFunction("uniqExact", (UInt64(),)))
    min_state = Column(AggregateFunction("min", (UInt64(),)))
    max_state = Column(AggregateFunction("max", (UInt64(),)))
    __engine__ = AggregatingMergeTree()
    __order_by__ = ["date"]


class MetricsWithIf(Table):
    """Table with AggregateFunction(sumIf, ...) columns."""
    __tablename__ = "test_metrics_if_aggregate"
    date = Column(Date())
    revenue_if_state = Column(AggregateFunction("sumIf", (UInt64(), UInt8())))
    avg_if_state = Column(AggregateFunction("avgIf", (Float64(), UInt8())))
    __engine__ = AggregatingMergeTree()
    __order_by__ = ["date"]


class Orders(Table):
    """Source table for generating aggregate states."""
    __tablename__ = "test_orders_for_aggregate"
    id = Column(UInt64(), primary_key=True)
    date = Column(Date())
    amount = Column(UInt64())
    user_id = Column(UInt64())
    status = Column(UInt32())
    __engine__ = MergeTree()
    __order_by__ = ["id", "date"]


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
        session.execute(f"DROP TABLE IF EXISTS {Metrics.__tablename__}")
        session.execute(f"DROP TABLE IF EXISTS {MetricsWithIf.__tablename__}")
        session.execute(f"DROP TABLE IF EXISTS {Orders.__tablename__}")
    except Exception:
        pass

    # Create source table
    session.execute(Orders.create_table(exists_ok=True))

    # Insert source data
    from datetime import date
    orders_data = [
        Orders(id=1, date=date(2024, 1, 1), amount=100, user_id=1, status=1),
        Orders(id=2, date=date(2024, 1, 1), amount=200, user_id=2, status=1),
        Orders(id=3, date=date(2024, 1, 1), amount=150, user_id=1, status=0),
        Orders(id=4, date=date(2024, 1, 2), amount=300, user_id=3, status=1),
        Orders(id=5, date=date(2024, 1, 2), amount=50, user_id=2, status=0),
    ]
    for order in orders_data:
        session.execute(insert(Orders).values(**order.to_dict()))

    # Create AggregatingMergeTree tables
    session.execute(Metrics.create_table(exists_ok=True))
    session.execute(MetricsWithIf.create_table(exists_ok=True))

    session.commit()

    yield

    # Cleanup
    try:
        session.execute(f"DROP TABLE IF EXISTS {Metrics.__tablename__}")
        session.execute(f"DROP TABLE IF EXISTS {MetricsWithIf.__tablename__}")
        session.execute(f"DROP TABLE IF EXISTS {Orders.__tablename__}")
        session.commit()
    except Exception:
        pass


def test_create_aggregating_mergetree_table(engine, setup_tables):
    """Test creating AggregatingMergeTree table with AggregateFunction columns."""
    session = Session(engine)

    # Verify table was created
    result = session.execute(
        f"SELECT name, type FROM system.columns WHERE table = '{Metrics.__tablename__}' AND database = currentDatabase()"
    ).all()

    column_types = {row[0]: row[1] for row in result}
    
    assert "revenue_state" in column_types
    assert "AggregateFunction" in column_types["revenue_state"]
    assert "sum" in column_types["revenue_state"]
    
    assert "avg_state" in column_types
    assert "AggregateFunction" in column_types["avg_state"]
    
    assert "count_state" in column_types
    assert "AggregateFunction" in column_types["count_state"]


def test_insert_aggregate_states(engine, setup_tables):
    """Test inserting data into AggregateFunction columns using State combinators."""
    session = Session(engine)

    # Clear existing data
    session.execute(f"TRUNCATE TABLE IF EXISTS {Metrics.__tablename__}")

    # Insert aggregate states from source table
    stmt = insert(Metrics).from_select(
        select(
            Orders.date,
            sum_state(Orders.amount).label("revenue_state"),
            avg_state(func.toFloat64(Orders.amount)).label("avg_state"),
            count_state().label("count_state"),
            uniq_state(Orders.user_id).label("uniq_state"),
            uniq_exact_state(Orders.user_id).label("uniq_exact_state"),
            min_state(Orders.amount).label("min_state"),
            max_state(Orders.amount).label("max_state"),
        )
        .select_from(Orders)
        .group_by(Orders.date)
    )

    session.execute(stmt)
    session.commit()

    # Verify data was inserted
    result = session.execute(select(func.count()).select_from(Metrics)).first()
    assert result[0] > 0


def test_select_aggregate_states_with_merge(engine, setup_tables):
    """Test selecting from AggregateFunction columns using Merge combinators."""
    session = Session(engine)

    # Clear existing data
    session.execute(f"TRUNCATE TABLE IF EXISTS {Metrics.__tablename__}")

    # First insert some data
    stmt = insert(Metrics).from_select(
        select(
            Orders.date,
            sum_state(Orders.amount).label("revenue_state"),
            avg_state(func.toFloat64(Orders.amount)).label("avg_state"),
            count_state().label("count_state"),
            uniq_state(Orders.user_id).label("uniq_state"),
            uniq_exact_state(Orders.user_id).label("uniq_exact_state"),
            min_state(Orders.amount).label("min_state"),
            max_state(Orders.amount).label("max_state"),
        )
        .select_from(Orders)
        .group_by(Orders.date)
    )
    session.execute(stmt)
    session.commit()

    # Select and merge aggregate states
    stmt = select(
        Metrics.date,
        sum_merge(Metrics.revenue_state).label("total_revenue"),
        avg_merge(Metrics.avg_state).label("avg_amount"),
        count_merge(Metrics.count_state).label("total_count"),
        uniq_merge(Metrics.uniq_state).label("unique_users"),
        uniq_exact_merge(Metrics.uniq_exact_state).label("unique_users_exact"),
        min_merge(Metrics.min_state).label("min_amount"),
        max_merge(Metrics.max_state).label("max_amount"),
    ).select_from(Metrics).group_by(Metrics.date).order_by(Metrics.date)

    results = session.execute(stmt).all()

    assert len(results) > 0
    
    # Verify merged values
    for row in results:
        assert row.total_revenue is not None
        assert row.avg_amount is not None
        assert row.total_count is not None
        assert row.unique_users is not None
        assert row.unique_users_exact is not None
        assert row.min_amount is not None
        assert row.max_amount is not None


def test_aggregate_function_with_sumif(engine, setup_tables):
    """Test AggregateFunction with sumIf (multiple arguments)."""
    session = Session(engine)

    # Clear existing data
    session.execute(f"TRUNCATE TABLE IF EXISTS {MetricsWithIf.__tablename__}")

    # Insert data with sumIfState
    stmt = insert(MetricsWithIf).from_select(
        select(
            Orders.date,
            sum_if_state(Orders.amount, Orders.status == 1).label("revenue_if_state"),
            avg_if_state(func.toFloat64(Orders.amount), Orders.status == 1).label("avg_if_state"),
        )
        .select_from(Orders)
        .group_by(Orders.date)
    )

    session.execute(stmt)
    session.commit()

    # Select and merge
    stmt = select(
        MetricsWithIf.date,
        sum_if_merge(MetricsWithIf.revenue_if_state).label("total_revenue"),
        avg_if_merge(MetricsWithIf.avg_if_state).label("avg_amount"),
    ).select_from(MetricsWithIf).group_by(MetricsWithIf.date).order_by(MetricsWithIf.date)

    results = session.execute(stmt).all()

    assert len(results) > 0
    
    for row in results:
        assert row.total_revenue is not None
        assert row.avg_amount is not None


def test_aggregate_function_merge_multiple_rows(engine, setup_tables):
    """Test that Merge correctly combines multiple aggregate states."""
    session = Session(engine)

    from datetime import date

    # Insert multiple rows with same date (should be merged by AggregatingMergeTree)
    # First, clear existing data
    session.execute(f"TRUNCATE TABLE {Metrics.__tablename__}")
    
    # Insert data grouped by date - need all columns from Metrics table
    stmt = insert(Metrics).from_select(
        select(
            Orders.date,
            sum_state(Orders.amount).label("revenue_state"),
            avg_state(func.toFloat64(Orders.amount)).label("avg_state"),
            count_state().label("count_state"),
            uniq_state(Orders.user_id).label("uniq_state"),
            uniq_exact_state(Orders.user_id).label("uniq_exact_state"),
            min_state(Orders.amount).label("min_state"),
            max_state(Orders.amount).label("max_state"),
        )
        .select_from(Orders)
        .group_by(Orders.date)
    )
    session.execute(stmt)
    session.commit()

    # Force merge (optimize table)
    session.execute(f"OPTIMIZE TABLE {Metrics.__tablename__} FINAL")
    session.commit()

    # Select merged values
    stmt = select(
        Metrics.date,
        sum_merge(Metrics.revenue_state).label("total_revenue"),
        count_merge(Metrics.count_state).label("total_count"),
    ).select_from(Metrics).group_by(Metrics.date).order_by(Metrics.date)

    results = session.execute(stmt).all()

    # Should have aggregated values
    total_revenue = sum(row.total_revenue for row in results)
    total_count = sum(row.total_count for row in results)
    
    # Total from source: 100 + 200 + 150 + 300 + 50 = 800
    assert total_revenue == 800
    # Total count: 5 orders
    assert total_count == 5


def test_aggregate_function_with_quantile(engine, setup_tables):
    """Test AggregateFunction with quantile function."""
    session = Session(engine)

    # Create table with quantile
    # In ClickHouse, quantileState is a parameterized function: quantileState(0.5)(value)
    class MetricsQuantile(Table):
        __tablename__ = "test_metrics_quantile"
        date = Column(Date())
        quantile_state = Column(AggregateFunction("quantile(0.5)", (UInt64(),)))
        __engine__ = AggregatingMergeTree()
        __order_by__ = ["date"]

    try:
        session.execute(f"DROP TABLE IF EXISTS {MetricsQuantile.__tablename__}")
        session.execute(MetricsQuantile.create_table(exists_ok=True))

        # Insert with quantileState - quantileState(0.5)(value) syntax
        stmt = insert(MetricsQuantile).from_select(
            select(
                Orders.date,
                quantile_state(0.5, Orders.amount).label("quantile_state"),
            )
            .select_from(Orders)
            .group_by(Orders.date)
        )
        session.execute(stmt)
        session.commit()

        # Select with quantileMerge - quantileMerge(0.5)(state) syntax
        stmt = select(
            MetricsQuantile.date,
            quantile_merge(0.5, MetricsQuantile.quantile_state).label("median_amount"),
        ).select_from(MetricsQuantile).group_by(MetricsQuantile.date).order_by(MetricsQuantile.date)

        results = session.execute(stmt).all()
        assert len(results) > 0

        for row in results:
            assert row.median_amount is not None

    finally:
        try:
            session.execute(f"DROP TABLE IF EXISTS {MetricsQuantile.__tablename__}")
        except Exception:
            pass

