"""Live stick, trigger and motion diagnostics from the passive HID reader."""
import math
from PySide6.QtCore import Qt, QPointF, QRectF, QThread, Signal
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel
from .diagnostics import monitor_analog, Circularity


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
        for side in ('Native left stick', 'Native right stick'):
            holder=QWidget()
            column = QVBoxLayout(holder)
            column.setContentsMargins(0,0,0,0)
            column.addWidget(QLabel(side))
            plot = StickPlot()
            column.addWidget(plot)
            label = QLabel('Move the stick around its full outer edge.')
            label.setWordWrap(True);label.setMinimumHeight(90)
            column.addWidget(label)
            row.addWidget(holder,1)
            self.plots.append(plot)
            self.labels.append(label)
        self.mapped_columns=[];self.mapped_plots=[];self.mapped_labels=[]
        for side in ('OS left stick','OS right stick'):
            column=QWidget();column_layout=QVBoxLayout(column)
            column_layout.setContentsMargins(0,0,0,0)
            column_layout.addWidget(QLabel(side))
            plot=StickPlot();column_layout.addWidget(plot)
            label=QLabel('Waiting for mapped input.');label.setWordWrap(True);label.setMinimumHeight(90);column_layout.addWidget(label)
            row.addWidget(column,1);column.hide()
            self.mapped_columns.append(column);self.mapped_plots.append(plot);self.mapped_labels.append(label)
        self.mapped_circles=[Circularity(),Circularity()]
        layout.addLayout(row)
        self.mapped_values=QLabel();self.mapped_values.setWordWrap(True)
        layout.addWidget(self.mapped_values);self.mapped_values.hide()
        self.values = QLabel('Native input is read without changing controller settings.')
        self.values.setWordWrap(True)
        layout.addWidget(self.values)

    def reset_comparison(self, enabled):
        self.mapped_circles=[Circularity(),Circularity()]
        for plot in (*self.plots,*self.mapped_plots):plot.setMinimumHeight(180 if enabled else 220)
        for widget in (*self.mapped_columns,self.mapped_values):widget.setVisible(enabled)
        for plot,label in zip(self.mapped_plots,self.mapped_labels):
            plot.point=(0,0);plot.radii={};plot.update()
            label.setText('Waiting for mapped input.')
        self.mapped_values.setText('OS gamepad sample; this can include Steam Input mapping.')

    def show_mapped(self, sample):
        if sample is None:
            self.mapped_values.setText('Selected OS gamepad is disconnected. Choose it again before the next test.')
            for plot in self.mapped_plots:plot.point=(0,0);plot.update()
            return
        for plot,label,circle,point in zip(self.mapped_plots,self.mapped_labels,self.mapped_circles,sample['sticks']):
            circle.add(*point);measured=circle.snapshot()
            plot.point=point;plot.radii=measured['radii'];plot.update()
            error=measured['error_percent']
            metric='—' if error is None else f'{error:.1f}%'
            label.setText(f'X {point[0]:+.3f}   Y {point[1]:+.3f}\n'
                          f'Sampled RMS {metric} · {measured["coverage"]}/32 sectors')
        self.mapped_values.setText(f'OS gamepad LT {sample["triggers"][0]*100:.1f}%   RT {sample["triggers"][1]*100:.1f}% · Buttons: '+(', '.join(sample['buttons']) or 'none')+
                                   '\nOS values are sampled by the UI; they do not measure USB polling rate or latency.')

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
