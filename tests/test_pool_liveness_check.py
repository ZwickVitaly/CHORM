
import asyncio
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
from chorm import create_engine, create_async_engine
from chorm.pool import ConnectionPool
from chorm.async_pool import AsyncConnectionPool

class TestPoolingLiveness:
    def test_sync_pool_pre_ping_alive(self):
        """Test that pre_ping validates a good connection."""
        engine = create_engine(pool_size=1, pool_pre_ping=True)
        # Mock the underlying pool's _validate_connection to track calls
        with patch.object(engine.pool, "_validate_connection", wraps=engine.pool._validate_connection) as mock_validate:
            with engine.connection() as conn:
                conn.execute("SELECT 1")
                assert mock_validate.called

    def test_sync_pool_pre_ping_dead(self):
        """Test that pre_ping discards a dead connection and creates a new one."""
        engine = create_engine(pool_size=1, pool_pre_ping=True)
        
        # Get a connection and simulate it dying
        conn1 = engine.pool.get()
        conn_id1 = id(conn1)
        
        # Manually close underlying client to simulate network failure
        conn1.client.close()
        
        # Return it to pool (it's marked as closed by client, but pool might not know if we don't tell it)
        # But wait, if client.close() sets closed flag, return_connection handles it.
        # We need to simulate a case where the connection *looks* open but fails on execute.
        # So we reopen it or mock execute to fail.
        
        # Let's mock _validate_connection to return False for the first call
        with patch.object(engine.pool, "_validate_connection", side_effect=[False, True]) as mock_validate:
             # We need to put it back first.
             engine.pool.return_connection(conn1)
             
             # Now get it again. It should trigger validation, fail, and create new one (which passes validation)
             conn2 = engine.pool.get()
             conn_id2 = id(conn2)
             
             assert conn_id1 != conn_id2
             assert mock_validate.call_count == 1 # Once for the failed connection. New one is assumed fresh.

    @pytest.mark.asyncio
    async def test_async_pool_pre_ping_alive(self):
        """Test async pre_ping validates good connection."""
        engine = create_async_engine(pool_size=1, pool_pre_ping=True)
        await engine.pool.initialize()
        
        # Mock _validate_connection
        with patch.object(engine.pool, "_validate_connection", wraps=engine.pool._validate_connection) as mock_validate:
            async with engine.connection() as conn:
                await conn.execute("SELECT 1")
                assert mock_validate.called

    @pytest.mark.asyncio
    async def test_async_pool_pre_ping_dead(self):
        """Test async pre_ping discards dead connection."""
        engine = create_async_engine(pool_size=1, pool_pre_ping=True)
        await engine.pool.initialize()
        
        conn1 = await engine.pool.get()
        conn_id1 = id(conn1)
        
        await engine.pool.return_connection(conn1)
        
        # Mock validate to fail once
        with patch.object(engine.pool, "_validate_connection", side_effect=[False, True]) as mock_validate:
            conn2 = await engine.pool.get()
            conn_id2 = id(conn2)
            
            assert conn_id1 != conn_id2
            assert mock_validate.call_count >= 1

