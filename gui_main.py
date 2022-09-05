import itertools
import os
import sys
import traceback
from typing import NamedTuple, Optional

import click
from loguru import logger
from PySide6 import QtCore, QtGui, QtWidgets

from database_properties import Properties
from gui_insert_services import InsertionWindow
from gui_manipulate_cities import CitiesWindow
from gui_update_services import UpdatingWindow

InitWindowDefaultValues = NamedTuple('InitWindowDefaultValues', [
        ('db_address', str),
        ('db_port', int),
        ('db_name', str),
        ('db_user', str),
        ('db_pass', str)
    ]
)

def get_init_window_default_values() -> InitWindowDefaultValues:
    return InitWindowDefaultValues('127.0.0.1', 5432, 'city_db_final', 'postgres', 'postgres')

app: QtWidgets.QApplication
logger = logger.bind(name='gui_main')

class InitWindow(QtWidgets.QWidget):

    DatabaseFields = NamedTuple('DatabaseFields', [
            ('address', QtWidgets.QLineEdit),
            ('name', QtWidgets.QLineEdit),
            ('user', QtWidgets.QLineEdit),
            ('password', QtWidgets.QLineEdit)
        ]
    )

    default_values = get_init_window_default_values()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._was_first_open = False

        self._db_properties = Properties(InitWindow.default_values.db_address, InitWindow.default_values.db_port,
                InitWindow.default_values.db_name, InitWindow.default_values.db_user, InitWindow.default_values.db_pass)

        logger.debug('Creating insertion window')
        self._insertion_window = InsertionWindow(self._db_properties.copy(), self._on_restart)
        logger.debug('Creating updating window')
        self._updating_window = UpdatingWindow(self._db_properties.copy(), self._on_restart)
        logger.debug('Creating cities manipulation window')
        self._cities_window = CitiesWindow(self._db_properties.copy(), self._on_restart)

        self._layout = QtWidgets.QHBoxLayout()
        self.setLayout(self._layout)

        self._db_group_box = QtWidgets.QGroupBox('База данных')
        self._db_group = QtWidgets.QFormLayout()
        self._db_group_box.setLayout(self._db_group)
        self._database_fields = InitWindow.DatabaseFields(*(QtWidgets.QLineEdit() for _ in range(4)))
        self._database_fields.password.setEchoMode(QtWidgets.QLineEdit.Password)
        self._db_group.addRow('Адрес:', self._database_fields.address)
        self._db_group.addRow('База:', self._database_fields.name)
        self._db_group.addRow('Пользователь:', self._database_fields.user)
        self._db_group.addRow('Пароль:', self._database_fields.password)
        self._db_check_btn = QtWidgets.QPushButton('&Подключиться к БД')
        self._db_check_btn.clicked.connect(self.on_connection_check)
        self._db_check_res = QtWidgets.QLabel('?')
        self._db_group.addRow(self._db_check_btn, self._db_check_res)
        self._layout.addWidget(self._db_group_box)

        self._right = QtWidgets.QVBoxLayout()
        self._layout.addLayout(self._right)
        self._variants = QtWidgets.QButtonGroup()
        self._variants.addButton(QtWidgets.QRadioButton('&Загрузка сервисов'), 0)
        self._variants.addButton(QtWidgets.QRadioButton('&Изменение сервисов'), 1)
        self._variants.addButton(QtWidgets.QRadioButton('&Операции с городами'), 2)
        self._variants.button(0).setChecked(True)
        for btn_n in range(3):
            self._right.addWidget(self._variants.button(btn_n))

        self._launch_btn = QtWidgets.QPushButton('З&апуск')
        self._launch_btn.clicked.connect(self._on_launch)
        self._launch_btn.setEnabled(False)
        self._right.addWidget(self._launch_btn)

        self._database_fields.address.setText(f'{InitWindow.default_values.db_address}:{InitWindow.default_values.db_port}')
        self._database_fields.name.setText(InitWindow.default_values.db_name)
        self._database_fields.user.setText(InitWindow.default_values.db_user)
        self._database_fields.password.setText(InitWindow.default_values.db_pass)

        self.setFixedWidth(self.sizeHint().width())
        self.setFixedHeight(self.sizeHint().height())

    def on_connection_check(self, refresh: bool = False) -> None:
        logger.debug('on_connection_check called')
        host, port_str = (self._database_fields.address.text().split(':') + [str(InitWindow.default_values.db_port)])[0:2]
        try:
            port = int(port_str)
        except ValueError:
            self._db_check_res.setText('<b style=color:red;>x</b>')
            return
        if self._db_properties.db_addr == host and \
                self._db_properties.db_port == port and \
                self._db_properties.db_name == self._database_fields.name.text() and \
                self._db_properties.db_user == self._database_fields.user.text() and \
                self._db_properties.db_pass == self._database_fields.password.text():
            logger.debug('Connection didn\'t change')
        else:
            logger.debug('Reopening the connection')
            self._db_properties.reopen(host, port, self._database_fields.name.text(),
                    self._database_fields.user.text(), self._database_fields.password.text())
            logger.debug('Connection reopened')
        try:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.BusyCursor)
            self._db_check_res.setText('<b style=color:yellow;>o</b>')
            self.repaint()
            with self._db_properties.conn, self._db_properties.conn.cursor() as cur:
                cur.execute('SELECT 1')
                assert cur.fetchone()[0] == 1, 'cannot connect to the database' # type: ignore
                self._insertion_window.change_db(self._db_properties.db_addr, self._db_properties.db_port, self._db_properties.db_name,
                        self._db_properties.db_user, self._db_properties.db_pass)
                self._updating_window.change_db(self._db_properties.db_addr, self._db_properties.db_port, self._db_properties.db_name,
                        self._db_properties.db_user, self._db_properties.db_pass)
                self._cities_window.change_db(self._db_properties.db_addr, self._db_properties.db_port, self._db_properties.db_name,
                        self._db_properties.db_user, self._db_properties.db_pass)

                cur.execute('SELECT name FROM cities ORDER BY population DESC')
                cities = list(itertools.chain.from_iterable(cur.fetchall()))
                self._insertion_window.set_cities(cities)
                self._updating_window.set_cities(cities)

                cur.execute('SELECT name FROM city_functions ORDER BY 1')
                items = list(itertools.chain.from_iterable(cur.fetchall()))
                self._insertion_window.set_city_functions(items)

                cur.execute('SELECT st.name, st.code, st.capacity_min, st.capacity_max, st.is_building, cf.name FROM city_service_types st'
                        '   JOIN city_functions cf on st.city_function_id = cf.id'
                        ' ORDER BY 1')
                service_types_params = dict(map(lambda x: (x[0], tuple(x[1:])), cur.fetchall()))
                self._insertion_window.set_service_types_params(service_types_params) # type: ignore
                
            self._launch_btn.setEnabled(True)
        except Exception as ex:
            self._db_properties.close()
            self._launch_btn.setEnabled(False)
            logger.error(f'Ошибка подключения к базе данных: {ex}')
            logger.debug(f'Стек ошибок: {traceback.format_exc()}')
            if QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.ShiftModifier:
                QtWidgets.QMessageBox.critical(self, 'Ошибка при попытке подключиться к БД', traceback.format_exc())
            self._db_check_res.setText('<b style=color:red;>x</b>')
        else:        
            self._db_check_res.setText('<b style=color:green;>v</b>')
            if not refresh:
                logger.opt(colors=True).info('Установлено подключение к базе данных:'
                        f' <cyan>{self._db_properties.db_user}@{self._db_properties.db_addr}:{self._db_properties.db_port}/{self._db_properties.db_name}</cyan>')
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    def _on_launch(self):
        self.hide()
        if self._variants.checkedId() == 0:
            app.setApplicationDisplayName('Загрузка сервисов')
            self._insertion_window.show()
        elif self._variants.checkedId() == 1:
            app.setApplicationDisplayName('Изменение сервисов')
            self._updating_window.show()
        else:
            app.setApplicationDisplayName('Операции с городами')
            self._cities_window.show()

    def _on_restart(self):
        self._insertion_window.hide()
        self._updating_window.hide()
        self._cities_window.hide()
        self.show()
        self.on_connection_check(True)

    def showEvent(self, event: QtGui.QShowEvent) -> None:
        if not self._was_first_open:
            logger.info('Открыто начальное окно работы с сервисами')
        self._was_first_open = True
        return super().showEvent(event)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if not self._insertion_window.isVisible() and not self._updating_window.isVisible():
            logger.info('Закрыто начальное окно работы с сервисами')
        return super().closeEvent(event)


