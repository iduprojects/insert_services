# pylint: disable=too-many-arguments,too-many-locals,
"""Administrative units and municipalities insertion logic is defined here."""
from __future__ import annotations

import operator
import os
import time
import traceback
import warnings
from enum import Enum
from functools import reduce
from typing import Callable

import pandas as pd
import psycopg2
from loguru import logger
from numpy import nan
from tqdm import tqdm

from platform_management.cli.common import SingleObjectStatus
from platform_management.dto import AdmDivisionInsertionMapping

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")


class AdmDivisionType(Enum):
    """Administrative division unit type."""

    ADMINISTRATIVE_UNIT = "ADMINISTRATIVE_UNIT"
    MUNICIPALITY = "MUNICIPALITY"


def insert_administrative_unit(
    cur: psycopg2.extensions.cursor,
    row: pd.Series,
    mapping: AdmDivisionInsertionMapping,
    administrative_unit_types: dict[str, int],
    city_id: int,
    commit: bool = True,
) -> int:
    """Insert administrative unit.

    Returns an identifier of the added administrative_units.
    """
    assert row[mapping.type_name] in administrative_unit_types, "Given adm division type is not in the database"
    cur.execute(
        "WITH geometry_t AS (SELECT ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326) geometry),"
        " center_t AS (SELECT ST_Centroid(geometry) center FROM geometry_t)"
        " INSERT INTO administrative_units (parent_id, city_id, type_id, name, geometry,"
        "   center, population)"
        " VALUES ("
        "   (SELECT id FROM administrative_units WHERE name = %s),"
        "   %s,"
        "   %s,"
        "   %s,"
        "   (SELECT geometry FROM geometry_t),"
        "   (SELECT center FROM center_t),"
        "   %s,"
        "   (SELECT id FROM municipalities WHERE city_id = %s AND name = %s)"
        ") RETURNING id",
        (
            row[mapping.geometry],
            row.get(mapping.parent_same_type),
            city_id,
            administrative_unit_types[row[mapping.type_name].lower()],
            row[mapping.name],
            row.get(mapping.population),
            city_id,
        ),
    )
    idx = cur.fetchone()[0]

    if commit:
        cur.execute("SAVEPOINT previous_object")
    return idx


def insert_municipality(
    cur: psycopg2.extensions.cursor,
    row: pd.Series,
    mapping: AdmDivisionInsertionMapping,
    municipalities_types: dict[str, int],
    city_id: int,
    commit: bool = True,
) -> int:
    """Insert municipality.

    Returns an identifier of the added municipality.
    """
    assert row[mapping.type_name] in municipalities_types, "Given adm division type is not in the database"
    cur.execute(
        "WITH geometry_t AS (SELECT ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326) geometry),"
        " center_t AS (SELECT ST_Centroid(geometry) center FROM geometry_t)"
        " INSERT INTO municipalities (parent_id, city_id, type_id, name, geometry,"
        "   center, population, admin_unit_parent_id)"
        " VALUES ("
        "   (SELECT id FROM municipalities WHERE name = %s),"
        "   %s,"
        "   %s,"
        "   %s,"
        "   (SELECT geometry FROM geometry_t),"
        "   (SELECT center FROM center_t),"
        "   %s,"
        "   (SELECT id FROM administrative_units WHERE city_id = %s AND name = %s)"
        ") RETURNING id",
        (
            row[mapping.geometry],
            row.get(mapping.parent_same_type),
            city_id,
            municipalities_types[row[mapping.type_name]],
            row[mapping.name],
            row.get(mapping.population),
            city_id,
            row.get(mapping.parent_other_type),
        ),
    )
    idx = cur.fetchone()[0]

    if commit:
        cur.execute("SAVEPOINT previous_object")
    return idx


