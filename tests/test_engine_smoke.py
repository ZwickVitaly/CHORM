"""Smoke tests for the ClickHouse Engine facade."""

from __future__ import annotations

import os
import pathlib
import sys
import types
from unittest.mock import MagicMock

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

from chorm.engine import Connection, Engine, create_engine  # noqa: E402


@pytest.fixture()
def client() -> MagicMock:
    mock_client = MagicMock()
    mock_client.close = MagicMock()
    mock_client.command = MagicMock(return_value="ok")
    mock_client.query = MagicMock(return_value=[("row",)])
    return mock_client


def test_create_engine_defaults(client: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    get_client = MagicMock(return_value=client)
    monkeypatch.setattr("chorm.engine.clickhouse_connect.get_client", get_client)

    engine = create_engine()
    connection = engine.connect()
    try:
        assert isinstance(engine, Engine)
        assert isinstance(connection, Connection)
        get_client.assert_called_once_with(
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
    finally:
        connection.close()


def test_create_engine_from_url(client: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    get_client = MagicMock(return_value=client)
    monkeypatch.setattr("chorm.engine.clickhouse_connect.get_client", get_client)

    url = (
        "clickhouse+https://user:secret@db.example.com:9440/analytics"
        "?setting.max_execution_time=5&secure=false&custom_timeout=2"
    )
    engine = create_engine(url, connect_timeout=10)

    connection = engine.connect()
    try:
        config = engine.config
        assert config.host == "db.example.com"
        assert config.port == 9440
        assert config.username == "user"
        assert config.password == "secret"
        assert config.database == "analytics"
        assert config.secure is False
        assert config.settings == {"max_execution_time": 5}

        get_client.assert_called_once_with(
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
    finally:
        connection.close()


def test_query_and_execute_delegate_to_client(client: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    get_client = MagicMock(return_value=client)
    monkeypatch.setattr("chorm.engine.clickhouse_connect.get_client", get_client)

    engine = create_engine()
    result_query = engine.query("SELECT 1")
    result_execute = engine.execute("SYSTEM FLUSH LOGS")

    assert result_query == [("row",)]
    assert result_execute == "ok"
    client.query.assert_called_once_with("SELECT 1", parameters=None, settings=None)
    client.command.assert_called_once_with("SYSTEM FLUSH LOGS", parameters=None, settings=None)
