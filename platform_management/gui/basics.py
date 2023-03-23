# pylint: disable=c-extension-no-member
"""
Common Qt widgets to use in GUI application.
"""
import json
from typing import Any, Callable, List, NamedTuple, Optional, Sequence, Tuple
from frozenlist import FrozenList

import psycopg2  # pylint: disable=unused-import
from PySide6 import QtCore, QtGui, QtWidgets


def check_geometry_correctness(
    geometry_geojson: Optional[str], conn: "psycopg2.connection"
) -> Optional[Tuple[float, float, str]]:
    if geometry_geojson is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ST_AsGeoJSON(ST_Centroid(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)), 6),"
                " ST_GeometryType(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))",
                (geometry_geojson,) * 2,
            )
            new_center, geom_type = cur.fetchone()  # type: ignore
            new_center = json.loads(new_center)
            new_longitude, new_latitude = new_center["coordinates"]
        return new_latitude, new_longitude, geom_type
    except RuntimeError:
        conn.rollback()
        return None


class ColorizingLine(QtWidgets.QLineEdit):
    def __init__(
        self,
        callback: Callable[[Optional[QtWidgets.QLineEdit], Optional[str]], None],
        text: Optional[str] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self._state: str = text or ""
        self.setText(text or "")
        self._callback = callback

    def focusInEvent(self, event: QtGui.QFocusEvent) -> None:  # pylint: disable=invalid-name
        self._state = self.text()
        return super().focusInEvent(event)

    def focusOutEvent(self, event: QtGui.QFocusEvent) -> None:  # pylint: disable=invalid-name
        if self.text() != self._state:
            old_state = self._state
            self._state = self.text()
            if self.isVisible():
                self._callback(self, old_state)
        return super().focusOutEvent(event)


class ColorizingComboBox(QtWidgets.QComboBox):
    def __init__(
        self,
        callback: Callable[[Optional[QtWidgets.QComboBox], Optional[int]], None],
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self._callback = callback
        self._state = 0
        self.currentIndexChanged.connect(self.changeEvent)

    def changeEvent(self, *_):  # pylint: disable=invalid-name
        if self._state != self.currentIndex():
            old_state = self._state
            self._state = self.currentIndex()
            if self.isVisible():
                self._callback(self, old_state)

    def __str__(self) -> str:
        return f'ColorizingComboBox("{self.currentText()}" / {self.currentIndex()}) at {hex(id(self))})'


class CheckableTableView(QtWidgets.QTableView):

    colorTable = NamedTuple("ColorTable", [("on", QtGui.QColor), ("off", QtGui.QColor)])(
        QtGui.QColor(152, 224, 173), QtGui.QColor(248, 161, 164)
    )  # type: ignore

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:  # pylint: disable=invalid-name
        if self.columnAt(int(event.position().x())) == 0:
            self.toggle_row(self.rowAt(int(event.position().y())))
        else:
            super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:  # pylint: disable=invalid-name
        key = event.key()
        if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter, QtCore.Qt.Key_Minus, QtCore.Qt.Key_Plus):
            indexes = set(
                map(
                    lambda index: index.row(),
                    filter(
                        lambda index: index.column() == 0,
                        self.selectedIndexes(),
                    ),
                )
            )  # type: ignore
            if len(indexes) > 0:
                func = (
                    self.turn_row_off
                    if key == QtCore.Qt.Key_Minus
                    else self.turn_row_on
                    if key == QtCore.Qt.Key_Plus
                    else self.toggle_row
                )
                for row in indexes:
                    func(row)
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def toggle_row(self, row: int) -> None:
        item_index = self.model().index(row, 0)
        item = self.model().data(item_index)
        self.model().setData(item_index, "-" if item == "+" else "+")
        self.model().setData(
            item_index,
            CheckableTableView.colorTable.off if item == "+" else CheckableTableView.colorTable.on,
            QtCore.Qt.BackgroundRole,
        )

    def turn_row_on(self, row: int) -> None:
        item_index = self.model().index(row, 0)
        self.model().setData(item_index, "+")
        self.model().setData(item_index, CheckableTableView.colorTable.on, QtCore.Qt.BackgroundRole)

    def turn_row_off(self, row: int) -> None:
        item_index = self.model().index(row, 0)
        self.model().setData(item_index, "-")
        self.model().setData(item_index, CheckableTableView.colorTable.off, QtCore.Qt.BackgroundRole)

    def is_turned_on(self, row: int) -> bool:
        return self.model().itemData(self.model().index(row, 0)) == "+"


class DropPushButton(QtWidgets.QPushButton):
    def __init__(
        self, text: str, formats: List[str], callback: Callable[[str], None], parent: Optional[QtWidgets.QWidget] = None
    ):
        self.formats = tuple((f".{format}" for format in formats))
        self._callback = callback
        super().__init__(text, parent=parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:  # pylint: disable=invalid-name
        if (event.mimeData().hasUrls() and event.mimeData().urls()[0].path().endswith(self.formats)) or (
            event.mimeData().text().startswith("file:///") and event.mimeData().text().endswith(self.formats)
        ):
            event.setDropAction(QtCore.Qt.LinkAction)
            event.accept()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:  # pylint: disable=invalid-name
        if event.mimeData().hasUrls():
            self._callback(event.mimeData().urls()[0].toLocalFile())
        else:
            self._callback(event.mimeData().text()[len("file:///") :])


class ColoringTableWidget(QtWidgets.QTableWidget):
    def __init__(
        self,
        data: List[Sequence[Any]],
        labels: List[str],
        correction_checker: Callable[[int, int, Any, str], bool] = lambda _column, _row, _old_value, _new_value: True,
        blocked_columns: Sequence[int] = FrozenList([]),
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent=parent)
        self._data = []
        self._initialized = False
        self._checker = correction_checker
        self.setRowCount(len(data))
        self.setColumnCount(len(labels))
        self.setHorizontalHeaderLabels(labels)
        for i, row in enumerate(data):
            self._data.append(list(row))
            for j, item in enumerate(row):
                self.setItem(
                    i,
                    j,
                    QtWidgets.QTableWidgetItem(
                        str(item or "" if not isinstance(item, bool) else "True" if item else "False")
                    ),
                )
            for j in blocked_columns:
                item = self.item(i, j)
                item.setBackground(QtGui.QColor.fromRgb(140, 140, 140))
                item.setForeground(QtGui.QColor.fromRgb(0, 0, 0))
                item.setFlags(QtCore.Qt.ItemIsEnabled)
        self._initialized = True

    def dataChanged(  # pylint: disable=invalid-name
        self, top_left: QtCore.QModelIndex, bottom_right: QtCore.QModelIndex, roles: Sequence[int] = ...
    ) -> None:  # type: ignore
        if self._initialized and 0 in roles:
            row, column, data = top_left.row(), top_left.column(), top_left.data()
            if data == "":
                data = None
            if self._checker(row, column, self._data[row][column], data):
                self.item(row, column).setBackground(QtCore.Qt.GlobalColor.yellow)
            else:
                self.item(row, column).setBackground(QtCore.Qt.GlobalColor.red)
            self._data[row][column] = data
        return super().dataChanged(top_left, bottom_right, roles=roles)

    def disable_triggers(self) -> None:
        self._initialized = False

    def enable_triggers(self) -> None:
        self._initialized = True


class GeometryShow(QtWidgets.QDialog):
    def __init__(self, geometry: str, parent: Optional[QtWidgets.QWidget] = None):
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
