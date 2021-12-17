import argparse
import itertools
import json
import logging
import os
import random
import time
import traceback
from enum import Enum
from enum import auto as enum_auto
from typing import Any, Dict, Iterable, List, NamedTuple, Optional

import pandas as pd
import psycopg2

from database_properties import Properties

properties: Properties

log = logging.getLogger('services_manipulation').getChild('services_insert_console')
log.addHandler(logging.FileHandler('insert_services.log', 'a', 'utf8'))
log.handlers[-1].setFormatter(logging.Formatter('{asctime} {name}: {message}', datefmt='%Y-%m-%d %H:%M:%S', style='{'))
log.handlers[-1].setLevel('INFO')

class SQLType(Enum):
    INT = enum_auto()
    VARCHAR = enum_auto()
    DOUBLE = enum_auto()
    BOOLEAN = enum_auto()
    SMALLINT = enum_auto()
    JSONB = enum_auto()
    TIMESTAMP = enum_auto()

    @classmethod
    def from_name(cls, name: str):
        if name.lower() in sqltype_mapping:
            return sqltype_mapping[name.lower()]
        if name.startswith('character varying'):
            return SQLType.VARCHAR
        else:
            raise ValueError(f'Type {name} cannot be mapped to SQLType')

    @property
    def sql_name(self) -> str:
        return {SQLType.INT: 'integer', SQLType.VARCHAR: 'character varying', SQLType.DOUBLE: 'double precision', SQLType.BOOLEAN: 'boolean',
                SQLType.SMALLINT: 'smallint', SQLType.JSONB: 'jsonb', SQLType.TIMESTAMP: 'timestamp with time zone'}[self]
    
    def cast(self, value) -> Any:
        if value is None or value != value or (isinstance(value, str) and value == ''):
            return None
        try:
            if self in (SQLType.INT, SQLType.SMALLINT):
                return int(float(value))
            if self == SQLType.DOUBLE:
                return float(value)
            if self == SQLType.BOOLEAN:
                if isinstance(value, str):
                    return False if value.lower() in ('-', '0', 'false', 'no', 'off', 'нет', 'ложь') else bool(value)
            if self == SQLType.JSONB:
                return json.dumps(value)
            if self == SQLType.TIMESTAMP:
                if isinstance(value, time.struct_time):
                    return f'{value.tm_year}-{value.tm_mon:02}-{value.tm_mday:02} {value.tm_hour:02}:{value.tm_min:02}:{value.tm_sec:02}'
                else:
                    raise ValueError('Only time.struct_time can be cast to SQL Timestamp')
            else:
                raise NotImplementedError(f'Type {self} cast is not implemented for some reason')
        except Exception:
            return None

sqltype_mapping: Dict[str, SQLType] = dict(itertools.chain(
        map(lambda x: (x, SQLType.VARCHAR), ('character varying', 'varchar', 'str', 'string', 'text', 'varchar', 'строка')),
        map(lambda x: (x, SQLType.DOUBLE), ('double precision', 'float', 'double', 'вещественное', 'нецелое')),
        map(lambda x: (x, SQLType.INT), ('integer', 'int', 'number', 'целое')),
        map(lambda x: (x, SQLType.SMALLINT), ('smallint', 'малое', 'малое целое')),
        map(lambda x: (x, SQLType.JSONB), ('jsonb', 'json')),
        map(lambda x: (x, SQLType.BOOLEAN), ('boolean', 'булево')),
        map(lambda x: (x, SQLType.TIMESTAMP), ('timestamp', 'date', 'time', 'datetime', 'дата', 'время'))
))

