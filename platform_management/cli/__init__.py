"""
Command-line interface logic is defined here.
"""
from .adm_division import AdmDivisionType, add_adm_division
from .blocks import add_blocks
from .buildings import add_buildings
from .files import load_objects
from .run_cli import (
    insert_adms_cli,
    insert_blocks_cli,
    insert_buildings_cli,
    insert_services_cli,
)
from .services import add_services, get_properties_keys
