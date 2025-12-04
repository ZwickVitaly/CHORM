"""Integration tests for connection pooling with live ClickHouse."""

import os
import pytest
import asyncio
from chorm import create_engine, create_async_engine, ConnectionPool, AsyncConnectionPool


# Skip all tests if CLICKHOUSE_HOST is not set
pytestmark = pytest.mark.skipif(
    not os.environ.get("CLICKHOUSE_HOST"), reason="Integration tests require CLICKHOUSE_HOST environment variable"
)


@pytest.fixture
def clickhouse_url():
    """Get ClickHouse connection URL from environment."""
    host = os.environ.get("CLICKHOUSE_HOST", "localhost")
    port = os.environ.get("CLICKHOUSE_PORT", "8123")
    return f"clickhouse://{host}:{port}/default"


class TestSyncConnectionPool:
    """Integration tests for sync connection pool."""

    def test_pool_connection_reuse(self, clickhouse_url):
        """Test that connections are reused from pool."""
        engine = create_engine(clickhouse_url, pool_size=3, max_overflow=2)

        # Get and return connection multiple times
        for i in range(5):
            with engine.connection() as conn:
                result = conn.query(f"SELECT {i}")
                assert result.result_rows[0][0] == i

        # Verify pool state
        assert engine.pool is not None
        assert engine.pool.size <= 3  # Should have connections in pool

        # Cleanup
        engine.pool.close_all()

    def test_pool_concurrent_queries(self, clickhouse_url):
        """Test concurrent query execution with pooling."""
        import threading

        engine = create_engine(clickhouse_url, pool_size=5, max_overflow=5)
        results = []
        errors = []

        def query_worker(n):
            try:
                with engine.connection() as conn:
                    result = conn.query(f"SELECT {n}")
                    results.append(result.result_rows[0][0])
            except Exception as e:
                errors.append(e)

        # Run 10 concurrent queries with pool of 5 + 5 overflow
        threads = [threading.Thread(target=query_worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 10
        assert sorted(results) == list(range(10))

        # Cleanup
        engine.pool.close_all()

    def test_pool_exhaustion_recovery(self, clickhouse_url):
        """Test that pool recovers from exhaustion."""
        engine = create_engine(clickhouse_url, pool_size=2, max_overflow=1)

        # Acquire all connections (2 pooled + 1 overflow)
        conn1 = engine.pool.get()
        conn2 = engine.pool.get()
        conn3 = engine.pool.get()

        assert engine.pool.size == 0  # Pool is empty
        assert engine.pool.overflow == 1  # 1 overflow connection

        # Return connections
        engine.pool.return_connection(conn1)
        engine.pool.return_connection(conn2)
        engine.pool.return_connection(conn3)

        # Pool should be replenished
        assert engine.pool.size == 2
        assert engine.pool.overflow == 0

        # Should be able to get connection again
        with engine.connection() as conn:
            result = conn.query("SELECT 1")
            assert result.result_rows[0][0] == 1

        # Cleanup
        engine.pool.close_all()

    def test_pool_connection_recycling(self, clickhouse_url):
        """Test that old connections are recycled."""
        import time

        # Create pool with short recycle time (1 second)
        engine = create_engine(clickhouse_url, pool_size=2, pool_recycle=1)

        # Get connection and note its ID
        conn1 = engine.pool.get()
        conn1_id = id(conn1)

        # Use and return connection
        result1 = conn1.query("SELECT 1")
        assert result1.result_rows[0][0] == 1
        engine.pool.return_connection(conn1)

        # Wait for recycle time to pass
        time.sleep(1.05)

        # Get connection again - should be recycled (new connection)
        conn2 = engine.pool.get()

        # Connection should still work
        result2 = conn2.query("SELECT 2")
        assert result2.result_rows[0][0] == 2

        engine.pool.return_connection(conn2)

        # Cleanup
        engine.pool.close_all()

    def test_pool_with_session(self, clickhouse_url):
        """Test pool integration with Session."""
        from chorm import Session, select
        from chorm.declarative import Table, Column
        from chorm.types import Int32, String

        engine = create_engine(clickhouse_url, pool_size=3)

        # Create test table
        class PoolTest(Table):
            __tablename__ = "pool_integration_test"
            __engine__ = "Memory"

            id = Column(Int32())
            name = Column(String())

        session = Session(engine)

        # Create table
        session.execute(f"DROP TABLE IF EXISTS {PoolTest.__tablename__}")
        session.execute(
            f"""
            CREATE TABLE {PoolTest.__tablename__} (
                id Int32,
                name String
            ) ENGINE = Memory
        """
        )

        # Insert data
        session.execute(
            f"""
            INSERT INTO {PoolTest.__tablename__} (id, name) 
            VALUES (1, 'test1'), (2, 'test2')
        """
        )

        # Query with Session
        result = session.execute(select("*").select_from(PoolTest.__tablename__))
        rows = result.all()
        assert len(rows) == 2

        # Cleanup
        session.execute(f"DROP TABLE IF EXISTS {PoolTest.__tablename__}")
        engine.pool.close_all()


class TestAsyncConnectionPool:
    """Integration tests for async connection pool."""

    @pytest.mark.asyncio
    async def test_async_pool_connection_reuse(self, clickhouse_url):
        """Test that async connections are reused from pool."""
        engine = create_async_engine(clickhouse_url, pool_size=3, max_overflow=2)

        # Initialize pool
        await engine.pool.initialize()

        # Get and return connection multiple times
        for i in range(5):
            async with engine.connection() as conn:
                result = await conn.query(f"SELECT {i}")
                assert result.result_rows[0][0] == i

        # Verify pool state
        assert engine.pool is not None
        assert engine.pool.size <= 3  # Should have connections in pool

        # Cleanup
        await engine.pool.close_all()

    @pytest.mark.asyncio
    async def test_async_pool_concurrent_queries(self, clickhouse_url):
        """Test concurrent async query execution with pooling."""
        engine = create_async_engine(clickhouse_url, pool_size=5, max_overflow=5)
        await engine.pool.initialize()

        async def query_worker(n):
            async with engine.connection() as conn:
                result = await conn.query(f"SELECT {n}")
                return result.result_rows[0][0]

        # Run 10 concurrent queries
        tasks = [query_worker(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert sorted(results) == list(range(10))

        # Cleanup
        await engine.pool.close_all()

    @pytest.mark.asyncio
    async def test_async_pool_exhaustion_recovery(self, clickhouse_url):
        """Test that async pool recovers from exhaustion."""
        engine = create_async_engine(clickhouse_url, pool_size=2, max_overflow=1)
        await engine.pool.initialize()

        # Acquire all connections (2 pooled + 1 overflow)
        conn1 = await engine.pool.get()
        conn2 = await engine.pool.get()
        conn3 = await engine.pool.get()

        assert engine.pool.size == 0  # Pool is empty
        assert engine.pool.overflow == 1  # 1 overflow connection

        # Return connections
        await engine.pool.return_connection(conn1)
        await engine.pool.return_connection(conn2)
        await engine.pool.return_connection(conn3)

        # Pool should be replenished
        assert engine.pool.size == 2
        assert engine.pool.overflow == 0

        # Should be able to get connection again
        async with engine.connection() as conn:
            result = await conn.query("SELECT 1")
            assert result.result_rows[0][0] == 1

        # Cleanup
        await engine.pool.close_all()

    @pytest.mark.asyncio
    async def test_async_pool_connection_recycling(self, clickhouse_url):
        """Test that old async connections are recycled."""
        import time

        # Create pool with short recycle time (1 second)
        engine = create_async_engine(clickhouse_url, pool_size=2, pool_recycle=1)
        await engine.pool.initialize()

        # Get connection and note its ID
        conn1 = await engine.pool.get()
        conn1_id = id(conn1)

        # Use and return connection
        result1 = await conn1.query("SELECT 1")
        assert result1.result_rows[0][0] == 1
        await engine.pool.return_connection(conn1)

        # Wait for recycle time to pass
        await asyncio.sleep(1.05)

        # Get connection again - should be recycled (new connection)
        conn2 = await engine.pool.get()

        # Connection should still work
        result2 = await conn2.query("SELECT 2")
        assert result2.result_rows[0][0] == 2

        await engine.pool.return_connection(conn2)

        # Cleanup
        await engine.pool.close_all()

    @pytest.mark.asyncio
    async def test_async_pool_with_session(self, clickhouse_url):
        """Test async pool integration with AsyncSession."""
        from chorm import AsyncSession, select
        from chorm.declarative import Table, Column
        from chorm.types import Int32, String

        engine = create_async_engine(clickhouse_url, pool_size=3)
        await engine.pool.initialize()

        # Create test table
        class AsyncPoolTest(Table):
            __tablename__ = "async_pool_integration_test"
            __engine__ = "Memory"

            id = Column(Int32())
            name = Column(String())

        session = AsyncSession(engine)

        # Create table
        await session.execute(f"DROP TABLE IF EXISTS {AsyncPoolTest.__tablename__}")
        await session.execute(
            f"""
            CREATE TABLE {AsyncPoolTest.__tablename__} (
                id Int32,
                name String
            ) ENGINE = Memory
        """
        )

        # Insert data
        await session.execute(
            f"""
            INSERT INTO {AsyncPoolTest.__tablename__} (id, name) 
            VALUES (1, 'test1'), (2, 'test2')
        """
        )

        # Query with AsyncSession
        result = await session.execute(select("*").select_from(AsyncPoolTest.__tablename__))
        rows = result.all()
        assert len(rows) == 2

        # Cleanup
        await session.execute(f"DROP TABLE IF EXISTS {AsyncPoolTest.__tablename__}")
        await engine.pool.close_all()
