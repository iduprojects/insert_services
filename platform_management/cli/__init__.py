"""
Command-line interface logic is defined here.
"""
from .buildings import add_buildings
from .files import load_objects
from .mappings import ServiceInsertionMapping, BuildingInsertionMapping
from .run_cli import insert_buildings_cli, insert_services_cli
from .services import add_services, get_properties_keys
