from PySide6 import QtCore, QtWidgets, QtGui
from typing import Any, Callable, Optional, NamedTuple, List, Tuple, Dict, Set
import time
import json
import traceback
import pandas as pd
import psycopg2

from database_properties import Properties
import adding_functional_objects

class ColorizingLine(QtWidgets.QLineEdit):
    def __init__(self, callback: Callable[[Optional[QtWidgets.QLineEdit], Optional[str]], None], parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._state: str = ''
        self._callback = callback
    
    def focusInEvent(self, event: QtGui.QFocusEvent) -> None:
        self._state = self.text()
        return super().focusInEvent(event)

    def focusOutEvent(self, event: QtGui.QFocusEvent) -> None:
        if self.text() != self._state:
            self._callback(self, self._state)
            self._state = self.text()
        return super().focusOutEvent(event)


class ColorizingComboBox(QtWidgets.QComboBox):
    def __init__(self, callback: Callable[[], None], parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._callback = callback
        self._state = 0
        self.currentIndexChanged.connect(callback)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        super().wheelEvent(event)
        if self.currentIndex() != self._state:
            self._callback()
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
            ('city_function', QtWidgets.QComboBox)
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
        self._load_objects_btn = QtWidgets.QPushButton('Загрузить объекты')
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
        self._db_check_btn = QtWidgets.QPushButton('Проверка')
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
                ColorizingLine(self.colorize_table),
                ColorizingComboBox(self.on_options_change)
        )
        self._options_group.addRow('Название таблицы:', self._options_fields.object_class)
        self._options_group.addRow('Тип сервиса:', self._options_fields.service_type)
        self._options_group.addRow('Код сервиса:', self._options_fields.service_code)
        self._options_group.addRow('Городская функция:', self._options_fields.city_function)
        self._options_group.addRow('Минимальная мощность:', self._options_fields.min_capacity)
        self._options_group.addRow('Максимальная мощность:', self._options_fields.max_capacity)
        self._options_group.addRow('Задать тип объекта:', self._options_fields.override_amenity)
        self._right.addWidget(self._options_group_box)

        self._document_group_box = QtWidgets.QGroupBox('Сопоставление документа')
        self._document_group = QtWidgets.QFormLayout()
        self._document_group_box.setLayout(self._document_group)
        self._document_fields = MainWindow.DocumentFields(*(ColorizingLine(self.colorize_table) for _ in range(9)))
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

        self._types_window = TypesWindow()
        self._types_window.resize(self._types_window.sizeHint().width(), self._types_window.sizeHint().height() * 2)
        self._types_window.setHidden(True)

        self._right.setAlignment(QtCore.Qt.AlignTop)
        right_width = max(map(lambda box: box.sizeHint().width(), (self._db_group_box, self._options_group_box,
                self._document_group_box, self._prefixes_group_box, self._types_group_box)))
        
        self._right_scroll.setFixedWidth(int(right_width * 1.15))
        self._db_group_box.setFixedWidth(right_width)
        self._options_group_box.setFixedWidth(right_width)
        self._document_group_box.setFixedWidth(right_width)
        self._prefixes_group_box.setFixedWidth(right_width)
        self._types_group_box.setFixedWidth(right_width)

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

        self._is_options_ok = False
        self._is_document_ok = False
        
        self.on_options_change()

    def on_open_file(self, filepath: Optional[str] = None) -> None:
        if not filepath:
            try:
                fileDialog = QtWidgets.QFileDialog(self)
                fileDialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)
                fileDialog.setNameFilters(('All files (*.xlsx *.xls *.json *.geojson *.ods *.csv)', 'Modern Excel files (*.xlsx)',
                        'Excel files (*.xls *.ods)', 'GeoJSON files (*.json *.geojson)', 'CSV files (*.csv)'))
                fileDialog.exec()
                if len(fileDialog.selectedFiles()) == 0:
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

        self.colorize_table()

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
            QtWidgets.QMessageBox(self, 'Ошибка при конвертации таблицы', f'Произошла ошибка при переводе данных в DataFrame: {ex}')
        return df

    def on_load_objects(self) -> None:
        self._load_objects_btn.setVisible(False)
        app.setOverrideCursor(QtCore.Qt.BusyCursor)
        try:
            adding_functional_objects.ensure_tables(self._db_properties.conn, self._options_fields.object_class.text(), False)
            service_type_id = adding_functional_objects.ensure_service(self._db_properties.conn,
                    self._options_fields.service_type.text(), self._options_fields.service_code.text(),
                    int(self._options_fields.min_capacity.text()) if self._options_fields.min_capacity.text() not in ('', '-') else None,
                    int(self._options_fields.max_capacity.text()) if self._options_fields.max_capacity.text() not in ('', '-') else None,
                    self._options_fields.city_function.currentText())
            results = adding_functional_objects.add_objects(
                    self._db_properties.conn,
                    self.table_as_DataFrame(False),
                    self._options_fields.object_class.text(),
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
                    False
            )
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
        fileDialog.exec()
        if len(fileDialog.selectedFiles()) == 0:
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
        self._prefixes_group.removeWidget(widget)
        widget.setVisible(False)
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
                cur.execute('SELECT name FROM city_functions order by 1')
                self._options_fields.city_function.clear()
                self._options_fields.city_function.addItem('(не выбрано)')
                self._options_fields.city_function.addItems(map(lambda x: x[0], cur.fetchall()))
                self._options_fields.city_function.view().setMinimumWidth(len(max(get_default_city_functions(), key=len)) * 8)
        except Exception:
            self._db_properties.close()
            self._db_check_res.setText('<b style=color:red;>x</b>')
        else:        
            self._db_check_res.setText('<b style=color:green;>v</b>')

    def on_options_change(self, _: Optional[QtWidgets.QLineEdit] = None, _1: Optional[str] = None):
        allowed_chars = set((chr(i) for i in range(ord('a'), ord('z'))))
        self._is_options_ok = True

        if len(self._options_fields.object_class.text()) == 0 or len(set(self._options_fields.object_class.text()) - allowed_chars) != 0:
            self._is_options_ok = False
            self._options_fields.object_class.setStyleSheet('background-color: rgb({}, {}, {})'.format(*MainWindow.colorTable.light_red.getRgb()[:3]))
        else:
            self._options_fields.object_class.setStyleSheet('background-color: rgb({}, {}, {})'.format(*MainWindow.colorTable.light_green.getRgb()[:3]))
        if self._options_fields.service_type.text() != '' and '"' not in self._options_fields.service_type.text() \
                and "'" not in self._options_fields.service_type.text():
            self._options_fields.service_type.setStyleSheet('background-color: rgb({}, {}, {})'.format(*MainWindow.colorTable.light_green.getRgb()[:3]))
        else:
            self._options_fields.service_type.setStyleSheet('background-color: rgb({}, {}, {})'.format(*MainWindow.colorTable.light_red.getRgb()[:3]))
        if len(self._options_fields.service_code.text()) == 0:
            self._options_fields.service_code.setStyleSheet('background-color: rgb({}, {}, {})'.format(*MainWindow.colorTable.grey.getRgb()[:3]))
        elif len(set(self._options_fields.service_code.text()) - allowed_chars) == 0:
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
            
        if self._is_options_ok and self._is_document_ok:
            self._load_objects_btn.setEnabled(True)
        else:
            self._load_objects_btn.setEnabled(False)
            


    def colorize_table(self, what_changed: Optional[QtWidgets.QLineEdit] = None, previous_value: Optional[str] = None) -> None:
        if self._table is None:
            return
        self._is_document_ok = True
        if what_changed is not None:
            if what_changed is self._options_fields.override_amenity or \
                    what_changed is self._document_fields.amenity and self._options_fields.override_amenity.text() not in ('', '-'):
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
                    self._is_document_ok = False
            else:
                what_changed.setStyleSheet('')
                col = self._table_axes.index(what_changed.text())
                for row in range(self._table_model.rowCount()):
                    self._table_model.setData(self._table_model.index(row, col), MainWindow.colorTable.light_green, QtCore.Qt.BackgroundRole)
                
            if previous_value in self._table_axes:
                col = self._table_axes.index(previous_value)
                for row in range(self._table_model.rowCount()):
                    self._table_model.setData(self._table_model.index(row, col), QtGui.QColor(QtCore.Qt.white), QtCore.Qt.BackgroundRole)
        else:
            for field in self._document_fields:
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
    def __init__(self, types: Dict[str, Tuple[str, str]] = {}, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)

        self.setWindowTitle('Соответствие внутренних типов')

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

    def types(self) -> Dict[str, Tuple[str, str]]:
        types = {}
        for i in range(self._layout_rows - 1):
            types[self._layout.itemAtPosition(i + 1, 0).widget().text().lower()] = \
                    (self._layout.itemAtPosition(i + 1, 1).widget().text(), self._layout.itemAtPosition(i + 1, 2).widget().text())
        return types

    def on_add(self) -> None:
        self._layout.addWidget(QtWidgets.QLineEdit(), self._layout_rows, 0)
        self._layout.addWidget(QtWidgets.QLineEdit(), self._layout_rows, 1)
        self._layout.addWidget(QtWidgets.QLineEdit(), self._layout_rows, 2)
        self._layout_rows += 1
        if self._layout_rows == 2:
            self._delete_btn.setEnabled(True)
    
    def on_delete(self) -> None:
        for j in range(2, -1, -1):
            widget = self._layout.itemAtPosition(self._layout_rows - 1, j).widget()
            self._layout.removeWidget(widget)
            widget.setVisible(False)
        self._layout_rows -= 1
        if self._layout_rows == 1:
            self._delete_btn.setEnabled(False)
    
    def on_save(self) -> None:
        fileDialog = QtWidgets.QFileDialog(self)
        fileDialog.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        fileDialog.setNameFilter('JSON file (*.json)')
        fileDialog.selectFile('types')
        fileDialog.exec()
        if len(fileDialog.selectedFiles()) == 0:
            return
        with open(fileDialog.selectedFiles()[0], 'wt', encoding='utf-8') as f:
            json.dump(self.types(), f, ensure_ascii=False)
    
    def on_load(self, filepath: Optional[str] = None) -> None:
        if not filepath:
            fileDialog = QtWidgets.QFileDialog(self)
            fileDialog.setNameFilter('JSON file (*.json)')
            fileDialog.exec()
            if len(fileDialog.selectedFiles()) == 0:
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
        if len(types) > 0:
            self._delete_btn.setEnabled(True)
        else:
            self._delete_btn.setEnabled(False)
        for i, (item, (name, code)) in enumerate(types.items(), 1):
            self._layout.addWidget(QtWidgets.QLineEdit(item), i, 0)
            self._layout.addWidget(QtWidgets.QLineEdit(name), i, 1)
            self._layout.addWidget(QtWidgets.QLineEdit(code), i, 2)
            self._layout_rows += 1


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    try:
        app.setWindowIcon(QtGui.QIcon(QtGui.QPixmap('icon.png')))
    except Exception as ex:
        traceback.print_exc()
    app.setApplicationName('Добавление сервисов')

    window = MainWindow()
    window.show()

    exit(app.exec())