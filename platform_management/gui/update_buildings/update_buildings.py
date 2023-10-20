"""Services data update module."""
from __future__ import annotations

import json
import time
from typing import Any, Callable, Iterable, NamedTuple

import pandas as pd
from loguru import logger
from PySide6 import QtCore, QtGui, QtWidgets

from platform_management.cli.buildings import get_properties_keys
from platform_management.database_properties import Properties
from platform_management.gui.basics import check_geometry_correctness
from platform_management.utils.converters import to_str

from .building_creation import BuildingCreationWidget
from .geometry_show import GeometryShowWidget
from .platform_buildings_table import PlatformBuildingsTableWidget


class BuildingsUpdatingWindow(QtWidgets.QWidget):  # pylint: disable=too-many-instance-attributes
    """Window to update services data."""

    EditButtons = NamedTuple(
        "EditButtons",
        [
            ("load", QtWidgets.QPushButton),
            ("delete", QtWidgets.QPushButton),
            ("showGeometry", QtWidgets.QPushButton),
            ("updateBuilding", QtWidgets.QPushButton),
            ("export", QtWidgets.QPushButton),
            ("commit", QtWidgets.QPushButton),
            ("rollback", QtWidgets.QPushButton),
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

        left_placeholder = QtWidgets.QLabel("(Здесь будут отображены здания)")
        left_placeholder.setMinimumSize(300, 300)
        left_placeholder.setAlignment(QtCore.Qt.AlignCenter)
        self._left.addWidget(left_placeholder)

        left_hlayout = QtWidgets.QHBoxLayout()
        self._left.addLayout(left_hlayout)
        self._left.setAlignment(QtCore.Qt.AlignCenter)
        self._table: QtWidgets.QTableWidget

        self._options_group_box = QtWidgets.QGroupBox("Опции выбора")
        self._options_group = QtWidgets.QFormLayout()
        self._city_choose = QtWidgets.QComboBox()
        self._options_group.addRow("Город:", self._city_choose)
        self._right.addWidget(self._options_group_box)
        self._options_group_box.setLayout(self._options_group)
        self._show_living = QtWidgets.QCheckBox()
        self._options_group.addRow("Жилые:", self._show_living)
        self._show_non_living = QtWidgets.QCheckBox()
        self._options_group.addRow("Нежилые:", self._show_non_living)

        self._editing_group_box = QtWidgets.QGroupBox("Изменение списка")
        self._editing_group = QtWidgets.QFormLayout()
        self._editing_group_box.setLayout(self._editing_group)
        self._edit_buttons = BuildingsUpdatingWindow.EditButtons(
            QtWidgets.QPushButton("Отобразить здания"),
            QtWidgets.QPushButton("Удалить здание"),
            QtWidgets.QPushButton("Посмотреть геометрию"),
            QtWidgets.QPushButton("Изменить здание"),
            QtWidgets.QPushButton("Экспортировать таблицу"),
            QtWidgets.QPushButton("Сохранить изменения в БД"),
            QtWidgets.QPushButton("Отмена внесенных изменений"),
        )
        self._edit_buttons.load.clicked.connect(self._on_objects_load)
        self._edit_buttons.delete.clicked.connect(self._on_object_delete)
        self._edit_buttons.showGeometry.clicked.connect(self._on_geometry_show)
        self._edit_buttons.updateBuilding.clicked.connect(self._on_update_building)
        self._edit_buttons.export.clicked.connect(self._on_export)
        self._edit_buttons.commit.clicked.connect(self._on_commit_changes)
        self._edit_buttons.commit.setStyleSheet("background-color: green; color: black")
        self._edit_buttons.rollback.clicked.connect(self._on_rollback)
        self._edit_buttons.rollback.setStyleSheet("background-color: red; color: black")
        self._editing_group.addWidget(self._edit_buttons.load)
        self._right.addWidget(self._editing_group_box)

        self._log_window = QtWidgets.QTextEdit()
        self._log_window.setReadOnly(True)
        self._right.addWidget(self._log_window)

        self._right.setAlignment(QtCore.Qt.AlignTop)
        self._city_choose.setMinimumWidth(200)
        right_width = max(map(lambda box: box.sizeHint().width(), (self._options_group_box, self._editing_group_box)))

        self._right_scroll.setFixedWidth(int(right_width * 1.1))
        self._options_group_box.setFixedWidth(right_width)
        self._editing_group_box.setFixedWidth(right_width)

    def _on_objects_load(self) -> None:
        self._log_window.clear()
        self._db_properties.conn.rollback()
        properties_keys = get_properties_keys(
            self._db_properties.conn, self._city_choose.currentText(), self._show_living, self._show_non_living
        )
        with self._db_properties.conn.cursor() as cur:
            cur.execute(
                "SELECT b.id,"
                "   b.address,"
                "   p.id physical_object_id,"
                "   b.is_living,"
                "   b.building_area,"
                "   b.living_area,"
                "   b.storeys_count,"
                "   ST_Y(p.center),"
                "   ST_X(p.center),"
                "   ST_GeometryType(p.geometry),"
                "   au.name as administrative_unit,"
                "   m.name as municipality,"
                "   date_trunc('second', p.created_at)::timestamp,"  # buildings do not have `created_at`
                "   date_trunc('second', p.updated_at)::timestamp,"  # buildings do not have `updated_at`
                "   b.properties"
                " FROM physical_objects p"
                "   JOIN buildings b ON b.physical_object_id = p.id"
                "   LEFT JOIN administrative_units au ON p.administrative_unit_id = au.id"
                "   LEFT JOIN municipalities m ON p.municipality_id = m.id"
                " WHERE p.city_id = (SELECT id FROM cities WHERE name = %s) AND "
                + (
                    "b.is_living = true"
                    if self._show_living.isChecked() and not self._show_non_living.isChecked()
                    else "b.is_living = false"
                    if self._show_non_living.isChecked() and not self._show_living.isChecked()
                    else "b.is_living IS null"
                    if not self._show_non_living.isChecked() and not self._show_living.isChecked()
                    else "b.is_living IS NOT null"
                )
                + " ORDER BY 1",
                (self._city_choose.currentText(),),
            )
            buildings_list = cur.fetchall()
            if len(buildings_list) > 0:
                buildings_list, buildings_properties = zip(
                    *[(row[:-1] + ("",) * len(properties_keys), row[-1]) for row in buildings_list]
                )
            else:
                buildings_properties = []
        if not hasattr(self, "_table"):
            self._editing_group.addWidget(self._edit_buttons.load)
            self._editing_group.addWidget(self._edit_buttons.delete)
            self._editing_group.addWidget(self._edit_buttons.showGeometry)
            self._editing_group.addWidget(self._edit_buttons.updateBuilding)
            self._editing_group.addWidget(self._edit_buttons.export)
            self._editing_group.addWidget(self._edit_buttons.commit)
            self._editing_group.addWidget(self._edit_buttons.rollback)

        left_placeholder = self._left.itemAt(0).widget()
        left_placeholder.setVisible(False)
        self._table = PlatformBuildingsTableWidget(
            buildings_list, properties_keys, self._on_cell_change, self._db_properties
        )
        self._table.disable_callback()
        for i, properties in enumerate(buildings_properties):
            properties: dict | None
            if properties is None:
                continue
            for functional_object_property, value in properties.items():
                self._table.item(
                    i, len(PlatformBuildingsTableWidget.LABELS) + properties_keys.index(functional_object_property)
                ).setText(str(value))
        self._table.enable_callback()
        self._left.replaceWidget(left_placeholder, self._table)

        self._log_window.insertHtml(f'<font color=blue>Работа с городом "{self._city_choose.currentText()}"</font><br>')
        self._log_window.insertHtml(f"<font color=blue>Загружены {len(buildings_list)} зданий</font><br>")

    def _on_cell_change(  # pylint: disable=too-many-arguments
        self, row: int, column_name: str, old_value: Any, new_value: Any, is_valid: bool
    ) -> None:
        building_id = self._table.item(row, 0).text()
        if not is_valid:
            self._log_window.insertHtml(
                f"<font color=#e6783c>Не изменен объект с building_id="
                f'{building_id}. {column_name}: "{to_str(old_value)}"->"{to_str(new_value)}"'
                " (некорректное значение)</font><br>"
            )
            return
        with self._db_properties.conn.cursor() as cur:
            if column_name in PlatformBuildingsTableWidget.LABELS:
                column = PlatformBuildingsTableWidget.LABELS.index(column_name)
                db_column = PlatformBuildingsTableWidget.LABELS_DB[column]
                cur.execute(
                    f"UPDATE buildings SET {db_column} = %s WHERE id = %s",
                    (new_value, building_id),
                )
                # buildings do not have update date
                cur.execute(
                    "WITH p_id AS (SELECT physical_object_id id FROM buildings WHERE id = %s)"
                    " UPDATE physical_objects SET updated_at = date_trunc('second', now())"
                    "   WHERE id = (SELECT id FROM p_id)",
                    (building_id,),
                )
            else:
                cur.execute(
                    "UPDATE buildings SET properties = properties || %s::jsonb WHERE id = %s",
                    (json.dumps({column_name: new_value}), building_id),
                )

    def _on_object_delete(self) -> None:
        rows = sorted(set(map(lambda index: index.row() + 1, self._table.selectedIndexes())))  # type: ignore
        if len(rows) == 0:
            return
        if len(rows) > 1:
            is_deleting = QtWidgets.QMessageBox.question(
                self,
                "Удаление объектов",
                f'Вы уверены, что хотите удалить объекты в строках под номерами: {", ".join(map(str, rows))}?',
            )
        else:
            object_row = next(iter(rows))
            is_deleting = QtWidgets.QMessageBox.question(
                self, "Удаление объекта", f"Вы уверены, что хотите удалить объект в строке под номером {object_row}?"
            )
        if is_deleting == QtWidgets.QMessageBox.StandardButton.Yes:
            if len(rows) == 1:
                self._log_window.insertHtml("<font color=red>Удаление объекта с func_id=</font>")
            else:
                self._log_window.insertHtml("<font color=red>Удаление объектов с func_id=</font>")
            with self._db_properties.conn.cursor() as cur:
                for i, row in enumerate(rows[::-1]):
                    building_id = self._table.item(row - 1, 0).text()
                    self._log_window.insertHtml(
                        f'<font color=red>{building_id}{", " if i != len(rows) - 1 else ""}</font>'
                    )
                    self._log_window.repaint()
                    cur.execute("SELECT physical_object_id FROM buildings WHERE id = %s", (building_id,))
                    phys_id = cur.fetchone()[0]  # type: ignore
                    cur.execute("DELETE FROM functional_objects WHERE physical_object_id = %s", (phys_id,))
                    cur.execute("DELETE FROM buildings WHERE id = %s", (building_id,))
                    cur.execute("DELETE FROM physical_objects WHERE id = %s", (phys_id,))
                    self._table.removeRow(row - 1)
                self._log_window.insertHtml("</font><br>")

    def _on_geometry_show(self) -> None:
        with self._db_properties.conn.cursor() as cur:
            cur.execute(
                "SELECT ST_AsGeoJSON(geometry, 6) FROM physical_objects WHERE id = %s",
                (
                    self._table.item(
                        self._table.currentRow(), PlatformBuildingsTableWidget.LABELS_DB.index("physical_object_id")
                    ).text(),
                ),
            )
            res = cur.fetchone()
            if res is None:
                return
            geometry = json.loads(res[0])
        GeometryShowWidget(json.dumps(geometry, indent=4)).exec()

    def _on_update_building(self) -> None:  # pylint: disable=too-many-locals
        row = self._table.currentRow()
        building_id, phys_id = (
            self._table.item(row, 0).text(),
            self._table.item(row, PlatformBuildingsTableWidget.LABELS_DB.index("physical_object_id")).text(),
        )
        with self._db_properties.conn.cursor() as cur:
            cur.execute(
                "SELECT ST_AsGeoJSON(p.geometry), p.osm_id, b.address, b.building_year,"
                "   b.repair_years, b.building_area, b.living_area,"
                "   b.storeys_count, b.lift_count, b.resident_number, b.project_type,"
                "   b.ukname, b.central_heating, b.central_hotwater,"
                "   b.central_electro, b.central_gas, b.refusechute,"
                "   b.failure, b.is_living, b.id"
                " FROM buildings b"
                "   JOIN physical_objects p ON b.physical_object_id = p.id"
                " WHERE p.id = %s",
                (phys_id,),
            )
            try:
                geometry, *res, b_id = cur.fetchone()  # type: ignore
            except TypeError:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Ошибка изменения здания",
                    "Здание, соответствующее физическому объекту" f" с id={phys_id} не найдено в базе данных",
                )
                return
        geometry = json.loads(geometry)
        dialog = BuildingCreationWidget(
            f"Если необходимо, измените параметры здания на строке {row + 1}",
            json.dumps(geometry, indent=2),
            *res,
        )
        if dialog.exec() != QtWidgets.QDialog.Accepted or self._additional_conn is None:
            return
        new_geom_tuple = check_geometry_correctness(dialog.get_geometry(), self._additional_conn)
        if new_geom_tuple is None:
            self._log_window.insertHtml(
                f"<font color=#e6783c>Здание с id={building_id}"
                f" (build_id={b_id}) не обновлено, ошибка в геометрии</font><br>"
            )
            return
        if dialog.address() is None:
            self._log_window.insertHtml(
                f"<font color=#e6783c>Здание id={building_id}"
                f" (build_id={b_id}) не обновлено, адрес не задан</font><br>"
            )
            return
        new_geometry = json.loads(dialog.get_geometry())  # type: ignore
        if geometry != new_geometry:
            new_latitude, new_longitude, geom_type = new_geom_tuple
            with self._db_properties.conn.cursor() as cur:
                cur.execute(
                    "UPDATE physical_objects"
                    " SET geometry = ST_SnapToGrid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), 0.000001),"
                    "   center = ST_SnapToGrid(ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 0.000001),"
                    "   updated_at = date_trunc('second', now())"
                    " WHERE id = %s",
                    (dialog.get_geometry(),) * 2 + (phys_id,),
                )
                cur.execute(
                    "UPDATE physical_objects SET"
                    " administrative_unit_id = (SELECT id from administrative_units"
                    "   WHERE ST_CoveredBy("
                    "       (SELECT center FROM physical_objects WHERE id = %s), geometry)"
                    "   ORDER BY population DESC LIMIT 1),"
                    " municipality_id = (SELECT id from municipalities"
                    "   WHERE ST_CoveredBy("
                    "       (SELECT center FROM physical_objects WHERE id = %s), geometry)"
                    "   ORDER BY population DESC LIMIT 1)"
                    " WHERE id = %s",
                    (phys_id,) * 3,
                )
            self._log_window.insertHtml(
                f"<font color=yellowgreen>Геометрия здания с id={building_id} (phys_id={phys_id}) изменена:"
                f" {self._table.item(row, 11).text()}({self._table.item(row, 9).text()},"
                f" {self._table.item(row, 10).text()})"
                f"->{geom_type}({new_latitude, new_longitude})</font><br>"
            )
            self._table.item(row, 9).setText(str(new_latitude))
            self._table.item(row, 10).setText(str(new_longitude))
            self._table.item(row, 11).setText(geom_type)
            for column in (9, 10, 11):
                self._table.item(row, column).setBackground(QtCore.Qt.GlobalColor.yellow)
        if res[0] != dialog.osm_id():
            with self._db_properties.conn.cursor() as cur:
                cur.execute(
                    "UPDATE physical_objects SET osm_id = %s, updated_at = date_trunc('second', now()) WHERE id = %s",
                    (res[0], phys_id),
                )
            self._log_window.insertHtml(
                f"<font color=yellowgreen>Изменен параметр OpenStreetMapID для phys_id={phys_id}:"
                f' "{res[0]}"->"{dialog.osm_id()}"</font><br>'
            )
        with self._db_properties.conn.cursor() as cur:
            if res[1] != dialog.address():
                self._table.item(row, 1).setText(dialog.address())  # type: ignore
                self._table.item(row, 1).setBackground(QtCore.Qt.GlobalColor.yellow)
            for name_interface, column, old_value, new_value in zip(
                (
                    "адрес",
                    "дата постройки",
                    "годы ремонта",
                    "площадь здания",
                    "жилая площадь",
                    "этажность",
                    "количество лифтов",
                    "население",
                    "тип проекта",
                    "название застройщика",
                    "централизованное отопление",
                    "централизованная горячая вода",
                    "централизованное электричество",
                    "централизованный газ",
                    "мусоропровод",
                    "аварийность",
                    "жилой",
                ),
                (
                    "address",
                    "building_year",
                    "repair_years",
                    "building_area",
                    "living_area",
                    "storeys_count",
                    "lift_count",
                    "resident_number",
                    "project_type",
                    "ukname",
                    "central_heating",
                    "central_hotwater",
                    "central_electro",
                    "central_gas",
                    "refusechute",
                    "failure",
                    "is_living",
                ),
                res[1:],
                (
                    dialog.address(),
                    dialog.building_year(),
                    dialog.repair_years(),
                    dialog.building_area(),
                    dialog.building_area_living(),
                    dialog.storeys(),
                    dialog.lift_count(),
                    dialog.population(),
                    dialog.project_type(),
                    dialog.ukname(),
                    dialog.central_heating(),
                    dialog.central_hotwater(),
                    dialog.central_electricity(),
                    dialog.central_gas(),
                    dialog.refusechute(),
                    dialog.is_failing(),
                    dialog.is_living(),
                ),
            ):
                if old_value != new_value:
                    self._log_window.insertHtml(
                        f"<font color=yellowgreen>Изменен параметр дома ({name_interface})"
                        f" для build_id={b_id} (phys_id={phys_id}):"
                        f' "{to_str(old_value)}"->"{to_str(new_value)}"</font><br>'
                    )
                cur.execute(f"UPDATE buildings SET {column} = %s WHERE id = %s", (new_value, b_id))

    def _on_export(self) -> None:
        lines: list[list[Any]] = []
        for row in range(self._table.rowCount()):
            lines.append([self._table.item(row, col).text() for col in range(self._table.columnCount())])
        dataframe = pd.DataFrame(
            lines, columns=[self._table.horizontalHeaderItem(i).text() for i in range(self._table.columnCount())]
        )

        file_dialog = QtWidgets.QFileDialog(self)
        file_dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        file_dialog.setNameFilters(
            (
                "Modern Excel files (*.xlsx)",
                "Excel files (*.xls)",
                "OpedDocumentTable files (*.ods)",
                "CSV files (*.csv)",
            )
        )
        t = time.localtime()  # pylint: disable=invalid-name
        filename: str = (
            f"{self._service_type.currentText()} {t.tm_year}-{t.tm_mon:02}-{t.tm_mday:02} "
            f"{t.tm_hour:02}-{t.tm_min:02}-{t.tm_sec:02}.csv"
        )
        file_dialog.selectNameFilter("CSV files (*.csv)")
        file_dialog.selectFile(filename)
        if file_dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        filename = file_dialog.selectedFiles()[0]
        file_format = file_dialog.selectedNameFilter()[file_dialog.selectedNameFilter().rfind(".") : -1]
        if not filename.endswith(file_format):
            filename += file_format
        save_func = pd.DataFrame.to_csv if filename.endswith("csv") else pd.DataFrame.to_excel
        save_func(dataframe, filename, index=False)

    def _on_commit_changes(self) -> None:
        self._log_window.insertHtml("<font color=green>Запись изменений в базу данных</font><br>")
        logger.opt(colors=True).info(
            f"<green>Коммит следующих изменений зданий в базу данных</green>:\n{self._log_window.toPlainText()[:-1]}"
        )
        self._db_properties.conn.commit()
        self._edit_buttons.load.click()
        self._log_window.insertHtml("<font color=green>Изменения записаны, обновленная информация загружена</font><br>")

    def _on_rollback(self) -> None:
        self._db_properties.conn.rollback()
        self._edit_buttons.load.click()

    def set_cities(self, cities: Iterable[str]) -> None:
        """Set cities list. Called from the outside if the connection to the database has changed."""
        cities = list(cities)
        current_city = self._city_choose.currentText()
        self._city_choose.clear()
        if len(cities) == 0:
            self._city_choose.addItem("(Нет городов)")
        else:
            self._city_choose.addItems(cities)
            if current_city in cities:
                self._city_choose.setCurrentText(current_city)
            self._city_choose.view().setMinimumWidth(len(max(cities, key=len)) * 8)

    def change_db(  # pylint: disable=too-many-arguments
        self, db_addr: str, db_port: int, db_name: str, db_user: str, db_pass: str
    ) -> None:
        """Uptdate database connection. Called from the outside if the connection to the database has changed."""
        self._db_properties.reopen(db_addr, db_port, db_name, db_user, db_pass)
        if self._additional_conn is not None and not self._additional_conn.closed:
            self._additional_conn.close()
        self._additional_conn = self._db_properties.copy().conn

    def showEvent(self, event: QtGui.QShowEvent) -> None:  # pylint: disable=invalid-name
        logger.info("Открыто окно изменения зданий")
        return super().showEvent(event)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # pylint: disable=invalid-name
        logger.info("Закрыто окно изменения зданий")
        if self._on_close is not None:
            self._on_close()
        return super().closeEvent(event)
