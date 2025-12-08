"""Utility functions for CHORM."""

def escape_string(value: str) -> str:
    """Escape string value for SQL literal.
    
    Escapes backslashes first, then single quotes.
    """
    return value.replace("\\", "\\\\").replace("'", "''")
