"""Some default values for services insertion GUI are located here."""
from typing import NamedTuple

InsertionWindowDefaultValues = NamedTuple(
    "InsertionWindowDefaultValues",
    [
        ("service_code", str),
        ("city_function", str),
        ("latitude", str),
        ("longitude", str),
        ("geometry", str),
        ("address", str),
        ("name", str),
        ("opening_hours", str),
        ("website", str),
        ("phone", str),
        ("osm_id", str),
    ],
)


def get_main_window_default_values() -> InsertionWindowDefaultValues:
    """Return default city address options values."""
    return InsertionWindowDefaultValues(
        "", "", "x", "y", "geometry", "yand_adr", "name", "opening_hours", "contact:website", "contact:phone", "id"
    )


def get_main_window_default_address_prefixes() -> list[str]:
    """Return default city address prefixes."""
    return [""]


def get_default_city_functions() -> list[str]:
    """Return default city functions."""
    return ["(необходимо соединение с базой)"]


def get_default_service_types() -> list[str]:
    """Return default service types."""
    return ["(необходимо соединение с базой)"]
