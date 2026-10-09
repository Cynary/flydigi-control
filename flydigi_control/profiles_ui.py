"""Four PC profiles, verified backups and explicit profile restoration."""
import os
from pathlib import Path
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QComboBox, QVBoxLayout, QHBoxLayout
from .persistence_check import snapshot
from .persistence import _backup
from .profiles import select_profile
from .transport import ConfigurationDevice
from . import profile_restore, factory_profile


class ProfileSelectionOperation(QThread):
    values = Signal(object)
    result = Signal(bool, str)

    def __init__(self, path, previous=None, target=None, backup_only=False, parent=None, restore_source=None):
        super().__init__(parent)
        self.path, self.previous, self.target, self.backup_only = path, previous, target, backup_only
        self.restore_source = restore_source

    def run(self):
        try:
            folder = Path(os.environ.get('XDG_STATE_HOME', str(Path.home()/'.local/state'))) / 'flydigi-control'
            with ConfigurationDevice(self.path) as device:
                if self.restore_source is not None:
                    data, backup = profile_restore.restore(device, self.restore_source, self.previous, folder)
                    message = f'Profile restored and saved. Previous settings backup: {backup}'
                elif self.target is not None:
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
    restore_requested = Signal()
    factory_requested = Signal()

    def __init__(self):
        super().__init__()
        self.snapshot = None; self.available = False; self.pending = False
        self.restore_pending = False; self.factory_pending = False; self.sources = {}
        self.folder = Path(os.environ.get('XDG_STATE_HOME', str(Path.home()/'.local/state'))) / 'flydigi-control'
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
        row = QHBoxLayout(); layout.addLayout(row)
        self.backups = QComboBox(); row.addWidget(self.backups, 2)
        self.refresh = QPushButton('Find backups'); row.addWidget(self.refresh)
        self.refresh.clicked.connect(self.refresh_backups)
        self.backups.currentIndexChanged.connect(self.review_restore)
        self.preview = QLabel('Choose a backup to review profile restoration.'); self.preview.setWordWrap(True); layout.addWidget(self.preview)
        self.restore = QPushButton('Restore profile from backup'); layout.addWidget(self.restore)
        self.restore.clicked.connect(self.confirm_restore)
        self.factory = QPushButton('Restore active profile defaults'); layout.addWidget(self.factory)
        self.factory.clicked.connect(self.confirm_factory)
        self.result = QLabel(); self.result.setWordWrap(True); layout.addWidget(self.result)
        note = QLabel('Switching or restoring can change buttons, LEDs and stick behavior immediately.\n'
                      'Both discard unsaved editor drafts and back up the current controller settings first.\n'
                      'Selecting uses an existing profile. Restoring replaces its contents and saves them onboard.')
        note.setWordWrap(True); layout.addWidget(note); layout.addStretch()
        self.controls = [self.back, self.read, self.target, self.select, self.backup,self.backups,self.refresh,self.restore,self.factory]
        self.set_available(False)

    def load(self, value):
        self.snapshot = value
        self.details.setText(f'Active: Profile {value["profile"]+1} · {value["identity"]["model"]} · firmware {value["identity"]["firmware"]}')
        self.target.setCurrentIndex(value['profile']); self.reset_confirmation()
        self.review_restore()

    def set_available(self, available):
        self.available = available; self.read.setEnabled(available)
        ready = available and self.snapshot is not None
        self.target.setEnabled(ready); self.backup.setEnabled(available)
        self.select.setEnabled(ready and self.target.currentIndex() != self.snapshot['profile'])
        self.refresh.setEnabled(available); self.backups.setEnabled(available)
        compatible = False
        if ready and self.backups.currentData() in self.sources:
            try:
                profile_restore.preview(self.restore_source(), self.snapshot)
                compatible = True
            except ValueError: pass
        self.restore.setEnabled(compatible)
        factory_ready = False
        if ready:
            try:
                factory_profile.source_for(self.snapshot)
                factory_ready = True
            except (OSError, ValueError): pass
        self.factory.setEnabled(factory_ready)
        if not available:self.cancel_confirmations()

    def cancel_confirmations(self):
        self.pending = False; self.factory_pending = False; self.restore_pending = False
        self.factory.setText('Restore active profile defaults')
        self.restore.setText('Restore profile from backup')
        self.select.setText('Use selected profile')

    def reset_confirmation(self, unused=None):
        self.cancel_confirmations(); self.set_available(self.available)

    def hideEvent(self, event):
        self.cancel_confirmations()
        super().hideEvent(event)

    def confirm(self):
        if not self.available or self.snapshot is None or self.target.currentIndex() == self.snapshot['profile']: return
        if not self.pending:
            self.cancel_confirmations()
            self.pending = True; self.select.setText('Confirm profile switch')
            self.result.setText('Save any editor drafts first. Press Confirm to back up the current settings and switch.')
        else:
            self.pending = False; self.requested.emit()

    def clear(self):
        self.snapshot = None; self.reset_confirmation()
        self.details.setText('Read the controller to see its active PC profile.')
        self.review_restore()

    def restore_source(self):
        return self.sources.get(self.backups.currentData())

    def refresh_backups(self):
        if not self.available:return
        from datetime import datetime
        self.sources = {}; self.backups.clear(); skipped = 0
        for path in sorted(self.folder.glob('*.json'), key=lambda p:p.name):
            try:
                data = profile_restore.read_backup(path)
                if type(data.get('profile')) is not int or not 0 <= data['profile'] <= 3:
                    raise ValueError('Invalid profile')
                stamp = datetime.fromtimestamp(path.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
                self.sources[path.name] = data
                self.backups.addItem(f'{stamp} · Profile {data["profile"]+1} · {path.stem[-6:]}', path.name)
            except (OSError, ValueError):skipped += 1
        self.review_restore()
        self.result.setText(f'{len(self.sources)} profile {"backup" if len(self.sources)==1 else "backups"} found; {skipped} other or unreadable files skipped.')

    def review_restore(self, unused=None):
        self.factory_pending = False; self.factory.setText('Restore active profile defaults')
        self.restore_pending = False; self.restore.setText('Restore profile from backup')
        if self.snapshot is None or self.restore_source() is None:
            self.preview.setText('Read the active profile and choose a backup to review restoration.')
        else:
            try:
                changed = profile_restore.preview(self.restore_source(), self.snapshot)
                labels = {'mapping':'Mappings and analog settings','lighting':'Lighting','macros':'Macros'}
                parts = [f'{labels[key]}: {"changed" if count else "unchanged"}' for key,count in changed.items()]
                self.preview.setText(' · '.join(parts)+'\nRestores this profile’s contents only. Global settings and Steam ownership stay as they are.')
            except ValueError as error:self.preview.setText(str(error))
        self.set_available(self.available)

    def confirm_restore(self):
        if not self.restore.isEnabled():return
        if not self.restore_pending:
            self.cancel_confirmations()
            self.restore_pending = True; self.restore.setText('Confirm restore and save')
            self.result.setText('Use only a backup from this same controller. This replaces the active profile and discards editor drafts; current contents are backed up first.')
        else:
            self.restore_pending = False; self.restore_requested.emit()

    def confirm_factory(self):
        if not self.factory.isEnabled():return
        if not self.factory_pending:
            try:
                profile_restore.preview(factory_profile.source_for(self.snapshot),self.snapshot)
            except (OSError,ValueError) as error:
                self.result.setText(str(error));return
            self.cancel_confirmations()
            self.factory_pending = True; self.factory.setText('Confirm reset and save')
            self.result.setText(f'Reset Profile {self.snapshot["profile"]+1}: restore default buttons, sticks, triggers, motion and lighting; clear its macros. '
                                'Current settings are backed up first. Global settings and the other profiles are not reset.')
        else:
            self.factory_pending = False; self.factory_requested.emit()
