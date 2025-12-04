"""Tests for Dictionary support."""

from chorm.sql.ddl import create_dictionary
from chorm.sql.expression import dict_get, dict_get_or_default, dict_has, Identifier, Literal


def test_create_dictionary_basic():
    """Test basic CREATE DICTIONARY."""
    stmt = create_dictionary(
        "user_dict",
        "ClickHouse(HOST 'localhost' PORT 9000 USER 'default' TABLE 'users' DB 'default')",
        "HASHED",
        [("id", "UInt64"), ("name", "String")],
    )
    expected = (
        "CREATE DICTIONARY user_dict "
        "(id UInt64, name String) "
        "PRIMARY KEY id "
        "SOURCE(ClickHouse(HOST 'localhost' PORT 9000 USER 'default' TABLE 'users' DB 'default')) "
        "LAYOUT(HASHED())"
    )
    assert stmt.to_sql() == expected


def test_create_dictionary_with_lifetime():
    """Test CREATE DICTIONARY with lifetime."""
    stmt = create_dictionary(
        "cache_dict",
        "ClickHouse(HOST 'localhost' PORT 9000 USER 'default' TABLE 'data' DB 'default')",
        "CACHE",
        [("key", "String"), ("value", "String")],
        lifetime=300,
    )
    assert "LIFETIME(300)" in stmt.to_sql()


def test_create_dictionary_if_not_exists():
    """Test CREATE DICTIONARY IF NOT EXISTS."""
    stmt = create_dictionary(
        "test_dict",
        "ClickHouse(HOST 'localhost' PORT 9000 USER 'default' TABLE 'test' DB 'default')",
        "FLAT",
        [("id", "UInt32")],
        if_not_exists=True,
    )
    assert stmt.to_sql().startswith("CREATE DICTIONARY IF NOT EXISTS")


def test_dict_get():
    """Test dictGet function."""
    stmt = dict_get("user_dict", "name", Identifier("user_id"))
    assert stmt.to_sql() == "dictGet('user_dict', 'name', user_id)"


def test_dict_get_or_default():
    """Test dictGetOrDefault function."""
    stmt = dict_get_or_default("user_dict", "name", Identifier("user_id"), Literal("Unknown"))
    assert stmt.to_sql() == "dictGetOrDefault('user_dict', 'name', user_id, 'Unknown')"


def test_dict_has():
    """Test dictHas function."""
    stmt = dict_has("user_dict", Identifier("user_id"))
    assert stmt.to_sql() == "dictHas('user_dict', user_id)"
