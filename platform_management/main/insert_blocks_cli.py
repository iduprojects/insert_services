"""
Blocks insertion command-line utility input information is defined here.
"""
from typing import Optional

import click

from platform_management.cli import insert_blocks_cli
from platform_management.dto import DatabaseCredentials

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
    help="Document geometry field (this or latitude and longitude)",
    default="geometry",
    show_default=True,
    show_envvar=True,
)
@click.argument("filename")
def insert_blocks(
    db_addr: str,
    db_port: int,
    db_name: str,
    db_user: str,
    db_pass: str,
    dry_run: bool,
    verbose: bool,
    log_filename: Optional[str],
    city: str,
    document_geometry: str,
    filename: str,
):  # pylint: disable=too-many-arguments,too-many-locals,
    "Insert blocks from geojson via command line"
    insert_blocks_cli(
        DatabaseCredentials(db_addr, db_port, db_name, db_user, db_pass),
        dry_run,
        verbose,
        log_filename,
        city,
        document_geometry,
        filename,
    )
