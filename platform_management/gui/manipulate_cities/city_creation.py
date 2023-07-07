"""City creation widget is defined here."""
from typing import Literal

from PySide6 import QtWidgets

from platform_management.utils.converters import int_or_none, str_or_none, to_str


class CityCreationWidget(QtWidgets.QDialog):
    """City creation window."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        text: str,
        regions: list[str],
        geometry: str | None = None,
        name: str | None = None,
        code: str | None = None,
        region: str | None = None,
        population: int | None = None,
        division_type: Literal["NO_PARENT", "ADMIN_UNIT_PARENT", "MUNICIPALITY_PARENT"] | None = None,
        is_adding: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ):
        super().__init__(parent=parent)
        self.window().setWindowTitle("Добавление города" if is_adding else "Изменение города")
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel(text))
        self._geometry_field = QtWidgets.QTextEdit()
        self._geometry_field.setPlainText(geometry or "")
        self._geometry_field.setPlaceholderText('{\n  "type": "...",\n  "coordinates": [...]\n}')
        self._geometry_field.setAcceptRichText(False)
        layout.addWidget(self._geometry_field)
        self._options_layout = QtWidgets.QFormLayout()
        self._name = QtWidgets.QLineEdit(name or "")
        self._name.setPlaceholderText("Санкт-Петербург")
        self._options_layout.addRow("Название:", self._name)
        self._code = QtWidgets.QLineEdit(code or "")
        self._code.setPlaceholderText("saint-petersburg")
        self._region = QtWidgets.QComboBox()
        self._region.addItems([None] + regions)
        if region is not None:
            self._region.setCurrentText(region)
        self._options_layout.addRow("Регион:", self._region)
        self._options_layout.addRow("Код:", self._code)
        self._population = QtWidgets.QLineEdit(to_str(population))
        self._population.setPlaceholderText("6000000")
        self._options_layout.addRow("Население:", self._population)
        self._division_type = QtWidgets.QComboBox()
        self._division_type.addItems(["NO_PARENT", "ADMIN_UNIT_PARENT", "MUNICIPALITY_PARENT"])
        if division_type is not None:
            self._division_type.setCurrentText(division_type)
        self._options_layout.addRow("Тип админ. деления:", self._division_type)
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

    def get_geometry(self) -> str | None:
        """Get geometry value set by user."""
        return str_or_none(self._geometry_field.toPlainText())

    def name(self) -> str | None:
        """Get city name value set by user."""
        return str_or_none(self._name.text())

    def code(self) -> str | None:
        """Get city code value set by user."""
        return str_or_none(self._code.text())

    def region(self) -> str | None:
        """Get city region value set by user."""
        return str_or_none(self._region.currentText())

    def population(self) -> int | None:
        """Get city population value set by user."""
        return int_or_none(self._population.text())

    def division_type(self) -> str:
        """Get city division type value set by user."""
        return self._division_type.currentText()
