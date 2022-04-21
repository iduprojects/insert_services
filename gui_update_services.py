import itertools
import json
import time
from typing import Any, Callable, Iterable, List, NamedTuple, Optional, Sequence, Union

import pandas as pd
from loguru import logger
from PySide6 import QtCore, QtGui, QtWidgets

from database_properties import Properties
from gui_basics import ColoringTableWidget, ColorizingComboBox, check_geometry_correctness

logger = logger.bind(name='gui_update_services')

class PlatformServicesTableWidget(ColoringTableWidget):
    LABELS = ['id сервиса', 'Адрес', 'Название', 'Рабочие часы', 'Веб-сайт', 'Телефон',
                'Мощность', 'Мощ-real', 'id физ. объекта', 'Широта', 'Долгота', 'Тип геометрии', 'Админ. единица', 'Муницип. образование', 'Создание', 'Обновление']
    LABELS_DB = ['id', '-', 'name', 'opening_hours', 'website', 'phone', 'capacity', 'is_capacity_real', 'physical_object_id', '-', '-', '-', '-', '-', '-']
    def __init__(self, services: Sequence[Sequence[Any]], changed_callback: Callable[[int, str, Any, Any, bool], None],
            db_properties: Properties, is_service_building: bool):
        super().__init__(services, PlatformServicesTableWidget.LABELS, self.correction_checker, (0, 1, 9, 10, 11, 12, 13, 14, 15))
        self._db_properties = db_properties
        self._changed_callback = changed_callback
        self._is_service_building = is_service_building
        self.setColumnWidth(2, 200)
        self.setColumnWidth(3, 120)
        self.setColumnWidth(4, 190)
        self.setColumnWidth(5, 180)
        for column in range(8, 16):
            self.resizeColumnToContents(column)
        self.setSortingEnabled(True)

    def correction_checker(self, row: int, column: int, old_data: Any, new_data: str) -> bool:
        res = True
        if new_data is None and column in (6, 7):
            res = False
        elif column == 6 and (not new_data.isnumeric() or int(new_data) < 0):
            res = False
        elif column == 7 and new_data.lower() not in ('true', 'false', '0', '1'):
            res = False
        elif column == 8 and not new_data.isnumeric():
            res = False
        elif column == 8:
            with self._db_properties.conn.cursor() as cur:
                cur.execute('SELECT EXISTS (SELECT 1 FROM physical_objects WHERE id = %s), EXISTS (SELECT 1 FROM buildings WHERE physical_object_id = %s)',
                        (new_data, new_data))
                if cur.fetchone() != (True, self._is_service_building):
                    res = False
        if PlatformServicesTableWidget.LABELS_DB[column] != '-':
            self._changed_callback(row, PlatformServicesTableWidget.LABELS[column], old_data, new_data, res)
        return res


class GeometryShow(QtWidgets.QDialog):
    def __init__(self, geometry: str, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent=parent)
        self.window().setWindowTitle('Просмотр геометрии')
        layout = QtWidgets.QVBoxLayout()
        geometry_field = QtWidgets.QTextEdit()
        geometry_field.setPlainText(geometry)
        geometry_field.setMinimumSize(300, 300)
        geometry_field.setReadOnly(True)
        layout.addWidget(geometry_field)
        copy_btn = QtWidgets.QPushButton('Скопировать в буфер обмена')
        def copy_and_close():
            QtWidgets.QApplication.clipboard().setText(geometry_field.toPlainText())
            self.accept()
        copy_btn.clicked.connect(copy_and_close)
        layout.addWidget(copy_btn)
        self.setLayout(layout)


def _str_or_none(s: str) -> Optional[str]:
    if len(s) == 0:
        return None
    return s

def _int_or_none(s: str) -> Optional[int]:
    if len(s) == 0:
        return None
    assert s.isnumeric(), f'{s} cannot be converted to integer'
    return int(s)

def _to_str(i: Optional[Union[int, float, str]]) -> str:
    return str(i) if i is not None else ''

def _float_or_none(s: str) -> Optional[float]:
    if len(s) == 0:
        return None
    assert s.replace('.', '').isnumeric() and s.count('.') < 2, f'{s} cannot be convected to float'
    return float(s)

def _bool_or_none(state: QtCore.Qt.CheckState) -> Optional[bool]:
    if state == QtCore.Qt.CheckState.PartiallyChecked:
        return None
    elif state == QtCore.Qt.CheckState.Checked:
        return True
    return False

def _bool_to_checkstate(b: Optional[bool]) -> QtCore.Qt.CheckState:
    if b is None:
        return QtCore.Qt.CheckState.PartiallyChecked
    if b:
        return QtCore.Qt.CheckState.Checked
    return QtCore.Qt.CheckState.Unchecked


class GeometryUpdate(QtWidgets.QDialog):
    def __init__(self, text: str, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent=parent)
        self.window().setWindowTitle('Изменение геометрии')
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel(text))
        self._geometry_field = QtWidgets.QTextEdit()
        self._geometry_field.setPlaceholderText('{\n  "type": "...",\n  "geometry": [...]\n}')
        self._geometry_field.setAcceptRichText(False)
        layout.addWidget(self._geometry_field)
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


