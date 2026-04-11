from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
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


class PreferencesDialog(QDialog):
    """Paths, SSH quick commands — stored in your profile."""

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("Preferences")
        self.setModal(True)
        app = QApplication.instance()
        if app is not None:
            self.setWindowIcon(app.windowIcon())
        self.resize(560, 480)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.addWidget(QLabel("Leave tool paths empty to use the programs on your PATH (adb, scrcpy)."))

        paths = QGroupBox("Executables")
        pf = QFormLayout(paths)
        row_adb = QHBoxLayout()
        self.adb_edit = QLineEdit(self._config.adb_path)
        self.adb_edit.setPlaceholderText("adb — or full path")
        btn_adb = QPushButton("Browse…")
        btn_adb.clicked.connect(self._browse_adb)
        row_adb.addWidget(self.adb_edit, 1)
        row_adb.addWidget(btn_adb)
        pf.addRow("ADB:", row_adb)

        row_sc = QHBoxLayout()
        self.scrcpy_edit = QLineEdit(self._config.scrcpy_path)
        self.scrcpy_edit.setPlaceholderText("scrcpy — or full path")
        btn_sc = QPushButton("Browse…")
        btn_sc.clicked.connect(self._browse_scrcpy)
        row_sc.addWidget(self.scrcpy_edit, 1)
        row_sc.addWidget(btn_sc)
        pf.addRow("scrcpy:", row_sc)
        root.addWidget(paths)

        ssh = QGroupBox("SSH (terminal)")
        sf = QVBoxLayout(ssh)
        ssh_intro = QLabel(
            "Custom commands for Commands → SSH (one per line). "
            "Each line: Label | shell command — sent to the active terminal when chosen."
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

    def _browse_adb(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select adb", str(Path.home()))
        if path:
            self.adb_edit.setText(path)

    def _browse_scrcpy(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select scrcpy", str(Path.home()))
        if path:
            self.scrcpy_edit.setText(path)

    def _parse_quick_commands(self) -> list:
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

    def _save(self):
        self._config.adb_path = self.adb_edit.text().strip()
        self._config.scrcpy_path = self.scrcpy_edit.text().strip()
        self._config.ssh_quick_commands = self._parse_quick_commands()
        try:
            self._config.save()
        except Exception as exc:
            QMessageBox.warning(self, "Save failed", str(exc))
            return
        self.accept()
