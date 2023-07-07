"""Application instance is defined here."""
from PySide6 import QtWidgets

_app: QtWidgets.QApplication = None


def get_application() -> QtWidgets.QApplication:
    """Get current application instance or create one if it is the first call."""

    global _app  # pylint: disable=global-statement
    if _app is None:
        _app = QtWidgets.QApplication([])

    return _app
