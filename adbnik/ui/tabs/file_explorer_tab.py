import errno
import hashlib
import io
import json
import os
import posixpath
import re
import sys
import threading
import time
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from ftplib import FTP, error_perm
from pathlib import Path
from stat import S_ISREG
from typing import Any, Callable, Dict, List, Optional, Tuple

# File-type bits (avoid stat.S_IFMT on SFTP modes — Python 3.13+ can raise "mode out of range" for 0xFFFFFFFF etc.)
_S_IFDIR = 0o040000
_S_IFLNK = 0o120000
_S_IFMT_MASK = 0o170000

from PyQt5.QtCore import (
    QByteArray,
    QEvent,
    QFileInfo,
    QFileSystemWatcher,
    QMimeData,
    QSize,
    Qt,
    QThread,
    QTimer,
    QUrl,
    pyqtSignal,
)
from PyQt5.QtGui import QDesktopServices, QDrag, QFont, QIcon, QKeySequence

from ... import APP_TITLE
from ...session import ConnectionKind, SessionProfile, normalize_tcp_port
from ...config import AppConfig
from ..combo_utils import ExpandAllComboBox
from ..icon_utils import icon_home_folder, icon_nav_up, icon_root_drive
from ..session_login_dialog import SessionLoginDialog, SessionLoginOutcome
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFileIconProvider,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressDialog,
    QPushButton,
    QShortcut,
    QSizePolicy,
    QSplitter,
    QStyle,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ...services.commands import (
    adb_remote_probe_size,
    adb_remote_path_bytes_now,
    adb_start_rm_rf,
    kill_all_adb_subprocesses,
    run_adb,
    run_adb_with_line_callback,
    unregister_adb_process,
)
from ...services.remote_clients import (
    connect_ftp,
    connect_sftp,
    disconnect_ftp,
    disconnect_sftp,
    sftp_first_listable_path,
    sftp_listdir_attr_safe,
)

# Windows/macOS shell icons by extension for remote listings (no real local path).
_remote_ext_icon_cache: Dict[str, QIcon] = {}
_MAX_INLINE_EDITOR_BYTES = 8 * 1024 * 1024
_MAX_FIND_FOLDER_HISTORY = 24

# Remote table → local table drag (pull); custom MIME, not file:// URLs.
MIME_REMOTE_PULL = "application/x-adbnik-remote-pull"


def _ftp_quote_token(name: str) -> str:
    """Quote a single path segment or filename for FTP CWD/MKD/RMD/DELE/STOR/RETR when spaces or quotes appear."""
    s = (name or "").replace("\r", "").replace("\n", "")
    if not s:
        return '""'
    if any(c in s for c in ' \t"'):
        return '"' + s.replace('"', '""') + '"'
    return s


def _ftp_void(ftp: FTP, cmd: str) -> str:
    return ftp.voidcmd(cmd)


def _ftp_safe_cwd(ftp: FTP, remote_path: str) -> None:
    """CWD to an absolute path; supports spaces and special characters in each segment."""
    r = (remote_path or "").replace("\\", "/").rstrip("/") or "/"
    if r == "/":
        ftp.cwd("/")
        return
    try:
        ftp.cwd("/")
    except error_perm:
        pass
    for seg in [p for p in r.split("/") if p]:
        _ftp_void(ftp, "CWD " + _ftp_quote_token(seg))


def _ftp_cwd_segment(ftp: FTP, segment: str) -> None:
    """CWD into one directory name relative to the current remote working directory."""
    _ftp_void(ftp, "CWD " + _ftp_quote_token(segment))


def _ftp_safe_mkd(ftp: FTP, dirname: str) -> None:
    _ftp_void(ftp, "MKD " + _ftp_quote_token(dirname))


def _ftp_safe_rmd(ftp: FTP, dirname: str) -> None:
    _ftp_void(ftp, "RMD " + _ftp_quote_token(dirname))


def _ftp_safe_delete_file(ftp: FTP, filename: str) -> None:
    _ftp_void(ftp, "DELE " + _ftp_quote_token(filename))


def _sftp_is_exists_err(exc: BaseException) -> bool:
    en = getattr(exc, "errno", None)
    if en in (errno.EEXIST, 17):
        return True
    if en in (183, 80):  # Windows FILE_EXISTS / directory exists
        return True
    msg = str(exc).lower()
    return "file exists" in msg or "already exists" in msg


def _sftp_is_dir(st_mode: Optional[int]) -> bool:
    """Some embedded SFTP servers report modes that trigger ValueError in stat.S_ISDIR (e.g. Python 3.13+)."""
    if st_mode is None:
        return False
    try:
        m = int(st_mode) & 0xFFFFFFFF
    except (TypeError, ValueError):
        return False
    return (m & _S_IFMT_MASK) == _S_IFDIR


def _sftp_entry_is_dir(sftp, parent: str, a) -> bool:
    """True for directories and for symlinks that point to directories (common for /data, /sbin, /tmp on embedded)."""
    if getattr(a, "st_mode", None) is None:
        return False
    try:
        m = int(a.st_mode) & 0xFFFFFFFF
    except (TypeError, ValueError):
        return False
    if (m & _S_IFMT_MASK) == _S_IFDIR:
        return True
    if (m & _S_IFMT_MASK) == _S_IFLNK:
        full = posixpath.join(parent.rstrip("/") or "/", a.filename).replace("\\", "/")
        try:
            st = sftp.stat(full)
            return _sftp_stat_is_dir(st)
        except (OSError, IOError, Exception):
            return False
    return False


def _sftp_perm_str(st_mode: Optional[int]) -> str:
    if st_mode is None:
        return ""
    try:
        m = int(st_mode) & 0xFFFFFFFF
        return f"{m & 0o777:03o}"
    except (TypeError, ValueError):
        return ""


def _sftp_stat_is_dir(st) -> bool:
    """Directory check without stat.S_ISDIR (embedded SFTP can return modes that raise 'mode out of range')."""
    try:
        m = int(getattr(st, "st_mode", 0)) & 0xFFFFFFFF
    except (TypeError, ValueError):
        return False
    return (m & _S_IFMT_MASK) == _S_IFDIR


def _sftp_rm_rf(sftp: Any, path: str) -> None:
    """Remove a remote file or directory tree (paramiko SFTPClient). Uses listdir_attr-safe listing; surfaces errors."""
    path = path.replace("\\", "/").rstrip("/")
    if not path:
        raise OSError("Empty remote path")
    if path == "/":
        raise OSError("Refusing to delete filesystem root")
    try:
        st = sftp.stat(path)
    except (OSError, IOError, Exception) as e:
        raise OSError(f"SFTP stat failed for {path!r}: {e}") from e
    try:
        mode = int(getattr(st, "st_mode", 0)) & 0xFFFFFFFF
    except (TypeError, ValueError):
        mode = 0
    is_dir = (mode & _S_IFMT_MASK) == _S_IFDIR if mode else _sftp_stat_is_dir(st)

    if not is_dir:
        try:
            sftp.remove(path)
            return
        except (OSError, IOError, Exception) as e:
            en = getattr(e, "errno", None)
            if en in (errno.EISDIR, 21) or "is a directory" in str(e).lower():
                is_dir = True
            else:
                raise OSError(f"SFTP remove failed for {path!r}: {e}") from e

    if is_dir:
        for a in sftp_listdir_attr_safe(sftp, path):
            if a.filename in (".", ".."):
                continue
            child = posixpath.join(path, a.filename).replace("\\", "/")
            _sftp_rm_rf(sftp, child)
        try:
            sftp.rmdir(path)
        except (OSError, IOError, Exception) as e:
            raise OSError(f"SFTP rmdir failed for {path!r}: {e}") from e


def _ftp_rm_rf(ftp: FTP, full_path: str) -> None:
    """Remove a remote file or directory tree (ftplib). Quoted CWD/MKD/RMD/DELE for paths with spaces."""
    full_path = full_path.replace("\\", "/").rstrip("/")
    if not full_path:
        return
    parent = posixpath.dirname(full_path) or "/"
    base = posixpath.basename(full_path)
    _ftp_safe_cwd(ftp, parent)
    try:
        _ftp_safe_cwd(ftp, full_path)
    except error_perm:
        _ftp_safe_delete_file(ftp, base)
        return
    entries: List[str] = []
    try:
        for name, _facts in ftp.mlsd():
            if name not in (".", ".."):
                entries.append(name)
    except (error_perm, AttributeError, Exception):
        try:
            for name in ftp.nlst():
                if name not in (".", ".."):
                    entries.append(name)
        except Exception:
            entries = []
    for n in entries:
        _ftp_rm_rf(ftp, posixpath.join(full_path, n).replace("\\", "/"))
        _ftp_safe_cwd(ftp, full_path)
    _ftp_safe_cwd(ftp, parent)
    _ftp_safe_rmd(ftp, base)


def _sftp_abs_remote_path(path: str, cwd: str) -> str:
    """Ensure a path passed to paramiko is absolute (embedded UIs sometimes omit leading '/')."""
    p = (path or "").replace("\\", "/").strip()
    c = (cwd or "/").replace("\\", "/").strip() or "/"
    if not p:
        return posixpath.normpath(c) or "/"
    if p.startswith("/"):
        out = posixpath.normpath(p)
    else:
        base = c.rstrip("/") or ""
        out = posixpath.normpath(f"{base}/{p}" if base else f"/{p}")
    return (out or "/").replace("\\", "/")


def _safe_mode_oct(mode: object) -> str:
    try:
        return oct(int(mode) & 0xFFFFFFFF)
    except (TypeError, ValueError, OverflowError):
        return "—"


def _push_find_folder_history(cfg: Optional[AppConfig], side: str, folder: str) -> None:
    if not cfg:
        return
    p = (folder or "").strip()
    if not p:
        return
    key = "find_folder_history_local" if side == "local" else "find_folder_history_remote"
    lst = getattr(cfg, key, None)
    if not isinstance(lst, list):
        lst = []
    if p in lst:
        lst.remove(p)
    lst.insert(0, p)
    setattr(cfg, key, lst[:_MAX_FIND_FOLDER_HISTORY])
    cfg.save()


def _first_serial_token(raw: Optional[str]) -> str:
    parts = (raw or "").split()
    return parts[0].strip() if parts else ""


def _icon_for_remote_name(name: str, is_dir: bool, icon_provider: QFileIconProvider, style) -> QIcon:
    if name == "..":
        return style.standardIcon(QStyle.SP_FileDialogToParent)
    if is_dir:
        icd = icon_provider.icon(QFileIconProvider.Folder)
        if icd.isNull():
            icd = style.standardIcon(QStyle.SP_DirIcon)
        return icd
    ext = Path(name).suffix.lower()
    cache_key = ext if ext else "<noext>"
    if cache_key in _remote_ext_icon_cache:
        return _remote_ext_icon_cache[cache_key]
    td = Path(tempfile.gettempdir())
    # Extensionless names: use .txt so Windows shows a normal document association instead of a blank shell.
    probe = td / (f"_adbnik_icon{ext}" if ext else "_adbnik_generic.txt")
    ic: QIcon
    try:
        if probe.exists():
            try:
                probe.unlink()
            except OSError:
                pass
        probe.write_bytes(b"")
        ic = icon_provider.icon(QFileInfo(str(probe)))
    except OSError:
        ic = QIcon()
    finally:
        try:
            if probe.exists():
                probe.unlink()
        except OSError:
            pass
    if ic.isNull():
        ic = style.standardIcon(QStyle.SP_FileIcon)
    _remote_ext_icon_cache[cache_key] = ic
    return ic


def _icon_for_local_path(path: Path, icon_provider: QFileIconProvider, style) -> QIcon:
    if path.is_dir():
        ic = icon_provider.icon(QFileIconProvider.Folder)
        if not ic.isNull():
            return ic
        return style.standardIcon(QStyle.SP_DirIcon)
    fi = QFileInfo(str(path))
    ic = icon_provider.icon(fi)
    if not ic.isNull():
        return ic
    return _icon_for_remote_name(path.name, False, icon_provider, style)


@dataclass
class RemoteItem:
    name: str
    is_dir: bool
    permissions: str
    owner: str
    group: str
    size: str
    modified: str


def _ftp_remote_item_mlsd(name: str, facts: dict, full: str) -> tuple:
    """Build RemoteItem from MLSD facts (size, permissions, modify time)."""
    typ = (facts.get("type") or "file").lower()
    is_dir = typ in ("dir", "cdir", "pdir")
    perm = (facts.get("unix.mode") or facts.get("perm") or "").strip()
    sz_raw = facts.get("size", "")
    sz = "0" if is_dir else (str(sz_raw) if sz_raw else "0")
    mt = ""
    mod = facts.get("modify", "")
    if isinstance(mod, str) and len(mod) >= 14:
        try:
            mt = datetime.strptime(mod[:14], "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M")
        except ValueError:
            mt = mod[:19]
    return (RemoteItem(name, is_dir, perm, "", "", sz, mt), full)


def _ftp_remote_item_nlst(ftp: FTP, name: str, full: str) -> tuple:
    """Best-effort size/dir when server only supports NLST."""
    try:
        s = ftp.size(name)
        return (RemoteItem(name, False, "", "", "", str(s), ""), full)
    except Exception:
        pass
    try:
        cur = ftp.pwd()
        try:
            joined = posixpath.join(cur, name).replace("\\", "/") if not name.startswith("/") else name
            _ftp_safe_cwd(ftp, joined)
            _ftp_safe_cwd(ftp, cur)
            return (RemoteItem(name, True, "", "", "", "0", ""), full)
        except Exception:
            try:
                _ftp_safe_cwd(ftp, cur)
            except Exception:
                pass
    except Exception:
        pass
    return (RemoteItem(name, False, "", "", "", "?", ""), full)


def _fmt_local_listing_size(path: Path) -> str:
    """Files: size on disk. Directories: placeholder (not computed — keeps browsing fast)."""
    try:
        if path.is_file():
            return _human_bytes(path.stat().st_size)
    except OSError:
        return ""
    if path.is_dir():
        return "…"
    return ""


def _fmt_mtime(path: Path) -> str:
    try:
        from datetime import datetime

        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    except OSError:
        return ""


def _local_type_label(path: Path) -> str:
    if path.is_dir():
        return "Folder"
    ext = path.suffix.lower().lstrip(".")
    return f"{ext.upper()} file" if ext else "File"


def _remote_type_label(name: str, is_dir: bool) -> str:
    if is_dir:
        return "Folder"
    ext = Path(name).suffix.lower().lstrip(".")
    return f"{ext.upper()} file" if ext else "File"


def _local_name_sort_key(path: Path) -> tuple:
    return (not path.is_dir(), path.name.lower())


def _local_size_sort_key(path: Path) -> tuple:
    if path.is_dir():
        try:
            n = sum(1 for _ in path.iterdir())
        except OSError:
            n = 0
        return (0, n)
    try:
        return (1, path.stat().st_size)
    except OSError:
        return (1, 0)


def _local_mtime_sort_key(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _local_type_sort_key(path: Path) -> tuple:
    return (not path.is_dir(), "folder" if path.is_dir() else "file")


def _remote_name_sort_key(parsed: RemoteItem) -> tuple:
    if parsed.name == "..":
        return (-2,)
    if parsed.is_dir:
        return (0, parsed.name.lower())
    return (1, parsed.name.lower())


def _remote_size_sort_key(parsed: RemoteItem) -> tuple:
    if parsed.name == "..":
        return (-1, 0)
    s = (parsed.size or "").strip()
    if s in ("", "<DIR>", "?"):
        return (1 if not parsed.is_dir else 0, 0)
    try:
        n = int(s)
    except ValueError:
        return (1 if not parsed.is_dir else 0, 0)
    return (1 if not parsed.is_dir else 0, n)


def _remote_mtime_sort_key(parsed: RemoteItem) -> tuple:
    if parsed.name == "..":
        return (-1, "")
    return (0, parsed.modified or "")


def _human_bytes(n: int) -> str:
    if n < 0:
        return "—"
    if n < 1024:
        return f"{n} bytes"
    units = ("KB", "MB", "GB", "TB")
    v = float(n)
    for u in units:
        v /= 1024.0
        if v < 1024.0 or u == "TB":
            return f"{v:.2f} {u} ({n} bytes)"
    return f"{n} bytes"


# Safety cap so a pathological tree cannot run unbounded on the background thread.
_DIR_SIZE_MAX_FILES = 2_000_000


def _dir_size_walk(
    path: Path,
    limit_files: int = _DIR_SIZE_MAX_FILES,
    *,
    interrupt_check: Optional[Callable[[], bool]] = None,
) -> Optional[int]:
    """Recursive sum of regular-file sizes under path. None on error, limit, or interrupt."""
    total = 0
    n = 0
    root = str(path)
    try:
        for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
            if interrupt_check is not None and interrupt_check():
                return None
            for fn in filenames:
                if interrupt_check is not None and interrupt_check():
                    return None
                if n >= limit_files:
                    return None
                fp = os.path.join(dirpath, fn)
                try:
                    st = os.stat(fp)
                    if not S_ISREG(st.st_mode):
                        continue
                    total += st.st_size
                    n += 1
                except OSError:
                    pass
        return total
    except OSError:
        return None


def _show_properties_dialog(parent: QWidget, title: str, rows: List[Tuple[str, str]]) -> None:
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    n = max(len(rows), 1)
    dlg.resize(580, min(520, 100 + n * 26))
    lay = QVBoxLayout(dlg)
    t = QTableWidget(len(rows), 2)
    t.setObjectName("WinScpTable")
    t.setHorizontalHeaderLabels(["Property", "Value"])
    t.verticalHeader().setVisible(False)
    t.setShowGrid(True)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setAlternatingRowColors(True)
    t.setWordWrap(True)
    h = t.horizontalHeader()
    h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
    h.setSectionResizeMode(1, QHeaderView.Stretch)
    for i, (k, v) in enumerate(rows):
        ki = QTableWidgetItem(k)
        ki.setFlags(ki.flags() & ~Qt.ItemIsEditable)
        vi = QTableWidgetItem(v)
        vi.setFlags(vi.flags() & ~Qt.ItemIsEditable)
        if len(v) > 120:
            vi.setToolTip(v)
        t.setItem(i, 0, ki)
        t.setItem(i, 1, vi)
    lay.addWidget(t, 1)
    bb = QDialogButtonBox(QDialogButtonBox.Ok)
    bb.accepted.connect(dlg.accept)
    lay.addWidget(bb)
    dlg.exec_()


class PlainTextEditorDialog(QDialog):
    """Plain text editor: Save writes to disk; optional after_save (e.g. upload). Done = save + close (Accepted)."""

    def __init__(
        self,
        parent: Optional[QWidget],
        path: Path,
        *,
        after_save: Optional[Callable[[Path], bool]] = None,
    ):
        super().__init__(parent)
        self._path = path
        self._after_save = after_save
        self.setWindowTitle(f"Edit — {path.name}")
        self.resize(780, 560)
        lay = QVBoxLayout(self)
        self._edit = QPlainTextEdit()
        self._edit.setFont(QFont("Consolas", 10))
        self._edit.setLineWrapMode(QPlainTextEdit.NoWrap)
        try:
            if path.is_file():
                sz = path.stat().st_size
                if sz > _MAX_INLINE_EDITOR_BYTES:
                    self._edit.setPlainText(
                        f"File is too large for the built-in editor ({_human_bytes(sz)}).\n"
                        "Use Open with default application for better performance."
                    )
                    self._edit.setReadOnly(True)
                else:
                    self._edit.setPlainText(path.read_text(encoding="utf-8-sig", errors="replace"))
        except OSError:
            pass
        lay.addWidget(self._edit)
        btn_row = QHBoxLayout()
        btn_save = QPushButton("Save")
        if after_save:
            btn_save.setToolTip("Save to disk and sync to remote (Ctrl+S)")
        else:
            btn_save.setToolTip("Save to disk (Ctrl+S) — editor stays open")
        btn_save.clicked.connect(self._save_only)
        btn_done = QPushButton("Done")
        btn_done.setDefault(True)
        btn_done.setToolTip("Save, sync if remote edit, and close")
        btn_done.clicked.connect(self._save_and_close)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_done)
        btn_row.addStretch(1)
        btn_row.addWidget(btn_cancel)
        lay.addLayout(btn_row)
        QShortcut(QKeySequence.Save, self, self._save_only)

    def _save_only(self) -> bool:
        tmp = self._path.with_name(self._path.name + ".~tmp")
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            text = self._edit.toPlainText()
            tmp.write_text(text, encoding="utf-8", newline="\n")
            tmp.replace(self._path)
        except OSError as exc:
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            QMessageBox.warning(self, "Save", str(exc))
            return False
        if self._after_save:
            if not self._after_save(self._path):
                return False
            self.setWindowTitle(f"Edit — {self._path.name} (saved & synced)")
        else:
            self.setWindowTitle(f"Edit — {self._path.name} (saved)")
        return True

    def _save_and_close(self) -> None:
        if not self._save_only():
            return
        self.accept()


def _apply_table_chrome(t: QTableWidget, stretch_first: bool = True) -> None:
    t.setObjectName("WinScpTable")
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.verticalHeader().setVisible(False)
    t.setShowGrid(False)
    t.verticalHeader().setDefaultSectionSize(22)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.ExtendedSelection)
    t.setAlternatingRowColors(True)
    t.setFocusPolicy(Qt.StrongFocus)
    t.setSortingEnabled(True)
    h = t.horizontalHeader()
    h.setHighlightSections(False)
    h.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    h.setMinimumSectionSize(72)
    h.setSectionsClickable(True)
    if stretch_first:
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        for c in range(1, t.columnCount()):
            h.setSectionResizeMode(c, QHeaderView.Interactive)
    else:
        h.setStretchLastSection(True)


class _SortTableItem(QTableWidgetItem):
    """Sort by ``sort_key`` (tuple/number); default is visible text."""

    def __init__(self, text: str = "", icon: Optional[QIcon] = None, sort_key=None):
        if icon is not None:
            super().__init__(icon, text)
        else:
            super().__init__(text)
        self._sk = sort_key if sort_key is not None else (text or "")

    def set_sort_key(self, sk) -> None:
        self._sk = sk

    def __lt__(self, other):
        if isinstance(other, _SortTableItem):
            a, b = self._sk, other._sk
            try:
                return a < b
            except Exception:
                pass
        return super().__lt__(other)


def _read_file_bytes_with_retry(path: str, attempts: int = 15, delay: float = 0.35) -> Optional[bytes]:
    """Read file bytes (retries while Word/PDF viewers hold a lock)."""
    last_err: Optional[BaseException] = None
    for _ in range(attempts):
        try:
            with open(path, "rb") as f:
                return f.read()
        except (PermissionError, OSError) as exc:
            last_err = exc
            time.sleep(delay)
    return None


class LocalFileTable(QTableWidget):
    """Local files: drag file:// URLs to remote (push); accept remote drags here (pull)."""

    def __init__(
        self,
        on_paste_paths: Optional[Callable[[List[str]], None]] = None,
        on_drop_remote_pull: Optional[Callable[[List[dict]], None]] = None,
        on_backspace_up: Optional[Callable[[], None]] = None,
    ):
        super().__init__()
        self._on_paste_paths = on_paste_paths
        self._on_drop_remote_pull = on_drop_remote_pull
        self._on_backspace_up = on_backspace_up
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e):
        if self._on_drop_remote_pull and e.mimeData().hasFormat(MIME_REMOTE_PULL):
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if self._on_drop_remote_pull and e.mimeData().hasFormat(MIME_REMOTE_PULL):
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        if self._on_drop_remote_pull and e.mimeData().hasFormat(MIME_REMOTE_PULL):
            try:
                raw = e.mimeData().data(MIME_REMOTE_PULL)
                payload = bytes(raw).decode("utf-8")
                infos = json.loads(payload)
                if isinstance(infos, list):
                    self._on_drop_remote_pull(infos)
            except (json.JSONDecodeError, OSError, UnicodeDecodeError):
                pass
            e.acceptProposedAction()
            return
        super().dropEvent(e)

    def keyPressEvent(self, ev):
        if (
            ev.key() == Qt.Key_Backspace
            and not (ev.modifiers() & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))
        ):
            if self._on_backspace_up:
                self._on_backspace_up()
            else:
                p = self.parentWidget()
                while p is not None:
                    if hasattr(p, "local_up"):
                        p.local_up()
                        break
                    p = p.parentWidget()
            ev.accept()
            return
        if (ev.modifiers() & Qt.ControlModifier) and ev.key() in (Qt.Key_C, Qt.Key_Insert):
            paths: List[str] = []
            for r in sorted({i.row() for i in self.selectedItems()}):
                it = self.item(r, 0)
                if it:
                    p = it.data(Qt.UserRole)
                    if p:
                        paths.append(str(p))
            if paths:
                QApplication.clipboard().setText("\n".join(paths))
            ev.accept()
            return
        if ev.key() == Qt.Key_V and (ev.modifiers() & Qt.ControlModifier) and self._on_paste_paths:
            raw = QApplication.clipboard().text()
            lines = [ln.strip() for ln in raw.replace("\r\n", "\n").split("\n") if ln.strip()]
            good: List[str] = []
            for ln in lines:
                pp = Path(ln)
                if pp.exists() and (pp.is_file() or pp.is_dir()):
                    good.append(str(pp.resolve()))
            if good:
                self._on_paste_paths(good)
                ev.accept()
                return
        if ev.key() == Qt.Key_A and (ev.modifiers() & Qt.ControlModifier):
            self.selectAll()
            ev.accept()
            return
        super().keyPressEvent(ev)

    def startDrag(self, supportedActions):
        rows = sorted({i.row() for i in self.selectedItems()})
        urls: List[QUrl] = []
        for r in rows:
            it = self.item(r, 0)
            if not it:
                continue
            p = it.data(Qt.UserRole)
            if not p:
                continue
            lp = Path(p)
            if lp.exists():
                urls.append(QUrl.fromLocalFile(str(lp.resolve())))
        if not urls:
            return
        m = QMimeData()
        m.setUrls(urls)
        drag = QDrag(self)
        drag.setMimeData(m)
        drag.exec_(Qt.CopyAction)


