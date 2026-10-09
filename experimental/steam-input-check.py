#!/usr/bin/env python3
"""Manual Steam Input action check. It observes Qt keys, not raw HID reports."""
import json
import os
from pathlib import Path
import time
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QLabel, QGridLayout, QVBoxLayout, QWidget

names = ['M1', 'M2', 'M3', 'M4', 'C', 'Z', 'LM', 'RM', 'Fn', 'Turbo']
folder = Path(os.environ.get('XDG_STATE_HOME', str(Path.home()/'.local/state')))/'flydigi-control'
folder.mkdir(parents=True, exist_ok=True)
log = (folder/'steam-input-actions.jsonl').open('w', buffering=1)
log.write(json.dumps({'event':'start','time':time.time()})+'\n')
app = QApplication([])
class Check(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Flydigi Steam Input Check')
        self.setStyleSheet('QWidget {background:#17202c;color:#edf2f7;font-size:25px;} QLabel {padding:18px;}')
        layout=QVBoxLayout(self)
        layout.addWidget(QLabel('Steam Input action check'))
        layout.addWidget(QLabel('Press each extra button separately, then release it.\nThis checks mapped keyboard actions reaching the app.'))
        grid=QGridLayout();layout.addLayout(grid);self.labels={};self.seen={}
        for i,name in enumerate(names):
            key=int(Qt.Key.Key_A)+i
            label=QLabel(f'{name}: waiting');grid.addWidget(label,i//5,i%5)
            self.labels[key]=(name,label);self.seen[key]=set()
        self.status=QLabel('Waiting for Steam Input');layout.addWidget(self.status)
    def record(self,event,pressed):
        if event.isAutoRepeat():return
        key=event.key();state='press' if pressed else 'release'
        log.write(json.dumps({'event':state,'time':time.time(),'key':key,'name':QKeySequence(key).toString(),'scan':event.nativeScanCode()})+'\n')
        if key in self.labels:
            name,label=self.labels[key];self.seen[key].add(state)
            label.setText(f'{name}: '+('passed' if len(self.seen[key])==2 else state))
            if len(self.seen[key])==2:label.setStyleSheet('color:#70dfaa;')
        count=sum(len(v)==2 for v in self.seen.values())
        self.status.setText(f'{count}/10 complete — last key: {QKeySequence(key).toString()}')
        if key==int(Qt.Key.Key_Escape) and pressed:self.close()
    def keyPressEvent(self,event):self.record(event,True)
    def keyReleaseEvent(self,event):self.record(event,False)
window=Check();window.showFullScreen();app.exec();log.close()
