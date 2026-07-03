import os
import sys

from PySide6.QtWidgets import QApplication


def ensure_backend_path() -> str:
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    return backend_dir


ensure_backend_path()

qt_app = QApplication.instance()
if qt_app is None:
    qt_app = QApplication(["-platform", "offscreen"])
