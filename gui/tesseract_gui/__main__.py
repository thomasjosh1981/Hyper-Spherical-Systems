"""tesseract_gui — top-level entry point.

Usage:
    python -m tesseract_gui                  # first-run wizard → dashboard
    python -m tesseract_gui --reset-config   # force the wizard to run again
"""

from __future__ import annotations
import argparse
import sys

from PySide6 import QtWidgets

from . import config_io
from .wizard import SetupWizard
from .dashboard import MainWindow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tesseract_gui")
    parser.add_argument("--reset-config", action="store_true",
                        help="Force the setup wizard to run again.")
    parser.add_argument("--skip-wizard", action="store_true",
                        help="Skip the wizard even if config is incomplete.")
    parser.add_argument("--engine-path", default=None,
                        help="Override path to tesseract_bridge.dll")
    args = parser.parse_args(argv)

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Tesseract Control Center")
    app.setStyle("Fusion")

    # Force palette to dark if requested
    cfg = config_io.load()
    if args.reset_config:
        cfg.wizard_completed = False
    if cfg.theme == "dark":
        app.setStyleSheet(_DARK_QSS)

    if not cfg.wizard_completed and not args.skip_wizard:
        wizard = SetupWizard(cfg)
        if wizard.exec() != SetupWizard.Accepted:
            print("Setup cancelled by user.")
            return 1
        cfg = config_io.load()

    if args.engine_path:
        cfg.engine_path_override = args.engine_path

    window = MainWindow(cfg)
    if cfg.window_geometry:
        window.restoreGeometry(QtCore.QByteArray(cfg.window_geometry))
    window.show()
    return app.exec()


# ── Minimal dark theme ────────────────────────────────────────────────
_DARK_QSS = """
QWidget        { background: #1e1e1e; color: #e0e0e0; }
QGroupBox      { border: 1px solid #444; border-radius: 6px; margin-top: 14px; padding-top: 8px; }
QGroupBox::title{ subcontrol-origin: margin; left: 10px; padding: 0 6px; color: #80cbc4; }
QPushButton    { background: #2d2d2d; border: 1px solid #555; padding: 6px 14px; border-radius: 4px; }
QPushButton:hover { background: #3a3a3a; }
QPushButton:disabled { background: #252525; color: #777; }
QPlainTextEdit, QLineEdit, QSpinBox, QDoubleSpinBox {
    background: #252525; border: 1px solid #444; border-radius: 4px; padding: 4px; }
QProgressBar   { background: #2a2a2a; border: 1px solid #444; border-radius: 4px; text-align: center; }
QTableWidget   { background: #252525; gridline-color: #444; }
QHeaderView::section { background: #2d2d2d; color: #80cbc4; padding: 4px; border: none; }
QMenuBar       { background: #252525; }
QMenuBar::item:selected { background: #3a3a3a; }
QMenu          { background: #252525; border: 1px solid #444; }
QMenu::item:selected { background: #3a3a3a; }
QStatusBar     { background: #252525; }
QToolBar       { background: #252525; spacing: 4px; padding: 4px; }
QTabWidget::pane { border: 1px solid #444; }
QTabBar::tab   { background: #2d2d2d; padding: 6px 12px; border: 1px solid #444; border-bottom: none; }
QTabBar::tab:selected { background: #1e1e1e; color: #80cbc4; }
QSplitter::handle { background: #333; }
"""


from PySide6 import QtCore  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
