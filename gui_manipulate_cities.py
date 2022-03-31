import itertools
import json
import logging
import time
from typing import Any, Callable, List, Literal, NamedTuple, Optional, Set, Sequence, Tuple, Union

from PySide6 import QtCore, QtGui, QtWidgets
import psycopg2

from database_properties import Properties
from gui_basics import ColoringTableWidget, GeometryShow, check_geometry_correctness

log = logging.getLogger('services_manipulation').getChild('cities_manipulation_gui')

class PlatformCitiesTableWidget(ColoringTableWidget):
    LABELS = ['id города', 'Название', 'Население', 'Тип деления', 'Широта', 'Долгота', 'Тип геометрии', 'Создание', 'Обновление']
    LABELS_DB = ['id', 'name', 'population', 'city_division_type', '-', '-', '-', '-', '-']
    def __init__(self, services: Sequence[Sequence[Any]], changed_callback: Callable[[int, str, Any, Any, bool], None],
            parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(services, PlatformCitiesTableWidget.LABELS, self.correction_checker, (0, 3, 4, 5, 6, 7, 8), parent=parent)
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
        if PlatformCitiesTableWidget.LABELS_DB[column] != '-':
            self._changed_callback(row, PlatformCitiesTableWidget.LABELS[column], old_data, new_data, res)
        return res

class PlatformTerritoriesTableWidget(QtWidgets.QTableWidget):
    LABELS = ['id территории', 'Название', 'Население', 'Тип территории', 'Родительская территория', 'Широта', 'Долгота', 'Тип геометрии', 'Создание', 'Обновление']
    LABELS_DB = ['id', 'name', 'population', '-', '-', '-', '-', '-', '-', '-']
    def __init__(self, territories: Sequence[Sequence[Any]], parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent=parent)
        self.setRowCount(len(territories))
        self.setColumnCount(len(PlatformTerritoriesTableWidget.LABELS))
        self.setHorizontalHeaderLabels(PlatformTerritoriesTableWidget.LABELS)
        self.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)
        for i, row in enumerate(territories):
            for j, item in enumerate(row):
                self.setItem(i, j, QtWidgets.QTableWidgetItem(_to_str(item)))
        self.setColumnWidth(1, 200)
        self.setColumnWidth(2, 90)
        for column in range(3, 10):
            self.resizeColumnToContents(column)
        self.setSortingEnabled(True)

def _str_or_none(s: str) -> Optional[str]:
    if len(s) == 0:
        return None
    return s

def _to_str(i: Optional[Union[int, float, str]]) -> str:
    return str(i) if i is not None else ''

def _int_or_none(s: str) -> Optional[int]:
    if len(s) == 0:
        return None
    assert s.isnumeric(), f'{s} cannot be converted to integer'
    return int(s)
    

class TerritoryCreation(QtWidgets.QDialog):
    def __init__(self, text: str, title: str, territory_types: List[str], parents: List[str] = [],
            geometry: Optional[str] = None, name: Optional[str] = None,
            population: Optional[int] = None, territory_type: Optional[str] = None, parent_territory: Optional[str] = None,
            parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent=parent)
        self.window().setWindowTitle(title)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel(text))
        self._geometry_field = QtWidgets.QTextEdit()
        self._geometry_field.setPlainText(geometry or '')
        self._geometry_field.setPlaceholderText('{\n  "type": "...",\n  "coordinates": [...]\n}')
        self._geometry_field.setAcceptRichText(False)
        layout.addWidget(self._geometry_field)
        self._options_layout = QtWidgets.QFormLayout()
        self._name = QtWidgets.QLineEdit(name or '')
        self._name.setPlaceholderText('Ленинский')
        self._options_layout.addRow('Название:', self._name)
        self._population = QtWidgets.QLineEdit(_to_str(population))
        self._population.setPlaceholderText('30000')
        self._options_layout.addRow('Население:', self._population)
        self._territory_type = QtWidgets.QComboBox()
        self._territory_type.addItems(territory_types)
        if territory_type is not None:
            self._territory_type.setCurrentText(territory_type)
        self._options_layout.addRow('Тип территории:', self._territory_type)
        self._parent_territory = QtWidgets.QComboBox()
        self._parent_territory.addItems(['-'] + parents)
        if parent_territory is not None:
            self._parent_territory.setCurrentText(parent_territory)
        self._options_layout.addRow('Родительская территория:', self._parent_territory)
        layout.addLayout(self._options_layout)
        buttons_layout = QtWidgets.QHBoxLayout()
        ok_btn = QtWidgets.QPushButton('Ок')
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QtWidgets.QPushButton('Отмена')
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(ok_btn)
        buttons_layout.addWidget(cancel_btn)
        layout.addLayout(buttons_layout)
        self.setLayout(layout)

    def get_geometry(self) -> Optional[str]:
        return _str_or_none(self._geometry_field.toPlainText())

    def name(self) -> Optional[str]:
        return _str_or_none(self._name.text())

    def population(self) -> Optional[int]:
        return _int_or_none(self._population.text())

    def territory_type(self) -> str:
        return self._territory_type.currentText()

    def parent_territory(self) -> Optional[str]:
        return self._parent_territory.currentText() if self._parent_territory.currentIndex() != 0 else None

