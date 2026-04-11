"""Application window icon — multi-resolution for taskbar and title bars.

Adbnik mark: dark slate tile + teal accent + white "A" (distinct from older generic device glyphs).
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QIcon, QPainter, QPen, QPixmap


def _render_icon_pixmap(size: int) -> QPixmap:
    s = max(16, int(size))
    pm = QPixmap(s, s)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)

    pad = max(1, s // 14)
    r = max(3, s // 5)

    # Base: deep slate rounded tile
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#0f172a"))
    p.drawRoundedRect(pad, pad, s - 2 * pad, s - 2 * pad, r, r)

    # Accent: teal node (top-right)
    nd = max(2, s // 5)
    ex = s - pad - nd - max(0, s // 40)
    ey = pad + max(0, s // 28)
    p.setBrush(QColor("#14b8a6"))
    p.drawEllipse(ex, ey, nd, nd)

    # Letter A — white
    pen_w = max(1, round(s / 14))
    p.setPen(QPen(QColor("#f8fafc"), pen_w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)

    cx = s // 2
    top = int(s * 0.30)
    bot = int(s * 0.72)
    half_w = int(s * 0.20)
    # Left and right legs meeting at top
    p.drawLine(cx - half_w, bot, cx, top)
    p.drawLine(cx, top, cx + half_w, bot)
    # Crossbar
    bar_y = int(s * 0.52)
    bar_half = int(s * 0.12)
    p.drawLine(cx - bar_half, bar_y, cx + bar_half, bar_y)

    p.end()
    return pm


def create_app_icon() -> QIcon:
    """Icons for taskbar, alt-tab, and window title — several sizes for HiDPI."""
    icon = QIcon()
    for sz in (16, 20, 24, 32, 40, 48, 64, 96, 128, 256):
        icon.addPixmap(_render_icon_pixmap(sz))
    return icon
