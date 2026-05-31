import asyncio
from typing import Any, List, Optional

import pytest

from chorm.declarative import Column, Table
from chorm.exceptions import MultipleResultsFound, NoResultFound
from chorm.result import (
    AsyncMappingStreamResult,
    AsyncScalarStreamResult,
    AsyncStreamResult,
    AsyncTupleStreamResult,
    MappingStreamResult,
    Row,
    ScalarStreamResult,
    StreamResult,
    TupleStreamResult,
)
from chorm.types import Int32, String


# Mock source object that holds column names
class MockSource:
    def __init__(self, columns: List[str]) -> None:
        self.column_names = columns


# Mock stream context that yields row blocks
class MockStreamContext:
    def __init__(self, blocks: List[List[tuple]], columns: List[str]) -> None:
        self.blocks = blocks
        self.source = MockSource(columns)
        self.entered = False
        self.exited = False

    def __enter__(self) -> "MockStreamContext":
        self.entered = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.exited = True

    def __iter__(self):
        return iter(self.blocks)

    async def __aenter__(self) -> "MockStreamContext":
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self.exited = True

    async def __aiter__(self):
        for block in self.blocks:
            yield block


# Mock connection context manager
class MockConnectionContextManager:
    def __init__(self) -> None:
        self.entered = False
        self.exited = False

    def __enter__(self) -> Any:
        self.entered = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.exited = True

    async def __aenter__(self) -> Any:
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self.exited = True


# Mock Table class for mapping tests
class DummyUser(Table):
    __tablename__ = "dummy_users"
    id = Column(Int32)
    name = Column(String)


@pytest.fixture
def sync_stream_setup():
    blocks = [[(1, "Alice"), (2, "Bob")], [(3, "Charlie")]]
    cols = ["id", "name"]
    stream_ctx = MockStreamContext(blocks, cols)
    conn_ctx = MockConnectionContextManager()
    return stream_ctx, conn_ctx


def test_sync_stream_result_iteration_rows(sync_stream_setup):
    """Test that synchronous StreamResult yields Row objects correctly."""
    stream_ctx, conn_ctx = sync_stream_setup
    result = StreamResult(stream_ctx, conn_ctx)

    with result as stream:
        assert conn_ctx.entered is False  # Already entered before StreamResult instantiation
        assert stream_ctx.entered is True

        rows = list(stream)
        assert len(rows) == 3
        assert all(isinstance(r, Row) for r in rows)
        assert rows[0].id == 1
        assert rows[0].name == "Alice"
        assert rows[1].id == 2
        assert rows[1].name == "Bob"
        assert rows[2].id == 3
        assert rows[2].name == "Charlie"

    assert stream_ctx.exited is True
    assert conn_ctx.exited is True


def test_sync_stream_result_iteration_model(sync_stream_setup):
    """Test that synchronous StreamResult maps rows to Table model objects."""
    stream_ctx, conn_ctx = sync_stream_setup
    result = StreamResult(stream_ctx, conn_ctx, model=DummyUser)

    with result as stream:
        users = list(stream)
        assert len(users) == 3
        assert all(isinstance(u, DummyUser) for u in users)
        assert users[0].id == 1
        assert users[0].name == "Alice"
        assert users[2].name == "Charlie"


def test_sync_stream_scalars(sync_stream_setup):
    """Test that synchronous StreamResult yields scalar values by index and name."""
    stream_ctx, conn_ctx = sync_stream_setup

    # Test by index
    with StreamResult(stream_ctx, conn_ctx) as result:
        scalars_idx = list(result.scalars(0))
        assert scalars_idx == [1, 2, 3]

    # Test by column name
    stream_ctx = MockStreamContext(stream_ctx.blocks, stream_ctx.source.column_names)
    with StreamResult(stream_ctx, conn_ctx) as result:
        scalars_name = list(result.scalars("name"))
        assert scalars_name == ["Alice", "Bob", "Charlie"]


def test_sync_stream_mappings(sync_stream_setup):
    """Test that synchronous StreamResult yields dictionary mappings."""
    stream_ctx, conn_ctx = sync_stream_setup
    with StreamResult(stream_ctx, conn_ctx) as result:
        mappings = list(result.mappings())
        assert len(mappings) == 3
        assert mappings[0] == {"id": 1, "name": "Alice"}
        assert mappings[2] == {"id": 3, "name": "Charlie"}


