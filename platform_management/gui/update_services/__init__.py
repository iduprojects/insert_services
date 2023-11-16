"""Service updation GUI logic is defined here."""
from .physical_object_creation import PhysicalObjectCreationWidget
from .platform_services_table import PlatformServicesTableWidget
from .update_services import ServicesUpdatingWindow

__all__ = [
    "PhysicalObjectCreationWidget",
    "PlatformServicesTableWidget",
    "ServicesUpdatingWindow",
]
