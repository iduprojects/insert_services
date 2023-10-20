"""Platform services table is defined here."""
from typing import Any, Callable, Sequence

from platform_management.database_properties import Properties
from platform_management.gui.basics import ColoringTableWidget


class PlatformServicesTableWidget(ColoringTableWidget):
    """Table representing Platform services data."""

    LABELS = [
        "id сервиса",
        "Адрес",
        "Название",
        "Рабочие часы",
        "Веб-сайт",
        "Телефон",
        "Мощность",
        "Мощ-real",
        "id физ. объекта",
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
        "id",
        "-",
        "name",
        "opening_hours",
        "website",
        "phone",
        "capacity",
        "is_capacity_real",
        "physical_object_id",
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
        services: list[Sequence[Any]],
        properties_keys: list[str],
        changed_callback: Callable[[int, str, Any, Any, bool], None],
        db_properties: Properties,
        is_service_building: bool,
    ):
        super().__init__(
            services,
            PlatformServicesTableWidget.LABELS + properties_keys,
            self.correction_checker,
            (0, 1, 9, 10, 11, 12, 13, 14, 15),
        )
        if len(services) > 0:
            assert len(PlatformServicesTableWidget.LABELS) + len(properties_keys) == len(
                list(services[0])
            ), "size of a service table is not equal to a predefined table"
        self._labels = PlatformServicesTableWidget.LABELS + properties_keys
        self._db_properties = db_properties
        self._changed_callback = changed_callback
        self._is_service_building = is_service_building
        self._is_callback_enabled = True
        self.setColumnWidth(2, 200)
        self.setColumnWidth(3, 120)
        self.setColumnWidth(4, 190)
        self.setColumnWidth(5, 180)
        for column in range(8, 16):
            self.resizeColumnToContents(column)
        self.setSortingEnabled(True)

    def correction_checker(self, row: int, column: int, old_data: Any, new_data: str) -> bool:
        """Check if the changed element have a correct value."""
        res = True
        if new_data is None and column in (6, 7):
            res = False
        elif column == 6 and (not new_data.isnumeric() or int(new_data) < 0):
            res = False
        elif column == 7 and new_data.lower() not in ("true", "false", "0", "1"):
            res = False
        elif column == 8 and not new_data.isnumeric():
            res = False
        elif column == 8:
            with self._db_properties.conn.cursor() as cur:
                cur.execute(
                    "SELECT EXISTS (SELECT 1 FROM physical_objects WHERE id = %(new_data)s),"
                    " EXISTS (SELECT 1 FROM buildings WHERE physical_object_id = %(new_data)s)",
                    ({"new_data": new_data}),
                )
                if cur.fetchone() != (True, self._is_service_building):
                    res = False
        if self._is_callback_enabled and (
            column > len(PlatformServicesTableWidget.LABELS_DB) or PlatformServicesTableWidget.LABELS_DB[column] != "-"
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
