"""Blocks insertion command-line utility input information is defined here."""
from __future__ import annotations

from typing import Literal

import click
import psycopg2

from platform_management.cli import refresh_materialized_views, update_physical_objects_locations
from platform_management.version import VERSION

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
@click.argument("action", type=click.Choice(["refresh-materialized-views", "update-physical-objects-locations"], False))
def operation(
    db_addr: str,
    db_port: int,
    db_name: str,
    db_user: str,
    db_pass: str,
    action: Literal["refresh-materialized-views", "update-physical-objects-locations"],
):  # pylint: disable=too-many-arguments,too-many-locals,
    "Insert blocks from geojson via command line"
    with psycopg2.connect(
        host=db_addr,
        port=db_port,
        dbname=db_name,
        user=db_user,
        password=db_pass,
        application_name=f"platform_management_app v{VERSION}",
    ) as conn, conn.cursor() as cur:
        if action == "refresh-materialized-views":
            refresh_materialized_views(cur)
        else:
            update_physical_objects_locations(cur)