def ensure_service_type(conn: psycopg2.connection, service_type: str, service_type_code: Optional[str],
        capacity_min: Optional[int], capacity_max: Optional[int], status_min: Optional[int], status_max: Optional[int],
        city_function: str, is_building: bool, commit: bool = True) -> int:
    '''ensure_service_type returns id of a service_type from database or inserts it if service_type is not present and all of the parameters are given'''
    with conn.cursor() as cur:
        cur.execute('SELECT id FROM city_service_types WHERE name = %s or code = %s', (service_type,) * 2)
        res = cur.fetchone()
        if res is not None:
            return res[0]
        if service_type_code is None or city_function is None:
            raise ValueError(f'service type "{service_type}" is not found in the database, but code and/or city_function is not provided')
        if capacity_min is None or capacity_max is None:
            raise ValueError(f'service type "{service_type}" is not found in the database, but capacity_min and/or capacity_max is not provided.')
        if status_min is None or status_max is None:
            raise ValueError(f'service type "{service_type}" is not found in the database, but status_min and/or status_max is not provided.')
        if is_building is None:
            raise ValueError(f'service type "{service_type}" is not found in the database, but is_building is not provided')
        cur.execute('INSERT INTO city_service_types (name, code, capacity_min, capacity_max, status_min, status_max, city_function_id, is_building) VALUES'
                ' (%s, %s, %s, %s, %s, %s, (SELECT id from city_functions WHERE name = %s or code = %s), %s) RETURNING ID',
                (service_type, service_type_code, capacity_min, capacity_max, status_min, status_max, city_function, city_function, is_building,))
        if commit:
            conn.commit()
        return cur.fetchone()[0]

InsertionMapping = NamedTuple('InsertionMapping', (
    ('name', Optional[str]),
    ('opening_hours', Optional[str]),
    ('website', Optional[str]),
    ('phone', Optional[str]),
    ('address', Optional[str]),
    ('capacity', Optional[str]),
    ('osm_id', Optional[str]),
    ('latitude', str),
    ('longitude', str)
))
def initInsertionMapping(name: Optional[str] = 'Name', opening_hours: Optional[str] = 'opening_hours', website: Optional[str] = 'contact:website',
        phone: Optional[str] = 'contact:phone', address: Optional[str] = 'yand_adr', osm_id: Optional[str] = 'id', capacity: Optional[str] = None,
        latitude: str = 'x', longitude: str = 'y') -> InsertionMapping:
    fixer = lambda s: None if s in ('', '-') else s
    return InsertionMapping(*map(fixer, (name, opening_hours, website, phone, address, capacity, osm_id)), latitude, longitude) # type: ignore

def insert_object(conn: psycopg2.connection, row: pd.Series, phys_id: int, service_type: str,
        service_type_id: int, mapping: InsertionMapping, commit: bool = True) -> int:
    '''insert_object inserts functional_object with connection to physical_object with phys_id.

    service_type_id must be vaild.
    
    Returns functional object id of the inserted object
    '''
    with conn.cursor() as cur:
        cur.execute('SELECT st.capacity_min, st.capacity_max, st.id, cf.id, it.id FROM city_infrastructure_types it'
                '   JOIN city_functions cf ON cf.city_infrastructure_type_id = it.id'
                '   JOIN city_service_types st ON st.city_function_id = cf.id'
                ' WHERE st.id = %s', (service_type_id,))
        mn, mx, *ids = cur.fetchone()
        assert ids[0] is not None and ids[1] is not None and ids[2] is not None, 'Service type, city function or infrastructure are not found in the database'
        cur.execute('INSERT INTO functional_objects (name, opening_hours, website, phone, city_service_type_id, city_function_id,'
                '   city_infrastructure_type_id, capacity, physical_object_id)'
                ' VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id',
                (
                        row.get(mapping.name) or f'({service_type} без названия)', row.get(mapping.opening_hours), row.get(mapping.website),
                        row.get(mapping.phone), *ids,
                        row[mapping.capacity] if mapping.capacity in row else (random.randint(mn, mx) if mn is not None and mx is not None else None),
                        phys_id
                )
        )
        func_id = cur.fetchone()[0]
        if commit:
            cur.execute('SAVEPOINT previous_object')
        return func_id


