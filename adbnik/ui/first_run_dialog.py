"""Shown once on a fresh install before ~/.adbnik.json exists — polished first-run experience."""

from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..config import AppConfig


class FirstRunDialog(QDialog):
    def __init__(self, config: AppConfig, parent=None, *, is_upgrade: bool = False):
        super().__init__(parent)
        self._config = config
        self._is_upgrade = bool(is_upgrade)
        self.setWindowTitle("Welcome — Adbnik" if not is_upgrade else "Adbnik updated — review settings")
        self.setModal(True)
        self.setObjectName("FirstRunDialog")
        app = QApplication.instance()
        if app is not None:
            self.setWindowIcon(app.windowIcon())
        self.setMinimumSize(620, 520)
        self.resize(680, 560)
        self._build_ui()
        self._apply_styles()

    def _theme_card(self, title: str, dark_preview: bool) -> QPushButton:
        btn = QPushButton()
        btn.setCheckable(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn.setFixedSize(220, 148)
        btn.setObjectName("FirstRunThemeCardDark" if dark_preview else "FirstRunThemeCardLight")

        outer = QVBoxLayout(btn)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        preview = QFrame()
        preview.setObjectName("FirstRunThemePreviewDark" if dark_preview else "FirstRunThemePreviewLight")
        preview.setFixedHeight(88)
        pl = QVBoxLayout(preview)
        pl.setContentsMargins(8, 8, 8, 8)
        hint = QLabel("user@device:~$ ls\n  build  src")
        hint.setObjectName("FirstRunThemePreviewHint")
        hint.setWordWrap(True)
        pl.addWidget(hint)

        cap = QLabel(title)
        cap.setAlignment(Qt.AlignCenter)
        cap.setObjectName("FirstRunThemeCaption")
        outer.addWidget(preview)
        outer.addWidget(cap)
        return btn

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        inner = QWidget()
        body = QVBoxLayout(inner)
        body.setContentsMargins(8, 8, 8, 8)
        body.setSpacing(22)

        brand = QHBoxLayout()
        brand.setSpacing(14)
        logo = QLabel()
        logo.setObjectName("FirstRunLogo")
        logo.setText('<span style="font-size: 32px; font-weight: 800; color: #58a6ff;">&gt;_</span>')
        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        t = QLabel("Adbnik")
        t.setObjectName("FirstRunBrandTitle")
        sub = QLabel(
            "Android & embedded workspace — terminal, files, screen mirror."
            if not self._is_upgrade
            else "Thanks for updating — confirm theme and tools below."
        )
        sub.setObjectName("FirstRunBrandSub")
        sub.setWordWrap(True)
        title_col.addWidget(t)
        title_col.addWidget(sub)
        brand.addWidget(logo, 0, Qt.AlignTop)
        brand.addLayout(title_col, 1)
        body.addLayout(brand)

        theme_hdr = QLabel("Select your favorite theme")
        theme_hdr.setObjectName("FirstRunSectionTitle")
        theme_hdr.setAlignment(Qt.AlignCenter)
        body.addWidget(theme_hdr)

        theme_row = QHBoxLayout()
        theme_row.setSpacing(18)
        theme_row.addStretch(1)
        self._btn_light = self._theme_card("Light", False)
        self._btn_dark = self._theme_card("Dark", True)
        self._theme_group = QButtonGroup(self)
        self._theme_group.setExclusive(True)
        self._theme_group.addButton(self._btn_light)
        self._theme_group.addButton(self._btn_dark)
        dark_on = bool(getattr(self._config, "dark_theme", False))
        self._btn_dark.setChecked(dark_on)
        self._btn_light.setChecked(not dark_on)
        theme_row.addWidget(self._btn_light)
        theme_row.addWidget(self._btn_dark)
        theme_row.addStretch(1)
        body.addLayout(theme_row)

        self._btn_light.clicked.connect(self._apply_styles)
        self._btn_dark.clicked.connect(self._apply_styles)

        paths_hdr = QLabel("Tools (optional — leave empty to use PATH)")
        paths_hdr.setObjectName("FirstRunSectionTitleSmall")
        paths_hdr.setAlignment(Qt.AlignCenter)
        body.addWidget(paths_hdr)

        paths_box = QFrame()
        paths_box.setObjectName("FirstRunPathsBox")
        pf = QFormLayout(paths_box)
        pf.setContentsMargins(16, 16, 16, 16)
        pf.setSpacing(12)
        row_adb = QHBoxLayout()
        self.adb_edit = QLineEdit(self._config.adb_path)
        self.adb_edit.setPlaceholderText("adb")
        btn_adb = QPushButton("Browse…")
        btn_adb.setObjectName("FirstRunBrowseBtn")
        btn_adb.clicked.connect(self._browse_adb)
        row_adb.addWidget(self.adb_edit, 1)
        row_adb.addWidget(btn_adb)
        pf.addRow("ADB", row_adb)

        row_sc = QHBoxLayout()
        self.scrcpy_edit = QLineEdit(self._config.scrcpy_path)
        self.scrcpy_edit.setPlaceholderText("scrcpy")
        btn_sc = QPushButton("Browse…")
        btn_sc.setObjectName("FirstRunBrowseBtn")
        btn_sc.clicked.connect(self._browse_scrcpy)
        row_sc.addWidget(self.scrcpy_edit, 1)
        row_sc.addWidget(btn_sc)
        pf.addRow("scrcpy", row_sc)
        body.addWidget(paths_box)

        body.addStretch(1)
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self._save)
        ok = buttons.button(QDialogButtonBox.Ok)
        if ok is not None:
            ok.setText("Continue")
            ok.setObjectName("FirstRunContinueBtn")
            ok.setMinimumHeight(40)
            ok.setMinimumWidth(140)
        root.addWidget(buttons)

    def _apply_styles(self) -> None:
        dark = self._btn_dark.isChecked()
        if dark:
            self.setStyleSheet(
                """
                QDialog#FirstRunDialog {
                    background-color: #1e1e1e;
                    color: #e6edf3;
                }
                QLabel#FirstRunBrandTitle {
                    font-size: 26px;
                    font-weight: 800;
                    color: #f0f6fc;
                }
                QLabel#FirstRunBrandSub {
                    font-size: 13px;
                    color: #8b949e;
                    max-width: 520px;
                }
                QLabel#FirstRunSectionTitle {
                    font-size: 15px;
                    font-weight: 700;
                    color: #c9d1d9;
                    margin-top: 8px;
                }
                QLabel#FirstRunSectionTitleSmall {
                    font-size: 13px;
                    font-weight: 600;
                    color: #8b949e;
                }
                QFrame#FirstRunPathsBox {
                    background-color: #252526;
                    border: 1px solid #3d3d42;
                    border-radius: 8px;
                }
                QLineEdit {
                    background-color: #1e1e1e;
                    color: #e6edf3;
                    border: 1px solid #3d3d42;
                    border-radius: 6px;
                    padding: 8px 10px;
                    min-height: 22px;
                    font-size: 13px;
                }
                QPushButton#FirstRunBrowseBtn {
                    background-color: #30363d;
                    color: #e6edf3;
                    border: 1px solid #484f58;
                    border-radius: 6px;
                    padding: 8px 14px;
                    min-width: 88px;
                }
                QPushButton#FirstRunBrowseBtn:hover { background-color: #3d444d; }
                QPushButton#FirstRunThemeCardDark {
                    background-color: #2d333b;
                    border: 2px solid #444c56;
                    border-radius: 10px;
                }
                QPushButton#FirstRunThemeCardDark:checked {
                    border: 2px solid #58a6ff;
                    background-color: #21262d;
                }
                QPushButton#FirstRunThemeCardLight {
                    background-color: #ffffff;
                    border: 2px solid #d0d7de;
                    border-radius: 10px;
                }
                QPushButton#FirstRunThemeCardLight:checked {
                    border: 2px solid #0969da;
                    background-color: #f6f8fa;
                }
                QPushButton#FirstRunThemeCardDark QLabel#FirstRunThemeCaption {
                    color: #e6edf3;
                }
                QPushButton#FirstRunThemeCardLight QLabel#FirstRunThemeCaption {
                    color: #24292f;
                }
                QFrame#FirstRunThemePreviewDark {
                    background-color: #0d1117;
                    border: 1px solid #30363d;
                    border-radius: 6px;
                }
                QFrame#FirstRunThemePreviewLight {
                    background-color: #ffffff;
                    border: 1px solid #d0d7de;
                    border-radius: 6px;
                }
                QLabel#FirstRunThemePreviewHint {
                    font-family: "Cascadia Mono", "Consolas", monospace;
                    font-size: 10px;
                    color: #3fb950;
                }
                QFrame#FirstRunThemePreviewLight QLabel#FirstRunThemePreviewHint {
                    color: #0969da;
                }
                QLabel#FirstRunThemeCaption {
                    font-size: 13px;
                    font-weight: 600;
                    color: #c9d1d9;
                }
                QPushButton#FirstRunContinueBtn {
                    background-color: #238636;
                    color: #ffffff;
                    border: none;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: 700;
                    padding: 10px 24px;
                }
                QPushButton#FirstRunContinueBtn:hover { background-color: #2ea043; }
                QScrollArea { background: transparent; border: none; }
                """
            )
        else:
            self.setStyleSheet(
                """
                QDialog#FirstRunDialog {
                    background-color: #f6f8fa;
                    color: #1f2328;
                }
                QLabel#FirstRunBrandTitle {
                    font-size: 26px;
                    font-weight: 800;
                    color: #1f2328;
                }
                QLabel#FirstRunBrandSub {
                    font-size: 13px;
                    color: #656d76;
                    max-width: 520px;
                }
                QLabel#FirstRunSectionTitle {
                    font-size: 15px;
                    font-weight: 700;
                    color: #24292f;
                    margin-top: 8px;
                }
                QLabel#FirstRunSectionTitleSmall {
                    font-size: 13px;
                    font-weight: 600;
                    color: #656d76;
                }
                QFrame#FirstRunPathsBox {
                    background-color: #ffffff;
                    border: 1px solid #d0d7de;
                    border-radius: 8px;
                }
                QLineEdit {
                    background-color: #ffffff;
                    color: #1f2328;
                    border: 1px solid #d0d7de;
                    border-radius: 6px;
                    padding: 8px 10px;
                    min-height: 22px;
                    font-size: 13px;
                }
                QPushButton#FirstRunBrowseBtn {
                    background-color: #f6f8fa;
                    color: #24292f;
                    border: 1px solid #d0d7de;
                    border-radius: 6px;
                    padding: 8px 14px;
                    min-width: 88px;
                }
                QPushButton#FirstRunBrowseBtn:hover { background-color: #eaeef2; }
                QPushButton#FirstRunThemeCardDark {
                    background-color: #2d333b;
                    border: 2px solid #444c56;
                    border-radius: 10px;
                }
                QPushButton#FirstRunThemeCardDark:checked {
                    border: 2px solid #58a6ff;
                    background-color: #21262d;
                }
                QPushButton#FirstRunThemeCardLight {
                    background-color: #ffffff;
                    border: 2px solid #d0d7de;
                    border-radius: 10px;
                }
                QPushButton#FirstRunThemeCardLight:checked {
                    border: 2px solid #0969da;
                    background-color: #f6f8fa;
                }
                QPushButton#FirstRunThemeCardDark QLabel#FirstRunThemeCaption {
                    color: #e6edf3;
                }
                QPushButton#FirstRunThemeCardLight QLabel#FirstRunThemeCaption {
                    color: #24292f;
                }
                QFrame#FirstRunThemePreviewDark {
                    background-color: #0d1117;
                    border: 1px solid #30363d;
                    border-radius: 6px;
                }
                QFrame#FirstRunThemePreviewLight {
                    background-color: #ffffff;
                    border: 1px solid #d0d7de;
                    border-radius: 6px;
                }
                QLabel#FirstRunThemePreviewHint {
                    font-family: "Cascadia Mono", "Consolas", monospace;
                    font-size: 10px;
                    color: #3fb950;
                }
                QFrame#FirstRunThemePreviewLight QLabel#FirstRunThemePreviewHint {
                    color: #0969da;
                }
                QLabel#FirstRunThemeCaption {
                    font-size: 13px;
                    font-weight: 600;
                    color: #24292f;
                }
                QPushButton#FirstRunContinueBtn {
                    background-color: #0969da;
                    color: #ffffff;
                    border: none;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: 700;
                    padding: 10px 24px;
                }
                QPushButton#FirstRunContinueBtn:hover { background-color: #0550ae; }
                QScrollArea { background: transparent; border: none; }
                """
            )

    def _browse_adb(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select adb", str(Path.home()))
        if path:
            self.adb_edit.setText(path)

    def _browse_scrcpy(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select scrcpy", str(Path.home()))
        if path:
            self.scrcpy_edit.setText(path)

    def _save(self) -> None:
        self._config.dark_theme = self._btn_dark.isChecked()
        self._config.adb_path = self.adb_edit.text().strip()
        self._config.scrcpy_path = self.scrcpy_edit.text().strip()
        self._config.last_acknowledged_version = __version__ or ""
        try:
            self._config.save()
        except OSError as exc:
            QMessageBox.warning(self, "Could not save", str(exc))
            return
        self.accept()
