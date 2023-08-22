"""Services insertion command-line utility input information is defined here."""
from __future__ import annotations

import click

from platform_management.cli import insert_services_cli
from platform_management.dto import DatabaseCredentials, ServiceInsertionMapping

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
    required=True,
)
@click.option(
    "--service_type",
    "-T",
    envvar="SERVICE_TYPE",
    help="Service type name or code for inserting services, must exist in the database",
    show_default=True,
    show_envvar=True,
    required=True,
)
@click.option(
    "--document_latitude",
    "-dx",
    envvar="DOCUMENT_LATITUDE",
    help="Document latutude field (this and longitude or geometry)",
    default="x",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_longitude",
    "-dy",
    envvar="DOCUMENT_LONGITUDE",
    help="Document longitude field (this and latitude or geometry)",
    default="y",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_geometry",
    "-dg",
    envvar="DOCUMENT_GEOMETRY",
    help="Document geometry field (this or latitude and longitude)",
    default="geometry",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_address",
    "-dA",
    envvar="DOCUMENT_ADDRESS",
    help="Document service building address field",
    default="yand_adr",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_service_name",
    "-dN",
    envvar="DOCUMENT_SERVICE_NAME",
    help="Document service name field",
    default="name",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_opening_hours",
    "-dO",
    envvar="DOCUMENT_OPENING_HOURS",
    help="Document service opening hours field",
    default="opening_hours",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_website",
    "-dw",
    envvar="DOCUMENT_WEBSITE",
    help="Document service website field",
    default="contact:website",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_phone",
    "-dP",
    envvar="DOCUMENT_PHONE",
    help="Document service phone number field",
    default="contact:phone",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_osm_id",
    "-dI",
    envvar="DOCUMENT_OSM_ID",
    help="Document physical object OSM identifier field",
    default="id",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_capacity",
    "-dC",
    envvar="DOCUMENT_CAPACITY",
    help="Document service capacity field",
    default="-",
    show_default=True,
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
@click.argument("filename")
def insert_services(
    db_addr: str,
    db_port: int,
    db_name: str,
    db_user: str,
    db_pass: str,
    dry_run: bool,
    verbose: bool,
    log_filename: str | None,
    city: str,
    service_type: str,
    document_latitude: str,
    document_longitude: str,
    document_geometry: str,
    document_address: str,
    document_service_name: str,
    document_opening_hours: str,
    document_website: str,
    document_phone: str,
    document_osm_id: str,
    document_capacity: str,
    address_prefix: list[str],
    new_address_prefix: str,
    properties_mapping: list[str],
    filename: str,
):  # pylint: disable=too-many-arguments,too-many-locals,
    """Insert services from geojson via command line"""
    columns_mapping = ServiceInsertionMapping(
        document_latitude,
        document_longitude,
        document_geometry,
        document_service_name,
        document_opening_hours,
        document_website,
        document_phone,
        document_address,
        document_osm_id,
        document_capacity,
    )
    insert_services_cli(
        DatabaseCredentials(db_addr, db_port, db_name, db_user, db_pass),
        dry_run,
        verbose,
        log_filename,
        city,
        service_type,
        columns_mapping,
        address_prefix,
        new_address_prefix,
        properties_mapping,
        filename,
    )
