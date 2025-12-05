"""Tests for AggregateFunction type handling in introspection."""

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
        # Verify syntax is valid (already checked above with ast.parse)

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

