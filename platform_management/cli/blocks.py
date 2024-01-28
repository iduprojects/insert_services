# pylint: disable=too-many-arguments,too-many-locals,
"""Blocks insertion logic is defined here.
"""
from __future__ import annotations

import os
import time
import traceback
import warnings
from typing import Callable

import pandas as pd
import psycopg2
from loguru import logger
from numpy import nan
from tqdm import tqdm

from platform_management.cli.common import SingleObjectStatus

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")


def insert_block(
    cur: psycopg2.extensions.cursor,
    geometry: str,
    city_id: int,
    commit: bool = True,
) -> int:
    """Insert block with given geometry if there is no intersections with other blocks.

    Returns an identifier of the added block.
    """
    cur.execute(
        "WITH center_t AS (SELECT ST_Centroid(%(geometry)s) center)"
        " INSERT INTO blocks (city_id, geometry, center, municipality_id, administrative_unit_id, area)"
        " VALUES (%(city_id)s, %(geometry)s, (SELECT center from center_t),"
        "   (SELECT id FROM municipalities WHERE city_id = %(city_id)s"
        "       AND ST_Within((SELECT center FROM center_t), geometry)),"
        "   (SELECT id FROM administrative_units WHERE city_id = %(city_id)s"
        "       AND ST_Within((SELECT center FROM center_t), geometry)),"
        "   (SELECT ST_Area(%(geometry)s::geography))"
        ") RETURNING id",
        {"geometry": geometry, "city_id": city_id},
    )
    idx = cur.fetchone()[0]

    if commit:
        cur.execute("SAVEPOINT previous_object")
    return idx


def update_block(
    cur: psycopg2.extensions.cursor,
    block_id: int,
    geometry: str,
    commit: bool = True,
):
    """Update functional_object data."""
    cur.execute(
        "WITH center_t AS (SELECT ST_Centroid(%(geometry)s) center)"
        " UPDATE blocks b SET"
        "   geometry = %(geometry)s,"
        "   center = (SELECT center from center_t),"
        "   municipality_id = (SELECT id FROM municipalities WHERE city_id = b.city_id"
        "       AND ST_Within((SELECT center FROM center_t), geometry)),"
        "   administrative_unit_id = (SELECT id FROM administrative_units WHERE city_id = b.city_id"
        "       AND ST_Within((SELECT center FROM center_t), geometry)),"
        "   area = (SELECT ST_Area(%(geometry)s::geography))"
        " WHERE id = %(block_id)s",
        {"geometry": geometry, "block_id": block_id},
    )
    if commit:
        cur.execute("SAVEPOINT previous_object")


