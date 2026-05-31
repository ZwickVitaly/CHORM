from typing import Any, Dict


class Compiler:
    """SQL Compiler.

    Manages the compilation of SQL expressions and the collection of bind parameters.
    """

    def __init__(self) -> None:
        self.params: Dict[str, Any] = {}
        self._param_index = 0

    def add_param(self, value: Any) -> str:
        """Add a parameter to the compiler and return its placeholder.

        Args:
            value: The value to bind

        Returns:
            The placeholder string (e.g., '%(p_0)s')
        """
        name = f"p_{self._param_index}"
        self.params[name] = value
        self._param_index += 1
        return f"%({name})s"

    def compile(self, expression: Any) -> str:
        """Compile an expression to SQL.

        Args:
            expression: The expression object (must have to_sql method)

        Returns:
            Compiled SQL string
        """
        # Circular import avoidance; handled by calling to_sql with self
        if hasattr(expression, "to_sql"):
            # Compile using the expression's to_sql method
            return expression.to_sql(self)
        return str(expression)
