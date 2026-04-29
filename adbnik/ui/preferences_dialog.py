from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from ..config import AppConfig
from .file_dialogs import get_open_filename


class PreferencesDialog(QDialog):
    """Dialog for tool paths and SSH quick commands (stored in the user config file)."""

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("Preferences")
        self.setModal(True)
        app = QApplication.instance()
        if app is not None:
            self.setWindowIcon(app.windowIcon())
        self.resize(560, 520)
        self._build_ui()

    def _build_ui(self) -> None:
        """Lay out path fields, SSH quick commands, and Save/Cancel."""
        root = QVBoxLayout(self)
        intro = QLabel(
            "ADB and scrcpy are not bundled with Adbnik. "
            "If adb and scrcpy are on your PATH, leave the fields empty. "
            "Otherwise enter the full path to each executable, or use Browse. "
            "That can be a normal install (for example Android SDK platform-tools) or a folder you keep yourself "
            "(portable zip, network share, USB stick): unpack adb and scrcpy there and choose those executables here."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        paths = QGroupBox("Executables")
        pf = QFormLayout(paths)
        row_adb = QHBoxLayout()
        self.adb_edit = QLineEdit(self._config.adb_path)
        self.adb_edit.setPlaceholderText("adb — or full path to adb")
        btn_adb = QPushButton("Browse…")
        btn_adb.clicked.connect(self._browse_adb)
        row_adb.addWidget(self.adb_edit, 1)
        row_adb.addWidget(btn_adb)
        pf.addRow("ADB:", row_adb)

        row_sc = QHBoxLayout()
        self.scrcpy_edit = QLineEdit(self._config.scrcpy_path)
        self.scrcpy_edit.setPlaceholderText("scrcpy — or full path to scrcpy")
        btn_sc = QPushButton("Browse…")
        btn_sc.clicked.connect(self._browse_scrcpy)
        row_sc.addWidget(self.scrcpy_edit, 1)
        row_sc.addWidget(btn_sc)
        pf.addRow("scrcpy:", row_sc)
        root.addWidget(paths)

        ssh = QGroupBox("SSH (terminal)")
        sf = QVBoxLayout(ssh)
        ssh_intro = QLabel(
            "Commands for the menu Commands → SSH (one per line). "
            "Each line: Label | shell command — sent to the active terminal when you pick it."
        )
        ssh_intro.setWordWrap(True)
        sf.addWidget(ssh_intro)
        self.quick_edit = QTextEdit()
        lines = []
        for x in getattr(self._config, "ssh_quick_commands", None) or []:
            if isinstance(x, dict):
                lab = str(x.get("label", "")).strip()
                cmd = str(x.get("command", "")).strip()
                if lab or cmd:
                    lines.append(f"{lab} | {cmd}")
        self.quick_edit.setPlainText("\n".join(lines))
        self.quick_edit.setPlaceholderText("Example:\nList disks | lsblk\nEdit fstab | sudo nano /etc/fstab")
        self.quick_edit.setMinimumHeight(120)
        sf.addWidget(self.quick_edit)
        root.addWidget(ssh)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _browse_adb(self) -> None:
        """Let the user pick adb (or adb.exe); write the path into the ADB field."""
        path, _ = get_open_filename(self, "Select adb", str(Path.home()), "")
        if path:
            self.adb_edit.setText(path)

    def _browse_scrcpy(self) -> None:
        """Let the user pick the scrcpy executable; write the path into the scrcpy field."""
        path, _ = get_open_filename(self, "Select scrcpy", str(Path.home()), "")
        if path:
            self.scrcpy_edit.setText(path)

    def _parse_quick_commands(self) -> list:
        """Parse the SSH quick-command text into a list of {label, command} dicts."""
        out = []
        for line in self.quick_edit.toPlainText().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "|" not in line:
                continue
            lab, _, cmd = line.partition("|")
            lab = lab.strip()
            cmd = cmd.strip()
            if lab or cmd:
                out.append({"label": lab or "Run", "command": cmd})
        return out

    def _save(self) -> None:
        """Persist paths and quick commands to disk and close the dialog on success."""
        self._config.adb_path = self.adb_edit.text().strip()
        self._config.scrcpy_path = self.scrcpy_edit.text().strip()
        self._config.ssh_quick_commands = self._parse_quick_commands()
        try:
            self._config.save()
        except Exception as exc:
            QMessageBox.warning(self, "Save failed", str(exc))
            return
        self.accept()
