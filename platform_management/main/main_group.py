"""
Main group for subcommands registration.
"""
import os

import click

envfile = os.environ.get("ENVFILE", ".env")
if os.path.isfile(envfile):
    with open(envfile, "rt", encoding="utf-8") as file:
        for name, value in (
            tuple((line[len("export ") :] if line.startswith("export ") else line).strip().split("=", 1))
            for line in file.readlines()
            if not line.startswith("#") and "=" in line
        ):
            if name not in os.environ:
                if " #" in value:
                    value = value[: value.index(" #")]
                os.environ[name] = value.strip()


@click.group()
def main():
    """IDU - Platform Management Tool.

    Includes CLI and GUI modes to manipulate database entities.
    """
