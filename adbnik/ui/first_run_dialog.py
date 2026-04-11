"""Shown once on a fresh install before ~/.adbnik.json exists."""

from pathlib import Path

from PyQt5.QtCore import Qt
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
    QRadioButton,
    QVBoxLayout,
)

from ..config import AppConfig


class FirstRunDialog(QDialog):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("Welcome — set up Adbnik")
        self.setModal(True)
        app = QApplication.instance()
        if app is not None:
            self.setWindowIcon(app.windowIcon())
        self.resize(520, 420)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        intro = QLabel(
            "<p><b>First run on this computer.</b></p>"
            "<p>Choose a theme and optional tool paths. You can change everything later under "
            "<b>File → Preferences</b>.</p>"
        )
        intro.setWordWrap(True)
        intro.setOpenExternalLinks(False)
        root.addWidget(intro)

        theme_box = QGroupBox("Theme")
        tb = QVBoxLayout(theme_box)
        self._radio_light = QRadioButton("Light")
        self._radio_dark = QRadioButton("Dark")
        self._radio_light.setChecked(not bool(getattr(self._config, "dark_theme", False)))
        self._radio_dark.setChecked(bool(getattr(self._config, "dark_theme", False)))
        tb.addWidget(self._radio_light)
        tb.addWidget(self._radio_dark)
        root.addWidget(theme_box)

        paths = QGroupBox("Tools (optional — leave empty to use PATH)")
        pf = QFormLayout(paths)
        row_adb = QHBoxLayout()
        self.adb_edit = QLineEdit(self._config.adb_path)
        self.adb_edit.setPlaceholderText("adb")
        btn_adb = QPushButton("Browse…")
        btn_adb.clicked.connect(self._browse_adb)
        row_adb.addWidget(self.adb_edit, 1)
        row_adb.addWidget(btn_adb)
        pf.addRow("ADB:", row_adb)

        row_sc = QHBoxLayout()
        self.scrcpy_edit = QLineEdit(self._config.scrcpy_path)
        self.scrcpy_edit.setPlaceholderText("scrcpy")
        btn_sc = QPushButton("Browse…")
        btn_sc.clicked.connect(self._browse_scrcpy)
        row_sc.addWidget(self.scrcpy_edit, 1)
        row_sc.addWidget(btn_sc)
        pf.addRow("scrcpy:", row_sc)
        root.addWidget(paths)

        root.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self._save)
        ok = buttons.button(QDialogButtonBox.Ok)
        if ok is not None:
            ok.setText("Continue")
        root.addWidget(buttons)

    def _browse_adb(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select adb", str(Path.home()))
        if path:
            self.adb_edit.setText(path)

    def _browse_scrcpy(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select scrcpy", str(Path.home()))
        if path:
            self.scrcpy_edit.setText(path)

    def _save(self) -> None:
        self._config.dark_theme = self._radio_dark.isChecked()
        self._config.adb_path = self.adb_edit.text().strip()
        self._config.scrcpy_path = self.scrcpy_edit.text().strip()
        try:
            self._config.save()
        except OSError as exc:
            QMessageBox.warning(self, "Could not save", str(exc))
            return
        self.accept()
