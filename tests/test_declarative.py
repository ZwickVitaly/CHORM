"""Tests for the declarative table base."""

from __future__ import annotations

import pytest

from chorm.declarative import Column, DeclarativeError, Table
from chorm.table_engines import MergeTree, ReplicatedMergeTree
from chorm.types import StringType, UInt64


class Base(Table):
    __abstract__ = True


class Event(Base):
    __tablename__ = "events"
    __order_by__ = ("id",)

    id = Column(UInt64(), primary_key=True)
    name = Column(StringType(), default="anon")
    engine = MergeTree()


class ReplicatedEvent(Event):
    __tablename__ = "replicated_events"

    engine = ReplicatedMergeTree("/clickhouse/events", "replica01")
    shard = Column(UInt64(), default=0)


def test_metadata_collected() -> None:
    metadata = Event.__table__
    assert metadata.name == "events"
    assert len(metadata.columns) == 2
    assert metadata.primary_key[0].name == "id"
    assert isinstance(metadata.engine, MergeTree)
    assert metadata.order_by == ("id",)


def test_instance_defaults_and_assignment() -> None:
    event = Event()
    assert event.id is None
    assert event.name == "anon"
    event2 = Event(id=1, name="hello")
    assert event2.id == 1
    assert event2.name == "hello"
    assert event2.to_dict() == {"id": 1, "name": "hello"}


def test_unknown_column_rejected() -> None:
    with pytest.raises(DeclarativeError):
        Event(unknown="value")  # type: ignore[arg-type]


def test_inheritance_merges_columns_and_engine() -> None:
    metadata = ReplicatedEvent.__table__
    column_names = [col.name for col in metadata.columns]
    assert column_names == ["id", "name", "shard"]
    assert isinstance(metadata.engine, ReplicatedMergeTree)
    assert metadata.order_by == ("id",)


def test_create_table_sql() -> None:
    sql = Event.create_table(exists_ok=True)
    assert "CREATE TABLE IF NOT EXISTS events" in sql
    assert "ENGINE = MergeTree" in sql
    assert "ORDER BY (id)" in sql


def test_create_all_from_base() -> None:
    sql = Base.create_all(exists_ok=True)
    assert "CREATE TABLE IF NOT EXISTS events" in sql
    assert "CREATE TABLE IF NOT EXISTS replicated_events" in sql


def test_create_all_from_event_includes_descendants() -> None:
    sql = Event.create_all(exists_ok=True)
    assert "CREATE TABLE IF NOT EXISTS events" in sql
    assert "CREATE TABLE IF NOT EXISTS replicated_events" in sql
