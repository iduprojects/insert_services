"""
Common classes and methods are defined here.
"""
import itertools
import json
import time
from enum import Enum
from enum import auto as enum_auto
from typing import Any, Dict

from loguru import logger


class SQLType(Enum):
    """
    Class to map SQL types to Python types
    """

    INT = enum_auto()
    VARCHAR = enum_auto()
    DOUBLE = enum_auto()
    BOOLEAN = enum_auto()
    SMALLINT = enum_auto()
    JSONB = enum_auto()
    TIMESTAMP = enum_auto()

    @classmethod
    def from_name(cls, name: str):
        """Get SQL type by name."""
        if name.lower() in sqltype_mapping:
            return sqltype_mapping[name.lower()]
        if name.startswith("character varying"):
            return SQLType.VARCHAR
        raise ValueError(f"Type {name} cannot be mapped to SQLType")

    @property
    def sql_name(self) -> str:
        """Get sql name of a type."""
        return {
            SQLType.INT: "integer",
            SQLType.VARCHAR: "character varying",
            SQLType.DOUBLE: "double precision",
            SQLType.BOOLEAN: "boolean",
            SQLType.SMALLINT: "smallint",
            SQLType.JSONB: "jsonb",
            SQLType.TIMESTAMP: "timestamp with time zone",
        }[self]

    def cast(self, value: Any) -> Any:  # pylint: disable=too-many-return-statements
        """Cast given value to a given type's correct data"""
        if (
            value is None
            or value != value  # pylint: disable=comparison-with-itself
            or (isinstance(value, str) and value == "")
        ):
            return None

        try:
            if self in (SQLType.INT, SQLType.SMALLINT):
                return int(float(value))
            if self == SQLType.DOUBLE:
                return float(value)
            if self == SQLType.BOOLEAN:
                if isinstance(value, str):
                    return False if value.lower() in ("-", "0", "false", "no", "off", "нет", "ложь") else bool(value)
            if self == SQLType.JSONB:
                return json.dumps(value)
            if self == SQLType.TIMESTAMP:
                if isinstance(value, time.struct_time):
                    return (
                        f"{value.tm_year}-{value.tm_mon:02}-{value.tm_mday:02}"
                        f" {value.tm_hour:02}:{value.tm_min:02}:{value.tm_sec:02}"
                    )
                raise ValueError("Only time.struct_time can be cast to SQL Timestamp")
            raise NotImplementedError(f"Type {self} cast is not implemented for some reason")
        except Exception as exc:  # pylint: disable=broad-except
            logger.trace("Could not cast {} to {}: {!r}", value, self.sql_name, exc)
            return None


sqltype_mapping: Dict[str, SQLType] = dict(
    itertools.chain(
        map(
            lambda x: (x, SQLType.VARCHAR),
            ("character varying", "varchar", "str", "string", "text", "varchar", "строка"),
        ),
        map(lambda x: (x, SQLType.DOUBLE), ("double precision", "float", "double", "вещественное", "нецелое")),
        map(lambda x: (x, SQLType.INT), ("integer", "int", "number", "целое")),
        map(lambda x: (x, SQLType.SMALLINT), ("smallint", "малое", "малое целое")),
        map(lambda x: (x, SQLType.JSONB), ("jsonb", "json")),
        map(lambda x: (x, SQLType.BOOLEAN), ("boolean", "булево")),
        map(lambda x: (x, SQLType.TIMESTAMP), ("timestamp", "date", "time", "datetime", "дата", "время")),
    )
)
"""Mapping of possible names of SQL types to themselves"""


class SingleObjectStatus(Enum):
    """
    Enumeration of possible objects status on insertion/updation process.
    """

    INSERTED = "INSERTED"
    UPDATED = "UPDATED"
    UNCHANGED = "UNCHANGED"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"
