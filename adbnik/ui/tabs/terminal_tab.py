import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from ...session import ConnectionKind, SessionProfile, ssh_command_args
from ...services.adb_devices import friendly_name_for_serial
from ..session_login_dialog import SessionLoginDialog, SessionLoginOutcome

from PyQt5.QtCore import QSize, Qt, QProcess, QTimer
from PyQt5.QtGui import QFont, QKeySequence, QTextCursor
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStyle,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...config import AppConfig
from ..combo_utils import ExpandAllComboBox
from ..icon_utils import bookmark_icon_from_entry, icon_windows_cmd_console, icon_windows_powershell


def _serial_from_combo_text(text: str) -> str:
    t = (text or "").strip()
    if not t or t.startswith("No ") or "not found" in t.lower():
        return ""
    return t.split()[0]


def adb_interactive_shell_command(adb_path: str, serial: Optional[str] = None) -> List[str]:
    """adb shell with -t -t: stdin is not a TTY (QProcess), so one -t is not enough; double -t forces remote PTY."""
    cmd = [adb_path]
    s = (serial or "").strip()
    if s:
        cmd.extend(["-s", s])
    # Matches native `adb shell`: prompts like hostname:/path $ (see adb: "Use multiple -t options...")
    cmd.extend(["shell", "-t", "-t"])
    return cmd


def _adb_terminal_banner(adb_path: str, serial: str, display_label: str) -> str:
    """One line at top of buffer so device identity is visible even before the shell prints a prompt."""
    s = (serial or "").strip()
    name = (display_label or "").strip()
    if not name and s:
        name = friendly_name_for_serial(adb_path, s)
    if not s:
        return f"ADB shell · {name or 'default device'}"
    # Avoid "… · RFCY… · RFCY…" when the tab label is already the serial / model lookup matches serial.
    if not name or name == s:
        return f"ADB shell · {s}"
    return f"ADB shell · {name} · {s}"


def _normalize_pty_text(data: str, *, collapse_blank_runs: bool = True) -> str:
    """CRLF / stray CR from PTYs; strip ANSI. Optional blank-run collapse for 3+ newlines."""
    if not data:
        return data
    # Strip ANSI escape/control sequences so `clear` and terminal color codes do not print raw bytes.
    data = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", data)
    data = re.sub(r"\x1b\][^\x07]*(\x07|\x1b\\)", "", data)
    data = data.replace("\r\n", "\n")
    data = data.replace("\r", "\n")
    if collapse_blank_runs:
        # Collapse 3+ newlines only (do not merge \n\n).
        data = re.sub(r"\n{3,}", "\n\n", data)
    return data


