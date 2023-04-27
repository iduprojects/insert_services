"""
Main group for subcommands registration.
"""
import click


@click.group()
def main():
    """
    IDU - Platform Management Tool.

    Includes CLI and GUI modes to manipulate database entities.
    """
