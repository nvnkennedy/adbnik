"""Non-native QFileDialog wrappers so Fusion stylesheets apply (fixes invisible text in light theme on Windows)."""

from __future__ import annotations

from typing import Optional, Tuple

from PyQt5.QtWidgets import QFileDialog, QWidget


def _force_styled_dialog(dlg: QFileDialog) -> None:
    dlg.setOption(QFileDialog.DontUseNativeDialog, True)


def get_open_filename(
    parent: Optional[QWidget],
    caption: str,
    directory: str = "",
    filter_str: str = "",
) -> Tuple[str, str]:
    dlg = QFileDialog(parent, caption, directory or "", filter_str)
    _force_styled_dialog(dlg)
    dlg.setFileMode(QFileDialog.ExistingFile)
    if dlg.exec_() == QFileDialog.Accepted:
        files = dlg.selectedFiles()
        return (files[0] if files else ""), dlg.selectedNameFilter()
    return "", ""


def get_save_filename(
    parent: Optional[QWidget],
    caption: str,
    directory: str = "",
    filter_str: str = "",
) -> Tuple[str, str]:
    dlg = QFileDialog(parent, caption, directory or "", filter_str)
    _force_styled_dialog(dlg)
    dlg.setAcceptMode(QFileDialog.AcceptSave)
    if dlg.exec_() == QFileDialog.Accepted:
        files = dlg.selectedFiles()
        return (files[0] if files else ""), dlg.selectedNameFilter()
    return "", ""


def get_existing_directory(parent: Optional[QWidget], caption: str, directory: str = "") -> str:
    dlg = QFileDialog(parent, caption, directory or "")
    _force_styled_dialog(dlg)
    dlg.setFileMode(QFileDialog.Directory)
    dlg.setOption(QFileDialog.ShowDirsOnly, True)
    if dlg.exec_() == QFileDialog.Accepted:
        files = dlg.selectedFiles()
        return files[0] if files else ""
    return ""
