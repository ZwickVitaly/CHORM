"""Tests for ClickHouse table engine classes."""

from __future__ import annotations

import pytest

from chorm.table_engines import (
    ENGINE_CLASSES,
    AggregatingMergeTree,
    Distributed,
    EngineConfigurationError,
    MergeTree,
    MySQL,
    ReplicatedMergeTree,
    ReplacingMergeTree,
    StripeLog,
    TableEngine,
)


def test_merge_tree_no_arguments() -> None:
    engine = MergeTree()
    assert engine.args == ()
    assert engine.settings == {}
    assert engine.format_clause() == "MergeTree"


def test_replacing_merge_tree_optional_argument() -> None:
    engine = ReplacingMergeTree()
    assert engine.args == (None,)

    engine_with_version = ReplacingMergeTree("version")
    assert engine_with_version.args == ("version",)
    assert engine_with_version.format_clause() == "ReplacingMergeTree(version)"


def test_replicated_merge_tree_requires_arguments() -> None:
    engine = ReplicatedMergeTree("/clickhouse/tables/mt", "replica01")
    assert engine.args == ("/clickhouse/tables/mt", "replica01")

    with pytest.raises(EngineConfigurationError):
        ReplicatedMergeTree("/clickhouse/tables/mt")


def test_keyword_arguments_supported() -> None:
    engine = Distributed(cluster="default", database="db", table="tbl", sharding_key="rand()")
    # policy_name is optional, so args includes None for it
    assert engine.args == ("default", "db", "tbl", "rand()", None)
    clause = engine.format_clause()
    assert clause.startswith("Distributed(")


def test_unknown_argument_or_setting_rejected() -> None:
    with pytest.raises(EngineConfigurationError):
        ReplacingMergeTree(version_column="ver", unknown=1)

    distributed = Distributed(cluster="c", database="d", table="t")
    with pytest.raises(EngineConfigurationError):
        Distributed("c", "d", "t", settings={"unknown": 1})
    assert distributed.settings == {}


def test_mysql_requires_full_connection_info() -> None:
    engine = MySQL("host:3306", "db", "tbl", "user", "pwd")
    assert engine.args == ("host:3306", "db", "tbl", "user", "pwd")
    with pytest.raises(EngineConfigurationError):
        MySQL("host", "db", "tbl", "user")


def test_engine_registry_contains_classes() -> None:
    assert ENGINE_CLASSES["MergeTree"] is MergeTree
    assert ENGINE_CLASSES["StripeLog"] is StripeLog
    for name, cls in ENGINE_CLASSES.items():
        assert issubclass(cls, TableEngine)