class ShellPlainTextEdit(QPlainTextEdit):
    """Shell output + typing at the end. History (Up/Down), context menu, Ctrl+Shift+C/V."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._anchor = 0
        self._on_commit_line: Optional[Callable[[str], None]] = None
        self._on_save_buffer: Optional[Callable[[], None]] = None
        self._cmd_history: List[str] = []
        self._hist_browse_idx: Optional[int] = None
        self._hist_stash: str = ""
        self.setCursorWidth(2)
        self.setUndoRedoEnabled(False)

    def set_on_commit(self, fn: Callable[[str], None]) -> None:
        self._on_commit_line = fn

    def set_on_save_buffer(self, fn: Callable[[], None]) -> None:
        self._on_save_buffer = fn

    def set_initial_content(self, text: str) -> None:
        self.setPlainText(text)
        cur = self.textCursor()
        cur.movePosition(QTextCursor.End)
        self.setTextCursor(cur)
        self._anchor = cur.position()
        self._reset_history_browse()

    def append_from_process(self, text: str) -> None:
        self.moveCursor(QTextCursor.End)
        self.insertPlainText(text)
        self._anchor = self.textCursor().position()
        self._reset_history_browse()
        self.ensureCursorVisible()

    def _reset_history_browse(self) -> None:
        self._hist_browse_idx = None
        self._hist_stash = ""

    def _replace_input_tail(self, text: str) -> None:
        cur = self.textCursor()
        cur.setPosition(self._anchor)
        cur.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        cur.removeSelectedText()
        cur.insertText(text)
        cur.movePosition(QTextCursor.End)
        self.setTextCursor(cur)

    def _history_prev(self) -> None:
        if not self._cmd_history:
            return
        doc = self.toPlainText()
        tail = doc[self._anchor :]
        if self._hist_browse_idx is None:
            self._hist_stash = tail
            self._hist_browse_idx = len(self._cmd_history) - 1
        else:
            self._hist_browse_idx = max(0, self._hist_browse_idx - 1)
        self._replace_input_tail(self._cmd_history[self._hist_browse_idx])

    def _history_next(self) -> None:
        if self._hist_browse_idx is None:
            return
        if self._hist_browse_idx >= len(self._cmd_history) - 1:
            self._replace_input_tail(self._hist_stash)
            self._reset_history_browse()
            return
        self._hist_browse_idx += 1
        self._replace_input_tail(self._cmd_history[self._hist_browse_idx])

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu(event.pos())
        menu.addSeparator()
        a_copy_all = menu.addAction("Copy all")
        a_copy_all.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        a_copy_all.triggered.connect(self._copy_all_to_clipboard)
        if self._on_save_buffer is not None:
            a_save = menu.addAction("Save terminal output as…")
            a_save.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
            a_save.triggered.connect(self._on_save_buffer)
        a_clear = menu.addAction("Clear terminal output")
        a_clear.setIcon(self.style().standardIcon(QStyle.SP_LineEditClearButton))
        a_clear.triggered.connect(self._clear_buffer)
        menu.addSeparator()
        pa = menu.addAction("Paste at prompt")
        pa.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        pa.setShortcut(QKeySequence("Ctrl+Shift+V"))
        pa.triggered.connect(self._paste_at_prompt)
        menu.exec_(event.globalPos())

    def _copy_all_to_clipboard(self) -> None:
        QApplication.clipboard().setText(self.toPlainText())

    def _paste_at_prompt(self) -> None:
        self.moveCursor(QTextCursor.End)
        self.paste()

    def _clear_buffer(self) -> None:
        self.clear()
        self._anchor = 0
        self._reset_history_browse()
        self.moveCursor(QTextCursor.End)

    def keyPressEvent(self, ev):
        cur = self.textCursor()
        pos = cur.position()
        k = ev.key()
        mods = ev.modifiers()

        if mods == (Qt.ControlModifier | Qt.ShiftModifier):
            if k == Qt.Key_C:
                self.copy()
                ev.accept()
                return
            if k == Qt.Key_V:
                self.moveCursor(QTextCursor.End)
                self.paste()
                ev.accept()
                return

        if mods & Qt.ControlModifier:
            if k == Qt.Key_C:
                self.copy()
                ev.accept()
                return
            if k == Qt.Key_V:
                self.moveCursor(QTextCursor.End)
                self.paste()
                ev.accept()
                return
            if k == Qt.Key_X:
                self.copy()
                ev.accept()
                return

        if cur.hasSelection():
            start = min(cur.selectionStart(), cur.selectionEnd())
            if start < self._anchor and ev.text():
                self.moveCursor(QTextCursor.End)
                cur = self.textCursor()
                pos = cur.position()

        if pos >= self._anchor and self._hist_browse_idx is not None and ev.text() and k not in (
            Qt.Key_Up,
            Qt.Key_Down,
        ):
            self._reset_history_browse()

        if k in (Qt.Key_Up, Qt.Key_Down) and pos >= self._anchor and not (mods & Qt.ControlModifier) and not (
            mods & Qt.AltModifier
        ):
            if k == Qt.Key_Up:
                self._history_prev()
            else:
                self._history_next()
            ev.accept()
            return

        if mods & Qt.ControlModifier:
            if k in (Qt.Key_C, Qt.Key_A):
                return super().keyPressEvent(ev)
            if k == Qt.Key_V and pos < self._anchor:
                self.moveCursor(QTextCursor.End)
            return super().keyPressEvent(ev)

        if k in (Qt.Key_Return, Qt.Key_Enter):
            if mods & Qt.ShiftModifier:
                return super().keyPressEvent(ev)
            self._commit_current_line()
            ev.accept()
            return

        if k == Qt.Key_Backspace and pos <= self._anchor:
            ev.accept()
            return
        if k == Qt.Key_Delete and pos < self._anchor:
            ev.accept()
            return

        if k == Qt.Key_Left and pos <= self._anchor:
            ev.accept()
            return

        if pos < self._anchor and ev.text():
            self.moveCursor(QTextCursor.End)

        super().keyPressEvent(ev)

    def mousePressEvent(self, ev):
        super().mousePressEvent(ev)
        if ev.button() == Qt.LeftButton and self.textCursor().position() < self._anchor:
            cur = self.textCursor()
            cur.movePosition(QTextCursor.End)
            self.setTextCursor(cur)

    def _commit_current_line(self) -> None:
        cur = self.textCursor()
        pos = cur.position()
        doc = self.toPlainText()
        line = doc[self._anchor : pos]
        if "\n" in line:
            line = line.split("\n", 1)[0]
        end_input = self._anchor + len(line)
        if line.strip():
            if not self._cmd_history or self._cmd_history[-1] != line:
                self._cmd_history.append(line)
        self._reset_history_browse()
        # Remove what we typed before sending: an interactive shell echoes the line from the PTY, so
        # keeping it here duplicates "ls" / blank lines and can interleave with async stdout if we send first.
        cur = self.textCursor()
        cur.setPosition(self._anchor)
        cur.setPosition(end_input, QTextCursor.KeepAnchor)
        cur.removeSelectedText()
        doc = self.toPlainText()
        pos = self.textCursor().position()
        # If the shell did not end the previous line with a newline, insert one so the next prompt/output
        # does not glue to the prior line. Do NOT insert when typing on the same line as a prompt:
        # Windows `>`, Android/adb ` $` / `#`, or trailing space after those.
        if pos > 0:
            prev = doc[pos - 1]
            at_prompt = prev in " \t" or prev in ">$#"
            if prev != "\n" and not at_prompt:
                cur.insertText("\n")
                pos += 1
        self._anchor = pos
        self.setTextCursor(cur)
        if self._on_commit_line:
            self._on_commit_line(line)


class SessionWidget(QWidget):
    """Single terminal session: scrollback + type-at-end shell (Moba-like dark theme)."""

    def __init__(
        self,
        session_label: str,
        command: List[str],
        banner: Optional[str] = None,
        *,
        working_dir: Optional[str] = None,
        shell_profile: Optional[str] = None,
    ):
        super().__init__()
        self.session_label = session_label
        self.command = command
        self._banner = (banner or "").strip() or None
        self._trim_first_pty_chunk = bool(self._banner)
        self._shell_profile = shell_profile if shell_profile in ("cmd", "powershell") else None
        try:
            base = Path(working_dir or os.getcwd()).resolve()
        except OSError:
            base = Path.cwd()
        self._working_dir_str = str(base)
        self._cwd: Path = base
        self.proc = QProcess(self)
        self._log_fp = None
        self._log_path = self._build_log_path()
        self._build_ui()
        self._start()

    @property
    def _is_adb_shell(self) -> bool:
        if not self.command:
            return False
        low = [str(x).lower() for x in self.command]
        return "shell" in low and "adb" in str(self.command[0]).lower()

    def _build_log_path(self) -> Path:
        safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in self.session_label)[:48] or "session"
        d = Path(tempfile.gettempdir()) / "adbnik_terminal_logs"
        d.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return d / f"{ts}_{safe}.log"

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        self.output = ShellPlainTextEdit()
        self.output.setObjectName("MobaTerminalOutput")
        self.output.setFont(QFont("Consolas", 11))
        self.output.setLineWrapMode(QPlainTextEdit.NoWrap)
        # Keep UI responsive; full stream is persisted to disk.
        self.output.setMaximumBlockCount(60000)
        self.output.set_on_commit(self._send_line)
        self.output.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.output.set_on_save_buffer(self._save_buffer_as)
        layout.addWidget(self.output, 1)
        self._session_footer = QLabel()
        self._session_footer.setObjectName("TerminalSessionFooter")
        self._session_footer.setFont(QFont("Consolas", 10))
        self._session_footer.setWordWrap(True)
        self._session_footer.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._session_footer.setToolTip(
            "Current folder and session type. Type in the pane above: the caret should sit one space "
            "after the > at the end of the last line (same as Windows Terminal)."
        )
        layout.addWidget(self._session_footer)
        self._update_session_footer()
        self._pending_chunks: List[str] = []
        self._flush_timer = QTimer(self)
        self._flush_timer.setSingleShot(True)
        self._flush_timer.setInterval(25)
        self._flush_timer.timeout.connect(self._flush_pending_output)

        self.proc.readyReadStandardOutput.connect(self._read_stdout)
        self.proc.readyReadStandardError.connect(self._read_stderr)
        self.proc.finished.connect(self._on_proc_finished)

    def shutdown(self, *, wait_for_process: bool = False) -> None:
        """Stop the shell process when the tab is closed.

        On normal tab close, the kill is fire-and-forget. On application exit, pass
        ``wait_for_process=True`` so ADB/SSH child processes are reaped before teardown.
        """
        if self.proc.state() == QProcess.Running:
            self.proc.kill()
            if wait_for_process:
                self.proc.waitForFinished(8000)
        self._close_log()

    def _on_proc_finished(self):
        self.output.append_from_process("\n[session terminated]\n")
        self._write_log("\n[session terminated]\n")
        self._write_log(f"[full log path] {self._log_path}\n")
        if hasattr(self, "_session_footer"):
            self._session_footer.setText(f"Session · {self.session_label} — ended")
        self._close_log()

    def _update_session_footer(self) -> None:
        if not hasattr(self, "_session_footer"):
            return
        if self._shell_profile == "cmd":
            self._session_footer.setText(f"Session · {self.session_label}  ·  {self._cwd}> ")
        elif self._shell_profile == "powershell":
            self._session_footer.setText(f"Session · {self.session_label}  ·  PS {self._cwd}> ")
        else:
            self._session_footer.setText(f"Session · {self.session_label}")

    def _ensure_prompt_trailing_space(self) -> None:
        """CMD only: pipe-backed cmd may end with `>` without a space. PowerShell prints its own prompt; adding a space here caused extra gaps and missing prompt lines."""
        if self._shell_profile != "cmd":
            return
        doc = self.output.toPlainText()
        if not doc or doc.endswith("> ") or not doc.rstrip().endswith(">"):
            return
        last = self._last_nonempty_line().rstrip()
        if not re.search(r"[A-Za-z]:\\[^>\n]*>$", last):
            return
        self.output.append_from_process(" ")

    def _send_line(self, line: str) -> None:
        if self.proc.state() != QProcess.Running:
            return
        self._apply_local_cd_line(line)
        self._update_session_footer()
        self._write_log(f">>> {line}\n")
        self.proc.write((line + "\n").encode("utf-8", errors="replace"))

    def _format_local_prompt(self) -> str:
        """Trailing space after `>` so the caret sits one space past the prompt (CMD pipe sessions only)."""
        return f"{str(self._cwd)}> "

    def _last_nonempty_line(self) -> str:
        for line in reversed(self.output.toPlainText().split("\n")):
            if line.strip():
                return line
        return ""

    def _buffer_already_shows_prompt(self) -> bool:
        if self._shell_profile != "cmd":
            return True
        last = self._last_nonempty_line().rstrip()
        if not last:
            return False
        return bool(re.search(r"[A-Za-z]:\\[^>\n]*>\s*$", last))

    def _maybe_append_synthetic_prompt(self) -> None:
        if not self._shell_profile or self.proc.state() != QProcess.Running:
            return
        # PowerShell already prints "PS path>" on stdout; a synthetic line duplicates it (PS ...> PS ...>).
        if self._shell_profile == "powershell":
            return
        if self._buffer_already_shows_prompt():
            return
        p = self._format_local_prompt()
        if not self.output.toPlainText().endswith("\n"):
            self.output.append_from_process("\n")
        self.output.append_from_process(p)

    def _apply_local_cd_line(self, line: str) -> None:
        """Best-effort cwd for the synthetic prompt (the real shell updates its own cwd)."""
        if not self._shell_profile:
            return
        raw = (line or "").strip()
        if not raw:
            return
        low = raw.lower()
        arg_part: Optional[str] = None
        if low.startswith("cd "):
            arg_part = raw[3:].strip()
        elif low.startswith("cd\\") or low.startswith("cd/"):
            arg_part = raw[2:].lstrip("/\\").strip()
        elif self._shell_profile == "powershell":
            if low.startswith("set-location "):
                arg_part = raw.split(None, 1)[1].strip() if len(raw.split()) > 1 else ""
            elif low == "sl" or low.startswith("sl "):
                arg_part = raw.split(None, 1)[1].strip() if len(raw.split()) > 1 else ""
        if arg_part is None:
            return
        arg = arg_part.strip().strip('"').strip("'")
        if not arg:
            return
        if self._shell_profile == "cmd" and arg.lower().startswith("/d "):
            rest = arg[3:].strip()
            try:
                self._cwd = Path(rest).resolve()
            except OSError:
                pass
            return
        if arg == "..":
            self._cwd = self._cwd.parent
            return
        if arg in (".\\", "./", "."):
            return
        p = Path(arg)
        if not p.is_absolute():
            try:
                self._cwd = (self._cwd / arg).resolve()
            except OSError:
                pass
        else:
            try:
                self._cwd = p.resolve()
            except OSError:
                pass

    def send_line(self, line: str) -> None:
        """Send a full line to the shell (same as pressing Enter after typing)."""
        self._send_line((line or "").rstrip("\n"))

    def _tighten_adb_chunk(self, text: str) -> str:
        """ADB shell PTY often emits extra blank lines between prompt, echo, and output — collapse to a single newline."""
        if not text:
            return text
        text = re.sub(r"\n{2,}", "\n", text)
        doc = self.output.toPlainText()
        if doc.endswith("\n") and text.startswith("\n"):
            text = text[1:]
        return text

    def _append(self, data: str):
        if not data:
            return
        data = _normalize_pty_text(data)
        if self._trim_first_pty_chunk:
            data = data.lstrip("\n")
            if not data:
                return
            self._trim_first_pty_chunk = False
        if not data:
            return
        self._write_log(data)
        self._pending_chunks.append(data)
        if not self._flush_timer.isActive():
            self._flush_timer.start()

    def _flush_pending_output(self) -> None:
        if not self._pending_chunks:
            return
        text = "".join(self._pending_chunks)
        self._pending_chunks.clear()
        if self._is_adb_shell:
            text = self._tighten_adb_chunk(text)
        self.output.append_from_process(text)
        self._maybe_append_synthetic_prompt()
        self._ensure_prompt_trailing_space()
        self._update_session_footer()

    def _start(self):
        # Banner line only; first PTY bytes may include leading newlines — trimmed in _append.
        self.output.set_initial_content((self._banner + "\n") if self._banner else "")
        self._open_log()
        if self._banner:
            self._write_log(self._banner + "\n")
        self.proc.setWorkingDirectory(self._working_dir_str)
        self.proc.start(self.command[0], self.command[1:])
        if not self.proc.waitForStarted(3500):
            self._append("Failed to start terminal process.\n")
        self.output.setFocus(Qt.OtherFocusReason)
        if self._shell_profile == "cmd":
            QTimer.singleShot(120, self._maybe_append_synthetic_prompt)
        self._update_session_footer()

    def _read_stdout(self):
        self._append(bytes(self.proc.readAllStandardOutput()).decode(errors="ignore"))

    def _read_stderr(self):
        self._append(bytes(self.proc.readAllStandardError()).decode(errors="ignore"))

    def _save_buffer_as(self) -> None:
        suggested = f"{self.session_label.replace(' ', '_')}.txt"
        path, _ = QFileDialog.getSaveFileName(self, "Save terminal output as", suggested, "Text files (*.txt);;All files (*.*)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", errors="replace") as f:
                f.write(self.output.toPlainText())
        except OSError:
            pass

    def _open_log(self) -> None:
        if self._log_fp is None:
            self._log_fp = self._log_path.open("a", encoding="utf-8", errors="replace")

    def _write_log(self, text: str) -> None:
        try:
            if self._log_fp is None:
                self._open_log()
            if self._log_fp is not None:
                self._log_fp.write(text)
                self._log_fp.flush()
        except Exception:
            pass

    def _close_log(self) -> None:
        try:
            if self._log_fp is not None:
                self._log_fp.flush()
                self._log_fp.close()
        except Exception:
            pass
        self._log_fp = None


class TerminalTab(QWidget):
    """MobaXterm-like workspace: device/serial bar, sidebar + tabbed sessions (dark terminal)."""

    def __init__(
        self,
        get_adb_path: Callable[[], str],
        get_default_ssh_host: Callable[[], str],
        get_default_serial_port: Callable[[], str],
        get_default_serial_baud: Callable[[], str],
        config: AppConfig,
        append_log: Optional[Callable[[str], None]] = None,
    ):
        super().__init__()
        self.get_adb_path = get_adb_path
        self.get_default_ssh_host = get_default_ssh_host
        self.get_default_serial_port = get_default_serial_port
        self.get_default_serial_baud = get_default_serial_baud
        self.config = config
        self._append_log = append_log or (lambda _m: None)
        self._placeholder_tab: Optional[QWidget] = None
        self._build_ui()

    def _init_hidden_session_controls(self) -> None:
        """ADB device list + serial fields for MainWindow (File Explorer, menus). Combo stays hidden in Terminal."""
        self.device_combo = ExpandAllComboBox(self)
        self.device_combo.setObjectName("SessionDeviceCombo")
        self.device_combo.setMaxVisibleItems(20)
        self.device_combo.hide()
        self.serial_port_edit = QLineEdit(self)
        self.serial_port_edit.setObjectName("TerminalSerialPortHidden")
        self.serial_baud_edit = QLineEdit(self)
        self.serial_baud_edit.setObjectName("TerminalSerialBaudHidden")
        self.serial_port_edit.setText(self.config.default_serial_port or "COM3")
        self.serial_baud_edit.setText(self.config.default_serial_baud or "115200")
        self.serial_port_edit.hide()
        self.serial_baud_edit.hide()

    def get_adb_serial(self) -> str:
        return self.current_adb_serial()

    def current_adb_serial(self) -> str:
        d = self.device_combo.currentData()
        if d is not None and str(d).strip():
            return str(d).strip()
        return _serial_from_combo_text(self.device_combo.currentText())

    def get_session_profile(self) -> SessionProfile:
        return SessionProfile(
            ConnectionKind.ANDROID_ADB,
            adb_serial=self.current_adb_serial(),
        )

    def get_serial_session_profile(self) -> SessionProfile:
        return SessionProfile(
            ConnectionKind.SERIAL,
            serial_port=self.serial_port_edit.text().strip() or self.get_default_serial_port(),
            serial_baud=self.serial_baud_edit.text().strip() or self.get_default_serial_baud(),
        )

    def sync_serial_from_config(self) -> None:
        self.serial_port_edit.setText(self.config.default_serial_port or "COM3")
        self.serial_baud_edit.setText(self.config.default_serial_baud or "115200")

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self._init_hidden_session_controls()

        top_toolbar = QHBoxLayout()
        top_toolbar.setSpacing(8)
        st = self.style()
        b_new = QPushButton("New Session…")
        b_new.setObjectName("MobaToolBtn")
        b_new.setIcon(st.standardIcon(QStyle.SP_FileDialogNewFolder))
        b_new.clicked.connect(self.add_session_dialog)
        top_toolbar.addWidget(b_new)
        top_toolbar.addStretch(1)
        layout.addLayout(top_toolbar)
        start_hint = QLabel(
            "How to start: click New Session, choose protocol/details, then open the terminal tab."
        )
        start_hint.setObjectName("MobaTabCtrlLabel")
        start_hint.setWordWrap(True)
        layout.addWidget(start_hint)

        split = QSplitter()
        layout.addWidget(split, 1)

        left = QWidget()
        left.setObjectName("MobaLeftPane")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(8)

        bm_lbl = QLabel("Bookmarks")
        bm_lbl.setObjectName("MobaSidebarHeading")
        left_layout.addWidget(bm_lbl)
        self.bookmark_list = QListWidget()
        self.bookmark_list.setObjectName("MobaBookmarkList")
        self.bookmark_list.setIconSize(QSize(20, 20))
        self.bookmark_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.bookmark_list.itemDoubleClicked.connect(self._on_bookmark_double_clicked)
        self.bookmark_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.bookmark_list.customContextMenuRequested.connect(self._on_bookmark_context_menu)
        left_layout.addWidget(self.bookmark_list, 1)
        self._reload_bookmark_sidebar()

        local_row = QHBoxLayout()
        local_row.setSpacing(4)
        for txt, fn, ic in [
            ("CMD", self._open_local_cmd, icon_windows_cmd_console()),
            ("PowerShell", self._open_local_powershell, icon_windows_powershell()),
        ]:
            b = QPushButton(txt)
            b.setObjectName("MobaToolBtn")
            b.setIcon(ic)
            b.clicked.connect(fn)
            local_row.addWidget(b)
        left_layout.addLayout(local_row)

        pin_row = QHBoxLayout()
        pin_row.setSpacing(4)
        b1 = QPushButton("Pin CMD")
        b1.setObjectName("MobaToolBtn")
        b1.setIcon(st.standardIcon(QStyle.SP_DialogSaveButton))
        b1.setToolTip("Save Command Prompt as a bookmark")
        b1.clicked.connect(self._pin_local_cmd_bookmark)
        b2 = QPushButton("Pin PS")
        b2.setObjectName("MobaToolBtn")
        b2.setIcon(st.standardIcon(QStyle.SP_DialogSaveButton))
        b2.setToolTip("Save PowerShell as a bookmark")
        b2.clicked.connect(self._pin_local_pwsh_bookmark)
        pin_row.addWidget(b1)
        pin_row.addWidget(b2)
        left_layout.addLayout(pin_row)

        go = QPushButton("Login…")
        go.setObjectName("MobaToolBtn")
        go.setIcon(st.standardIcon(QStyle.SP_DialogOpenButton))
        go.clicked.connect(self.add_session_dialog)
        left_layout.addWidget(go)

        right = QWidget()
        right.setObjectName("MobaRightPane")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("MobaTabs")
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        tb = self.tabs.tabBar()
        tb.setObjectName("MobaTabBar")
        tb.setElideMode(Qt.ElideNone)
        tb.setUsesScrollButtons(True)
        tb.setContextMenuPolicy(Qt.CustomContextMenu)
        tb.customContextMenuRequested.connect(self._on_terminal_tab_bar_context_menu)
        self.tabs.tabCloseRequested.connect(self._on_tab_close)
        right_layout.addWidget(self.tabs, 1)

        status = QLabel("Ready")
        status.setObjectName("MobaStatus")
        right_layout.addWidget(status)

        split.addWidget(left)
        split.addWidget(right)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([240, 1000])

        self._add_placeholder_tab()

    def _ssh_tab_title(self, profile: SessionProfile) -> str:
        h = (profile.ssh_host or "").strip()
        u = (profile.ssh_user or "").strip()
        p = int(profile.ssh_port or 22)
        if u:
            base = f"{u}@{h}"
        else:
            base = h or "SSH"
        if p != 22:
            return f"{base}:{p}"
        return base

    def _reload_bookmark_sidebar(self) -> None:
        self.bookmark_list.clear()
        for bm in self.config.session_bookmarks:
            if not isinstance(bm, dict):
                continue
            if bm.get("kind") not in ("ssh", "adb", "serial", "local_cmd", "local_pwsh"):
                continue
            it = QListWidgetItem(bm.get("name") or "Untitled")
            it.setIcon(bookmark_icon_from_entry(bm, self))
            it.setData(Qt.UserRole, bm)
            self.bookmark_list.addItem(it)

    def _on_bookmark_double_clicked(self, item: QListWidgetItem) -> None:
        bm = item.data(Qt.UserRole)
        if isinstance(bm, dict):
            self._open_bookmark(bm)

    def _on_bookmark_context_menu(self, pos) -> None:
        it = self.bookmark_list.itemAt(pos)
        m = QMenu(self)
        a_login = m.addAction("Start new session…")
        a_login.setIcon(self.style().standardIcon(QStyle.SP_FileDialogNewFolder))
        a_login.triggered.connect(self.add_session_dialog)
        if it is not None:
            bm = it.data(Qt.UserRole)
            if isinstance(bm, dict):
                m.addSeparator()
                a_open = m.addAction("Open bookmark")
                a_open.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
                a_open.triggered.connect(lambda: self._open_bookmark(bm))
                a_new = m.addAction("Start new session from bookmark")
                a_new.setIcon(self.style().standardIcon(QStyle.SP_FileDialogNewFolder))
                a_new.triggered.connect(lambda: self._open_bookmark(bm))
        selected = [x for x in self.bookmark_list.selectedItems() if isinstance(x.data(Qt.UserRole), dict)]
        if selected:
            m.addSeparator()
            a_del = m.addAction(f"Delete selected bookmark(s) ({len(selected)})")
            a_del.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
            a_del.triggered.connect(self._delete_selected_bookmarks)
        m.exec_(self.bookmark_list.mapToGlobal(pos))

    def _delete_bookmark_by_name(self, name: str) -> None:
        if not name:
            return
        self.config.session_bookmarks = [
            x for x in self.config.session_bookmarks if isinstance(x, dict) and x.get("name") != name
        ]
        self.config.save()
        self._reload_bookmark_sidebar()

    def _delete_selected_bookmarks(self) -> None:
        names = []
        for it in self.bookmark_list.selectedItems():
            bm = it.data(Qt.UserRole)
            if isinstance(bm, dict):
                n = str(bm.get("name", "")).strip()
                if n:
                    names.append(n)
        if not names:
            return
        drop = set(names)
        self.config.session_bookmarks = [
            x
            for x in self.config.session_bookmarks
            if not (isinstance(x, dict) and str(x.get("name", "")).strip() in drop)
        ]
        self.config.save()
        self._reload_bookmark_sidebar()

    def _open_bookmark(self, bm: dict) -> None:
        k = bm.get("kind")
        if k == "local_cmd":
            self._open_local_cmd()
            return
        if k == "local_pwsh":
            self._open_local_powershell()
            return
        if k == "adb":
            serial = (bm.get("adb_serial") or "").strip()
            if not serial:
                QMessageBox.information(self, "Bookmark", "This bookmark has no device serial.")
                return
            adb = self.get_adb_path()
            cmd = adb_interactive_shell_command(adb, serial)
            label = (bm.get("adb_label") or "").strip() or f"{friendly_name_for_serial(adb, serial)} · {serial}"
            self.add_session(label, cmd, banner=_adb_terminal_banner(adb, serial, label))
            return
        if k == "ssh":
            try:
                sp = int(bm.get("ssh_port") or 22)
            except (TypeError, ValueError):
                sp = 22
            profile = SessionProfile(
                ConnectionKind.SSH_SFTP,
                ssh_host=bm.get("ssh_host", ""),
                ssh_user=bm.get("ssh_user", ""),
                ssh_port=sp,
                ssh_password=bm.get("ssh_password", "") or "",
            )
            self.add_session(self._ssh_tab_title(profile), ssh_command_args(profile))
            return
        if k == "serial":
            port = bm.get("serial_port") or self.get_default_serial_port()
            baud = bm.get("serial_baud") or self.get_default_serial_baud()
            cmd = [sys.executable, "-m", "serial.tools.miniterm", str(port), str(baud)]
            self.add_session(f"Serial · {port}", cmd)

    def _open_local_cmd(self) -> None:
        # Small quality-of-life aliases so Linux-style habits still work in CMD.
        cmd_exe = os.environ.get("COMSPEC", "cmd.exe")
        # Chain with `&` — `$T` is for inside a doskey macro body, not two separate doskey commands.
        self.add_session(
            "Command Prompt",
            [cmd_exe, "/K", "doskey ls=dir & doskey pwd=cd"],
            working_dir=os.getcwd(),
            shell_profile="cmd",
        )

    def _open_local_powershell(self) -> None:
        sys_root = os.environ.get("SystemRoot", r"C:\Windows")
        ps = Path(sys_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        ps_exe = str(ps) if ps.is_file() else "powershell.exe"
        # Startup command: `lx` is a common typo for `ls` (helps when muscle memory slips).
        self.add_session(
            "Windows PowerShell",
            [
                ps_exe,
                "-NoLogo",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-NoExit",
                "-Command",
                "Set-Alias -Name lx -Value Get-ChildItem -Scope Global",
            ],
            working_dir=os.getcwd(),
            shell_profile="powershell",
        )

    def _next_bookmark_name(self, base: str) -> str:
        names = {x.get("name") for x in self.config.session_bookmarks if isinstance(x, dict)}
        if base not in names:
            return base
        n = 2
        while f"{base} ({n})" in names:
            n += 1
        return f"{base} ({n})"

    def _pin_local_cmd_bookmark(self) -> None:
        name = self._next_bookmark_name("Command Prompt")
        self.config.session_bookmarks.append({"name": name, "kind": "local_cmd"})
        self.config.save()
        self._reload_bookmark_sidebar()

    def _pin_local_pwsh_bookmark(self) -> None:
        name = self._next_bookmark_name("Windows PowerShell")
        self.config.session_bookmarks.append({"name": name, "kind": "local_pwsh"})
        self.config.save()
        self._reload_bookmark_sidebar()

    def _add_placeholder_tab(self) -> None:
        if self._placeholder_tab is not None:
            return
        w = QWidget()
        w.setObjectName("MobaRightPane")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 16, 20, 16)
        msg = QLabel(
            "No shell session yet.\n\n"
            "Use the sidebar to open Command Prompt or PowerShell, or New Session for SSH or Android (ADB). "
            "Plug in the device and use Session → Refresh if the list is empty."
        )
        msg.setWordWrap(True)
        msg.setObjectName("MobaMenuText")
        msg.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addStretch(1)
        lay.addWidget(msg)
        go = QPushButton("New Session…")
        go.setObjectName("MobaToolBtn")
        go.setIcon(self.style().standardIcon(QStyle.SP_FileDialogNewFolder))
        go.clicked.connect(self.add_session_dialog)
        lay.addWidget(go, alignment=Qt.AlignHCenter)
        lay.addStretch(2)
        self._placeholder_tab = w
        self.tabs.addTab(w, "Start")

    def _on_tab_close(self, index: int) -> None:
        w = self.tabs.widget(index)
        if isinstance(w, SessionWidget):
            w.shutdown()
        if w is self._placeholder_tab:
            self._placeholder_tab = None
        self.tabs.removeTab(index)
        if self.tabs.count() == 0:
            self._add_placeholder_tab()

    def _on_terminal_tab_bar_context_menu(self, pos) -> None:
        """Moba-style: right-click a session tab for close / close others / close to the side."""
        tb = self.tabs.tabBar()
        idx = tb.tabAt(pos)
        if idx < 0:
            return
        m = QMenu(self)
        a_close = m.addAction("Close")
        a_close.setToolTip("Close this tab")
        a_others = m.addAction("Close others")
        a_others.setToolTip("Close all tabs except this one")
        a_right = m.addAction("Close to the right")
        a_right.setToolTip("Close every tab to the right of this one")
        a_left = m.addAction("Close to the left")
        a_left.setToolTip("Close every tab to the left of this one")
        chosen = m.exec_(tb.mapToGlobal(pos))
        if chosen == a_close:
            self._remove_tab_at(idx)
            if self.tabs.count() == 0:
                self._add_placeholder_tab()
        elif chosen == a_others:
            self._close_all_tabs_except(idx)
        elif chosen == a_right:
            self._close_tabs_to_the_right_of(idx)
        elif chosen == a_left:
            self._close_tabs_to_the_left_of(idx)

    def _close_all_tabs_except(self, keep_index: int) -> None:
        for i in range(self.tabs.count() - 1, -1, -1):
            if i != keep_index:
                self._remove_tab_at(i)
        if self.tabs.count() == 0:
            self._add_placeholder_tab()

    def _close_tabs_to_the_right_of(self, index: int) -> None:
        for i in range(self.tabs.count() - 1, index, -1):
            self._remove_tab_at(i)
        if self.tabs.count() == 0:
            self._add_placeholder_tab()

    def _close_tabs_to_the_left_of(self, index: int) -> None:
        for i in range(index - 1, -1, -1):
            self._remove_tab_at(i)
        if self.tabs.count() == 0:
            self._add_placeholder_tab()

    def _remove_tab_at(self, index: int) -> None:
        """Remove tab by index; shutdown SessionWidget if present."""
        if index < 0 or index >= self.tabs.count():
            return
        w = self.tabs.widget(index)
        if isinstance(w, SessionWidget):
            w.shutdown()
        if w is self._placeholder_tab:
            self._placeholder_tab = None
        self.tabs.removeTab(index)

    def add_session_dialog(self) -> None:
        dlg = SessionLoginDialog(
            self.get_adb_path,
            self.get_default_ssh_host(),
            self.current_adb_serial() or "",
            self,
            for_terminal=True,
            config=self.config,
            on_bookmarks_changed=self._reload_bookmark_sidebar,
        )
        if dlg.exec_() != QDialog.Accepted:
            return
        o = dlg.outcome()
        if o:
            self._apply_login_outcome(o)

    def _apply_login_outcome(self, o: SessionLoginOutcome) -> None:
        if o.kind == "adb":
            adb = self.get_adb_path()
            serial = (o.adb_serial or "").strip()
            cmd = adb_interactive_shell_command(adb, serial or None)
            short = (o.adb_display_label or "").strip() or f"{friendly_name_for_serial(self.get_adb_path(), serial)} · {serial}"
            self.add_session(short, cmd, banner=_adb_terminal_banner(adb, serial, short))
        elif o.kind == "sftp":
            profile = SessionProfile(
                ConnectionKind.SSH_SFTP,
                ssh_host=o.sftp_host,
                ssh_user=o.sftp_user,
                ssh_port=o.sftp_port,
                ssh_password=o.sftp_password or "",
            )
            self.add_session(self._ssh_tab_title(profile), ssh_command_args(profile))
        elif o.kind == "serial":
            port = (o.serial_port or "").strip() or self.get_default_serial_port()
            baud = (o.serial_baud or "").strip() or self.get_default_serial_baud()
            cmd = [sys.executable, "-m", "serial.tools.miniterm", port, baud]
            self.add_session(f"Serial · {port}", cmd)
        elif o.kind == "local_cmd":
            self._open_local_cmd()
        elif o.kind == "local_pwsh":
            self._open_local_powershell()

    def add_session(
        self,
        label: str,
        command: List[str],
        *,
        banner: Optional[str] = None,
        working_dir: Optional[str] = None,
        shell_profile: Optional[str] = None,
    ):
        if self._placeholder_tab is not None:
            idx = self.tabs.indexOf(self._placeholder_tab)
            if idx >= 0:
                self.tabs.removeTab(idx)
            self._placeholder_tab = None
        widget = SessionWidget(
            label,
            command,
            banner=banner,
            working_dir=working_dir,
            shell_profile=shell_profile,
        )
        idx = self.tabs.addTab(widget, label)
        self.tabs.setCurrentIndex(idx)

    def close_session(self):
        idx = self.tabs.currentIndex()
        if idx < 0:
            return
        w = self.tabs.widget(idx)
        if isinstance(w, SessionWidget):
            w.shutdown()
        if w is self._placeholder_tab:
            self._placeholder_tab = None
        self.tabs.removeTab(idx)
        if self.tabs.count() == 0:
            self._add_placeholder_tab()

    def send_line_to_current_session(self, line: str) -> bool:
        """Send one line to the active terminal tab. Returns False if no running session."""
        w = self.tabs.currentWidget()
        if not isinstance(w, SessionWidget):
            QMessageBox.information(
                self,
                "Terminal",
                "Open a terminal session tab first (e.g. Session → SSH → New SSH session).",
            )
            return False
        w.send_line(line)
        self.tabs.setCurrentWidget(w)
        return True

    def shutdown_all_sessions(self) -> None:
        """Terminate every open shell (ADB, SSH, serial, local) before the application exits."""
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, SessionWidget):
                w.shutdown(wait_for_process=True)

    def _open_current_connection(self):
        self.open_session_matching_profile(self.get_session_profile())

    def open_session_matching_profile(self, profile: SessionProfile):
        if profile.kind == ConnectionKind.ANDROID_ADB:
            adb = self.get_adb_path()
            serial = (profile.adb_serial or "").strip()
            cmd = adb_interactive_shell_command(adb, serial or None)
            short = f"{friendly_name_for_serial(adb, serial)} · {serial}" if serial else "ADB"
            self.add_session(short, cmd, banner=_adb_terminal_banner(adb, serial, short))
        elif profile.kind == ConnectionKind.SSH_SFTP:
            if not (profile.ssh_host or "").strip():
                QMessageBox.information(
                    self,
                    "SSH",
                    "Enter host in File Explorer → SFTP tab, then use "
                    "Session → Open SSH terminal (from Explorer SFTP fields).",
                )
                return
            self.add_session(self._ssh_tab_title(profile), ssh_command_args(profile))
        elif profile.kind == ConnectionKind.FTP:
            QMessageBox.information(
                self,
                "FTP",
                "FTP is for file transfer in File Explorer. Use New Session for a shell.",
            )
        elif profile.kind == ConnectionKind.SERIAL:
            port = profile.serial_port or self.get_default_serial_port()
            baud = profile.serial_baud or self.get_default_serial_baud()
            cmd = [sys.executable, "-m", "serial.tools.miniterm", port, baud]
            self.add_session(f"Serial · {port}", cmd)
