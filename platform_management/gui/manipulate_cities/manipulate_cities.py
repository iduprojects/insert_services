"""Cities insertion/editing module."""
from __future__ import annotations

import itertools
import json
import time
from math import ceil
from typing import Any, Callable, NamedTuple

import pandas as pd
from loguru import logger
from PySide6 import QtCore, QtGui, QtWidgets
from tqdm import trange

from platform_management.cli import refresh_materialized_views
from platform_management.cli.operations import update_buildings_area, update_physical_objects_locations
from platform_management.database_properties import Properties
from platform_management.gui.basics import GeometryShow, check_geometry_correctness
from platform_management.utils.converters import to_str

from .cities_table import PlatformCitiesTableWidget
from .city_creation import CityCreationWidget
from .territory_window import TerritoryWindow


class CitiesWindow(QtWidgets.QWidget):  # pylint: disable=too-many-instance-attributes
    """Platform cities list window."""

    EditButtons = NamedTuple(
        "EditButtons",
        [
            ("add", QtWidgets.QPushButton),
            ("edit", QtWidgets.QPushButton),
            ("delete", QtWidgets.QPushButton),
            ("showGeometry", QtWidgets.QPushButton),
            ("listMO", QtWidgets.QPushButton),
            ("listAU", QtWidgets.QPushButton),
            ("commit", QtWidgets.QPushButton),
            ("rollback", QtWidgets.QPushButton),
            ("refresh_matviews", QtWidgets.QPushButton),
            ("update_locations", QtWidgets.QPushButton),
            ("update_area", QtWidgets.QPushButton),
        ],
    )

    def __init__(  # pylint: disable=too-many-statements
        self,
        db_properties: Properties,
        on_close: Callable[[], None] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ):
        super().__init__(parent)

        self._db_properties = db_properties
        try:
            self._db_properties.connect_timeout = 1
            self._additional_conn = self._db_properties.copy().conn
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("could not create an additional connection: {!r}", exc)
            self._additional_conn = None  # type: ignore
        finally:
            self._db_properties.connect_timeout = 10
        self._on_close = on_close
        self._territory_window: TerritoryWindow | None = None
        self._regions = pd.Series(dtype=object)

        self._layout = QtWidgets.QHBoxLayout()
        self._left = QtWidgets.QVBoxLayout()
        self._right_scroll = QtWidgets.QScrollArea()
        self._right_scroll_widget = QtWidgets.QWidget()
        self._right_scroll_vlayout = QtWidgets.QVBoxLayout()
        self._right = QtWidgets.QVBoxLayout()

        self.setLayout(self._layout)
        self._layout.addLayout(self._left)
        self._right_scroll_widget.setLayout(self._right)
        self._right_scroll.setWidget(self._right_scroll_widget)
        self._right_scroll.setWidgetResizable(True)
        self._right_scroll_vlayout.addWidget(self._right_scroll)
        self._right_scroll_widget.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Preferred)
        self._layout.addWidget(self._right_scroll)

        left_placeholder = QtWidgets.QLabel("(Здесь будут отображены объекты)")
        left_placeholder.setMinimumSize(300, 300)
        left_placeholder.setAlignment(QtCore.Qt.AlignCenter)
        self._left.addWidget(left_placeholder)

        self._table: QtWidgets.QTableWidget

        self._editing_group_box = QtWidgets.QGroupBox("Изменение списка")
        self._editing_group = QtWidgets.QFormLayout()
        self._editing_group_box.setLayout(self._editing_group)
        self._edit_buttons = CitiesWindow.EditButtons(
            QtWidgets.QPushButton("Добавить город"),
            QtWidgets.QPushButton("Изменить город"),
            QtWidgets.QPushButton("Удалить город"),
            QtWidgets.QPushButton("Посмотреть геометрию"),
            QtWidgets.QPushButton("Список МО"),
            QtWidgets.QPushButton("Список АЕ"),
            QtWidgets.QPushButton("Сохранить изменения в БД"),
            QtWidgets.QPushButton("Отмена внесенных изменений"),
            QtWidgets.QPushButton("Обновить мат. представления"),
            QtWidgets.QPushButton("Обновить локации объектов"),
            QtWidgets.QPushButton("Обновить площадь зданий (осн.+жил.)"),
        )
        self._edit_buttons.add.clicked.connect(self._on_city_add)
        self._edit_buttons.edit.clicked.connect(self._on_city_edit)
        self._edit_buttons.delete.clicked.connect(self._on_city_delete)
        self._edit_buttons.showGeometry.clicked.connect(self._on_geometry_show)
        self._edit_buttons.listMO.clicked.connect(self._on_show_municipalities)
        self._edit_buttons.listAU.clicked.connect(self._on_show_administrative_units)
        self._edit_buttons.commit.clicked.connect(self._on_commit_changes)
        self._edit_buttons.commit.setStyleSheet("background-color: lightgreen;color: black")
        self._edit_buttons.rollback.clicked.connect(self._on_rollback)
        self._edit_buttons.rollback.setStyleSheet("background-color: red;color: black")
        self._edit_buttons.refresh_matviews.clicked.connect(self._on_refresh_matviews)
        self._edit_buttons.update_locations.clicked.connect(self._on_update_locations)
        self._edit_buttons.update_area.clicked.connect(self._on_update_area)
        for btn in self._edit_buttons:
            self._editing_group.addWidget(btn)
        self._right.addWidget(self._editing_group_box)

        self._log_window = QtWidgets.QTextEdit()
        self._log_window.setReadOnly(True)
        self._right.addWidget(self._log_window)

        self._right.setAlignment(QtCore.Qt.AlignTop)
        right_width = self._editing_group_box.sizeHint().width()

        self._right_scroll.setMinimumWidth(int(right_width * 1.6))
        self._editing_group_box.setMinimumWidth(int(right_width * 1.5))
        self._editing_group_box.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        self._right_scroll.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)

    def _on_cities_load(self) -> None:
        self._log_window.clear()
        self._db_properties.conn.rollback()
        with self._db_properties.conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, code, population, local_crs, (SELECT name FROM regions WHERE id = region_id),"
                "   city_division_type, ST_Y(center), ST_X(center), ST_GeometryType(geometry),"
                "   date_trunc('minute', created_at)::timestamp, date_trunc('minute', updated_at)::timestamp"
                " FROM cities"
                " ORDER BY 1"
            )
            cities = cur.fetchall()
            cur.execute("SELECT id, name FROM regions ORDER BY id")
            regions = cur.fetchall()
            self._regions = pd.Series((r[1] for r in regions), (r[0] for r in regions))
        left_placeholder = self._left.itemAt(0).widget()
        left_placeholder.setVisible(False)
        self._table = PlatformCitiesTableWidget(cities, self._on_cell_change)
        self._left.replaceWidget(left_placeholder, self._table)

        self._log_window.insertHtml(f"<font color=blue>Загружены {len(cities)} городов</font><br>")

    def _on_cell_change(  # pylint: disable=too-many-arguments
        self, row: int, column_name: str, old_value: Any, new_value: Any, is_valid: bool
    ) -> None:
        city_id = self._table.item(row, 0).text()
        if is_valid:
            self._log_window.insertHtml(
                f"<font color=yellowgreen>Изменен город с id={city_id}. {column_name}:"
                f' "{to_str(old_value)}"->"{to_str(new_value)}"</font><br>'
            )
        else:
            self._log_window.insertHtml(
                f"<font color=#e6783c>Не изменен город с id="
                f'{city_id}. {column_name}: "{to_str(old_value)}"->"{to_str(new_value)}"'
                " (некорректное значение)</font><br>"
            )
            return
        column = PlatformCitiesTableWidget.LABELS.index(column_name)
        db_column = PlatformCitiesTableWidget.LABELS_DB[column]
        with self._db_properties.conn.cursor() as cur:
            cur.execute(
                f"UPDATE cities SET {db_column} = %s, updated_at = date_trunc('second', now()) WHERE id = %s",
                (new_value, city_id),
            )

    def _on_city_add(self) -> None:
        dialog = CityCreationWidget("Добавление нового города", list(self._regions), is_adding=True)
        if dialog.exec() != QtWidgets.QDialog.Accepted or self._additional_conn is None:
            return
        new_geom_tuple = check_geometry_correctness(dialog.get_geometry(), self._additional_conn)
        if new_geom_tuple is None:
            self._log_window.insertHtml("<font color=#e6783c>Город не добавлен, ошибка в геометрии</font><br>")
            return
        latitude, longitude, geom_type = new_geom_tuple
        with self._db_properties.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO cities ("
                "   name,"
                "   code,"
                "   region_id,"
                "   geometry,"
                "   center,"
                "   population,"
                "   local_crs,"
                "   city_division_type"
                ")"
                " VALUES (%s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),"
                "   ST_SnapToGrid(ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 0.000001), %s, %s, %s)"
                " RETURNING id",
                (
                    dialog.name(),
                    dialog.code(),
                    (
                        int(self._regions[self._regions == dialog.region()].index[0])
                        if dialog.region() is not None
                        else None
                    ),
                    dialog.get_geometry(),
                    dialog.get_geometry(),
                    dialog.population(),
                    dialog.local_crs(),
                    dialog.division_type(),
                ),
            )
            city_id = cur.fetchone()[0]  # type: ignore
        self._log_window.insertHtml(
            f'<font color=yellowgreen>Добавлен город "{dialog.name()}" c id={city_id}</font><br>'
        )
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(city_id)))
        self._table.setItem(row, 1, QtWidgets.QTableWidgetItem(to_str(dialog.name())))
        self._table.setItem(row, 2, QtWidgets.QTableWidgetItem(to_str(dialog.code())))
        self._table.setItem(row, 3, QtWidgets.QTableWidgetItem(to_str(dialog.local_crs())))
        self._table.setItem(row, 4, QtWidgets.QTableWidgetItem(to_str(dialog.population())))
        self._table.setItem(row, 5, QtWidgets.QTableWidgetItem(to_str(dialog.region())))
        self._table.setItem(row, 6, QtWidgets.QTableWidgetItem(to_str(dialog.division_type())))
        self._table.setItem(row, 7, QtWidgets.QTableWidgetItem(str(latitude)))
        self._table.setItem(row, 8, QtWidgets.QTableWidgetItem(str(longitude)))
        self._table.setItem(row, 9, QtWidgets.QTableWidgetItem(geom_type))
        now = time.strftime("%Y-%M-%d %H:%M:00")
        self._table.setItem(row, 10, QtWidgets.QTableWidgetItem(now))
        self._table.setItem(row, 11, QtWidgets.QTableWidgetItem(now))
        for column in range(self._table.columnCount()):
            self._table.item(row, column).setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))

    def _on_city_edit(self) -> None:  # pylint: disable=too-many-locals,too-many-statements
        row = self._table.currentRow()
        if row == -1:
            return
        city_id = self._table.item(row, 0).text()
        with self._db_properties.conn.cursor() as cur:
            cur.execute(
                "SELECT"
                "   ST_AsGeoJSON(geometry)::jsonb,"
                "   name,"
                "   code,"
                "   local_crs,"
                "   (SELECT name FROM regions WHERE id = region_id),"
                "   population,"
                "   city_division_type"
                " FROM cities"
                " WHERE id = %s",
                (city_id,),
            )
            geometry, name, code, local_crs, region, population, division_type = cur.fetchone()  # type: ignore
        dialog = CityCreationWidget(
            f"Внесение изменений в город в строке под номером {row + 1}",
            list(self._regions),
            json.dumps(geometry, indent=2),
            name,
            code,
            region,
            population,
            division_type,
            local_crs,
        )
        if dialog.exec() != QtWidgets.QDialog.Accepted or self._additional_conn is None:
            return
        new_geom_tuple = check_geometry_correctness(dialog.get_geometry(), self._additional_conn)
        if new_geom_tuple is None:
            self._log_window.insertHtml(
                f'<font color=#e6783c>Город "{name}" с id={city_id} не изменен, ошибка в геометрии</font><br>'
            )
            return
        new_geometry = json.loads(dialog.get_geometry())  # type: ignore
        changed = False
        if geometry != new_geometry:
            new_latitude, new_longitude, geom_type = new_geom_tuple
            with self._db_properties.conn.cursor() as cur:
                cur.execute(
                    "UPDATE cities SET geometry = ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),"
                    "   center = ST_SnapToGrid(ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 0.000001)"
                    " WHERE id = %s",
                    (dialog.get_geometry(), dialog.get_geometry(), city_id),
                )
            self._log_window.insertHtml(
                f'<font color=yellowgreen>Изменена геометрия города "{dialog.name()}" c id={city_id}:'
                f" {self._table.item(row, 9).text()}({self._table.item(row, 6).text()},"
                f" {self._table.item(row, 8).text()})"
                f"->{geom_type}({new_latitude, new_longitude}</font><br>"
            )
            self._table.item(row, 7).setText(str(new_latitude))
            self._table.item(row, 8).setText(str(new_longitude))
            self._table.item(row, 9).setText(geom_type)
            changed = True
            for column in (7, 8, 9):
                self._table.item(row, column).setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))
        if name != dialog.name():
            self._table.item(row, 1).setText(to_str(dialog.name()))
            self._table.item(row, 1).setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))
            changed = True
        if code != dialog.code():
            self._table.item(row, 2).setText(to_str(dialog.code()))
            self._table.item(row, 2).setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))
            changed = True
        if population != dialog.population():
            self._table.item(row, 3).setText(to_str(dialog.population()))
            self._table.item(row, 3).setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))
            changed = True
        if local_crs != dialog.local_crs():
            self._table.item(row, 4).setText(to_str(dialog.local_crs()))
            self._table.item(row, 4).setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))
            changed = True
        if region != dialog.region():
            self._table.item(row, 5).setText(to_str(dialog.region()))
            self._table.item(row, 5).setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))
            changed = True
            with self._db_properties.conn.cursor() as cur:
                cur.execute(
                    "UPDATE cities SET region_id = %s WHERE id = %s",
                    (
                        int(self._regions[self._regions == dialog.region()].index[0])
                        if dialog.region() is not None
                        else None,
                        city_id,
                    ),
                )
        if division_type != dialog.division_type():
            self._table.item(row, 6).setText(dialog.division_type())
            self._table.item(row, 6).setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))
            changed = True
            with self._db_properties.conn.cursor() as cur:
                cur.execute(
                    "UPDATE cities SET city_division_type = %s WHERE id = %s", (dialog.division_type(), city_id)
                )
        if changed:
            with self._db_properties.conn.cursor() as cur:
                cur.execute("UPDATE cities SET updated_at = now() WHERE id = %s", (city_id,))

    def _on_city_delete(self) -> None:
        rows = sorted(set(map(lambda index: index.row() + 1, self._table.selectedIndexes())))  # type: ignore
        if len(rows) == 0:
            return
        if len(rows) > 1:
            is_deleting = QtWidgets.QMessageBox.question(
                self,
                "Удаление городов",
                f'Вы уверены, что хотите удалить города в строках под номерами: {", ".join(map(str, rows))}?',
            )
        else:
            object_row = next(iter(rows))
            is_deleting = QtWidgets.QMessageBox.question(
                self, "Удаление города", f"Вы уверены, что хотите удалить город в строке под номером {object_row}?"
            )
        if is_deleting == QtWidgets.QMessageBox.StandardButton.Yes:
            with self._db_properties.conn.cursor() as cur:
                for row in rows[::-1]:
                    city_id = self._table.item(row - 1, 0).text()
                    logger.debug("Preparing to delete city with id={}", city_id)
                    self._log_window.insertHtml(f"<font color=red>Удаление города с id={city_id}</font><br>")
                    cur.execute(
                        "SELECT f.id FROM functional_objects f JOIN physical_objects p ON f.physical_object_id = p.id"
                        " WHERE p.city_id = %s",
                        (city_id,),
                    )
                    city_objects = tuple(itertools.chain.from_iterable(cur.fetchall()))
                    if len(city_objects) > 0:
                        logger.debug("Preparing to delete {} functional_objects", len(city_objects))
                        for i in trange(ceil(len(city_objects) / 100), desc="Deleting functional objects"):
                            cur.execute(
                                "DELETE FROM functional_objects WHERE id IN %s",
                                (city_objects[i * 100 : (i + 1) * 100],),
                            )

                    cur.execute("SELECT id FROM physical_objects WHERE city_id = %s", (city_id,))
                    city_objects = tuple(itertools.chain.from_iterable(cur.fetchall()))
                    if len(city_objects) > 0:
                        cur.execute("SELECT id FROM buildings WHERE physical_object_id IN %s", (city_objects,))
                        buildings_ids = tuple(itertools.chain.from_iterable(cur.fetchall()))
                        if len(buildings_ids) > 0:
                            # skipped to boost prformance
                            # cur.execute(
                            #     "DELETE FROM social_stats.sex_age_social_houses WHERE house_id IN %s",
                            #     (buildings_ids,),
                            # )
                            try:
                                logger.debug("Preparing to delete {} buildings", len(buildings_ids))
                                for i in trange(ceil(len(buildings_ids) / 100), desc="Deleting functional objects"):
                                    cur.execute(
                                        "DELETE FROM buildings WHERE id IN %s",
                                        (buildings_ids[i * 100 : (i + 1) * 100],),
                                    )
                            except Exception as exc:  # pylint: disable=broad-except
                                self._log_window.insertHtml(
                                    f"<font color=red>Произошла ошибка при удалении сервисов: {exc}."
                                    " Проверьте таблицы, связанные с functional_objects.</font"
                                )
                                raise
                        logger.debug("Preparing to delete {} physical objects", len(city_objects))
                        for i in trange(ceil(len(city_objects) / 100), desc="Deleting functional objects"):
                            cur.execute("DELETE FROM physical_objects WHERE city_id = %s", (city_id,))

                    logger.debug("Deleting blocks, municipalities and administrative units")
                    cur.execute("DELETE FROM blocks WHERE city_id = %s", (city_id,))
                    cur.execute("UPDATE municipalities SET admin_unit_parent_id = null WHERE city_id = %s", (city_id,))
                    cur.execute(
                        "UPDATE administrative_units SET municipality_parent_id = null WHERE city_id = %s", (city_id,)
                    )

                    cur.execute("DELETE FROM administrative_units WHERE city_id = %s", (city_id,))
                    cur.execute("DELETE FROM municipalities WHERE city_id = %s", (city_id,))
                    logger.debug("Finally deleting city with id = {}", city_id)
                    cur.execute("DELETE FROM cities WHERE id = %s", (city_id,))
                    self._table.removeRow(row - 1)
                logger.info("Auto-commiting city deletion")
                self._edit_buttons.commit.click()

    def _on_geometry_show(self) -> None:
        row = self._table.currentRow()
        if row == -1:
            return
        with self._db_properties.conn.cursor() as cur:
            cur.execute(
                "SELECT ST_AsGeoJSON(geometry, 6) FROM cities WHERE id = %s", (self._table.item(row, 0).text(),)
            )
            res = cur.fetchone()
            if res is None:
                return
            geometry = json.loads(res[0])
        GeometryShow(json.dumps(geometry, indent=2)).exec()

    def _on_error(self, text: str) -> None:
        self._log_window.insertHtml(f"<font color=#e6783c>{text}</font><br>")

    def _on_show_municipalities(self) -> None:
        row = self._table.currentRow()
        if row == -1 or self._additional_conn is None:
            return
        self._territory_window = TerritoryWindow(
            self._db_properties.conn,
            self._additional_conn,
            self._table.item(row, 1).text(),
            "municipality",
            self._on_municipality_add,
            self._on_municipality_edit,
            self._on_municipality_delete,
            self._on_error,
        )
        self._territory_window.show()

    def _on_municipality_add(self, municipality_id: int, municipality_name: str, city_name) -> None:
        self._log_window.insertHtml(
            "<font color=yellowgreen>Добавлено муниципальное образование к городу"
            f' {city_name}: "{municipality_name}" (id={municipality_id})</font><br>'
        )

    def _on_municipality_edit(
        self, municipality_id: int, municipality_name: str, changes: list[tuple[str, str, str]], city_name: str
    ) -> None:
        if len(changes) != 0:
            self._log_window.insertHtml(
                f'<font color=yellowgreen>Изменены параметры муниципального образования "{municipality_name}"'
                f" (id={municipality_id}) города {city_name}:<br>"
            )
            for what_changed, old_value, new_value in changes:
                self._log_window.insertHtml(
                    f'&nbsp;&nbsp;{what_changed}: "{to_str(old_value)}"->"{to_str(new_value)}"<br>'
                )
            self._log_window.insertHtml("</font>")

    def _on_municipality_delete(self, deleting: list[tuple[int, str]], city_name: str) -> None:
        for municipality_id, municipality_name in deleting:
            self._log_window.insertHtml(
                f'<font color=red>Удаление муниципального образования "{municipality_name}"'
                f" с id={municipality_id} города {city_name}</font><br>"
            )

    def _on_show_administrative_units(self) -> None:
        row = self._table.currentRow()
        if row == -1 or self._additional_conn is None:
            return
        self._territory_window = TerritoryWindow(
            self._db_properties.conn,
            self._additional_conn,
            self._table.item(row, 1).text(),
            "administrative_unit",
            self._on_administrative_unit_add,
            self._on_administrative_unit_edit,
            self._on_administrative_unit_delete,
            self._on_error,
        )
        self._territory_window.show()

    def _on_administrative_unit_add(
        self, administrative_unit_id: int, administrative_unit_name: str, city_name: str
    ) -> None:
        self._log_window.insertHtml(
            "<font color=yellowgreen>Добавлена административная единица к городу"
            f' {city_name}: "{administrative_unit_name}" (id={administrative_unit_id})</font><br>'
        )

    def _on_administrative_unit_edit(
        self,
        administrative_unit_id: int,
        administrative_unit_name: str,
        changes: list[tuple[str, str, str]],
        city_name: str,
    ) -> None:
        if len(changes) != 0:
            self._log_window.insertHtml(
                f'<font color=yellowgreen>Изменены параметры административной единицы "{administrative_unit_name}"'
                f" (id={administrative_unit_id}) города {city_name}:<br>"
            )
            for what_changed, old_value, new_value in changes:
                self._log_window.insertHtml(
                    f'&nbsp;&nbsp;{what_changed}: "{to_str(old_value)}"->"{to_str(new_value)}"<br>'
                )
            self._log_window.insertHtml("</font>")

    def _on_administrative_unit_delete(self, deleting: list[tuple[int, str]], city_name: str) -> None:
        for administrative_unit_id, administrative_unit_name in deleting:
            self._log_window.insertHtml(
                f'<font color=red>Удаление административной единицы "{administrative_unit_name}"'
                f" с id={administrative_unit_id} города {city_name}</font><br>"
            )

    def _on_commit_changes(self) -> None:
        self._log_window.insertHtml("<font color=green>Запись изменений в базу данных</font><br>")
        logger.opt(colors=True).info(
            f"<green>Коммит следующих изменений сервисов в базу данных</green>:\n{self._log_window.toPlainText()[:-1]}"
        )
        self._db_properties.conn.commit()
        self._on_cities_load()
        self._log_window.insertHtml("<font color=green>Изменения записаны, обновленная информация загружена</font><br>")

    def _on_rollback(self) -> None:
        self._db_properties.conn.rollback()
        self._on_cities_load()

    def _on_refresh_matviews(self) -> None:
        logger.info("Обновление материализованных представлений запущено")
        self._log_window.insertHtml("<font color=grey>Обновление материализованных представлений...</font>")
        self._log_window.repaint()
        with self._db_properties.conn, self._db_properties.conn.cursor() as cur:
            refresh_materialized_views(cur)
        logger.info("Обновление материализованных представлений завершено")
        self._log_window.insertHtml("<font color=green>Завершено</font><br>")

    def _on_update_locations(self) -> None:
        logger.info(
            "Обновление местоположения физических объектов без"
            " указания административного образования, МО или квартала запущено"
        )
        self._log_window.insertHtml("<font color=grey>Обновление местоположения физических объектов...</font>")
        self._log_window.repaint()
        with self._db_properties.conn.cursor() as cur:
            update_physical_objects_locations(cur)
        logger.info("Обновление местоположения физических объектов завершено")
        self._log_window.insertHtml("<font color=green>Завершено</font><br>")

    def _on_update_area(self) -> None:
        """Launch buildings area update process"""
        logger.info(
            "Запущен процесс обновления площади здания по площади пятна геометрии и моделирования жилой площади"
        )
        self._log_window.insertHtml("<font color=grey>Обновление площади (общей и жилой) зданий...</font>")
        self._log_window.repaint()
        with self._db_properties.conn.cursor() as cur:
            update_buildings_area(cur)
        logger.info("Обновление площади зданий завершено")
        self._log_window.insertHtml("<font color=green>Завершено</font><br>")

    def change_db(  # pylint: disable=too-many-arguments
        self, db_addr: str, db_port: int, db_name: str, db_user: str, db_pass: str
    ) -> None:
        """Change database connection config. Called from the outside on reconnecting to the database."""
        self._db_properties.reopen(db_addr, db_port, db_name, db_user, db_pass)
        if self._additional_conn is not None and not self._additional_conn.closed:
            self._additional_conn.close()
        self._additional_conn = self._db_properties.copy().conn

    def showEvent(self, event: QtGui.QShowEvent) -> None:  # pylint: disable=invalid-name
        logger.info("Открыто окно работы с городами")
        self._on_cities_load()
        return super().showEvent(event)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # pylint: disable=invalid-name
        logger.info("Закрыто окно работы с городами")
        if self._territory_window is not None:
            self._territory_window.close()
        if self._on_close is not None:
            self._on_close()
        return super().closeEvent(event)
