"""Tests for advanced aggregate functions."""

from chorm.sql.expression import (
    top_k,
    top_k_weighted,
    group_bitmap,
    group_bit_and,
    group_bit_or,
    group_bit_xor,
    any_last,
    any_heavy,
    arg_max,
    arg_min,
    Identifier,
)


def test_top_k():
    """Test topK aggregate."""
    assert top_k(10, Identifier("country")).to_sql() == "topK(10, country)"


def test_top_k_weighted():
    """Test topKWeighted aggregate."""
    assert (
        top_k_weighted(10, Identifier("product_id"), Identifier("quantity")).to_sql()
        == "topKWeighted(10, product_id, quantity)"
    )


def test_group_bitmap():
    """Test groupBitmap aggregate."""
    assert group_bitmap(Identifier("user_id")).to_sql() == "groupBitmap(user_id)"


def test_group_bit_and():
    """Test groupBitAnd aggregate."""
    assert group_bit_and(Identifier("flags")).to_sql() == "groupBitAnd(flags)"


def test_group_bit_or():
    """Test groupBitOr aggregate."""
    assert group_bit_or(Identifier("flags")).to_sql() == "groupBitOr(flags)"


def test_group_bit_xor():
    """Test groupBitXor aggregate."""
    assert group_bit_xor(Identifier("checksum")).to_sql() == "groupBitXor(checksum)"


def test_any_last():
    """Test anyLast sampling aggregate."""
    assert any_last(Identifier("last_login")).to_sql() == "anyLast(last_login)"


def test_any_heavy():
    """Test anyHeavy heavy hitter aggregate."""
    assert any_heavy(Identifier("browser")).to_sql() == "anyHeavy(browser)"


def test_arg_max():
    """Test argMax aggregate."""
    assert (
        arg_max(Identifier("name"), Identifier("updated_at")).to_sql()
        == "argMax(name, updated_at)"
    )


def test_arg_min():
    """Test argMin aggregate."""
    assert (
        arg_min(Identifier("name"), Identifier("created_at")).to_sql()
        == "argMin(name, created_at)"
    )
