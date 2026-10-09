"""Controller-friendly PC library; hardware writes remain in the macro editor."""
from dataclasses import replace
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox
from . import macro_library as library
from .button_mappings import BUTTONS
from .macro_bank import replace_macro


class MacroLibraryPanel(QWidget):
    draft_loaded = Signal()

    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.folder = library.library_directory()
        self.pending_delete = None
        self.busy = False
        layout = QVBoxLayout(self)
        heading = QHBoxLayout(); layout.addLayout(heading)
        title = QLabel('PC macro library'); title.setObjectName('title'); heading.addWidget(title)
        self.back = QPushButton('Back to macro editor'); heading.addWidget(self.back)
        self.location = QLabel(str(self.folder)); self.location.setWordWrap(True); layout.addWidget(self.location)
        self.items = QComboBox(); layout.addWidget(self.items)
        self.items.currentIndexChanged.connect(self.selected)
        self.details = QLabel(); self.details.setWordWrap(True); layout.addWidget(self.details)
        self.refresh = QPushButton('Refresh library'); layout.addWidget(self.refresh)
        self.save = QPushButton('Save editor draft as a new PC copy'); layout.addWidget(self.save)
        self.load = QPushButton('Load into the selected button’s draft'); layout.addWidget(self.load)
        self.delete = QPushButton('Delete PC copy'); layout.addWidget(self.delete)
        self.imports = QComboBox(); layout.addWidget(self.imports)
        self.import_vendor = QPushButton('Import selected Space Station .dat'); layout.addWidget(self.import_vendor)
        self.result = QLabel(); self.result.setWordWrap(True); layout.addWidget(self.result)
        note = QLabel('Loading changes the editor draft only. Review it and choose Save macro to the controller to apply.\n'
                      'Copy JSON files here to share macros. For Space Station macros, put .dat files in the imports subfolder and refresh.')
        note.setWordWrap(True); layout.addWidget(note); layout.addStretch()
        self.controls = [self.back, self.items, self.refresh, self.save, self.load, self.delete, self.imports, self.import_vendor]
        self.refresh.clicked.connect(self.reload)
        self.save.clicked.connect(self.save_draft)
        self.load.clicked.connect(self.load_draft)
        self.delete.clicked.connect(self.delete_copy)
        self.import_vendor.clicked.connect(self.import_copy)
        self.imports.currentIndexChanged.connect(lambda unused:self.set_busy(self.busy))

    def set_busy(self, busy):
        self.busy = busy
        self.items.setEnabled(not busy); self.refresh.setEnabled(not busy)
        self.save.setEnabled(not busy and self.editor.snapshot is not None and bool(self.editor.actions))
        self.load.setEnabled(not busy and self.editor.snapshot is not None and self.items.currentData() is not None)
        self.delete.setEnabled(not busy and self.items.currentData() is not None)
        self.imports.setEnabled(not busy)
        self.import_vendor.setEnabled(not busy and self.imports.currentData() is not None)

    def reload(self, selected=None):
        if self.busy: return
        try:
            records, errors = library.entries(self.folder)
            old = selected if isinstance(selected, str) else self.items.currentData()
            self.items.blockSignals(True); self.items.clear()
            for filename, macro in records:
                self.items.addItem(f'{macro.name} · {len(macro.actions)} actions · {filename[:8]}', filename)
            if old is not None and self.items.findData(old) >= 0:
                self.items.setCurrentIndex(self.items.findData(old))
            self.items.blockSignals(False)
            self.imports.clear()
            for path in sorted((self.folder/'imports').glob('*.dat')):
                if path.name.lower() != 'index.dat' and path.is_file() and not path.is_symlink():
                    self.imports.addItem(path.name, path.name)
            self.selected()
            self.result.setText('\n'.join(errors[:3]) if errors else
                                f'{len(records)} {"macro" if len(records) == 1 else "macros"} on this PC.')
        except OSError as error:
            self.result.setText(str(error))

    def selected(self, unused=None):
        self.pending_delete = None; self.delete.setText('Delete PC copy')
        filename = self.items.currentData()
        if filename is None:
            self.details.setText('Save a completed editor draft to start a library.')
        else:
            try:
                macro = library.load(self.folder, filename)
                target = (f'Load target: {BUTTONS[self.editor.source.currentIndex()]}. '
                          'The original button assignment will not replace this target.'
                          if self.editor.snapshot is not None else 'Read the active controller profile before loading a draft.')
                self.details.setText(f'{macro.name} · {sum(a.delay_ms for a in macro.actions)} ms · '
                                     f'repeat delay {macro.interval_ms} ms\n{target}')
            except (OSError, ValueError) as error:
                self.details.setText(str(error))
        self.set_busy(self.busy)

    def save_draft(self):
        if self.busy or self.editor.snapshot is None: return
        try:
            filename = library.save_copy(self.folder, self.editor.macro())
            self.reload(filename)
            self.result.setText('PC copy saved. The controller was not changed.')
        except (OSError, ValueError) as error:
            self.result.setText(str(error))

    def load_draft(self):
        if self.busy or self.editor.snapshot is None or self.items.currentData() is None: return
        try:
            macro = library.load(self.folder, self.items.currentData())
            macro = replace(macro, key=self.editor.source.currentIndex())
            replace_macro(self.editor.snapshot['macros'], macro)  # Check target bank capacity first.
            self.editor.loading = True
            self.editor.name = macro.name
            self.editor.mode.setCurrentIndex(self.editor.mode.findData(macro.mode))
            self.editor.interval.setValue(macro.interval_ms)
            self.editor.actions = list(macro.actions)
            self.editor.loading = False
            self.editor.delete_pending = False; self.editor.delete.setText('Remove saved macro')
            self.editor.refresh_actions()
            self.editor.result.setText('PC macro loaded into the draft; nothing written to the controller.')
            self.draft_loaded.emit()
        except (OSError, ValueError) as error:
            self.result.setText(str(error))

    def delete_copy(self):
        filename = self.items.currentData()
        if self.busy or filename is None: return
        if self.pending_delete != filename:
            self.pending_delete = filename; self.delete.setText('Confirm deletion of PC copy')
            self.result.setText('This deletes only the PC file. Press Confirm to continue.')
            return
        try:
            library.remove(self.folder, filename)
            self.reload()
        except (OSError, ValueError) as error:
            self.result.setText(str(error))

    def import_copy(self):
        filename = self.imports.currentData()
        if self.busy or filename is None: return
        try:
            from .vendor_macro import read
            macro = read(self.folder/'imports'/filename, self.editor.source.currentIndex())
            saved = library.save_copy(self.folder, macro)
            self.reload(saved)
            self.result.setText('Imported a PC copy. Review it in the editor before applying; the original file is unchanged.')
        except (OSError, ValueError) as error:
            self.result.setText(str(error))
