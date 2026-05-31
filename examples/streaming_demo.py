"""
Query Streaming Demo
====================

This example demonstrates how to use CHORM's streaming execution
for large result sets in both synchronous and asynchronous modes.

Key Concepts:
- Streaming queries block-by-block using session.stream(...)
- Memory-efficient mapping to Row and Table Model objects
- List retrieval methods on streaming results (all, first, one, one_or_none)
- Streaming transformations (scalars, mappings, tuples)

Run: python examples/streaming_demo.py
"""

import asyncio

from chorm import (
    Column,
    MergeTree,
    Session,
    Table,
    create_engine,
    insert,
    select,
)
from chorm.async_engine import create_async_engine
from chorm.async_session import AsyncSession
from chorm.types import String, UInt64


class StreamDemoUser(Table):
    __tablename__ = "demo_streaming_users"
    __engine__ = MergeTree()

    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    role = Column(String())


def setup_data(engine) -> None:
    """Create table and populate it with sample users."""
    session = Session(engine)
    session.execute(f"DROP TABLE IF EXISTS {StreamDemoUser.__tablename__}")
    session.execute(StreamDemoUser.create_table(exists_ok=True))

    users = [
        StreamDemoUser(id=1, name="Alice", role="Admin"),
        StreamDemoUser(id=2, name="Bob", role="User"),
        StreamDemoUser(id=3, name="Charlie", role="User"),
        StreamDemoUser(id=4, name="David", role="Admin"),
        StreamDemoUser(id=5, name="Eve", role="User"),
    ]
    for user in users:
        session.execute(insert(StreamDemoUser).values(**user.to_dict()))
    session.commit()
    session.close()


def run_sync_streaming_demo(engine) -> None:
    """Demonstrate synchronous streaming features."""
    print("\n=== Synchronous Streaming Demo ===")
    session = Session(engine)

    stmt = select(StreamDemoUser.id, StreamDemoUser.name, StreamDemoUser.role).select_from(StreamDemoUser).order_by(StreamDemoUser.id)

    # 1. Standard streaming of Model objects
    print("\n1. Streaming Model instances:")
    with session.stream(stmt, model=StreamDemoUser) as stream:
        for user in stream:
            print(f"   - User #{user.id}: {user.name} ({user.role})")

    # 2. Streaming scalar values
    print("\n2. Streaming scalar column (name):")
    with session.stream(stmt) as stream:
        for name in stream.scalars("name"):
            print(f"   - Name: {name}")

    # 3. Streaming mapping (dict) results
    print("\n3. Streaming dictionary mappings:")
    with session.stream(stmt) as stream:
        for user_dict in stream.mappings():
            print(f"   - Dict: {user_dict}")

    # 4. Using list retrieval methods
    print("\n4. Using list retrieval methods on stream:")
    with session.stream(stmt, model=StreamDemoUser) as stream:
        first_user = stream.first()
        print(f"   - First user in stream: {first_user.name if first_user else 'None'}")

    with session.stream(stmt.where(StreamDemoUser.id == 3), model=StreamDemoUser) as stream:
        one_user = stream.one()
        print(f"   - Single user with ID 3: {one_user.name}")

    session.close()


async def run_async_streaming_demo(async_engine) -> None:
    """Demonstrate asynchronous streaming features."""
    print("\n=== Asynchronous Streaming Demo ===")
    session = AsyncSession(async_engine)

    stmt = select(StreamDemoUser.id, StreamDemoUser.name, StreamDemoUser.role).select_from(StreamDemoUser).order_by(StreamDemoUser.id)

    # 1. Standard async streaming of Row objects
    print("\n1. Async streaming Row objects:")
    async with await session.stream(stmt) as stream:
        async for row in stream:
            print(f"   - Row: ID={row.id}, Name={row.name}, Role={row.role}")

    # 2. Async streaming mapped to Models
    print("\n2. Async streaming mapped to Models:")
    async with await session.stream(stmt, model=StreamDemoUser) as stream:
        async for user in stream:
            print(f"   - Model: {user.name} ({user.role})")

    # 3. Async list retrieval methods
    print("\n3. Async list retrieval methods:")
    async with await session.stream(stmt) as stream:
        all_rows = await stream.all()
        print(f"   - Retrieved all {len(all_rows)} rows asynchronously")

    async with await session.stream(stmt.where(StreamDemoUser.id == 5)) as stream:
        user_5 = await stream.one_or_none()
        print(f"   - User ID 5: {user_5.name if user_5 else 'None'}")


def main():
    # Sync Setup
    engine = create_engine("clickhouse://localhost:8123/default")
    try:
        setup_data(engine)
        # Run Sync Demo
        run_sync_streaming_demo(engine)
    except Exception as e:
        print(f"Skipping sync demo (ClickHouse connection failed): {e}")

    # Run Async Demo
    async_engine = create_async_engine("clickhouse://localhost:8123/default")
    try:
        asyncio.run(run_async_streaming_demo(async_engine))
    except Exception as e:
        print(f"Skipping async demo (ClickHouse connection failed): {e}")


if __name__ == "__main__":
    main()
