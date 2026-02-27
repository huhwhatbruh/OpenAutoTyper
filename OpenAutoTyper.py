# OpenAutoTyper.py
import sys
from PySide6.QtWidgets import QApplication
from appdata.core.version.checker import check_version
from appdata.ui.main import OpenAutoTyperApp

if __name__ == "__main__":
    print("[INFO] Starting OpenAutoTyper application...")
    app = QApplication(sys.argv)
    window = OpenAutoTyperApp()
    window.show()
    # Version check runs in a background thread; any resulting dialog
    # is scheduled back on the main thread via QTimer.singleShot.
    check_version()
    app.exec()
    print("[INFO] Application closed.")
