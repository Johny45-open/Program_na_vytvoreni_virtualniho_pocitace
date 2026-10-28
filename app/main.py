"""Vstupní bod aplikace.

Spuštění:  python -m app  (nebo  python app/main.py)
"""
import sys

from PySide6.QtWidgets import QApplication

from .i18n.tr import lang_manager
from .ui.main_window import MainWindow
from .ui.styles import DARK


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("VM Manager")
    app.setStyle("Fusion")
    app.setStyleSheet(DARK)
    lang_manager.set_language("cs")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()