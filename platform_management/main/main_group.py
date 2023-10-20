"""
Main group for subcommands registration.
"""
import click

from platform_management.utils.dotenv import try_read_envfile
from platform_management.version import VERSION

try_read_envfile()


@click.group()
@click.version_option(VERSION)
def main():
    """IDU - Platform Management Tool.

    Includes CLI and GUI modes to manipulate database entities.
    """
