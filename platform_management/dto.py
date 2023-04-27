"""
Document-database mappings are defined here.
"""
from dataclasses import dataclass
from typing import Dict, Optional, Union


@dataclass(frozen=True)
class DatabaseCredentials:
    """
    Dataclass to store database credentials.
    """

    address: str
    port: int
    name: str
    user: str
    password: str

    def get_connection_params(
        self, additional_params: Optional[Dict[str, str | int]] = ...
    ) -> Dict[str, Union[str, int]]:
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
            "application_name": "platform_management_app",
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


@dataclass(frozen=True)
class ServiceInsertionMapping:  # pylint: disable=too-many-instance-attributes
    """
    Class to store the mapping between input document service properties and database columns.

    Should be initialized with `init()`.
    """

    latitude: Optional[str] = None
    longitude: Optional[str] = None
    geometry: Optional[str] = None
    name: Optional[str] = None
    opening_hours: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    capacity: Optional[str] = None
    osm_id: Optional[str] = None

    @classmethod
    def init(  # pylint: disable=too-many-arguments
        cls,
        latitude: Optional[str] = "x",
        longitude: Optional[str] = "y",
        geometry: Optional[str] = "geometry",
        name: Optional[str] = "Name",
        opening_hours: Optional[str] = "opening_hours",
        website: Optional[str] = "contact:website",
        phone: Optional[str] = "contact:phone",
        address: Optional[str] = "yand_adr",
        osm_id: Optional[str] = "id",
        capacity: Optional[str] = None,
    ) -> "ServiceInsertionMapping":
        """
        Initialize `ServiceInsertionMapping` instance with given values (except empty values and "-")
        """
        assert not (
            (latitude is None or longitude is None) and geometry is None
        ), "At least one of (latitude+longitude) and (geometry) must be set"
        return cls(
            *map(
                lambda s: None if s in ("", "-") else s,
                (
                    latitude,
                    longitude,
                    geometry,
                    name,
                    opening_hours,
                    website,
                    phone,
                    address,
                    capacity,
                    osm_id,
                ),
            )
        )  # type: ignore


@dataclass(frozen=True)
class BuildingInsertionMapping:  # pylint: disable=too-many-instance-attributes
    """
    Class to store the mapping between input document building properties and database columns.

    Should be initialized with `init()`.
    """

    geometry: Optional[str] = None
    address: Optional[str] = None
    project_type: Optional[str] = None
    living_area: Optional[str] = None
    storeys_count: Optional[str] = None
    resident_number: Optional[str] = None
    osm_id: Optional[str] = None
    central_heating: Optional[str] = None
    central_water: Optional[str] = None
    central_hot_water: Optional[str] = None
    central_electricity: Optional[str] = None
    central_gas: Optional[str] = None
    refusechute: Optional[str] = None
    ukname: Optional[str] = None
    is_failing: Optional[str] = None
    lift_count: Optional[str] = None
    repair_years: Optional[str] = None
    is_living: Optional[str] = None
    building_year: Optional[str] = None

    @classmethod
    def init(  # pylint: disable=too-many-arguments,too-many-locals
        cls,
        geometry: str = "geometry",
        address: Optional[str] = "address",
        project_type: Optional[str] = "project_type",
        living_area: Optional[str] = "area_residential",
        storeys_count: Optional[str] = "building:levels",
        resident_number: Optional[str] = "resident_number",
        osm_id: Optional[str] = "osm_id",
        central_heating: Optional[str] = "central_heating",
        central_water: Optional[str] = "central_water",
        central_hot_water: Optional[str] = "central_hot_water",
        central_electricity: Optional[str] = "central_electricity",
        central_gas: Optional[str] = "central_gas",
        refusechute: Optional[str] = "refusechute",
        ukname: Optional[str] = "ukname",
        is_failing: Optional[str] = "is_failing",
        lift_count: Optional[str] = "lift_count",
        repair_years: Optional[str] = "repair_years",
        is_living: Optional[str] = "is_living",
        building_year: Optional[str] = "built_year",
    ) -> "BuildingInsertionMapping":
        """
        Initialize `BuildingInsertionMapping` instance with given values (except empty values and "-")
        """
        return cls(
            *map(
                lambda s: None if s in ("", "-") else s,
                (
                    geometry,
                    address,
                    project_type,
                    living_area,
                    storeys_count,
                    resident_number,
                    osm_id,
                    central_heating,
                    central_water,
                    central_hot_water,
                    central_electricity,
                    central_gas,
                    refusechute,
                    ukname,
                    is_failing,
                    lift_count,
                    repair_years,
                    is_living,
                    building_year,
                ),
            )
        )


@dataclass(frozen=True)
class AdmDivisionInsertionMapping:  # pylint: disable=too-many-instance-attributes
    """
    Class to store the mapping between input document administrative division unit properties and database columns.

    Should be initialized with `init()`.
    """

    geometry: str
    type_name: str
    name: str
    parent_same_type: Optional[str] = None
    parent_other_type: Optional[str] = None
    population: Optional[str] = None

    @classmethod
    def init(  # pylint: disable=too-many-arguments
        cls,
        geometry: str = "geometry",
        type_name: str = "type",
        name: Optional[str] = "name",
        parent_same_type: Optional[str] = "parent_same_type",
        parent_other_type: Optional[str] = "parent",
        population: Optional[str] = "population",
    ) -> "ServiceInsertionMapping":
        """
        Initialize `ServiceInsertionMapping` instance with given values (except empty values and "-")
        """
        assert geometry is not None, "Administrative division unit geometry column must be set"
        assert type_name is not None, "Administrative division unit type column must be set"
        return cls(
            *map(
                lambda s: None if s in ("", "-") else s,
                (
                    geometry,
                    name,
                    parent_same_type,
                    parent_other_type,
                    population,
                ),
            )
        )  # type: ignore
