"""Couch configuration window, suitable for a non-Steam library shortcut."""
from __future__ import annotations
import sys
import json
import os
import time
import logging
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QKeyEvent, QIcon, QPixmap, QColor
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QSlider, QComboBox, QStackedWidget)
from .transport import discover, ConfigurationDevice
from .navigation import GamepadNavigation
from .lighting import PALETTE, GRADIENT, make_blob


class ApplyColor(QThread):
    result = Signal(bool, str)

    def __init__(self, path, mode, colors, brightness, period, parent=None):
        super().__init__(parent)
        self.path, self.mode, self.colors = path, mode, colors
        self.brightness, self.period = brightness, period

    def run(self):
        try:
            with ConfigurationDevice(self.path) as device:
                profile, original = device.read_lighting()
                folder = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'flydigi-control'
                folder.mkdir(parents=True, exist_ok=True)
                backup = folder / ('lighting-' + str(time.time_ns()) + '.json')
                backup.write_text(json.dumps({'profile': profile, 'blob': original.hex()}, indent=2))
                blob = make_blob(original, self.mode, self.colors, self.brightness, self.period)
                device.write_lighting(profile, blob)
                actual_profile, actual = device.read_lighting()
                if actual_profile != profile or actual != blob:
                    raise RuntimeError('Controller lighting readback differs from the request; original settings are backed up.')
            self.result.emit(True, 'Lighting applied and read back. Temporary: turning the controller off restores saved lights.')
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
                if self.name is None:
                    device.info()
                if self.name == 'third_party_control':
                    device.set_third_party_control(self.enabled)
                elif self.name is not None:
                    device.set_feature(self.name, self.enabled)
                values = device.features()
                values['third_party_control'] = {'supported': True,
                    'enabled': device.mapping_status()['third_party_control']}
                self.values.emit(values)
                self.result.emit(True, 'Settings read back from the controller.')
        except (OSError, ValueError, RuntimeError) as error:
            self.result.emit(False, str(error))


class ButtonTest(QThread):
    report = Signal(object)
    result = Signal(bool, str)

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = path

    def run(self):
        from .capture import monitor
        folder = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'flydigi-control'
        try:
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / time.strftime('buttons-%Y%m%d-%H%M%S.jsonl')
            with target.open('w') as file:
                worker = self
                class Output:
                    def write(self, line):
                        file.write(line)
                        worker.report.emit(json.loads(line))
                    def flush(self):
                        file.flush()
                monitor(self.path, 60, Output())
            self.result.emit(True, 'Finished. Saved the report to ' + str(target))
        except (OSError, ValueError, RuntimeError) as error:
            self.result.emit(False, str(error))


