import os

import pytest

from chorm import Column, MergeTree, Table, create_engine, insert, select
from chorm.async_engine import create_async_engine
from chorm.async_session import AsyncSession
from chorm.result import Row
from chorm.session import Session
from chorm.types import String, UInt64

# Skip integration tests if ClickHouse is not available
pytestmark = pytest.mark.skipif(
    os.getenv("CLICKHOUSE_HOST") is None,
    reason="ClickHouse not configured (set CLICKHOUSE_HOST env var)",
)


class StreamUser(Table):
    __tablename__ = "test_users_stream"
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    engine = MergeTree()


@pytest.fixture(scope="module")
def engine():
    """Create engine for tests."""
    host = os.getenv("CLICKHOUSE_HOST", "localhost")
    port = int(os.getenv("CLICKHOUSE_PORT", "8123"))
    database = os.getenv("CLICKHOUSE_DB", "default")
    password = os.getenv("CLICKHOUSE_PASSWORD", "123")

    return create_engine(
        host=host,
        port=port,
        username="default",
        password=password,
        database=database,
    )


@pytest.fixture(scope="module")
def async_engine():
    """Create async engine for tests."""
    host = os.getenv("CLICKHOUSE_HOST", "localhost")
    port = int(os.getenv("CLICKHOUSE_PORT", "8123"))
    database = os.getenv("CLICKHOUSE_DB", "default")
    password = os.getenv("CLICKHOUSE_PASSWORD", "123")

    return create_async_engine(
        host=host,
        port=port,
        username="default",
        password=password,
        database=database,
    )


@pytest.fixture(scope="module")
def setup_tables(engine):
    """Create test table and insert data."""
    session = Session(engine)

    try:
        session.execute(f"DROP TABLE IF EXISTS {StreamUser.__tablename__}")
    except Exception:
        pass

    session.execute(StreamUser.create_table(exists_ok=True))

    users_data = [
        StreamUser(id=1, name="Alice"),
        StreamUser(id=2, name="Bob"),
        StreamUser(id=3, name="Charlie"),
    ]
    for user in users_data:
        session.execute(insert(StreamUser).values(**user.to_dict()))

    session.commit()

    yield

    try:
        session.execute(f"DROP TABLE IF EXISTS {StreamUser.__tablename__}")
        session.commit()
    except Exception:
        pass


def test_sync_stream_integration(engine, setup_tables):
    """Test synchronous streaming with real ClickHouse connection."""
    session = Session(engine)
    stmt = select(StreamUser.id, StreamUser.name).select_from(StreamUser).order_by(StreamUser.id)

    # Test default Row streaming
    with session.stream(stmt) as stream:
        results = list(stream)
        assert len(results) == 3
        assert all(isinstance(r, Row) for r in results)
        assert results[0].id == 1
        assert results[0].name == "Alice"
        assert results[1].name == "Bob"

    # Test model mapping streaming
    with session.stream(stmt, model=StreamUser) as stream:
        users = list(stream)
        assert len(users) == 3
        assert all(isinstance(u, StreamUser) for u in users)
        assert users[0].id == 1
        assert users[0].name == "Alice"

    # Test scalar streaming
    with session.stream(stmt) as stream:
        names = list(stream.scalars("name"))
        assert names == ["Alice", "Bob", "Charlie"]

    # Test mappings streaming
    with session.stream(stmt) as stream:
        mappings = list(stream.mappings())
        assert mappings == [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
            {"id": 3, "name": "Charlie"},
        ]

    # Test raw tuples streaming
    with session.stream(stmt) as stream:
        tuples = list(stream.tuples())
        assert tuples == [(1, "Alice"), (2, "Bob"), (3, "Charlie")]


@pytest.mark.asyncio
async def test_async_stream_integration(async_engine, setup_tables):
    """Test asynchronous streaming with real ClickHouse connection."""
    session = AsyncSession(async_engine)
    stmt = select(StreamUser.id, StreamUser.name).select_from(StreamUser).order_by(StreamUser.id)

    # Test default Row streaming
    async with await session.stream(stmt) as stream:
        results = []
        async for r in stream:
            results.append(r)
        assert len(results) == 3
        assert all(isinstance(r, Row) for r in results)
        assert results[0].id == 1
        assert results[0].name == "Alice"

    # Test model mapping streaming
    async with await session.stream(stmt, model=StreamUser) as stream:
        users = []
        async for u in stream:
            users.append(u)
        assert len(users) == 3
        assert all(isinstance(u, StreamUser) for u in users)
        assert users[0].id == 1
        assert users[0].name == "Alice"

    # Test scalar streaming
    async with await session.stream(stmt) as stream:
        names = []
        async for name in stream.scalars("name"):
            names.append(name)
        assert names == ["Alice", "Bob", "Charlie"]

    # Test mappings streaming
    async with await session.stream(stmt) as stream:
        mappings = []
        async for m in stream.mappings():
            mappings.append(m)
        assert mappings == [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
            {"id": 3, "name": "Charlie"},
        ]

    # Test raw tuples streaming
    async with await session.stream(stmt) as stream:
        tuples = []
        async for t in stream.tuples():
            tuples.append(t)
        assert tuples == [(1, "Alice"), (2, "Bob"), (3, "Charlie")]
