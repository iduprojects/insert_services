# pylint: disable=too-many-arguments,too-many-locals,
"""Buildings insertion logic is defined here."""
from __future__ import annotations

import json
import os
import time
import traceback
import warnings
from dataclasses import fields as dc_fields
from numbers import Number
from typing import Callable, Literal

import pandas as pd
import psycopg2
from frozenlist import FrozenList
from loguru import logger
from numpy import nan
from tqdm import tqdm

from platform_management.cli.common import SingleObjectStatus
from platform_management.dto import BuildingInsertionMapping
from platform_management.utils import simplify_data

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

_buildings_columns_used = list(
    (
        "central_electro"
        if f.name == "central_electricity"
        else "failure"
        if f.name == "is_failing"
        else "central_hotwater"
        if f.name == "central_hot_water"
        else f.name
    )
    for f in dc_fields(BuildingInsertionMapping)
    if f.name not in ("geometry", "osm_id", "modeled")
)
_buildings_mappings_used = list(
    f.name for f in dc_fields(BuildingInsertionMapping) if f.name not in ("geometry", "osm_id", "modeled")
)


def insert_building(
    cur: psycopg2.extensions.cursor,
    row: pd.Series,
    physical_object_id: int,
    mapping: BuildingInsertionMapping,
    properties_mapping: dict[str, str],
    commit: bool = True,
) -> tuple[int, int]:
    """Insert building.

    Returns identifier of the inserted building and physical object.
    """
    building_properties = {
        db_name: row[row_name]
        for db_name, row_name in properties_mapping.items()
        if row_name in row and row[row_name] is not None and row[row_name] != ""
    }
    cur.execute(
        "INSERT INTO buildings (physical_object_id, " + ", ".join(_buildings_columns_used) + ", properties)"
        " VALUES (" + ", ".join(("%s",) * (len(_buildings_columns_used) + 2)) + ") RETURNING id",
        (
            physical_object_id,
            *(row.get(getattr(mapping, f)) for f in _buildings_mappings_used),
            json.dumps(building_properties),
        ),
    )
    building_id = cur.fetchone()[0]  # type: ignore

    if row.get(mapping.modeled, None) is not None:
        mapping_doc_db = {
            doc: _buildings_columns_used[_buildings_mappings_used.index(db)]
            for db, doc in vars(mapping).items()
            if doc is not None and db in _buildings_mappings_used
        }
        modeled_columns_doc = set(
            mapping_doc_db[column.strip()] for column in row[mapping.modeled].split(",") if column in mapping_doc_db
        )
        if len(modeled_columns_doc) != 0:
            cur.execute(
                "UPDATE buildings SET modeled = %s::jsonb WHERE id = %s",
                (json.dumps({field: 1 for field in modeled_columns_doc}), building_id),
            )
    if commit:
        cur.execute("SAVEPOINT previous_object")
    return building_id


