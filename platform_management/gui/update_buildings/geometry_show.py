"""Geometry displaying window is defined here."""
from __future__ import annotations

from PySide6 import QtWidgets


class GeometryShowWidget(QtWidgets.QDialog):
    """Window showing the geometry GeoJSON value and allowing to copy it."""

    def __init__(self, geometry: str, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent=parent)
        self.window().setWindowTitle("Просмотр геометрии")
        layout = QtWidgets.QVBoxLayout()
        geometry_field = QtWidgets.QTextEdit()
        geometry_field.setPlainText(geometry)
        geometry_field.setMinimumSize(300, 300)
        geometry_field.setReadOnly(True)
        layout.addWidget(geometry_field)
        copy_btn = QtWidgets.QPushButton("Скопировать в буфер обмена")

        def copy_and_close():
            QtWidgets.QApplication.clipboard().setText(geometry_field.toPlainText())
            self.accept()

        copy_btn.clicked.connect(copy_and_close)
        layout.addWidget(copy_btn)
        self.setLayout(layout)
