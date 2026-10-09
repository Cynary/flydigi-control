"""Controller-friendly editor for the firmware's gyro-to-stick mapping."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QPushButton, QSlider
from .motion_mapping import TARGETS, ACTIVATION, KEYS, read_motion, with_motion


class MotionPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.mapping=None;self.available=False;self.valid_read=False;self.loading=False
        layout=QVBoxLayout(self)
        self.back=QPushButton('Back to controller settings');layout.addWidget(self.back)
        title=QLabel('Onboard motion mapping');title.setObjectName('title');layout.addWidget(title)
        self.read=QPushButton('Read active profile');layout.addWidget(self.read)
        self.fields={}
        for key,label,choices in [('target','Map gyro to',TARGETS),('activation','Activation',ACTIVATION),
                                  ('key','Activation button',KEYS),('second','Second hold button',KEYS)]:
            control=QComboBox()
            for value,text in choices:control.addItem(text,value)
            self.fields[key]=control
            row=QHBoxLayout();row.addWidget(QLabel(label));row.addWidget(control,1);layout.addLayout(row)
            control.currentIndexChanged.connect(self.validate)
        for key,label in [('sensitivity','Sensitivity'),('deadzone','Stick deadzone compensation')]:
            text=QLabel(label)
            slider=QSlider(Qt.Orientation.Horizontal);slider.setRange(0,100);slider.setProperty('step',1)
            slider.valueChanged.connect(lambda value,t=text,l=label:t.setText(f'{l} · {value}'))
            slider.valueChanged.connect(self.validate)
            self.fields[key]=slider
            row=QHBoxLayout();row.addWidget(text);row.addWidget(slider,1);layout.addLayout(row)
        self.details=QLabel('Read the active profile before editing.');self.details.setWordWrap(True);layout.addWidget(self.details)
        self.save=QPushButton('Save motion mapping to the controller');layout.addWidget(self.save)
        self.result=QLabel();self.result.setWordWrap(True);layout.addWidget(self.result)
        note=QLabel('The official app warns that onboard motion mapping reduces report rate.\n'
                    'Steam Input’s gyro bindings are separate and may bypass this mapping.')
        note.setWordWrap(True);layout.addWidget(note);layout.addStretch()
        self.controls=[self.back,self.read,*self.fields.values(),self.save]
        self.set_available(False)

    def load(self,value):
        self.mapping=value['mapping'];self.profile=value['profile'];self.valid_read=False
        self.loading=True
        try:
            current=read_motion(self.mapping)
            for name,control in self.fields.items():
                if isinstance(control,QComboBox):control.setCurrentIndex(control.findData(current[name]))
                else:control.setValue(current[name])
            self.valid_read=True
            self.details.setText(f'Profile {self.profile+1}. Smoothing fields are preserved unchanged.')
        except ValueError as error:
            self.details.setText(str(error))
        finally:
            self.loading=False
        self.set_available(self.available)

    def edit(self):
        values={name:control.currentData() if isinstance(control,QComboBox) else control.value()
                for name,control in self.fields.items()}
        # A disabled second-button control may hold a draft from hold mode.
        # Toggling activation must not accidentally write that draft.
        if values['activation']==0:
            values['second']=read_motion(self.mapping)['second']
        return lambda mapping:with_motion(mapping,**values)

    def validate(self,unused=None):
        if self.loading or not hasattr(self,'save'):return
        enabled=self.available and self.valid_read and self.mapping is not None
        self.fields['target'].setEnabled(enabled)
        active=enabled and self.fields['target'].currentData()!=0
        for name in ('activation','key','sensitivity','deadzone'):self.fields[name].setEnabled(active)
        self.fields['second'].setEnabled(active and self.fields['activation'].currentData()==1)
        changed=False
        if enabled:
            try:
                changed=self.edit()(self.mapping)!=self.mapping
                if unused is not None:self.result.clear()
            except ValueError as error:self.result.setText(str(error))
        self.save.setEnabled(changed)

    def set_available(self,available):
        self.available=available;self.read.setEnabled(available);self.validate()

    def clear(self):
        self.mapping=None;self.valid_read=False
        self.details.setText('Read the active profile before editing.');self.set_available(self.available)
