import shlex
import sys
from typing import Callable, Optional

from PyQt5.QtCore import QProcess, QProcessEnvironment, Qt, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ... import APP_TITLE
from ...config import AppConfig
from ...services.adb_devices import list_adb_devices
from ..combo_utils import ExpandAllComboBox
from ..icon_utils import icon_media_play_green, icon_media_stop_red
from ...services.commands import run_adb


def _win_find_window_by_title(title: str) -> int:
    """Return HWND of top-level visible window whose title equals `title`, or 0."""
    if sys.platform != "win32" or not title:
        return 0
    try:
        import ctypes

        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, title)
        if hwnd:
            return int(hwnd)
    except Exception:
        return 0
    return 0


def _win_find_window_title_contains(sub: str) -> int:
    if sys.platform != "win32" or not sub:
        return 0
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        found = ctypes.c_void_p(0)
        sub_l = sub.lower()

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _enum(hwnd, _lp):
            if not user32.IsWindowVisible(hwnd):
                return True
            buf = ctypes.create_unicode_buffer(1024)
            user32.GetWindowTextW(hwnd, buf, 1024)
            t = (buf.value or "").lower()
            if sub_l in t:
                found.value = hwnd
                return False
            return True

        user32.EnumWindows(_enum, 0)
        return int(found.value or 0)
    except Exception:
        return 0


def _win_embed_hwnd_into_widget(hwnd: int, parent: QWidget) -> bool:
    """Re-parent a native window into `parent` and stretch it to fill (Windows)."""
    if sys.platform != "win32" or not hwnd or parent is None:
        return False
    try:
        import ctypes

        user32 = ctypes.windll.user32
        ph = int(parent.winId())
        user32.SetParent(hwnd, ph)
        GWL_STYLE = -16
        WS_CHILD = 0x40000000
        WS_POPUP = int(0x80000000)
        style = user32.GetWindowLongW(hwnd, GWL_STYLE)
        style = (style | WS_CHILD) & ~WS_POPUP
        user32.SetWindowLongW(hwnd, GWL_STYLE, style)
        r = parent.contentsRect()
        user32.MoveWindow(hwnd, 0, 0, max(1, r.width()), max(1, r.height()), True)
        user32.ShowWindow(hwnd, 5)  # SW_SHOW
        return True
    except Exception:
        return False


def _win_move_window(hwnd: int, parent: QWidget) -> None:
    if sys.platform != "win32" or not hwnd or parent is None:
        return
    try:
        import ctypes

        user32 = ctypes.windll.user32
        r = parent.contentsRect()
        w = max(1, r.width())
        h = max(1, r.height())
        user32.MoveWindow(hwnd, 0, 0, w, h, True)
        # WM_SIZE helps input/touch routing after device rotation or splitter resize (embedded mirror).
        WM_SIZE = 0x0005
        SIZE_RESTORED = 0
        lp = (h << 16) | (w & 0xFFFF)
        user32.SendMessageW(hwnd, WM_SIZE, SIZE_RESTORED, lp)
        user32.UpdateWindow(hwnd)
    except Exception:
        pass


