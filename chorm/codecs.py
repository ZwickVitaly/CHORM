from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, Union, Sequence, List

class Codec(ABC):
    """Base class for ClickHouse compression codecs."""

    @abstractmethod
    def to_sql(self) -> str:
        """Render the codec as a SQL string component."""
        pass

    def __or__(self, other: Union[Codec, str]) -> CodecPipeline:
        """Chain codecs using the | operator."""
        return CodecPipeline([self]).chain(other)

    def __repr__(self) -> str:
        return self.__class__.__name__ + "()"


class CodecPipeline(Codec):
    """Represents a chain of codecs."""
    
    def __init__(self, codecs: List[Codec]):
        self.codecs = codecs

    def chain(self, other: Union[Codec, str]) -> CodecPipeline:
        if isinstance(other, CodecPipeline):
            self.codecs.extend(other.codecs)
        elif isinstance(other, Codec):
            self.codecs.append(other)
        else:
            raise TypeError(f"Cannot chain Codec with {type(other)}")
        return self

    def to_sql(self) -> str:
        return ", ".join(c.to_sql() for c in self.codecs)

    def __or__(self, other: Union[Codec, str]) -> CodecPipeline:
        return self.chain(other)
    
    def __repr__(self) -> str:
        return " | ".join(repr(c) for c in self.codecs)


class SimpleCodec(Codec):
    """Codec without parameters (e.g. LZ4, DoubleDelta)."""
    
    def to_sql(self) -> str:
        return self.__class__.__name__


class ParametrizedCodec(Codec):
    """Codec with parameters (e.g. ZSTD(1), Delta(4))."""
    
    def __init__(self, *args):
        self.args = args

    def to_sql(self) -> str:
        if self.args:
            args_str = ", ".join(str(a) for a in self.args)
            return f"{self.__class__.__name__}({args_str})"
        return self.__class__.__name__

    def __repr__(self) -> str:
        if self.args:
            args_str = ", ".join(str(a) for a in self.args)
            return f"{self.__class__.__name__}({args_str})"
        return f"{self.__class__.__name__}()"


# --- Implementations ---

class LZ4(SimpleCodec):
    """LZ4 compression (default)."""
    pass

class LZ4HC(ParametrizedCodec):
    """LZ4HC compression with configurable level (1-9)."""
    pass

class ZSTD(ParametrizedCodec):
    """ZSTD compression with configurable level (1-22)."""
    pass

class Delta(ParametrizedCodec):
    """Delta encoding for time series or monotonic data."""
    pass

class DoubleDelta(ParametrizedCodec):
    """Double Delta encoding for slowly changing values (like timestamps)."""
    pass

class Gorilla(ParametrizedCodec):
    """Gorilla encoding for floating point values."""
    pass

class T64(SimpleCodec):
    """T64 encoding for integers."""
    pass

class FPC(ParametrizedCodec):
    """FPC encoding for floating point values."""
    pass

class NONE(SimpleCodec):
    """No compression."""
    def to_sql(self) -> str:
        return "NONE"

# Allow using string aliases for convenience in introspection parsing if needed
CODEC_MAP = {
    "LZ4": LZ4,
    "LZ4HC": LZ4HC,
    "ZSTD": ZSTD,
    "Delta": Delta,
    "DoubleDelta": DoubleDelta,
    "Gorilla": Gorilla,
    "T64": T64,
    "FPC": FPC,
    "NONE": NONE,
}