class CityCreation(QtWidgets.QDialog):
    def __init__(self, text: str, geometry: Optional[str] = None, name: Optional[str] = None,
            population: Optional[int] = None,
            division_type: Optional[Literal['NO_PARENT', 'ADMIN_UNIT_PARENT', 'MUNICIPALITY_PARENT']] = None,
            is_adding: bool = False, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent=parent)
        self.window().setWindowTitle('Добавление города' if is_adding else 'Изменение города')
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel(text))
        self._geometry_field = QtWidgets.QTextEdit()
        self._geometry_field.setPlainText(geometry or '')
        self._geometry_field.setPlaceholderText('{\n  "type": "...",\n  "coordinates": [...]\n}')
        self._geometry_field.setAcceptRichText(False)
        layout.addWidget(self._geometry_field)
        self._options_layout = QtWidgets.QFormLayout()
        self._name = QtWidgets.QLineEdit(name or '')
        self._name.setPlaceholderText('Санкт-Петербург')
        self._options_layout.addRow('Название:', self._name)
        self._population = QtWidgets.QLineEdit(_to_str(population))
        self._population.setPlaceholderText('6000000')
        self._options_layout.addRow('Население:', self._population)
        self._division_type = QtWidgets.QComboBox()
        self._division_type.addItems(['NO_PARENT', 'ADMIN_UNIT_PARENT', 'MUNICIPALITY_PARENT'])
        if division_type is not None:
            self._division_type.setCurrentText(division_type)
        self._options_layout.addRow('Тип админ. деления:', self._division_type)
        layout.addLayout(self._options_layout)
        buttons_layout = QtWidgets.QHBoxLayout()
        ok_btn = QtWidgets.QPushButton('Ок')
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QtWidgets.QPushButton('Отмена')
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(ok_btn)
        buttons_layout.addWidget(cancel_btn)
        layout.addLayout(buttons_layout)
        self.setLayout(layout)

    def get_geometry(self) -> Optional[str]:
        return _str_or_none(self._geometry_field.toPlainText())

    def name(self) -> Optional[str]:
        return _str_or_none(self._name.text())

    def population(self) -> Optional[int]:
        return _int_or_none(self._population.text())

    def division_type(self) -> str:
        return self._division_type.currentText()


