"""Initial credentials window logic is defined here."""
from __future__ import annotations

import itertools
import traceback
from typing import NamedTuple

from loguru import logger
from PySide6 import QtCore, QtGui, QtWidgets

from platform_management.database_properties import Properties
from platform_management.gui.insert_services import ServicesInsertionWindow
from platform_management.gui.manipulate_cities import CitiesWindow
from platform_management.gui.manipulate_regions import RegionsWindow
from platform_management.gui.update_buildings import BuildingsUpdatingWindow
from platform_management.gui.update_services import ServicesUpdatingWindow

from .app import get_application

InitWindowDefaultValues = NamedTuple(
    "InitWindowDefaultValues",
    [("db_address", str), ("db_port", int), ("db_name", str), ("db_user", str), ("db_pass", str)],
)


def get_init_window_default_values() -> InitWindowDefaultValues:
    """Get default values fot credentials window."""
    return InitWindowDefaultValues("127.0.0.1", 5432, "city_db_final", "postgres", "postgres")


class InitWindow(QtWidgets.QWidget):  # pylint: disable=too-many-instance-attributes
    """Credentials window with links to the other application parts."""

    DatabaseFields = NamedTuple(
        "DatabaseFields",
        [
            ("address", QtWidgets.QLineEdit),
            ("name", QtWidgets.QLineEdit),
            ("user", QtWidgets.QLineEdit),
            ("password", QtWidgets.QLineEdit),
        ],
    )

    default_values = get_init_window_default_values()

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._was_first_open = False

        self._db_properties = Properties(
            InitWindow.default_values.db_address,
            InitWindow.default_values.db_port,
            InitWindow.default_values.db_name,
            InitWindow.default_values.db_user,
            InitWindow.default_values.db_pass,
        )

        logger.debug("Creating insertion window")
        self._insertion_window = ServicesInsertionWindow(self._db_properties.copy(), self._on_restart)
        logger.debug("Creating services updating window")
        self._services_updating_window = ServicesUpdatingWindow(self._db_properties.copy(), self._on_restart)
        logger.debug("Creating buildings updating window")
        self._buildings_updating_window = BuildingsUpdatingWindow(self._db_properties.copy(), self._on_restart)
        logger.debug("Creating cities manipulation window")
        self._cities_window = CitiesWindow(self._db_properties.copy(), self._on_restart)
        logger.debug("Creating regions manipulation window")
        self._regions_window = RegionsWindow(self._db_properties.copy(), self._on_restart)

        self._layout = QtWidgets.QHBoxLayout()
        self.setLayout(self._layout)

        self._db_group_box = QtWidgets.QGroupBox("База данных")
        self._db_group = QtWidgets.QFormLayout()
        self._db_group_box.setLayout(self._db_group)
        self._database_fields = InitWindow.DatabaseFields(*(QtWidgets.QLineEdit() for _ in range(4)))
        self._database_fields.password.setEchoMode(QtWidgets.QLineEdit.Password)
        self._db_group.addRow("Адрес:", self._database_fields.address)
        self._db_group.addRow("База:", self._database_fields.name)
        self._db_group.addRow("Пользователь:", self._database_fields.user)
        self._db_group.addRow("Пароль:", self._database_fields.password)
        self._db_check_btn = QtWidgets.QPushButton("&Подключиться к БД")
        self._db_check_btn.clicked.connect(self.on_connection_check)
        self._db_check_res = QtWidgets.QLabel("?")
        self._db_group.addRow(self._db_check_btn, self._db_check_res)
        self._layout.addWidget(self._db_group_box)

        self._right = QtWidgets.QVBoxLayout()
        self._layout.addLayout(self._right)
        self._variants = QtWidgets.QButtonGroup()
        self._variants.addButton(QtWidgets.QRadioButton("&Загрузка сервисов"), 0)
        self._variants.addButton(QtWidgets.QRadioButton("Изменение &сервисов"), 1)
        self._variants.addButton(QtWidgets.QRadioButton("Изменение &зданий"), 2)
        self._variants.addButton(QtWidgets.QRadioButton("Операции с &городами"), 3)
        self._variants.addButton(QtWidgets.QRadioButton("Операции с &регионами"), 4)
        self._variants.button(0).setChecked(True)
        for btn_n in range(5):
            self._right.addWidget(self._variants.button(btn_n))

        self._launch_btn = QtWidgets.QPushButton("З&апуск")
        self._launch_btn.clicked.connect(self._on_launch)
        self._launch_btn.setEnabled(False)
        self._right.addWidget(self._launch_btn)

        self._database_fields.address.setText(
            f"{InitWindow.default_values.db_address}:{InitWindow.default_values.db_port}"
        )
        self._database_fields.name.setText(InitWindow.default_values.db_name)
        self._database_fields.user.setText(InitWindow.default_values.db_user)
        self._database_fields.password.setText(InitWindow.default_values.db_pass)

        self.setFixedWidth(self.sizeHint().width())
        self.setFixedHeight(self.sizeHint().height())

    def on_connection_check(self, refresh: bool = False) -> None:
        """Update connection if the credentials have changed, update sumbodules additional connections information

        Method is executed on click on connect button.
        """
        logger.debug("on_connection_check called")
        host, port_str = (self._database_fields.address.text().split(":") + [str(InitWindow.default_values.db_port)])[
            0:2
        ]
        try:
            port = int(port_str)
        except ValueError:
            self._db_check_res.setText("<b style=color:red;>x</b>")
            return
        if (
            self._db_properties.db_addr == host
            and self._db_properties.db_port == port
            and self._db_properties.db_name == self._database_fields.name.text()
            and self._db_properties.db_user == self._database_fields.user.text()
            and self._db_properties.db_pass == self._database_fields.password.text()
        ):
            logger.debug("Connection didn't change")
        else:
            logger.debug("Reopening the connection")
            self._db_properties.reopen(
                host,
                port,
                self._database_fields.name.text(),
                self._database_fields.user.text(),
                self._database_fields.password.text(),
            )
            logger.debug("Connection reopened")
        try:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.BusyCursor)
            self._db_check_res.setText("<b style=color:pink;>o</b>")
            self.repaint()
            with self._db_properties.conn, self._db_properties.conn.cursor() as cur:
                cur.execute("SELECT 1")
                assert cur.fetchone()[0] == 1, "cannot connect to the database"  # type: ignore
                for func in (
                    self._insertion_window.change_db,
                    self._services_updating_window.change_db,
                    self._buildings_updating_window.change_db,
                    self._cities_window.change_db,
                    self._regions_window.change_db,
                ):
                    func(
                        self._db_properties.db_addr,
                        self._db_properties.db_port,
                        self._db_properties.db_name,
                        self._db_properties.db_user,
                        self._db_properties.db_pass,
                    )

                cur.execute("SELECT name FROM cities ORDER BY population DESC")
                cities = list(itertools.chain.from_iterable(cur.fetchall()))
                self._insertion_window.set_cities(cities)
                self._services_updating_window.set_cities(cities)
                self._buildings_updating_window.set_cities(cities)

                cur.execute("SELECT name FROM city_functions ORDER BY 1")
                items = list(itertools.chain.from_iterable(cur.fetchall()))
                self._insertion_window.set_city_functions(items)

                cur.execute(
                    "SELECT st.name, st.code, st.capacity_min, st.capacity_max, st.is_building, cf.name"
                    " FROM city_service_types st"
                    "   JOIN city_functions cf on st.city_function_id = cf.id"
                    " ORDER BY 1"
                )
                service_types_params = dict(map(lambda x: (x[0], tuple(x[1:])), cur.fetchall()))
                self._insertion_window.set_service_types_params(service_types_params)  # type: ignore

            self._launch_btn.setEnabled(True)
        except Exception as exc:  # pylint: disable=broad-except
            self._db_properties.close()
            self._launch_btn.setEnabled(False)
            logger.error(f"Ошибка подключения к базе данных: {exc}")
            logger.debug(f"Стек ошибок: {traceback.format_exc()}")
            if QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.ShiftModifier:
                QtWidgets.QMessageBox.critical(self, "Ошибка при попытке подключиться к БД", traceback.format_exc())
            self._db_check_res.setText("<b style=color:red;>x</b>")
        else:
            self._db_check_res.setText("<b style=color:green;>v</b>")
            if not refresh:
                logger.opt(colors=True).info(
                    "Установлено подключение к базе данных:"
                    f" <cyan>{self._db_properties.db_user}@{self._db_properties.db_addr}:"
                    f"{self._db_properties.db_port}/{self._db_properties.db_name}</cyan>"
                )
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    def _on_launch(self):
        self.hide()
        app = get_application()
        if self._variants.checkedId() == 0:
            app.setApplicationDisplayName("Загрузка сервисов")
            self._insertion_window.show()
        elif self._variants.checkedId() == 1:
            app.setApplicationDisplayName("Изменение сервисов")
            self._services_updating_window.show()
        elif self._variants.checkedId() == 2:
            app.setApplicationDisplayName("Изменение зданий")
            self._buildings_updating_window.show()
        elif self._variants.checkedId() == 3:
            app.setApplicationDisplayName("Операции с городами")
            self._cities_window.show()
        else:
            app.setApplicationDisplayName("Операции с регионами")
            self._regions_window.show()

    def _on_restart(self):
        self._insertion_window.hide()
        self._services_updating_window.hide()
        self._buildings_updating_window.hide()
        self._cities_window.hide()
        self._regions_window.hide()
        self.show()
        self.on_connection_check(True)

    def showEvent(self, event: QtGui.QShowEvent) -> None:  # pylint: disable=invalid-name
        """Log application open"""
        if not self._was_first_open:
            logger.info("Открыто начальное окно работы с сервисами")
        self._was_first_open = True
        return super().showEvent(event)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # pylint: disable=invalid-name
        """Log application close."""
        if not any(
            window.isVisible()
            for window in (
                self._cities_window,
                self._regions_window,
                self._insertion_window,
                self._insertion_window,
                self._services_updating_window,
                self._buildings_updating_window,
            )
        ):
            logger.info("Закрыто начальное окно работы с сервисами")
        return super().closeEvent(event)
