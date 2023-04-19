"""
Command Line Interface launch logic is defined here.
"""
import os
import sys
import time
from typing import List, Optional

import psycopg2
from loguru import logger

from .files import load_objects
from .buildings import add_buildings
from .services import add_services
from .mappings import BuildingInsertionMapping, ServiceInsertionMapping

LOG_HANDLER_ID = logger.add(
    "platform_management_insertion.log",
    level="INFO",
    filter=__name__,
    colorize=False,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: ^8} | {message}",
)


def insert_services_cli(  # pylint: disable=too-many-branches,too-many-statements,too-many-arguments,too-many-locals
    db_addr: str,
    db_port: int,
    db_name: str,
    db_user: str,
    db_pass: str,
    dry_run: bool,
    verbose: bool,
    log_filename: Optional[str],
    city: str,
    service_type: str,
    columns_mapping: ServiceInsertionMapping,
    address_prefix: List[str],
    new_address_prefix: str,
    properties_mapping: List[str],
    filename: str,
):
    """
    Run services insertion command line interface with the given parameters.
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

    address_prefixes = list(address_prefix)
    if len(address_prefixes) == 0:
        address_prefixes.append("Россия, Санкт-Петербург")
    else:
        address_prefixes.sort(key=len, reverse=True)

    for entry in properties_mapping:
        if ":" not in entry:
            logger.error(f'Properties mapping "{entry}" does not set a mapping (missing ":"). Exiting')
            sys.exit(1)

    properties_mapping_dict = {entry[: entry.find(":")]: entry[entry.find(":") + 1 :] for entry in properties_mapping}

    if not os.path.isfile(filename):
        logger.error(f'Входной файл "{filename}" не найден или не является файлом, завершение работы')
        sys.exit(1)

    if log_filename is None:
        t = time.localtime()  # pylint: disable=invalid-name
        fname: str
        if os.path.sep in os.path.relpath(filename):  # type: ignore
            fname = os.path.relpath(filename)[os.path.relpath(filename).rfind(os.path.sep) + 1 :]  # type: ignore
        else:
            fname = filename

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

    logger.info(f"Соответствие (маппинг) документа: {columns_mapping}")

    logger.opt(colors=True).info(f"Подключение к базе данных <cyan>{db_user}@{db_addr}:{db_port}/{db_name}</cyan>.")

    conn = psycopg2.connect(
        host=db_addr, port=db_port, dbname=db_name, user=db_user, password=db_pass, connect_timeout=20
    )

    if dry_run:
        logger.warning("Холостой запуск, изменения не будут сохранены")
    else:
        logger.info("Загруженные объекты будут сохранены в базе данных")
    if logfile is not None:
        logger.opt(colors=True).info(f'Сохарнение лога будет произведено в файл <cyan>"{logfile}"</cyan>')

    services = load_objects(filename)
    logger.info(f'Загружено {services.shape[0]} объектов из файла "{filename}"')
    for column, value in vars(columns_mapping).items():
        if value is not None and value not in services.columns:
            logger.warning(f'Столбец "{value}" используется ({column}), но не задан в файле')

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
    logger.opt(colors=True).info(f'Завершено, лог записан в файл <green>"{logfile}"</green>')


def insert_buildings_cli(  # pylint: disable=too-many-branches,too-many-statements,too-many-arguments,too-many-locals
    db_addr: str,
    db_port: int,
    db_name: str,
    db_user: str,
    db_pass: str,
    dry_run: bool,
    verbose: bool,
    log_filename: Optional[str],
    city: str,
    columns_mapping: BuildingInsertionMapping,
    address_prefix: List[str],
    new_address_prefix: str,
    properties_mapping: List[str],
    filename: str,
):
    """
    Run services insertion command line interface with the given parameters.
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

    address_prefixes = list(address_prefix)
    if len(address_prefixes) == 0:
        address_prefixes.append("Россия, Санкт-Петербург")
    else:
        address_prefixes.sort(key=len, reverse=True)

    for entry in properties_mapping:
        if ":" not in entry:
            logger.error(f'Properties mapping "{entry}" does not set a mapping (missing ":"). Exiting')
            sys.exit(1)

    properties_mapping_dict = {entry[: entry.find(":")]: entry[entry.find(":") + 1 :] for entry in properties_mapping}

    if not os.path.isfile(filename):
        logger.error(f'Входной файл "{filename}" не найден или не является файлом, завершение работы')
        sys.exit(1)

    if log_filename is None:
        t = time.localtime()  # pylint: disable=invalid-name
        fname: str
        if os.path.sep in os.path.relpath(filename):  # type: ignore
            fname = os.path.relpath(filename)[os.path.relpath(filename).rfind(os.path.sep) + 1 :]  # type: ignore
        else:
            fname = filename

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

    logger.info(f"Соответствие (маппинг) документа: {columns_mapping}")

    logger.opt(colors=True).info(f"Подключение к базе данных <cyan>{db_user}@{db_addr}:{db_port}/{db_name}</cyan>.")

    conn = psycopg2.connect(
        host=db_addr, port=db_port, dbname=db_name, user=db_user, password=db_pass, connect_timeout=20
    )

    if dry_run:
        logger.warning("Холостой запуск, изменения не будут сохранены")
    else:
        logger.info("Загруженные объекты будут сохранены в базе данных")
    if logfile is not None:
        logger.opt(colors=True).info(f'Сохарнение лога будет произведено в файл <cyan>"{logfile}"</cyan>')

    buildings = load_objects(filename)
    logger.info(f'Загружено {buildings.shape[0]} объектов из файла "{filename}"')
    for column, value in vars(columns_mapping).items():
        if value is not None and value not in buildings.columns:
            logger.warning(f'Столбец "{value}" используется ({column}), но не задан в файле')

    buildings = add_buildings(
        conn,
        buildings,
        city,
        columns_mapping,
        properties_mapping_dict,
        address_prefixes,
        new_address_prefix,
        not dry_run,
        verbose,
    )

    if logfile is not None:
        buildings.to_csv(logfile)
    logger.opt(colors=True).info(f'Завершено, лог записан в файл <green>"{logfile}"</green>')