class PhysicalObjectCreation(QtWidgets.QDialog):
    def __init__(self, text: str, geometry: Optional[str] = None,
            osm_id: Optional[str] = None, is_adding: bool = False, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent=parent)
        self.window().setWindowTitle('Добавление физического объекта' if is_adding else 'Изменение физического объекта')
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel(text))
        self._geometry_field = QtWidgets.QTextEdit()
        self._geometry_field.setPlainText(geometry or '')
        self._geometry_field.setPlaceholderText('{\n  "type": "...",\n  "coordinates": [...]\n}')
        self._geometry_field.setAcceptRichText(False)
        layout.addWidget(self._geometry_field)
        self._options_layout = QtWidgets.QFormLayout()
        self._osm_id = QtWidgets.QLineEdit(osm_id or '')
        self._osm_id.setPlaceholderText('5255196821')
        self._options_layout.addRow('OpenStreetMap id:', self._osm_id)
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

    def osm_id(self) -> Optional[str]:
        return _str_or_none(self._osm_id.text())

    def get_geometry(self) -> Optional[str]:
        return _str_or_none(self._geometry_field.toPlainText())

class BuildingCreation(QtWidgets.QDialog):
    def __init__(self, text: str, geometry: Optional[str] = None, osm_id: Optional[str] = None,
            address: Optional[str] = None, building_date: Optional[str] = None,
            repair_years: Optional[str] = None, building_area: Optional[float] = None,
            living_area: Optional[float] = None, storeys: Optional[int] = None, lift_count: Optional[int] = None,
            population: Optional[int] = None, project_type: Optional[str] = None, ukname: Optional[str] = None,
            central_heating: Optional[bool] = None, central_hotwater: Optional[bool] = None,
            central_electricity: Optional[bool] = None, central_gas: Optional[bool] = None,
            refusechute: Optional[bool] = None, is_failfing: Optional[bool] = None,
            is_living: Optional[bool] = None, is_adding: bool = False,
            parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent=parent)
        self.window().setWindowTitle('Добавление здания' if is_adding else 'Изменение здания')

        double_validator = QtGui.QDoubleValidator(0.0, 1000000.0, 4)
        double_validator.setLocale(QtCore.QLocale.English)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel(text))
        self._geometry_field = QtWidgets.QTextEdit()
        self._geometry_field.setPlainText(geometry or '')
        self._geometry_field.setPlaceholderText('{\n  "type": "...",\n  "coordinates": [...]\n}')
        self._geometry_field.setAcceptRichText(False)
        layout.addWidget(self._geometry_field)
        self._options_layout = QtWidgets.QFormLayout()
        self._osm_id = QtWidgets.QLineEdit(osm_id or '')
        self._osm_id.setPlaceholderText('5255196821')
        self._options_layout.addRow('OpenStreetMap id:', self._osm_id)
        self._address = QtWidgets.QLineEdit(address or '')
        self._address.setPlaceholderText('Город, улица, номер дома')
        self._options_layout.addRow('Адрес', self._address)
        self._building_date = QtWidgets.QLineEdit(building_date or '')
        self._building_date.setPlaceholderText('2001-2002')
        self._options_layout.addRow('Дата постройки', self._building_date)
        self._repair_years = QtWidgets.QLineEdit(repair_years or '')
        self._repair_years.setPlaceholderText('2003; 2007')
        self._options_layout.addRow('Года ремонта', self._repair_years)
        self._building_area = QtWidgets.QLineEdit(_to_str(building_area))
        self._building_area.setPlaceholderText('123.45')
        self._building_area.setValidator(double_validator)
        self._options_layout.addRow('Площадь дома', self._building_area)
        self._building_area_living = QtWidgets.QLineEdit(_to_str(living_area))
        self._building_area_living.setPlaceholderText('1234.5')
        self._building_area_living.setValidator(double_validator)
        self._options_layout.addRow('Общая жилая площадь', self._building_area_living)
        self._storeys = QtWidgets.QLineEdit(_to_str(storeys))
        self._storeys.setPlaceholderText('8')
        self._storeys.setValidator(QtGui.QIntValidator(1, 100))
        self._options_layout.addRow('Этажность', self._storeys)
        self._lift_count = QtWidgets.QLineEdit(_to_str(lift_count))
        self._lift_count.setPlaceholderText('4')
        self._options_layout.addRow('Количество лифтов', self._lift_count)
        self._population = QtWidgets.QLineEdit(_to_str(population))
        self._population.setPlaceholderText('250')
        self._population.setValidator(QtGui.QIntValidator(0, 20000))
        self._options_layout.addRow('Население', self._population)
        self._project_type = QtWidgets.QLineEdit(project_type or '')
        self._project_type.setPlaceholderText('1ЛГ-602В-8')
        self._ukname = QtWidgets.QLineEdit(ukname or '')
        self._ukname.setPlaceholderText('ЖСК № 355')
        self._options_layout.addRow('Застройщик', self._ukname)
        self._central_heating = QtWidgets.QCheckBox()
        self._central_heating.setTristate(True)
        self._central_heating.setCheckState(_bool_to_checkstate(central_heating))
        self._options_layout.addRow('Централизованное отопление', self._central_heating)
        self._central_hotwater = QtWidgets.QCheckBox()
        self._central_hotwater.setTristate(True)
        self._central_hotwater.setCheckState(_bool_to_checkstate(central_hotwater))
        self._options_layout.addRow('Централизованная горячая вода', self._central_hotwater)
        self._central_electricity = QtWidgets.QCheckBox()
        self._central_electricity.setTristate(True)
        self._central_electricity.setCheckState(_bool_to_checkstate(central_electricity))
        self._options_layout.addRow('Централизованное электричество', self._central_electricity)
        self._central_gas = QtWidgets.QCheckBox()
        self._central_gas.setTristate(True)
        self._central_gas.setCheckState(_bool_to_checkstate(central_gas))
        self._options_layout.addRow('Централизованный газ', self._central_gas)
        self._refusechute = QtWidgets.QCheckBox()
        self._refusechute.setTristate(True)
        self._refusechute.setCheckState(_bool_to_checkstate(refusechute))
        self._options_layout.addRow('Наличие мусоропровода', self._refusechute)
        self._is_failing = QtWidgets.QCheckBox()
        self._is_failing.setTristate(True)
        self._is_failing.setCheckState(_bool_to_checkstate(is_failfing))
        self._options_layout.addRow('Аварийное состояние', self._is_failing)
        self._is_living = QtWidgets.QCheckBox()
        self._is_living.setTristate(True)
        self._is_living.setCheckState(_bool_to_checkstate(is_living))
        self._options_layout.addRow('Жилой дом', self._is_living)
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

    def osm_id(self) -> Optional[str]:
        return _str_or_none(self._osm_id.text())

    def get_geometry(self) -> Optional[str]:
        return _str_or_none(self._geometry_field.toPlainText())

    def address(self) -> Optional[str]:
        return _str_or_none(self._address.text())

    def building_date(self) -> Optional[str]:
        return _str_or_none(self._building_date.text())

    def repair_years(self) -> Optional[str]:
        return _str_or_none(self._repair_years.text())

    def building_area(self) -> Optional[float]:
        return _float_or_none(self._building_area.text())

    def building_area_living(self) -> Optional[float]:
        return _float_or_none(self._building_area_living.text())

    def storeys(self) -> Optional[int]:
        return _int_or_none(self._storeys.text())

    def lift_count(self) -> Optional[int]:
        return _int_or_none(self._lift_count.text())

    def population(self) -> Optional[int]:
        return _int_or_none(self._population.text())

    def project_type(self) -> Optional[str]:
        return _str_or_none(self._project_type.text())

    def ukname(self) -> Optional[str]:
        return _str_or_none(self._ukname.text())

    def central_heating(self) -> Optional[bool]:
        return _bool_or_none(self._central_heating.checkState())

    def central_hotwater(self) -> Optional[bool]:
        return _bool_or_none(self._central_hotwater.checkState())

    def central_electricity(self) -> Optional[bool]:
        return _bool_or_none(self._central_electricity.checkState())

    def central_gas(self) -> Optional[bool]:
        return _bool_or_none(self._central_gas.checkState())

    def refusechute(self) -> Optional[bool]:
        return _bool_or_none(self._refusechute.checkState())

    def is_failing(self) -> Optional[bool]:
        return _bool_or_none(self._is_failing.checkState())

    def is_living(self) -> Optional[bool]:
        return _bool_or_none(self._is_living.checkState())


