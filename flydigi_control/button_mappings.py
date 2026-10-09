"""Per-button records from the vendor's mapping formats 3.0–3.2.

Only the selected three-byte record is changed. Macros and keyboard/mouse
markers are recognized but not rewritten until their separate storage is handled.
"""
from dataclasses import dataclass
from .persistence import _mapping_version

# device_config_f5 marks 0–23 editable. Fn (24), Turbo (25), Home (27)
# are deliberately excluded. M5/M6 in the SDK are labelled LM/RM on this model.
BUTTONS = ('D-pad up', 'D-pad right', 'D-pad down', 'D-pad left', 'A', 'B',
           'View', 'X', 'Y', 'Menu', 'LB', 'RB', 'LT', 'RT', 'Left stick click',
           'Right stick click', 'C', 'Z', 'M1', 'M2', 'M3', 'M4', 'LM', 'RM')
RAPID_MODES = ((0, 'Off'), (1, 'While held'), (2, 'Press to start / press to stop'))


@dataclass(frozen=True)
class ButtonMapping:
    kind: str
    target: int | None = None
    activation: int = 0
    frequency: int = 0
    raw: bytes = b''

    @property
    def editable(self):
        return self.kind in ('button', 'rapid_fire')


def _offset(mapping, source):
    _mapping_version(mapping)
    if type(source) is not int or source not in range(len(BUTTONS)):
        raise ValueError('Choose one of the controller’s 24 remappable buttons')
    return 13 + 3*source


def read_button(mapping, source):
    offset = _offset(mapping, source)
    raw = bytes(mapping[offset:offset+3])
    target, activation, frequency = raw
    if target == 32:
        return ButtonMapping('macro', raw=raw)
    if target == 254:
        return ButtonMapping('keyboard_mouse', raw=raw)
    if frequency:
        if target not in range(len(BUTTONS)) or activation not in (0,1,2) or not 1 <= frequency <= 30:
            return ButtonMapping('unknown', raw=raw)
        return ButtonMapping('rapid_fire', target, activation, frequency, raw)
    if target == 255:
        target = source  # Vendor's identity/default marker, not "disabled".
    if target not in range(len(BUTTONS)) or activation != 0:
        return ButtonMapping('unknown', raw=raw)
    return ButtonMapping('button', target, raw=raw)


def with_button(mapping, source, *, kind, target, activation=0, frequency=0):
    current = read_button(mapping, source)
    if not current.editable:
        raise ValueError('This record has a macro, PC mapping or unknown format; it was not changed')
    if type(target) is not int or target not in range(len(BUTTONS)):
        raise ValueError('Choose a gamepad button output')
    if type(activation) is not int or type(frequency) is not int:
        raise ValueError('Rapid-fire settings must be integers')
    if kind == 'button':
        if activation != 0 or frequency != 0:
            raise ValueError('Ordinary button mappings cannot include rapid-fire settings')
        record = bytes([255 if target == source else target, 0, 0])
    elif kind == 'rapid_fire':
        if activation not in (0,1,2) or not 1 <= frequency <= 30:
            raise ValueError('Choose a rapid-fire mode and 1–30 presses per second')
        record = bytes([target, activation, frequency])
    else:
        raise ValueError('Choose a button or rapid-fire mapping')
    # Preserve a noncanonical but equivalent explicit self-mapping unchanged.
    if (kind,target,activation,frequency) == (current.kind,current.target,current.activation,current.frequency):
        return bytes(mapping)
    result = bytearray(mapping)
    offset = _offset(mapping, source)
    result[offset:offset+3] = record
    return bytes(result)
