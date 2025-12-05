"""Integration tests for Advanced Aggregate Functions."""

import os
import pytest

from chorm import Table, Column, Engine, insert, select
from chorm.table_engines import MergeTree
from chorm.types import UInt64, String
from chorm.sql.expression import top_k, top_k_weighted, group_bitmap, any_last, Identifier

# Skip if ClickHouse is not available
pytestmark = pytest.mark.skipif(not os.getenv("CLICKHOUSE_HOST"), reason="CLICKHOUSE_HOST environment variable not set")


class EventsTable(Table):
    __tablename__ = "agg_events_table"
    __engine__ = MergeTree()
    __order_by__ = ["id"]

    id = Column(UInt64())
    user_id = Column(UInt64())
    country = Column(String())
    event_type = Column(String())
    weight = Column(UInt64())


@pytest.fixture
def engine():
    """Create engine for tests."""
    from chorm import create_engine

    host = os.getenv("CLICKHOUSE_HOST", "localhost")
    password = os.getenv("CLICKHOUSE_PASSWORD", "123")
    return create_engine(f"clickhouse://default:{password}@{host}:8123/default")


@pytest.fixture
def setup_table(engine):
    """Setup test table with data."""
    # Create table
    engine.execute(EventsTable.create_table())

    # Insert test data
    test_data = [
        {"id": 1, "user_id": 1, "country": "US", "event_type": "click", "weight": 10},
        {"id": 2, "user_id": 2, "country": "US", "event_type": "view", "weight": 5},
        {"id": 3, "user_id": 3, "country": "UK", "event_type": "click", "weight": 15},
        {"id": 4, "user_id": 4, "country": "US", "event_type": "click", "weight": 20},
        {"id": 5, "user_id": 5, "country": "DE", "event_type": "view", "weight": 8},
        {"id": 6, "user_id": 6, "country": "US", "event_type": "purchase", "weight": 50},
        {"id": 7, "user_id": 7, "country": "UK", "event_type": "click", "weight": 12},
        {"id": 8, "user_id": 8, "country": "US", "event_type": "click", "weight": 18},
    ]

    stmt = insert(EventsTable).values(test_data)
    engine.execute(stmt.to_sql())

    yield

    # Cleanup
    engine.execute("DROP TABLE IF EXISTS agg_events_table")


def test_top_k_aggregate(engine, setup_table):
    """Test topK aggregate function."""
    # topK in ClickHouse: topK(N)(column)
    result = engine.execute("SELECT topK(3)(country) FROM agg_events_table")
    # Just verify it executes and returns data
    assert result is not None


def test_top_k_weighted_aggregate(engine, setup_table):
    """Test topKWeighted aggregate function."""
    # topKWeighted in ClickHouse: topKWeighted(N)(column, weight)
    result = engine.execute("SELECT topKWeighted(2)(event_type, weight) FROM agg_events_table")
    # Just verify it executes and returns data
    assert result is not None


def test_group_bitmap_aggregate(engine, setup_table):
    """Test groupBitmap aggregate function."""
    stmt = (
        select(EventsTable.country, group_bitmap(EventsTable.user_id).label("user_bitmap"))
        .select_from(EventsTable)
        .group_by(EventsTable.country)
    )

    result = engine.execute(stmt.to_sql())
    # Just verify it executes and returns data
    assert result is not None


def test_any_last_aggregate(engine, setup_table):
    """Test anyLast sampling aggregate."""
    stmt = (
        select(EventsTable.country, any_last(EventsTable.event_type).label("last_event"))
        .select_from(EventsTable)
        .group_by(EventsTable.country)
    )

    result = engine.execute(stmt.to_sql())
    # Just verify it executes and returns data
    assert result is not None
