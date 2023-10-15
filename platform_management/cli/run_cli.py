"""Command Line Interface launch logic is defined here."""
from __future__ import annotations

import os
import sys
import time

import psycopg2
from loguru import logger

from platform_management.cli.defaults import InsertBuildings as DefaultValues
from platform_management.dto import (
    AdmDivisionInsertionMapping,
    BuildingInsertionCLIParameters,
    BuildingInsertionMapping,
    DatabaseCredentials,
    ServiceInsertionMapping,
)

from .adm_division import AdmDivisionType, add_adm_division
from .blocks import add_blocks
from .buildings import add_buildings
from .files import load_objects
from .services import add_services

LOG_HANDLER_ID = logger.add(
    "platform_management_insertion.log",
    level="INFO",
    filter=__name__,
    colorize=False,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: ^8} | {message}",
)


def _common(
    dry_run: bool,
    verbose: bool,
    log_filename: str | None,
    database_credentials: DatabaseCredentials,
    filename: str,
) -> tuple[str, "psycopg2.connection"]:
    """Perform common operations for all CLI processes.

    Returns logfile name and database connection object.
    """
    global LOG_HANDLER_ID  # pylint: disable=global-statement
    if verbose:
        logger.remove(LOG_HANDLER_ID)
        LOG_HANDLER_ID = logger.add(
            "insert_services.log",
            level="DEBUG",
            filter=__name__,
            colorize=False,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: ^8} | {message}",
        )

    logger.remove(0)
    logger.add(
        sys.stderr,
        level="INFO" if not verbose else "DEBUG",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: ^8}</level>"
        " | <cyan>{line:03}</cyan> - <level>{message}</level>",
    )

    if not os.path.isfile(filename):
        logger.error('Входной файл "{}" не найден или не является файлом, завершение работы', filename)
        sys.exit(1)

    if log_filename is None:
        t = time.localtime()  # pylint: disable=invalid-name
        fname = os.path.split(filename)[1]

        logfile = (
            f"{t.tm_year}-{t.tm_mon:02}-{t.tm_mday:02} "
            f"{t.tm_hour:02}-{t.tm_min:02}-{t.tm_sec:02}-"
            f'{fname[:fname.rfind(".")] if "." in fname else fname}.csv'
        )
        if os.path.isfile(logfile):
            logfile = f"{logfile[-4:]}-{time.time()}.csv"
        del fname
    else:
        if log_filename not in ("", "-"):
            logfile = log_filename
        else:
            logfile = None

    if log_filename is not None:
        logger.opt(colors=True).info(f'Сохарнение лога будет произведено в файл <cyan>"{logfile}"</cyan>')

    logger.opt(colors=True).info(
        "Подключение к базе данных <cyan>{}@{}:{}/{}</cyan>.",
        database_credentials.user,
        database_credentials.address,
        database_credentials.port,
        database_credentials.name,
    )

    conn = psycopg2.connect(**database_credentials.get_connection_params())

    if dry_run:
        logger.warning("Холостой запуск, изменения не будут сохранены")
    else:
        logger.info("Загруженные объекты будут сохранены в базе данных")

    return logfile, conn


def insert_services_cli(  # pylint: disable=too-many-arguments,too-many-locals
    database_credentials: DatabaseCredentials,
    dry_run: bool,
    verbose: bool,
    log_filename: str | None,
    city: str,
    service_type: str,
    columns_mapping: ServiceInsertionMapping,
    address_prefix: list[str],
    new_address_prefix: str,
    properties_mapping: list[str],
    filename: str,
):
    """Run services insertion command line interface with the given parameters."""
    address_prefixes = list(address_prefix)
    if len(address_prefixes) == 0:
        address_prefixes.append("Россия, Санкт-Петербург")
    else:
        address_prefixes.sort(key=len, reverse=True)

    for entry in properties_mapping:
        if ":" not in entry:
            logger.error('Properties mapping "{}" does not set a mapping (missing ":"). Exiting', entry)
            sys.exit(1)

    properties_mapping_dict = {entry[: entry.find(":")]: entry[entry.find(":") + 1 :] for entry in properties_mapping}

    logger.info("Соответствие (маппинг) документа: {}", columns_mapping)

    logfile, conn = _common(dry_run, verbose, log_filename, database_credentials, filename)

    services = load_objects(filename)
    logger.info('Загружено {} объектов из файла "{}"', services.shape[0], filename)
    for column, value in vars(columns_mapping).items():
        if value is not None and value not in services.columns:
            logger.warning('Столбец "{}" используется ({}), но не задан в файле', value, column)

    services = add_services(
        conn,
        services,
        city,
        service_type,
        columns_mapping,
        properties_mapping_dict,
        address_prefixes,
        new_address_prefix,
        not dry_run,
        verbose,
    )

    if logfile is not None:
        services.to_csv(logfile)
    logger.opt(colors=True).info('Завершено, лог записан в файл <green>"{}"</green>', logfile)