class TerritoryWindow(QtWidgets.QWidget):
    EditButtons = NamedTuple('EditButtons', [
            ('add', QtWidgets.QPushButton),
            ('edit', QtWidgets.QPushButton),
            ('delete', QtWidgets.QPushButton),
            ('showGeometry', QtWidgets.QPushButton),
        ]
    )
    def __init__(self, conn: psycopg2.extensions.connection, additional_conn: psycopg2.extensions.connection,
            city_name: str, territory_type: Literal['municipality', 'administrative_unit'], on_territory_add_callback: Callable[[int, str], None],
            on_territory_edit_callback: Callable[[int, str, List[Tuple[str, str, str]]], None], on_territory_delete_callback: Callable[[List[Tuple[int, str]]], None],
            on_error_callback: Callable[[str], None], parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._conn = conn
        self._additional_conn = additional_conn
        self._territory_window: Optional[TerritoryWindow] = None
        self._on_territory_add_callback = on_territory_add_callback
        self._on_territory_edit_callback = on_territory_edit_callback
        self._on_territory_delete_callback = on_territory_delete_callback
        self._on_error_callback = on_error_callback
        

        self._territory_name_what = 'муниципального образования' if territory_type == 'municipality' else 'административной единицы'
        self._territory_name_action = 'муниципальное образование' if territory_type == 'municipality' else 'административную единицу'
        self._territory_name_plural = 'муниципальных образований' if territory_type == 'municipality' else 'административных единиц'
        self._territory_table = 'municipalities' if territory_type == 'municipality' else 'administrative_units'
        self._territory_types_table = 'municipality_types' if territory_type == 'municipality' else 'administrative_unit_types'
        self._other_territory_table = 'administrative_units' if territory_type == 'municipality' else 'municipalities'
        self._parent_id_column = 'admin_unit_parent_id' if territory_type == 'municipality' else 'municipality_parent_id'
        self._other_parent_id_column = 'municipality_parent_id' if territory_type == 'municipality' else 'admin_unit_parent_id'
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
            cur.execute(f'SELECT id, name, population, (select full_name FROM {self._territory_types_table} WHERE id = type_id),'
                    f'      (SELECT name FROM {self._other_territory_table} WHERE id = {self._parent_id_column}),'
                    '       ST_Y(center), ST_X(center), ST_GeometryType(geometry),'
                    "       date_trunc('minute', created_at)::timestamp, date_trunc('minute', updated_at)::timestamp"
                    f' FROM {self._territory_table}'
                    ' WHERE city_id = (SELECT id from cities WHERE name = %s)'
                    ' ORDER BY 1',
                    (self._city_name,)
            )
            territories = cur.fetchall()
            cur.execute(f'SELECT name FROM {self._other_territory_table}'
                    ' WHERE city_id = (SELECT id from cities WHERE name = %s)'
                    ' ORDER BY 1',
                    (self._city_name,)
            )
            self._parents = list(itertools.chain.from_iterable(cur.fetchall()))
            cur.execute(f'SELECT full_name FROM {self._territory_types_table} ORDER BY id')
            self._territory_types = list(itertools.chain.from_iterable(cur.fetchall()))
        self._table = PlatformTerritoriesTableWidget(territories)
        self._left.addWidget(self._table)
        
        self._editing_group_box = QtWidgets.QGroupBox('Изменение списка')
        self._editing_group = QtWidgets.QFormLayout()
        self._editing_group_box.setLayout(self._editing_group)
        self._edit_buttons = TerritoryWindow.EditButtons(QtWidgets.QPushButton(f'Добавить {self._territory_name_action}'),
                QtWidgets.QPushButton(f'Изменить {self._territory_name_action}'), QtWidgets.QPushButton(f'Удалить {self._territory_name_action}'),
                QtWidgets.QPushButton('Посмотреть геометрию')
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
        dialog = TerritoryCreation(f'Добавление территории - {self._territory_name_what}', f'Город "{self._city_name}" - добавить {self._territory_name_action}',
                self._territory_types, self._parents)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        else:
            new_geom_tuple = check_geometry_correctness(dialog.get_geometry(), self._additional_conn)
            if new_geom_tuple is None:
                self._on_error_callback(f'Ошибка в геометрии при добавлении территории - {self._territory_name_what} для города {self._city_name}')
                return
            latitude, longitude, geom_type = new_geom_tuple
            with self._conn.cursor() as cur:
                cur.execute(f'INSERT INTO {self._territory_table} (city_id, type_id, name, geometry, center, population) VALUES'
                        f'   ((SELECT id FROM cities WHERE name = %s), (SELECT id FROM {self._territory_types_table} WHERE full_name = %s),'
                        '       %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),'
                        '       ST_SnapToGrid(ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 0.000001), %s)'
                        ' RETURNING id',
                        (self._city_name, dialog.territory_type(), dialog.name(), dialog.get_geometry(),
                                dialog.get_geometry(), dialog.population())
                )
                territory_id = cur.fetchone()[0]
            self._on_territory_add_callback(territory_id, _to_str(dialog.name()))
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(territory_id)))
            self._table.setItem(row, 1, QtWidgets.QTableWidgetItem(_to_str(dialog.name())))
            self._table.setItem(row, 2, QtWidgets.QTableWidgetItem(_to_str(dialog.population())))
            self._table.setItem(row, 3, QtWidgets.QTableWidgetItem(dialog.territory_type()))
            self._table.setItem(row, 4, QtWidgets.QTableWidgetItem(_to_str(dialog.parent_territory())))
            self._table.setItem(row, 5, QtWidgets.QTableWidgetItem(str(latitude)))
            self._table.setItem(row, 6, QtWidgets.QTableWidgetItem(str(longitude)))
            self._table.setItem(row, 7, QtWidgets.QTableWidgetItem(geom_type))
            now = time.strftime('%Y-%M-%d %H:%M:00')
            self._table.setItem(row, 8, QtWidgets.QTableWidgetItem(now))
            self._table.setItem(row, 9, QtWidgets.QTableWidgetItem(now))
            for column in range(self._table.columnCount()):
                self._table.item(row, column).setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))

    def _on_territoey_edit(self) -> None:
        row = self._table.currentRow()
        territory_id = self._table.item(row, 0).text()
        with self._conn.cursor() as cur:
            cur.execute(f'SELECT ST_AsGeoJSON(geometry), name, population, (SELECT name FROM {self._other_territory_table} WHERE id = {self._parent_id_column}),'
                    f'       (select full_name FROM {self._territory_types_table} WHERE id = type_id) FROM {self._territory_table} WHERE id = %s',
                    (self._table.item(row, 0).text(),))
            geometry, name, population, parent_territory, territory_type = cur.fetchone()
            geometry = json.loads(geometry)
        dialog = TerritoryCreation(f'Изменение территории - {self._territory_name_what}', f'Город "{self._city_name}" - изменить {self._territory_name_action}',
                self._territory_types, self._parents, json.dumps(geometry, indent=2), name, population, territory_type, parent_territory)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        else:
            changes = []
            new_geom_tuple = check_geometry_correctness(dialog.get_geometry(), self._additional_conn)
            if new_geom_tuple is None:
                self._on_error_callback(f'{self._territory_name_what} "{name}" с id={territory_id} не изменен, ошибка в геометрии')
                return
            new_geometry = json.loads(dialog.get_geometry()) # type: ignore
            with self._conn.cursor() as cur:
                if geometry != new_geometry:
                    new_latitude, new_longitude, geom_type = new_geom_tuple
                    cur.execute(f'UPDATE {self._territory_table} SET geometry = ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),'
                            '   center = ST_SnapToGrid(ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 0.000001),'
                            " updated_at = date_trunc('second', now())"
                            ' WHERE id = %s',
                            (dialog.get_geometry(), dialog.get_geometry(), territory_id))
                    changes.append(('геометрия', f'{self._table.item(row, 6).text()}({self._table.item(row, 4).text()}, {self._table.item(row, 5).text()})',
                            f'{geom_type}({new_latitude, new_longitude}'))
                    self._table.item(row, 5).setText(str(new_latitude))
                    self._table.item(row, 6).setText(str(new_longitude))
                    self._table.item(row, 7).setText(geom_type)
                    for c in (5, 6, 7):
                        self._table.item(row, c).setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))
                if name != dialog.name():
                    changes.append(('название', name, _to_str(dialog.name())))
                    self._table.item(row, 1).setText(_to_str(name))
                    self._table.item(row, 1).setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))
                    cur.execute(f'UPDATE {self._territory_table} SET name = %s,'
                            " updated_at = date_trunc('second', now()) WHERE id = %s", (dialog.name(), territory_id))
                if population != dialog.population():
                    changes.append(('население', population, _to_str(dialog.population())))
                    self._table.item(row, 2).setText(_to_str(population))
                    self._table.item(row, 2).setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))
                    cur.execute(f'UPDATE {self._territory_table} SET population = %s,'
                            " updated_at = date_trunc('second', now()) WHERE id = %s", (dialog.population(), territory_id))
                if territory_type != dialog.territory_type():
                    changes.append(('тип территории', territory_type, _to_str(dialog.territory_type())))
                    self._table.item(row, 3).setText(_to_str(dialog.territory_type()))
                    self._table.item(row, 3).setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))
                    cur.execute(f'UPDATE {self._territory_table} SET type_id ='
                            f' (SELECT id FROM {self._territory_types_table} WHERE full_name = %s),'
                            " updated_at = date_trunc('second', now()) WHERE id = %s", (dialog.territory_type(), territory_id))
                if parent_territory != dialog.parent_territory():
                    changes.append(('родительская территория', parent_territory, _to_str(dialog.parent_territory())))
                    self._table.item(row, 4).setText(_to_str(dialog.parent_territory()))
                    self._table.item(row, 4).setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))
                    cur.execute(f'UPDATE {self._territory_table} u SET {self._parent_id_column} ='
                            f' (SELECT id FROM {self._other_territory_table} p WHERE name = %s AND p.city_id = u.city_id),'
                            " updated_at = date_trunc('second', now()) WHERE id = %s", (dialog.parent_territory(), territory_id))
            self._on_territory_edit_callback(int(territory_id), self._table.item(row, 2).text(), changes)
    
    def _on_territory_delete(self) -> None:
        rows = sorted(set(map(lambda index: index.row() + 1, self._table.selectedIndexes())))
        if len(rows) == 0:
            return
        if len(rows) > 1:
            is_deleting = QtWidgets.QMessageBox.question(self, f'Удаление территориальных единиц - {self._territory_name_what}',
                    f'Вы уверены, что хотите удалить {self._territory_name_plural} в строках под номерами: {", ".join(map(str, rows))}?')
        else:
            object_row = next(iter(rows))
            is_deleting = QtWidgets.QMessageBox.question(self, f'Удаление {self._territory_name_what}',
                    f'Вы уверены, что хотите удалить {self._territory_name_action} в строке под номером {object_row}?')
        if is_deleting == QtWidgets.QMessageBox.StandardButton.Yes:
            deleting = []
            with self._conn.cursor() as cur:
                for row in rows[::-1]:
                    territory_id = self._table.item(row - 1, 0).text()
                    deleting.append((int(self._table.item(row - 1, 0).text()), self._table.item(row - 1, 1).text()))
                    cur.execute(f'UPDATE {self._other_territory_table} SET {self._other_parent_id_column} = null WHERE {self._other_parent_id_column} = %s', (territory_id,))
                    cur.execute(f'DELETE FROM {self._territory_table} WHERE id = %s', (territory_id,))
                    self._table.removeRow(row - 1)
            self._on_territory_delete_callback(deleting)

    def _on_geometry_show(self) -> None:
        with self._conn.cursor() as cur:
            cur.execute(f'SELECT ST_AsGeoJSON(geometry, 6) FROM {self._territory_table} WHERE id = %s', (self._table.item(self._table.currentRow(), 0).text(),))
            res = cur.fetchone()
            if res is None:
                return
            geometry = json.loads(res[0])
        GeometryShow(json.dumps(geometry, indent=2)).exec()


