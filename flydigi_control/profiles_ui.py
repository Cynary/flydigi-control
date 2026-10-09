"""Four PC profiles; no factory reset or implicit saving of editor drafts."""
import os
from pathlib import Path
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QComboBox, QVBoxLayout, QHBoxLayout
from .persistence_check import snapshot
from .persistence import _backup
from .profiles import select_profile
from .transport import ConfigurationDevice


class ProfileSelectionOperation(QThread):
    values = Signal(object)
    result = Signal(bool, str)

    def __init__(self, path, previous=None, target=None, backup_only=False, parent=None):
        super().__init__(parent)
        self.path, self.previous, self.target, self.backup_only = path, previous, target, backup_only

    def run(self):
        try:
            folder = Path(os.environ.get('XDG_STATE_HOME', str(Path.home()/'.local/state'))) / 'flydigi-control'
            with ConfigurationDevice(self.path) as device:
                if self.target is not None:
                    data, backup = select_profile(device, self.previous, self.target, folder)
                    message = f'Profile {data["profile"]+1} selected. Previous profile backup: {backup}'
                else:
                    data = snapshot(device)
                    message = f'Backup: {_backup(folder, data)}' if self.backup_only else 'Active profile read; no settings changed.'
                self.values.emit(data)
            self.result.emit(True, message)
        except (OSError, ValueError, RuntimeError) as error:
            self.result.emit(False, str(error))


class ProfileSelectionPanel(QWidget):
    requested = Signal()

    def __init__(self):
        super().__init__()
        self.snapshot = None; self.available = False; self.pending = False
        layout = QVBoxLayout(self); heading = QHBoxLayout(); layout.addLayout(heading)
        title = QLabel('Onboard profiles'); title.setObjectName('title'); heading.addWidget(title)
        self.back = QPushButton('Back to settings'); heading.addWidget(self.back)
        self.read = QPushButton('Read active profile'); layout.addWidget(self.read)
        self.details = QLabel('Read the controller to see its active PC profile.'); self.details.setWordWrap(True); layout.addWidget(self.details)
        self.target = QComboBox(); self.target.addItems([f'Profile {i+1}' for i in range(4)]); layout.addWidget(self.target)
        self.target.currentIndexChanged.connect(self.reset_confirmation)
        self.select = QPushButton('Use selected profile'); layout.addWidget(self.select)
        self.select.clicked.connect(self.confirm)
        self.backup = QPushButton('Back up active profile to PC'); layout.addWidget(self.backup)
        self.result = QLabel(); self.result.setWordWrap(True); layout.addWidget(self.result)
        note = QLabel('Switching can change buttons, LEDs and stick behavior immediately.\n'
                      'Unsaved editor drafts are discarded. The current controller settings are backed up first.\n'
                      'This selects existing settings; it does not save or reset a profile. Fn shortcuts are configured separately.')
        note.setWordWrap(True); layout.addWidget(note); layout.addStretch()
        self.controls = [self.back, self.read, self.target, self.select, self.backup]
        self.set_available(False)

    def load(self, value):
        self.snapshot = value
        self.details.setText(f'Active: Profile {value["profile"]+1} · {value["identity"]["model"]} · firmware {value["identity"]["firmware"]}')
        self.target.setCurrentIndex(value['profile']); self.reset_confirmation()

    def set_available(self, available):
        self.available = available; self.read.setEnabled(available)
        ready = available and self.snapshot is not None
        self.target.setEnabled(ready); self.backup.setEnabled(available)
        self.select.setEnabled(ready and self.target.currentIndex() != self.snapshot['profile'])

    def reset_confirmation(self, unused=None):
        self.pending = False; self.select.setText('Use selected profile'); self.set_available(self.available)

    def confirm(self):
        if not self.available or self.snapshot is None or self.target.currentIndex() == self.snapshot['profile']: return
        if not self.pending:
            self.pending = True; self.select.setText('Confirm profile switch')
            self.result.setText('Save any editor drafts first. Press Confirm to back up the current settings and switch.')
        else:
            self.pending = False; self.requested.emit()

    def clear(self):
        self.snapshot = None; self.reset_confirmation()
        self.details.setText('Read the controller to see its active PC profile.')
