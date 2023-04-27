"""
Blocks insertion command-line utility input information is defined here.
"""
from typing import Optional

import click

from platform_management.cli.adm_division import AdmDivisionType
from platform_management.cli.run_cli import insert_adms_cli
from platform_management.dto import AdmDivisionInsertionMapping, DatabaseCredentials

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
    "--document_parent_same_type",
    "-dSP",
    envvar="DOCUMENT_PARENT_SAME_TYPE",
    help="Document parent of the same type field",
    default="parent_same_type",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_name",
    "-dN",
    envvar="DOCUMENT_NAME",
    help="Document name field",
    default="name",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_type_name",
    "-dT",
    envvar="DOCUMENT_TYPE_NAME",
    help="Document type name field",
    default="type",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--default_type_name",
    "-DT",
    envvar="DEFAULT_TYPE_NAME",
    help="Default type name",
    default=None,
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
    "--document_population",
    "-dP",
    envvar="DOCUMENT_POPULATION",
    help="Document population field",
    default="population",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--document_parent_other_type",
    "-dSP",
    envvar="DOCUMENT_PARENT_OTHER_TYPE",
    help="Document parent of the other type field",
    default="parent",
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--division_type",
    "-D",
    envvar="DIVISION_TYPE",
    help="Type of administrative division to be inserted",
    default="ADMINISTRATIVE_UNIT",
    type=click.Choice([t.value for t in AdmDivisionType], case_sensitive=False),
    show_default=True,
    show_envvar=True,
)
@click.argument("filename")
def insert_adms(
    db_addr: str,
    db_port: int,
    db_name: str,
    db_user: str,
    db_pass: str,
    dry_run: bool,
    verbose: bool,
    log_filename: Optional[str],
    city: str,
    document_parent_same_type: str,
    document_name: str,
    document_type_name: str,
    default_type_name: Optional[str],
    document_geometry: str,
    document_population: str,
    document_parent_other_type: str,
    division_type: str,
    filename: str,
):  # pylint: disable=too-many-arguments,too-many-locals,
    "Insert administrative division units from geojson via command line"
    insert_adms_cli(
        DatabaseCredentials(db_addr, db_port, db_name, db_user, db_pass),
        dry_run,
        verbose,
        log_filename,
        city,
        AdmDivisionType(division_type.upper()),
        AdmDivisionInsertionMapping(
            document_geometry,
            document_type_name,
            document_name,
            document_parent_same_type,
            document_parent_other_type,
            document_population,
        ),
        filename,
        default_type_name,
    )
