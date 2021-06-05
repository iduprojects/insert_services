from PySide6 import QtCore, QtWidgets, QtGui
from typing import Any, Callable, Optional, NamedTuple, List, Tuple, Dict, Union
import os, time, traceback, itertools
import json
import pandas as pd
import psycopg2

from database_properties import Properties
import adding_functional_objects

class ColorizingLine(QtWidgets.QLineEdit):
    def __init__(self, callback: Callable[[Optional[QtWidgets.QLineEdit], Optional[str]], None], text: Optional[str] = None, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._state: str = text or ''
        self.setText(text or '')
        self._callback = callback
    
    def focusInEvent(self, event: QtGui.QFocusEvent) -> None:
        self._state = self.text()
        return super().focusInEvent(event)

    def focusOutEvent(self, event: QtGui.QFocusEvent) -> None:
        if self.text() != self._state:
            if self.isVisible():
                self._callback(self, self._state)
            self._state = self.text()
        return super().focusOutEvent(event)


class ColorizingComboBox(QtWidgets.QComboBox):
    def __init__(self, callback: Callable[[Optional[QtWidgets.QComboBox]], None], parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._callback = callback
        self._state = 0
        self.currentIndexChanged.connect(lambda: callback(self))

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        super().wheelEvent(event)
        if self.currentIndex() != self._state:
            if self.isVisible():
                self._callback(self)
            self._state = self.currentIndex()


class CheckableTableView(QtWidgets.QTableView):

    colorTable = NamedTuple('ColorTable', [
            ('on', QtGui.QColor),
            ('off', QtGui.QColor)
    ])(QtGui.QColor(152, 224, 173), QtGui.QColor(248, 161, 164)) # type: ignore
    
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        if self.columnAt(int(event.position().x())) == 0:
            row = self.rowAt(int(event.position().y()))
            item_index = self.model().index(row, 0)
            item = self.model().data(item_index)
            self.model().setData(item_index, '-' if item == '+' else '+')
            self.model().setData(item_index, CheckableTableView.colorTable.off if item == '+' else CheckableTableView.colorTable.on,
                    QtCore.Qt.BackgroundRole)
        else:
            return super().mouseDoubleClickEvent(event)

    def is_turned_on(self, row: int) -> bool:
        return self.model().itemData(self.model().index(row, 0)) == '+'


class DropPushButton(QtWidgets.QPushButton):
    def __init__(self, text: str, formats: List[str], callback: Callable[[str], None], parent: Optional[QtWidgets.QWidget] = None):
        self.formats = tuple((f'.{format}' for format in formats))
        self._callback = callback
        super().__init__(text, parent=parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        if event.mimeData().text().startswith('file:///') and event.mimeData().text().endswith(self.formats):
            event.setDropAction(QtCore.Qt.LinkAction)
            event.accept()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        self._callback(event.mimeData().text()[len('file:///'):])


MainWindowDefaultValues = NamedTuple('MainWindowDefaultValues', [
        ('db_address', str),
        ('db_port', int),
        ('db_name', str),
        ('db_user', str),
        ('db_pass', str),
        ('object_class', str),
        ('service_type', str),
        ('service_code', str),
        ('city_function', str),
        ('min_capacity', str),
        ('max_capacity', str),
        ('override_amenity', str),
        ('latitude', str),
        ('longitude', str),
        ('address', str),
        ('amenity', str),
        ('name', str),
        ('opening_hours', str),
        ('website', str),
        ('phone', str),
        ('osm_id', str),
    ]
)

def get_main_window_default_values() -> MainWindowDefaultValues:
    return MainWindowDefaultValues('127.0.0.1', 5432, 'citydb', 'postgres', 'postgres', '', '', '', '', '', '', '', 'x', 'y',
            'yand_adr', 'amenity', 'name', 'opening_hours', 'contact:website', 'contact:phone', 'id')

def get_main_window_default_address_prefixes() -> List[str]:
    return ['Россия, Санкт-Петербург']

def get_default_city_functions() -> List[str]:
    return ['(Не выбрано, необходимо соединение с базой)']

def get_default_object_classes() -> List[str]:
    return ['(Не выбрано, необходимо соединение с базой)']

def get_default_service_types() -> List[str]:
    return ['(Не выбрано, необходимо соединение с базой)']

    
class MainWindow(QtWidgets.QWidget):

    DatabaseFields = NamedTuple('DatabaseFields', [
            ('address', QtWidgets.QLineEdit),
            ('name', QtWidgets.QLineEdit),
            ('user', QtWidgets.QLineEdit),
            ('password', QtWidgets.QLineEdit)
        ]
    )

    InsertionOptionsFields = NamedTuple('InsertionOptionsFields', [
            ('object_class', QtWidgets.QLineEdit),
            ('service_type', QtWidgets.QLineEdit),
            ('service_code', QtWidgets.QLineEdit),
            ('min_capacity', QtWidgets.QLineEdit),
            ('max_capacity', QtWidgets.QLineEdit),
            ('override_amenity', QtWidgets.QLineEdit),
            ('city_function', QtWidgets.QComboBox),
            ('object_class_choose', QtWidgets.QComboBox),
            ('service_type_choose', QtWidgets.QComboBox),
            ('object_class_choosable', QtWidgets.QCheckBox),
            ('service_type_choosable', QtWidgets.QCheckBox)
        ]
    )

    DocumentFields = NamedTuple('DocumentFields', [
            ('latitude', QtWidgets.QLineEdit),
            ('longitude', QtWidgets.QLineEdit),
            ('address', QtWidgets.QLineEdit),
            ('amenity', QtWidgets.QLineEdit),
            ('name', QtWidgets.QLineEdit),
            ('opening_hours', QtWidgets.QLineEdit),
            ('website', QtWidgets.QLineEdit),
            ('phone', QtWidgets.QLineEdit),
            ('osm_id', QtWidgets.QLineEdit)
        ]
    )

    colorTable = NamedTuple('ColorTable', [
            ('light_green', QtGui.QColor),
            ('light_red', QtGui.QColor),
            ('dark_green', QtGui.QColor),
            ('dark_red', QtGui.QColor),
            ('grey', QtGui.QColor),
            ('sky_blue', QtGui.QColor)
    ])(QtGui.QColor(200, 239, 212), QtGui.QColor(255, 192, 203), QtGui.QColor(97, 204, 128), \
            QtGui.QColor(243, 104, 109), QtGui.QColor(230, 230, 230), QtGui.QColor(148, 216, 246)) # type: ignore

    default_values = get_main_window_default_values()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        self._db_properties = Properties(MainWindow.default_values.db_address, MainWindow.default_values.db_port,
                MainWindow.default_values.db_name, MainWindow.default_values.db_user, MainWindow.default_values.db_pass)
        super().__init__(parent)

        self._additionals_cnt = 0
        self._is_options_ok = False
        self._is_document_ok = False

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

        self._open_file_btn = DropPushButton('Открыть файл', ['xlsx', 'xls', 'json', 'geojson', 'ods', 'csv'], self.on_open_file)
        self._open_file_btn.clicked.connect(self.on_open_file)
        self._load_objects_btn = QtWidgets.QPushButton('Загрузить сервисы')
        self._load_objects_btn.setStyleSheet('font-weight: bold')
        self._load_objects_btn.clicked.connect(self.on_load_objects)
        self._load_objects_btn.setVisible(False)
        self._save_results_btn = QtWidgets.QPushButton('Сохранить результаты')
        self._save_results_btn.setStyleSheet('font-weight: bold')
        self._save_results_btn.clicked.connect(self.on_save_results)
        self._save_results_btn.setVisible(False)
        left_hlayout = QtWidgets.QHBoxLayout()
        left_hlayout.addWidget(self._open_file_btn)
        left_hlayout.addWidget(self._load_objects_btn)
        left_hlayout.addWidget(self._save_results_btn)
        self._left.addLayout(left_hlayout)
        self._left.setAlignment(QtCore.Qt.AlignCenter)
        self._table: Optional[QtWidgets.QTableView] = None

        self._db_group_box = QtWidgets.QGroupBox('База данных')
        self._db_group = QtWidgets.QFormLayout()
        self._db_group_box.setLayout(self._db_group)
        self._database_fields = MainWindow.DatabaseFields(*(QtWidgets.QLineEdit() for _ in range(4)))
        self._database_fields.password.setEchoMode(QtWidgets.QLineEdit.Password)
        self._db_group.addRow('Адрес:', self._database_fields.address)
        self._db_group.addRow('База:', self._database_fields.name)
        self._db_group.addRow('Пользователь:', self._database_fields.user)
        self._db_group.addRow('Пароль:', self._database_fields.password)
        self._db_check_btn = QtWidgets.QPushButton('Проверить подключение')
        self._db_check_btn.clicked.connect(self.on_connection_check)
        self._db_check_res = QtWidgets.QLabel('?')
        self._db_group.addRow(self._db_check_btn, self._db_check_res)
        self._right.addWidget(self._db_group_box)

        self._options_group_box = QtWidgets.QGroupBox('Опции вставки')
        self._options_group = QtWidgets.QFormLayout()
        self._options_group_box.setLayout(self._options_group)
        self._options_fields = MainWindow.InsertionOptionsFields(
                ColorizingLine(self.on_options_change),
                ColorizingLine(self.on_options_change),
                ColorizingLine(self.on_options_change),
                ColorizingLine(self.on_options_change),
                ColorizingLine(self.on_options_change),
                ColorizingLine(self.on_document_change),
                ColorizingComboBox(self.on_options_change),
                ColorizingComboBox(self.on_options_change),
                ColorizingComboBox(self.on_options_change),
                QtWidgets.QCheckBox(),
                QtWidgets.QCheckBox()                
        )
        self._options_fields.object_class_choosable.clicked.connect(lambda: self.on_choose_change(self._options_fields.object_class_choosable))
        self._options_fields.service_type_choosable.clicked.connect(lambda: self.on_choose_change(self._options_fields.service_type_choosable))
        self._options_fields.object_class_choose.addItems(get_default_object_classes())
        self._options_fields.service_type_choose.addItems(get_default_service_types())
        self._options_fields.object_class_choose.view().setMinimumWidth(len(max(get_default_object_classes(), key=len)) * 8)
        self._options_fields.service_type_choose.view().setMinimumWidth(len(max(get_default_service_types(), key=len)) * 8)

        self._options_group.addRow('Класс сервиса:', self._options_fields.object_class)
        self._options_group.addRow('Выбрать класс:', self._options_fields.object_class_choosable)
        self._options_group.addRow('Тип сервиса:', self._options_fields.service_type)
        self._options_group.addRow('Выбрать сервис:', self._options_fields.service_type_choosable)
        self._options_group.addRow('Код сервиса:', self._options_fields.service_code)
        self._options_group.addRow('Городская функция:', self._options_fields.city_function)
        self._options_group.addRow('Минимальная мощность:', self._options_fields.min_capacity)
        self._options_group.addRow('Максимальная мощность:', self._options_fields.max_capacity)
        self._options_group.addRow('Задать тип объекта:', self._options_fields.override_amenity)
        self._right.addWidget(self._options_group_box)

        self._document_group_box = QtWidgets.QGroupBox('Сопоставление документа')
        self._document_group = QtWidgets.QFormLayout()
        self._document_group_box.setLayout(self._document_group)
        self._document_fields = MainWindow.DocumentFields(*(ColorizingLine(self.on_document_change) for _ in range(9)))
        self._document_address_prefixes = [QtWidgets.QLineEdit() for _ in range(len(get_main_window_default_address_prefixes()))]
        self._document_group.addRow('Широта:', self._document_fields.latitude)
        self._document_group.addRow('Долгота:', self._document_fields.longitude)
        self._document_group.addRow('Адрес:', self._document_fields.address)
        self._document_group.addRow('Внутренний тип:', self._document_fields.amenity)
        self._document_group.addRow('Название:', self._document_fields.name)
        self._document_group.addRow('Рабочие часы:', self._document_fields.opening_hours)
        self._document_group.addRow('Веб-сайт:', self._document_fields.website)
        self._document_group.addRow('Телефон:', self._document_fields.phone)
        self._document_group.addRow('OSM id:', self._document_fields.osm_id)
        self._right.addWidget(self._document_group_box)

        self._additionals_group_box = QtWidgets.QGroupBox('Дополнительные поля')
        self._additionals_group = QtWidgets.QGridLayout()
        self._additionals_group_box.setLayout(self._additionals_group)
        self._additional_add_btn = QtWidgets.QPushButton('Добавить')
        self._additional_add_btn.clicked.connect(self.on_additional_add)
        self._additional_delete_btn = QtWidgets.QPushButton('Удалить')
        self._additional_delete_btn.clicked.connect(self.on_additional_delete)
        self._additional_delete_btn.setEnabled(False)
        self._additionals_group.addWidget(self._additional_add_btn, 0, 0)
        self._additionals_group.addWidget(self._additional_delete_btn, 0, 1, 1, 2)
        self._additionals_group.addWidget(QtWidgets.QLabel('В базе'), 1, 0)
        self._additionals_group.addWidget(QtWidgets.QLabel('Тип данных'), 1, 1)
        self._additionals_group.addWidget(QtWidgets.QLabel('В документе'), 1, 2)
        for i in range(3):
            self._additionals_group.itemAtPosition(1, i).widget().setVisible(False)
            self._additionals_group.itemAtPosition(1, i).widget().setAlignment(QtCore.Qt.AlignCenter)
            self._additionals_group.itemAtPosition(1, i).widget().setStyleSheet('font-weight: bold;')
        self._right.addWidget(self._additionals_group_box)

        self._prefixes_group_box = QtWidgets.QGroupBox('Префиксы адреса')
        self._prefixes_group = QtWidgets.QVBoxLayout()
        self._prefixes_group_box.setLayout(self._prefixes_group)
        for prefix in self._document_address_prefixes:
            self._prefixes_group.addWidget(prefix)
        self._address_prefix_add_btn = QtWidgets.QPushButton('Добавить префикс')
        self._address_prefix_add_btn.clicked.connect(self.on_prefix_add)
        self._address_prefix_remove_btn = QtWidgets.QPushButton('Удалить префикс')
        self._address_prefix_remove_btn.clicked.connect(self.on_prefix_remove)
        self._address_prefix_remove_btn.setEnabled(False)
        self._address_prefix_check_btn = QtWidgets.QPushButton('Проверить префиксы')
        self._address_prefix_check_btn.clicked.connect(self.on_prefix_check)
        self._address_prefix_check_btn.setEnabled(False)
        self._prefixes_group.addWidget(self._address_prefix_add_btn)
        self._prefixes_group.addWidget(self._address_prefix_remove_btn)
        self._prefixes_group.addWidget(self._address_prefix_check_btn)
        self._right.addWidget(self._prefixes_group_box)
        
        self._types_group_box = QtWidgets.QGroupBox('Внутренние типы сервисов')
        self._types_group = QtWidgets.QVBoxLayout()
        self._types_group_box.setLayout(self._types_group)
        self._types_open_btn = QtWidgets.QPushButton('Открыть окно типов')
        self._types_open_btn.clicked.connect(self.on_types_open)
        self._types_check_btn = QtWidgets.QPushButton('Проверить соответствие типов')
        self._types_check_btn.setEnabled(False)
        self._types_check_btn.clicked.connect(self.on_types_check)
        self._types_group.addWidget(self._types_open_btn)
        self._types_group.addWidget(self._types_check_btn)
        self._right.addWidget(self._types_group_box)

        types: Optional[Dict[str, Tuple[str, str]]]
        if os.path.isfile('types.json'):
            with open('types.json', 'rt', encoding='utf-8') as f:
                types = json.load(f)
            types = dict(map(lambda x: (x[0].lower(), x[1]), types.items())) # type: ignore
        else:
            types = None

        self._types_window = TypesWindow(types)
        self._types_window.resize(self._types_window.sizeHint().width(), self._types_window.sizeHint().height() * 2)
        self._types_window.setHidden(True)

        self._right.setAlignment(QtCore.Qt.AlignTop)
        right_width = max(map(lambda box: box.sizeHint().width(), (self._db_group_box, self._options_group_box,
                self._document_group_box, self._prefixes_group_box, self._types_group_box, self._additionals_group_box)))
        
        self._right_scroll.setFixedWidth(int(right_width * 1.15))
        self._db_group_box.setFixedWidth(right_width)
        self._options_group_box.setFixedWidth(right_width)
        self._document_group_box.setFixedWidth(right_width)
        self._prefixes_group_box.setFixedWidth(right_width)
        self._types_group_box.setFixedWidth(right_width)
        self._additionals_group_box.setFixedWidth(right_width)

        self._database_fields.address.setText(f'{MainWindow.default_values.db_address}:{MainWindow.default_values.db_port}')
        self._database_fields.name.setText(MainWindow.default_values.db_name)
        self._database_fields.user.setText(MainWindow.default_values.db_user)
        self._database_fields.password.setText(MainWindow.default_values.db_pass)
        
        self._options_fields.object_class.setText(MainWindow.default_values.object_class)
        self._options_fields.service_type.setText(MainWindow.default_values.service_type)
        self._options_fields.service_code.setText(MainWindow.default_values.service_code)
        self._options_fields.city_function.addItems(get_default_city_functions())
        self._options_fields.city_function.view().setMinimumWidth(len(max(get_default_city_functions(), key=len)) * 8)
        self._options_fields.min_capacity.setText(MainWindow.default_values.min_capacity)
        self._options_fields.max_capacity.setText(MainWindow.default_values.max_capacity)
        self._options_fields.override_amenity.setText(MainWindow.default_values.override_amenity)

        self._document_fields.latitude.setText(MainWindow.default_values.latitude)
        self._document_fields.longitude.setText(MainWindow.default_values.longitude)
        self._document_fields.address.setText(MainWindow.default_values.address)
        self._document_fields.amenity.setText(MainWindow.default_values.amenity)
        self._document_fields.name.setText(MainWindow.default_values.name)
        self._document_fields.opening_hours.setText(MainWindow.default_values.opening_hours)
        self._document_fields.website.setText(MainWindow.default_values.website)
        self._document_fields.phone.setText(MainWindow.default_values.phone)
        self._document_fields.osm_id.setText(MainWindow.default_values.osm_id)
        for line, prefix_line in zip(self._document_address_prefixes, get_main_window_default_address_prefixes()):
            line.setText(prefix_line)
            line.setMinimumWidth(250)

        self._service_type_params: Dict[str, Tuple[str, Optional[int], Optional[int]]] = {}
        
        self.on_options_change()

    def on_open_file(self, filepath: Optional[str] = None) -> None:
        if not filepath:
            try:
                fileDialog = QtWidgets.QFileDialog(self)
                fileDialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)
                fileDialog.setNameFilters(('All files (*.xlsx *.xls *.json *.geojson *.ods *.csv)', 'Modern Excel files (*.xlsx)',
                        'Excel files (*.xls *.ods)', 'GeoJSON files (*.json *.geojson)', 'CSV files (*.csv)'))
                if fileDialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
                    return
                filename = fileDialog.selectedFiles()[0]
            except ValueError:
                QtWidgets.QMessageBox.critical(self, 'Невозможно открыть файл', 'Ошибка при открытии файла')
                return
            except Exception as ex:
                QtWidgets.QMessageBox.critical(self, 'Невозможно открыть файл', f'Неизвестная ошибка при открытии: {ex}')
                return
        else:
            filename = filepath

        df = adding_functional_objects.load_objects(filename)
        self.setWindowTitle(f'Загрузка объектов - "{filename[filename.rindex("/") + 1:]}"')

        self._table_axes: List[str] = ['Загрузить'] + list(df.axes[1])
        self._table_model = QtGui.QStandardItemModel(*df.shape)
        self._table_model.setHorizontalHeaderLabels(list(self._table_axes))
        for i, service in df.iterrows():
            for j, data in enumerate(service, 1):
                self._table_model.setItem(i, j, QtGui.QStandardItem(str(data or '')))
            ok_item = QtGui.QStandardItem('+')
            ok_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self._table_model.setItem(i, 0, ok_item)
            self._table_model.setData(self._table_model.index(i, 0), CheckableTableView.colorTable.on, 8) # 8 <- QtCore.Qt.BackgroundRole

        if self._table is None:
            self._table = CheckableTableView()
            self._left.insertWidget(0, self._table)
            self._address_prefix_check_btn.setEnabled(True)
            self._types_check_btn.setEnabled(True)

        self._load_objects_btn.setVisible(True)
        self._save_results_btn.setVisible(False)

        self.on_document_change()

        self._table.setModel(self._table_model)
        self._table.horizontalHeader().setMinimumSectionSize(0)
        self._table.resizeColumnsToContents()

    def table_as_DataFrame(self, include_all: bool = True) -> pd.DataFrame:
        lines: List[List[Any]] = []
        index: List[int] = []
        for row in range(self._table_model.rowCount()):
            if include_all or self._table_model.index(row, 0).data() == '+':
                lines.append([])
                index.append(row)
                lines[-1].append('1' if self._table_model.index(row, 0).data() == '+' else '0')
                for col in range(self._table_model.columnCount())[1:]:
                    lines[-1].append(self._table_model.index(row, col).data())
        df = pd.DataFrame(lines, columns=self._table_axes, index=index)
        try:
            if self._document_fields.latitude.text() in self._table_axes:
                df[self._document_fields.latitude.text()] = df[self._document_fields.latitude.text()].astype(float)
            if self._document_fields.longitude.text() in self._table_axes:
                df[self._document_fields.longitude.text()] = df[self._document_fields.longitude.text()].astype(float)
        except Exception as ex:
            QtWidgets.QMessageBox.critical(self, 'Ошибка при конвертации таблицы', f'Произошла ошибка при переводе данных в DataFrame: {ex}')
        return df

    def on_load_objects(self) -> None:
        self._load_objects_btn.setVisible(False)
        app.setOverrideCursor(QtCore.Qt.BusyCursor)
        is_commit = not bool(QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.ShiftModifier)
        try:
            types_mapping = {'целое': int, 'нецелое': float, 'строка': str, 'булево': bool}
            adding_functional_objects.ensure_tables(
                    self._db_properties.conn, self._options_fields.object_class.text() if not self._options_fields.object_class_choosable.isChecked() else \
                    self._options_fields.object_class_choose.currentText(), 
                    {self._additionals_group.itemAtPosition(i + 2, 0).widget().text(): types_mapping[self._additionals_group.itemAtPosition(i + 2, 1).widget().currentText()] \
                            for i in range(self._additionals_cnt)},
                    is_commit)
            service_type_id = adding_functional_objects.ensure_service(self._db_properties.conn,
                    self._options_fields.service_type.text() if not self._options_fields.service_type_choosable.isChecked() else \
                             self._options_fields.service_type_choose.currentText(),
                    self._options_fields.service_code.text() if not self._options_fields.service_type_choosable.isChecked() else \
                             None,
                    (int(self._options_fields.min_capacity.text()) if self._options_fields.min_capacity.text() not in ('', '-') else None) \
                            if not self._options_fields.service_type_choosable.isChecked() else None,
                    (int(self._options_fields.max_capacity.text()) if self._options_fields.max_capacity.text() not in ('', '-') else None) \
                            if not self._options_fields.service_type_choosable.isChecked() else None,
                    self._options_fields.city_function.currentText())
            results = adding_functional_objects.add_objects(
                    self._db_properties.conn,
                    self.table_as_DataFrame(False),
                    self._options_fields.object_class.text() if not self._options_fields.object_class_choosable.isChecked() else \
                            self._options_fields.object_class_choose.currentText(),
                    self._types_window.types(),
                    service_type_id,
                    self._options_fields.override_amenity.text() if self._options_fields.override_amenity.text() not in ('', '-') else None,
                    {
                        'lat': self._document_fields.latitude.text(),
                        'lng': self._document_fields.longitude.text(),
                        'amenity': self._document_fields.amenity.text(),
                        'name': self._document_fields.name.text(),
                        'opening_hours': self._document_fields.opening_hours.text(),
                        'website': self._document_fields.website.text(),
                        'phone': self._document_fields.phone.text(),
                        'address': self._document_fields.address.text(),
                        'osm_id': self._document_fields.osm_id.text()
                    },
                    list(map(lambda line_edit: line_edit.text(), self._document_address_prefixes)),
                    {self._additionals_group.itemAtPosition(i + 2, 0).widget().text():
                            (self._additionals_group.itemAtPosition(i + 2, 2).widget().text(), types_mapping[self._additionals_group.itemAtPosition(i + 2, 1).widget().currentText()]) \
                                    for i in range(self._additionals_cnt)},
                    is_commit
            )
            if not is_commit:
                self._db_properties.conn.rollback()
        except psycopg2.OperationalError as ex:
            self._load_objects_btn.setVisible(True)
            QtWidgets.QMessageBox.critical(self, 'Ошибка при загрузке',
                    f'Произошла ошибка при загрузке объектов в базу\nВозможны проблемы с подключением к базе')
            self._db_check_btn.click()
            return
        except Exception as ex:
            self._load_objects_btn.setVisible(True)
            QtWidgets.QMessageBox.critical(self, 'Ошибка при загрузке', f'Произошла ошибка при загрузке объектов в базу\n{ex}')
            traceback.print_exc()
            return
        finally:
            app.restoreOverrideCursor()
        df = self.table_as_DataFrame().join(results[['result', 'functional_obj_id']]).fillna('')
        self._table_axes += ['Результат', 'id Функционального объекта']
        self._table_model.appendColumn(list(map(lambda text: QtGui.QStandardItem(text), df['result'])))
        self._table_model.appendColumn(list(map(lambda text: QtGui.QStandardItem(str(int(text)) if isinstance(text, (int, float)) else ''), df['functional_obj_id'])))
        self._table_model.setHorizontalHeaderLabels(self._table_axes)
        self._table.resizeColumnToContents(len(self._table_axes) - 2) # type: ignore
        self._table.resizeColumnToContents(len(self._table_axes) - 1) # type: ignore
        for row in range(self._table_model.rowCount()):
            self._table_model.setData(self._table_model.index(row, len(self._table_axes) - 2), MainWindow.colorTable.sky_blue, QtCore.Qt.BackgroundRole)
            self._table_model.setData(self._table_model.index(row, len(self._table_axes) - 1), MainWindow.colorTable.sky_blue, QtCore.Qt.BackgroundRole)
        self._save_results_btn.setVisible(True)
        # set table not-editable
        # for i in range(self._table_model.rowCount()):
        #     for j in range(self._table_model.columnCount()):
        #         self._table_model.index(i, j)

    def on_save_results(self) -> None:
        fileDialog = QtWidgets.QFileDialog(self)
        fileDialog.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        fileDialog.setNameFilters(('All files (*.xlsx *.xls *.ods *.csv)', 'Modern Excel files (*.xlsx)',
                'Excel files (*.xls *.ods)', 'CSV files (*.csv)'))
        filename = self.windowTitle()[self.windowTitle().index('"') + 1:self.windowTitle().rindex('"')]
        t = time.localtime()
        logfile = f'{t.tm_year}-{t.tm_mon:02}-{t.tm_mday:02} ' \
                f'{t.tm_hour:02}-{t.tm_min:02}-{t.tm_sec:02}-{filename[:filename.rindex(".")]}'
        fileDialog.selectNameFilter('CSV files (*.csv)')
        fileDialog.selectFile(logfile)
        if fileDialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        filename = fileDialog.selectedFiles()[0]
        df = self.table_as_DataFrame()
        save_func = pd.DataFrame.to_csv if filename[filename.rfind('.') + 1:] == 'csv' else pd.DataFrame.to_excel
        save_func(df, filename, index=False)

    def on_prefix_add(self) -> None:
        self._document_address_prefixes.append(QtWidgets.QLineEdit())
        self._prefixes_group.insertWidget(self._prefixes_group.count() - 3, self._document_address_prefixes[-1])
        if len(self._document_address_prefixes) == 2:
            self._address_prefix_remove_btn.setEnabled(True)

    def on_prefix_remove(self) -> None:
        self._document_address_prefixes.pop()
        widget = self._prefixes_group.itemAt(self._prefixes_group.count() - 4).widget()
        widget.setVisible(False)
        self._prefixes_group.removeWidget(widget)
        if len(self._document_address_prefixes) == 1:
            self._address_prefix_remove_btn.setEnabled(False)

    def on_prefix_check(self) -> None:
        if self._document_fields.address.text() in self._table_axes:
            col = self._table_axes.index(self._document_fields.address.text())
            for row in range(self._table_model.rowCount()):
                found = False
                for prefix in self._document_address_prefixes:
                    if str(self._table_model.index(row, col).data()).startswith(prefix.text()):
                        self._table_model.setData(self._table_model.index(row, col), MainWindow.colorTable.dark_green, QtCore.Qt.BackgroundRole)
                        found = True
                        break
                if not found:
                    self._table_model.setData(self._table_model.index(row, col), MainWindow.colorTable.dark_red, QtCore.Qt.BackgroundRole)

    def on_connection_check(self) -> None:
        host, port_str = (self._database_fields.address.text().split(':') + [str(MainWindow.default_values.db_port)])[0:2]
        try:
            port = int(port_str)
        except ValueError:
            self._db_check_res.setText('<b style=color:red;>x</b>')
            return
        if not (self._db_properties.db_addr == host and self._db_properties.db_port == port and 
                self._db_properties.db_name == self._database_fields.name.text() and
                self._db_properties.db_user == self._database_fields.user.text() and
                self._db_properties.db_pass == self._database_fields.password.text()):
            self._db_properties.close()
            self._db_properties = Properties(host, port, self._database_fields.name.text(),
                    self._database_fields.user.text(), self._database_fields.password.text())
        try:
            with self._db_properties.conn.cursor() as cur:
                cur.execute('SELECT 1')
                assert cur.fetchone()[0] == 1
                cur.execute('SELECT name FROM city_functions ORDER BY 1')
                items = list(map(lambda x: x[0], cur.fetchall()))
                self._options_fields.city_function.clear()
                self._options_fields.city_function.addItem('(не выбрано)')
                self._options_fields.city_function.addItems(items)
                self._options_fields.city_function.view().setMinimumWidth(len(max(items, key=len)) * 8)

                cur.execute("SELECT substring(tablename, 0, length(tablename) - 7) FROM pg_tables WHERE tablename like '%_objects' AND tablename NOT IN ('physical_objects', 'functional_objects') ORDER BY 1")
                items = list(map(lambda x: x[0], cur.fetchall()))
                self._options_fields.object_class_choose.clear()
                self._options_fields.object_class_choose.addItem('(не выбрано)')
                self._options_fields.object_class_choose.addItems(items)
                self._options_fields.object_class_choose.view().setMinimumWidth(len(max(items, key=len)) * 8)

                cur.execute('SELECT name, code, capacity_min, capacity_max FROM service_types ORDER BY 1')
                self._service_type_params = dict(map(lambda x: (x[0], x[1:4]), cur.fetchall()))
                self._options_fields.service_type_choose.clear()
                self._options_fields.service_type_choose.addItem('(не выбрано)')
                self._options_fields.service_type_choose.addItems(sorted(self._service_type_params.keys()))
                self._options_fields.service_type_choose.view().setMinimumWidth(len(max(self._service_type_params.keys(), key=len)) * 8)
        except Exception:
            self._db_properties.close()
            if QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.ShiftModifier:
                QtWidgets.QMessageBox.critical(self, 'Ошибка при попытке подключиться к БД', traceback.format_exc())
            self._db_check_res.setText('<b style=color:red;>x</b>')
        else:        
            self._db_check_res.setText('<b style=color:green;>v</b>')

    def on_options_change(self, what_changed: Optional[Union[QtWidgets.QLineEdit, QtWidgets.QComboBox]] = None, _: Optional[str] = None):
        allowed_chars = set((chr(i) for i in range(ord('a'), ord('z') + 1))) | {'_'}
        self._is_options_ok = True

        if what_changed is self._options_fields.object_class_choose:
            if what_changed.currentIndex() > 0:
                while self._additionals_cnt > 0:
                    self.on_additional_delete()
                try:
                    with self._db_properties.conn.cursor() as cur:
                        cur.execute('SELECT column_name, data_type from information_schema.columns where table_name = %s', (what_changed.currentText() + '_objects',))
                        for column_name, datatype in filter(lambda column_and_type: column_and_type[0] not in \
                                ('id', 'properties', 'functional_object_id', 'type_id', 'created_at', 'updated_at'),
                                map(lambda column_and_type: (column_and_type[0], int if column_and_type[1] == 'integer' else \
                                        float if column_and_type[1] == 'double precision' else bool if column_and_type[1] == 'boolean' else str), cur.fetchall())):
                            self.on_additional_add(column_name, datatype)
                        cur.execute("SELECT count(distinct column_name) from information_schema.columns where table_name = %s and column_name = 'name' or column_name = 'code'",
                                (what_changed.currentText() + '_object_types',))
                        tmp = cur.fetchone()[0]
                        if tmp == 2:
                            cur.execute(f'SELECT name, code FROM {what_changed.currentText()}_object_types ORDER BY 1')
                            self._types_window.update_types_list(cur.fetchall())
                except Exception:
                    traceback.print_exc()
        elif what_changed is self._options_fields.service_type_choose:
            if what_changed.currentIndex() > 1:
                try:
                    with self._db_properties.conn.cursor() as cur:
                        cur.execute('SELECT cf.name FROM service_types st JOIN city_functions cf ON st.city_function_id = cf.id WHERE st.name = %s', (what_changed.currentText(),))
                        self._options_fields.city_function.setCurrentText(cur.fetchone()[0])
                except Exception:
                    traceback.print_exc()
            else:
                self._options_fields.city_function.setCurrentIndex(0)

        if self._options_fields.object_class_choosable.isChecked():
            if self._options_fields.object_class_choose.currentIndex() == 0:
                self._is_options_ok = False
                self._options_fields.object_class_choose.setStyleSheet('background-color: rgb({}, {}, {})'.format(*MainWindow.colorTable.light_red.getRgb()[:3]))
            else:
                self._options_fields.object_class_choose.setStyleSheet('background-color: rgb({}, {}, {})'.format(*MainWindow.colorTable.light_green.getRgb()[:3]))
        else:
            if len(self._options_fields.object_class.text()) == 0 or len(set(self._options_fields.object_class.text()) - allowed_chars) != 0:
                self._is_options_ok = False
                self._options_fields.object_class.setStyleSheet('background-color: rgb({}, {}, {})'.format(*MainWindow.colorTable.light_red.getRgb()[:3]))
            else:
                self._options_fields.object_class.setStyleSheet('background-color: rgb({}, {}, {})'.format(*MainWindow.colorTable.light_green.getRgb()[:3]))

        if self._options_fields.service_type_choosable.isChecked():
            if self._options_fields.service_type_choose.currentIndex() == 0:
                self._is_options_ok = False
                self._options_fields.service_type_choose.setStyleSheet('background-color: rgb({}, {}, {})'.format(*MainWindow.colorTable.light_red.getRgb()[:3]))
            else:
                self._options_fields.service_type_choose.setStyleSheet('background-color: rgb({}, {}, {})'.format(*MainWindow.colorTable.light_green.getRgb()[:3]))
            service = self._service_type_params.get(self._options_fields.service_type_choose.currentText(), (None,) * 3)
            self._options_fields.service_code.setText(service[0] or '')
            self._options_fields.min_capacity.setText(str(service[1] or ''))
            self._options_fields.max_capacity.setText(str(service[2] or ''))
        else:
            if self._options_fields.service_type.text() != '' and '"' not in self._options_fields.service_type.text() \
                    and "'" not in self._options_fields.service_type.text():
                self._options_fields.service_type.setStyleSheet('background-color: rgb({}, {}, {})'.format(*MainWindow.colorTable.light_green.getRgb()[:3]))
            else:
                self._is_options_ok = False
                self._options_fields.service_type.setStyleSheet('background-color: rgb({}, {}, {})'.format(*MainWindow.colorTable.light_red.getRgb()[:3]))

        if len(self._options_fields.service_code.text()) == 0:
            self._options_fields.service_code.setStyleSheet('background-color: rgb({}, {}, {})'.format(*MainWindow.colorTable.grey.getRgb()[:3]))
        elif len(set(self._options_fields.service_code.text()) - allowed_chars - {'-'}) == 0:
            self._options_fields.service_code.setStyleSheet('background-color: rgb({}, {}, {})'.format(*MainWindow.colorTable.light_green.getRgb()[:3]))
        else:
            self._is_options_ok = False
            self._options_fields.service_code.setStyleSheet('background-color: rgb({}, {}, {})'.format(*MainWindow.colorTable.light_red.getRgb()[:3]))

        if self._options_fields.city_function.currentIndex() == 0:
            self._is_options_ok = False
            self._options_fields.city_function.setStyleSheet('background-color: rgb({}, {}, {})'.format(*MainWindow.colorTable.light_red.getRgb()[:3]))
        else:
            self._options_fields.city_function.setStyleSheet('background-color: rgb({}, {}, {})'.format(*MainWindow.colorTable.light_green.getRgb()[:3]))
        
        for line in (self._options_fields.min_capacity, self._options_fields.max_capacity):
            if line.text().isdigit():
                line.setStyleSheet('background-color: rgb({}, {}, {})'.format(*MainWindow.colorTable.light_green.getRgb()[:3]))
            elif line.text() == '':
                line.setStyleSheet('background-color: rgb({}, {}, {})'.format(*MainWindow.colorTable.grey.getRgb()[:3]))
            else:
                self._is_options_ok = False
                line.setStyleSheet('background-color: rgb({}, {}, {})'.format(*MainWindow.colorTable.light_red.getRgb()[:3]))

        for line in (self._additionals_group.itemAtPosition(i + 2, 0).widget() for i in range(self._additionals_cnt)):
            if len(line.text()) == 0 or len(set(line.text()) - allowed_chars - {'-', '_'}) != 0:
                self._is_options_ok = False
                line.setStyleSheet('background-color: rgb({}, {}, {})'.format(*MainWindow.colorTable.light_red.getRgb()[:3]))
            else:
                line.setStyleSheet('')
            
        # print(f'Options check. Options: {self._is_options_ok}, document: {self._is_document_ok}')
        if self._is_options_ok and self._is_document_ok:
            self._load_objects_btn.setEnabled(True)
        else:
            self._load_objects_btn.setEnabled(False)

    def on_choose_change(self, what_changed: QtWidgets.QCheckBox) -> None:
        if what_changed is self._options_fields.object_class_choosable:
            if what_changed.isChecked():
                self._options_group.replaceWidget(self._options_fields.object_class, self._options_fields.object_class_choose)
                self._options_fields.object_class.setVisible(False)
                self._options_fields.object_class_choose.setVisible(True)
                self.on_options_change(self._options_fields.object_class_choose)
            else:
                self._options_group.replaceWidget(self._options_fields.object_class_choose, self._options_fields.object_class)
                self._options_fields.object_class_choose.setVisible(False)
                self._options_fields.object_class.setVisible(True)
        elif what_changed is self._options_fields.service_type_choosable:
            if what_changed.isChecked():
                self._options_group.replaceWidget(self._options_fields.service_type, self._options_fields.service_type_choose)
                self._options_fields.service_type.setVisible(False)
                self._options_fields.service_type_choose.setVisible(True)
                self._options_fields.service_code.setEnabled(False)
                self._options_fields.min_capacity.setEnabled(False)
                self._options_fields.max_capacity.setEnabled(False)
                self._options_fields.city_function.setEnabled(False)
                self.on_options_change(self._options_fields.service_type_choose)
            else:
                self._options_group.replaceWidget(self._options_fields.service_type_choose, self._options_fields.service_type)
                self._options_fields.service_type_choose.setVisible(False)
                self._options_fields.service_type.setVisible(True)
                self._options_fields.service_code.setEnabled(True)
                self._options_fields.min_capacity.setEnabled(True)
                self._options_fields.max_capacity.setEnabled(True)
                self._options_fields.city_function.setEnabled(True)
        self.on_options_change()

    def on_additional_add(self, db_column: Optional[str] = None, datatype: Optional[type] = None) -> None:
        self._additionals_group.addWidget(ColorizingLine(self.on_options_change, ), self._additionals_cnt + 2, 0)
        self._additionals_group.addWidget(QtWidgets.QComboBox(), self._additionals_cnt + 2, 1)
        self._additionals_group.addWidget(ColorizingLine(self.on_document_change), self._additionals_cnt + 2, 2)
        self.on_document_change(self._additionals_group.itemAtPosition(self._additionals_cnt + 2, 2).widget())
        self._additionals_group.itemAtPosition(self._additionals_cnt + 2, 1).widget().addItems(['строка', 'целое', 'нецелое', 'булево'])
        if db_column is not None:
            self._additionals_group.itemAtPosition(self._additionals_cnt + 2, 0).widget().setText(db_column)
        if datatype is not None:
            self._additionals_group.itemAtPosition(self._additionals_cnt + 2, 1).widget().setCurrentIndex({str: 0, int: 1, float: 2, bool: 3}[datatype])
        self._additionals_cnt += 1
        if self._additionals_cnt == 1:
            for i in range(3):
                self._additionals_group.itemAtPosition(1, i).widget().setVisible(True)
            self._additional_delete_btn.setEnabled(True)
        self.on_options_change()

    def on_additional_delete(self) -> None:
        self._additionals_cnt -= 1
        for i in range(2, -1, -1):
            widget = self._additionals_group.itemAtPosition(self._additionals_cnt + 2, i).widget()
            if i == 2:
                if self._table is not None:
                    old_text = widget.text()
                    widget.setText(max(self._table_axes, key=len) + self._table_axes[0])
                    self.on_document_change(widget, old_text)
            widget.setVisible(False)
            self._additionals_group.removeWidget(widget)
        if self._additionals_cnt == 0:
            for i in range(3):
                self._additionals_group.itemAtPosition(1, i).widget().setVisible(False)
            self._additional_delete_btn.setEnabled(False)
        self.check_document_correctness()
        self.on_options_change()

    def check_document_correctness(self) -> None:
        self._is_document_ok = True
        field: QtWidgets.QLineEdit
        for field in itertools.chain(self._document_fields, (self._additionals_group.itemAtPosition(i + 2, 2).widget() for i in range(self._additionals_cnt))): # type: ignore
            if field.text() not in self._table_axes:
                if not (field.text() in ('', '-') and not (field is self._document_fields.address or
                        field is self._document_fields.latitude or field is self._document_fields.longitude)) or \
                        (field is self._document_fields.amenity and self._options_fields.override_amenity.text() not in ('', '-')):
                    self._is_document_ok = False

    def on_document_change(self, what_changed: Optional[QtWidgets.QLineEdit] = None, previous_value: Optional[str] = None) -> None:
        if self._table is None:
            return
        if what_changed is not None:
            if what_changed is self._options_fields.override_amenity or \
                    what_changed is self._document_fields.amenity and self._options_fields.override_amenity.text() not in ('', '-'):
                if self._options_fields.override_amenity.text() in ('', '-'):
                    self._options_fields.override_amenity.setStyleSheet('background-color: rgb({}, {}, {});'.format(*MainWindow.colorTable.grey.getRgb()[:3]))
                    self.on_document_change(self._document_fields.amenity)
                    return
                self._document_fields.amenity.setStyleSheet('background-color: rgb({}, {}, {});'.format(*MainWindow.colorTable.grey.getRgb()[:3]))
                if self._document_fields.amenity.text() in self._table_axes:
                    col = self._table_axes.index(self._document_fields.amenity.text())
                    for row in range(self._table_model.rowCount()):
                        self._table_model.setData(self._table_model.index(row, col), MainWindow.colorTable.grey, QtCore.Qt.BackgroundRole)
            elif what_changed.text() not in self._table_axes:
                if (what_changed.text() in ('', '-') and not (what_changed is self._document_fields.address or
                        what_changed is self._document_fields.latitude or what_changed is self._document_fields.longitude)) or \
                        (what_changed is self._document_fields.amenity and self._options_fields.override_amenity.text() not in ('', '-')):
                    what_changed.setStyleSheet('background-color: rgb({}, {}, {});'.format(*MainWindow.colorTable.grey.getRgb()[:3]))
                else:
                    what_changed.setStyleSheet('background-color: rgb({}, {}, {});'.format(*MainWindow.colorTable.light_red.getRgb()[:3]))
            else:
                what_changed.setStyleSheet('')
                col = self._table_axes.index(what_changed.text())
                for row in range(self._table_model.rowCount()):
                    self._table_model.setData(self._table_model.index(row, col), MainWindow.colorTable.light_green, QtCore.Qt.BackgroundRole)
                
            if previous_value in self._table_axes:
                col = self._table_axes.index(previous_value)
                for row in range(self._table_model.rowCount()):
                    self._table_model.setData(self._table_model.index(row, col), QtGui.QColor(QtCore.Qt.white), QtCore.Qt.BackgroundRole)
            self.check_document_correctness()
        else:
            self._is_document_ok = True
            field: QtWidgets.QLineEdit
            for field in itertools.chain(self._document_fields, (self._additionals_group.itemAtPosition(i + 2, 2).widget() for i in range(self._additionals_cnt))): # type: ignore
                if field.text() not in self._table_axes:
                    if (field.text() in ('', '-') and not (field is self._document_fields.address or
                            field is self._document_fields.latitude or field is self._document_fields.longitude)) or \
                            (field is self._document_fields.amenity and self._options_fields.override_amenity.text() not in ('', '-')):
                        field.setStyleSheet('background-color: rgb({}, {}, {});'.format(*MainWindow.colorTable.grey.getRgb()[:3]))
                    else:
                        field.setStyleSheet('background-color: rgb({}, {}, {});'.format(*MainWindow.colorTable.light_red.getRgb()[:3]))
                        self._is_document_ok = False
                else:
                    field.setStyleSheet('')
                    col = self._table_axes.index(field.text())
                    for row in range(self._table_model.rowCount()):
                        self._table_model.setData(self._table_model.index(row, col), MainWindow.colorTable.light_green, QtCore.Qt.BackgroundRole)
            if self._options_fields.override_amenity.text() not in ('', '-'):
                self._document_fields.amenity.setStyleSheet('background-color: rgb({}, {}, {});'.format(*MainWindow.colorTable.grey.getRgb()[:3]))
                if self._document_fields.amenity.text() in self._table_axes:
                    col = self._table_axes.index(self._document_fields.amenity.text())
                    for row in range(self._table_model.rowCount()):
                        self._table_model.setData(self._table_model.index(row, col), MainWindow.colorTable.grey, QtCore.Qt.BackgroundRole)
            else:
                self._options_fields.override_amenity.setStyleSheet('background-color: rgb({}, {}, {});'.format(*MainWindow.colorTable.grey.getRgb()[:3]))

        # print(f'Document check. Options: {self._is_options_ok}, document: {self._is_document_ok}')

        if self._is_options_ok and self._is_document_ok:
            self._load_objects_btn.setEnabled(True)
        else:
            self._load_objects_btn.setEnabled(False)

    def on_types_open(self) -> None:
        if self._types_window.isHidden():
            self._types_window.show()

    def on_types_check(self) -> None:
        types = self._types_window.types()
        if self._options_fields.override_amenity.text() not in ('', '-'):
            if self._options_fields.override_amenity.text().lower() in types:
                self._options_fields.override_amenity.setStyleSheet('background-color: rgb({}, {}, {});'.format(*MainWindow.colorTable.light_green.getRgb()[:3]))
            else:
                self._options_fields.override_amenity.setStyleSheet('background-color: rgb({}, {}, {});'.format(*MainWindow.colorTable.light_red.getRgb()[:3]))
        else:
            if self._document_fields.amenity.text() in self._table_axes:
                col = self._table_axes.index(self._document_fields.amenity.text())
                for row in range(self._table_model.rowCount()):
                    if self._table_model.index(row, col).data().lower() in types:
                        self._table_model.setData(self._table_model.index(row, col), MainWindow.colorTable.dark_green, QtCore.Qt.BackgroundRole)
                    else:
                        self._table_model.setData(self._table_model.index(row, col), MainWindow.colorTable.dark_red, QtCore.Qt.BackgroundRole)
            else:
                self._document_fields.amenity.setStyleSheet('background-color: rgb({}, {}, {})'.format(*MainWindow.colorTable.light_red.getRgb()[:3]))

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self._types_window.close()
        return super().closeEvent(event)


class TypesWindow(QtWidgets.QWidget):
    def __init__(self, types: Optional[Dict[str, Tuple[str, str]]] = None, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)

        self.setWindowTitle('Соответствие внутренних типов')

        if types is None:
            types = {}

        self._layout = QtWidgets.QGridLayout()
        self._scroll = QtWidgets.QScrollArea()
        self._scroll_widget = QtWidgets.QFrame()
        self._scroll_vlayout = QtWidgets.QVBoxLayout()

        self._scroll.setWidget(self._scroll_widget)
        self._scroll.setWidgetResizable(True)
        self._scroll_widget.setLayout(self._layout)
        self._scroll_vlayout.addWidget(self._scroll)
        self.setLayout(self._scroll_vlayout)

        self._layout.setAlignment(QtCore.Qt.AlignTop)

        self._layout.addWidget(QtWidgets.QLabel('<b>Название в документе</b>'), 0, 0)
        self._layout.addWidget(QtWidgets.QLabel('<b>Название в базе     </b>'), 0, 1)
        self._layout.addWidget(QtWidgets.QLabel('<b>Код в базе          </b>'), 0, 2)
        self._layout.setHorizontalSpacing(30)
        self._layout_rows = 1

        for item, (name, code) in types.items():
            self._layout.addWidget(QtWidgets.QLineEdit(item), self._layout_rows, 0)
            self._layout.addWidget(QtWidgets.QLineEdit(name), self._layout_rows, 1)
            self._layout.addWidget(QtWidgets.QLineEdit(code), self._layout_rows, 2)
            self._layout_rows += 1

        self._edit_buttons_layout = QtWidgets.QHBoxLayout()
        self._save_load_buttons_layout = QtWidgets.QHBoxLayout()

        self._add_btn = QtWidgets.QPushButton('Добавить')
        self._add_btn.clicked.connect(self.on_add)
        self._delete_btn = QtWidgets.QPushButton('Удалить')
        self._delete_btn.clicked.connect(self.on_delete)
        if self._layout_rows == 1:
            self._delete_btn.setEnabled(False)
        self._edit_buttons_layout.addWidget(self._add_btn)
        self._edit_buttons_layout.addWidget(self._delete_btn)

        self._load_btn = DropPushButton('Загрузить', ['json'], self.on_load)
        self._load_btn.clicked.connect(self.on_load)
        self._save_btn = QtWidgets.QPushButton('Сохранить')
        self._save_btn.clicked.connect(self.on_save)
        self._save_load_buttons_layout.addWidget(self._load_btn)
        self._save_load_buttons_layout.addWidget(self._save_btn)

        self._scroll_vlayout.addLayout(self._edit_buttons_layout)
        self._scroll_vlayout.addLayout(self._save_load_buttons_layout)
    
    def update_types_list(self, types: List[Tuple[str, str]]):
        while self._layout_rows > 1:
            self.on_delete()
        for name_db, code in types:
            self.on_add(None, name_db, code)

    def types(self) -> Dict[str, Tuple[str, str]]:
        types = {}
        for i in range(self._layout_rows - 1):
            types[self._layout.itemAtPosition(i + 1, 0).widget().text().lower()] = \
                    (self._layout.itemAtPosition(i + 1, 1).widget().text(), self._layout.itemAtPosition(i + 1, 2).widget().text())
        return types

    def on_add(self, name_document: Optional[str] = None, name_db: Optional[str] = None, code: Optional[str] = None) -> None:
        self._layout.addWidget(QtWidgets.QLineEdit(name_document), self._layout_rows, 0)
        self._layout.addWidget(QtWidgets.QLineEdit(name_db), self._layout_rows, 1)
        self._layout.addWidget(QtWidgets.QLineEdit(code), self._layout_rows, 2)
        self._layout_rows += 1
        if self._layout_rows == 2:
            self._delete_btn.setEnabled(True)
    
    def on_delete(self) -> None:
        for j in range(2, -1, -1):
            widget = self._layout.itemAtPosition(self._layout_rows - 1, j).widget()
            widget.setVisible(False)
            self._layout.removeWidget(widget)
        self._layout_rows -= 1
        if self._layout_rows == 1:
            self._delete_btn.setEnabled(False)
    
    def on_save(self) -> None:
        fileDialog = QtWidgets.QFileDialog(self)
        fileDialog.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        fileDialog.setNameFilter('JSON file (*.json)')
        fileDialog.selectFile('types')
        if fileDialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        with open(fileDialog.selectedFiles()[0], 'wt', encoding='utf-8') as f:
            json.dump(self.types(), f, ensure_ascii=False)
    
    def on_load(self, filepath: Optional[str] = None) -> None:
        if not filepath:
            fileDialog = QtWidgets.QFileDialog(self)
            fileDialog.setNameFilter('JSON file (*.json)')
            if fileDialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
                return
            filename = fileDialog.selectedFiles()[0]
        else:
            filename = filepath
        while self._layout_rows > 1:
            self.on_delete()
        try:
            with open(filename, 'rt', encoding='utf-8') as f:
                types = json.load(f)
            for item in types.items():
                assert isinstance(item, tuple) and len(item) == 2, 'Неверный формат файла'
        except AssertionError as ex:
            QtWidgets.QMessageBox.critical(self, 'Невозможно открыть файл', f'Ошибка при открытии файла: {ex}')
            return
        except Exception as ex:
            QtWidgets.QMessageBox.critical(self, 'Невозможно открыть файл', f'Неизвестная ошибка при открытии: {ex}')
            return
        types = dict(map(lambda item: (item[0].lower(), item[1]), types.items()))
        for i, (item, (name, code)) in enumerate(types.items(), 1):
            self.on_add(item, name, code)


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    app.setWindowIcon(QtGui.QIcon(QtGui.QPixmap('icon.png')))
    app.setApplicationName('Добавление сервисов')

    window = MainWindow()
    window.show()

    exit(app.exec())