"""
Buildings insertion command-line utility input information is defined here.
"""
import click

from platform_management.cli import insert_buildings_cli
from platform_management.dto import BuildingInsertionMapping, DatabaseCredentials

from .main_group import main


@main.command()
@click.option(
    "--db_addr",
    "-H",
    envvar="DB_ADDR",
    help="Postgres DBMS address",
    default="localhost",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--db_port",
    "-P",
    envvar="DB_PORT",
    type=int,
    help="Postgres DBMS port",
    default=5432,
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--db_name",
    "-D",
    envvar="DB_NAME",
    help="Postgres city database name",
    default="city_db_final",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--db_user",
    "-U",
    envvar="DB_USER",
    help="Postgres DBMS user name",
    default="postgres",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--db_pass",
    "-W",
    envvar="DB_PASS",
    help="Postgres DBMS user password",
    default="postgres",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--dry_run",
    "-d",
    envvar="DRY_RUN",
    is_flag=True,
    help="Try to insert objects, but do not save results",
    show_envvar=True,
)
@click.option(
    "--verbose", "-v", envvar="VERBOSE", is_flag=True, help="Output stack trace when error happens", show_envvar=True
)
@click.option(
    "--log_filename",
    "-l",
    envvar="LOGFILE",
    help='path to create log file, empty or "-" to disable logging',
    required=False,
    show_default='current datetime "YYYY-MM-DD HH-mm-ss-<filename>.csv"',
    show_envvar=True,
)
@click.option(
    "--city",
    "-c",
    envvar="CITY",
    help="City to insert services to, must exist in the database",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_geometry",
    "-dg",
    envvar="DOCUMENT_GEOMETRY",
    help="Document geometry field name",
    default="geometry",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_address",
    "-dA",
    envvar="DOCUMENT_ADDRESS",
    help="Document building address field name",
    default="yand_adr",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_project_type",
    "-dP",
    envvar="DOCUMENT_PROJCET_TYPE",
    help="Document building project type name field name",
    default="project_type",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_living_area",
    "-dL",
    envvar="DOCUMENT_LIVING_AREA",
    help="Document building living area field name",
    default="area_residential",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_storeys_count",
    "-dS",
    envvar="DOCUMENT_STOREYS_COUNT",
    help="Document buildings storeys count field name",
    default="building:levels",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_resident_number",
    "-dR",
    envvar="DOCUMENT_RESIDENT_NUMBER",
    help="Document buildings resident number count field name",
    default="resident_number",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_osm_id",
    "-dI",
    envvar="DOCUMENT_OSM_ID",
    help="Document physical object OSM identifier field field name",
    default="id",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_central_heating",
    "-dCH",
    envvar="DOCUMENT_CENTRAL_HEATING",
    help="Document building central heating field name",
    default="central_heating",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_central_water",
    "-dCC",
    envvar="DOCUMENT_CENTRAL_WATER",
    help="Document building central water field name",
    default="central_water",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_central_hot_water",
    "-dCW",
    envvar="DOCUMENT_CENTRAL_HOT_WATER",
    help="Document building central hot water field name",
    default="central_hot_water",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_central_electricity",
    "-dCE",
    envvar="DOCUMENT_CENTRAL_ELECTRICITY",
    help="Document building central electricity field name",
    default="central_electricity",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_central_gas",
    "-dCG",
    envvar="DOCUMENT_CENTRAL_GAS",
    help="Document building central gas field name",
    default="central_gas",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_refusechute",
    "-dR",
    envvar="DOCUMENT_REFUSECHUTE",
    help="Document building refusechute field name",
    default="refusechute",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_ukname",
    "-dU",
    envvar="DOCUMENT_UKNAME",
    help="Document building company field name",
    default="ukname",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_is_failing",
    "-dF",
    envvar="DOCUMENT_IS_FAILING",
    help="Document building is_failing field name",
    default="is_failing",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_lift_count",
    "-dL",
    envvar="DOCUMENT_LIFT_COUNT",
    help="Document building lift count field name",
    default="lift_count",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_repair_years",
    "-dF",
    envvar="DOCUMENT_REPAIR_YEARS",
    help="Document building repair_years field name",
    default="repair_years",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_is_living",
    "-dL",
    envvar="DOCUMENT_IS_LIVING",
    help="Document building is_living field name",
    default="is_living",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_building_year",
    "-dL",
    envvar="DOCUMENT_BUILDING_YEAR",
    help="Document building built year",
    default="built_year",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_modeled",
    "-dM",
    envvar="DOCUMENT_MODELED",
    help="Document modeled fields (as in document, separated by comma) field name",
    default="modeled_fields",
    show_envvar=True,
)
@click.option(
    "--address_prefix",
    "-aP",
    multiple=True,
    envvar="ADDRESS_PREFIX",
    help="Address prefix (available for multiple prefixes), no comma or space needed",
    default=[],
    show_default="Россия, Санкт-Петербург",
    show_envvar=True,
)
@click.option(
    "--new_address_prefix",
    "-nAP",
    envvar="NEW_ADDRESS_PREFIX",
    help="New address prefix that would be added to all addresses after cutting old address prefix",
    default="",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--properties_mapping",
    "-p",
    multiple=True,
    envvar="PROPERTIES_MAPPING",
    help='Properties mapping, entries in "key_in_properties:column_in_document" format',
    default=[],
    show_envvar=True,
)
@click.argument("filename", type=click.Path(exists=True, dir_okay=False))
def insert_buildings(
    db_addr: str,
    db_port: int,
    db_name: str,
    db_user: str,
    db_pass: str,
    dry_run: bool,
    verbose: bool,
    log_filename: str | None,
    city: str,
    document_geometry: str,
    document_address: str,
    document_project_type: str,
    document_living_area: str,
    document_storeys_count: str,
    document_resident_number: str,
    document_osm_id: str,
    document_central_heating: str,
    document_central_water: str,
    document_central_hot_water: str,
    document_central_electricity: str,
    document_central_gas: str,
    document_refusechute: str,
    document_ukname: str,
    document_is_failing: str,
    document_lift_count: str,
    document_repair_years: str,
    document_is_living: str,
    document_building_year: str,
    document_modeled: str,
    address_prefix: list[str],
    new_address_prefix: str,
    properties_mapping: list[str],
    filename: str,
):  # pylint: disable=too-many-arguments,too-many-locals,
    """Insert buildings via command line

    Document source can have geojson csv, xlsx, json, xls or ods format.

    Pass the database access credentials, set city name or code and map document fields to the buildings
    table in the database.

    Additional properties can be set via '-p key_in_properties:column_in_document'.

    Modeled column should contain document columnd separated by comma. Corresponding table columns will be
    marked modeled on insert.
    """
    columns_mapping = BuildingInsertionMapping(
        document_geometry,
        document_address,
        document_project_type,
        document_living_area,
        document_storeys_count,
        document_resident_number,
        document_osm_id,
        document_central_heating,
        document_central_water,
        document_central_hot_water,
        document_central_electricity,
        document_central_gas,
        document_refusechute,
        document_ukname,
        document_is_failing,
        document_lift_count,
        document_repair_years,
        document_is_living,
        document_building_year,
        document_modeled,
    )
    insert_buildings_cli(
        DatabaseCredentials(db_addr, db_port, db_name, db_user, db_pass),
        dry_run,
        verbose,
        log_filename,
        city,
        columns_mapping,
        address_prefix,
        new_address_prefix,
        properties_mapping,
        filename,
    )
