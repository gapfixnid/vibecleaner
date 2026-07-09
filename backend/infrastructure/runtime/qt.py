"""Offscreen Qt runtime bootstrap.

Text layout uses QFontMetricsF in request handlers, so the backend process
needs an offscreen QApplication before routes start serving bubble data.
Import this module for its side effect.
"""

from PySide6.QtWidgets import QApplication

qt_app = QApplication.instance()
if qt_app is None:
    qt_app = QApplication(["-platform", "offscreen"])
