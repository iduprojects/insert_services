"""Platform territory widget is defined here."""
import itertools
import json
import time
from typing import Callable, Literal, NamedTuple

import psycopg2  # pylint: disable=unused-import
from PySide6 import QtCore, QtGui, QtWidgets

from platform_management.gui.basics import GeometryShow, check_geometry_correctness
from platform_management.utils.converters import to_str

from .territories_table import PlatformTerritoriesTableWidget
from .territory_creation import TerritoryCreationWidget


class TerritoryWindow(QtWidgets.QWidget):  # pylint: disable=too-many-instance-attributes
    """Platform territories list window."""

    EditButtons = NamedTuple(
        "EditButtons",
        [
            ("add", QtWidgets.QPushButton),
            ("edit", QtWidgets.QPushButton),
            ("delete", QtWidgets.QPushButton),
            ("showGeometry", QtWidgets.QPushButton),
        ],
    )

    def __init__(  # pylint: disable=too-many-arguments,too-many-statements
        self,
        conn: "psycopg2.connection",
        additional_conn: "psycopg2.connection",
        city_name: str,
        territory_type: Literal["municipality", "administrative_unit"],
        on_territory_add_callback: Callable[[int, str, str], None],
        on_territory_edit_callback: Callable[[int, str, list[tuple[str, str, str]], str], None],
        on_territory_delete_callback: Callable[[list[tuple[int, str]], str], None],
        on_error_callback: Callable[[str], None],
        parent: QtWidgets.QWidget | None = None,
    ):
        super().__init__(parent)
        self._conn = conn
        self._additional_conn = additional_conn
        self._territory_window: TerritoryWindow | None = None
        self._on_territory_add_callback = on_territory_add_callback
        self._on_territory_edit_callback = on_territory_edit_callback
        self._on_territory_delete_callback = on_territory_delete_callback
        self._on_error_callback = on_error_callback

        self._territory_name_what = (
            "муниципального образования" if territory_type == "municipality" else "административной единицы"
        )
        self._territory_name_action = (
            "муниципальное образование" if territory_type == "municipality" else "административную единицу"
        )
        self._territory_name_plural = (
            "муниципальных образований" if territory_type == "municipality" else "административных единиц"
        )
        self._territory_table = "municipalities" if territory_type == "municipality" else "administrative_units"
        self._territory_types_table = (
            "municipality_types" if territory_type == "municipality" else "administrative_unit_types"
        )
        self._other_territory_table = "administrative_units" if territory_type == "municipality" else "municipalities"
        self._parent_id_column = (
            "admin_unit_parent_id" if territory_type == "municipality" else "municipality_parent_id"
        )
        self._other_parent_id_column = (
            "municipality_parent_id" if territory_type == "municipality" else "admin_unit_parent_id"
        )
        self._city_name = city_name

        self.window().setWindowTitle(f'Город "{city_name}" - список {self._territory_name_plural}')

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

        with self._conn.cursor() as cur:
            cur.execute(
                f"SELECT id, name, population,"
                f"       (SELECT full_name FROM {self._territory_types_table} WHERE id = type_id),"
                f"      (SELECT name FROM {self._other_territory_table} WHERE id = {self._parent_id_column}),"
                "       ST_Y(center), ST_X(center), ST_GeometryType(geometry),"
                "       date_trunc('minute', created_at)::timestamp, date_trunc('minute', updated_at)::timestamp"
                f" FROM {self._territory_table}"
                " WHERE city_id = (SELECT id from cities WHERE name = %s)"
                " ORDER BY 1",
                (self._city_name,),
            )
            territories = cur.fetchall()
            cur.execute(
                f"SELECT name FROM {self._other_territory_table}"
                " WHERE city_id = (SELECT id from cities WHERE name = %s)"
                " ORDER BY 1",
                (self._city_name,),
            )
            self._parents = list(itertools.chain.from_iterable(cur.fetchall()))
            cur.execute(f"SELECT full_name FROM {self._territory_types_table} ORDER BY id")
            self._territory_types = list(itertools.chain.from_iterable(cur.fetchall()))
        self._table = PlatformTerritoriesTableWidget(territories)
        self._left.addWidget(self._table)

        self._editing_group_box = QtWidgets.QGroupBox("Изменение списка")
        self._editing_group = QtWidgets.QFormLayout()
        self._editing_group_box.setLayout(self._editing_group)
        self._edit_buttons = TerritoryWindow.EditButtons(
            QtWidgets.QPushButton(f"Добавить {self._territory_name_action}"),
            QtWidgets.QPushButton(f"Изменить {self._territory_name_action}"),
            QtWidgets.QPushButton(f"Удалить {self._territory_name_action}"),
            QtWidgets.QPushButton("Посмотреть геометрию"),
        )
        self._edit_buttons.add.clicked.connect(self._on_territory_add)
        self._edit_buttons.edit.clicked.connect(self._on_territoey_edit)
        self._edit_buttons.delete.clicked.connect(self._on_territory_delete)
        self._edit_buttons.showGeometry.clicked.connect(self._on_geometry_show)
        for btn in self._edit_buttons:
            self._editing_group.addWidget(btn)
        self._right.addWidget(self._editing_group_box)

        self._right.setAlignment(QtCore.Qt.AlignTop)
        right_width = self._editing_group_box.sizeHint().width()

        self._right_scroll.setFixedWidth(int(right_width * 1.1))
        self._editing_group_box.setFixedWidth(right_width)

    def _on_territory_add(self) -> None:
        dialog = TerritoryCreationWidget(
            f"Добавление территории - {self._territory_name_what}",
            f'Город "{self._city_name}" - добавить {self._territory_name_action}',
            self._territory_types,
            self._parents,
        )
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        new_geom_tuple = check_geometry_correctness(dialog.get_geometry(), self._additional_conn)
        if new_geom_tuple is None:
            self._on_error_callback(
                f"Ошибка в геометрии при добавлении территории - {self._territory_name_what}"
                f" для города {self._city_name}"
            )
            return
        latitude, longitude, geom_type = new_geom_tuple
        with self._conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {self._territory_table} (city_id, type_id, name, geometry, center, population) VALUES"
                f"   ((SELECT id FROM cities WHERE name = %s), (SELECT id FROM {self._territory_types_table}"
                "           WHERE full_name = %s),"
                "   %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),"
                "   ST_SnapToGrid(ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 0.000001), %s)"
                " RETURNING id",
                (
                    self._city_name,
                    dialog.territory_type(),
                    dialog.name(),
                    dialog.get_geometry(),
                    dialog.get_geometry(),
                    dialog.population(),
                ),
            )
            territory_id = cur.fetchone()[0]  # type: ignore
        self._on_territory_add_callback(territory_id, to_str(dialog.name()), self._city_name)
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(territory_id)))
        self._table.setItem(row, 1, QtWidgets.QTableWidgetItem(to_str(dialog.name())))
        self._table.setItem(row, 2, QtWidgets.QTableWidgetItem(to_str(dialog.population())))
        self._table.setItem(row, 3, QtWidgets.QTableWidgetItem(dialog.territory_type()))
        self._table.setItem(row, 4, QtWidgets.QTableWidgetItem(to_str(dialog.parent_territory())))
        self._table.setItem(row, 5, QtWidgets.QTableWidgetItem(str(latitude)))
        self._table.setItem(row, 6, QtWidgets.QTableWidgetItem(str(longitude)))
        self._table.setItem(row, 7, QtWidgets.QTableWidgetItem(geom_type))
        now = time.strftime("%Y-%M-%d %H:%M:00")
        self._table.setItem(row, 8, QtWidgets.QTableWidgetItem(now))
        self._table.setItem(row, 9, QtWidgets.QTableWidgetItem(now))
        for column in range(self._table.columnCount()):
            self._table.item(row, column).setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))

    def _on_territoey_edit(self) -> None:  # pylint: disable=too-many-locals,too-many-statements
        row = self._table.currentRow()
        territory_id = self._table.item(row, 0).text()
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT ST_AsGeoJSON(geometry), name, population,"
                f"   (SELECT name FROM {self._other_territory_table} WHERE id = {self._parent_id_column}),"
                f"   (SELECT full_name FROM {self._territory_types_table} WHERE id = type_id)"
                f" FROM {self._territory_table} WHERE id = %s",
                (self._table.item(row, 0).text(),),
            )
            geometry, name, population, parent_territory, territory_type = cur.fetchone()  # type: ignore
            geometry = json.loads(geometry)
        dialog = TerritoryCreationWidget(
            f"Изменение территории - {self._territory_name_what}",
            f'Город "{self._city_name}" - изменить {self._territory_name_action}',
            self._territory_types,
            self._parents,
            json.dumps(geometry, indent=2),
            name,
            population,
            territory_type,
            parent_territory,
        )
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        changes = []
        new_geom_tuple = check_geometry_correctness(dialog.get_geometry(), self._additional_conn)
        if new_geom_tuple is None:
            self._on_error_callback(
                f'{self._territory_name_what} "{name}" с id={territory_id} для города'
                f' "{self._city_name}" не изменен, ошибка в геометрии'
            )
            return
        new_geometry = json.loads(dialog.get_geometry())  # type: ignore
        changed = False
        with self._conn.cursor() as cur:
            if geometry != new_geometry:
                new_latitude, new_longitude, geom_type = new_geom_tuple
                cur.execute(
                    f"UPDATE {self._territory_table} SET geometry = ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),"
                    "   center = ST_SnapToGrid(ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 0.000001),"
                    " updated_at = date_trunc('second', now())"
                    " WHERE id = %s",
                    (dialog.get_geometry(), dialog.get_geometry(), territory_id),
                )
                changes.append(
                    (
                        "геометрия",
                        f"{self._table.item(row, 6).text()}({self._table.item(row, 4).text()},"
                        f" {self._table.item(row, 5).text()})",
                        f"{geom_type}({new_latitude, new_longitude}",
                    )
                )
                self._table.item(row, 5).setText(str(new_latitude))
                self._table.item(row, 6).setText(str(new_longitude))
                self._table.item(row, 7).setText(geom_type)
                changed = True
                for column in (5, 6, 7):
                    self._table.item(row, column).setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))
            if name != dialog.name():
                changes.append(("название", name, to_str(dialog.name())))
                self._table.item(row, 1).setText(to_str(name))
                self._table.item(row, 1).setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))
                changed = True
                cur.execute(
                    f"UPDATE {self._territory_table} SET name = %s,"
                    " updated_at = date_trunc('second', now()) WHERE id = %s",
                    (dialog.name(), territory_id),
                )
            if population != dialog.population():
                changes.append(("население", population, to_str(dialog.population())))
                self._table.item(row, 2).setText(to_str(population))
                self._table.item(row, 2).setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))
                changed = True
                cur.execute(
                    f"UPDATE {self._territory_table} SET population = %s,"
                    " updated_at = date_trunc('second', now()) WHERE id = %s",
                    (dialog.population(), territory_id),
                )
            if territory_type != dialog.territory_type():
                changes.append(("тип территории", territory_type, to_str(dialog.territory_type())))
                self._table.item(row, 3).setText(to_str(dialog.territory_type()))
                self._table.item(row, 3).setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))
                changed = True
                cur.execute(
                    f"UPDATE {self._territory_table} SET type_id ="
                    f" (SELECT id FROM {self._territory_types_table} WHERE full_name = %s),"
                    " updated_at = date_trunc('second', now()) WHERE id = %s",
                    (dialog.territory_type(), territory_id),
                )
            if parent_territory != dialog.parent_territory():
                changes.append(("родительская территория", parent_territory, to_str(dialog.parent_territory())))
                self._table.item(row, 4).setText(to_str(dialog.parent_territory()))
                self._table.item(row, 4).setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))
                changed = True
                cur.execute(
                    f"UPDATE {self._territory_table} u SET {self._parent_id_column} ="
                    f" (SELECT id FROM {self._other_territory_table} p WHERE name = %s AND p.city_id = u.city_id),"
                    " updated_at = date_trunc('second', now()) WHERE id = %s",
                    (dialog.parent_territory(), territory_id),
                )
            if changed:
                cur.execute(f"UPDATE {self._territory_table} SET updated_at = now() WHERE id = %s", (territory_id,))
        self._on_territory_edit_callback(int(territory_id), self._table.item(row, 2).text(), changes, self._city_name)

    def _on_territory_delete(self) -> None:
        rows = sorted(set(map(lambda index: index.row() + 1, self._table.selectedIndexes())))  # type: ignore
        if len(rows) == 0:
            return
        if len(rows) > 1:
            is_deleting = QtWidgets.QMessageBox.question(
                self,
                f"Удаление территориальных единиц - {self._territory_name_what}",
                f"Вы уверены, что хотите удалить {self._territory_name_plural} в"
                f' строках под номерами: {", ".join(map(str, rows))}?',
            )
        else:
            object_row = next(iter(rows))
            is_deleting = QtWidgets.QMessageBox.question(
                self,
                f"Удаление {self._territory_name_what}",
                f"Вы уверены, что хотите удалить {self._territory_name_action} в строке под номером {object_row}?",
            )
        if is_deleting == QtWidgets.QMessageBox.StandardButton.Yes:
            deleting = []
            with self._conn.cursor() as cur:
                for row in rows[::-1]:
                    territory_id = self._table.item(row - 1, 0).text()
                    deleting.append((int(self._table.item(row - 1, 0).text()), self._table.item(row - 1, 1).text()))
                    cur.execute(
                        f"UPDATE {self._other_territory_table} SET {self._other_parent_id_column} = null"
                        f" WHERE {self._other_parent_id_column} = %s",
                        (territory_id,),
                    )
                    cur.execute(f"DELETE FROM {self._territory_table} WHERE id = %s", (territory_id,))
                    self._table.removeRow(row - 1)
            self._on_territory_delete_callback(deleting, self._city_name)

    def _on_geometry_show(self) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                f"SELECT ST_AsGeoJSON(geometry, 6) FROM {self._territory_table} WHERE id = %s",
                (self._table.item(self._table.currentRow(), 0).text(),),
            )
            res = cur.fetchone()
            if res is None:
                return
            geometry = json.loads(res[0])
        GeometryShow(json.dumps(geometry, indent=2)).exec()