def insert_buildings_cli(  # pylint: disable=too-many-arguments,too-many-locals
    database_credentials: DatabaseCredentials,
    dry_run: bool,
    verbose: bool,
    log_filename: str | None,
    city: str,
    columns_mapping: BuildingInsertionCLIParameters,
    address_prefix: list[str],
    new_address_prefix: str,
    properties_mapping: list[str],
    filename: str,
):
    """Run services insertion command line interface with the given parameters."""
    address_prefixes = list(address_prefix)
    if len(address_prefixes) == 0:
        address_prefixes.append("Россия, Санкт-Петербург")
    else:
        address_prefixes.sort(key=len, reverse=True)

    for entry in properties_mapping:
        if ":" not in entry:
            logger.error('Properties mapping "{}" does not set a mapping (missing ":"). Exiting', entry)
            sys.exit(1)

    properties_mapping_dict = {entry[: entry.find(":")]: entry[entry.find(":") + 1 :] for entry in properties_mapping}

    logfile, conn = _common(dry_run, verbose, log_filename, database_credentials, filename)

    buildings_df = load_objects(filename)
    logger.info('Загружено {} объектов из файла "{}"', buildings_df.shape[0], filename)

    # Получение ColumnMapping'а из MultipleColumnMapping'а с выводом warning'ов в случае, когда пользователь явно задал
    #   варианты опций, но они не были найдены в файле
    found_columns: dict[str, str] = {}
    for column, value_options in vars(columns_mapping).items():
        value_options: list[str]
        defaults_used = value_options is None
        if defaults_used:
            value_options = getattr(DefaultValues, f"document_{column}")

        for value in value_options:
            if value in buildings_df.columns:
                found_columns[column] = value
                break
        else:
            if not defaults_used:
                logger.warning(
                    'Значение для атрибута в БД "{}" задано при загрузке ({}), но не обнаружено в файле',
                    column,
                    (", ".join(map(lambda s: f'"{s}" ', value_options))),
                )
            else:
                logger.debug(
                    'Значение для атрибута в БД "{}" не было обнаружено в документе из значений по-умолчанию', column
                )
    new_columns_mapping = BuildingInsertionMapping(**found_columns)
    logger.info("Соответствие (маппинг) документа: {}", new_columns_mapping)

    buildings_df = add_buildings(
        conn,
        buildings_df,
        city,
        new_columns_mapping,
        properties_mapping_dict,
        address_prefixes,
        new_address_prefix,
        not dry_run,
        verbose,
    )

    if logfile is not None:
        buildings_df.to_csv(logfile)
    logger.opt(colors=True).info('Завершено, лог записан в файл <green>"{}"</green>', logfile)


def insert_blocks_cli(  # pylint: disable=too-many-arguments
    database_credentials: DatabaseCredentials,
    dry_run: bool,
    verbose: bool,
    log_filename: str | None,
    city: str,
    geometry_column: str,
    filename: str,
):
    """Run services insertion command line interface with the given parameters."""
    logfile, conn = _common(dry_run, verbose, log_filename, database_credentials, filename)

    blocks = load_objects(filename)
    logger.info('Загружено {} объектов из файла "{}"', blocks.shape[0], filename)
    assert geometry_column is not None
    if geometry_column not in blocks.columns:
        logger.error('Столбец "{}" используется как геометрия кварталов, но не задан в файле', geometry_column)
        sys.exit(1)

    blocks = add_blocks(
        conn,
        blocks,
        city,
        geometry_column,
        not dry_run,
        verbose,
    )

    if logfile is not None:
        blocks.to_csv(logfile)
    logger.opt(colors=True).info('Завершено, лог записан в файл <green>"{}"</green>', logfile)


def insert_adms_cli(  # pylint: disable=too-many-arguments
    database_credentials: DatabaseCredentials,
    dry_run: bool,
    verbose: bool,
    log_filename: str | None,
    city: str,
    division_type: AdmDivisionType,
    mapping: AdmDivisionInsertionMapping,
    filename: str,
    default_type_name: str | None = None,
):
    """Run services insertion command line interface with the given parameters."""
    logfile, conn = _common(dry_run, verbose, log_filename, database_credentials, filename)

    adms_df = load_objects(filename)
    if default_type_name is not None:
        if mapping.type_name not in adms_df.columns:
            adms_df[mapping.type_name] = [default_type_name] * adms_df.shape[0]
        else:
            adms_df[mapping.type_name] = adms_df[mapping.type_name].fillna(default_type_name)
    logger.info('Загружено {} объектов из файла "{}"', adms_df.shape[0], filename)
    if mapping.geometry not in adms_df.columns:
        logger.error(
            'Столбец "{}" используется как геометрия территориальных единиц, но не задан в файле', mapping.geometry
        )
        sys.exit(1)

    adms_df = add_adm_division(
        conn,
        adms_df,
        city,
        division_type,
        mapping,
        not dry_run,
        verbose,
    )

    if logfile is not None:
        adms_df.to_csv(logfile)
    logger.opt(colors=True).info('Завершено, лог записан в файл <green>"{}"</green>', logfile)
