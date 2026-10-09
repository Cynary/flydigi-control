"""Onboard button mapping page, using the shared profile save transaction."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QPushButton, QSlider
from .button_mappings import BUTTONS, RAPID_MODES, read_button, with_button


class ButtonMappingPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.mapping = None
        self.available = False
        self.loading = False
        self.valid_read = False
        layout = QVBoxLayout(self)
        self.back = QPushButton('Back to controller settings');layout.addWidget(self.back)
        title = QLabel('Onboard button mappings');title.setObjectName('title');layout.addWidget(title)
        self.read = QPushButton('Read active profile');layout.addWidget(self.read)
        self.source = QComboBox()
        for i,name in enumerate(BUTTONS):self.source.addItem(name,i)
        self.kind = QComboBox();self.kind.addItem('Single button','button');self.kind.addItem('Rapid fire','rapid_fire')
        self.target = QComboBox()
        for i,name in enumerate(BUTTONS):self.target.addItem(name,i)
        self.activation = QComboBox()
        for value,label in RAPID_MODES:self.activation.addItem(label,value)
        for label,control in [('Physical button',self.source),('Mapping',self.kind),('Output button',self.target),('Rapid-fire trigger',self.activation)]:
            row=QHBoxLayout();row.addWidget(QLabel(label));row.addWidget(control,1);layout.addLayout(row)
        self.frequency_label = QLabel('Rapid fire · 15 presses/s');layout.addWidget(self.frequency_label)
        self.frequency = QSlider(Qt.Orientation.Horizontal)
        self.frequency.setRange(1,30);self.frequency.setValue(15);self.frequency.setProperty('step',1)
        layout.addWidget(self.frequency)
        self.details=QLabel('Read the active profile before editing.');self.details.setWordWrap(True);layout.addWidget(self.details)
        self.save=QPushButton('Save selected button to the controller');layout.addWidget(self.save)
        self.result=QLabel();self.result.setWordWrap(True);layout.addWidget(self.result)
        note=QLabel('Steam Input may bypass onboard mappings while it owns native input.\n'
                    'Fn, Turbo and Home use firmware shortcuts or Steam bindings instead.')
        note.setWordWrap(True);layout.addWidget(note);layout.addStretch()
        self.controls=[self.back,self.read,self.source,self.kind,self.target,self.activation,self.frequency,self.save]
        self.source.currentIndexChanged.connect(self.load_source)
        for control in (self.kind,self.target,self.activation):control.currentIndexChanged.connect(self.validate)
        self.frequency.valueChanged.connect(self.validate)
        self.set_available(False)

    def load(self, value):
        self.mapping=value['mapping'];self.profile=value['profile'];self.load_source()

    def load_source(self, unused=None):
        self.valid_read=False
        if self.mapping is None:
            self.validate();return
        self.loading=True
        try:
            value=read_button(self.mapping,self.source.currentData())
            if value.editable:
                self.kind.setCurrentIndex(self.kind.findData(value.kind))
                self.target.setCurrentIndex(self.target.findData(value.target))
                self.activation.setCurrentIndex(self.activation.findData(value.activation))
                self.frequency.setValue(value.frequency or 15)
                self.valid_read=True
                self.details.setText(f'Profile {self.profile+1}. Only this button’s record will change.')
            else:
                self.details.setText({'macro':'This button has a macro. Open Onboard macros in Controller settings to edit or remove it.',
                    'keyboard_mouse':'This button uses a PC keyboard/mouse mapping. It is preserved unchanged.',
                    'unknown':f'Unrecognized record: {value.raw.hex()}. Editing is disabled.'}[value.kind])
        except ValueError as error:
            self.details.setText(str(error))
        finally:
            self.loading=False
        self.set_available(self.available)

    def edit(self):
        source,target,kind=self.source.currentData(),self.target.currentData(),self.kind.currentData()
        activation=self.activation.currentData() if kind=='rapid_fire' else 0
        frequency=self.frequency.value() if kind=='rapid_fire' else 0
        return lambda mapping:with_button(mapping,source,kind=kind,target=target,activation=activation,frequency=frequency)

    def validate(self,unused=None):
        if self.loading:return
        self.frequency_label.setText(f'Rapid fire · {self.frequency.value()} presses/s')
        enabled=self.available and self.valid_read and self.mapping is not None
        for control in (self.kind,self.target):control.setEnabled(enabled)
        rapid=enabled and self.kind.currentData()=='rapid_fire'
        self.activation.setEnabled(rapid);self.frequency.setEnabled(rapid)
        changed=False
        if enabled:
            try:changed=self.edit()(self.mapping)!=self.mapping
            except ValueError as error:self.result.setText(str(error))
        self.save.setEnabled(changed)

    def set_available(self,available):
        self.available=available
        self.read.setEnabled(available)
        self.source.setEnabled(available and self.mapping is not None)
        self.validate()

    def clear(self):
        self.mapping=None;self.valid_read=False
        self.details.setText('Read the active profile before editing.')
        self.set_available(self.available)
