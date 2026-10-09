"""Controller-friendly editor for global hardware settings."""
import os
from pathlib import Path
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QComboBox
from . import protocol
from .hardware_settings import SETTINGS, parse_status, apply_setting
from .transport import ConfigurationDevice


class HardwareOperation(QThread):
    result = Signal(bool, str)
    values = Signal(object)

    def __init__(self, path, parent=None, *, previous=None, name=None, value=None):
        super().__init__(parent)
        self.path, self.previous, self.name, self.value = path, previous, name, value

    def run(self):
        try:
            with ConfigurationDevice(self.path) as device:
                if self.name is None:
                    device.info()
                    reply = device.exchange(protocol.request(0x03))
                    parse_status(reply)
                else:
                    folder = Path(os.environ.get('XDG_STATE_HOME', str(Path.home()/'.local/state'))) / 'flydigi-control'
                    reply = apply_setting(device, self.previous, self.name, self.value, folder)
                self.values.emit(bytes(reply))
            self.result.emit(True, 'Change read back successfully. Power-cycle persistence still needs verification.'
                             if self.name is not None else 'Global settings read from the controller.')
        except (OSError, ValueError, RuntimeError) as error:
            self.result.emit(False, str(error))


class HardwarePanel(QWidget):
    def __init__(self):
        super().__init__()
        self.snapshot = None
        self.available = False
        layout = QVBoxLayout(self)
        self.back = QPushButton('Back to controller settings'); layout.addWidget(self.back)
        title = QLabel('Global controller settings'); title.setObjectName('title'); layout.addWidget(title)
        self.read = QPushButton('Read current settings'); layout.addWidget(self.read)
        self.setting = QComboBox()
        for name, item in SETTINGS.items():
            self.setting.addItem(item.label, name)
        layout.addWidget(self.setting)
        self.description = QLabel(); self.description.setWordWrap(True)
        self.description.setMinimumHeight(90); layout.addWidget(self.description)
        self.current = QLabel(); self.current.setWordWrap(True); layout.addWidget(self.current)
        self.choice = QComboBox(); layout.addWidget(self.choice)
        self.apply = QPushButton('Apply selected setting'); layout.addWidget(self.apply)
        self.result = QLabel(); self.result.setWordWrap(True); layout.addWidget(self.result)
        self.report_rate = QLabel('Report rate: not read'); layout.addWidget(self.report_rate)
        note = QLabel('Changes affect the controller globally, not just one profile.\n'
                      'Only Apply sends a change; reading or reconnecting never does.')
        note.setWordWrap(True); layout.addWidget(note)
        layout.addStretch()
        self.controls = [self.back, self.read, self.setting, self.choice, self.apply]
        self.setting.currentIndexChanged.connect(self.select_setting)
        self.choice.currentIndexChanged.connect(self.update_enabled)
        self.select_setting()

    def load(self, reply):
        parse_status(reply)
        self.snapshot = bytes(reply)
        # Keep the raw value: the vendor UI and SDK disagree about 250/125 Hz,
        # and the UI limits that control to Vader 4, not Vader 5.
        self.report_rate.setText(f'Report-rate code: {reply[10]} (read only; not a measured rate)')
        self.select_setting()

    def select_setting(self, unused=None):
        name = self.setting.currentData()
        item = SETTINGS[name]
        self.description.setText(item.description)
        self.choice.blockSignals(True)
        self.choice.clear()
        for value, text in item.choices:
            self.choice.addItem(text, value)
        self.choice.setCurrentIndex(-1)
        self.known_supported = False
        if self.snapshot is None:
            self.current.setText('Read the controller before editing.')
        else:
            state = parse_status(self.snapshot)[name]
            value = state['value']
            if not state['supported']:
                self.current.setText('Not advertised by this firmware.')
            elif value not in dict(item.choices):
                self.current.setText(f'Unrecognized saved value: {value}. Editing is disabled.')
            else:
                self.known_supported = True
                self.current.setText('Current: ' + dict(item.choices)[value])
                self.choice.setCurrentIndex(self.choice.findData(value))
        self.choice.blockSignals(False)
        self.update_enabled()

    def update_enabled(self, unused=None):
        enabled = self.available and self.snapshot is not None and self.known_supported
        self.read.setEnabled(self.available)
        self.setting.setEnabled(self.available)
        self.choice.setEnabled(enabled)
        changed = enabled and self.choice.currentIndex() >= 0 and self.choice.currentData() != parse_status(self.snapshot)[self.setting.currentData()]['value']
        self.apply.setEnabled(bool(changed))

    def set_available(self, available):
        self.available = available
        self.update_enabled()

    def clear(self):
        self.snapshot = None
        self.result.clear()
        self.report_rate.setText('Report rate: not read')
        self.select_setting()
