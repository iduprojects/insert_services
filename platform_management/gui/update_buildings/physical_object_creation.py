"""Physical object creation widget is defined here."""
from __future__ import annotations

from PySide6 import QtWidgets

from platform_management.utils.converters import str_or_none


class PhysicalObjectCreationWidget(QtWidgets.QDialog):
    """Physical object creation window."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        text: str,
        geometry: str | None = None,
        osm_id: str | None = None,
        is_adding: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ):
        super().__init__(parent=parent)
        self.window().setWindowTitle("Добавление физического объекта" if is_adding else "Изменение физического объекта")
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
