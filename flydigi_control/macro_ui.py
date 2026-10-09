"""Controller-operated editor for the format-3.2 onboard macro bank."""
import os
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QComboBox, QSlider, QVBoxLayout, QHBoxLayout
from .button_mappings import BUTTONS
from .macro_bank import Action, Macro, decode_bank, replace_macro, validate_execution
from .persistence import _mapping_version, apply_macro, remove_saved_macro
from .transport import ConfigurationDevice

DIRECTIONS = ('Center', 'Up', 'Up-right', 'Right', 'Down-right', 'Down', 'Down-left', 'Left', 'Up-left')


class MacroOperation(QThread):
    result = Signal(bool, str)
    values = Signal(object)

    def __init__(self, path, snapshot=None, macro=None, parent=None, remove_key=None):
        super().__init__(parent)
        self.path, self.snapshot, self.macro = path, snapshot, macro
        self.remove_key = remove_key

    def run(self):
        try:
            with ConfigurationDevice(self.path) as device:
                if self.remove_key is not None:
                    folder = Path(os.environ.get('XDG_STATE_HOME', str(Path.home()/'.local/state'))) / 'flydigi-control'
                    remove_saved_macro(device,self.snapshot['mapping'],self.snapshot['macros'],self.remove_key,
                                       folder,expected_profile=self.snapshot['profile'])
                if self.macro is not None:
                    folder = Path(os.environ.get('XDG_STATE_HOME', str(Path.home()/'.local/state'))) / 'flydigi-control'
                    apply_macro(device, self.snapshot['mapping'], self.snapshot['macros'], self.macro,
                                folder, expected_profile=self.snapshot['profile'])
                device.info()
                state = device.profile_state()
                mapping = device.read_mapping(state[0])
                if _mapping_version(mapping) != state[1][state[0]] or mapping[0] != 2:
                    raise ValueError('Macro editor requires a current format-3.2 profile')
                macros = device.read_macros(state[0])
                decode_bank(macros)
                if device.profile_state() != state:
                    raise RuntimeError('Profile changed during read; try again')
                self.values.emit(dict(mapping=mapping, macros=macros, profile=state[0]))
            self.result.emit(True, 'Macro removed; button restored.' if self.remove_key is not None else
                             'Macro saved and read back.' if self.macro else 'Macros read from the active profile.')
        except (OSError, ValueError, RuntimeError) as error:
            self.result.emit(False, str(error))


class MacroRecording(QThread):
    result=Signal(bool,str)
    actions=Signal(object)
    progress=Signal(object)

    def __init__(self,path,max_actions,parent=None):
        super().__init__(parent)
        self.path,self.max_actions=path,max_actions

    def run(self):
        from .macro_record import record
        try:
            actions=record(self.path,15,self.max_actions,self.progress.emit)
            if not actions:raise ValueError('No actions recorded; the draft is unchanged')
            self.actions.emit(actions)
            self.result.emit(True,'Recording added to the draft. Review it, then Save to apply.')
        except (OSError,ValueError,RuntimeError) as error:
            self.result.emit(False,str(error))


