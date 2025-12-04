"""Tests for query profiling and complexity analysis."""

from chorm.profiler import QueryAnalyzer, QueryComplexity


class TestQueryAnalyzer:
    """Test QueryAnalyzer class."""

    def test_simple_query(self):
        """Test analyzing simple query."""
        analyzer = QueryAnalyzer()

        result = analyzer.analyze("SELECT id, name FROM users WHERE id = 1")

        assert result.score < 20  # Low complexity
        assert analyzer.get_complexity_level(result.score) == "low"

    def test_select_star(self):
        """Test detecting SELECT *."""
        analyzer = QueryAnalyzer()

        result = analyzer.analyze("SELECT * FROM users")

        assert result.score > 0
        assert any("SELECT *" in w for w in result.warnings)

    def test_missing_where(self):
        """Test detecting missing WHERE clause."""
        analyzer = QueryAnalyzer()

        result = analyzer.analyze("SELECT id FROM users")

        assert any("WHERE" in w for w in result.warnings)

    def test_multiple_joins(self):
        """Test detecting multiple JOINs."""
        analyzer = QueryAnalyzer()

        sql = """
        SELECT * FROM users u
        JOIN orders o ON u.id = o.user_id
        JOIN products p ON o.product_id = p.id
        JOIN categories c ON p.category_id = c.id
        """

        result = analyzer.analyze(sql)

        assert result.details["join_count"] == 3
        assert result.score > 20

    def test_subqueries(self):
        """Test detecting subqueries."""
        analyzer = QueryAnalyzer()

        sql = "SELECT * FROM users WHERE id IN (SELECT user_id FROM orders)"

        result = analyzer.analyze(sql)

        assert result.details["subquery_count"] == 1
        assert result.score > 0

    def test_complexity_levels(self):
        """Test complexity level classification."""
        analyzer = QueryAnalyzer()

        assert analyzer.get_complexity_level(10) == "low"
        assert analyzer.get_complexity_level(30) == "medium"
        assert analyzer.get_complexity_level(50) == "high"
        assert analyzer.get_complexity_level(80) == "very high"

    def test_recommendations(self):
        """Test that recommendations are provided."""
        analyzer = QueryAnalyzer()

        result = analyzer.analyze("SELECT * FROM users")

        assert len(result.recommendations) > 0