class RemoteFileTable(QTableWidget):
    """Remote listing: accept local file drops to Push into current remote folder."""

    def __init__(
        self,
        activated_slot,
        on_drop_local_paths: Callable[[List[str]], None],
        on_paste_paths: Optional[Callable[[List[str]], None]] = None,
        on_backspace_up: Optional[Callable[[], None]] = None,
    ):
        super().__init__()
        self._on_drop_local_paths = on_drop_local_paths
        self._on_paste_paths = on_paste_paths
        self._on_backspace_up = on_backspace_up
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels(["Name", "Size", "Permissions", "Date modified", "Type"])
        _apply_table_chrome(self, stretch_first=True)
        self.setIconSize(QSize(24, 24))
        self.itemActivated.connect(activated_slot)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.CopyAction)
        self.setDropIndicatorShown(True)

    def startDrag(self, supportedActions):
        rows = sorted({i.row() for i in self.selectedItems()})
        infos: List[dict] = []
        for r in rows:
            it = self.item(r, 0)
            if not it or it.text() == "..":
                continue
            data = it.data(Qt.UserRole) or {}
            p = data.get("path")
            if p:
                infos.append({"path": str(p), "is_dir": bool(data.get("is_dir"))})
        if not infos:
            return
        m = QMimeData()
        m.setData(MIME_REMOTE_PULL, QByteArray(json.dumps(infos).encode("utf-8")))
        drag = QDrag(self)
        drag.setMimeData(m)
        drag.exec_(Qt.CopyAction)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
            if paths:
                self._on_drop_local_paths(paths)
            e.acceptProposedAction()
            return
        super().dropEvent(e)

    def keyPressEvent(self, ev):
        if (
            ev.key() == Qt.Key_Backspace
            and not (ev.modifiers() & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))
        ):
            if self._on_backspace_up:
                self._on_backspace_up()
            else:
                p = self.parentWidget()
                while p is not None:
                    if hasattr(p, "remote_up"):
                        p.remote_up()
                        break
                    p = p.parentWidget()
            ev.accept()
            return
        if (ev.modifiers() & Qt.ControlModifier) and ev.key() in (Qt.Key_C, Qt.Key_Insert):
            paths: List[str] = []
            for r in sorted({i.row() for i in self.selectedItems()}):
                it = self.item(r, 0)
                if it:
                    info = it.data(Qt.UserRole) or {}
                    p = info.get("path")
                    if p:
                        paths.append(str(p))
            if paths:
                QApplication.clipboard().setText("\n".join(paths))
            ev.accept()
            return
        if ev.key() == Qt.Key_V and (ev.modifiers() & Qt.ControlModifier) and self._on_paste_paths:
            raw = QApplication.clipboard().text()
            lines = [ln.strip() for ln in raw.replace("\r\n", "\n").split("\n") if ln.strip()]
            good: List[str] = []
            for ln in lines:
                pp = Path(ln)
                if pp.exists() and (pp.is_file() or pp.is_dir()):
                    good.append(str(pp.resolve()))
            if good:
                self._on_paste_paths(good)
                ev.accept()
                return
        if ev.key() == Qt.Key_A and (ev.modifiers() & Qt.ControlModifier):
            self.selectAll()
            ev.accept()
            return
        super().keyPressEvent(ev)


_MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def _strip_ls_datetime_name_tokens(rtoks: List[str]) -> List[str]:
    """Remove leading ls date/time tokens; remainder is the file name."""
    if not rtoks:
        return []
    t = list(rtoks)
    if len(t[0]) >= 10 and t[0][4:5] == "-":
        t.pop(0)
        if t and re.match(r"^\d{1,2}:\d{2}$", t[0]):
            t.pop(0)
        return t
    if len(t[0]) == 3 and t[0] in _MONTHS:
        t.pop(0)
        if t and t[0].isdigit():
            t.pop(0)
        if t and (len(t[0]) == 4 and t[0].isdigit()):
            t.pop(0)
        elif t and re.match(r"^\d{1,2}:\d{2}$", t[0]):
            t.pop(0)
        return t
    return t


def _parse_ls_line(line: str) -> Optional[RemoteItem]:
    line = line.strip()
    if not line or line.startswith("total "):
        return None
    m = re.match(
        r"^([drwxlsStT\-\+]{10})\s+(\d+)\s+(\S+)\s+(\S+)\s+(\d+)\s+(.+)$",
        line,
    )
    if not m:
        return None
    perm, _nlink, user, group, size_s, rest = m.groups()
    is_dir = perm.startswith("d")
    sym = ""
    rest_main = rest.strip()
    if " -> " in rest_main:
        rest_main, sym = rest_main.split(" -> ", 1)
        sym = " -> " + sym.strip()
    rtoks = rest_main.split()
    name_toks = _strip_ls_datetime_name_tokens(rtoks)
    name = (" ".join(name_toks) if name_toks else "") + sym
    if not name.strip():
        return None
    first_tok = name.split(None, 1)[0]
    if first_tok in (".", "..") and " -> " not in name:
        return None
    mtime = rest_main[: min(48, len(rest_main))]
    return RemoteItem(name.strip(), is_dir, perm, user, group, size_s, mtime)


def _fill_remote_table(
    table: QTableWidget, rows: List[tuple], style, icon_provider: QFileIconProvider
) -> None:
    table.setUpdatesEnabled(False)
    try:
        table.setSortingEnabled(False)
        table.setIconSize(QSize(24, 24))
        table.setRowCount(len(rows))
        for i, (parsed, full_path) in enumerate(rows):
            icon = _icon_for_remote_name(parsed.name, parsed.is_dir, icon_provider, style)
            name_item = _SortTableItem(parsed.name, icon, sort_key=_remote_name_sort_key(parsed))
            name_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            table.setItem(i, 0, name_item)
            if parsed.name == "..":
                size_cell = "—"
            elif parsed.is_dir:
                size_cell = "…"
            else:
                raw = (parsed.size or "").strip()
                try:
                    size_cell = _human_bytes(int(raw))
                except ValueError:
                    size_cell = raw if raw else "—"
            table.setItem(i, 1, _SortTableItem(size_cell, sort_key=_remote_size_sort_key(parsed)))
            table.setItem(i, 2, _SortTableItem(parsed.permissions, sort_key=parsed.permissions))
            table.setItem(
                i,
                3,
                _SortTableItem(parsed.modified, sort_key=_remote_mtime_sort_key(parsed)),
            )
            typ = _remote_type_label(parsed.name, parsed.is_dir)
            table.setItem(i, 4, _SortTableItem(typ, sort_key=typ.lower()))
            table.item(i, 0).setData(Qt.UserRole, {"path": full_path, "is_dir": parsed.is_dir})
        table.setSortingEnabled(True)
        table.sortByColumn(0, Qt.AscendingOrder)
    finally:
        table.setUpdatesEnabled(True)


class _FindFilesSearchThread(QThread):
    """Runs search off the UI thread so large trees do not freeze the window."""

    finished_ok = pyqtSignal(list)
    finished_err = pyqtSignal(str)

    def __init__(
        self,
        page: "ExplorerSessionPage",
        side: str,
        folder: str,
        needle: str,
        parent: Optional[QWidget] = None,
    ):
        # Parent to the dialog so the thread is torn down after cancel/wait in closeEvent,
        # not when the explorer page is destroyed while run() is still busy.
        super().__init__(parent)
        self._page = page
        self._side = side
        self._folder = folder
        self._needle = needle

    def run(self) -> None:
        try:
            if self._side == "local":
                paths = self._page.find_local_matches(
                    self._folder, self._needle, interrupt_check=self.isInterruptionRequested
                )
                self.finished_ok.emit([str(p) for p in paths])
            else:
                paths = self._page.find_remote_matches(
                    self._folder, self._needle, interrupt_check=self.isInterruptionRequested
                )
                self.finished_ok.emit(list(paths))
        except Exception as exc:
            self.finished_err.emit(str(exc))