def update_administrative_unit(
    cur: psycopg2.extensions.cursor,
    administrative_unit_id: int,
    row: pd.Series,
    mapping: AdmDivisionInsertionMapping,
    administrative_unit_types: dict[str, int],
    commit: bool = True,
) -> bool:
    """Update administrative_unit data.

    Returns True if data was updated, False otherwise.
    """
    assert row[mapping.type_name] in administrative_unit_types, "Given adm division type is not in the database"
    cur.execute(
        "SELECT"
        "   city_id,"
        "   ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),"
        "   (SELECT name FROM administrative_units WHERE id = au.parent_id),"
        "   (SELECT lower(full_name) FROM administrative_unit_types WHERE id = au.type_id),"
        "   name,"
        "   geometry,"
        "   population"
        " FROM administrative_units au"
        " WHERE id = %s",
        (row[mapping.geometry], administrative_unit_id),
    )
    city_id, geom_str, *data = cur.fetchone()
    db_fields = []
    preparations = []
    values = []
    if row.get(mapping.parent_same_type) is not None and row[mapping.parent_same_type] != data[0]:
        db_fields.append("parent_id")
        preparations.append(
            "(SELECT id FROM administrative_units WHERE city = %(city_id)s AND name = %(parent_same_type)s)"
        )
        values.append({"city_id": city_id, "parent_same_type": row[mapping.parent_same_type]})

    if row[mapping.type_name].lower() != data[1]:
        db_fields.append("type_id")
        preparations.append("%(administrative_unit_type_id)s")
        values.append({"administrative_unit_type_id": administrative_unit_types[row[mapping.type_name]]})

    if row[mapping.name] is not None and row[mapping.name] != data[2]:
        db_fields.append("name")
        preparations.append("%(name)s")
        values.append({"name": row[mapping.name]})

    if geom_str != data[3]:
        db_fields.extend(["geometry", "center"])
        preparations.extend(["%(geometry)s", "(SELECT ST_Centroid(%(geometry)s))"])
        values.append({"geometry": row[mapping.geometry]})

    if row.get(mapping.population) is not None and row[mapping.population] != data[4]:
        db_fields.append("population")
        preparations.append("%(population)s")
        values.append({"population": row[mapping.population]})

    if len(db_fields) == 0:
        return False
    cur.execute(
        "UPDATE administrative_units SET "
        + ", ".join(f"{k} = {v}" for k, v in zip(db_fields, preparations))
        + " WHERE id = %(administrative_unit_id)s",
        reduce(operator.ior, values, {}) | {"administrative_unit_id": administrative_unit_id},
    )

    if commit:
        cur.execute("SAVEPOINT previous_object")
    return True


def update_municipality(
    cur: psycopg2.extensions.cursor,
    municipality_id: int,
    row: pd.Series,
    mapping: AdmDivisionInsertionMapping,
    municipality_types: dict[str, int],
    commit: bool = True,
) -> bool:
    """Update administrative_unit data.

    Returns True if data was updated, False otherwise.
    """
    assert row[mapping.type_name] in municipality_types, "Given adm division type is not in the database"
    cur.execute(
        "SELECT"
        "   city_id,"
        "   ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),"
        "   (SELECT name FROM municipalities WHERE id = mo.parent_id),"
        "   (SELECT name FROM municipality_types WHERE id = mo.type_id),"
        "   name,"
        "   geometry,"
        "   population,"
        "   (SELECT name FROM administrative_units WHERE id = mo.admin_unit_parent_id)"
        " FROM municipalities mo"
        " WHERE id = %s",
        (row[mapping.geometry], municipality_id),
    )
    city_id, geom_str, *data = cur.fetchone()
    db_fields = []
    preparations = []
    values = []
    if row.get(mapping.parent_same_type) is not None and row[mapping.parent_same_type] != data[0]:
        db_fields.append("parent_id")
        preparations.append("(SELECT id FROM municipalities WHERE city = %(city_id)s AND name = %(parent_same_type)s)")
        values.append({"city_id": city_id, "parent_same_type": row[mapping.parent_same_type]})

    if row[mapping.type_name] is not None and row[mapping.type_name] != data[1]:
        db_fields.append("type_id")
        preparations.append("%(municipality_type_id)s")
        values.append({"municipality_type_id": municipality_types[row[mapping.type_name]]})

    if row[mapping.name] is not None and row[mapping.name] != data[2]:
        db_fields.append("name")
        preparations.append("%(name)s")
        values.append({"name": row[mapping.name]})

    if geom_str != data[3]:
        db_fields.extend(["geometry", "center"])
        preparations.extend(["%(geometry)", "(SELECT ST_Centroid(%(geometry)s)"])
        values.append({"geometry": row[mapping.name]})

    if row.get(mapping.population) is not None and row[mapping.population] != data[4]:
        db_fields.append("population")
        preparations.append("%(population)s")
        values.append({"population": row[mapping.population]})

    if row.get(mapping.parent_other_type) is not None and row[mapping.parent_other_type] != data[5]:
        db_fields.append("admin_unit_parent_id")
        preparations.append(
            "(SELECT id FROM administrative_units WHERE city_id = %(city_id)s AND name = %(parent_other_type)s)"
        )
        values.append({"city_id": city_id, "parent_other_type": row[mapping.parent_other_type]})

    if len(db_fields) == 0:
        return False
    cur.execute(
        "UPDATE municipalities SET "
        + ", ".join(f"{k} = {v}" for k, v in zip(db_fields, preparations))
        + " WHERE id = %(municipality_id)s",
        reduce(operator.ior, values, {}) | {"municipality_id": municipality_id},
    )

    if commit:
        cur.execute("SAVEPOINT previous_object")
    return True