class _EmbedHost(QWidget):
    """Hosts a reparented scrcpy HWND; keeps the child window sized to this widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hwnd: int = 0
        self.setMinimumSize(320, 220)

    def set_embedded_hwnd(self, hwnd: int) -> None:
        self._hwnd = int(hwnd or 0)

    def _deferred_embed_resize(self) -> None:
        if self._hwnd:
            _win_move_window(self._hwnd, self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._hwnd:
            _win_move_window(self._hwnd, self)
            QTimer.singleShot(50, self._deferred_embed_resize)


class ScrcpyTab(QWidget):
    """Screen mirroring via scrcpy; optional Windows embed (default off — separate window for reliable touch)."""

    def __init__(
        self,
        get_scrcpy_path: Callable[[], str],
        get_adb_path: Callable[[], str],
        append_log: Callable[[str], None],
        get_serial: Callable[[], str],
        config: AppConfig,
    ):
        super().__init__()
        self.get_scrcpy_path = get_scrcpy_path
        self.get_adb_path = get_adb_path
        self._append_log = append_log
        self._get_serial = get_serial
        self.config = config
        self.proc: Optional[QProcess] = None
        self._embed_poll: Optional[QTimer] = None
        self._embed_title: str = ""
        self._embed_hwnd: int = 0
        self._build_ui()

    def _sync_stop_hotkey(self, running: bool) -> None:
        w = self.window()
        if w is None:
            return
        if running:
            if hasattr(w, "register_scrcpy_stop_hotkey"):
                w.register_scrcpy_stop_hotkey()
        else:
            if hasattr(w, "unregister_scrcpy_stop_hotkey"):
                w.unregister_scrcpy_stop_hotkey()

    def _on_embed_mirror_changed(self) -> None:
        self.config.embed_scrcpy_mirror = self.embed_mirror_cb.isChecked()
        self.config.embed_scrcpy_mirror_opt_out = not self.embed_mirror_cb.isChecked()
        try:
            self.config.save()
        except OSError:
            pass

    def _adb_serial_prefix(self) -> list:
        s = (self._selected_serial() or "").strip().split()
        return ["-s", s[0]] if s else []

    def _selected_serial(self) -> str:
        if hasattr(self, "device_combo") and self.device_combo.count() > 0:
            d = self.device_combo.currentData()
            if d is not None and str(d).strip():
                return str(d).strip()
            t = (self.device_combo.currentText() or "").strip().split()
            if t:
                return t[0]
        s = (self._get_serial() or "").strip().split()
        return s[0] if s else ""

    def _refresh_screen_devices(self) -> None:
        if not hasattr(self, "device_combo"):
            return
        prev = self._selected_serial()
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        pairs = list_adb_devices(self.get_adb_path())
        if not pairs:
            self.device_combo.addItem("No device", "")
            self.device_combo.blockSignals(False)
            return
        idx = 0
        top = (self._get_serial() or "").strip().split()
        prefer = prev or (top[0] if top else "")
        for i, (serial, display) in enumerate(pairs):
            self.device_combo.addItem(display, serial)
            if prefer and serial == prefer:
                idx = i
        self.device_combo.setCurrentIndex(idx)
        self.device_combo.blockSignals(False)

    def _ensure_adb_device(self) -> bool:
        if not (self._get_serial() or "").strip():
            QMessageBox.information(self, "ADB", "Select a device in the bar at the top of the window first.")
            return False
        return True

    def _ensure_device_ready_for_scrcpy(self, serial: str) -> bool:
        adb = self.get_adb_path()
        run_adb(adb, ["start-server"], timeout=8)
        code, out, err = run_adb(adb, ["-s", serial, "get-state"], timeout=8)
        state = (out or "").strip().lower()
        if code == 0 and state == "device":
            return True
        # Try one reconnect cycle, then check again.
        run_adb(adb, ["reconnect"], timeout=12)
        code2, out2, _ = run_adb(adb, ["-s", serial, "get-state"], timeout=8)
        state2 = (out2 or "").strip().lower()
        if code2 == 0 and state2 == "device":
            return True
        self._append_log(
            "Screen: selected device is not ready for scrcpy. "
            + (err.strip() if err else f"state={state or 'unknown'}")
        )
        return False

    def _adb_restart_server(self) -> None:
        adb = self.get_adb_path()
        c1, _, e1 = run_adb(adb, ["kill-server"], timeout=15)
        self._append_log(f"ADB kill-server: exit {c1}" + (f" — {e1.strip()}" if e1 and e1.strip() else ""))
        c2, out, e2 = run_adb(adb, ["start-server"], timeout=30)
        msg = (out or e2 or "").strip() or f"exit {c2}"
        self._append_log(f"ADB start-server: {msg}")
        if c2 != 0:
            QMessageBox.warning(self, "ADB server", e2 or "start-server failed.")

    def _adb_reconnect(self) -> None:
        code, out, err = run_adb(self.get_adb_path(), ["reconnect"], timeout=30)
        self._append_log(f"ADB reconnect: {(out or err or '').strip() or f'exit {code}'}")

    def _adb_remount(self) -> None:
        if not self._ensure_adb_device():
            return
        code, out, err = run_adb(self.get_adb_path(), [*self._adb_serial_prefix(), "remount"], timeout=120)
        text = (out or err or "").strip() or f"exit {code}"
        self._append_log(f"ADB remount: {text}")
        if code != 0:
            QMessageBox.warning(self, "ADB remount", text or "Often needs adb root first.")
        else:
            QMessageBox.information(self, "ADB remount", text or "OK.")

    def _adb_root(self) -> None:
        if not self._ensure_adb_device():
            return
        code, out, err = run_adb(self.get_adb_path(), [*self._adb_serial_prefix(), "root"], timeout=90)
        text = (out or err or "").strip() or f"exit {code}"
        self._append_log(f"ADB root: {text}")
        QMessageBox.information(self, "ADB root", text)

    def _adb_unroot(self) -> None:
        if not self._ensure_adb_device():
            return
        code, out, err = run_adb(self.get_adb_path(), [*self._adb_serial_prefix(), "unroot"], timeout=90)
        text = (out or err or "").strip() or f"exit {code}"
        self._append_log(f"ADB unroot: {text}")
        QMessageBox.information(self, "ADB unroot", text)

    def _adb_reboot(self) -> None:
        if not self._ensure_adb_device():
            return
        r = QMessageBox.question(
            self,
            "Reboot device",
            "Send adb reboot to the selected device?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if r != QMessageBox.Yes:
            return
        code, out, err = run_adb(self.get_adb_path(), [*self._adb_serial_prefix(), "reboot"], timeout=30)
        self._append_log(f"ADB reboot: {(out or err or '').strip() or f'exit {code}'}")

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 4, 6, 4)
        root.setSpacing(0)

        split = QSplitter(Qt.Horizontal)
        split.setObjectName("ScrcpyMainSplit")
        split.setChildrenCollapsible(False)

        left_wrap = QWidget()
        left_wrap.setObjectName("ScrcpyLeftPanel")
        left_wrap.setMinimumWidth(280)
        left_wrap.setMaximumWidth(900)
        left_wrap.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        left_l = QVBoxLayout(left_wrap)
        left_l.setContentsMargins(0, 0, 8, 0)
        left_l.setSpacing(4)

        inner = QWidget()
        inner.setObjectName("ScrcpyLeftInner")
        inner.setMinimumWidth(260)
        inner.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        form = QVBoxLayout(inner)
        form.setContentsMargins(6, 6, 6, 6)
        form.setSpacing(6)

        hdr = QLabel("Configuration")
        hdr.setObjectName("ScrcpyConfigTitle")
        hdr.setFont(QFont("Segoe UI", 9, QFont.Bold))
        form.addWidget(hdr)

        grp = QGroupBox("Mirror")
        grp.setObjectName("ScrcpyOptionsGroup")
        grid = QGridLayout(grp)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(10)
        grid.setContentsMargins(6, 8, 6, 8)
        grid.setColumnMinimumWidth(0, 110)
        grid.setColumnStretch(1, 1)

        grid.addWidget(QLabel("Device"), 0, 0)
        dev_row = QHBoxLayout()
        dev_row.setContentsMargins(0, 0, 0, 0)
        dev_row.setSpacing(6)
        self.device_combo = ExpandAllComboBox()
        self.device_combo.setMaxVisibleItems(20)
        self.device_combo.setMinimumHeight(34)
        dev_row.addWidget(self.device_combo, 1)
        b_dev_refresh = QToolButton()
        b_dev_refresh.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        b_dev_refresh.setToolTip("Refresh device list")
        b_dev_refresh.setFixedSize(34, 34)
        b_dev_refresh.clicked.connect(self._refresh_screen_devices)
        dev_row.addWidget(b_dev_refresh)
        grid.addLayout(dev_row, 0, 1)
        self._refresh_screen_devices()

        grid.addWidget(QLabel("Bit rate"), 1, 0)
        self.bitrate_combo = ExpandAllComboBox()
        self.bitrate_combo.setMaxVisibleItems(12)
        self.bitrate_combo.setEditable(True)
        self.bitrate_combo.addItems(["8M", "16M", "32M", "48M", "60M"])
        self.bitrate_combo.setCurrentText("60M")
        self.bitrate_combo.setToolTip(
            "Video bit rate. Default is high quality; if the mirror stutters, try 16M or 8M."
        )
        self.bitrate_combo.setMinimumHeight(34)
        grid.addWidget(self.bitrate_combo, 1, 1)

        grid.addWidget(QLabel("Max size"), 2, 0)
        self.max_size = ExpandAllComboBox()
        self.max_size.setEditable(True)
        self.max_size.setMaxVisibleItems(12)
        self.max_size.addItems(["1024", "1280", "1600", "1920", "2560", "3200"])
        self.max_size.setCurrentText("1920")
        self.max_size.setToolTip(
            "Longer edge in pixels (scrcpy --max-size). 1920 is a sharp default; "
            "if the PC or device struggles, try 1280 or 1024."
        )
        self.max_size.setMinimumHeight(34)
        grid.addWidget(self.max_size, 2, 1)

        grid.addWidget(QLabel("Max FPS"), 3, 0)
        self.max_fps = ExpandAllComboBox()
        self.max_fps.setMaxVisibleItems(12)
        self.max_fps.addItems(["(default)", "30", "60", "90", "120"])
        self.max_fps.setCurrentText("60")
        self.max_fps.setToolTip(
            "Cap frame rate (--max-fps). 60 is smooth; use 30 on slower machines."
        )
        self.max_fps.setMinimumHeight(34)
        grid.addWidget(self.max_fps, 3, 1)

        grid.addWidget(QLabel("Window title"), 4, 0)
        self.window_title = QLineEdit(f"{APP_TITLE} — mirror")
        self.window_title.setToolTip("Must match for embedding (Windows)")
        self.window_title.setMinimumHeight(34)
        grid.addWidget(self.window_title, 4, 1)

        self.audio_cb = QCheckBox("Forward audio")
        self.audio_cb.setChecked(True)
        self.audio_cb.setToolTip("Off → --no-audio (often faster)")
        grid.addWidget(self.audio_cb, 5, 0)

        self.stay_awake_cb = QCheckBox("Stay awake (USB)")
        self.stay_awake_cb.setChecked(True)
        grid.addWidget(self.stay_awake_cb, 5, 1)

        self.turn_screen_off_cb = QCheckBox("Turn device screen off")
        self.turn_screen_off_cb.setChecked(False)
        self.turn_screen_off_cb.setToolTip(
            "scrcpy --turn-screen-off: turns off the phone’s physical display while mirroring "
            "(image still shows in this window). Useful to save the OLED and avoid burn-in."
        )
        grid.addWidget(self.turn_screen_off_cb, 6, 0)

        self.fullscreen_cb = QCheckBox("Fullscreen (separate)")
        self.fullscreen_cb.setChecked(False)
        self.fullscreen_cb.setToolTip(
            "Whole monitor; embedding skipped. Exit fullscreen mirror: MOD+q in scrcpy, "
            "or Ctrl+Alt+F12 / Ctrl+Alt+End / View → Stop screen mirror."
        )
        grid.addWidget(self.fullscreen_cb, 6, 1)

        self.embed_mirror_cb = QCheckBox("Embed in this tab (Windows)")
        # Default off: separate scrcpy window — touch/swipes work reliably. Embedding uses SetParent and often breaks input.
        self.embed_mirror_cb.setChecked(bool(getattr(self.config, "embed_scrcpy_mirror", False)))
        self.config.embed_scrcpy_mirror = self.embed_mirror_cb.isChecked()
        self.config.embed_scrcpy_mirror_opt_out = not self.embed_mirror_cb.isChecked()
        self.embed_mirror_cb.setToolTip(
            "Off (recommended): separate mirror window — best for touch and unlock gestures. "
            "On: dock inside this panel (can break touch on some setups)."
        )
        self.embed_mirror_cb.stateChanged.connect(self._on_embed_mirror_changed)
        grid.addWidget(self.embed_mirror_cb, 7, 0, 1, 2)

        grid.addWidget(QLabel("Extra CLI"), 8, 0)
        self.extra_args = QLineEdit()
        self.extra_args.setPlaceholderText("optional scrcpy flags…")
        self.extra_args.setMinimumHeight(34)
        grid.addWidget(self.extra_args, 8, 1)

        form.addWidget(grp)

        st = self.style()
        row = QHBoxLayout()
        row.setSpacing(6)
        b_start = QPushButton("Start")
        b_start.setObjectName("ScrcpyStartBtn")
        b_start.setIcon(icon_media_play_green())
        b_start.clicked.connect(self.start_scrcpy)
        b_stop = QPushButton("Stop")
        b_stop.setObjectName("ScrcpyStopBtn")
        b_stop.setIcon(icon_media_stop_red())
        b_stop.clicked.connect(self.stop_scrcpy)
        row.addWidget(b_start)
        row.addWidget(b_stop)
        form.addLayout(row)

        adb_grp = QGroupBox("ADB (uses device in top bar)")
        adb_grp.setObjectName("ScrcpyAdbGroup")
        adb_grid = QGridLayout(adb_grp)
        adb_grid.setHorizontalSpacing(6)
        adb_grid.setVerticalSpacing(6)
        adb_actions = [
            ("Restart server", "adb kill-server && adb start-server", QStyle.SP_BrowserReload, self._adb_restart_server),
            ("Reconnect", "adb reconnect", QStyle.SP_DriveNetIcon, self._adb_reconnect),
            ("Remount", "adb remount (often needs root)", QStyle.SP_DialogApplyButton, self._adb_remount),
            ("Root", "adb root", QStyle.SP_VistaShield, self._adb_root),
            ("Unroot", "adb unroot", QStyle.SP_DialogCancelButton, self._adb_unroot),
            ("Reboot", "adb reboot", QStyle.SP_ComputerIcon, self._adb_reboot),
        ]
        for i, (text, tip, icon, slot) in enumerate(adb_actions):
            tb = QToolButton()
            tb.setText(text)
            tb.setToolTip(tip)
            tb.setIcon(st.standardIcon(icon))
            tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            tb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            tb.setMinimumHeight(30)
            tb.clicked.connect(slot)
            row, col = divmod(i, 2)
            adb_grid.addWidget(tb, row, col)
        form.addWidget(adb_grp)

        self.status = QLabel("Idle")
        self.status.setObjectName("ScrcpyStatusLabel")
        self.status.setWordWrap(True)
        form.addWidget(self.status)

        left_l.addWidget(inner, 0)

        right_wrap = QWidget()
        right_l = QVBoxLayout(right_wrap)
        right_l.setContentsMargins(0, 0, 0, 0)
        right_l.setSpacing(0)

        self._embed_host = _EmbedHost(self)
        self._embed_host.setObjectName("ScrcpyEmbedHost")
        self._embed_host.setMinimumSize(400, 280)
        self._embed_host.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        el = QVBoxLayout(self._embed_host)
        el.setContentsMargins(0, 0, 0, 0)

        self._placeholder = QLabel(
            "How to start Screen Control:\n"
            "1) Select a device.\n"
            "2) Configure Bit rate, Max size, and Max FPS.\n"
            "3) Choose options (audio/fullscreen/embed) if needed.\n"
            "4) Click Start.\n"
            "5) Click Stop to end mirroring.\n\n"
            "Preview appears here after mirror starts."
        )
        self._placeholder.setWordWrap(True)
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setMargin(16)
        self._placeholder.setObjectName("ScrcpyHintLabel")
        el.addWidget(self._placeholder, 1)

        right_l.addWidget(self._embed_host, 1)

        split.addWidget(left_wrap)
        split.addWidget(right_wrap)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([400, 2000])

        root.addWidget(split, 1)

    def _clear_embed(self) -> None:
        self._embed_hwnd = 0
        self._embed_host.set_embedded_hwnd(0)
        lay = self._embed_host.layout()
        if lay is not None:
            while lay.count():
                w = lay.takeAt(0).widget()
                if w is not None:
                    w.deleteLater()
            self._placeholder = QLabel(
                "How to start Screen Control:\n"
                "1) Select a device.\n"
                "2) Configure Bit rate, Max size, and Max FPS.\n"
                "3) Choose options (audio/fullscreen/embed) if needed.\n"
                "4) Click Start.\n"
                "5) Click Stop to end mirroring.\n\n"
                "Preview appears here after mirror starts."
            )
            self._placeholder.setWordWrap(True)
            self._placeholder.setAlignment(Qt.AlignCenter)
            self._placeholder.setMargin(16)
            self._placeholder.setObjectName("ScrcpyHintLabel")
            lay.addWidget(self._placeholder, 1)

    def _stop_embed_poll(self) -> None:
        if self._embed_poll is not None:
            self._embed_poll.stop()
            self._embed_poll.deleteLater()
            self._embed_poll = None

    def _poll_embed_window(self) -> None:
        if not self.proc or self.proc.state() != QProcess.Running:
            self._stop_embed_poll()
            return
        if self.fullscreen_cb.isChecked() or not self.embed_mirror_cb.isChecked():
            self._stop_embed_poll()
            return
        title = (self._embed_title or "").strip()
        if not title:
            self._stop_embed_poll()
            return
        hwnd = _win_find_window_by_title(title)
        if not hwnd:
            hwnd = _win_find_window_title_contains(title[: min(32, len(title))])
        if not hwnd:
            return
        self._stop_embed_poll()
        if sys.platform == "win32":
            lay = self._embed_host.layout()
            if lay is not None:
                while lay.count():
                    w = lay.takeAt(0).widget()
                    if w is not None:
                        w.deleteLater()
            if _win_embed_hwnd_into_widget(hwnd, self._embed_host):
                self._embed_hwnd = int(hwnd)
                self._embed_host.set_embedded_hwnd(self._embed_hwnd)
                self._append_log("Screen: embedded mirror via Win32 SetParent.")
            else:
                self._embed_hwnd = 0
                self._embed_host.set_embedded_hwnd(0)
                ph = QLabel(
                    "Could not embed the mirror window. It should still appear as a separate window.\n"
                    "Stop scrcpy from here when finished."
                )
                ph.setWordWrap(True)
                ph.setMargin(12)
                ph.setObjectName("ScrcpyHintLabel")
                if self._embed_host.layout() is not None:
                    self._embed_host.layout().addWidget(ph, 1)
                self._append_log("Screen: could not embed mirror window — using external scrcpy window.")

    def _drain_process_log(self) -> None:
        if not self.proc:
            return
        try:
            out = bytes(self.proc.readAllStandardOutput()).decode(errors="ignore").strip()
            if out:
                for line in out.splitlines():
                    if line.strip():
                        self._append_log(f"scrcpy: {line.strip()}")
        except Exception:
            pass

    def _on_proc_output(self) -> None:
        if not self.proc:
            return
        chunk = bytes(self.proc.readAllStandardOutput()).decode(errors="ignore")
        if chunk.strip():
            for line in chunk.splitlines():
                if line.strip():
                    self._append_log(f"scrcpy: {line.strip()}")

    def _on_proc_finished(self, exit_code: int, exit_status: int) -> None:
        self._sync_stop_hotkey(False)
        self._stop_embed_poll()
        self._drain_process_log()
        self._append_log(f"Screen: scrcpy process finished — exit code {exit_code}, exit status {exit_status}.")
        self.status.setText("Idle")
        self._clear_embed()

    def start_scrcpy(self):
        if self.proc and self.proc.state() == QProcess.Running:
            self._append_log("Screen: already running.")
            return
        self._refresh_screen_devices()
        if not self._ensure_adb_device():
            return
        serial = self._selected_serial()
        if not serial:
            QMessageBox.information(self, "ADB", "Select a valid device serial first.")
            return
        if not self._ensure_device_ready_for_scrcpy(serial):
            QMessageBox.warning(
                self,
                "Screen Control",
                "Selected device is not ready. Reconnect USB and accept RSA prompt on phone.",
            )
            return
        exe = self.get_scrcpy_path()
        adb_path = self.get_adb_path()
        win_title = (self.window_title.text().strip() or f"{APP_TITLE} - mirror").replace("\u2014", "-").replace("—", "-")
        self._embed_title = win_title

        br = (self.bitrate_combo.currentText() or "32M").strip() or "32M"
        ms = (self.max_size.currentText() or "1920").strip() or "1920"

        cmd = [
            exe,
            "-s",
            serial,
            "--video-bit-rate",
            br,
            "--max-size",
            ms,
            "--window-title",
            win_title,
        ]
        fps_txt = self.max_fps.currentText().strip()
        if fps_txt and fps_txt != "(default)":
            cmd.extend(["--max-fps", fps_txt])

        if not self.audio_cb.isChecked():
            cmd.append("--no-audio")
        if self.stay_awake_cb.isChecked():
            cmd.append("--stay-awake")
        if self.turn_screen_off_cb.isChecked():
            cmd.append("--turn-screen-off")
        if self.fullscreen_cb.isChecked():
            cmd.append("--fullscreen")

        extras = (self.extra_args.text() or "").strip()
        if extras:
            try:
                # Windows paths and quoting differ from POSIX; use non-POSIX rules on Windows.
                tokens = shlex.split(extras, posix=sys.platform != "win32")
            except ValueError as exc:
                tokens = []
                self._append_log(f"Screen: could not parse extra args ({exc}). Check quoting.")
            blocked = {"--no-control", "--otg"}
            cleaned = [t for t in tokens if t not in blocked]
            removed = [t for t in tokens if t in blocked]
            if removed:
                self._append_log(
                    "Screen: removed extra arg(s) that disable normal touch/control: "
                    + ", ".join(removed)
                )
            cmd.extend(cleaned)

        self._clear_embed()
        self._append_log(f"Screen: starting on {serial}: {' '.join(cmd)}")
        self._append_log(f"Screen: ADB executable={adb_path!r}")

        def _launch(_cmd: list, started_timeout_ms: int = 8000) -> bool:
            if self.proc is not None:
                prev = self.proc
                self.proc = None
                prev.deleteLater()
            self.proc = QProcess(self)
            self.proc.setProcessChannelMode(QProcess.MergedChannels)
            env = QProcessEnvironment.systemEnvironment()
            env.insert("ADB", adb_path)
            self.proc.setProcessEnvironment(env)
            self.proc.readyReadStandardOutput.connect(self._on_proc_output)
            self.proc.finished.connect(self._on_proc_finished)
            self.proc.start(_cmd[0], _cmd[1:])
            return bool(self.proc.waitForStarted(started_timeout_ms))

        started = _launch(cmd)
        if not started:
            # Fallback launch with safest settings if first start failed.
            safe_cmd = [exe, "-s", serial, "--window-title", win_title, "--video-bit-rate", br]
            self._append_log("Screen: first start failed, retrying with safe fallback options.")
            started = _launch(safe_cmd, started_timeout_ms=9000)

        if not started:
            self.status.setText("Failed to start")
            err = ""
            if self.proc:
                err = bytes(self.proc.readAllStandardOutput()).decode(errors="ignore")
            self._append_log(
                "Screen: failed to start scrcpy after retry (check scrcpy path, USB debugging, RSA trust, cable). "
                + (err.strip() or "(no process output)")
            )
            return

        self.status.setText("Running")
        self._sync_stop_hotkey(True)
        self._stop_embed_poll()
        if sys.platform == "win32" and not self.fullscreen_cb.isChecked() and self.embed_mirror_cb.isChecked():
            self._embed_poll = QTimer(self)
            self._embed_poll.setInterval(180)
            n = [0]

            def _tick():
                n[0] += 1
                if n[0] > 80:
                    self._stop_embed_poll()
                    self._append_log(
                        "Screen: embedding timed out — mirror may still be open in a separate window."
                    )
                    return
                self._poll_embed_window()

            self._embed_poll.timeout.connect(_tick)
            self._embed_poll.start()

    def stop_scrcpy(self):
        self._sync_stop_hotkey(False)
        self._stop_embed_poll()
        if self.proc and self.proc.state() == QProcess.Running:
            self.proc.kill()
            self.proc.waitForFinished(5000)
            self.status.setText("Stopped")
            self._append_log("Screen: stopped.")
        self._clear_embed()

    def shutdown(self):
        self.stop_scrcpy()
