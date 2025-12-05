"""Tests for AggregateFunction combinators (State and Merge)."""

from chorm.sql.expression import (
    sum_state,
    sum_merge,
    avg_state,
    avg_merge,
    count_state,
    count_merge,
    uniq_state,
    uniq_merge,
    uniq_exact_state,
    uniq_exact_merge,
    quantile_state,
    quantile_merge,
    quantiles_state,
    quantiles_merge,
    min_state,
    min_merge,
    max_state,
    max_merge,
    sum_if_state,
    sum_if_merge,
    avg_if_state,
    avg_if_merge,
    count_if_state,
    count_if_merge,
    min_if_state,
    min_if_merge,
    max_if_state,
    max_if_merge,
    uniq_if_state,
    uniq_if_merge,
    Identifier,
)


class TestStateCombinators:
    """Test State combinators for creating AggregateFunction states."""

    def test_sum_state(self):
        """Test sumState combinator."""
        expr = sum_state(Identifier("amount"))
        assert expr.to_sql() == "sumState(amount)"

    def test_avg_state(self):
        """Test avgState combinator."""
        expr = avg_state(Identifier("value"))
        assert expr.to_sql() == "avgState(value)"

    def test_count_state(self):
        """Test countState combinator."""
        expr = count_state()
        assert expr.to_sql() == "countState()"

    def test_count_state_with_arg(self):
        """Test countState combinator with argument."""
        expr = count_state(Identifier("id"))
        assert expr.to_sql() == "countState(id)"

    def test_uniq_state(self):
        """Test uniqState combinator."""
        expr = uniq_state(Identifier("user_id"))
        assert expr.to_sql() == "uniqState(user_id)"

    def test_uniq_exact_state(self):
        """Test uniqExactState combinator."""
        expr = uniq_exact_state(Identifier("user_id"))
        assert expr.to_sql() == "uniqExactState(user_id)"

    def test_quantile_state(self):
        """Test quantileState combinator."""
        expr = quantile_state(0.5, Identifier("value"))
        assert expr.to_sql() == "quantileState(0.5)(value)"

    def test_quantiles_state(self):
        """Test quantilesState combinator."""
        expr = quantiles_state([0.5, 0.9], Identifier("value"))
        assert expr.to_sql() == "quantilesState(0.5, 0.9)(value)"

    def test_min_state(self):
        """Test minState combinator."""
        expr = min_state(Identifier("price"))
        assert expr.to_sql() == "minState(price)"

    def test_max_state(self):
        """Test maxState combinator."""
        expr = max_state(Identifier("price"))
        assert expr.to_sql() == "maxState(price)"


class TestMergeCombinators:
    """Test Merge combinators for finalizing AggregateFunction states."""

    def test_sum_merge(self):
        """Test sumMerge combinator."""
        expr = sum_merge(Identifier("revenue_state"))
        assert expr.to_sql() == "sumMerge(revenue_state)"

    def test_avg_merge(self):
        """Test avgMerge combinator."""
        expr = avg_merge(Identifier("avg_state"))
        assert expr.to_sql() == "avgMerge(avg_state)"

    def test_count_merge(self):
        """Test countMerge combinator."""
        expr = count_merge(Identifier("count_state"))
        assert expr.to_sql() == "countMerge(count_state)"

    def test_uniq_merge(self):
        """Test uniqMerge combinator."""
        expr = uniq_merge(Identifier("uniq_state"))
        assert expr.to_sql() == "uniqMerge(uniq_state)"

    def test_uniq_exact_merge(self):
        """Test uniqExactMerge combinator."""
        expr = uniq_exact_merge(Identifier("uniq_exact_state"))
        assert expr.to_sql() == "uniqExactMerge(uniq_exact_state)"

    def test_quantile_merge(self):
        """Test quantileMerge combinator."""
        expr = quantile_merge(0.5, Identifier("quantile_state"))
        assert expr.to_sql() == "quantileMerge(0.5)(quantile_state)"

    def test_quantiles_merge(self):
        """Test quantilesMerge combinator."""
        expr = quantiles_merge([0.5, 0.9], Identifier("quantiles_state"))
        assert expr.to_sql() == "quantilesMerge(0.5, 0.9)(quantiles_state)"

    def test_min_merge(self):
        """Test minMerge combinator."""
        expr = min_merge(Identifier("min_state"))
        assert expr.to_sql() == "minMerge(min_state)"

    def test_max_merge(self):
        """Test maxMerge combinator."""
        expr = max_merge(Identifier("max_state"))
        assert expr.to_sql() == "maxMerge(max_state)"


class TestIfStateCombinators:
    """Test State combinators for conditional aggregate functions."""

    def test_sum_if_state(self):
        """Test sumIfState combinator."""
        expr = sum_if_state(Identifier("amount"), Identifier("condition"))
        assert expr.to_sql() == "sumIfState(amount, condition)"

    def test_avg_if_state(self):
        """Test avgIfState combinator."""
        expr = avg_if_state(Identifier("value"), Identifier("condition"))
        assert expr.to_sql() == "avgIfState(value, condition)"

    def test_count_if_state(self):
        """Test countIfState combinator."""
        expr = count_if_state(Identifier("condition"))
        assert expr.to_sql() == "countIfState(condition)"

    def test_min_if_state(self):
        """Test minIfState combinator."""
        expr = min_if_state(Identifier("price"), Identifier("condition"))
        assert expr.to_sql() == "minIfState(price, condition)"

    def test_max_if_state(self):
        """Test maxIfState combinator."""
        expr = max_if_state(Identifier("price"), Identifier("condition"))
        assert expr.to_sql() == "maxIfState(price, condition)"

    def test_uniq_if_state(self):
        """Test uniqIfState combinator."""
        expr = uniq_if_state(Identifier("user_id"), Identifier("condition"))
        assert expr.to_sql() == "uniqIfState(user_id, condition)"


class TestIfMergeCombinators:
    """Test Merge combinators for conditional aggregate functions."""

    def test_sum_if_merge(self):
        """Test sumIfMerge combinator."""
        expr = sum_if_merge(Identifier("sum_if_state"))
        assert expr.to_sql() == "sumIfMerge(sum_if_state)"

    def test_avg_if_merge(self):
        """Test avgIfMerge combinator."""
        expr = avg_if_merge(Identifier("avg_if_state"))
        assert expr.to_sql() == "avgIfMerge(avg_if_state)"

    def test_count_if_merge(self):
        """Test countIfMerge combinator."""
        expr = count_if_merge(Identifier("count_if_state"))
        assert expr.to_sql() == "countIfMerge(count_if_state)"

    def test_min_if_merge(self):
        """Test minIfMerge combinator."""
        expr = min_if_merge(Identifier("min_if_state"))
        assert expr.to_sql() == "minIfMerge(min_if_state)"

    def test_max_if_merge(self):
        """Test maxIfMerge combinator."""
        expr = max_if_merge(Identifier("max_if_state"))
        assert expr.to_sql() == "maxIfMerge(max_if_state)"

    def test_uniq_if_merge(self):
        """Test uniqIfMerge combinator."""
        expr = uniq_if_merge(Identifier("uniq_if_state"))
        assert expr.to_sql() == "uniqIfMerge(uniq_if_state)"

