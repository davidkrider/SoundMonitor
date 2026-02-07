import math

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
    def __init__(self, low_db, high_db, min_db=None, max_db=None, parent=None):
        super().__init__(parent)
        self.value = 0.0
        self.low_db = low_db
        self.high_db = high_db
        if min_db is None or max_db is None:
            center = (low_db + high_db) / 2.0
            span = max(20.0, (high_db - low_db) * 8.0)
            self.min_db = center - span
            self.max_db = center + span
        else:
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
        painter.fillRect(rect, QtGui.QColor("#000000"))
        painter.setPen(QtGui.QPen(QtGui.QColor("#333333"), 2))
        painter.drawRoundedRect(rect, 12, 12)

        start_angle = 225.0
        sweep_angle = -270.0

        def clamp(value, low, high):
            return max(low, min(value, high))

        def angle_for_db(db):
            t = (db - self.min_db) / (self.max_db - self.min_db)
            t = clamp(t, 0.0, 1.0)
            return start_angle + sweep_angle * t

        def point_on_circle(center, radius, angle_deg):
            rad = math.radians(angle_deg)
            return QtCore.QPointF(
                center.x() + math.cos(rad) * radius,
                center.y() - math.sin(rad) * radius,
            )

        def lerp_color(a, b, t):
            return QtGui.QColor(
                int(a.red() + (b.red() - a.red()) * t),
                int(a.green() + (b.green() - a.green()) * t),
                int(a.blue() + (b.blue() - a.blue()) * t),
            )

        def draw_gradient_arc(center, radius, start_deg, end_deg, start_color, end_color, width, steps=80):
            for i in range(steps):
                t0 = i / steps
                t1 = (i + 1) / steps
                a0 = start_deg + (end_deg - start_deg) * t0
                a1 = start_deg + (end_deg - start_deg) * t1
                color = lerp_color(start_color, end_color, (t0 + t1) * 0.5)
                painter.setPen(QtGui.QPen(color, width, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
                painter.drawLine(point_on_circle(center, radius, a0), point_on_circle(center, radius, a1))

        center = QtCore.QPointF(rect.center().x(), rect.center().y() + rect.height() * 0.1)
        arc_width = max(10.0, min(rect.width(), rect.height()) * 0.05)
        max_radius = min(
            center.x() - rect.left(),
            rect.right() - center.x(),
            center.y() - rect.top(),
            rect.bottom() - center.y(),
        )
        radius = max(max_radius - arc_width * 0.6, 10.0)

        base_color = QtGui.QColor("#dddddd")
        draw_gradient_arc(center, radius, start_angle, start_angle + sweep_angle, base_color, base_color, arc_width, steps=60)

        orange = QtGui.QColor("#f28c28")
        green = QtGui.QColor("#2e8b57")
        red = QtGui.QColor("#b31b1b")

        low_angle = angle_for_db(self.low_db)
        high_angle = angle_for_db(self.high_db)
        end_angle = start_angle + sweep_angle

        draw_gradient_arc(center, radius, start_angle, low_angle, orange, green, arc_width)
        draw_gradient_arc(center, radius, low_angle, high_angle, green, green, arc_width)
        draw_gradient_arc(center, radius, high_angle, end_angle, green, red, arc_width)

        for tick_db in (self.min_db, self.low_db, 95.0, self.high_db, self.max_db):
            tick_angle = angle_for_db(tick_db)
            inner = point_on_circle(center, radius - arc_width * 0.9, tick_angle)
            outer = point_on_circle(center, radius + arc_width * 0.1, tick_angle)
            painter.setPen(QtGui.QPen(QtGui.QColor("#ffffff"), 2))
            painter.drawLine(inner, outer)

        value_angle = angle_for_db(self.value)
        needle_end = point_on_circle(center, radius - arc_width * 0.6, value_angle)
        painter.setPen(QtGui.QPen(QtGui.QColor("#ffffff"), 4))
        painter.drawLine(center, needle_end)
        painter.setBrush(QtGui.QBrush(QtGui.QColor("#ffffff")))
        painter.drawEllipse(center, 6, 6)

        painter.setPen(QtGui.QColor("#ffffff"))
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
