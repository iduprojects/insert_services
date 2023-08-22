"""Short data type converters are defined here."""
from __future__ import annotations

from PySide6 import QtCore


def str_or_none(string: str) -> str | None:
    """Return the given string or None if it is empty."""
    if len(string) == 0:
        return None
    return string


def int_or_none(string: str) -> int | None:
    """Return the given string as integer or None if it is empty."""
    if len(string) == 0:
        return None
    assert string.isnumeric(), f"{string} cannot be converted to integer"
    return int(string)


def to_str(i: int | float | str | None) -> str:  # pylint: disable=invalid-name
    """Return the given value as string, empty string on None."""
    return str(i) if i is not None else ""


def float_or_none(string: str) -> float | None:
    """Return the given string as float or None if it is empty."""
    if len(string) == 0:
        return None
    assert string.replace(".", "").isnumeric() and string.count(".") < 2, f"{string} cannot be convected to float"
    return float(string)


def bool_or_none(state: QtCore.Qt.CheckState) -> bool | None:
    """Return True if state is cheched, False if not checked and None if partially checked (unknown)."""
    if state == QtCore.Qt.CheckState.PartiallyChecked:
        return None
    if state == QtCore.Qt.CheckState.Checked:
        return True
    return False


def bool_to_checkstate(bool_value: bool | None) -> QtCore.Qt.CheckState:
    """Return PartiallyChecked state for None, Checked for True and Unchecked for False."""
    if bool_value is None:
        return QtCore.Qt.CheckState.PartiallyChecked
    if bool_value:
        return QtCore.Qt.CheckState.Checked
    return QtCore.Qt.CheckState.Unchecked
