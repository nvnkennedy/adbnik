from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QComboBox


class ExpandAllComboBox(QComboBox):
    """Combobox that expands to show all options in one popup using native look."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setSizeAdjustPolicy(QComboBox.AdjustToContents)

    def showPopup(self) -> None:
        rows = max(1, self.count())
        self.setMaxVisibleItems(rows)
        view = self.view()
        # Use font metrics for predictable performance when opening popup.
        row_h = max(self.fontMetrics().height() + 10, 24)
        frame = view.frameWidth() * 2
        popup_h = rows * row_h + frame + 2
        fm = self.fontMetrics()
        max_w = self.width()
        for i in range(self.count()):
            text_w = fm.horizontalAdvance(self.itemText(i)) + 56
            if text_w > max_w:
                max_w = text_w
        view.setMinimumWidth(max_w)
        view.setMinimumHeight(popup_h)
        view.setMaximumHeight(popup_h)
        super().showPopup()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        # Draw a high-contrast chevron so dropdown arrow stays visible in all themes.
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        c = self.palette().color(self.foregroundRole())
        if not self.isEnabled():
            c = QColor(c.red(), c.green(), c.blue(), 130)
        p.setPen(QPen(c, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        x = self.rect().right() - 12
        y = self.rect().center().y()
        p.drawLine(x - 4, y - 2, x, y + 2)
        p.drawLine(x, y + 2, x + 4, y - 2)
        p.end()