def test_sync_stream_tuples(sync_stream_setup):
    """Test that synchronous StreamResult yields raw tuples."""
    stream_ctx, conn_ctx = sync_stream_setup
    with StreamResult(stream_ctx, conn_ctx) as result:
        tuples = list(result.tuples())
        assert tuples == [(1, "Alice"), (2, "Bob"), (3, "Charlie")]


@pytest.mark.asyncio
async def test_async_stream_result_iteration_rows(sync_stream_setup):
    """Test that asynchronous AsyncStreamResult yields Row objects correctly."""
    stream_ctx, conn_ctx = sync_stream_setup
    result = AsyncStreamResult(stream_ctx, conn_ctx)

    async with result as stream:
        assert stream_ctx.entered is True
        rows = []
        async for r in stream:
            rows.append(r)

        assert len(rows) == 3
        assert all(isinstance(r, Row) for r in rows)
        assert rows[0].id == 1
        assert rows[2].name == "Charlie"

    assert stream_ctx.exited is True
    assert conn_ctx.exited is True


@pytest.mark.asyncio
async def test_async_stream_result_iteration_model(sync_stream_setup):
    """Test that asynchronous AsyncStreamResult maps rows to Table model objects."""
    stream_ctx, conn_ctx = sync_stream_setup
    result = AsyncStreamResult(stream_ctx, conn_ctx, model=DummyUser)

    async with result as stream:
        users = []
        async for u in stream:
            users.append(u)

        assert len(users) == 3
        assert all(isinstance(u, DummyUser) for u in users)
        assert users[0].id == 1
        assert users[2].name == "Charlie"


@pytest.mark.asyncio
async def test_async_stream_scalars(sync_stream_setup):
    """Test that asynchronous AsyncStreamResult yields scalar values by index and name."""
    stream_ctx, conn_ctx = sync_stream_setup

    async with AsyncStreamResult(stream_ctx, conn_ctx) as result:
        scalars = []
        async for s in result.scalars(0):
            scalars.append(s)
        assert scalars == [1, 2, 3]


@pytest.mark.asyncio
async def test_async_stream_mappings(sync_stream_setup):
    """Test that asynchronous AsyncStreamResult yields dictionary mappings."""
    stream_ctx, conn_ctx = sync_stream_setup

    async with AsyncStreamResult(stream_ctx, conn_ctx) as result:
        mappings = []
        async for m in result.mappings():
            mappings.append(m)
        assert len(mappings) == 3
        assert mappings[0] == {"id": 1, "name": "Alice"}


@pytest.mark.asyncio
async def test_async_stream_tuples(sync_stream_setup):
    """Test that asynchronous AsyncStreamResult yields raw tuples."""
    stream_ctx, conn_ctx = sync_stream_setup

    async with AsyncStreamResult(stream_ctx, conn_ctx) as result:
        tuples = []
        async for t in result.tuples():
            tuples.append(t)
        assert tuples == [(1, "Alice"), (2, "Bob"), (3, "Charlie")]


def test_sync_stream_cleanup_on_exception(sync_stream_setup):
    """Test that synchronous StreamResult guarantees connection cleanup even if an exception occurs."""
    stream_ctx, conn_ctx = sync_stream_setup
    result = StreamResult(stream_ctx, conn_ctx)

    try:
        with result:
            raise ValueError("Simulated error during stream processing")
    except ValueError:
        pass

    assert stream_ctx.exited is True
    assert conn_ctx.exited is True


@pytest.mark.asyncio
async def test_async_stream_cleanup_on_exception(sync_stream_setup):
    """Test that asynchronous AsyncStreamResult guarantees connection cleanup even if an exception occurs."""
    stream_ctx, conn_ctx = sync_stream_setup
    result = AsyncStreamResult(stream_ctx, conn_ctx)

    try:
        async with result:
            raise ValueError("Simulated error during stream processing")
    except ValueError:
        pass

    assert stream_ctx.exited is True
    assert conn_ctx.exited is True


