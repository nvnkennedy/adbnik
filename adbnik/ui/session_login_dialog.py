"""WinSCP-style Login: form + saved sessions list (bookmarks). Terminal and Explorer share the same storage."""

from dataclasses import dataclass

from .. import APP_TITLE
from typing import Any, Callable, Dict, List, Optional

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QShowEvent
from PyQt5.QtWidgets import (
    QAbstractItemView,
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
    QPushButton,
    QVBoxLayout,
    QWidget,
    QStyle,
)

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
"""

from ..config import AppConfig
from .icon_utils import bookmark_icon_from_entry
from ..session import parse_user_at_host
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
    kind: str = ""  # adb | sftp | ftp
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
        self.setWindowTitle(f"Connect — {APP_TITLE}")
        self.setModal(True)
        self.resize(720, 420)
        self._build_ui(default_ssh_host, preferred_adb_serial)
        dark = bool(getattr(self._config, "dark_theme", False))
        self.setStyleSheet(_LOGIN_DIALOG_DARK_STYLESHEET if dark else _LOGIN_DIALOG_STYLESHEET)

    def outcome(self) -> Optional[SessionLoginOutcome]:
        return self._outcome

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if hasattr(self, "device_combo") and getattr(self, "adb_box", None) and self.adb_box.isVisible():
            cur_data = self.device_combo.currentData()
            pref = str(cur_data).strip() if cur_data is not None else ""
            self._fill_device_combo(pref or self._preferred_adb_serial)

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
        if not self._for_terminal:
            k = bm.get("kind")
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
        self._try_login(skip_bookmark_save=True)

    def _apply_bookmark_to_fields(self, bm: Dict[str, Any]) -> None:
        k = bm.get("kind")
        if k == "adb":
            self.protocol_combo.setCurrentText("Android (ADB)")
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
            self.protocol_combo.setCurrentText("SFTP")
            self.host_edit.setText(bm.get("ssh_host", ""))
            try:
                p = int(bm.get("ssh_port") or 22)
            except (TypeError, ValueError):
                p = 22
            self.port_edit.setText(str(p))
            self.user_edit.setText(bm.get("ssh_user", ""))
            self.password_edit.clear()
        elif k == "sftp" and not self._for_terminal:
            self.protocol_combo.setCurrentText("SFTP")
            self.host_edit.setText(bm.get("sftp_host", bm.get("ssh_host", "")))
            try:
                p = int(bm.get("sftp_port", bm.get("ssh_port")) or 22)
            except (TypeError, ValueError):
                p = 22
            self.port_edit.setText(str(p))
            self.user_edit.setText(bm.get("sftp_user", bm.get("ssh_user", "")))
            self.password_edit.clear()
        elif k == "ftp" and not self._for_terminal:
            self.protocol_combo.setCurrentText("FTP")
            self.host_edit.setText(bm.get("ftp_host", ""))
            try:
                p = int(bm.get("ftp_port") or 21)
            except (TypeError, ValueError):
                p = 21
            self.port_edit.setText(str(p))
            self.user_edit.setText(bm.get("ftp_user", ""))
            self.password_edit.clear()
        elif k == "serial" and self._for_terminal:
            self.protocol_combo.setCurrentText("Serial")
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

        form_host = QVBoxLayout()
        if self._for_terminal:
            intro = QLabel(
                "Choose SFTP, Android (ADB), or Serial. Enter connection details, or pick a bookmark on the left. "
                "Double-click a bookmark to connect; use Load into form to edit fields first."
            )
            intro.setObjectName("LoginDialogIntro")
            intro.setWordWrap(True)
            form_host.addWidget(intro)
        else:
            intro2 = QLabel(
                "Connect to SFTP, FTP, or Android (ADB). "
                "Double-click a bookmark to connect; use Load into form to copy details into the fields first."
            )
            intro2.setObjectName("LoginDialogIntro")
            intro2.setWordWrap(True)
            form_host.addWidget(intro2)

        self.protocol_combo = ExpandAllComboBox()
        self.protocol_combo.setMaxVisibleItems(12)
        if self._for_terminal:
            self.protocol_combo.addItems(["SFTP", "Android (ADB)", "Serial"])
        else:
            self.protocol_combo.addItems(["SFTP", "FTP", "Android (ADB)"])
        self.protocol_combo.currentIndexChanged.connect(self._on_protocol_changed)
        form_host.addWidget(self.protocol_combo)

        self.network_box = QGroupBox("Session")
        net_form = QFormLayout(self.network_box)
        du, dh = parse_user_at_host(default_ssh_host)
        self.host_edit = QLineEdit(dh)
        self.host_edit.setPlaceholderText("Host name")
        self.port_edit = QLineEdit("22")
        self.port_edit.setMaximumWidth(72)
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

        outer.addLayout(form_host, 1)
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

        self._on_protocol_changed(0)
        if self._initial_protocol:
            idx = self.protocol_combo.findText(self._initial_protocol)
            if idx >= 0:
                self.protocol_combo.setCurrentIndex(idx)

    def _on_protocol_changed(self, _index: int) -> None:
        proto = self.protocol_combo.currentText()
        is_adb = proto == "Android (ADB)"
        is_serial = proto == "Serial"
        is_ftp = proto == "FTP"
        self.network_box.setVisible((not is_adb) and (not is_serial))
        self.adb_box.setVisible(is_adb)
        self.serial_box.setVisible(is_serial)
        if (not is_adb) and (not is_serial):
            self.port_edit.setText("21" if is_ftp else "22")

    def _serial_from_device_selection(self) -> str:
        data = self.device_combo.currentData()
        if data is not None:
            return str(data).strip()
        t = self.device_combo.currentText().strip()
        return t.split()[0] if t else ""

    def _try_login(self, skip_bookmark_save: bool = False) -> None:
        proto = self.protocol_combo.currentText()
        if proto == "Android (ADB)":
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

        if proto == "Serial":
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
            port = int(self.port_edit.text().strip() or ("21" if proto == "FTP" else "22"))
        except ValueError:
            port = 21 if proto == "FTP" else 22
        user = self.user_edit.text().strip()
        password = self.password_edit.text()

        if proto == "SFTP":
            if self._for_terminal:
                self._outcome = SessionLoginOutcome(
                    kind="sftp",
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
            t, sftp, err = connect_sftp(host, port, user, password)
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

        if proto == "FTP":
            ftp, err = connect_ftp(host, port, user, password)
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