def update_object(conn: psycopg2.connection, row: pd.Series, func_id: int, mapping: InsertionMapping, service_type: str,
        commit: bool = True) -> int:
    '''update_object update functional_object and concrete <service_type>_object connected to it.

    service_type_id must be valid.
    
    Returns functional object id inserted
    '''
    with conn.cursor() as cur:
        cur.execute('SELECT name, opening_hours, website, phone, capacity FROM functional_objects WHERE id = %s', (func_id,))
        res = cur.fetchone()
        change = list(filter(lambda c_v_nw: c_v_nw[1] != c_v_nw[2] and c_v_nw[2] is not None, zip(
                ('name', 'opening_hours', 'website', 'phone', 'capacity'),
                res,
                (row.get(mapping.name) or f'({service_type} без названия)', row.get(mapping.opening_hours), row.get(mapping.website),
                        row.get(mapping.phone), row.get(mapping.capacity))
        )))
        t = time.localtime()
        current_time = f'{t.tm_year}-{t.tm_mon:02}-{t.tm_mday:02} {t.tm_hour:02}:{t.tm_min:02}:{t.tm_sec:02}'
        change.append(('updated_at', '', current_time))
        cur.execute(f'UPDATE functional_objects SET {", ".join(list(map(lambda x: x[0] + "=%s", change)))} WHERE id = %s',
                list(map(lambda x: x[2], change)) + [func_id])
        if commit:
            cur.execute('SAVEPOINT previous_object')
        return func_id


