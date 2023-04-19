# pylint: disable=consider-using-f-string,c-extension-no-member
"""
Services insertion module.
"""
import itertools
import json
import os
import time
import traceback
from typing import Any, Callable, Dict, Iterable, List, NamedTuple, Optional, Tuple, Union

import pandas as pd
import psycopg2
from loguru import logger
from PySide6 import QtCore, QtGui, QtWidgets

import platform_management.cli as insert_services_cli
from platform_management.database_properties import Properties
from platform_management.gui.basics import CheckableTableView, ColorizingComboBox, ColorizingLine, DropPushButton

logger = logger.bind(name="gui_insert_services")

InsertionWindowDefaultValues = NamedTuple(
    "InsertionWindowDefaultValues",
    [
        ("service_code", str),
        ("city_function", str),
        ("latitude", str),
        ("longitude", str),
        ("geometry", str),
        ("address", str),
        ("name", str),
        ("opening_hours", str),
        ("website", str),
        ("phone", str),
        ("osm_id", str),
    ],
)


def get_main_window_default_values() -> InsertionWindowDefaultValues:
    return InsertionWindowDefaultValues(
        "", "", "x", "y", "geometry", "yand_adr", "name", "opening_hours", "contact:website", "contact:phone", "id"
    )


def get_main_window_default_address_prefixes() -> List[str]:
    return ["Россия, Санкт-Петербург"]


def get_default_city_functions() -> List[str]:
    return ["(необходимо соединение с базой)"]


def get_default_service_types() -> List[str]:
    return ["(необходимо соединение с базой)"]


