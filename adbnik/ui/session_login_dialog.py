"""WinSCP-style Login: form + saved sessions list (bookmarks). Terminal and Explorer share the same storage."""

from dataclasses import dataclass

from .. import APP_TITLE
from typing import Any, Callable, Dict, List, Optional

from PyQt5.QtCore import QEventLoop, QTimer, QSize, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QShowEvent
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProxyStyle,
    QPushButton,
    QProgressDialog,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QStyle,
    QFrame,
)


class _BookmarkListNoSingleActivateStyle(QProxyStyle):
    """Windows/macOS may treat one click as item activation; we only connect double-click to connect."""

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.SH_ItemView_ActivateItemOnSingleClick:
            return 0
        return super().styleHint(hint, option, widget, returnData)


# Self-contained so the Login window stays readable regardless of the main window theme.
_LOGIN_DIALOG_STYLESHEET = """
QDialog#SessionLoginDialog {
    background-color: #ffffff;
}
QDialog#SessionLoginDialog QLabel {
    color: #0f172a;
    background-color: transparent;
}
QDialog#SessionLoginDialog QLabel#LoginDialogIntro {
    color: #1e293b;
    font-size: 13px;
}
QDialog#SessionLoginDialog QGroupBox {
    color: #0f172a;
    font-weight: 600;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 12px;
    background-color: #f8fafc;
}
QDialog#SessionLoginDialog QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}
QDialog#SessionLoginDialog QLineEdit, QDialog#SessionLoginDialog QComboBox {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #94a3b8;
    border-radius: 4px;
    padding: 6px 8px;
    min-height: 20px;
}
QDialog#SessionLoginDialog QComboBox QAbstractItemView {
    margin: 0px;
    padding: 0px;
}
QDialog#SessionLoginDialog QComboBox QAbstractItemView::viewport {
    background-color: #ffffff;
    margin: 0px;
    padding: 0px;
}
QDialog#SessionLoginDialog QComboBox QAbstractItemView::item {
    min-height: 22px;
    padding: 2px 6px;
}
QDialog#SessionLoginDialog QListWidget#SessionBookmarkList {
    background-color: #f8fafc;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 4px;
    font-size: 13px;
}
QDialog#SessionLoginDialog QListWidget#SessionBookmarkList::item {
    padding: 6px;
    color: #0f172a;
}
QDialog#SessionLoginDialog QListWidget#SessionBookmarkList::item:selected {
    background-color: #dbeafe;
    color: #0f172a;
}
QDialog#SessionLoginDialog QPushButton {
    background-color: #f1f5f9;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 6px 12px;
}
QDialog#SessionLoginDialog QPushButton:hover {
    background-color: #e2e8f0;
}
QDialog#SessionLoginDialog QDialogButtonBox QPushButton {
    min-width: 72px;
}
QToolButton#SessionProtocolBtn {
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 8px 10px;
    background-color: #f8fafc;
    min-width: 76px;
    font-size: 11px;
}
QToolButton#SessionProtocolBtn:checked {
    border: 2px solid #f59e0b;
    background-color: #eff6ff;
}
"""

_LOGIN_DIALOG_DARK_STYLESHEET = """
QDialog#SessionLoginDialog {
    background-color: #0f172a;
    color: #f8fafc;
}
QDialog#SessionLoginDialog QLabel {
    color: #e2e8f0;
    background-color: transparent;
}
QDialog#SessionLoginDialog QLabel#LoginDialogIntro {
    color: #cbd5e1;
}
QDialog#SessionLoginDialog QGroupBox {
    color: #f8fafc;
    font-weight: 600;
    border: 1px solid #334155;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 12px;
    background-color: #111827;
}
QDialog#SessionLoginDialog QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: #cbd5e1;
}
QDialog#SessionLoginDialog QLineEdit, QDialog#SessionLoginDialog QComboBox {
    background-color: #0b1220;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 4px;
    padding: 6px 8px;
    min-height: 20px;
}
QDialog#SessionLoginDialog QComboBox QAbstractItemView {
    background-color: #0b1220;
    color: #f8fafc;
    border: 1px solid #334155;
    selection-background-color: #1d4ed8;
    selection-color: #ffffff;
    margin: 0px;
    padding: 0px;
}
QDialog#SessionLoginDialog QComboBox QAbstractItemView::viewport {
    background-color: #0b1220;
    margin: 0px;
    padding: 0px;
}
QDialog#SessionLoginDialog QComboBox QAbstractItemView::item {
    min-height: 22px;
    padding: 2px 6px;
}
QDialog#SessionLoginDialog QListWidget#SessionBookmarkList {
    background-color: #0b1220;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 4px;
    padding: 4px;
    font-size: 13px;
}
QDialog#SessionLoginDialog QListWidget#SessionBookmarkList::item {
    padding: 6px;
    color: #f8fafc;
}
QDialog#SessionLoginDialog QListWidget#SessionBookmarkList::item:selected {
    background-color: #1d4ed8;
    color: #ffffff;
}
QDialog#SessionLoginDialog QPushButton {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 4px;
    padding: 6px 12px;
}
QDialog#SessionLoginDialog QPushButton:hover {
    background-color: #334155;
}
QDialog#SessionLoginDialog QDialogButtonBox QPushButton {
    min-width: 72px;
}
QToolButton#SessionProtocolBtn {
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 10px;
    background-color: #111827;
    min-width: 76px;
    font-size: 11px;
    color: #e2e8f0;
}
QToolButton#SessionProtocolBtn:checked {
    border: 2px solid #fbbf24;
    background-color: #1e293b;
}
"""

