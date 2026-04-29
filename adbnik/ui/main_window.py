import html
import os
import platform
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt5.QtCore import QSize, Qt, QThread, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices, QFont, QKeySequence, QTextCursor
from PyQt5.QtWidgets import (
    QAction,
    QActionGroup,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QInputDialog,
    QMainWindow,
    QMenu,
    QMessageBox,
    QTextBrowser,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStyle,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import APP_TITLE, __version__
from ..config import AppConfig
from ..urls import GITHUB_REPO, PYPI_PROJECT, USER_GUIDE, WEBSITE_HOME
from ..services.adb_devices import list_adb_devices
from ..services.commands import kill_all_adb_subprocesses
from ..services.commands import run_adb, run_adb_with_line_callback
from ..session import ConnectionKind, SessionProfile
from .app_icon import create_app_icon
from .first_run_dialog import FirstRunDialog
from .preferences_dialog import PreferencesDialog
from .styles import get_stylesheet
from .icon_utils import icon_adb_android
from .tabs.file_explorer_tab import FileExplorerTab
from .file_dialogs import get_open_filename, get_save_filename
from .tabs.scrcpy_tab import ScrcpyTab
from .tabs.terminal_tab import TerminalTab
from .win_scrcpy_hotkey import (
    is_windows_hotkey_message,
    register_scrcpy_stop_hotkey as _win_register_scrcpy_hotkey,
    unregister_scrcpy_stop_hotkey as _win_unregister_scrcpy_hotkey,
)


class _AdbDevicesRefreshThread(QThread):
    done = pyqtSignal(object, bool)

    def __init__(self, adb_path: str, parent=None):
        super().__init__(parent)
        self._adb_path = adb_path

    def run(self) -> None:
        pairs = list_adb_devices(self._adb_path)
        if pairs:
            self.done.emit(pairs, True)
            return
        code, _, _ = run_adb(self._adb_path, ["devices"], timeout=8)
        self.done.emit([], code == 0)


class _AdbDeviceStatsThread(QThread):
    done = pyqtSignal(str, object, str)

    def __init__(self, adb_path: str, serial: str, parent=None):
        super().__init__(parent)
        self._adb_path = adb_path
        self._serial = serial

    def run(self) -> None:
        serial = (self._serial or "").strip()
        if not serial:
            self.done.emit("", None, "No device selected")
            return
        cmd = (
            "cat /proc/uptime; "
            "head -n 1 /proc/stat; "
            "cat /proc/meminfo"
        )
        code, out, err = run_adb(self._adb_path, ["-s", serial, "shell", cmd], timeout=12)
        if code != 0:
            self.done.emit(serial, None, (err or "stats command failed").strip())
            return
        self.done.emit(serial, out, "")


class MainWindow(QMainWindow):
    """Main application window: tabbed Terminal, File Explorer, Screen Control, app log, and menus."""

    def __init__(self, config: AppConfig, *, first_launch: bool = False, is_upgrade: bool = False):
        """Load UI, theme, device refresh, and optional first-run / upgrade welcome."""
        super().__init__()
        self.config = config
        self._first_launch = first_launch
        self._is_upgrade_welcome = bool(is_upgrade)
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(create_app_icon(dark=bool(getattr(self.config, "dark_theme", False))))
        self.resize(1450, 900)
        self.setMinimumSize(720, 480)
        self._shutting_down = False
        self._log_history: List[str] = []
        self._build_ui()
        self._device_refresh_thread: Optional[_AdbDevicesRefreshThread] = None
        self._device_refresh_pending = False
        self._stats_refresh_thread: Optional[_AdbDeviceStatsThread] = None
        self._stats_refresh_pending = False
        self._stats_prev_cpu: Dict[str, Tuple[int, int]] = {}
        self._apply_theme()
        self._setup_version_status()
        self._sync_theme_menu_checks()
        self.append_log("Application started.")
        self.append_log(f"ADB path: {self.get_adb_path()}  ·  scrcpy: {self.get_scrcpy_path()}")
        if getattr(self.config, "dark_theme", False):
            self.append_log("Dark theme is enabled (View → Theme → Dark).")
        self.refresh_devices()
        if self._first_launch:
            QTimer.singleShot(0, self.prompt_first_run_if_needed)
        self._adb_poll_timer = QTimer(self)
        self._adb_poll_timer.setInterval(5000)
        self._adb_poll_timer.timeout.connect(self.refresh_devices)
        self._adb_poll_timer.start()
        self._adb_stats_timer = QTimer(self)
        self._adb_stats_timer.setInterval(8000)
        self._adb_stats_timer.timeout.connect(self.refresh_device_stats)
        self._adb_stats_timer.start()
        self._scrcpy_hotkey_registered = False
        _app = QApplication.instance()
        if _app is not None:
            _app.applicationStateChanged.connect(self._on_application_state_changed)

    def showEvent(self, event):
        super().showEvent(event)
        # Avoid duplicate startup refresh work; timer + initial call handle it.

    def _on_application_state_changed(self, state: Qt.ApplicationState) -> None:
        """Pause ADB timers in the background to cut idle CPU and reduce long-session UI stalls."""
        if state != Qt.ApplicationActive:
            self._adb_poll_timer.stop()
            self._adb_stats_timer.stop()
        else:
            self._adb_poll_timer.start()
            self._adb_stats_timer.start()
            self.refresh_devices()
            self.refresh_device_stats()

    def append_log(self, message: str) -> None:
        self._log_history.append(message or "")
        if len(self._log_history) > 4000:
            self._log_history = self._log_history[-4000:]
        self._append_log_html(message or "")

    def _append_log_html(self, message: str) -> None:
        if not hasattr(self, "log_view"):
            return
        dark = bool(getattr(self.config, "dark_theme", False))
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg_l = (message or "").lower()
        ts_color = "#94a3b8" if dark else "#64748b"
        fs = "15px"
        msg_color = "#e2e8f0" if dark else "#0f172a"
        if any(k in msg_l for k in ("error", "failed", "warning", "denied", "not found", "timed out")):
            msg_color = "#fca5a5" if dark else "#b91c1c"
        elif any(k in msg_l for k in ("saved", "ok", "success", "running", "started", "connected")):
            msg_color = "#86efac" if dark else "#15803d"
        elif any(k in msg_l for k in ("refresh", "adb:", "screen:", "session")):
            msg_color = "#7dd3fc" if dark else "#0369a1"
        safe_msg = html.escape(message)
        line = (
            f'<div style="margin:4px 0 6px 0;line-height:1.45;">'
            f'<span style="color:{ts_color};font-size:{fs};">{ts}</span>'
            f'<span style="color:{msg_color};margin-left:10px;font-size:{fs};">{safe_msg}</span>'
            f"</div>"
        )
        self.log_view.append(line)
        self.log_view.moveCursor(QTextCursor.End)

    def _refresh_log_after_theme_change(self) -> None:
        if not hasattr(self, "log_view"):
            return
        self.log_view.clear()
        for m in self._log_history:
            self._append_log_html(m)

    def _clear_app_log(self) -> None:
        self._log_history.clear()
        if hasattr(self, "log_view"):
            self.log_view.clear()

    def _apply_theme(self) -> None:
        """Defer stylesheet work via qt-thread-updater so the UI stays responsive after heavy terminal I/O."""
        os.environ.setdefault("QT_API", "pyqt5")
        # Before first show, apply synchronously so the window does not flash the wrong palette.
        if not self.isVisible():
            self._apply_theme_impl()
            return
        try:
            from qt_thread_updater import call_latest
        except Exception:
            self._apply_theme_impl()
            return
        call_latest(self._apply_theme_impl)

    def _apply_theme_impl(self) -> None:
        dark = bool(getattr(self.config, "dark_theme", False))
        self.setStyleSheet(get_stylesheet(dark=dark))
        _icon = create_app_icon(dark=dark)
        self.setWindowIcon(_icon)
        _app = QApplication.instance()
        if _app is not None:
            _app.setWindowIcon(_icon)
        self._refresh_version_label_style()
        self._refresh_log_after_theme_change()

    def _setup_version_status(self) -> None:
        self._version_label = QLabel(f"v{__version__}")
        self._version_label.setObjectName("VersionStatusLabel")
        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().addPermanentWidget(self._version_label)
        self._refresh_version_label_style()

    def _refresh_version_label_style(self) -> None:
        if not hasattr(self, "_version_label"):
            return
        dark = bool(getattr(self.config, "dark_theme", False))
        if dark:
            self._version_label.setStyleSheet(
                "color: #94a3b8; font-size: 11px; padding: 2px 12px; font-weight: 500;"
            )
        else:
            self._version_label.setStyleSheet(
                "color: #64748b; font-size: 11px; padding: 2px 12px; font-weight: 500;"
            )

    def _sync_theme_menu_checks(self) -> None:
        d = bool(getattr(self.config, "dark_theme", False))
        if not hasattr(self, "_action_theme_dark"):
            return
        self._theme_action_group.blockSignals(True)
        try:
            self._action_theme_dark.setChecked(d)
            self._action_theme_light.setChecked(not d)
        finally:
            self._theme_action_group.blockSignals(False)

    def _on_theme_menu(self, action: QAction) -> None:
        dark = action is self._action_theme_dark
        self._apply_theme_config(dark)

    def _apply_theme_config(self, dark: bool) -> None:
        self.config.dark_theme = bool(dark)
        try:
            self.config.save()
        except OSError as exc:
            self.append_log(f"Could not save theme preference: {exc}")
        self._apply_theme()
        self.append_log("Dark theme enabled." if self.config.dark_theme else "Light theme enabled.")

    def _vsep(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.VLine)
        f.setFrameShadow(QFrame.Sunken)
        f.setObjectName("SessionStripVSep")
        return f

    def get_session_profile(self) -> SessionProfile:
        """ADB profile from Terminal tab device bar."""
        return self.terminal.get_session_profile()

    def get_serial_session_profile(self) -> SessionProfile:
        return self.terminal.get_serial_session_profile()

    def get_ssh_profile_from_explorer(self) -> SessionProfile:
        """SFTP fields from File Explorer (for Terminal → SSH)."""
        if hasattr(self, "file_explorer"):
            return self.file_explorer.get_sftp_session_profile()
        return SessionProfile(ConnectionKind.SSH_SFTP)

    def _notify_explorer_session_changed(self):
        if hasattr(self, "file_explorer"):
            self.file_explorer.refresh_all_remotes()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._clamp_window_to_screen)

    def _clamp_window_to_screen(self) -> None:
        """Reduce bogus multi-monitor geometry warnings (e.g. DISPLAY49) by fitting the window to a real screen."""
        try:
            screen = QApplication.screenAt(self.frameGeometry().center())
            if screen is None:
                screen = QApplication.primaryScreen()
            if screen is None:
                return
            ag = screen.availableGeometry()
            fg = self.frameGeometry()
            w = min(fg.width(), ag.width())
            h = min(fg.height(), ag.height())
            x = max(ag.left(), min(fg.x(), ag.right() - w + 1))
            y = max(ag.top(), min(fg.y(), ag.bottom() - h + 1))
            self.setGeometry(x, y, w, h)
        except Exception:
            pass

    def closeEvent(self, event):
        if hasattr(self, "file_explorer") and self.file_explorer.has_active_file_transfer():
            QMessageBox.information(
                self,
                "File transfer in progress",
                "A file is still being pushed or pulled. Wait for the transfer to finish, then close again.",
            )
            event.ignore()
            return
        self._shutting_down = True
        try:
            kill_all_adb_subprocesses()
        except Exception:
            pass
        self.unregister_scrcpy_stop_hotkey()
        if hasattr(self, "_adb_poll_timer"):
            self._adb_poll_timer.stop()
        if hasattr(self, "_adb_stats_timer"):
            self._adb_stats_timer.stop()
        if hasattr(self, "terminal"):
            self.terminal.shutdown_all_sessions()
            if sys.platform == "win32":
                time.sleep(0.2)
        if hasattr(self, "file_explorer"):
            self.file_explorer.disconnect_remote_services()
        if hasattr(self, "scrcpy"):
            self.scrcpy.shutdown(fast=True)
        cam = getattr(self, "camera", None)
        if cam is not None:
            cam.shutdown(fast=True)
        for _name in ("_device_refresh_thread", "_stats_refresh_thread"):
            th = getattr(self, _name, None)
            if th is not None:
                if th.isRunning():
                    if not th.wait(15000):
                        try:
                            th.terminate()
                        except Exception:
                            pass
                        th.wait(3000)
                setattr(self, _name, None)
        super().closeEvent(event)

    def nativeEvent(self, eventType, message):
        """Windows: Ctrl+Alt+F12 or Ctrl+Alt+End stops scrcpy even when the mirror has focus."""
        if sys.platform == "win32" and is_windows_hotkey_message(eventType, message):
            if hasattr(self, "scrcpy"):
                self.scrcpy.stop_scrcpy()
            return True, 0
        return super().nativeEvent(eventType, message)

    def register_scrcpy_stop_hotkey(self) -> None:
        if sys.platform != "win32" or self._scrcpy_hotkey_registered:
            return
        try:
            hwnd = int(self.winId())
        except Exception:
            return
        if _win_register_scrcpy_hotkey(hwnd):
            self._scrcpy_hotkey_registered = True
            self.append_log(
                "Screen: Ctrl+Alt+F12 or Ctrl+Alt+End stops the mirror anytime (even fullscreen). "
                "Or View → Stop screen mirror."
            )
        else:
            self.append_log(
                "Screen: could not register stop hotkeys (in use or denied). Use View → Stop screen mirror."
            )

    def unregister_scrcpy_stop_hotkey(self) -> None:
        if sys.platform != "win32" or not self._scrcpy_hotkey_registered:
            return
        try:
            _win_unregister_scrcpy_hotkey(int(self.winId()))
        except Exception:
            pass
        self._scrcpy_hotkey_registered = False

    def _build_ui(self):
        """Create the central splitter (tabs + log), wire tabs to services, then build the menu bar."""
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(6)

        body = QWidget()
        body.setObjectName("MainBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(4)

        body_split = QSplitter(Qt.Vertical)
        body_split.setObjectName("MainBodySplit")
        body_split.setChildrenCollapsible(False)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("MainTabs")
        tb = self.tabs.tabBar()
        tb.setElideMode(Qt.ElideNone)
        tb.setUsesScrollButtons(True)
        self.terminal = TerminalTab(
            self.get_adb_path,
            self.get_default_ssh_host,
            self.get_default_serial_port,
            self.get_default_serial_baud,
            self.config,
            append_log=self.append_log,
        )
        self.file_explorer = FileExplorerTab(
            self.get_adb_path,
            self.append_log,
            config=self.config,
            on_refresh_devices=self.refresh_devices,
            get_default_ssh_host=self.get_default_ssh_host,
            on_remote_session_changed=self._notify_explorer_session_changed,
        )
        self.scrcpy = ScrcpyTab(
            self.get_scrcpy_path,
            self.get_adb_path,
            self.append_log,
            get_serial=lambda: self.terminal.current_adb_serial(),
            config=self.config,
        )
        self.camera = None  # lazily created CameraTab when the Camera tab is first opened (keeps startup fast)
        self._camera_tab_built = False
        self._camera_placeholder = QWidget()
        _cph = QVBoxLayout(self._camera_placeholder)
        _cph.setContentsMargins(16, 24, 16, 24)
        _cam_lazy_lbl = QLabel(
            "Camera loads when you open this tab so the rest of the window stays responsive."
        )
        _cam_lazy_lbl.setWordWrap(True)
        _cam_lazy_lbl.setObjectName("CameraLazyHintLabel")
        _cph.addWidget(_cam_lazy_lbl)
        _cph.addStretch()
        st = self.style()
        self.tabs.addTab(self.terminal, st.standardIcon(QStyle.SP_FileDialogDetailedView), "Terminal")
        self.tabs.addTab(self.file_explorer, st.standardIcon(QStyle.SP_DirLinkIcon), "File Explorer")
        self.tabs.addTab(self.scrcpy, st.standardIcon(QStyle.SP_ComputerIcon), "Screen Control")
        self.tabs.addTab(
            self._camera_placeholder,
            st.standardIcon(getattr(QStyle, "SP_CameraIcon", QStyle.SP_DesktopIcon)),
            "Camera",
        )
        self.tabs.tabBar().setIconSize(QSize(18, 18))
        self._prev_main_tab_index = 0
        self.tabs.currentChanged.connect(self._on_main_tab_changed)
        self.terminal.device_combo.currentTextChanged.connect(self._on_device_combo_changed)
        body_split.addWidget(self.tabs)

        log_wrap = QWidget()
        log_v = QVBoxLayout(log_wrap)
        log_v.setContentsMargins(0, 0, 0, 0)
        log_v.setSpacing(4)

        log_row = QHBoxLayout()
        log_row.setSpacing(6)
        log_lbl = QLabel("Log")
        log_lbl.setObjectName("LogPanelLabel")
        log_row.addWidget(log_lbl)
        log_row.addStretch()
        clear_log = QPushButton("Clear")
        clear_log.setObjectName("HeaderMiniBtn")
        clear_log.setIcon(self.style().standardIcon(QStyle.SP_LineEditClearButton))
        clear_log.clicked.connect(self._clear_app_log)
        log_row.addWidget(clear_log)
        save_log = QPushButton("Save log")
        save_log.setObjectName("HeaderMiniBtn")
        save_log.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        save_log.clicked.connect(self._save_app_log)
        log_row.addWidget(save_log)
        log_v.addLayout(log_row)

        self.log_view = QTextBrowser()
        self.log_view.setObjectName("AppLogView")
        self.log_view.setReadOnly(True)
        self.log_view.setOpenExternalLinks(True)
        self.log_view.document().setMaximumBlockCount(4000)
        self.log_view.setFont(QFont("Consolas", 12))
        self.log_view.setPlaceholderText(
            "Application log — newest lines at the bottom. Tags: OK (green), ERR (red), INFO (blue)."
        )
        self.log_view.setMinimumHeight(140)
        self.log_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.log_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.log_view.customContextMenuRequested.connect(self._log_context_menu)
        log_v.addWidget(self.log_view, 1)

        body_split.addWidget(log_wrap)
        body_split.setStretchFactor(0, 1)
        body_split.setStretchFactor(1, 0)
        body_split.setSizes([720, 260])

        body_layout.addWidget(body_split, 1)

        root.addWidget(body, 1)

        self.setCentralWidget(central)
        self._build_menu_bar()

    def prompt_first_run_if_needed(self) -> None:
        if not self._first_launch:
            return
        self._first_launch = False
        dlg = FirstRunDialog(self.config, self, is_upgrade=self._is_upgrade_welcome)
        if dlg.exec_():
            self._apply_theme()
            self._sync_theme_menu_checks()
            self.append_log("Welcome — preferences saved. Use File → Preferences anytime.")
        else:
            self.append_log("Using defaults. Open File → Preferences to set paths and theme.")

    def _open_serial_terminal_tab(self):
        self.tabs.setCurrentIndex(0)
        self.terminal.open_session_matching_profile(self.get_serial_session_profile())

    def _serial_from_combo_text(self, text: str) -> str:
        t = (text or "").strip()
        if not t or t.startswith("No ") or "not found" in t.lower():
            return ""
        return t.split()[0]

    def _lazy_init_camera_tab(self) -> None:
        """Instantiate Qt Multimedia camera UI only on first visit — avoids slowing cold start."""
        if self._camera_tab_built:
            return
        from .tabs.camera_tab import CameraTab

        self._camera_tab_built = True
        idx = self.tabs.indexOf(self._camera_placeholder)
        if idx < 0:
            return
        # removeTab() can switch current tab to another index; restore Camera after insert.
        self.tabs.blockSignals(True)
        try:
            self.tabs.removeTab(idx)
            self.camera = CameraTab(
                self.append_log,
                get_output_dir=self.get_camera_output_dir,
                set_output_dir=self.set_camera_output_dir,
            )
            self.tabs.insertTab(
                idx,
                self.camera,
                self.style().standardIcon(getattr(QStyle, "SP_CameraIcon", QStyle.SP_DesktopIcon)),
                "Camera",
            )
            self.tabs.setCurrentIndex(idx)
        finally:
            self.tabs.blockSignals(False)

    def _on_main_tab_changed(self, index: int) -> None:
        if index == 3:
            self._lazy_init_camera_tab()
        prev = getattr(self, "_prev_main_tab_index", 0)
        if prev == 3 and index != 3:
            cam = getattr(self, "camera", None)
            if cam is not None:
                try:
                    cam.pause_for_background()
                except Exception:
                    try:
                        cam.shutdown(fast=True)
                    except Exception:
                        pass
        self._prev_main_tab_index = index
        if index == 0 and hasattr(self, "terminal"):
            self.terminal._reload_bookmark_sidebar()
        if index == 1:
            # Avoid spawning back-to-back ADB refresh threads when flipping Terminal ↔ Files (reduces races / warnings).
            now = time.monotonic()
            if now - getattr(self, "_last_files_tab_device_refresh", 0.0) >= 2.0:
                self._last_files_tab_device_refresh = now
                self.refresh_devices()

    def _on_device_combo_changed(self, _text: str):
        if hasattr(self, "file_explorer"):
            self.file_explorer.set_remote_device(self.terminal.current_adb_serial())
        self.refresh_device_stats()

    def refresh_devices(self):
        if getattr(self, "_shutting_down", False):
            return
        if not hasattr(self, "terminal"):
            return
        if self._device_refresh_thread and self._device_refresh_thread.isRunning():
            self._device_refresh_pending = True
            return
        self._prev_selected_serial_for_refresh = self.terminal.current_adb_serial()
        th = _AdbDevicesRefreshThread(self.get_adb_path(), self)
        th.done.connect(self._on_devices_refreshed, Qt.QueuedConnection)
        self._device_refresh_thread = th
        th.start()

    def _on_devices_refreshed(self, pairs, adb_ok: bool) -> None:
        th = self.sender()
        if th is not self._device_refresh_thread:
            if isinstance(th, QThread):
                if th.isRunning():
                    th.wait(15000)
                th.deleteLater()
            return
        self._device_refresh_thread = None
        if isinstance(th, QThread):
            if th.isRunning():
                th.wait(15000)
            th.deleteLater()
        prev_selected_serial = getattr(self, "_prev_selected_serial_for_refresh", "")
        prev_sig = getattr(self, "_last_adb_device_sig", None)
        sig = tuple(pairs) if pairs else ()
        self.terminal.device_combo.blockSignals(True)
        self.terminal.device_combo.clear()
        if not pairs:
            if not adb_ok:
                self.terminal.device_combo.addItem("ADB not found")
                self.terminal.device_combo.blockSignals(False)
                if hasattr(self, "file_explorer"):
                    self.file_explorer.set_remote_device("")
                if prev_sig != ("__adb_err__",):
                    self._last_adb_device_sig = ("__adb_err__",)
                    self.append_log("ADB not responding — check ADB path in Preferences (menu).")
            else:
                self.terminal.device_combo.addItem("No device")
                self.terminal.device_combo.blockSignals(False)
                if hasattr(self, "file_explorer"):
                    self.file_explorer.set_remote_device("")
                if prev_sig != ():
                    self._last_adb_device_sig = ()
                    self.append_log("ADB: no devices detected — connect a device, enable USB debugging, and authorize this PC.")
        else:
            selected_index = 0
            for serial, display in pairs:
                self.terminal.device_combo.addItem(display, serial)
                if prev_selected_serial and serial == prev_selected_serial:
                    selected_index = self.terminal.device_combo.count() - 1
            self.terminal.device_combo.setCurrentIndex(selected_index)
            self.terminal.device_combo.blockSignals(False)
            if hasattr(self, "file_explorer"):
                self.file_explorer.set_remote_device(self.terminal.current_adb_serial())
            if sig != prev_sig:
                self._last_adb_device_sig = sig
                self.append_log(
                    f"ADB: {len(pairs)} device(s) — {', '.join(s for s, _ in pairs[:5])}{'…' if len(pairs) > 5 else ''}"
                )
                if hasattr(self, "file_explorer") and self.tabs.currentWidget() is self.file_explorer:
                    QTimer.singleShot(0, self.file_explorer.refresh_all_remotes)
        if self._device_refresh_pending:
            self._device_refresh_pending = False
            self.refresh_devices()
        self.refresh_device_stats()

    def _format_uptime(self, seconds: float) -> str:
        s = max(0, int(seconds))
        d, rem = divmod(s, 86400)
        h, rem = divmod(rem, 3600)
        m, _ = divmod(rem, 60)
        if d > 0:
            return f"{d}d {h}h {m}m"
        if h > 0:
            return f"{h}h {m}m"
        return f"{m}m"

    def _parse_device_stats(self, serial: str, raw: str) -> str:
        lines = [ln.strip() for ln in (raw or "").splitlines() if ln.strip()]
        uptime_sec = 0.0
        cpu_total = None
        cpu_idle = None
        mem_total_kb = None
        mem_avail_kb = None
        for ln in lines:
            if ln.startswith("cpu "):
                parts = ln.split()[1:]
                vals = []
                for p in parts:
                    try:
                        vals.append(int(p))
                    except ValueError:
                        vals.append(0)
                if len(vals) >= 4:
                    cpu_total = sum(vals)
                    cpu_idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
            elif "MemTotal:" in ln:
                try:
                    mem_total_kb = int(ln.split(":", 1)[1].strip().split()[0])
                except (ValueError, IndexError):
                    pass
            elif "MemAvailable:" in ln:
                try:
                    mem_avail_kb = int(ln.split(":", 1)[1].strip().split()[0])
                except (ValueError, IndexError):
                    pass
            elif uptime_sec <= 0.0 and " " in ln:
                parts = ln.split()
                try:
                    uptime_sec = float(parts[0])
                except (ValueError, IndexError):
                    pass

        cpu_txt = "CPU --"
        if cpu_total is not None and cpu_idle is not None:
            prev = self._stats_prev_cpu.get(serial)
            self._stats_prev_cpu[serial] = (cpu_total, cpu_idle)
            if prev is not None:
                dt = max(1, cpu_total - prev[0])
                di = max(0, cpu_idle - prev[1])
                usage = max(0.0, min(100.0, 100.0 * (dt - di) / dt))
                cpu_txt = f"CPU {usage:.0f}%"

        mem_txt = "RAM --"
        if mem_total_kb and mem_avail_kb is not None and mem_total_kb > 0:
            used = max(0, mem_total_kb - mem_avail_kb)
            pct = 100.0 * used / mem_total_kb
            mem_txt = f"RAM {pct:.0f}% ({used // 1024}MB/{mem_total_kb // 1024}MB)"

        up_txt = f"Uptime {self._format_uptime(uptime_sec)}" if uptime_sec > 0 else "Uptime --"
        return f"{up_txt} · {cpu_txt} · {mem_txt}"

    def _apply_device_stats(self, text: str) -> None:
        stats = (text or "").strip()
        if hasattr(self, "terminal"):
            self.terminal.set_device_stats_text(stats)
        if hasattr(self, "file_explorer"):
            self.file_explorer.set_device_stats_text(stats)

    def refresh_device_stats(self) -> None:
        if getattr(self, "_shutting_down", False):
            return
        if not hasattr(self, "terminal"):
            return
        serial = (self.terminal.current_adb_serial() or "").strip()
        if not serial:
            self._apply_device_stats("")
            return
        if self._stats_refresh_thread and self._stats_refresh_thread.isRunning():
            self._stats_refresh_pending = True
            return
        th = _AdbDeviceStatsThread(self.get_adb_path(), serial, self)
        th.done.connect(self._on_device_stats_ready, Qt.QueuedConnection)
        self._stats_refresh_thread = th
        th.start()

    def _on_device_stats_ready(self, serial: str, raw: object, err: str) -> None:
        th = self.sender()
        if th is not self._stats_refresh_thread:
            if isinstance(th, QThread):
                if th.isRunning():
                    th.wait(15000)
                th.deleteLater()
            return
        self._stats_refresh_thread = None
        if isinstance(th, QThread):
            if th.isRunning():
                th.wait(15000)
            th.deleteLater()
        current = (self.terminal.current_adb_serial() or "").strip() if hasattr(self, "terminal") else ""
        if serial and current and serial != current:
            return
        if err:
            self._apply_device_stats("Uptime -- · CPU -- · RAM --")
        else:
            txt = self._parse_device_stats(serial, str(raw or ""))
            try:
                from qt_thread_updater import call_latest

                call_latest(self._apply_device_stats, txt)
            except Exception:
                self._apply_device_stats(txt)
        if self._stats_refresh_pending:
            self._stats_refresh_pending = False
            self.refresh_device_stats()

    def _build_menu_bar(self):
        """Populate File, Edit, Session, Commands, View, and Help menus (rebuilt when preferences change)."""
        bar = self.menuBar()
        bar.clear()
        bar.setObjectName("AppMenuBar")
        bar.setNativeMenuBar(True)

        file_menu = bar.addMenu("&File")
        a_new_session = QAction("&New session…", self)
        a_new_session.setIcon(self.style().standardIcon(QStyle.SP_FileDialogNewFolder))
        a_new_session.setShortcut(QKeySequence("Ctrl+N"))
        a_new_session.triggered.connect(self._menu_session_new_ssh)
        file_menu.addAction(a_new_session)
        a_pref = QAction("&Preferences…", self)
        a_pref.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        a_pref.setShortcut(QKeySequence("Ctrl+,"))
        a_pref.triggered.connect(self._open_preferences)
        file_menu.addAction(a_pref)
        a_save_settings = QAction("&Save settings", self)
        a_save_settings.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        a_save_settings.setShortcut(QKeySequence("Ctrl+S"))
        a_save_settings.triggered.connect(self._save_config_to_disk)
        file_menu.addAction(a_save_settings)
        file_menu.addSeparator()
        a_exit = QAction("E&xit", self)
        a_exit.setIcon(self.style().standardIcon(QStyle.SP_DialogCloseButton))
        a_exit.setShortcut(QKeySequence("Alt+F4"))
        a_exit.triggered.connect(self.close)
        file_menu.addAction(a_exit)

        edit_menu = bar.addMenu("&Edit")
        a_copy_log = QAction("&Copy log", self)
        a_copy_log.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        a_copy_log.setShortcut(QKeySequence.Copy)
        a_copy_log.triggered.connect(lambda: QApplication.clipboard().setText(self.log_view.toPlainText()))
        edit_menu.addAction(a_copy_log)
        a_clear_log = QAction("C&lear log", self)
        a_clear_log.setIcon(self.style().standardIcon(QStyle.SP_LineEditClearButton))
        a_clear_log.setShortcut(QKeySequence("Ctrl+L"))
        a_clear_log.triggered.connect(self._clear_app_log)
        edit_menu.addAction(a_clear_log)
        a_save_log = QAction("Save &log as…", self)
        a_save_log.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        a_save_log.setShortcut(QKeySequence("Ctrl+Shift+S"))
        a_save_log.triggered.connect(self._save_app_log)
        edit_menu.addAction(a_save_log)

        session = bar.addMenu("&Session")
        adb_menu = session.addMenu("ADB")
        adb_menu.setIcon(icon_adb_android())
        a_refresh = QAction("Refresh / reload remote", self)
        a_refresh.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        a_refresh.setShortcut(QKeySequence("F5"))
        a_refresh.triggered.connect(self._menu_session_refresh_devices)
        adb_menu.addAction(a_refresh)
        a_reconn = QAction("Reconnect &ADB", self)
        a_reconn.setIcon(self.style().standardIcon(QStyle.SP_DriveNetIcon))
        a_reconn.triggered.connect(self._menu_session_adb_reconnect)
        adb_menu.addAction(a_reconn)
        a_restart = QAction("Restart ADB &server", self)
        a_restart.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        a_restart.triggered.connect(self._menu_session_restart_server)
        adb_menu.addAction(a_restart)
        a_adb_shell = QAction("Open &ADB shell (Terminal tab)", self)
        a_adb_shell.setIcon(icon_adb_android())
        a_adb_shell.triggered.connect(self._menu_session_adb_shell)
        adb_menu.addAction(a_adb_shell)
        a_install_apk = QAction("Install &APK on selected device…", self)
        a_install_apk.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        a_install_apk.setToolTip("Runs adb install -r against the device chosen in the Terminal tab.")
        a_install_apk.triggered.connect(self._menu_install_apk)
        adb_menu.addAction(a_install_apk)

        ssh_menu = session.addMenu("SSH")
        ssh_menu.setIcon(self.style().standardIcon(QStyle.SP_DriveNetIcon))
        a_open_ssh = QAction("Open &SSH terminal (from Explorer SFTP fields)…", self)
        a_open_ssh.setIcon(self.style().standardIcon(QStyle.SP_DriveNetIcon))
        a_open_ssh.triggered.connect(self._menu_open_ssh_from_explorer)
        ssh_menu.addAction(a_open_ssh)
        a_new_ssh = QAction("New &SSH session…", self)
        a_new_ssh.setIcon(self.style().standardIcon(QStyle.SP_FileDialogNewFolder))
        a_new_ssh.triggered.connect(self._menu_session_new_ssh)
        ssh_menu.addAction(a_new_ssh)


        commands = bar.addMenu("&Commands")
        adb_cmd = commands.addMenu("ADB")
        adb_cmd.setIcon(icon_adb_android())
        a_root = QAction("ADB &root", self)
        a_root.setIcon(self.style().standardIcon(QStyle.SP_VistaShield))
        a_root.triggered.connect(self._menu_cmd_adb_root)
        adb_cmd.addAction(a_root)
        a_unroot = QAction("ADB &unroot", self)
        a_unroot.setIcon(self.style().standardIcon(QStyle.SP_DialogCancelButton))
        a_unroot.triggered.connect(self._menu_cmd_adb_unroot)
        adb_cmd.addAction(a_unroot)
        a_remount = QAction("ADB &remount", self)
        a_remount.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        a_remount.triggered.connect(self._menu_cmd_adb_remount)
        adb_cmd.addAction(a_remount)
        a_reboot = QAction("ADB &reboot device", self)
        a_reboot.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        a_reboot.triggered.connect(self._menu_cmd_adb_reboot)
        adb_cmd.addAction(a_reboot)

        ssh_cmd = commands.addMenu("SSH")
        ssh_cmd.setIcon(self.style().standardIcon(QStyle.SP_DriveNetIcon))
        for i, qc in enumerate(getattr(self.config, "ssh_quick_commands", None) or []):
            if not isinstance(qc, dict):
                continue
            lab = str(qc.get("label", "") or "Command").strip()
            cmd = str(qc.get("command", "")).strip()
            if not cmd:
                continue
            act = QAction(lab, self)
            act.setIcon(self.style().standardIcon(QStyle.SP_ArrowRight))
            act.triggered.connect(lambda checked=False, c=cmd: self._menu_ssh_send_line(c))
            ssh_cmd.addAction(act)

        view = bar.addMenu("&View")
        a_term = QAction("&Terminal", self)
        a_term.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        a_term.setShortcut(QKeySequence("Ctrl+1"))
        a_term.triggered.connect(lambda: self.tabs.setCurrentIndex(0))
        view.addAction(a_term)
        a_fe = QAction("&File Explorer", self)
        a_fe.setIcon(self.style().standardIcon(QStyle.SP_DirIcon))
        a_fe.setShortcut(QKeySequence("Ctrl+2"))
        a_fe.triggered.connect(lambda: self.tabs.setCurrentIndex(1))
        view.addAction(a_fe)
        a_scr = QAction("&Screen Control", self)
        a_scr.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        a_scr.setShortcut(QKeySequence("Ctrl+3"))
        a_scr.triggered.connect(lambda: self.tabs.setCurrentIndex(2))
        view.addAction(a_scr)
        a_cam = QAction("&Camera", self)
        a_cam.setIcon(self.style().standardIcon(getattr(QStyle, "SP_CameraIcon", QStyle.SP_DesktopIcon)))
        a_cam.setShortcut(QKeySequence("Ctrl+4"))
        a_cam.triggered.connect(lambda: self.tabs.setCurrentIndex(3))
        view.addAction(a_cam)
        a_cmd_palette = QAction("Command &palette…", self)
        a_cmd_palette.setShortcut(QKeySequence("Ctrl+Shift+P"))
        a_cmd_palette.setIcon(self.style().standardIcon(QStyle.SP_FileDialogContentsView))
        a_cmd_palette.triggered.connect(self._open_command_palette)
        view.addAction(a_cmd_palette)
        view.addSeparator()
        a_stop_scr = QAction("Stop &screen mirror", self)
        a_stop_scr.setIcon(self.style().standardIcon(QStyle.SP_BrowserStop))
        a_stop_scr.setShortcuts(
            [QKeySequence("Ctrl+Alt+F12"), QKeySequence("Ctrl+Alt+End")]
        )
        a_stop_scr.setToolTip("Stops scrcpy even when the mirror is fullscreen or has focus (Windows global hotkeys).")
        a_stop_scr.triggered.connect(self._menu_stop_screen_mirror)
        view.addAction(a_stop_scr)
        view.addSeparator()
        theme_menu = view.addMenu("&Theme")
        theme_menu.setIcon(self.style().standardIcon(QStyle.SP_DesktopIcon))
        self._theme_action_group = QActionGroup(self)
        self._theme_action_group.setExclusive(True)
        self._action_theme_light = QAction("&Light", self)
        self._action_theme_light.setCheckable(True)
        self._action_theme_dark = QAction("&Dark", self)
        self._action_theme_dark.setCheckable(True)
        self._theme_action_group.addAction(self._action_theme_light)
        self._theme_action_group.addAction(self._action_theme_dark)
        self._theme_action_group.triggered.connect(self._on_theme_menu)
        theme_menu.addAction(self._action_theme_light)
        theme_menu.addAction(self._action_theme_dark)

        help_menu = bar.addMenu("&Help")
        a_site = QAction("Adbnik &website", self)
        a_site.setIcon(self.style().standardIcon(QStyle.SP_DialogHelpButton))
        a_site.triggered.connect(lambda: self._open_help_url(WEBSITE_HOME))
        help_menu.addAction(a_site)
        a_guide = QAction("&User guide", self)
        a_guide.setShortcut(QKeySequence("F1"))
        a_guide.triggered.connect(lambda: self._open_help_url(USER_GUIDE))
        help_menu.addAction(a_guide)
        a_gh = QAction("&GitHub repository", self)
        a_gh.setIcon(self.style().standardIcon(QStyle.SP_DriveNetIcon))
        a_gh.triggered.connect(lambda: self._open_help_url(GITHUB_REPO))
        help_menu.addAction(a_gh)
        a_pypi = QAction("&PyPI package", self)
        a_pypi.triggered.connect(lambda: self._open_help_url(PYPI_PROJECT))
        help_menu.addAction(a_pypi)
        help_menu.addSeparator()
        a_about = QAction(f"&About {APP_TITLE}", self)
        a_about.setIcon(self.style().standardIcon(QStyle.SP_MessageBoxInformation))
        a_about.triggered.connect(self._menu_help_about)
        help_menu.addAction(a_about)

        self._sync_theme_menu_checks()

    def _open_help_url(self, url: str) -> None:
        """Open a documentation or project URL in the default browser."""
        QDesktopServices.openUrl(QUrl(url))

    def _menu_stop_screen_mirror(self) -> None:
        if hasattr(self, "scrcpy"):
            self.scrcpy.stop_scrcpy()

    def _show_health_dialog(self) -> None:
        term_total = 0
        term_running = 0
        if hasattr(self, "terminal") and hasattr(self.terminal, "tabs"):
            for i in range(self.terminal.tabs.count()):
                w = self.terminal.tabs.widget(i)
                if hasattr(w, "proc"):
                    term_total += 1
                    try:
                        if w.proc.state() == 2:  # QProcess.Running
                            term_running += 1
                    except Exception:
                        pass
        scr_status = "idle"
        if hasattr(self, "scrcpy") and getattr(self.scrcpy, "proc", None) is not None:
            try:
                scr_status = "running" if self.scrcpy.proc.state() == 2 else "stopped"
            except Exception:
                scr_status = "unknown"
        exp_total = self.file_explorer.session_tabs.count() if hasattr(self, "file_explorer") else 0
        QMessageBox.information(
            self,
            "Session Health",
            f"Terminal sessions: {term_running}/{term_total} running\n"
            f"Screen mirror: {scr_status}\n"
            f"Explorer sessions: {exp_total}\n"
            f"ADB selected: {(self.terminal.current_adb_serial() or 'none') if hasattr(self, 'terminal') else 'none'}",
        )

    def _open_command_palette(self) -> None:
        items = [
            "Open Terminal",
            "Open File Explorer",
            "Open Screen Control",
            "Open Camera",
            "Reconnect ADB",
            "Reconnect Screen Mirror",
            "Reconnect Explorer Remote",
            "Show Session Health",
            "Refresh Devices",
        ]
        choice, ok = QInputDialog.getItem(self, "Command Palette", "Action", items, 0, False)
        if not ok or not choice:
            return
        if choice == "Open Terminal":
            self.tabs.setCurrentIndex(0)
        elif choice == "Open File Explorer":
            self.tabs.setCurrentIndex(1)
        elif choice == "Open Screen Control":
            self.tabs.setCurrentIndex(2)
        elif choice == "Open Camera":
            self.tabs.setCurrentIndex(3)
        elif choice == "Reconnect ADB":
            self._menu_session_adb_reconnect()
        elif choice == "Reconnect Screen Mirror":
            if hasattr(self, "scrcpy"):
                self.scrcpy.reconnect_scrcpy()
        elif choice == "Reconnect Explorer Remote":
            if hasattr(self, "file_explorer"):
                page = self.file_explorer._current_page()
                if page is not None:
                    page.user_requested_reconnect_remote()
        elif choice == "Show Session Health":
            self._show_health_dialog()
        elif choice == "Refresh Devices":
            self.refresh_devices()

    def _open_preferences(self):
        dlg = PreferencesDialog(self.config, self)
        if dlg.exec_():
            self.append_log("Preferences saved.")
            if hasattr(self, "terminal"):
                self.terminal.sync_serial_from_config()
            self.refresh_devices()
            self._build_menu_bar()

    def _save_config_to_disk(self):
        try:
            self.config.save()
            self.append_log("Configuration saved.")
            QMessageBox.information(self, "Saved", "Configuration saved.")
        except Exception as exc:
            self.append_log(f"Save failed: {exc}")
            QMessageBox.warning(self, "Save Failed", f"Unable to save config: {exc}")

    def _menu_session_refresh_devices(self):
        self.refresh_devices()
        self.file_explorer.refresh_remote()
        self.append_log("Refreshed.")

    def _menu_open_connection_terminal(self):
        self.tabs.setCurrentIndex(0)
        self.terminal.open_session_matching_profile(self.get_session_profile())

    def _menu_open_ssh_from_explorer(self):
        self.tabs.setCurrentIndex(0)
        profile = self.get_ssh_profile_from_explorer()
        self.terminal.open_session_matching_profile(profile)

    def _menu_session_adb_reconnect(self):
        self.file_explorer.action_adb_reconnect()

    def _menu_session_restart_server(self):
        self.file_explorer.action_restart_adb_server()

    def _menu_session_new_ssh(self):
        self.tabs.setCurrentIndex(0)
        self.terminal.add_session_dialog()

    def _menu_session_adb_shell(self):
        self.tabs.setCurrentIndex(0)
        self.terminal.open_session_matching_profile(self.get_session_profile())

    def _menu_install_apk(self) -> None:
        self.tabs.setCurrentIndex(0)
        adb = self.get_adb_path()
        serial = self.terminal.current_adb_serial()
        if not serial:
            QMessageBox.warning(
                self,
                "No device",
                "No Android device is selected for ADB. Connect a device with USB debugging, "
                "wait until it appears in the ADB device list, then pick it — same selection used for "
                "Terminal and File Explorer — and try again.",
            )
            return
        path, _ = get_open_filename(
            self,
            "Install APK",
            "",
            "Android packages (*.apk);;All files (*.*)",
        )
        if not path:
            return
        self.append_log(f"ADB: installing APK on {serial} …")
        args = ["-s", serial, "install", "-r", path]

        def on_line(line: str) -> None:
            self.append_log(line.rstrip())

        code, out, err = run_adb_with_line_callback(adb, args, timeout=600, on_line=on_line)
        tail = (err or out or "").strip()
        if code != 0:
            msg = f"adb install exited with code {code}."
            if tail:
                msg += f"\n\n{tail[-1200:]}"
            self.append_log(f"ADB install failed: {msg.replace(chr(10), ' ')}")
            QMessageBox.warning(self, "Install failed", msg)
            return
        self.append_log("ADB: install finished.")
        QMessageBox.information(self, "Install", "APK install finished. See the application log for adb output.")

    def _menu_cmd_adb_root(self):
        self.tabs.setCurrentIndex(1)
        self.file_explorer.action_adb_root()

    def _menu_cmd_adb_unroot(self):
        self.tabs.setCurrentIndex(1)
        self.file_explorer.action_adb_unroot()

    def _menu_cmd_adb_remount(self):
        self.tabs.setCurrentIndex(1)
        self.file_explorer.action_adb_remount()

    def _menu_cmd_adb_reboot(self):
        self.tabs.setCurrentIndex(1)
        self.file_explorer.action_adb_reboot()

    def _menu_ssh_send_line(self, line: str):
        self.tabs.setCurrentIndex(0)
        self.terminal.send_line_to_ssh_session(line)

    def _menu_help_about(self) -> None:
        """Show version, feature summary, and links to the site, guide, GitHub, and PyPI."""
        dlg = QDialog(self)
        dlg.setWindowTitle(f"About {APP_TITLE} — v{__version__}")
        dlg.setModal(True)
        dlg.setWindowIcon(self.windowIcon())
        dlg.resize(560, 480)
        lay = QVBoxLayout(dlg)
        body = QTextBrowser()
        body.setReadOnly(True)
        body.setOpenExternalLinks(True)
        py_ver = html.escape(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
        plat = html.escape(platform.platform())
        ver_esc = html.escape(__version__)
        dark = bool(getattr(self.config, "dark_theme", False))
        fg = "#e6edf3" if dark else "#0f172a"
        sub = "#94a3b8" if dark else "#334155"
        muted = "#64748b" if not dark else "#94a3b8"
        body.setHtml(
            f"""
<!DOCTYPE html>
<html><body style="font-family:Segoe UI,Arial,sans-serif;font-size:13px;color:{fg};line-height:1.45;">
<h2 style="margin-top:0;">{html.escape(APP_TITLE)}</h2>
<p style="color:{sub}; margin-bottom:8px;"><b>Version</b> {ver_esc}</p>
<p style="color:{sub};">A desktop workspace for Android debugging, remote files, and screen control. Built with
PyQt5 and Python {py_ver} on {plat}.</p>

<p style="margin-bottom:12px;">
<a href="{html.escape(WEBSITE_HOME)}">Website</a> ·
<a href="{html.escape(USER_GUIDE)}">User guide</a> ·
<a href="{html.escape(GITHUB_REPO)}">GitHub</a> ·
<a href="{html.escape(PYPI_PROJECT)}">PyPI</a>
</p>

<h3 style="margin-bottom:6px;">What you can do</h3>
<ul style="margin-top:0;">
<li><b>Terminal</b> — SSH, ADB shell, serial, and local shells. Sessions and bookmarks live in the sidebar.</li>
<li><b>File Explorer</b> — WinSCP-style <b>Local | Remote</b> panes per session: ADB device storage, SFTP, or FTP.
Pull, push, drag-and-drop, find files, and external editors with sync where supported.</li>
<li><b>Screen Control</b> — Launch and manage <b>scrcpy</b> mirroring (paths and options in Preferences).</li>
<li><b>Camera</b> — USB or built-in webcam preview, snapshots, optional MP4 recording; choose the save folder from the tab.</li>
</ul>

<h3 style="margin-bottom:6px;">Menus worth knowing</h3>
<ul style="margin-top:0;">
<li><b>File → Preferences</b> — ADB/scrcpy paths, dark theme, serial defaults, and <b>SSH quick commands</b>
(label and command per line: <code>Label | command</code>). Those commands appear under <b>Commands → SSH</b>.</li>
<li><b>Session</b> — Refresh devices (F5), ADB tools (including <b>Install APK</b> on the selected device),
open SSH using Explorer’s SFTP host or a new session.</li>
<li><b>Commands</b> — ADB shortcuts (root, remount, reboot) and your custom SSH lines from Preferences.</li>
<li><b>View</b> — Jump tabs (<b>Ctrl+1</b> Terminal, <b>Ctrl+2</b> Explorer, <b>Ctrl+3</b> Screen, <b>Ctrl+4</b> Camera), stop screen mirror, toggle dark theme.</li>
</ul>

<h3 style="margin-bottom:6px;">Tips</h3>
<ul style="margin-top:0;">
<li>Long file searches run in the background so you can keep using the window.</li>
<li>Folder rows show “…” in the size column (listing big folders fast skips per-folder totals). Use <b>Properties</b> on a folder when you need a full recursive size.</li>
</ul>

<p style="color:{muted};font-size:12px;margin-bottom:0;">Configuration is stored in your user profile
(<code>.adbnik.json</code>). Bookmarks never store passwords.</p>
</body></html>
"""
        )
        lay.addWidget(body)
        bb = QDialogButtonBox(QDialogButtonBox.Ok)
        bb.accepted.connect(dlg.accept)
        lay.addWidget(bb)
        dlg.exec_()

    def _log_context_menu(self, pos) -> None:
        m = self.log_view.createStandardContextMenu()
        m.addSeparator()
        a_save = m.addAction("Save log as…")
        a_save.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        a_save.triggered.connect(self._save_app_log)
        m.exec_(self.log_view.mapToGlobal(pos))

    def _save_app_log(self) -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path, _ = get_save_filename(
            self,
            "Save application log",
            f"adbnik_log_{ts}.txt",
            "Text files (*.txt);;All files (*.*)",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", errors="replace") as f:
                f.write(self.log_view.toPlainText())
            self.append_log(f"Log saved: {path}")
            box = QMessageBox(self)
            box.setWindowTitle("Saved")
            box.setIcon(QMessageBox.Information)
            box.setText("Application log saved.")
            box.setInformativeText(path)
            open_btn = box.addButton("Open file", QMessageBox.ActionRole)
            box.addButton(QMessageBox.Ok)
            box.exec_()
            if box.clickedButton() == open_btn:
                from PyQt5.QtCore import QUrl
                from PyQt5.QtGui import QDesktopServices

                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        except OSError as exc:
            QMessageBox.warning(self, "Save Log Failed", f"Unable to save log: {exc}")

    def get_adb_path(self) -> str:
        raw = (self.config.adb_path or "").strip()
        if not raw:
            return "adb"
        p = Path(raw)
        try:
            if p.is_file():
                return str(p.resolve())
        except OSError:
            pass
        return raw

    def get_camera_output_dir(self) -> str:
        return str(getattr(self.config, "camera_output_dir", "") or "").strip()

    def set_camera_output_dir(self, path: str) -> None:
        self.config.camera_output_dir = (path or "").strip()
        try:
            self.config.save()
        except Exception:
            pass

    def get_scrcpy_path(self) -> str:
        raw = (self.config.scrcpy_path or "").strip()
        if not raw:
            return "scrcpy"
        p = Path(raw)
        try:
            if p.is_file():
                return str(p.resolve())
        except OSError:
            pass
        return raw

    def get_default_ssh_host(self) -> str:
        return (self.config.default_ssh_host or "").strip()

    def get_default_serial_port(self) -> str:
        return (self.config.default_serial_port or "").strip() or "COM3"

    def get_default_serial_baud(self) -> str:
        return (self.config.default_serial_baud or "").strip() or "115200"
