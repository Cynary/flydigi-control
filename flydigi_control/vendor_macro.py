"""Exchange Space Station 4.2.0.9 MacroItem protobuf files; no hardware access."""
import os
import stat
from pathlib import Path
import tempfile
import uuid

from .macro_bank import Action, Macro, validate_execution
from .macro_library import MAX_FILE_BYTES


def _encode_integer(value):
    result = bytearray()
    while value >= 128:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def _scalar(number, value):
    # Protobuf's serializer omits scalar defaults.
    return _encode_integer(number << 3) + _encode_integer(value) if value else b''


def _message(number, raw):
    return _encode_integer((number << 3) | 2) + _encode_integer(len(raw)) + raw


def encode(macro):
    """Serialize a validated local macro as the vendor's individual .dat file."""
    validate_execution(macro)
    raw = _scalar(1, macro.key) + _scalar(2, len(macro.actions)) + _scalar(3, macro.mode)
    for action in macro.actions:
        raw += _message(4, _scalar(1, action.key) + _scalar(2, action.delay_ms) + _scalar(3, action.event))
    raw += _scalar(5, macro.interval_ms)
    if macro.name:
        raw += _message(6, macro.name.encode('utf-8'))
    return raw


def export_copy(folder, macro):
    """Write a new private .dat file; never overwrite a library or vendor file."""
    raw = encode(macro)
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    filename = uuid.uuid4().hex + '.dat'
    descriptor, temporary = tempfile.mkstemp(prefix='.macro-', dir=folder)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, folder / filename)
        directory = os.open(folder, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return folder / filename


def _varint(raw, offset):
    value = 0
    for shift in range(0, 70, 7):
        if offset >= len(raw): raise ValueError('Truncated macro integer')
        byte = raw[offset]; offset += 1
        if shift == 63 and byte > 1: raise ValueError('Oversized macro integer')
        value |= (byte & 127) << shift
        if not byte & 128: return value, offset
    raise ValueError('Invalid macro integer')


def _fields(raw, types, repeated=()):
    result = {}; offset = 0
    while offset < len(raw):
        tag, offset = _varint(raw, offset)
        number, wire = tag >> 3, tag & 7
        if number not in types or wire != types[number]:
            raise ValueError(f'Unsupported vendor macro field {number} (wire type {wire})')
        if number in result and number not in repeated:
            raise ValueError('Repeated scalar field in vendor macro')
        value, offset = _varint(raw, offset)
        if wire == 2:
            end = offset + value
            if end > len(raw): raise ValueError('Truncated vendor macro field')
            value = raw[offset:end]; offset = end
        if number in repeated: result.setdefault(number, []).append(value)
        else: result[number] = value
    return result


def decode(raw, target, name=None):
    if len(raw) > MAX_FILE_BYTES: raise ValueError('Macro file exceeds 64 KiB')
    fields = _fields(raw, {1:0, 2:0, 3:0, 4:2, 5:0, 6:2}, repeated=(4,))
    # Macro=32 and None=255 are library templates, not controller buttons.
    if fields.get(1, 0) not in (*range(24), 32, 255):
        raise ValueError('Unsupported vendor activation type')
    records = fields.get(4, [])
    if len(records) > 256: raise ValueError('Macro exceeds 256 actions')
    # Some editor files omit Count. An explicit inconsistent count is suspect.
    if 2 in fields and fields[2] != len(records):
        raise ValueError('Vendor macro action count disagrees with its data')
    actions = []
    for record in records:
        action = _fields(record, {1:0, 2:0, 3:0})
        event = action.get(3, 0)
        if event == 5:
            raise ValueError('Vendor Hold actions need conversion; import a macro with explicit press/release actions')
        actions.append(Action(action.get(2, 0), action.get(1, 0), event))
    try:
        stored_name = fields.get(6, b'').decode('utf-8')
    except UnicodeError as error:
        raise ValueError('Invalid vendor macro name') from error
    macro = Macro(target, fields.get(3, 0), fields.get(5, 0),
                  name if name is not None else stored_name or 'Imported macro', tuple(actions))
    validate_execution(macro)
    return macro


def read(path, target, name=None):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('Choose a regular macro file')
        return decode(stream.read(MAX_FILE_BYTES + 1), target, name)
