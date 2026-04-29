import os
import re
import shlex
from html import escape as html_escape
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from ...session import ConnectionKind, SessionProfile, normalize_tcp_port, ssh_command_args
from ...services.adb_devices import friendly_name_for_serial
from ...services.commands import run_adb
from ..session_login_dialog import SessionLoginDialog, SessionLoginOutcome

from PyQt5.QtCore import QProcessEnvironment, QSize, Qt, QProcess, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QFont, QIcon, QKeySequence, QTextCharFormat, QTextCursor, QTextOption
from PyQt5.QtWidgets import (
    QAction,
    QAbstractItemView,
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QShortcut,
    QSplitter,
    QStyle,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...config import AppConfig
from ..ansi_html import (
    AnsiToHtmlConverter,
    bare_unix_prompt_needs_trailing_space,
    ensure_remote_pty_visual_line_breaks,
    get_prompt_palette,
    normalize_remote_pty_plain_text,
    preprocess_escape_noise,
    preprocess_prompt_lines_for_highlight,
    preprocess_serial_esc_boundaries,
    preprocess_serial_stream,
    strip_sgr_sequences_for_prompt,
)
from ..combo_utils import ExpandAllComboBox
from ..file_dialogs import get_save_filename
from ..icon_utils import (
    bookmark_icon_from_entry,
    icon_adb_android,
    icon_serial_port,
    icon_ssh_session,
    icon_windows_cmd_console,
    icon_windows_powershell,
)

# SSH/ADB use plain QTextCursor.insertText (not insertHtml); larger cap, still bounded per timer tick.
# Smaller chunks + slightly faster timer yield smoother tab switches under heavy streams.
_LOCAL_HTML_FLUSH_CAP = 96 * 1024
_SERIAL_MINITERM_BANNER_RE = re.compile(
    r"(?ms)^---[^\n]*(?:Miniterm|miniterm)[^\n]*\r?\n|"
    r"^---[^\n]*Quit:\s*Ctrl[^\n]*\r?\n|"
    r"^---[^\n]*Menu:\s*Ctrl[^\n]*\r?\n|"
    r"^---[^\n]*Help:\s*Ctrl[^\n]*\r?\n"
)


def _filter_serial_miniterm_banner(text: str) -> str:
    """Hide pySerial miniterm boilerplate; we show our own serial-console banner instead."""
    if not text:
        return text
    return _SERIAL_MINITERM_BANNER_RE.sub("", text)


def _scrub_serial_display_glitches(text: str) -> str:
    """Drop UART artifacts like ``[0;39m`` / ``0;39m`` / stray CSI bodies when ESC was lost or split."""
    if not text:
        return text
    text = re.sub(r"(?i)(?<!\x1b)\[(?:\d{1,4};)*\d{1,4}m", "", text)
    text = re.sub(r"(?i)(?<!\x1b)\[(?:0;)?39m", "", text)
    text = re.sub(r"(?i)(?<!\x1b)\[0m\b", "", text)
    text = re.sub(r"(?i)(?<!\x1b)\[0?[;:]39m\]?", "", text)
    text = re.sub(r"(?i)(?<![\d\x1b\[])\b0[;:]39m\b", "", text)
    text = re.sub(r"(?m)^\s*\[?0[;:.]39m\]?\s*$", "", text)
    text = re.sub(r"(?<![\[\x1b])0;39m", "", text)
    text = re.sub(r"(?i)(?<![\[\x1b])0\.39m", "", text)
    return text


class _SerialPortReleaseThread(QThread):
    """Windows taskkill / miniterm cleanup and pacing sleeps — must not run on the GUI thread."""

    finished_ok = pyqtSignal()

    def __init__(self, com: str, serial_pid: Optional[int], still_running: bool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._com = (com or "").strip()
        self._serial_pid = serial_pid
        self._still_running = bool(still_running)

    def run(self) -> None:
        if self._serial_pid and self._still_running:
            _win_taskkill_serial_tree(self._serial_pid)
            time.sleep(0.35)
        if sys.platform == "win32" and self._com:
            _win_kill_python_miniterm_for_com(self._com)
            time.sleep(0.75)
        else:
            time.sleep(0.45)
        self.finished_ok.emit()


def _serial_from_combo_text(text: str) -> str:
    t = (text or "").strip()
    if not t or t.startswith("No ") or "not found" in t.lower():
        return ""
    return t.split()[0]


def bookmark_session_tab_title(bm: dict) -> str:
    """Tab label when opening a saved bookmark: name · kind · connection details."""
    name = (bm.get("name") or "").strip() or "Bookmark"
    k = str(bm.get("kind", "")).lower()
    if k == "local_cmd":
        return f"{name} · Local · CMD"
    if k == "local_pwsh":
        return f"{name} · Local · PowerShell"
    if k == "adb":
        ser = (bm.get("adb_serial") or "").strip()
        label = (bm.get("adb_label") or "").strip()
        if label and ser:
            detail = f"{label} · {ser}"
        elif ser:
            detail = ser
        elif label:
            detail = label
        else:
            detail = ""
        return f"{name} · ADB · {detail}" if detail else f"{name} · ADB"
    if k == "ssh":
        host = str(bm.get("ssh_host", "")).strip()
        user = str(bm.get("ssh_user", "")).strip()
        try:
            sp = int(bm.get("ssh_port") or 22)
        except (TypeError, ValueError):
            sp = 22
        sp = normalize_tcp_port(sp, 22)
        base = f"{user}@{host}" if user else host
        if sp != 22:
            base = f"{base}:{sp}"
        return f"{name} · SSH · {base}" if base.strip() else f"{name} · SSH"
    if k == "serial":
        port = str(bm.get("serial_port") or "").strip()
        baud = str(bm.get("serial_baud") or "").strip()
        if port and baud:
            detail = f"{port} @ {baud}"
        elif port:
            detail = port
        elif baud:
            detail = baud
        else:
            detail = ""
        return f"{name} · Serial · {detail}" if detail else f"{name} · Serial"
    return name


def bookmark_entry_fingerprint(bm: dict) -> str:
    """Stable key for a saved bookmark (matches SessionWidget.session_bookmark_fingerprint)."""
    if not isinstance(bm, dict):
        return ""
    k = str(bm.get("kind", "")).lower()
    if k == "adb":
        return f"adb:{(bm.get('adb_serial') or '').strip()}"
    if k == "ssh":
        host = (bm.get("ssh_host") or "").strip().lower()
        user = (bm.get("ssh_user") or "").strip().lower()
        try:
            port = int(bm.get("ssh_port") or 22)
        except (TypeError, ValueError):
            port = 22
        tgt = f"{user}@{host}" if user else host
        return f"ssh:{tgt}:{port}"
    if k == "serial":
        return f"serial:{str(bm.get('serial_port') or '').strip().upper()}"
    if k == "local_cmd":
        return "local_cmd"
    if k == "local_pwsh":
        return "local_pwsh"
    return ""


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


def _preferred_python_exe_from_path(path_val: str) -> str:
    raw_path = path_val or os.environ.get("PATH", "")
    for d in raw_path.split(os.pathsep):
        d = (d or "").strip().strip('"')
        if not d:
            continue
        p = Path(d) / "python.exe"
        if p.is_file() and "windowsapps" not in str(p).lower():
            return str(p)
    cand = shutil.which("python") or ""
    if cand and "windowsapps" not in cand.lower() and Path(cand).is_file():
        return cand
    return str(Path(sys.executable).resolve())


_ssh_tab_ls_cache: Dict[Tuple[str, str, str, str], Tuple[float, List[str]]] = {}
_SSH_TAB_LS_TTL_SEC = 0.75
_ssh_tab_cmd_pool_cache: Dict[Tuple[str, str, str], Tuple[float, List[str]]] = {}
_SSH_TAB_CMD_POOL_TTL_SEC = 120.0
# One helper ssh at a time so Tab completion does not stack under load (keeps rest of UI smooth).
_SSH_HELPER_SUBPROCESS_LOCK = threading.Lock()


def _ssh_remote_path_pool_script() -> str:
    """Remote shell: list common QNX/Android bin dirs first (e.g. /ifs/bin), then walk ``$PATH``."""
    return (
        "n=0; "
        "for d in /ifs/bin /system/bin /vendor/bin /opt/bin /usr/bin /bin /sbin /usr/sbin; do "
        '[ ! -d "$d" ] && continue; '
        'n=$((n+1)); [ "$n" -gt 10 ] && break; '
        "printf '%s\\n' \"__ADBNIK_H__:$d\"; "
        'ls -1a "$d" 2>/dev/null || true; '
        "done; "
        "IFS=:; "
        "for d in $PATH; do "
        '[ -z "$d" ] && continue; [ ! -d "$d" ] && continue; '
        'n=$((n+1)); [ "$n" -gt 22 ] && break; '
        "printf '%s\\n' \"__ADBNIK_H__:$d\"; "
        'ls -1a "$d" 2>/dev/null || true; '
        "done"
    )


def _ssh_subprocess_run_flags() -> int:
    if sys.platform != "win32":
        return 0
    flags = int(subprocess.CREATE_NO_WINDOW)  # type: ignore[attr-defined]
    # Keep Tab-completion ssh.exe from starving the Qt UI thread on Windows.
    bnp = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
    if bnp:
        flags |= int(bnp)
    return flags


def _ssh_tab_render_token(left: str, token: str) -> str:
    if " " not in token:
        return token
    cmd = (left or "").lstrip()
    if cmd.startswith("cd "):
        return f'"{token}"'
    return token.replace(" ", r"\ ")


def _expand_common_prefix_str(token: str, candidates: Sequence[str]) -> str:
    if not token or not candidates:
        return token
    lowers = [c.lower() for c in candidates]
    low_prefix = os.path.commonprefix(lowers)
    if not low_prefix:
        return token
    first = candidates[0]
    matched_case_prefix = first[: len(low_prefix)]
    if len(low_prefix) > len(token):
        return matched_case_prefix
    if len(low_prefix) == len(token) and token.lower() == low_prefix and token != matched_case_prefix:
        return matched_case_prefix
    return token


def _ssh_tab_complete_compute(
    exe: str,
    port: str,
    target: str,
    cwd: str,
    want_path: bool,
    token: str,
    left: str,
) -> dict:
    """SSH Tab completion work (runs off the UI thread). Returns a small dict for the main thread."""
    try:
        if want_path:
            if token.startswith("/"):
                remote_dir = token.rsplit("/", 1)[0] or "/"
                prefix = token.rsplit("/", 1)[1]
            else:
                rel_dir = token.rsplit("/", 1)[0] if "/" in token else ""
                prefix = token.rsplit("/", 1)[1] if "/" in token else token
                base = (cwd.rstrip("/") + "/" + rel_dir).replace("//", "/") if rel_dir else cwd
                remote_dir = base
            names = _ssh_list_dir_names_for_args(exe, port, target, remote_dir)
            prefix_l = prefix.lower()
            candidates = [n for n in names if n.lower().startswith(prefix_l)]
            if len(candidates) == 1:
                filled = (
                    f"{remote_dir.rstrip('/')}/{candidates[0]}"
                    if token.startswith("/")
                    else (f"{token.rsplit('/', 1)[0]}/{candidates[0]}" if "/" in token else candidates[0])
                )
                if not filled.endswith("/"):
                    filled = filled + "/"
                return {"action": "set_tail", "text": left + _ssh_tab_render_token(left, filled)}
            expanded = _expand_common_prefix_str(prefix, candidates)
            if expanded != prefix:
                if token.startswith("/"):
                    filled = f"{remote_dir.rstrip('/')}/{expanded}"
                else:
                    filled = f"{token.rsplit('/', 1)[0]}/{expanded}" if "/" in token else expanded
                return {"action": "set_tail", "text": left + _ssh_tab_render_token(left, filled)}
            if not candidates:
                return {"action": "forward_tab"}
            return {"action": "list", "candidates": candidates}
        names = _ssh_list_dir_names_for_args(exe, port, target, cwd)
        common_bins = _ssh_list_command_pool_for_args(exe, port, target)
        pool = list(dict.fromkeys([*names, *common_bins]))
        candidates = [n for n in pool if n.lower().startswith(token.lower())]
        if len(candidates) == 1:
            return {"action": "set_tail", "text": left + _ssh_tab_render_token(left, candidates[0])}
        expanded = _expand_common_prefix_str(token, candidates)
        if expanded != token:
            return {"action": "set_tail", "text": left + _ssh_tab_render_token(left, expanded)}
        if not candidates:
            return {"action": "forward_tab"}
        return {"action": "list", "candidates": candidates}
    except Exception:
        return {"action": "forward_tab"}


def _win_taskkill_serial_tree(pid: int) -> None:
    if sys.platform != "win32" or not pid:
        return
    try:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            timeout=8,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,  # type: ignore[attr-defined]
        )
    except Exception:
        pass


def _win_kill_python_miniterm_for_com(port_name: str) -> None:
    """End any python process running pyserial miniterm for this COM port (orphans after kill)."""
    if sys.platform != "win32":
        return
    com = (port_name or "").strip().upper()
    if not re.match(r"^COM\d+$", com):
        return
    # Word-boundary match: '*COM3*' wrongly matched COM30/COM31 and could kill other serial tabs.
    ps = (
        f"$com = '{com}'; "
        "$pat = '\\b' + [regex]::Escape($com) + '\\b'; "
        "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | "
        "Where-Object { $_.CommandLine -and "
        "($_.CommandLine -like '*serial.tools.miniterm*' -or $_.CommandLine -like '*serial\\\\tools\\\\miniterm*') -and "
        "($_.CommandLine -match $pat) } | "
        "ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch {} }"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=45,
            creationflags=subprocess.CREATE_NO_WINDOW,  # type: ignore[attr-defined]
        )
    except Exception:
        pass


def _win_pnp_reset_com_port(port_name: str) -> bool:
    """Disable+enable the COM port device via PowerShell (same idea as Device Manager)."""
    if sys.platform != "win32":
        return False
    p = (port_name or "").strip().upper()
    m = re.match(r"^(COM\d+)$", p)
    if not m:
        return False
    com = m.group(1)
    ps = (
        f"$d = Get-PnpDevice -Class Ports -ErrorAction SilentlyContinue | "
        f"Where-Object {{ $_.FriendlyName -like '*({com})*' }} | Select-Object -First 1; "
        f"if (-not $d) {{ exit 2 }}; "
        f"Disable-PnpDevice -InstanceId $d.InstanceId -Confirm:$false; "
        f"Start-Sleep -Seconds 2; "
        f"Enable-PnpDevice -InstanceId $d.InstanceId -Confirm:$false"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW,  # type: ignore[attr-defined]
        )
        return r.returncode == 0
    except Exception:
        return False


def _ssh_build_ls_remote_cmd_static(remote_dir: str) -> str:
    """Remote `ls` via login shell so path expansion and quoting match adb/cmd-style host completion."""
    d = (remote_dir or ".").strip() or "."
    if d.startswith("~"):
        inner = f"ls -1a {d} 2>/dev/null"
    else:
        inner = f"ls -1a {shlex.quote(d)} 2>/dev/null"
    safe = inner.replace("'", "'\"'\"'")
    return f"sh -lc '{safe}'"


def _ssh_list_dir_names_for_args(exe: str, port: str, target: str, remote_dir: str) -> List[str]:
    if not exe or not target:
        return []
    port = str(normalize_tcp_port(port, 22))
    key = (exe, port, target, remote_dir)
    now = time.monotonic()
    hit = _ssh_tab_ls_cache.get(key)
    if hit is not None and (now - hit[0]) < _SSH_TAB_LS_TTL_SEC:
        return list(hit[1])
    inner = _ssh_build_ls_remote_cmd_static(remote_dir)
    cmd = [
        exe,
        "-T",
        "-n",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ConnectTimeout=3",
        "-o",
        "ConnectionAttempts=1",
        "-p",
        port,
        target,
        inner,
    ]
    kwargs = {"capture_output": True, "text": True, "timeout": 3}
    cf = _ssh_subprocess_run_flags()
    if cf:
        kwargs["creationflags"] = cf
    try:
        with _SSH_HELPER_SUBPROCESS_LOCK:
            r = subprocess.run(cmd, **kwargs)
    except Exception:
        return []
    if r.returncode != 0:
        return []
    out_names: List[str] = []
    for ln in (r.stdout or "").splitlines():
        n = ln.strip()
        if not n or n in (".", ".."):
            continue
        out_names.append(n)
    if len(_ssh_tab_ls_cache) > 48:
        _ssh_tab_ls_cache.clear()
    _ssh_tab_ls_cache[key] = (now, list(out_names))
    return out_names


def _ssh_list_command_pool_for_args(exe: str, port: str, target: str) -> List[str]:
    """One SSH round-trip: filenames from common bin dirs (incl. ``/ifs/bin``) plus ``$PATH``.

    Bounded with a short timeout so a stuck NFS mount cannot block helpers for long.
    """
    if not exe or not target:
        return []
    port = str(normalize_tcp_port(port, 22))
    ck = (exe, port, target)
    now = time.monotonic()
    hit = _ssh_tab_cmd_pool_cache.get(ck)
    if hit is not None and (now - hit[0]) < _SSH_TAB_CMD_POOL_TTL_SEC:
        return list(hit[1])
    inner = _ssh_remote_path_pool_script()
    safe = inner.replace("'", "'\"'\"'")
    remote = f"sh -lc '{safe}'"
    cmd = [
        exe,
        "-T",
        "-n",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ConnectTimeout=3",
        "-o",
        "ConnectionAttempts=1",
        "-p",
        port,
        target,
        remote,
    ]
    kwargs = {"capture_output": True, "text": True, "timeout": 5}
    cf = _ssh_subprocess_run_flags()
    if cf:
        kwargs["creationflags"] = cf
    out_names: List[str] = []
    try:
        with _SSH_HELPER_SUBPROCESS_LOCK:
            r = subprocess.run(cmd, **kwargs)
    except Exception:
        if len(_ssh_tab_cmd_pool_cache) > 24:
            _ssh_tab_cmd_pool_cache.clear()
        _ssh_tab_cmd_pool_cache[ck] = (now, [])
        return []
    if r.returncode != 0:
        if len(_ssh_tab_cmd_pool_cache) > 24:
            _ssh_tab_cmd_pool_cache.clear()
        _ssh_tab_cmd_pool_cache[ck] = (now, [])
        return []
    for ln in (r.stdout or "").splitlines():
        t = (ln or "").strip()
        if not t or t.startswith("__ADBNIK_H__:"):
            continue
        if t in (".", ".."):
            continue
        out_names.append(t)
    uniq: List[str] = []
    seen = set()
    for n in out_names:
        k = n.lower()
        if k not in seen:
            seen.add(k)
            uniq.append(n)
    if len(_ssh_tab_cmd_pool_cache) > 24:
        _ssh_tab_cmd_pool_cache.clear()
    _ssh_tab_cmd_pool_cache[ck] = (now, list(uniq))
    return uniq


def _adb_list_dir_names_for_args(adb_path: str, serial: str, remote_dir: str) -> List[str]:
    if not adb_path:
        return []
    d = (remote_dir or "/").replace('"', '\\"')
    args = ["shell", f'ls -1 -a "{d}" 2>/dev/null']
    if (serial or "").strip():
        args = ["-s", serial.strip(), *args]
    code, out, _err = run_adb(adb_path, args, timeout=6)
    if code != 0:
        return []
    out_names: List[str] = []
    for ln in out.splitlines():
        n = ln.strip()
        if not n or n in (".", ".."):
            continue
        out_names.append(n)
    return out_names


def _adb_render_completed_token(left: str, token: str) -> str:
    if " " not in token:
        return token
    cmd = (left or "").lstrip()
    if cmd.startswith("cd "):
        return f'"{token}"'
    return token.replace(" ", r"\ ")


def _adb_tab_complete_compute(
    adb_path: str,
    serial: str,
    cwd: str,
    want_path: bool,
    token: str,
    left: str,
) -> dict:
    """ADB Tab completion work (runs off the UI thread). Same contract as ``_ssh_tab_complete_compute``."""
    try:
        if want_path:
            if token.startswith("/"):
                remote_dir = token.rsplit("/", 1)[0] or "/"
                prefix = token.rsplit("/", 1)[1]
                base = remote_dir if remote_dir.startswith("/") else "/" + remote_dir
            else:
                rel_dir = token.rsplit("/", 1)[0] if "/" in token else ""
                prefix = token.rsplit("/", 1)[1] if "/" in token else token
                base = (cwd.rstrip("/") + "/" + rel_dir).replace("//", "/") if rel_dir else cwd
                remote_dir = base
            names = _adb_list_dir_names_for_args(adb_path, serial, remote_dir)
            prefix_l = prefix.lower()
            candidates = [n for n in names if n.lower().startswith(prefix_l)]
            if len(candidates) == 1:
                filled = f"{remote_dir.rstrip('/')}/{candidates[0]}" if token.startswith("/") else (
                    f"{token.rsplit('/', 1)[0]}/{candidates[0]}" if "/" in token else candidates[0]
                )
                if not filled.endswith("/"):
                    filled = filled + "/"
                return {"action": "set_tail", "text": left + _adb_render_completed_token(left, filled)}
            expanded = _expand_common_prefix_str(prefix, candidates)
            if expanded != prefix:
                if token.startswith("/"):
                    filled = f"{remote_dir.rstrip('/')}/{expanded}"
                else:
                    filled = f"{token.rsplit('/', 1)[0]}/{expanded}" if "/" in token else expanded
                return {"action": "set_tail", "text": left + _adb_render_completed_token(left, filled)}
            if not candidates:
                return {"action": "forward_tab"}
            return {"action": "list", "candidates": candidates}
        names = _adb_list_dir_names_for_args(adb_path, serial, cwd)
        common_bins: List[str] = []
        for d in ("/ifs/bin", "/system/bin", "/system/xbin"):
            common_bins.extend(_adb_list_dir_names_for_args(adb_path, serial, d))
        pool = list(dict.fromkeys([*names, *common_bins]))
        token_l = token.lower()
        candidates = [n for n in pool if n.lower().startswith(token_l)]
        if len(candidates) == 1:
            return {"action": "set_tail", "text": left + _adb_render_completed_token(left, candidates[0])}
        expanded = _expand_common_prefix_str(token, candidates)
        if expanded != token:
            return {"action": "set_tail", "text": left + _adb_render_completed_token(left, expanded)}
        if not candidates:
            return {"action": "forward_tab"}
        return {"action": "list", "candidates": candidates}
    except Exception:
        return {"action": "forward_tab"}


class ShellPlainTextEdit(QTextEdit):
    """Shell output + typing at the end (ANSI colors via HTML). Copy: Ctrl+Shift+C; interrupt: Ctrl+C / Ctrl+Z / Ctrl+X."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._anchor = 0
        self._on_commit_line: Optional[Callable[[str], None]] = None
        self._on_save_buffer: Optional[Callable[[], None]] = None
        self._on_tab_key: Optional[Callable[[bool], None]] = None  # bool = shift (Backtab)
        self._is_session_running_fn: Optional[Callable[[], bool]] = None
        self._skip_bridging_newline_fn: Optional[Callable[[], bool]] = None
        self._remote_pty_relaxed_bridging = False
        self._cmd_history: List[str] = []
        self._hist_browse_idx: Optional[int] = None
        self._hist_stash: str = ""
        self._preserve_typed_input = False
        self._font_pt = 11
        self._on_clear_buffer_fn: Optional[Callable[[], None]] = None
        self._send_control_bytes_fn: Optional[Callable[[bytes], None]] = None
        # ADB/SSH/serial: join accidental block/paragraph breaks so one logical line is sent (Wrap + QText block model).
        self._collapse_commit_whitespace = False
        # When True, LineWrapMode + WordWrapMode + document must stay NoWrap (font/zoom must not re-enable wrap).
        self._force_no_wrap = False
        self._stream_plain_fg = "#f8fafc"
        self._typing_fg: Optional[str] = None
        self.setCursorWidth(2)
        self.setUndoRedoEnabled(False)
        self.setAcceptRichText(True)
        # Wrap at pane width — prefer word boundaries when possible (less “broken mid-token” wrap than WrapAnywhere).
        self.setLineWrapMode(QTextEdit.WidgetWidth)
        self.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.setTabChangesFocus(False)
        try:
            self.document().setMaximumBlockCount(60000)
        except Exception:
            pass

    def set_on_commit(self, fn: Callable[[str], None]) -> None:
        self._on_commit_line = fn

    def set_on_save_buffer(self, fn: Callable[[], None]) -> None:
        self._on_save_buffer = fn

    def set_on_tab_key(self, fn: Optional[Callable[[bool], None]]) -> None:
        """If set, Tab / Shift+Tab are sent to the shell (completion) instead of changing Qt focus."""
        self._on_tab_key = fn

    def set_session_running(self, fn: Optional[Callable[[], bool]]) -> None:
        """When set and returns False, block typing at the prompt (session ended)."""
        self._is_session_running_fn = fn

    def set_skip_bridging_newline(self, fn: Optional[Callable[[], bool]]) -> None:
        """When True, do not insert a synthetic newline after sending a line (SSH/serial echo their own)."""
        self._skip_bridging_newline_fn = fn

    def set_remote_pty_relaxed_bridging(self, enabled: bool) -> None:
        """ADB/SSH: do not treat trailing space after $/# as 'at prompt' — avoids gluing output to the prompt line."""
        self._remote_pty_relaxed_bridging = bool(enabled)

    def set_collapse_commit_whitespace(self, enabled: bool) -> None:
        """When True, a committed line collapses internal whitespace/newlines to single spaces (remote PTY/serial)."""
        self._collapse_commit_whitespace = bool(enabled)

    def set_force_no_wrap(self, enabled: bool) -> None:
        """Optional horizontal-only layout; default remains wrap-at-widget-width for readability."""
        self._force_no_wrap = bool(enabled)
        if self._force_no_wrap:
            self._apply_force_no_wrap()
        else:
            self.setLineWrapMode(QTextEdit.WidgetWidth)
            self.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
            opt = QTextOption(self.document().defaultTextOption())
            opt.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
            self.document().setDefaultTextOption(opt)
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    def _apply_force_no_wrap(self) -> None:
        self.setLineWrapMode(QTextEdit.NoWrap)
        self.setWordWrapMode(QTextOption.NoWrap)
        opt = QTextOption(self.document().defaultTextOption())
        opt.setWrapMode(QTextOption.NoWrap)
        self.document().setDefaultTextOption(opt)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    def set_on_clear_buffer(self, fn: Optional[Callable[[], None]]) -> None:
        """Called after the user clears the terminal (reset scrollback / tail caches in SessionWidget)."""
        self._on_clear_buffer_fn = fn

    def set_send_control_bytes(self, fn: Optional[Callable[[bytes], None]]) -> None:
        """Send raw bytes to the shell (Ctrl+C / Ctrl+Z / Ctrl+X interrupt / job control)."""
        self._send_control_bytes_fn = fn

    def _try_send_shell_control(self, byte_val: int) -> bool:
        if self._send_control_bytes_fn is None:
            return False
        if self._is_session_running_fn is not None and not self._is_session_running_fn():
            return False
        try:
            self._send_control_bytes_fn(bytes([byte_val & 0xFF]))
        except Exception:
            return False
        return True

    def set_preserve_typed_input(self, enabled: bool) -> None:
        self._preserve_typed_input = bool(enabled)

    def set_stream_plain_foreground(self, hex_color: str) -> None:
        """Plain PTY stream ``append_stream_plain`` / completion tint (command output vs shell chrome)."""
        self._stream_plain_fg = (hex_color or "#f8fafc").strip() or "#f8fafc"

    def set_typing_foreground(self, hex_color: str) -> None:
        """Characters typed at the prompt — distinct from streamed output."""
        t = (hex_color or "").strip()
        self._typing_fg = t or None

    def insertFromMimeData(self, source) -> None:
        if self._typing_fg and self.textCursor().position() >= self._anchor:
            cfmt = QTextCharFormat()
            cfmt.setForeground(QBrush(QColor(self._typing_fg)))
            self.mergeCurrentCharFormat(cfmt)
        super().insertFromMimeData(source)

    def set_terminal_font_size(self, pt: int) -> None:
        self._font_pt = max(8, min(24, int(pt)))
        f = QFont(self.font())
        f.setPointSize(self._font_pt)
        self.setFont(f)
        doc = self.document()
        doc.setDefaultFont(f)
        cur = QTextCursor(doc)
        cur.beginEditBlock()
        cur.select(QTextCursor.Document)
        ch = QTextCharFormat()
        ch.setFontPointSize(self._font_pt)
        cur.mergeCharFormat(ch)
        cur.endEditBlock()
        if getattr(self, "_force_no_wrap", False):
            self._apply_force_no_wrap()

    def adjust_terminal_font_size(self, delta: int) -> None:
        self.set_terminal_font_size(self._font_pt + int(delta))

    def set_initial_content(self, text: str) -> None:
        self.setPlainText(text)
        cur = self.textCursor()
        cur.movePosition(QTextCursor.End)
        self.setTextCursor(cur)
        self._anchor = cur.position()
        self._reset_history_browse()

    def append_from_process_html(self, html: str, ensure_visible: bool = True) -> None:
        if not html:
            return
        fs = self._font_pt
        wrapped = (
            f'<span style="white-space:pre-wrap;font-family:Consolas,\'Courier New\',monospace;'
            f'font-size:{fs}pt">{html}</span>'
        )
        user_cur = QTextCursor(self.textCursor())
        ins = QTextCursor(self.document())
        ins.movePosition(QTextCursor.End)
        insert_at = ins.position()
        ins.insertHtml(wrapped)
        self._anchor = ins.position()
        self._reset_history_browse()

        if user_cur.hasSelection():
            self.setTextCursor(user_cur)
        elif user_cur.position() == insert_at:
            follow = QTextCursor(self.document())
            follow.movePosition(QTextCursor.End)
            self.setTextCursor(follow)
        else:
            self.setTextCursor(user_cur)

        if ensure_visible:
            tb = self.textCursor()
            if not tb.hasSelection() and tb.position() >= self._document_end_position() - 1:
                self.ensureCursorVisible()

    def append_plain_fragment(self, text: str) -> None:
        """Insert plain text (escaped) with default terminal foreground — for completion rows, prompts, etc."""
        if not text:
            return
        from html import escape as _html_escape

        h = _html_escape(text).replace("\n", "<br/>")
        frag = f'<span style="color:{self._stream_plain_fg}">{h}</span>'
        user_cur = QTextCursor(self.textCursor())
        ins = QTextCursor(self.document())
        ins.movePosition(QTextCursor.End)
        insert_at = ins.position()
        ins.insertHtml(frag)
        self._anchor = ins.position()
        self._reset_history_browse()

        if user_cur.hasSelection():
            self.setTextCursor(user_cur)
        elif user_cur.position() == insert_at:
            follow = QTextCursor(self.document())
            follow.movePosition(QTextCursor.End)
            self.setTextCursor(follow)
        else:
            self.setTextCursor(user_cur)

        tb = self.textCursor()
        if not tb.hasSelection() and tb.position() >= self._document_end_position() - 1:
            self.ensureCursorVisible()

    def append_stream_plain(self, text: str, *, ensure_visible: bool = True) -> None:
        """Fast path for high-volume PTY output — insertText, not insertHtml (Moba-style responsiveness)."""
        if not text:
            return
        user_cur = QTextCursor(self.textCursor())
        ins = QTextCursor(self.document())
        ins.movePosition(QTextCursor.End)
        insert_at = ins.position()
        fmt = QTextCharFormat()
        fmt.setForeground(QBrush(QColor(self._stream_plain_fg)))
        ins.setCharFormat(fmt)
        ins.insertText(text)
        self._anchor = ins.position()
        self._reset_history_browse()

        if user_cur.hasSelection():
            self.setTextCursor(user_cur)
        elif user_cur.position() == insert_at:
            follow = QTextCursor(self.document())
            follow.movePosition(QTextCursor.End)
            self.setTextCursor(follow)
        else:
            self.setTextCursor(user_cur)

        if ensure_visible:
            tb = self.textCursor()
            if not tb.hasSelection() and tb.position() >= self._document_end_position() - 1:
                self.ensureCursorVisible()

    def sync_input_anchor_to_end(self) -> None:
        """Place the input cursor and anchor at the document end (e.g. after menu-injected SSH commands)."""
        cur = self.textCursor()
        cur.movePosition(QTextCursor.End)
        self.setTextCursor(cur)
        self._anchor = cur.position()
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

    def _plain_text_range(self, start: int, end: int) -> str:
        """Slice [start,end) via QTextCursor — do not cap ``end`` to ``n-1`` or the last character is lost."""
        doc = self.document()
        nc = doc.characterCount()
        if nc <= 0:
            return ""
        start = max(0, min(int(start), nc - 1))
        end = max(int(start), int(end))
        cur = self.textCursor()
        cur.setPosition(start)
        cur.setPosition(end, QTextCursor.KeepAnchor)
        return cur.selectedText().replace("\u2029", "\n")

    def _document_end_position(self) -> int:
        c = QTextCursor(self.document())
        c.movePosition(QTextCursor.End)
        return c.position()

    def current_input_tail(self) -> str:
        """Full logical input after ``_anchor`` (same as anchor→document end; blocks joined as \\u2029 in Qt)."""
        doc = self.document()
        if doc.characterCount() <= 0 or self._anchor > self._document_end_position():
            return ""
        cur = self.textCursor()
        cur.setPosition(self._anchor)
        cur.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        return cur.selectedText().replace("\u2029", "\n")

    def set_input_tail(self, text: str) -> None:
        self._replace_input_tail(text)

    def _history_prev(self) -> None:
        if not self._cmd_history:
            return
        tail = self.current_input_tail()
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
        for a in menu.actions():
            t = (a.text() or "").replace("&", "").strip().lower()
            if t == "copy":
                a.setText("Copy selection (Ctrl+Shift+C)")
            elif t == "paste":
                a.setText("Paste (Ctrl+Shift+V at prompt)")
        tip = QAction("Interrupt: Ctrl+C  ·  Suspend: Ctrl+Z  ·  Extra: Ctrl+X", self)
        tip.setEnabled(False)
        if menu.actions():
            first = menu.actions()[0]
            menu.insertAction(first, tip)
            menu.insertSeparator(first)
        else:
            menu.addAction(tip)
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
        if self._on_clear_buffer_fn is not None:
            self._on_clear_buffer_fn()

    def keyPressEvent(self, ev):
        cur = self.textCursor()
        pos = cur.position()
        k = ev.key()
        mods = ev.modifiers()
        alive = self._is_session_running_fn is None or self._is_session_running_fn()

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
            if k in (Qt.Key_Equal, Qt.Key_Plus):
                self.adjust_terminal_font_size(+1)
                ev.accept()
                return
            if k == Qt.Key_Minus:
                self.adjust_terminal_font_size(-1)
                ev.accept()
                return
            if k == Qt.Key_0:
                self.set_terminal_font_size(11)
                ev.accept()
                return
            if k == Qt.Key_C:
                if cur.hasSelection():
                    self.copy()
                    ev.accept()
                    return
                if self._try_send_shell_control(0x03):
                    ev.accept()
                    return
            if k == Qt.Key_Z:
                if self._try_send_shell_control(0x1A):
                    ev.accept()
                    return
            if k == Qt.Key_X:
                if cur.hasSelection():
                    self.copy()
                    ev.accept()
                    return
                if self._try_send_shell_control(0x18):
                    ev.accept()
                    return
            if k == Qt.Key_V:
                self.moveCursor(QTextCursor.End)
                self.paste()
                ev.accept()
                return

        if self._on_tab_key:
            if k == Qt.Key_Tab and not (mods & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)):
                self._on_tab_key(False)
                ev.accept()
                return
            if k == Qt.Key_Backtab and not (mods & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)):
                self._on_tab_key(True)
                ev.accept()
                return

        if not alive:
            if mods & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier):
                return super().keyPressEvent(ev)
            nav_ok = k in (
                Qt.Key_Left,
                Qt.Key_Right,
                Qt.Key_Up,
                Qt.Key_Down,
                Qt.Key_Home,
                Qt.Key_End,
                Qt.Key_PageUp,
                Qt.Key_PageDown,
            )
            if nav_ok:
                return super().keyPressEvent(ev)
            if k in (Qt.Key_Return, Qt.Key_Enter):
                ev.accept()
                return
            if ev.text() and k not in (Qt.Key_Backspace, Qt.Key_Delete, Qt.Key_Tab, Qt.Key_Backtab):
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
            if k == Qt.Key_A:
                return super().keyPressEvent(ev)
            if k == Qt.Key_V and pos < self._anchor:
                self.moveCursor(QTextCursor.End)
            return super().keyPressEvent(ev)

        if k in (Qt.Key_Return, Qt.Key_Enter):
            # Never insert a paragraph inside the prompt (Shift+Enter used to add a second block and break commits).
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

        if (
            self._typing_fg
            and alive
            and pos >= self._anchor
            and ev.text()
            and not (mods & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))
            and k
            not in (
                Qt.Key_Backspace,
                Qt.Key_Delete,
                Qt.Key_Tab,
                Qt.Key_Backtab,
                Qt.Key_Return,
                Qt.Key_Enter,
            )
        ):
            cfmt = QTextCharFormat()
            cfmt.setForeground(QBrush(QColor(self._typing_fg)))
            self.mergeCurrentCharFormat(cfmt)

        # One logical input line: typing and backspace only at the document end of the tail (copy/select anywhere).
        if alive and self._anchor >= 0:
            endp = self._document_end_position()
            if k == Qt.Key_Backspace and pos > self._anchor:
                if pos != endp:
                    self.moveCursor(QTextCursor.End)
            elif k == Qt.Key_Delete and pos >= self._anchor and pos < endp:
                self.moveCursor(QTextCursor.End)
            elif (
                ev.text()
                and not (mods & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))
                and k not in (Qt.Key_Tab, Qt.Key_Backtab)
                and pos >= self._anchor
            ):
                if pos != endp or cur.hasSelection():
                    self.moveCursor(QTextCursor.End)

        super().keyPressEvent(ev)

    def wheelEvent(self, ev):
        if ev.modifiers() & Qt.ControlModifier:
            if ev.angleDelta().y() > 0:
                self.adjust_terminal_font_size(+1)
            elif ev.angleDelta().y() < 0:
                self.adjust_terminal_font_size(-1)
            ev.accept()
            return
        super().wheelEvent(ev)

    def _commit_current_line(self) -> None:
        if self._is_session_running_fn is not None and not self._is_session_running_fn():
            return
        cur = self.textCursor()
        # Always commit/remove the full input tail (anchor→doc end). Cursor-in-the-middle + QTextEdit wrap
        # used to truncate or split what was sent vs what was deleted.
        cur.setPosition(self._anchor)
        cur.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        raw = cur.selectedText().replace("\u2029", "\n")
        if self._collapse_commit_whitespace:
            line = " ".join(raw.split())
        elif "\n" in raw:
            line = raw.split("\n", 1)[0]
        else:
            line = raw
        if line.strip():
            if not self._cmd_history or self._cmd_history[-1] != line:
                self._cmd_history.append(line)
        self._reset_history_browse()
        cur = self.textCursor()
        if not self._preserve_typed_input:
            # Remove what we typed before sending: an interactive shell echoes the line from the PTY, so
            # keeping it here duplicates "ls" / blank lines and can interleave with async stdout if we send first.
            cur.setPosition(self._anchor)
            cur.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
            cur.removeSelectedText()
            pos = self.textCursor().position()
            # If the shell did not end the previous line with a newline, insert one so the next prompt/output
            # does not glue to the prior line. Do NOT insert when typing on the same line as a prompt:
            # Windows `>`, Android/adb ` $` / `#`, or trailing space after those.
            if pos > 0:
                c2 = self.textCursor()
                c2.setPosition(pos - 1)
                c2.setPosition(pos, QTextCursor.KeepAnchor)
                prev_chunk = c2.selectedText().replace("\u2029", "\n")
                prev = prev_chunk[0] if prev_chunk else "\n"
                at_prompt = (prev in " \t" or prev in ">$#]") and not self._remote_pty_relaxed_bridging
                skip_nl = bool(self._skip_bridging_newline_fn and self._skip_bridging_newline_fn())
                if prev != "\n" and not at_prompt and not skip_nl:
                    cur.insertText("\n")
                    pos += 1
        else:
            cur.movePosition(QTextCursor.End)
            cur.insertText("\n")
            pos = cur.position()
        self._anchor = pos
        self.setTextCursor(cur)
        if self._on_commit_line:
            self._on_commit_line(line)


