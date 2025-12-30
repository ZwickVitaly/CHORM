"""SQL expression primitives and operator overloading."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Tuple, Union, Optional, List


class Expression:
    """Base class for all SQL expressions."""

    def to_sql(self, compiler: Any = None) -> str:
        """Render the expression as a SQL string.
        
        Args:
            compiler: Optional Compiler instance to collect parameters.
        """
        raise NotImplementedError

    def __str__(self) -> str:
        return self.to_sql()

    def __eq__(self, other: Any) -> BinaryExpression:  # type: ignore[override]
        return BinaryExpression(self, "=", _coerce(other))

    def __ne__(self, other: Any) -> BinaryExpression:  # type: ignore[override]
        return BinaryExpression(self, "!=", _coerce(other))

    def __gt__(self, other: Any) -> BinaryExpression:
        return BinaryExpression(self, ">", _coerce(other))

    def __ge__(self, other: Any) -> BinaryExpression:
        return BinaryExpression(self, ">=", _coerce(other))

    def __lt__(self, other: Any) -> BinaryExpression:
        return BinaryExpression(self, "<", _coerce(other))

    def __le__(self, other: Any) -> BinaryExpression:
        return BinaryExpression(self, "<=", _coerce(other))

    def __and__(self, other: Any) -> BinaryExpression:
        return BinaryExpression(self, "AND", _coerce(other))

    def __or__(self, other: Any) -> BinaryExpression:
        return BinaryExpression(self, "OR", _coerce(other))

    def __invert__(self) -> UnaryExpression:
        return UnaryExpression("NOT", self)

    def __add__(self, other: Any) -> BinaryExpression:
        return BinaryExpression(self, "+", _coerce(other))

    def __sub__(self, other: Any) -> BinaryExpression:
        return BinaryExpression(self, "-", _coerce(other))

    def __mul__(self, other: Any) -> BinaryExpression:
        return BinaryExpression(self, "*", _coerce(other))

    def __truediv__(self, other: Any) -> BinaryExpression:
        return BinaryExpression(self, "/", _coerce(other))

    def in_(self, other: Any) -> BinaryExpression:
        return BinaryExpression(self, "IN", _coerce(other))

    def not_in(self, other: Any) -> BinaryExpression:
        return BinaryExpression(self, "NOT IN", _coerce(other))

    def like(self, other: Any) -> BinaryExpression:
        return BinaryExpression(self, "LIKE", _coerce(other))

    def ilike(self, other: Any) -> BinaryExpression:
        return BinaryExpression(self, "ILIKE", _coerce(other))

    def is_(self, other: Any) -> BinaryExpression:
        return BinaryExpression(self, "IS", _coerce(other))

    def is_not(self, other: Any) -> BinaryExpression:
        return BinaryExpression(self, "IS NOT", _coerce(other))

    def label(self, name: str) -> Label:
        return Label(name, self)

    def asc(self) -> "OrderByClause":
        """Return an ascending ORDER BY clause for this expression.

        Example:
            select(User).order_by(User.name.asc())
        """
        return OrderByClause(self, "ASC")

    def desc(self) -> "OrderByClause":
        """Return a descending ORDER BY clause for this expression.

        Example:
            select(User).order_by(User.created_at.desc())
        """
        return OrderByClause(self, "DESC")


@dataclass(frozen=True)
class BinaryExpression(Expression):
    left: Expression
    operator: str
    right: Expression

    def to_sql(self, compiler: Any = None) -> str:
        return f"({self.left.to_sql(compiler)} {self.operator} {self.right.to_sql(compiler)})"


@dataclass(frozen=True)
class UnaryExpression(Expression):
    operator: str
    operand: Expression

    def to_sql(self, compiler: Any = None) -> str:
        return f"{self.operator} ({self.operand.to_sql(compiler)})"


@dataclass(frozen=True, eq=False)
class Identifier(Expression):
    name: str

    def to_sql(self, compiler: Any = None) -> str:
        return self.name


from chorm.utils import escape_string

@dataclass(frozen=True)
class Literal(Expression):
    value: Any

    def to_sql(self, compiler: Any = None) -> str:
        if compiler is not None:
            return compiler.add_param(self.value)
            
        if isinstance(self.value, str):
            return f"'{escape_string(self.value)}'"
        if self.value is None:
            return "NULL"
        if isinstance(self.value, bool):
            return "1" if self.value else "0"
        if isinstance(self.value, (date, datetime)):
            return f"'{self.value}'"
        return str(self.value)


@dataclass(frozen=True)
class Raw(Expression):
    sql: str

    def to_sql(self, compiler: Any = None) -> str:
        return self.sql


def text(sql: str) -> Raw:
    """Create a raw SQL expression.
    
    Example:
        select(text("count(*) as c")).select_from(text("users"))
    """
    return Raw(sql)


@dataclass(frozen=True)
class FunctionCall(Expression):
    name: str
    args: Tuple[Expression, ...]

    def to_sql(self, compiler: Any = None) -> str:
        rendered = ", ".join(arg.to_sql(compiler) for arg in self.args)
        return f"{self.name}({rendered})"

    def __call__(self, *args: Any) -> "FunctionCall":
        """Allow function calls to be parameterized (curried).
        
        This enables syntax like quantileState(0.5)(value) for parameterized functions.
        """
        coerced_args = tuple(_coerce(arg) for arg in args)
        return FunctionCall(self.name, self.args + coerced_args)

    def over(
        self,
        partition_by: Union[Expression, List[Expression], None] = None,
        order_by: Union[Expression, List[Expression], None] = None,
        frame: Optional[str] = None,
    ) -> "WindowFunction":
        """Create a window function expression.

        Args:
            partition_by: Expression or list of expressions to partition by
            order_by: Expression or list of expressions to order by
            frame: Window frame specification (e.g. "ROWS BETWEEN 1 PRECEDING AND CURRENT ROW")

        Returns:
            WindowFunction expression
        """
        partition_list = []
        if partition_by:
            if isinstance(partition_by, (list, tuple)):
                partition_list = [_coerce(p) for p in partition_by]
            else:
                partition_list = [_coerce(partition_by)]

        order_list = []
        if order_by:
            if isinstance(order_by, (list, tuple)):
                order_list = [_coerce(p) for p in order_by]
            else:
                order_list = [_coerce(order_by)]

        window = Window(partition_by=partition_list, order_by=order_list, frame=frame)
        return WindowFunction(self, window)


@dataclass(frozen=True)
class ParameterizedFunctionCall(Expression):
    """Represents a parameterized function call like quantileState(0.5)(value).
    
    In ClickHouse, some functions like quantileState are parameterized:
    - quantileState(0.5) returns a function that takes a value
    - quantileState(0.5)(value) is the full call
    """
    name: str
    params: Tuple[Expression, ...]
    args: Tuple[Expression, ...]

    def to_sql(self, compiler: Any = None) -> str:
        params_rendered = ", ".join(param.to_sql(compiler) for param in self.params)
        args_rendered = ", ".join(arg.to_sql(compiler) for arg in self.args)
        return f"{self.name}({params_rendered})({args_rendered})"

    def over(
        self,
        partition_by: Union[Expression, List[Expression], None] = None,
        order_by: Union[Expression, List[Expression], None] = None,
        frame: Optional[str] = None,
    ) -> "WindowFunction":
        """Create a window function expression.

        Args:
            partition_by: Expression or list of expressions to partition by
            order_by: Expression or list of expressions to order by
            frame: Window frame specification (e.g. "ROWS BETWEEN 1 PRECEDING AND CURRENT ROW")

        Returns:
            WindowFunction expression
        """
        partition_list = []
        if partition_by:
            if isinstance(partition_by, (list, tuple)):
                partition_list = [_coerce(p) for p in partition_by]
            else:
                partition_list = [_coerce(partition_by)]

        order_list = []
        if order_by:
            if isinstance(order_by, (list, tuple)):
                order_list = [_coerce(p) for p in order_by]
            else:
                order_list = [_coerce(order_by)]

        window = Window(partition_by=partition_list, order_by=order_list, frame=frame)
        return WindowFunction(self, window)


@dataclass(frozen=True)
class Window(Expression):
    """Represents a window specification (OVER clause)."""

    partition_by: List[Expression]
    order_by: List[Expression]
    frame: Optional[str] = None

    def to_sql(self, compiler: Any = None) -> str:
        parts = []
        if self.partition_by:
            parts.append(f"PARTITION BY {', '.join(p.to_sql(compiler) for p in self.partition_by)}")
        if self.order_by:
            parts.append(f"ORDER BY {', '.join(o.to_sql(compiler) for o in self.order_by)}")
        if self.frame:
            parts.append(self.frame)

        return f"OVER ({' '.join(parts)})"


@dataclass(frozen=True)
class WindowFunction(Expression):
    """Represents a function call with a window specification."""

    function: FunctionCall
    window: Window

    def to_sql(self, compiler: Any = None) -> str:
        return f"{self.function.to_sql(compiler)} {self.window.to_sql(compiler)}"


@dataclass(frozen=True)
class Label(Expression):
    name: str
    expression: Expression

    def to_sql(self, compiler: Any = None) -> str:
        return f"{self.expression.to_sql(compiler)} AS {self.name}"


@dataclass(frozen=True)
class OrderByClause(Expression):
    """Represents an ORDER BY clause with direction."""

    expression: Expression
    direction: str  # "ASC" or "DESC"

    def to_sql(self, compiler: Any = None) -> str:
        return f"{self.expression.to_sql(compiler)} {self.direction}"


@dataclass(frozen=True)
class Subquery(Expression):
    """Represents a subquery (SELECT statement in parentheses)."""

    select: Expression
    alias: Optional[str] = None

    @property
    def c(self) -> "ColumnNamespace":
        """Column access namespace like SQLAlchemy.

        Returns a namespace object that allows accessing columns as attributes:
        subq.c.column_name or subq.c['column_name']

        Example:
            daily = select(Order.user_id, func.sum(Order.amount).label('total')).subquery('daily')
            query = select(daily.c.user_id, daily.c.total)
        """
        return ColumnNamespace(self.alias or "subquery", self.select)

    def to_sql(self, compiler: Any = None) -> str:
        sql = f"({self.select.to_sql(compiler)})"
        if self.alias:
            sql += f" AS {self.alias}"
        return sql


@dataclass(frozen=True)
class ScalarSubquery(Expression):
    """Represents a scalar subquery (single value)."""

    select: Expression

    def to_sql(self, compiler: Any = None) -> str:
        return f"({self.select.to_sql(compiler)})"


@dataclass(frozen=True)
class CTE(Expression):
    """Represents a Common Table Expression (CTE) for use in WITH clause."""

    name: str
    select: Expression

    @property
    def c(self) -> "ColumnNamespace":
        """Column access namespace like SQLAlchemy.

        Returns a namespace object that allows accessing columns as attributes:
        cte.c.column_name or cte.c['column_name']

        Example:
            monthly = cte(select(Order.user_id, func.sum(Order.amount).label('total')), name='monthly')
            query = select(monthly.c.user_id, monthly.c.total).with_cte(monthly)
        """
        return ColumnNamespace(self.name, self.select)

    def to_sql(self, compiler: Any = None) -> str:
        """Render CTE as 'name AS (SELECT ...)'."""
        return f"{self.name} AS ({self.select.to_sql(compiler)})"


class ColumnNamespace:
    """Namespace for accessing columns from subqueries and CTEs.

    This class provides a convenient way to reference columns from subqueries
    and CTEs, similar to SQLAlchemy's approach.

    Example:
        subq = select(User.id, User.name).subquery('u')
        # Access columns via attribute
        query = select(subq.c.id, subq.c.name)
        # Or via item access
        query = select(subq.c['id'], subq.c['name'])
    """

    def __init__(self, source_name: str, stmt: Expression) -> None:
        """Initialize column namespace.

        Args:
            source_name: Name of the subquery/CTE (used as table alias in SQL)
            stmt: The SELECT statement to extract columns from
        """
        self._source_name = source_name
        self._stmt = stmt
        self._columns: dict[str, Identifier] = {}
        self._build_columns()

    def _build_columns(self) -> None:
        """Extract column names from SELECT statement."""
        # Check if statement has _columns attribute (Select objects)
        if not hasattr(self._stmt, "_columns"):
            return

        for col in self._stmt._columns:
            col_name = None

            if isinstance(col, Label):
                # Labeled column: use the label name
                col_name = col.name
            elif hasattr(col, "name"):
                # Column object: use its name
                col_name = col.name
            elif hasattr(col, "__name__"):
                # Function or other named object
                col_name = col.__name__

            if col_name:
                # Create an Identifier for this column
                self._columns[col_name] = Identifier(f"{self._source_name}.{col_name}")

    def __getattr__(self, name: str) -> Identifier:
        """Access column by attribute: subq.c.column_name

        Args:
            name: Column name

        Returns:
            Identifier expression for the column

        Raises:
            AttributeError: If name starts with underscore (reserved for internal use)
        """
        if name.startswith("_"):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

        # Return known column if exists
        if name in self._columns:
            return self._columns[name]

        # Allow dynamic column access even if not in SELECT
        # (useful for SELECT * scenarios or when column tracking is incomplete)
        return Identifier(f"{self._source_name}.{name}")

    def __getitem__(self, name: str) -> Identifier:
        """Access column by key: subq.c['column_name']

        Args:
            name: Column name

        Returns:
            Identifier expression for the column
        """
        return self.__getattr__(name)

    def __contains__(self, name: str) -> bool:
        """Check if column exists: 'column_name' in subq.c

        Args:
            name: Column name to check

        Returns:
            True if column was explicitly selected in the statement
        """
        return name in self._columns

    def keys(self) -> list[str]:
        """Return list of known column names.

        Returns:
            List of column names that were explicitly selected
        """
        return list(self._columns.keys())


def _coerce(value: Any) -> Expression:
    """Coerce a value to an Expression for use in operators/comparisons."""
    if isinstance(value, Expression):
        return value
    if isinstance(value, str):
        # In comparisons, strings are literals
        return Literal(value)
    return Literal(value)


def _coerce_func_arg(value: Any) -> Expression:
    """Coerce a value to an Expression for use as a function argument."""
    if isinstance(value, Expression):
        return value
    if isinstance(value, str):
        # In function calls, bare strings are identifiers (column names)
        return Identifier(value)
    # Numbers and other values are literals
    return Literal(value)


class FunctionNamespace:
    """Namespace that produces :class:`FunctionCall` expressions."""

    def __getattr__(self, item: str) -> "_FunctionFactory":
        return _FunctionFactory(item)

    def __call__(self, name: str) -> "_FunctionFactory":
        return _FunctionFactory(name)


class _FunctionFactory:
    def __init__(self, name: str) -> None:
        self.name = name

    def __call__(self, *args: Any) -> FunctionCall:
        coerced = tuple(_coerce_func_arg(arg) for arg in args)
        return FunctionCall(self.name, coerced)


func = FunctionNamespace()


# Convenience wrappers
def cast(expression: Any, type_: str) -> FunctionCall:
    return func.cast(expression, Raw(f"'{type_}'"))


def distinct(expression: Any) -> FunctionCall:
    return func.distinct(expression)


def sum_(value: Any) -> FunctionCall:
    return func.sum(value)


def avg(value: Any) -> FunctionCall:
    return func.avg(value)


def min_(value: Any) -> FunctionCall:
    return func.min(value)


def max_(value: Any) -> FunctionCall:
    return func.max(value)


def count(value: Any | None = None) -> FunctionCall:
    if value is None:
        return func.count()
    return func.count(value)


def count_distinct(value: Any) -> FunctionCall:
    return func.countDistinct(value)


def lower(value: Any) -> FunctionCall:
    return func.lower(value)


def lower_utf8(value: Any) -> FunctionCall:
    return func.lowerUTF8(value)


def upper(value: Any) -> FunctionCall:
    return func.upper(value)


def upper_utf8(value: Any) -> FunctionCall:
    return func.upperUTF8(value)


def coalesce(*args: Any) -> FunctionCall:
    return func.coalesce(*args)


def if_null(expr: Any, default: Any) -> FunctionCall:
    return func.ifNull(expr, default)


def null_if(expr: Any, null_value: Any) -> FunctionCall:
    return func.nullIf(expr, null_value)


def to_date(value: Any) -> FunctionCall:
    return func.toDate(value)


def to_datetime(value: Any, timezone: Any | None = None) -> FunctionCall:
    if timezone is not None:
        return func.toDateTime(value, timezone if isinstance(timezone, Expression) else Literal(timezone))
    return func.toDateTime(value)


def to_decimal32(value: Any, scale: Any) -> FunctionCall:
    return func.toDecimal32(value, scale)


def to_decimal64(value: Any, scale: Any) -> FunctionCall:
    return func.toDecimal64(value, scale)


def exists(select: Expression) -> FunctionCall:
    """Create an EXISTS clause."""
    return func.exists(select)


def row_number() -> FunctionCall:
    return func.row_number()


def rank() -> FunctionCall:
    return func.rank()


def dense_rank() -> FunctionCall:
    return func.dense_rank()


def lag(expr: Any, offset: Any = 1, default: Any = None) -> FunctionCall:
    args = [expr, offset]
    if default is not None:
        args.append(default)
    return func.lag(*args)


def lead(expr: Any, offset: Any = 1, default: Any = None) -> FunctionCall:
    args = [expr, offset]
    if default is not None:
        args.append(default)
    return func.lead(*args)


def multi_if(*args: Any) -> FunctionCall:
    """ClickHouse multiIf function (CASE WHEN equivalent).

    Args:
        *args: Pairs of (condition, result), optionally followed by an else result.
               multiIf(cond1, val1, cond2, val2, ..., else_val)

    Example:
        multi_if(
            User.age < 18, 'minor',
            User.age < 65, 'adult',
            'senior'
        )
    """
    return func.multiIf(*args)


def if_(condition: Any, then_: Any, else_: Any) -> FunctionCall:
    """ClickHouse if() function (ternary operator).

    Args:
        condition: Boolean condition
        then_: Result if true
        else_: Result if false

    Example:
        if_(User.age >= 18, 'adult', 'minor')
    """
    return func("if")(condition, then_, else_)


# ClickHouse-specific aggregation functions
def uniq(*args: Any) -> FunctionCall:
    """Approximate COUNT DISTINCT using HyperLogLog.

    Example:
        select(func.uniq(User.id)).select_from(User)
    """
    return func.uniq(*args)


def uniq_exact(*args: Any) -> FunctionCall:
    """Exact COUNT DISTINCT.

    Example:
        select(func.uniqExact(User.id)).select_from(User)
    """
    return func.uniqExact(*args)


def quantile(level: Any, expr: Any) -> FunctionCall:
    """Calculate quantile (percentile).

    Args:
        level: Quantile level (0.0 to 1.0), e.g., 0.5 for median, 0.95 for 95th percentile
        expr: Expression to calculate quantile for

    Example:
        select(func.quantile(0.95, Order.amount)).select_from(Order)
    """
    return func.quantile(level, expr)


def quantiles(levels: Any, expr: Any) -> FunctionCall:
    """Calculate multiple quantiles.

    Args:
        levels: Array of quantile levels
        expr: Expression to calculate quantiles for

    Example:
        select(func.quantiles([0.25, 0.5, 0.75], Order.amount)).select_from(Order)
    """
    return func.quantiles(levels, expr)


def median(expr: Any) -> FunctionCall:
    """Calculate median (50th percentile).

    Example:
        select(func.median(Order.amount)).select_from(Order)
    """
    return func.median(expr)


def group_array(expr: Any, max_size: Any = None) -> FunctionCall:
    """Collect values into array.

    Args:
        expr: Expression to collect
        max_size: Optional maximum array size (Note: ClickHouse syntax varies by version)

    Example:
        select(User.city, func.groupArray(User.name)).group_by(User.city)
    """
    # Note: In ClickHouse, groupArray with max size is just groupArray(expr)
    # The max_size parameter is kept for API compatibility but not used in SQL generation
    # For limited arrays, use arraySlice(groupArray(expr), 1, max_size) in ClickHouse
    return func.groupArray(expr)


def stddev_pop(expr: Any) -> FunctionCall:
    """Population standard deviation.

    Example:
        select(func.stddevPop(Order.amount)).select_from(Order)
    """
    return func.stddevPop(expr)


def var_pop(expr: Any) -> FunctionCall:
    """Population variance.

    Example:
        select(func.varPop(Order.amount)).select_from(Order)
    """
    return func.varPop(expr)


def corr(x: Any, y: Any) -> FunctionCall:
    """Pearson correlation coefficient.

    Args:
        x: First variable
        y: Second variable

    Example:
        select(func.corr(User.age, Order.amount)).select_from(User).join(Order, ...)
    """
    return func.corr(x, y)


# Date/Time helper functions
def to_start_of_month(date: Any) -> FunctionCall:
    """Round down to start of month.

    Example:
        select(func.toStartOfMonth(Order.date), func.sum(Order.amount))
            .group_by(func.toStartOfMonth(Order.date))
    """
    return func.toStartOfMonth(date)


def to_start_of_week(date: Any, mode: Any = 0) -> FunctionCall:
    """Round down to start of week.

    Args:
        date: Date expression
        mode: Week mode (0 = Sunday, 1 = Monday, etc.)

    Example:
        select(func.toStartOfWeek(Order.date)).select_from(Order)
    """
    return func.toStartOfWeek(date, mode)


def to_start_of_day(date: Any) -> FunctionCall:
    """Round down to start of day.

    Example:
        select(func.toStartOfDay(Order.created_at)).select_from(Order)
    """
    return func.toStartOfDay(date)


def date_diff(unit: str, start: Any, end: Any) -> FunctionCall:
    """Calculate difference between dates.

    Args:
        unit: Time unit ('day', 'month', 'year', 'hour', 'minute', 'second')
        start: Start date
        end: End date

    Example:
        select(func.dateDiff('day', Order.created_at, func.now())).select_from(Order)
    """
    return func.dateDiff(Literal(unit), start, end)


def now() -> FunctionCall:
    """Current date and time.

    Example:
        select(User.name).where(User.last_login > func.now() - 86400)
    """
    return func.now()


def today() -> FunctionCall:
    """Current date.

    Example:
        select(Order).where(Order.date == func.today())
    """
    return func.today()


# String helper functions
def concat(*args: Any) -> FunctionCall:
    """Concatenate strings.

    Example:
        select(func.concat(User.first_name, ' ', User.last_name).label('full_name'))
    """
    return func.concat(*args)


def substring(s: Any, offset: Any, length: Any = None) -> FunctionCall:
    """Extract substring.

    Args:
        s: String expression
        offset: Starting position (1-indexed)
        length: Optional length to extract

    Example:
        select(func.substring(User.email, 1, 5)).select_from(User)
    """
    if length is not None:
        return func.substring(s, offset, length)
    return func.substring(s, offset)


def position(haystack: Any, needle: Any) -> FunctionCall:
    """Find position of substring.

    Args:
        haystack: String to search in
        needle: String to search for

    Example:
        select(func.position(User.email, '@')).select_from(User)
    """
    return func.position(haystack, needle)


def length(s: Any) -> FunctionCall:
    """String length.

    Example:
        select(User.name).where(func.length(User.name) > 10)
    """
    return func.length(s)


# ClickHouse conditional aggregations (-If combinator)
def sum_if(column: Any, condition: Any) -> FunctionCall:
    """Sum values where condition is true.

    Args:
        column: Column to sum
        condition: Condition expression

    Example:
        select(sumIf(Order.amount, Order.status == 'completed'))
    """
    return func.sumIf(column, condition)


def count_if(condition: Any) -> FunctionCall:
    """Count rows where condition is true.

    Args:
        condition: Condition expression

    Example:
        select(countIf(User.age >= 18).label('adults'))
    """
    return func.countIf(condition)


def avg_if(column: Any, condition: Any) -> FunctionCall:
    """Average values where condition is true.

    Args:
        column: Column to average
        condition: Condition expression

    Example:
        select(avgIf(Order.amount, User.tier == 'premium'))
    """
    return func.avgIf(column, condition)


def min_if(column: Any, condition: Any) -> FunctionCall:
    """Minimum value where condition is true.

    Args:
        column: Column to find minimum
        condition: Condition expression

    Example:
        select(minIf(Order.amount, Order.status == 'completed'))
    """
    return func.minIf(column, condition)


def max_if(column: Any, condition: Any) -> FunctionCall:
    """Maximum value where condition is true.

    Args:
        column: Column to find maximum
        condition: Condition expression

    Example:
        select(maxIf(Order.amount, Order.status == 'completed'))
    """
    return func.maxIf(column, condition)


def uniq_if(column: Any, condition: Any) -> FunctionCall:
    """Unique count where condition is true.

    Args:
        column: Column to count unique values
        condition: Condition expression

    Example:
        select(uniqIf(User.id, User.age >= 18))
    """
    return func.uniqIf(column, condition)


def group_array_if(column: Any, condition: Any) -> FunctionCall:
    """Collect values into array where condition is true.

    Args:
        column: Column to collect
        condition: Condition expression

    Example:
        select(groupArrayIf(User.name, User.active == 1))
    """
    return func.groupArrayIf(column, condition)


def median_if(column: Any, condition: Any) -> FunctionCall:
    """Median where condition is true.

    Args:
        column: Column to calculate median
        condition: Condition expression

    Example:
        select(medianIf(Order.amount, Order.status == 'completed'))
    """
    return func.medianIf(column, condition)


# ClickHouse array functions
def group_uniq_array(column: Any) -> FunctionCall:
    """Collect unique values into array.

    Args:
        column: Column to collect unique values from

    Example:
        select(User.city, groupUniqArray(User.tags)).group_by(User.city)
    """
    return func.groupUniqArray(column)


def sum_array(array_column: Any) -> FunctionCall:
    """Sum all elements in array column.

    Args:
        array_column: Array column to sum

    Example:
        select(User.id, sumArray(User.daily_amounts))
    """
    return func.arraySum(array_column)


def avg_array(array_column: Any) -> FunctionCall:
    """Average of array elements.

    Args:
        array_column: Array column to average

    Example:
        select(User.id, avgArray(User.scores))
    """
    return func.arrayAvg(array_column)


def array_concat(*arrays: Any) -> FunctionCall:
    """Concatenate arrays.

    Args:
        *arrays: Arrays to concatenate

    Example:
        select(arrayConcat(User.tags1, User.tags2))
    """
    return func.arrayConcat(*arrays)


def trim(s: Any) -> FunctionCall:
    """Trim whitespace from string.

    Example:
        select(func.trim(User.name))
    """
    return func.trim(s)


def ltrim(s: Any) -> FunctionCall:
    """Trim whitespace from left side of string.

    Example:
        select(func.ltrim(User.name))
    """
    return func.ltrim(s)


def rtrim(s: Any) -> FunctionCall:
    """Trim whitespace from right side of string.

    Example:
        select(func.rtrim(User.name))
    """
    return func.rtrim(s)


def replace(haystack: Any, needle: Any, replacement: Any) -> FunctionCall:
    """Replace all occurrences of substring.

    Args:
        haystack: String to search in
        needle: String to search for
        replacement: String to replace with

    Example:
        select(func.replace(User.bio, 'bad', 'good'))
    """
    return func.replaceAll(haystack, needle, replacement)


def split_by_char(separator: Any, s: Any) -> FunctionCall:
    """Split string by character.

    Args:
        separator: Character to split by
        s: String to split

    Example:
        select(func.splitByChar(',', User.tags_str))
    """
    return func.splitByChar(separator, s)


def to_year(date: Any) -> FunctionCall:
    """Extract year from date.

    Example:
        select(func.toYear(Order.date))
    """
    return func.toYear(date)


def to_month(date: Any) -> FunctionCall:
    """Extract month from date.

    Example:
        select(func.toMonth(Order.date))
    """
    return func.toMonth(date)


def to_day(date: Any) -> FunctionCall:
    """Extract day of month from date.

    Example:
        select(func.toDayOfMonth(Order.date))
    """
    return func.toDayOfMonth(date)


def add_days(date: Any, delta: Any) -> FunctionCall:
    """Add days to date.

    Args:
        date: Date expression
        delta: Number of days to add (can be negative)

    Example:
        select(func.addDays(Order.date, 7))
    """
    return func.addDays(date, delta)


def add_months(date: Any, delta: Any) -> FunctionCall:
    """Add months to date.

    Args:
        date: Date expression
        delta: Number of months to add

    Example:
        select(func.addMonths(Order.date, 1))
    """
    return func.addMonths(date, delta)


# Advanced aggregate functions
def top_k(k: Any, expr: Any) -> FunctionCall:
    """Top-K aggregate (most frequent values).

    Args:
        k: Number of top values to return
        expr: Expression to aggregate

    Example:
        select(topK(10, User.country)).select_from(User)
    """
    return func.topK(k, expr)


def top_k_weighted(k: Any, expr: Any, weight: Any) -> FunctionCall:
    """Top-K aggregate with weights.

    Args:
        k: Number of top values to return
        expr: Expression to aggregate
        weight: Weight expression

    Example:
        select(topKWeighted(10, Product.id, Order.quantity))
    """
    return func.topKWeighted(k, expr, weight)


def group_bitmap(expr: Any) -> FunctionCall:
    """Bitmap aggregate (for bitmap operations).

    Args:
        expr: Expression to create bitmap from

    Example:
        select(groupBitmap(User.id)).select_from(User)
    """
    return func.groupBitmap(expr)


def group_bit_and(expr: Any) -> FunctionCall:
    """Bitwise AND aggregate.

    Args:
        expr: Expression to aggregate

    Example:
        select(groupBitAnd(Permissions.flags))
    """
    return func.groupBitAnd(expr)


def group_bit_or(expr: Any) -> FunctionCall:
    """Bitwise OR aggregate.

    Args:
        expr: Expression to aggregate

    Example:
        select(groupBitOr(Permissions.flags))
    """
    return func.groupBitOr(expr)


def group_bit_xor(expr: Any) -> FunctionCall:
    """Bitwise XOR aggregate.

    Args:
        expr: Expression to aggregate

    Example:
        select(groupBitXor(Data.checksum))
    """
    return func.groupBitXor(expr)


def any_last(expr: Any) -> FunctionCall:
    """Return last encountered value (sampling aggregate).

    Args:
        expr: Expression to sample

    Example:
        select(anyLast(User.last_login)).group_by(User.country)
    """
    return func.anyLast(expr)


def any_heavy(expr: Any) -> FunctionCall:
    """Return frequently occurring value (heavy hitter).
    
    Args:
        expr: Expression to sample
        
    Example:
        select(anyHeavy(User.browser)).select_from(User)
    """
    return func.anyHeavy(expr)


def arg_max(expr: Any, value: Any) -> FunctionCall:
    """Return the value of `expr` for the row with maximum `value`.
    
    Args:
        expr: Expression to return
        value: Expression to maximize
        
    Example:
        # Get the name of the user with the latest update
        select(
            User.id,
            argMax(User.name, User.updated_at).label('name')
        ).group_by(User.id)
    """
    return func.argMax(expr, value)


def arg_min(expr: Any, value: Any) -> FunctionCall:
    """Return the value of `expr` for the row with minimum `value`.
    
    Args:
        expr: Expression to return
        value: Expression to minimize
        
    Example:
        # Get the name of the user with the earliest creation
        select(
            User.id,
            argMin(User.name, User.created_at).label('name')
        ).group_by(User.id)
    """
    return func.argMin(expr, value)


# Dictionary functions
def dict_get(dict_name: str, attr_name: str, id_expr: Any) -> FunctionCall:
    """Get attribute value from dictionary.

    Args:
        dict_name: Dictionary name
        attr_name: Attribute name to retrieve
        id_expr: Key expression

    Example:
        select(dictGet('user_dict', 'name', User.id))
    """
    from chorm.sql.expression import Literal

    return func.dictGet(Literal(dict_name), Literal(attr_name), id_expr)


def dict_get_or_default(dict_name: str, attr_name: str, id_expr: Any, default: Any) -> FunctionCall:
    """Get attribute value from dictionary with default.

    Args:
        dict_name: Dictionary name
        attr_name: Attribute name to retrieve
        id_expr: Key expression
        default: Default value if key not found

    Example:
        select(dictGetOrDefault('user_dict', 'name', User.id, 'Unknown'))
    """
    from chorm.sql.expression import Literal

    return func.dictGetOrDefault(Literal(dict_name), Literal(attr_name), id_expr, default)


def dict_has(dict_name: str, id_expr: Any) -> FunctionCall:
    """Check if key exists in dictionary.

    Args:
        dict_name: Dictionary name
        id_expr: Key expression

    Example:
        select(User).where(dictHas('user_dict', User.id))
    """
    from chorm.sql.expression import Literal

    return func.dictHas(Literal(dict_name), id_expr)


# --- AggregateFunction combinators (State and Merge) ---


def sum_state(value: Any) -> FunctionCall:
    """Create sum state for AggregateFunction(sum, ...).
    
    Used when inserting into AggregateFunction columns.
    
    Example:
        insert(Metrics).values(sum_state=sum_state(Order.amount))
    """
    return func.sumState(value)


def sum_merge(value: Any) -> FunctionCall:
    """Merge sum states and return final result.
    
    Used when selecting from AggregateFunction(sum, ...) columns.
    
    Example:
        select(sum_merge(Metrics.revenue_state)).select_from(Metrics)
    """
    return func.sumMerge(value)


def avg_state(value: Any) -> FunctionCall:
    """Create avg state for AggregateFunction(avg, ...)."""
    return func.avgState(value)


def avg_merge(value: Any) -> FunctionCall:
    """Merge avg states and return final result."""
    return func.avgMerge(value)


def count_state(value: Any | None = None) -> FunctionCall:
    """Create count state for AggregateFunction(count, ...)."""
    if value is None:
        return func.countState()
    return func.countState(value)


def count_merge(value: Any) -> FunctionCall:
    """Merge count states and return final result."""
    return func.countMerge(value)


def uniq_state(value: Any) -> FunctionCall:
    """Create uniq state for AggregateFunction(uniq, ...)."""
    return func.uniqState(value)


def uniq_merge(value: Any) -> FunctionCall:
    """Merge uniq states and return final result."""
    return func.uniqMerge(value)


def uniq_exact_state(value: Any) -> FunctionCall:
    """Create uniqExact state for AggregateFunction(uniqExact, ...)."""
    return func.uniqExactState(value)


def uniq_exact_merge(value: Any) -> FunctionCall:
    """Merge uniqExact states and return final result."""
    return func.uniqExactMerge(value)


def quantile_state(level: Any, expr: Any) -> ParameterizedFunctionCall:
    """Create quantile state for AggregateFunction(quantile(...), ...).
    
    In ClickHouse, quantileState is a parameterized function:
    quantileState(0.5)(value) - where 0.5 is the parameter and value is the argument.
    """
    from chorm.sql.expression import ParameterizedFunctionCall
    return ParameterizedFunctionCall(
        "quantileState",
        params=(_coerce(level),),
        args=(_coerce(expr),)
    )


def quantile_merge(level: Any, value: Any) -> ParameterizedFunctionCall:
    """Merge quantile states and return final result.
    
    In ClickHouse, quantileMerge is a parameterized function:
    quantileMerge(0.5)(state) - where 0.5 is the parameter and state is the argument.
    """
    from chorm.sql.expression import ParameterizedFunctionCall
    return ParameterizedFunctionCall(
        "quantileMerge",
        params=(_coerce(level),),
        args=(_coerce(value),)
    )


def quantiles_state(levels: Any, expr: Any) -> ParameterizedFunctionCall:
    """Create quantiles state for AggregateFunction(quantiles(...), ...).
    
    In ClickHouse, quantilesState is a parameterized function:
    quantilesState(0.5, 0.9)(value) - where [0.5, 0.9] are parameters and value is the argument.
    """
    from chorm.sql.expression import ParameterizedFunctionCall
    # Handle list/tuple of levels
    if isinstance(levels, (list, tuple)):
        params = tuple(_coerce(level) for level in levels)
    else:
        params = (_coerce(levels),)
    return ParameterizedFunctionCall(
        "quantilesState",
        params=params,
        args=(_coerce(expr),)
    )


def quantiles_merge(levels: Any, value: Any) -> ParameterizedFunctionCall:
    """Merge quantiles states and return final result.
    
    In ClickHouse, quantilesMerge is a parameterized function:
    quantilesMerge(0.5, 0.9)(state) - where [0.5, 0.9] are parameters and state is the argument.
    """
    from chorm.sql.expression import ParameterizedFunctionCall
    # Handle list/tuple of levels
    if isinstance(levels, (list, tuple)):
        params = tuple(_coerce(level) for level in levels)
    else:
        params = (_coerce(levels),)
    return ParameterizedFunctionCall(
        "quantilesMerge",
        params=params,
        args=(_coerce(value),)
    )


def min_state(value: Any) -> FunctionCall:
    """Create min state for AggregateFunction(min, ...)."""
    return func.minState(value)


def min_merge(value: Any) -> FunctionCall:
    """Merge min states and return final result."""
    return func.minMerge(value)


def max_state(value: Any) -> FunctionCall:
    """Create max state for AggregateFunction(max, ...)."""
    return func.maxState(value)


def max_merge(value: Any) -> FunctionCall:
    """Merge max states and return final result."""
    return func.maxMerge(value)


# --- AggregateFunction combinators for conditional functions (If) ---


def sum_if_state(column: Any, condition: Any) -> FunctionCall:
    """Create sumIf state for AggregateFunction(sumIf, ...).
    
    Used when inserting into AggregateFunction(sumIf, ...) columns.
    
    Example:
        insert(Metrics).values(sum_state=sum_if_state(Order.amount, Order.status == 'completed'))
    """
    return func.sumIfState(column, condition)


def sum_if_merge(value: Any) -> FunctionCall:
    """Merge sumIf states and return final result.
    
    Used when selecting from AggregateFunction(sumIf, ...) columns.
    """
    return func.sumIfMerge(value)


def avg_if_state(column: Any, condition: Any) -> FunctionCall:
    """Create avgIf state for AggregateFunction(avgIf, ...)."""
    return func.avgIfState(column, condition)


def avg_if_merge(value: Any) -> FunctionCall:
    """Merge avgIf states and return final result."""
    return func.avgIfMerge(value)


def count_if_state(condition: Any) -> FunctionCall:
    """Create countIf state for AggregateFunction(countIf, ...)."""
    return func.countIfState(condition)


def count_if_merge(value: Any) -> FunctionCall:
    """Merge countIf states and return final result."""
    return func.countIfMerge(value)


def min_if_state(column: Any, condition: Any) -> FunctionCall:
    """Create minIf state for AggregateFunction(minIf, ...)."""
    return func.minIfState(column, condition)


def min_if_merge(value: Any) -> FunctionCall:
    """Merge minIf states and return final result."""
    return func.minIfMerge(value)


def max_if_state(column: Any, condition: Any) -> FunctionCall:
    """Create maxIf state for AggregateFunction(maxIf, ...)."""
    return func.maxIfState(column, condition)


def max_if_merge(value: Any) -> FunctionCall:
    """Merge maxIf states and return final result."""
    return func.maxIfMerge(value)


def uniq_if_state(column: Any, condition: Any) -> FunctionCall:
    """Create uniqIf state for AggregateFunction(uniqIf, ...)."""
    return func.uniqIfState(column, condition)


def uniq_if_merge(value: Any) -> FunctionCall:
    """Merge uniqIf states and return final result."""
    return func.uniqIfMerge(value)