def add_adm_division(  # pylint: disable=too-many-branches,too-many-statements
    conn: psycopg2.extensions.connection,
    adms_df: pd.DataFrame,
    city_name: str,
    division_type: AdmDivisionType,
    mapping: AdmDivisionInsertionMapping,
    commit: bool = True,
    verbose: bool = False,
    log_n: int = 200,
    callback: Callable[[SingleObjectStatus], None] | None = None,
) -> pd.DataFrame:
    """Insert administrative divition units to database.

    Input:

        - `conn` - connection for the database
        - `adms_df` - DataFrame containing objects
        - `city_name` - name of the city to add objects to. Must be created in the database
        - `division_type` - enumeration of administrative division type to insert
        - `mapping` - AdmDivisionInsertionMapping of namings in the database and namings in the DataFrame columns
        - `commit` - True to commit changes, False for dry run, only resulting DataFrame is returned
        - `verbose` - True to output traceback with errors, False for only error messages printing
        - `log_n` - number of inserted/updated services to log after each
        - `callback` - optional callback function which is called after every service insertion

    Return:

        - dataframe of objects with "result" and "adm_id" columns added
    """
    if mapping.geometry not in adms_df.columns:
        logger.error('Заданный столбец геометри "{}" отсутствует в переданных данных', mapping.geometry)
    if mapping.type_name not in adms_df.columns:
        logger.error(
            'Заданный столбец типа административной единицы/муниципального образования "{}"'
            "отсутствует в переданных данных",
            mapping.type_name,
        )

    def call_callback(status: str) -> None:
        """
        Execute callback function with a parameter corresponding to the given status.
        """
        if callback is not None:
            if status.startswith(("Геометрия в поле", "Пропущен (отсутствует", "Пропущен, вызывает ошибку")):
                callback(SingleObjectStatus.ERROR)
            elif status.startswith("Пропущен"):
                callback(SingleObjectStatus.SKIPPED)
            elif status.startswith("Добавлен"):
                callback(SingleObjectStatus.INSERTED)
            elif status.startswith("Обновлен"):
                callback(SingleObjectStatus.UPDATED)
            elif "совпадает" in status:
                callback(SingleObjectStatus.UNCHANGED)
            else:
                callback(SingleObjectStatus.ERROR)
                logger.warning("Could not get the category of result based on status: {}", results[i - 1])

    if division_type == AdmDivisionType.ADMINISTRATIVE_UNIT:
        logger.info(f'Вставка административных единиц в город "{city_name}," всего {adms_df.shape[0]} объектов')
    else:
        logger.info(
            f'Вставка муниципальных образований единиц в город "{city_name}," всего {adms_df.shape[0]} объектов'
        )

    adms_df = adms_df.copy().replace({nan: None})

    updated = 0  # number of updated adms which were already present in the database
    unchanged = 0  # number of amds already present in the database with the same properties
    added, skipped = 0, 0
    results: list[str] = list(("",) * adms_df.shape[0])
    adm_ids: list[int] = [-1 for _ in range(adms_df.shape[0])]

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM cities WHERE name = %(city)s OR code = %(city)s OR id::varchar = %(city)s",
            {"city": city_name},
        )
        city_id = cur.fetchone()
        if city_id is None:
            logger.error(f'Заданный город "{city_name}" отсутствует в базе данных')
            adms_df["result"] = pd.Series(
                [f'Город "{city_name}" отсутсвует в базе данных'] * adms_df.shape[0], index=adms_df.index
            )
            adms_df["adm_id"] = pd.Series([-1] * adms_df.shape[0], index=adms_df.index)
            return adms_df
        city_id = city_id[0]

        cur.execute("SELECT lower(full_name), id FROM administrative_unit_types")
        administrative_unit_types = dict(cur)
        cur.execute("SELECT lower(full_name), id FROM municipality_types")
        municipality_types = dict(cur)

        if commit:
            cur.execute("SAVEPOINT previous_object")
        i = 0
        try:
            for i, (_, row) in enumerate(tqdm(adms_df.iterrows(), total=adms_df.shape[0])):
                if i > 0:
                    call_callback(results[i - 1])
                if i % log_n == 0:
                    logger.opt(colors=True).info(
                        "Обработано {:4} единиц деления из {}: <green>{} добавлены</green>,"
                        " <yellow>{} обновлены</yellow>, <blue>{} оставлены без изменений</blue>,"
                        " <red>{} пропущены</red>",
                        i,
                        adms_df.shape[0],
                        added,
                        updated,
                        unchanged,
                        skipped,
                    )
                    if commit:
                        conn.commit()
                        cur.execute("SAVEPOINT previous_object")
                try:
                    if row.get(mapping.geometry) is None:
                        results[i] = "Пропущен (отсутствует геометрия)"
                        skipped += 1
                        continue

                    cur.execute("SELECT ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)", (row[mapping.geometry],))
                    geom_str = cur.fetchone()[0]
                    cur.execute(
                        "SELECT id FROM "
                        + (
                            "administrative_units"
                            if division_type == AdmDivisionType.ADMINISTRATIVE_UNIT
                            else "municipalities"
                        )
                        + " WHERE city_id = %(city_id)s"
                        "   AND (ST_Overlaps(geometry, %(geom)s) OR ST_Equals(geometry, %(geom)s))",
                        {"city_id": city_id, "geom": geom_str},
                    )

                    if cur.rowcount > 2:
                        adm_ids[i] = -1
                        results[i] = (
                            "Пропущен. Пересекается более чем с одной другой территориальной единицей того же типа"
                            " (необходима ручная вставка в случае вложенности)"
                        )
                        skipped += 1
                    elif cur.rowcount == 0:
                        if division_type == AdmDivisionType.ADMINISTRATIVE_UNIT:
                            adm_ids[i] = insert_administrative_unit(
                                cur,
                                row,
                                mapping,
                                administrative_unit_types,
                                city_id,
                                commit,
                            )  # type: ignore
                        else:
                            adm_ids[i] = insert_municipality(
                                cur,
                                row,
                                mapping,
                                municipality_types,
                                city_id,
                                commit,
                            )
                        results[i] = f"Добавлен с id={adm_ids[i]}"
                        added += 1
                    else:
                        adm_id = cur.fetchone()[0]
                        adm_ids[i] = adm_id
                        if division_type == AdmDivisionType.ADMINISTRATIVE_UNIT:
                            updated_result = update_administrative_unit(
                                cur, adm_id, row, mapping, administrative_unit_types, commit
                            )
                        else:
                            updated_result = update_municipality(cur, adm_id, row, mapping, municipality_types, commit)
                        if updated_result:
                            results[i] = f"Обновлена единица административного деления с id={adm_id}"
                            updated += 1
                        else:
                            results[i] = (
                                "Оставлен без изменений, совпадает с единицей"
                                f" административного деления в БД: id={adm_id}"
                            )
                            unchanged += 1
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
            logger.opt(colors=True).warning(
                "Обработано {:4} единиц деления из {}: <green>{} добавлены</green>, <yellow>{} обновлены</yellow>,"
                " <blue>{} оставлены без изменений</blue>, <red>{} пропущены</red>",
                i + 1,
                adms_df.shape[0],
                added,
                updated,
                unchanged,
                skipped,
            )
            if commit:
                choice = input("Сохранить внесенные на данный момент изменения? (y/д/1 / n/н/0): ")
                if choice.startswith(("y", "д", "1")):
                    conn.commit()
                    logger.success("Сохранение внесенных изменений")
                else:
                    logger.warning("Отмена внесенных изменений")
                    conn.rollback()
            for j in range(i, adms_df.shape[0]):
                results[j] = "Пропущен (отмена пользователем)"
        else:
            if commit:
                conn.commit()
        call_callback(results[-1])

        logger.info("Обновление отношениея зданий и физических объектов к единицам административного деления")
        cur.execute(
            f"UPDATE physical_objects p SET {division_type.name.lower()}_id ="
            "       (SELECT id FROM "
            + ("administrative_units" if division_type == AdmDivisionType.ADMINISTRATIVE_UNIT else "municipalities")
            + "           adm WHERE city_id = %(city_id)s AND ST_Within(p.center, adm.geometry) LIMIT 1)"
            " WHERE city_id = %(city_id)s",
            {"city_id": city_id},
        )
        if commit:
            conn.commit()

    adms_df["result"] = pd.Series(results, index=adms_df.index)
    adms_df["adm_id"] = pd.Series(adm_ids, index=adms_df.index)
    if division_type == AdmDivisionType.ADMINISTRATIVE_UNIT:
        logger.success("Вставка административных единиц завершена")
    else:
        logger.success("Вставка муниципальных образований завершена")
    logger.opt(colors=True).info(
        "{:4} единиц деления обработано: <green>{} добавлены</green>, <yellow>{} обновлены</yellow>, "
        " <blue>{} оставлены без изменений</blue>, <red>{} пропущены</red>",
        i + 1,
        added,
        updated,
        unchanged,
        skipped,
    )
    filename = f"adms_insertion_{conn.info.host}_{conn.info.port}_{conn.info.dbname}.xlsx"
    sheet_name = f'{time.strftime("%Y-%m-%d %H_%M-%S")}'
    logger.opt(colors=True).info(
        "Сохранение лога в файл Excel (нажмите Ctrl+C для отмены, <magenta>но это может повредить файл лога</magenta>)"
    )
    try:
        with pd.ExcelWriter(  # pylint: disable=abstract-class-instantiated
            filename, mode=("a" if os.path.isfile(filename) else "w"), engine="openpyxl"
        ) as writer:
            adms_df.to_excel(writer, sheet_name=sheet_name)
        logger.info(f'Лог вставки сохранен в файл "{filename}", лист "{sheet_name}"')
    except Exception as exc:  # pylint: disable=broad-except
        newlog = f"services_insertion_{int(time.time())}.xlsx"
        logger.error(
            f'Ошибка при сохранении лога вставки в файл "{filename}",'
            f' лист "{sheet_name}": {exc!r}. Попытка сохранения с именем {newlog}'
        )
        try:
            adms_df.to_excel(newlog, sheet_name=sheet_name)
            logger.success('Сохранение в файл "{}" прошло успешно', newlog)
        except Exception as exc_1:  # pylint: disable=broad-except
            logger.error(f"Ошибка сохранения лога: {exc_1!r}")
    except KeyboardInterrupt:
        logger.warning(f'Отмена сохранения файла лога, файл "{filename}" может быть поврежден')
    return adms_df
