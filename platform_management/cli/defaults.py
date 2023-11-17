"""Default input values for CLI are defined here."""


class InsertBuildings:  # pylint: disable=too-few-public-methods
    """Default values for Insert Buildings CLI command"""

    document_geometry = ["geometry"]
    document_address = ["yand_addr", "address", "addr"]
    document_project_type = ["project_type", "project_ty"]
    document_living_area = ["living_area", "area_resid", "area_residential"]
    document_storeys_count = ["building:levels", "building:level", "building_l", "storeys_count", "storey_count"]
    document_resident_number = ["resident_number", "population"]
    document_osm_id = ["osm_id", "id", "@id"]
    document_central_heating = ["central_heating"]
    document_central_water = ["central_water"]
    document_central_hot_water = ["central_hot_water", "central_hotwater"]
    document_central_electricity = ["central_electricity", "central_electro"]
    document_central_gas = ["central_gas"]
    document_refusechute = ["refusechute"]
    document_ukname = ["ukname"]
    document_is_failing = ["is_failing", "failure"]
    document_lift_count = ["lift_count", "elevators_", "elevators_count"]
    document_repair_years = ["repair_years"]
    document_is_living = ["is_living"]
    document_building_year = ["built_year", "building_year"]
    document_modeled = ["modeled_fields"]
    address_prefix = []
    new_address_prefix = ""
    properties_mapping = []
