"""Icons for bookmarks and local shell buttons (clear, recognizable glyphs)."""

from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import QStyle, QWidget


def icon_windows_cmd_console() -> QIcon:
    """Dark console tile with >_ — distinct from PowerShell."""
    pm = QPixmap(22, 22)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#1e293b"))
    p.drawRoundedRect(2, 2, 18, 18, 4, 4)
    p.setPen(QColor("#94a3b8"))
    p.drawRoundedRect(2, 2, 18, 18, 4, 4)
    p.setPen(QColor("#f1f5f9"))
    p.setFont(QFont("Consolas", 8, QFont.Bold))
    p.drawText(4, 15, ">_")
    p.end()
    return QIcon(pm)


def icon_windows_powershell() -> QIcon:
    """PowerShell blue tile with PS monogram."""
    pm = QPixmap(22, 22)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#012456"))
    p.drawRoundedRect(2, 2, 18, 18, 4, 4)
    p.setPen(QColor("#38bdf8"))
    p.drawRoundedRect(2, 2, 18, 18, 4, 4)
    p.setPen(QColor("#f8fafc"))
    p.setFont(QFont("Segoe UI", 7, QFont.Bold))
    p.drawText(5, 14, "PS")
    p.end()
    return QIcon(pm)


def icon_media_play_green() -> QIcon:
    pm = QPixmap(22, 22)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#16a34a"))
    p.drawRoundedRect(2, 2, 18, 18, 4, 4)
    p.setBrush(QColor("#f8fafc"))
    p.drawPolygon(QPoint(8, 6), QPoint(8, 16), QPoint(16, 11))
    p.end()
    return QIcon(pm)


def icon_media_stop_red() -> QIcon:
    pm = QPixmap(22, 22)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#dc2626"))
    p.drawRoundedRect(2, 2, 18, 18, 4, 4)
    p.setBrush(QColor("#f8fafc"))
    p.drawRect(7, 7, 8, 8)
    p.end()
    return QIcon(pm)


def icon_nav_up() -> QIcon:
    pm = QPixmap(22, 22)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#1e293b"))
    p.drawRoundedRect(2, 2, 18, 18, 4, 4)
    p.setPen(QColor("#93c5fd"))
    p.setBrush(QColor("#93c5fd"))
    p.drawPolygon(QPoint(11, 6), QPoint(6, 12), QPoint(9, 12), QPoint(9, 16), QPoint(13, 16), QPoint(13, 12), QPoint(16, 12))
    p.end()
    return QIcon(pm)


def icon_home_folder() -> QIcon:
    pm = QPixmap(22, 22)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#1e293b"))
    p.drawRoundedRect(2, 2, 18, 18, 4, 4)
    p.setBrush(QColor("#f8fafc"))
    p.drawPolygon(QPoint(4, 11), QPoint(11, 5), QPoint(18, 11))
    p.drawRoundedRect(6, 10, 10, 7, 1, 1)
    p.setBrush(QColor("#1e293b"))
    p.drawRoundedRect(10, 12, 2, 5, 1, 1)
    p.end()
    return QIcon(pm)


def icon_root_drive() -> QIcon:
    pm = QPixmap(22, 22)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#334155"))
    p.drawRoundedRect(3, 6, 16, 10, 3, 3)
    p.setBrush(QColor("#22c55e"))
    p.drawEllipse(15, 12, 3, 3)
    p.end()
    return QIcon(pm)


def bookmark_icon_for_kind(kind: str, widget: QWidget) -> QIcon:
    """Map bookmark kind to a platform-standard icon."""
    st = widget.style()
    k = (kind or "").lower()
    if k == "ssh":
        return st.standardIcon(QStyle.SP_DriveNetIcon)
    if k == "adb":
        return st.standardIcon(QStyle.SP_ComputerIcon)
    if k == "local_cmd":
        return icon_windows_cmd_console()
    if k == "local_pwsh":
        return icon_windows_powershell()
    if k == "serial":
        return st.standardIcon(QStyle.SP_MessageBoxInformation)
    if k in ("sftp", "ftp"):
        return st.standardIcon(QStyle.SP_FileDialogStart)
    return st.standardIcon(QStyle.SP_FileIcon)


def bookmark_icon_from_entry(bm: dict, widget: QWidget) -> QIcon:
    """Optional per-bookmark override: bm['icon'] = 'ssh'|'adb'|..."""
    if isinstance(bm, dict):
        override = (bm.get("icon") or "").strip().lower()
        if override:
            return bookmark_icon_for_kind(override, widget)
        return bookmark_icon_for_kind(str(bm.get("kind", "")), widget)
    return bookmark_icon_for_kind("", widget)
