"""Smoke tests for the asynchronous ClickHouse Engine facade."""

from __future__ import annotations

import asyncio
import os
import pathlib
import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest


def _ensure_stub_clickhouse_module() -> None:
    """Inject a stub module if clickhouse-connect is unavailable."""
    if "clickhouse_connect" in sys.modules:
        return

    stub = types.ModuleType("clickhouse_connect")
    stub.get_client = MagicMock()
    stub.get_async_client = MagicMock()
    sys.modules["clickhouse_connect"] = stub


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

_ensure_stub_clickhouse_module()

from chorm.async_engine import AsyncConnection, AsyncEngine, create_async_engine  # noqa: E402


@pytest.fixture()
def async_client() -> MagicMock:
    client = MagicMock()
    client.close = AsyncMock()
    client.command = AsyncMock(return_value="ok")
    client.query = AsyncMock(return_value=[("row",)])
    client.insert = AsyncMock(return_value=1)
    return client


def test_create_async_engine_defaults(async_client: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    # Use AsyncMock for get_async_client since _create_client is now async
    get_async_client = AsyncMock(return_value=async_client)
    monkeypatch.setattr("chorm.async_engine.clickhouse_connect.get_async_client", get_async_client)

    engine = create_async_engine()

    async def _exercise() -> None:
        async with engine.connection() as connection:
            assert isinstance(connection, AsyncConnection)
            assert isinstance(connection.client, MagicMock)
        get_async_client.assert_called_once_with(
            host="localhost",
            port=8123,
            username="default",
            password="123",  # Default EngineConfig reads from CLICKHOUSE_PASSWORD env var
            database="default",
            secure=False,
            connect_timeout=10,
            send_receive_timeout=300,
            compress=False,
            query_limit=0,
            verify=True,
        )

    asyncio.run(_exercise())


def test_create_async_engine_from_url(async_client: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    # Use AsyncMock for get_async_client since _create_client is now async
    get_async_client = AsyncMock(return_value=async_client)
    monkeypatch.setattr("chorm.async_engine.clickhouse_connect.get_async_client", get_async_client)

    url = (
        "clickhouse+https://user:secret@db.example.com:9440/analytics"
        "?setting.max_execution_time=5&secure=false&custom_timeout=2"
    )

    engine = create_async_engine(url, connect_timeout=10)

    async def _exercise() -> None:
        assert isinstance(engine, AsyncEngine)
        config = engine.config
        assert config.host == "db.example.com"
        assert config.port == 9440
        assert config.username == "user"
        assert config.password == "secret"
        assert config.database == "analytics"
        assert config.secure is False
        assert config.settings == {"max_execution_time": 5}

        async with engine.connection() as connection:
            pass  # Just verify connection works

        get_async_client.assert_called_once_with(
            host="db.example.com",
            port=9440,
            username="user",
            password="secret",
            database="analytics",
            secure=False,
            connect_timeout=10,
            send_receive_timeout=300,
            compress=False,
            query_limit=0,
            verify=True,
            settings={"max_execution_time": 5},
            custom_timeout=2,
        )

    asyncio.run(_exercise())


def test_query_and_execute_delegate_to_client(async_client: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    # Use AsyncMock for get_async_client since _create_client is now async
    get_async_client = AsyncMock(return_value=async_client)
    monkeypatch.setattr("chorm.async_engine.clickhouse_connect.get_async_client", get_async_client)

    engine = create_async_engine()

    async def _exercise() -> None:
        result_query = await engine.query("SELECT 1")
        result_execute = await engine.execute("SYSTEM FLUSH LOGS")

        assert result_query == [("row",)]
        assert result_execute == "ok"
        async_client.query.assert_awaited_once_with("SELECT 1", parameters=None, settings=None)
        async_client.command.assert_awaited_once_with("SYSTEM FLUSH LOGS", parameters=None, settings=None)

    asyncio.run(_exercise())
