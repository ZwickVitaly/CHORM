"""Example of using AsyncSession with CHORM."""

import asyncio
from chorm import Table, Column, AsyncSession, create_async_engine, select, MetaData, MergeTree
from chorm.types import UInt64, String


metadata = MetaData()


class User(Table):
    metadata = metadata
    __tablename__ = "users"
    __engine__ = MergeTree()
    
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    email = Column(String())


async def main():
    # Create async engine
    engine = create_async_engine(
        "clickhouse://localhost:8123/default",
        username="default",
        password=""
    )
    
    # Example 1: Using context manager (auto-commit on success)
    async with AsyncSession(engine) as session:
        user1 = User(id=1, name="Alice", email="alice@example.com")
        user2 = User(id=2, name="Bob", email="bob@example.com")
        
        session.add(user1)
        session.add(user2)
        # commit() will be called automatically on __aexit__
    
    # Example 2: Manual session management
    session = AsyncSession(engine)
    
    # Add new users
    user3 = User(id=3, name="Charlie", email="charlie@example.com")
    session.add(user3)
    
    # Commit inserts
    await session.commit()
    
    # Query users
    stmt = select(User.id, User.name, User.email).where(User.id > 1)
    result = await session.execute(stmt)
    
    # Get all rows
    rows = result.all()
    for row in rows:
        print(f"User: {row}")
    
    # Close session
    await session.close()


if __name__ == "__main__":
    print("AsyncSession Example")
    print("=" * 50)
    print("This example demonstrates AsyncSession usage.")
    print("Note: Requires a running ClickHouse instance.")
    print("=" * 50)
    
    # Uncomment to run:
    # asyncio.run(main())