class Window(QWidget):
    COLORS = PALETTE

    def __init__(self):
        super().__init__()
        self.setWindowTitle('Flydigi Control')
        self.resize(1280, 800)
        self.worker = None
        self.testing = False
        self.selected = '#ff00ff'
        self.colors = [(255, 0, 255)]
        self.loading_color = False
        self.devices = []
        self.feature_values = {}
        self.setStyleSheet('''
            QWidget { background:#171d25; color:#e8edf3; font:22px "Sans Serif"; }
            QLabel#eyebrow { color:#7b9ab5; font-size:18px; }
            QLabel#title { font-size:36px; font-weight:600; }
            QLabel#muted { color:#a9bacb; font-size:21px; }
            QPushButton, QComboBox { background:#293848; border:3px solid transparent;
                border-radius:10px; padding:9px; text-align:left; }
            QPushButton:focus, QComboBox:focus { border-color:#77cdff; background:#3c536a; }
            QPushButton:disabled { color:#8e9bab; }
            QSlider { padding:8px; border:3px solid transparent; border-radius:10px; }
            QSlider:focus { border-color:#77cdff; }
            QSlider::groove:horizontal { height:8px; background:#405063; }
            QSlider::handle:horizontal { background:#77cdff; width:24px; margin:-8px 0; border-radius:10px; }
        ''')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 24, 48, 24)
        layout.setSpacing(8)
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
        self.test_tab = QPushButton('Test buttons')
        tabs.addWidget(self.lighting_tab)
        tabs.addWidget(self.settings_tab)
        tabs.addWidget(self.test_tab)
        layout.addLayout(tabs)
        self.pages = QStackedWidget()
        layout.addWidget(self.pages)
        self.lighting_tab.clicked.connect(lambda: self.pages.setCurrentIndex(0))
        self.settings_tab.clicked.connect(lambda: self.pages.setCurrentIndex(1))
        self.test_tab.clicked.connect(lambda: self.pages.setCurrentIndex(2))
        root_layout = layout
        lighting_page = QWidget()
        layout = QVBoxLayout(lighting_page)
        self.pages.addWidget(lighting_page)
        self.effect = QComboBox()
        for label, mode in [('Steady', 5), ('Breathing', 2), ('Gradient', 3), ('Flow', 1)]:
            self.effect.addItem(label, mode)
        layout.addWidget(self.effect)
        self.effect.currentIndexChanged.connect(self.effect_changed)
        color_row = QHBoxLayout()
        self.color_slot = QComboBox()
        self.color_slot.currentIndexChanged.connect(self.load_color)
        color_row.addWidget(self.color_slot)
        self.add_color = QPushButton('Add color')
        self.add_color.clicked.connect(self.append_color)
        color_row.addWidget(self.add_color)
        self.remove_color = QPushButton('Remove color')
        self.remove_color.clicked.connect(self.delete_color)
        color_row.addWidget(self.remove_color)
        layout.addLayout(color_row)
        grid = QGridLayout()
        self.color_buttons = []
        for index, (name, color) in enumerate(self.COLORS):
            button = QPushButton(name)
            swatch = QPixmap(24, 24)
            swatch.fill(QColor(color))
            button.setIcon(QIcon(swatch))
            button.clicked.connect(lambda checked=False, c=color: self.choose(c))
            grid.addWidget(button, index // 3, index % 3)
            self.color_buttons.append(button)
        layout.addLayout(grid)
        self.rgb_sliders = []
        rgb_row = QHBoxLayout()
        for name in ('R', 'G', 'B'):
            column = QVBoxLayout()
            label = QLabel(name + ": 0")
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 255)
            slider.setSingleStep(1)
            slider.setProperty('step', 1)
            slider.valueChanged.connect(lambda value, n=name, l=label: l.setText(f'{n}: {value}'))
            slider.valueChanged.connect(self.rgb_changed)
            column.addWidget(label)
            column.addWidget(slider)
            self.rgb_sliders.append(slider)
            rgb_row.addLayout(column)
        layout.addLayout(rgb_row)
        self.brightness_label = self.label(layout, 'Brightness · 30%', 'muted')
        self.brightness = QSlider(Qt.Orientation.Horizontal)
        self.brightness.setRange(0, 100)
        self.brightness.setValue(30)
        self.brightness.setSingleStep(5)
        self.brightness.valueChanged.connect(lambda v: self.brightness_label.setText(f'Brightness · {v}%'))
        layout.addWidget(self.brightness)
        self.period_label = self.label(layout, 'Cycle time · 15 (lower is faster)', 'muted')
        self.period = QSlider(Qt.Orientation.Horizontal)
        self.period.setRange(1, 100)
        self.period.setValue(15)
        self.period.valueChanged.connect(lambda v: self.period_label.setText(f'Cycle time · {v} (lower is faster)'))
        layout.addWidget(self.period)
        row = QHBoxLayout()
        self.apply = QPushButton('Apply magenta')
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
        self.native = QPushButton('Native Steam Input · read settings first')
        self.native.clicked.connect(lambda: self.toggle_feature('third_party_control'))
        settings.addWidget(self.native)
        self.label(settings, 'Allow Steam to map the extra buttons. Controller profiles are bypassed\n'
                            'while Steam owns it. Restart Steam after changing this.', 'muted')
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
        test_page = QWidget()
        test_layout = QVBoxLayout(test_page)
        self.pages.addWidget(test_page)
        self.label(test_layout, 'Test buttons', 'title')
        self.label(test_layout, 'Press each button separately. During this 60-second test, buttons\n'
                               'cannot navigate the app or change settings.', 'muted')
        self.test_start = QPushButton('Start 60-second test')
        self.test_start.clicked.connect(self.start_button_test)
        test_layout.addWidget(self.test_start)
        self.test_result = self.label(test_layout, 'Native Steam Input must be active to receive extra-button reports.', 'muted')
        self.test_result.setWordWrap(True)
        self.test_buttons = self.label(test_layout, '', 'muted')
        self.test_buttons.setWordWrap(True)
        self.test_seen = set()
        test_layout.addStretch()
        self.label(root_layout, 'D-pad / stick: navigate    A: select    B: return to Steam', 'eyebrow')
        self.controls = [self.device_box, self.lighting_tab, self.settings_tab, self.test_tab,
                         self.effect, self.color_slot, self.add_color, self.remove_color,
                         *self.color_buttons, *self.rgb_sliders, self.brightness, self.period, self.apply, self.off,
                         self.read_settings, self.native, self.turbo, self.hotkeys, self.test_start]
        for control in self.controls:
            control.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        try:
            self.navigation = GamepadNavigation()
        except (OSError, RuntimeError, AttributeError) as error:
            self.navigation = None
            logging.exception("Gamepad navigation initialization failed")
        self._navigation_state = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll_navigation)
        self.timer.start(16)
        self.discovery_timer = QTimer(self)
        self.discovery_timer.timeout.connect(self.refresh)
        self.discovery_timer.start(2000)
        self.refresh()
        self.refresh_colors()
        self.color_buttons[0].setFocus()

    def label(self, layout, text, name):
        label = QLabel(text)
        label.setObjectName(name)
        layout.addWidget(label)
        return label

    def refresh_colors(self, index=0):
        self.color_slot.blockSignals(True)
        self.color_slot.clear()
        for i, color in enumerate(self.colors):
            self.color_slot.addItem(f'Color {i+1} · #{color[0]:02x}{color[1]:02x}{color[2]:02x}')
        self.color_slot.setCurrentIndex(min(index, len(self.colors)-1))
        self.color_slot.blockSignals(False)
        self.load_color()
        mode = self.effect.currentData()
        editable = mode != 1
        for widget in [self.color_slot, *self.color_buttons, *self.rgb_sliders]:
            widget.setEnabled(editable)
        self.add_color.setEnabled(mode in (2, 3) and len(self.colors) < 5)
        self.remove_color.setEnabled(mode in (2, 3) and len(self.colors) > (2 if mode == 3 else 1))
        self.period.setEnabled(mode in (1, 2, 3))

    def load_color(self, unused=None):
        if not hasattr(self, 'rgb_sliders') or self.color_slot.currentIndex() < 0:
            return
        self.loading_color = True
        for slider, value in zip(self.rgb_sliders, self.colors[self.color_slot.currentIndex()]):
            slider.setValue(value)
        self.loading_color = False
        self.apply.setText('Apply lighting')

    def rgb_changed(self, unused=None):
        if self.loading_color or not hasattr(self, 'apply'):
            return
        index = self.color_slot.currentIndex()
        if index >= 0:
            self.colors[index] = tuple(s.value() for s in self.rgb_sliders)
            c = self.colors[index]
            self.color_slot.setItemText(index, f'Color {index+1} · #{c[0]:02x}{c[1]:02x}{c[2]:02x}')

    def choose(self, color):
        index = max(0, self.color_slot.currentIndex())
        self.colors[index] = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
        self.refresh_colors(index)

    def effect_changed(self, unused=None):
        mode = self.effect.currentData()
        if mode == 5:
            self.colors = self.colors[:1]
        elif mode == 3 and len(self.colors) < 2:
            self.colors = list(GRADIENT)
        self.period.setValue(4 if mode == 1 else 15)
        self.brightness.setValue(20 if mode == 1 else 30 if mode == 5 else 50)
        self.refresh_colors()

    def append_color(self):
        if self.effect.currentData() in (2, 3) and len(self.colors) < 5:
            self.colors.append((0, 116, 255))
            self.refresh_colors(len(self.colors)-1)

    def delete_color(self):
        if len(self.colors) > (2 if self.effect.currentData() == 3 else 1):
            self.colors.pop(max(0, self.color_slot.currentIndex()))
            self.refresh_colors()

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
            if devices:
                self.device_box.setCurrentIndex(index if index >= 0 else 0)
            self.device_box.blockSignals(False)
            self.feature_values = {}
        self.show_device()

    def show_device(self):
        busy = self.worker is not None
        for tab in (self.lighting_tab, self.settings_tab, self.test_tab):
            tab.setEnabled(not self.testing)
        self.test_start.setEnabled(bool(self.devices) and not busy)
        self.apply.setEnabled(bool(self.devices) and not busy)
        self.off.setEnabled(bool(self.devices) and not busy)
        self.device_box.setEnabled(bool(self.devices) and not busy)
        self.read_settings.setEnabled(bool(self.devices) and not busy)
        for button, name in ((self.native, 'third_party_control'), (self.turbo, 'turbo'), (self.hotkeys, 'profile_hotkeys')):
            value = self.feature_values.get(name)
            button.setEnabled(bool(self.devices) and not busy and bool(value and value['supported']))
            label = {'turbo': 'Turbo', 'profile_hotkeys': 'Fn profile shortcuts',
                     'third_party_control': 'Native Steam Input'}[name]
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
        mode = 6 if off else self.effect.currentData()
        colors = tuple(self.colors)
        self.worker = ApplyColor(self.device_box.currentData(), mode, colors,
                                 self.brightness.value(), self.period.value(), self)
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

    def start_button_test(self):
        if self.worker is not None or not self.devices:
            return
        self.testing = True
        self.test_seen = set()
        self.test_buttons.setText('Waiting for input…')
        self.test_result.setText('Recording for 60 seconds. Navigation is disabled until it finishes.')
        self.worker = ButtonTest(self.device_box.currentData(), self)
        self.worker.report.connect(self.button_test_report)
        self.worker.result.connect(lambda ok, text: self.test_result.setText(text))
        self.worker.finished.connect(self.button_test_finished)
        self.show_device()
        self.worker.start()

    def button_test_report(self, value):
        if value['event'] == 'buttons':
            self.test_seen.update(value['pressed'])
            self.test_buttons.setText('Pressed: ' + (', '.join(value['pressed']) or 'none') +
                                      '\n\nSeen: ' + ', '.join(sorted(self.test_seen)))
        elif value['event'] == 'summary':
            self.test_buttons.setText('Seen: ' + ', '.join(value['buttons_seen']) +
                                      '\n\nNot seen: ' + ', '.join(value['buttons_not_seen']))

    def button_test_finished(self):
        self.worker.deleteLater()
        self.worker = None
        self.testing = False
        self.show_device()
        self.test_start.setFocus()

    def poll_navigation(self):
        if self.navigation is None:
            return
        # Keep processing hotplug while the Steam overlay owns focus. Only
        # dispatch navigation actions when our own window is active.
        actions = self.navigation.poll()
        state = (self.isActiveWindow(), tuple(self.navigation.devices), self.testing)
        if state != self._navigation_state:
            logging.info("Navigation active/devices/testing: %s", state)
            self._navigation_state = state
        if not self.isActiveWindow() or self.testing:
            return
        for action in actions:
            key = {'up': Qt.Key.Key_Up, 'down': Qt.Key.Key_Down,
                   'left': Qt.Key.Key_Left, 'right': Qt.Key.Key_Right,
                   'accept': Qt.Key.Key_Return, 'back': Qt.Key.Key_Escape}[action]
            self.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier))

    def keyPressEvent(self, event):
        if self.testing:
            return
        key = event.key()
        focused = QApplication.focusWidget()
        if key == Qt.Key.Key_Escape:
            self.close()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if isinstance(focused, QPushButton):
                focused.click()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Right) and isinstance(focused, QSlider):
            focused.setValue(focused.value() + (int(focused.property('step') or 5) * (1 if key == Qt.Key.Key_Right else -1)))
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Right) and isinstance(focused, QComboBox):
            delta = 1 if key == Qt.Key.Key_Right else -1
            focused.setCurrentIndex((focused.currentIndex() + delta) % max(1, focused.count()))
        elif key in (Qt.Key.Key_Up, Qt.Key.Key_Left, Qt.Key.Key_Down, Qt.Key.Key_Right):
            controls = [w for w in self.controls if w.isEnabled() and w.isVisible()]
            if not controls:
                return
            if focused not in controls:
                controls[0].setFocus()
                return
            origin = focused.mapTo(self, focused.rect().center())
            horizontal = key in (Qt.Key.Key_Left, Qt.Key.Key_Right)
            sign = -1 if key in (Qt.Key.Key_Up, Qt.Key.Key_Left) else 1
            candidates = []
            for widget in controls:
                point = widget.mapTo(self, widget.rect().center())
                dx, dy = point.x()-origin.x(), point.y()-origin.y()
                forward, sideways = (dx*sign, abs(dy)) if horizontal else (dy*sign, abs(dx))
                if forward > 0:
                    candidates.append((forward + 3*sideways, controls.index(widget), widget))
            if candidates:
                min(candidates, key=lambda item: item[:2])[2].setFocus()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        if self.worker is not None:
            event.ignore()
            self.result_label.setText('Finishing the controller operation before closing…')
            self.worker.finished.connect(self.close)
            return
        if self.navigation is not None:
            self.navigation.close()
        event.accept()


def run(screenshot=None):
    from .app_logging import create_handler
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',
                        handlers=[create_handler()])
    logging.info("App source: %s", __file__)
    application = QApplication(sys.argv[:1])
    window = Window()
    if screenshot:
        window.show()
        QTimer.singleShot(300, lambda: (window.grab().save(screenshot), window.close()))
    else:
        window.showFullScreen()
    application.exec()
