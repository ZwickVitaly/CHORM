"""ClickHouse field types and value converters.

This module models modern ClickHouse data types and provides helper
conversions between Python values and the formats expected by
``clickhouse-connect``.  The implementation focuses on the data types that
ClickHouse documents as of 2024, including high-precision integers,
decimal/DateTime variants, IP/UUID helpers, and composite wrappers such as
``Nullable`` or ``Array``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date, datetime as _datetime
from decimal import Decimal as _Decimal, ROUND_HALF_UP, getcontext, localcontext
from ipaddress import IPv4Address, IPv6Address, ip_address
import json
from chorm.sql.expression import FunctionCall, Literal, _FunctionFactory
from typing import Any, Dict, List, Optional, Tuple, Type, Mapping, Sequence, Union, Iterable
from uuid import UUID as _UUID
from zoneinfo import ZoneInfo

from chorm.exceptions import TypeConversionError

# Backward compatibility alias
ConversionError = TypeConversionError


@dataclass(frozen=True, slots=True)
class ConversionContext:
    """Optional hints controlling conversions."""

    default_timezone: ZoneInfo | None = None


class FieldType:
    """Base class for ClickHouse field types."""

    ch_type: str

    def __init__(self, ch_type: str) -> None:
        self.ch_type = ch_type

    def to_python(self, value: Any, *, context: ConversionContext | None = None) -> Any:
        """Convert a raw ClickHouse value to a Python representation."""
        return value

    def to_clickhouse(self, value: Any, *, context: ConversionContext | None = None) -> Any:
        """Coerce a Python value into a ClickHouse-compatible representation."""
        return value

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"{self.__class__.__name__}({self.ch_type!r})"


class IntegerType(FieldType):
    def __init__(self, ch_type: str, *, bits: int, signed: bool) -> None:
        super().__init__(ch_type)
        self._bits = bits
        self._signed = signed
        if signed:
            self._min = -(1 << (bits - 1))
            self._max = (1 << (bits - 1)) - 1
        else:
            self._min = 0
            self._max = (1 << bits) - 1

    def to_python(self, value: Any, *, context: ConversionContext | None = None) -> int | None:
        if value is None:
            return None
        return int(value)

    def to_clickhouse(self, value: Any, *, context: ConversionContext | None = None) -> int | None:
        if value is None:
            return None
        try:
            converted = int(value)
        except (TypeError, ValueError) as exc:
            raise ConversionError(f"Expected integer for {self.ch_type}, got {value!r}") from exc
        if not (self._min <= converted <= self._max):
            raise ConversionError(f"Value {converted} out of range for {self.ch_type} " f"[{self._min}, {self._max}]")
        return converted


class Int8(IntegerType):
    def __init__(self) -> None:
        super().__init__("Int8", bits=8, signed=True)


class Int16(IntegerType):
    def __init__(self) -> None:
        super().__init__("Int16", bits=16, signed=True)


class Int32(IntegerType):
    def __init__(self) -> None:
        super().__init__("Int32", bits=32, signed=True)


class Int64(IntegerType):
    def __init__(self) -> None:
        super().__init__("Int64", bits=64, signed=True)


class Int128(IntegerType):
    def __init__(self) -> None:
        super().__init__("Int128", bits=128, signed=True)


class Int256(IntegerType):
    def __init__(self) -> None:
        super().__init__("Int256", bits=256, signed=True)


class UInt8(IntegerType):
    def __init__(self) -> None:
        super().__init__("UInt8", bits=8, signed=False)


class UInt16(IntegerType):
    def __init__(self) -> None:
        super().__init__("UInt16", bits=16, signed=False)


class UInt32(IntegerType):
    def __init__(self) -> None:
        super().__init__("UInt32", bits=32, signed=False)


class UInt64(IntegerType):
    def __init__(self) -> None:
        super().__init__("UInt64", bits=64, signed=False)


class UInt128(IntegerType):
    def __init__(self) -> None:
        super().__init__("UInt128", bits=128, signed=False)


class UInt256(IntegerType):
    def __init__(self) -> None:
        super().__init__("UInt256", bits=256, signed=False)


class FloatType(FieldType):
    def __init__(self, ch_type: str) -> None:
        super().__init__(ch_type)

    def to_python(self, value: Any, *, context: ConversionContext | None = None) -> float | None:
        if value is None:
            return None
        return float(value)

    def to_clickhouse(self, value: Any, *, context: ConversionContext | None = None) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise ConversionError(f"Expected float for {self.ch_type}, got {value!r}") from exc


class Float32(FloatType):
    def __init__(self) -> None:
        super().__init__("Float32")


class Float64(FloatType):
    def __init__(self) -> None:
        super().__init__("Float64")


class BFloat16(FloatType):
    def __init__(self) -> None:
        super().__init__("BFloat16")


class BooleanType(FieldType):
    def __init__(self) -> None:
        super().__init__("Bool")

    def to_python(self, value: Any, *, context: ConversionContext | None = None) -> bool | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, str)):
            return bool(int(value))
        raise ConversionError(f"Cannot convert {value!r} to bool")

    def to_clickhouse(self, value: Any, *, context: ConversionContext | None = None) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, str)):
            try:
                return int(bool(int(value)))
            except (TypeError, ValueError) as exc:
                raise ConversionError(f"Cannot coerce {value!r} to bool") from exc
        raise ConversionError(f"Cannot coerce {value!r} to bool")


class DecimalType(FieldType):
    def __init__(self, precision: int, scale: int) -> None:
        super().__init__(f"Decimal({precision}, {scale})")
        self.precision = precision
        self.scale = scale

    def to_python(self, value: Any, *, context: ConversionContext | None = None) -> _Decimal | None:
        if value is None:
            return None
        if isinstance(value, _Decimal):
            return value
        try:
            return _Decimal(str(value))
        except (TypeError, ValueError, ArithmeticError) as exc:
            raise ConversionError(f"Cannot convert {value!r} to Decimal") from exc

    def to_clickhouse(self, value: Any, *, context: ConversionContext | None = None) -> _Decimal | None:
        python_value = self.to_python(value, context=context)
        if python_value is None:
            return None

        with localcontext() as ctx:
            ctx.prec = max(getcontext().prec, self.precision)
            ctx.rounding = ROUND_HALF_UP
            quantize_target = _Decimal(1).scaleb(-self.scale)
            try:
                return python_value.quantize(quantize_target)
            except (ArithmeticError, ValueError) as exc:
                raise ConversionError(f"Decimal {python_value} does not fit scale {self.scale}") from exc


class StringType(FieldType):
    def __init__(self) -> None:
        super().__init__("String")

    def to_python(self, value: Any, *, context: ConversionContext | None = None) -> str | None:
        if value is None:
            return None
        return str(value)

    def to_clickhouse(self, value: Any, *, context: ConversionContext | None = None) -> str | None:
        if value is None:
            return None
        return str(value)


class JSONType(FieldType):
    def __init__(self) -> None:
        super().__init__("JSON")

    def _ensure_text(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, (bytes, bytearray)):
            try:
                return value.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ConversionError("JSON bytes must be UTF-8 encoded") from exc
        raise ConversionError(f"Expected JSON text or serializable object, got {value!r}")

    def to_python(self, value: Any, *, context: ConversionContext | None = None) -> Any:
        if value is None:
            return None
        if isinstance(value, (dict, list, int, float, bool)):
            return value
        if value is None:
            return None
        text = self._ensure_text(value)
        try:
            return json.loads(text)
        except (TypeError, ValueError) as exc:
            raise ConversionError(f"Invalid JSON data: {value!r}") from exc

    def to_clickhouse(self, value: Any, *, context: ConversionContext | None = None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            try:
                json.loads(value)
            except (TypeError, ValueError) as exc:
                raise ConversionError(f"Invalid JSON string: {value!r}") from exc
            return value
        if isinstance(value, (bytes, bytearray)):
            text = self._ensure_text(value)
            try:
                json.loads(text)
            except (TypeError, ValueError) as exc:
                raise ConversionError(f"Invalid JSON bytes: {value!r}") from exc
            return text

        try:
            return json.dumps(value, separators=(",", ":"), ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise ConversionError(f"Cannot serialize {value!r} to JSON") from exc


class FixedStringType(FieldType):
    def __init__(self, length: int) -> None:
        super().__init__(f"FixedString({length})")
        self.length = length

    def to_python(self, value: Any, *, context: ConversionContext | None = None) -> bytes | None:
        if value is None:
            return None
        if isinstance(value, bytes):
            return value
        if isinstance(value, str):
            return value.encode("utf-8")
        raise ConversionError(f"Expected bytes for {self.ch_type}, got {value!r}")

    def to_clickhouse(self, value: Any, *, context: ConversionContext | None = None) -> bytes | None:
        data = self.to_python(value, context=context)
        if data is None:
            return None
        if len(data) != self.length:
            raise ConversionError(f"{self.ch_type} expects exactly {self.length} bytes, got {len(data)}")
        return data


class UUIDType(FieldType):
    def __init__(self) -> None:
        super().__init__("UUID")

    def to_python(self, value: Any, *, context: ConversionContext | None = None) -> _UUID | None:
        if value is None:
            return None
        return _UUID(str(value))

    def to_clickhouse(self, value: Any, *, context: ConversionContext | None = None) -> _UUID | None:
        if value is None:
            return None
        if isinstance(value, _UUID):
            return value
        return _UUID(str(value))


class IPAddressType(FieldType):
    def __init__(self, ch_type: str, version: int) -> None:
        super().__init__(ch_type)
        self._version = version

    def to_python(
        self, value: Any, *, context: ConversionContext | None = None
    ) -> Union[IPv4Address, IPv6Address, None]:
        if value is None:
            return None
        address = ip_address(value)
        if address.version != self._version:
            raise ConversionError(f"Expected IPv{self._version} for {self.ch_type}, got {value!r}")
        return address

    def to_clickhouse(self, value: Any, *, context: ConversionContext | None = None) -> str | None:
        address = self.to_python(value, context=context)
        if address is None:
            return None
        return str(address)


class DateType(FieldType):
    def __init__(self, ch_type: str) -> None:
        super().__init__(ch_type)

    def to_python(self, value: Any, *, context: ConversionContext | None = None) -> _date | None:
        if value is None:
            return None
        if isinstance(value, _date) and not isinstance(value, _datetime):
            return value
        if isinstance(value, _datetime):
            return value.date()
        if isinstance(value, str):
            return _date.fromisoformat(value)
        raise ConversionError(f"Cannot convert {value!r} to date")

    def to_clickhouse(self, value: Any, *, context: ConversionContext | None = None) -> _date | None:
        converted = self.to_python(value, context=context)
        return converted


class DateTimeType(FieldType):
    def __init__(self, precision: int | None = None, timezone: str | None = None) -> None:
        if precision is None:
            ch_type = "DateTime" if timezone is None else f"DateTime('{timezone}')"
        else:
            base = f"DateTime64({precision})"
            if timezone is not None:
                base = f"DateTime64({precision}, '{timezone}')"
            ch_type = base
        super().__init__(ch_type)
        self.precision = precision
        self.timezone = timezone
        self._tzinfo = ZoneInfo(timezone) if timezone else None

    def _attach_timezone(self, value: _datetime, context: ConversionContext | None = None) -> _datetime:
        if value.tzinfo:
            if self._tzinfo:
                return value.astimezone(self._tzinfo)
            return value

        target_tz = self._tzinfo or (context.default_timezone if context else None)
        if target_tz:
            return value.replace(tzinfo=target_tz)
        return value

    def to_python(self, value: Any, *, context: ConversionContext | None = None) -> _datetime | None:
        if value is None:
            return None
        if isinstance(value, _datetime):
            return self._attach_timezone(value, context)
        if isinstance(value, str):
            parsed = _datetime.fromisoformat(value)
            return self._attach_timezone(parsed, context)
        if isinstance(value, (int, float)):
            parsed = _datetime.fromtimestamp(value)
            return self._attach_timezone(parsed, context)
        raise ConversionError(f"Cannot convert {value!r} to datetime")

    def to_clickhouse(self, value: Any, *, context: ConversionContext | None = None) -> _datetime | None:
        converted = self.to_python(value, context=context)
        return converted


class EnumType(FieldType):
    def __init__(self, ch_type: str, members: Mapping[str, int]) -> None:
        super().__init__(ch_type)
        self.members = dict(members)

    def to_python(self, value: Any, *, context: ConversionContext | None = None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, int):
            reverse = {v: k for k, v in self.members.items()}
            try:
                return reverse[value]
            except KeyError as exc:
                raise ConversionError(f"{value} not part of {self.ch_type}") from exc
        raise ConversionError(f"Cannot convert {value!r} to enum label")

    def to_clickhouse(self, value: Any, *, context: ConversionContext | None = None) -> str | None:
        if value is None:
            return None
        label = str(value)
        if label not in self.members:
            raise ConversionError(f"{label!r} not part of {self.ch_type}")
        return label


class NullableType(FieldType):
    def __init__(self, inner: FieldType) -> None:
        super().__init__(f"Nullable({inner.ch_type})")
        self.inner = inner

    def to_python(self, value: Any, *, context: ConversionContext | None = None) -> Any:
        if value is None:
            return None
        return self.inner.to_python(value, context=context)

    def to_clickhouse(self, value: Any, *, context: ConversionContext | None = None) -> Any:
        if value is None:
            return None
        return self.inner.to_clickhouse(value, context=context)


class LowCardinalityType(FieldType):
    def __init__(self, inner: FieldType) -> None:
        super().__init__(f"LowCardinality({inner.ch_type})")
        self.inner = inner

    def to_python(self, value: Any, *, context: ConversionContext | None = None) -> Any:
        return self.inner.to_python(value, context=context)

    def to_clickhouse(self, value: Any, *, context: ConversionContext | None = None) -> Any:
        return self.inner.to_clickhouse(value, context=context)


class ArrayType(FieldType):
    def __init__(self, inner: FieldType) -> None:
        super().__init__(f"Array({inner.ch_type})")
        self.inner = inner

    def to_python(self, value: Any, *, context: ConversionContext | None = None) -> List[Any] | None:
        if value is None:
            return None
        if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
            raise ConversionError(f"Expected iterable for {self.ch_type}, got {value!r}")
        return [self.inner.to_python(item, context=context) for item in value]

    def to_clickhouse(self, value: Any, *, context: ConversionContext | None = None) -> List[Any] | None:
        if value is None:
            return None
        if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
            raise ConversionError(f"Expected iterable for {self.ch_type}, got {value!r}")
        return [self.inner.to_clickhouse(item, context=context) for item in value]


class TupleType(FieldType):
    def __init__(self, elements: Sequence[FieldType]) -> None:
        ch_elements = ", ".join(elem.ch_type for elem in elements)
        super().__init__(f"Tuple({ch_elements})")
        self.elements = tuple(elements)

    def to_python(self, value: Any, *, context: ConversionContext | None = None) -> Tuple[Any, ...] | None:
        if value is None:
            return None
        if not isinstance(value, Sequence):
            raise ConversionError(f"Expected sequence for {self.ch_type}, got {value!r}")
        if len(value) != len(self.elements):
            raise ConversionError(f"{self.ch_type} expects {len(self.elements)} items, got {len(value)}")
        return tuple(field.to_python(item, context=context) for field, item in zip(self.elements, value))

    def to_clickhouse(self, value: Any, *, context: ConversionContext | None = None) -> Tuple[Any, ...] | None:
        if value is None:
            return None
        if not isinstance(value, Sequence):
            raise ConversionError(f"Expected sequence for {self.ch_type}, got {value!r}")
        if len(value) != len(self.elements):
            raise ConversionError(f"{self.ch_type} expects {len(self.elements)} items, got {len(value)}")
        return tuple(field.to_clickhouse(item, context=context) for field, item in zip(self.elements, value))


class MapType(FieldType):
    def __init__(self, key_type: FieldType, value_type: FieldType) -> None:
        super().__init__(f"Map({key_type.ch_type}, {value_type.ch_type})")
        self.key_type = key_type
        self.value_type = value_type

    def to_python(self, value: Any, *, context: ConversionContext | None = None) -> Dict[Any, Any] | None:
        if value is None:
            return None
        if not isinstance(value, Mapping):
            raise ConversionError(f"Expected mapping for {self.ch_type}, got {value!r}")
        return {
            self.key_type.to_python(k, context=context): self.value_type.to_python(v, context=context)
            for k, v in value.items()
        }

    def to_clickhouse(self, value: Any, *, context: ConversionContext | None = None) -> Dict[Any, Any] | None:
        if value is None:
            return None
        if not isinstance(value, Mapping):
            raise ConversionError(f"Expected mapping for {self.ch_type}, got {value!r}")
        return {
            self.key_type.to_clickhouse(k, context=context): self.value_type.to_clickhouse(v, context=context)
            for k, v in value.items()
        }


class AggregateFunctionType(FieldType):
    """Type for ClickHouse AggregateFunction.
    
    AggregateFunction stores intermediate states of aggregate functions.
    Values are binary states (bytes) that can be merged using -Merge combinators.
    
    Examples:
        from chorm.sql.expression import func
        from chorm.types import AggregateFunction, UInt64
        
        # Using function from func namespace
        AggregateFunction(func.sum, UInt64())
        AggregateFunction(func.uniq, UInt64())
        AggregateFunction(func.quantile(0.5), UInt64())
        
        # Or using string (for parse_type compatibility)
        AggregateFunction("sum", UInt64())
    """
    
    def __init__(self, func_or_name: Any, *arg_types: FieldType) -> None:
        """Initialize AggregateFunction type.
        
        Args:
            func_or_name: Either:
                - FunctionCall from func namespace (e.g., func.sum('dummy'), func.quantile(0.5, 'dummy'))
                  Note: Use dummy argument for functions with parameters, only parameter values matter
                - _FunctionFactory from func (e.g., func.sum) - will extract just the name
                - String with function name (e.g., 'sum', 'quantiles(0.5, 0.9)')
            *arg_types: Variable number of argument types for the aggregate function
        """
        # Extract function name from FunctionCall, _FunctionFactory, or use string directly
        from chorm.sql.expression import FunctionCall, Literal
        
        if isinstance(func_or_name, FunctionCall):
            # Extract function name and parameters from FunctionCall
            func_name = func_or_name.name
            # If function has parameters (like quantile(0.5)), include them
            # Parameters are typically Literal values at the start of args
            param_args = []
            for arg in func_or_name.args:
                if isinstance(arg, Literal):
                    # Extract parameter value
                    val = arg.value
                    # Format appropriately
                    if isinstance(val, (list, tuple)):
                        # For quantiles([0.5, 0.9]) -> "quantiles(0.5, 0.9)"
                        # Expand list/tuple into multiple parameters
                        param_args.extend(str(v) for v in val)
                    elif isinstance(val, str):
                        param_args.append(f"'{val}'")
                    else:
                        param_args.append(str(val))
                else:
                    # If we hit a non-literal, stop - these are actual column args (ignored for AggregateFunction)
                    break
            
            if param_args:
                # Function with parameters: quantile(0.5) -> "quantile(0.5)"
                func_name = f"{func_name}({', '.join(param_args)})"
        elif isinstance(func_or_name, str):
            func_name = func_or_name
        else:
            # Try to get name from _FunctionFactory (e.g., func.sum)
            if isinstance(func_or_name, _FunctionFactory):
                func_name = func_or_name.name
            elif hasattr(func_or_name, 'name'):
                func_name = func_or_name.name
            else:
                raise ConversionError(
                    f"AggregateFunction first argument must be FunctionCall, _FunctionFactory, string, "
                    f"or function from func namespace, got {type(func_or_name).__name__}: {func_or_name!r}"
                )
        
        # Handle backward compatibility: if only one tuple is passed, unpack it
        if len(arg_types) == 1 and isinstance(arg_types[0], tuple):
            arg_types = arg_types[0]
        
        # Build type string: AggregateFunction(func_name, type1, type2, ...)
        arg_types_str = ", ".join(arg_type.ch_type for arg_type in arg_types)
        ch_type = f"AggregateFunction({func_name}, {arg_types_str})" if arg_types else f"AggregateFunction({func_name})"
        super().__init__(ch_type)
        self.func_name = func_name
        self.arg_types = tuple(arg_types)  # Store as tuple for backward compatibility
    
    def to_python(self, value: Any, *, context: ConversionContext | None = None) -> bytes | None:
        """Convert AggregateFunction state to Python representation.
        
        AggregateFunction values are binary states. They are returned as bytes.
        To get actual aggregated values, use -Merge combinators in queries.
        
        Args:
            value: Binary state from ClickHouse (bytes, bytearray, or None)
            context: Optional conversion context
            
        Returns:
            bytes or None - the binary state representation
        """
        if value is None:
            return None
        if isinstance(value, bytes):
            return value
        if isinstance(value, bytearray):
            return bytes(value)
        if isinstance(value, str):
            # Some drivers might return base64-encoded strings
            import base64
            try:
                return base64.b64decode(value)
            except Exception:
                # If not base64, try to encode as UTF-8
                return value.encode('utf-8')
        # Try to convert to bytes
        try:
            return bytes(value)
        except (TypeError, ValueError) as exc:
            raise ConversionError(
                f"Expected bytes, bytearray, or None for {self.ch_type}, got {type(value).__name__}: {value!r}"
            ) from exc
    
    def to_clickhouse(self, value: Any, *, context: ConversionContext | None = None) -> bytes | None:
        """Convert Python value to AggregateFunction state for ClickHouse.
        
        AggregateFunction states are typically created using -State combinators
        (e.g., sumState, uniqState) in INSERT queries, not directly from Python.
        However, this method allows passing binary states directly.
        
        Args:
            value: Binary state (bytes, bytearray, or None)
            context: Optional conversion context
            
        Returns:
            bytes or None - the binary state for ClickHouse
        """
        if value is None:
            return None
        if isinstance(value, bytes):
            return value
        if isinstance(value, bytearray):
            return bytes(value)
        if isinstance(value, str):
            # Try base64 decode first, then UTF-8 encode
            import base64
            try:
                return base64.b64decode(value)
            except Exception:
                return value.encode('utf-8')
        # Try to convert to bytes
        try:
            return bytes(value)
        except (TypeError, ValueError) as exc:
            raise ConversionError(
                f"Expected bytes, bytearray, or None for {self.ch_type}, got {type(value).__name__}: {value!r}. "
                f"Note: AggregateFunction states are typically created using -State combinators in SQL queries."
            ) from exc


# --- Registry and parsing helpers -------------------------------------------------

_SIMPLE_FACTORIES: Dict[str, Callable[[], FieldType]] = {}


def _register_simple(name: str, factory: Callable[[], FieldType]) -> None:
    _SIMPLE_FACTORIES[name] = factory


def _init_registry() -> None:
    integer_classes = (
        Int8,
        Int16,
        Int32,
        Int64,
        Int128,
        Int256,
        UInt8,
        UInt16,
        UInt32,
        UInt64,
        UInt128,
        UInt256,
    )
    for cls in integer_classes:
        instance = cls()
        _register_simple(instance.ch_type, cls)

    other_classes = (
        BFloat16,
        Float32,
        Float64,
        BooleanType,
        StringType,
        JSONType,
        UUIDType,
    )
    for cls in other_classes:
        instance = cls()
        _register_simple(instance.ch_type, cls)

    _register_simple("IPv4", lambda: IPAddressType("IPv4", version=4))
    _register_simple("IPv6", lambda: IPAddressType("IPv6", version=6))
    _register_simple("Date", lambda: DateType("Date"))
    _register_simple("Date32", lambda: DateType("Date32"))
    _register_simple("DateTime", lambda: DateTimeType())


_init_registry()


def get_simple_type(name: str) -> FieldType:
    try:
        factory = _SIMPLE_FACTORIES[name]
    except KeyError as exc:
        raise ConversionError(f"Unknown ClickHouse type '{name}'") from exc
    return factory()


def parse_type(type_spec: str) -> FieldType:
    """Parse a ClickHouse type definition into a :class:`FieldType`."""

    type_spec = type_spec.strip()
    if not type_spec:
        raise ConversionError("Empty type spec")

    if "(" not in type_spec:
        return get_simple_type(type_spec)

    name, args_str = _split_name_and_args(type_spec)
    args = _split_args(args_str)

    if name == "Nullable":
        return NullableType(parse_type(args[0]))
    if name == "LowCardinality":
        return LowCardinalityType(parse_type(args[0]))
    if name == "Array":
        return ArrayType(parse_type(args[0]))
    if name == "Tuple":
        return TupleType(tuple(parse_type(arg) for arg in args))
    if name == "Map":
        if len(args) != 2:
            raise ConversionError("Map requires two arguments")
        return MapType(parse_type(args[0]), parse_type(args[1]))
    if name.startswith("Decimal"):
        if name == "Decimal":
            if len(args) != 2:
                raise ConversionError("Decimal requires precision and scale")
            precision = int(args[0])
            scale = int(args[1])
        else:
            precision = {
                "Decimal32": 9,
                "Decimal64": 18,
                "Decimal128": 38,
                "Decimal256": 76,
            }.get(name)
            if precision is None:
                raise ConversionError(f"Unsupported decimal type '{name}'")
            if len(args) != 1:
                raise ConversionError(f"{name} requires a single scale argument")
            scale = int(args[0])
        return DecimalType(precision, scale)
    if name == "FixedString":
        if len(args) != 1:
            raise ConversionError("FixedString requires length")
        return FixedStringType(int(args[0]))
    if name.startswith("Enum"):
        mapping = _parse_enum_members(args)
        return EnumType(f"{name}({', '.join(args)})", mapping)
    if name.startswith("DateTime64"):
        if len(args) not in (1, 2):
            raise ConversionError("DateTime64 requires precision and optional timezone")
        precision = int(args[0])
        timezone = _unquote(args[1]) if len(args) == 2 else None
        return DateTimeType(precision=precision, timezone=timezone)
    if name == "DateTime":
        if len(args) > 1:
            raise ConversionError("DateTime accepts at most one timezone argument")
        timezone = _unquote(args[0]) if args else None
        return DateTimeType(precision=None, timezone=timezone)
    if name == "JSON":
        return JSONType()
    if name == "AggregateFunction":
        # Parse AggregateFunction(func_name, arg_types...)
        # Examples:
        #   AggregateFunction(sum, UInt64)
        #   AggregateFunction(anyIf, String, UInt8)
        #   AggregateFunction(quantiles(0.5, 0.9), UInt64)
        if not args:
            raise ConversionError("AggregateFunction requires at least function name")
        
        # First argument is function name (may include parameters like quantiles(0.5, 0.9))
        func_name = args[0]
        # Remaining arguments are argument types - unpack as *arg_types
        arg_types = [parse_type(arg) for arg in args[1:]] if len(args) > 1 else []
        
        return AggregateFunctionType(func_name, *arg_types)

    raise ConversionError(f"Unsupported ClickHouse type '{name}'")


def _split_name_and_args(type_spec: str) -> Tuple[str, str]:
    depth = 0
    start = 0
    for idx, char in enumerate(type_spec):
        if char == "(":
            if depth == 0:
                start = idx
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                break
    if depth != 0:
        raise ConversionError(f"Unbalanced parentheses in {type_spec!r}")
    name = type_spec[:start].strip()
    args = type_spec[start + 1 : idx].strip()
    return name, args


def _split_args(args: str) -> List[str]:
    result: List[str] = []
    current: List[str] = []
    depth = 0
    in_quote = False
    quote_char = ""

    for char in args:
        if in_quote:
            current.append(char)
            if char == quote_char:
                in_quote = False
            continue
        if char in ("'", '"'):
            in_quote = True
            quote_char = char
            current.append(char)
            continue
        if char == "(":
            depth += 1
            current.append(char)
            continue
        if char == ")":
            depth -= 1
            current.append(char)
            continue
        if char == "," and depth == 0:
            result.append("".join(current).strip())
            current = []
            continue
        current.append(char)

    if current:
        result.append("".join(current).strip())

    return [arg for arg in result if arg]


def _parse_enum_members(args: Sequence[str]) -> Dict[str, int]:
    members: Dict[str, int] = {}
    for arg in args:
        if "=" not in arg:
            raise ConversionError(f"Enum entry {arg!r} missing '='")
        label, value = arg.split("=", 1)
        label = _unquote(label.strip())
        value = value.strip()
        members[label] = int(value)
    return members


def _unquote(value: str) -> str:
    if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
        return value[1:-1]
    return value


# Aliases for convenience and compatibility
String = StringType
FixedString = FixedStringType
Array = ArrayType
Map = MapType
Tuple = TupleType
Nullable = NullableType
LowCardinality = LowCardinalityType
Enum = EnumType
Decimal = DecimalType
DateTime = DateTimeType
JSON = JSONType
UUID = UUIDType
IPv4 = IPAddressType
IPv6 = IPAddressType
Bool = BooleanType
Float32 = Float32
Float64 = Float64
AggregateFunction = AggregateFunctionType


# Factory functions for types that require arguments
def Date() -> DateType:
    """Create a Date type."""
    return DateType("Date")


__all__ = [
    "AggregateFunctionType",
    "ArrayType",
    "BooleanType",
    "ConversionContext",
    "ConversionError",
    "DateTimeType",
    "DateType",
    "DecimalType",
    "EnumType",
    "FieldType",
    "FixedStringType",
    "FloatType",
    "BFloat16",
    "Float32",
    "Float64",
    "JSONType",
    "IPAddressType",
    "IntegerType",
    "Int8",
    "Int16",
    "Int32",
    "Int64",
    "Int128",
    "Int256",
    "LowCardinalityType",
    "MapType",
    "NullableType",
    "StringType",
    "TupleType",
    "UUIDType",
    "UInt8",
    "UInt16",
    "UInt32",
    "UInt64",
    "UInt128",
    "UInt256",
    "parse_type",
    "String",
    "FixedString",
    "Array",
    "Map",
    "Tuple",
    "Nullable",
    "LowCardinality",
    "Enum",
    "Decimal",
    "DateTime",
    "Date",
    "JSON",
    "UUID",
    "IPv4",
    "IPv6",
    "Bool",
    "AggregateFunction",
]
