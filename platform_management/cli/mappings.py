"""
Document-database mappings are defined here.
"""
from dataclasses import dataclass
from typing import Optional


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
    def init(
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
