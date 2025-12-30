"""Select statement construction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Union, TYPE_CHECKING
from chorm.sql.explain import Explain

from chorm.sql.expression import (
    Expression,
    Identifier,
    Subquery,
    ScalarSubquery,
    CTE,
    Window,
    _coerce,
    WindowFunction,
    BinaryExpression,
    UnaryExpression,
    FunctionCall,
    Label,
)
from chorm.exceptions import QueryValidationError


def _has_window_function(expr: Any) -> bool:
    """Check if expression contains a window function."""
    if isinstance(expr, WindowFunction):
        return True
    if isinstance(expr, BinaryExpression):
        return _has_window_function(expr.left) or _has_window_function(expr.right)
    if isinstance(expr, UnaryExpression):
        return _has_window_function(expr.operand)
    if isinstance(expr, FunctionCall):
        return any(_has_window_function(arg) for arg in expr.args)
    if isinstance(expr, Label):
        return _has_window_function(expr.expression)
    return False


@dataclass(frozen=True)
class JoinClause:
    """Represents a JOIN clause."""

    join_type: str  # "INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL JOIN", "CROSS JOIN"
    target: Expression  # Table or expression to join
    on_condition: Optional[Expression] = None  # ON condition
    using_columns: Optional[List[str]] = None  # USING columns

    def to_sql(self, compiler: Any = None) -> str:
        """Render the JOIN clause to SQL."""
        parts = [self.join_type, self.target.to_sql(compiler)]

        if self.on_condition is not None:
            parts.append(f"ON {self.on_condition.to_sql(compiler)}")
        elif self.using_columns:
            columns_str = ", ".join(self.using_columns)
            parts.append(f"USING ({columns_str})")

        return " ".join(parts)


@dataclass(frozen=True)
class ArrayJoinClause:
    """Represents an ARRAY JOIN clause."""

    target: Union[Expression, List[Expression]]
    left: bool = False  # If True, renders as LEFT ARRAY JOIN

    def to_sql(self, compiler: Any = None) -> str:
        """Render the ARRAY JOIN clause to SQL."""
        join_type = "LEFT ARRAY JOIN" if self.left else "ARRAY JOIN"

        if isinstance(self.target, list):
            # Multiple arrays: ARRAY JOIN [arr1, arr2] or just ARRAY JOIN arr1, arr2
            # ClickHouse syntax: ARRAY JOIN arr1, arr2
            targets = ", ".join(t.to_sql(compiler) for t in self.target)
            return f"{join_type} {targets}"
        else:
            return f"{join_type} {self.target.to_sql(compiler)}"


@dataclass(frozen=True)
class LimitByClause(Expression):
    """Represents a LIMIT BY clause."""

    limit: int
    by: List[Expression]
    offset: Optional[int] = None

    def to_sql(self, compiler: Any = None) -> str:
        parts = [f"LIMIT {self.limit}"]
        if self.offset is not None:
            parts.append(f"OFFSET {self.offset}")
        parts.append(f"BY {', '.join(e.to_sql(compiler) for e in self.by)}")
        return " ".join(parts)


class Select(Expression):
    """Represents a SELECT statement."""

    def __init__(self, *columns: Any) -> None:
        self._columns: List[Expression] = []
        for c in columns:
            if hasattr(c, "__tablename__") and hasattr(c, "__table__") and hasattr(c.__table__, "columns"):
                 # Handle Table class: expand to all columns
                 for col_info in c.__table__.columns:
                     self._columns.append(col_info.column)
            else:
                 self._columns.append(_coerce(c))
        self._from: Optional[Expression] = None
        self._joins: List[Union[JoinClause, ArrayJoinClause]] = []
        self._where_criteria: List[Expression] = []
        self._prewhere_criteria: List[Expression] = []
        self._order_by_criteria: List[Expression] = []
        self._group_by_criteria: List[Expression] = []
        self._having_criteria: List[Expression] = []
        self._limit: Optional[int] = None
        self._limit_by: Optional[LimitByClause] = None
        self._offset: Optional[int] = None
        self._final: bool = False
        self._with_totals: bool = False
        self._sample: Optional[Expression] = None
        self._settings: Dict[str, Any] = {}
        self._distinct: bool = False
        self._union_queries: List[tuple[str, "Select"]] = []  # List of ("UNION" | "UNION ALL", query)
        self._ctes: List[CTE] = []  # List of CTEs for WITH clause

    def distinct(self) -> Select:
        """Apply DISTINCT to the result set."""
        self._distinct = True
        return self

    def select_from(self, from_obj: Any) -> Select:
        """Explicitly set the FROM clause."""
        if hasattr(from_obj, "__table__") and hasattr(from_obj.__table__, "qualified_name"):
            # Handle declarative Table classes with optional database
            self._from = Identifier(from_obj.__table__.qualified_name)
        elif hasattr(from_obj, "__tablename__"):
            # Fallback for older code without __table__
            self._from = Identifier(from_obj.__tablename__)
        elif isinstance(from_obj, str):
            self._from = Identifier(from_obj)
        else:
            self._from = _coerce(from_obj)
        return self

    def _add_join(
        self,
        join_type: str,
        target: Any,
        on: Optional[Any] = None,
        using: Optional[List[str]] = None,
    ) -> Select:
        """Internal method to add a JOIN clause."""
        # Validate parameters
        if on is None and using is None and join_type != "CROSS JOIN":
            raise ValueError("Either 'on' or 'using' must be provided for JOIN (except CROSS JOIN)")
        if on is not None and using is not None:
            raise ValueError("Cannot specify both 'on' and 'using' for JOIN")
        if join_type == "CROSS JOIN" and (on is not None or using is not None):
            raise ValueError("CROSS JOIN does not accept 'on' or 'using' parameters")

        # Convert target to Expression
        if hasattr(target, "__table__") and hasattr(target.__table__, "qualified_name"):
            target_expr = Identifier(target.__table__.qualified_name)
        elif hasattr(target, "__tablename__"):
            target_expr = Identifier(target.__tablename__)
        elif isinstance(target, str):
            target_expr = Identifier(target)
        else:
            target_expr = _coerce(target)

        # Convert on condition to Expression if provided
        on_expr = _coerce(on) if on is not None else None

        # Create and append JoinClause
        join_clause = JoinClause(
            join_type=join_type,
            target=target_expr,
            on_condition=on_expr,
            using_columns=using,
        )
        self._joins.append(join_clause)
        return self

    def join(
        self,
        target: Any,
        on: Optional[Any] = None,
        using: Optional[List[str]] = None,
    ) -> Select:
        """Add an INNER JOIN clause.

        Args:
            target: Table or table name to join
            on: Join condition expression (e.g., User.id == Order.user_id)
            using: List of column names for USING clause (alternative to on)

        Returns:
            Self for method chaining

        Example:
            select(User).join(Order, on=User.id == Order.user_id)
            select(User).join(Order, using=['user_id'])
        """
        return self._add_join("INNER JOIN", target, on=on, using=using)

    def left_join(
        self,
        target: Any,
        on: Optional[Any] = None,
        using: Optional[List[str]] = None,
    ) -> Select:
        """Add a LEFT OUTER JOIN clause.

        Args:
            target: Table or table name to join
            on: Join condition expression
            using: List of column names for USING clause

        Returns:
            Self for method chaining
        """
        return self._add_join("LEFT JOIN", target, on=on, using=using)

    def right_join(
        self,
        target: Any,
        on: Optional[Any] = None,
        using: Optional[List[str]] = None,
    ) -> Select:
        """Add a RIGHT OUTER JOIN clause.

        Args:
            target: Table or table name to join
            on: Join condition expression
            using: List of column names for USING clause

        Returns:
            Self for method chaining
        """
        return self._add_join("RIGHT JOIN", target, on=on, using=using)

    def full_join(
        self,
        target: Any,
        on: Optional[Any] = None,
        using: Optional[List[str]] = None,
    ) -> Select:
        """Add a FULL OUTER JOIN clause.

        Args:
            target: Table or table name to join
            on: Join condition expression
            using: List of column names for USING clause

        Returns:
            Self for method chaining
        """
        return self._add_join("FULL JOIN", target, on=on, using=using)

    def cross_join(self, target: Any) -> Select:
        """Add a CROSS JOIN clause.

        Args:
            target: Table or table name to join

        Returns:
            Self for method chaining

        Example:
            select(User).cross_join(Order)
        """
        return self._add_join("CROSS JOIN", target)

    def array_join(self, *targets: Any) -> Select:
        """Add an ARRAY JOIN clause.

        Args:
            *targets: Arrays to join. Can be column expressions or aliases.

        Returns:
            Self for method chaining

        Example:
            select(User.name, Identifier("tag")).select_from(User).array_join(User.tags.alias("tag"))
        """
        coerced_targets = [_coerce(t) for t in targets]
        if not coerced_targets:
            raise ValueError("ARRAY JOIN requires at least one target")

        if len(coerced_targets) == 1:
            self._joins.append(ArrayJoinClause(coerced_targets[0], left=False))
        else:
            self._joins.append(ArrayJoinClause(coerced_targets, left=False))
        return self

    def left_array_join(self, *targets: Any) -> Select:
        """Add a LEFT ARRAY JOIN clause.

        Args:
            *targets: Arrays to join.

        Returns:
            Self for method chaining
        """
        coerced_targets = [_coerce(t) for t in targets]
        if not coerced_targets:
            raise ValueError("ARRAY JOIN requires at least one target")

        if len(coerced_targets) == 1:
            self._joins.append(ArrayJoinClause(coerced_targets[0], left=True))
        else:
            self._joins.append(ArrayJoinClause(coerced_targets, left=True))
        return self

    def asof_join(
        self,
        target: Any,
        on: Optional[Any] = None,
        using: Optional[List[str]] = None,
        type: str = "ASOF LEFT JOIN",
    ) -> Select:
        """Add an ASOF JOIN clause (time-series join).

        Args:
            target: Table or table name to join
            on: Join condition expression (must include time inequality)
            using: List of column names for USING clause
            type: Join type (default "ASOF LEFT JOIN")

        Returns:
            Self for method chaining
        """
        return self._add_join(type, target, on=on, using=using)

    def where(self, *criteria: Any) -> Select:
        """Add WHERE criteria."""
        for criterion in criteria:
            self._where_criteria.append(_coerce(criterion))
        return self

    def prewhere(self, *criteria: Any) -> Select:
        """Add PREWHERE criteria (ClickHouse specific)."""
        for criterion in criteria:
            self._prewhere_criteria.append(_coerce(criterion))
        return self

    def order_by(self, *criteria: Any) -> Select:
        """Add ORDER BY criteria."""
        for criterion in criteria:
            self._order_by_criteria.append(_coerce(criterion))
        return self

    def group_by(self, *criteria: Any) -> Select:
        """Add GROUP BY criteria."""
        for criterion in criteria:
            self._group_by_criteria.append(_coerce(criterion))
        return self

    def having(self, *criteria: Any) -> Select:
        """Add HAVING criteria."""
        for criterion in criteria:
            self._having_criteria.append(_coerce(criterion))
        return self

    def limit(self, limit: int, offset: Optional[int] = None) -> Select:
        """Add LIMIT and optional OFFSET."""
        self._limit = limit
        self._offset = offset
        return self

    def limit_by(self, limit: int, *by: Any, offset: Optional[int] = None) -> Select:
        """Add a LIMIT BY clause (ClickHouse specific).

        Args:
            limit: Number of rows to limit per group
            *by: Expressions to group by for the limit
            offset: Optional offset within the group

        Example:
            select(User).limit_by(5, User.city)  # Top 5 users per city
        """
        self._limit_by = LimitByClause(limit, [_coerce(b) for b in by], offset)
        return self

    def offset(self, offset: int) -> Select:
        """Add an OFFSET clause."""
        self._offset = offset
        return self

    def final(self) -> Select:
        """Add FINAL modifier (ClickHouse specific)."""
        self._final = True
        return self

    def with_totals(self) -> Select:
        """Add WITH TOTALS modifier (ClickHouse specific).

        Calculates totals for all columns in the SELECT list.
        Usually used with GROUP BY.
        """
        self._with_totals = True
        return self

    def sample(self, sample: Any) -> Select:
        """Add SAMPLE clause (ClickHouse specific)."""
        self._sample = _coerce(sample)
        return self

    def settings(self, **kwargs: Any) -> Select:
        """Add SETTINGS clause."""
        self._settings.update(kwargs)
        return self

    def union(self, other: "Select") -> Select:
        """Combine this query with another using UNION (removes duplicates).

        Args:
            other: Another Select statement to union with

        Returns:
            Self for method chaining

        Example:
            query1 = select(User.name).where(User.city == "Moscow")
            query2 = select(User.name).where(User.city == "SPB")
            query1.union(query2)
        """
        self._union_queries.append(("UNION", other))
        return self

    def union_all(self, other: "Select") -> Select:
        """Combine this query with another using UNION ALL (keeps duplicates).

        Args:
            other: Another Select statement to union with

        Returns:
            Self for method chaining

        Example:
            query1 = select(User.name).where(User.city == "Moscow")
            query2 = select(User.name).where(User.city == "SPB")
            query1.union_all(query2)
        """
        self._union_queries.append(("UNION ALL", other))
        return self

    def intersect(self, other: "Select") -> Select:
        """Combine this query with another using INTERSECT.

        Args:
            other: Another Select statement to intersect with

        Returns:
            Self for method chaining
        """
        self._union_queries.append(("INTERSECT", other))
        return self

    def except_(self, other: "Select") -> Select:
        """Combine this query with another using EXCEPT.

        Args:
            other: Another Select statement to except with

        Returns:
            Self for method chaining
        """
        self._union_queries.append(("EXCEPT", other))
        return self

    def subquery(self, name: Optional[str] = None) -> Subquery:
        """Create a subquery from this SELECT statement.

        Args:
            name: Optional alias for the subquery

        Returns:
            Subquery expression
        """
        return Subquery(self, name)

    def scalar_subquery(self) -> ScalarSubquery:
        """Create a scalar subquery from this SELECT statement.

        Returns:
            ScalarSubquery expression
        """
        return ScalarSubquery(self)

    def cte(self, name: str) -> CTE:
        """Create a Common Table Expression (CTE) from this SELECT statement.

        Args:
            name: Name for the CTE

        Returns:
            CTE expression

        Example:
            cte = select(User.id, User.name).where(User.city == "Moscow").cte("moscow_users")
            stmt = select(Identifier("*")).select_from(cte).with_cte(cte)
        """
        return CTE(name, self)

    def with_cte(self, *ctes: CTE) -> Select:
        """Attach one or more CTEs to this query for use in WITH clause.

        Args:
            *ctes: One or more CTE expressions to attach

        Returns:
            Self for method chaining

        Example:
            cte = select(User).where(User.active == True).cte("active_users")
            stmt = select(Identifier("*")).select_from(Identifier("active_users")).with_cte(cte)
        """
        self._ctes.extend(ctes)
        return self

    def _validate_query(self) -> None:
        """Validate query structure before SQL generation.

        Raises:
            QueryValidationError: If query violates ClickHouse rules
        """
        # HAVING without GROUP BY
        if self._having_criteria and not self._group_by_criteria:
            raise QueryValidationError(
                "HAVING clause requires GROUP BY", hint="Add .group_by() before .having(), or remove .having()"
            )

        # Window functions in WHERE/PREWHERE/GROUP BY/HAVING
        for criterion in self._where_criteria:
            if _has_window_function(criterion):
                raise QueryValidationError(
                    "Window functions are not allowed in WHERE clause",
                    hint="Use a subquery or CTE to filter by window function result",
                )

        for criterion in self._prewhere_criteria:
            if _has_window_function(criterion):
                raise QueryValidationError(
                    "Window functions are not allowed in PREWHERE clause",
                    hint="Use a subquery or CTE to filter by window function result",
                )

        for criterion in self._group_by_criteria:
            if _has_window_function(criterion):
                raise QueryValidationError(
                    "Window functions are not allowed in GROUP BY clause",
                    hint="Group by the underlying columns instead",
                )

        for criterion in self._having_criteria:
            if _has_window_function(criterion):
                raise QueryValidationError(
                    "Window functions are not allowed in HAVING clause",
                    hint="Use a subquery or CTE to filter by window function result",
                )

    def to_sql(self, compiler: Any = None) -> str:
        """Render the SELECT statement to SQL.
        
        Args:
            compiler: Optional Compiler instance to collect parameters.
        """
        # Validate query before generating SQL
        self._validate_query()

        parts = []

        # Render WITH clause if CTEs exist
        if self._ctes:
            cte_parts = ", ".join(cte.to_sql(compiler) for cte in self._ctes)
            parts.append(f"WITH {cte_parts}")

        parts.append("SELECT")

        if self._distinct:
            parts.append("DISTINCT")

        if not self._columns:
            parts.append("*")
        else:
            parts.append(", ".join(c.to_sql(compiler) for c in self._columns))

        if self._from:
            parts.append(f"FROM {self._from.to_sql(compiler)}")

        # Render JOIN and ARRAY JOIN clauses in order
        for join_clause in self._joins:
            parts.append(join_clause.to_sql(compiler))

        if self._final:
            parts.append("FINAL")

        if self._sample:
            parts.append(f"SAMPLE {self._sample.to_sql(compiler)}")

        if self._prewhere_criteria:
            criteria = " AND ".join(c.to_sql(compiler) for c in self._prewhere_criteria)
            parts.append(f"PREWHERE {criteria}")

        if self._where_criteria:
            criteria = " AND ".join(c.to_sql(compiler) for c in self._where_criteria)
            parts.append(f"WHERE {criteria}")

        if self._group_by_criteria:
            criteria = ", ".join(c.to_sql(compiler) for c in self._group_by_criteria)
            parts.append(f"GROUP BY {criteria}")

        if self._with_totals:
            parts.append("WITH TOTALS")

        if self._having_criteria:
            criteria = " AND ".join(c.to_sql(compiler) for c in self._having_criteria)
            parts.append(f"HAVING {criteria}")

        if self._order_by_criteria:
            criteria = ", ".join(c.to_sql(compiler) for c in self._order_by_criteria)
            parts.append(f"ORDER BY {criteria}")

        if self._limit is not None:
            parts.append(f"LIMIT {self._limit}")

        if self._limit_by is not None:
            # LimitByClause now accepts compiler
            parts.append(self._limit_by.to_sql(compiler))

        if self._offset is not None:
            parts.append(f"OFFSET {self._offset}")

        if self._settings:
            settings_list = []
            for k, v in self._settings.items():
                val_str = str(v)
                if isinstance(v, str):
                    val_str = f"'{v}'"
                settings_list.append(f"{k}={val_str}")
            parts.append(f"SETTINGS {', '.join(settings_list)}")

        # Build the base query
        base_query = " ".join(parts)

        # Append UNION queries
        if self._union_queries:
            union_parts = [base_query]
            for union_type, query in self._union_queries:
                union_parts.append(union_type)
                union_parts.append(query.to_sql(compiler))
            return " ".join(union_parts)

        return base_query

    def explain(self, explain_type: str = "AST", **settings: Any) -> "Explain":
        """Create an EXPLAIN statement for this query.

        Args:
            explain_type: Type of explanation (AST, SYNTAX, PLAN, PIPELINE, ESTIMATE, TABLE OVERRIDE)
            **settings: Settings for the EXPLAIN clause

        Returns:
            Explain expression
        """

        return Explain(self, explain_type=explain_type, settings=settings)

    def analyze(self, **settings: Any) -> "Explain":
        """Create an EXPLAIN PIPELINE statement for this query (profiling).

        Args:
            **settings: Settings for the EXPLAIN clause

        Returns:
            Explain expression with type='PIPELINE'
        """
        return self.explain(explain_type="PIPELINE", **settings)


def select(*columns: Any) -> Select:
    """Create a new Select statement."""
    # Auto-detect FROM clause if a Table class is passed as the first argument
    # and it's the only argument, or if we want to support select(User) -> SELECT * FROM user

    # For now, simple implementation:
    # If the first argument is a Table class (has __tablename__), use it as FROM
    # and select * (or columns if specified).

    # Actually, SQLAlchemy behavior: select(User) -> SELECT user.id, user.name FROM user
    # We need to inspect the columns.

    # If columns contains a Table class, we should expand it to its columns?
    # Or just let the user handle it?

    # Let's stick to explicit columns for now, but if a Table is passed, we treat it as "all columns of table"
    # AND set the FROM clause.

    # But wait, I can't import Table here.
    # I'll check for __tablename__ and __table__ attributes.

    expanded_columns = []
    from_obj = None

    for col in columns:
        if hasattr(col, "__tablename__") and hasattr(col, "__table__"):
            # It's a Table class
            if from_obj is None:
                from_obj = col
            # Expand to columns
            # We need to access the columns from the Table metadata
            # This requires the Table to be fully initialized.
            # Since we can't import Table, we rely on the object structure.
            if hasattr(col, "__table__"):
                # Assuming __table__ is TableMetadata
                # We can't easily iterate columns without importing ColumnInfo?
                # Actually, we can just use "*" for now if we select the whole table.
                # But SQLAlchemy expands it.
                pass
            expanded_columns.append(col)  # We'll handle Table in _coerce or Select logic?
        else:
            expanded_columns.append(col)

    # Refined logic:
    # If we pass a Table class to Select, we probably want to select from it.
    # But Select constructor takes *columns.
    # Let's just pass everything to Select constructor and let the user call select_from if needed,
    # OR we can try to be smart.

    # Let's keep it simple: select(User) -> Select(User).
    # Inside Select, we might need to handle Table objects in _columns.

    stmt = Select(*columns)

    # Attempt to infer FROM
    if len(columns) > 0:
        first = columns[0]
        if hasattr(first, "__tablename__"):
            stmt.select_from(first)
        elif hasattr(first, "table") and hasattr(first.table, "__tablename__"):
            stmt.select_from(first.table)

    return stmt


def cte(stmt, name):
    """Create a CTE (Common Table Expression) from a SELECT statement.

    Args:
        stmt: SELECT statement to use as CTE
        name: Name for the CTE

    Returns:
        CTE object that can be used with .with_cte()
    """
    return stmt.cte(name)


def window(
    partition_by: Union[Expression, List[Expression], None] = None,
    order_by: Union[Expression, List[Expression], None] = None,
    frame: Optional[str] = None,
) -> "Window":
    """Create a window specification for window functions.

    Args:
        partition_by: Expression or list of expressions to partition by
        order_by: Expression or list of expressions to order by
        frame: Window frame specification (e.g., "ROWS BETWEEN 1 PRECEDING AND CURRENT ROW")

    Returns:
        Window object that can be used with .over()

    Example:
        from chorm import select, func, window
        from models import Order

        # Create a window partitioned by user_id, ordered by created_at
        w = window(partition_by=[Order.user_id], order_by=[Order.created_at])

        # Use the window with a function
        query = select(
            Order.id,
            Order.user_id,
            Order.amount,
            func.row_number().over(w).label('order_number'),
            func.sum(Order.amount).over(w).label('running_total')
        )
    """

    # Convert partition_by to list
    partition_list = []
    if partition_by:
        if isinstance(partition_by, (list, tuple)):
            partition_list = [_coerce(p) for p in partition_by]
        else:
            partition_list = [_coerce(partition_by)]

    # Convert order_by to list
    order_list = []
    if order_by:
        if isinstance(order_by, (list, tuple)):
            order_list = [_coerce(o) for o in order_by]
        else:
            order_list = [_coerce(order_by)]

    return Window(partition_by=partition_list, order_by=order_list, frame=frame)
