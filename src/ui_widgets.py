from PyQt5 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg

from .audio import GRAPHIC_EQ_BANDS


class DbDisplayWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0.0

        self.label = QtWidgets.QLabel("0.0 dBA")
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        font = QtGui.QFont("Arial", 60, QtGui.QFont.Bold)
        self.label.setFont(font)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.label)

    def set_value(self, value):
        self._value = value
        self.label.setText(f"{value:.1f} dBA")


class RangeBarWidget(QtWidgets.QWidget):
    def __init__(self, low_db, high_db, min_db=40.0, max_db=110.0, parent=None):
        super().__init__(parent)
        self.value = 0.0
        self.low_db = low_db
        self.high_db = high_db
        self.min_db = min_db
        self.max_db = max_db
        self.setMinimumHeight(200)

    def set_value(self, value):
        self.value = value
        self.update()

    def set_range(self, low_db, high_db):
        self.low_db = low_db
        self.high_db = high_db
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        rect = self.rect().adjusted(20, 20, -20, -20)

        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtGui.QPen(QtGui.QColor("#333333"), 2))
        painter.drawRoundedRect(rect, 12, 12)

        def scale(db):
            return (db - self.min_db) / (self.max_db - self.min_db)

        low_x = rect.left() + rect.width() * scale(self.low_db)
        high_x = rect.left() + rect.width() * scale(self.high_db)

        red = QtGui.QColor("#b31b1b")
        green = QtGui.QColor("#2e8b57")

        painter.fillRect(QtCore.QRectF(rect.left(), rect.top(), max(low_x - rect.left(), 0), rect.height()), red)
        painter.fillRect(QtCore.QRectF(low_x, rect.top(), max(high_x - low_x, 0), rect.height()), green)
        painter.fillRect(QtCore.QRectF(high_x, rect.top(), max(rect.right() - high_x, 0), rect.height()), red)

        value_x = rect.left() + rect.width() * scale(self.value)
        value_x = max(rect.left(), min(value_x, rect.right()))

        painter.setPen(QtGui.QPen(QtGui.QColor("#111111"), 4))
        painter.drawLine(QtCore.QPointF(value_x, rect.top()), QtCore.QPointF(value_x, rect.bottom()))

        painter.setPen(QtGui.QColor("#111111"))
        painter.setFont(QtGui.QFont("Arial", 24, QtGui.QFont.Bold))
        painter.drawText(rect, QtCore.Qt.AlignCenter, f"{self.value:.1f} dBA")


class SpectrumWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        pg.setConfigOptions(antialias=True)
        self.plot = pg.PlotWidget(background="w")
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.showGrid(x=False, y=True, alpha=0.3)
        self.plot.setYRange(-80, 0)
        self.plot.setLabel("left", "dB", units="FS")
        self.plot.setLabel("bottom", "31-band EQ")

        self.bar_item = pg.BarGraphItem(x=list(range(len(GRAPHIC_EQ_BANDS))),
                                        height=[-80] * len(GRAPHIC_EQ_BANDS),
                                        width=0.6,
                                        brush=pg.mkBrush("#1f77b4"))
        self.plot.addItem(self.bar_item)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.plot)

        axis = self.plot.getAxis("bottom")
        labels = [self._format_freq(f) for f in GRAPHIC_EQ_BANDS]
        axis.setTicks([list(enumerate(labels))])

    def _format_freq(self, freq):
        if freq >= 1000:
            return f"{freq/1000:.1f}k"
        return f"{freq:g}"

    def set_levels(self, levels_db):
        heights = [max(min(v, 0), -80) for v in levels_db]
        self.bar_item.setOpts(height=heights)
