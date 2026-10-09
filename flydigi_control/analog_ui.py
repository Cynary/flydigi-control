"""Live stick, trigger and motion diagnostics from the passive HID reader."""
import math
from PySide6.QtCore import Qt, QPointF, QRectF, QThread, Signal
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel
from .diagnostics import monitor_analog


class AnalogTest(QThread):
    report = Signal(object)
    result = Signal(bool, str)

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = path

    def run(self):
        try:
            monitor_analog(self.path, 60, self.report.emit)
            self.result.emit(True, 'Finished. Open a new test to reset the measurements.')
        except (OSError, ValueError, RuntimeError) as error:
            self.result.emit(False, str(error))


class StickPlot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.point = (0, 0)
        self.radii = {}
        self.setMinimumSize(220, 220)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(self.width()/2, self.height()/2)
        scale = min(self.width(), self.height())*.33
        painter.setPen(QPen(QColor('#586573'), 1))
        painter.drawRect(QRectF(center.x()-scale, center.y()-scale, scale*2, scale*2))
        painter.drawEllipse(center, scale, scale)
        painter.drawLine(QPointF(center.x()-scale, center.y()), QPointF(center.x()+scale, center.y()))
        painter.drawLine(QPointF(center.x(), center.y()-scale), QPointF(center.x(), center.y()+scale))
        painter.setPen(QPen(QColor('#76bbff'), 4))
        for sector, radius in self.radii.items():
            angle = sector*math.pi/16
            painter.drawPoint(QPointF(center.x()+scale*radius*math.cos(angle), center.y()-scale*radius*math.sin(angle)))
        painter.setBrush(QColor('#a9f89a'))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(center.x()+scale*self.point[0], center.y()-scale*self.point[1]), 6, 6)


class AnalogPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self.plots, self.labels = [], []
        for side in ('Left stick', 'Right stick'):
            column = QVBoxLayout()
            column.addWidget(QLabel(side))
            plot = StickPlot()
            column.addWidget(plot)
            label = QLabel('Move the stick around its full outer edge.')
            label.setWordWrap(True)
            column.addWidget(label)
            row.addLayout(column)
            self.plots.append(plot)
            self.labels.append(label)
        layout.addLayout(row)
        self.values = QLabel('Native input is read without changing controller settings.')
        self.values.setWordWrap(True)
        layout.addWidget(self.values)

    def show_report(self, sample):
        for i, (plot, label) in enumerate(zip(self.plots, self.labels)):
            plot.point = sample['sticks'][i]
            circle = sample['circles'][i]
            plot.radii = circle['radii']
            plot.update()
            error = circle['error_percent']
            metric = '—' if error is None else f'{error:.1f}%'
            label.setText(f'X {plot.point[0]:+.3f}   Y {plot.point[1]:+.3f}\n'
                          f'Circularity RMS error {metric} · {circle["coverage"]}/32 sectors')
        gyro = ' / '.join(f'{v:+.1f}' for v in sample['gyro'])
        accel = ' / '.join(f'{v:+.2f}' for v in sample['accel'])
        self.values.setText(f'LT {sample["triggers"][0]*100:.1f}%   RT {sample["triggers"][1]*100:.1f}%'
                            f'     Native reports/s {sample["reports_per_second"]:.0f}     {sample["remaining"]}s remaining\n'
                            f'Gyro X/Y/Z: {gyro} °/s    Acceleration X/Y/Z: {accel} g\n'
                            'Pressed: ' + (', '.join(sample['buttons']) or 'none'))