class CitiesWindow(QtWidgets.QWidget):

    EditButtons = NamedTuple('EditButtons', [
            ('add', QtWidgets.QPushButton),
            ('edit', QtWidgets.QPushButton),
            ('delete', QtWidgets.QPushButton),
            ('showGeometry', QtWidgets.QPushButton),
            ('listMO', QtWidgets.QPushButton),
            ('listAU', QtWidgets.QPushButton),
            ('commit', QtWidgets.QPushButton),
            ('rollback', QtWidgets.QPushButton),
            ('refresh_matviews', QtWidgets.QPushButton),
            ('update_locations', QtWidgets.QPushButton)
        ]
    )

    def __init__(self, db_properties: Properties, on_close: Optional[Callable[[], None]] = None, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)

        self._db_properties = db_properties
        self._additional_conn = db_properties.copy().conn
        self._on_close = on_close
        self._territory_window: Optional[TerritoryWindow] = None

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

        left_placeholder = QtWidgets.QLabel('(Здесь будут отображены объекты)')
        left_placeholder.setMinimumSize(300, 300)
        left_placeholder.setAlignment(QtCore.Qt.AlignCenter)
        self._left.addWidget(left_placeholder)

        self._table: QtWidgets.QTableWidget

        self._editing_group_box = QtWidgets.QGroupBox('Изменение списка')
        self._editing_group = QtWidgets.QFormLayout()
        self._editing_group_box.setLayout(self._editing_group)
        self._edit_buttons = CitiesWindow.EditButtons(QtWidgets.QPushButton('Добавить город'),
                QtWidgets.QPushButton('Изменить город'), QtWidgets.QPushButton('Удалить город'),
                QtWidgets.QPushButton('Посмотреть геометрию'), QtWidgets.QPushButton('Список МО'),
                QtWidgets.QPushButton('Список АЕ'), QtWidgets.QPushButton('Сохранить изменения в БД'),
                QtWidgets.QPushButton('Отмена внесенных изменений'), QtWidgets.QPushButton('Обновить представления'),
                QtWidgets.QPushButton('Обновить локации объектов')
        )
        self._edit_buttons.add.clicked.connect(self._on_city_add)
        self._edit_buttons.edit.clicked.connect(self._on_city_edit)
        self._edit_buttons.delete.clicked.connect(self._on_city_delete)
        self._edit_buttons.showGeometry.clicked.connect(self._on_geometry_show)
        self._edit_buttons.listMO.clicked.connect(self._on_show_MOs)
        self._edit_buttons.listAU.clicked.connect(self._on_show_AUs)
        self._edit_buttons.commit.clicked.connect(self._on_commit_changes)
        self._edit_buttons.commit.setStyleSheet('background-color: lightgreen;color: black')
        self._edit_buttons.rollback.clicked.connect(self._on_rollback)
        self._edit_buttons.rollback.setStyleSheet('background-color: red;color: black')
        self._edit_buttons.refresh_matviews.clicked.connect(self._on_refresh_matviews)
        self._edit_buttons.update_locations.clicked.connect(self._on_update_locations)
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
            cur.execute('SELECT id, name, population, city_division_type, ST_Y(center), ST_X(center), ST_GeometryType(geometry),'
                    "   date_trunc('minute', created_at)::timestamp, date_trunc('minute', updated_at)::timestamp"
                    ' FROM cities'
                    ' ORDER BY 1'
            )
            cities = cur.fetchall()
        left_placeholder = self._left.itemAt(0).widget()
        left_placeholder.setVisible(False)
        self._table = PlatformCitiesTableWidget(cities, self._on_cell_change)
        self._left.replaceWidget(left_placeholder, self._table)
        
        self._log_window.insertHtml(f'<font color=blue>Загружены {len(cities)} городов</font><br>')

    def _on_cell_change(self, row: int, column_name: str, old_value: Any, new_value: Any, is_valid: bool) -> None:
        city_id = self._table.item(row, 0).text()
        if is_valid:
            self._log_window.insertHtml(f'<font color=yellowgreen>Изменен город с id={city_id}. {column_name}:'
                    f' "{_to_str(old_value)}"->"{_to_str(new_value)}"</font><br>')
        else:
            self._log_window.insertHtml(f'<font color=#e6783c>Не изменен город с id='
                    f'{city_id}. {column_name}: "{_to_str(old_value)}"->"{_to_str(new_value)}" (некорректное значение)</font><br>')
            return
        column = PlatformCitiesTableWidget.LABELS.index(column_name)
        db_column = PlatformCitiesTableWidget.LABELS_DB[column]
        with self._db_properties.conn.cursor() as cur:
            cur.execute(f"UPDATE cities SET {db_column} = %s, updated_at = date_trunc('second', now()) WHERE id = %s",
                    (new_value, city_id))

    def _on_city_add(self) -> None:
        dialog = CityCreation('Добавление нового города', is_adding=True)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        else:
            new_geom_tuple = check_geometry_correctness(dialog.get_geometry(), self._additional_conn)
            if new_geom_tuple is None:
                self._log_window.insertHtml(f'<font color=#e6783c>Город не добавлен, ошибка в геометрии</font><br>')
                return
            latitude, longitude, geom_type = new_geom_tuple
            with self._db_properties.conn.cursor() as cur:
                cur.execute('INSERT INTO cities (name, geometry, center, population, city_division_type) VALUES'
                        '   (%s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), ST_SnapToGrid(ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 0.000001), %s, %s)'
                        ' RETURNING id',
                        (dialog.name(), dialog.get_geometry(), dialog.get_geometry(), dialog.population(), dialog.division_type()))
                city_id = cur.fetchone()[0]
            self._log_window.insertHtml(f'<font color=yellowgreen>Добавлен город "{dialog.name()}" c id={city_id}</font><br>')
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(city_id)))
            self._table.setItem(row, 1, QtWidgets.QTableWidgetItem(_to_str(dialog.name())))
            self._table.setItem(row, 2, QtWidgets.QTableWidgetItem(_to_str(dialog.population())))
            self._table.setItem(row, 3, QtWidgets.QTableWidgetItem(_to_str(dialog.division_type())))
            self._table.setItem(row, 4, QtWidgets.QTableWidgetItem(str(latitude)))
            self._table.setItem(row, 5, QtWidgets.QTableWidgetItem(str(longitude)))
            self._table.setItem(row, 6, QtWidgets.QTableWidgetItem(geom_type))
            now = time.strftime('%Y-%M-%d %H:%M:00')
            self._table.setItem(row, 7, QtWidgets.QTableWidgetItem(now))
            self._table.setItem(row, 8, QtWidgets.QTableWidgetItem(now))
            for column in range(self._table.columnCount()):
                self._table.item(row, column).setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))

    def _on_city_edit(self) -> None:
        row = self._table.currentRow()
        if row == -1:
            return
        city_id = self._table.item(row, 0).text()
        with self._db_properties.conn.cursor() as cur:
            cur.execute('SELECT ST_AsGeoJSON(geometry), name, population, city_division_type FROM cities WHERE id = %s', (self._table.item(row, 0).text(),))
            geometry, name, population, division_type = cur.fetchone()
            geometry = json.loads(geometry)
        dialog = CityCreation(f'Внесение изменений в город в строке под номером {row + 1}', json.dumps(geometry, indent=2), name, population, division_type)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        else:
            new_geom_tuple = check_geometry_correctness(dialog.get_geometry(), self._additional_conn)
            if new_geom_tuple is None:
                self._log_window.insertHtml(f'<font color=#e6783c>Город "{name}" с id={city_id} не изменен, ошибка в геометрии</font><br>')
                return
            new_geometry = json.loads(dialog.get_geometry()) # type: ignore
            if geometry != new_geometry:
                new_latitude, new_longitude, geom_type = new_geom_tuple
                with self._db_properties.conn.cursor() as cur:
                    cur.execute('UPDATE cities SET geometry = ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326),'
                            '   center = ST_SnapToGrid(ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 0.000001)'
                            ' WHERE id = %s',
                            (dialog.get_geometry(), dialog.get_geometry(), city_id))
                self._log_window.insertHtml(f'<font color=yellowgreen>Изменена геометрия города "{dialog.name()}" c id={city_id}:'
                        f' {self._table.item(row, 6).text()}({self._table.item(row, 4).text()}, {self._table.item(row, 5).text()})'
                        f'->{geom_type}({new_latitude, new_longitude}</font><br>')
                self._table.item(row, 4).setText(str(new_latitude))
                self._table.item(row, 5).setText(str(new_longitude))
                self._table.item(row, 6).setText(geom_type)
                for c in (4, 5, 6):
                    self._table.item(row, c).setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))
            if name != dialog.name():
                self._table.item(row, 1).setText(_to_str(name))
                self._table.item(row, 1).setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))
            if population != dialog.population():
                self._table.item(row, 2).setText(_to_str(population))
                self._table.item(row, 2).setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))
            if division_type != dialog.division_type():
                self._table.item(row, 3).setText(dialog.division_type())
                self._table.item(row, 3).setBackground(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))
            
    def _on_city_delete(self) -> None:
        rows = sorted(set(map(lambda index: index.row() + 1, self._table.selectedIndexes())))
        if len(rows) == 0:
            return
        if len(rows) > 1:
            is_deleting = QtWidgets.QMessageBox.question(self, 'Удаление городов',
                    f'Вы уверены, что хотите удалить города в строках под номерами: {", ".join(map(str, rows))}?')
        else:
            object_row = next(iter(rows))
            is_deleting = QtWidgets.QMessageBox.question(self, 'Удаление города', f'Вы уверены, что хотите удалить город в строке под номером {object_row}?')
        if is_deleting == QtWidgets.QMessageBox.StandardButton.Yes:
            with self._db_properties.conn.cursor() as cur:
                for row in rows[::-1]:
                    city_id = self._table.item(row - 1, 0).text()
                    self._log_window.insertHtml(f'<font color=red>Удаление города с id={city_id}</font><br>')
                    cur.execute('SELECT f.id FROM functional_objects f JOIN physical_objects p ON f.physical_object_id = p.id'
                            ' WHERE p.city_id = %s', (city_id,))
                    city_objects = tuple(itertools.chain.from_iterable(cur.fetchall()))
                    if len(city_objects) == 1:
                        city_objects *= 2
                    if len(city_objects) > 0:
                        cur.execute(f'DELETE FROM provision.houses_services WHERE house_id IN {city_objects} OR service_id IN {city_objects}')
                        cur.execute(f'DELETE FROM provision.services WHERE service_id IN {city_objects}')
                        cur.execute(f'DELETE FROM provision.houses WHERE house_id IN {city_objects}')
                        cur.execute(f'DELETE FROM functional_objects WHERE id IN {city_objects}')
                        cur.execute('SELECT id FROM physical_objects WHERE city_id = %s', (city_id,))
                    city_objects = tuple(itertools.chain.from_iterable(cur.fetchall()))
                    if len(city_objects) == 1:
                        city_objects *= 2
                    if len(city_objects) > 0:
                        cur.execute(f'DELETE FROM buildings WHERE physical_object_id IN {city_objects}')
                        cur.execute('DELETE FROM physical_objects WHERE city_id = %s', (city_id,))
                    cur.execute('DELETE FROM blocks WHERE city_id = %s', (city_id,))
                    cur.execute('UPDATE municipalities SET admin_unit_parent_id = null WHERE city_id = %s', (city_id,))
                    cur.execute('DELETE FROM administrative_units WHERE city_id = %s', (city_id,))
                    cur.execute('DELETE FROM municipalities WHERE city_id = %s', (city_id,))
                    cur.execute('DELETE FROM cities WHERE id = %s', (city_id,))
                    self._table.removeRow(row - 1)

    def _on_geometry_show(self) -> None:
        row = self._table.currentRow()
        if row == -1:
            return
        with self._db_properties.conn.cursor() as cur:
            cur.execute('SELECT ST_AsGeoJSON(geometry, 6) FROM cities WHERE id = %s', (self._table.item(row, 0).text(),))
            res = cur.fetchone()
            if res is None:
                return
            geometry = json.loads(res[0])
        GeometryShow(json.dumps(geometry, indent=2)).exec()

    def _on_error(self, text: str) -> None:
        self._log_window.insertHtml(f'<font color=#e6783c>{text}</font><br>')

    def _on_show_MOs(self) -> None:
        row = self._table.currentRow()
        if row == -1:
            return
        self._territory_window = TerritoryWindow(self._db_properties.conn, self._additional_conn, self._table.item(row, 1).text(),
                'municipality', self._on_municipality_add, self._on_municipality_edit, self._on_municipality_delete, self._on_error)
        self._territory_window.show()

    def _on_municipality_add(self, municipality_id: int, municipality_name: str) -> None:
        self._log_window.insertHtml('<font color=yellowgreen>Добавлено муниципальное образование к городу'
                f' {self._table.item(self._table.currentRow(), 1).text()}: "{municipality_name}" (id={municipality_id})</font><br>')
    
    def _on_municipality_edit(self, municipality_id: int, municipality_name: str, changes: List[Tuple[str, str, str]]) -> None:
        if len(changes) != 0:
            self._log_window.insertHtml(f'<font color=yellowgreen>Изменены параметры муниципального образования "{municipality_name}"'
                    f' (id={municipality_id}):<br>')
            for what_changed, old_value, new_value in changes:
                self._log_window.insertHtml(f'&nbsp;&nbsp;{what_changed}: "{_to_str(old_value)}"->"{_to_str(new_value)}"<br>')
            self._log_window.insertHtml('</font>')
    
    def _on_municipality_delete(self, deleting: List[Tuple[int, str]]) -> None:
        for municipality_id, municipality_name in deleting:
            self._log_window.insertHtml(f'<font color=red>Удаление муниципального образования "{municipality_name}" с id={municipality_id}</font><br>')
    
    def _on_show_AUs(self) -> None:
        row = self._table.currentRow()
        if row == -1:
            return
        self._territory_window = TerritoryWindow(self._db_properties.conn, self._additional_conn, self._table.item(row, 1).text(),
                'administrative_unit', self._on_administrative_unit_add, self._on_administrative_unit_edit, self._on_administrative_unit_delete, self._on_error)
        self._territory_window.show()

    def _on_administrative_unit_add(self, administrative_unit_id: int, administrative_unit_name: str) -> None:
        self._log_window.insertHtml('<font color=yellowgreen>Добавлена административная единица к городу'
                f' {self._table.item(self._table.currentRow(), 1).text()}: "{administrative_unit_name}" (id={administrative_unit_id})</font><br>')
    
    def _on_administrative_unit_edit(self, administrative_unit_id: int, administrative_unit_name: str, changes: List[Tuple[str, str, str]]) -> None:
        if len(changes) != 0:
            self._log_window.insertHtml(f'<font color=yellowgreen>Изменены параметры административной единицы "{administrative_unit_name}"'
                    f' (id={administrative_unit_id}):<br>')
            for what_changed, old_value, new_value in changes:
                self._log_window.insertHtml(f'&nbsp;&nbsp;{what_changed}: "{_to_str(old_value)}"->"{_to_str(new_value)}"<br>')
            self._log_window.insertHtml('</font>')
    
    def _on_administrative_unit_delete(self, deleting: List[Tuple[int, str]]) -> None:
        for administrative_unit_id, administrative_unit_name in deleting:
            self._log_window.insertHtml(f'<font color=red>Удаление административной единицы "{administrative_unit_name}" с id={administrative_unit_id}</font><br>')

    def _on_commit_changes(self) -> None:
        self._log_window.insertHtml('<font color=green>Запись изменений в базу данных</font><br>')
        log.info(f'Коммит следующих изменений сервисов в базу данных:\n{self._log_window.toPlainText()[:-1]}')
        self._db_properties.conn.commit()
        self._on_cities_load()
        self._log_window.insertHtml('<font color=green>Изменения записаны, обновленная информация загружена</font><br>')

    def _on_rollback(self) -> None:
        self._db_properties.conn.rollback()
        self._on_cities_load()

    def _on_refresh_matviews(self) -> None:
        log.info('Обновление материализованных представлений')
        self._log_window.insertHtml('<font color=grey>Обновление материализованных представлений...</font>')
        self._log_window.repaint()
        with self._db_properties.conn, self._db_properties.conn.cursor() as cur:
            cur.execute('REFRESH MATERIALIZED VIEW all_services')
            cur.execute('REFRESH MATERIALIZED VIEW houses')
            cur.execute('REFRESH MATERIALIZED VIEW all_houses')
        self._log_window.insertHtml('<font color=green>Завершено</font><br>')

    def _on_update_locations(self) -> None:
        log.info('Обновление местоположения физических объектов без указания административного образования, МО или квартала')
        self._log_window.insertHtml('<font color=grey>Обновление местоположения физических объектов...</font>')
        self._log_window.repaint()
        with self._db_properties.conn, self._db_properties.conn.cursor() as cur:
            cur.execute('select update_physical_objects_location()')
        self._log_window.insertHtml('<font color=green>Завершено</font><br>')

    def change_db(self, db_addr: str, db_port: int, db_name: str, db_user: str, db_pass: str) -> None:
        self._db_properties.reopen(db_addr, db_port, db_name, db_user, db_pass)
        if self._additional_conn is not None and not self._additional_conn.closed:
            self._additional_conn.close()
        self._additional_conn = self._db_properties.copy().conn
    
    def showEvent(self, event: QtGui.QShowEvent) -> None:
        log.info('Открыто окно работы с городами')
        self._on_cities_load()
        return super().showEvent(event)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        log.info('Закрыто окно работы с городами')
        if self._territory_window is not None:
            self._territory_window.close()
        if self._on_close is not None:
            self._on_close()
        return super().closeEvent(event)