def update_building(
    cur: psycopg2.extensions.cursor,
    row: pd.Series,
    building_id: int,
    mapping: BuildingInsertionMapping,
    properties_mapping: dict[str, str],
    commit: bool = True,
) -> bool:
    """Update building data.

    Returns True if building was updated (some properties were different), False otherwise.
    """
    cur.execute(
        "SELECT "
        + ", ".join(_buildings_columns_used)
        + ", physical_object_id, modeled, properties FROM buildings WHERE id = %s",
        (building_id,),
    )
    res: tuple
    db_modeled: dict[str, Literal[1]]
    *res, physical_object_id, db_modeled, db_properties = cur.fetchone()  # type: ignore
    if row[mapping.geometry].startswith("{"):
        cur.execute(
            "SELECT geometry, (SELECT ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)) FROM physical_objects WHERE id = %s",
            (row[mapping.geometry], physical_object_id),
        )
        geom, geom_new = cur.fetchone()
    else:
        cur.execute("SELECT geometry FROM physical_objects WHERE id = %s", (physical_object_id,))
        geom = cur.fetchone()[0]
        geom_new = row[mapping.geometry]
    change = list(
        filter(
            lambda c_v_nw: c_v_nw[1] != c_v_nw[2] and c_v_nw[2] is not None and c_v_nw[2] != "",
            zip(
                _buildings_columns_used,
                (simplify_data(value) for value in res),
                (simplify_data(row.get(getattr(mapping, f))) for f in _buildings_mappings_used),
            ),
        )
    )
    if len(change) > 0:
        logger.trace("Building id={} changes: {}", building_id, change)
    if len(change) > 0:
        cur.execute(
            f'UPDATE buildings SET {", ".join(list(map(lambda x: x[0] + "=%s", change)))} WHERE id = %s',
            list(map(lambda x: x[2], change)) + [building_id],
        )

    building_properties = {
        db_name: row[row_name]
        for db_name, row_name in properties_mapping.items()
        if row_name in row and row[row_name] is not None and row[row_name] != ""
    }
    if db_properties != building_properties:
        cur.execute(
            "UPDATE buildings SET properties = properties || %s::jsonb WHERE id = %s",
            (json.dumps(building_properties), building_id),
        )

    if row.get(mapping.modeled, None) is not None:
        mapping_doc_db = {
            doc: _buildings_columns_used[_buildings_mappings_used.index(db)]
            for db, doc in vars(mapping).items()
            if doc is not None and db in _buildings_mappings_used
        }
        modeled_columns_doc = set(
            mapping_doc_db[column.strip()] for column in row[mapping.modeled].split(",") if column in mapping_doc_db
        )
        modeled_columns_db = set(db_modeled.keys())
        to_add = modeled_columns_doc - modeled_columns_db
        to_remove = {
            db_field
            for db_field in (modeled_columns_db - modeled_columns_doc)
            if row.get(getattr(mapping, _buildings_mappings_used[_buildings_columns_used.index(db_field)])) is not None
        }
        if len(to_add) != 0 or len(to_remove) != 0:
            cur.execute(
                "UPDATE buildings SET modeled = %s::jsonb WHERE id = %s",
                (json.dumps({field: 1 for field in ((modeled_columns_db | to_add) - to_remove)}), building_id),
            )

    if geom != geom_new:
        logger.trace("Updating geometry: {} -> {}", geom_new, geom)
        cur.execute("UPDATE physical_objects SET geometry = %s WHERE id = %s", (geom_new, physical_object_id))

    if commit:
        cur.execute("SAVEPOINT previous_object")

    return len(change) != 0 or db_properties != building_properties or geom != geom_new


def get_properties_keys(
    cur_or_conn: psycopg2.extensions.connection | psycopg2.extensions.cursor,
    city: str,
    living: bool,
    non_living: bool,
) -> list[str]:
    """Return a list of properties keys of buildings in a given city."""
    if isinstance(cur_or_conn, psycopg2.extensions.connection):
        cur = cur_or_conn.cursor()
    else:
        cur = cur_or_conn
    try:
        cur.execute(
            "WITH phys AS ("
            "   SELECT p.id FROM physical_objects p"
            "       JOIN cities c ON p.city_id = c.id"
            "   WHERE c.name = %(city)s"
            "       OR c.code = %(city)s"
            "       OR c.id::varchar = %(city)s"
            ")"
            " SELECT DISTINCT jsonb_object_keys(properties)"
            " FROM buildings"
            " WHERE physical_object_id IN (SELECT id FROM phys) AND "
            + (
                " is_living = true"
                if living and not non_living
                else "is_living = false"
                if non_living and not living
                else "is_living IS null"
                if not non_living and not living
                else "is_living IS NOT null"
            )
            + " ORDER BY 1",
            {"city": city},
        )
        return [r[0] for r in cur.fetchall()]
    finally:
        if isinstance(cur_or_conn, psycopg2.extensions.connection):
            cur.close()


