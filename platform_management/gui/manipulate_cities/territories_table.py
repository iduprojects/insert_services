"""Platform territories table is defined here."""

from typing import Any, Sequence

from PySide6 import QtWidgets

from platform_management.utils.converters import to_str


class PlatformTerritoriesTableWidget(QtWidgets.QTableWidget):
    """Table representing Platform territories data."""

    LABELS = [
        "id территории",
        "Название",
        "Население",
        "Тип территории",
        "Родительская территория",
        "Широта",
        "Долгота",
        "Тип геометрии",
        "Создание",
        "Обновление",
    ]
    """Names of table columns."""
    LABELS_DB = [
        "id",
        "name",
        "population",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
    ]
    """Mapping of table columns to the database columns for editing purposes."""

    def __init__(self, territories: Sequence[Sequence[Any]], parent: QtWidgets.QWidget | None = None):
        super().__init__(parent=parent)
        self.setRowCount(len(territories))
        self.setColumnCount(len(PlatformTerritoriesTableWidget.LABELS))
        self.setHorizontalHeaderLabels(PlatformTerritoriesTableWidget.LABELS)
        self.setEditTriggers(QtWidgets.QTableWidget.NoEditTriggers)  # type: ignore
        for i, row in enumerate(territories):
            for j, item in enumerate(row):
                self.setItem(i, j, QtWidgets.QTableWidgetItem(to_str(item)))
        self.setColumnWidth(1, 200)
        self.setColumnWidth(2, 90)
        for column in range(2, len(PlatformTerritoriesTableWidget.LABELS)):
            self.resizeColumnToContents(column)
        self.setSortingEnabled(True)
