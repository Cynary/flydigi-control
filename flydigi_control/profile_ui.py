"""Stored trigger and grip settings, sharing the guarded profile transaction."""
import os
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QComboBox, QSlider, QVBoxLayout, QGridLayout, QHBoxLayout
from .profile_controls import read_grip, with_grip, read_trigger, with_trigger
from .persistence import apply_mapping_edit
from .transport import ConfigurationDevice


class ProfileOperation(QThread):
    result = Signal(bool,str)
    values = Signal(object)

    def __init__(self,path,mapping=None,edit=None,parent=None,profile=None):
        super().__init__(parent)
        self.path,self.mapping,self.edit = path,mapping,edit
        self.profile=profile

    def run(self):
        try:
            with ConfigurationDevice(self.path) as device:
                if self.edit is not None:
                    folder = Path(os.environ.get('XDG_STATE_HOME',str(Path.home()/'.local/state'))) / 'flydigi-control'
                    apply_mapping_edit(device,self.mapping,self.edit,folder,expected_profile=self.profile)
                device.info()
                state = device.profile_state()
                mapping = device.read_mapping(state[0])
                if device.profile_state() != state:
                    raise RuntimeError('Profile changed during read; try again')
                self.values.emit(dict(mapping=mapping,profile=state[0]))
            self.result.emit(True,'Profile saved and verified.' if self.edit is not None else 'Settings read from the active profile.')
        except (OSError,ValueError,RuntimeError) as error:
            self.result.emit(False,str(error))


class ProfilePanel(QWidget):
    def __init__(self,kind):
        super().__init__()
        self.kind = kind
        self.mapping = None
        self.available = False
        self.loading = False
        self.valid_read = False
        layout = QVBoxLayout(self)
        self.back = QPushButton('Back to controller settings')
        layout.addWidget(self.back)
        title = QLabel('Trigger travel and vibration' if kind == 'trigger' else 'Saved grip vibration')
        title.setObjectName('title');layout.addWidget(title)
        selection=QHBoxLayout()
        self.read = QPushButton('Read active profile')
        selection.addWidget(self.read)
        self.side = QComboBox();self.side.addItems(['Left','Right'])
        self.side.currentIndexChanged.connect(self.load_side)
        selection.addWidget(self.side)
        layout.addLayout(selection)
        self.fields = {}
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setContentsMargins(0,0,0,0)
        fields = ([('start','Travel starts at',0,255),('end','Full output at',0,255),
                   ('enabled','Trigger vibration — both sides',None,None),
                   ('minimum','Minimum amplitude %',1,100),('maximum','Maximum amplitude %',1,100),
                   ('threshold','Suppress vibration below',1,255),('strength','Vibration strength %',1,100)]
                  if kind == 'trigger' else
                  [('master_enabled','All grip vibration',None,None),('enabled','Selected grip motor',None,None),
                   ('strength','Vibration strength %',1,100)])
        for index,(key,name,low,high) in enumerate(fields):
            label = QLabel(name)
            if low is None:
                control = QComboBox();control.addItems(['Off','On'])
                control.setMinimumHeight(54)
                control.currentIndexChanged.connect(self.validate)
            else:
                control = QSlider(Qt.Orientation.Horizontal)
                control.setRange(low,high);control.setSingleStep(1);control.setProperty('step',1)
                control.valueChanged.connect(lambda value,label=label,name=name: label.setText(f'{name} · {value}'))
                control.valueChanged.connect(self.validate)
                label.setText(f'{name} · {low}')
            grid.addWidget(label,index,0);grid.addWidget(control,index,1)
            self.fields[key]=control
        grid_widget.setMinimumHeight(sum(56 if lo is None else 40 for _,_,lo,_ in fields)+6*(len(fields)-1))
        layout.addWidget(grid_widget)
        self.details=QLabel('Read the controller before editing.');self.details.setWordWrap(True)
        layout.addWidget(self.details)
        self.save=QPushButton('Save selected side to the controller');layout.addWidget(self.save)
        self.result=QLabel('');self.result.setWordWrap(True);layout.addWidget(self.result)
        note=QLabel('Saved onboard; Steam Input may bypass these settings. Motor tests are separate.')
        note.setWordWrap(True);layout.addWidget(note)
        layout.addStretch()
        self.controls=[self.back,self.read,self.side,*self.fields.values(),self.save]
        self.set_available(False)

    def values(self):
        return {key:(bool(control.currentIndex()) if isinstance(control,QComboBox) else control.value())
                for key,control in self.fields.items()}

    def edit(self):
        values,side=self.values(),self.side.currentIndex()
        function=with_trigger if self.kind=='trigger' else with_grip
        return lambda mapping:function(mapping,side,**values)

    def load(self,value):
        self.mapping=value['mapping'];self.profile=value['profile']
        self.load_side()

    def load_side(self,unused=None):
        self.valid_read=False
        if self.mapping is None:
            self.validate();return
        try:
            values=(read_trigger if self.kind=='trigger' else read_grip)(self.mapping,self.side.currentIndex())
            # Never silently clamp an unknown saved value to the UI range.
            for key,control in self.fields.items():
                if isinstance(control,QSlider) and not control.minimum()<=values[key]<=control.maximum():
                    raise ValueError(f'Unknown saved {key}: {values[key]}; no settings were changed')
            self.loading=True
            for key,control in self.fields.items():
                if isinstance(control,QComboBox):control.setCurrentIndex(int(values[key]))
                else:control.setValue(values[key])
            self.valid_read=True
            detail=(f'Preserved motor amplitude range: {values["minimum"]}–{values["maximum"]} (0–255).' if self.kind=='grip' else
                    'Travel uses 0–255. The enable switch affects both triggers; other fields affect the selected side.')
            self.details.setText(f'Profile {self.profile+1}. '+detail)
        except ValueError as error:
            self.details.setText(str(error))
        finally:
            self.loading=False
        self.set_available(self.available)

    def validate(self,unused=None):
        if self.loading:return
        valid=self.valid_read and self.mapping is not None
        if valid:
            try:self.edit()(self.mapping)
            except ValueError as error:
                self.result.setText(str(error));valid=False
        self.save.setEnabled(self.available and valid)

    def set_available(self,available):
        self.available=available
        self.read.setEnabled(available)
        self.side.setEnabled(available and self.mapping is not None)
        for control in self.fields.values():control.setEnabled(available and self.valid_read)
        self.validate()

    def clear(self):
        self.mapping=None;self.valid_read=False
        self.details.setText('Read the controller before editing.')
        self.set_available(self.available)