class _AdbCommandThread(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    prep_done = pyqtSignal(str)
    done = pyqtSignal(int, str)

    def __init__(
        self,
        adb_path: str,
        adb_args: List[str],
        timeout: int = 600,
        *,
        adb_shell_prefix: Optional[List[str]] = None,
        poll_total_bytes: int = 0,
        poll_mode: str = "",
        poll_remote: str = "",
        poll_local: str = "",
        prep_measure_push_dir: Optional[str] = None,
        prep_measure_pull: Optional[Tuple[str, str]] = None,
        cancel_event: Optional[threading.Event] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._adb_path = adb_path
        self._adb_args = list(adb_args)
        self._timeout = timeout
        self._adb_shell_prefix = list(adb_shell_prefix or [])
        self._poll_total_bytes = int(poll_total_bytes or 0)
        self._poll_mode = (poll_mode or "").strip()
        self._poll_remote = poll_remote
        self._poll_local = poll_local
        self._prep_measure_push_dir = (prep_measure_push_dir or "").strip() or None
        self._prep_measure_pull = prep_measure_pull
        self._cancel_event = cancel_event

    def run(self) -> None:
        last_pct = [0]
        cancel_ev = self._cancel_event

        def on_pct(p: int) -> None:
            if p < 0:
                self.progress.emit(-1)
                return
            if 0 <= p <= 100 and p >= last_pct[0]:
                last_pct[0] = p
                self.progress.emit(p)

        def on_line(line: str) -> None:
            txt = (line or "").strip()
            if txt:
                self.status.emit(txt[:180])

        poll_total_bytes = int(self._poll_total_bytes or 0)
        poll_mode = (self._poll_mode or "").strip()
        poll_remote = self._poll_remote
        poll_local = self._poll_local

        def _cancelled() -> bool:
            return bool(cancel_ev is not None and cancel_ev.is_set()) or self.isInterruptionRequested()

        if self._prep_measure_push_dir:
            if _cancelled():
                self.done.emit(130, "Cancelled")
                return
            self.status.emit("Measuring local folder size (this can take a while)…")
            self.progress.emit(0)
            try:
                lp = Path(self._prep_measure_push_dir)
                walked = _dir_size_walk(lp, interrupt_check=_cancelled)
                if _cancelled():
                    self.done.emit(130, "Cancelled")
                    return
                poll_total_bytes = int(walked or 0)
                poll_mode = "push_dir" if poll_total_bytes > 0 else ""
            except OSError as exc:
                self.done.emit(1, f"Could not measure folder: {exc}")
                return

        if self._prep_measure_pull:
            if _cancelled():
                self.done.emit(130, "Cancelled")
                return
            src, dest = self._prep_measure_pull
            self.status.emit("Measuring remote size…")
            self.progress.emit(0)
            pbytes: Optional[int] = None
            pkind = "unknown"
            try:
                pbytes, pkind = adb_remote_probe_size(self._adb_path, self._adb_shell_prefix, src)
            except Exception as exc:
                self.status.emit(f"Remote size probe failed: {exc}"[:180])
            if _cancelled():
                self.done.emit(130, "Cancelled")
                return
            poll_total_bytes = int(pbytes or 0)
            poll_remote = ""
            poll_local = dest
            poll_mode = ""
            if pkind == "file" and poll_total_bytes > 0:
                poll_mode = "pull_file"
            elif pkind == "dir" and poll_total_bytes > 0:
                poll_mode = "pull_dir"
            else:
                poll_mode = ""

        did_prep = bool(self._prep_measure_push_dir) or bool(self._prep_measure_pull)
        if did_prep:
            if poll_total_bytes > 0:
                self.prep_done.emit(f"≈ {_human_bytes(int(poll_total_bytes))} total (measured)")
            else:
                self.prep_done.emit("Size not estimated — using adb output for progress")

        code, out, err = run_adb_with_line_callback(
            self._adb_path,
            self._adb_args,
            timeout=self._timeout,
            on_line=on_line,
            on_percent=on_pct,
            poll_total_bytes=poll_total_bytes,
            poll_mode=poll_mode,
            poll_remote=poll_remote,
            poll_local=poll_local,
            adb_shell_prefix=self._adb_shell_prefix,
            cancel_event=cancel_ev,
        )
        msg = (err or out or "").strip()
        self.done.emit(code, msg)


class _RemoteTransferThread(QThread):
    progress = pyqtSignal(int, str)
    done = pyqtSignal(bool, str, str)

    def __init__(self, *, kind: str, mode: str, items: List[dict], remote_path: str, local_path: str, creds: dict):
        super().__init__(None)
        self._kind = kind
        self._mode = mode
        self._items = list(items)
        self._remote_path = remote_path
        self._local_path = local_path
        self._creds = dict(creds or {})

    def run(self) -> None:
        try:
            if self._kind == "sftp":
                self._run_sftp()
            elif self._kind == "ftp":
                self._run_ftp()
            else:
                self.done.emit(False, "", f"Unsupported transfer kind: {self._kind}")
        except Exception as exc:
            self.done.emit(False, "", str(exc))

    def _progress(self, idx: int, total: int, pct: int, msg: str) -> None:
        base = int((idx * 100) / max(total, 1))
        span = max(1, int(100 / max(total, 1)))
        v = min(99, base + int((span * max(0, min(100, pct))) / 100))
        self.progress.emit(v, msg)

    def _run_sftp(self) -> None:
        t, sftp, err = connect_sftp(
            self._creds.get("host", ""),
            int(self._creds.get("port", 22) or 22),
            self._creds.get("user", ""),
            self._creds.get("password", ""),
            timeout=60,
        )
        if err or sftp is None:
            self.done.emit(False, "", err or "SFTP connection failed")
            return
        last = ""
        ok = 0
        total = max(len(self._items), 1)
        try:
            for idx, it in enumerate(self._items):
                if self._mode == "push":
                    lp = Path(str(it.get("local", "")))
                    if not lp.exists():
                        continue
                    rp = posixpath.join(self._remote_path.rstrip("/"), lp.name).replace("\\", "/")
                    self._sftp_put(sftp, str(lp), rp, idx, total)
                    last = lp.name
                    ok += 1
                else:
                    rp = str(it.get("remote", "")).replace("\\", "/")
                    if not rp:
                        continue
                    name = posixpath.basename(rp.rstrip("/")) or "item"
                    lp = str(Path(self._local_path) / name)
                    self._sftp_get(sftp, rp, lp, idx, total)
                    last = name
                    ok += 1
            self.done.emit(True, last, f"Transferred {ok} item(s).")
        finally:
            disconnect_sftp(t, sftp)

    def _run_ftp(self) -> None:
        ftp, err = connect_ftp(
            self._creds.get("host", ""),
            int(self._creds.get("port", 21) or 21),
            self._creds.get("user", ""),
            self._creds.get("password", ""),
            timeout=60,
        )
        if err or ftp is None:
            self.done.emit(False, "", err or "FTP connection failed")
            return
        last = ""
        ok = 0
        total = max(len(self._items), 1)
        try:
            for idx, it in enumerate(self._items):
                if self._mode == "push":
                    lp = Path(str(it.get("local", "")))
                    if not lp.exists():
                        continue
                    self._ftp_put(ftp, str(lp), self._remote_path, idx, total)
                    last = lp.name
                    ok += 1
                else:
                    rp = str(it.get("remote", "")).replace("\\", "/")
                    if not rp:
                        continue
                    name = posixpath.basename(rp.rstrip("/")) or "item"
                    lp = str(Path(self._local_path) / name)
                    self._ftp_get(ftp, rp, lp, idx, total, is_dir=bool(it.get("is_dir")))
                    last = name
                    ok += 1
            self.done.emit(True, last, f"Transferred {ok} item(s).")
        finally:
            disconnect_ftp(ftp)

    def _sftp_put(self, sftp, local_path: str, remote_path: str, idx: int, total: int) -> None:
        self._sftp_mkdir_p(sftp, posixpath.dirname(remote_path) or "/")
        if Path(local_path).is_dir():
            for root, _dirs, files in os.walk(local_path):
                rel = Path(root).relative_to(local_path)
                rel_s = "" if str(rel) == "." else str(rel).replace("\\", "/")
                base_remote = posixpath.join(remote_path, rel_s).replace("//", "/") if rel_s else remote_path
                self._sftp_mkdir_p(sftp, base_remote)
                for fn in files:
                    lp = str(Path(root) / fn)
                    rp = posixpath.join(base_remote, fn).replace("\\", "/")
                    self._sftp_put_file(sftp, lp, rp, idx, total)
        else:
            self._sftp_put_file(sftp, local_path, remote_path, idx, total)

    def _sftp_put_file(self, sftp, local_file: str, remote_file: str, idx: int, total: int) -> None:
        def _cb(sent: int, size: int) -> None:
            pct = int((100 * sent) / max(size, 1)) if size else 0
            self._progress(idx, total, pct, f"Uploading {Path(local_file).name} ({pct}%)")
        # Larger SFTP chunks via remote_clients (MAX_REQUEST_SIZE); confirm=False skips post-stat verify for speed.
        sftp.put(local_file, remote_file, callback=_cb, confirm=False)

    def _sftp_get(self, sftp, remote_path: str, local_path: str, idx: int, total: int) -> None:
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            st = sftp.stat(remote_path)
            if _sftp_is_dir(st.st_mode):
                root_local = Path(local_path)
                root_local.mkdir(parents=True, exist_ok=True)
                for a in sftp_listdir_attr_safe(sftp, remote_path):
                    if a.filename in (".", ".."):
                        continue
                    self._sftp_get(
                        sftp,
                        posixpath.join(remote_path, a.filename).replace("\\", "/"),
                        str(root_local / a.filename),
                        idx,
                        total,
                    )
                return
        except Exception:
            pass
        def _cb(sent: int, size: int) -> None:
            pct = int((100 * sent) / max(size, 1)) if size else 0
            self._progress(idx, total, pct, f"Downloading {Path(local_path).name} ({pct}%)")
        sftp.get(remote_path, local_path, callback=_cb)

    def _sftp_mkdir_p(self, sftp, remote_dir: str) -> None:
        r = remote_dir.replace("\\", "/").rstrip("/")
        if not r or r == "/":
            return
        acc = ""
        for p in [x for x in r.split("/") if x]:
            acc = f"{acc}/{p}" if acc else f"/{p}"
            try:
                sftp.stat(acc)
                continue
            except Exception:
                pass
            try:
                sftp.mkdir(acc)
            except Exception as e:
                if not _sftp_is_exists_err(e):
                    raise

    def _ftp_put(self, ftp, local_path: str, remote_dir: str, idx: int, total: int) -> None:
        if Path(local_path).is_dir():
            base_remote = posixpath.join(remote_dir.rstrip("/"), Path(local_path).name).replace("\\", "/")
            for root, _dirs, files in os.walk(local_path):
                rel = Path(root).relative_to(local_path)
                rel_s = "" if str(rel) == "." else str(rel).replace("\\", "/")
                cur_remote = posixpath.join(base_remote, rel_s).replace("//", "/") if rel_s else base_remote
                self._ftp_ensure_dir(ftp, cur_remote)
                for fn in files:
                    self._ftp_put_file(ftp, str(Path(root) / fn), cur_remote, idx, total)
        else:
            self._ftp_put_file(ftp, local_path, remote_dir, idx, total)

    def _ftp_put_file(self, ftp, local_file: str, remote_dir: str, idx: int, total: int) -> None:
        self._ftp_ensure_dir(ftp, remote_dir)
        size = max(Path(local_file).stat().st_size, 1)
        sent = [0]
        name = Path(local_file).name
        def _cb(block: bytes) -> None:
            sent[0] += len(block)
            pct = int((100 * sent[0]) / size)
            self._progress(idx, total, pct, f"Uploading {name} ({pct}%)")
        with open(local_file, "rb") as f:
            ftp.storbinary(f"STOR {_ftp_quote_token(name)}", f, blocksize=65536, callback=_cb)

    def _ftp_get(self, ftp, remote_path: str, local_path: str, idx: int, total: int, *, is_dir: bool = False) -> None:
        if is_dir:
            root = Path(local_path)
            root.mkdir(parents=True, exist_ok=True)
            self._ftp_get_tree(ftp, remote_path.rstrip("/"), root, idx, total)
            return
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        parent = posixpath.dirname(remote_path) or "/"
        name = posixpath.basename(remote_path)
        self._ftp_ensure_dir(ftp, parent)
        with open(local_path, "wb") as out:
            ftp.retrbinary(f"RETR {_ftp_quote_token(name)}", out.write)
        self._progress(idx, total, 100, f"Downloaded {Path(local_path).name}")

    def _ftp_get_tree(self, ftp, remote_path: str, local_root: Path, idx: int, total: int) -> None:
        try:
            _ftp_safe_cwd(ftp, remote_path)
        except Exception:
            return
        try:
            entries = list(ftp.mlsd())
        except Exception:
            entries = []
            try:
                for n in ftp.nlst():
                    if n not in (".", ".."):
                        entries.append((n, {"type": "file"}))
            except Exception:
                return
        for n, facts in entries:
            if n in (".", ".."):
                continue
            rp = posixpath.join(remote_path, n).replace("\\", "/")
            lp = local_root / n
            if bool(facts) and facts.get("type") == "dir":
                lp.mkdir(parents=True, exist_ok=True)
                self._ftp_get_tree(ftp, rp, lp, idx, total)
            else:
                self._ftp_get(ftp, rp, str(lp), idx, total, is_dir=False)

    def _ftp_ensure_dir(self, ftp, remote_dir: str) -> None:
        r = remote_dir.replace("\\", "/").rstrip("/")
        if r in ("", "/"):
            try:
                ftp.cwd("/")
            except Exception:
                pass
            return
        try:
            _ftp_safe_cwd(ftp, r)
            return
        except Exception:
            pass
        parent = posixpath.dirname(r) or "/"
        base = posixpath.basename(r)
        self._ftp_ensure_dir(ftp, parent)
        try:
            _ftp_safe_mkd(ftp, base)
        except Exception:
            pass
        try:
            _ftp_cwd_segment(ftp, base)
        except Exception:
            pass


class _RemoteListThread(QThread):
    done = pyqtSignal(object, str)

    def __init__(self, *, kind: str, adb_path: str, adb_args: List[str], remote_path: str, creds: dict):
        super().__init__(None)
        self._kind = kind
        self._adb_path = adb_path
        self._adb_args = list(adb_args)
        self._remote_path = remote_path
        self._creds = dict(creds or {})

    def run(self) -> None:
        rows = []
        err = ""
        try:
            rp = (self._remote_path or "").strip() or "/"
            parent = posixpath.dirname(rp.rstrip("/")) or "/"
            rows.append((RemoteItem("..", True, "", "", "", "", ""), parent))
            if self._kind == "adb":
                safe_rp = rp.replace("\\", "\\\\").replace('"', '\\"')
                code, stdout, stderr = run_adb(
                    self._adb_path,
                    [*self._adb_args, "shell", f'ls -la "{safe_rp}"'],
                )
                if code != 0:
                    err = (stderr or "ADB list failed.").strip()
                    self.done.emit(rows, err)
                    return
                for line in stdout.splitlines():
                    parsed = _parse_ls_line(line)
                    if not parsed:
                        continue
                    rows.append((parsed, f"{rp.rstrip('/')}/{parsed.name}".replace("//", "/")))
                self.done.emit(rows, "")
                return
            if self._kind == "sftp":
                t, sftp, e = connect_sftp(
                    self._creds.get("host", ""),
                    int(self._creds.get("port", 22) or 22),
                    self._creds.get("user", ""),
                    self._creds.get("password", ""),
                    timeout=45,
                )
                if e or sftp is None:
                    self.done.emit(rows, e or "SFTP connection failed.")
                    return
                try:
                    attrs = sftp_listdir_attr_safe(sftp, rp.rstrip("/") or "/")
                    rp_base = rp.rstrip("/") or "/"
                    for a in sorted(
                        attrs, key=lambda x: (not _sftp_entry_is_dir(sftp, rp_base, x), x.filename.lower())
                    ):
                        name = a.filename
                        if name in (".", ".."):
                            continue
                        is_dir = _sftp_entry_is_dir(sftp, rp_base, a)
                        full = posixpath.join(rp.rstrip("/") or "/", name).replace("\\", "/")
                        perm = _sftp_perm_str(a.st_mode)
                        sz = str(a.st_size)
                        mt = datetime.fromtimestamp(a.st_mtime).strftime("%Y-%m-%d %H:%M") if a.st_mtime else ""
                        rows.append((RemoteItem(name, is_dir, perm, "", "", sz, mt), full))
                    self.done.emit(rows, "")
                finally:
                    disconnect_sftp(t, sftp)
                return
            if self._kind == "ftp":
                ftp, e = connect_ftp(
                    self._creds.get("host", ""),
                    int(self._creds.get("port", 21) or 21),
                    self._creds.get("user", ""),
                    self._creds.get("password", ""),
                    timeout=45,
                )
                if e or ftp is None:
                    self.done.emit(rows, e or "FTP connection failed.")
                    return
                try:
                    _ftp_safe_cwd(ftp, rp.rstrip("/") or "/")
                    try:
                        raw_mlsd = list(ftp.mlsd())

                        def _ftp_mlsd_sort_key(t: tuple) -> tuple:
                            name, facts = t[0], t[1]
                            if name in (".", ".."):
                                return (0, name.lower())
                            fd = facts if isinstance(facts, dict) else {}
                            is_d = fd.get("type") == "dir"
                            return (1 if is_d else 2, name.lower())

                        for name, facts in sorted(raw_mlsd, key=_ftp_mlsd_sort_key):
                            if name in (".", ".."):
                                continue
                            full = posixpath.join(rp.rstrip("/") or "/", name).replace("\\", "/")
                            rows.append(_ftp_remote_item_mlsd(name, facts, full))
                    except (error_perm, AttributeError):
                        for name in sorted(ftp.nlst(), key=str.lower):
                            if name in (".", ".."):
                                continue
                            full = posixpath.join(rp.rstrip("/") or "/", name).replace("\\", "/")
                            rows.append(_ftp_remote_item_nlst(ftp, name, full))
                    self.done.emit(rows, "")
                finally:
                    disconnect_ftp(ftp)
                return
            self.done.emit(rows, f"Unsupported remote kind: {self._kind}")
        except Exception as exc:
            self.done.emit(rows, str(exc))


class _DeleteThread(QThread):
    """Delete local or ADB paths with determinate progress (0–100%) where measurable."""

    done = pyqtSignal(bool, str)
    progress = pyqtSignal(int)

    def __init__(
        self,
        *,
        mode: str,
        target: str,
        is_dir: bool = False,
        adb_path: str = "",
        adb_args: Optional[List[str]] = None,
        cancel_event: Optional[threading.Event] = None,
    ):
        super().__init__(None)
        self._mode = mode
        self._target = target
        self._is_dir = is_dir
        self._adb_path = adb_path
        self._adb_args = list(adb_args or [])
        self._cancel_event = cancel_event

    def _cancelled(self) -> bool:
        return bool(self._cancel_event is not None and self._cancel_event.is_set()) or self.isInterruptionRequested()

    def run(self) -> None:
        try:
            if self._mode == "local":
                self._run_local_delete()
                return
            if self._mode == "adb":
                self._run_adb_delete()
                return
            self.done.emit(False, "Unsupported delete mode")
        except Exception as exc:
            self.done.emit(False, str(exc))

    def _run_local_delete(self) -> None:
        p = Path(self._target)
        if not p.exists():
            self.progress.emit(100)
            self.done.emit(True, "")
            return
        if p.is_file() or (p.is_symlink() and not p.is_dir()):
            try:
                p.unlink()
            except OSError as exc:
                self.done.emit(False, str(exc))
                return
            self.progress.emit(100)
            self.done.emit(True, "")
            return
        if not p.is_dir():
            try:
                p.unlink()
            except OSError as exc:
                self.done.emit(False, str(exc))
                return
            self.progress.emit(100)
            self.done.emit(True, "")
            return
        total = _dir_size_walk(p, interrupt_check=self._cancelled)
        if self._cancelled():
            self.done.emit(False, "Cancelled.")
            return
        if total is None or total <= 0:
            try:
                shutil.rmtree(p)
            except OSError as exc:
                self.done.emit(False, str(exc))
                return
            self.progress.emit(100)
            self.done.emit(True, "")
            return
        deleted = 0
        root = str(p)
        last_pct_shown = -1
        for dirpath, _dirnames, filenames in os.walk(root, topdown=False):
            if self._cancelled():
                self.done.emit(False, "Cancelled.")
                return
            for name in filenames:
                fp = os.path.join(dirpath, name)
                try:
                    st = os.stat(fp)
                    if not S_ISREG(st.st_mode):
                        continue
                    sz = int(st.st_size)
                    os.unlink(fp)
                    deleted += sz
                    pct = int(min(99, deleted * 100 // max(total, 1)))
                    if pct != last_pct_shown:
                        self.progress.emit(pct)
                        last_pct_shown = pct
                except OSError:
                    pass
            try:
                os.rmdir(dirpath)
            except OSError:
                pass
        self.progress.emit(100)
        self.done.emit(True, "")

    def _run_adb_delete(self) -> None:
        tgt = (self._target or "").strip()
        if not tgt:
            self.done.emit(False, "Empty path.")
            return
        initial = adb_remote_path_bytes_now(self._adb_path, self._adb_args, tgt)
        if initial is None:
            self.progress.emit(100)
            self.done.emit(True, "")
            return
        proc = adb_start_rm_rf(self._adb_path, self._adb_args, tgt)
        last_emit = -1
        try:
            while proc.poll() is None:
                if self._cancelled():
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    self.done.emit(False, "Cancelled.")
                    return
                cur = adb_remote_path_bytes_now(self._adb_path, self._adb_args, tgt)
                if cur is None:
                    pct = 100
                elif initial <= 0:
                    pct = 0
                else:
                    pct = int(min(99, max(0, (initial - cur) * 100 // initial)))
                pct = max(last_emit, pct)
                if pct != last_emit:
                    self.progress.emit(pct)
                    last_emit = pct
                time.sleep(0.65)
            code = int(proc.returncode or 0)
            self.progress.emit(100)
            self.done.emit(code == 0, "")
        except Exception as exc:
            try:
                proc.kill()
            except Exception:
                pass
            self.done.emit(False, str(exc))
        finally:
            try:
                unregister_adb_process(proc)
            except Exception:
                pass


class _SftpFtpDeleteThread(QThread):
    """SFTP/FTP recursive delete off the UI thread (paramiko/ftplib calls stay in one thread per run)."""

    done = pyqtSignal(bool, str)

    def __init__(self, *, kind: str, sftp: Any = None, ftp: Optional[FTP] = None, path: str):
        super().__init__(None)
        self._kind = (kind or "").strip().lower()
        self._sftp = sftp
        self._ftp = ftp
        self._path = path

    def run(self) -> None:
        try:
            if self._kind == "sftp":
                _sftp_rm_rf(self._sftp, self._path)
            elif self._kind == "ftp":
                _ftp_rm_rf(self._ftp, self._path)
            else:
                self.done.emit(False, f"Unsupported delete kind: {self._kind}")
                return
            self.done.emit(True, "")
        except Exception as exc:
            self.done.emit(False, str(exc))


_FIND_FILES_DIALOG_QSS_DARK = """
QDialog#FindFilesDialog {
    background-color: #0f172a;
}
QDialog#FindFilesDialog QLabel {
    color: #e2e8f0;
}
QDialog#FindFilesDialog QLineEdit, QDialog#FindFilesDialog QComboBox {
    background-color: #1e293b;
    color: #f1f5f9;
    border: 1px solid #334155;
    border-radius: 4px;
    padding: 4px 8px;
}
QDialog#FindFilesDialog QListWidget#FindFilesResultList {
    background-color: #1e293b;
    color: #e2e8f0;
    alternate-background-color: #334155;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
}
QDialog#FindFilesDialog QListWidget#FindFilesResultList::item {
    color: #e2e8f0;
    padding: 2px 4px;
}
QDialog#FindFilesDialog QListWidget#FindFilesResultList::item:alternate {
    background-color: #334155;
    color: #e2e8f0;
}
"""


class FindFilesDialog(QDialog):
    """WinSCP-style: folder + name pattern + result list in one dialog."""

    def __init__(self, page: "ExplorerSessionPage", side: str, parent=None):
        super().__init__(parent)
        self.setObjectName("FindFilesDialog")
        self._page = page
        self._side = side  # "local" | "remote"
        self._cfg: Optional[AppConfig] = getattr(page, "_app_config", None)
        self._search_thread: Optional[_FindFilesSearchThread] = None
        self._last_search_folder = ""
        self.setWindowTitle("Find files" if side == "local" else "Find files on device")
        self.resize(560, 420)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.folder_combo = ExpandAllComboBox()
        self.folder_combo.setEditable(True)
        self.folder_combo.setMaxVisibleItems(16)
        self.folder_combo.setMinimumWidth(360)
        hist_key = "find_folder_history_local" if side == "local" else "find_folder_history_remote"
        hist: List[str] = []
        if self._cfg and isinstance(getattr(self._cfg, hist_key, None), list):
            hist = [str(x) for x in getattr(self._cfg, hist_key) if str(x).strip()]
        cur = (page.local_path if side == "local" else page.remote_path).strip()
        seen = set()
        if cur:
            self.folder_combo.addItem(cur)
            seen.add(cur)
        for p in hist:
            ps = str(p).strip()
            if ps and ps not in seen:
                self.folder_combo.addItem(ps)
                seen.add(ps)
        self.folder_combo.setCurrentIndex(0)
        self.pattern_edit = QLineEdit()
        self.pattern_edit.setPlaceholderText("Name contains…")
        form.addRow("Folder:", self.folder_combo)
        form.addRow("Name contains:", self.pattern_edit)
        lay.addLayout(form)
        row = QHBoxLayout()
        self._btn_browse = QPushButton("Browse…")
        self._btn_browse.clicked.connect(self._browse_folder)
        if side != "local":
            self._btn_browse.setVisible(False)
        row.addWidget(self._btn_browse)
        self._btn_search = QPushButton("Search")
        self._btn_search.setIcon(self.style().standardIcon(QStyle.SP_FileDialogContentsView))
        self._btn_search.clicked.connect(self._run_search)
        row.addWidget(self._btn_search)
        row.addStretch(1)
        lay.addLayout(row)
        self._list = QListWidget()
        self._list.setObjectName("FindFilesResultList")
        self._list.setAlternatingRowColors(True)
        self._list.itemDoubleClicked.connect(self._go_selected)
        lay.addWidget(self._list, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        self._btn_go = bb.addButton("Go to selected", QDialogButtonBox.ActionRole)
        self._btn_go.clicked.connect(self._go_selected)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        dark = bool(self._cfg and getattr(self._cfg, "dark_theme", False))
        if dark:
            self.setStyleSheet(_FIND_FILES_DIALOG_QSS_DARK)

    def closeEvent(self, event) -> None:
        self._cancel_search_thread()
        super().closeEvent(event)

    def reject(self) -> None:
        self._cancel_search_thread()
        super().reject()

    def _cancel_search_thread(self) -> None:
        t = self._search_thread
        if t is not None and t.isRunning():
            t.requestInterruption()
            # ADB remote find can block inside run_adb for up to ~120s before checking interruption.
            if not t.wait(130000):
                t.terminate()
                t.wait(5000)
        self._search_thread = None

    def _browse_folder(self) -> None:
        le = self.folder_combo.lineEdit()
        start = (le.text() if le else self.folder_combo.currentText()) or str(Path.home())
        d = QFileDialog.getExistingDirectory(self, "Search folder", start)
        if d:
            if le:
                le.setText(d)
            else:
                self.folder_combo.setEditText(d)

    def _run_search(self) -> None:
        le = self.folder_combo.lineEdit()
        folder = (le.text() if le else self.folder_combo.currentText()).strip()
        needle = (self.pattern_edit.text() or "").strip().lower()
        self._list.clear()
        if not needle:
            QMessageBox.information(self, "Find", "Enter text to search for in the file or folder name.")
            return
        self._cancel_search_thread()
        self._last_search_folder = folder
        self._btn_search.setEnabled(False)
        self._btn_search.setText("Searching…")
        th = _FindFilesSearchThread(self._page, self._side, folder, needle, self)
        self._search_thread = th
        th.finished_ok.connect(self._on_search_finished)
        th.finished_err.connect(self._on_search_failed)
        th.finished.connect(self._on_search_thread_done)
        th.start()

    def _on_search_finished(self, paths: List[str]) -> None:
        for p in paths:
            if self._side == "local":
                it = QListWidgetItem(p)
                it.setData(Qt.UserRole, ("local", p))
            else:
                it = QListWidgetItem(p)
                it.setData(Qt.UserRole, ("remote", p))
            self._list.addItem(it)
        _push_find_folder_history(self._cfg, self._side, self._last_search_folder)
        if self._list.count() == 0:
            QMessageBox.information(self, "Find", "No matches.")

    def _on_search_failed(self, message: str) -> None:
        QMessageBox.warning(self, "Find", message or "Search failed.")

    def _on_search_thread_done(self) -> None:
        self._btn_search.setEnabled(True)
        self._btn_search.setText("Search")
        th = self.sender()
        self._search_thread = None
        if isinstance(th, QThread):
            th.deleteLater()

    def _go_selected(self) -> None:
        it = self._list.currentItem()
        if not it:
            return
        data = it.data(Qt.UserRole)
        if not data:
            return
        kind, path = data
        if kind == "local":
            self._page.apply_find_local_result(path)
        else:
            self._page.apply_find_remote_result(path)
        self.accept()


class ExplorerSessionPage(QWidget):
    """One WinSCP-style window: Local | Remote. Connection is established in the Login dialog before this tab opens."""

    def __init__(
        self,
        kind: str,
        get_adb_path: Callable[[], str],
        get_device_serial: Callable[[], str],
        log: Callable[[str], None],
        session_adb_serial: Optional[str] = None,
        sftp_transport=None,
        sftp_client=None,
        sftp_host: str = "",
        sftp_user: str = "",
        sftp_port: int = 22,
        sftp_password: str = "",
        ftp_client=None,
        ftp_host: str = "",
        ftp_port: int = 21,
        ftp_user: str = "",
        ftp_password: str = "",
        app_config: Optional[AppConfig] = None,
    ):
        super().__init__()
        self.kind = kind
        self._app_config = app_config
        self.get_adb_path = get_adb_path
        self.get_device_serial = get_device_serial
        self._log = log
        self._session_adb_serial = (session_adb_serial or "").strip()
        self._ssh_host = sftp_host
        self._ssh_user = sftp_user
        self._ssh_port = normalize_tcp_port(sftp_port, 22)
        self._ssh_password = sftp_password
        self._ftp_host = ftp_host
        self._ftp_port = normalize_tcp_port(ftp_port, 21)
        self._ftp_user = ftp_user
        self._ftp_password = ftp_password
        self._sftp_transport = sftp_transport
        self._sftp_client = sftp_client
        self._ftp_client = ftp_client
        self.local_path = self._default_local_root()
        self.remote_path = "/sdcard" if kind == "adb" else "/"
        if kind == "sftp" and self._sftp_client is not None:
            self.remote_path = sftp_first_listable_path(self._sftp_client, self._ssh_user)
        self.icon_provider = QFileIconProvider()
        self._adb_last_error = ""
        self._sftp_last_error = ""
        self._ftp_last_error = ""
        self._last_refresh_note = ""
        self._last_error_popup_key = ""
        # When a file is opened in an external app (Word, PDF reader), sync saves back to the remote path.
        self._ext_sync_remote: Dict[str, str] = {}
        self._ext_sync_timers: Dict[str, QTimer] = {}
        self._ext_last_mtime: Dict[str, float] = {}
        self._ext_fs_watcher: Optional[QFileSystemWatcher] = None
        self._ext_poll_timer = QTimer(self)
        self._ext_poll_timer.setInterval(2000)
        self._ext_poll_timer.timeout.connect(self._poll_external_mtime)
        self._ext_poll_timer.start()
        self._adb_transfer_thread: Optional[_AdbCommandThread] = None
        self._adb_transfer_dialog: Optional[QProgressDialog] = None
        self._adb_transfer_done_cb: Optional[Callable[[int, str], None]] = None
        self._adb_elapsed_timer: Optional[QTimer] = None
        self._delete_elapsed_timer: Optional[QTimer] = None
        self._remote_transfer_thread: Optional[_RemoteTransferThread] = None
        self._remote_transfer_dialog: Optional[QProgressDialog] = None
        self._remote_transfer_mode: str = ""
        self._delete_thread: Optional[_DeleteThread] = None
        self._delete_dialog: Optional[QProgressDialog] = None
        self._delete_done_cb: Optional[Callable[[bool, str], None]] = None
        self._sftp_ftp_delete_thread: Optional[_SftpFtpDeleteThread] = None
        self._sftp_ftp_delete_dialog: Optional[QProgressDialog] = None
        self._remote_refresh_thread: Optional[_RemoteListThread] = None
        self._remote_refresh_pending: bool = False
        self._last_active_side: str = "local"
        self._local_history: List[str] = []
        self._local_root_map: Dict[str, str] = {}
        self._remote_history: List[str] = []
        self._build_ui()
        QApplication.instance().installEventFilter(self)
        self._backspace_page_shortcut = QShortcut(QKeySequence(Qt.Key_Backspace), self)
        self._backspace_page_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self._backspace_page_shortcut.activated.connect(self._handle_backspace_nav)
        self.refresh_local()
        self.refresh_remote()

    def _default_local_root(self) -> str:
        if getattr(sys, "frozen", False):
            try:
                return str(Path(sys.executable).resolve().parent)
            except OSError:
                pass
        try:
            return str(Path.cwd().resolve())
        except OSError:
            return str(Path.home())

    def has_active_file_transfer(self) -> bool:
        adb = self._adb_transfer_thread is not None and self._adb_transfer_thread.isRunning()
        rem = self._remote_transfer_thread is not None and self._remote_transfer_thread.isRunning()
        sdel = self._sftp_ftp_delete_thread is not None and self._sftp_ftp_delete_thread.isRunning()
        return bool(adb or rem or sdel)

    def hideEvent(self, event) -> None:
        if self._adb_transfer_dialog is not None:
            self._adb_transfer_dialog.hide()
        if self._remote_transfer_dialog is not None:
            self._remote_transfer_dialog.hide()
        if self._sftp_ftp_delete_dialog is not None:
            self._sftp_ftp_delete_dialog.hide()
        super().hideEvent(event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._adb_transfer_dialog is not None and self._adb_transfer_thread and self._adb_transfer_thread.isRunning():
            self._adb_transfer_dialog.show()
        if (
            self._remote_transfer_dialog is not None
            and self._remote_transfer_thread
            and self._remote_transfer_thread.isRunning()
        ):
            self._remote_transfer_dialog.show()
        if (
            self._sftp_ftp_delete_dialog is not None
            and self._sftp_ftp_delete_thread
            and self._sftp_ftp_delete_thread.isRunning()
        ):
            self._sftp_ftp_delete_dialog.show()

    @staticmethod
    def _is_descendant_of(widget: Optional[QWidget], parent: Optional[QWidget]) -> bool:
        w = widget
        while w is not None:
            if w is parent:
                return True
            w = w.parentWidget()
        return False

    def _handle_backspace_nav(self) -> bool:
        fw = QApplication.focusWidget()
        if fw is None:
            if self._last_active_side == "remote":
                self.remote_up()
            else:
                self.local_up()
            return True
        le_local = self.local_address.lineEdit() if hasattr(self, "local_address") else None
        le_remote = self.remote_address.lineEdit() if hasattr(self, "remote_address") else None
        if fw is le_local:
            self._last_active_side = "local"
            self.local_up()
            return True
        if fw is le_remote:
            self._last_active_side = "remote"
            self.remote_up()
            return True
        if self._is_descendant_of(fw, self.local_table):
            self._last_active_side = "local"
            self.local_up()
            return True
        if self._is_descendant_of(fw, self.remote_table):
            self._last_active_side = "remote"
            self.remote_up()
            return True
        if self._last_active_side == "remote":
            self.remote_up()
        else:
            self.local_up()
        return True

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.KeyPress and ev.key() == Qt.Key_Backspace:
            mods = ev.modifiers()
            if not (mods & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)):
                fw = QApplication.focusWidget()
                if fw is not None and self._is_descendant_of(fw, self) and self._handle_backspace_nav():
                    ev.accept()
                    return True
        if ev.type() in (QEvent.MouseButtonPress, QEvent.FocusIn):
            if obj in {self.local_table, self.local_table.viewport(), self.local_address, self.local_address.lineEdit()}:
                self._last_active_side = "local"
            elif obj in {
                self.remote_table,
                self.remote_table.viewport(),
                self.remote_address,
                self.remote_address.lineEdit(),
            }:
                self._last_active_side = "remote"
        return super().eventFilter(obj, ev)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Backspace and not (ev.modifiers() & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)):
            if self._handle_backspace_nav():
                ev.accept()
                return
        super().keyPressEvent(ev)

    def disconnect_session(self) -> None:
        self._stop_background_threads()
        disconnect_sftp(self._sftp_transport, self._sftp_client)
        self._sftp_transport = None
        self._sftp_client = None
        disconnect_ftp(self._ftp_client)
        self._ftp_client = None

    def closeEvent(self, event) -> None:
        self._stop_background_threads()
        QApplication.instance().removeEventFilter(self)
        super().closeEvent(event)

    def _stop_background_threads(self) -> None:
        try:
            ev = getattr(self, "_adb_transfer_cancel_ev", None)
            if ev is not None:
                ev.set()
        except Exception:
            pass
        try:
            dev = getattr(self, "_delete_cancel_ev", None)
            if dev is not None:
                dev.set()
        except Exception:
            pass
        try:
            kill_all_adb_subprocesses()
        except Exception:
            pass
        threads = [
            self._adb_transfer_thread,
            self._remote_transfer_thread,
            self._remote_refresh_thread,
            self._delete_thread,
            self._sftp_ftp_delete_thread,
        ]
        for th in threads:
            if th is None:
                continue
            try:
                if th.isRunning():
                    th.requestInterruption()
                    if not th.wait(400):
                        th.terminate()
                        th.wait(800)
            except Exception:
                pass
        self._adb_transfer_thread = None
        self._remote_transfer_thread = None
        self._remote_refresh_thread = None
        self._delete_thread = None
        self._sftp_ftp_delete_thread = None
        if self._sftp_ftp_delete_dialog is not None:
            self._sftp_ftp_delete_dialog.close()
            self._sftp_ftp_delete_dialog.deleteLater()
            self._sftp_ftp_delete_dialog = None
        if self._adb_transfer_dialog is not None:
            self._adb_transfer_dialog.close()
            self._adb_transfer_dialog.deleteLater()
            self._adb_transfer_dialog = None
        if self._remote_transfer_dialog is not None:
            self._remote_transfer_dialog.close()
            self._remote_transfer_dialog.deleteLater()
            self._remote_transfer_dialog = None
        if self._delete_dialog is not None:
            self._delete_dialog.close()
            self._delete_dialog.deleteLater()
            self._delete_dialog = None
        if self._adb_elapsed_timer is not None:
            try:
                self._adb_elapsed_timer.stop()
            except Exception:
                pass
            self._adb_elapsed_timer.deleteLater()
            self._adb_elapsed_timer = None
        if self._delete_elapsed_timer is not None:
            try:
                self._delete_elapsed_timer.stop()
            except Exception:
                pass
            self._delete_elapsed_timer.deleteLater()
            self._delete_elapsed_timer = None

    def get_sftp_profile(self) -> SessionProfile:
        if self.kind != "sftp":
            return SessionProfile(ConnectionKind.SSH_SFTP)
        return SessionProfile(
            ConnectionKind.SSH_SFTP,
            ssh_host=self._ssh_host,
            ssh_user=self._ssh_user,
            ssh_port=self._ssh_port,
            ssh_password=self._ssh_password,
        )

    def _adb_prefix(self) -> List[str]:
        # Prefer global device (Terminal bar / refresh_devices); fall back to session from Login.
        serial = _first_serial_token(self.get_device_serial())
        if not serial:
            serial = _first_serial_token(self._session_adb_serial)
        return ["-s", serial] if serial else []

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(2, 0, 2, 2)
        root.setSpacing(2)

        if self.kind == "adb":
            self._explorer_hdr = QLabel()
            self._explorer_hdr.setObjectName("ExplorerSessionHint")
            root.addWidget(self._explorer_hdr)
        elif self.kind == "sftp":
            self._explorer_hdr = QLabel(
                f"SFTP — {self._ssh_user + '@' if self._ssh_user else ''}{self._ssh_host}:{self._ssh_port}"
            )
            self._explorer_hdr.setObjectName("ExplorerSessionHint")
            root.addWidget(self._explorer_hdr)
        else:
            self._explorer_hdr = QLabel(f"FTP — {self._ftp_host}:{self._ftp_port}")
            self._explorer_hdr.setObjectName("ExplorerSessionHint")
            root.addWidget(self._explorer_hdr)
        start_hint = QLabel(
            "How to start: create/login a session, browse folders, then use Pull or Push for transfer."
        )
        start_hint.setObjectName("ExplorerSessionHint")
        start_hint.setWordWrap(True)
        root.addWidget(start_hint)

        transfer_col = QFrame()
        transfer_col.setObjectName("ExplorerTransferStrip")
        tc = QVBoxLayout(transfer_col)
        tc.setContentsMargins(4, 6, 4, 6)
        tc.setSpacing(6)
        tc.addStretch(1)
        st = self.style()
        tb_pull = QToolButton()
        tb_pull.setObjectName("ExplorerTransferBtn")
        tb_pull.setIcon(st.standardIcon(QStyle.SP_ArrowLeft))
        tb_pull.setText("Pull")
        tb_pull.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        tb_pull.setToolTip(
            "Pull into the current local folder (left address bar). "
            "Or drag remote file(s) onto the local list."
        )
        tb_pull.clicked.connect(self.pull_selected)
        tb_push = QToolButton()
        tb_push.setObjectName("ExplorerTransferBtn")
        tb_push.setIcon(st.standardIcon(QStyle.SP_ArrowRight))
        tb_push.setText("Push")
        tb_push.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        tb_push.setToolTip(
            "Send selected local file(s) or folder(s) to the current remote folder. "
            "Or drag from the local list onto the remote list."
        )
        tb_push.clicked.connect(self.push_selected)
        tc.addWidget(tb_pull, alignment=Qt.AlignHCenter)
        tc.addWidget(tb_push, alignment=Qt.AlignHCenter)
        tc.addStretch(1)
        transfer_col.setFixedWidth(88)

        loc_header = QFrame()
        loc_header.setObjectName("WinScpPane")
        lov = QVBoxLayout(loc_header)
        lov.setContentsMargins(2, 0, 2, 2)
        lov.addWidget(QLabel("Local site"))
        la = QHBoxLayout()
        la.addWidget(QLabel())
        self.local_address = ExpandAllComboBox()
        self.local_address.setEditable(True)
        self.local_address.setObjectName("WinScpAddress")
        self.local_address.setCurrentText(self.local_path)
        self._seed_local_roots()
        self.local_address.setCurrentText(self.local_path)
        self.local_address.activated.connect(lambda _i: self.go_local())
        if self.local_address.lineEdit():
            self.local_address.lineEdit().returnPressed.connect(self.go_local)
            self.local_address.lineEdit().installEventFilter(self)
        la.addWidget(self.local_address, 1)
        st = self.style()
        self._local_up_btn = QToolButton()
        self._local_up_btn.setObjectName("WinScpIconBtn")
        self._local_up_btn.setIcon(self.style().standardIcon(QStyle.SP_FileDialogToParent))
        self._local_up_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._local_up_btn.setIconSize(QSize(16, 16))
        self._local_up_btn.setFixedSize(28, 28)
        self._local_up_btn.setToolTip("Up one folder")
        self._local_up_btn.clicked.connect(self.local_up)
        la.addWidget(self._local_up_btn)
        self._local_home_btn = QToolButton()
        self._local_home_btn.setObjectName("WinScpIconBtn")
        self._local_home_btn.setIcon(icon_home_folder())
        self._local_home_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._local_home_btn.setIconSize(QSize(16, 16))
        self._local_home_btn.setFixedSize(28, 28)
        self._local_home_btn.setToolTip("Home folder")
        self._local_home_btn.clicked.connect(self.local_go_home)
        la.addWidget(self._local_home_btn)
        b_refresh_l = QToolButton()
        b_refresh_l.setObjectName("WinScpIconBtn")
        b_refresh_l.setIcon(st.standardIcon(QStyle.SP_BrowserReload))
        b_refresh_l.setToolButtonStyle(Qt.ToolButtonIconOnly)
        b_refresh_l.setIconSize(QSize(16, 16))
        b_refresh_l.setFixedSize(28, 28)
        b_refresh_l.setToolTip("Refresh")
        b_refresh_l.clicked.connect(self.refresh_local)
        la.addWidget(b_refresh_l)
        lov.addLayout(la)
        loc_act = QHBoxLayout()
        loc_act.setSpacing(4)
        for tip, icon, fn, oname in [
            ("Refresh listing", QStyle.SP_BrowserReload, self.refresh_local, "WinScpIconBtn"),
            ("Find in list", QStyle.SP_FileDialogContentsView, self.find_in_local, "WinScpIconBtn"),
            ("New folder", QStyle.SP_DirIcon, self.new_local_folder, "WinScpIconBtn"),
            ("Create new empty file here", QStyle.SP_FileDialogStart, self.new_local_file, "ExplorerNewFileBtn"),
            ("Open with default application", QStyle.SP_DialogOpenButton, self.open_local, "WinScpIconBtn"),
            ("Edit in text editor", QStyle.SP_FileDialogDetailedView, self.edit_local, "ExplorerEditBtn"),
            ("Delete", QStyle.SP_TrashIcon, self.delete_local, "WinScpIconBtn"),
            ("Properties", QStyle.SP_FileDialogInfoView, self.local_properties, "WinScpIconBtn"),
        ]:
            b = QToolButton()
            b.setObjectName(oname)
            b.setIcon(st.standardIcon(icon))
            b.setToolTip(tip)
            b.clicked.connect(fn)
            loc_act.addWidget(b)
        loc_act.addStretch()
        lov.addLayout(loc_act)

        self.local_table = LocalFileTable(
            on_paste_paths=self._drop_local_paths_push,
            on_drop_remote_pull=self._drop_remote_infos_pull,
            on_backspace_up=self.local_up,
        )
        self.local_table.setColumnCount(4)
        self.local_table.setHorizontalHeaderLabels(["Name", "Size", "Date modified", "Type"])
        _apply_table_chrome(self.local_table, stretch_first=True)
        self.local_table.setIconSize(QSize(24, 24))
        self.local_table.setDragEnabled(True)
        self.local_table.setDragDropMode(QAbstractItemView.DragDrop)
        self.local_table.setDefaultDropAction(Qt.CopyAction)
        self.local_table.itemActivated.connect(self.on_local_activated)

        rem_header = QFrame()
        rem_header.setObjectName("WinScpPane")
        rov = QVBoxLayout(rem_header)
        rov.setContentsMargins(2, 0, 2, 2)
        rt = "Remote site"
        if self.kind == "adb":
            rt = "Remote site (Android)"
        elif self.kind == "sftp":
            rt = "Remote site (SFTP)"
        else:
            rt = "Remote site (FTP)"
        rov.addWidget(QLabel(rt))
        ra = QHBoxLayout()
        ra.addWidget(QLabel())
        self.remote_address = ExpandAllComboBox()
        self.remote_address.setEditable(True)
        self.remote_address.setObjectName("WinScpAddress")
        self.remote_address.setCurrentText(self.remote_path)
        if self.remote_address.lineEdit():
            self.remote_address.lineEdit().returnPressed.connect(self.go_remote)
            self.remote_address.lineEdit().installEventFilter(self)
        ra.addWidget(self.remote_address, 1)
        self._remote_up_btn = QToolButton()
        self._remote_up_btn.setObjectName("WinScpIconBtn")
        self._remote_up_btn.setIcon(self.style().standardIcon(QStyle.SP_FileDialogToParent))
        self._remote_up_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._remote_up_btn.setIconSize(QSize(16, 16))
        self._remote_up_btn.setFixedSize(28, 28)
        self._remote_up_btn.setToolTip("Up one folder")
        self._remote_up_btn.clicked.connect(self.remote_up)
        ra.addWidget(self._remote_up_btn)
        self._remote_home_btn = QToolButton()
        self._remote_home_btn.setObjectName("WinScpIconBtn")
        self._remote_home_btn.setIcon(icon_home_folder())
        self._remote_home_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._remote_home_btn.setIconSize(QSize(16, 16))
        self._remote_home_btn.setFixedSize(28, 28)
        if self.kind == "adb":
            self._remote_home_btn.setToolTip("Android shared storage (/sdcard)")
        else:
            self._remote_home_btn.setToolTip("Home folder")
        self._remote_home_btn.clicked.connect(self.remote_go_home)
        ra.addWidget(self._remote_home_btn)
        if self.kind != "adb":
            b_root = QToolButton()
            b_root.setObjectName("WinScpIconBtn")
            b_root.setIcon(icon_root_drive())
            b_root.setToolTip("Root (/)")
            b_root.clicked.connect(self.remote_root)
            ra.addWidget(b_root)
        b_refresh_r = QToolButton()
        b_refresh_r.setObjectName("WinScpIconBtn")
        b_refresh_r.setIcon(st.standardIcon(QStyle.SP_BrowserReload))
        b_refresh_r.setToolButtonStyle(Qt.ToolButtonIconOnly)
        b_refresh_r.setIconSize(QSize(16, 16))
        b_refresh_r.setFixedSize(28, 28)
        b_refresh_r.setToolTip("Refresh")
        b_refresh_r.clicked.connect(self.refresh_remote)
        ra.addWidget(b_refresh_r)
        rov.addLayout(ra)
        rem_act = QHBoxLayout()
        rem_act.setSpacing(4)
        for tip, icon, fn, oname in [
            ("Refresh listing", QStyle.SP_BrowserReload, self.refresh_remote, "WinScpIconBtn"),
            ("Find in list", QStyle.SP_FileDialogContentsView, self.find_in_remote, "WinScpIconBtn"),
            ("New folder", QStyle.SP_DirIcon, self.make_remote_folder, "WinScpIconBtn"),
            ("Create new empty file here", QStyle.SP_FileDialogStart, self.new_remote_file, "ExplorerNewFileBtn"),
            ("Open with default application (download first)", QStyle.SP_DialogOpenButton, self.open_remote, "WinScpIconBtn"),
            ("Edit in text editor", QStyle.SP_FileDialogDetailedView, self.edit_remote, "ExplorerEditBtn"),
            ("Delete", QStyle.SP_TrashIcon, self.delete_selected_remote, "WinScpIconBtn"),
            ("Properties", QStyle.SP_FileDialogInfoView, self.remote_properties, "WinScpIconBtn"),
        ]:
            b = QToolButton()
            b.setObjectName(oname)
            b.setIcon(st.standardIcon(icon))
            b.setToolTip(tip)
            b.clicked.connect(fn)
            rem_act.addWidget(b)
        rem_act.addStretch()
        rov.addLayout(rem_act)

        self.remote_table = RemoteFileTable(
            self.on_remote_activated,
            self._drop_local_paths_push,
            on_paste_paths=self._drop_local_paths_push,
            on_backspace_up=self.remote_up,
        )

        mid_wrap = QWidget()
        mid_wrap.setMinimumWidth(88)
        mid_lay = QHBoxLayout(mid_wrap)
        mid_lay.setContentsMargins(6, 0, 6, 0)
        mid_lay.setSpacing(0)
        mid_lay.addStretch(1)
        mid_lay.addWidget(transfer_col, 0, Qt.AlignCenter)
        mid_lay.addStretch(1)

        self.local_table.setMinimumWidth(140)
        self.remote_table.setMinimumWidth(140)
        self.local_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.local_table.customContextMenuRequested.connect(self._on_local_context_menu)
        self.remote_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.remote_table.customContextMenuRequested.connect(self._on_remote_context_menu)
        lv = self.local_table.viewport()
        lv.setContextMenuPolicy(Qt.CustomContextMenu)
        lv.customContextMenuRequested.connect(self._on_local_context_menu)
        rv = self.remote_table.viewport()
        rv.setContextMenuPolicy(Qt.CustomContextMenu)
        rv.customContextMenuRequested.connect(self._on_remote_context_menu)
        self.local_table.installEventFilter(self)
        self.local_table.viewport().installEventFilter(self)
        self.remote_table.installEventFilter(self)
        self.remote_table.viewport().installEventFilter(self)
        self.local_address.installEventFilter(self)
        self.remote_address.installEventFilter(self)
        if self.local_address.lineEdit():
            self.local_address.lineEdit().installEventFilter(self)
        if self.remote_address.lineEdit():
            self.remote_address.lineEdit().installEventFilter(self)
        QShortcut(QKeySequence(Qt.Key_F5), self.local_table, self.refresh_local)
        QShortcut(QKeySequence(Qt.Key_Delete), self.local_table, self.delete_local)
        QShortcut(QKeySequence(Qt.Key_F5), self.remote_table, self.refresh_remote)
        QShortcut(QKeySequence(Qt.Key_Delete), self.remote_table, self.delete_selected_remote)
        self._backspace_nav_shortcut = QShortcut(QKeySequence(Qt.Key_Backspace), self)
        self._backspace_nav_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self._backspace_nav_shortcut.activated.connect(self._handle_backspace_nav)

        header_grid = QGridLayout()
        header_grid.setContentsMargins(0, 0, 0, 0)
        header_grid.setHorizontalSpacing(0)
        header_grid.addWidget(loc_header, 0, 0)
        header_mid = QWidget()
        header_mid.setFixedWidth(112)
        header_mid.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        header_grid.addWidget(header_mid, 0, 1)
        header_grid.addWidget(rem_header, 0, 2)
        header_grid.setColumnStretch(0, 1)
        header_grid.setColumnStretch(2, 1)

        table_split = QSplitter(Qt.Horizontal)
        table_split.setObjectName("ExplorerSessionSplit")
        table_split.addWidget(self.local_table)
        table_split.addWidget(mid_wrap)
        table_split.addWidget(self.remote_table)
        table_split.setStretchFactor(0, 1)
        table_split.setStretchFactor(1, 0)
        table_split.setStretchFactor(2, 1)
        table_split.setCollapsible(0, False)
        table_split.setCollapsible(1, False)
        table_split.setCollapsible(2, False)
        table_split.setSizes([520, 112, 520])

        explorer_body = QVBoxLayout()
        explorer_body.setContentsMargins(0, 0, 0, 0)
        explorer_body.setSpacing(2)
        explorer_body.addLayout(header_grid)
        explorer_body.addWidget(table_split, 1)
        explorer_wrap = QWidget()
        explorer_wrap.setLayout(explorer_body)
        root.addWidget(explorer_wrap, 1)
        self._update_explorer_header()

    def _update_explorer_header(self) -> None:
        if not getattr(self, "_explorer_hdr", None):
            return
        if self.kind == "adb":
            ser = _first_serial_token(self.get_device_serial()) or _first_serial_token(self._session_adb_serial)
            self._explorer_hdr.setText(
                f"Android · ADB — {ser or 'choose a device in the toolbar (USB debugging on, authorize this PC)'}"
            )

    def _on_local_context_menu(self, pos) -> None:
        idx = self.local_table.indexAt(pos)
        if idx.isValid():
            self.local_table.selectRow(idx.row())
        m = QMenu(self)
        a_copy = m.addAction("Copy path(s)")
        a_copy.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        a_copy.setShortcut(QKeySequence.Copy)
        a_copy.setShortcutVisibleInContextMenu(True)
        a_copy.triggered.connect(self._ctx_copy_local_paths)
        m.addSeparator()
        a_ref = m.addAction("Refresh")
        a_ref.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        a_ref.triggered.connect(self.refresh_local)
        a_newf = m.addAction("New file")
        a_newf.setIcon(self.style().standardIcon(QStyle.SP_FileDialogStart))
        a_newf.triggered.connect(self.new_local_file)
        a_newd = m.addAction("New folder")
        a_newd.setIcon(self.style().standardIcon(QStyle.SP_DirIcon))
        a_newd.triggered.connect(self.new_local_folder)
        a_push = m.addAction("Push selected")
        a_push.setIcon(self.style().standardIcon(QStyle.SP_ArrowRight))
        a_push.triggered.connect(self.push_selected)
        a_open = m.addAction("Open with default application")
        a_open.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        a_open.triggered.connect(self.open_local)
        a_edit = m.addAction("Edit in text editor")
        a_edit.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        a_edit.triggered.connect(self.edit_local)
        a_del = m.addAction("Delete")
        a_del.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        a_del.triggered.connect(self.delete_local)
        a_prop = m.addAction("Properties")
        a_prop.setIcon(self.style().standardIcon(QStyle.SP_FileDialogInfoView))
        a_prop.triggered.connect(self.local_properties)
        m.exec_(self.local_table.viewport().mapToGlobal(pos))

    def _on_remote_context_menu(self, pos) -> None:
        idx = self.remote_table.indexAt(pos)
        if idx.isValid():
            self.remote_table.selectRow(idx.row())
        m = QMenu(self)
        a_copy = m.addAction("Copy path(s)")
        a_copy.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        a_copy.setShortcut(QKeySequence.Copy)
        a_copy.setShortcutVisibleInContextMenu(True)
        a_copy.triggered.connect(self._ctx_copy_remote_paths)
        m.addSeparator()
        a_pull = m.addAction("Pull")
        a_pull.setIcon(self.style().standardIcon(QStyle.SP_ArrowLeft))
        a_pull.triggered.connect(self.pull_selected)
        a_newf = m.addAction("New file")
        a_newf.setIcon(self.style().standardIcon(QStyle.SP_FileDialogStart))
        a_newf.triggered.connect(self.new_remote_file)
        a_newd = m.addAction("New folder")
        a_newd.setIcon(self.style().standardIcon(QStyle.SP_DirIcon))
        a_newd.triggered.connect(self.make_remote_folder)
        m.addSeparator()
        a_ref = m.addAction("Refresh")
        a_ref.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        a_ref.triggered.connect(self.refresh_remote)
        a_open = m.addAction("Open with default application (download first)")
        a_open.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        a_open.triggered.connect(self.open_remote)
        a_edit = m.addAction("Edit in text editor")
        a_edit.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        a_edit.triggered.connect(self.edit_remote)
        a_del = m.addAction("Delete")
        a_del.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        a_del.triggered.connect(self.delete_selected_remote)
        a_prop = m.addAction("Properties")
        a_prop.setIcon(self.style().standardIcon(QStyle.SP_FileDialogInfoView))
        a_prop.triggered.connect(self.remote_properties)
        m.exec_(self.remote_table.viewport().mapToGlobal(pos))

    def _ctx_copy_local_paths(self) -> None:
        rows = sorted({i.row() for i in self.local_table.selectedItems()})
        paths: List[str] = []
        for r in rows:
            it = self.local_table.item(r, 0)
            if it and it.data(Qt.UserRole):
                paths.append(str(it.data(Qt.UserRole)))
        if paths:
            QApplication.clipboard().setText("\n".join(paths))
            self._log(f"Explorer: copied {len(paths)} local path(s).")

    def _ctx_copy_remote_paths(self) -> None:
        rows = sorted({i.row() for i in self.remote_table.selectedItems()})
        paths: List[str] = []
        for r in rows:
            it = self.remote_table.item(r, 0)
            if it:
                info = it.data(Qt.UserRole) or {}
                p = info.get("path")
                if p:
                    paths.append(str(p))
        if paths:
            QApplication.clipboard().setText("\n".join(paths))
            self._log(f"Explorer: copied {len(paths)} remote path(s).")

    def _select_local_basename(self, name: str) -> None:
        name = (name or "").strip()
        if not name:
            return
        for r in range(self.local_table.rowCount()):
            it = self.local_table.item(r, 0)
            if it and it.text() == name:
                self.local_table.clearSelection()
                self.local_table.selectRow(r)
                self.local_table.setCurrentCell(r, 0)
                self.local_table.scrollToItem(it)
                self.local_table.setFocus(Qt.OtherFocusReason)
                return

    def _select_remote_basename(self, name: str) -> None:
        name = (name or "").strip()
        if not name:
            return
        for r in range(self.remote_table.rowCount()):
            it = self.remote_table.item(r, 0)
            if it and it.text() == name:
                self.remote_table.clearSelection()
                self.remote_table.selectRow(r)
                self.remote_table.setCurrentCell(r, 0)
                self.remote_table.scrollToItem(it)
                self.remote_table.setFocus(Qt.OtherFocusReason)
                return

    def _addr_local_text(self) -> str:
        txt = (self.local_address.currentText() or "").strip()
        data = self.local_address.currentData()
        if isinstance(data, str):
            drv = data.strip()
            if drv and txt in self._local_root_map:
                return drv
        return txt

    def _addr_remote_text(self) -> str:
        return (self.remote_address.currentText() or "").strip()

    def _set_local_address(self, path: str) -> None:
        self.local_address.setCurrentText(path)
        if path and path not in self._local_history:
            self._local_history.append(path)
            self.local_address.addItem(path)

    def _seed_local_roots(self) -> None:
        if sys.platform == "win32":
            for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                drv = f"{ch}:\\"
                try:
                    if Path(drv).exists() and drv not in self._local_history:
                        label = drv
                        try:
                            import ctypes

                            vol = ctypes.create_unicode_buffer(260)
                            fsn = ctypes.create_unicode_buffer(260)
                            serial = ctypes.c_uint(0)
                            max_comp = ctypes.c_uint(0)
                            flags = ctypes.c_uint(0)
                            ok = ctypes.windll.kernel32.GetVolumeInformationW(
                                ctypes.c_wchar_p(drv),
                                vol,
                                len(vol),
                                ctypes.byref(serial),
                                ctypes.byref(max_comp),
                                ctypes.byref(flags),
                                fsn,
                                len(fsn),
                            )
                            if ok and vol.value.strip():
                                label = f"{vol.value.strip()} ({drv})"
                        except Exception:
                            pass
                        self._local_history.append(drv)
                        self._local_root_map[label] = drv
                        self.local_address.addItem(label, drv)
                except OSError:
                    continue

    def _set_remote_address(self, path: str) -> None:
        self.remote_address.setCurrentText(path)
        if path and path not in self._remote_history:
            self._remote_history.append(path)
            self.remote_address.addItem(path)

    def _notify_path_result(self, title: str, message: str, target_path: str) -> None:
        p = Path(target_path)
        file_url = QUrl.fromLocalFile(str(p.resolve()))
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setIcon(QMessageBox.Information)
        box.setText(message)
        box.setInformativeText(str(p.resolve()))
        open_btn = box.addButton("Open", QMessageBox.ActionRole)
        box.addButton(QMessageBox.Ok)
        box.exec_()
        if box.clickedButton() == open_btn:
            QDesktopServices.openUrl(file_url)

    def find_local_matches(
        self, folder: str, needle: str, interrupt_check: Optional[Callable[[], bool]] = None
    ) -> List[Path]:
        root = Path(folder.strip() or self.local_path)
        if not root.exists() or not root.is_dir():
            return []
        out: List[Path] = []
        try:
            for p in root.rglob("*"):
                if interrupt_check and interrupt_check():
                    break
                if needle in p.name.lower():
                    out.append(p)
                if len(out) >= 500:
                    break
        except OSError:
            return []
        return out

    def find_remote_matches(
        self, folder: str, needle: str, interrupt_check: Optional[Callable[[], bool]] = None
    ) -> List[str]:
        root = (folder.strip() or self.remote_path).replace("\\", "/")
        needle_l = needle.lower()
        out: List[str] = []
        if self.kind == "adb":
            if interrupt_check and interrupt_check():
                return []
            serial = _first_serial_token(self.get_device_serial()) or _first_serial_token(self._session_adb_serial)
            if not serial:
                return []
            safe = root.replace("\\", "\\\\").replace('"', '\\"')
            code, stdout, stderr = run_adb(
                self.get_adb_path(),
                [*self._adb_prefix(), "shell", f'find "{safe}" 2>/dev/null | head -n 4000'],
                timeout=120,
            )
            if code != 0 and not stdout.strip():
                self._log(f"Explorer find (ADB): {stderr.strip() or 'find failed'}")
            for line in stdout.splitlines():
                if interrupt_check and interrupt_check():
                    break
                line = line.strip()
                if not line or needle_l not in Path(line).name.lower():
                    continue
                out.append(line)
                if len(out) >= 500:
                    break
            return out
        if self.kind == "sftp" and self._sftp_client:
            stack = [root.rstrip("/") or "/"]

            def walk() -> None:
                while stack and len(out) < 500:
                    if interrupt_check and interrupt_check():
                        return
                    d = stack.pop()
                    try:
                        for a in sftp_listdir_attr_safe(self._sftp_client, d):
                            if interrupt_check and interrupt_check():
                                return
                            name = a.filename
                            if name in (".", ".."):
                                continue
                            full = posixpath.join(d, name).replace("\\", "/")
                            if needle_l in name.lower():
                                out.append(full)
                            if _sftp_entry_is_dir(self._sftp_client, d, a):
                                stack.append(full)
                    except Exception:
                        continue

            walk()
            return out
        if self.kind == "ftp" and self._ftp_client:
            start_cwd = ""
            try:
                start_cwd = self._ftp_client.pwd()
            except Exception:
                pass

            def scan(d: str, depth: int) -> None:
                if interrupt_check and interrupt_check():
                    return
                if depth > 4 or len(out) >= 200:
                    return
                try:
                    _ftp_safe_cwd(self._ftp_client, d)
                except Exception:
                    return
                try:
                    for name, facts in self._ftp_client.mlsd():
                        if interrupt_check and interrupt_check():
                            return
                        if name in (".", ".."):
                            continue
                        is_dir = facts.get("type") == "dir"
                        full = posixpath.join(d, name).replace("\\", "/")
                        if needle_l in name.lower():
                            out.append(full)
                        if is_dir:
                            scan(full, depth + 1)
                except (error_perm, AttributeError, Exception):
                    try:
                        for name in self._ftp_client.nlst():
                            if interrupt_check and interrupt_check():
                                return
                            if name in (".", ".."):
                                continue
                            full = posixpath.join(d, name).replace("\\", "/")
                            if needle_l in name.lower():
                                out.append(full)
                    except Exception:
                        pass

            try:
                scan(root.rstrip("/") or "/", 0)
            except Exception:
                pass
            finally:
                if start_cwd:
                    try:
                        _ftp_safe_cwd(self._ftp_client, start_cwd)
                    except Exception:
                        pass
            return out
        return []

    def apply_find_local_result(self, path_str: str) -> None:
        target = Path(path_str)
        if not target.exists():
            return
        target_dir = target.parent if target.is_file() else target
        self.local_path = str(target_dir.resolve())
        self._set_local_address(self.local_path)
        self.refresh_local()
        self._select_local_basename(target.name)

    def apply_find_remote_result(self, path_str: str) -> None:
        rp = path_str.replace("\\", "/").strip()
        if not rp:
            return
        parent = posixpath.dirname(rp) or "/"
        self.remote_path = parent
        self._set_remote_address(self.remote_path)
        self.refresh_remote()
        self._select_remote_basename(posixpath.basename(rp))

    def _sftp_get_with_progress(self, remote_path: str, local_dest: str) -> None:
        assert self._sftp_client is not None
        try:
            st = self._sftp_client.stat(remote_path)
            total = max(st.st_size, 1)
        except Exception:
            total = 1
        dlg = QProgressDialog("Downloading from server…", None, 0, 100, self)
        dlg.setCancelButton(None)
        dlg.setMinimumDuration(0)
        dlg.setWindowModality(Qt.ApplicationModal)

        def _cb(sent: int, size: int) -> None:
            if size:
                dlg.setValue(min(99, int(100 * sent / max(size, 1))))
            QApplication.processEvents()

        self._sftp_client.get(remote_path, local_dest, callback=_cb)
        dlg.setValue(100)
        dlg.close()

    def _sftp_mkdir_p(self, remote_dir: str) -> None:
        assert self._sftp_client is not None
        r = remote_dir.replace("\\", "/").rstrip("/")
        if not r or r == "/":
            return
        parts = [p for p in r.split("/") if p]
        acc = ""
        for p in parts:
            acc = f"{acc}/{p}" if acc else f"/{p}"
            try:
                self._sftp_client.stat(acc)
                continue
            except (OSError, IOError):
                pass
            try:
                self._sftp_client.mkdir(acc)
            except (OSError, IOError) as e:
                if not _sftp_is_exists_err(e):
                    raise

    def _sftp_put_tree(self, local_root: Path, remote_parent: str) -> bool:
        assert self._sftp_client is not None
        remote_root = posixpath.join(remote_parent.rstrip("/"), local_root.name).replace("\\", "/")
        self._sftp_mkdir_p(remote_root)
        n = 0
        for root, _dirs, files in os.walk(local_root):
            rel = Path(root).relative_to(local_root)
            rel_s = "" if str(rel) == "." else str(rel).replace("\\", "/")
            sub_remote = posixpath.join(remote_root, rel_s).replace("//", "/") if rel_s else remote_root
            if rel_s:
                self._sftp_mkdir_p(sub_remote)
            for fn in files:
                lp = Path(root) / fn
                rp = posixpath.join(sub_remote, fn).replace("\\", "/")
                try:
                    total = max(lp.stat().st_size, 1)
                except OSError:
                    total = 1
                dlg = QProgressDialog(f"SFTP upload {lp.name}…", None, 0, 100, self)
                dlg.setCancelButton(None)
                dlg.setMinimumDuration(0)
                dlg.setWindowModality(Qt.ApplicationModal)

                def _cb(sent: int, size: int) -> None:
                    if size:
                        dlg.setValue(min(99, int(100 * sent / max(size, 1))))
                    QApplication.processEvents()

                self._sftp_client.put(str(lp), rp, callback=_cb)
                dlg.setValue(100)
                dlg.close()
                n += 1
        self._log(f"Explorer: SFTP uploaded folder {local_root.name} ({n} file(s)).")
        return True

    def _sftp_pull_tree(self, remote_path: str, local_parent: str) -> None:
        assert self._sftp_client is not None
        name = posixpath.basename(remote_path.rstrip("/"))
        local_root = os.path.join(local_parent, name)
        os.makedirs(local_root, exist_ok=True)
        self._sftp_pull_recursive(remote_path.rstrip("/"), local_root)

    def _sftp_pull_recursive(self, remote_path: str, local_path: str) -> None:
        assert self._sftp_client is not None
        for a in sftp_listdir_attr_safe(self._sftp_client, remote_path):
            if a.filename in (".", ".."):
                continue
            r = posixpath.join(remote_path, a.filename).replace("\\", "/")
            l = os.path.join(local_path, a.filename)
            if _sftp_entry_is_dir(self._sftp_client, remote_path, a):
                os.makedirs(l, exist_ok=True)
                self._sftp_pull_recursive(r, l)
            else:
                self._sftp_get_with_progress(r, l)

    def _ftp_ensure_remote_dir(self, remote_abs: str) -> None:
        """Create remote path if needed; leave FTP cwd at remote_abs."""
        assert self._ftp_client is not None
        r = remote_abs.replace("\\", "/").rstrip("/")
        if r == "" or r == "/":
            try:
                self._ftp_client.cwd("/")
            except error_perm:
                pass
            return
        try:
            _ftp_safe_cwd(self._ftp_client, r)
            return
        except error_perm:
            pass
        parent = posixpath.dirname(r)
        if not parent or parent == ".":
            parent = "/"
        base = posixpath.basename(r)
        self._ftp_ensure_remote_dir(parent)
        try:
            _ftp_safe_mkd(self._ftp_client, base)
        except error_perm:
            pass
        try:
            _ftp_cwd_segment(self._ftp_client, base)
        except error_perm:
            pass

    def _ftp_put_tree(self, local_root: Path, remote_parent: str) -> bool:
        assert self._ftp_client is not None
        remote_root = posixpath.join(remote_parent.rstrip("/"), local_root.name).replace("\\", "/")
        self._ftp_ensure_remote_dir(remote_root)
        n = 0
        for walk_root, _dirs, files in os.walk(local_root):
            rel = Path(walk_root).relative_to(local_root)
            rel_s = "" if str(rel) == "." else str(rel).replace("\\", "/")
            sub_remote = posixpath.join(remote_root, rel_s).replace("//", "/") if rel_s else remote_root
            if rel_s:
                self._ftp_ensure_remote_dir(sub_remote)
            for fn in files:
                lp = Path(walk_root) / fn
                rp_file = posixpath.join(sub_remote, fn).replace("\\", "/")
                parent = posixpath.dirname(rp_file) or "/"
                base = posixpath.basename(rp_file)
                self._ftp_ensure_remote_dir(parent)
                try:
                    total = max(lp.stat().st_size, 1)
                except OSError:
                    total = 1
                dlg = QProgressDialog(f"FTP upload {lp.name}…", None, 0, 100, self)
                dlg.setCancelButton(None)
                dlg.setMinimumDuration(0)
                dlg.setWindowModality(Qt.ApplicationModal)
                sent = [0]

                def _dcb(block: bytes) -> None:
                    sent[0] += len(block)
                    dlg.setValue(min(99, int(100 * sent[0] / max(total, 1))))
                    QApplication.processEvents()

                with open(lp, "rb") as f:
                    self._ftp_client.storbinary(
                        f"STOR {_ftp_quote_token(base)}", f, blocksize=65536, callback=_dcb
                    )
                dlg.setValue(100)
                dlg.close()
                n += 1
        self._log(f"Explorer: FTP uploaded folder {local_root.name} ({n} file(s)).")
        return True

    def _ftp_pull_tree(self, remote_path: str, local_parent: str) -> None:
        assert self._ftp_client is not None
        name = posixpath.basename(remote_path.rstrip("/"))
        local_root = os.path.join(local_parent, name)
        os.makedirs(local_root, exist_ok=True)
        self._ftp_pull_recursive(remote_path.rstrip("/"), local_root)

    def _ftp_pull_recursive(self, remote_path: str, local_path: str) -> None:
        assert self._ftp_client is not None
        try:
            _ftp_safe_cwd(self._ftp_client, remote_path)
        except error_perm as exc:
            self._log(f"Explorer: FTP cwd {remote_path}: {exc}")
            raise
        try:
            entries = list(self._ftp_client.mlsd())
        except (error_perm, AttributeError):
            entries = []
            for name in self._ftp_client.nlst():
                if name not in (".", ".."):
                    entries.append((name, {"type": "file"}))
        for name, facts in entries:
            if name in (".", ".."):
                continue
            r = posixpath.join(remote_path, name).replace("\\", "/")
            l = os.path.join(local_path, name)
            is_dir = bool(facts) and facts.get("type") == "dir"
            if is_dir:
                os.makedirs(l, exist_ok=True)
                self._ftp_pull_recursive(r, l)
            else:
                parent = posixpath.dirname(r) or "/"
                fn = posixpath.basename(r)
                dlg = QProgressDialog(f"FTP download {fn}…", None, 0, 0, self)
                dlg.setCancelButton(None)
                dlg.setMinimumDuration(0)
                dlg.setWindowModality(Qt.ApplicationModal)
                QApplication.processEvents()
                self._ftp_ensure_remote_dir(parent)
                with open(l, "wb") as out:
                    self._ftp_client.retrbinary(f"RETR {_ftp_quote_token(fn)}", out.write)
                dlg.close()

    def _adb_progress_exec(
        self, label: str, adb_args: List[str], timeout: int = 600, *, quiet: bool = False
    ) -> Tuple[int, str]:
        if quiet:
            code, out, err = run_adb(self.get_adb_path(), adb_args, timeout=timeout)
            return code, (err or out or "").strip()

        dlg = QProgressDialog(label, "Cancel", 0, 100, self)
        dlg.setWindowModality(Qt.ApplicationModal)
        dlg.setMinimumDuration(0)
        dlg.setValue(0)
        dlg.setAutoClose(True)
        dlg.setAutoReset(True)
        dlg.setCancelButton(None)
        last_pct = [0]

        def on_pct(p: int) -> None:
            if 0 <= p <= 100 and p >= last_pct[0]:
                last_pct[0] = p
                dlg.setValue(p)
                dlg.setLabelText(f"{label}\n{p}%")
            QApplication.processEvents()

        code, out, err = run_adb_with_line_callback(
            self.get_adb_path(),
            adb_args,
            timeout=timeout,
            on_percent=on_pct,
        )
        dlg.setValue(100)
        dlg.close()
        msg = (err or out or "").strip()
        return code, msg

    def _start_adb_transfer(
        self,
        *,
        label: str,
        adb_args: List[str],
        timeout: int,
        done_cb: Callable[[int, str], None],
        poll_total_bytes: int = 0,
        poll_mode: str = "",
        poll_remote: str = "",
        poll_local: str = "",
        prep_measure_push_dir: Optional[str] = None,
        prep_measure_pull: Optional[Tuple[str, str]] = None,
    ) -> bool:
        if self._adb_transfer_thread and self._adb_transfer_thread.isRunning():
            QMessageBox.information(self, "Transfer in progress", "Wait for the current ADB transfer to finish.")
            return False
        self._adb_transfer_done_cb = done_cb
        self._adb_transfer_cancel_ev = threading.Event()
        dlg = QProgressDialog(label, "Cancel", 0, 100, self)
        dlg.setMinimumDuration(0)
        dlg.setWindowModality(Qt.NonModal)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        defer_prep = bool((prep_measure_push_dir or "").strip()) or bool(prep_measure_pull)
        use_poll = defer_prep or (int(poll_total_bytes or 0) > 0 and bool((poll_mode or "").strip()))
        if use_poll:
            dlg.setRange(0, 100)
            dlg.setValue(0)
        else:
            dlg.setRange(0, 0)
            dlg.setValue(0)
        dlg.canceled.connect(self._adb_transfer_cancel_ev.set)
        dlg.show()
        self._adb_transfer_dialog = dlg
        self._adb_transfer_base_label = label
        self._adb_transfer_use_poll = bool(use_poll)
        self._adb_transfer_t0 = time.monotonic()
        self._adb_last_pct = -1
        extra = ""
        if defer_prep:
            extra = "\nPreparing…"
        elif use_poll:
            extra = f"\n≈ {_human_bytes(int(poll_total_bytes))} total (measured)"
        self._adb_transfer_extra_note = extra
        if self._adb_elapsed_timer is not None:
            try:
                self._adb_elapsed_timer.stop()
            except Exception:
                pass
            self._adb_elapsed_timer.deleteLater()
            self._adb_elapsed_timer = None
        self._adb_elapsed_timer = QTimer(self)
        self._adb_elapsed_timer.setInterval(200)
        self._adb_elapsed_timer.timeout.connect(self._tick_adb_transfer_elapsed)
        self._adb_elapsed_timer.start()
        self._tick_adb_transfer_elapsed()

        th = _AdbCommandThread(
            self.get_adb_path(),
            adb_args,
            timeout=timeout,
            adb_shell_prefix=self._adb_prefix(),
            poll_total_bytes=poll_total_bytes,
            poll_mode=poll_mode,
            poll_remote=poll_remote,
            poll_local=poll_local,
            prep_measure_push_dir=prep_measure_push_dir,
            prep_measure_pull=prep_measure_pull,
            cancel_event=self._adb_transfer_cancel_ev,
            parent=self,
        )
        th.progress.connect(self._on_adb_transfer_progress)
        th.status.connect(self._on_adb_transfer_status)
        th.prep_done.connect(self._on_adb_prep_done)
        th.done.connect(self._on_adb_transfer_done)
        th.finished.connect(th.deleteLater)
        self._adb_transfer_thread = th
        th.start()
        return True

    def _tick_adb_transfer_elapsed(self) -> None:
        dlg = self._adb_transfer_dialog
        if dlg is None:
            return
        t0 = getattr(self, "_adb_transfer_t0", None)
        if t0 is None:
            return
        elapsed = time.monotonic() - float(t0)
        lbl = getattr(self, "_adb_transfer_base_label", "Transfer")
        extra = getattr(self, "_adb_transfer_extra_note", "")
        pct = getattr(self, "_adb_last_pct", -1)
        use_poll = getattr(self, "_adb_transfer_use_poll", False)
        if use_poll and (pct is None or int(pct) < 0):
            dlg.setRange(0, 100)
            dlg.setValue(0)
            dlg.setLabelText(f"{lbl}\n0% · {elapsed:,.1f}s elapsed{extra}")
            return
        if pct is None or int(pct) < 0:
            dlg.setLabelText(f"{lbl}\nWorking… · {elapsed:,.1f}s elapsed{extra}")
        else:
            dlg.setLabelText(f"{lbl}\n{int(pct)}% · {elapsed:,.1f}s elapsed{extra}")

    def _on_adb_transfer_progress(self, pct: int) -> None:
        if self._adb_transfer_dialog is None:
            return
        lbl = getattr(self, "_adb_transfer_base_label", "Transfer")
        extra = getattr(self, "_adb_transfer_extra_note", "")
        if int(pct) >= 0:
            self._adb_last_pct = max(int(getattr(self, "_adb_last_pct", -1)), int(pct))
        else:
            self._adb_last_pct = int(pct)
        use_poll = getattr(self, "_adb_transfer_use_poll", False)
        if pct < 0:
            if use_poll:
                self._adb_transfer_dialog.setRange(0, 100)
                self._adb_transfer_dialog.setValue(0)
                t0 = getattr(self, "_adb_transfer_t0", None)
                elapsed = 0.0 if t0 is None else (time.monotonic() - float(t0))
                self._adb_transfer_dialog.setLabelText(f"{lbl}\n0% · {elapsed:,.1f}s elapsed{extra}")
            else:
                self._adb_transfer_dialog.setRange(0, 0)
                t0 = getattr(self, "_adb_transfer_t0", None)
                elapsed = 0.0 if t0 is None else (time.monotonic() - float(t0))
                self._adb_transfer_dialog.setLabelText(f"{lbl}\nWorking… · {elapsed:,.1f}s elapsed{extra}")
            return
        self._adb_transfer_dialog.setRange(0, 100)
        showv = max(0, min(100, int(getattr(self, "_adb_last_pct", int(pct)))))
        self._adb_transfer_dialog.setValue(showv)
        t0 = getattr(self, "_adb_transfer_t0", None)
        elapsed = 0.0 if t0 is None else (time.monotonic() - float(t0))
        self._adb_transfer_dialog.setLabelText(f"{lbl}\n{showv}% · {elapsed:,.1f}s elapsed{extra}")

    def _on_adb_transfer_status(self, line: str) -> None:
        if self._adb_transfer_dialog is None:
            return
        lbl = getattr(self, "_adb_transfer_base_label", "Transfer")
        extra = getattr(self, "_adb_transfer_extra_note", "")
        txt = (line or "").strip()
        t0 = getattr(self, "_adb_transfer_t0", None)
        elapsed = 0.0 if t0 is None else (time.monotonic() - float(t0))
        pct = getattr(self, "_adb_last_pct", -1)
        if txt:
            if pct is not None and int(pct) >= 0:
                self._adb_transfer_dialog.setLabelText(
                    f"{lbl}\n{int(pct)}% · {elapsed:,.1f}s elapsed{extra}\n{txt[:120]}"
                )
            else:
                self._adb_transfer_dialog.setLabelText(f"{lbl}\n{txt[:140]}\n{elapsed:,.1f}s elapsed{extra}")

    def _on_adb_prep_done(self, note: str) -> None:
        """After folder-size prep finishes, replace the short “Preparing…” line with the measured total."""
        self._adb_transfer_extra_note = f"\n{note}"
        self._tick_adb_transfer_elapsed()

    def _on_adb_transfer_done(self, code: int, msg: str) -> None:
        th = self.sender()
        if th is not self._adb_transfer_thread:
            return
        if self._adb_elapsed_timer is not None:
            try:
                self._adb_elapsed_timer.stop()
            except Exception:
                pass
            self._adb_elapsed_timer.deleteLater()
            self._adb_elapsed_timer = None
        if self._adb_transfer_dialog is not None:
            self._adb_transfer_dialog.setValue(100)
            self._adb_transfer_dialog.close()
            self._adb_transfer_dialog.deleteLater()
            self._adb_transfer_dialog = None
        self._adb_transfer_thread = None
        self._adb_last_pct = -1
        self._adb_transfer_use_poll = False
        self._adb_transfer_cancel_ev = None
        if code == 130:
            self._log("Explorer: transfer cancelled.")
        cb = self._adb_transfer_done_cb
        self._adb_transfer_done_cb = None
        if cb:
            cb(code, msg)

    def _queue_adb_pull(
        self,
        infos: List[dict],
        *,
        notify_final: bool = True,
        select_final: bool = True,
        explicit_final_name: Optional[str] = None,
    ) -> None:
        pull_items = [i for i in infos if isinstance(i, dict) and i.get("path")]
        if not pull_items:
            return
        target_dir = self.local_path
        total = len(pull_items)
        result = {"ok": 0}

        def _finish() -> None:
            if result["ok"] > 0:
                if notify_final:
                    self._notify_path_result(
                        "Pull complete",
                        f"Pulled {result['ok']} item(s)\nTo local folder:",
                        target_dir,
                    )
                if select_final:
                    final_name = explicit_final_name or posixpath.basename(str(pull_items[-1]["path"]).rstrip("/"))
                    if final_name:
                        self._select_local_basename(final_name)
                QTimer.singleShot(0, self.refresh_local)

        def _run_one(idx: int) -> None:
            if idx >= total:
                _finish()
                return
            info = pull_items[idx]
            src = str(info["path"])
            self._log(f"Explorer: pull {src} → {target_dir}")
            base = posixpath.basename(src.rstrip("/")) or "item"
            local_dest = str(Path(target_dir) / base)
            started = self._start_adb_transfer(
                label=f"Pull ({idx + 1}/{total})",
                adb_args=[*self._adb_prefix(), "pull", src, target_dir],
                timeout=3600,
                done_cb=lambda code, msg, i=idx, s=src: _on_done(i, s, code, msg),
                poll_total_bytes=0,
                poll_mode="",
                poll_remote="",
                poll_local="",
                prep_measure_pull=(src, local_dest),
            )
            if not started:
                return

        def _on_done(idx: int, src: str, code: int, msg: str) -> None:
            if code == 130:
                return
            if code != 0:
                self._log(f"Explorer: pull failed ({code}) {msg[:400]}")
                QMessageBox.warning(self, "Pull", msg or "Failed.")
                return
            result["ok"] += 1
            self._log(f"Explorer: pull finished — {msg[:400] if msg else 'ok'}")
            _run_one(idx + 1)

        _run_one(0)

    def _queue_adb_push(self, items: List[str]) -> None:
        push_items = []
        for p in items:
            try:
                if p and Path(p).exists():
                    push_items.append(p)
            except OSError:
                continue
        if not push_items:
            return
        total = len(push_items)
        result = {"ok": 0, "last": ""}

        def _finish() -> None:
            if result["ok"] <= 0:
                return
            self._log(
                f"Explorer: push completed ({result['ok']} item(s)) from local folder '{self.local_path}' "
                f"to remote folder '{self.remote_path}'."
            )
            QMessageBox.information(
                self,
                "Push",
                f"Transferred {result['ok']} item(s)\nFrom: {self.local_path}\nTo: {self.remote_path}",
            )
            if result["last"]:
                self._select_remote_basename(result["last"])
            QTimer.singleShot(0, self.refresh_remote)

        def _run_one(idx: int) -> None:
            if idx >= total:
                _finish()
                return
            local = push_items[idx]
            lp = Path(local)
            name = lp.name
            poll_total = 0
            poll_mode = ""
            poll_remote = ""
            poll_local = ""
            prep_measure_push_dir: Optional[str] = None
            try:
                if lp.is_file():
                    poll_total = int(lp.stat().st_size)
                    if poll_total > 0:
                        poll_mode = "push_file"
                        poll_remote = posixpath.join(self.remote_path.rstrip("/"), name).replace("\\", "/")
                elif lp.is_dir():
                    prep_measure_push_dir = str(lp)
                    poll_remote = posixpath.join(self.remote_path.rstrip("/"), name).replace("\\", "/")
            except OSError:
                poll_total = 0
            started = self._start_adb_transfer(
                label=f"Push ({idx + 1}/{total})",
                adb_args=[*self._adb_prefix(), "push", local, self.remote_path],
                timeout=3600,
                done_cb=lambda code, msg, i=idx, n=name: _on_done(i, n, code, msg),
                poll_total_bytes=poll_total,
                poll_mode=poll_mode,
                poll_remote=poll_remote,
                poll_local=poll_local,
                prep_measure_push_dir=prep_measure_push_dir,
            )
            if not started:
                return

        def _on_done(idx: int, name: str, code: int, msg: str) -> None:
            if code == 130:
                return
            if code != 0:
                self._log(f"Explorer: push failed ({code}) {msg[:300]}")
                QMessageBox.warning(self, "Push", msg or "Failed.")
                return
            result["ok"] += 1
            result["last"] = name
            _run_one(idx + 1)

        _run_one(0)

    def _start_remote_transfer(self, *, mode: str, items: List[dict]) -> bool:
        if self._remote_transfer_thread and self._remote_transfer_thread.isRunning():
            QMessageBox.information(self, "Transfer in progress", "Wait for the current transfer to finish.")
            return False
        if self.kind not in ("sftp", "ftp"):
            return False
        creds = (
            {
                "host": self._ssh_host,
                "port": self._ssh_port,
                "user": self._ssh_user,
                "password": self._ssh_password,
            }
            if self.kind == "sftp"
            else {
                "host": self._ftp_host,
                "port": self._ftp_port,
                "user": self._ftp_user,
                "password": self._ftp_password,
            }
        )
        dlg = QProgressDialog("Transferring…", None, 0, 100, self)
        dlg.setCancelButton(None)
        dlg.setMinimumDuration(0)
        dlg.setWindowModality(Qt.NonModal)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.setValue(0)
        dlg.show()
        self._remote_transfer_dialog = dlg
        self._remote_transfer_mode = mode
        th = _RemoteTransferThread(
            kind=self.kind,
            mode=mode,
            items=items,
            remote_path=self.remote_path,
            local_path=self.local_path,
            creds=creds,
        )
        th.progress.connect(self._on_remote_transfer_progress)
        th.done.connect(self._on_remote_transfer_done)
        th.finished.connect(th.deleteLater)
        self._remote_transfer_thread = th
        th.start()
        return True

    def _on_remote_transfer_progress(self, pct: int, msg: str) -> None:
        if self._remote_transfer_dialog is None:
            return
        self._remote_transfer_dialog.setValue(max(0, min(100, int(pct))))
        self._remote_transfer_dialog.setLabelText(msg or "Transferring…")

    def _on_remote_transfer_done(self, ok: bool, last_name: str, message: str) -> None:
        th = self.sender()
        if th is not self._remote_transfer_thread:
            return
        if self._remote_transfer_dialog is not None:
            self._remote_transfer_dialog.setValue(100)
            self._remote_transfer_dialog.close()
            self._remote_transfer_dialog.deleteLater()
            self._remote_transfer_dialog = None
        self._remote_transfer_thread = None
        if not ok:
            QMessageBox.warning(self, "Transfer", message or "Transfer failed.")
            return
        if self._remote_transfer_mode == "push":
            self.refresh_remote()
            if last_name:
                self._select_remote_basename(last_name)
        else:
            self.refresh_local()
            if last_name:
                self._select_local_basename(last_name)
        self._log(f"Explorer: {self.kind.upper()} {self._remote_transfer_mode} complete — {message}")

    def _start_delete_job(
        self,
        *,
        mode: str,
        target: str,
        is_dir: bool = False,
        done_cb: Callable[[bool, str], None],
    ) -> bool:
        if self._delete_thread and self._delete_thread.isRunning():
            QMessageBox.information(self, "Delete", "Another delete operation is still running.")
            return False
        self._delete_done_cb = done_cb
        self._delete_cancel_ev = threading.Event()
        dlg = QProgressDialog("Deleting…", "Cancel", 0, 100, self)
        dlg.setMinimumDuration(0)
        dlg.setWindowModality(Qt.NonModal)
        dlg.setRange(0, 100)
        dlg.setValue(0)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.canceled.connect(self._delete_cancel_ev.set)
        dlg.show()
        self._delete_dialog = dlg
        self._delete_last_pct = 0
        self._delete_t0 = time.monotonic()
        if self._delete_elapsed_timer is not None:
            try:
                self._delete_elapsed_timer.stop()
            except Exception:
                pass
            self._delete_elapsed_timer.deleteLater()
            self._delete_elapsed_timer = None
        self._delete_elapsed_timer = QTimer(self)
        self._delete_elapsed_timer.setInterval(200)
        self._delete_elapsed_timer.timeout.connect(self._tick_delete_elapsed)
        self._delete_elapsed_timer.start()
        self._tick_delete_elapsed()
        th = _DeleteThread(
            mode=mode,
            target=target,
            is_dir=is_dir,
            adb_path=self.get_adb_path(),
            adb_args=self._adb_prefix(),
            cancel_event=self._delete_cancel_ev,
        )
        th.progress.connect(self._on_delete_progress)
        th.done.connect(self._on_delete_job_done)
        th.finished.connect(th.deleteLater)
        self._delete_thread = th
        th.start()
        return True

    def _on_delete_progress(self, pct: int) -> None:
        self._delete_last_pct = max(int(getattr(self, "_delete_last_pct", 0)), max(0, min(100, int(pct))))
        dlg = self._delete_dialog
        if dlg is None:
            return
        dlg.setRange(0, 100)
        dlg.setValue(self._delete_last_pct)

    def _tick_delete_elapsed(self) -> None:
        dlg = self._delete_dialog
        if dlg is None:
            return
        t0 = getattr(self, "_delete_t0", None)
        if t0 is None:
            return
        elapsed = time.monotonic() - float(t0)
        pct = int(getattr(self, "_delete_last_pct", 0))
        dlg.setLabelText(f"Deleting…\n{pct}% · {elapsed:,.1f}s elapsed")

    def _on_delete_job_done(self, ok: bool, err: str) -> None:
        th = self.sender()
        if th is not self._delete_thread:
            return
        if self._delete_elapsed_timer is not None:
            try:
                self._delete_elapsed_timer.stop()
            except Exception:
                pass
            self._delete_elapsed_timer.deleteLater()
            self._delete_elapsed_timer = None
        if self._delete_dialog is not None:
            self._delete_dialog.close()
            self._delete_dialog.deleteLater()
            self._delete_dialog = None
        self._delete_thread = None
        self._delete_cancel_ev = None
        cb = self._delete_done_cb
        self._delete_done_cb = None
        if cb:
            cb(ok, err)

    def local_go_home(self) -> None:
        self.local_path = self._default_local_root()
        self._set_local_address(self.local_path)
        self.refresh_local()

    def remote_go_home(self) -> None:
        if self.kind == "adb":
            self.remote_path = "/sdcard"
        elif self.kind == "sftp":
            if self._sftp_client is not None:
                self.remote_path = sftp_first_listable_path(self._sftp_client, self._ssh_user)
            else:
                u = (self._ssh_user or "").strip()
                self.remote_path = f"/home/{u}" if u else "/"
        else:
            self.remote_path = "/"
        self._set_remote_address(self.remote_path)
        self.refresh_remote()

    def _update_nav_buttons(self) -> None:
        if hasattr(self, "_local_up_btn"):
            try:
                lp = Path(self.local_path)
                at_root = not lp.exists() or lp.resolve() == lp.parent.resolve()
            except OSError:
                at_root = True
            self._local_up_btn.setMinimumSize(30, 28)
            self._local_up_btn.setVisible(True)
            self._local_up_btn.setEnabled(True)
            self._local_up_btn.setToolTip(
                "Up one folder" if not at_root else "Already at the root of this path (button stays visible)"
            )
        if hasattr(self, "_remote_up_btn"):
            rp = (self.remote_path or "").strip().rstrip("/") or "/"
            at_rr = rp in ("/", "")
            self._remote_up_btn.setMinimumSize(30, 28)
            self._remote_up_btn.setVisible(True)
            self._remote_up_btn.setEnabled(True)
            self._remote_up_btn.setToolTip(
                "Up one folder" if not at_rr else "Already at root (/) — button stays visible"
            )

    def go_local(self) -> None:
        txt = self._addr_local_text() or self.local_path
        if sys.platform == "win32" and re.fullmatch(r"[A-Za-z]:", txt):
            txt = txt + "\\"
        p = Path(txt)
        if p.exists() and p.is_dir():
            self.local_path = str(p.resolve())
            self._set_local_address(self.local_path)
            self.refresh_local()

    def local_up(self) -> None:
        p = Path(self.local_path).parent
        if p != Path(self.local_path):
            self.local_path = str(p)
            self._set_local_address(self.local_path)
            self.refresh_local()

    def refresh_local(self) -> None:
        self._notify_refresh_start("Local")
        self.local_table.setSortingEnabled(False)
        self.local_table.setRowCount(0)
        current = Path(self._addr_local_text() or self.local_path)
        if not current.exists() or not current.is_dir():
            self.local_table.setSortingEnabled(True)
            return
        self.local_path = str(current.resolve())
        self._set_local_address(self.local_path)
        rows = []
        parent = current.parent if current.parent != current else current
        rows.append((Path(parent), "Parent"))
        try:
            scan_rows: List[Path] = []
            with os.scandir(str(current)) as it:
                for ent in it:
                    try:
                        scan_rows.append(Path(ent.path))
                    except OSError:
                        continue
            for child in sorted(scan_rows, key=lambda p: (not p.is_dir(), p.name.lower())):
                rows.append((child, _local_type_label(child)))
        except OSError:
            pass
        self.local_table.setRowCount(len(rows))
        for i, (child, typ) in enumerate(rows):
            if typ == "Parent":
                icon = self.style().standardIcon(QStyle.SP_FileDialogToParent)
                name_item = _SortTableItem("..", icon, sort_key=(-2,))
                size_item = _SortTableItem("—", sort_key=(-1, 0))
                mtime_item = _SortTableItem("", sort_key=-1.0)
                type_item = _SortTableItem("Folder", sort_key=(-1, "folder"))
                self.local_table.setItem(i, 0, name_item)
                self.local_table.setItem(i, 1, size_item)
                self.local_table.setItem(i, 2, mtime_item)
                self.local_table.setItem(i, 3, type_item)
                self.local_table.item(i, 0).setData(Qt.UserRole, str(child))
                continue
            icon = _icon_for_local_path(child, self.icon_provider, self.style())
            display_name = child.name or str(child)
            name_item = _SortTableItem(display_name, icon, sort_key=_local_name_sort_key(child))
            name_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            self.local_table.setItem(i, 0, name_item)
            self.local_table.setItem(
                i, 1, _SortTableItem(_fmt_local_listing_size(child), sort_key=_local_size_sort_key(child))
            )
            self.local_table.setItem(
                i,
                2,
                _SortTableItem(
                    _fmt_mtime(child),
                    sort_key=_local_mtime_sort_key(child),
                ),
            )
            self.local_table.setItem(i, 3, _SortTableItem(typ, sort_key=_local_type_sort_key(child)))
            self.local_table.item(i, 0).setData(Qt.UserRole, str(child))
        self.local_table.setSortingEnabled(True)
        self.local_table.sortByColumn(0, Qt.AscendingOrder)
        self._last_refresh_note = datetime.now().strftime("%H:%M:%S")
        self._update_nav_buttons()
        self._notify_parent_status()
        self._notify_refresh_flash("Local")

    def _notify_parent_status(self) -> None:
        w = self.parent()
        while w:
            if hasattr(w, "_update_status_bar"):
                w._update_status_bar()
                break
            w = w.parent()

    def _notify_refresh_flash(self, side: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        w = self.parent()
        while w:
            if hasattr(w, "_flash_refresh_banner"):
                w._flash_refresh_banner(side, ts)
                break
            w = w.parent()

    def _notify_refresh_start(self, side: str) -> None:
        w = self.parent()
        while w:
            if hasattr(w, "_show_refreshing_banner"):
                w._show_refreshing_banner(side)
                break
            w = w.parent()

    def _report_remote_error(self, msg: str) -> None:
        txt = (msg or "").strip()
        if not txt:
            return
        self._log(f"Explorer remote error: {txt}")
        if "permission denied" in txt.lower():
            key = f"{self.kind}:{self.remote_path}:{txt}"
            if key != self._last_error_popup_key:
                self._last_error_popup_key = key
                QMessageBox.warning(self, "Remote permission denied", txt)

    def on_local_activated(self, item) -> None:
        """Double-click or Enter: enter folders; open files with the default app (single click only selects)."""
        it = self.local_table.item(item.row(), 0)
        if not it:
            return
        path = it.data(Qt.UserRole)
        if not path:
            return
        p = Path(path)
        if p.is_dir():
            self.local_path = str(p)
            self._set_local_address(str(p))
            self.refresh_local()
        elif p.is_file():
            self.local_table.selectRow(item.row())
            self._launch_local_file(p)

    def go_remote(self) -> None:
        self.remote_path = self._addr_remote_text() or self.remote_path
        self._set_remote_address(self.remote_path)
        self.refresh_remote()

    def remote_up(self) -> None:
        rp = (self.remote_path or "").strip().rstrip("/") or "/"
        if rp in ("", "/"):
            return
        self.remote_path = posixpath.dirname(rp) or "/"
        self._set_remote_address(self.remote_path)
        self.refresh_remote()

    def remote_root(self) -> None:
        self.remote_path = "/"
        self._set_remote_address(self.remote_path)
        self.refresh_remote()

    def refresh_remote(self) -> None:
        if self._remote_transfer_thread and self._remote_transfer_thread.isRunning():
            self._notify_parent_status()
            return
        self._notify_refresh_start("Remote")
        self.remote_path = self._addr_remote_text() or self.remote_path
        self._set_remote_address(self.remote_path)
        self._start_remote_refresh()

    def _start_remote_refresh(self) -> None:
        if self._remote_refresh_thread and self._remote_refresh_thread.isRunning():
            self._remote_refresh_pending = True
            return
        creds = (
            {
                "host": self._ssh_host,
                "port": self._ssh_port,
                "user": self._ssh_user,
                "password": self._ssh_password,
            }
            if self.kind == "sftp"
            else {
                "host": self._ftp_host,
                "port": self._ftp_port,
                "user": self._ftp_user,
                "password": self._ftp_password,
            }
        )
        th = _RemoteListThread(
            kind=self.kind,
            adb_path=self.get_adb_path(),
            adb_args=self._adb_prefix(),
            remote_path=self.remote_path,
            creds=creds,
        )
        th.done.connect(self._on_remote_refresh_done)
        th.finished.connect(th.deleteLater)
        self._remote_refresh_thread = th
        th.start()

    def _on_remote_refresh_done(self, rows, err: str) -> None:
        th = self.sender()
        if th is not self._remote_refresh_thread:
            return
        self._remote_refresh_thread = None
        _fill_remote_table(self.remote_table, rows or [], self.style(), self.icon_provider)
        msg = (err or "").strip()
        if self.kind == "adb":
            self._adb_last_error = msg
        elif self.kind == "sftp":
            self._sftp_last_error = msg
        else:
            self._ftp_last_error = msg
        if msg:
            self._report_remote_error(msg)
        else:
            self._last_error_popup_key = ""
        self._last_refresh_note = datetime.now().strftime("%H:%M:%S")
        self._update_nav_buttons()
        self._update_explorer_header()
        self._notify_parent_status()
        self._notify_refresh_flash("Remote")
        if self._remote_refresh_pending:
            self._remote_refresh_pending = False
            self._start_remote_refresh()

    def _refresh_adb(self) -> None:
        serial = _first_serial_token(self.get_device_serial()) or _first_serial_token(self._session_adb_serial)
        if not serial:
            self.remote_table.setRowCount(0)
            self._adb_last_error = ""
            return
        rp = (self.remote_path or "").strip() or "/"
        parent = posixpath.dirname(rp.rstrip("/")) or "/"
        rows: List[tuple] = []
        rows.append((RemoteItem("..", True, "", "", "", "", ""), parent))
        # Android shells vary; running a single shell command string is more compatible for paths with spaces.
        safe_rp = rp.replace("\\", "\\\\").replace('"', '\\"')
        code, stdout, stderr = run_adb(
            self.get_adb_path(),
            [*self._adb_prefix(), "shell", f'ls -la "{safe_rp}"'],
        )
        if code != 0:
            _fill_remote_table(self.remote_table, rows, self.style(), self.icon_provider)
            self._adb_last_error = stderr.strip() or "ADB list failed."
            self._report_remote_error(self._adb_last_error)
            return
        self._adb_last_error = ""
        self._last_error_popup_key = ""
        for line in stdout.splitlines():
            parsed = _parse_ls_line(line)
            if not parsed:
                continue
            rows.append((parsed, f"{rp.rstrip('/')}/{parsed.name}".replace("//", "/")))
        _fill_remote_table(self.remote_table, rows, self.style(), self.icon_provider)

    def _refresh_sftp(self) -> None:
        if self._sftp_client is None:
            self.remote_table.setRowCount(0)
            self._sftp_last_error = ""
            return
        path = self.remote_path.rstrip("/") or "/"
        try:
            attrs = sftp_listdir_attr_safe(self._sftp_client, path)
        except Exception as exc:
            self.remote_table.setRowCount(0)
            self._sftp_last_error = str(exc)
            self._report_remote_error(self._sftp_last_error)
            return
        self._sftp_last_error = ""
        self._last_error_popup_key = ""
        rows: List[tuple] = []
        parent = posixpath.dirname(path) or "/"
        rows.append((RemoteItem("..", True, "", "", "", "", ""), parent))
        from datetime import datetime

        for a in sorted(
            attrs, key=lambda x: (not _sftp_entry_is_dir(self._sftp_client, path, x), x.filename.lower())
        ):
            name = a.filename
            if name in (".", ".."):
                continue
            is_dir = _sftp_entry_is_dir(self._sftp_client, path, a)
            full = posixpath.join(path, name).replace("\\", "/")
            perm = _sftp_perm_str(a.st_mode)
            sz = str(a.st_size)
            mt = ""
            if a.st_mtime:
                mt = datetime.fromtimestamp(a.st_mtime).strftime("%Y-%m-%d %H:%M")
            rows.append((RemoteItem(name, is_dir, perm, "", "", sz, mt), full))
        _fill_remote_table(self.remote_table, rows, self.style(), self.icon_provider)

    def _refresh_ftp(self) -> None:
        if self._ftp_client is None:
            self.remote_table.setRowCount(0)
            self._ftp_last_error = ""
            return
        rp = self.remote_path.rstrip("/") or "/"
        try:
            _ftp_safe_cwd(self._ftp_client, rp)
        except error_perm as exc:
            self.remote_table.setRowCount(0)
            self._ftp_last_error = str(exc)
            self._report_remote_error(self._ftp_last_error)
            return
        self._ftp_last_error = ""
        self._last_error_popup_key = ""
        rows: List[tuple] = []
        parent = posixpath.dirname(rp) or "/"
        rows.append((RemoteItem("..", True, "", "", "", "", ""), parent))
        try:
            for name, facts in self._ftp_client.mlsd():
                if name in (".", ".."):
                    continue
                full = posixpath.join(rp, name).replace("\\", "/")
                rows.append(_ftp_remote_item_mlsd(name, facts, full))
        except (error_perm, AttributeError):
            for name in self._ftp_client.nlst():
                if name in (".", ".."):
                    continue
                full = posixpath.join(rp, name).replace("\\", "/")
                rows.append(_ftp_remote_item_nlst(self._ftp_client, name, full))
        _fill_remote_table(self.remote_table, rows, self.style(), self.icon_provider)

    def on_remote_activated(self, item) -> None:
        """Double-click or Enter: enter directories; open files with default app (single click only selects)."""
        it = self.remote_table.item(item.row(), 0)
        if not it:
            return
        info = it.data(Qt.UserRole) or {}
        if info.get("is_dir"):
            self.remote_path = info["path"]
            self._set_remote_address(self.remote_path)
            self.refresh_remote()
        else:
            name_it = self.remote_table.item(item.row(), 0)
            if name_it and name_it.text() == "..":
                return
            self.remote_table.selectRow(item.row())
            self._open_remote_default_app(info["path"])

    def status_line(self) -> str:
        ln = self.local_table.rowCount()
        rn = self.remote_table.rowCount()
        err = self._adb_last_error or self._sftp_last_error or self._ftp_last_error
        base = f"{self.kind.upper()}  ·  Local: {ln}  ·  Remote: {rn} @ {self.remote_path}"
        if self._last_refresh_note:
            base += f"  ·  Refreshed {self._last_refresh_note}"
        return f"{base}  ·  {err}" if err else base

    def _drop_local_paths_push(self, paths: List[str]) -> None:
        items: List[str] = []
        for p in paths:
            if not p:
                continue
            lp = Path(p)
            if lp.is_file() or lp.is_dir():
                items.append(p)
        if not items:
            QMessageBox.information(self, "Push", "Drop one or more files or folders.")
            return
        self.push_paths(items)

    def find_in_local(self) -> None:
        dlg = FindFilesDialog(self, "local", self)
        dlg.exec_()

    def find_in_remote(self) -> None:
        dlg = FindFilesDialog(self, "remote", self)
        dlg.exec_()

    def new_local_file(self) -> None:
        name, ok = QInputDialog.getText(self, "New file", "File name:")
        if not ok or not name.strip():
            return
        p = Path(self.local_path) / name.strip()
        if p.exists():
            QMessageBox.warning(self, "New file", "A file or folder with that name already exists.")
            return
        try:
            p.touch()
            self.refresh_local()
        except OSError as exc:
            QMessageBox.warning(self, "New file", str(exc))

    def new_local_folder(self) -> None:
        name, ok = QInputDialog.getText(self, "New folder", "Folder name:")
        if not ok or not name.strip():
            return
        p = Path(self.local_path) / name.strip()
        if p.exists():
            QMessageBox.warning(self, "New folder", "A file or folder with that name already exists.")
            return
        try:
            p.mkdir(parents=True)
            self.refresh_local()
        except OSError as exc:
            QMessageBox.warning(self, "New folder", str(exc))

    def edit_local(self) -> None:
        path = self._selected_local()
        if not path:
            QMessageBox.information(self, "Edit", "Select a local file first.")
            return
        p = Path(path)
        if p.is_dir():
            QMessageBox.information(self, "Edit", "Select a file, not a folder.")
            return
        if not p.is_file():
            return
        try:
            sz = p.stat().st_size
        except OSError:
            sz = 0
        if sz > _MAX_INLINE_EDITOR_BYTES:
            QMessageBox.information(
                self,
                "Edit",
                f"This file is large ({_human_bytes(sz)}). Opening in external app for responsiveness.",
            )
            self._launch_local_file(p)
            return
        PlainTextEditorDialog(self, p).exec_()
        self.refresh_local()

    def open_local(self) -> None:
        path = self._selected_local()
        if not path:
            QMessageBox.information(self, "Open", "Select a local file first.")
            return
        p = Path(path)
        if p.is_dir():
            QMessageBox.information(self, "Open", "Select a file, not a folder.")
            return
        if not p.is_file():
            return
        self._launch_local_file(p)

    def _launch_local_file(self, p: Path) -> None:
        if not p.is_file():
            return
        url = QUrl.fromLocalFile(str(p.resolve()))
        if not QDesktopServices.openUrl(url):
            QMessageBox.warning(
                self,
                "Open",
                "No default application is associated with this file.\n"
                "Use Edit for the built-in text editor.",
            )

    def open_remote(self) -> None:
        info = self._selected_remote()
        if not info:
            QMessageBox.information(self, "Open", "Select a remote file first.")
            return
        if info.get("is_dir"):
            QMessageBox.information(self, "Open", "Select a file, not a folder.")
            return
        name_it = self.remote_table.item(self.remote_table.currentRow(), 0)
        if name_it and name_it.text() == "..":
            return
        self._open_remote_default_app(info["path"])

    def delete_local(self) -> None:
        path = self._selected_local()
        if not path:
            QMessageBox.information(self, "Delete", "Select a local file or folder first.")
            return
        p = Path(path)
        if not p.exists():
            return
        if QMessageBox.question(self, "Delete", f"Delete?\n{p}") != QMessageBox.Yes:
            return
        self._log(f"Explorer: delete local {p}")
        self._start_delete_job(
            mode="local",
            target=str(p),
            is_dir=p.is_dir(),
            done_cb=lambda ok, err: self._on_local_delete_done(ok, err),
        )

    def _on_local_delete_done(self, ok: bool, err: str) -> None:
        if ok:
            self._log("Explorer: local delete completed.")
            self.refresh_local()
            return
        QMessageBox.warning(self, "Delete", err or "Delete failed.")

    def local_properties(self) -> None:
        path = self._selected_local()
        if not path:
            QMessageBox.information(self, "Properties", "Select a local item first.")
            return
        p = Path(path)
        try:
            st = p.stat()
            rows: List[Tuple[str, str]] = [
                ("Path", str(p.resolve())),
                ("Name", p.name),
                (
                    "Type",
                    "Directory"
                    if p.is_dir()
                    else ("Symbolic link" if p.is_symlink() else "File"),
                ),
            ]
            if p.is_file():
                rows.append(("Size", _human_bytes(st.st_size)))
                rows.append(("Size (bytes)", str(st.st_size)))
            elif p.is_dir():
                try:
                    n = sum(1 for _ in p.iterdir())
                    rows.append(("Immediate children", str(n)))
                except OSError:
                    pass
                ds = _dir_size_walk(p)
                if ds is None:
                    rows.append(("Total size (folder tree)", "Not computed (too many entries)"))
                else:
                    rows.append(("Total size (folder tree)", _human_bytes(ds)))
            rows.append(("Modified", datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")))
            rows.append(
                (
                    "Metadata changed",
                    datetime.fromtimestamp(getattr(st, "st_ctime", st.st_mtime)).strftime("%Y-%m-%d %H:%M:%S"),
                )
            )
            rows.append(("Mode", _safe_mode_oct(st.st_mode)))
            _show_properties_dialog(self, "Properties — local", rows)
        except OSError as exc:
            QMessageBox.warning(self, "Properties", str(exc))

    def remote_properties(self) -> None:
        info = self._selected_remote()
        if not info:
            QMessageBox.information(self, "Properties", "Select a remote item first.")
            return
        name_it = self.remote_table.item(self.remote_table.currentRow(), 0)
        if name_it and name_it.text() == "..":
            return
        rp = info.get("path", "")
        rows: List[Tuple[str, str]] = [
            ("Path", rp),
            ("Name", Path(rp).name if rp else ""),
            ("Type", "Directory" if info.get("is_dir") else "File"),
        ]
        if self.kind == "adb":
            code, out, err = run_adb(
                self.get_adb_path(), [*self._adb_prefix(), "shell", "ls", "-ld", rp], timeout=25
            )
            rows.append(("ls -ld", (out or err or "").strip() or "(no output)"))
            _, out2, err2 = run_adb(
                self.get_adb_path(), [*self._adb_prefix(), "shell", "stat", rp], timeout=25
            )
            stat_txt = (out2 or err2 or "").strip()
            rows.append(("stat", stat_txt if stat_txt else "(no output)"))
        elif self.kind == "sftp" and self._sftp_client:
            try:
                st = self._sftp_client.stat(rp)
                rows.append(("Size", _human_bytes(st.st_size)))
                rows.append(("Size (bytes)", str(st.st_size)))
                rows.append(("Modified", datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")))
                rows.append(("Mode", _safe_mode_oct(getattr(st, "st_mode", 0))))
                rows.append(("UID", str(getattr(st, "st_uid", "?"))))
                rows.append(("GID", str(getattr(st, "st_gid", "?"))))
            except Exception as exc:
                rows.append(("Error", str(exc)))
        elif self.kind == "ftp" and self._ftp_client:
            rows.append(("Note", "Detailed attributes depend on server LIST/MLSD support."))
        it = self.remote_table.item(self.remote_table.currentRow(), 1)
        itp = self.remote_table.item(self.remote_table.currentRow(), 2)
        itd = self.remote_table.item(self.remote_table.currentRow(), 3)
        if it:
            rows.append(("Size (listed)", it.text()))
        if itp:
            rows.append(("Permissions (listed)", itp.text()))
        if itd:
            rows.append(("Date modified (listed)", itd.text()))
        _show_properties_dialog(self, "Properties — remote", rows)

    def new_remote_file(self) -> None:
        name, ok = QInputDialog.getText(self, "New file", "File name:")
        if not ok or not name.strip():
            return
        base = self.remote_path.rstrip("/") or "/"
        path = posixpath.join(base, name.strip()).replace("\\", "/")

        if self.kind == "adb":
            code, _, stderr = run_adb(self.get_adb_path(), [*self._adb_prefix(), "shell", "touch", path])
            if code == 0:
                self.refresh_remote()
            else:
                QMessageBox.warning(self, "New file", stderr or "Failed.")
            return
        if self.kind == "sftp" and self._sftp_client:
            try:
                self._sftp_client.putfo(io.BytesIO(b""), path)
                self.refresh_remote()
            except Exception as exc:
                QMessageBox.warning(self, "New file", str(exc))
            return
        if self.kind == "ftp" and self._ftp_client:
            try:
                _ftp_safe_cwd(self._ftp_client, self.remote_path.rstrip("/") or "/")
                self._ftp_client.storbinary(f"STOR {_ftp_quote_token(name.strip())}", io.BytesIO(b""))
                self.refresh_remote()
            except Exception as exc:
                QMessageBox.warning(self, "New file", str(exc))

    def edit_remote(self) -> None:
        info = self._selected_remote()
        if not info:
            QMessageBox.information(self, "Edit", "Select a remote file first.")
            return
        if info.get("is_dir"):
            QMessageBox.information(self, "Edit", "Select a file, not a folder.")
            return
        name_it = self.remote_table.item(self.remote_table.currentRow(), 0)
        if name_it and name_it.text() == "..":
            return
        self._open_remote_editor(info["path"])

    def _upload_local_to_remote(self, local_fs_path: str, remote_file_path: str, *, quiet: bool = False) -> bool:
        if self.kind == "adb":
            self._log(f"Explorer: push (save) → {remote_file_path}")
            _ADB_STAGE_MAX = 128 * 1024 * 1024
            try:
                sz = os.path.getsize(local_fs_path)
            except OSError as exc:
                if not quiet:
                    QMessageBox.warning(self, "Save to device", str(exc))
                self._log(f"Explorer: push stat failed: {exc}")
                return False
            if sz > _ADB_STAGE_MAX:
                code, msg = self._adb_progress_exec(
                    "Push to device",
                    [*self._adb_prefix(), "push", local_fs_path, remote_file_path],
                    timeout=600,
                    quiet=quiet,
                )
            else:
                attempts = 28 if quiet else 14
                data = _read_file_bytes_with_retry(local_fs_path, attempts=attempts, delay=0.3)
                if data is None:
                    if not quiet:
                        QMessageBox.warning(
                            self,
                            "Save to device",
                            "Could not read the file (it may be locked by another program). "
                            "Close the other app or save, then retry.",
                        )
                    self._log("Explorer: push aborted — could not read local file after retries.")
                    return False
                fd, tmp = tempfile.mkstemp(prefix="dd_adbpush_", dir=tempfile.gettempdir())
                try:
                    with os.fdopen(fd, "wb") as f:
                        f.write(data)
                    try:
                        os.chmod(tmp, 0o600)
                    except OSError:
                        pass
                    code, msg = self._adb_progress_exec(
                        "Push to device",
                        [*self._adb_prefix(), "push", tmp, remote_file_path],
                        timeout=600,
                        quiet=quiet,
                    )
                finally:
                    try:
                        os.unlink(tmp)
                    except OSError:
                        pass
            if code != 0:
                if not quiet:
                    QMessageBox.warning(self, "Save to device", msg or "Push failed.")
                self._log(f"Explorer: push failed ({code}) {msg[:300]}")
                return False
            self._log("Explorer: push (save) completed.")
            return True
        if self.kind == "sftp" and self._sftp_client:
            try:
                if quiet:
                    self._sftp_client.put(local_fs_path, remote_file_path)
                    self._log(f"Explorer: SFTP uploaded {remote_file_path}")
                    return True
                try:
                    total = max(os.path.getsize(local_fs_path), 1)
                except OSError:
                    total = 1
                dlg = QProgressDialog("Uploading to server…", None, 0, 100, self)
                dlg.setCancelButton(None)
                dlg.setMinimumDuration(0)
                dlg.setWindowModality(Qt.ApplicationModal)

                def _cb(sent: int, size: int) -> None:
                    if size:
                        dlg.setValue(min(99, int(100 * sent / max(size, 1))))
                    QApplication.processEvents()

                self._sftp_client.put(local_fs_path, remote_file_path, callback=_cb)
                dlg.setValue(100)
                dlg.close()
                self._log(f"Explorer: SFTP uploaded {remote_file_path}")
                return True
            except Exception as exc:
                if not quiet:
                    QMessageBox.warning(self, "Save to remote", str(exc))
                self._log(f"Explorer: SFTP upload error: {exc}")
                return False
        if self.kind == "ftp" and self._ftp_client:
            try:
                if quiet:
                    parent = posixpath.dirname(remote_file_path) or "/"
                    fn = posixpath.basename(remote_file_path)
                    _ftp_safe_cwd(self._ftp_client, parent)
                    with open(local_fs_path, "rb") as f:
                        self._ftp_client.storbinary(f"STOR {_ftp_quote_token(fn)}", f, blocksize=65536)
                    self._log(f"Explorer: FTP uploaded {remote_file_path}")
                    return True
                total = max(os.path.getsize(local_fs_path), 1)
                dlg = QProgressDialog("Uploading (FTP)…", None, 0, 100, self)
                dlg.setCancelButton(None)
                dlg.setMinimumDuration(0)
                dlg.setWindowModality(Qt.ApplicationModal)
                sent = [0]

                def _dcb(block: bytes) -> None:
                    sent[0] += len(block)
                    dlg.setValue(min(99, int(100 * sent[0] / total)))
                    QApplication.processEvents()

                parent = posixpath.dirname(remote_file_path) or "/"
                fn = posixpath.basename(remote_file_path)
                _ftp_safe_cwd(self._ftp_client, parent)
                with open(local_fs_path, "rb") as f:
                    self._ftp_client.storbinary(
                        f"STOR {_ftp_quote_token(fn)}", f, blocksize=65536, callback=_dcb
                    )
                dlg.setValue(100)
                dlg.close()
                self._log(f"Explorer: FTP uploaded {remote_file_path}")
                return True
            except Exception as exc:
                if not quiet:
                    QMessageBox.warning(self, "Save to remote", str(exc))
                return False
        return False

    def _norm_local_path(self, path: str) -> str:
        return os.path.normcase(os.path.normpath(path))

    def _stable_open_cache_path(self, remote_path: str) -> str:
        """Same local path for each remote file so re-open always pulls/overwrites one cache (device stays in sync after upload)."""
        serial = _first_serial_token(self.get_device_serial()) or _first_serial_token(self._session_adb_serial) or "default"
        key = f"{self.kind}|{serial}|{remote_path}"
        h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
        root = Path(tempfile.gettempdir()) / "adbnik_open_cache" / h
        root.mkdir(parents=True, exist_ok=True)
        return str(root / posixpath.basename(remote_path))

    def _register_external_open_sync(self, local_path: str, remote_path: str) -> None:
        """Watch file and its folder (atomic saves); push back to `remote_path` on change."""
        key = self._norm_local_path(local_path)
        self._ext_sync_remote[key] = remote_path
        if self._ext_fs_watcher is None:
            self._ext_fs_watcher = QFileSystemWatcher(self)
            self._ext_fs_watcher.fileChanged.connect(self._on_external_open_file_changed)
            self._ext_fs_watcher.directoryChanged.connect(self._on_external_dir_changed)
        for p in (local_path, str(Path(local_path).parent)):
            if p not in self._ext_fs_watcher.files():
                self._ext_fs_watcher.addPath(p)

    def _readd_external_watch_paths(self, local_path: str) -> None:
        if self._ext_fs_watcher is None:
            return
        for p in (local_path, str(Path(local_path).parent)):
            if os.path.exists(p) and p not in self._ext_fs_watcher.files():
                self._ext_fs_watcher.addPath(p)

    def _on_external_dir_changed(self, dir_path: str) -> None:
        """Some apps save via temp file then rename in the same folder."""
        nd = self._norm_local_path(dir_path)
        for key, remote in list(self._ext_sync_remote.items()):
            if self._norm_local_path(str(Path(key).parent)) != nd:
                continue
            QTimer.singleShot(500, lambda k=key, r=remote: self._schedule_external_sync(k, r))

    def _schedule_external_sync(self, path: str, remote: str) -> None:
        key = self._norm_local_path(path)
        old_t = self._ext_sync_timers.pop(key, None)
        if old_t is not None:
            old_t.stop()
            old_t.deleteLater()
        t = QTimer(self)
        t.setSingleShot(True)
        t.setInterval(2000)
        t.timeout.connect(lambda: self._sync_external_file_if_ready(path, remote, 0))
        self._ext_sync_timers[key] = t
        t.start()

    def _poll_external_mtime(self) -> None:
        """Fallback when editors do not trigger QFileSystemWatcher reliably."""
        if not self._ext_sync_remote:
            return
        for key, remote in list(self._ext_sync_remote.items()):
            if not os.path.isfile(key):
                continue
            try:
                m = os.path.getmtime(key)
            except OSError:
                continue
            nk = self._norm_local_path(key)
            prev = self._ext_last_mtime.get(nk)
            if prev is None:
                self._ext_last_mtime[nk] = m
                continue
            if m > prev + 0.5:
                self._ext_last_mtime[nk] = m
                self._schedule_external_sync(key, remote)

    def _sync_external_file_if_ready(self, path: str, remote: str, attempt: int = 0) -> None:
        if not os.path.isfile(path):
            return
        if attempt == 0:
            self._log(f"Explorer: external app saved file → syncing to remote {remote}")
        ok = self._upload_local_to_remote(path, remote, quiet=True)
        if ok:
            self.refresh_remote()
            self._select_remote_basename(posixpath.basename(remote))
            self._readd_external_watch_paths(path)
            nk = self._norm_local_path(path)
            try:
                self._ext_last_mtime[nk] = os.path.getmtime(path)
            except OSError:
                pass
            return
        if attempt < 5:
            self._log(f"Explorer: auto-sync retry {attempt + 1}/5 (editor may still have the file locked)…")
            QTimer.singleShot(1800, lambda: self._sync_external_file_if_ready(path, remote, attempt + 1))

    def _on_external_open_file_changed(self, path: str) -> None:
        key = self._norm_local_path(path)
        remote = self._ext_sync_remote.get(key)
        if not remote:
            for k, r in self._ext_sync_remote.items():
                if self._norm_local_path(k) == key:
                    key = k
                    remote = r
                    break
        if not remote:
            return
        old_t = self._ext_sync_timers.pop(key, None)
        if old_t is not None:
            old_t.stop()
            old_t.deleteLater()

        def _fire():
            self._ext_sync_timers.pop(key, None)
            if not os.path.isfile(path):
                QTimer.singleShot(900, lambda: self._sync_external_file_if_ready(path, remote, 0))
                return
            self._sync_external_file_if_ready(path, remote, 0)

        t = QTimer(self)
        t.setSingleShot(True)
        t.setInterval(2000)
        t.timeout.connect(_fire)
        self._ext_sync_timers[key] = t
        t.start()

    def _open_remote_default_app(self, remote_path: str) -> None:
        """Download to a stable cache path and open with the default app; saves sync back automatically."""
        dest = self._stable_open_cache_path(remote_path)
        try:
            if self.kind == "adb":
                code, msg = self._adb_progress_exec(
                    "Download to open",
                    [*self._adb_prefix(), "pull", remote_path, dest],
                    timeout=600,
                )
                if code != 0:
                    QMessageBox.warning(self, "Open", msg or "Download failed.")
                    return
            elif self.kind == "sftp" and self._sftp_client:
                self._sftp_get_with_progress(remote_path, dest)
            elif self.kind == "ftp" and self._ftp_client:
                parent = posixpath.dirname(remote_path) or "/"
                fn = posixpath.basename(remote_path)
                _ftp_safe_cwd(self._ftp_client, parent)
                with open(dest, "wb") as out:
                    self._ftp_client.retrbinary(f"RETR {_ftp_quote_token(fn)}", out.write)
            else:
                return
            if not os.path.isfile(dest):
                QMessageBox.warning(self, "Open", "Could not download file.")
                return
            self._register_external_open_sync(dest, remote_path)
            nk = self._norm_local_path(dest)
            try:
                self._ext_last_mtime[nk] = os.path.getmtime(dest)
            except OSError:
                pass
            url = QUrl.fromLocalFile(os.path.normpath(dest))
            if not QDesktopServices.openUrl(url):
                QMessageBox.warning(self, "Open", "No default application for this file type.")
        except Exception as exc:
            QMessageBox.warning(self, "Open", str(exc))

    def _open_remote_editor(self, remote_path: str) -> None:
        tmpdir = tempfile.mkdtemp(prefix="rw_edit_")
        dest = os.path.join(tmpdir, posixpath.basename(remote_path))
        try:
            if self.kind == "adb":
                self._log(f"Explorer: pull for edit ← {remote_path}")
                code, msg = self._adb_progress_exec(
                    "Pull for edit",
                    [*self._adb_prefix(), "pull", remote_path, dest],
                    timeout=600,
                )
                if code != 0:
                    QMessageBox.warning(self, "Edit", msg or "Pull failed.")
                    self._log(f"Explorer: pull for edit failed ({code})")
                    return
            elif self.kind == "sftp" and self._sftp_client:
                self._sftp_get_with_progress(remote_path, dest)
            elif self.kind == "ftp" and self._ftp_client:
                parent = posixpath.dirname(remote_path) or "/"
                fn = posixpath.basename(remote_path)
                _ftp_safe_cwd(self._ftp_client, parent)
                with open(dest, "wb") as out:
                    self._ftp_client.retrbinary(f"RETR {_ftp_quote_token(fn)}", out.write)
            else:
                return
            if not os.path.isfile(dest):
                QMessageBox.warning(self, "Edit", "Could not download file for editing.")
                return
            try:
                rsz = os.path.getsize(dest)
            except OSError:
                rsz = 0
            if rsz > _MAX_INLINE_EDITOR_BYTES:
                self._log(
                    f"Explorer: remote file is large ({_human_bytes(rsz)}), opening externally for responsiveness."
                )
                self._register_external_open_sync(dest, remote_path)
                if not QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.normpath(dest))):
                    QMessageBox.warning(self, "Edit", "No default application for this file type.")
                return

            def _sync_to_remote(tmp: Path) -> bool:
                ok = self._upload_local_to_remote(str(tmp), remote_path)
                if ok:
                    self.refresh_remote()
                    self._select_remote_basename(posixpath.basename(remote_path))
                return ok

            if PlainTextEditorDialog(self, Path(dest), after_save=_sync_to_remote).exec_() != QDialog.Accepted:
                return
            self.refresh_remote()
        except Exception as exc:
            QMessageBox.warning(self, "Edit", str(exc))
        finally:
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except OSError:
                pass

    # --- toolbar actions (this session only) ---
    def _selected_local(self) -> Optional[str]:
        row = self.local_table.currentRow()
        if row < 0:
            return None
        it = self.local_table.item(row, 0)
        return it.data(Qt.UserRole) if it else None

    def _selected_remote(self) -> Optional[dict]:
        row = self.remote_table.currentRow()
        if row < 0:
            return None
        it = self.remote_table.item(row, 0)
        return it.data(Qt.UserRole) if it else None

    def _ensure_local_pull_target_or_warn(self) -> bool:
        target_dir = self.local_path
        if Path(target_dir).is_dir():
            return True
        QMessageBox.warning(
            self,
            "Pull",
            "Current local folder is not valid. Fix the path in the local address bar and refresh, then try again.",
        )
        return False

    def _drop_remote_infos_pull(self, infos: List[dict]) -> None:
        good = [i for i in infos if isinstance(i, dict) and i.get("path")]
        if not good:
            return
        if not self._ensure_local_pull_target_or_warn():
            return
        if self.kind == "adb":
            self._queue_adb_pull(good, notify_final=True, select_final=True)
            return
        if self.kind in ("sftp", "ftp"):
            items = [{"remote": str(i.get("path", "")), "is_dir": bool(i.get("is_dir"))} for i in good]
            self._start_remote_transfer(mode="pull", items=items)
            return
        n = len(good)
        for idx, info in enumerate(good):
            path = str(info["path"])
            pulled_name = posixpath.basename(path.rstrip("/")) or path
            last = idx == n - 1
            self._pull_single_remote_item(
                info,
                pulled_name,
                notify=last,
                select_basename=last,
            )

    def _pull_single_remote_item(
        self,
        info: dict,
        pulled_name: str,
        *,
        notify: bool = True,
        select_basename: bool = True,
    ) -> None:
        target_dir = self.local_path

        if self.kind == "adb":
            self._queue_adb_pull(
                [info],
                notify_final=notify,
                select_final=select_basename,
                explicit_final_name=pulled_name,
            )
            return
        if self.kind in ("sftp", "ftp"):
            self._start_remote_transfer(
                mode="pull",
                items=[{"remote": str(info.get("path", "")), "is_dir": bool(info.get("is_dir"))}],
            )
            return

        if info.get("is_dir"):
            if self.kind == "sftp" and self._sftp_client:
                try:
                    dlg = QProgressDialog("Downloading folder (SFTP)…", None, 0, 0, self)
                    dlg.setCancelButton(None)
                    dlg.setMinimumDuration(0)
                    dlg.setWindowModality(Qt.ApplicationModal)
                    QApplication.processEvents()
                    self._sftp_pull_tree(info["path"], target_dir)
                    dlg.close()
                    self._log(f"Explorer: SFTP folder pull → {target_dir}")
                    self.refresh_local()
                    if notify:
                        self._notify_path_result(
                            "Pull complete",
                            f"Pulled folder: {info['path']}\nTo local folder:",
                            target_dir,
                        )
                    if select_basename:
                        self._select_local_basename(pulled_name)
                except Exception as exc:
                    dlg.close()
                    self._log(f"Explorer: SFTP pull error: {exc}")
                    QMessageBox.warning(self, "Pull", str(exc))
                return
            if self.kind == "ftp" and self._ftp_client:
                try:
                    dlg = QProgressDialog("Downloading folder (FTP)…", None, 0, 0, self)
                    dlg.setCancelButton(None)
                    dlg.setMinimumDuration(0)
                    dlg.setWindowModality(Qt.ApplicationModal)
                    QApplication.processEvents()
                    self._ftp_pull_tree(info["path"], target_dir)
                    dlg.close()
                    self._log(f"Explorer: FTP folder pull → {target_dir}")
                    self.refresh_local()
                    if notify:
                        self._notify_path_result(
                            "Pull complete",
                            f"Pulled folder: {info['path']}\nTo local folder:",
                            target_dir,
                        )
                    if select_basename:
                        self._select_local_basename(pulled_name)
                except Exception as exc:
                    dlg.close()
                    QMessageBox.warning(self, "Pull", str(exc))
                return
            QMessageBox.information(self, "Pull", "Folder download is not available for this session type.")
            return

        dest = str(Path(target_dir) / Path(info["path"]).name)

        if self.kind == "sftp" and self._sftp_client:
            try:
                self._sftp_get_with_progress(info["path"], dest)
                self._log(f"Explorer: SFTP pull saved → {dest}")
                self.refresh_local()
                if notify:
                    self._notify_path_result(
                        "Pull complete",
                        f"Pulled: {info['path']}\nSaved to:",
                        dest,
                    )
                if select_basename:
                    self._select_local_basename(pulled_name)
            except Exception as exc:
                self._log(f"Explorer: SFTP pull error: {exc}")
                QMessageBox.warning(self, "Pull", str(exc))
            return
        if self.kind == "ftp" and self._ftp_client:
            try:
                dlg = QProgressDialog("Downloading (FTP)…", None, 0, 0, self)
                dlg.setCancelButton(None)
                dlg.setMinimumDuration(0)
                dlg.setWindowModality(Qt.ApplicationModal)
                QApplication.processEvents()
                parent = posixpath.dirname(info["path"]) or "/"
                fn = posixpath.basename(info["path"])
                _ftp_safe_cwd(self._ftp_client, parent)
                with open(dest, "wb") as out:
                    self._ftp_client.retrbinary(f"RETR {_ftp_quote_token(fn)}", out.write)
                dlg.close()
                self._log(f"Explorer: FTP pull saved → {dest}")
                self.refresh_local()
                if notify:
                    self._notify_path_result(
                        "Pull complete",
                        f"Pulled: {info['path']}\nSaved to:",
                        dest,
                    )
                if select_basename:
                    self._select_local_basename(pulled_name)
            except Exception as exc:
                QMessageBox.warning(self, "Pull", str(exc))

    def pull_selected(self) -> None:
        info = self._selected_remote()
        if not info:
            QMessageBox.information(self, "Pull", "Select a remote item first.")
            return
        name_it = self.remote_table.item(self.remote_table.currentRow(), 0)
        if name_it and name_it.text() == "..":
            return
        pulled_name = (name_it.text() or "").strip()
        if not self._ensure_local_pull_target_or_warn():
            return
        self._pull_single_remote_item(info, pulled_name)

    def push_paths(self, paths: List[str]) -> None:
        n_ok = 0
        items: List[str] = []
        for p in paths:
            if not p:
                continue
            lp = Path(p)
            if not lp.exists():
                continue
            if lp.is_file():
                items.append(p)
            elif lp.is_dir() and self.kind in ("adb", "sftp", "ftp"):
                items.append(p)
        if not items:
            QMessageBox.information(
                self,
                "Push",
                "Nothing to push. Select file(s) or folder(s) (ADB / SFTP / FTP).",
            )
            return
        self._log(f"Explorer: push {len(items)} item(s) → {self.remote_path}")
        if self.kind == "adb":
            self._queue_adb_push(items)
            return
        if self.kind in ("sftp", "ftp"):
            self._start_remote_transfer(mode="push", items=[{"local": p} for p in items])
            return
        last_pushed = ""
        for idx, local in enumerate(items):
            lp = Path(local)
            name = lp.name
            remote_file = posixpath.join(self.remote_path.rstrip("/"), name).replace("\\", "/")
            if lp.is_dir():
                if self.kind == "adb":
                    label = f"Push ({idx + 1}/{len(items)})"
                    code, msg = self._adb_progress_exec(
                        label,
                        [*self._adb_prefix(), "push", local, self.remote_path],
                        timeout=600,
                    )
                    if code != 0:
                        self._log(f"Explorer: push failed ({code}) {msg[:300]}")
                        QMessageBox.warning(self, "Push", msg or "Failed.")
                        return
                    n_ok += 1
                    last_pushed = name
                    continue
                if self.kind == "sftp" and self._sftp_client:
                    try:
                        dlg = QProgressDialog(f"SFTP folder upload ({idx + 1}/{len(items)})…", None, 0, 0, self)
                        dlg.setCancelButton(None)
                        dlg.setMinimumDuration(0)
                        dlg.setWindowModality(Qt.ApplicationModal)
                        QApplication.processEvents()
                        if self._sftp_put_tree(lp, self.remote_path.rstrip("/")):
                            n_ok += 1
                            last_pushed = name
                        dlg.close()
                    except Exception as exc:
                        dlg.close()
                        self._log(f"Explorer: SFTP push error: {exc}")
                        QMessageBox.warning(self, "Push", str(exc))
                        return
                    continue
                if self.kind == "ftp" and self._ftp_client:
                    try:
                        dlg = QProgressDialog(f"FTP folder upload ({idx + 1}/{len(items)})…", None, 0, 0, self)
                        dlg.setCancelButton(None)
                        dlg.setMinimumDuration(0)
                        dlg.setWindowModality(Qt.ApplicationModal)
                        QApplication.processEvents()
                        if self._ftp_put_tree(lp, self.remote_path.rstrip("/")):
                            n_ok += 1
                            last_pushed = name
                        dlg.close()
                    except Exception as exc:
                        dlg.close()
                        QMessageBox.warning(self, "Push", str(exc))
                        return
                    continue
                continue
            if self.kind == "adb":
                label = f"Push ({idx + 1}/{len(items)})"
                code, msg = self._adb_progress_exec(
                    label,
                    [*self._adb_prefix(), "push", local, self.remote_path],
                    timeout=600,
                )
                if code != 0:
                    self._log(f"Explorer: push failed ({code}) {msg[:300]}")
                    QMessageBox.warning(self, "Push", msg or "Failed.")
                    return
                n_ok += 1
                last_pushed = name
                continue
            if self.kind == "sftp" and self._sftp_client:
                try:
                    try:
                        total = max(os.path.getsize(local), 1)
                    except OSError:
                        total = 1
                    dlg = QProgressDialog(f"Upload ({idx + 1}/{len(items)})…", None, 0, 100, self)
                    dlg.setCancelButton(None)
                    dlg.setMinimumDuration(0)
                    dlg.setWindowModality(Qt.ApplicationModal)

                    def _cb(sent: int, size: int) -> None:
                        if size:
                            dlg.setValue(min(99, int(100 * sent / max(size, 1))))
                        QApplication.processEvents()

                    self._sftp_client.put(local, remote_file, callback=_cb)
                    dlg.setValue(100)
                    dlg.close()
                    n_ok += 1
                    last_pushed = name
                except Exception as exc:
                    self._log(f"Explorer: SFTP push error: {exc}")
                    QMessageBox.warning(self, "Push", str(exc))
                    return
                continue
            if self.kind == "ftp" and self._ftp_client:
                try:
                    total = max(os.path.getsize(local), 1)
                    dlg = QProgressDialog(f"Upload FTP ({idx + 1}/{len(items)})…", None, 0, 100, self)
                    dlg.setCancelButton(None)
                    dlg.setMinimumDuration(0)
                    dlg.setWindowModality(Qt.ApplicationModal)
                    sent = [0]

                    def _dcb(block: bytes) -> None:
                        sent[0] += len(block)
                        dlg.setValue(min(99, int(100 * sent[0] / total)))
                        QApplication.processEvents()

                    _ftp_safe_cwd(self._ftp_client, self.remote_path.rstrip("/") or "/")
                    with open(local, "rb") as f:
                        self._ftp_client.storbinary(
                            f"STOR {_ftp_quote_token(name)}", f, blocksize=65536, callback=_dcb
                        )
                    dlg.setValue(100)
                    dlg.close()
                    n_ok += 1
                    last_pushed = name
                except Exception as exc:
                    QMessageBox.warning(self, "Push", str(exc))
                    return
        if n_ok:
            self._log(
                f"Explorer: push completed ({n_ok} item(s)) from local folder '{self.local_path}' "
                f"to remote folder '{self.remote_path}'."
            )
            self.refresh_remote()
            QMessageBox.information(
                self,
                "Push",
                f"Transferred {n_ok} item(s)\nFrom: {self.local_path}\nTo: {self.remote_path}",
            )
            if last_pushed:
                self._select_remote_basename(last_pushed)

    def push_selected(self) -> None:
        rows = sorted({i.row() for i in self.local_table.selectedItems()})
        paths = []
        for r in rows:
            it = self.local_table.item(r, 0)
            if not it:
                continue
            p = it.data(Qt.UserRole)
            if not p:
                continue
            pp = Path(p)
            if pp.is_file() or pp.is_dir():
                paths.append(p)
        if len(paths) > 1:
            self.push_paths(paths)
            return
        local = paths[0] if paths else None
        if not local:
            local, _ = QFileDialog.getOpenFileName(self, "Select file", self.local_path)
            if not local:
                return
        self.push_paths([local])

    def delete_selected_remote(self) -> None:
        info = self._selected_remote()
        if not info:
            return
        row = self.remote_table.currentRow()
        name_it = self.remote_table.item(row, 0)
        if name_it and name_it.text() == "..":
            return
        if QMessageBox.question(self, "Delete", f"Delete?\n{info['path']}") != QMessageBox.Yes:
            return

        dlg = QProgressDialog("Deleting…", None, 0, 0, self)
        dlg.setCancelButton(None)
        dlg.setMinimumDuration(0)
        dlg.setWindowModality(Qt.ApplicationModal)
        QApplication.processEvents()

        if self.kind == "adb":
            self._log(f"Explorer: delete remote {info['path']}")
            dlg.close()
            self._start_delete_job(
                mode="adb",
                target=str(info["path"]),
                is_dir=bool(info.get("is_dir")),
                done_cb=lambda ok, err: self._on_remote_adb_delete_done(ok, err),
            )
            return
        if self.kind == "sftp" and self._sftp_client:
            if self._sftp_ftp_delete_thread and self._sftp_ftp_delete_thread.isRunning():
                dlg.close()
                QMessageBox.information(self, "Delete", "Another remote delete is still running.")
                return
            rpath = _sftp_abs_remote_path(str(info["path"]), self.remote_path)
            self._log(f"Explorer: SFTP delete {rpath}")
            dlg.close()
            pdlg = QProgressDialog("Deleting on server…", None, 0, 0, self)
            pdlg.setCancelButton(None)
            pdlg.setMinimumDuration(0)
            pdlg.setWindowModality(Qt.NonModal)
            pdlg.show()
            self._sftp_ftp_delete_dialog = pdlg
            th = _SftpFtpDeleteThread(kind="sftp", sftp=self._sftp_client, path=rpath)
            th.done.connect(self._on_sftp_ftp_delete_done)
            th.finished.connect(th.deleteLater)
            self._sftp_ftp_delete_thread = th
            th.start()
            return
        if self.kind == "ftp" and self._ftp_client:
            if self._sftp_ftp_delete_thread and self._sftp_ftp_delete_thread.isRunning():
                dlg.close()
                QMessageBox.information(self, "Delete", "Another remote delete is still running.")
                return
            fpath = str(info["path"]).replace("\\", "/")
            self._log(f"Explorer: FTP delete {fpath}")
            dlg.close()
            pdlg = QProgressDialog("Deleting on server…", None, 0, 0, self)
            pdlg.setCancelButton(None)
            pdlg.setMinimumDuration(0)
            pdlg.setWindowModality(Qt.NonModal)
            pdlg.show()
            self._sftp_ftp_delete_dialog = pdlg
            th = _SftpFtpDeleteThread(kind="ftp", ftp=self._ftp_client, path=fpath)
            th.done.connect(self._on_sftp_ftp_delete_done)
            th.finished.connect(th.deleteLater)
            self._sftp_ftp_delete_thread = th
            th.start()
            return

    def _on_remote_adb_delete_done(self, ok: bool, err: str) -> None:
        if ok:
            self._log("Explorer: delete completed.")
            self.refresh_remote()
            return
        self._log(f"Explorer: delete failed: {err or 'unknown'}")
        QMessageBox.warning(self, "Delete", err or "Failed.")

    def _on_sftp_ftp_delete_done(self, ok: bool, err: str) -> None:
        th = self.sender()
        if th is not self._sftp_ftp_delete_thread:
            return
        if self._sftp_ftp_delete_dialog is not None:
            self._sftp_ftp_delete_dialog.close()
            self._sftp_ftp_delete_dialog.deleteLater()
            self._sftp_ftp_delete_dialog = None
        self._sftp_ftp_delete_thread = None
        if not ok:
            self._log(f"Explorer: remote delete failed: {err or 'unknown'}")
            QMessageBox.warning(self, "Delete", err or "Delete failed.")
            return
        self._log("Explorer: remote delete completed.")
        try:
            from qt_thread_updater import call_latest

            call_latest(self.refresh_remote)
        except Exception:
            self.refresh_remote()

    def make_remote_folder(self) -> None:
        name, ok = QInputDialog.getText(self, "New folder", "Folder name:")
        if not ok or not name.strip():
            return
        base = self.remote_path.rstrip("/") or "/"
        joined = posixpath.join(base, name.strip()).replace("\\", "/")

        if self.kind == "adb":
            adb_path = f"{self.remote_path.rstrip('/')}/{name.strip()}".replace("//", "/")
            code, _, stderr = run_adb(self.get_adb_path(), [*self._adb_prefix(), "shell", "mkdir", "-p", adb_path])
            if code == 0:
                self.refresh_remote()
            else:
                QMessageBox.warning(self, "New folder", stderr or "Failed.")
            return
        if self.kind == "sftp" and self._sftp_client:
            try:
                path = _sftp_abs_remote_path(joined, self.remote_path)
                self._sftp_mkdir_p(path)
                self._sftp_client.stat(path)
                self.refresh_remote()
            except Exception as exc:
                QMessageBox.warning(self, "New folder", str(exc))
            return
        if self.kind == "ftp" and self._ftp_client:
            nm = name.strip()
            saved = None
            try:
                saved = self._ftp_client.pwd()
            except Exception:
                pass
            try:
                rp = self.remote_path.rstrip("/") or "/"
                _ftp_safe_cwd(self._ftp_client, rp)
                _ftp_safe_mkd(self._ftp_client, nm)
                self.refresh_remote()
            except Exception as exc:
                QMessageBox.warning(self, "New folder", str(exc))
            finally:
                if saved is not None:
                    try:
                        _ftp_safe_cwd(self._ftp_client, saved)
                    except Exception:
                        pass


class FileExplorerTab(QWidget):
    """WinSCP-style explorer: tabbed sessions — each tab is Local | Remote (ADB or SFTP/FTP after Login)."""

    def __init__(
        self,
        get_adb_path: Callable[[], str],
        log: Optional[Callable[[str], None]] = None,
        config: Optional[AppConfig] = None,
        on_refresh_devices: Optional[Callable[[], None]] = None,
        get_default_ssh_host: Optional[Callable[[], str]] = None,
        on_remote_session_changed: Optional[Callable[[], None]] = None,
    ):
        super().__init__()
        self.get_adb_path = get_adb_path
        self._config = config
        self._log = log or (lambda _m: None)
        self._on_refresh_devices = on_refresh_devices
        self._get_default_ssh_host = get_default_ssh_host or (lambda: "")
        self._on_remote_session_changed = on_remote_session_changed
        self._adb_serial = ""
        self._device_stats_text = ""
        self._build_ui()
        QApplication.instance().installEventFilter(self)
        self._update_status_bar()

    def apply_session_kind(self, _kind: ConnectionKind) -> None:
        pass

    def _current_page(self) -> Optional[ExplorerSessionPage]:
        w = self.session_tabs.currentWidget()
        return w if isinstance(w, ExplorerSessionPage) else None

    def get_sftp_session_profile(self) -> SessionProfile:
        page = self._current_page()
        if page and page.kind == "sftp":
            return page.get_sftp_profile()
        for i in range(self.session_tabs.count()):
            w = self.session_tabs.widget(i)
            if isinstance(w, ExplorerSessionPage) and w.kind == "sftp":
                return w.get_sftp_profile()
        return SessionProfile(ConnectionKind.SSH_SFTP)

    def disconnect_remote_services(self) -> None:
        for i in range(self.session_tabs.count()):
            w = self.session_tabs.widget(i)
            if isinstance(w, ExplorerSessionPage):
                w.disconnect_session()

    def has_active_file_transfer(self) -> bool:
        for i in range(self.session_tabs.count()):
            w = self.session_tabs.widget(i)
            if isinstance(w, ExplorerSessionPage) and w.has_active_file_transfer():
                return True
        return False

    def set_remote_device(self, serial: str) -> None:
        """Main bar device — used to pre-select the device in the Login dialog for new ADB tabs."""
        self._adb_serial = serial if serial and not serial.startswith("No ") else ""
        self._update_status_bar()

    def get_adb_serial(self) -> str:
        return self._adb_serial

    def _tool_btn(self, text: str, icon, slot=None, tip: str = "") -> QToolButton:
        b = QToolButton()
        b.setObjectName("WinScpMainToolBtn")
        b.setIcon(icon)
        b.setText(text)
        b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        b.setAutoRaise(True)
        if tip:
            b.setToolTip(tip)
        if slot:
            b.clicked.connect(slot)
        return b

    def _vsep(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.VLine)
        f.setFrameShadow(QFrame.Sunken)
        f.setObjectName("WinScpVSep")
        return f

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        chrome = QWidget()
        chrome.setObjectName("ExplorerChrome")
        chrome_col = QVBoxLayout(chrome)
        chrome_col.setContentsMargins(2, 2, 2, 0)
        chrome_col.setSpacing(0)

        main_tb = QHBoxLayout()
        main_tb.setContentsMargins(4, 0, 4, 0)
        main_tb.setSpacing(6)
        btn_new = QPushButton("New session…")
        btn_new.setObjectName("SessionStripBtn")
        btn_new.setIcon(self.style().standardIcon(QStyle.SP_FileDialogNewFolder))
        btn_new.setToolTip("Add a session: SFTP, FTP, or Android (ADB)")
        btn_new.clicked.connect(self._open_login_dialog)
        main_tb.addWidget(btn_new)
        main_tb.addStretch(1)
        chrome_col.addLayout(main_tb)

        root.addWidget(chrome)

        self.session_tabs = QTabWidget()
        self.session_tabs.setObjectName("ExplorerSessionTabs")
        self.session_tabs.setTabsClosable(True)
        self.session_tabs.setMovable(True)
        etb = self.session_tabs.tabBar()
        etb.setElideMode(Qt.ElideNone)
        etb.setUsesScrollButtons(True)
        self.session_tabs.currentChanged.connect(lambda _i: self._update_status_bar())
        self.session_tabs.tabCloseRequested.connect(self._on_tab_close_requested)
        self._empty_state = QLabel(
            "No explorer session is open.\n\n"
            "How to start:\n"
            "1) Click New session...\n"
            "2) Select ADB / SFTP / FTP and login\n"
            "3) Local (left) and remote (right) panes will open in the session tab"
        )
        self._empty_state.setAlignment(Qt.AlignCenter)
        self._empty_state.setObjectName("ExplorerSessionHint")
        self._empty_state.setWordWrap(True)
        self._session_stack = QStackedWidget()
        self._session_stack.addWidget(self._empty_state)
        self._session_stack.addWidget(self.session_tabs)
        root.addWidget(self._session_stack, 1)

        self.status_bar = QFrame()
        self.status_bar.setObjectName("WinScpStatusBar")
        sl = QHBoxLayout(self.status_bar)
        sl.setContentsMargins(6, 3, 6, 3)
        self.status_label = QLabel(f"{APP_TITLE} — add a session or pick an open tab.")
        self.status_label.setObjectName("WinScpStatusText")
        sl.addWidget(self.status_label, 1)
        self.status_conn_label = QLabel("")
        self.status_conn_label.setObjectName("WinScpStatusConn")
        sl.addWidget(self.status_conn_label)
        root.addWidget(self.status_bar)
        self._backspace_global_shortcut = QShortcut(QKeySequence(Qt.Key_Backspace), self)
        self._backspace_global_shortcut.setContext(Qt.ApplicationShortcut)
        self._backspace_global_shortcut.activated.connect(self._on_backspace_global)

    def _on_backspace_global(self) -> None:
        page = self._current_page()
        if not page:
            return
        page._handle_backspace_nav()

    @staticmethod
    def _is_descendant_of(widget: Optional[QWidget], parent: Optional[QWidget]) -> bool:
        w = widget
        while w is not None:
            if w is parent:
                return True
            w = w.parentWidget()
        return False

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.KeyPress and ev.key() == Qt.Key_Backspace:
            page = self._current_page()
            if page is None:
                return super().eventFilter(obj, ev)
            fw = QApplication.focusWidget()
            if fw is not None and self._is_descendant_of(fw, page):
                page._handle_backspace_nav()
                ev.accept()
                return True
        return super().eventFilter(obj, ev)

    def _open_login_dialog(self) -> None:
        par = self.window()
        dlg = SessionLoginDialog(
            self.get_adb_path,
            self._get_default_ssh_host(),
            self._adb_serial or "",
            par if par is not None and par.width() >= 80 else None,
            for_terminal=False,
            config=self._config,
            on_bookmarks_changed=None,
        )
        if dlg.exec_() != QDialog.Accepted:
            return
        o = dlg.outcome()
        if o:
            self._append_session_from_outcome(o)

    def _append_session_from_outcome(self, o: SessionLoginOutcome) -> None:
        if o.kind == "adb":
            page = ExplorerSessionPage(
                "adb",
                self.get_adb_path,
                self.get_adb_serial,
                self._log,
                session_adb_serial=o.adb_serial,
                app_config=self._config,
            )
            title = f"ADB {o.adb_serial}"
        elif o.kind == "sftp":
            page = ExplorerSessionPage(
                "sftp",
                self.get_adb_path,
                self.get_adb_serial,
                self._log,
                sftp_transport=o.sftp_transport,
                sftp_client=o.sftp_client,
                sftp_host=o.sftp_host,
                sftp_user=o.sftp_user,
                sftp_port=o.sftp_port,
                sftp_password=o.sftp_password,
                app_config=self._config,
            )
            title = f"SFTP {o.sftp_user + '@' if o.sftp_user else ''}{o.sftp_host}"
            self._log(f"SFTP tab: {title}")
            if self._on_remote_session_changed:
                self._on_remote_session_changed()
        else:
            page = ExplorerSessionPage(
                "ftp",
                self.get_adb_path,
                self.get_adb_serial,
                self._log,
                ftp_client=o.ftp_client,
                ftp_host=o.ftp_host,
                ftp_port=o.ftp_port,
                ftp_user=o.ftp_user,
                ftp_password=o.ftp_password,
                app_config=self._config,
            )
            title = f"FTP {o.ftp_host}"
            self._log(f"FTP tab: {title}")
            if self._on_remote_session_changed:
                self._on_remote_session_changed()
        idx = self.session_tabs.addTab(page, title)
        self.session_tabs.setCurrentIndex(idx)
        self._update_status_bar()

    def _on_tab_close_requested(self, index: int) -> None:
        w = self.session_tabs.widget(index)
        if isinstance(w, ExplorerSessionPage):
            w.disconnect_session()
        self.session_tabs.removeTab(index)
        self._update_status_bar()

    def closeEvent(self, event) -> None:
        try:
            QApplication.instance().removeEventFilter(self)
        except Exception:
            pass
        super().closeEvent(event)

    def _update_status_bar(self) -> None:
        page = self._current_page()
        conn = "Sessions"
        if self._device_stats_text:
            conn = f"{conn} · {self._device_stats_text}"
        self.status_conn_label.setText(conn)
        self._session_stack.setCurrentIndex(1 if self.session_tabs.count() > 0 else 0)
        if page:
            self.status_label.setText(page.status_line())
        elif self.session_tabs.count() == 0:
            self.status_label.setText(
                f'{APP_TITLE} — use "New session…" to connect (SFTP, FTP, or Android).'
            )
        else:
            self.status_label.setText(f"{APP_TITLE} — select a session tab.")

    def set_device_stats_text(self, text: str) -> None:
        self._device_stats_text = (text or "").strip()
        self._update_status_bar()

    def _flash_refresh_banner(self, side: str, ts: str) -> None:
        self.status_label.setStyleSheet("color: #2563eb; font-weight: 700;")
        self.status_label.setText(f"Listing updated · {side} · {ts}")
        page = self._current_page()
        if page:
            self._log(page.status_line())
        else:
            self._log(f"Explorer: {side.lower()} listing updated at {ts}.")
        QTimer.singleShot(850, self._clear_refresh_flash)

    def _show_refreshing_banner(self, side: str) -> None:
        self.status_label.setStyleSheet("color: #38bdf8; font-weight: 700;")
        self.status_label.setText(f"Refreshing {side}…")

    def _clear_refresh_flash(self) -> None:
        self.status_label.setStyleSheet("")
        self._update_status_bar()

    def refresh_local(self) -> None:
        page = self._current_page()
        if page:
            page.refresh_local()
            self._update_status_bar()

    def refresh_remote(self) -> None:
        page = self._current_page()
        if page:
            page.refresh_remote()
            self._update_status_bar()

    def refresh_all_remotes(self) -> None:
        for i in range(self.session_tabs.count()):
            w = self.session_tabs.widget(i)
            if isinstance(w, ExplorerSessionPage):
                w.refresh_remote()
        self._update_status_bar()

    def _need_session(self) -> bool:
        if self._current_page() is not None:
            return True
        QMessageBox.information(
            self,
            APP_TITLE,
            'No file session is open. Click "New session…" above to connect (SFTP, FTP, or Android).',
        )
        return False

    def pull_selected(self) -> None:
        if not self._need_session():
            return
        self._current_page().pull_selected()

    def push_selected(self) -> None:
        if not self._need_session():
            return
        self._current_page().push_selected()

    def delete_selected_remote(self) -> None:
        if not self._need_session():
            return
        self._current_page().delete_selected_remote()

    def make_remote_folder(self) -> None:
        if not self._need_session():
            return
        self._current_page().make_remote_folder()

    def run_adb_global(self, args: List[str], timeout: int = 60) -> Tuple[int, str, str]:
        return run_adb(self.get_adb_path(), args, timeout=timeout)

    def run_adb_device(self, args: List[str], timeout: int = 120) -> Tuple[int, str, str]:
        serial = self._adb_serial.split(" ")[0] if self._adb_serial else ""
        prefix = ["-s", serial] if serial else []
        return run_adb(self.get_adb_path(), [*prefix, *args], timeout=timeout)

    def action_adb_reconnect(self) -> None:
        code, out, err = self.run_adb_global(["reconnect"], timeout=30)
        msg = (out or err or "").strip() or ("OK" if code == 0 else f"exit {code}")
        self._log(f"ADB reconnect: {msg}")
        if code != 0:
            QMessageBox.warning(self, "ADB reconnect", err or "Command failed.")
        if self._on_refresh_devices:
            self._on_refresh_devices()

    def action_restart_adb_server(self) -> None:
        c1, _, e1 = self.run_adb_global(["kill-server"], timeout=15)
        self._log(f"ADB kill-server: exit {c1}" + (f" — {e1.strip()}" if e1 and e1.strip() else ""))
        c2, out, e2 = self.run_adb_global(["start-server"], timeout=30)
        msg = (out or e2 or "").strip() or f"exit {c2}"
        self._log(f"ADB start-server: {msg}")
        if self._on_refresh_devices:
            self._on_refresh_devices()
        if c2 != 0:
            QMessageBox.warning(self, "ADB server", e2 or "start-server failed.")

    def _ensure_device_for_adb_device_commands(self) -> bool:
        if not self._adb_serial:
            QMessageBox.information(self, "ADB", "Select a device in the bar at the top of the window first.")
            return False
        return True

    def action_adb_root(self) -> None:
        if not self._ensure_device_for_adb_device_commands():
            return
        code, out, err = self.run_adb_device(["root"], timeout=90)
        text = (out or err or "").strip() or f"exit {code}"
        self._log(f"ADB root: {text}")
        QMessageBox.information(self, "ADB root", text)
        if self._on_refresh_devices:
            self._on_refresh_devices()

    def action_adb_unroot(self) -> None:
        if not self._ensure_device_for_adb_device_commands():
            return
        code, out, err = self.run_adb_device(["unroot"], timeout=90)
        text = (out or err or "").strip() or f"exit {code}"
        self._log(f"ADB unroot: {text}")
        QMessageBox.information(self, "ADB unroot", text)
        if self._on_refresh_devices:
            self._on_refresh_devices()

    def action_adb_remount(self) -> None:
        if not self._ensure_device_for_adb_device_commands():
            return
        code, out, err = self.run_adb_device(["remount"], timeout=120)
        text = (out or err or "").strip() or f"exit {code}"
        self._log(f"ADB remount: {text}")
        if code != 0:
            QMessageBox.warning(self, "ADB remount", text or err or "Failed (often needs adb root first).")
        else:
            QMessageBox.information(self, "ADB remount", text or "OK.")

    def action_adb_reboot(self) -> None:
        if not self._ensure_device_for_adb_device_commands():
            return
        if (
            QMessageBox.question(
                self,
                "ADB reboot",
                "Send adb reboot to the selected device?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            != QMessageBox.Yes
        ):
            return
        code, out, err = self.run_adb_device(["reboot"], timeout=30)
        msg = (out or err or "").strip() or f"exit {code}"
        self._log(f"ADB reboot: {msg}")
        QMessageBox.information(self, "ADB reboot", msg if code == 0 else (err or msg or "Failed."))
