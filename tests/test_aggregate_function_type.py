"""Tests for AggregateFunctionType."""

import pytest
from chorm.types import (
    AggregateFunctionType,
    AggregateFunction,
    parse_type,
    UInt64,
    UInt32,
    String,
    UInt8,
    ConversionError,
)
from chorm.sql.expression import func
from chorm import Column


class TestAggregateFunctionType:
    """Test AggregateFunctionType class."""

    def test_create_simple(self):
        """Test creating simple AggregateFunctionType."""
        agg_type = AggregateFunctionType("sum", (UInt64(),))
        assert agg_type.ch_type == "AggregateFunction(sum, UInt64)"
        assert agg_type.func_name == "sum"
        assert len(agg_type.arg_types) == 1
        assert agg_type.arg_types[0].ch_type == "UInt64"

    def test_create_multiple_args(self):
        """Test creating AggregateFunctionType with multiple arguments."""
        agg_type = AggregateFunctionType("anyIf", (String(), UInt8()))
        assert agg_type.ch_type == "AggregateFunction(anyIf, String, UInt8)"
        assert agg_type.func_name == "anyIf"
        assert len(agg_type.arg_types) == 2
        assert agg_type.arg_types[0].ch_type == "String"
        assert agg_type.arg_types[1].ch_type == "UInt8"

    def test_create_no_args(self):
        """Test creating AggregateFunctionType without argument types."""
        agg_type = AggregateFunctionType("count", ())
        assert agg_type.ch_type == "AggregateFunction(count)"
        assert agg_type.func_name == "count"
        assert len(agg_type.arg_types) == 0

    def test_parse_type_simple(self):
        """Test parsing simple AggregateFunction type."""
        result = parse_type("AggregateFunction(sum, UInt64)")
        assert isinstance(result, AggregateFunctionType)
        assert result.func_name == "sum"
        assert len(result.arg_types) == 1
        assert result.arg_types[0].ch_type == "UInt64"

    def test_parse_type_multiple_args(self):
        """Test parsing AggregateFunction with multiple arguments."""
        result = parse_type("AggregateFunction(anyIf, String, UInt8)")
        assert isinstance(result, AggregateFunctionType)
        assert result.func_name == "anyIf"
        assert len(result.arg_types) == 2
        assert result.arg_types[0].ch_type == "String"
        assert result.arg_types[1].ch_type == "UInt8"

    def test_parse_type_with_params(self):
        """Test parsing AggregateFunction with function parameters."""
        result = parse_type("AggregateFunction(quantiles(0.5, 0.9), UInt64)")
        assert isinstance(result, AggregateFunctionType)
        assert result.func_name == "quantiles(0.5, 0.9)"
        assert len(result.arg_types) == 1
        assert result.arg_types[0].ch_type == "UInt64"

    def test_parse_type_uniq_exact(self):
        """Test parsing AggregateFunction with uniqExact."""
        result = parse_type("AggregateFunction(uniqExact, UInt32)")
        assert isinstance(result, AggregateFunctionType)
        assert result.func_name == "uniqExact"
        assert len(result.arg_types) == 1
        assert result.arg_types[0].ch_type == "UInt32"

    def test_parse_type_no_args(self):
        """Test parsing AggregateFunction without argument types."""
        result = parse_type("AggregateFunction(count)")
        assert isinstance(result, AggregateFunctionType)
        assert result.func_name == "count"
        assert len(result.arg_types) == 0

    def test_to_python_bytes(self):
        """Test converting bytes to Python."""
        agg_type = AggregateFunctionType("sum", (UInt64(),))
        value = b"\x01\x02\x03"
        result = agg_type.to_python(value)
        assert result == b"\x01\x02\x03"
        assert isinstance(result, bytes)

    def test_to_python_bytearray(self):
        """Test converting bytearray to Python."""
        agg_type = AggregateFunctionType("sum", (UInt64(),))
        value = bytearray(b"\x01\x02\x03")
        result = agg_type.to_python(value)
        assert result == b"\x01\x02\x03"
        assert isinstance(result, bytes)

    def test_to_python_none(self):
        """Test converting None to Python."""
        agg_type = AggregateFunctionType("sum", (UInt64(),))
        assert agg_type.to_python(None) is None

    def test_to_clickhouse_bytes(self):
        """Test converting bytes to ClickHouse."""
        agg_type = AggregateFunctionType("sum", (UInt64(),))
        value = b"\x01\x02\x03"
        result = agg_type.to_clickhouse(value)
        assert result == b"\x01\x02\x03"
        assert isinstance(result, bytes)

    def test_to_clickhouse_bytearray(self):
        """Test converting bytearray to ClickHouse."""
        agg_type = AggregateFunctionType("sum", (UInt64(),))
        value = bytearray(b"\x01\x02\x03")
        result = agg_type.to_clickhouse(value)
        assert result == b"\x01\x02\x03"
        assert isinstance(result, bytes)

    def test_to_clickhouse_none(self):
        """Test converting None to ClickHouse."""
        agg_type = AggregateFunctionType("sum", (UInt64(),))
        assert agg_type.to_clickhouse(None) is None

    def test_column_with_string(self):
        """Test creating Column with AggregateFunction string."""
        col = Column("AggregateFunction(sum, UInt64)")
        assert isinstance(col.field_type, AggregateFunctionType)
        assert col.field_type.func_name == "sum"
        assert len(col.field_type.arg_types) == 1

    def test_column_with_multiple_args(self):
        """Test creating Column with AggregateFunction multiple args."""
        col = Column("AggregateFunction(anyIf, String, UInt8)")
        assert isinstance(col.field_type, AggregateFunctionType)
        assert col.field_type.func_name == "anyIf"
        assert len(col.field_type.arg_types) == 2

    def test_repr(self):
        """Test string representation."""
        agg_type = AggregateFunctionType("sum", (UInt64(),))
        repr_str = repr(agg_type)
        assert "AggregateFunctionType" in repr_str
        assert "AggregateFunction(sum, UInt64)" in repr_str

    def test_with_func_sum(self):
        """Test AggregateFunction with func.sum."""
        agg_type = AggregateFunction(func.sum, (UInt64(),))
        assert agg_type.ch_type == "AggregateFunction(sum, UInt64)"
        assert agg_type.func_name == "sum"

    def test_with_func_quantile(self):
        """Test AggregateFunction with func.quantile(0.5)."""
        agg_type = AggregateFunction(func.quantile(0.5, "dummy"), (UInt64(),))
        assert agg_type.ch_type == "AggregateFunction(quantile(0.5), UInt64)"
        assert agg_type.func_name == "quantile(0.5)"

    def test_with_func_quantiles(self):
        """Test AggregateFunction with func.quantiles([0.5, 0.9])."""
        agg_type = AggregateFunction(func.quantiles([0.5, 0.9], "dummy"), (UInt64(),))
        assert agg_type.ch_type == "AggregateFunction(quantiles(0.5, 0.9), UInt64)"
        assert agg_type.func_name == "quantiles(0.5, 0.9)"

    def test_column_with_func_sum(self):
        """Test Column with AggregateFunction using func.sum."""
        col = Column(AggregateFunction(func.sum, (UInt64(),)))
        assert isinstance(col.field_type, AggregateFunctionType)
        assert col.field_type.func_name == "sum"