from ..config import AppConfig
from .icon_utils import (
    bookmark_icon_from_entry,
    icon_adb_android,
    icon_ftp_session,
    icon_serial_port,
    icon_sftp_session,
    icon_ssh_session,
)
from ..session import normalize_tcp_port, parse_user_at_host
from ..services.adb_devices import list_adb_devices
from ..services.commands import run_adb
from ..services.remote_clients import connect_ftp, connect_sftp
from .combo_utils import ExpandAllComboBox

try:
    from serial.tools import list_ports
except Exception:
    list_ports = None


@dataclass
class SessionLoginOutcome:
    kind: str = ""  # adb | ssh | sftp | ftp | serial | local_cmd | local_pwsh
    adb_serial: str = ""
    adb_display_label: str = ""
    sftp_transport: Any = None
    sftp_client: Any = None
    sftp_host: str = ""
    sftp_user: str = ""
    sftp_port: int = 22
    sftp_password: str = ""
    ftp_client: Any = None
    ftp_host: str = ""
    ftp_port: int = 21
    ftp_user: str = ""
    ftp_password: str = ""
    serial_port: str = ""
    serial_baud: str = "115200"


def _bookmark_allowed_for_dialog(for_terminal: bool, kind: str) -> bool:
    if for_terminal:
        return kind in ("ssh", "adb", "serial", "local_cmd", "local_pwsh")
    return kind in ("sftp", "ftp", "adb")


class _SftpConnectThread(QThread):
    """Run paramiko SFTP connect off the UI thread so login stays responsive (timeouts, slow hosts)."""

    finished_sig = pyqtSignal(object, object, str)

    def __init__(self, host: str, port: int, user: str, password: str):
        super().__init__(None)
        self._host = host
        self._port = port
        self._user = user
        self._password = password

    def run(self) -> None:
        t, sftp, err = connect_sftp(self._host, self._port, self._user, self._password, timeout=45)
        self.finished_sig.emit(t, sftp, err or "")


class _FtpConnectThread(QThread):
    finished_sig = pyqtSignal(object, str)

    def __init__(self, host: str, port: int, user: str, password: str):
        super().__init__(None)
        self._host = host
        self._port = port
        self._user = user
        self._password = password

    def run(self) -> None:
        ftp, err = connect_ftp(self._host, self._port, self._user, self._password, timeout=45)
        self.finished_sig.emit(ftp, err or "")


