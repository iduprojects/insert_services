"""
Click cli launchnig options are defined here.
"""

from . import (  # noqa: F401
    gui,
    insert_adms_cli,
    insert_blocks_cli,
    insert_buildings_cli,
    insert_services_cli,
    operations,
)
from .main_group import main

__all__ = [
    "main",
]
