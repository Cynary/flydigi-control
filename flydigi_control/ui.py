"""Couch configuration window, suitable for a non-Steam library shortcut."""
from __future__ import annotations
import sys
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QSlider, QComboBox, QStackedWidget)
from .transport import discover, ConfigurationDevice
from .navigation import GamepadNavigation


class ApplyColor(QThread):
    result = Signal(bool, str)

    def __init__(self, path, color, parent=None):
        super().__init__(parent)
        self.path, self.color = path, color

    def run(self):
        try:
            with ConfigurationDevice(self.path) as device:
                device.set_color(*self.color)
            self.result.emit(True, 'Color applied. These lights reset when the controller powers off.')
        except (OSError, ValueError, RuntimeError) as error:
            self.result.emit(False, str(error))


class FeatureOperation(QThread):
    result = Signal(bool, str)
    values = Signal(object)

    def __init__(self, path, name=None, enabled=None, parent=None):
        super().__init__(parent)
        self.path, self.name, self.enabled = path, name, enabled

    def run(self):
        try:
            with ConfigurationDevice(self.path) as device:
                device.info()
                if self.name is not None:
                    device.set_feature(self.name, self.enabled)
                self.values.emit(device.features())
                self.result.emit(True, 'Settings read back from the controller.')
        except (OSError, ValueError, RuntimeError) as error:
            self.result.emit(False, str(error))