def add_objects(conn: psycopg2.connection, objects: pd.DataFrame, city_name: str, service_type: str, service_type_id: int,
        mapping: InsertionMapping, address_prefixes: List[str] = ['Россия, Санкт-Петербург'], new_prefix: str = '',
        is_service_building: bool = True, commit: bool = True, verbose: bool = False) -> pd.DataFrame:
    '''add_objects inserts objects to database.

    Input:

        - `conn` - connection for the database
        - `objects` - DataFrame containing objects
        - `city_name` - name of the city to add objects to. Must be created in the database
        - `service_type` - name of service_type for logging and services names fillment if they are missing
        - `service_type_id` - id of service_type (got by `ensure_service_type` function), must be valid
        - `mapping` - InsertionMapping of namings in the database and namings in the DataFrame columns
        - `address_prefixes` - list of possible prefixes (will be sorted by length)
        - `new_prefix` - unified prefix for all of the inserted objects
        - `is_service_building` - True if there is need to use address, search or insert buildings
        - `commit` - True to commit changes, False for dry run, only resulting DataFrame is returned
        - `verbose` - True to output traceback with errors, False for only error messages printing

    Return:

        - dataframe of objects with "result" column added and "functional_obj_id" columns added

    Algorithm steps:

        1. If latitude or longitude is invaild, or address does not start with any of prefixes (if `is_service_building` == True), skip

        2. Check if building with given address is present in the database (if `is_service_building` == True)

        3. If found:

            3.1. If functional object with the same name and service_type_id is already connected to the physical object, update by calling `update_object`

            3.2. Else get building id and physical_object id

        4. Else:
            
            4.1. If there is physical object (building if only `is_service_building` == True) which geometry contains current object's coordinates,
                 get its physical_object id and building id if needed

            4.2. Else insert physical_object/building with geometry type Point

            4.3. Else include inserted ids in the result

        5. Insert functional_object connected to physical_object by calling `insert_object`
    '''
    log.info(f'Вставка сервисов запущена из {"командной строки" if __name__ == "__main__" else "внешнего приложения"}')
    log.info(f'Вставка сервисов типа "{service_type}" (id {service_type_id}), всего {objects.shape[0]} объектов')
    log.info(f'Город вставки - "{city_name}". Список префиксов: {address_prefixes}, новый префикс: "{new_prefix}"')

    if mapping.address in objects.columns:
        objects[mapping.address] = objects[mapping.address].apply(lambda x: x.replace('?', '').strip() if isinstance(x, str) else None)
    present = 0 # objects already present in the database
    added_to_address, added_to_geom, added_as_points, skipped = 0, 0, 0, 0
    results: List[str] = list(('',) * objects.shape[0])
    functional_ids: List[int] = [-1 for _ in range(objects.shape[0])]
    address_prefixes = sorted(address_prefixes, key=lambda s: -len(s))
    with conn.cursor() as cur:
        cur.execute('SELECT id FROM cities WHERE name = %s', (city_name,))
        city_id = cur.fetchone()
        if city_id is None:
            log.error(f'Заданный город "{city_name}" отсутствует в базе данных')
            objects['result'] = pd.Series([f'Город "{city_name}" отсутсвует в базе данных'] * objects.shape[0], index=objects.index)
            objects['functional_obj_id'] = pd.Series([-1] * objects.shape[0], index=objects.index)
            return objects
        city_id = city_id[0]
        if commit:
            cur.execute('SAVEPOINT previous_object')
        for i, (_, row) in enumerate(objects.iterrows()):
            try:
                try:
                    row[mapping.latitude] = round(float(row[mapping.latitude]), 6)
                    row[mapping.longitude] = round(float(row[mapping.longitude]), 6)
                except Exception:
                    results[i] = 'Пропущен (широта или долгота некорректны)'
                    skipped += 1
                    continue
                if is_service_building:
                    for address_prefix in address_prefixes:
                        if row.get(mapping.address, '').startswith(address_prefix):
                            break
                    else:
                        if len(address_prefixes) == 1:
                            results[i] = f'Пропущен (Адрес не начинается с "{address_prefixes[0]}")'
                        else:
                            results[i] = f'Пропущен (Адрес не начинается ни с одного из {len(address_prefixes)} префиксов)'
                        skipped += 1
                        continue
                if is_service_building and mapping.address not in row or mapping.latitude not in row or mapping.longitude not in row:
                    results[i] = f'Пропущен (отсутствует как минимум одно необходимое поле: широта ({mapping.latitude}), долгота({mapping.longitude})' + \
                            f', адрес({mapping.address}))' if is_service_building else ')'
                    skipped += 1
                    continue
                name = row.get(mapping.name) or f'({service_type} без названия)'
                phys_id: int
                build_id: Optional[int]
                insert_physical_object = False
                if is_service_building:
                    cur.execute('SELECT phys.id, build.id FROM physical_objects phys JOIN buildings build ON build.physical_object_id = phys.id'
                            ' WHERE phys.city_id = %s AND build.address LIKE %s AND'
                            '   ST_Distance(phys.center::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography) < 100 LIMIT 1',
                            (city_id, '%' + row.get(mapping.address)[len(address_prefix):].strip(', '), row[mapping.longitude], row[mapping.latitude]))
                    res = cur.fetchone()
                    if res is not None: # if building with the same address found and distance between point and the center of geometry is less than 100m
                        phys_id, build_id = res
                        cur.execute('SELECT id FROM functional_objects f'
                                ' WHERE physical_object_id = %s AND city_service_type_id = %s AND name = %s LIMIT 1', (phys_id, service_type_id, name))
                        res = cur.fetchone()
                        if res is not None: # if service is already present in this building
                            present += 1
                            results[i] = f'Обновлен существующий сервис (build_id = {build_id}, phys_id = {phys_id}, functional_object_id = {res[0]})'
                            functional_ids[i] = res[0]
                            update_object(conn, row, res[0], mapping, service_type, commit)
                            continue
                        else:
                            added_to_address += 1
                            results[i] = f'Сервис вставлен в здание, найденное по совпадению адреса (build_id = {build_id}, phys_id = {phys_id}).'
                    else: # if no building with the same address found or distance is too high (address is wrong or it's not a concrete house)
                        cur.execute('SELECT phys.id, build.id, build.address FROM physical_objects phys JOIN buildings build ON build.physical_object_id = phys.id'
                            ' WHERE city_id = %s AND (ST_CoveredBy(ST_SetSRID(ST_MakePoint(%s, %s), 4326), geometry) OR'
                            "   ST_GeometryType(geometry) = 'ST_Point' AND abs(ST_X(geometry) - %s) < 0.0001 AND abs(ST_Y(geometry) - %s) < 0.0001)"
                            ' LIMIT 1',
                            (city_id,) + (row[mapping.longitude], row[mapping.latitude]) * 2)
                        res = cur.fetchone()
                        if res is not None: # if building found by geometry
                            phys_id, build_id, address = res
                            cur.execute('SELECT id FROM functional_objects f'
                                    ' WHERE physical_object_id = %s AND city_service_type_id = %s AND name = %s LIMIT 1', (phys_id, service_type_id, name))
                            res = cur.fetchone()
                            if res is not None: # if service is already present in this building
                                present += 1
                                results[i] = f'Обновлен существующий сервис, находящийся в здании с другим адресом: "{address}"' \
                                        f' (build_id = {build_id}, phys_id = {phys_id}, functional_object_id = {res[0]})'
                                functional_ids[i] = res[0]
                                update_object(conn, row, res[0], mapping, service_type, commit)
                                continue
                            else: # if no service present, but buiding found
                                added_to_geom += 1
                                results[i] = f'Сервис вставлен в здание, подходящее по геометрии, но имеющее другой адрес: "{address}"' \
                                                f' (build_id = {build_id}, phys_id = {phys_id})'
                        else: # if no building found by address or geometry
                            insert_physical_object = True
                else:
                    cur.execute('SELECT id FROM physical_objects phys'
                            ' WHERE city_id = %s AND (SELECT EXISTS (SELECT 1 FROM buildings where physical_object_id = phys.id)) = false AND'
                            '   (ST_CoveredBy(ST_SetSRID(ST_MakePoint(%s, %s), 4326), geometry) OR'
                            "       ST_GeometryType(geometry) = 'ST_Point' AND abs(ST_X(geometry) - %s) < 0.0001 AND abs(ST_Y(geometry) - %s) < 0.0001)"
                            ' LIMIT 1',
                            (city_id,) + (row[mapping.longitude], row[mapping.latitude]) * 2)
                    res = cur.fetchone()
                    if res is not None: # if physical_object found by geometry
                        phys_id = res[0]
                        cur.execute('SELECT id FROM functional_objects f '
                                ' WHERE physical_object_id = %s AND city_service_type_id = %s AND name = %s'
                                ' LIMIT 1',
                                (phys_id, service_type_id, name))
                        res = cur.fetchone()
                        if res is not None: # if service is already present in this pysical_object
                            present += 1
                            results[i] = f'Обновлен существующий сервис без здания' \
                                    f' (phys_id = {phys_id}, functional_object_id = {res[0]})'
                            functional_ids[i] = res[0]
                            update_object(conn, row, res[0], mapping, service_type, commit)
                            continue
                        else: # if no service present, but physical_object found
                            added_to_geom += 1
                            results[i] = f'Сервис вставлен в физический объект, подходящий по геометрии (phys_id = {phys_id})'
                    else:
                        insert_physical_object = True
                if insert_physical_object:
                    cur.execute('INSERT INTO physical_objects (osm_id, geometry, center, city_id) VALUES'
                            ' (%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s) RETURNING id',
                            (row.get(mapping.osm_id), row[mapping.longitude], row[mapping.latitude], row[mapping.longitude], row[mapping.latitude], city_id))
                    phys_id = cur.fetchone()[0]
                    if is_service_building and mapping.address in row and len(row.get(mapping.address)) != len(address_prefix):
                        cur.execute("INSERT INTO buildings (physical_object_id, address) VALUES (%s, %s) RETURNING id",
                                    (phys_id, new_prefix + row[mapping.address][len(address_prefix):].strip(', ')))
                        build_id = cur.fetchone()[0]
                        results[i] = f'Сервис вставлен в новое здание, добавленное с типом геометрии "Точка" (build_id = {build_id}, phys_id = {phys_id})'
                    else:
                        results[i] = f'Сервис вставлен в новый физический объект, добавленный с типом геометрии "Точка" (phys_id = {phys_id})'
                    added_as_points += 1
                functional_ids[i] = insert_object(conn, row, phys_id, service_type, service_type_id, mapping, commit)
            except Exception as ex:
                log.error(f'Произошла ошибка: {ex}')
                if verbose:
                    log.error('Traceback:\ntraceback.format_exc()')
                if commit:
                    cur.execute('ROLLBACK TO previous_object')
                else:
                    conn.rollback()
                results[i] = f'Пропущен, вызывает ошибку: {ex}'
                skipped += 1
        if commit:
            conn.commit()
    objects['result'] = pd.Series(results, index=objects.index)
    objects['functional_obj_id'] = pd.Series(functional_ids, index=objects.index)
    log.info(f'Вставка сервисов типа "{service_type}" завершена')
    log.info(f'{len(objects)} сервисов обработано: {added_as_points + added_to_address + added_to_geom} добавлены,'
            f' {present} обновлены, {skipped} пропущены')
    log.info(f'{added_as_points} сервисов были добавлены с типом геометрии "точка", {added_to_address} добавлены в здания по совпадению адреса,'
        f' {added_to_geom} добавлены в физические объекты/здания по совпадению геометрии')
    filename = f'insertion_{conn.info.host}_{conn.info.port}_{conn.info.dbname}.xlsx'
    list_name = f'{service_type.replace("/", "_")}_{time.strftime("%Y-%m-%d %H_%M-%S")}'
    try:
        with pd.ExcelWriter(filename, mode = ('a' if os.path.isfile(filename) else 'w')) as writer:
            objects.to_excel(writer, list_name)
        log.info(f'Лог вставки сохранен в файл "{filename}", лист "{list_name}"')
    except Exception:
        log.error(f'Ошибка при сохранении лога вставки в файл "{filename}", лист "{list_name}"')
    return objects