class SessionLoginDialog(QDialog):
    def __init__(
        self,
        get_adb_path: Callable[[], str],
        default_ssh_host: str,
        preferred_adb_serial: str,
        parent: Optional[QWidget] = None,
        *,
        for_terminal: bool = False,
        initial_protocol: Optional[str] = None,
        config: Optional[AppConfig] = None,
        on_bookmarks_changed: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent)
        self._get_adb_path = get_adb_path
        self._for_terminal = for_terminal
        self._initial_protocol = initial_protocol
        self._config = config
        self._on_bookmarks_changed = on_bookmarks_changed
        self._outcome: Optional[SessionLoginOutcome] = None
        self._preferred_adb_serial = (preferred_adb_serial or "").strip()
        self.setObjectName("SessionLoginDialog")
        self.setWindowTitle(f"Session settings — {APP_TITLE}")
        self.setModal(True)
        self.setMinimumSize(720 if not for_terminal else 520, 520 if not for_terminal else 400)
        self.resize(940 if not for_terminal else 780, 640 if not for_terminal else 480)
        self._build_ui(default_ssh_host, preferred_adb_serial)
        dark = bool(getattr(self._config, "dark_theme", False))
        self.setStyleSheet(_LOGIN_DIALOG_DARK_STYLESHEET if dark else _LOGIN_DIALOG_STYLESHEET)

    def outcome(self) -> Optional[SessionLoginOutcome]:
        return self._outcome

    def _connect_sftp_blocking(self, host: str, port: int, user: str, password: str):
        # Parent=None avoids QWidgetWindow geometry errors when the caller widget has no valid size yet.
        dlg = QProgressDialog("Connecting via SFTP…", None, 0, 0, None)
        dlg.setWindowTitle(APP_TITLE)
        dlg.setWindowModality(Qt.ApplicationModal)
        dlg.setMinimumDuration(0)
        dlg.setCancelButton(None)
        dlg.show()
        QApplication.processEvents()
        th = _SftpConnectThread(host, port, user, password)
        loop = QEventLoop()
        box = [None, None, ""]

        def _done_sftp(t, sftp, err):
            box[0], box[1], box[2] = t, sftp, err
            loop.quit()

        th.finished_sig.connect(_done_sftp)
        th.start()
        loop.exec_()
        dlg.close()
        dlg.deleteLater()
        th.wait(60000)
        th.deleteLater()
        QApplication.processEvents()
        return box[0], box[1], box[2]

    def _connect_ftp_blocking(self, host: str, port: int, user: str, password: str):
        dlg = QProgressDialog("Connecting via FTP…", None, 0, 0, None)
        dlg.setWindowTitle(APP_TITLE)
        dlg.setWindowModality(Qt.ApplicationModal)
        dlg.setMinimumDuration(0)
        dlg.setCancelButton(None)
        dlg.show()
        QApplication.processEvents()
        th = _FtpConnectThread(host, port, user, password)
        loop = QEventLoop()
        box = [None, ""]

        def _done_ftp(ftp, err):
            box[0], box[1] = ftp, err
            loop.quit()

        th.finished_sig.connect(_done_ftp)
        th.start()
        loop.exec_()
        dlg.close()
        dlg.deleteLater()
        th.wait(60000)
        th.deleteLater()
        QApplication.processEvents()
        return box[0], box[1]

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._ensure_safe_geometry)
        if hasattr(self, "device_combo") and getattr(self, "adb_box", None) and self.adb_box.isVisible():
            cur_data = self.device_combo.currentData()
            pref = str(cur_data).strip() if cur_data is not None else ""
            self._fill_device_combo(pref or self._preferred_adb_serial)

    def _ensure_safe_geometry(self) -> None:
        """Keep the dialog on-screen without shrinking inner fields (avoids truncated controls)."""
        try:
            if not self.isVisible():
                return
            scr = QApplication.primaryScreen()
            if scr is None:
                return
            g = scr.availableGeometry()
            fg = self.frameGeometry()
            if fg.right() > g.right() or fg.bottom() > g.bottom() or fg.left() < g.left() or fg.top() < g.top():
                fg.moveCenter(g.center())
                self.move(fg.topLeft())
        except Exception:
            pass

    def _refresh_devices_clicked(self) -> None:
        cur_data = self.device_combo.currentData()
        pref = str(cur_data).strip() if cur_data is not None else ""
        self._fill_device_combo(pref or self._preferred_adb_serial)

    def _fill_device_combo(self, preferred_serial: str) -> None:
        self.device_combo.clear()
        pairs = list_adb_devices(self._get_adb_path())
        if pairs:
            for serial, display in pairs:
                self.device_combo.addItem(display, serial)
                if preferred_serial and serial == preferred_serial:
                    self.device_combo.setCurrentIndex(self.device_combo.count() - 1)
        else:
            code, _, _ = run_adb(self._get_adb_path(), ["devices"])
            if code != 0:
                self.device_combo.addItem("ADB not found — check Preferences")
            else:
                self.device_combo.addItem("No device — connect USB / enable ADB")

    def _bookmark_list_data(self) -> List[Dict[str, Any]]:
        if not self._config:
            return []
        return [
            bm
            for bm in self._config.session_bookmarks
            if isinstance(bm, dict) and _bookmark_allowed_for_dialog(self._for_terminal, bm.get("kind", ""))
        ]

    def _refresh_bookmark_list(self) -> None:
        if not hasattr(self, "_bookmark_list"):
            return
        self._bookmark_list.clear()
        for bm in self._bookmark_list_data():
            it = QListWidgetItem(bm.get("name") or "Untitled")
            it.setIcon(bookmark_icon_from_entry(bm, self))
            it.setData(Qt.UserRole, bm)
            self._bookmark_list.addItem(it)
        self._bookmark_list.clearSelection()

    def _load_bookmark_into_form(self, _item: Optional[QListWidgetItem] = None) -> None:
        """Apply the selected bookmark to the form (does not connect)."""
        it = self._bookmark_list.currentItem()
        if not it:
            QMessageBox.information(self, "Bookmarks", "Select a saved session in the list first.")
            return
        bm = it.data(Qt.UserRole)
        if not isinstance(bm, dict):
            return
        self._apply_bookmark_to_fields(bm)

    def _on_bookmark_double_clicked(self, item: QListWidgetItem) -> None:
        bm = item.data(Qt.UserRole)
        if not isinstance(bm, dict):
            return
        self._bookmark_list.setCurrentItem(item)
        self._connect_from_bookmark(bm)

    def _connect_from_bookmark(self, bm: Dict[str, Any]) -> None:
        """Double-click: connect immediately using bookmark data (same as Login, without re-saving bookmark)."""
        if self._for_terminal:
            k = bm.get("kind")
            if k == "local_cmd":
                self._outcome = SessionLoginOutcome(kind="local_cmd")
                self.accept()
                return
            if k == "local_pwsh":
                self._outcome = SessionLoginOutcome(kind="local_pwsh")
                self.accept()
                return
        self._apply_bookmark_to_fields(bm)
        k = bm.get("kind")
        if not self._for_terminal:
            if k in ("sftp", "ftp") and not self.password_edit.text().strip():
                pwd, ok = QInputDialog.getText(
                    self,
                    "Password",
                    "Password for this connection (not stored in saved bookmarks):",
                    QLineEdit.Password,
                )
                if not ok:
                    return
                self.password_edit.setText(pwd)
        elif self._for_terminal and k in ("ssh", "sftp") and not self.password_edit.text().strip():
            pwd, ok = QInputDialog.getText(
                self,
                "Password",
                "Password for SSH (not stored in saved bookmarks):",
                QLineEdit.Password,
            )
            if not ok:
                return
            self.password_edit.setText(pwd)
        self._try_login(skip_bookmark_save=True)

    def _apply_bookmark_to_fields(self, bm: Dict[str, Any]) -> None:
        k = bm.get("kind")
        if k == "adb":
            self._set_protocol_key("adb")
            serial = (bm.get("adb_serial") or "").strip()
            for i in range(self.device_combo.count()):
                if self.device_combo.itemData(i) == serial:
                    self.device_combo.setCurrentIndex(i)
                    break
            else:
                if serial:
                    self.device_combo.insertItem(0, bm.get("adb_label") or serial, serial)
                    self.device_combo.setCurrentIndex(0)
        elif k == "ssh" and self._for_terminal:
            self._set_protocol_key("ssh")
            self.host_edit.setText(bm.get("ssh_host", ""))
            try:
                p = int(bm.get("ssh_port") or 22)
            except (TypeError, ValueError):
                p = 22
            self.port_edit.setText(str(p))
            self.user_edit.setText(bm.get("ssh_user", ""))
            self.password_edit.clear()
        elif k == "sftp" and self._for_terminal:
            # Legacy bookmarks created when terminal SSH was labeled SFTP
            self._set_protocol_key("ssh")
            self.host_edit.setText(bm.get("ssh_host", bm.get("sftp_host", "")))
            try:
                p = int(bm.get("ssh_port", bm.get("sftp_port")) or 22)
            except (TypeError, ValueError):
                p = 22
            self.port_edit.setText(str(p))
            self.user_edit.setText(bm.get("ssh_user", bm.get("sftp_user", "")))
            self.password_edit.clear()
        elif k == "sftp" and not self._for_terminal:
            self._set_protocol_key("sftp")
            self.host_edit.setText(bm.get("sftp_host", bm.get("ssh_host", "")))
            try:
                p = int(bm.get("sftp_port", bm.get("ssh_port")) or 22)
            except (TypeError, ValueError):
                p = 22
            self.port_edit.setText(str(p))
            self.user_edit.setText(bm.get("sftp_user", bm.get("ssh_user", "")))
            self.password_edit.clear()
        elif k == "ftp" and not self._for_terminal:
            self._set_protocol_key("ftp")
            self.host_edit.setText(bm.get("ftp_host", ""))
            try:
                p = int(bm.get("ftp_port") or 21)
            except (TypeError, ValueError):
                p = 21
            self.port_edit.setText(str(p))
            self.user_edit.setText(bm.get("ftp_user", ""))
            self.password_edit.clear()
        elif k == "serial" and self._for_terminal:
            self._set_protocol_key("serial")
            serial_port = (bm.get("serial_port") or "").strip() or "COM3"
            idx = self.serial_port_combo.findText(serial_port)
            if idx < 0:
                self.serial_port_combo.addItem(serial_port)
                idx = self.serial_port_combo.findText(serial_port)
            if idx >= 0:
                self.serial_port_combo.setCurrentIndex(idx)
            baud = (bm.get("serial_baud") or "").strip() or "115200"
            idxb = self.serial_baud_combo.findText(baud)
            if idxb >= 0:
                self.serial_baud_combo.setCurrentIndex(idxb)

    def _remove_selected_bookmark(self) -> None:
        if not self._config:
            return
        selected = [it for it in self._bookmark_list.selectedItems() if isinstance(it.data(Qt.UserRole), dict)]
        if not selected:
            return
        names = {str(it.data(Qt.UserRole).get("name", "")).strip() for it in selected}
        names.discard("")
        if not names:
            return
        self._config.session_bookmarks = [
            x
            for x in self._config.session_bookmarks
            if not (isinstance(x, dict) and str(x.get("name", "")).strip() in names)
        ]
        self._config.save()
        self._refresh_bookmark_list()
        if self._on_bookmarks_changed:
            self._on_bookmarks_changed()

    def _upsert_bookmark(self, bm: Dict[str, Any]) -> None:
        if not self._config:
            return
        name = (bm.get("name") or "").strip()
        if not name:
            return
        lst = self._config.session_bookmarks
        replaced = False
        for i, x in enumerate(lst):
            if isinstance(x, dict) and x.get("name") == name:
                lst[i] = bm
                replaced = True
                break
        if not replaced:
            lst.append(bm)
        self._config.save()
        self._refresh_bookmark_list()
        if self._on_bookmarks_changed:
            self._on_bookmarks_changed()

    def _maybe_save_bookmark(
        self,
        kind: str,
        payload: Dict[str, Any],
    ) -> None:
        if not self._config:
            return
        if not getattr(self, "save_bookmark_cb", None) or not self.save_bookmark_cb.isChecked():
            return
        name = self.bookmark_name_edit.text().strip()
        if not name and kind == "adb":
            serial = str(payload.get("adb_serial") or "").strip()
            if serial:
                name = f"ADB {serial}"
        if not name:
            return
        bm: Dict[str, Any] = {"name": name, "kind": kind}
        bm.update(payload)
        icon_key = self.bookmark_icon_combo.currentData()
        if icon_key:
            bm["icon"] = str(icon_key)
        else:
            bm.pop("icon", None)
        self._upsert_bookmark(bm)

    def _set_protocol_key(self, key: str) -> None:
        self._protocol_key = key
        if hasattr(self, "_protocol_buttons"):
            for k, btn in self._protocol_buttons.items():
                btn.setChecked(k == key)
        self._apply_protocol_visibility()

    def _apply_protocol_visibility(self) -> None:
        key = getattr(self, "_protocol_key", "adb")
        is_adb = key == "adb"
        is_serial = key == "serial"
        is_ftp = key == "ftp"
        is_net = key in ("ssh", "sftp", "ftp")
        self.network_box.setVisible(is_net)
        self.adb_box.setVisible(is_adb)
        self.serial_box.setVisible(is_serial)
        if is_net:
            self.port_edit.setText("21" if is_ftp else "22")
        if key == "ssh":
            self.network_box.setTitle("SSH session")
        elif key == "sftp":
            self.network_box.setTitle("SFTP session")
        elif key == "ftp":
            self.network_box.setTitle("FTP session")
        else:
            self.network_box.setTitle("Session")

    def _build_protocol_bar(self, form_host: QVBoxLayout) -> None:
        self._protocol_buttons = {}
        self._protocol_key = "adb"
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 4, 0, 10)
        row.setSpacing(10)
        if self._for_terminal:
            defs = [
                ("adb", "Android", icon_adb_android()),
                ("ssh", "SSH", icon_ssh_session()),
                ("serial", "Serial", icon_serial_port()),
            ]
        else:
            defs = [
                ("adb", "Android", icon_adb_android()),
                ("sftp", "SFTP", icon_sftp_session()),
                ("ftp", "FTP", icon_ftp_session()),
            ]
        for key, label, icon in defs:
            btn = QToolButton()
            btn.setObjectName("SessionProtocolBtn")
            btn.setCheckable(True)
            btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            btn.setIconSize(QSize(44, 44))
            if icon is not None and not icon.isNull():
                btn.setIcon(icon)
            btn.setText(label)
            btn.setToolTip(label)
            btn.clicked.connect(lambda _checked=False, k=key: self._set_protocol_key(k))
            self._protocol_buttons[key] = btn
            row.addWidget(btn)
        row.addStretch(1)
        form_host.addWidget(bar)

    def _build_ui(self, default_ssh_host: str, preferred_adb_serial: str) -> None:
        root = QVBoxLayout(self)

        outer = QHBoxLayout()
        if self._config is not None:
            left = QVBoxLayout()
            lbl = QLabel("Saved sessions")
            lbl.setObjectName("MobaSidebarHeading")
            left.addWidget(lbl)
            self._bookmark_list = QListWidget()
            self._bookmark_list.setObjectName("SessionBookmarkList")
            self._bookmark_list.setIconSize(QSize(20, 20))
            self._bookmark_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
            _bs = self._bookmark_list.style() or QApplication.instance().style()
            _bm_style = _BookmarkListNoSingleActivateStyle(_bs)
            self._bookmark_list.setStyle(_bm_style)
            self._bookmark_list.viewport().setStyle(_bm_style)
            self._refresh_bookmark_list()
            self._bookmark_list.clearSelection()
            self._bookmark_list.itemDoubleClicked.connect(self._on_bookmark_double_clicked)
            left.addWidget(self._bookmark_list, 1)
            load_btn = QPushButton("Load into form")
            load_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
            load_btn.setToolTip(
                "Copy the selected bookmark into the fields on the right. Double-click a bookmark to connect immediately."
            )
            load_btn.clicked.connect(self._load_bookmark_into_form)
            left.addWidget(load_btn)
            rm = QPushButton("Remove selected")
            rm.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
            rm.clicked.connect(self._remove_selected_bookmark)
            left.addWidget(rm)
            outer.addLayout(left)

        form_inner = QWidget()
        form_host = QVBoxLayout(form_inner)
        form_host.setContentsMargins(4, 4, 8, 8)
        form_host.setSpacing(10)
        intro = QLabel(
            "Choose a session type below, then enter details. Saved sessions are on the left."
            if self._for_terminal
            else "Choose Android, SFTP, or FTP, then enter host and credentials. Saved sessions are on the left."
        )
        intro.setObjectName("LoginDialogIntro")
        intro.setWordWrap(True)
        form_host.addWidget(intro)
        self._build_protocol_bar(form_host)

        self.network_box = QGroupBox("Session")
        net_form = QFormLayout(self.network_box)
        du, dh = parse_user_at_host(default_ssh_host)
        self.host_edit = QLineEdit(dh)
        self.host_edit.setPlaceholderText("Host name")
        self.host_edit.setMinimumWidth(360)
        self.host_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.port_edit = QLineEdit("22")
        self.port_edit.setFixedWidth(88)
        self.user_edit = QLineEdit(du)
        self.user_edit.setPlaceholderText("User name")
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("Password (optional)")
        net_form.addRow("Host name:", self.host_edit)
        net_form.addRow("Port number:", self.port_edit)
        net_form.addRow("User name:", self.user_edit)
        net_form.addRow("Password:", self.password_edit)
        form_host.addWidget(self.network_box)

        self.adb_box = QGroupBox("Android device")
        adb_l = QVBoxLayout(self.adb_box)
        self.device_combo = ExpandAllComboBox()
        self.device_combo.setMaxVisibleItems(20)
        self.device_combo.setMinimumWidth(320)
        self._fill_device_combo(preferred_adb_serial)
        adb_row = QHBoxLayout()
        adb_row.addWidget(self.device_combo, 1)
        ref_dev = QPushButton("Refresh devices")
        ref_dev.setToolTip("Run adb again (use after plugging in USB or authorizing debugging).")
        ref_dev.clicked.connect(self._refresh_devices_clicked)
        adb_row.addWidget(ref_dev)
        adb_l.addLayout(adb_row)
        adb_hint = QLabel(
            "Device name comes from adb (model). Each tab can use a different device."
            if not self._for_terminal
            else "Device list shows name · serial. Login starts adb shell only."
        )
        adb_hint.setWordWrap(True)
        adb_l.addWidget(adb_hint)
        form_host.addWidget(self.adb_box)

        self.serial_box = QGroupBox("Serial terminal")
        serial_form = QFormLayout(self.serial_box)
        self.serial_port_combo = ExpandAllComboBox()
        self.serial_port_combo.setEditable(True)
        ports = []
        if list_ports is not None:
            try:
                ports = sorted([p.device for p in list_ports.comports()])
            except Exception:
                ports = []
        if ports:
            self.serial_port_combo.addItems(ports)
        else:
            self.serial_port_combo.addItem("COM3")
        default_port = (self._config.default_serial_port if self._config else "") or "COM3"
        idxp = self.serial_port_combo.findText(default_port)
        if idxp < 0:
            self.serial_port_combo.addItem(default_port)
            idxp = self.serial_port_combo.findText(default_port)
        self.serial_port_combo.setCurrentIndex(max(0, idxp))

        self.serial_baud_combo = ExpandAllComboBox()
        self.serial_baud_combo.setEditable(True)
        self.serial_baud_combo.addItems(["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"])
        default_baud = (self._config.default_serial_baud if self._config else "") or "115200"
        idxb = self.serial_baud_combo.findText(default_baud)
        if idxb < 0:
            self.serial_baud_combo.addItem(default_baud)
            idxb = self.serial_baud_combo.findText(default_baud)
        self.serial_baud_combo.setCurrentIndex(max(0, idxb))

        serial_form.addRow("COM port:", self.serial_port_combo)
        serial_form.addRow("Baud rate:", self.serial_baud_combo)
        form_host.addWidget(self.serial_box)

        self.save_bookmark_cb = QCheckBox("Save this connection as bookmark")
        self.save_bookmark_cb.setChecked(False)
        form_host.addWidget(self.save_bookmark_cb)
        self.bookmark_name_edit = QLineEdit()
        self.bookmark_name_edit.setPlaceholderText("Bookmark name")
        form_host.addWidget(self.bookmark_name_edit)
        self._bookmark_icon_lbl = QLabel("Bookmark icon:")
        form_host.addWidget(self._bookmark_icon_lbl)
        self.bookmark_icon_combo = ExpandAllComboBox()
        self.bookmark_icon_combo.setMaxVisibleItems(12)
        self.bookmark_icon_combo.addItem("Auto (from session type)", "")
        self.bookmark_icon_combo.addItem("SSH / network", "ssh")
        self.bookmark_icon_combo.addItem("ADB / device", "adb")
        self.bookmark_icon_combo.addItem("Command Prompt", "local_cmd")
        self.bookmark_icon_combo.addItem("PowerShell", "local_pwsh")
        self.bookmark_icon_combo.addItem("Serial", "serial")
        self.bookmark_icon_combo.addItem("SFTP / files", "sftp")
        self.bookmark_icon_combo.addItem("FTP", "ftp")
        form_host.addWidget(self.bookmark_icon_combo)
        self.save_bookmark_cb.toggled.connect(self.bookmark_name_edit.setEnabled)
        self.save_bookmark_cb.toggled.connect(self.bookmark_icon_combo.setEnabled)
        self.save_bookmark_cb.toggled.connect(self._bookmark_icon_lbl.setEnabled)
        self.bookmark_name_edit.setEnabled(False)
        self.bookmark_icon_combo.setEnabled(False)
        self._bookmark_icon_lbl.setEnabled(False)

        scroll_form = QScrollArea()
        scroll_form.setWidgetResizable(True)
        scroll_form.setFrameShape(QFrame.NoFrame)
        scroll_form.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_form.setWidget(form_inner)
        outer.addWidget(scroll_form, 1)
        root.addLayout(outer)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._try_login)
        buttons.rejected.connect(self.reject)
        self._login_btn = buttons.button(QDialogButtonBox.Ok)
        self._login_btn.setText("Login")
        self._login_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
        cancel_btn = buttons.button(QDialogButtonBox.Cancel)
        if cancel_btn is not None:
            cancel_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogCancelButton))
        root.addWidget(buttons)

        self._set_protocol_key("adb")
        if self._initial_protocol:
            m = {
                "Android (ADB)": "adb",
                "SSH": "ssh",
                "SFTP": "ssh" if self._for_terminal else "sftp",
                "FTP": "ftp",
                "Serial": "serial",
            }
            k = m.get(self._initial_protocol)
            if k and k in getattr(self, "_protocol_buttons", {}):
                self._set_protocol_key(k)

    def _serial_from_device_selection(self) -> str:
        data = self.device_combo.currentData()
        if data is not None:
            return str(data).strip()
        t = self.device_combo.currentText().strip()
        return t.split()[0] if t else ""

    def _try_login(self, skip_bookmark_save: bool = False) -> None:
        key = getattr(self, "_protocol_key", "adb")
        if key == "adb":
            text = self.device_combo.currentText().strip()
            if not text or "No device" in text or "not found" in text.lower() or "ADB not found" in text:
                QMessageBox.warning(self, "Login", "Select a device, or fix ADB (USB / Preferences).")
                return
            serial = self._serial_from_device_selection()
            if not serial:
                QMessageBox.warning(self, "Login", "Could not read device serial.")
                return
            self._outcome = SessionLoginOutcome(
                kind="adb",
                adb_serial=serial,
                adb_display_label=text,
            )
            if not skip_bookmark_save:
                self._maybe_save_bookmark(
                    "adb",
                    {"adb_serial": serial, "adb_label": text},
                )
            self.accept()
            return

        if key == "serial":
            port = (self.serial_port_combo.currentText() or "").strip() or "COM3"
            baud = (self.serial_baud_combo.currentText() or "").strip() or "115200"
            self._outcome = SessionLoginOutcome(
                kind="serial",
                serial_port=port,
                serial_baud=baud,
            )
            if not skip_bookmark_save:
                self._maybe_save_bookmark(
                    "serial",
                    {"serial_port": port, "serial_baud": baud},
                )
            self.accept()
            return

        host = self.host_edit.text().strip()
        if not host:
            QMessageBox.warning(self, "Login", "Enter host name.")
            return
        try:
            port = int(self.port_edit.text().strip() or ("21" if key == "ftp" else "22"))
        except ValueError:
            port = 21 if key == "ftp" else 22
        port = normalize_tcp_port(port, 21 if key == "ftp" else 22)
        user = self.user_edit.text().strip()
        password = self.password_edit.text()

        if key == "ssh" and self._for_terminal:
            self._outcome = SessionLoginOutcome(
                kind="ssh",
                sftp_transport=None,
                sftp_client=None,
                sftp_host=host,
                sftp_user=user,
                sftp_port=port,
                sftp_password=password,
            )
            if not skip_bookmark_save:
                self._maybe_save_bookmark(
                    "ssh",
                    {
                        "ssh_host": host,
                        "ssh_user": user,
                        "ssh_port": port,
                    },
                )
            self.accept()
            return

        if key == "sftp" and not self._for_terminal:
            t, sftp, err = self._connect_sftp_blocking(host, port, user, password)
            if err or sftp is None:
                QMessageBox.warning(self, "SFTP", err or "Connection failed.")
                return
            self._outcome = SessionLoginOutcome(
                kind="sftp",
                sftp_transport=t,
                sftp_client=sftp,
                sftp_host=host,
                sftp_user=user,
                sftp_port=port,
                sftp_password=password,
            )
            if not skip_bookmark_save:
                self._maybe_save_bookmark(
                    "sftp",
                    {
                        "sftp_host": host,
                        "sftp_user": user,
                        "sftp_port": port,
                    },
                )
            self.accept()
            return

        if key == "ftp":
            ftp, err = self._connect_ftp_blocking(host, port, user, password)
            if err or ftp is None:
                QMessageBox.warning(self, "FTP", err or "Connection failed.")
                return
            self._outcome = SessionLoginOutcome(
                kind="ftp",
                ftp_client=ftp,
                ftp_host=host,
                ftp_port=port,
                ftp_user=user,
                ftp_password=password,
            )
            if not skip_bookmark_save:
                self._maybe_save_bookmark(
                    "ftp",
                    {
                        "ftp_host": host,
                        "ftp_port": port,
                        "ftp_user": user,
                    },
                )
            self.accept()
