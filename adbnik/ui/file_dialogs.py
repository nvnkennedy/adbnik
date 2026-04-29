"""QFileDialog helpers using Qt static APIs so Windows/macOS get native open/save/folder dialogs."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple

from PyQt5.QtWidgets import QFileDialog, QWidget


def _normalize_initial_path(directory: str) -> str:
    """Turn optional filename or relative path into an absolute path Qt shows correctly."""
    d = (directory or "").strip()
    if not d:
        return ""
    if os.path.isabs(d):
        return d
    return str((Path.home() / d).resolve())


def get_open_filename(
    parent: Optional[QWidget],
    caption: str,
    directory: str = "",
    filter_str: str = "",
) -> Tuple[str, str]:
    path, selected_filter = QFileDialog.getOpenFileName(
        parent, caption, _normalize_initial_path(directory), filter_str
    )
    return path or "", selected_filter or ""


def get_save_filename(
    parent: Optional[QWidget],
    caption: str,
    directory: str = "",
    filter_str: str = "",
) -> Tuple[str, str]:
    path, selected_filter = QFileDialog.getSaveFileName(
        parent, caption, _normalize_initial_path(directory), filter_str
    )
    return path or "", selected_filter or ""


def get_existing_directory(parent: Optional[QWidget], caption: str, directory: str = "") -> str:
    """Folder picker: Qt non-native dialog is typically faster than the shell dialog on Windows."""
    dlg = QFileDialog(parent, caption, _normalize_initial_path(directory))
    dlg.setFileMode(QFileDialog.Directory)
    dlg.setOption(QFileDialog.ShowDirsOnly, True)
    dlg.setOption(QFileDialog.DontResolveSymlinks, True)
    dlg.setOption(QFileDialog.DontUseNativeDialog, True)
    if dlg.exec_() == QFileDialog.Accepted:
        files = dlg.selectedFiles()
        return files[0] if files else ""
    return ""
