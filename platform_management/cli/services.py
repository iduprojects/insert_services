# pylint: disable=too-many-arguments,too-many-locals,
"""
Services insertion logic is defined here.
"""
import json
import os
import random
import time
import traceback
import warnings
from typing import Callable, Dict, List, Optional, Tuple, Union

import pandas as pd
import psycopg2
from frozenlist import FrozenList
from loguru import logger
from numpy import nan
from tqdm import tqdm
from platform_management.cli.common import SingleObjectStatus

from platform_management.dto import ServiceInsertionMapping

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

logger = logger.bind(name="insert_services")


def insert_object(
    cur: "psycopg2.cursor",
    row: pd.Series,
    phys_id: int,
    name: str,
    service_type_id: int,
    mapping: ServiceInsertionMapping,
    properties_mapping: Dict[str, str],
    commit: bool = True,
) -> int:
    """
    Insert functional_object, returning identifier of the inserted functional object.

    `service_type_id` must be vaild.
    """
    cur.execute(
        "SELECT st.capacity_min, st.capacity_max, st.id, cf.id, it.id"
        " FROM city_infrastructure_types it"
        "   JOIN city_functions cf ON cf.city_infrastructure_type_id = it.id"
        "   JOIN city_service_types st ON st.city_function_id = cf.id"
        " WHERE st.id = %s",
        (service_type_id,),
    )
    capacity_min, capacity_max, *ids = cur.fetchone()  # type: ignore
    assert (
        ids[0] is not None and ids[1] is not None and ids[2] is not None
    ), "Service type, city function or infrastructure type are not found in the database"
    if mapping.capacity in row and row[mapping.capacity] is not None:
        try:
            capacity = int(float(row[mapping.capacity]))
            is_capacity_real = True
        except ValueError:
            logger.warning(
                "Capacity '{}' is not an integer value, setting false capacity for object {}",
                row[mapping.capacity],
                name,
            )
            capacity = random.randint(capacity_min, capacity_max)
            is_capacity_real = False
    else:
        capacity = random.randint(capacity_min, capacity_max)
        is_capacity_real = False
    functional_object_properties = {
        db_name: row[row_name]
        for db_name, row_name in properties_mapping.items()
        if row_name in row and row[row_name] is not None and row[row_name] != ""
    }
    cur.execute(
        "INSERT INTO functional_objects (name, opening_hours, website, phone,"
        "       city_service_type_id, city_function_id, city_infrastructure_type_id,"
        "       capacity, is_capacity_real, physical_object_id, properties)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (
            name,
            row.get(mapping.opening_hours),
            row.get(mapping.website),
            row.get(mapping.phone),
            *ids,
            capacity,
            is_capacity_real,
            phys_id,
            json.dumps(functional_object_properties),
        ),
    )
    functional_object_id = cur.fetchone()[0]  # type: ignore
    if commit:
        cur.execute("SAVEPOINT previous_object")
    return functional_object_id


