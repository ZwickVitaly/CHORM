"""Unit tests for ARRAY JOIN functionality."""

import pytest
from chorm import Table, Column, MergeTree, select
from chorm.types import UInt64, String, Array
from chorm.sql.expression import Identifier, Literal, func


class User(Table):
    __tablename__ = "users"
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    tags = Column(Array(String()))
    scores = Column(Array(UInt64()))
    engine = MergeTree()


class TestArrayJoin:
    """Tests for ARRAY JOIN SQL generation."""

    def test_simple_array_join(self):
        """Test simple ARRAY JOIN."""
        stmt = select(User.name, Identifier("tag")).select_from(User).array_join(User.tags.label("tag"))
        sql = stmt.to_sql()
        assert "FROM users" in sql
        assert "ARRAY JOIN users.tags AS tag" in sql
        assert "SELECT users.name, tag" in sql

    def test_left_array_join(self):
        """Test LEFT ARRAY JOIN."""
        stmt = select(User.name, Identifier("tag")).select_from(User).left_array_join(User.tags.label("tag"))
        sql = stmt.to_sql()
        assert "FROM users" in sql
        assert "LEFT ARRAY JOIN users.tags AS tag" in sql

    def test_multiple_array_joins_chained(self):
        """Test chained ARRAY JOINs."""
        stmt = (
            select(User.name)
            .select_from(User)
            .array_join(User.tags.label("tag"))
            .array_join(User.scores.label("score"))
        )
        sql = stmt.to_sql()
        assert "ARRAY JOIN users.tags AS tag" in sql
        assert "ARRAY JOIN users.scores AS score" in sql
        # Order matters
        assert sql.index("tags AS tag") < sql.index("scores AS score")

    def test_multiple_arrays_in_one_join(self):
        """Test joining multiple arrays in one clause."""
        stmt = (
            select(User.name, Identifier("tag"), Identifier("score"))
            .select_from(User)
            .array_join(User.tags.label("tag"), User.scores.label("score"))
        )
        sql = stmt.to_sql()
        assert "ARRAY JOIN users.tags AS tag, users.scores AS score" in sql

    def test_array_join_without_alias(self):
        """Test ARRAY JOIN without explicit alias (using column name)."""
        stmt = select(User.name, User.tags).select_from(User).array_join(User.tags)
        sql = stmt.to_sql()
        assert "ARRAY JOIN users.tags" in sql

    def test_array_join_with_where(self):
        """Test ARRAY JOIN with WHERE clause."""
        from chorm.sql.expression import BinaryExpression

        stmt = (
            select(User.name, Identifier("tag"))
            .select_from(User)
            .array_join(User.tags.label("tag"))
            .where(BinaryExpression(Identifier("tag"), "=", Literal("vip")))
        )
        sql = stmt.to_sql()
        assert "ARRAY JOIN users.tags AS tag" in sql
        assert "WHERE (tag = 'vip')" in sql

    def test_join_then_array_join(self):
        """Test JOIN followed by ARRAY JOIN (order preservation)."""
        # We want: FROM users JOIN other ON ... ARRAY JOIN other.items
        # Current implementation might force ARRAY JOIN before JOIN

        # Mock a second table
        class Other(Table):
            __tablename__ = "other"
            id = Column(UInt64(), primary_key=True)
            user_id = Column(UInt64())
            items = Column(Array(String()))
            engine = MergeTree()

        stmt = (
            select(User.name, Other.items)
            .select_from(User)
            .join(Other, on=User.id == Other.user_id)
            .array_join(Other.items)
        )

        sql = stmt.to_sql()
        # We expect JOIN first, then ARRAY JOIN
        assert "FROM users INNER JOIN other ON (users.id = other.user_id) ARRAY JOIN other.items" in sql