def add_buildings(  # pylint: disable=too-many-branches,too-many-statements
    conn: psycopg2.extensions.connection,
    buildings_df: pd.DataFrame,
    city_name: str,
    mapping: BuildingInsertionMapping,
    properties_mapping: dict[str, str] = frozenset({}),
    address_prefixes: list[str] = FrozenList(["Россия, Санкт-Петербург"]),
    new_prefix: str = "",
    commit: bool = True,
    verbose: bool = False,
    log_n: int = 200,
    callback: Callable[[SingleObjectStatus], None] | None = None,
) -> pd.DataFrame:
    """Insert buildings to database.

    Input:

        - `conn` - connection for the database
        - `buildings_df` - DataFrame containing buildings
        - `city_name` - name of the city to add objects to. Must be created in the database
        - `mapping` - BuildingInsertionMapping of namings in the database and namings in the DataFrame columns
        - `properties_mapping` - dict[str, str] of additional properties namings in the
        buildings.properties and namings in the DataFrame columns
        - `address_prefix` - list of possible prefixes (will be sorted by length)
        - `new_prefix` - unified prefix for all of the inserted objects
        - `commit` - True to commit changes, False for dry run, only resulting DataFrame is returned
        - `verbose` - True to output traceback with errors, False for only error messages printing
        - `log_n` - number of inserted/updated services to log after each
        - `callback` - optional callback function which is called after every service insertion

    Return:

        - dataframe of objects with "result" and "building_id" columns added
    """

    def call_callback(status: str) -> None:
        """
        Execute callback function with a parameter corresponding to the given status.
        """
        if callback is not None:
            if status.startswith(("Геометрия в поле", "Пропущен (отсутствует", "Пропущен, вызывает ошибку")):
                callback(SingleObjectStatus.ERROR)
            elif status.startswith("Пропущен"):
                callback(SingleObjectStatus.SKIPPED)
            elif "вставлен" in status:
                callback(SingleObjectStatus.INSERTED)
            elif status.startswith("Обновл"):
                callback(SingleObjectStatus.UPDATED)
            elif "совпадает" in status:
                callback(SingleObjectStatus.UNCHANGED)
            else:
                callback(SingleObjectStatus.ERROR)
                logger.warning("Could not get the category of result based on status: {}", results[i - 1])

    logger.info(f"Вставка зданий, всего {buildings_df.shape[0]} объектов")
    logger.info(f'Город вставки - "{city_name}". Список префиксов: {address_prefixes}, новый префикс: "{new_prefix}"')

    buildings_df = buildings_df.copy().replace({nan: None})
    for i in range(buildings_df.shape[1]):
        buildings_df.iloc[:, i] = pd.Series(
            map(
                lambda x: float(x.replace(",", "."))
                if isinstance(x, str) and len(x) != 1 and x.count(",") == 1 and x.replace(",", "1").isnumeric()
                else x,
                buildings_df.iloc[:, i],
            ),
            dtype=object,
        )
    for boolean_mapping in (
        mapping.is_living,
        mapping.is_failing,
        mapping.central_electricity,
        mapping.central_gas,
        mapping.central_heating,
        mapping.central_hot_water,
        mapping.central_water,
    ):
        if boolean_mapping in buildings_df.columns:
            buildings_df.loc[:, boolean_mapping] = pd.Series(
                map(
                    lambda x: (isinstance(x, str) and x.lower().strip() in ("1", "y", "t", "true"))
                    or (isinstance(x, Number) and x - 0 > 1e-5),
                    buildings_df.loc[:, boolean_mapping],
                ),
                dtype=object,
            )
    if mapping.address in buildings_df.columns:
        buildings_df[mapping.address] = buildings_df[mapping.address].apply(
            lambda x: x.replace("?", "").strip() if isinstance(x, str) else None
        )
    updated = 0  # number of updated buildings which were already present
    unchanged = 0  # number of buildings already present in the database with the same properties
    added, skipped = 0, 0
    skip_logs = False
    results: list[str] = list(("",) * buildings_df.shape[0])
    building_ids: list[int] = [-1 for _ in range(buildings_df.shape[0])]
    address_prefixes = sorted(address_prefixes, key=lambda s: -len(s))
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM cities WHERE name = %(city)s or code = %(city)s or id::varchar = %(city)s",
            {"city": city_name},
        )
        city_id = cur.fetchone()
        if city_id is None:
            logger.error(f'Заданный город "{city_name}" отсутствует в базе данных')
            buildings_df["result"] = pd.Series(
                [f'Город "{city_name}" отсутсвует в базе данных'] * buildings_df.shape[0], index=buildings_df.index
            )
            buildings_df["building_id"] = pd.Series([-1] * buildings_df.shape[0], index=buildings_df.index)
            return buildings_df
        city_id: int = city_id[0]

        if commit:
            cur.execute("SAVEPOINT previous_object")
        i = 0
        try:
            for i, (_, row) in enumerate(tqdm(buildings_df.iterrows(), total=buildings_df.shape[0])):
                if i > 0:
                    call_callback(results[i - 1])
                if i % log_n == 0:
                    logger.opt(colors=True).info(
                        "Обработано {:4} зданий из {}: <green>{} добавлены</green>, <yellow>{} обновлены</yellow>,"
                        " <blue>{} оставлены без изменений</blue>, <red>{} пропущены</red>",
                        i,
                        buildings_df.shape[0],
                        added,
                        updated,
                        unchanged,
                        skipped,
                    )
                    if commit:
                        conn.commit()
                        cur.execute("SAVEPOINT previous_object")
                try:
                    if mapping.geometry not in row:
                        results[i] = "Пропущен (отсутствует геометрия)"
                        skipped += 1
                        continue
                    try:
                        cur.execute(
                            "WITH geom as (SELECT ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326) geometry)"
                            " SELECT geometry, ST_Centroid(geometry)"
                            " FROM geom",
                            (row[mapping.geometry],),
                        )
                        geometry, center = cur.fetchone()  # type: ignore
                    except Exception as exc:  # pylint: disable=broad-except
                        logger.trace("invalid geometry for row={}: {!r}", i, exc)
                        results[i] = f'Геометрия в поле "{mapping.geometry}" некорректна'
                        skipped += 1
                        if commit:
                            cur.execute("ROLLBACK TO previous_object")
                        else:
                            conn.rollback()
                        continue
                    address: str | None = None
                    if mapping.address in row and row[mapping.address] is not None and row[mapping.address] != "":
                        for address_prefix in address_prefixes:
                            if row.get(mapping.address, "").startswith(tuple(address_prefixes)):
                                address = row.get(mapping.address)[len(address_prefix) :].strip(", ")
                                break
                        else:
                            if len(address_prefixes) == 1:
                                results[i] = f'Пропущен (адрес не начинается с "{address_prefixes[0]}")'
                            else:
                                results[
                                    i
                                ] = f"Пропущен (адрес не начинается ни с одного из {len(address_prefixes)} префиксов)"
                            skipped += 1
                            continue

                    cur.execute(
                        "SELECT (SELECT id FROM municipalities WHERE city_id = %(city_id)s"
                        "   AND ST_Within(%(center)s, geometry)),"
                        " (SELECT id FROM administrative_units WHERE city_id = %(city_id)s"
                        "   AND ST_Within(%(center)s, geometry))",
                        {"city_id": city_id, "center": center},
                    )
                    municipality_id: int | None
                    administrative_unit_id: int | None
                    municipality_id, administrative_unit_id = cur.fetchone()

                    build_id: int
                    if address is not None and address != "":
                        cur.execute(
                            "SELECT b.id FROM"
                            "   (SELECT center, id FROM physical_objects WHERE city_id = %s) phys"
                            "       JOIN buildings b ON b.physical_object_id = phys.id"
                            " WHERE b.address LIKE %s AND"
                            "   ST_Distance(phys.center::geography, %s::geography) < 100"
                            " LIMIT 1",
                            (city_id, f"%{address}", center),
                        )
                        res = cur.fetchone()  # type: ignore
                    else:
                        res = None
                    if res is not None:
                        # if building with the same address found and distance between point
                        # and the center of geometry is less than 100m
                        build_id = res
                        if update_building(cur, row, build_id, mapping, properties_mapping, commit):
                            updated += 1
                            results[i] = f"Здание обновлено по совпадению адреса (build_id = {build_id})"
                        else:
                            unchanged += 1
                            results[i] = f"Здание полностью совпадает с информацией в БД (build_id = {build_id})"
                        continue
                    # if no building with the same address found or distance is
                    # too high (address is wrong or it's not a concrete house)
                    cur.execute(
                        "WITH geom_table AS (SELECT %s::geometry AS geom)"
                        " SELECT"
                        "   build.id,"
                        "   build.address,"
                        "   CASE"
                        "       WHEN ST_GeometryType(geometry) = 'ST_Point'"
                        "           THEN 1.0"
                        "           ELSE ST_Area(ST_Intersection((SELECT geom from geom_table), geometry)) /"
                        "               LEAST(ST_Area((SELECT geom FROM geom_table)), ST_Area(geometry))"
                        "   END AS coverage"
                        " FROM (SELECT id, geometry, administrative_unit_id, municipality_id"
                        "       FROM physical_objects WHERE city_id = %s) phys"
                        "   JOIN buildings build ON build.physical_object_id = phys.id"
                        " WHERE"
                        + (" municipality_id = %s" if municipality_id is not None else "")
                        + (" AND " if municipality_id is not None else "")
                        + (" administrative_unit_id = %s" if administrative_unit_id is not None else "")
                        + (" AND " if administrative_unit_id is not None else "")
                        + " ST_Intersects((SELECT geom FROM geom_table), geometry)"
                        " ORDER BY 3 DESC",
                        list(
                            filter(
                                lambda x: x is not None,
                                (geometry, city_id, municipality_id, administrative_unit_id),
                            )
                        ),
                    )
                    res = cur.fetchall()
                    if len(res) > 0:  # if building geometry intersects with other building(s)
                        # if maximum intersection area is more than 30% of smaller geometry - update existing building
                        if res[0][2] > 0.3:
                            build_id, address, intersection_area = res[0]
                            building_ids[i] = build_id
                            if len(res) > 1:
                                if len(res) > 2:
                                    cur.execute(
                                        "WITH b AS (SELECT physical_object_id FROM buildings WHERE id IN %s)"
                                        " SELECT ST_Difference(%s, ("
                                        "   SELECT ST_Union(geometry)"
                                        "   FROM physical_objects"
                                        "   WHERE id IN (SELECT physical_object_id FROM b)"
                                        "))",
                                        (tuple(r[0] for r in res[1:]), geometry),
                                    )
                                else:
                                    cur.execute(
                                        "SELECT ST_Difference(%s, ("
                                        "   SELECT geometry"
                                        "   FROM physical_objects"
                                        "   WHERE id = (SELECT physical_object_id FROM buildings WHERE id = %s)"
                                        "))",
                                        (geometry, res[1][0]),
                                    )
                                row[mapping.geometry] = cur.fetchone()[0]
                            if update_building(cur, row, build_id, mapping, properties_mapping, commit):
                                updated += 1
                                results[i] = (
                                    f"Здание обновлено, адрес в БД: '{address}' (build_id = {build_id},"
                                    f" %_пересечения = {intersection_area * 100:.1f})"
                                )
                            else:
                                unchanged += 1
                                results[i] = (
                                    f"Здание полностью совпадает с информацией в БД (build_id = {build_id},"
                                    f" %_пересечения = {intersection_area * 100:.1f})"
                                )
                            continue
                        if len(res) > 1:
                            cur.execute(
                                "WITH b AS (SELECT physical_object_id FROM buildings WHERE id IN %s)"
                                " SELECT ST_Difference(%s, ("
                                "   SELECT ST_Union(geometry)"
                                "   FROM physical_objects"
                                "   WHERE id IN (SELECT physical_object_id FROM b)"
                                "))",
                                (tuple(r[0] for r in res), geometry),
                            )
                        else:
                            cur.execute(
                                "SELECT ST_Difference(%s, ("
                                "   SELECT geometry"
                                "   FROM physical_objects"
                                "   WHERE id = (SELECT physical_object_id FROM buildings WHERE id = %s)"
                                "))",
                                (geometry, res[0][0]),
                            )
                        geometry = cur.fetchone()[0]

                    # building insertion
                    cur.execute(
                        "INSERT INTO physical_objects (osm_id, geometry, center, city_id,"
                        "   municipality_id, administrative_unit_id, block_id)"
                        " VALUES"
                        " (%s, %s, %s, %s, %s, %s,"
                        "       (SELECT id FROM blocks WHERE city_id = %s AND ST_Within(%s, geometry) LIMIT 1)"
                        " )"
                        " RETURNING id",
                        (
                            row.get(mapping.osm_id),
                            geometry,
                            center,
                            city_id,
                            municipality_id,
                            administrative_unit_id,
                            city_id,
                            center,
                        ),
                    )
                    phys_id: int = cur.fetchone()[0]  # type: ignore
                    building_ids[i] = insert_building(
                        cur,
                        row,
                        phys_id,
                        mapping,
                        properties_mapping,
                        commit,
                    )  # type: ignore
                    results[i] = f"Здание добавлено, id={building_ids[i]} (physical_object_id={phys_id})"
                    added += 1
                except Exception as exc:  # pylint: disable=broad-except
                    logger.error("Произошла ошибка: {!r}", exc, traceback=True)
                    if verbose:
                        logger.error(f"Traceback:\n{traceback.format_exc()}")
                    if commit:
                        cur.execute("ROLLBACK TO previous_object")
                    else:
                        conn.rollback()
                    results[i] = f"Пропущен, вызывает ошибку: {exc}"
                    skipped += 1

        except KeyboardInterrupt:
            logger.warning("Прерывание процесса пользователем")
            logger.opt(colors=True).info(
                "Обработано {:4} зданий из {}: <green>{} добавлены</green>, <yellow>{} обновлены</yellow>,"
                " <blue>{} оставлены без изменений</blue>, <red>{} пропущены</red>",
                i,
                buildings_df.shape[0],
                added,
                updated,
                unchanged,
                skipped,
            )
            if commit:
                choice = input("Сохранить внесенные на данный момент изменения? (y/д/1 | n/н/0 | s/л/-): ")
                if choice.lower().strip().startswith(("y", "д", "1")):
                    conn.commit()
                    logger.success("Сохранение внесенных изменений")
                elif choice.lower().strip().startswith(("s", "л", "-")):
                    logger.info("Отмена изменений и пропуск записи лога")
                    conn.rollback()
                    skip_logs = True
                else:
                    logger.warning("Отмена внесенных изменений")
                    conn.rollback()
            for j in range(i, buildings_df.shape[0]):
                results[j] = "Пропущен (отмена пользователем)"
        else:
            if commit:
                conn.commit()
    call_callback(results[-1])

    buildings_df["result"] = pd.Series(results, index=buildings_df.index)
    buildings_df["building_id"] = pd.Series(building_ids, index=buildings_df.index)
    logger.success(f'Вставка зданий в город "{city_name}" завершена')
    logger.opt(colors=True).info(
        "Обработано {:4} зданий из {}: <green>{} добавлены</green>, <yellow>{} обновлены</yellow>,"
        " <blue>{} оставлены без изменений</blue>, <red>{} пропущены</red>",
        i,
        buildings_df.shape[0],
        added,
        updated,
        unchanged,
        skipped,
    )
    if not skip_logs:
        filename = f"buildings_insertion_{conn.info.host}_{conn.info.port}_{conn.info.dbname}.xlsx"
        sheet_name = f'{city_name}_{time.strftime("%Y-%m-%d %H_%M-%S")}'
        logger.opt(colors=True).info(
            "Сохранение лога в файл Excel (нажмите Ctrl+C для отмены,"
            " <magenta>но это может повредить файл лога</magenta>)"
        )
        try:
            with pd.ExcelWriter(  # pylint: disable=abstract-class-instantiated
                filename, mode=("a" if os.path.isfile(filename) else "w"), engine="openpyxl"
            ) as writer:
                buildings_df.to_excel(writer, sheet_name)
            logger.info(f'Лог вставки сохранен в файл "{filename}", лист "{sheet_name}"')
        except Exception as exc:  # pylint: disable=broad-except
            newlog = f"buildings_insertion_{int(time.time())}.xlsx"
            logger.error(
                f'Ошибка при сохранении лога вставки в файл "{filename}",'
                f' лист "{sheet_name}": {exc!r}. Попытка сохранения с именем {newlog}'
            )
            try:
                buildings_df.to_excel(newlog, sheet_name)
                logger.success("Сохранение прошло успешно")
            except Exception as exc_1:  # pylint: disable=broad-except
                logger.error(f"Ошибка сохранения лога: {exc_1!r}")
        except KeyboardInterrupt:
            logger.warning(f'Отмена сохранения файла лога, файл "{filename}" может быть поврежден')
    return buildings_df
