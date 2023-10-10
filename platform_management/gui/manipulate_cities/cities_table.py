"""Platform cities table is defined here."""
from __future__ import annotations

from typing import Any, Callable, Sequence

from PySide6 import QtWidgets

from platform_management.gui.basics import ColoringTableWidget


class PlatformCitiesTableWidget(ColoringTableWidget):
    """Table representing Platform cities data."""

    LABELS = [
        "id города",
        "Название",
        "Код",
        "Население",
        "С.К.",
        "Регион",
        "Тип деления",
        "Широта",
        "Долгота",
        "Тип геометрии",
        "Создание",
        "Обновление",
    ]
    """Table columns names."""
    LABELS_DB = [
        "id",
        "name",
        "code",
        "population",
        "local_crs",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
    ]
    """Mapping of table columns to the database columns for editing purposes."""

    def __init__(
        self,
        services: Sequence[Sequence[Any]],
        changed_callback: Callable[[int, str, Any, Any, bool], None],
        parent: QtWidgets.QWidget | None = None,
    ):
        super().__init__(
            services,
            PlatformCitiesTableWidget.LABELS,
            self.correction_checker,
            list(
                map(
                    lambda x: x[0],
                    filter(lambda y: y[1] in ("id", "-"), enumerate(PlatformCitiesTableWidget.LABELS_DB)),
                )
            ),
            parent=parent,
        )
        self._changed_callback = changed_callback
        self.setColumnWidth(1, 200)
        for column in range(2, len(PlatformCitiesTableWidget.LABELS)):
            self.resizeColumnToContents(column)
        self.setSortingEnabled(True)

    def correction_checker(self, row: int, column: int, old_data: Any, new_data: str) -> bool:
        """Check the correctness of the changed cell value."""
        res = True
        if new_data is None and column in (1, 2):
            res = False
        elif column == 2 and (not new_data.isnumeric() or int(new_data) < 0):
            res = False
        if PlatformCitiesTableWidget.LABELS_DB[column] != "-":
            self._changed_callback(row, PlatformCitiesTableWidget.LABELS[column], old_data, new_data, res)
        return res
