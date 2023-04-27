import click

from platform_management.gui import InitWindow, run_gui

from .main_group import main


@main.command()
@click.option(
    "--db_addr",
    "-H",
    envvar="DB_ADDR",
    help="Postgres DBMS address",
    default=InitWindow.default_values.db_address,
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--db_port",
    "-P",
    envvar="DB_PORT",
    type=int,
    help="Postgres DBMS port",
    default=InitWindow.default_values.db_port,
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--db_name",
    "-D",
    envvar="DB_NAME",
    help="Postgres city database name",
    default=InitWindow.default_values.db_name,
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--db_user",
    "-U",
    envvar="DB_USER",
    help="Postgres DBMS user name",
    default=InitWindow.default_values.db_user,
    show_default=True,
    show_envvar=True,
)
@click.option(
    "--db_pass",
    "-W",
    envvar="DB_PASS",
    help="Postgres DBMS user password",
    default=InitWindow.default_values.db_pass,
    show_default=True,
    show_envvar=True,
)
@click.option("--verbose", "-v", envvar="VERBOSE", is_flag=True, help="Include debug information")
def gui(
    db_addr: str, db_port: int, db_name: str, db_user: str, db_pass: str, verbose: bool
):  # pylint: disable=too-many-arguments
    "Graphical User Interface"
    run_gui(db_addr, db_port, db_name, db_user, db_pass, verbose)
