"""Services data update module."""
from __future__ import annotations

import itertools
import json
import time
from typing import Any, Callable, Iterable, NamedTuple

import pandas as pd
from loguru import logger
from PySide6 import QtCore, QtGui, QtWidgets

from platform_management import get_properties_keys
from platform_management.database_properties import Properties
from platform_management.gui.basics import ColorizingComboBox, check_geometry_correctness
from platform_management.gui.update_buildings.building_creation import BuildingCreationWidget
from platform_management.gui.update_buildings.geometry_show import GeometryShowWidget
from platform_management.utils.converters import to_str

from .physical_object_creation import PhysicalObjectCreationWidget
from .platform_services_table import PlatformServicesTableWidget


class ServicesUpdatingWindow(QtWidgets.QWidget):  # pylint: disable=too-many-instance-attributes
    """Window to update services data."""

    EditButtons = NamedTuple(
        "EditButtons",
        [
            ("load", QtWidgets.QPushButton),
            ("delete", QtWidgets.QPushButton),
            ("showGeometry", QtWidgets.QPushButton),
            ("addPhysicalObject", QtWidgets.QPushButton),
            ("updatePhysicalObject", QtWidgets.QPushButton),
            ("addBuilding", QtWidgets.QPushButton),
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

        left_placeholder = QtWidgets.QLabel("(Здесь будут отображены объекты)")
        left_placeholder.setMinimumSize(300, 300)
        left_placeholder.setAlignment(QtCore.Qt.AlignCenter)
        self._left.addWidget(left_placeholder)

        left_hlayout = QtWidgets.QHBoxLayout()
        self._left.addLayout(left_hlayout)
        self._left.setAlignment(QtCore.Qt.AlignCenter)
        self._table: QtWidgets.QTableWidget

        self._options_group_box = QtWidgets.QGroupBox("Опции выбора")
        self._options_group = QtWidgets.QFormLayout()
        self._city_choose = ColorizingComboBox(self._on_city_change)
        self._options_group.addRow("Город:", self._city_choose)
        self._right.addWidget(self._options_group_box)
        self._options_group_box.setLayout(self._options_group)
        self._service_type = QtWidgets.QComboBox()
        self._options_group.addRow("Тип сервиса:", self._service_type)

        self._editing_group_box = QtWidgets.QGroupBox("Изменение списка")
        self._editing_group = QtWidgets.QFormLayout()
        self._editing_group_box.setLayout(self._editing_group)
        self._edit_buttons = ServicesUpdatingWindow.EditButtons(
            QtWidgets.QPushButton("Отобразить сервисы"),
            QtWidgets.QPushButton("Удалить сервис"),
            QtWidgets.QPushButton("Посмотреть геометрию"),
            QtWidgets.QPushButton("Добавить физический объект"),
            QtWidgets.QPushButton("Изменить физический объект"),
            QtWidgets.QPushButton("Добавить здание"),
            QtWidgets.QPushButton("Изменить здание"),
            QtWidgets.QPushButton("Экспортировать таблицу"),
            QtWidgets.QPushButton("Сохранить изменения в БД"),
            QtWidgets.QPushButton("Отмена внесенных изменений"),
        )
        self._edit_buttons.load.clicked.connect(self._on_objects_load)
        self._edit_buttons.delete.clicked.connect(self._on_object_delete)
        self._edit_buttons.showGeometry.clicked.connect(self._on_geometry_show)
        self._edit_buttons.addPhysicalObject.clicked.connect(self._on_add_physical_object)
        self._edit_buttons.updatePhysicalObject.clicked.connect(self._on_update_physical_object)
        self._edit_buttons.addBuilding.clicked.connect(self._on_add_building)
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

    def _on_city_change(self, _changed: QtWidgets.QComboBox | None = None, _old_state: int | None = None) -> None:
        with self._db_properties.conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT st.name FROM functional_objects f"
                "   JOIN physical_objects p ON f.physical_object_id = p.id"
                "   JOIN city_service_types st ON f.city_service_type_id = st.id"
                " WHERE p.city_id = (SELECT id FROM cities WHERE name = %s)"
                " ORDER BY 1",
                (self._city_choose.currentText(),),
            )
            service_types = list(itertools.chain.from_iterable(cur.fetchall()))
        self._set_service_types(service_types)

    def _on_objects_load(self) -> None:
        self._log_window.clear()
        self._db_properties.conn.rollback()
        properties_keys = get_properties_keys(self._db_properties.conn, self._service_type.currentText())
        with self._db_properties.conn.cursor() as cur:
            cur.execute(
                "SELECT is_building FROM city_service_types WHERE name = %s", (self._service_type.currentText(),)
            )
            is_building = cur.fetchone()[0]  # type: ignore
            cur.execute(
                "SELECT f.id as functional_object_id, b.address, f.name AS service_name,"
                "   f.opening_hours, f.website, f.phone,"
                "   f.capacity, f.is_capacity_real, p.id as physical_object_id, ST_Y(p.center), ST_X(p.center),"
                "   ST_GeometryType(p.geometry), au.name as administrative_unit, m.name as municipality,"
                "   date_trunc('second', f.created_at)::timestamp, date_trunc('second', f.updated_at)::timestamp,"
                "   b.modeled building_modeled, f.modeled functional_object_modeled, f.properties"
                " FROM physical_objects p"
                "   JOIN functional_objects f ON f.physical_object_id = p.id"
                "   LEFT JOIN buildings b ON b.physical_object_id = p.id"
                "   LEFT JOIN administrative_units au ON p.administrative_unit_id = au.id"
                "   LEFT JOIN municipalities m ON p.municipality_id = m.id"
                " WHERE f.city_service_type_id = (SELECT id from city_service_types WHERE name = %s)"
                "   AND p.city_id = (SELECT id FROM cities WHERE name = %s)"
                " ORDER BY 1",
                (self._service_type.currentText(), self._city_choose.currentText()),
            )
            services_list, buildings_modeled, functional_objects_modeled, functional_object_properties = zip(
                *[(row[:-3] + ("",) * len(properties_keys), row[-3], row[-2], row[-1]) for row in cur.fetchall()]
            )
        if "_table" not in dir(self):
            self._editing_group.addWidget(self._edit_buttons.load)
            self._editing_group.addWidget(self._edit_buttons.delete)
            self._editing_group.addWidget(self._edit_buttons.showGeometry)
            if is_building:
                self._editing_group.addWidget(self._edit_buttons.addBuilding)
                self._editing_group.addWidget(self._edit_buttons.updateBuilding)
            else:
                self._editing_group.addWidget(self._edit_buttons.addPhysicalObject)
                self._editing_group.addWidget(self._edit_buttons.updatePhysicalObject)
            self._editing_group.addWidget(self._edit_buttons.export)
            self._editing_group.addWidget(self._edit_buttons.commit)
            self._editing_group.addWidget(self._edit_buttons.rollback)
        left_placeholder = self._left.itemAt(0).widget()
        left_placeholder.setVisible(False)
        self._table = PlatformServicesTableWidget(
            services_list, properties_keys, self._on_cell_change, self._db_properties, is_building
        )
        self._table.disable_callback()
        for i, (_building_modeled, _functional_object_modeled, properties) in enumerate(
            zip(buildings_modeled, functional_objects_modeled, functional_object_properties)
        ):
            for functional_object_property, value in properties.items():
                self._table.item(
                    i, len(PlatformServicesTableWidget.LABELS) + properties_keys.index(functional_object_property)
                ).setText(str(value))
        self._table.enable_callback()
        self._left.replaceWidget(left_placeholder, self._table)
        if not is_building:
            self._table.setColumnWidth(1, 20)
            self._edit_buttons.addBuilding.setVisible(False)
            self._edit_buttons.updateBuilding.setVisible(False)
            self._edit_buttons.addPhysicalObject.setVisible(True)
            self._edit_buttons.updatePhysicalObject.setVisible(True)
            self._editing_group.replaceWidget(self._edit_buttons.addBuilding, self._edit_buttons.addPhysicalObject)
            self._editing_group.replaceWidget(
                self._edit_buttons.updateBuilding, self._edit_buttons.updatePhysicalObject
            )
        else:
            self._table.setColumnWidth(1, 400)
            self._edit_buttons.addBuilding.setVisible(True)
            self._edit_buttons.updateBuilding.setVisible(True)
            self._edit_buttons.addPhysicalObject.setVisible(False)
            self._edit_buttons.updatePhysicalObject.setVisible(False)
            self._editing_group.replaceWidget(self._edit_buttons.addPhysicalObject, self._edit_buttons.addBuilding)
            self._editing_group.replaceWidget(
                self._edit_buttons.updatePhysicalObject, self._edit_buttons.updateBuilding
            )

        self._log_window.insertHtml(f'<font color=blue>Работа с городом "{self._city_choose.currentText()}"</font><br>')
        self._log_window.insertHtml(
            "<font color=blue>Загружены {len(services_list)} сервисов"
            f' типа "{self._service_type.currentText()}"</font><br>'
        )

    def _on_cell_change(  # pylint: disable=too-many-arguments
        self, row: int, column_name: str, old_value: Any, new_value: Any, is_valid: bool
    ) -> None:
        func_id = self._table.item(row, 0).text()
        if is_valid:
            if (
                column_name == "Мощность"
                and self._table.item(row, PlatformServicesTableWidget.LABELS_DB.index("is_capacity_real")).text()
                == "False"
            ):
                with self._db_properties.conn.cursor() as cur:
                    cur.execute("UPDATE functional_objects SET is_capacity_real = true WHERE id = %s", (func_id,))
                self._table.item(row, PlatformServicesTableWidget.LABELS_DB.index("is_capacity_real")).setText("true")
            self._log_window.insertHtml(
                f"<font color=yellowgreen>Изменен объект с func_id={func_id}. {column_name}:"
                f' "{to_str(old_value)}"->"{to_str(new_value)}"</font><br>'
            )
        else:
            self._log_window.insertHtml(
                f"<font color=#e6783c>Не изменен объект с func_id="
                f'{func_id}. {column_name}: "{to_str(old_value)}"->"{to_str(new_value)}"'
                " (некорректное значение)</font><br>"
            )
            return
        with self._db_properties.conn.cursor() as cur:
            if column_name in PlatformServicesTableWidget.LABELS:
                column = PlatformServicesTableWidget.LABELS.index(column_name)
                db_column = PlatformServicesTableWidget.LABELS_DB[column]
                cur.execute(
                    f"UPDATE functional_objects SET {db_column} = %s,"
                    " updated_at = date_trunc('second', now()) WHERE id = %s",
                    (new_value, func_id),
                )
            else:
                cur.execute(
                    "UPDATE functional_objects SET properties = properties || %s::jsonb WHERE id = %s",
                    (json.dumps({column_name: new_value}), func_id),
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
                    func_id = self._table.item(row - 1, 0).text()
                    self._log_window.insertHtml(f'<font color=red>{func_id}{", " if i != len(rows) - 1 else ""}</font>')
                    self._log_window.repaint()
                    cur.execute(
                        "DELETE FROM provision.houses_services WHERE house_id = %s OR service_id = %s", (func_id,) * 2
                    )
                    cur.execute("DELETE FROM provision.services WHERE service_id = %s", (func_id,))
                    cur.execute("DELETE FROM provision.houses WHERE house_id = %s", (func_id,))
                    cur.execute("SELECT physical_object_id FROM functional_objects WHERE id = %s", (func_id,))
                    phys_id = cur.fetchone()[0]  # type: ignore
                    cur.execute("DELETE FROM functional_objects WHERE id = %s", (func_id,))
                    cur.execute("SELECT count(*) FROM functional_objects WHERE physical_object_id = %s", (phys_id,))
                    phys_count = cur.fetchone()[0]  # type: ignore
                    if phys_count == 0:
                        cur.execute("DELETE FROM buildings WHERE physical_object_id = %s", (phys_id,))
                        cur.execute("DELETE FROM physical_objects WHERE id = %s", (phys_id,))
                    self._table.removeRow(row - 1)
                self._log_window.insertHtml("</font><br>")

    def _on_geometry_show(self) -> None:
        with self._db_properties.conn.cursor() as cur:
            cur.execute(
                "SELECT ST_AsGeoJSON(geometry, 6) FROM physical_objects WHERE id = %s",
                (
                    self._table.item(
                        self._table.currentRow(), PlatformServicesTableWidget.LABELS_DB.index("physical_object_id")
                    ).text(),
                ),
            )
            res = cur.fetchone()
            if res is None:
                return
            geometry = json.loads(res[0])
        GeometryShowWidget(json.dumps(geometry, indent=4)).exec()

    def _on_add_physical_object(self) -> None:
        row = self._table.currentRow()
        func_id, _phys_id = self._table.item(row, 0).text(), self._table.item(row, 8).text()
        dialog = PhysicalObjectCreationWidget(
            f"Введите информацию о физическом объекте для сервиса в строке {row + 1} в поля ниже", is_adding=True
        )
        if dialog.exec() != QtWidgets.QDialog.Accepted or self._additional_conn is None:
            return
        try:
            new_geometry = json.loads(dialog.get_geometry())  # type: ignore
            with self._additional_conn.cursor() as cur:
                cur.execute(
                    "SELECT ST_AsGeoJSON(ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 6),"
                    " ST_GeometryType(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))",
                    (json.dumps(new_geometry),) * 2,
                )
                new_center, geom_type = cur.fetchone()  # type: ignore
                new_center = json.loads(new_center)
                new_longitude, new_latitude = new_center["coordinates"]
        except Exception as exc:  # pylint: disable=broad-except
            logger.trace("error on an physical_object insertion for a functional_object with id={}: {!r}", func_id, exc)
            self._additional_conn.rollback()
            self._log_window.insertHtml(
                f"<font color=#e6783c>Ошибка при добавлении физического объекта сервису с id={func_id}</font><br>"
            )
        else:
            with self._db_properties.conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO physical_objects (osm_id, geometry, center, city_id)"
                    " VALUES (%s, ST_SnapToGrid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), 0.000001),"
                    "   ST_SnapToGrid(ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 0.000001),"
                    "   (SELECT id FROM cities WHERE name = %s))"
                    " RETURNING id",
                    (dialog.osm_id(),) + (json.dumps(new_geometry),) * 2 + (self._city_choose.currentText(),),
                )
                new_phys_id = cur.fetchone()[0]  # type: ignore
                cur.execute(
                    "UPDATE physical_objects SET"
                    " administrative_unit_id = (SELECT id from administrative_units WHERE ST_CoveredBy("
                    " (SELECT center FROM physical_objects WHERE id = %s), geometry) ORDER BY population DESC LIMIT 1),"
                    " municipality_id = (SELECT id from municipalities WHERE ST_CoveredBy("
                    " (SELECT center FROM physical_objects WHERE id = %s), geometry) ORDER BY population DESC LIMIT 1)"
                    " WHERE id = %s",
                    (new_phys_id,) * 3,
                )
                cur.execute(
                    "UPDATE functional_objects SET physical_object_id = %s, updated_at = date_trunc('second', now())"
                    " WHERE id = %s",
                    (new_phys_id, func_id),
                )
            self._log_window.insertHtml(
                f"<font color=yellowgreen>Добавлен физический объект для сервиса с"
                " id={func_id}: {phys_id}->{new_phys_id}"
                f" ({self._table.item(row, 11).text()}({self._table.item(row, 9).text()},"
                f" {self._table.item(row, 10).text()})"
                f"->{geom_type}({new_latitude, new_longitude}))</font><br>"
            )
            self._table.item(row, 8).setText(str(new_phys_id))
            self._table.item(row, 8).setBackground(QtCore.Qt.GlobalColor.yellow)
            self._table.item(row, 9).setText(str(new_latitude))
            self._table.item(row, 9).setBackground(QtCore.Qt.GlobalColor.yellow)
            self._table.item(row, 10).setText(str(new_longitude))
            self._table.item(row, 10).setBackground(QtCore.Qt.GlobalColor.yellow)
            self._table.item(row, 11).setText(geom_type)
            self._table.item(row, 11).setBackground(QtCore.Qt.GlobalColor.yellow)

    def _on_update_physical_object(self) -> None:
        row = self._table.currentRow()
        func_id, phys_id = self._table.item(row, 0).text(), self._table.item(row, 8).text()
        with self._db_properties.conn.cursor() as cur:
            cur.execute("SELECT ST_AsGeoJSON(geometry), osm_id FROM physical_objects WHERE id = %s", (phys_id,))
            geometry, osm_id = cur.fetchone()  # type: ignore
        geometry = json.loads(geometry)
        dialog = PhysicalObjectCreationWidget(
            f"Если необходимо, измените параметры физического объекта для сервиса на строке {row + 1}",
            json.dumps(geometry, indent=2),
            osm_id,
        )
        if dialog.exec() != QtWidgets.QDialog.Accepted or self._additional_conn is None:
            return
        new_geom_tuple = check_geometry_correctness(dialog.get_geometry(), self._additional_conn)
        if new_geom_tuple is None:
            self._log_window.insertHtml(
                f"<font color=#e6783c>Физический объект для сервиса с id={func_id}"
                f" (phys_id)={phys_id}) не обновлен, ошибка в геометрии</font><br>"
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
                    "       ORDER BY population DESC LIMIT 1),"
                    " municipality_id = (SELECT id from municipalities"
                    "   WHERE ST_CoveredBy("
                    "       (SELECT center FROM physical_objects WHERE id = %s), geometry)"
                    "   ORDER BY population DESC LIMIT 1)"
                    " WHERE id = %s",
                    (phys_id,) * 3,
                )
            self._log_window.insertHtml(
                "<font color=yellowgreen>Геометрия физического объекта сервиса"
                f" с id={func_id} (phys_id={phys_id}) изменена:"
                f" {self._table.item(row, 11).text()}({self._table.item(row, 9).text()},"
                f" {self._table.item(row, 10).text()})"
                f"->{geom_type}({new_latitude, new_longitude})</font><br>"
            )
            self._table.item(row, 9).setText(str(new_latitude))
            self._table.item(row, 9).setBackground(QtCore.Qt.GlobalColor.yellow)
            self._table.item(row, 10).setText(str(new_longitude))
            self._table.item(row, 10).setBackground(QtCore.Qt.GlobalColor.yellow)
            self._table.item(row, 11).setText(geom_type)
            self._table.item(row, 11).setBackground(QtCore.Qt.GlobalColor.yellow)
        if osm_id != dialog.osm_id():
            with self._db_properties.conn.cursor() as cur:
                cur.execute(
                    "UPDATE physical_objects SET osm_id = %s, updated_at = date_trunc('second', now()) WHERE id = %s",
                    (osm_id, phys_id),
                )
            self._log_window.insertHtml(
                f"<font color=yellowgreen>OpenStreetMapID для phys_id={phys_id} изменен:"
                f" {osm_id}->{dialog.osm_id()}</font><br>"
            )

    def _on_add_building(self) -> None:  # pylint: disable=too-many-locals
        row = self._table.currentRow()
        func_id = self._table.item(row, 0).text()
        dialog = BuildingCreationWidget(
            f"Введите информацию о здании для добавления для сервиса на строке {row + 1} в поля ниже", is_adding=True
        )
        if dialog.exec() != QtWidgets.QDialog.Accepted or self._additional_conn is None:
            return
        (
            osm_id,
            address,
            building_date,
            building_area,
            repair_years,
            building_area_living,
            storeys,
            lift_count,
            population,
            project_type,
            ukname,
        ) = (
            dialog.osm_id(),
            dialog.address(),
            dialog.building_date(),
            dialog.repair_years(),
            dialog.building_area(),
            dialog.building_area_living(),
            dialog.storeys(),
            dialog.lift_count(),
            dialog.population(),
            dialog.project_type(),
            dialog.ukname(),
        )
        heating, hotwater, electricity, gas, refusechute, is_failing, is_living = (
            dialog.central_heating(),
            dialog.central_hotwater(),
            dialog.central_electricity(),
            dialog.central_gas(),
            dialog.refusechute(),
            dialog.is_failing(),
            dialog.is_living(),
        )
        res = check_geometry_correctness(dialog.get_geometry(), self._additional_conn)
        if res is None or address is None:
            self._log_window.insertHtml(
                f"<font color=#e6783c>Ошибка при добавлении здания сервису с id={func_id}</font><br>"
            )
            return
        new_latitude, new_longitude, geom_type = res
        with self._db_properties.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO physical_objects (osm_id, geometry, center, city_id)"
                " VALUES (%s, ST_SnapToGrid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), 0.000001),"
                "   ST_SnapToGrid(ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 0.000001),"
                "   (SELECT id FROM cities WHERE name = %s))"
                " RETURNING id",
                (osm_id,) + (dialog.get_geometry(),) * 2 + (self._city_choose.currentText(),),
            )
            new_phys_id = cur.fetchone()[0]  # type: ignore
            cur.execute(
                "UPDATE physical_objects SET"
                " administrative_unit_id = (SELECT id from administrative_units WHERE ST_CoveredBy("
                " (SELECT center FROM physical_objects WHERE id = %s), geometry) ORDER BY population DESC LIMIT 1),"
                " municipality_id = (SELECT id from municipalities WHERE ST_CoveredBy("
                " (SELECT center FROM physical_objects WHERE id = %s), geometry) ORDER BY population DESC LIMIT 1)"
                " WHERE id = %s",
                (new_phys_id,) * 3,
            )
            cur.execute(
                "INSERT INTO buildings (physical_object_id, address, building_date,"
                "      repair_years, building_area, living_area,"
                "   storeys_count, lift_count, resident_number, project_type, ukname,"
                "   central_heating, central_hotwater, central_electro,"
                "   central_gas, refusechute, failure, is_living)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    new_phys_id,
                    address,
                    building_date,
                    repair_years,
                    building_area,
                    building_area_living,
                    storeys,
                    lift_count,
                    population,
                    project_type,
                    ukname,
                    heating,
                    hotwater,
                    electricity,
                    gas,
                    refusechute,
                    is_failing,
                    is_living,
                ),
            )
            cur.execute("UPDATE functional_objects SET physical_object_id = %s WHERE id = %s", (new_phys_id, func_id))
        self._table.item(row, 1).setText(address)
        self._table.item(row, 1).setBackground(QtCore.Qt.GlobalColor.yellow)
        self._table.item(row, 8).setText(str(new_phys_id))
        self._table.item(row, 8).setBackground(QtCore.Qt.GlobalColor.yellow)
        self._table.item(row, 9).setText(str(new_latitude))
        self._table.item(row, 9).setBackground(QtCore.Qt.GlobalColor.yellow)
        self._table.item(row, 10).setText(str(new_longitude))
        self._table.item(row, 10).setBackground(QtCore.Qt.GlobalColor.yellow)
        self._table.item(row, 11).setText(geom_type)
        self._table.item(row, 11).setBackground(QtCore.Qt.GlobalColor.yellow)

    def _on_update_building(self) -> None:  # pylint: disable=too-many-locals
        row = self._table.currentRow()
        func_id, phys_id = self._table.item(row, 0).text(), self._table.item(row, 8).text()
        with self._db_properties.conn.cursor() as cur:
            cur.execute(
                "SELECT ST_AsGeoJSON(p.geometry), p.osm_id, b.address, b.building_date,"
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
            f"Если необходимо, измените параметры здания для сервиса на строке {row + 1}",
            json.dumps(geometry, indent=2),
            *res,
        )
        if dialog.exec() != QtWidgets.QDialog.Accepted or self._additional_conn is None:
            return
        new_geom_tuple = check_geometry_correctness(dialog.get_geometry(), self._additional_conn)
        if new_geom_tuple is None:
            self._log_window.insertHtml(
                f"<font color=#e6783c>Здание для сервиса с id={func_id}"
                f" (build_id={b_id}) не обновлено, ошибка в геометрии</font><br>"
            )
            return
        if dialog.address() is None:
            self._log_window.insertHtml(
                f"<font color=#e6783c>Здание для сервиса с id={func_id}"
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
                f"<font color=yellowgreen>Геометрия сервиса с id={func_id} (phys_id={phys_id}) изменена:"
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
                    "building_date",
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
                    dialog.building_date(),
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
            f"<green>Коммит следующих изменений сервисов в базу данных</green>:\n{self._log_window.toPlainText()[:-1]}"
        )
        self._db_properties.conn.commit()
        self._edit_buttons.load.click()
        self._log_window.insertHtml("<font color=green>Изменения записаны, обновленная информация загружена</font><br>")

    def _on_rollback(self) -> None:
        self._db_properties.conn.rollback()
        self._edit_buttons.load.click()

    def _set_service_types(self, service_types: Iterable[str]) -> None:
        service_types = list(service_types)
        current_service_type = self._service_type.currentText()
        self._service_type.clear()
        if len(service_types) == 0:
            self._service_type.addItem("(Нет типов сервисов)")
            self._service_type.view().setMinimumWidth(len(self._service_type.currentText()) * 8)
            self._edit_buttons.load.setEnabled(False)
        else:
            self._service_type.addItems(service_types)
            if current_service_type in service_types:
                self._service_type.setCurrentText(current_service_type)
            self._service_type.view().setMinimumWidth(len(max(service_types, key=len)) * 8)
            self._edit_buttons.load.setEnabled(True)

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
            else:
                self._on_city_change()
            self._city_choose.view().setMinimumWidth(len(max(cities, key=len)) * 8)

    def change_db(  # pylint: disable=too-many-arguments
        self, db_addr: str, db_port: int, db_name: str, db_user: str, db_pass: str
    ) -> None:
        """Uptdate database connection. Called from the outside if the connection to the database has changed."""
        self._db_properties.reopen(db_addr, db_port, db_name, db_user, db_pass)
        if self._additional_conn is not None and not self._additional_conn.closed:
            self._additional_conn.close()
        self._additional_conn = self._db_properties.copy().conn
        self._on_city_change()

    def showEvent(self, event: QtGui.QShowEvent) -> None:  # pylint: disable=invalid-name
        logger.info("Открыто окно изменения сервисов")
        return super().showEvent(event)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # pylint: disable=invalid-name
        logger.info("Закрыто окно изменения сервисов")
        if self._on_close is not None:
            self._on_close()
        return super().closeEvent(event)
