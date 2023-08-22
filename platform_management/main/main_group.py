"""
Main group for subcommands registration.
"""
import click

from platform_management.utils.dotenv import try_read_envfile

try_read_envfile()


@click.group()
def main():
    """IDU - Platform Management Tool.

    Includes CLI and GUI modes to manipulate database entities.
    """
