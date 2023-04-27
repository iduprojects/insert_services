# pylint: disable=too-many-arguments,too-many-locals
"""
Platform management main module, subcommands are defined in `platform_management.main`.
"""
import os

from platform_management.main import main

if __name__ == "__main__":
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
    main()
