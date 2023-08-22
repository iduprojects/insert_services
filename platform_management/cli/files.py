"""Functions to load pandas.DataFrame from different file types are defined here."""
from __future__ import annotations

import json
from typing import Any, Iterable

import pandas as pd
from numpy import nan


def replace_with_default(dataframe: pd.DataFrame, default_values: dict[str, Any]) -> pd.DataFrame:
    """Replace null items in dataframe in given columns with given values.

    `default_values` is a dictionary with columns names as key and default values for them as values.

    If column is missing, it will be created filled fully with default values

    Returns new dataframe with null entries replaced with given defaults
    """
    for column, value in default_values.items():
        if column in dataframe:
            dataframe[column] = dataframe[column].fillna(value)
        else:
            dataframe[column] = pd.DataFrame([value] * dataframe.shape[0])
    return dataframe


def load_objects_geojson(
    filename: str,
    default_values: dict[str, Any] | None = None,
    needed_columns: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Load objects as DataFrame from geojson. It contains only [features][properties] columns.

    Calls `replace_with_default` after load if `default_values` is present
    """
    with open(filename, "r", encoding="utf-8") as file:
        try:
            data = json.load(file)
            assert "features" in data
        except Exception as exc:  # pylint: disable=broad-except
            raise ValueError("Given GeoJSON has wrong format") from exc
        res = pd.DataFrame(
            (entry["properties"] | {"geometry": json.dumps(entry["geometry"])}) for entry in data["features"]
        )
        if default_values is not None:
            res = replace_with_default(res, default_values)
        if needed_columns is not None:
            res = res[needed_columns]
        return res.dropna(how="all").reset_index(drop=True).replace({nan: None})


def load_objects_json(
    filename: str, default_values: dict[str, Any] | None = None, needed_columns: Iterable[str] | None = None
) -> pd.DataFrame:
    """Load objects as DataFrame from json by calling pd.read_json.

    Calls `replace_with_default` after load if `default_values` is present
    """
    res: pd.DataFrame = pd.read_json(filename)
    if default_values is not None:
        res = replace_with_default(res, default_values)
    if needed_columns is not None:
        res = res[needed_columns]
    return res.dropna(how="all").reset_index(drop=True).replace({nan: None})


def load_objects_csv(
    filename: str, default_values: dict[str, Any] | None = None, needed_columns: Iterable[str] | None = None
) -> pd.DataFrame:
    """Load objects as DataFrame from csv by calling pd.read_csv.

    Calls `replace_with_default` after load if `default_values` is present
    """
    res: pd.DataFrame = pd.read_csv(filename)
    if default_values is not None:
        res = replace_with_default(res, default_values)
    if needed_columns is not None:
        res = res[needed_columns]
    return res.dropna(how="all").reset_index(drop=True).replace({nan: None})


def load_objects_xlsx(
    filename: str, default_values: dict[str, Any] | None = None, needed_columns: Iterable[str] | None = None
) -> pd.DataFrame:
    """Load objects as DataFrame from xlsx by calling pd.read_excel
    (need to install `openpyxl` Pyhton module installed).

    Calls `replace_with_default` after load if `default_values` is present
    """
    res: pd.DataFrame = pd.read_excel(filename, engine="openpyxl")
    if default_values is not None:
        res = replace_with_default(res, default_values)
    if needed_columns is not None:
        res = res[needed_columns]
    return res.dropna(how="all").reset_index(drop=True).replace({nan: None})


def load_objects_excel(
    filename: str, default_values: dict[str, Any] | None = None, needed_columns: Iterable[str] | None = None
) -> pd.DataFrame:
    """Load objects as DataFrame from xls or ods by calling pd.read_excel
    (need to install `xlrd` Pyhton module installed for xls and `odfpy` for ods).

    Calls `replace_with_default` after load if `default_values` is present
    """
    res: pd.DataFrame = pd.read_excel(filename)
    if default_values is not None:
        res = replace_with_default(res, default_values)
    if needed_columns is not None:
        res = res[needed_columns]
    return res.dropna(how="all").reset_index(drop=True).replace({nan: None})


def load_objects(
    filename: str, default_values: dict[str, Any] | None = None, needed_columns: Iterable[str] | None = None
) -> pd.DataFrame:
    """Load objects as DataFrame from the given fie (csv, xlsx, xls, ods, json or geojson)."""
    funcs = {
        "csv": load_objects_csv,
        "xlsx": load_objects_xlsx,
        "xls": load_objects_excel,
        "ods": load_objects_excel,
        "json": load_objects_json,
        "geojson": load_objects_geojson,
    }
    try:
        return funcs[filename[filename.rfind(".") + 1 :]](filename, default_values, needed_columns)
    except KeyError as exc:
        raise ValueError(f'File extension "{filename[filename.rfind(".") + 1:]}" is not supported') from exc
