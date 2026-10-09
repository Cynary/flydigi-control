import threading
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QLabel, QPushButton, QSlider
from .motors import pulse
from .transport import ConfigurationDevice


class MotorTest(QThread):
    result = Signal(bool, str)

    def __init__(self, path, levels, parent=None):
        super().__init__(parent)
        self.path, self.levels = path, levels
        self.cancel = threading.Event()

    def run(self):
        try:
            with ConfigurationDevice(self.path) as device:
                pulse(device, self.levels, self.cancel)
            self.result.emit(True, 'Test ended; stop command sent. Did you feel the selected motors?')
        except (OSError, ValueError, RuntimeError) as error:
            self.result.emit(False, 'Motor test could not finish: ' + str(error))


class MotorPanel(QWidget):
    requested = Signal(object)
    stopped = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        note = QLabel('Test each grip or trigger motor, or all four together.\n'
                      'Each test lasts half a second. These levels are for testing, not saved settings.')
        note.setWordWrap(True)
        layout.addWidget(note)
        grid = QGridLayout()
        self.sliders, self.buttons = [], []
        for index, name in enumerate(('Left grip', 'Right grip', 'Left trigger', 'Right trigger')):
            label = QLabel(name + ' · 25%')
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(25)
            slider.setSingleStep(5)
            slider.valueChanged.connect(lambda value, label=label, name=name: label.setText(f'{name} · {value}%'))
            button = QPushButton('Test ' + name.lower())
            button.clicked.connect(lambda checked=False, i=index: self.request(i))
            grid.addWidget(label, index * 2, 0)
            grid.addWidget(slider, index * 2 + 1, 0)
            grid.addWidget(button, index * 2, 1, 2, 1)
            self.sliders.append(slider)
            self.buttons.append(button)
        layout.addLayout(grid)
        self.all = QPushButton('Test all four together')
        self.all.clicked.connect(lambda: self.request(None))
        layout.addWidget(self.all)
        self.stop = QPushButton('Stop test')
        self.stop.clicked.connect(self.stopped.emit)
        layout.addWidget(self.stop)
        self.result = QLabel('Run this from the local app while no game is sending vibration.')
        self.result.setWordWrap(True)
        layout.addWidget(self.result)
        layout.addStretch()
        self.controls = [*self.sliders, *self.buttons, self.all, self.stop]
        self.set_available(False, False)

    def request(self, side):
        levels = tuple(round(slider.value() * 255 / 100) if side is None or side == i else 0
                       for i, slider in enumerate(self.sliders))
        self.requested.emit(levels)

    def set_available(self, available, running):
        for control in (*self.sliders, *self.buttons, self.all):
            control.setEnabled(available)
        self.stop.setEnabled(running)