class InsertionWindow(QtWidgets.QWidget):

    InsertionOptionsFields = NamedTuple(
        "InsertionOptionsFields",
        [
            ("city", QtWidgets.QComboBox),
            ("service_code", QtWidgets.QLineEdit),
            ("city_function", QtWidgets.QComboBox),
            ("service_type", QtWidgets.QComboBox),
            ("is_building", QtWidgets.QCheckBox),
        ],
    )

    DocumentFields = NamedTuple(
        "DocumentFields",
        [
            ("latitude", QtWidgets.QComboBox),
            ("longitude", QtWidgets.QComboBox),
            ("geometry", QtWidgets.QComboBox),
            ("address", QtWidgets.QComboBox),
            ("name", QtWidgets.QComboBox),
            ("opening_hours", QtWidgets.QComboBox),
            ("website", QtWidgets.QComboBox),
            ("phone", QtWidgets.QComboBox),
            ("osm_id", QtWidgets.QComboBox),
            ("capacity", QtWidgets.QComboBox),
        ],
    )

    colorTable = NamedTuple(
        "ColorTable",
        [
            ("light_green", QtGui.QColor),
            ("light_red", QtGui.QColor),
            ("dark_green", QtGui.QColor),
            ("dark_red", QtGui.QColor),
            ("grey", QtGui.QColor),
            ("sky_blue", QtGui.QColor),
            ("yellow", QtGui.QColor),
        ],
    )(
        QtGui.QColor(200, 239, 212),
        QtGui.QColor(255, 192, 203),
        QtGui.QColor(97, 204, 128),
        QtGui.QColor(243, 104, 109),
        QtGui.QColor(230, 230, 230),
        QtGui.QColor(148, 216, 246),
        QtGui.QColor(255, 255, 100),
    )  # type: ignore

    default_values = get_main_window_default_values()

    def __init__(
        self,
        db_properties: Properties,
        on_close: Optional[Callable[[], None]] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)

        self._db_properties = db_properties
        self._on_close = on_close

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

        self._open_file_btn = DropPushButton(
            "Открыть файл", ["xlsx", "xls", "json", "geojson", "ods", "csv"], self.on_open_file
        )
        self._open_file_btn.clicked.connect(self.on_open_file)
        self._load_objects_btn = QtWidgets.QPushButton("Загрузить сервисы")
        self._load_objects_btn.setStyleSheet("font-weight: bold")
        self._load_objects_btn.clicked.connect(self.on_upload_objects)
        self._load_objects_btn.setVisible(False)
        self._save_results_btn = QtWidgets.QPushButton("Сохранить результаты")
        self._save_results_btn.setStyleSheet("font-weight: bold")
        self._save_results_btn.clicked.connect(self.on_export_results)
        self._save_results_btn.setVisible(False)
        left_hlayout = QtWidgets.QHBoxLayout()
        left_hlayout.addWidget(self._open_file_btn)
        left_hlayout.addWidget(self._load_objects_btn)
        left_hlayout.addWidget(self._save_results_btn)
        self._left.addLayout(left_hlayout)
        self._left.setAlignment(QtCore.Qt.AlignCenter)
        self._table: Optional[QtWidgets.QTableView] = None
        self._table_axes: List[str]  # type: ignore
        self._table_model: QtGui.QStandardItemModel = None  # type: ignore

        self._options_group_box = QtWidgets.QGroupBox("Опции вставки")
        self._options_group = QtWidgets.QFormLayout()
        self._options_group_box.setLayout(self._options_group)
        self._options_fields = InsertionWindow.InsertionOptionsFields(
            QtWidgets.QComboBox(),
            ColorizingLine(self.on_options_change),
            ColorizingComboBox(self.on_options_change),
            ColorizingComboBox(self.on_options_change),
            QtWidgets.QCheckBox(),
        )
        self._options_fields.service_type.addItems(get_default_service_types())
        self._options_fields.service_type.view().setMinimumWidth(len(max(get_default_service_types(), key=len)) * 8)

        self._options_group.addRow("Город:", self._options_fields.city)
        self._options_group.addRow("Тип сервиса:", self._options_fields.service_type)
        self._options_group.addRow("Код сервиса:", self._options_fields.service_code)
        self._options_group.addRow("Городская функция:", self._options_fields.city_function)
        self._options_group.addRow("Сервис-здание?", self._options_fields.is_building)
        self._right.addWidget(self._options_group_box)

        self._document_group_box = QtWidgets.QGroupBox("Сопоставление документа")
        self._document_group = QtWidgets.QFormLayout()
        self._document_group_box.setLayout(self._document_group)
        self._document_fields = InsertionWindow.DocumentFields(
            *(ColorizingComboBox(self.on_document_change) for _ in range(10))
        )
        self._document_address_prefixes = [
            ColorizingLine(self.on_prefix_check) for _ in range(len(get_main_window_default_address_prefixes()))
        ]
        self._document_group.addRow("Широта:", self._document_fields.latitude)
        self._document_group.addRow("Долгота:", self._document_fields.longitude)
        self._document_group.addRow("Геометрия:", self._document_fields.geometry)
        self._document_group.addRow("Адрес:", self._document_fields.address)
        self._document_group.addRow("Название:", self._document_fields.name)
        self._document_group.addRow("Рабочие часы:", self._document_fields.opening_hours)
        self._document_group.addRow("Веб-сайт:", self._document_fields.website)
        self._document_group.addRow("Телефон:", self._document_fields.phone)
        self._document_group.addRow("OSM id:", self._document_fields.osm_id)
        self._document_group.addRow("Мощность:", self._document_fields.capacity)
        self._right.addWidget(self._document_group_box)

        self._properties_group_box = QtWidgets.QGroupBox("Дополнительные поля сервисов")
        self._properties_group = QtWidgets.QGridLayout()
        self._properties_group_box.setLayout(self._properties_group)
        self._property_add_btn = QtWidgets.QPushButton("Добавить")
        self._property_add_btn.clicked.connect(self.on_property_add)
        self._property_delete_btn = QtWidgets.QPushButton("Удалить")
        self._property_delete_btn.clicked.connect(self.on_property_delete)
        self._property_delete_btn.setEnabled(False)
        self._properties_group.addWidget(self._property_add_btn, 0, 0)
        self._properties_group.addWidget(self._property_delete_btn, 0, 1)
        self._properties_group.addWidget(QtWidgets.QLabel("В базе данных"), 1, 0)
        self._properties_group.addWidget(QtWidgets.QLabel("В документе"), 1, 1)
        for i in (0, 1):
            self._properties_group.itemAtPosition(1, i).widget().setVisible(False)
            self._properties_group.itemAtPosition(1, i).widget().setAlignment(QtCore.Qt.AlignCenter)
            self._properties_group.itemAtPosition(1, i).widget().setStyleSheet("font-weight: bold;")
        self._right.addWidget(self._properties_group_box)
        self._properties_cnt = 0

        self._prefixes_group_box = QtWidgets.QGroupBox("Префиксы адреса")
        self._prefixes_group = QtWidgets.QVBoxLayout()
        self._prefixes_group_box.setLayout(self._prefixes_group)
        for prefix in self._document_address_prefixes:
            self._prefixes_group.addWidget(prefix)
        self._address_prefix_add_btn = QtWidgets.QPushButton("Добавить префикс")
        self._address_prefix_add_btn.clicked.connect(self.on_prefix_add)
        self._address_prefix_remove_btn = QtWidgets.QPushButton("Удалить префикс")
        self._address_prefix_remove_btn.clicked.connect(self.on_prefix_remove)
        self._address_prefix_remove_btn.setEnabled(False)
        self._prefixes_group.addWidget(self._address_prefix_add_btn)
        self._prefixes_group.addWidget(self._address_prefix_remove_btn)
        self._prefixes_group.addWidget(QtWidgets.QLabel("Новый префикс"))
        self._prefixes_group.addWidget(QtWidgets.QLineEdit())
        self._right.addWidget(self._prefixes_group_box)

        types: Optional[Dict[str, Tuple[str, str]]]
        if os.path.isfile("types.json"):
            with open("types.json", "rt", encoding="utf-8") as file:
                types = json.load(file)
            types = dict(map(lambda x: (x[0].lower(), x[1]), types.items()))  # type: ignore
        else:
            types = None

        self._right.setAlignment(QtCore.Qt.AlignTop)
        right_width = max(
            map(
                lambda box: box.sizeHint().width(),
                (
                    self._options_group_box,
                    self._document_group_box,
                    self._prefixes_group_box,
                    self._properties_group_box,
                ),
            )
        )

        self._right_scroll.setFixedWidth(int(right_width * 1.15))
        self._options_group_box.setFixedWidth(right_width)
        self._document_group_box.setFixedWidth(right_width)
        self._prefixes_group_box.setFixedWidth(right_width)
        self._properties_group_box.setFixedWidth(right_width)

        self._options_fields.service_type.setCurrentIndex(0)
        self._options_fields.service_code.setText(InsertionWindow.default_values.service_code)
        self._options_fields.service_code.setEnabled(False)
        self._options_fields.city_function.addItems(get_default_city_functions())
        self._options_fields.city_function.view().setMinimumWidth(len(max(get_default_city_functions(), key=len)) * 8)
        self._options_fields.city_function.setEnabled(False)
        self._options_fields.is_building.setEnabled(False)
        self._is_options_ok = False
        self._options_fields.service_type.setStyleSheet(
            "background-color: rgb({}, {}, {});color: black".format(*InsertionWindow.colorTable.light_red.getRgb()[:3])
        )

        for field in self._document_fields:
            field.addItem("(необходимо открыть файл)")
            field.setEnabled(False)
        for line, prefix_line in zip(self._document_address_prefixes, get_main_window_default_address_prefixes()):
            line.setText(prefix_line)
            line.setMinimumWidth(250)

        self._service_type_params: Dict[str, Tuple[str, int, int, bool, str]] = {}

        self.on_options_change()

    def on_open_file(self, filepath: Optional[str] = None) -> None:
        if not filepath:
            try:
                file_dialog = QtWidgets.QFileDialog(self)
                file_dialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)
                file_dialog.setNameFilters(
                    (
                        "All files (*.xlsx *.xls *.json *.geojson *.ods *.csv)",
                        "Modern Excel files (*.xlsx)",
                        "Excel files (*.xls *.ods)",
                        "GeoJSON files (*.json *.geojson)",
                        "CSV files (*.csv)",
                    )
                )
                if file_dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
                    return
                filename = file_dialog.selectedFiles()[0]
            except ValueError:
                QtWidgets.QMessageBox.critical(self, "Невозможно открыть файл", "Ошибка при открытии файла")
                return
            except Exception as exc:  # pylint: disable=broad-except
                QtWidgets.QMessageBox.critical(
                    self, "Невозможно открыть файл", f"Неизвестная ошибка при открытии: {exc!r}"
                )
                return
        else:
            filename = filepath

        dataframe = insert_services_cli.load_objects(filename)
        self.setWindowTitle(f'Загрузка объектов - "{filename[filename.rindex("/") + 1:]}"')
        logger.info(f"Открыт файл для вставки: {filename}, {dataframe.shape[0]} объектов")

        self._table_axes: List[str] = ["Загрузить"] + list(dataframe.axes[1])
        self._table_model = QtGui.QStandardItemModel(*dataframe.shape)
        self._table_model.setHorizontalHeaderLabels(list(self._table_axes))
        for i, service in dataframe.iterrows():
            for j, data in enumerate(service, 1):
                self._table_model.setItem(
                    i, j, QtGui.QStandardItem(data if isinstance(data, str) else str(data) if data is not None else "")
                )
            ok_item = QtGui.QStandardItem("+")
            ok_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self._table_model.setItem(i, 0, ok_item)
            self._table_model.item(i, 0).setBackground(CheckableTableView.colorTable.on)
            self._table_model.item(i, 0).setForeground(QtCore.Qt.black)

        field: QtWidgets.QComboBox
        for field in itertools.chain(
            self._document_fields,
            (self._properties_group.itemAtPosition(i + 2, 1).widget() for i in range(self._properties_cnt)),
        ):
            previous_text = field.currentText()
            field.clear()
            field.addItem("-")
            field.addItems(self._table_axes[1:])
            if previous_text in self._table_axes:
                field.setCurrentIndex(self._table_axes.index(previous_text))
            field.setEnabled(True)
        for field, default_value in zip(self._document_fields, InsertionWindow.default_values[2:]):
            if field.currentIndex() == 0 and default_value in self._table_axes:
                field.setCurrentIndex(self._table_axes.index(default_value))

        if self._table is None:
            self._table = CheckableTableView()
            self._left.insertWidget(0, self._table)

        self._load_objects_btn.setVisible(True)
        self._save_results_btn.setVisible(False)

        self.on_document_change()
        self.on_prefix_check()

        self._table.setModel(self._table_model)
        self._table.horizontalHeader().setMinimumSectionSize(0)
        self._table.resizeColumnsToContents()

    def table_as_dataframe(self, include_all: bool = True) -> pd.DataFrame:
        lines: List[List[Any]] = []
        index: List[int] = []
        for row in range(self._table_model.rowCount()):
            if include_all or self._table_model.index(row, 0).data() == "+":
                lines.append([])
                index.append(row)
                lines[-1].append("1" if self._table_model.index(row, 0).data() == "+" else "0")
                for col in range(self._table_model.columnCount())[1:]:
                    lines[-1].append(self._table_model.index(row, col).data())
        dataframe = pd.DataFrame(lines, columns=self._table_axes, index=index)
        return dataframe

    def on_upload_objects(self) -> None:
        self._load_objects_btn.setEnabled(False)
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.BusyCursor)
        verbose = not bool(QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.ShiftModifier)
        is_commit = not bool(QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.ControlModifier)
        try:
            results = insert_services_cli.add_services(
                self._db_properties.conn,
                self.table_as_dataframe(False),
                self._options_fields.city.currentText(),
                self._options_fields.service_type.currentText(),
                insert_services_cli.ServiceInsertionMapping.init(
                    self._document_fields.latitude.currentText(),
                    self._document_fields.longitude.currentText(),
                    self._document_fields.geometry.currentText(),
                    self._document_fields.name.currentText(),
                    self._document_fields.opening_hours.currentText(),
                    self._document_fields.website.currentText(),
                    self._document_fields.phone.currentText(),
                    self._document_fields.address.currentText(),
                    self._document_fields.osm_id.currentText(),
                    self._document_fields.capacity.currentText(),
                ),
                {
                    self._properties_group.itemAtPosition(i + 2, 0)
                    .widget()
                    .text(): self._properties_group.itemAtPosition(i + 2, 1)
                    .widget()
                    .currentText()
                    for i in range(self._properties_cnt)
                    if self._properties_group.itemAtPosition(i + 2, 1).widget().currentIndex() > 0
                },
                list(map(lambda line_edit: line_edit.text(), self._document_address_prefixes)),
                self._prefixes_group.itemAt(self._prefixes_group.count() - 1).widget().text(),  # type: ignore
                is_commit,
                verbose,
            )
            if not is_commit:
                self._db_properties.conn.rollback()
        except psycopg2.OperationalError:
            QtWidgets.QMessageBox.critical(
                self,
                "Ошибка при загрузке",
                "Произошла ошибка при загрузке объектов в базу\nВозможны проблемы с подключением к базе",
            )
            return
        except Exception as exc:  # pylint: disable=broad-except
            QtWidgets.QMessageBox.critical(
                self, "Ошибка при загрузке", f"Произошла ошибка при загрузке объектов в базу\n{exc!r}"
            )
            traceback.print_exc()
            return
        finally:
            self._load_objects_btn.setEnabled(True)
            QtWidgets.QApplication.restoreOverrideCursor()  # TODO ?
        dataframe = self.table_as_dataframe().join(results[["result", "functional_obj_id"]]).fillna("")
        self._table_axes += ["Результат", "id Функционального объекта"]
        self._table_model.appendColumn(list(map(QtGui.QStandardItem, dataframe["result"])))
        self._table_model.appendColumn(
            list(
                map(
                    lambda text: QtGui.QStandardItem(str(int(text)) if isinstance(text, (int, float)) else ""),
                    dataframe["functional_obj_id"],
                )
            )
        )
        self._table_model.setHorizontalHeaderLabels(self._table_axes)
        self._table.resizeColumnToContents(len(self._table_axes) - 2)  # type: ignore
        self._table.resizeColumnToContents(len(self._table_axes) - 1)  # type: ignore
        for row in range(self._table_model.rowCount()):
            self._table_model.item(row, len(self._table_axes) - 2).setBackground(InsertionWindow.colorTable.sky_blue)
            self._table_model.item(row, len(self._table_axes) - 1).setBackground(InsertionWindow.colorTable.sky_blue)
            self._table_model.item(row, len(self._table_axes) - 2).setForeground(QtCore.Qt.black)
            self._table_model.item(row, len(self._table_axes) - 1).setForeground(QtCore.Qt.black)
            self._table_model.item(row, len(self._table_axes) - 1).setFlags(QtCore.Qt.ItemIsEnabled)
            self._table_model.item(row, len(self._table_axes) - 2).setFlags(QtCore.Qt.ItemIsEnabled)
        self._save_results_btn.setVisible(True)

    def on_export_results(self) -> None:
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
        filename: str = self.windowTitle()[self.windowTitle().index('"') + 1 : self.windowTitle().rindex('"')]
        t = time.localtime()  # pylint: disable=invalid-name
        logfile = (
            f"{t.tm_year}-{t.tm_mon:02}-{t.tm_mday:02} "
            f'{t.tm_hour:02}-{t.tm_min:02}-{t.tm_sec:02}-{filename[:filename.rindex(".")]}'
        )
        file_dialog.selectNameFilter("CSV files (*.csv)")
        file_dialog.selectFile(logfile)
        if file_dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        filename = file_dialog.selectedFiles()[0]
        file_format = file_dialog.selectedNameFilter()[file_dialog.selectedNameFilter().rfind(".") : -1]
        if not filename.endswith(file_format):
            filename += file_format
        dataframe = self.table_as_dataframe()
        save_func = pd.DataFrame.to_csv if filename[filename.rfind(".") + 1 :] == "csv" else pd.DataFrame.to_excel
        save_func(dataframe, filename, index=False)

    def on_prefix_add(self) -> None:
        self._document_address_prefixes.append(ColorizingLine(self.on_prefix_check))
        self._prefixes_group.insertWidget(self._prefixes_group.count() - 4, self._document_address_prefixes[-1])
        if len(self._document_address_prefixes) == 2:
            self._address_prefix_remove_btn.setEnabled(True)
        self.on_prefix_check()

    def on_prefix_remove(self) -> None:
        self._document_address_prefixes.pop()
        widget = self._prefixes_group.itemAt(self._prefixes_group.count() - 5).widget()
        widget.setVisible(False)
        self._prefixes_group.removeWidget(widget)
        if len(self._document_address_prefixes) == 1:
            self._address_prefix_remove_btn.setEnabled(False)
        self.on_prefix_check()

    def on_prefix_check(self, _: Optional[Any] = None, __: Optional[Any] = None) -> None:
        res = 0
        if self._document_fields.address.currentIndex() != 0:
            col = self._document_fields.address.currentIndex()
            for row in range(self._table_model.rowCount()):
                found = False
                for prefix in self._document_address_prefixes:
                    if str(self._table_model.index(row, col).data()).startswith(prefix.text()):
                        self._table_model.item(row, col).setBackground(InsertionWindow.colorTable.dark_green)
                        self._table_model.item(row, col).setForeground(QtGui.QColor.fromRgb(0, 0, 0))
                        found = True
                        break
                if found:
                    res += 1
                else:
                    self._table_model.item(row, col).setBackground(InsertionWindow.colorTable.dark_red)
                    self._table_model.item(row, col).setForeground(QtGui.QColor.fromRgb(0, 0, 0))
        if self._table is not None:
            self._prefixes_group_box.setTitle(
                f"Префиксы адреса ({res} / {self._table_model.rowCount()}))"
            )  # )) = ) , magic

    def on_options_change(
        self,
        what_changed: Optional[Union[QtWidgets.QLineEdit, QtWidgets.QComboBox]] = None,
        _previous_value: Optional[Union[int, str]] = None,
    ):
        allowed_chars = set((chr(i) for i in range(ord("a"), ord("z") + 1))) | {"_"}
        self._is_options_ok = True

        if what_changed is self._options_fields.service_type:
            old_is_building = self._options_fields.is_building.isChecked()
            if self._options_fields.service_type.currentText() in self._service_type_params:
                service = self._service_type_params[self._options_fields.service_type.currentText()]
                self._options_fields.service_code.setText(service[0])
                self._options_fields.is_building.setChecked(service[3])
                self._options_fields.city_function.setCurrentText(service[4])
                self._options_fields.service_type.setStyleSheet(
                    "background-color: rgb({}, {}, {});color: black".format(
                        *InsertionWindow.colorTable.light_green.getRgb()[:3]
                    )
                )
                while self._properties_cnt > 0:
                    self.on_property_delete()
                properties_available = insert_services_cli.get_properties_keys(
                    self._db_properties.conn, self._options_fields.service_type.currentText()
                )
                for functional_object_property in properties_available:
                    self.on_property_add(functional_object_property)
            else:
                self._options_fields.service_code.setText("")
                self._options_fields.is_building.setChecked(False)
                self._options_fields.city_function.setCurrentIndex(0)
                if what_changed is not None:
                    what_changed.setStyleSheet(
                        "background-color: rgb({}, {}, {});color: black".format(
                            *InsertionWindow.colorTable.light_red.getRgb()[:3]
                        )
                    )
            if old_is_building != self._options_fields.is_building.isChecked():
                self.on_document_change(self._document_fields.address)

        if (
            self._options_fields.service_code.text() != ""
            and len(set(self._options_fields.service_code.text()) - allowed_chars - {"-"}) == 0
        ):
            self._options_fields.service_code.setStyleSheet(
                "background-color: rgb({}, {}, {});color: black".format(
                    *InsertionWindow.colorTable.light_green.getRgb()[:3]
                )
            )
        else:
            self._is_options_ok = False
            self._options_fields.service_code.setStyleSheet(
                "background-color: rgb({}, {}, {});color: black".format(
                    *InsertionWindow.colorTable.light_red.getRgb()[:3]
                )
            )

        if self._options_fields.city_function.currentIndex() == 0:
            self._is_options_ok = False
            self._options_fields.city_function.setStyleSheet(
                "background-color: rgb({}, {}, {});color: black".format(
                    *InsertionWindow.colorTable.light_red.getRgb()[:3]
                )
            )
        else:
            self._options_fields.city_function.setStyleSheet(
                "background-color: rgb({}, {}, {});color: black".format(
                    *InsertionWindow.colorTable.light_green.getRgb()[:3]
                )
            )

        for line in (self._properties_group.itemAtPosition(i + 2, 0).widget() for i in range(1, self._properties_cnt)):
            if len(line.text()) == 0 or len(set(line.text()) - allowed_chars - {"-", "_"}) != 0:
                self._is_options_ok = False
                line.setStyleSheet(
                    "background-color: rgb({}, {}, {})".format(*InsertionWindow.colorTable.light_red.getRgb()[:3])
                )
            else:
                line.setStyleSheet("")

        if self._is_options_ok and self._is_document_ok:
            self._load_objects_btn.setEnabled(True)
        else:
            self._load_objects_btn.setEnabled(False)

    def on_document_change(
        self, what_changed: Optional[QtWidgets.QComboBox] = None, previous_value: Optional[int] = None
    ) -> None:
        logger.debug(
            "on_document_changed called with what_changed argument ({}), previous_value ({})",
            what_changed,
            previous_value,
        )
        self._is_document_ok = True
        if self._table is None:
            return
        if what_changed is not None and what_changed.currentIndex() > 0:
            if what_changed is self._document_fields.address:
                self.on_prefix_check()
            else:
                what_changed.setStyleSheet("")
                col = what_changed.currentIndex()
                if col > 0:
                    for row in range(self._table_model.rowCount()):
                        self._table_model.item(row, col).setBackground(InsertionWindow.colorTable.light_green)
                        self._table_model.item(row, col).setForeground(QtCore.Qt.black)

        if previous_value is not None and previous_value != 0:
            if previous_value == self._document_fields.address.currentIndex():
                self.on_prefix_check()
            else:
                is_used = False
                field: QtWidgets.QComboBox
                for field in self._document_fields:
                    if field.currentIndex() == previous_value:
                        is_used = True
                if not is_used:
                    col = previous_value
                    for row in range(self._table_model.rowCount()):
                        item = self._table_model.item(row, col)
                        if item is None:
                            break
                        item.setBackground(QtGui.QColor(QtCore.Qt.white))

        for field in self._document_fields:
            if field.currentIndex() == 0:
                if field is self._document_fields.address and self._options_fields.is_building.isChecked():
                    field.setStyleSheet(
                        "background-color: rgb({}, {}, {});color: black".format(
                            *InsertionWindow.colorTable.yellow.getRgb()[:3]
                        )
                    )
                elif not (
                    (
                        (field is self._document_fields.latitude or field is self._document_fields.longitude)
                        and self._document_fields.geometry.currentIndex() == 0
                    )
                    or (
                        field is self._document_fields.geometry
                        and (
                            self._document_fields.latitude.currentIndex() == 0
                            or self._document_fields.longitude.currentIndex() == 0
                        )
                    )
                ):
                    field.setStyleSheet(
                        "background-color: rgb({}, {}, {});color: black".format(
                            *InsertionWindow.colorTable.grey.getRgb()[:3]
                        )
                    )
                else:
                    field.setStyleSheet(
                        "background-color: rgb({}, {}, {});color: black".format(
                            *InsertionWindow.colorTable.light_red.getRgb()[:3]
                        )
                    )
                    self._is_document_ok = False
            elif field is not self._document_fields.address:
                field.setStyleSheet("")
                col = field.currentIndex()
                if col > 0:
                    color = InsertionWindow.colorTable.light_green
                    for field_inner in self._document_fields:
                        if field_inner is not field and field_inner.currentIndex() == col:
                            color = InsertionWindow.colorTable.grey
                    for row in range(self._table_model.rowCount()):
                        if self._table_model.item(row, col) is None:
                            logger.debug(f"Table {row}, {col} is None")
                            continue
                        self._table_model.item(row, col).setBackground(color)
                        self._table_model.item(row, col).setForeground(QtCore.Qt.black)

            else:
                field.setStyleSheet(
                    "background-color: rgb({}, {}, {});color: black".format(
                        *InsertionWindow.colorTable.grey.getRgb()[:3]
                    )
                )
        if self._is_options_ok and self._is_document_ok:
            self._load_objects_btn.setEnabled(True)
        else:
            self._load_objects_btn.setEnabled(False)

    def on_property_add(self, db_name: Optional[str] = None) -> None:
        self._properties_group.addWidget(ColorizingLine(self.on_options_change), self._properties_cnt + 2, 0)
        property_box = ColorizingComboBox(self.on_document_change)
        property_box.addItem("-")
        if self._table is not None:
            property_box.addItems(self._table_axes[1:])
        self._properties_group.addWidget(property_box, self._properties_cnt + 2, 1)
        self.on_document_change(self._properties_group.itemAtPosition(self._properties_cnt + 2, 1).widget())
        if isinstance(db_name, str):
            self._properties_group.itemAtPosition(self._properties_cnt + 2, 0).widget().setText(db_name)
        self._properties_cnt += 1
        if self._properties_cnt == 1:
            self._properties_group.itemAtPosition(1, 0).widget().setVisible(True)
            self._properties_group.itemAtPosition(1, 1).widget().setVisible(True)
            self._property_delete_btn.setEnabled(True)
        self.on_options_change()

    def on_property_delete(self) -> None:
        self._properties_cnt -= 1
        widget: ColorizingComboBox = self._properties_group.itemAtPosition(self._properties_cnt + 2, 1).widget()
        if self._table is not None:
            old_text = widget.currentText()
            widget.setCurrentIndex(0)
            self.on_document_change(widget, old_text)
        widget.setVisible(False)
        self._properties_group.removeWidget(widget)

        widget = self._properties_group.itemAtPosition(self._properties_cnt + 2, 0).widget()
        widget.setVisible(False)
        self._properties_group.removeWidget(widget)

        if self._properties_cnt == 0:
            self._properties_group.itemAtPosition(1, 0).widget().setVisible(False)
            self._properties_group.itemAtPosition(1, 1).widget().setVisible(False)
            self._property_delete_btn.setEnabled(False)
        self.on_options_change()

    def set_cities(self, cities: Iterable[str]):
        cities = list(cities)
        current_city = self._options_fields.city.currentText()
        self._options_fields.city.clear()
        if len(cities) == 0:
            self._options_fields.city.addItem("(Нет городов)")
        else:
            self._options_fields.city.addItems(cities)
            if current_city in cities:
                self._options_fields.city.setCurrentText(current_city)
            self._options_fields.city.view().setMinimumWidth(len(max(cities, key=len)) * 8)

    def set_city_functions(self, city_functions_list: List[str]) -> None:
        current_city_function = self._options_fields.city_function.currentText()
        self._options_fields.city_function.clear()
        self._options_fields.city_function.addItem("(не выбрано)")
        self._options_fields.city_function.addItems(city_functions_list)
        if current_city_function in city_functions_list:
            self._options_fields.city_function.setCurrentText(current_city_function)
        self._options_fields.city_function.view().setMinimumWidth(len(max(city_functions_list, key=len)) * 8)

    def set_service_types_params(self, service_types_params: Dict[str, Tuple[str, int, int, bool, str]]):
        self._service_type_params = service_types_params
        current_service_type = self._options_fields.service_type.currentText()
        self._options_fields.service_type.clear()
        self._options_fields.service_type.addItem("(не выбрано)")
        self._options_fields.service_type.addItems(sorted(self._service_type_params.keys()))
        if current_service_type in service_types_params:
            self._options_fields.service_type.setCurrentText(current_service_type)
        self._options_fields.service_type.view().setMinimumWidth(
            len(max(self._service_type_params.keys(), key=len)) * 8
        )

    def change_db(self, db_addr: str, db_port: int, db_name: str, db_user: str, db_pass: str) -> None:
        self._db_properties.reopen(db_addr, db_port, db_name, db_user, db_pass)

    def showEvent(self, event: QtGui.QShowEvent) -> None:  # pylint: disable=invalid-name
        logger.info("Открыто окно вставки сервисов")
        return super().showEvent(event)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # pylint: disable=invalid-name
        logger.info("Закрыто окно вставки сервисов")
        if self._on_close is not None:
            self._on_close()
        return super().closeEvent(event)