def update_object(
    cur: "psycopg2.cursor",
    row: pd.Series,
    functional_object_id: int,
    name: str,
    mapping: ServiceInsertionMapping,
    properties_mapping: Dict[str, str],
    commit: bool = True,
) -> bool:
    """
    Update functional_object data.

    Returns True if service was updated (some properties were different), False otherwise.
    """
    cur.execute(
        "SELECT name, opening_hours, website, phone, capacity, is_capacity_real, properties"
        " FROM functional_objects WHERE id = %s",
        (functional_object_id,),
    )
    res: Tuple[str, str, str, str, int]
    *res, db_properties = cur.fetchone()  # type: ignore
    try:
        capacity = int(float(row[mapping.capacity])) if row.get(mapping.capacity, None) is not None else None
        is_capacity_real = capacity is not None
    except ValueError:
        capacity = None
        is_capacity_real = False
        logger.warning(
            "Capacity value '{}' is invalid, skipping for functional object with id={}",
            row[mapping.capacity],
            functional_object_id,
        )
    change = list(
        filter(
            lambda c_v_nw: c_v_nw[1] != c_v_nw[2] and c_v_nw[2] is not None and c_v_nw[2] != "",
            zip(
                ("name", "opening_hours", "website", "phone", "capacity", "is_capacity_real"),
                res,
                (
                    name,
                    row.get(mapping.opening_hours),
                    row.get(mapping.website),
                    row.get(mapping.phone),
                    capacity,
                    is_capacity_real,
                ),
            ),
        )
    )
    if res[-1] and not mapping.capacity in row:
        change = change[:-2]
    if len(change) > 0:
        cur.execute(
            f'UPDATE functional_objects SET {", ".join(list(map(lambda x: x[0] + "=%s", change)))} WHERE id = %s',
            list(map(lambda x: x[2], change)) + [functional_object_id],
        )
    functional_object_properties = {
        db_name: row[row_name]
        for db_name, row_name in properties_mapping.items()
        if row_name in row and row[row_name] is not None and row[row_name] != ""
    }
    if db_properties != functional_object_properties:
        cur.execute(
            "UPDATE functional_objects SET properties = properties || %s::jsonb WHERE id = %s",
            (json.dumps(functional_object_properties), functional_object_id),
        )
    if commit:
        cur.execute("SAVEPOINT previous_object")
    return len(change) != 0 or db_properties != functional_object_properties


def get_properties_keys(
    cur_or_conn: Union["psycopg2.connection", "psycopg2.cursor"], city_service_type: str
) -> List[str]:
    """Return a list of properties keys of a given city_service_type by name or id."""
    if isinstance(cur_or_conn, psycopg2.extensions.connection):
        cur = cur_or_conn.cursor()
    else:
        cur = cur_or_conn
    try:
        cur.execute(
            "WITH st AS (SELECT id FROM city_service_types"
            "   WHERE name = %(city_service_type)s or code = %(city_service_type)s)"
            " SELECT DISTINCT jsonb_object_keys(properties)"
            " FROM functional_objects"
            " WHERE city_service_type_id = (SELECT id FROM st)"
            " ORDER BY 1",
            {"city_service_type": city_service_type},
        )
        return [r[0] for r in cur.fetchall()]
    finally:
        if isinstance(cur_or_conn, psycopg2.extensions.connection):
            cur.close()


