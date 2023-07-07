"""Territory creation widget is defined here."""
from frozenlist import FrozenList
from PySide6 import QtWidgets

from platform_management.utils.converters import int_or_none, str_or_none, to_str


class TerritoryCreationWidget(QtWidgets.QDialog):
    """Territory creation window."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        text: str,
        title: str,
        territory_types: list[str],
        parents: list[str] = FrozenList([]),
        geometry: str | None = None,
        name: str | None = None,
        population: int | None = None,
        territory_type: str | None = None,
        parent_territory: str | None = None,
        parent: QtWidgets.QWidget | None = None,
    ):
        super().__init__(parent=parent)
        self.window().setWindowTitle(title)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel(text))
        self._geometry_field = QtWidgets.QTextEdit()
        self._geometry_field.setPlainText(geometry or "")
        self._geometry_field.setPlaceholderText('{\n  "type": "...",\n  "coordinates": [...]\n}')
        self._geometry_field.setAcceptRichText(False)
        layout.addWidget(self._geometry_field)
        self._options_layout = QtWidgets.QFormLayout()
        self._name = QtWidgets.QLineEdit(name or "")
        self._name.setPlaceholderText("Ленинский")
        self._options_layout.addRow("Название:", self._name)
        self._population = QtWidgets.QLineEdit(to_str(population))
        self._population.setPlaceholderText("30000")
        self._options_layout.addRow("Население:", self._population)
        self._territory_type = QtWidgets.QComboBox()
        self._territory_type.addItems(territory_types)
        if territory_type is not None:
            self._territory_type.setCurrentText(territory_type)
        self._options_layout.addRow("Тип территории:", self._territory_type)
        self._parent_territory = QtWidgets.QComboBox()
        self._parent_territory.addItems(["-"] + parents)
        if parent_territory is not None:
            self._parent_territory.setCurrentText(parent_territory)
        self._options_layout.addRow("Родительская территория:", self._parent_territory)
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
        """Get territory name value set by user."""
        return str_or_none(self._name.text())

    def population(self) -> int | None:
        """Get territory population value set by user."""
        return int_or_none(self._population.text())

    def territory_type(self) -> str:
        """Get territory type value set by user."""
        return self._territory_type.currentText()

    def parent_territory(self) -> str | None:
        """Get parent territory value set by user."""
        return self._parent_territory.currentText() if self._parent_territory.currentIndex() != 0 else None