def test_sync_stream_retrieval_methods(sync_stream_setup):
    """Test all(), first(), one(), and one_or_none() on synchronous stream results."""
    stream_ctx, conn_ctx = sync_stream_setup

    # Test all()
    with StreamResult(stream_ctx, conn_ctx) as result:
        rows = result.all()
        assert len(rows) == 3
        assert rows[0].id == 1

    # Test first()
    stream_ctx = MockStreamContext(sync_stream_setup[0].blocks, sync_stream_setup[0].source.column_names)
    with StreamResult(stream_ctx, conn_ctx) as result:
        row = result.first()
        assert row.id == 1

    # Test one() - raises MultipleResultsFound
    stream_ctx = MockStreamContext(sync_stream_setup[0].blocks, sync_stream_setup[0].source.column_names)
    with StreamResult(stream_ctx, conn_ctx) as result:
        with pytest.raises(MultipleResultsFound):
            result.one()

    # Test one() - success
    stream_ctx = MockStreamContext([[(1, "Alice")]], ["id", "name"])
    with StreamResult(stream_ctx, conn_ctx) as result:
        row = result.one()
        assert row.id == 1

    # Test one() - raises NoResultFound
    stream_ctx = MockStreamContext([], ["id", "name"])
    with StreamResult(stream_ctx, conn_ctx) as result:
        with pytest.raises(NoResultFound):
            result.one()

    # Test one_or_none() - raises MultipleResultsFound
    stream_ctx = MockStreamContext(sync_stream_setup[0].blocks, sync_stream_setup[0].source.column_names)
    with StreamResult(stream_ctx, conn_ctx) as result:
        with pytest.raises(MultipleResultsFound):
            result.one_or_none()

    # Test one_or_none() - success
    stream_ctx = MockStreamContext([[(1, "Alice")]], ["id", "name"])
    with StreamResult(stream_ctx, conn_ctx) as result:
        row = result.one_or_none()
        assert row.id == 1

    # Test one_or_none() - returns None
    stream_ctx = MockStreamContext([], ["id", "name"])
    with StreamResult(stream_ctx, conn_ctx) as result:
        assert result.one_or_none() is None


@pytest.mark.asyncio
async def test_async_stream_retrieval_methods(sync_stream_setup):
    """Test all(), first(), one(), and one_or_none() on asynchronous stream results."""
    stream_ctx, conn_ctx = sync_stream_setup

    # Test all()
    async with AsyncStreamResult(stream_ctx, conn_ctx) as result:
        rows = await result.all()
        assert len(rows) == 3
        assert rows[0].id == 1

    # Test first()
    stream_ctx = MockStreamContext(sync_stream_setup[0].blocks, sync_stream_setup[0].source.column_names)
    async with AsyncStreamResult(stream_ctx, conn_ctx) as result:
        row = await result.first()
        assert row.id == 1

    # Test one() - raises MultipleResultsFound
    stream_ctx = MockStreamContext(sync_stream_setup[0].blocks, sync_stream_setup[0].source.column_names)
    async with AsyncStreamResult(stream_ctx, conn_ctx) as result:
        with pytest.raises(MultipleResultsFound):
            await result.one()

    # Test one() - success
    stream_ctx = MockStreamContext([[(1, "Alice")]], ["id", "name"])
    async with AsyncStreamResult(stream_ctx, conn_ctx) as result:
        row = await result.one()
        assert row.id == 1

    # Test one() - raises NoResultFound
    stream_ctx = MockStreamContext([], ["id", "name"])
    async with AsyncStreamResult(stream_ctx, conn_ctx) as result:
        with pytest.raises(NoResultFound):
            await result.one()

    # Test one_or_none() - raises MultipleResultsFound
    stream_ctx = MockStreamContext(sync_stream_setup[0].blocks, sync_stream_setup[0].source.column_names)
    async with AsyncStreamResult(stream_ctx, conn_ctx) as result:
        with pytest.raises(MultipleResultsFound):
            await result.one_or_none()

    # Test one_or_none() - success
    stream_ctx = MockStreamContext([[(1, "Alice")]], ["id", "name"])
    async with AsyncStreamResult(stream_ctx, conn_ctx) as result:
        row = await result.one_or_none()
        assert row.id == 1

    # Test one_or_none() - returns None
    stream_ctx = MockStreamContext([], ["id", "name"])
    async with AsyncStreamResult(stream_ctx, conn_ctx) as result:
        assert await result.one_or_none() is None
