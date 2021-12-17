import itertools
import traceback
import logging
from typing import NamedTuple, Optional

from PySide6 import QtCore, QtGui, QtWidgets

log = logging.getLogger('services_manipulation')
log.addHandler(logging.FileHandler('services_manipulation.log', 'a', 'utf8'))
log.handlers[-1].setFormatter(logging.Formatter('{asctime} [{name}]: {message}', datefmt='%Y-%m-%d %H:%M:%S', style='{'))
log.handlers[-1].setLevel('INFO')
log.addHandler(logging.StreamHandler())
log.handlers[-1].setFormatter(logging.Formatter('{asctime} [{name}]: {message}', datefmt='%Y-%m-%d %H:%M:%S', style='{'))
log.handlers[-1].setLevel('DEBUG')
log.setLevel('DEBUG')

from database_properties import Properties
from gui_insert_services import InsertionWindow
from gui_update_services import UpdatingWindow
from gui_manipulate_cities import CitiesWindow

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

        self._insertion_window = InsertionWindow(self._db_properties.copy(), self._on_restart)
        self._updating_window = UpdatingWindow(self._db_properties.copy(), self._on_restart)
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
        host, port_str = (self._database_fields.address.text().split(':') + [str(InitWindow.default_values.db_port)])[0:2]
        try:
            port = int(port_str)
        except ValueError:
            self._db_check_res.setText('<b style=color:red;>x</b>')
            return
        if not (self._db_properties.db_addr == host and self._db_properties.db_port == port and 
                self._db_properties.db_name == self._database_fields.name.text() and
                self._db_properties.db_user == self._database_fields.user.text() and
                self._db_properties.db_pass == self._database_fields.password.text()):
            self._db_properties.reopen(host, port, self._database_fields.name.text(),
                    self._database_fields.user.text(), self._database_fields.password.text())
        try:
            with self._db_properties.conn, self._db_properties.conn.cursor() as cur:
                cur.execute('SELECT 1')
                assert cur.fetchone()[0] == 1, 'cannot connect to the database'
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

                cur.execute('SELECT st.name, st.code, st.capacity_min, st.capacity_max, st.status_min,'
                        '       st.status_max, st.is_building, cf.name FROM city_service_types st'
                        '   JOIN city_functions cf on st.city_function_id = cf.id'
                        ' ORDER BY 1')
                service_types_params = dict(map(lambda x: (x[0], tuple(x[1:])), cur.fetchall()))
                self._insertion_window.set_service_types_params(service_types_params) # type: ignore
                
            self._insertion_window._options_fields.city_function.setEnabled(True)
            self._launch_btn.setEnabled(True)
        except Exception:
            self._db_properties.close()
            self._launch_btn.setEnabled(False)
            if QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.ShiftModifier:
                QtWidgets.QMessageBox.critical(self, 'Ошибка при попытке подключиться к БД', traceback.format_exc())
            self._db_check_res.setText('<b style=color:red;>x</b>')
        else:        
            self._db_check_res.setText('<b style=color:green;>v</b>')
            if not refresh:
                log.info('Установлено подключение к базе данных:'
                        f' {self._db_properties.db_user}@{self._db_properties.db_addr}:{self._db_properties.db_port}/{self._db_properties.db_name}')

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
            log.info('Открыто начальное окно работы с сервисами')
        self._was_first_open = True
        return super().showEvent(event)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if not self._insertion_window.isVisible() and not self._updating_window.isVisible():
            log.info('Закрыто начальное окно работы с сервисами')
        return super().closeEvent(event)


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    app.setWindowIcon(QtGui.QIcon(QtGui.QPixmap('icon.png')))
    app.setApplicationName('Работа с сервисами')

    window = InitWindow()
    window.show()

    exit(app.exec())