class UpdatingWindow(QtWidgets.QWidget):

    EditButtons = NamedTuple('EditButtons', [
            ('load', QtWidgets.QPushButton),
            ('delete', QtWidgets.QPushButton),
            ('showGeometry', QtWidgets.QPushButton),
            ('addPhysicalObject', QtWidgets.QPushButton),
            ('updatePhysicalObject', QtWidgets.QPushButton),
            ('addBuilding', QtWidgets.QPushButton),
            ('updateBuilding', QtWidgets.QPushButton),
            ('export', QtWidgets.QPushButton),
            ('commit', QtWidgets.QPushButton),
            ('rollback', QtWidgets.QPushButton)
        ]
    )

    def __init__(self, db_properties: Properties, on_close: Optional[Callable[[], None]] = None, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)

        self._db_properties = db_properties
        self._additional_conn = db_properties.copy().conn
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

        left_placeholder = QtWidgets.QLabel('(Здесь будут отображены объекты)')
        left_placeholder.setMinimumSize(300, 300)
        left_placeholder.setAlignment(QtCore.Qt.AlignCenter)
        self._left.addWidget(left_placeholder)

        left_hlayout = QtWidgets.QHBoxLayout()
        self._left.addLayout(left_hlayout)
        self._left.setAlignment(QtCore.Qt.AlignCenter)
        self._table: QtWidgets.QTableWidget

        self._options_group_box = QtWidgets.QGroupBox('Опции выбора')
        self._options_group = QtWidgets.QFormLayout()
        self._city_choose = ColorizingComboBox(self._on_city_change)
        self._options_group.addRow('Город:', self._city_choose)
        self._right.addWidget(self._options_group_box)
        self._options_group_box.setLayout(self._options_group)
        self._service_type_choose = QtWidgets.QComboBox()
        self._options_group.addRow('Тип сервиса:', self._service_type_choose)

        self._editing_group_box = QtWidgets.QGroupBox('Изменение списка')
        self._editing_group = QtWidgets.QFormLayout()
        self._editing_group_box.setLayout(self._editing_group)
        self._edit_buttons = UpdatingWindow.EditButtons(QtWidgets.QPushButton('Отобразить сервисы'),
                QtWidgets.QPushButton('Удалить сервис'), QtWidgets.QPushButton('Посмотреть геометрию'),
                QtWidgets.QPushButton('Добавить физический объект'), QtWidgets.QPushButton('Изменить физический объект'),
                QtWidgets.QPushButton('Добавить здание'), QtWidgets.QPushButton('Изменить здание'),
                QtWidgets.QPushButton('Экспортировать таблицу'), QtWidgets.QPushButton('Сохранить изменения в БД'),
                QtWidgets.QPushButton('Отмена внесенных изменений')
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
        self._edit_buttons.commit.setStyleSheet('background-color: green; color: black')
        self._edit_buttons.rollback.clicked.connect(self._on_rollback)
        self._edit_buttons.rollback.setStyleSheet('background-color: red; color: black')
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

    def _on_city_change(self, _changed: Optional[QtWidgets.QComboBox] = None, _old_state: Optional[int] = None) -> None:
        with self._db_properties.conn.cursor() as cur:
            cur.execute('SELECT DISTINCT st.name FROM functional_objects f'
                    '   JOIN physical_objects p ON f.physical_object_id = p.id'
                    '   JOIN city_service_types st ON f.city_service_type_id = st.id'
                    ' WHERE p.city_id = (SELECT id FROM cities WHERE name = %s)'
                    ' ORDER BY 1', (self._city_choose.currentText(),))
            service_types = list(itertools.chain.from_iterable(cur.fetchall()))
        self._set_service_types(service_types)

    def _on_objects_load(self) -> None:
        self._log_window.clear()
        self._db_properties.conn.rollback()
        with self._db_properties.conn.cursor() as cur:
            cur.execute('SELECT is_building FROM city_service_types WHERE name = %s', (self._service_type_choose.currentText(),))
            is_building = cur.fetchone()[0] # type: ignore
            cur.execute('SELECT f.id as functional_object_id, b.address, f.name AS service_name, f.opening_hours, f.website, f.phone,'
                    '   f.capacity, f.is_capacity_real, p.id as physical_object_id, ST_Y(p.center), ST_X(p.center),'
                    '   ST_GeometryType(p.geometry), au.name as administrative_unit, m.name as municipality,'
                    "   date_trunc('second', f.created_at)::timestamp, date_trunc('second', f.updated_at)::timestamp"
                    ' FROM physical_objects p'
                    '   JOIN functional_objects f ON f.physical_object_id = p.id'
                    '   LEFT JOIN buildings b ON b.physical_object_id = p.id'
                    '   LEFT JOIN administrative_units au ON p.administrative_unit_id = au.id'
                    '   LEFT JOIN municipalities m ON p.municipality_id = m.id'
                    ' WHERE f.city_service_type_id = (SELECT id from city_service_types WHERE name = %s)'
                    '   AND p.city_id = (SELECT id FROM cities WHERE name = %s)'
                    ' ORDER BY 1',
                    (self._service_type_choose.currentText(), self._city_choose.currentText())
            )
            services_list = cur.fetchall()
        if '_table' not in dir(self):
            self._editing_group.addWidget(self._edit_buttons.load)
            self._editing_group.addWidget(self._edit_buttons.delete)
            self._editing_group.addWidget(self._edit_buttons.showGeometry)
            # self._editing_group.addWidget(self._edit_buttons.updateGeometry)
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
        self._table = PlatformServicesTableWidget(services_list, self._on_cell_change, self._db_properties, is_building)
        self._left.replaceWidget(left_placeholder, self._table)
        if not is_building:
            self._table.setColumnWidth(1, 20)
            self._edit_buttons.addBuilding.setVisible(False)
            self._edit_buttons.updateBuilding.setVisible(False)
            self._edit_buttons.addPhysicalObject.setVisible(True)
            self._edit_buttons.updatePhysicalObject.setVisible(True)
            self._editing_group.replaceWidget(self._edit_buttons.addBuilding, self._edit_buttons.addPhysicalObject)
            self._editing_group.replaceWidget(self._edit_buttons.updateBuilding, self._edit_buttons.updatePhysicalObject)
        else:
            self._table.setColumnWidth(1, 400)
            self._edit_buttons.addBuilding.setVisible(True)
            self._edit_buttons.updateBuilding.setVisible(True)
            self._edit_buttons.addPhysicalObject.setVisible(False)
            self._edit_buttons.updatePhysicalObject.setVisible(False)
            self._editing_group.replaceWidget(self._edit_buttons.addPhysicalObject, self._edit_buttons.addBuilding)
            self._editing_group.replaceWidget(self._edit_buttons.updatePhysicalObject, self._edit_buttons.updateBuilding)
        
        self._log_window.insertHtml(f'<font color=blue>Работа с городом "{self._city_choose.currentText()}"</font><br>')
        self._log_window.insertHtml(f'<font color=blue>Загружены {len(services_list)} сервисов типа "{self._service_type_choose.currentText()}"</font><br>')

    def _on_cell_change(self, row: int, column_name: str, old_value: Any, new_value: Any, is_valid: bool) -> None:
        func_id = self._table.item(row, 0).text()
        if is_valid:
            if column_name == 'Мощность' and self._table.item(row, PlatformServicesTableWidget.LABELS_DB.index('is_capacity_real')).text() == 'False':
                with self._db_properties.conn.cursor() as cur:
                    cur.execute('UPDATE functional_objects SET is_capacity_real = true WHERE id = %s', (func_id,))
                self._table.item(row, PlatformServicesTableWidget.LABELS_DB.index('is_capacity_real')).setText('true')
            self._log_window.insertHtml(f'<font color=yellowgreen>Изменен объект с func_id={func_id}. {column_name}:'
                    f' "{_to_str(old_value)}"->"{_to_str(new_value)}"</font><br>')
        else:
            self._log_window.insertHtml(f'<font color=#e6783c>Не изменен объект с func_id='
                    f'{func_id}. {column_name}: "{_to_str(old_value)}"->"{_to_str(new_value)}" (некорректное значение)</font><br>')
            return
        column = PlatformServicesTableWidget.LABELS.index(column_name)
        db_column = PlatformServicesTableWidget.LABELS_DB[column]
        with self._db_properties.conn.cursor() as cur:
            cur.execute(f"UPDATE functional_objects SET {db_column} = %s, updated_at = date_trunc('second', now()) WHERE id = %s",
                    (new_value, func_id))

    def _on_object_delete(self) -> None:
        rows = sorted(set(map(lambda index: index.row() + 1, self._table.selectedIndexes()))) # type: ignore
        if len(rows) == 0:
            return
        if len(rows) > 1:
            is_deleting = QtWidgets.QMessageBox.question(self, 'Удаление объектов',
                    f'Вы уверены, что хотите удалить объекты в строках под номерами: {", ".join(map(str, rows))}?')
        else:
            object_row = next(iter(rows))
            is_deleting = QtWidgets.QMessageBox.question(self, 'Удаление объекта', f'Вы уверены, что хотите удалить объект в строке под номером {object_row}?')
        if is_deleting == QtWidgets.QMessageBox.StandardButton.Yes:
            if len(rows) == 1:
                self._log_window.insertHtml('<font color=red>Удаление объекта с func_id=</font>')
            else:
                self._log_window.insertHtml('<font color=red>Удаление объектов с func_id=</font>')
            with self._db_properties.conn.cursor() as cur:
                for i, row in enumerate(rows[::-1]):
                    func_id = self._table.item(row - 1, 0).text()
                    self._log_window.insertHtml(f'<font color=red>{func_id}{", " if i != len(rows) - 1 else ""}</font>')
                    self._log_window.repaint()
                    cur.execute('DELETE FROM provision.houses_services WHERE house_id = %s OR service_id = %s', (func_id,) * 2)
                    cur.execute('DELETE FROM provision.services WHERE service_id = %s', (func_id,))
                    cur.execute('DELETE FROM provision.houses WHERE house_id = %s', (func_id,))
                    cur.execute('SELECT physical_object_id FROM functional_objects WHERE id = %s', (func_id,))
                    phys_id = cur.fetchone()[0] # type: ignore
                    cur.execute('DELETE FROM functional_objects WHERE id = %s', (func_id,))
                    cur.execute('SELECT count(*) FROM functional_objects WHERE physical_object_id = %s', (phys_id,))
                    phys_count = cur.fetchone()[0] # type: ignore
                    if phys_count == 0:
                        cur.execute('DELETE FROM buildings WHERE physical_object_id = %s', (phys_id,))
                        cur.execute('DELETE FROM physical_objects WHERE id = %s', (phys_id,))
                    self._table.removeRow(row - 1)
                self._log_window.insertHtml('</font><br>')

    def _on_geometry_show(self) -> None:
        with self._db_properties.conn.cursor() as cur:
            cur.execute('SELECT ST_AsGeoJSON(geometry, 6) FROM physical_objects WHERE id = %s', (self._table.item(self._table.currentRow(),
                    PlatformServicesTableWidget.LABELS_DB.index('physical_object_id')).text(),))
            res = cur.fetchone()
            if res is None:
                return
            geometry = json.loads(res[0])
        GeometryShow(json.dumps(geometry, indent=4)).exec()

    def _on_add_physical_object(self) -> None:
        row = self._table.currentRow()
        func_id, phys_id = self._table.item(row, 0).text(), self._table.item(row, 8).text()
        dialog = PhysicalObjectCreation(f'Введите информацию о физическом объекте для сервиса в строке {row + 1} в поля ниже', is_adding=True)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        try:
            newGeometry = json.loads(dialog.get_geometry()) # type: ignore
            with self._additional_conn.cursor() as cur:
                cur.execute('SELECT ST_AsGeoJSON(ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 6),'
                        ' ST_GeometryType(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))', (json.dumps(newGeometry),) * 2)
                new_center, geom_type = cur.fetchone() # type: ignore
                new_center = json.loads(new_center)
                new_longitude, new_latitude = new_center['coordinates']
        except Exception:
            self._additional_conn.rollback()
            self._log_window.insertHtml(f'<font color=#e6783c>Ошибка при добавлении физического объекта сервису с id={func_id}</font><br>')
        else:
            with self._db_properties.conn.cursor() as cur:
                cur.execute('INSERT INTO physical_objects (osm_id, geometry, center, city_id)'
                        ' VALUES (%s, ST_SnapToGrid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), 0.000001),'
                        '   ST_SnapToGrid(ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 0.000001), (SELECT id FROM cities WHERE name = %s))'
                        ' RETURNING id',
                        (dialog.osm_id(),) + (json.dumps(newGeometry),) * 2 + (self._city_choose.currentText(),)
                )
                new_phys_id = cur.fetchone()[0] # type: ignore
                cur.execute('UPDATE physical_objects SET'
                        ' administrative_unit_id = (SELECT id from administrative_units WHERE ST_CoveredBy('
                                ' (SELECT center FROM physical_objects WHERE id = %s), geometry) ORDER BY population DESC LIMIT 1),'
                        ' municipality_id = (SELECT id from municipalities WHERE ST_CoveredBy('
                                ' (SELECT center FROM physical_objects WHERE id = %s), geometry) ORDER BY population DESC LIMIT 1)'
                        ' WHERE id = %s',
                        (new_phys_id,) * 3
                )
                cur.execute("UPDATE functional_objects SET physical_object_id = %s, updated_at = date_trunc('second', now()) WHERE id = %s",
                        (new_phys_id, func_id))
            self._log_window.insertHtml(f'<font color=yellowgreen>Добавлен физический объект для сервиса с id={func_id}: {phys_id}->{new_phys_id}'
                    f' ({self._table.item(row, 11).text()}({self._table.item(row, 9).text()}, {self._table.item(row, 10).text()})'
                    f'->{geom_type}({new_latitude, new_longitude}))</font><br>')
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
            cur.execute('SELECT ST_AsGeoJSON(geometry), osm_id FROM physical_objects WHERE id = %s', (phys_id,))
            geometry, osm_id = cur.fetchone() # type: ignore
        geometry = json.loads(geometry)
        dialog = PhysicalObjectCreation(f'Если необходимо, измените параметры физического объекта для сервиса на строке {row + 1}',
                json.dumps(geometry, indent=2), osm_id)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        new_geom_tuple = check_geometry_correctness(dialog.get_geometry(), self._additional_conn)
        if new_geom_tuple is None:
            self._log_window.insertHtml(f'<font color=#e6783c>Физический объект для сервиса с id={func_id}'
                    f' (phys_id)={phys_id}) не обновлен, ошибка в геометрии</font><br>')
            return
        new_geometry = json.loads(dialog.get_geometry()) # type: ignore
        if geometry != new_geometry:
            new_latitude, new_longitude, geom_type = new_geom_tuple
            with self._db_properties.conn.cursor() as cur:
                cur.execute('UPDATE physical_objects SET geometry = ST_SnapToGrid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), 0.000001),'
                        ' center = ST_SnapToGrid(ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 0.000001),'
                        " updated_at = date_trunc('second', now()) WHERE id = %s",
                        (dialog.get_geometry(),) * 2 + (phys_id,))
                cur.execute('UPDATE physical_objects SET'
                    ' administrative_unit_id = (SELECT id from administrative_units WHERE ST_CoveredBy('
                            ' (SELECT center FROM physical_objects WHERE id = %s), geometry) ORDER BY population DESC LIMIT 1),'
                    ' municipality_id = (SELECT id from municipalities WHERE ST_CoveredBy('
                            ' (SELECT center FROM physical_objects WHERE id = %s), geometry) ORDER BY population DESC LIMIT 1)'
                    ' WHERE id = %s',
                    (phys_id,) * 3
            )
            self._log_window.insertHtml(f'<font color=yellowgreen>Геометрия физического объекта сервиса с id={func_id} (phys_id={phys_id}) изменена:'
                    f' {self._table.item(row, 11).text()}({self._table.item(row, 9).text()}, {self._table.item(row, 10).text()})'
                    f'->{geom_type}({new_latitude, new_longitude})</font><br>')
            self._table.item(row, 9).setText(str(new_latitude))
            self._table.item(row, 9).setBackground(QtCore.Qt.GlobalColor.yellow)
            self._table.item(row, 10).setText(str(new_longitude))
            self._table.item(row, 10).setBackground(QtCore.Qt.GlobalColor.yellow)
            self._table.item(row, 11).setText(geom_type)
            self._table.item(row, 11).setBackground(QtCore.Qt.GlobalColor.yellow)
        if osm_id != dialog.osm_id():
            with self._db_properties.conn.cursor() as cur:
                cur.execute("UPDATE physical_objects SET osm_id = %s, updated_at = date_trunc('second', now()) WHERE id = %s", (osm_id, phys_id))
            self._log_window.insertHtml(f'<font color=yellowgreen>OpenStreetMapID для phys_id={phys_id} изменен: {osm_id}->{dialog.osm_id()}</font><br>')

    def _on_add_building(self) -> None:
        row = self._table.currentRow()
        func_id = self._table.item(row, 0).text()
        dialog = BuildingCreation(f'Введите информацию о здании для добавления для сервиса на строке {row + 1} в поля ниже', is_adding=True)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        osm_id, address, building_date, building_area, repair_years, building_area_living, storeys, lift_count, population, project_type, ukname = \
                dialog.osm_id(), dialog.address(), dialog.building_date(), dialog.repair_years(), dialog.building_area(), \
                dialog.building_area_living(), dialog.storeys(), dialog.lift_count(), dialog.population(), dialog.project_type(), dialog.ukname()
        heating, hotwater, electricity, gas, refusechute, is_failing, is_living = dialog.central_heating(), dialog.central_hotwater(), dialog.central_electricity(), \
                dialog.central_gas(), dialog.refusechute(), dialog.is_failing(), dialog.is_living()
        res = check_geometry_correctness(dialog.get_geometry(), self._additional_conn)
        if res is None or address is None:
            self._log_window.insertHtml(f'<font color=#e6783c>Ошибка при добавлении здания сервису с id={func_id}</font><br>')
            return
        new_latitude, new_longitude, geom_type = res
        with self._db_properties.conn.cursor() as cur:
            cur.execute('INSERT INTO physical_objects (osm_id, geometry, center, city_id)'
                    ' VALUES (%s, ST_SnapToGrid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), 0.000001),'
                    '   ST_SnapToGrid(ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 0.000001), (SELECT id FROM cities WHERE name = %s))'
                    ' RETURNING id',
                    (osm_id,) + (dialog.get_geometry(),) * 2 + (self._city_choose.currentText(),)
            )
            new_phys_id = cur.fetchone()[0] # type: ignore
            cur.execute('UPDATE physical_objects SET'
                    ' administrative_unit_id = (SELECT id from administrative_units WHERE ST_CoveredBy('
                            ' (SELECT center FROM physical_objects WHERE id = %s), geometry) ORDER BY population DESC LIMIT 1),'
                    ' municipality_id = (SELECT id from municipalities WHERE ST_CoveredBy('
                            ' (SELECT center FROM physical_objects WHERE id = %s), geometry) ORDER BY population DESC LIMIT 1)'
                    ' WHERE id = %s',
                    (new_phys_id,) * 3
            )
            cur.execute('INSERT INTO buildings (physical_object_id, address, building_date, repair_years, building_area, living_area,'
                    ' storeys_count, lift_count, resident_number, project_type, ukname, central_heating, central_hotwater, central_electro,'
                    ' central_gas, refusechute, failure, is_living) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
                    (new_phys_id, address, building_date, repair_years, building_area, building_area_living, storeys, lift_count, population,
                        project_type, ukname, heating, hotwater, electricity, gas, refusechute, is_failing, is_living))
            cur.execute('UPDATE functional_objects SET physical_object_id = %s WHERE id = %s', (new_phys_id, func_id))
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

    def _on_update_building(self) -> None:
        row = self._table.currentRow()
        func_id, phys_id = self._table.item(row, 0).text(), self._table.item(row, 8).text()
        with self._db_properties.conn.cursor() as cur:
            cur.execute('SELECT ST_AsGeoJSON(p.geometry), p.osm_id, b.address, b.building_date, b.repair_years, b.building_area, b.living_area,'
                    ' b.storeys_count, b.lift_count, b.resident_number, b.project_type, b.ukname, b.central_heating, b.central_hotwater,'
                    ' b.central_electro, b.central_gas, b.refusechute, b.failure, b.is_living, b.id FROM buildings b'
                    ' JOIN physical_objects p ON b.physical_object_id = p.id'
                    ' WHERE p.id = %s', (phys_id,))
            try:
                geometry, *res, b_id = cur.fetchone() # type: ignore
            except TypeError:
                QtWidgets.QMessageBox.critical(self, 'Ошибка изменения здания', 'Здание, соответствующее физическому объекту'
                        f' с id={phys_id} не найдено в базе данных')
                return
        geometry = json.loads(geometry)
        dialog = BuildingCreation(f'Если необходимо, измените параметры здания для сервиса на строке {row + 1}', json.dumps(geometry, indent=2), *res)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        new_geom_tuple = check_geometry_correctness(dialog.get_geometry(), self._additional_conn)
        if new_geom_tuple is None:
            self._log_window.insertHtml(f'<font color=#e6783c>Здание для сервиса с id={func_id}'
                    f' (build_id={b_id}) не обновлено, ошибка в геометрии</font><br>')
            return
        if dialog.address() is None:
            self._log_window.insertHtml(f'<font color=#e6783c>Здание для сервиса с id={func_id}'
                    f' (build_id={b_id}) не обновлено, адрес не задан</font><br>')
            return
        new_geometry = json.loads(dialog.get_geometry()) # type: ignore
        if geometry != new_geometry:
            new_latitude, new_longitude, geom_type = new_geom_tuple
            with self._db_properties.conn.cursor() as cur:
                cur.execute('UPDATE physical_objects SET geometry = ST_SnapToGrid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), 0.000001),'
                        ' center = ST_SnapToGrid(ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 0.000001),'
                        " updated_at = date_trunc('second', now()) WHERE id = %s",
                        (dialog.get_geometry(),) * 2 + (phys_id,))
                cur.execute('UPDATE physical_objects SET'
                    ' administrative_unit_id = (SELECT id from administrative_units WHERE ST_CoveredBy('
                            ' (SELECT center FROM physical_objects WHERE id = %s), geometry) ORDER BY population DESC LIMIT 1),'
                    ' municipality_id = (SELECT id from municipalities WHERE ST_CoveredBy('
                            ' (SELECT center FROM physical_objects WHERE id = %s), geometry) ORDER BY population DESC LIMIT 1)'
                    ' WHERE id = %s',
                    (phys_id,) * 3
            )
            self._log_window.insertHtml(f'<font color=yellowgreen>Геометрия сервиса с id={func_id} (phys_id={phys_id}) изменена:'
                    f' {self._table.item(row, 11).text()}({self._table.item(row, 9).text()}, {self._table.item(row, 10).text()})'
                    f'->{geom_type}({new_latitude, new_longitude})</font><br>')
            self._table.item(row, 9).setText(str(new_latitude))
            self._table.item(row, 10).setText(str(new_longitude))
            self._table.item(row, 11).setText(geom_type)
            for c in (9, 10, 11):
                self._table.item(row, c).setBackground(QtCore.Qt.GlobalColor.yellow)
        if res[0] != dialog.osm_id():
            with self._db_properties.conn.cursor() as cur:
                cur.execute("UPDATE physical_objects SET osm_id = %s, updated_at = date_trunc('second', now()) WHERE id = %s", (res[0], phys_id))
            self._log_window.insertHtml(f'<font color=yellowgreen>Изменен параметр OpenStreetMapID для phys_id={phys_id}:'
                    f' "{res[0]}"->"{dialog.osm_id()}"</font><br>')
        with self._db_properties.conn.cursor() as cur:
            if res[1] != dialog.address():
                self._table.item(row, 1).setText(dialog.address()) # type: ignore
                self._table.item(row, 1).setBackground(QtCore.Qt.GlobalColor.yellow)
            for name_interface, column, old_value, new_value in zip(
                ('адрес', 'дата постройки', 'годы ремонта', 'площадь здания', 'жилая площадь', 'этажность', 'количество лифтов',
                        'население', 'тип проекта', 'название застройщика', 'централизованное отопление', 'централизованная горячая вода',
                        'централизованное электричество', 'централизованный газ', 'мусоропровод', 'аварийность', 'жилой'),
                ('address', 'building_date', 'repair_years', 'building_area', 'living_area', 'storeys_count', 'lift_count', 'resident_number',
                        'project_type', 'ukname', 'central_heating', 'central_hotwater', 'central_electro', 'central_gas', 'refusechute', 'failure', 'is_living'),
                res[1:],
                (dialog.address(), dialog.building_date(), dialog.repair_years(), dialog.building_area(), dialog.building_area_living(),
                        dialog.storeys(), dialog.lift_count(), dialog.population(), dialog.project_type(), dialog.ukname(), dialog.central_heating(),
                        dialog.central_hotwater(), dialog.central_electricity(), dialog.central_gas(), dialog.refusechute(), dialog.is_failing(), dialog.is_living())
            ):
                    if old_value != new_value:
                        self._log_window.insertHtml(f'<font color=yellowgreen>Изменен параметр дома ({name_interface}) для build_id={b_id} (phys_id={phys_id}):'
                                f' "{_to_str(old_value)}"->"{_to_str(new_value)}"</font><br>')
                    cur.execute(f'UPDATE buildings SET {column} = %s WHERE id = %s', (new_value, b_id))

    def _on_export(self) -> None:
        lines: List[List[Any]] = []
        for row in range(self._table.rowCount()):
            lines.append([self._table.item(row, col).text() for col in range(self._table.columnCount())])
        df = pd.DataFrame(lines, columns=[self._table.horizontalHeaderItem(i).text() for i in range(self._table.columnCount())])

        fileDialog = QtWidgets.QFileDialog(self)
        fileDialog.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        fileDialog.setNameFilters(('Modern Excel files (*.xlsx)', 'Excel files (*.xls)', 'OpedDocumentTable files (*.ods)', 'CSV files (*.csv)'))
        t = time.localtime()
        filename: str = f'{self._service_type_choose.currentText()} {t.tm_year}-{t.tm_mon:02}-{t.tm_mday:02} ' \
                f'{t.tm_hour:02}-{t.tm_min:02}-{t.tm_sec:02}.csv'
        fileDialog.selectNameFilter('CSV files (*.csv)')
        fileDialog.selectFile(filename)
        if fileDialog.exec() != QtWidgets.QDialog.Accepted:
            return
        filename = fileDialog.selectedFiles()[0]
        format = fileDialog.selectedNameFilter()[fileDialog.selectedNameFilter().rfind('.'):-1]
        if not filename.endswith(format):
            filename += format
        save_func = pd.DataFrame.to_csv if filename.endswith('csv') else pd.DataFrame.to_excel
        save_func(df, filename, index=False)

    def _on_commit_changes(self) -> None:
        self._log_window.insertHtml('<font color=green>Запись изменений в базу данных</font><br>')
        logger.opt(colors=True).info(f'<green>Коммит следующих изменений сервисов в базу данных</green>:\n{self._log_window.toPlainText()[:-1]}')
        self._db_properties.conn.commit()
        self._edit_buttons.load.click()
        self._log_window.insertHtml('<font color=green>Изменения записаны, обновленная информация загружена</font><br>')

    def _on_rollback(self) -> None:
        self._db_properties.conn.rollback()
        self._edit_buttons.load.click()

    def _set_service_types(self, service_types: Iterable[str]) -> None:
        service_types = list(service_types)
        current_service_type = self._service_type_choose.currentText()
        self._service_type_choose.clear()
        if len(service_types) == 0:
            self._service_type_choose.addItem('(Нет типов сервисов)')
            self._service_type_choose.view().setMinimumWidth(len(self._service_type_choose.currentText()) * 8)
            self._edit_buttons.load.setEnabled(False)
        else:
            self._service_type_choose.addItems(service_types)
            if current_service_type in service_types:
                self._service_type_choose.setCurrentText(current_service_type)
            self._service_type_choose.view().setMinimumWidth(len(max(service_types, key=len)) * 8)
            self._edit_buttons.load.setEnabled(True)

    def set_cities(self, cities: Iterable[str]) -> None:
        cities = list(cities)
        current_city = self._city_choose.currentText()
        self._city_choose.clear()
        if len(cities) == 0:
            self._city_choose.addItem('(Нет городов)')
        else:
            self._city_choose.addItems(cities)
            if current_city in cities:
                self._city_choose.setCurrentText(current_city)
            else:
                self._on_city_change()
            self._city_choose.view().setMinimumWidth(len(max(cities, key=len)) * 8)

    def change_db(self, db_addr: str, db_port: int, db_name: str, db_user: str, db_pass: str) -> None:
        self._db_properties.reopen(db_addr, db_port, db_name, db_user, db_pass)
        if self._additional_conn is not None and not self._additional_conn.closed:
            self._additional_conn.close()
        self._additional_conn = self._db_properties.copy().conn
        self._on_city_change()
    
    def showEvent(self, event: QtGui.QShowEvent) -> None:
        logger.info('Открыто окно изменения сервисов')
        return super().showEvent(event)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        logger.info('Закрыто окно изменения сервисов')
        if self._on_close is not None:
            self._on_close()
        return super().closeEvent(event)
