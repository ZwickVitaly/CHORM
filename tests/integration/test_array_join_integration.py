"""Integration tests for ARRAY JOIN functionality."""

import os
import pytest
from chorm import Table, Column, MergeTree, select, insert, create_engine
from chorm.session import Session
from chorm.types import UInt64, String, Array
from chorm.sql.expression import Identifier, Literal, func


# Skip integration tests if ClickHouse is not available
pytestmark = pytest.mark.skipif(
    os.getenv("CLICKHOUSE_HOST") is None,
    reason="ClickHouse not configured (set CLICKHOUSE_HOST env var)",
)


class User(Table):
    __tablename__ = "test_users_array_join"
    id = Column(UInt64(), primary_key=True)
    name = Column(String())
    tags = Column(Array(String()))
    scores = Column(Array(UInt64()))
    engine = MergeTree()


@pytest.fixture(scope="module")
def engine():
    """Create engine for tests."""
    host = os.getenv("CLICKHOUSE_HOST", "localhost")
    port = int(os.getenv("CLICKHOUSE_PORT", "8123"))
    database = os.getenv("CLICKHOUSE_DB", "default")
    password = os.getenv("CLICKHOUSE_PASSWORD", "123")

    engine = create_engine(
        host=host,
        port=port,
        username="default",
        password=password,
        database=database,
    )
    return engine


@pytest.fixture(scope="module")
def setup_tables(engine):
    """Create test tables and insert data."""
    session = Session(engine)

    # Drop tables if they exist
    try:
        session.execute(f"DROP TABLE IF EXISTS {User.__tablename__}")
    except Exception:
        pass

    # Create tables
    session.execute(User.create_table(exists_ok=True))

    # Insert test data
    users_data = [
        User(id=1, name="Alice", tags=["vip", "premium"], scores=[10, 20]),
        User(id=2, name="Bob", tags=["regular"], scores=[5]),
        User(id=3, name="Charlie", tags=[], scores=[]),  # Empty arrays
    ]
    for user in users_data:
        session.execute(insert(User).values(**user.to_dict()))

    session.commit()

    yield

    # Cleanup
    try:
        session.execute(f"DROP TABLE IF EXISTS {User.__tablename__}")
        session.commit()
    except Exception:
        pass


def test_basic_array_join(engine, setup_tables):
    """Test basic ARRAY JOIN to flatten tags."""
    session = Session(engine)

    # Flatten tags
    stmt = (
        select(User.name, Identifier("tag"))
        .select_from(User)
        .array_join(User.tags.label("tag"))
        .order_by(User.name, Identifier("tag"))
    )

    results = session.execute(stmt).all()

    # Alice has 2 tags, Bob has 1, Charlie has 0
    assert len(results) == 3

    alice_rows = [r for r in results if r.name == "Alice"]
    assert len(alice_rows) == 2
    assert set(r.tag for r in alice_rows) == {"vip", "premium"}

    bob_rows = [r for r in results if r.name == "Bob"]
    assert len(bob_rows) == 1
    assert bob_rows[0].tag == "regular"

    # Charlie should not be present because inner ARRAY JOIN excludes empty arrays
    charlie_rows = [r for r in results if r.name == "Charlie"]
    assert len(charlie_rows) == 0


def test_left_array_join(engine, setup_tables):
    """Test LEFT ARRAY JOIN to include empty arrays."""
    session = Session(engine)

    stmt = (
        select(User.name, Identifier("tag"))
        .select_from(User)
        .left_array_join(User.tags.label("tag"))
        .order_by(User.name)
    )

    results = session.execute(stmt).all()

    # Alice (2) + Bob (1) + Charlie (1 with default value)
    assert len(results) == 4

    charlie_row = next(r for r in results if r.name == "Charlie")
    # For String, default is empty string
    assert charlie_row.tag == ""


def test_array_join_alias_filtering(engine, setup_tables):
    """Test filtering on aliased array column."""
    from chorm.sql.expression import BinaryExpression

    session = Session(engine)

    stmt = (
        select(User.name, Identifier("tag"))
        .select_from(User)
        .array_join(User.tags.label("tag"))
        .where(BinaryExpression(Identifier("tag"), "=", Literal("vip")))
    )

    results = session.execute(stmt).all()

    assert len(results) == 1
    assert results[0].name == "Alice"
    assert results[0].tag == "vip"


def test_multiple_array_joins(engine, setup_tables):
    """Test joining multiple arrays."""
    session = Session(engine)

    # Join tags and scores
    # Note: If arrays have different lengths, ClickHouse behavior depends on syntax.
    # ARRAY JOIN arr1, arr2 expects same length.
    # Chained ARRAY JOIN produces Cartesian product.

    # Here we chain them
    stmt = (
        select(User.name, Identifier("tag"), Identifier("score"))
        .select_from(User)
        .array_join(User.tags.label("tag"))
        .array_join(User.scores.label("score"))
        .where(User.name == "Alice")
    )

    results = session.execute(stmt).all()

    # Alice: 2 tags * 2 scores = 4 rows
    assert len(results) == 4

    tags = set(r.tag for r in results)
    scores = set(r.score for r in results)

    assert tags == {"vip", "premium"}
    assert scores == {10, 20}
