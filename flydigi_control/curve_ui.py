"""Controller-navigable response editor; no hardware writes until Save."""
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import QWidget, QLabel, QComboBox, QPushButton, QSlider, QVBoxLayout, QHBoxLayout, QGridLayout
from .curves import Curve, preset, samples


class CurvePlot(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(280, 280)
        self.stored = ()
        self.proposed = samples(Curve())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width, height = self.width()-40, self.height()-40
        def point(x, y):
            return QPointF(20 + width*x/100, 20+height*(100-y)/150)
        painter.setPen(QPen(QColor('#455363'), 1))
        for value in (0, 25, 50, 75, 100):
            painter.drawLine(point(value, -50), point(value, 100))
            painter.drawLine(point(0, value), point(100, value))
        for values, color in ((self.stored, '#8291a0'), (self.proposed, '#77cdff')):
            painter.setPen(QPen(QColor(color), 3))
            for i in range(1, len(values)):
                painter.drawLine(point((i-1)*12.5, values[i-1]-50), point(i*12.5, values[i]-50))


class CurvePanel(QWidget):
    def __init__(self):
        super().__init__()
        self.loading = False
        self.available = False
        layout = QVBoxLayout(self)
        self.back = QPushButton('Back to stick settings')
        layout.addWidget(self.back)
        self.description = QLabel('Create a new response for the selected stick. Nothing changes until Save.')
        self.description.setWordWrap(True)
        layout.addWidget(self.description)
        self.kind = QComboBox()
        self.kind.addItems(['Default / linear', 'Quick', 'Slow', 'Custom'])
        self.kind.currentIndexChanged.connect(self.choose_preset)
        layout.addWidget(self.kind)
        row = QHBoxLayout()
        left = QVBoxLayout()
        self.plot = CurvePlot()
        left.addWidget(self.plot)
        legend = QLabel('Gray: stored · Blue: proposed\nX: travel 0–100% · Y: output −50–100%')
        legend.setWordWrap(True)
        left.addWidget(legend)
        row.addLayout(left, 1)
        right = QGridLayout()
        self.sliders = []
        for name, low, high in (('Center', -100, 100), ('Edge', -100, 100),
                                ('Point 1 X', 0, 127), ('Point 1 Y', 0, 127),
                                ('Point 2 X', 0, 127), ('Point 2 Y', 0, 127)):
            label = QLabel()
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(low, high)
            slider.setSingleStep(1)
            slider.setProperty('step', 1)
            slider.valueChanged.connect(lambda value, n=name, l=label: l.setText(f'{n} · {value}'))
            slider.valueChanged.connect(self.edited)
            label.setText(name + ' · 0')
            right.addWidget(label, len(self.sliders), 0)
            right.addWidget(slider, len(self.sliders), 1)
            self.sliders.append(slider)
        row.addLayout(right, 1)
        layout.addLayout(row)
        self.note = QLabel()
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        self.save = QPushButton('Save response to selected stick')
        layout.addWidget(self.save)
        self.result = QLabel('')
        self.result.setWordWrap(True)
        layout.addWidget(self.result)
        self.controls = [self.back, self.kind, *self.sliders, self.save]
        self.choose_preset(0)

    def curve(self):
        c, e, x1, y1, x2, y2 = (s.value() for s in self.sliders)
        return Curve(self.kind.currentIndex(), c, e, (x1,y1), (x2,y2))

    def choose_preset(self, index):
        if index < 3:
            self.loading = True
            curve = preset(index)
            for slider, value in zip(self.sliders, (curve.center,curve.edge,*curve.point1,*curve.point2)):
                slider.setValue(value)
            self.loading = False
        self.preview()

    def edited(self, unused=None):
        if self.loading:
            return
        self.kind.blockSignals(True)
        self.kind.setCurrentIndex(3)
        self.kind.blockSignals(False)
        self.preview()

    def preview(self):
        valid = False
        try:
            curve = self.curve()
            self.plot.proposed = samples(curve)
            valid = curve.center >= 0 and curve.edge >= 0
            message = ('Center: deadzone. Edge: full output sooner. Control points use a 0–127 scale.') if valid else (
                       'Negative compensation is preview-only: its onboard encoding needs hardware validation.')
        except ValueError as error:
            self.plot.proposed = ()
            message = str(error)
        self.plot.update()
        self.note.setText(message)
        self.save.setEnabled(self.available and valid)

    def set_available(self, available):
        self.available = available
        self.preview()

    def reset(self, side, stored):
        self.description.setText(f'New {"left" if side == 0 else "right"} stick response. '
                                 'Presets reset center/edge to zero. Save changes only this stick.')
        self.plot.stored = tuple(stored)
        self.kind.blockSignals(True)
        self.kind.setCurrentIndex(0)
        self.kind.blockSignals(False)
        self.choose_preset(0)
        self.result.clear()
