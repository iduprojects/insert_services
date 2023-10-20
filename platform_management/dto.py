"""
Document-database mappings are defined here.
"""
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import fields as get_fields

from platform_management.version import VERSION


@dataclass
class DatabaseCredentials:
    """
    Dataclass to store database credentials.
    """

    address: str
    port: int
    name: str
    user: str
    password: str

    def get_connection_params(self, additional_params: dict[str, str | int] | None = ...) -> dict[str, str | int]:
        """
        Return connection parameters dictionady.

        If `additional_params` are not set, defaults are used. None value equals to {}.
        """
        params = {
            "host": self.address,
            "port": self.port,
            "dbname": self.name,
            "user": self.user,
            "password": self.password,
            "application_name": f"platform_management_app v{VERSION}",
        }
        if additional_params is not ...:
            if additional_params is not None:
                params.update(additional_params)
        else:
            params.update(
                {
                    "connect_timeout": 10,
                    "keepalives": 1,
                    "keepalives_idle": 5,
                    "keepalives_interval": 2,
                    "keepalives_count": 2,
                }
            )
        return params


@dataclass
class ServiceInsertionMapping:  # pylint: disable=too-many-instance-attributes
    """Class to store the mapping between input document service properties and database columns."""

    latitude: str | None = "x"
    longitude: str | None = "y"
    geometry: str | None = "geometry"
    name: str | None = "Name"
    opening_hours: str | None = "opening_hours"
    website: str | None = "contact:website"
    phone: str | None = "contact:phone"
    address: str | None = "yand_adr"
    capacity: str | None = "id"
    osm_id: str | None = None

    def __post_init__(self) -> None:
        for field in get_fields(self):
            value = getattr(self, field.name)
            if value in ("", "-"):
                setattr(self, field.name, None)
        if (self.latitude is None or self.longitude is None) and self.geometry is None:
            raise ValueError("At least one of (latitude+longitude) and (geometry) must be set")


@dataclass
class BuildingInsertionCLIParameters:  # pylint: disable=too-many-instance-attributes
    """Class to store user input with multiple mapping options available for each attribute.

    - None value means that parameter was not set and should be treated as default.
    - [] value means that defaults were intentionally disabled by passing empty value or "-" as an ragument.
    """

    geometry: list[str] | None
    address: list[str] | None
    project_type: list[str] | None
    living_area: list[str] | None
    storeys_count: list[str] | None
    resident_number: list[str] | None
    osm_id: list[str] | None
    central_heating: list[str] | None
    central_water: list[str] | None
    central_hot_water: list[str] | None
    central_electricity: list[str] | None
    central_gas: list[str] | None
    refusechute: list[str] | None
    ukname: list[str] | None
    is_failing: list[str] | None
    lift_count: list[str] | None
    repair_years: list[str] | None
    is_living: list[str] | None
    building_year: list[str] | None
    modeled: list[str] | None

    def __post_init__(self) -> None:
        for field in get_fields(self):
            values = getattr(self, field.name)
            if len(values) == 0:
                setattr(self, field.name, None)
            elif len(values) > 0 and all(value in ("", "-") for value in values):
                setattr(self, field.name, [])


@dataclass
class BuildingInsertionMapping:  # pylint: disable=too-many-instance-attributes
    """Class to store the mapping between input document building properties and database columns."""

    geometry: str
    address: str | None = None
    project_type: str | None = None
    living_area: str | None = None
    storeys_count: str | None = None
    resident_number: str | None = None
    osm_id: str | None = None
    central_heating: str | None = None
    central_water: str | None = None
    central_hot_water: str | None = None
    central_electricity: str | None = None
    central_gas: str | None = None
    refusechute: str | None = None
    ukname: str | None = None
    is_failing: str | None = None
    lift_count: str | None = None
    repair_years: str | None = None
    is_living: str | None = None
    building_year: str | None = None
    modeled: str | None = None


@dataclass
class AdmDivisionInsertionMapping:  # pylint: disable=too-many-instance-attributes
    """Class to store the mapping between input document administrative division unit
    properties and database columns.
    """

    geometry: str = "geometry"
    type_name: str = "type"
    name: str = "name"
    parent_same_type: str | None = "parent_same_type"
    parent_other_type: str | None = "parent"
    population: str | None = "population"

    def __post_init__(self) -> None:
        if self.geometry is None:
            raise ValueError("Administrative division unit (geometry) column name must be set")
        if self.type_name is None:
            raise ValueError("Administrative division unit (type) column name must be set")
        if self.name is None:
            raise ValueError("Administrative division unit (name) column name must be set")
