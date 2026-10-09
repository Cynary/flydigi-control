"""Small on-screen keyboard for controller-only macro naming."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QLabel


class NamePanel(QWidget):
    accepted=Signal(str)
    cancelled=Signal()

    def __init__(self):
        super().__init__()
        self.value='';self.upper=False
        layout=QVBoxLayout(self)
        heading=QLabel('Macro name');heading.setObjectName('title');layout.addWidget(heading)
        self.preview=QLabel();self.preview.setWordWrap(True);layout.addWidget(self.preview)
        self.message=QLabel('Up to 20 UTF-8 bytes. Changes remain a draft until you save the macro.')
        self.message.setWordWrap(True);layout.addWidget(self.message)
        grid=QGridLayout();layout.addLayout(grid)
        self.keys=[]
        for i,char in enumerate('abcdefghijklmnopqrstuvwxyz0123456789-_. '):
            key=QPushButton('Space' if char==' ' else char)
            key.clicked.connect(lambda checked=False,c=char:self.append(c))
            grid.addWidget(key,i//10,i%10);self.keys.append(key)
        row=QHBoxLayout();layout.addLayout(row)
        self.case=QPushButton('Uppercase');self.backspace=QPushButton('Backspace')
        self.clear_button=QPushButton('Clear');self.done=QPushButton('Use name');self.cancel=QPushButton('Cancel')
        for button in (self.case,self.backspace,self.clear_button,self.done,self.cancel):row.addWidget(button)
        self.case.clicked.connect(self.toggle_case)
        self.backspace.clicked.connect(lambda:self.set_value(self.value[:-1]))
        self.clear_button.clicked.connect(lambda:self.set_value(''))
        self.done.clicked.connect(lambda:self.accepted.emit(self.value))
        self.cancel.clicked.connect(self.cancelled.emit)
        self.controls=[*self.keys,self.case,self.backspace,self.clear_button,self.done,self.cancel]
        layout.addStretch();self.set_value('')

    def set_value(self,value):
        self.value=value
        self.preview.setText(f'{value or "(empty)"}  ·  {len(value.encode("utf-8"))}/20 bytes')
        self.done.setEnabled(bool(value.strip()) and len(value.encode('utf-8'))<=20)

    def append(self,char):
        char=char.upper() if self.upper else char
        if len((self.value+char).encode('utf-8'))<=20:self.set_value(self.value+char)

    def toggle_case(self):
        self.upper=not self.upper
        for key in self.keys[:26]:key.setText(key.text().upper() if self.upper else key.text().lower())
        self.case.setText('Lowercase' if self.upper else 'Uppercase')
