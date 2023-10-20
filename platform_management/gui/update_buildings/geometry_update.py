"""Geometry updation widget is defined here."""
from __future__ import annotations

from PySide6 import QtWidgets

from platform_management.utils.converters import str_or_none


class GeometryUpdateWidget(QtWidgets.QDialog):
    """Geometry update window for the given service."""

    def __init__(self, text: str, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent=parent)
        self.window().setWindowTitle("Изменение геометрии")
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel(text))
        self._geometry_field = QtWidgets.QTextEdit()
        self._geometry_field.setPlaceholderText('{\n  "type": "...",\n  "geometry": [...]\n}')
        self._geometry_field.setAcceptRichText(False)
        layout.addWidget(self._geometry_field)
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
        """Return the geometry set by user."""
        return str_or_none(self._geometry_field.toPlainText())
