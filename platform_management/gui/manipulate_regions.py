# pylint: disable=c-extension-no-member
"""
Regions insertion/editing module.
"""
import json
import time
from typing import Any, Callable, NamedTuple, Optional, Sequence, Union

from loguru import logger
from PySide6 import QtCore, QtGui, QtWidgets

from platform_management.database_properties import Properties
from platform_management.gui.basics import ColoringTableWidget, GeometryShow, check_geometry_correctness

logger = logger.bind(name="gui_manipulate_regions")


class PlatformRegionsTableWidget(ColoringTableWidget):
    LABELS = ["id региона", "Название", "Код", "Широта", "Долгота", "Тип геометрии", "Создание", "Обновление"]
    LABELS_DB = ["id", "name", "code", "-", "-", "-", "-", "-"]

    def __init__(
        self,
        services: Sequence[Sequence[Any]],
        changed_callback: Callable[[int, str, Any, Any, bool], None],
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(
            services,
            PlatformRegionsTableWidget.LABELS,
            self.correction_checker,
            list(
                map(
                    lambda x: x[0],
                    filter(lambda y: y[1] in ("id", "-"), enumerate(PlatformRegionsTableWidget.LABELS_DB)),
                )
            ),
            parent=parent,
        )
        self._changed_callback = changed_callback
        self.setColumnWidth(1, 200)
        self.setColumnWidth(2, 90)
        for column in (3, 4, 5, 6, 7, 8):
            self.resizeColumnToContents(column)
        self.setSortingEnabled(True)

    def correction_checker(self, row: int, column: int, old_data: Any, new_data: str) -> bool:
        res = True
        if new_data is None and column in (1, 2):
            res = False
        elif column == 2 and (not new_data.isnumeric() or int(new_data) < 0):
            res = False
        if PlatformRegionsTableWidget.LABELS_DB[column] != "-":
            self._changed_callback(row, PlatformRegionsTableWidget.LABELS[column], old_data, new_data, res)
        return res


def _str_or_none(string: str) -> Optional[str]:
    if len(string) == 0:
        return None
    return string


def _to_str(i: Optional[Union[int, float, str]]) -> str:
    return str(i) if i is not None else ""


class RegionCreation(QtWidgets.QDialog):
    def __init__(
        self,
        text: str,
        geometry: Optional[str] = None,
        name: Optional[str] = None,
        code: Optional[str] = None,
        is_adding: bool = False,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent=parent)
        self.window().setWindowTitle("Добавление региона" if is_adding else "Изменение региона")
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel(text))
        self._geometry_field = QtWidgets.QTextEdit()
        self._geometry_field.setPlainText(geometry or "")
        self._geometry_field.setPlaceholderText('{\n  "type": "...",\n  "coordinates": [...]\n}')
        self._geometry_field.setAcceptRichText(False)
        layout.addWidget(self._geometry_field)
        self._options_layout = QtWidgets.QFormLayout()
        self._name = QtWidgets.QLineEdit(name or "")
        self._name.setPlaceholderText("Ленинградская область")
        self._options_layout.addRow("Название:", self._name)
        self._code = QtWidgets.QLineEdit(code or "")
        self._code.setPlaceholderText("leningrad_oblast")
        self._options_layout.addRow("Код в БД:", self._code)
        layout.addLayout(self._options_layout)
        buttons_layout = QtWidgets.QHBoxLayout()
        ok_btn = QtWidgets.QPushButton("Ок")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QtWidgets.QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(ok_btn)
        buttons_layout.addWidget(cancel_btn)
        layout.addLayout(buttons_layout)
        self.setLayout(layout)

    def get_geometry(self) -> Optional[str]:
        return _str_or_none(self._geometry_field.toPlainText())

    def name(self) -> Optional[str]:
        return _str_or_none(self._name.text())

    def code(self) -> Optional[str]:
        return _str_or_none(self._code.text())