class MacroPanel(QWidget):
    delete_requested=Signal()
    def __init__(self):
        super().__init__()
        self.snapshot = None
        self.available = False
        self.loading = False
        self.actions = []
        self.name = ''
        self.delete_pending = False
        layout = QVBoxLayout(self)
        heading = QHBoxLayout()
        title = QLabel('Onboard macros'); title.setObjectName('title'); heading.addWidget(title)
        self.back = QPushButton('Back to settings'); heading.addWidget(self.back); layout.addLayout(heading)
        row = QHBoxLayout()
        self.read = QPushButton('Read active profile'); row.addWidget(self.read)
        self.source = QComboBox(); self.source.addItems(BUTTONS); row.addWidget(self.source)
        layout.addLayout(row)
        self.source.currentIndexChanged.connect(self.load_macro)
        self.mode = QComboBox()
        for value, label in ((0,'Disabled'), (1,'Run once'), (2,'Repeat while held'), (3,'Press to start / press to stop')):
            self.mode.addItem(label, value)
        self.mode.currentIndexChanged.connect(self.validate)
        mode_row=QHBoxLayout();mode_row.addWidget(self.mode,2)
        self.record=QPushButton('Record 15 seconds');self.rename=QPushButton('Rename')
        mode_row.addWidget(self.record);mode_row.addWidget(self.rename);layout.addLayout(mode_row)
        interval_row = QHBoxLayout()
        self.interval_label = QLabel('Repeat delay · 100 ms'); interval_row.addWidget(self.interval_label)
        self.interval = QSlider(Qt.Orientation.Horizontal)
        self.interval.setRange(0,65535); self.interval.setValue(100); self.interval.setProperty('step',10)
        self.interval.valueChanged.connect(lambda n:self.interval_label.setText(f'Repeat delay · {n} ms'))
        self.interval.valueChanged.connect(self.validate); interval_row.addWidget(self.interval); layout.addLayout(interval_row)
        self.action = QComboBox(); self.action.currentIndexChanged.connect(self.load_action); layout.addWidget(self.action)
        row = QHBoxLayout()
        self.event = QComboBox()
        for value,label in ((1,'Press button'),(0,'Release button'),(2,'Left stick'),(3,'Right stick')):
            self.event.addItem(label,value)
        self.event.currentIndexChanged.connect(self.event_changed); row.addWidget(self.event)
        self.target = QComboBox(); row.addWidget(self.target); layout.addLayout(row)
        delay_row = QHBoxLayout()
        self.delay_label = QLabel('Action delay · 0 ms'); delay_row.addWidget(self.delay_label)
        self.delay = QSlider(Qt.Orientation.Horizontal); self.delay.setRange(0,65535); self.delay.setProperty('step',10)
        self.delay.valueChanged.connect(lambda n:self.delay_label.setText(f'Action delay · {n} ms'))
        delay_row.addWidget(self.delay); layout.addLayout(delay_row)
        row = QHBoxLayout()
        self.add = QPushButton('Insert action'); self.update = QPushButton('Replace action'); self.remove = QPushButton('Remove action')
        for button in (self.add,self.update,self.remove): row.addWidget(button)
        layout.addLayout(row)
        self.add.clicked.connect(lambda:self.change_action('add'))
        self.update.clicked.connect(lambda:self.change_action('update'))
        self.remove.clicked.connect(lambda:self.change_action('remove'))
        row = QHBoxLayout()
        self.earlier = QPushButton('Move action earlier'); self.later = QPushButton('Move action later')
        self.earlier.clicked.connect(lambda:self.move_action(-1)); self.later.clicked.connect(lambda:self.move_action(1))
        row.addWidget(self.earlier); row.addWidget(self.later); layout.addLayout(row)
        self.summary = QLabel('Read the controller before editing.'); self.summary.setWordWrap(True); layout.addWidget(self.summary)
        save_row=QHBoxLayout();layout.addLayout(save_row)
        self.save = QPushButton('Save macro to the controller');save_row.addWidget(self.save)
        self.delete=QPushButton('Remove saved macro');save_row.addWidget(self.delete)
        self.delete.clicked.connect(self.confirm_delete)
        self.result = QLabel(''); self.result.setWordWrap(True); layout.addWidget(self.result)
        note = QLabel('Actions run in order after their delay. Pair each press with a release; return sticks to Center.\n'
                      'This changes onboard behavior; Steam Input may bypass it. Reconnect persistence still needs testing.')
        note.setWordWrap(True); layout.addWidget(note); layout.addStretch()
        self.controls = [self.back,self.read,self.source,self.mode,self.interval,self.action,self.event,self.target,
                         self.delay,self.add,self.update,self.remove,self.earlier,self.later,self.record,self.rename,self.delete,self.save]
        self.event_changed(); self.set_available(False)

    def event_changed(self, unused=None):
        self.target.clear()
        self.target.addItems(BUTTONS if self.event.currentData() in (0,1) else DIRECTIONS)

    def load(self, snapshot):
        decode_bank(snapshot['macros'])
        self.snapshot = snapshot
        self.load_macro()

    def load_macro(self, unused=None):
        self.delete_pending=False;self.delete.setText('Remove saved macro')
        self.actions = []
        if self.snapshot is None:
            self.refresh_actions(); return
        bank = decode_bank(self.snapshot['macros'])
        current = next((r.macro for r in bank.records if r.macro.key == self.source.currentIndex()), None)
        self.loading = True
        label = {14: 'L3', 15: 'R3'}.get(self.source.currentIndex(), BUTTONS[self.source.currentIndex()])
        self.name = current.name if current else label + ' macro'
        self.mode.setCurrentIndex(self.mode.findData(current.mode if current else 1))
        self.interval.setValue(current.interval_ms if current else 100)
        self.actions = list(current.actions) if current else []
        self.loading = False
        self.refresh_actions()

    def macro(self, actions=None):
        return Macro(self.source.currentIndex(),self.mode.currentData(),self.interval.value(),self.name,
                     tuple(self.actions if actions is None else actions))

    def describe(self, action):
        if action.event in (0,1) and 0 <= action.key < len(BUTTONS):
            what = ('Press ' if action.event else 'Release ') + BUTTONS[action.key]
        elif action.event in (2,3) and 160 <= action.key <= 168:
            what = ('Left' if action.event==2 else 'Right')+' stick '+DIRECTIONS[action.key-160]
        else:
            what = f'Unknown event {action.event}, value {action.key}'
        return f'+{action.delay_ms} ms: {what}'

    def refresh_actions(self, selected=0):
        self.action.blockSignals(True); self.action.clear()
        for index, action in enumerate(self.actions): self.action.addItem(f'{index+1}. {self.describe(action)}')
        self.action.setCurrentIndex(min(max(0,selected),len(self.actions)-1))
        self.action.blockSignals(False)
        self.load_action(); self.set_available(self.available)

    def load_action(self, unused=None):
        index = self.action.currentIndex()
        if index < 0: return
        action = self.actions[index]
        event_index = self.event.findData(action.event)
        self.event.setCurrentIndex(event_index)
        self.event_changed()
        target = action.key-(160 if action.event in (2,3) else 0)
        self.target.setCurrentIndex(target if 0 <= target < self.target.count() else -1)
        self.delay.setValue(action.delay_ms)
        self.validate()

    def change_action(self, kind):
        if self.snapshot is None or not self.available: return
        actions = list(self.actions); index = self.action.currentIndex()
        if kind == 'remove':
            if index < 0: return
            del actions[index]
        else:
            event = self.event.currentData(); target = self.target.currentIndex()
            if event is None or target < 0:
                self.result.setText('Choose an action and its button or direction.'); return
            action = Action(self.delay.value(),target+(160 if event in (2,3) else 0),event)
            if kind == 'add':
                index += 1; actions.insert(index,action)
            elif index >= 0: actions[index] = action
            else: return
        try:
            if actions: replace_macro(self.snapshot['macros'],self.macro(actions))
        except ValueError as error:
            self.result.setText(str(error)); return
        self.actions = actions; self.result.setText('Draft updated; nothing written yet.')
        self.refresh_actions(index)

    def move_action(self, delta):
        index = self.action.currentIndex(); other = index+delta
        if self.available and 0 <= index < len(self.actions) and 0 <= other < len(self.actions):
            self.actions[index],self.actions[other] = self.actions[other],self.actions[index]
            self.refresh_actions(other)

    def validate(self, unused=None):
        if self.loading: return
        valid = self.snapshot is not None
        if valid:
            try:
                replace_macro(self.snapshot['macros'],self.macro())
                validate_execution(self.macro())
                self.summary.setText(f'Profile {self.snapshot["profile"]+1} · {self.name} · '
                                     f'{len(self.actions)} actions · {sum(a.delay_ms for a in self.actions)} ms per run')
            except ValueError as error:
                valid = False; self.summary.setText(str(error))
        self.save.setEnabled(self.available and valid)
        self.record.setEnabled(self.available and self.recording_capacity()>=2)

    def set_available(self, available):
        self.available = available; self.read.setEnabled(available)
        for control in self.controls[2:-1]: control.setEnabled(available and self.snapshot is not None)
        for control in (self.action,self.update,self.remove,self.earlier,self.later):
            control.setEnabled(available and self.snapshot is not None and bool(self.actions))
        saved=self.snapshot is not None and any(r.macro.key==self.source.currentIndex()
                 for r in decode_bank(self.snapshot['macros']).records)
        self.delete.setEnabled(available and saved)
        self.record.setEnabled(available and self.snapshot is not None and self.recording_capacity()>=2)
        self.validate()

    def recording_capacity(self):
        if self.snapshot is None or self.mode.currentData() is None or len(self.name.encode('utf-8'))>20:return 0
        bank=decode_bank(self.snapshot['macros'])
        if len(bank.records)>=10 and not any(r.macro.key==self.source.currentIndex() for r in bank.records):return 0
        return 256-sum(len(r.macro.actions) for r in bank.records if r.macro.key!=self.source.currentIndex())

    def set_recording(self, actions):
        if self.snapshot is None:return
        replace_macro(self.snapshot['macros'],self.macro(actions))
        self.actions=list(actions);self.refresh_actions()

    def confirm_delete(self):
        if not self.available or self.snapshot is None:return
        if not self.delete_pending:
            self.delete_pending=True
            self.delete.setText('Confirm removal')
            self.result.setText('This removes the saved macro and restores this button’s default output. Press Confirm removal to apply.')
        else:
            self.delete_pending=False;self.delete.setText('Remove saved macro')
            self.delete_requested.emit()

    def clear(self):
        self.snapshot = None; self.actions = []; self.action.clear()
        self.delete_pending=False;self.delete.setText('Remove saved macro')
        self.summary.setText('Read the controller before editing.'); self.set_available(self.available)
