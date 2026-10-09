"""Portable PC macro library. Loading never applies a macro to hardware."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
import uuid

from .macro_bank import Action, Macro, validate_execution

MAX_FILE_BYTES = 65536


def library_directory():
    return Path(os.environ.get('XDG_DATA_HOME', str(Path.home()/'.local/share'))) / 'flydigi-control/macros'


def encode(macro):
    validate_execution(macro)
    return json.dumps({'format': 'flydigi-control-macro', 'version': 1,
                       'macro': asdict(macro)}, ensure_ascii=False, indent=2).encode('utf-8')


def decode(raw):
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError('Macro file exceeds 64 KiB')
    try:
        data = json.loads(raw)
        if (set(data) != {'format', 'version', 'macro'} or data['format'] != 'flydigi-control-macro'
                or type(data['version']) is not int or data['version'] != 1):
            raise ValueError('Unsupported macro file format')
        value = data['macro']
        if set(value) != {'key', 'mode', 'interval_ms', 'name', 'actions'}:
            raise ValueError('Invalid macro fields')
        if not isinstance(value['actions'], list) or len(value['actions']) > 256:
            raise ValueError('Macro needs at most 256 actions')
        actions = tuple(Action(**item) for item in value['actions'])
        macro = Macro(value['key'], value['mode'], value['interval_ms'], value['name'], actions)
        validate_execution(macro)
        return macro
    except (TypeError, KeyError, UnicodeError) as error:
        raise ValueError('Invalid macro file') from error


def _path(folder, filename):
    if (not isinstance(filename, str) or Path(filename).name != filename
            or not filename.endswith('.json') or filename.startswith('.')):
        raise ValueError('Choose a macro file in the library')
    path = Path(folder) / filename
    if path.is_symlink():
        raise ValueError('Symbolic links are not macro library files')
    return path


def load(folder, filename):
    path = _path(folder, filename)
    # Do not follow a link swapped in after directory enumeration.
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as stream:
        import stat
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('Macro must be a regular file')
        return decode(stream.read(MAX_FILE_BYTES + 1))


def entries(folder):
    valid, errors = [], []
    for path in sorted(Path(folder).glob('*.json')):
        if path.name.startswith('.'): continue
        try:
            valid.append((path.name, load(folder, path.name)))
        except (OSError, ValueError) as error:
            errors.append(f'{path.name}: {error}')
    return valid, errors


def save_copy(folder, macro):
    raw = encode(macro)
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    filename = uuid.uuid4().hex + '.json'
    descriptor, temporary = tempfile.mkstemp(prefix='.macro-', dir=folder)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, folder / filename)
        _sync(folder)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return filename


def remove(folder, filename):
    _path(folder, filename).unlink()
    _sync(folder)


def _sync(folder):
    descriptor = os.open(folder, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)