class RegionsWindow(QtWidgets.QWidget):

    EditButtons = NamedTuple(
        "EditButtons",
        [
            ("add", QtWidgets.QPushButton),
            ("edit", QtWidgets.QPushButton),
            ("delete", QtWidgets.QPushButton),
            ("showGeometry", QtWidgets.QPushButton),
            ("commit", QtWidgets.QPushButton),
            ("rollback", QtWidgets.QPushButton),
        ],
    )

    def __init__(
        self,
        db_properties: Properties,
        on_close: Optional[Callable[[], None]] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)

        self._db_properties = db_properties
        try:
            self._db_properties.connect_timeout = 1
            self._additional_conn = self._db_properties.copy().conn
        except RuntimeError:
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

        self._table: QtWidgets.QTableWidget

        self._editing_group_box = QtWidgets.QGroupBox("Изменение списка")
        self._editing_group = QtWidgets.QFormLayout()
        self._editing_group_box.setLayout(self._editing_group)
        self._edit_buttons = RegionsWindow.EditButtons(
            QtWidgets.QPushButton("Добавить регион"),
            QtWidgets.QPushButton("Изменить регион"),
            QtWidgets.QPushButton("Удалить регион"),
            QtWidgets.QPushButton("Посмотреть геометрию"),
            QtWidgets.QPushButton("Сохранить изменения в БД"),
            QtWidgets.QPushButton("Отмена внесенных изменений"),
        )
        self._edit_buttons.add.clicked.connect(self._on_region_add)
        self._edit_buttons.edit.clicked.connect(self._on_city_edit)
        self._edit_buttons.delete.clicked.connect(self._on_city_delete)
        self._edit_buttons.showGeometry.clicked.connect(self._on_geometry_show)
        self._edit_buttons.commit.clicked.connect(self._on_commit_changes)
        self._edit_buttons.commit.setStyleSheet("background-color: lightgreen;color: black")
        self._edit_buttons.rollback.clicked.connect(self._on_rollback)
        self._edit_buttons.rollback.setStyleSheet("background-color: red;color: black")
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

    def _on_regions_load(self) -> None:
        self._log_window.clear()
        self._db_properties.conn.rollback()
        with self._db_properties.conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, code, ST_Y(center), ST_X(center), ST_GeometryType(geometry),"
                "   date_trunc('minute', created_at)::timestamp, date_trunc('minute', updated_at)::timestamp"
                " FROM regions"
                " ORDER BY 1"
            )
            cities = cur.fetchall()
        left_placeholder = self._left.itemAt(0).widget()
        left_placeholder.setVisible(False)
        self._table = PlatformRegionsTableWidget(cities, self._on_cell_change)
        self._left.replaceWidget(left_placeholder, self._table)

        self._log_window.insertHtml(f"<font color=blue>Загружены {len(cities)} регионов</font><br>")

    def _on_cell_change(self, row: int, column_name: str, old_value: Any, new_value: Any, is_valid: bool) -> None:
        city_id = self._table.item(row, 0).text()
        if is_valid:
            self._log_window.insertHtml(
                f"<font color=yellowgreen>Изменен регион с id={city_id}. {column_name}:"
                f' "{_to_str(old_value)}"->"{_to_str(new_value)}"</font><br>'
            )
        else:
            self._log_window.insertHtml(
                f"<font color=#e6783c>Не изменен регион с id="
                f'{city_id}. {column_name}: "{_to_str(old_value)}"->"{_to_str(new_value)}"'
                f" (некорректное значение)</font><br>"
            )
            return
        column = PlatformRegionsTableWidget.LABELS.index(column_name)
        db_column = PlatformRegionsTableWidget.LABELS_DB[column]
        with self._db_properties.conn.cursor() as cur:
            cur.execute(
                f"UPDATE regions SET {db_column} = %s, updated_at = date_trunc('second', now()) WHERE id = %s",
                (new_value, city_id),
            )

    def _on_region_add(self) -> None:
        dialog = RegionCreation("Добавление нового региона", is_adding=True)
        if dialog.exec() != QtWidgets.QDialog.Accepted or self._additional_conn is None:
            return
        new_geom_tuple = check_geometry_correctness(dialog.get_geometry(), self._additional_conn)
        if new_geom_tuple is None:
            self._log_window.insertHtml("<font color=#e6783c>Регион не добавлен, ошибка в геометрии</font><br>")
            return
        latitude, longitude, geom_type = new_geom_tuple
        with self._db_properties.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO regions (name, code, geometry, center)"
                " VALUES (%s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),"
                "   ST_SnapToGrid(ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 0.000001))"
                " RETURNING id",
                (dialog.name(), dialog.code(), dialog.get_geometry(), dialog.get_geometry()),
            )
            city_id = cur.fetchone()[0]  # type: ignore
        self._log_window.insertHtml(
            f'<font color=yellowgreen>Добавлен регион "{dialog.name()}" c id={city_id}</font><br>'
        )
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(city_id)))
        self._table.setItem(row, 1, QtWidgets.QTableWidgetItem(_to_str(dialog.name())))
        self._table.setItem(row, 2, QtWidgets.QTableWidgetItem(_to_str(dialog.code())))
        self._table.setItem(row, 3, QtWidgets.QTableWidgetItem(str(latitude)))
        self._table.setItem(row, 4, QtWidgets.QTableWidgetItem(str(longitude)))
        self._table.setItem(row, 5, QtWidgets.QTableWidgetItem(geom_type))
        now = time.strftime("%Y-%M-%d %H:%M:00")
        self._table.setItem(row, 6, QtWidgets.QTableWidgetItem(now))
        self._table.setItem(row, 7, QtWidgets.QTableWidgetItem(now))
        for column in range(self._table.columnCount()):
            self._table.item(row, column).setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))

    def _on_city_edit(self) -> None:
        row = self._table.currentRow()
        if row == -1:
            return
        city_id = self._table.item(row, 0).text()
        with self._db_properties.conn.cursor() as cur:
            cur.execute(
                "SELECT ST_AsGeoJSON(geometry)::jsonb, name, code FROM cities WHERE id = %s",
                (self._table.item(row, 0).text(),),
            )
            geometry, name, code = cur.fetchone()  # type: ignore
        dialog = RegionCreation(
            f"Внесение изменений в регион в строке под номером {row + 1}", json.dumps(geometry, indent=2), name, code
        )
        if dialog.exec() != QtWidgets.QDialog.Accepted or self._additional_conn is None:
            return
        new_geom_tuple = check_geometry_correctness(dialog.get_geometry(), self._additional_conn)
        if new_geom_tuple is None:
            self._log_window.insertHtml(
                f'<font color=#e6783c>Регион "{name}" с id={city_id} не изменен, ошибка в геометрии</font><br>'
            )
            return
        new_geometry = json.loads(dialog.get_geometry())  # type: ignore
        if geometry != new_geometry:
            new_latitude, new_longitude, geom_type = new_geom_tuple
            with self._db_properties.conn.cursor() as cur:
                cur.execute(
                    "UPDATE regions SET geometry = ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),"
                    "   center = ST_SnapToGrid(ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 0.000001)"
                    " WHERE id = %s",
                    (dialog.get_geometry(), dialog.get_geometry(), city_id),
                )
            self._log_window.insertHtml(
                f'<font color=yellowgreen>Изменена геометрия региона "{dialog.name()}" c id={city_id}:'
                f" {self._table.item(row, 5).text()}({self._table.item(row, 3).text()},"
                f" {self._table.item(row, 4).text()})"
                f"->{geom_type}({new_latitude, new_longitude}</font><br>"
            )
            self._table.item(row, 3).setText(str(new_latitude))
            self._table.item(row, 4).setText(str(new_longitude))
            self._table.item(row, 5).setText(geom_type)
            for column in (4, 5, 6):
                self._table.item(row, column).setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))
        if name != dialog.name():
            self._table.item(row, 1).setText(_to_str(name))
            self._table.item(row, 1).setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))
        if code != dialog.code():
            self._table.item(row, 2).setText(_to_str(code))
            self._table.item(row, 2).setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))

    def _on_city_delete(self) -> None:
        rows = sorted(set(map(lambda index: index.row() + 1, self._table.selectedIndexes())))  # type: ignore
        if len(rows) == 0:
            return
        if len(rows) > 1:
            is_deleting = QtWidgets.QMessageBox.question(
                self,
                "Удаление регионов",
                f'Вы уверены, что хотите удалить регионы в строках под номерами: {", ".join(map(str, rows))}?',
            )
        else:
            object_row = next(iter(rows))
            is_deleting = QtWidgets.QMessageBox.question(
                self, "Удаление региона", f"Вы уверены, что хотите удалить регионы в строке под номером {object_row}?"
            )
        if is_deleting == QtWidgets.QMessageBox.StandardButton.Yes:
            with self._db_properties.conn.cursor() as cur:
                for row in rows[::-1]:
                    region_id = self._table.item(row - 1, 0).text()
                    self._log_window.insertHtml(f"<font color=red>Удаление региона с id={region_id}</font><br>")
                    cur.execute("UPDATE cities SET region = null WHERE region_id = %s", (region_id,))
                    cur.execute("DELETE FROM regions WHERE id = %s", (region_id,))
                    self._table.removeRow(row - 1)

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

    def _on_commit_changes(self) -> None:
        self._log_window.insertHtml("<font color=green>Запись изменений в базу данных</font><br>")
        logger.opt(colors=True).info(
            f"<green>Коммит следующих изменений сервисов в базу данных</green>:\n{self._log_window.toPlainText()[:-1]}"
        )
        self._db_properties.conn.commit()
        self._on_regions_load()
        self._log_window.insertHtml("<font color=green>Изменения записаны, обновленная информация загружена</font><br>")

    def _on_rollback(self) -> None:
        self._db_properties.conn.rollback()
        self._on_regions_load()

    def change_db(self, db_addr: str, db_port: int, db_name: str, db_user: str, db_pass: str) -> None:
        self._db_properties.reopen(db_addr, db_port, db_name, db_user, db_pass)
        if self._additional_conn is not None and not self._additional_conn.closed:
            self._additional_conn.close()
        self._additional_conn = self._db_properties.copy().conn

    def showEvent(self, event: QtGui.QShowEvent) -> None:  # pylint: disable=invalid-name
        logger.info("Открыто окно работы с регионами")
        self._on_regions_load()
        return super().showEvent(event)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # pylint: disable=invalid-name
        logger.info("Закрыто окно работы с регионами")
        self._on_close()
        return super().closeEvent(event)