def replace_with_default(df: pd.DataFrame, default_values: Dict[str, Any]) -> pd.DataFrame:
    '''replace_with_default replace null items in dataframe in given columns with given values.

    `default_values` is a dictionary with columns names as key and default values for them as values.
    
    If column is missing, it will be created filled fully with default values

    Returns new dataframe with null entries replaced with given defaults
    '''
    for (column, value) in default_values.items():
        if column in df:
            df[column] = df[column].fillna(value)
        else:
            df[column] = pd.DataFrame([value] * df.shape[0])
    return df


def load_objects_geojson(filename: str, default_values: Optional[Dict[str, Any]] = None, needed_columns: Optional[Iterable[str]] = None) -> pd.DataFrame:
    '''load_objects_geojson loads objects as DataFrame from geojson. It contains only [features][properties] columns.
    Calls `replace_with_default` after load if `default_values` is present
    '''
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
        properties = pd.DataFrame(data['features'])['properties']
        res: pd.DataFrame = pd.DataFrame(map(lambda x: x.values(), properties), columns=properties[0].keys())
        if default_values is not None:
            res = replace_with_default(res, default_values)
        if needed_columns is not None:
            res = res[needed_columns]
        return res.dropna(how='all').reset_index(drop=True).where(pd.DataFrame.notnull(res), None)


