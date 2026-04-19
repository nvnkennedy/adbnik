import os
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QStyleFactory

from . import APP_TITLE, __version__
from .config import AppConfig, has_existing_config_file
from .ui.app_icon import create_app_icon


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
    os.environ.setdefault("QT_API", "pyqt5")
    try:
        from qt_thread_updater import get_updater

        get_updater().start()
    except Exception:
        pass
    fusion = QStyleFactory.create("Fusion")
    if fusion is not None:
        app.setStyle(fusion)
    app.setApplicationName(APP_TITLE)
    try:
        QApplication.setCursorFlashTime(530)
    except AttributeError:
        pass

    config = AppConfig.load()
    fresh_config = not has_existing_config_file()
    upgraded = (
        not fresh_config
        and (getattr(config, "last_acknowledged_version", "") or "") != (__version__ or "")
    )
    # First install, or upgraded build: show welcome / theme / paths once user confirms (or skip).
    need_welcome = fresh_config or upgraded
    app.setWindowIcon(create_app_icon(dark=bool(config.dark_theme)))

    from .ui.main_window import MainWindow

    window = MainWindow(config, first_launch=need_welcome, is_upgrade=upgraded)
    window.show()
    sys.exit(app.exec_())