def add_services(  # pylint: disable=too-many-branches,too-many-statements,too-many-nested-blocks
    conn: "psycopg2.connection",
    services_df: pd.DataFrame,
    city_name: str,
    service_type: str,
    mapping: ServiceInsertionMapping,
    properties_mapping: Dict[str, str] = frozenset({}),
    address_prefixes: List[str] = FrozenList(["Россия, Санкт-Петербург"]),
    new_prefix: str = "",
    commit: bool = True,
    verbose: bool = False,
    log_n: int = 200,
    callback: Optional[Callable[[SingleObjectStatus], None]] = None,
) -> pd.DataFrame:
    """
    Insert service objects to database.

    Input:

        - `conn` - connection for the database
        - `services_df` - DataFrame containing objects
        - `city_name` - name of the city to add objects to. Must be created in the database
        - `service_type` - name of service_type for logging and services names fillment if they are missing
        - `mapping` - ServiceInsertionMapping of namings in the database and namings in the DataFrame columns
        - `properties_mapping` - dict[str, str] of additional properties namings in the
        functional_objects.properties and namings in the DataFrame columns
        - `address_prefix` - list of possible prefixes (will be sorted by length)
        - `new_prefix` - unified prefix for all of the inserted objects
        - `commit` - True to commit changes, False for dry run, only resulting DataFrame is returned
        - `verbose` - True to output traceback with errors, False for only error messages printing
        - `log_n` - number of inserted/updated services to log after each
        - `callback` - optional callback function which is called after every service insertion

    Return:

        - dataframe of objects with "result" and "functional_obj_id" columns added

    Algorithm steps:

        1. If latitude or longitude is invaild, or address does not start with any of prefixes
            (if `is_service_building` == True), skip

        2. Check if building with given address is present in the database (if `is_service_building` == True)

        3. If found:

            3.1. If functional object with the same name and service_type_id is already
                connected to the physical object, update by calling `update_object`

            3.2. Else get building id and physical_object id

        4. Else:

            4.1. If there is physical object (building if only `is_service_building` == True)
                which geometry contains current object's coordinates,
                get its physical_object id and building id if needed

            4.2. Else insert physical_object/building with geometry type Point

            4.3. Else include inserted ids in the result

        5. Insert functional_object connected to physical_object by calling `insert_object`
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

    logger.info(f'Вставка сервисов типа "{service_type}", всего {services_df.shape[0]} объектов')
    logger.info(f'Город вставки - "{city_name}". Список префиксов: {address_prefixes}, новый префикс: "{new_prefix}"')

    services_df = services_df.copy().replace({nan: None, "": None})
    if mapping.address in services_df.columns:
        services_df[mapping.address] = services_df[mapping.address].apply(
            lambda x: x.replace("?", "").strip() if isinstance(x, str) else None
        )

    updated = 0  # number of updated service objects which were already present in the database
    unchanged = 0  # number of service objects already present in the database with the same properties
    added_to_address, added_to_geom, added_as_points, skipped = 0, 0, 0, 0
    results: List[str] = list(("",) * services_df.shape[0])
    functional_ids: List[int] = [-1 for _ in range(services_df.shape[0])]
    address_prefixes = sorted(address_prefixes, key=lambda s: -len(s))
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM cities WHERE name = %(city)s or code = %(city)s", {"city": city_name})
        city_id = cur.fetchone()
        if city_id is None:
            logger.error(f'Заданный город "{city_name}" отсутствует в базе данных')
            services_df["result"] = pd.Series(
                [f'Город "{city_name}" отсутсвует в базе данных'] * services_df.shape[0], index=services_df.index
            )
            services_df["functional_obj_id"] = pd.Series([-1] * services_df.shape[0], index=services_df.index)
            return services_df
        city_id = city_id[0]

        cur.execute(
            "SELECT id, is_building FROM city_service_types WHERE name = %(service)s or code = %(service)s",
            {"service": service_type},
        )
        res = cur.fetchone()
        if res is not None:
            service_type_id, is_service_building = res
        else:
            logger.error(f'Заданный тип сервиса "{service_type}" отсутствует в базе данных')
            services_df["result"] = pd.Series(
                [f'Тип сервиса "{service_type}" отсутствует в базе данных'] * services_df.shape[0],
                index=services_df.index,
            )
            services_df["functional_obj_id"] = pd.Series([-1] * services_df.shape[0], index=services_df.index)
            return services_df

        if commit:
            cur.execute("SAVEPOINT previous_object")
        i = 0
        try:
            for i, (_, row) in enumerate(tqdm(services_df.iterrows(), total=services_df.shape[0])):
                if i > 0:
                    call_callback(results[i - 1])
                if i % log_n == 0:
                    logger.opt(colors=True).info(
                        f"Обработано {i:4} сервисов из {services_df.shape[0]}:"
                        f" <green>{added_as_points + added_to_address + added_to_geom} добавлены</green>,"
                        f" <yellow>{updated} обновлены</yellow>, <red>{skipped} пропущены</red>"
                    )
                    if commit:
                        cur.execute("SAVEPOINT previous_object")
                try:
                    if mapping.geometry not in row and (mapping.latitude not in row or mapping.longitude not in row):
                        results[i] = (
                            "Пропущен (отсутствует как минимум одно необходимое поле:"
                            f" (широта ({mapping.latitude}) + долгота"
                            f" ({mapping.longitude}) или геометрия({mapping.geometry}))"
                        )
                        skipped += 1
                        continue
                    if mapping.geometry in row:
                        try:
                            cur.execute(
                                "WITH tmp AS (SELECT geometry FROM"
                                "       (VALUES (ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)))"
                                "   ) tmp_inner(geometry))"
                                " SELECT"
                                "   ST_GeometryType((SELECT geometry FROM tmp)) geometry_type,"
                                "   ST_Y((SELECT geometry FROM tmp)) y,"
                                "   ST_X((SELECT geometry FROM tmp)) x",
                                (row[mapping.geometry],),
                            )
                            geom_type, latitude, longitude = cur.fetchone()  # type: ignore
                        except Exception as exc:  # pylint: disable=broad-except
                            logger.trace("invalid geometry for row={}: {!r}", i, exc)
                            results[i] = f'Геометрия в поле "{mapping.geometry}" некорректна'
                            skipped += 1
                            if commit:
                                cur.execute("ROLLBACK TO previous_object")
                            else:
                                conn.rollback()
                            continue
                    else:
                        geom_type = "ST_Point"
                        try:
                            latitude = round(float(row[mapping.latitude]), 6)
                            longitude = round(float(row[mapping.longitude]), 6)
                        except Exception as exc:  # pylint: disable=broad-except
                            logger.trace("invalid latitude/longitude for row={}: {!r}", i, exc)
                            results[i] = "Пропущен (широта или долгота некорректны)"
                            skipped += 1
                            continue
                    address: Optional[str] = None
                    if is_service_building:
                        if mapping.address in row:
                            for address_prefix in address_prefixes:
                                if row.get(mapping.address, "").startswith(address_prefix):
                                    address = row.get(mapping.address)[len(address_prefix) :].strip(", ")
                                    break
                            else:
                                if len(address_prefixes) == 1:
                                    results[i] = f'Пропущен (адрес не начинается с "{address_prefixes[0]}")'
                                else:
                                    results[i] = (
                                        "Пропущен (адрес не начинается ни с одного"
                                        f" из {len(address_prefixes)} префиксов)"
                                    )
                                skipped += 1
                                continue
                    name = row.get(mapping.name, f"({service_type} без названия)")
                    if name is None or name == "":
                        name = f"({service_type} без названия)"

                    cur.execute(
                        "SELECT id FROM municipalities"
                        " WHERE ST_Within(ST_SetSRID(ST_MakePoint(%s, %s), 4326), geometry)",
                        (longitude, latitude),
                    )
                    municipality_id: Optional[int] = cur.fetchone()[0] if cur.rowcount > 0 else None
                    cur.execute(
                        "SELECT id FROM administrative_units"
                        " WHERE ST_Within(ST_SetSRID(ST_MakePoint(%s, %s), 4326), geometry)",
                        (longitude, latitude),
                    )
                    administrative_unit_id: Optional[int] = cur.fetchone()[0] if cur.rowcount > 0 else None

                    phys_id: int
                    build_id: Optional[int]
                    insert_physical_object = False
                    if is_service_building:
                        if address is not None and address != "":
                            cur.execute(
                                "SELECT phys.id, build.id FROM physical_objects phys"
                                "   JOIN buildings build ON build.physical_object_id = phys.id"
                                " WHERE phys.city_id = %s AND build.address LIKE %s AND"
                                "   ST_Distance(phys.center::geography,"
                                "       ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography) < 200"
                                " LIMIT 1",
                                (city_id, f"%{address}", longitude, latitude),
                            )
                            res = cur.fetchone()  # type: ignore
                        else:
                            res = None
                        if res is not None:
                            # if building with the same address found and distance between point
                            # and the center of geometry is less than 100m
                            phys_id, build_id = res
                            cur.execute(
                                "SELECT id FROM functional_objects f"
                                " WHERE physical_object_id = %s AND city_service_type_id = %s AND name = %s LIMIT 1",
                                (phys_id, service_type_id, name),
                            )
                            res = cur.fetchone()
                            if res is not None:  # if service is already present in this building
                                functional_ids[i] = res[0]
                                if update_object(cur, row, res[0], name, mapping, properties_mapping, commit):
                                    updated += 1
                                    results[i] = (
                                        f"Обновлен существующий сервис (build_id = {build_id},"
                                        f" phys_id = {phys_id}, functional_object_id = {res[0]})"
                                    )
                                else:
                                    unchanged += 1
                                    results[i] = (
                                        f"Сервис полностью совпадает с информацией в БД (build_id = {build_id},"
                                        f" phys_id = {phys_id}, functional_object_id = {res[0]})"
                                    )
                                continue
                            added_to_address += 1
                            results[i] = (
                                "Сервис вставлен в здание, найденное по совпадению адреса"
                                f" (build_id = {build_id}, phys_id = {phys_id})."
                            )
                        else:
                            # if no building with the same address found or distance is
                            # too high (address is wrong or it's not a concrete house)
                            if mapping.geometry in row:
                                cur.execute(
                                    "SELECT ST_GeometryType(geometry), phys.id, build.id, build.address"
                                    " FROM physical_objects phys"
                                    "   JOIN buildings build ON build.physical_object_id = phys.id"
                                    " WHERE city_id = %s"
                                    + (" AND municipality_id = %s" if municipality_id is not None else "")
                                    + (" AND administrative_unit_id = %s" if administrative_unit_id is not None else "")
                                    + " AND ST_Intersects(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), geometry)"
                                    " LIMIT 1",
                                    list(
                                        filter(
                                            lambda x: x is not None,
                                            (city_id, municipality_id, administrative_unit_id, row[mapping.geometry]),
                                        )
                                    ),
                                )
                            else:
                                cur.execute(
                                    "SELECT ST_GeometryType(geometry), phys.id, build.id, build.address"
                                    " FROM physical_objects phys"
                                    "   JOIN buildings build ON build.physical_object_id = phys.id"
                                    " WHERE city_id = %(city_id)s"
                                    + (
                                        " AND municipality_id = %(municipality_id)s"
                                        if municipality_id is not None
                                        else ""
                                    )
                                    + (
                                        " AND administrative_unit_id = %(administrative_unit_id)s"
                                        if administrative_unit_id is not None
                                        else ""
                                    )
                                    + " AND ("
                                    "       ST_GeometryType(geometry) = 'ST_Point'"
                                    "           AND abs(ST_X(geometry) - %(lng)s) < 0.0001"
                                    "           AND abs(ST_Y(geometry) - %(lat)s) < 0.0001"
                                    "       OR ST_Intersects(ST_SetSRID(ST_MakePoint(%(lng)s, %(lat)s), 4326),"
                                    "           geometry)"
                                    "   )"
                                    " LIMIT 1",
                                    {"city_id": city_id, "lng": longitude, "lat": latitude}
                                    | ({"municipality_id": municipality_id} if municipality_id is not None else {})
                                    | (
                                        {"administrative_unit_id": administrative_unit_id}
                                        if administrative_unit_id is not None
                                        else {}
                                    ),
                                )
                            res = cur.fetchone()
                            if res is not None:  # if building found by geometry
                                current_geom_type, phys_id, build_id, address = res
                                cur.execute(
                                    "SELECT id FROM functional_objects f"
                                    " WHERE physical_object_id = %s"
                                    "   AND city_service_type_id = %s AND name = %s LIMIT 1",
                                    (phys_id, service_type_id, name),
                                )
                                res = cur.fetchone()
                                if res is not None:  # if service is already present in this building
                                    functional_ids[i] = res[0]
                                    if update_object(cur, row, res[0], name, mapping, properties_mapping, commit):
                                        updated += 1
                                        if address is not None:
                                            results[i] = (
                                                "Обновлен существующий сервис, находящийся в здании"
                                                f' с другим адресом: "{address}" (build_id = {build_id},'
                                                f" phys_id = {phys_id}, functional_object_id = {res[0]})"
                                            )
                                        else:
                                            results[i] = (
                                                f"Обновлен существующий сервис, находящийся в здании без адреса"
                                                f" (build_id = {build_id}, phys_id = {phys_id},"
                                                f" functional_object_id = {res[0]})"
                                            )
                                    else:
                                        unchanged += 1
                                        results[i] = (
                                            f"Сервис полностью совпадает с информацией в БД (build_id = {build_id},"
                                            f" phys_id = {phys_id}, functional_object_id = {res[0]})"
                                        )
                                    continue
                                # if no service present, but buiding found
                                added_to_geom += 1
                                if address is None:
                                    results[i] = (
                                        f"Сервис вставлен в здание, подходящее по геометрии, но не имеющее адреса"
                                        f" (build_id = {build_id}, phys_id = {phys_id})"
                                    )
                                else:
                                    results[i] = (
                                        "Сервис вставлен в здание, подходящее по геометрии,"
                                        f' но имеющее другой адрес: "{address}"'
                                        f" (build_id = {build_id}, phys_id = {phys_id})"
                                    )
                                if current_geom_type == "ST_Point" and geom_type != "ST_Point":
                                    cur.execute(
                                        "WITH tmp AS (SELECT geometry FROM"
                                        "       (VALUES (ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)))"
                                        "   ) tmp_inner(geometry))"
                                        " UPDATE physical_objects"
                                        " SET geometry = (SELECT geometry FORM tmp),"
                                        "   center = ST_Centroid((SELECT geometry FROM tmp))"
                                    )
                                    results[i] += ". Обновлена геометрия здания с точки"
                            else:  # if no building found by address or geometry
                                insert_physical_object = True
                    else:
                        if mapping.geometry in row:
                            cur.execute(
                                "SELECT ST_GeometryType(geometry), id FROM physical_objects phys"
                                " WHERE city_id = %s"
                                "   AND (SELECT EXISTS"
                                "       (SELECT 1 FROM buildings where physical_object_id = phys.id)) = false"
                                + ("  AND municipality_id = %s" if municipality_id is not None else "")
                                + ("  AND administrative_unit_id = %s" if administrative_unit_id is not None else "")
                                + "   AND (ST_CoveredBy(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), geometry))"
                                " LIMIT 1",
                                list(
                                    filter(
                                        lambda x: x is not None,
                                        (city_id, municipality_id, administrative_unit_id, row[mapping.geometry]),
                                    )
                                ),
                            )
                        else:
                            cur.execute(
                                "SELECT ST_GeometryType(geometry), id FROM physical_objects phys"
                                " WHERE city_id = %(city_id)s"
                                "   AND (SELECT EXISTS"
                                "       (SELECT 1 FROM buildings where physical_object_id = phys.id)) = false"
                                + (" AND municipality_id = %(municipality_id)s" if municipality_id is not None else "")
                                + (
                                    " AND administrative_unit_id = %(administrative_unit_id)s"
                                    if administrative_unit_id is not None
                                    else ""
                                )
                                + "   AND (ST_GeometryType(geometry) = 'ST_Point'"
                                "   AND abs(ST_X(geometry) - %(lng)s) < 0.0001"
                                "   AND abs(ST_Y(geometry) - %(lat)s) < 0.0001"
                                "   OR ST_Intersects(ST_SetSRID(ST_MakePoint(%(lng)s, %(lat)s), 4326), geometry))"
                                " LIMIT 1",
                                {"city_id": city_id, "lng": longitude, "lat": latitude}
                                | ({"municipality_id": municipality_id} if municipality_id is not None else set())
                                | (
                                    {"administrative_unit_id": administrative_unit_id}
                                    if administrative_unit_id is not None
                                    else set()
                                ),
                            )
                        res = cur.fetchone()
                        if res is not None:  # if physical_object found by geometry
                            current_geom_type, phys_id = res
                            cur.execute(
                                "SELECT id FROM functional_objects f "
                                " WHERE physical_object_id = %s AND city_service_type_id = %s AND name = %s"
                                " LIMIT 1",
                                (phys_id, service_type_id, name),
                            )
                            res = cur.fetchone()
                            if res is not None:  # if service is already present in this pysical_object
                                functional_ids[i] = res[0]
                                if update_object(cur, row, res[0], name, mapping, properties_mapping, commit):
                                    updated += 1
                                else:
                                    unchanged += 1
                                    results[i] = (
                                        "Обновлен существующий сервис без здания"
                                        f" (phys_id = {phys_id}, functional_object_id = {res[0]})"
                                    )
                                    results[i] = (
                                        f"Сервис полностью совпадает с информацией в БД (build_id = {build_id},"
                                        f" phys_id = {phys_id}, functional_object_id = {res[0]})"
                                    )
                                continue
                            # if no service present, but physical_object found
                            added_to_geom += 1
                            results[i] = (
                                "Сервис вставлен в физический объект," f" подходящий по геометрии (phys_id = {phys_id})"
                            )
                            if current_geom_type == "Point" and geom_type != "Point":
                                cur.execute(
                                    "WITH tmp AS (SELECT geometry FROM (VALUES"
                                    "   (ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)))) tmp_inner(geometry))"
                                    " UPDATE physical_objects"
                                    " SET geometry = (SELECT geometry FORM tmp),"
                                    "   center = ST_Centroid((SELECT geometry FROM tmp))"
                                )
                                results[i] += ". Обновлена геометрия физического объекта с точки"
                        else:
                            insert_physical_object = True
                    if insert_physical_object:
                        if mapping.geometry in row:
                            cur.execute(
                                "INSERT INTO physical_objects (osm_id, geometry, center, city_id,"
                                "   municipality_id, administrative_unit_id)"
                                " VALUES"
                                " (%s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),"
                                "   ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s)"
                                " RETURNING id",
                                (
                                    row.get(mapping.osm_id),
                                    row[mapping.geometry],
                                    longitude,
                                    latitude,
                                    city_id,
                                    municipality_id,
                                    administrative_unit_id,
                                ),
                            )
                        else:
                            cur.execute(
                                "INSERT INTO physical_objects (osm_id, geometry, center, city_id,"
                                "   municipality_id, administrative_unit_id)"
                                " VALUES"
                                " (%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326),"
                                "   ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s)"
                                " RETURNING id",
                                (
                                    row.get(mapping.osm_id),
                                    longitude,
                                    latitude,
                                    longitude,
                                    latitude,
                                    city_id,
                                    municipality_id,
                                    administrative_unit_id,
                                ),
                            )
                        phys_id = cur.fetchone()[0]  # type: ignore
                        if is_service_building:
                            if address is not None:
                                cur.execute(
                                    "INSERT INTO buildings (physical_object_id, address) VALUES (%s, %s) RETURNING id",
                                    (phys_id, new_prefix + address),
                                )
                                build_id = cur.fetchone()[0]  # type: ignore
                                results[
                                    i
                                ] = f"Сервис вставлен в новое здание (build_id = {build_id}, phys_id = {phys_id})"
                            else:
                                cur.execute(
                                    "INSERT INTO buildings (physical_object_id) VALUES (%s) RETURNING id", (phys_id,)
                                )
                                build_id = cur.fetchone()[0]  # type: ignore
                                results[i] = (
                                    f"Сервис вставлен в новое здание без указания адреса"
                                    f" (build_id = {build_id}, phys_id = {phys_id})"
                                )
                        else:
                            if geom_type != "ST_Point":
                                results[i] = (
                                    "Сервис вставлен в новый физический объект,"
                                    f" добавленный с геометрией (phys_id = {phys_id})"
                                )
                            else:
                                results[i] = (
                                    "Сервис вставлен в новый физический объект, добавленный"
                                    f' с типом геометрии "Точка" (phys_id = {phys_id})'
                                )
                        added_as_points += 1
                    functional_ids[i] = insert_object(
                        cur, row, phys_id, name, service_type_id, mapping, properties_mapping, commit
                    )  # type: ignore
                except Exception as exc:  # pylint: disable=broad-except
                    logger.error("Произошла ошибка: {!r}", exc, traceback=True)
                    if verbose:
                        logger.error(f"Traceback:\n{traceback.format_exc()}")
                    if commit:
                        cur.execute("ROLLBACK TO previous_object")
                    else:
                        cur.rollback()
                    results[i] = f"Пропущен, вызывает ошибку: {exc}"
                    skipped += 1
        except KeyboardInterrupt:
            logger.warning("Прерывание процесса пользователем")
            logger.opt(colors=True).warning(
                "Обработано {:4} сервисов из {}: <green>{} добавлены</green>, <yellow>{} обновлены</yellow>,"
                " <blue>{} оставлены без изменений</blue>, <red>{} пропущены</red>",
                i + 1,
                services_df.shape[0],
                added_as_points + added_to_address + added_to_geom,
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
            for j in range(i, services_df.shape[0]):
                results[j] = "Пропущен (отмена пользователем)"
        else:
            if commit:
                conn.commit()
    call_callback(results[-1])

    services_df["result"] = pd.Series(results, index=services_df.index)
    services_df["functional_obj_id"] = pd.Series(functional_ids, index=services_df.index)
    logger.success(f'Вставка сервисов типа "{service_type}" завершена')
    logger.opt(colors=True).info(
        f"{i+1} сервисов обработано: <green>{added_as_points + added_to_address + added_to_geom} добавлены</green>,"
        f" <yellow>{updated} обновлены</yellow>, <red>{skipped} пропущены</red>"
    )
    logger.opt(colors=True).info(
        f"<cyan>{added_as_points} сервисов были добавлены в новые физические объекты/здания</cyan>,"
        f" <green>{added_to_address} добавлены в здания по совпадению адреса</green>,"
        f" <yellow>{added_to_geom} добавлены в физические объекты/здания по совпадению геометрии</yellow>"
    )
    filename = f"services_insertion_{conn.info.host}_{conn.info.port}_{conn.info.dbname}.xlsx"
    sheet_name = f'{service_type.replace("/", "_")}_{time.strftime("%Y-%m-%d %H_%M-%S")}'
    logger.opt(colors=True).info(
        "Сохранение лога в файл Excel (нажмите Ctrl+C для отмены, <magenta>но это может повредить файл лога</magenta>)"
    )
    try:
        with pd.ExcelWriter(  # pylint: disable=abstract-class-instantiated
            filename, mode=("a" if os.path.isfile(filename) else "w"), engine="openpyxl"
        ) as writer:
            services_df.to_excel(writer, sheet_name)
        logger.info(f'Лог вставки сохранен в файл "{filename}", лист "{sheet_name}"')
    except Exception as exc:  # pylint: disable=broad-except
        newlog = f"services_insertion_{int(time.time())}.xlsx"
        logger.error(
            f'Ошибка при сохранении лога вставки в файл "{filename}",'
            f' лист "{sheet_name}": {exc!r}. Попытка сохранения с именем {newlog}'
        )
        try:
            services_df.to_excel(newlog, sheet_name)
            logger.success("Сохранение прошло успешно")
        except Exception as exc_1:  # pylint: disable=broad-except
            logger.error(f"Ошибка сохранения лога: {exc_1!r}")
    except KeyboardInterrupt:
        logger.warning(f'Отмена сохранения файла лога, файл "{filename}" может быть поврежден')
    return services_df