class Window(QWidget):
    COLORS = [('Ice blue', '#45c5ff'), ('Purple', '#a078ff'), ('Pink', '#fa75c0'),
              ('Green', '#79db9c'), ('Amber', '#ffb84a'), ('White', '#ffffff')]

    def __init__(self):
        super().__init__()
        self.setWindowTitle('Flydigi Control')
        self.resize(1280, 800)
        self.worker = None
        self.selected = '#45c5ff'
        self.devices = []
        self.feature_values = {}
        self.setStyleSheet('''
            QWidget { background:#171d25; color:#e8edf3; font:24px "Sans Serif"; }
            QLabel#eyebrow { color:#7b9ab5; font-size:18px; }
            QLabel#title { font-size:46px; font-weight:600; }
            QLabel#muted { color:#a9bacb; font-size:21px; }
            QPushButton, QComboBox { background:#293848; border:3px solid transparent;
                border-radius:10px; padding:17px; text-align:left; }
            QPushButton:focus, QComboBox:focus { border-color:#77cdff; background:#3c536a; }
            QPushButton:disabled { color:#8e9bab; }
            QSlider { padding:15px; border:3px solid transparent; border-radius:10px; }
            QSlider:focus { border-color:#77cdff; }
            QSlider::groove:horizontal { height:8px; background:#405063; }
            QSlider::handle:horizontal { background:#77cdff; width:24px; margin:-8px 0; border-radius:10px; }
        ''')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(64, 40, 64, 35)
        layout.setSpacing(18)
        self.label(layout, 'MOONMACHINE  /  CONTROLLERS', 'eyebrow')
        self.label(layout, 'Flydigi Vader 5 Pro', 'title')
        self.status = self.label(layout, '', 'muted')
        self.device_box = QComboBox()
        self.device_box.currentIndexChanged.connect(self.device_changed)
        self.device_box.setPlaceholderText('No receiver connected')
        layout.addWidget(self.device_box)
        tabs = QHBoxLayout()
        self.lighting_tab = QPushButton('Lighting')
        self.settings_tab = QPushButton('Controller settings')
        tabs.addWidget(self.lighting_tab)
        tabs.addWidget(self.settings_tab)
        layout.addLayout(tabs)
        self.pages = QStackedWidget()
        layout.addWidget(self.pages)
        self.lighting_tab.clicked.connect(lambda: self.pages.setCurrentIndex(0))
        self.settings_tab.clicked.connect(lambda: self.pages.setCurrentIndex(1))
        root_layout = layout
        lighting_page = QWidget()
        layout = QVBoxLayout(lighting_page)
        self.pages.addWidget(lighting_page)
        self.label(layout, 'Lighting', 'title')
        grid = QGridLayout()
        self.color_buttons = []
        for index, (name, color) in enumerate(self.COLORS):
            button = QPushButton('●  ' + name)
            button.clicked.connect(lambda checked=False, c=color: self.choose(c))
            grid.addWidget(button, index // 3, index % 3)
            self.color_buttons.append(button)
        layout.addLayout(grid)
        self.brightness_label = self.label(layout, 'Brightness · 50%', 'muted')
        self.brightness = QSlider(Qt.Orientation.Horizontal)
        self.brightness.setRange(0, 100)
        self.brightness.setValue(50)
        self.brightness.setSingleStep(5)
        self.brightness.valueChanged.connect(lambda v: self.brightness_label.setText(f'Brightness · {v}%'))
        layout.addWidget(self.brightness)
        row = QHBoxLayout()
        self.apply = QPushButton('Apply ice blue')
        self.apply.clicked.connect(self.apply_color)
        row.addWidget(self.apply)
        self.off = QPushButton('Turn lights off')
        self.off.clicked.connect(lambda: self.apply_color(off=True))
        row.addWidget(self.off)
        layout.addLayout(row)
        self.result_label = self.label(layout, 'Choose a color and apply it to the connected controller.', 'muted')
        self.result_label.setWordWrap(True)
        layout.addStretch()
        settings_page = QWidget()
        settings = QVBoxLayout(settings_page)
        self.pages.addWidget(settings_page)
        self.label(settings, 'Controller settings', 'title')
        self.read_settings = QPushButton('Read current settings')
        self.read_settings.clicked.connect(lambda: self.feature_operation())
        settings.addWidget(self.read_settings)
        self.turbo = QPushButton('Turbo · read settings first')
        self.turbo.clicked.connect(lambda: self.toggle_feature('turbo'))
        settings.addWidget(self.turbo)
        self.label(settings, 'Turbo + a button enables rapid fire. Hold Turbo + an extra button\n'
                            'for 1.5 seconds to record a macro; press Turbo to finish.', 'muted')
        self.hotkeys = QPushButton('Fn profile shortcuts · read settings first')
        self.hotkeys.clicked.connect(lambda: self.toggle_feature('profile_hotkeys'))
        settings.addWidget(self.hotkeys)
        self.label(settings, 'Fn + A / B / X / Y selects controller profiles 1 / 2 / 3 / 4.\n'
                            'These shortcuts and Turbo are handled by the controller.', 'muted')
        self.settings_result = self.label(settings, 'Read the controller before changing a setting.', 'muted')
        self.settings_result.setWordWrap(True)
        settings.addStretch()
        self.label(root_layout, 'D-pad / stick: navigate    A: select    B: return to Steam', 'eyebrow')
        self.controls = [self.device_box, self.lighting_tab, self.settings_tab,
                         *self.color_buttons, self.brightness, self.apply, self.off,
                         self.read_settings, self.turbo, self.hotkeys]
        for control in self.controls:
            control.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        try:
            self.navigation = GamepadNavigation()
        except (OSError, RuntimeError, AttributeError):
            self.navigation = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll_navigation)
        self.timer.start(16)
        self.discovery_timer = QTimer(self)
        self.discovery_timer.timeout.connect(self.refresh)
        self.discovery_timer.start(2000)
        self.refresh()
        self.color_buttons[0].setFocus()

    def label(self, layout, text, name):
        label = QLabel(text)
        label.setObjectName(name)
        layout.addWidget(label)
        return label

    def choose(self, color):
        self.selected = color
        name = next(n for n, c in self.COLORS if c == color)
        self.apply.setText('Apply ' + name.lower())
        self.apply.setFocus()

    def refresh(self):
        devices = discover()
        if devices != self.devices:
            old = self.device_box.currentData()
            self.devices = devices
            self.device_box.blockSignals(True)
            self.device_box.clear()
            for d in devices:
                self.device_box.addItem(d['name'] + ' · ' + d['path'], d['path'])
            index = self.device_box.findData(old)
            if index >= 0:
                self.device_box.setCurrentIndex(index)
            self.device_box.blockSignals(False)
            self.feature_values = {}
        self.show_device()

    def show_device(self):
        busy = self.worker is not None
        self.apply.setEnabled(bool(self.devices) and not busy)
        self.off.setEnabled(bool(self.devices) and not busy)
        self.device_box.setEnabled(bool(self.devices) and not busy)
        self.read_settings.setEnabled(bool(self.devices) and not busy)
        for button, name in ((self.turbo, 'turbo'), (self.hotkeys, 'profile_hotkeys')):
            value = self.feature_values.get(name)
            button.setEnabled(bool(self.devices) and not busy and bool(value and value['supported']))
            label = 'Turbo' if name == 'turbo' else 'Fn profile shortcuts'
            state = ('On' if value['enabled'] else 'Off') if value else 'read settings first'
            if value and not value['supported']:
                state = 'not supported by this firmware'
            button.setText(label + ' · ' + state)
        if not self.devices:
            self.status.setText('Connect the receiver and turn on your controller.')
            return
        d = self.devices[max(0, self.device_box.currentIndex())]
        wake = 'USB wake advertised; wake test still required' if d['remote_wake_advertised'] else 'Receiver does not advertise USB remote wake'
        self.status.setText(wake)

    def device_changed(self):
        self.feature_values = {}
        self.show_device()

    def apply_color(self, checked=False, off=False):
        if self.worker is not None or not self.devices:
            return
        level = 0 if off else self.brightness.value() / 100
        color = tuple(round(int(self.selected[i:i+2], 16) * level) for i in (1, 3, 5))
        self.worker = ApplyColor(self.device_box.currentData(), color, self)
        self.worker.result.connect(lambda ok, text: self.result_label.setText(text))
        self.worker.finished.connect(self.applied)
        self.result_label.setText('Sending lighting command…')
        self.show_device()
        self.worker.start()

    def applied(self):
        self.worker.deleteLater()
        self.worker = None
        self.show_device()
        if self.pages.currentIndex() == 0:
            self.apply.setFocus()
        else:
            self.read_settings.setFocus()

    def feature_operation(self, name=None, enabled=None):
        if self.worker is not None or not self.devices:
            return
        self.worker = FeatureOperation(self.device_box.currentData(), name, enabled, self)
        self.worker.values.connect(self.set_feature_values)
        self.worker.result.connect(lambda ok, text: self.settings_result.setText(text))
        self.worker.finished.connect(self.applied)
        self.settings_result.setText('Reading controller…')
        self.show_device()
        self.worker.start()

    def set_feature_values(self, values):
        self.feature_values = values

    def toggle_feature(self, name):
        value = self.feature_values.get(name)
        if value and value['supported']:
            self.feature_operation(name, not value['enabled'])

    def poll_navigation(self):
        if self.navigation is None or not self.isActiveWindow():
            return
        for action in self.navigation.poll():
            key = {'up': Qt.Key.Key_Up, 'down': Qt.Key.Key_Down,
                   'left': Qt.Key.Key_Left, 'right': Qt.Key.Key_Right,
                   'accept': Qt.Key.Key_Return, 'back': Qt.Key.Key_Escape}[action]
            self.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier))

    def keyPressEvent(self, event):
        key = event.key()
        focused = QApplication.focusWidget()
        if key == Qt.Key.Key_Escape:
            self.close()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if isinstance(focused, QPushButton):
                focused.click()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Right) and isinstance(focused, QSlider):
            focused.setValue(focused.value() + (5 if key == Qt.Key.Key_Right else -5))
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Right) and focused is self.device_box:
            delta = 1 if key == Qt.Key.Key_Right else -1
            self.device_box.setCurrentIndex((self.device_box.currentIndex() + delta) % max(1, self.device_box.count()))
        elif key in (Qt.Key.Key_Up, Qt.Key.Key_Left, Qt.Key.Key_Down, Qt.Key.Key_Right):
            controls = [w for w in self.controls if w.isEnabled() and w.isVisible()]
            index = controls.index(focused) if focused in controls else 0
            direction = -1 if key in (Qt.Key.Key_Up, Qt.Key.Key_Left) else 1
            controls[(index + direction) % len(controls)].setFocus()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        if self.worker is not None:
            event.ignore()
            self.result_label.setText('Finishing the lighting command before closing…')
            self.worker.finished.connect(self.close)
            return
        if self.navigation is not None:
            self.navigation.close()
        event.accept()


def run(screenshot=None):
    application = QApplication(sys.argv[:1])
    window = Window()
    if screenshot:
        window.show()
        QTimer.singleShot(300, lambda: (window.grab().save(screenshot), window.close()))
    else:
        window.showFullScreen()
    application.exec()
