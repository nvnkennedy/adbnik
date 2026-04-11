import html
import platform
import sys
from datetime import datetime

from PyQt5.QtCore import QSize, Qt, QTimer
from PyQt5.QtGui import QFont, QKeySequence, QTextCursor
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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
from ..services.adb_devices import list_adb_devices
from ..services.commands import run_adb
from ..session import ConnectionKind, SessionProfile
from .app_icon import create_app_icon
from .first_run_dialog import FirstRunDialog
from .preferences_dialog import PreferencesDialog
from .styles import get_stylesheet
from .tabs.file_explorer_tab import FileExplorerTab
from .tabs.scrcpy_tab import ScrcpyTab
from .tabs.terminal_tab import TerminalTab
from .win_scrcpy_hotkey import (
    is_windows_hotkey_message,
    register_scrcpy_stop_hotkey as _win_register_scrcpy_hotkey,
    unregister_scrcpy_stop_hotkey as _win_unregister_scrcpy_hotkey,
)


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig, *, first_launch: bool = False):
        super().__init__()
        self.config = config
        self._first_launch = first_launch
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(create_app_icon(dark=bool(getattr(self.config, "dark_theme", False))))
        self.resize(1450, 900)
        self.setMinimumSize(720, 480)
        self._build_ui()
        self._apply_theme()
        self._setup_version_status()
        if hasattr(self, "_action_dark"):
            self._action_dark.setChecked(bool(getattr(self.config, "dark_theme", False)))
        self.append_log("Application started.")
        self.append_log(f"ADB path: {self.get_adb_path()}  ·  scrcpy: {self.get_scrcpy_path()}")
        if getattr(self.config, "dark_theme", False):
            self.append_log("Dark theme is enabled (View → Dark theme).")
        self.refresh_devices()
        if self._first_launch:
            QTimer.singleShot(0, self.prompt_first_run_if_needed)
        self._adb_poll_timer = QTimer(self)
        self._adb_poll_timer.setInterval(5000)
        self._adb_poll_timer.timeout.connect(self.refresh_devices)
        self._adb_poll_timer.start()
        self._scrcpy_hotkey_registered = False

    def showEvent(self, event):
        super().showEvent(event)
        # Avoid duplicate startup refresh work; timer + initial call handle it.

    def append_log(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        msg_l = (message or "").lower()
        color = "#cbd5e1"
        level = "INFO"
        badge_bg = "#334155"
        if any(k in msg_l for k in ("error", "failed", "warning", "denied", "not found", "timed out")):
            color = "#ef4444"
            level = "ERR"
            badge_bg = "#991b1b"
        elif any(k in msg_l for k in ("saved", "ok", "success", "running", "started", "connected")):
            color = "#22c55e"
            level = "OK"
            badge_bg = "#166534"
        elif any(k in msg_l for k in ("refresh", "adb:", "screen:", "session")):
            color = "#38bdf8"
            level = "INFO"
            badge_bg = "#1e3a8a"
        safe_msg = html.escape(message)
        line = (
            f'<span style="color:#94a3b8;">[{ts}]</span> '
            f'<span style="background:{badge_bg}; color:#f8fafc; padding:1px 6px; border-radius:4px; '
            f'font-weight:700; letter-spacing:0.3px;">{level}</span> '
            f'<span style="color:{color}; font-weight:600;">{safe_msg}</span>'
        )
        self.log_view.append(line)
        self.log_view.moveCursor(QTextCursor.End)

    def _apply_theme(self) -> None:
        dark = bool(getattr(self.config, "dark_theme", False))
        self.setStyleSheet(get_stylesheet(dark=dark))
        _icon = create_app_icon(dark=dark)
        self.setWindowIcon(_icon)
        _app = QApplication.instance()
        if _app is not None:
            _app.setWindowIcon(_icon)
        self._refresh_version_label_style()

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

    def _toggle_dark_theme(self) -> None:
        self.config.dark_theme = self._action_dark.isChecked()
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

    def closeEvent(self, event):
        self.unregister_scrcpy_stop_hotkey()
        if hasattr(self, "_adb_poll_timer"):
            self._adb_poll_timer.stop()
        if hasattr(self, "terminal"):
            self.terminal.shutdown_all_sessions()
        if hasattr(self, "file_explorer"):
            self.file_explorer.disconnect_remote_services()
        if hasattr(self, "scrcpy"):
            self.scrcpy.shutdown()
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
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(6, 4, 6, 4)
        root.setSpacing(4)

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
        st = self.style()
        self.tabs.addTab(self.terminal, st.standardIcon(QStyle.SP_FileDialogDetailedView), "Terminal")
        self.tabs.addTab(self.file_explorer, st.standardIcon(QStyle.SP_DirLinkIcon), "File Explorer")
        self.tabs.addTab(self.scrcpy, st.standardIcon(QStyle.SP_ComputerIcon), "Screen Control")
        self.tabs.tabBar().setIconSize(QSize(18, 18))
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
        clear_log.clicked.connect(lambda: self.log_view.clear())
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
        self.log_view.setFont(QFont("Consolas", 9))
        self.log_view.setPlaceholderText("Application log — transfers, errors, and status appear here.")
        self.log_view.setMinimumHeight(120)
        self.log_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.log_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.log_view.customContextMenuRequested.connect(self._log_context_menu)
        log_v.addWidget(self.log_view, 1)

        body_split.addWidget(log_wrap)
        body_split.setStretchFactor(0, 1)
        body_split.setStretchFactor(1, 0)
        body_split.setSizes([620, 220])

        body_layout.addWidget(body_split, 1)

        root.addWidget(body, 1)

        self.setCentralWidget(central)
        self._build_menu_bar()

    def prompt_first_run_if_needed(self) -> None:
        if not self._first_launch:
            return
        self._first_launch = False
        dlg = FirstRunDialog(self.config, self)
        if dlg.exec_():
            self._apply_theme()
            if hasattr(self, "_action_dark"):
                self._action_dark.setChecked(bool(getattr(self.config, "dark_theme", False)))
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

    def _on_main_tab_changed(self, index: int) -> None:
        if index == 0 and hasattr(self, "terminal"):
            self.terminal._reload_bookmark_sidebar()
        if index == 1:
            self.refresh_devices()

    def _on_device_combo_changed(self, _text: str):
        if hasattr(self, "file_explorer"):
            self.file_explorer.set_remote_device(self.terminal.current_adb_serial())

    def refresh_devices(self):
        if not hasattr(self, "terminal"):
            return
        prev_selected_serial = self.terminal.current_adb_serial()
        self.terminal.device_combo.blockSignals(True)
        self.terminal.device_combo.clear()
        pairs = list_adb_devices(self.get_adb_path())
        prev_sig = getattr(self, "_last_adb_device_sig", None)
        sig = tuple(pairs) if pairs else ()
        if not pairs:
            code, _, _ = run_adb(self.get_adb_path(), ["devices"])
            if code != 0:
                self.terminal.device_combo.addItem("ADB not found")
                self.terminal.device_combo.blockSignals(False)
                if hasattr(self, "file_explorer"):
                    self.file_explorer.set_remote_device("")
                if prev_sig != ("__adb_err__",):
                    self._last_adb_device_sig = ("__adb_err__",)
                    self.append_log("ADB not responding — check ADB path in Preferences (menu).")
                return
            self.terminal.device_combo.addItem("No device")
            self.terminal.device_combo.blockSignals(False)
            if hasattr(self, "file_explorer"):
                self.file_explorer.set_remote_device("")
            if prev_sig != ():
                self._last_adb_device_sig = ()
                self.append_log("ADB: no devices detected — connect a device, enable USB debugging, and authorize this PC.")
            return
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
            if hasattr(self, "file_explorer"):
                self.file_explorer.refresh_all_remotes()

    def _build_menu_bar(self):
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
        a_clear_log.triggered.connect(self.log_view.clear)
        edit_menu.addAction(a_clear_log)
        a_save_log = QAction("Save &log as…", self)
        a_save_log.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        a_save_log.setShortcut(QKeySequence("Ctrl+Shift+S"))
        a_save_log.triggered.connect(self._save_app_log)
        edit_menu.addAction(a_save_log)

        session = bar.addMenu("&Session")
        adb_menu = session.addMenu("ADB")
        adb_menu.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
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
        a_adb_shell.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        a_adb_shell.triggered.connect(self._menu_session_adb_shell)
        adb_menu.addAction(a_adb_shell)

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
        adb_cmd.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
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
        self._action_dark = QAction("&Dark theme", self)
        self._action_dark.setIcon(self.style().standardIcon(QStyle.SP_DialogYesButton))
        self._action_dark.setCheckable(True)
        self._action_dark.setChecked(bool(getattr(self.config, "dark_theme", False)))
        self._action_dark.triggered.connect(self._toggle_dark_theme)
        view.addAction(self._action_dark)

        help_menu = bar.addMenu("&Help")
        a_about = QAction(f"&About {APP_TITLE}", self)
        a_about.setIcon(self.style().standardIcon(QStyle.SP_MessageBoxInformation))
        a_about.triggered.connect(self._menu_help_about)
        help_menu.addAction(a_about)

    def _menu_stop_screen_mirror(self) -> None:
        if hasattr(self, "scrcpy"):
            self.scrcpy.stop_scrcpy()

    def _open_preferences(self):
        dlg = PreferencesDialog(self.config, self)
        if dlg.exec_():
            self.append_log("Preferences saved.")
            if hasattr(self, "terminal"):
                self.terminal.sync_serial_from_config()
            self.refresh_devices()
            self._build_menu_bar()
            if hasattr(self, "_action_dark"):
                self._action_dark.setChecked(bool(getattr(self.config, "dark_theme", False)))

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
        self.terminal.send_line_to_current_session(line)

    def _menu_help_about(self) -> None:
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
<p style="color:{sub};">A desktop workspace for Android debugging, remote files, and screen control — built with
PyQt5 and Python {py_ver} on {plat}.</p>

<h3 style="margin-bottom:6px;">What you can do</h3>
<ul style="margin-top:0;">
<li><b>Terminal</b> — SSH, ADB shell, serial, and local shells. Sessions and bookmarks live in the sidebar.</li>
<li><b>File Explorer</b> — WinSCP-style <b>Local | Remote</b> panes per session: ADB device storage, SFTP, or FTP.
Pull, push, drag-and-drop, find files, and external editors with sync where supported.</li>
<li><b>Screen Control</b> — Launch and manage <b>scrcpy</b> mirroring (paths and options in Preferences).</li>
</ul>

<h3 style="margin-bottom:6px;">Menus worth knowing</h3>
<ul style="margin-top:0;">
<li><b>File → Preferences</b> — ADB/scrcpy paths, dark theme, serial defaults, and <b>SSH quick commands</b>
(label and command per line: <code>Label | command</code>). Those commands appear under <b>Commands → SSH</b>.</li>
<li><b>Session</b> — Refresh devices (F5), ADB tools, open SSH using Explorer’s SFTP host or a new session.</li>
<li><b>Commands</b> — ADB shortcuts (root, remount, reboot) and your custom SSH lines from Preferences.</li>
<li><b>View</b> — Jump tabs (Ctrl+1–3), stop screen mirror, toggle dark theme.</li>
</ul>

<h3 style="margin-bottom:6px;">Tips</h3>
<ul style="margin-top:0;">
<li>Heavy work (e.g. file search) runs in the background so the window stays responsive.</li>
<li>Folder rows show “…” in the size column (totals are not listed for speed). Use <b>Properties</b> on a folder for a full recursive size when you need it.</li>
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
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save application log",
            "adbnik_log.txt",
            "Text files (*.txt);;All files (*.*)",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", errors="replace") as f:
                f.write(self.log_view.toPlainText())
            self.append_log(f"Log saved: {path}")
        except OSError as exc:
            QMessageBox.warning(self, "Save Log Failed", f"Unable to save log: {exc}")

    def get_adb_path(self) -> str:
        return (self.config.adb_path or "").strip() or "adb"

    def get_scrcpy_path(self) -> str:
        return (self.config.scrcpy_path or "").strip() or "scrcpy"

    def get_default_ssh_host(self) -> str:
        return (self.config.default_ssh_host or "").strip()

    def get_default_serial_port(self) -> str:
        return (self.config.default_serial_port or "").strip() or "COM3"

    def get_default_serial_baud(self) -> str:
        return (self.config.default_serial_baud or "").strip() or "115200"
