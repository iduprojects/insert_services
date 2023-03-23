"""
Command-line interface logic is defined here.
"""
from platform_management.cli.insert_services import (
    InsertionMapping,
    add_objects,
    get_properties_keys,
    load_objects,
    run_cli,
)

__all__ = (
    "InsertionMapping",
    "add_objects",
    "get_properties_keys",
    "load_objects",
    "run_cli",
)
