"""Styly QSS pro tmavý a světlý motiv."""

DARK = """
QMainWindow, QDialog, QWidget { background-color: #1e1e1e; color: #dcdcdc; }
QListWidget {
    background-color: #252526; color: #dcdcdc;
    border: 1px solid #3f3f46; border-radius: 4px;
    outline: none;
}
QListWidget::item { padding: 6px; }
QListWidget::item:selected { background-color: #094771; color: #ffffff; }
QPlainTextEdit {
    background-color: #0c0c0c; color: #e8e8e8;
    border: 1px solid #3f3f46; border-radius: 4px;
    font-family: Consolas, monospace; font-size: 14px;
}
QToolBar { background-color: #252526; border-bottom: 1px solid #3f3f46; spacing: 4px; }
QPushButton, QToolButton {
    background-color: #333337; color: #dcdcdc;
    border: 1px solid #4a4a52; border-radius: 4px; padding: 6px 12px;
}
QPushButton:hover, QToolButton:hover { background-color: #3d3d42; }
QPushButton:pressed, QToolButton:pressed { background-color: #2a2a2e; }
QLineEdit, QSpinBox {
    background-color: #252526; color: #dcdcdc;
    border: 1px solid #3f3f46; border-radius: 4px; padding: 4px;
}
QCheckBox { color: #dcdcdc; }
QStatusBar { background-color: #252526; color: #9cdcfe; }
QLabel { color: #dcdcdc; }
QGroupBox { border: 1px solid #3f3f46; border-radius: 4px; margin-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
"""

LIGHT = """
QMainWindow, QDialog, QWidget { background-color: #f5f5f5; color: #1e1e1e; }
QListWidget {
    background-color: #ffffff; color: #1e1e1e;
    border: 1px solid #c8c8c8; border-radius: 4px;
    outline: none;
}
QListWidget::item { padding: 6px; }
QListWidget::item:selected { background-color: #cce4f7; color: #1e1e1e; }
QPlainTextEdit {
    background-color: #ffffff; color: #1e1e1e;
    border: 1px solid #c8c8c8; border-radius: 4px;
    font-family: Consolas, monospace; font-size: 14px;
}
QToolBar { background-color: #ececec; border-bottom: 1px solid #c8c8c8; spacing: 4px; }
QPushButton, QToolButton {
    background-color: #e2e2e2; color: #1e1e1e;
    border: 1px solid #c8c8c8; border-radius: 4px; padding: 6px 12px;
}
QPushButton:hover, QToolButton:hover { background-color: #d5d5d5; }
QPushButton:pressed, QToolButton:pressed { background-color: #c8c8c8; }
QLineEdit, QSpinBox {
    background-color: #ffffff; color: #1e1e1e;
    border: 1px solid #c8c8c8; border-radius: 4px; padding: 4px;
}
QCheckBox { color: #1e1e1e; }
QStatusBar { background-color: #ececec; color: #0055aa; }
QLabel { color: #1e1e1e; }
QGroupBox { border: 1px solid #c8c8c8; border-radius: 4px; margin-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
"""

THEMES = {"dark": DARK, "light": LIGHT}