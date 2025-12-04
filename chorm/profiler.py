"""Performance profiling and query complexity analysis."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class QueryComplexity:
    """Query complexity analysis result.

    Attributes:
        sql: SQL query text
        score: Complexity score (0-100, higher = more complex)
        warnings: List of complexity warnings
        recommendations: List of optimization recommendations
        details: Detailed complexity breakdown
    """

    sql: str
    score: int
    warnings: List[str]
    recommendations: List[str]
    details: Dict[str, any]


class QueryAnalyzer:
    """Analyze query complexity and provide optimization recommendations.

    Example:
        >>> analyzer = QueryAnalyzer()
        >>> result = analyzer.analyze("SELECT * FROM huge_table WHERE x = 1")
        >>> print(f"Complexity score: {result.score}")
        >>> for warning in result.warnings:
        ...     print(f"Warning: {warning}")
    """

    def analyze(self, sql: str) -> QueryComplexity:
        """Analyze query complexity.

        Args:
            sql: SQL query text

        Returns:
            QueryComplexity result
        """
        sql_upper = sql.upper()
        score = 0
        warnings = []
        recommendations = []
        details = {}

        # Check for SELECT *
        if re.search(r"\bSELECT\s+\*", sql_upper):
            score += 10
            warnings.append("Using SELECT * - consider selecting only needed columns")
            recommendations.append("Replace SELECT * with explicit column names")

        # Check for missing WHERE clause
        if "SELECT" in sql_upper and "WHERE" not in sql_upper and "LIMIT" not in sql_upper:
            score += 20
            warnings.append("No WHERE clause - may scan entire table")
            recommendations.append("Add WHERE clause to filter data")

        # Check for JOINs
        join_count = len(re.findall(r"\bJOIN\b", sql_upper))
        if join_count > 0:
            score += join_count * 5
            details["join_count"] = join_count
            if join_count > 3:
                warnings.append(f"Multiple JOINs ({join_count}) - may be slow")
                recommendations.append("Consider denormalizing data or using materialized views")

        # Check for subqueries
        subquery_count = sql.count("(SELECT")
        if subquery_count > 0:
            score += subquery_count * 10
            details["subquery_count"] = subquery_count
            if subquery_count > 2:
                warnings.append(f"Multiple subqueries ({subquery_count}) - consider CTEs")
                recommendations.append("Replace subqueries with CTEs for better readability")

        # Check for DISTINCT
        if "DISTINCT" in sql_upper:
            score += 15
            warnings.append("Using DISTINCT - may require sorting")
            recommendations.append("Consider using GROUP BY if possible")

        # Check for ORDER BY without LIMIT
        if "ORDER BY" in sql_upper and "LIMIT" not in sql_upper:
            score += 15
            warnings.append("ORDER BY without LIMIT - may sort entire result set")
            recommendations.append("Add LIMIT to reduce sorting overhead")

        # Check for LIKE with leading wildcard
        if re.search(r"LIKE\s+['\"]%", sql_upper):
            score += 20
            warnings.append("LIKE with leading wildcard - cannot use index")
            recommendations.append("Avoid leading wildcards in LIKE patterns")

        # Check for functions in WHERE clause
        if re.search(r"WHERE.*\b(LOWER|UPPER|SUBSTRING|CONCAT)\(", sql_upper):
            score += 10
            warnings.append("Functions in WHERE clause - may prevent index usage")
            recommendations.append("Consider using functional indexes or computed columns")

        # Cap score at 100
        score = min(score, 100)

        return QueryComplexity(
            sql=sql, score=score, warnings=warnings, recommendations=recommendations, details=details
        )

    def get_complexity_level(self, score: int) -> str:
        """Get complexity level description.

        Args:
            score: Complexity score

        Returns:
            Complexity level: "low", "medium", "high", or "very high"
        """
        if score < 20:
            return "low"
        elif score < 40:
            return "medium"
        elif score < 70:
            return "high"
        else:
            return "very high"


# Public API
__all__ = [
    "QueryComplexity",
    "QueryAnalyzer",
]
