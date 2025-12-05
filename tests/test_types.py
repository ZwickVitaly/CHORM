"""Tests for ClickHouse field types and converters."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from ipaddress import IPv4Address
from zoneinfo import ZoneInfo

import pytest

from chorm.types import (
    ConversionContext,
    ConversionError,
    DateTimeType,
    DecimalType,
    EnumType,
    MapType,
    NullableType,
    TupleType,
    JSONType,
    BFloat16,
    Float32,
    Int32,
    UInt8,
    parse_type,
)


def test_parse_simple_integer() -> None:
    field = parse_type("Int32")
    assert isinstance(field, Int32)
    assert field.to_clickhouse(123) == 123
    with pytest.raises(ConversionError):
        field.to_clickhouse(1 << 40)


def test_unsigned_bounds() -> None:
    field = parse_type("UInt8")
    assert isinstance(field, UInt8)
    assert field.to_clickhouse(255) == 255
    with pytest.raises(ConversionError):
        field.to_clickhouse(-1)


def test_float_type_uses_dedicated_class() -> None:
    field = parse_type("Float32")
    assert isinstance(field, Float32)
    assert field.to_clickhouse("1.5") == pytest.approx(1.5)


def test_bfloat16_supported() -> None:
    field = parse_type("BFloat16")
    assert isinstance(field, BFloat16)
    assert field.to_clickhouse(1.234) == pytest.approx(1.234, rel=1e-6)


def test_json_type_parsing_and_conversion() -> None:
    field = parse_type("JSON")
    assert isinstance(field, JSONType)
    payload = {"a": 1, "b": ["x", 2]}
    serialized = field.to_clickhouse(payload)
    assert isinstance(serialized, str)
    restored = field.to_python(serialized)
    assert restored == payload
    # string validation
    with pytest.raises(ConversionError):
        field.to_clickhouse("not json")


def test_decimal_conversion_quantizes_scale() -> None:
    field = parse_type("Decimal64(2)")
    assert isinstance(field, DecimalType)
    result = field.to_clickhouse("12.345")
    assert isinstance(result, Decimal)
    assert result == Decimal("12.35")


def test_fixed_string_enforces_length() -> None:
    field = parse_type("FixedString(4)")
    data = field.to_clickhouse("test")
    assert data == b"test"
    with pytest.raises(ConversionError):
        field.to_clickhouse("toolong")


def test_uuid_and_ip_conversion() -> None:
    field_uuid = parse_type("UUID")
    uuid_value = field_uuid.to_clickhouse("12345678-1234-5678-1234-567812345678")
    assert str(uuid_value) == "12345678-1234-5678-1234-567812345678"

    field_ip = parse_type("IPv4")
    addr = field_ip.to_python("192.168.1.1")
    assert isinstance(addr, IPv4Address)
    assert field_ip.to_clickhouse(addr) == "192.168.1.1"


def test_date_and_datetime_conversion_with_timezone() -> None:
    field_date = parse_type("Date")
    assert field_date.to_python("2024-03-17") == date(2024, 3, 17)

    field_dt = parse_type("DateTime('UTC')")
    context = ConversionContext(default_timezone=ZoneInfo("Europe/Berlin"))
    value = field_dt.to_python("2024-01-02T03:04:05", context=context)
    assert isinstance(value, datetime)
    assert value.tzinfo == ZoneInfo("UTC")

    dt64 = parse_type("DateTime64(3, 'Europe/Berlin')")
    converted = dt64.to_clickhouse("2024-01-02T03:04:05.123")
    assert isinstance(converted, datetime)
    assert converted.tzinfo == ZoneInfo("Europe/Berlin")


def test_nullable_and_array() -> None:
    field = parse_type("Array(Nullable(UUID))")
    value = field.to_clickhouse(["12345678-1234-5678-1234-567812345678", None])
    assert value[0].hex == "12345678123456781234567812345678"
    assert value[1] is None


def test_enum_roundtrip() -> None:
    field = parse_type("Enum8('hello' = 1, 'world' = 2)")
    assert isinstance(field, EnumType)
    assert field.to_clickhouse("hello") == "hello"
    assert field.to_python(2) == "world"
    with pytest.raises(ConversionError):
        field.to_clickhouse("unknown")


def test_tuple_and_map_types() -> None:
    tuple_field = parse_type("Tuple(String, UInt8, Nullable(Int32))")
    assert isinstance(tuple_field, TupleType)
    value = tuple_field.to_clickhouse(("abc", 5, None))
    assert value == ("abc", 5, None)

    map_field = parse_type("Map(String, Int32)")
    assert isinstance(map_field, MapType)
    converted = map_field.to_python({"a": "1"})
    assert converted == {"a": 1}


def test_low_cardinality_passthrough() -> None:
    field = parse_type("LowCardinality(String)")
    assert field.to_python("hello") == "hello"


def test_parse_unknown_type_raises() -> None:
    with pytest.raises(ConversionError):
        parse_type("UnknownType(123)")