def load_objects_json(filename: str, default_values: Optional[Dict[str, Any]] = None, needed_columns: Optional[Iterable[str]] = None) -> pd.DataFrame:
    '''load_objects_json loads objects as DataFrame from json by calling pd.read_json.
    Calls `replace_with_default` after load if `default_values` is present
    '''
    res: pd.DataFrame = pd.read_json(filename)
    if default_values is not None:
        res = replace_with_default(res, default_values)
    if needed_columns is not None:
        res = res[needed_columns]
    return res.dropna(how='all').reset_index(drop=True).where(pd.DataFrame.notnull(res), None)


def load_objects_csv(filename: str, default_values: Optional[Dict[str, Any]] = None, needed_columns: Optional[Iterable[str]] = None) -> pd.DataFrame:
    '''load_objects_csv loads objects as DataFrame from csv by calling pd.read_csv.
    Calls `replace_with_default` after load if `default_values` is present
    '''
    res: pd.DataFrame = pd.read_csv(filename)
    if default_values is not None:
        res = replace_with_default(res, default_values)
    if needed_columns is not None:
        res = res[needed_columns]
    return res.dropna(how='all').reset_index(drop=True).where(pd.DataFrame.notnull(res), None)


def load_objects_xlsx(filename: str, default_values: Optional[Dict[str, Any]] = None, needed_columns: Optional[Iterable[str]] = None) -> pd.DataFrame:
    '''load_objects_xlcx loads objects as DataFrame from xlsx by calling pd.read_excel (need to have `openpyxl` Pyhton module installed).
    Calls `replace_with_default` after load if `default_values` is present
    '''
    res: pd.DataFrame = pd.read_excel(filename, engine='openpyxl')
    if default_values is not None:
        res = replace_with_default(res, default_values)
    if needed_columns is not None:
        res = res[needed_columns]
    return res.dropna(how='all').reset_index(drop=True).where(pd.DataFrame.notnull(res), None)


