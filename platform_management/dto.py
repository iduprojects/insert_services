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
class BuildingInsertionMapping:  # pylint: disable=too-many-instance-attributes
    """Class to store the mapping between input document building properties and database columns."""

    geometry: str | None = "geometry"
    address: str | None = "address"
    project_type: str | None = "project_type"
    living_area: str | None = "area_residential"
    storeys_count: str | None = "building:levels"
    resident_number: str | None = "resident_number"
    osm_id: str | None = "osm_id"
    central_heating: str | None = "central_heating"
    central_water: str | None = "central_water"
    central_hot_water: str | None = "central_hot_water"
    central_electricity: str | None = "central_electricity"
    central_gas: str | None = "central_gas"
    refusechute: str | None = "refusechute"
    ukname: str | None = "ukname"
    is_failing: str | None = "is_failing"
    lift_count: str | None = "lift_count"
    repair_years: str | None = "repair_years"
    is_living: str | None = "is_living"
    building_year: str | None = "built_year"
    modeled: str | None = "modeled_fields"

    def __post_init__(self) -> None:
        for field in get_fields(self):
            value = getattr(self, field.name)
            if value in ("", "-"):
                setattr(self, field.name, None)


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
