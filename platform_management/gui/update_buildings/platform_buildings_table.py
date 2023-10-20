"""Platform services table is defined here."""
from typing import Any, Callable, Sequence

from platform_management.database_properties import Properties
from platform_management.gui.basics import ColoringTableWidget


class PlatformBuildingsTableWidget(ColoringTableWidget):
    """Table representing Platform services data."""

    LABELS = [
        "id здания",
        "Адрес",
        "id физ. объекта",
        "Жилой",
        "Площадь пятна",
        "Жил.площадь",
        "Этажность",
        "Широта",
        "Долгота",
        "Тип геометрии",
        "Админ. единица",
        "Муницип. образование",
        "Создание",
        "Обновление",
    ]
    """Table columns names."""
    LABELS_DB = [
        "-",
        "address",
        "physical_object_id",
        "is_living",
        "building_area",
        "living_area",
        "storeys_count",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
    ]
    """Columns mapping to the database columns for editing purposes."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        buildings: list[Sequence[Any]],
        properties_keys: list[str],
        changed_callback: Callable[[int, str, Any, Any, bool], None],
        db_properties: Properties,
    ):
        super().__init__(
            buildings,
            PlatformBuildingsTableWidget.LABELS + properties_keys,
            self.correction_checker,
            (0,) + tuple(range(7, len(self.LABELS) + len(properties_keys))),
        )
        if len(buildings) > 0:
            assert len(PlatformBuildingsTableWidget.LABELS) + len(properties_keys) == len(
                list(buildings[0])
            ), "size of a service table is not equal to a predefined table"
        self._labels = PlatformBuildingsTableWidget.LABELS + properties_keys
        self._db_properties = db_properties
        self._changed_callback = changed_callback
        self._is_callback_enabled = True
        for column in range(len(self.LABELS)):
            self.resizeColumnToContents(column)
        self.setSortingEnabled(True)

    def correction_checker(self, row: int, column: int, old_data: Any, new_data: str) -> bool:
        """Check if the changed element have a correct value."""
        res = True
        if new_data is not None and column == self.LABELS_DB.index("address") and len(new_data) >= 128:
            res = False
        elif column in (self.LABELS_DB.index("building_area"), self.LABELS_DB.index("living_area")) and (
            new_data.count(".") >= 1 or not new_data.replace(".", "").isnumeric() or float(new_data) < 0
        ):
            res = False
        elif column == self.LABELS_DB.index("is_living") and new_data.lower() not in ("true", "false", "0", "1"):
            res = False
        if self._is_callback_enabled and (
            column > len(PlatformBuildingsTableWidget.LABELS_DB)
            or PlatformBuildingsTableWidget.LABELS_DB[column] != "-"
        ):
            self._changed_callback(row, self._labels[column], old_data, new_data, res)
        return res

    def disable_callback(self):
        """Disable edit hooks."""
        self._is_callback_enabled = False
        self.disable_triggers()

    def enable_callback(self):
        """Enable edit hooks."""
        self._is_callback_enabled = True
        self.enable_triggers()