def load_objects_excel(filename: str, default_values: Optional[Dict[str, Any]] = None, needed_columns: Optional[Iterable[str]] = None) -> pd.DataFrame:
    '''load_objects_excel loads objects as DataFrame from xls or ods by calling pd.read_excel
        (need to have `xlrd` Pyhton module installed for xls and `odfpy` for ods).
    Calls `replace_with_default` after load if `default_values` is present
    '''
    res: pd.DataFrame = pd.read_excel(filename)
    if default_values is not None:
        res = replace_with_default(res, default_values)
    if needed_columns is not None:
        res = res[needed_columns]
    return res.dropna(how='all').reset_index(drop=True).where(pd.DataFrame.notnull(res), None)


def load_objects(filename: str, default_values: Optional[Dict[str, Any]] = None, needed_columns: Optional[Iterable[str]] = None) -> pd.DataFrame:
    funcs = {'csv': load_objects_csv, 'xlsx': load_objects_xlsx, 'xls': load_objects_excel,
            'ods': load_objects_excel, 'json': load_objects_json, 'geojson': load_objects_geojson}
    try:
        return funcs[filename[filename.rfind('.') + 1:]](filename, default_values, needed_columns)
    except KeyError:
        raise ValueError(f'File extension "{args.filename[args.filename.rfind(".") + 1:]}" is not supported')
    

