"""Application window icon — multi-resolution for crisp taskbar and title bars."""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QIcon, QPainter, QPixmap


def _render_icon_pixmap(size: int) -> QPixmap:
    """Rounded tile with a simple device glyph, scaled to ``size``."""
    s = max(16, int(size))
    pm = QPixmap(s, s)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    p.setPen(Qt.NoPen)

    m = max(1, s // 10)
    r = max(2, s // 5)
    p.setBrush(QColor("#2563eb"))
    p.drawRoundedRect(m, m, s - 2 * m, s - 2 * m, r, r)

    inner_l = s // 4
    inner_t = s // 5
    inner_w = s - 2 * inner_l
    inner_h = int(s * 0.55)
    p.setBrush(QColor("#e2e8f0"))
    p.drawRoundedRect(inner_l, inner_t, inner_w, inner_h, max(1, s // 32), max(1, s // 32))

    p.setBrush(QColor("#2563eb"))
    ex = s // 2 - s // 10
    ey = inner_t + inner_h - s // 12
    ew = max(2, s // 5)
    eh = max(2, s // 12)
    p.drawEllipse(ex, ey, ew, eh)

    p.end()
    return pm


def create_app_icon() -> QIcon:
    """Icons for taskbar, alt-tab, and window title — several sizes for HiDPI."""
    icon = QIcon()
    for size in (16, 20, 24, 32, 40, 48, 64, 96, 128, 256):
        pm = _render_icon_pixmap(size)
        icon.addPixmap(pm)
    return icon
