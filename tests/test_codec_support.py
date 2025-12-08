import pytest
from unittest.mock import MagicMock
from chorm import Table, Column, MergeTree
from chorm.types import UInt64, String, UInt8
from chorm.ddl import format_ddl
from chorm.introspection import ModelGenerator
from chorm.codecs import Delta, ZSTD, LZ4

class TestCodecDDL:
    def test_column_codec(self):
        class Users(Table):
            __tablename__ = "users"
            __engine__ = MergeTree()
            __order_by__ = ["id"]
            
            id = Column(UInt64(), codec=Delta(8) | ZSTD(1))
            name = Column(String(), codec=ZSTD())
            
        ddl = Users.create_table()
        assert "id UInt64 CODEC(Delta(8), ZSTD(1))" in ddl
        assert "name String CODEC(ZSTD)" in ddl

    def test_no_codec(self):
        class Simple(Table):
            __tablename__ = "simple"
            __engine__ = MergeTree()
            __order_by__ = ["id"]
            
            id = Column(UInt64())
            
        ddl = Simple.create_table()
        assert "id UInt64" in ddl
        assert "CODEC" not in ddl

class TestCodecIntrospection:
    def test_introspection_parses_codec(self):
        generator = ModelGenerator()
        
        table_info = {
            "name": "users",
            "engine": "MergeTree",
            "engine_full": "MergeTree()",
            "sorting_key": "id",
            "partition_key": "",
            "primary_key": "",
            "columns": [
                {
                    "name": "id",
                    "type": "UInt64",
                    "default_kind": "",
                    "default_expression": "",
                    "comment": "",
                    "codec": "CODEC(Delta(8), ZSTD(1))"
                },
                {
                    "name": "name",
                    "type": "String",
                    "default_kind": "",
                    "default_expression": "",
                    "comment": "",
                    "codec": "CODEC(ZSTD(1))"
                },
                 {
                    "name": "age",
                    "type": "UInt8",
                    "default_kind": "",
                    "default_expression": "",
                    "comment": "",
                    "codec": "" # empty codec
                }
            ]
        }
        
        code = generator.generate_file([table_info])
        
        # Verify imports (order may vary, check parts)
        assert "from chorm.codecs import" in code
        assert "Delta" in code
        assert "ZSTD" in code
        
        # Verify codec expressions
        assert "id = Column(UInt64(), codec=Delta(8) | ZSTD(1))" in code
        assert "name = Column(String(), codec=ZSTD(1))" in code
        # Age should not have codec
        assert "age = Column(UInt8())" in code