if __name__ == '__main__':

    log.handlers[1].setLevel('INFO')

    properties = Properties('localhost', 5432, 'citydb', 'postgres', 'postgres')

    parser = argparse.ArgumentParser(description='Inserts functional objects to the database')
    parser.add_argument('-H', '--db_addr', action='store', dest='db_addr',
                        help=f'postgres host address [default: {properties.db_addr}]', type=str)
    parser.add_argument('-P', '--db_port', action='store', dest='db_port',
                        help=f'postgres port number [default: {properties.db_port}]', type=int)
    parser.add_argument('-d', '--db_name', action='store', dest='db_name',
                        help=f'postgres database name [default: {properties.db_name}]', type=str)
    parser.add_argument('-U', '--db_user', action='store', dest='db_user',
                        help=f'postgres user name [default: {properties.db_user}]', type=str)
    parser.add_argument('-W', '--db_pass', action='store', dest='db_pass',
                        help=f'postgres user password [default: {properties.db_pass}]', type=str)

    parser.add_argument('-D', '--dry_run', action='store_true', dest='dry_run',
                        help=f'do not commit anything to the database, only output log file')
    parser.add_argument('-v', '--verbose', action='store_true', dest='verbose',
                        help=f'output stack trace when error happens')
    parser.add_argument('-l', '--log', action='store', dest='log_filename',
                        help=f'path to create log file [default: current datetime "YYYY-MM-DD HH-mm-ss-<filename>.csv"]', type=str)
    parser.add_argument('-c', '--city', action='store', dest='city',
                        help=f'name of the city, must be in the database [required]', type=str, required=True)
    parser.add_argument('-T', '--service_type', action='store', dest='service_type',
                        help=f'service type name (for service_types table) [required]', type=str, required=True)
    parser.add_argument('-C', '--service_type_code', action='store', dest='service_type_code',
                        help=f'service type code (for service_types table) [required to insert, default null]', type=str)
    parser.add_argument('-f', '--city_function', action='store', dest='city_function',
                        help=f'name/code of city function of service type (from city_functions table) [required to insert, default null]', type=str)
    parser.add_argument('-mC', '--min_capacity', action='store', dest='min_capacity',
                        help=f'service type minimum capacity (for service_types table) [default null]', type=int)
    parser.add_argument('-MC', '--max_capacity', action='store', dest='max_capacity',
                        help=f'service type maximum capacity (for service_types table) [default null]', type=int)
    parser.add_argument('-mS', '--min_status', action='store', dest='min_status',
                        help=f'service type minimum status (for service_types table) [default null]', type=int)
    parser.add_argument('-MS', '--max_status', action='store', dest='max_status',
                        help=f'service type maximum status (for service_types table) [default null]', type=int)
    
    parser.add_argument('-dx', '--document_latitude', action='store', dest='latitude',
                        help=f'[default x]', type=str, default='x')
    parser.add_argument('-dy', '--document_longitude', action='store', dest='longitude',
                        help=f'[default y]', type=str, default='y')
    parser.add_argument('-dN', '--document_name', action='store', dest='name',
                        help=f'[default name]', type=str, default='name')
    parser.add_argument('-dO', '--document_opening_hours', action='store', dest='opening_hours',
                        help=f'[default opening_hours]', type=str, default='opening_hours')
    parser.add_argument('-dW', '--document_website', action='store', dest='website',
                        help=f'[default contact:website]', type=str, default='contact:website')
    parser.add_argument('-dP', '--document_phone', action='store', dest='phone',
                        help=f'[default contact:phone]', type=str, default='contact:phone')
    parser.add_argument('-dC', '--document_capacity', action='store', dest='capacity',
                        help=f'[default -]', type=str, default='-')
    parser.add_argument('-dAD', '--document_address', action='store', dest='address',
                        help=f'[default yand_adr]', type=str, default='yand_adr')
    parser.add_argument('-dAP', '--document_address_prefix', action='append', dest='adr_prefixes',
                        help=f'[default "Россия, Санкт-Петербург" (comma and space are not needed, adderess will be cut)], you can add multiple prefixes',
                        type=str, default=[])
    parser.add_argument('-nAP', '--new_address_prefix', action='store', dest='new_address_prefix',
                        help=f'[default (empty)]', type=str, default='')
    parser.add_argument('-dI', '--document_osm_id', action='store', dest='osm_id',
                        help=f'[default id]', type=str, default='id')

    parser.add_argument('filename', action='store', help=f'path to file with data [required]', type=str)
    args = parser.parse_args()

    if len(args.adr_prefixes) == 0:
        args.adr_prefixes.append('Россия, Санкт-Петербург')
    else:
        args.adr_prefixes.sort(key=len, reverse=True)

    assert os.path.isfile(args.filename), 'Input file is not found. Exiting'

    if args.db_addr is not None:
        properties.db_addr = args.db_addr
    if args.db_port is not None:
        properties.db_port = args.db_port
    if args.db_name is not None:
        properties.db_name = args.db_name
    if args.db_user is not None:
        properties.db_user = args.db_user
    if args.db_pass is not None:
        properties.db_pass = args.db_pass
    if args.log_filename is None:
        t = time.localtime()
        fname = args.filename if os.path.sep not in os.path.relpath(args.filename) else args.filename[os.path.relpath(args.filename).rfind(os.path.sep) + 1:]
        logfile = f'{t.tm_year}-{t.tm_mon:02}-{t.tm_mday:02} ' \
                f'{t.tm_hour:02}-{t.tm_min:02}-{t.tm_sec:02}-' \
                f'{fname[:fname.rfind(".")] if "." in fname else fname}.csv'
        if os.path.isfile(logfile):
            logfile = f'{logfile[-4:]}-{time.time()}.csv'
        del fname
    else:
        logfile = args.log_filename

    mapping = initInsertionMapping(args.name, args.opening_hours, args.website, args.phone, args.address, args.osm_id, args.capacity, args.latitude, args.longitude)
    log.info("Document's mapping:", mapping)

    log.info(f'Using database {properties.db_user}@{properties.db_addr}:{properties.db_port}/{properties.db_name}. ', end='')
    if args.dry_run:
        log.info('Dry run, no changes to database will be made')
    else:
        log.info('Objects will be written to the database')
    log.info(f'Output log file - "{logfile}"')

    objects: pd.DataFrame = load_objects(args.filename)
    log.info(f'Loaded {objects.shape[0]} objects from file "{args.filename}"')

    service_id = ensure_service_type(properties.conn, args.service_type, args.service_type_code, args.min_capacity, args.max_capacity,
            args.min_status, args.max_status, args.city_function, not args.dry_run)
    objects = add_objects(properties.conn, objects, args.city, args.service_type, service_id, mapping, args.adr_prefixes,
            args.new_address_prefix, not args.dry_run, args.verbose)

    objects.to_csv(logfile)
    log.info(f'Finished, result is written to {logfile}')
