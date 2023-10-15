"""
IDU Digital City Platform management tool, GUI and CLI versions
"""
from platform_management.cli import (
    add_buildings,
    add_services,
    insert_buildings_cli,
    insert_services_cli,
    load_objects,
)

from .dto import BuildingInsertionMapping, ServiceInsertionMapping
from .version import VERSION as __version__
