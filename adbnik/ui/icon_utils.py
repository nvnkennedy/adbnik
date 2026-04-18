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


def icon_ssh_session() -> QIcon:
    """SSH: dark tile + network link + prompt (distinct from generic “network drive”)."""
    pm = QPixmap(22, 22)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#0f172a"))
    p.drawRoundedRect(2, 2, 18, 18, 4, 4)
    p.setPen(QColor("#38bdf8"))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(5, 6, 5, 5)
    p.drawEllipse(12, 6, 5, 5)
    p.drawLine(10, 8, 12, 8)
    p.setPen(QColor("#94a3b8"))
    p.setFont(QFont("Consolas", 8, QFont.Bold))
    p.drawText(5, 18, ">_")
    p.end()
    return QIcon(pm)


def icon_adb_android() -> QIcon:
    """ADB: small Android-green bug droid head."""
    pm = QPixmap(22, 22)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#3ddc84"))
    p.drawRoundedRect(5, 7, 12, 10, 3, 3)
    p.setBrush(QColor("#0f172a"))
    p.drawEllipse(8, 10, 2, 2)
    p.drawEllipse(12, 10, 2, 2)
    p.setBrush(QColor("#3ddc84"))
    p.drawRect(4, 5, 2, 4)
    p.drawRect(16, 5, 2, 4)
    p.end()
    return QIcon(pm)


def icon_serial_port() -> QIcon:
    """Serial / COM: D-sub style connector."""
    pm = QPixmap(22, 22)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(QColor("#64748b"))
    p.setBrush(QColor("#1e293b"))
    p.drawRoundedRect(4, 6, 14, 11, 2, 2)
    p.setPen(QColor("#94a3b8"))
    for i, x in enumerate((7, 10, 13)):
        p.drawPoint(x, 10 + (i % 2))
    p.setPen(QColor("#f59e0b"))
    p.drawLine(11, 4, 11, 6)
    p.end()
    return QIcon(pm)


def icon_sftp_session() -> QIcon:
    """SFTP: secure folder + up-arrow (upload semantics)."""
    pm = QPixmap(22, 22)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#1e3a5f"))
    p.drawRoundedRect(3, 8, 16, 11, 2, 2)
    p.setBrush(QColor("#e2e8f0"))
    p.drawPolygon(QPoint(6, 8), QPoint(11, 3), QPoint(16, 8))
    p.setPen(QColor("#38bdf8"))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(3, 8, 16, 11, 2, 2)
    p.setPen(QColor("#22c55e"))
    p.drawLine(11, 12, 11, 16)
    p.drawLine(11, 12, 8, 15)
    p.drawLine(11, 12, 14, 15)
    p.end()
    return QIcon(pm)


def icon_ftp_session() -> QIcon:
    """FTP: folder + bidirectional arrows."""
    pm = QPixmap(22, 22)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#422006"))
    p.drawRoundedRect(3, 8, 16, 11, 2, 2)
    p.setBrush(QColor("#fdba74"))
    p.drawPolygon(QPoint(6, 8), QPoint(11, 3), QPoint(16, 8))
    p.setPen(QColor("#fb923c"))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(3, 8, 16, 11, 2, 2)
    p.drawLine(7, 13, 15, 13)
    p.drawLine(7, 13, 9, 11)
    p.drawLine(7, 13, 9, 15)
    p.drawLine(15, 15, 7, 15)
    p.drawLine(15, 15, 13, 13)
    p.drawLine(15, 15, 13, 17)
    p.end()
    return QIcon(pm)


def bookmark_icon_for_kind(kind: str, widget: QWidget) -> QIcon:
    """Map bookmark kind to a clear, purpose-built icon."""
    st = widget.style()
    k = (kind or "").lower()
    if k == "ssh":
        return icon_ssh_session()
    if k == "adb":
        return icon_adb_android()
    if k == "local_cmd":
        return icon_windows_cmd_console()
    if k == "local_pwsh":
        return icon_windows_powershell()
    if k == "serial":
        return icon_serial_port()
    if k == "sftp":
        return icon_sftp_session()
    if k == "ftp":
        return icon_ftp_session()
    return st.standardIcon(QStyle.SP_FileIcon)


def bookmark_icon_from_entry(bm: dict, widget: QWidget) -> QIcon:
    """Optional per-bookmark override: bm['icon'] = 'ssh'|'adb'|..."""
    if isinstance(bm, dict):
        override = (bm.get("icon") or "").strip().lower()
        if override:
            return bookmark_icon_for_kind(override, widget)
        return bookmark_icon_for_kind(str(bm.get("kind", "")), widget)
    return bookmark_icon_for_kind("", widget)
