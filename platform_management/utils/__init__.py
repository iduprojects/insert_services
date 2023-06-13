"""
Utility functions used in platform_management module are located here.
"""
import string
from typing import Any


def simplify_data(value: Any) -> Any:  # pylint: disable=too-many-return-statements
    """
    Simplify data class when possible.

    Examples:
    >>> simplify_data('123')       # 123
    >>> simplify_data('123.0')     # 123
    >>> simplify_data('123.45)     # 123.45
    >>> simplify_data('123.45.67') # '123.45.67'
    >>> simplify_data('true')      # True
    >>> simplify_data('none')      # None
    >>> simplify_data(numpy.nan)   # None
    >>> simplify_data(object())    # <object object at 0x...>
    """
    if (
        value is None
        or (isinstance(value, float) and value != value)  # pylint: disable=comparison-with-itself
        or (isinstance(value, str) and value.lower() in ("", "nan", "none", "undefined"))
    ):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else value
    if isinstance(value, str):
        if value.isnumeric():
            return int(value)
        if value.count(".") == 1 and len(set(value) - {"."} - set(string.digits)) == 0:
            res = float(value)
            if res.is_integer():
                return int(res)
        if value.lower() in ("false", "true"):
            return len(value) == 4
        return value
    return value
