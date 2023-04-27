"""
IDU Digital City Platform management tool, GUI and CLI versions
"""
from platform_management.cli import (
    add_buildings,
    add_services,
    get_properties_keys,
    insert_buildings_cli,
    insert_services_cli,
    load_objects,
)

from .dto import BuildingInsertionMapping, ServiceInsertionMapping

__author__ = "Aleksei Sokol"
__maintainer__ = __author__

__email__ = "kanootoko@gmail.com"
__license__ = "MIT"
__version__ = "0.3.0"
