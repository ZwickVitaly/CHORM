"""Tests for introspection: AggregateFunction types and Distributed tables."""

import ast
import pytest
from chorm.introspection import ModelGenerator


class TestAggregateFunctionIntrospection:
    """Test AggregateFunction type mapping and code generation."""

    def test_map_type_aggregate_function_simple(self):
        """Test mapping simple AggregateFunction type."""
        gen = ModelGenerator()
        result = gen.map_type("AggregateFunction(sum, UInt64)")
        assert "AggregateFunction" in result
        assert "func.sum" in result
        assert "UInt64()" in result

    def test_map_type_aggregate_function_multiple_args(self):
        """Test mapping AggregateFunction with multiple arguments."""
        gen = ModelGenerator()
        result = gen.map_type("AggregateFunction(anyIf, String, UInt8)")
        assert "AggregateFunction" in result
        assert "func.anyIf" in result
        assert "String()" in result
        assert "UInt8()" in result

    def test_map_type_aggregate_function_with_params(self):
        """Test mapping AggregateFunction with function parameters."""
        gen = ModelGenerator()
        result = gen.map_type("AggregateFunction(quantiles(0.5, 0.9), UInt64)")
        assert "AggregateFunction" in result
        assert "func.quantiles" in result
        assert "[0.5, 0.9]" in result
        assert "UInt64()" in result

    def test_map_type_aggregate_function_uniq_exact(self):
        """Test mapping AggregateFunction with uniqExact."""
        gen = ModelGenerator()
        result = gen.map_type("AggregateFunction(uniqExact, UInt32)")
        assert "AggregateFunction" in result
        assert "func.uniqExact" in result
        assert "UInt32()" in result

    def test_map_type_aggregate_function_group_uniq_array(self):
        """Test mapping AggregateFunction with groupUniqArray."""
        gen = ModelGenerator()
        result = gen.map_type("AggregateFunction(groupUniqArray, UInt32)")
        assert "AggregateFunction" in result
        assert "func.groupUniqArray" in result
        assert "UInt32()" in result

    def test_map_type_aggregate_function_count_distinct(self):
        """Test mapping AggregateFunction with countDistinct."""
        gen = ModelGenerator()
        result = gen.map_type("AggregateFunction(countDistinct, UInt32)")
        assert "AggregateFunction" in result
        assert "func.countDistinct" in result
        assert "UInt32()" in result

    def test_map_type_aggregate_function_quantile(self):
        """Test mapping AggregateFunction with quantile parameter."""
        gen = ModelGenerator()
        result = gen.map_type("AggregateFunction(quantile(0.5), UInt64)")
        assert "AggregateFunction" in result
        assert "func.quantile" in result
        assert "0.5" in result
        assert "UInt64()" in result

    def test_generate_model_with_aggregate_function(self):
        """Test generating model code with AggregateFunction columns."""
        gen = ModelGenerator()
        table_info = {
            "name": "test_agg_table",
            "engine": "AggregatingMergeTree",
            "engine_full": "AggregatingMergeTree()",
            "partition_key": "toYYYYMM(date)",
            "sorting_key": "id, date",
            "primary_key": "id, date",
            "columns": [
                {
                    "name": "id",
                    "type": "UInt32",
                    "default_kind": "",
                    "default_expression": "",
                    "comment": "",
                },
                {
                    "name": "date",
                    "type": "Date",
                    "default_kind": "",
                    "default_expression": "",
                    "comment": "",
                },
                {
                    "name": "revenue_state",
                    "type": "AggregateFunction(sum, UInt64)",
                    "default_kind": "",
                    "default_expression": "",
                    "comment": "",
                },
                {
                    "name": "uniq_wb_state",
                    "type": "AggregateFunction(uniqExact, UInt32)",
                    "default_kind": "",
                    "default_expression": "",
                    "comment": "",
                },
            ],
        }

        code = gen.generate_model(table_info)

        # Verify syntax is correct
        try:
            ast.parse(code)
        except SyntaxError as e:
            pytest.fail(f"Generated code has syntax error: {e}")

        # Verify AggregateFunction columns are present
        assert "revenue_state" in code
        assert "uniq_wb_state" in code
        assert "AggregateFunction" in code
        assert "func.sum" in code
        assert "func.uniqExact" in code
        assert "UInt64()" in code
        assert "UInt32()" in code

        # Verify proper Column() syntax with AggregateFunction
        assert "Column(AggregateFunction" in code

    def test_generate_model_supplier_warehouse_data(self):
        """Test generating model for supplier_warehouse_data table."""
        gen = ModelGenerator()
        table_info = {
            "name": "supplier_warehouse_data",
            "engine": "AggregatingMergeTree",
            "engine_full": "AggregatingMergeTree()",
            "partition_key": "toYYYYMM(date)",
            "sorting_key": "id, date, warehouse",
            "primary_key": "id, date, warehouse",
            "columns": [
                {
                    "name": "id",
                    "type": "UInt32",
                    "default_kind": "",
                    "default_expression": "",
                    "comment": "",
                },
                {
                    "name": "date",
                    "type": "Date",
                    "default_kind": "",
                    "default_expression": "",
                    "comment": "",
                },
                {
                    "name": "warehouse",
                    "type": "UInt32",
                    "default_kind": "",
                    "default_expression": "",
                    "comment": "",
                },
                {
                    "name": "revenue_state",
                    "type": "AggregateFunction(sum, UInt64)",
                    "default_kind": "",
                    "default_expression": "",
                    "comment": "",
                },
                {
                    "name": "revenue_spp_state",
                    "type": "AggregateFunction(sum, UInt64)",
                    "default_kind": "",
                    "default_expression": "",
                    "comment": "",
                },
                {
                    "name": "orders_state",
                    "type": "AggregateFunction(sum, UInt32)",
                    "default_kind": "",
                    "default_expression": "",
                    "comment": "",
                },
                {
                    "name": "quantity_state",
                    "type": "AggregateFunction(sum, UInt32)",
                    "default_kind": "",
                    "default_expression": "",
                    "comment": "",
                },
                {
                    "name": "uniq_wb_state",
                    "type": "AggregateFunction(uniqExact, UInt32)",
                    "default_kind": "",
                    "default_expression": "",
                    "comment": "",
                },
            ],
        }

        code = gen.generate_model(table_info)

        # Verify syntax is correct
        try:
            ast.parse(code)
        except SyntaxError as e:
            pytest.fail(f"Generated code has syntax error: {e}")

        # Verify all AggregateFunction columns are present
        assert "revenue_state" in code
        assert "revenue_spp_state" in code
        assert "orders_state" in code
        assert "quantity_state" in code
        assert "uniq_wb_state" in code

        # Verify all AggregateFunction types are properly generated
        assert "AggregateFunction" in code
        assert "func.sum" in code
        assert "func.uniqExact" in code
        assert "UInt64()" in code
        assert "UInt32()" in code

        # Verify proper syntax - no broken parentheses
        lines = code.split("\n")
        for line in lines:
            if "Column(" in line:
                # Count opening and closing parentheses
                open_count = line.count("(")
                close_count = line.count(")")
                assert (
                    open_count == close_count
                ), f"Unbalanced parentheses in line: {line}"


