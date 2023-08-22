"""Building creation widget is defined here."""
from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from platform_management.utils.converters import (
    bool_or_none,
    bool_to_checkstate,
    float_or_none,
    int_or_none,
    str_or_none,
    to_str,
)


class BuildingCreationWidget(QtWidgets.QDialog):  # pylint: disable=too-many-instance-attributes
    """Building creation window."""

    def __init__(  # pylint: disable=too-many-arguments,too-many-locals,too-many-statements
        self,
        text: str,
        geometry: str | None = None,
        osm_id: str | None = None,
        address: str | None = None,
        building_date: str | None = None,
        repair_years: str | None = None,
        building_area: float | None = None,
        living_area: float | None = None,
        storeys: int | None = None,
        lift_count: int | None = None,
        population: int | None = None,
        project_type: str | None = None,
        ukname: str | None = None,
        central_heating: bool | None = None,
        central_hotwater: bool | None = None,
        central_electricity: bool | None = None,
        central_gas: bool | None = None,
        refusechute: bool | None = None,
        is_failfing: bool | None = None,
        is_living: bool | None = None,
        is_adding: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ):
        super().__init__(parent=parent)
        self.window().setWindowTitle("Добавление здания" if is_adding else "Изменение здания")

        double_validator = QtGui.QDoubleValidator(0.0, 1000000.0, 4)
        double_validator.setLocale(QtCore.QLocale.English)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel(text))
        self._geometry_field = QtWidgets.QTextEdit()
        self._geometry_field.setPlainText(geometry or "")
        self._geometry_field.setPlaceholderText('{\n  "type": "...",\n  "coordinates": [...]\n}')
        self._geometry_field.setAcceptRichText(False)
        layout.addWidget(self._geometry_field)
        self._options_layout = QtWidgets.QFormLayout()
        self._osm_id = QtWidgets.QLineEdit(osm_id or "")
        self._osm_id.setPlaceholderText("5255196821")
        self._options_layout.addRow("OpenStreetMap id:", self._osm_id)
        self._address = QtWidgets.QLineEdit(address or "")
        self._address.setPlaceholderText("Город, улица, номер дома")
        self._options_layout.addRow("Адрес", self._address)
        self._building_date = QtWidgets.QLineEdit(building_date or "")
        self._building_date.setPlaceholderText("2001-2002")
        self._options_layout.addRow("Дата постройки", self._building_date)
        self._repair_years = QtWidgets.QLineEdit(repair_years or "")
        self._repair_years.setPlaceholderText("2003; 2007")
        self._options_layout.addRow("Года ремонта", self._repair_years)
        self._building_area = QtWidgets.QLineEdit(to_str(building_area))
        self._building_area.setPlaceholderText("123.45")
        self._building_area.setValidator(double_validator)
        self._options_layout.addRow("Площадь дома", self._building_area)
        self._building_area_living = QtWidgets.QLineEdit(to_str(living_area))
        self._building_area_living.setPlaceholderText("1234.5")
        self._building_area_living.setValidator(double_validator)
        self._options_layout.addRow("Общая жилая площадь", self._building_area_living)
        self._storeys = QtWidgets.QLineEdit(to_str(storeys))
        self._storeys.setPlaceholderText("8")
        self._storeys.setValidator(QtGui.QIntValidator(1, 100))
        self._options_layout.addRow("Этажность", self._storeys)
        self._lift_count = QtWidgets.QLineEdit(to_str(lift_count))
        self._lift_count.setPlaceholderText("4")
        self._options_layout.addRow("Количество лифтов", self._lift_count)
        self._population = QtWidgets.QLineEdit(to_str(population))
        self._population.setPlaceholderText("250")
        self._population.setValidator(QtGui.QIntValidator(0, 20000))
        self._options_layout.addRow("Население", self._population)
        self._project_type = QtWidgets.QLineEdit(project_type or "")
        self._project_type.setPlaceholderText("1ЛГ-602В-8")
        self._ukname = QtWidgets.QLineEdit(ukname or "")
        self._ukname.setPlaceholderText("ЖСК № 355")
        self._options_layout.addRow("Застройщик", self._ukname)
        self._central_heating = QtWidgets.QCheckBox()
        self._central_heating.setTristate(True)
        self._central_heating.setCheckState(bool_to_checkstate(central_heating))
        self._options_layout.addRow("Централизованное отопление", self._central_heating)
        self._central_coldwater = QtWidgets.QCheckBox()
        self._central_coldwater.setTristate(True)
        self._central_coldwater.setCheckState(bool_to_checkstate(central_hotwater))
        self._options_layout.addRow("Централизованная холодная вода", self._central_coldwater)
        self._central_hotwater = QtWidgets.QCheckBox()
        self._central_hotwater.setTristate(True)
        self._central_hotwater.setCheckState(bool_to_checkstate(central_hotwater))
        self._options_layout.addRow("Централизованная горячая вода", self._central_hotwater)
        self._central_electricity = QtWidgets.QCheckBox()
        self._central_electricity.setTristate(True)
        self._central_electricity.setCheckState(bool_to_checkstate(central_electricity))
        self._options_layout.addRow("Централизованное электричество", self._central_electricity)
        self._central_gas = QtWidgets.QCheckBox()
        self._central_gas.setTristate(True)
        self._central_gas.setCheckState(bool_to_checkstate(central_gas))
        self._options_layout.addRow("Централизованный газ", self._central_gas)
        self._refusechute = QtWidgets.QCheckBox()
        self._refusechute.setTristate(True)
        self._refusechute.setCheckState(bool_to_checkstate(refusechute))
        self._options_layout.addRow("Наличие мусоропровода", self._refusechute)
        self._is_failing = QtWidgets.QCheckBox()
        self._is_failing.setTristate(True)
        self._is_failing.setCheckState(bool_to_checkstate(is_failfing))
        self._options_layout.addRow("Аварийное состояние", self._is_failing)
        self._is_living = QtWidgets.QCheckBox()
        self._is_living.setTristate(True)
        self._is_living.setCheckState(bool_to_checkstate(is_living))
        self._options_layout.addRow("Жилой дом", self._is_living)
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

    def osm_id(self) -> str | None:
        """Get osm_id value set by user."""
        return str_or_none(self._osm_id.text())

    def get_geometry(self) -> str | None:
        """Get geometry value set by user."""
        return str_or_none(self._geometry_field.toPlainText())

    def address(self) -> str | None:
        """Get address value set by user."""
        return str_or_none(self._address.text())

    def building_date(self) -> str | None:
        """Get building date set by user."""
        return str_or_none(self._building_date.text())

    def repair_years(self) -> str | None:
        """Get repair years value set by user"""
        return str_or_none(self._repair_years.text())

    def building_area(self) -> float | None:
        """Get building area value set by user"""
        return float_or_none(self._building_area.text())

    def building_area_living(self) -> float | None:
        """Get living area value set by user"""
        return float_or_none(self._building_area_living.text())

    def storeys(self) -> int | None:
        """Get storeys count value set by user"""
        return int_or_none(self._storeys.text())

    def lift_count(self) -> int | None:
        """Get lift count value set by user"""
        return int_or_none(self._lift_count.text())

    def population(self) -> int | None:
        """Get population value set by user"""
        return int_or_none(self._population.text())

    def project_type(self) -> str | None:
        """Get project type value set by user"""
        return str_or_none(self._project_type.text())

    def ukname(self) -> str | None:
        """Get house managing company name value set by user"""
        return str_or_none(self._ukname.text())

    def central_heating(self) -> bool | None:
        """Get central heating availability value set by user"""
        return bool_or_none(self._central_heating.checkState())

    def central_coldwater(self) -> bool | None:
        """Get cold water availability value set by user"""
        return bool_or_none(self._central_coldwater.checkState())

    def central_hotwater(self) -> bool | None:
        """Get hot water availability value set by user"""
        return bool_or_none(self._central_hotwater.checkState())

    def central_electricity(self) -> bool | None:
        """Get central electricity availability value set by user"""
        return bool_or_none(self._central_electricity.checkState())

    def central_gas(self) -> bool | None:
        """Get central gas availability value set by user"""
        return bool_or_none(self._central_gas.checkState())

    def refusechute(self) -> bool | None:
        """Get refusechute availability value set by user"""
        return bool_or_none(self._refusechute.checkState())

    def is_failing(self) -> bool | None:
        """Get is_failing value set by user"""
        return bool_or_none(self._is_failing.checkState())

    def is_living(self) -> bool | None:
        """Get is_living value set by user"""
        return bool_or_none(self._is_living.checkState())