class SessionWidget(QWidget):
    """Single terminal session: scrollback + type-at-end shell (Moba-like dark theme)."""

    # Thread-safe delivery of Tab-completion results from worker threads (avoid QTimer from non-Qt threads).
    _tab_async_complete = pyqtSignal(str, int, object)

    def __init__(
        self,
        session_label: str,
        command: List[str],
        banner: Optional[str] = None,
        *,
        working_dir: Optional[str] = None,
        shell_profile: Optional[str] = None,
        path_extra_dirs: Optional[Sequence[str]] = None,
        auto_reconnect: bool = False,
    ):
        super().__init__()
        self.session_label = session_label
        self.command = command
        self._banner = (banner or "").strip() or None
        self._trim_first_pty_chunk = bool(self._banner)
        self._shell_profile = shell_profile if shell_profile in ("cmd", "powershell") else None
        self._path_extra_dirs = [
            str(Path(d).resolve())
            for d in (path_extra_dirs or [])
            if d and str(d).strip() and Path(d).is_dir()
        ]
        try:
            base = Path(working_dir or os.getcwd()).resolve()
        except OSError:
            base = Path.cwd()
        self._working_dir_str = str(base)
        self._cwd: Path = base
        self.proc = QProcess(self)
        self._stdout_pending = bytearray()
        self._stderr_pending = bytearray()
        self._stdout_drain_scheduled = False
        self._stderr_drain_scheduled = False
        self._log_fp = None
        self._log_pending_chunks: List[str] = []
        self._tail_cache = ""
        self._path_command_cache: List[str] = []
        self._path_command_cache_key: str = ""
        self._python_repl_mode = False
        self._log_path = self._build_log_path()
        self._ansi = AnsiToHtmlConverter(
            ignore_background=True,
            lift_black_foreground=True,
            prompt_highlight=True,
            prompt_palette=get_prompt_palette(self._session_prompt_palette_name()),
            reset_fg_each_physical_line=(
                self._is_ssh_session
                or self._is_adb_shell
                or self._shell_profile in ("cmd", "powershell")
            ),
        )
        self._welcome_is_reconnect = False
        self._scroll_output_on_newline_only = True
        self._stream_chunk = 65536
        # Serial: auto-retry when the COM port is still held by a dead miniterm (max 2 restarts).
        self._serial_auto_retries_used = 0
        self._serial_retry_scheduled = False
        self._serial_start_monotonic = 0.0
        self._ssh_complete_seq = 0
        self._adb_complete_seq = 0
        self._remote_ui_tick = 0
        self._flush_paused = False
        self._auto_reconnect_enabled = bool(auto_reconnect)
        self._auto_reconnect_attempts = 0
        self._auto_reconnect_max = 4
        self._manual_shutdown = False
        self._tab_async_complete.connect(self._on_tab_async_complete)
        self._build_ui()
        self._start()

    @property
    def _is_adb_shell(self) -> bool:
        if not self.command:
            return False
        low = [str(x).lower() for x in self.command]
        return "shell" in low and "adb" in str(self.command[0]).lower()

    @property
    def _is_ssh_session(self) -> bool:
        if not self.command:
            return False
        exe = os.path.basename(str(self.command[0])).lower()
        return exe in ("ssh", "ssh.exe")

    @property
    def _is_remote_pty_shell(self) -> bool:
        """Interactive ADB shell or SSH — same completion, drain, merge, and UI-throttle behavior."""
        return self._is_ssh_session or self._is_adb_shell

    @property
    def _is_serial_session(self) -> bool:
        return "serial.tools.miniterm" in " ".join(str(x) for x in self.command).lower()

    def session_bookmark_fingerprint(self) -> str:
        """If this session matches a sidebar bookmark, return the same key as bookmark_entry_fingerprint."""
        if self._is_adb_shell:
            s = self._adb_shell_serial()
            return f"adb:{s}" if s else ""
        if self._is_ssh_session:
            _exe, port, target = self._ssh_parse_connection()
            return f"ssh:{target}:{port}" if target else ""
        if self._is_serial_session:
            com = self._serial_com_port_from_command()
            return f"serial:{com.upper()}" if com else ""
        if self._shell_profile == "cmd":
            return "local_cmd"
        if self._shell_profile == "powershell":
            return "local_pwsh"
        return ""

    def _session_kind_label(self) -> str:
        if self._is_serial_session:
            return "Serial console"
        if self._is_ssh_session:
            return "SSH"
        if self._is_adb_shell:
            return "ADB shell"
        if self._shell_profile == "powershell":
            return "PowerShell"
        if self._shell_profile == "cmd":
            return "Windows Command Prompt"
        return "Local terminal"

    def _session_prompt_palette_name(self) -> str:
        if self._is_ssh_session:
            return "ssh"
        if self._is_adb_shell:
            return "adb"
        if self._is_serial_session:
            return "serial"
        if self._shell_profile == "powershell":
            return "powershell"
        if self._shell_profile == "cmd":
            return "cmd"
        return "local"

    def _apply_terminal_edit_palette(self) -> None:
        """Streamed plain output vs user typing: match ANSI palette (all session kinds)."""
        try:
            pal = self._ansi._prompt_palette
            self.output.set_stream_plain_foreground(pal.line_output)
            self.output.set_typing_foreground(pal.typed_input)
        except Exception:
            pass

    def _welcome_banner_parts(self) -> Tuple[str, str]:
        dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        kind = self._session_kind_label()
        tag = "Reconnected" if self._welcome_is_reconnect else "Session started"
        extra = ""
        if (self._banner or "").strip():
            extra = self._banner.strip().replace("\n", " ")
            if len(extra) > 220:
                extra = extra[:217] + "…"
        sep_plain = "=" * 72
        lines_plain = ["Welcome to adbnik", f"{kind} · {tag}", dt]
        if extra:
            lines_plain.append(extra)
        plain = "\n".join(lines_plain) + "\n" + sep_plain + "\n\n"
        fz = "16px"
        fz_meta = "14px"
        h = (
            f'<div style="color:#8b949e;font-size:{fz_meta};line-height:1.55;margin:0;padding:0 0 10px 0;'
            'width:100%;box-sizing:border-box">'
            f'<span style="color:#58a6ff;font-weight:700;font-size:{fz}">Welcome to adbnik</span><br/>'
            f'<span style="color:#7ee787;font-size:{fz_meta}">{html_escape(kind)}</span>'
            f'<span style="color:#6e7681"> · </span>'
            f'<span style="color:#a371f7;font-size:{fz_meta}">{html_escape(tag)}</span><br/>'
            f'<span style="color:#6e7681;font-size:{fz_meta}">{html_escape(dt)}</span>'
        )
        if extra:
            h += f'<br/><span style="color:#8b949e;font-size:{fz_meta}">{html_escape(extra)}</span>'
        h += (
            '</div>'
            '<div style="width:100%;max-width:100%;box-sizing:border-box;margin:8px 0 14px 0;padding:0;'
            'height:0;border:none;border-top:3px solid #484f58">&nbsp;</div>'
        )
        return h, plain

    def _emit_session_welcome(self) -> None:
        html, plain = self._welcome_banner_parts()
        self._append_output_html(html, force_scroll=True)
        self._write_log(plain)
        self._tail_cache = (self._tail_cache + plain)[-32768:]

    def _pending_flush_backlog(self) -> int:
        return sum(len(x) for x in self._pending_chunks)

    def _flush_interval_ms(self) -> int:
        if self._is_serial_session:
            return 10
        if self._is_remote_pty_shell:
            n = self._pending_flush_backlog()
            if n > 1_200_000:
                return 80
            if n > 600_000:
                return 50
            if n > 200_000:
                return 32
            return 20
        return 20

    def _arm_flush_timer(self) -> None:
        if self._flush_paused:
            return
        self._flush_timer.setInterval(self._flush_interval_ms())
        if not self._flush_timer.isActive():
            self._flush_timer.start()

    def set_flush_paused(self, paused: bool) -> None:
        """When this session tab is not selected, stop burning CPU flushing scrollback (other tabs stay responsive)."""
        self._flush_paused = bool(paused)
        if self._flush_paused:
            self._flush_timer.stop()
        elif self._pending_chunks:
            self._arm_flush_timer()

    @staticmethod
    def _serial_recoverable_open_error(text: str) -> bool:
        """Errors where retry + optional COM PnP reset may help (busy port, permission, stale handle)."""
        tl = (text or "").lower()
        if not tl.strip():
            return False
        needles = (
            "permissionerror",
            "permission denied",
            "operation not permitted",
            "access is denied",
            "access denied",
            "could not open port",
            "could not open",
            "serial.serialutil.serialexception",
            "being used by another process",
            "errno 13",
            "errno 16",
            "failed to open port",
            "could not exclusively lock",
            "winerror 5",
            "winerror 32",
            "unable to open",
            "port is busy",
            "device is being used",
            "cannot configure port",
            "insufficient permissions",
        )
        return any(n in tl for n in needles)

    def _serial_com_port_from_command(self) -> str:
        parts = [str(x) for x in (self.command or [])]
        joined = " ".join(parts).lower()
        if "miniterm" not in joined:
            return ""
        for p in parts:
            if re.match(r"(?i)^COM\d+$", (p or "").strip()):
                return p.strip()
        return ""

    def _serial_force_kill_and_release(self) -> None:
        """Kill miniterm; COM cleanup runs on a worker thread (bounded ``waitForFinished`` on the GUI thread)."""
        if not self._is_serial_session:
            return
        com = self._serial_com_port_from_command()
        serial_pid: Optional[int] = None
        st = self.proc.state()
        if st == QProcess.Running:
            try:
                serial_pid = int(self.proc.processId())
            except Exception:
                serial_pid = None
        still_running = False
        if st in (QProcess.Running, QProcess.Starting):
            self.proc.kill()
            still_running = not self.proc.waitForFinished(4000)
        worker = _SerialPortReleaseThread(com, serial_pid, still_running, self)
        worker.start()
        worker.wait(25000)
        worker.deleteLater()

    def _serial_force_kill_and_release_async(self, on_released: Callable[[], None]) -> None:
        """Restart path: avoid long ``waitForFinished`` / sleeps on the GUI thread; ``on_released`` runs after COM cleanup."""
        if not self._is_serial_session:
            QTimer.singleShot(0, on_released)
            return
        com = self._serial_com_port_from_command()
        done = {"ok": False}

        def finish(timer: Optional[QTimer], still_running: bool) -> None:
            if done["ok"]:
                return
            done["ok"] = True
            if timer is not None:
                try:
                    timer.stop()
                except Exception:
                    pass
            try:
                self.proc.finished.disconnect(on_proc_finished)
            except Exception:
                pass
            serial_pid: Optional[int] = None
            try:
                if self.proc.state() == QProcess.Running:
                    serial_pid = int(self.proc.processId())
            except Exception:
                serial_pid = None
            worker = _SerialPortReleaseThread(com, serial_pid, still_running, self)

            def _after() -> None:
                if worker.isRunning():
                    worker.wait(30000)
                worker.deleteLater()
                on_released()

            worker.finished_ok.connect(_after)
            worker.start()

        st = self.proc.state()
        if st == QProcess.NotRunning:
            finish(None, False)
            return

        timer = QTimer(self)
        timer.setSingleShot(True)

        def on_proc_finished() -> None:
            finish(timer, False)

        timer.timeout.connect(lambda: finish(timer, True))
        self.proc.finished.connect(on_proc_finished)
        self.proc.kill()
        timer.start(4000)

    def _serial_maybe_retry_on_text(self, raw: str) -> None:
        """If miniterm reports the COM port is busy, tear down and reopen (limited retries)."""
        if not self._is_serial_session or self._serial_retry_scheduled:
            return
        if self._serial_auto_retries_used >= 2:
            return
        if time.monotonic() - self._serial_start_monotonic > 120.0:
            return
        if not self._serial_recoverable_open_error(raw):
            return
        self._schedule_serial_restart()

    def _schedule_serial_restart(self) -> None:
        if not self._is_serial_session or self._serial_retry_scheduled:
            return
        if self._serial_auto_retries_used >= 2:
            return
        self._serial_retry_scheduled = True
        QTimer.singleShot(120, self._restart_serial_session_impl)

    def _restart_serial_session_impl(self) -> None:
        """Kill the current serial-console process (and tree on Windows) and start the same command again."""
        self._serial_retry_scheduled = False
        if not self._is_serial_session:
            return
        if self._serial_auto_retries_used >= 2:
            self._append_plain_ui("\n[serial] Port still busy after 2 retries.\n")
            return
        self._serial_auto_retries_used += 1
        self._append_plain_ui(f"\n[serial] Retrying ({self._serial_auto_retries_used}/2)…\n")
        self._disconnect_proc_signals()
        self._stdout_pending.clear()
        self._stderr_pending.clear()
        self._pending_chunks.clear()
        self._flush_timer.stop()
        self._stdout_drain_scheduled = False
        self._stderr_drain_scheduled = False

        # Kill + COM release off the GUI thread where possible; then reconnect and reopen miniterm.
        self._serial_force_kill_and_release_async(self._restart_serial_session_after_release)

    def _restart_serial_session_after_release(self) -> None:
        self._ansi.reset()
        self._trim_first_pty_chunk = bool(self._banner)
        self._welcome_is_reconnect = True
        self._connect_proc_signals()
        self._serial_start_monotonic = time.monotonic()
        self.proc.start(self.command[0], self.command[1:])
        self._update_session_footer()

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
        self.output.set_terminal_font_size(11)
        # Block limit is set on QTextDocument inside ShellPlainTextEdit (QTextEdit has no setMaximumBlockCount).
        self.output.set_on_commit(self._send_line)
        self.output.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.output.set_on_save_buffer(self._save_buffer_as)
        self.output.set_on_tab_key(self._send_tab_to_shell)
        self.output.set_session_running(lambda: self.proc.state() == QProcess.Running)
        # Remote shells echo line endings; a synthetic newline after send duplicates prompts and blanks (SSH/ADB/serial).
        self.output.set_skip_bridging_newline(lambda: self._is_serial_session or self._is_remote_pty_shell)
        self.output.set_remote_pty_relaxed_bridging(False)
        self.output.set_collapse_commit_whitespace(self._is_serial_session or self._is_remote_pty_shell)
        self.output.set_on_clear_buffer(self._on_terminal_cleared)
        self.output.set_send_control_bytes(self._write_raw_to_shell)
        # UART often does not echo locally; keep typed text visible until device echoes it back.
        if self._is_serial_session:
            self.output.set_preserve_typed_input(True)
        # Reliable font zoom shortcuts on terminal widget.
        self._zoom_in_sc = QShortcut(QKeySequence.ZoomIn, self.output)
        self._zoom_out_sc = QShortcut(QKeySequence.ZoomOut, self.output)
        self._zoom_in_sc_alt = QShortcut(QKeySequence("Ctrl+="), self.output)
        self._zoom_out_sc_alt = QShortcut(QKeySequence("Ctrl+-"), self.output)
        self._zoom_reset_sc = QShortcut(QKeySequence("Ctrl+0"), self.output)
        self._zoom_in_sc.activated.connect(lambda: self.output.adjust_terminal_font_size(+1))
        self._zoom_out_sc.activated.connect(lambda: self.output.adjust_terminal_font_size(-1))
        self._zoom_in_sc_alt.activated.connect(lambda: self.output.adjust_terminal_font_size(+1))
        self._zoom_out_sc_alt.activated.connect(lambda: self.output.adjust_terminal_font_size(-1))
        self._zoom_reset_sc.activated.connect(lambda: self.output.set_terminal_font_size(10))
        self._apply_terminal_edit_palette()
        layout.addWidget(self.output, 1)
        if self._is_remote_pty_shell:
            try:
                self.output.document().setMaximumBlockCount(6000)
            except Exception:
                pass
        self._session_footer = QLabel()
        self._session_footer.setObjectName("TerminalSessionFooter")
        self._session_footer.setFont(QFont("Consolas", 11))
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
        # SSH: coalesce UI updates (~1 frame); smaller intervals burn CPU and can starve other threads.
        if self._is_serial_session:
            self._flush_timer.setInterval(12)
            self._stream_chunk = 131072
        elif self._is_remote_pty_shell:
            self._flush_timer.setInterval(32)
            self._stream_chunk = 65536
        else:
            self._flush_timer.setInterval(20)
        self._flush_timer.timeout.connect(self._flush_pending_output)
        self._log_flush_timer = QTimer(self)
        self._log_flush_timer.setSingleShot(True)
        self._log_flush_timer.setInterval(180)
        self._log_flush_timer.timeout.connect(self._flush_log_buffer)

        self._connect_proc_signals()

    def _connect_proc_signals(self) -> None:
        self.proc.readyReadStandardOutput.connect(self._read_stdout)
        self.proc.readyReadStandardError.connect(self._read_stderr)
        self.proc.started.connect(self._on_proc_started)
        self.proc.finished.connect(self._on_proc_finished)
        self.proc.errorOccurred.connect(self._on_proc_error)

    def _disconnect_proc_signals(self) -> None:
        for sig in (
            self.proc.readyReadStandardOutput,
            self.proc.readyReadStandardError,
            self.proc.started,
            self.proc.finished,
            self.proc.errorOccurred,
        ):
            try:
                sig.disconnect()
            except Exception:
                pass

    def _send_tab_to_shell(self, shift: bool) -> None:
        """Forward Tab to the child process so CMD/PowerShell/adb shell can complete paths/commands."""
        if self.proc.state() != QProcess.Running:
            return
        if self._is_adb_shell and not shift:
            if self._adb_complete_from_host():
                return
        if self._is_ssh_session and not shift:
            if self._ssh_complete_from_host():
                return
        if self._shell_profile in ("cmd", "powershell") and not shift:
            if self._local_complete_from_host():
                return
            self._beep_completion_miss()
            return
        if shift:
            if self._shell_profile in ("cmd", "powershell"):
                self.proc.write(b"\t")
            else:
                self.proc.write(b"\x1b[Z")
        else:
            self.proc.write(b"\t")

    def _adb_shell_serial(self) -> str:
        parts = [str(x) for x in self.command]
        for i, p in enumerate(parts[:-1]):
            if p == "-s":
                return parts[i + 1].strip()
        return ""

    def _adb_shell_cwd(self) -> str:
        last = self._last_nonempty_line().strip()
        m = re.search(r":(/[^ ]*)\s*[$#]\s*$", last)
        return m.group(1) if m else "/"

    def _adb_list_dir_names(self, remote_dir: str) -> List[str]:
        adb = self.command[0] if self.command else ""
        return _adb_list_dir_names_for_args(adb, self._adb_shell_serial(), remote_dir)

    @staticmethod
    def _expand_common_prefix(token: str, candidates: Sequence[str]) -> str:
        return _expand_common_prefix_str(token, candidates)

    def _beep_completion_miss(self) -> None:
        # Moba-like feedback: when Tab cannot complete further, emit a local bell.
        QApplication.beep()

    def _show_completion_lines(self, candidates: Sequence[str]) -> None:
        opts = sorted(dict.fromkeys(candidates), key=lambda s: s.lower())
        if not opts:
            return
        # Moba-like: show candidates on next line(s), then continue current input line.
        line = "  ".join(opts[:48])
        more = "" if len(opts) <= 48 else f"  ...(+{len(opts) - 48})"
        tail = self.output.current_input_tail()
        prompt = ""
        last = self._last_nonempty_line()
        m = re.search(r"^((?:\d+\|)?[^\n]*?[>$#]\s*)$", last)
        if m:
            prompt = m.group(1)
        self._append_plain_ui(f"\n{line}{more}\n{prompt}")
        self.output.set_input_tail(tail)

    @staticmethod
    def _adb_escape_word(text: str) -> str:
        return text.replace(" ", r"\ ")

    def _adb_complete_from_host(self) -> bool:
        tail = self.output.current_input_tail()
        if not tail:
            return False
        m = re.search(r"^(.*?)([^\s]*)$", tail, re.DOTALL)
        if not m:
            return False
        left, token = m.group(1), m.group(2)
        if token == "":
            return False
        adb = self.command[0] if self.command else ""
        if not adb:
            return False
        cwd = self._adb_shell_cwd()
        want_path = "/" in token
        self._adb_complete_seq += 1
        seq = self._adb_complete_seq
        serial = self._adb_shell_serial()
        left_s, token_s = left, token

        def work() -> None:
            res = _adb_tab_complete_compute(adb, serial, cwd, want_path, token_s, left_s)
            self._tab_async_complete.emit("adb", seq, res)

        threading.Thread(target=work, daemon=True).start()
        return True

    def _on_tab_async_complete(self, kind: str, seq: int, res: object) -> None:
        if not isinstance(res, dict):
            res = {}
        if kind == "ssh":
            self._apply_ssh_tab_result(seq, res)
        elif kind == "adb":
            self._apply_adb_tab_result(seq, res)

    def _apply_adb_tab_result(self, seq: int, res: dict) -> None:
        if seq != self._adb_complete_seq:
            return
        if self.proc.state() != QProcess.Running:
            return
        act = (res or {}).get("action")
        if act == "set_tail":
            self.output.set_input_tail((res or {}).get("text") or "")
        elif act == "list":
            self._show_completion_lines((res or {}).get("candidates") or [])
        elif act == "forward_tab":
            self.proc.write(b"\t")

    def _on_terminal_cleared(self) -> None:
        self._tail_cache = ""
        self._ansi.reset()

    def _append_plain_ui(self, text: str) -> None:
        """Append non-ANSI UI text (completion list, synthetic CMD prompt, session messages)."""
        if not text:
            return
        self.output.append_plain_fragment(text)
        self._tail_cache = (self._tail_cache + text)[-32768:]
        self._sync_python_repl_mode()

    def _ssh_parse_connection(self) -> Tuple[str, str, str]:
        """Return (ssh_executable, port, remote_target like user@host)."""
        if not self.command:
            return "", "22", ""
        parts = [str(x) for x in self.command]
        exe = parts[0]
        port = "22"
        for j in range(len(parts) - 1):
            if parts[j] == "-p" and j + 1 < len(parts):
                port = parts[j + 1]
        target = parts[-1] if len(parts) > 1 else ""
        port = str(normalize_tcp_port(port, 22))
        return exe, port, target

    def _ssh_shell_cwd(self) -> str:
        last = self._last_nonempty_line().strip()
        m = re.search(r"@[^:]+:([^$#\r\n]+)\s*[$#>]+\s*$", last)
        if m:
            return (m.group(1) or "").strip() or "~"
        return "~"

    def _ssh_build_ls_remote_cmd(self, remote_dir: str) -> str:
        return _ssh_build_ls_remote_cmd_static(remote_dir)

    def _ssh_list_dir_names(self, remote_dir: str) -> List[str]:
        exe, port, target = self._ssh_parse_connection()
        return _ssh_list_dir_names_for_args(exe, port, target, remote_dir)

    def _ssh_render_completed_token(self, left: str, token: str) -> str:
        if " " not in token:
            return token
        cmd = (left or "").lstrip()
        if cmd.startswith("cd "):
            return f'"{token}"'
        return token.replace(" ", r"\ ")

    def _ssh_complete_from_host(self) -> bool:
        """Host-side path/command completion (SSH work runs off the UI thread so the session stays responsive)."""
        tail = self.output.current_input_tail()
        if not tail:
            return False
        m = re.search(r"^(.*?)([^\s]*)$", tail, re.DOTALL)
        if not m:
            return False
        left, token = m.group(1), m.group(2)
        if token == "":
            return False
        exe, port, target = self._ssh_parse_connection()
        if not exe or not target:
            return False
        cwd = self._ssh_shell_cwd()
        want_path = "/" in token

        self._ssh_complete_seq += 1
        seq = self._ssh_complete_seq
        exe_s, port_s, target_s, cwd_s = exe, str(port), target, cwd

        def work() -> None:
            res = _ssh_tab_complete_compute(exe_s, port_s, target_s, cwd_s, want_path, token, left)
            self._tab_async_complete.emit("ssh", seq, res)

        threading.Thread(target=work, daemon=True).start()
        return True

    def _apply_ssh_tab_result(self, seq: int, res: dict) -> None:
        if seq != self._ssh_complete_seq:
            return
        if self.proc.state() != QProcess.Running:
            return
        act = (res or {}).get("action")
        if act == "set_tail":
            self.output.set_input_tail((res or {}).get("text") or "")
        elif act == "list":
            self._show_completion_lines((res or {}).get("candidates") or [])
        elif act == "forward_tab":
            self.proc.write(b"\t")

    def _list_local_dir_names(self, directory: str) -> List[str]:
        try:
            return [n for n in os.listdir(directory or ".") if n not in (".", "..")]
        except OSError:
            return []

    def _local_command_candidates(self) -> List[str]:
        env = self.proc.processEnvironment()
        path_val = env.value("PATH", "") or env.value("Path", "")
        key = path_val.lower()
        if key == self._path_command_cache_key and self._path_command_cache:
            return self._path_command_cache
        out: List[str] = []
        seen = set()
        exts = [".exe", ".cmd", ".bat", ".com", ".ps1"]
        for d in path_val.split(os.pathsep):
            d = (d or "").strip().strip('"')
            if not d or not os.path.isdir(d):
                continue
            try:
                for n in os.listdir(d):
                    nl = n.lower()
                    base = n
                    for ext in exts:
                        if nl.endswith(ext):
                            base = n[: -len(ext)]
                            break
                    b = base.strip()
                    if not b:
                        continue
                    bl = b.lower()
                    if bl not in seen:
                        seen.add(bl)
                        out.append(b)
            except OSError:
                continue
        self._path_command_cache_key = key
        self._path_command_cache = out
        return out

    def _preferred_python_exe(self) -> str:
        env = self.proc.processEnvironment()
        path_val = env.value("PATH", "") or env.value("Path", "")
        return _preferred_python_exe_from_path(path_val)

    def _local_complete_from_host(self) -> bool:
        tail = self.output.current_input_tail()
        if not tail:
            return False
        m = re.search(r"^(.*?)([^\s]*)$", tail, re.DOTALL)
        if not m:
            return False
        left, token = m.group(1), m.group(2)
        if token == "":
            return False
        cmd_name = ""
        m_cmd = re.search(r"(?:^|\s)(cd|chdir|dir|ls|set-location|sl)\s+$", left.lstrip(), re.IGNORECASE)
        if m_cmd:
            cmd_name = (m_cmd.group(1) or "").lower()
        force_path_context = bool(cmd_name)
        token_norm = token.replace("/", "\\")
        want_path = force_path_context or ("\\" in token_norm) or ("/" in token) or token_norm.startswith(".")
        if want_path:
            if token_norm.endswith("\\"):
                return False
            if "\\" in token_norm:
                head, prefix = token_norm.rsplit("\\", 1)
                if re.match(r"^[A-Za-z]:$", head):
                    base = head + "\\"
                elif os.path.isabs(token_norm):
                    # Rooted path without drive (e.g. "\foo") means "current drive root" on Windows.
                    if not head:
                        drv = Path(str(self._cwd)).drive or ""
                        base = (drv + "\\") if drv else "\\"
                    else:
                        base = head
                else:
                    base = str((self._cwd / head).resolve())
            else:
                prefix = token_norm
                base = str(self._cwd)
            names = self._list_local_dir_names(base)
            cands = [n for n in names if n.lower().startswith(prefix.lower())]
            if cmd_name in {"cd", "chdir", "set-location", "sl"}:
                cands = [n for n in cands if os.path.isdir(os.path.join(base, n))]
            if not cands:
                return False
            expanded = self._expand_common_prefix(prefix, cands)
            if expanded == prefix and len(cands) == 1:
                expanded = cands[0]
            if expanded == prefix and len(cands) > 1:
                self._show_completion_lines(cands)
                return True
            if "\\" in token_norm:
                repl = token_norm.rsplit("\\", 1)[0] + "\\" + expanded
            else:
                repl = expanded
            if len(cands) == 1:
                full = os.path.join(base, cands[0])
                if os.path.isdir(full) and not repl.endswith("\\"):
                    repl += "\\"
                elif os.path.isfile(full) and not repl.endswith(" "):
                    repl += " "
            self.output.set_input_tail(left + repl)
            return True
        pool = self._list_local_dir_names(str(self._cwd)) + self._local_command_candidates()
        # Stable unique pool (case-insensitive)
        uniq: List[str] = []
        seen = set()
        for n in pool:
            nl = n.lower()
            if nl not in seen:
                seen.add(nl)
                uniq.append(n)
        cands = [n for n in uniq if n.lower().startswith(token.lower())]
        if not cands:
            return False
        expanded = self._expand_common_prefix(token, cands)
        if expanded == token and len(cands) == 1:
            expanded = cands[0]
        if expanded == token and len(cands) > 1:
            self._show_completion_lines(cands)
            return True
        if len(cands) == 1 and not expanded.endswith(" "):
            expanded += " "
        self.output.set_input_tail(left + expanded)
        return True

    def shutdown(self, *, wait_for_process: bool = False) -> None:
        """Stop the shell process when the tab is closed.

        On normal tab close, the kill is fire-and-forget. On application exit, pass
        ``wait_for_process=False`` so the window closes immediately (avoids Windows socket noise).
        """
        self._manual_shutdown = True
        if self._is_serial_session:
            self._disconnect_proc_signals()
            self._serial_force_kill_and_release()
            self._close_log()
            return
        if self.proc.state() == QProcess.Running:
            self._disconnect_proc_signals()
            self.proc.kill()
            wtime = 800 if wait_for_process else 400
            self.proc.waitForFinished(wtime)
        self._close_log()

    def reconnect_session(self) -> None:
        """Reconnect this tab with the same command/profile after a disconnect/power-cycle."""
        self._manual_shutdown = False
        self._auto_reconnect_attempts = 0
        self._disconnect_proc_signals()
        self._stdout_pending.clear()
        self._stderr_pending.clear()
        self._pending_chunks.clear()
        self._flush_timer.stop()
        self._stdout_drain_scheduled = False
        self._stderr_drain_scheduled = False
        self._ansi.reset()
        self._trim_first_pty_chunk = True
        self._welcome_is_reconnect = True
        if self.proc.state() == QProcess.Running:
            self.proc.kill()
            self.proc.waitForFinished(1200)
        if self._is_serial_session:
            self._serial_auto_retries_used = 0
            self._serial_force_kill_and_release()
            self._serial_start_monotonic = time.monotonic()
        self._connect_proc_signals()
        self.proc.start(self.command[0], self.command[1:])
        self._update_session_footer()

    def _schedule_auto_reconnect(self) -> None:
        if not self._auto_reconnect_enabled or self._manual_shutdown:
            return
        if self._auto_reconnect_attempts >= self._auto_reconnect_max:
            self._append_plain_ui("\n[auto-reconnect] Max retries reached. Use tab menu -> Reconnect.\n")
            return
        self._auto_reconnect_attempts += 1
        delay_ms = min(10000, 1200 * self._auto_reconnect_attempts)
        self._append_plain_ui(
            f"\n[auto-reconnect] Attempt {self._auto_reconnect_attempts}/{self._auto_reconnect_max} in {delay_ms // 1000}s...\n"
        )
        QTimer.singleShot(delay_ms, self.reconnect_session)

    def _on_proc_started(self) -> None:
        self._manual_shutdown = False
        self._auto_reconnect_attempts = 0
        self._emit_session_welcome()

    def _flush_pending_streams(self) -> None:
        """Drain chunked stdout/stderr when the process ends (no further readyRead)."""
        self._stdout_drain_scheduled = False
        self._stderr_drain_scheduled = False
        sz = int(getattr(self, "_stream_chunk", 65536) or 65536)
        while self._stdout_pending:
            chunk = self._stdout_pending[:sz]
            del self._stdout_pending[:sz]
            self._append(chunk.decode(errors="ignore"))
        while self._stderr_pending:
            chunk = self._stderr_pending[:sz]
            del self._stderr_pending[:sz]
            self._append(chunk.decode(errors="ignore"))

    def _on_proc_finished(self):
        self._flush_pending_streams()
        self._ansi.reset()
        self._append_plain_ui("\n[session terminated — right-click tab -> Reconnect]\n")
        self._write_log("\n[session terminated — right-click tab -> Reconnect]\n")
        self._write_log(f"[full log path] {self._log_path}\n")
        if hasattr(self, "_session_footer"):
            self._session_footer.setText(f"Session · {self.session_label} — ended")
        self._close_log()
        if not self._is_serial_session:
            self._schedule_auto_reconnect()

    def _on_proc_error(self, _error) -> None:
        err = (self.proc.errorString() or "").strip()
        if not err:
            err = "Process failed to start."
        if self._is_serial_session:
            self._append_plain_ui(f"\n{err}\n")
            if self._serial_recoverable_open_error(err):
                self._schedule_serial_restart()
            return
        cmd = " ".join(shlex.quote(str(x)) for x in self.command)
        self._append(f"\n[start error] {err}\nCommand: {cmd}\n")

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
        """Ensure one visible space after the prompt token so the caret sits past ``$``/``#``/``>``."""
        if self._shell_profile == "cmd":
            doc = self._tail_cache
            if not doc or doc.endswith("> ") or not doc.rstrip().endswith(">"):
                return
            last = self._last_nonempty_line().rstrip()
            # ``C:\path>``, ``C:>``, ``D:\>``
            if not re.search(r"[A-Za-z]:[^>\n]*>$", last):
                return
            self._append_plain_ui(" ")
            return
        if self._shell_profile == "powershell":
            raw = self._last_nonempty_line()
            if not raw.strip():
                return
            bare = strip_sgr_sequences_for_prompt(raw.rstrip("\r")).rstrip()
            if bare.endswith("> "):
                return
            if re.match(r"^PS\s+", bare.strip()) and bare.rstrip().endswith(">") and not bare.endswith("> "):
                self._append_plain_ui(" ")
            return
        # ADB / SSH / serial UART / local Unix shells: one visible gap after ``$`` / ``#`` / zsh ``%``.
        if (
            self._is_adb_shell
            or self._is_ssh_session
            or self._is_serial_session
            or (not self._shell_profile and not self._is_adb_shell and not self._is_ssh_session)
        ):
            raw = self._last_nonempty_line()
            if not raw.strip():
                return
            bare = strip_sgr_sequences_for_prompt(raw.rstrip("\r")).rstrip()
            if bare_unix_prompt_needs_trailing_space(bare):
                self._append_plain_ui(" ")
            return

    def _write_raw_to_shell(self, data: bytes) -> None:
        if self.proc.state() != QProcess.Running or not data:
            return
        self.proc.write(data)

    def _send_line(self, line: str) -> None:
        if self.proc.state() != QProcess.Running:
            return
        stripped = (line or "").strip().lower()
        if self._shell_profile in ("cmd", "powershell") and stripped in ("python", "py", "python.exe"):
            self._python_repl_mode = True
            self.output.set_preserve_typed_input(True)
            py = self._preferred_python_exe()
            if self._shell_profile == "powershell":
                line = f'& "{py}" -i'
            else:
                line = f'"{py}" -i'
        if self._shell_profile == "cmd":
            s = (line or "").strip()
            m = re.match(r"^cd\s+(.+)$", s, re.IGNORECASE)
            if m:
                arg = m.group(1).strip()
                if arg and not arg.lower().startswith("/d ") and re.match(r'^[A-Za-z]:[\\/]', arg.strip('"')):
                    line = f"cd /d {arg}"
        self._apply_local_cd_line(line)
        self._update_session_footer()
        self._write_log(f"{line}\n")
        self.proc.write((line + "\n").encode("utf-8", errors="replace"))

    def _format_local_prompt(self) -> str:
        """Trailing space after `>` so the caret sits one space past the prompt (CMD pipe sessions only)."""
        return f"{str(self._cwd)}> "

    def _last_nonempty_line(self) -> str:
        for line in reversed(self._tail_cache.split("\n")):
            if line.strip():
                return line
        return ""

    def _buffer_already_shows_prompt(self) -> bool:
        if self._shell_profile != "cmd":
            return True
        last = self._last_nonempty_line().rstrip()
        if not last:
            return False
        return bool(re.search(r"[A-Za-z]:[^>\n]*>\s*$", last))

    def _maybe_append_synthetic_prompt(self) -> None:
        if not self._shell_profile or self.proc.state() != QProcess.Running:
            return
        # PowerShell already prints "PS path>" on stdout; a synthetic line duplicates it (PS ...> PS ...>).
        if self._shell_profile == "powershell":
            return
        if self._buffer_already_shows_prompt():
            return
        p = self._format_local_prompt()
        if self._tail_cache and not self._tail_cache.endswith("\n"):
            self._append_plain_ui("\n")
        self._append_plain_ui(p)

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

    def send_line(self, line: str, *, sync_anchor_after: bool = False) -> None:
        """Send a full line to the shell (same as pressing Enter after typing)."""
        raw = (line or "").rstrip("\n")
        self._send_line(raw)
        # Optional: menu-injected SSH lines — nudge the typing anchor after the PTY catches up (see main_window).
        if sync_anchor_after and self._is_ssh_session and raw.strip():
            QTimer.singleShot(120, self.output.sync_input_anchor_to_end)

    def _tighten_pty_chunk(self, text: str) -> str:
        """Collapse stacked newlines from PTY/serial (embedded shells often emit extra LFs)."""
        if not text:
            return text
        if self._is_remote_pty_shell or self._is_serial_session:
            # Do not merge all blank lines into one — that can glue command output and the next prompt.
            text = re.sub(r"\n{6,}", "\n\n\n\n\n", text)
        else:
            text = re.sub(r"\n{2,}", "\n", text)
        text = text.replace(r"\ ", " ")
        if self._tail_cache.endswith("\n") and text.startswith("\n"):
            if not (self._is_remote_pty_shell or self._is_serial_session):
                text = text[1:]
        return text

    def _append(self, data: str):
        if not data:
            return
        if self._is_serial_session:
            self._serial_maybe_retry_on_text(data)
        if self._is_serial_session:
            data = preprocess_serial_stream(data)
            data = preprocess_serial_esc_boundaries(data)
            data = _filter_serial_miniterm_banner(data)
            data = _scrub_serial_display_glitches(data)
            # Collapse UART noise lines (ESC fragments / lone resets) that double vertical space
            data = re.sub(r"\n(?:\s*(?:\x1b\[[0-9;]*m|\[(?:0;)?39m|0;39m|\x1b))+\s*\n", "\n", data, flags=re.I)
            data = re.sub(r"\n{2,}", "\n", data)
        else:
            # ADB/local shells need the same orphan-CSI / lone-ESC cleanup as SSH (not only preprocess_pty_stream).
            data = preprocess_escape_noise(data)
        if self._trim_first_pty_chunk:
            data = data.lstrip("\n")
            if not data:
                return
            self._trim_first_pty_chunk = False
        if not data:
            return
        if self._is_remote_pty_shell or self._is_serial_session:
            data = self._tighten_pty_chunk(data)
            if not data:
                return
        elif self._shell_profile in ("cmd", "powershell") and not self._python_repl_mode:
            data = re.sub(r"\n[ \t]*\n+", "\n", data)
            data = re.sub(r"\n{2,}", "\n", data)
        # Serial + SSH + ADB: same ANSI → HTML path as local shells (Moba-style colors). Flush caps keep UI responsive.
        if self._is_serial_session:
            self._ansi.reset()
            data = preprocess_prompt_lines_for_highlight(
                data, palette_kind=self._session_prompt_palette_name()
            )
            html_frag, plain_frag = self._ansi.feed(data)
            if html_frag:
                html_frag = re.sub(r"(?:<br/>){3,}", "<br/>", html_frag)
            if not html_frag and not plain_frag:
                return
            pl = plain_frag or ""
            self._write_log(pl)
            if pl:
                self._tail_cache = (self._tail_cache + pl)[-32768:]
            self._pending_chunks.append(html_frag)
            self._arm_flush_timer()
            return
        if self._is_remote_pty_shell:
            data = normalize_remote_pty_plain_text(data)
            data = ensure_remote_pty_visual_line_breaks(self._tail_cache, data)
            data = preprocess_prompt_lines_for_highlight(
                data, palette_kind=self._session_prompt_palette_name()
            )
            data = re.sub(r"\n{6,}", "\n\n\n\n\n", data)
            data = re.sub(r"\n{3,}", "\n", data)
            html_frag, plain_frag = self._ansi.feed(data)
            if not html_frag and not plain_frag:
                return
            pl = plain_frag or ""
            self._write_log(pl)
            if pl:
                self._tail_cache = (self._tail_cache + pl)[-32768:]
            self._pending_chunks.append(html_frag)
            self._arm_flush_timer()
            return
        data = preprocess_prompt_lines_for_highlight(
            data, palette_kind=self._session_prompt_palette_name()
        )
        html_frag, plain_frag = self._ansi.feed(data)
        if not html_frag and not plain_frag:
            return
        self._write_log(plain_frag)
        if plain_frag:
            self._tail_cache = (self._tail_cache + plain_frag)[-32768:]
        self._pending_chunks.append(html_frag)
        self._arm_flush_timer()

    def _maybe_reset_ansi_after_prompt(self) -> None:
        """If the last line looks like a shell prompt, reset SGR state so the next line uses default colors."""
        if self._is_serial_session:
            return
        tail = (self._tail_cache or "")[-4096:]
        last = ""
        for line in reversed(tail.split("\n")):
            if line.strip():
                last = line
                break
        if not last:
            return
        s = last.strip()
        if self._is_adb_shell and re.search(r":(/[^ ]*)\s*[$#]\s*$", s):
            self._ansi.reset()
        elif self._is_ssh_session and (
            re.search(r"@[^:]+:.+\s+[$#>]+\s*$", s)
            or re.match(r"^\s*#\s*$", s)
            or re.match(r"^\s*#\s+\S", s)
            or re.match(r"^\S+\s+#\s*$", s)
        ):
            self._ansi.reset()

    def _flush_pending_output(self) -> None:
        if not self._pending_chunks:
            return
        cap = _LOCAL_HTML_FLUSH_CAP
        parts: List[str] = []
        total = 0
        for ch in self._pending_chunks:
            if parts and total + len(ch) > cap:
                break
            parts.append(ch)
            total += len(ch)
        if not parts:
            parts = [self._pending_chunks[0]]
        self._pending_chunks = self._pending_chunks[len(parts) :]
        text = "".join(parts)
        self.output.setUpdatesEnabled(False)
        try:
            self._append_output_html(text)
        finally:
            self.output.setUpdatesEnabled(True)
        self._maybe_reset_ansi_after_prompt()
        self._ensure_prompt_trailing_space()
        if self._shell_profile == "cmd":
            self._maybe_append_synthetic_prompt()
            self._ensure_prompt_trailing_space()
        self._update_session_footer()
        if self._pending_chunks:
            self._arm_flush_timer()

    def _append_output_html(self, text: str, ensure_visible: bool = True, *, force_scroll: bool = False) -> None:
        if not text:
            return
        ev = ensure_visible
        if force_scroll:
            ev = True
        elif ev and getattr(self, "_scroll_output_on_newline_only", False):
            ev = "<br" in (text or "").lower()
        self.output.append_from_process_html(text, ensure_visible=ev)
        self._sync_python_repl_mode()

    def _sync_python_repl_mode(self) -> None:
        if self._shell_profile not in ("cmd", "powershell"):
            self._python_repl_mode = False
            self.output.set_preserve_typed_input(False)
            return
        last = self._last_nonempty_line()
        py_prompt = bool(re.search(r"(>>>|\.\.\.)\s*$", last))
        shell_prompt = bool(
            re.search(r"(?:^[A-Za-z]:[^>\n]*>\s*$)|(?:^PS\s+.*>\s*$)", last)
        )
        if py_prompt:
            self._python_repl_mode = True
            self.output.set_preserve_typed_input(True)
            return
        if shell_prompt:
            self._python_repl_mode = False
            self.output.set_preserve_typed_input(False)

    def _start(self):
        if self._is_serial_session:
            self._serial_start_monotonic = time.monotonic()
            if not self._banner:
                parts = [str(x) for x in self.command]
                com = parts[-2] if len(parts) >= 2 else "COM?"
                baud = parts[-1] if len(parts) >= 2 else "?"
                self._banner = (
                    f"Serial console · {com} @ {baud} baud — close tab to disconnect; Ctrl+] = break (miniterm)."
                )
            self._trim_first_pty_chunk = bool(self._banner)
        self.output.set_initial_content("")
        self._tail_cache = ""
        self._open_log()
        env = QProcessEnvironment.systemEnvironment()
        if self._path_extra_dirs:
            path = env.value("PATH", "") or env.value("Path", "")
            merged = os.pathsep.join(self._path_extra_dirs)
            combined = merged + (os.pathsep + path if path else "")
            env.insert("PATH", combined)
            env.insert("Path", combined)
        elif env.value("PATH", "") and not env.value("Path", ""):
            env.insert("Path", env.value("PATH", ""))
        elif env.value("Path", "") and not env.value("PATH", ""):
            env.insert("PATH", env.value("Path", ""))
        self.proc.setProcessEnvironment(env)
        self.proc.setWorkingDirectory(self._working_dir_str)
        if self._is_ssh_session:
            parts = [str(x) for x in self.command]
            dest = parts[-1] if parts else ""
            if "_adbnik_missing_host.invalid" in dest:
                self._append_plain_ui(
                    "\n[SSH] No host configured. Close this tab, then use Session → Login (enter Host), "
                    "or connect SFTP in File Explorer before opening an SSH terminal from there.\n"
                )
                self._update_session_footer()
                return
        # Merge stderr into stdout so a noisy remote cannot fill the stderr pipe and stall the session
        # (can look like slog2info or similar "never finishes" when output is large).
        # Serial: merge so miniterm/Python errors on stderr still reach the same drain path as stdout.
        if self._is_remote_pty_shell or self._is_serial_session:
            self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.start(self.command[0], self.command[1:])
        self.output.setFocus(Qt.OtherFocusReason)
        self._update_session_footer()
        if self._is_remote_pty_shell:
            QTimer.singleShot(80, self._warm_remote_tab_completion_cache)

    def _warm_remote_tab_completion_cache(self) -> None:
        """Prefetch Tab-completion data for whichever remote shell is active (ADB or SSH)."""
        if self._is_ssh_session:
            self._warm_ssh_tab_completion_cache()
        elif self._is_adb_shell:
            self._warm_adb_tab_completion_cache()

    def _warm_adb_tab_completion_cache(self) -> None:
        """Prefetch common remote bin listings so Tab completion stays responsive."""
        if not self._is_adb_shell or self.proc.state() != QProcess.Running:
            return
        adb = self.command[0] if self.command else ""
        if not adb:
            return
        serial = self._adb_shell_serial()

        def work() -> None:
            for d in ("/ifs/bin", "/system/bin", "/system/xbin"):
                _adb_list_dir_names_for_args(adb, serial, d)

        threading.Thread(target=work, daemon=True).start()

    def _warm_ssh_tab_completion_cache(self) -> None:
        """Prefetch remote PATH tool names (e.g. ``/ifs/bin``) so the first Tab is not a cold cache miss."""
        if not self._is_ssh_session or self.proc.state() != QProcess.Running:
            return
        exe, port, target = self._ssh_parse_connection()
        if not exe or not target:
            return

        def work() -> None:
            _ssh_list_command_pool_for_args(exe, port, target)

        threading.Thread(target=work, daemon=True).start()

    def _read_stdout(self) -> None:
        self._stdout_pending.extend(bytes(self.proc.readAllStandardOutput()))
        self._schedule_stdout_drain()

    def _read_stderr(self) -> None:
        self._stderr_pending.extend(bytes(self.proc.readAllStandardError()))
        self._schedule_stderr_drain()

    def _schedule_stdout_drain(self) -> None:
        if self._stdout_drain_scheduled:
            return
        self._stdout_drain_scheduled = True
        QTimer.singleShot(0, self._drain_stdout_pending)

    def _schedule_stderr_drain(self) -> None:
        if self._stderr_drain_scheduled:
            return
        self._stderr_drain_scheduled = True
        QTimer.singleShot(0, self._drain_stderr_pending)

    def _drain_stdout_pending(self) -> None:
        self._stdout_drain_scheduled = False
        if not self._stdout_pending:
            return
        if self._is_remote_pty_shell:
            backlog = self._pending_flush_backlog()
            if backlog > 1_200_000:
                budget = 96 * 1024
            elif backlog > 600_000:
                budget = 192 * 1024
            elif backlog > 250_000:
                budget = 512 * 1024
            else:
                budget = 2 * 1024 * 1024
            taken = 0
            parts: List[bytes] = []
            slice_sz = max(65536, int(getattr(self, "_stream_chunk", 65536) or 65536))
            while self._stdout_pending and taken < budget:
                n = min(len(self._stdout_pending), slice_sz)
                parts.append(bytes(self._stdout_pending[:n]))
                del self._stdout_pending[:n]
                taken += n
            raw = b"".join(parts)
            self._append(raw.decode(errors="ignore"))
        else:
            sz = int(getattr(self, "_stream_chunk", 65536) or 65536)
            chunk = self._stdout_pending[:sz]
            del self._stdout_pending[:sz]
            self._append(chunk.decode(errors="ignore"))
        if self._stdout_pending:
            self._schedule_stdout_drain()

    def _drain_stderr_pending(self) -> None:
        self._stderr_drain_scheduled = False
        if not self._stderr_pending:
            return
        if self._is_remote_pty_shell:
            # Stdout/stderr are merged for ssh/adb shell; this path is usually idle.
            budget = 512 * 1024
            taken = 0
            parts: List[bytes] = []
            while self._stderr_pending and taken < budget:
                n = min(len(self._stderr_pending), 65536)
                parts.append(bytes(self._stderr_pending[:n]))
                del self._stderr_pending[:n]
                taken += n
            raw = b"".join(parts)
            if raw:
                self._append(raw.decode(errors="ignore"))
        else:
            sz = int(getattr(self, "_stream_chunk", 65536) or 65536)
            chunk = self._stderr_pending[:sz]
            del self._stderr_pending[:sz]
            self._append(chunk.decode(errors="ignore"))
        if self._stderr_pending:
            self._schedule_stderr_drain()

    def _save_buffer_as(self) -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        suggested = f"{self.session_label.replace(' ', '_')}_{ts}.txt"
        path, _ = get_save_filename(self, "Save terminal output as", suggested, "Text files (*.txt);;All files (*.*)")
        if not path:
            return
        mode = QMessageBox.question(
            self,
            "Save terminal output",
            "Save full session log (all output since tab opened)?\n\n"
            "Yes = full session log\n"
            "No = visible buffer only",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.Yes,
        )
        if mode == QMessageBox.Cancel:
            return
        try:
            if mode == QMessageBox.Yes and self._log_path.exists():
                self._flush_log_buffer()
                shutil.copyfile(str(self._log_path), path)
            else:
                with open(path, "w", encoding="utf-8", errors="replace") as f:
                    f.write(self.output.toPlainText())
            box = QMessageBox(self)
            box.setWindowTitle("Saved")
            box.setIcon(QMessageBox.Information)
            box.setText("Terminal output saved.")
            box.setInformativeText(path)
            open_btn = box.addButton("Open file", QMessageBox.ActionRole)
            box.addButton(QMessageBox.Ok)
            box.exec_()
            if box.clickedButton() == open_btn:
                from PyQt5.QtCore import QUrl
                from PyQt5.QtGui import QDesktopServices

                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        except OSError:
            pass

    def _open_log(self) -> None:
        if self._log_fp is None:
            self._log_fp = self._log_path.open("a", encoding="utf-8", errors="replace")

    def _write_log(self, text: str) -> None:
        if not text:
            return
        self._log_pending_chunks.append(text)
        if not self._log_flush_timer.isActive():
            self._log_flush_timer.start()

    def _flush_log_buffer(self) -> None:
        if not self._log_pending_chunks:
            return
        try:
            if self._log_fp is None:
                self._open_log()
            if self._log_fp is None:
                return
            payload = "".join(self._log_pending_chunks)
            self._log_pending_chunks.clear()
            self._log_fp.write(payload)
            self._log_fp.flush()
        except Exception:
            pass

    def _close_log(self) -> None:
        try:
            self._flush_log_buffer()
            if self._log_fp is not None:
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

    def _tool_bin_dirs_for_path(self) -> List[str]:
        """Prepend configured tool locations (adb/scrcpy) to PATH for embedded CMD/PowerShell."""
        out: List[str] = []
        py = self._preferred_python_exe()
        if py:
            p = Path(py)
            if p.is_file():
                out.append(str(p.resolve().parent))
        ap = (self.get_adb_path() or "").strip()
        if ap:
            p = Path(ap)
            if p.is_file():
                out.append(str(p.resolve().parent))
        sp = (self.config.scrcpy_path or "").strip()
        if sp:
            p = Path(sp)
            if p.is_file():
                out.append(str(p.resolve().parent))
        return out

    def _preferred_python_exe(self) -> str:
        return _preferred_python_exe_from_path(os.environ.get("PATH", ""))

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
        self.tabs.currentChanged.connect(self._on_terminal_stack_changed)
        right_layout.addWidget(self.tabs, 1)

        self._status_label = QLabel("Ready")
        self._status_label.setObjectName("MobaStatus")
        right_layout.addWidget(self._status_label)

        split.addWidget(left)
        split.addWidget(right)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([240, 1000])

        self._add_placeholder_tab()
        # Bookmarks refresh touches session tabs — run only after self.tabs exists.
        self._reload_bookmark_sidebar()
        QTimer.singleShot(0, self._sync_terminal_flush_pause)
        for _seq in ("Ctrl+R", "Ctrl+Shift+R"):
            _sc = QShortcut(QKeySequence(_seq), self)
            _sc.setContext(Qt.WidgetWithChildrenShortcut)
            _sc.activated.connect(self._shortcut_reconnect_current_session)

    def _shortcut_reconnect_current_session(self) -> None:
        w = self.tabs.currentWidget()
        if isinstance(w, SessionWidget):
            w.reconnect_session()

    def _on_terminal_stack_changed(self, _index: int) -> None:
        self._refresh_bookmark_open_indicators()
        self._sync_terminal_flush_pause()

    def _sync_terminal_flush_pause(self) -> None:
        idx = self.tabs.currentIndex()
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if hasattr(w, "set_flush_paused"):
                w.set_flush_paused(i != idx)

    def _ssh_tab_title(self, profile: SessionProfile) -> str:
        h = (profile.ssh_host or "").strip()
        u = (profile.ssh_user or "").strip()
        p = normalize_tcp_port(profile.ssh_port, 22)
        if u:
            base = f"{u}@{h}"
        else:
            base = h or "SSH"
        if p != 22:
            return f"{base}:{p}"
        return base

    def _ftp_tab_title(self, profile: SessionProfile) -> str:
        h = (profile.ftp_host or "").strip() or "FTP"
        p = normalize_tcp_port(profile.ftp_port, 21)
        u = (profile.ftp_user or "").strip()
        base = f"{u}@{h}" if u else h
        return f"{base}:{p}" if p != 21 else base

    def _ensure_ssh_client_available(self) -> bool:
        if shutil.which("ssh"):
            return True
        QMessageBox.warning(
            self,
            "SSH client not found",
            "OpenSSH client ('ssh') is not available on PATH.\n"
            "Install/enable OpenSSH Client in Windows Optional Features, then retry.",
        )
        return False

    def _open_ftp_terminal(self, host: str, port: int, user: str = "") -> None:
        h = (host or "").strip()
        if not h:
            QMessageBox.information(self, "FTP", "Enter host first.")
            return
        ftp_exe = shutil.which("ftp")
        if not ftp_exe:
            QMessageBox.warning(
                self,
                "FTP client not found",
                "Windows FTP client ('ftp') is not available on PATH.\n"
                "Enable/install it, then retry.",
            )
            return
        label = f"FTP · {(user + '@') if user else ''}{h}:{int(port or 21)}"
        cmd = [ftp_exe, h]
        self.add_session(
            label,
            cmd,
            shell_profile=None,
            working_dir=os.getcwd(),
            path_extra_dirs=self._tool_bin_dirs_for_path(),
        )
        self._append_log(
            "FTP terminal: started interactive ftp client. "
            "Login is manual in terminal (user/password prompts)."
        )

    def set_device_stats_text(self, text: str) -> None:
        base = "Ready"
        extra = (text or "").strip()
        self._status_label.setText(f"{base} · {extra}" if extra else base)

    def _reload_bookmark_sidebar(self) -> None:
        self.bookmark_list.clear()
        for bm in self.config.session_bookmarks:
            if not isinstance(bm, dict):
                continue
            if str(bm.get("kind", "")) not in ("ssh", "adb", "serial", "local_cmd", "local_pwsh"):
                continue
            it = QListWidgetItem(bm.get("name") or "Untitled")
            it.setIcon(bookmark_icon_from_entry(bm, self))
            it.setData(Qt.UserRole, bm)
            self.bookmark_list.addItem(it)
        self._refresh_bookmark_open_indicators()

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
            cmd_exe = os.environ.get("COMSPEC", "cmd.exe")
            self.add_session(
                bookmark_session_tab_title(bm),
                [cmd_exe, "/K", "doskey ls=dir"],
                working_dir=os.getcwd(),
                shell_profile="cmd",
                path_extra_dirs=self._tool_bin_dirs_for_path(),
            )
            return
        if k == "local_pwsh":
            sys_root = os.environ.get("SystemRoot", r"C:\Windows")
            ps = Path(sys_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
            ps_exe = str(ps) if ps.is_file() else "powershell.exe"
            self.add_session(
                bookmark_session_tab_title(bm),
                [
                    ps_exe,
                    "-NoLogo",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-NoExit",
                ],
                working_dir=os.getcwd(),
                shell_profile="powershell",
                path_extra_dirs=self._tool_bin_dirs_for_path(),
            )
            return
        if k == "adb":
            serial = (bm.get("adb_serial") or "").strip()
            if not serial:
                QMessageBox.information(self, "Bookmark", "This bookmark has no device serial.")
                return
            adb = self.get_adb_path()
            cmd = adb_interactive_shell_command(adb, serial)
            label = bookmark_session_tab_title(bm)
            self.add_session(label, cmd, banner=_adb_terminal_banner(adb, serial, label))
            return
        if k == "ssh":
            if not self._ensure_ssh_client_available():
                return
            host = str(bm.get("ssh_host", "")).strip()
            if not host:
                QMessageBox.warning(
                    self,
                    "Bookmark",
                    "This SSH bookmark has no host. Edit the bookmark or use Session → Login.",
                )
                return
            try:
                sp = int(bm.get("ssh_port") or 22)
            except (TypeError, ValueError):
                sp = 22
            sp = normalize_tcp_port(sp, 22)
            profile = SessionProfile(
                ConnectionKind.SSH_SFTP,
                ssh_host=host,
                ssh_user=bm.get("ssh_user", ""),
                ssh_port=sp,
                ssh_password=bm.get("ssh_password", "") or "",
            )
            self.add_session(
                bookmark_session_tab_title(bm),
                ssh_command_args(profile),
                path_extra_dirs=self._tool_bin_dirs_for_path(),
            )
            return
        if k == "ftp":
            try:
                fp = int(bm.get("ftp_port") or 21)
            except (TypeError, ValueError):
                fp = 21
            self._open_ftp_terminal(
                host=str(bm.get("ftp_host") or "").strip(),
                port=fp,
                user=str(bm.get("ftp_user") or "").strip(),
            )
            return
        if k == "serial":
            port = bm.get("serial_port") or self.get_default_serial_port()
            baud = bm.get("serial_baud") or self.get_default_serial_baud()
            cmd = [sys.executable, "-m", "serial.tools.miniterm", str(port), str(baud)]
            self.add_session(bookmark_session_tab_title(bm), cmd)

    def _open_local_cmd(self) -> None:
        # Native CMD behavior; keep command parsing/execution identical to real cmd.exe.
        cmd_exe = os.environ.get("COMSPEC", "cmd.exe")
        self.add_session(
            "Command Prompt",
            [cmd_exe, "/K", "doskey ls=dir"],
            working_dir=os.getcwd(),
            shell_profile="cmd",
            path_extra_dirs=self._tool_bin_dirs_for_path(),
        )

    def _open_local_powershell(self) -> None:
        sys_root = os.environ.get("SystemRoot", r"C:\Windows")
        ps = Path(sys_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        ps_exe = str(ps) if ps.is_file() else "powershell.exe"
        # Native PowerShell behavior; no startup command rewriting.
        self.add_session(
            "Windows PowerShell",
            [
                ps_exe,
                "-NoLogo",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-NoExit",
            ],
            working_dir=os.getcwd(),
            shell_profile="powershell",
            path_extra_dirs=self._tool_bin_dirs_for_path(),
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
        self._refresh_bookmark_open_indicators()

    def _on_terminal_tab_bar_context_menu(self, pos) -> None:
        """Moba-style: right-click a session tab for close / close others / close to the side."""
        tb = self.tabs.tabBar()
        idx = tb.tabAt(pos)
        if idx < 0:
            return
        st = self.style()
        m = QMenu(self)
        a_close = m.addAction(st.standardIcon(QStyle.SP_TitleBarCloseButton), "Close")
        a_close.setToolTip("Close this tab")
        a_others = m.addAction(st.standardIcon(QStyle.SP_DialogCancelButton), "Close others")
        a_others.setToolTip("Close all tabs except this one")
        a_right = m.addAction(st.standardIcon(QStyle.SP_ArrowForward), "Close to the right")
        a_right.setToolTip("Close every tab to the right of this one")
        a_left = m.addAction(st.standardIcon(QStyle.SP_ArrowBack), "Close to the left")
        a_left.setToolTip("Close every tab to the left of this one")
        m.addSeparator()
        a_reconnect = m.addAction(st.standardIcon(QStyle.SP_BrowserReload), "Reconnect")
        a_reconnect.setToolTip("Restart this session (Ctrl+R or Ctrl+Shift+R)")
        m.addSeparator()
        a_font_up = m.addAction(st.standardIcon(QStyle.SP_ArrowUp), "Increase font size")
        a_font_up.setToolTip("Larger text (Ctrl++ or Ctrl+mouse wheel)")
        a_font_down = m.addAction(st.standardIcon(QStyle.SP_ArrowDown), "Decrease font size")
        a_font_down.setToolTip("Smaller text (Ctrl+-)")
        a_font_reset = m.addAction(st.standardIcon(QStyle.SP_DialogResetButton), "Reset font size")
        a_font_reset.setToolTip("Default 11 pt (Ctrl+0 in terminal)")
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
        elif chosen == a_reconnect:
            w = self.tabs.widget(idx)
            if isinstance(w, SessionWidget):
                w.reconnect_session()
        elif chosen in (a_font_up, a_font_down, a_font_reset):
            w = self.tabs.widget(idx)
            if isinstance(w, SessionWidget):
                if chosen == a_font_up:
                    w.output.adjust_terminal_font_size(+1)
                elif chosen == a_font_down:
                    w.output.adjust_terminal_font_size(-1)
                else:
                    w.output.set_terminal_font_size(11)

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
        elif o.kind in ("ssh", "sftp"):
            if not self._ensure_ssh_client_available():
                return
            profile = SessionProfile(
                ConnectionKind.SSH_SFTP,
                ssh_host=o.sftp_host,
                ssh_user=o.sftp_user,
                ssh_port=o.sftp_port,
                ssh_password=o.sftp_password or "",
            )
            self.add_session(
                self._ssh_tab_title(profile),
                ssh_command_args(profile),
                path_extra_dirs=self._tool_bin_dirs_for_path(),
            )
        elif o.kind == "ftp":
            self._open_ftp_terminal(
                host=o.ftp_host,
                port=normalize_tcp_port(o.ftp_port, 21),
                user=o.ftp_user or "",
            )
        elif o.kind == "serial":
            port = (o.serial_port or "").strip() or self.get_default_serial_port()
            baud = (o.serial_baud or "").strip() or self.get_default_serial_baud()
            cmd = [sys.executable, "-m", "serial.tools.miniterm", port, baud]
            self.add_session(f"Serial console · {port}", cmd)
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
        path_extra_dirs: Optional[Sequence[str]] = None,
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
            path_extra_dirs=path_extra_dirs,
            auto_reconnect=bool(getattr(self.config, "auto_reconnect_terminal", True)),
        )
        tab_icon = QIcon()
        if widget._is_adb_shell:
            tab_icon = icon_adb_android()
        elif widget._is_ssh_session:
            tab_icon = icon_ssh_session()
        elif widget._is_serial_session:
            tab_icon = icon_serial_port()
        idx = self.tabs.addTab(widget, label)
        if tab_icon and not tab_icon.isNull():
            self.tabs.setTabIcon(idx, tab_icon)
        self._apply_terminal_tab_colors(idx, widget)
        self.tabs.setCurrentIndex(idx)
        self._refresh_bookmark_open_indicators()

    def _apply_terminal_tab_colors(self, index: int, widget: "SessionWidget") -> None:
        """Color session tab labels: ADB green, SSH blue, serial yellow, local shells light gray."""
        bar = self.tabs.tabBar()
        if not hasattr(bar, "setTabTextColor"):
            return
        if not isinstance(widget, SessionWidget):
            return
        w = widget
        if w._is_adb_shell:
            c = QColor("#22c55e")
        elif w._is_ssh_session:
            c = QColor("#38bdf8")
        elif w._is_serial_session:
            c = QColor("#eab308")
        else:
            c = QColor("#cbd5e1")
        bar.setTabTextColor(index, c)

    def _open_bookmark_fingerprints(self) -> Set[str]:
        """Fingerprints for sessions that match a bookmark (same host/serial/etc.)."""
        out: Set[str] = set()
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, SessionWidget):
                fp = w.session_bookmark_fingerprint()
                if fp:
                    out.add(fp)
        return out

    def _refresh_bookmark_open_indicators(self) -> None:
        """Sidebar bookmark labels: green when a matching tab is open, red when not."""
        if not getattr(self, "tabs", None):
            return
        active = self._open_bookmark_fingerprints()
        for row in range(self.bookmark_list.count()):
            it = self.bookmark_list.item(row)
            if it is None:
                continue
            bm = it.data(Qt.UserRole)
            fp = bookmark_entry_fingerprint(bm) if isinstance(bm, dict) else ""
            if not fp:
                continue
            if fp in active:
                it.setForeground(QBrush(QColor("#22c55e")))
            else:
                it.setForeground(QBrush(QColor("#b91c1c")))

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
        w.send_line(line, sync_anchor_after=True)
        self.tabs.setCurrentWidget(w)
        return True

    def send_line_to_ssh_session(self, line: str) -> bool:
        """Send one line to a running SSH terminal tab (Commands → SSH), not the active tab if it is ADB/local."""
        ssh_tabs: List[Tuple[int, SessionWidget]] = []
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if not isinstance(w, SessionWidget):
                continue
            if not w._is_ssh_session:
                continue
            if w.proc.state() != QProcess.Running:
                continue
            ssh_tabs.append((i, w))
        if not ssh_tabs:
            QMessageBox.information(
                self,
                "SSH",
                "Open an SSH terminal tab first (Session → Login → SSH, or File Explorer → SSH terminal). "
                "Commands → SSH sends only to SSH sessions, not ADB or local shells.",
            )
            return False
        cur = self.tabs.currentIndex()
        chosen: Optional[Tuple[int, SessionWidget]] = None
        for i, w in ssh_tabs:
            if i == cur:
                chosen = (i, w)
                break
        if chosen is None:
            chosen = ssh_tabs[0]
        i, w = chosen
        self.tabs.setCurrentIndex(i)
        w.send_line(line, sync_anchor_after=True)
        return True

    def shutdown_all_sessions(self) -> None:
        """Terminate every open shell (ADB, SSH, serial, local) before the application exits."""
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, SessionWidget):
                w.shutdown(wait_for_process=w._is_serial_session)

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
            if not self._ensure_ssh_client_available():
                return
            if not (profile.ssh_host or "").strip():
                QMessageBox.information(
                    self,
                    "SSH",
                    "Enter host in File Explorer → SFTP tab, then use "
                    "Session → Open SSH terminal (from Explorer SFTP fields).",
                )
                return
            self.add_session(
                self._ssh_tab_title(profile),
                ssh_command_args(profile),
                path_extra_dirs=self._tool_bin_dirs_for_path(),
            )
        elif profile.kind == ConnectionKind.FTP:
            self._open_ftp_terminal(
                host=profile.ftp_host,
                port=normalize_tcp_port(profile.ftp_port, 21),
                user=profile.ftp_user,
            )
        elif profile.kind == ConnectionKind.SERIAL:
            port = profile.serial_port or self.get_default_serial_port()
            baud = profile.serial_baud or self.get_default_serial_baud()
            cmd = [sys.executable, "-m", "serial.tools.miniterm", port, baud]
            self.add_session(f"Serial console · {port}", cmd)
