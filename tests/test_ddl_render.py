"""Tests for DDL rendering helpers."""

from __future__ import annotations

from chorm.ddl import format_ddl
from chorm.declarative import Column, Table
from chorm.table_engines import MergeTree
from chorm.types import StringType, UInt64


class DDLBase(Table):
    __abstract__ = True


class Orders(DDLBase):
    __tablename__ = "orders"
    __order_by__ = ("id",)
    __partition_by__ = ("toYYYYMM(created_at)",)
    __ttl__ = "created_at + INTERVAL 30 DAY"

    id = Column(UInt64(), primary_key=True, nullable=False)
    created_at = Column("DateTime", nullable=False)
    customer = Column(StringType(), nullable=True, default=None)
    engine = MergeTree()


def test_format_ddl_includes_clauses() -> None:
    ddl = format_ddl(Orders.__table__)
    assert "CREATE TABLE orders" in ddl
    assert "MergeTree" in ddl
    assert "ORDER BY (id)" in ddl
    assert "PARTITION BY (toYYYYMM(created_at))" in ddl
    assert "TTL created_at + INTERVAL 30 DAY" in ddl
    assert "PRIMARY KEY (id)" in ddl
    assert "Nullable(String" in ddl
