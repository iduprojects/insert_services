"""Region creation widget is defined here."""
from __future__ import annotations

from PySide6 import QtWidgets

from platform_management.utils.converters import str_or_none


class RegionCreation(QtWidgets.QDialog):
    """Region creation window."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        text: str,
        geometry: str | None = None,
        name: str | None = None,
        code: str | None = None,
        is_adding: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ):
        super().__init__(parent=parent)
        self.window().setWindowTitle("Добавление региона" if is_adding else "Изменение региона")
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel(text))
        self._geometry_field = QtWidgets.QTextEdit()
        self._geometry_field.setPlainText(geometry or "")
        self._geometry_field.setPlaceholderText('{\n  "type": "...",\n  "coordinates": [...]\n}')
        self._geometry_field.setAcceptRichText(False)
        layout.addWidget(self._geometry_field)
        self._options_layout = QtWidgets.QFormLayout()
        self._name = QtWidgets.QLineEdit(name or "")
        self._name.setPlaceholderText("Ленинградская область")
        self._options_layout.addRow("Название:", self._name)
        self._code = QtWidgets.QLineEdit(code or "")
        self._code.setPlaceholderText("leningrad_oblast")
        self._options_layout.addRow("Код в БД:", self._code)
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
        """Get region name value set by user."""
        return str_or_none(self._name.text())

    def code(self) -> str | None:
        """Get region code value set by user."""
        return str_or_none(self._code.text())