@click.command('IDU - Insert Services App GUI')
@click.option('--db_addr', '-H', envvar='DB_ADDR', help='Postgres DBMS address', default=InitWindow.default_values.db_address, show_default=True, show_envvar=True)
@click.option('--db_port', '-P', envvar='DB_PORT', type=int, help='Postgres DBMS port', default=InitWindow.default_values.db_port, show_default=True, show_envvar=True)
@click.option('--db_name', '-D', envvar='DB_NAME', help='Postgres city database name', default=InitWindow.default_values.db_name, show_default=True, show_envvar=True)
@click.option('--db_user', '-U', envvar='DB_USER', help='Postgres DBMS user name', default=InitWindow.default_values.db_user, show_default=True, show_envvar=True)
@click.option('--db_pass', '-W', envvar='DB_PASS', help='Postgres DBMS user password', default=InitWindow.default_values.db_pass, show_default=True, show_envvar=True)
@click.option('--verbose', '-v', envvar='VERBOSE', is_flag=True, help='Include debug information')
def main(db_addr: str, db_port: int, db_name: str, db_user: str, db_pass: str, verbose: bool):
    global app
    logger.debug('Starting the application')

    logger.remove(0)
    logger.add(sys.stderr, level = 'INFO' if not verbose else 'DEBUG',
            format='<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: ^8}</level> | <cyan>{extra[name]}:{line:03}</cyan> - <level>{message}</level>')

    InitWindow.default_values = InitWindowDefaultValues(db_addr, db_port, db_name, db_user, db_pass)

    app = QtWidgets.QApplication([])
    app.setWindowIcon(QtGui.QIcon(QtGui.QPixmap('icon.png')))
    app.setApplicationName('IDU - Insert Services App')

    window = InitWindow()
    window.show()

    exit(app.exec())

if __name__ == '__main__':
    if os.path.isfile('.env'):
        with open('.env', 'r') as f:
            for name, value in (tuple((line[len('export '):] if line.startswith('export ') else line).strip().split('=')) \
                        for line in f.readlines() if not line.startswith('#') and line != ''):
                if name not in os.environ:
                    os.environ[name] = value
    main()