def add_blocks(  # pylint: disable=too-many-branches,too-many-statements
    conn: psycopg2.extensions.connection,
    blocks_df: pd.DataFrame,
    city_name: str,
    geometry_column: str,
    commit: bool = True,
    verbose: bool = False,
    log_n: int = 200,
    callback: Callable[[SingleObjectStatus], None] | None = None,
) -> pd.DataFrame:
    """Insert service objects to database.

    Input:

        - `conn` - connection for the database
        - `blocks_df` - DataFrame containing objects
        - `city_name` - name of the city to add objects to. Must be created in the database
        - `geometry_column` - name of a dataframe column containing geometry in GeoJSON format
        - `commit` - True to commit changes, False for dry run, only resulting DataFrame is returned
        - `verbose` - True to output traceback with errors, False for only error messages printing
        - `log_n` - number of inserted/updated services to log after each
        - `callback` - optional callback function which is called after every service insertion

    Return:

        - dataframe of objects with "result" and "block_id" columns added
    """

    def call_callback(status: str) -> None:
        """Execute callback function with a parameter corresponding to the given status."""
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

    logger.info(f'Вставка кварталов в город "{city_name}," всего {blocks_df.shape[0]} объектов')

    blocks_df = blocks_df.copy().replace({nan: None})

    updated = 0  # number of updated blocks which were already present in the database
    unchanged = 0  # number of blocks already present in the database with the same properties
    added, skipped = 0, 0
    results: list[str] = list(("",) * blocks_df.shape[0])
    block_ids: list[int] = [-1 for _ in range(blocks_df.shape[0])]

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM cities WHERE name = %(city)s OR code = %(city)s OR id::varchar = %(city)s",
            {"city": city_name},
        )
        city_id = cur.fetchone()
        if city_id is None:
            logger.error(f'Заданный город "{city_name}" отсутствует в базе данных')
            blocks_df["result"] = pd.Series(
                [f'Город "{city_name}" отсутсвует в базе данных'] * blocks_df.shape[0], index=blocks_df.index
            )
            blocks_df["block_id"] = pd.Series([-1] * blocks_df.shape[0], index=blocks_df.index)
            return blocks_df
        city_id = city_id[0]

        if commit:
            cur.execute("SAVEPOINT previous_object")
        i = 0
        try:
            for i, (_, row) in enumerate(tqdm(blocks_df.iterrows(), total=blocks_df.shape[0])):
                if i > 0:
                    call_callback(results[i - 1])
                if i % log_n == 0:
                    logger.opt(colors=True).info(
                        "Обработано {:4} кварталов из {}: <green>{} добавлены</green>,"
                        " <yellow>{} обновлены</yellow>, <blue>{} оставлены без изменений</blue>,"
                        " <red>{} пропущены</red>",
                        i,
                        blocks_df.shape[0],
                        added,
                        updated,
                        unchanged,
                        skipped,
                    )
                    if commit:
                        conn.commit()
                        cur.execute("SAVEPOINT previous_object")
                try:
                    if geometry_column not in row or row[geometry_column] is None:
                        results[i] = "Пропущен (отсутствует геометрия)"
                        skipped += 1
                        continue

                    cur.execute("SELECT ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)", (row[geometry_column],))
                    geom_str = cur.fetchone()[0]
                    cur.execute(
                        "SELECT id, geometry FROM blocks"
                        " WHERE city_id = %(city_id)s"
                        "   AND ("
                        "       ST_Contains(geometry, %(geom)s)"
                        "       OR ST_Contains(%(geom)s, geometry)"
                        "       OR ST_Overlaps(geometry, %(geom)s)"
                        "       OR ST_Equals(geometry, %(geom)s)"
                        "   )",
                        {"city_id": city_id, "geom": geom_str},
                    )

                    if cur.rowcount > 2:
                        block_ids[i] = -1
                        results[i] = "Пропущен. Пересекается более чем с одним другим кварталом"
                        skipped += 1
                    elif cur.rowcount == 0:
                        block_ids[i] = insert_block(
                            cur,
                            geom_str,
                            city_id,
                            commit,
                        )  # type: ignore
                        results[i] = f"Добавлен с id={block_ids[i]}"
                        added += 1
                    else:
                        block_id, block_geometry = cur.fetchone()
                        block_ids[i] = block_id
                        if block_geometry == geom_str:
                            results[i] = f"Оставлен без изменений, совпадает с кварталом в БД: id={block_id}"
                            unchanged += 1
                        else:
                            update_block(cur, block_id, geom_str, commit)
                            results[i] = f"Обновлен квартал с id={block_id}"
                            updated += 1
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
                "Обработано {:4} кварталов из {}: <green>{} добавлены</green>, <yellow>{} обновлены</yellow>,"
                " <blue>{} оставлены без изменений</blue>, <red>{} пропущены</red>",
                i + 1,
                blocks_df.shape[0],
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
            for j in range(i, blocks_df.shape[0]):
                results[j] = "Пропущен (отмена пользователем)"
        else:
            if commit:
                conn.commit()
        call_callback(results[-1])

        logger.info("Обновление отношениея зданий и физических объектов к кварталам")
        cur.execute(
            "UPDATE physical_objects p SET block_id ="
            "       (SELECT id FROM blocks b WHERE city_id = %(city_id)s AND ST_Within(p.center, b.geometry) LIMIT 1)"
            " WHERE city_id = %(city_id)s",
            {"city_id": city_id},
        )
        logger.info("Обновление населения кварталов города")
        cur.execute(
            "UPDATE blocks b SET population = ("
            "   SELECT sum(population_balanced)"
            "   FROM buildings b JOIN physical_objects p ON b.physical_object_id = p.id"
            "   WHERE block_id = b.id)",
            (city_id,),
        )

    blocks_df["result"] = pd.Series(results, index=blocks_df.index)
    blocks_df["block_id"] = pd.Series(block_ids, index=blocks_df.index)
    logger.success("Вставка кварталов завершена")
    logger.opt(colors=True).info(
        "{:4} кварталов обработано: <green>{} добавлены</green>, <yellow>{} обновлены</yellow>, "
        " <blue>{} оставлены без изменений</blue>, <red>{} пропущены</red>",
        i + 1,
        added,
        updated,
        unchanged,
        skipped,
    )
    filename = f"blocks_insertion_{conn.info.host}_{conn.info.port}_{conn.info.dbname}.xlsx"
    sheet_name = f'{time.strftime("%Y-%m-%d %H_%M-%S")}'
    logger.opt(colors=True).info(
        "Сохранение лога в файл Excel (нажмите Ctrl+C для отмены, <magenta>но это может повредить файл лога</magenta>)"
    )
    try:
        with pd.ExcelWriter(  # pylint: disable=abstract-class-instantiated
            filename, mode=("a" if os.path.isfile(filename) else "w"), engine="openpyxl"
        ) as writer:
            blocks_df.to_excel(writer, sheet_name)
        logger.info(f'Лог вставки сохранен в файл "{filename}", лист "{sheet_name}"')
    except Exception as exc:  # pylint: disable=broad-except
        newlog = f"services_insertion_{int(time.time())}.xlsx"
        logger.error(
            f'Ошибка при сохранении лога вставки в файл "{filename}",'
            f' лист "{sheet_name}": {exc!r}. Попытка сохранения с именем {newlog}'
        )
        try:
            blocks_df.to_excel(newlog, sheet_name)
            logger.success('Сохранение в файл "{}" прошло успешно', newlog)
        except Exception as exc_1:  # pylint: disable=broad-except
            logger.error(f"Ошибка сохранения лога: {exc_1!r}")
    except KeyboardInterrupt:
        logger.warning(f'Отмена сохранения файла лога, файл "{filename}" может быть поврежден')
    return blocks_df
