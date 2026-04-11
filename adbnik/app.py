import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QStyleFactory

from . import APP_TITLE
from .config import AppConfig, has_existing_config_file
from .ui.app_icon import create_app_icon
from .ui.main_window import MainWindow


def _set_windows_app_user_model_id() -> None:
    """So the taskbar uses our window icon instead of the generic Python icon."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Adbnik.Adbnik.Application.1")
    except Exception:
        pass


def main():
    _set_windows_app_user_model_id()
    try:
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    except AttributeError:
        pass
    app = QApplication(sys.argv)
    fusion = QStyleFactory.create("Fusion")
    if fusion is not None:
        app.setStyle(fusion)
    app.setApplicationName(APP_TITLE)
    try:
        QApplication.setCursorFlashTime(530)
    except AttributeError:
        pass

    fresh_config = not has_existing_config_file()
    config = AppConfig.load()
    app.setWindowIcon(create_app_icon(dark=bool(config.dark_theme)))

    window = MainWindow(config, first_launch=fresh_config)
    window.show()
    sys.exit(app.exec_())
