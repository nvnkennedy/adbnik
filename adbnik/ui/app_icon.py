"""Application window icon — multi-resolution for taskbar and title bars.

Two variants: **dark** (slate tile, for dark UI) and **light** (soft card, for light UI).
"""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QIcon, QPainter, QPen, QPixmap


def _render_icon_pixmap(size: int, *, dark: bool) -> QPixmap:
    s = max(16, int(size))
    pm = QPixmap(s, s)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)

    pad = max(1, s // 14)
    r = max(3, s // 5)

    p.setPen(Qt.NoPen)
    if dark:
        # Dark: deep slate tile
        p.setBrush(QColor("#0f172a"))
        p.drawRoundedRect(pad, pad, s - 2 * pad, s - 2 * pad, r, r)
        accent = QColor("#2dd4bf")  # teal-400
        letter = QColor("#f8fafc")
    else:
        # Light: soft card with subtle rim (simulated with two rounded rects)
        p.setBrush(QColor("#e2e8f0"))
        p.drawRoundedRect(pad, pad, s - 2 * pad, s - 2 * pad, r, r)
        inset = max(1, s // 64)
        p.setBrush(QColor("#f8fafc"))
        p.drawRoundedRect(
            pad + inset,
            pad + inset,
            s - 2 * pad - 2 * inset,
            s - 2 * pad - 2 * inset,
            max(2, r - 2),
            max(2, r - 2),
        )
        accent = QColor("#0d9488")  # teal-600 — readable on light
        letter = QColor("#0f172a")

    # Accent node (top-right)
    nd = max(2, s // 5)
    ex = s - pad - nd - max(0, s // 40)
    ey = pad + max(0, s // 28)
    p.setBrush(accent)
    p.drawEllipse(ex, ey, nd, nd)

    # Letter A
    pen_w = max(1, round(s / 14))
    p.setPen(QPen(letter, pen_w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)

    cx = s // 2
    top = int(s * 0.30)
    bot = int(s * 0.72)
    half_w = int(s * 0.20)
    p.drawLine(cx - half_w, bot, cx, top)
    p.drawLine(cx, top, cx + half_w, bot)
    bar_y = int(s * 0.52)
    bar_half = int(s * 0.12)
    p.drawLine(cx - bar_half, bar_y, cx + bar_half, bar_y)

    p.end()
    return pm


def create_app_icon(*, dark: bool = True) -> QIcon:
    """Build a multi-size icon. Match ``dark`` to the active UI theme for best contrast."""
    icon = QIcon()
    for sz in (16, 20, 24, 32, 40, 48, 64, 96, 128, 256):
        icon.addPixmap(_render_icon_pixmap(sz, dark=dark))
    return icon