class TestDistributedIntrospection:
    """Test Distributed table engine handling in introspection."""

    def test_map_engine_distributed_simple(self):
        """Test mapping Distributed engine without sharding_key."""
        gen = ModelGenerator()
        engine_full = "Distributed('monitoring', 'radar', 'dates')"
        result = gen._map_distributed_engine(engine_full)
        assert "Distributed(" in result
        assert "cluster='monitoring'" in result
        assert "database='radar'" in result
        assert "table='dates'" in result

    def test_map_engine_distributed_with_sharding_key_rand(self):
        """Test mapping Distributed engine with rand() sharding_key."""
        gen = ModelGenerator()
        engine_full = "Distributed('monitoring', 'radar', 'dates', rand())"
        result = gen._map_distributed_engine(engine_full)
        assert "Distributed(" in result
        assert "cluster='monitoring'" in result
        assert "database='radar'" in result
        assert "table='dates'" in result
        assert "sharding_key" in result
        assert "rand()" in result

    def test_map_engine_distributed_with_sharding_key_column(self):
        """Test mapping Distributed engine with column sharding_key."""
        gen = ModelGenerator()
        engine_full = "Distributed('monitoring', 'radar', 'dates', id)"
        result = gen._map_distributed_engine(engine_full)
        assert "Distributed(" in result
        assert "sharding_key" in result
        assert "id" in result

    def test_map_engine_distributed_with_sharding_key_function(self):
        """Test mapping Distributed engine with function sharding_key."""
        gen = ModelGenerator()
        engine_full = "Distributed('monitoring', 'radar', 'dates', cityHash64(id))"
        result = gen._map_distributed_engine(engine_full)
        assert "Distributed(" in result
        assert "sharding_key" in result
        assert "cityHash64(id)" in result

    def test_map_engine_distributed_with_sharding_key_complex(self):
        """Test mapping Distributed engine with complex sharding_key expression."""
        gen = ModelGenerator()
        engine_full = "Distributed('monitoring', 'radar', 'dates', (id + user_id) % 10)"
        result = gen._map_distributed_engine(engine_full)
        assert "Distributed(" in result
        assert "sharding_key" in result
        assert "(id + user_id) % 10" in result

    def test_generate_model_distributed_table(self):
        """Test generating model code for Distributed table."""
        gen = ModelGenerator()
        table_info = {
            "name": "dates",
            "engine": "Distributed",
            "engine_full": "Distributed('monitoring', 'radar', 'dates', rand())",
            "partition_key": None,
            "sorting_key": None,
            "primary_key": None,
            "columns": [
                {
                    "name": "id",
                    "type": "UInt16",
                    "default_kind": "",
                    "default_expression": "",
                    "comment": "",
                },
                {
                    "name": "date",
                    "type": "Date",
                    "default_kind": "",
                    "default_expression": "",
                    "comment": "",
                },
            ],
        }

        code = gen.generate_model(table_info)

        # Verify syntax is correct
        try:
            ast.parse(code)
        except SyntaxError as e:
            pytest.fail(f"Generated code has syntax error: {e}")

        # Verify Distributed engine is present
        assert "Distributed(" in code
        assert "cluster=" in code
        assert "database=" in code
        assert "table=" in code
        assert "sharding_key=" in code

        # Verify no ORDER BY or PARTITION BY for Distributed
        assert "__order_by__" not in code
        assert "__partition_by__" not in code


