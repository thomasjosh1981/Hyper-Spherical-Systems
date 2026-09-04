"""
Main execution entry point for pirate_gui package.
"""
import sys
import os
import argparse
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).parent.parent.parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "gui") not in sys.path:
    sys.path.insert(0, str(ROOT / "gui"))

def main(args_list=None):
    from PySide6 import QtWidgets
    from gui.pirate_gui.dashboard import MainWindow
    from gui.pirate_gui.wizard import WizardDialog
    from gui.pirate_gui import config_io

    parser = argparse.ArgumentParser(description="HypeS Control Center")
    parser.add_argument("--app", choices=["core", "proxy", "spinner", "mcp", "keys"], default="core")
    parser.add_argument("--skip-wizard", action="store_true", help="Skip first-run wizard")
    
    if args_list is not None:
        parsed_args, _ = parser.parse_known_args(args_list)
    else:
        parsed_args, _ = parser.parse_known_args()

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")

    cfg = config_io.load()

    # Show first-run wizard if not skipped and first run
    if not parsed_args.skip_wizard and not cfg.get("wizard_completed", False):
        wiz = WizardDialog(cfg)
        if wiz.exec() != QtWidgets.QDialog.Accepted:
            return 0
        cfg = config_io.load()

    main_win = MainWindow(cfg)
    main_win.show()

    # If a specific app module was requested, switch tab
    if parsed_args.app == "proxy":
        main_win.tabs.setCurrentIndex(1)
    elif parsed_args.app == "spinner":
        if hasattr(main_win, "gcs_tab_index") and main_win.gcs_tab_index is not None:
            main_win.tabs.setCurrentIndex(main_win.gcs_tab_index)
        try:
            from gui.pirate_gui.golden_candy_spinner_panel import GoldenCandySpinnerWindow
            GoldenCandySpinnerWindow.show_window()
        except Exception as e:
            print(f"[HypeS] Golden Candy Spinner launch error: {e}")

    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