class TestIntrospectionImports:
    """Test import generation in introspection."""

    def test_generate_imports_with_aggregate_function(self):
        """Test generating imports when AggregateFunction is used."""
        gen = ModelGenerator()
        gen.map_type("AggregateFunction(sum, UInt64)")
        imports = gen.generate_imports()
        
        assert "from chorm import Table, Column" in imports
        assert "AggregateFunction" in imports
        assert "from chorm.sql.expression import func" in imports
        assert "UInt64" in imports

    def test_generate_imports_with_distributed(self):
        """Test generating imports when Distributed engine is used."""
        gen = ModelGenerator()
        gen._map_engine("Distributed", "Distributed('cluster', 'db', 'table')")
        imports = gen.generate_imports()
        
        assert "from chorm import Table, Column" in imports
        assert "Distributed" in imports
        assert "from chorm.table_engines import" in imports

    def test_generate_imports_with_aggregating_merge_tree(self):
        """Test generating imports when AggregatingMergeTree is used."""
        gen = ModelGenerator()
        gen._map_engine("AggregatingMergeTree", "AggregatingMergeTree()")
        imports = gen.generate_imports()
        
        assert "AggregatingMergeTree" in imports
        assert "from chorm.table_engines import" in imports

    def test_generate_imports_mixed(self):
        """Test generating imports with multiple engines and types."""
        gen = ModelGenerator()
        # Add AggregateFunction
        gen.map_type("AggregateFunction(sum, UInt64)")
        gen.map_type("AggregateFunction(groupUniqArray, UInt32)")
        # Add Distributed engine
        gen._map_engine("Distributed", "Distributed('cluster', 'db', 'table')")
        # Add AggregatingMergeTree
        gen._map_engine("AggregatingMergeTree", "AggregatingMergeTree()")
        
        imports = gen.generate_imports()
        
        # Verify all imports are present
        assert "from chorm import Table, Column" in imports
        assert "AggregateFunction" in imports
        assert "from chorm.sql.expression import func" in imports
        assert "UInt64" in imports
        assert "UInt32" in imports
        assert "Distributed" in imports
        assert "AggregatingMergeTree" in imports
