"""Restore this app's active-profile backups, without replaying global settings."""
import json
import os
import stat

from .lighting import validate_blob
from .macro_bank import decode_bank, validate_execution
from .persistence import _mapping_version, apply_configuration, _backup
from .persistence_check import snapshot, compare


def read_backup(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('Choose a regular profile backup file')
        raw = stream.read(65537)
    if len(raw) > 65536: raise ValueError('Profile backup exceeds 64 KiB')
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get('schema') != 1 or data.get('kind') != 'persistence-check':
        raise ValueError('Choose an active-profile backup made by this app')
    return data


def restore_data(source, current):
    """Validate compatibility and return bytes with the current save version."""
    try:
        if source.get('schema') != 1 or source.get('kind') != 'persistence-check':
            raise ValueError('Not an active-profile backup')
        if source['identity'] != current['identity'] or source['identity']['device_id'] != 130:
            raise ValueError('Backup model, firmware or connection type differs')
        if type(source['profile']) is not int or source['profile'] != current['profile']:
            raise ValueError('Select the backup’s original PC profile before restoring')
        mapping = bytes.fromhex(source['mapping']); live = bytes.fromhex(current['mapping'])
        version = _mapping_version(mapping)
        if version != source['versions'][source['profile']]:
            raise ValueError('Backup version disagrees with its mapping data')
        if mapping[:3] != live[:3] or len(mapping) != len(live):
            raise ValueError('Backup mapping format differs from the controller')
        updated = bytearray(mapping); updated[225:227] = live[225:227]
        lighting = bytes.fromhex(source['lighting']); live_lighting = bytes.fromhex(current['lighting'])
        if validate_blob(lighting) != validate_blob(live_lighting) or len(lighting) != len(live_lighting):
            raise ValueError('Backup lighting geometry differs from the controller')
        macros = None
        if mapping[0] >= 2:
            macros = bytes.fromhex(source['macros'])
            bank = decode_bank(macros); live_bank = decode_bank(bytes.fromhex(current['macros']))
            from .macro_bank import BANK_SIZE
            if len(bank.raw) != len(live_bank.raw) or bank.raw[BANK_SIZE:] != live_bank.raw[BANK_SIZE:]:
                raise ValueError('Macro-bank geometry or reserved tail differs')
            if bank.version != live_bank.version: raise ValueError('Macro bank format differs')
            for record in bank.records: validate_execution(record.macro)
        elif source['macros'] is not None or current['macros'] is not None:
            raise ValueError('Unexpected separate macro bank')
        return {'mapping': bytes(updated), 'lighting': lighting, 'macros': macros}
    except (KeyError, TypeError, IndexError, AttributeError) as error:
        raise ValueError('Incomplete or invalid profile backup') from error


def preview(source, current):
    restored = restore_data(source, current)
    return {field: sum(a != b for a,b in zip(blob, bytes.fromhex(current[field])))
            for field,blob in restored.items() if blob is not None}


def restore(device, source, previous, folder):
    current = snapshot(device)
    if compare(previous, current):
        raise RuntimeError('Controller settings changed; read and review the restore again')
    restored = restore_data(source, current)
    recovery = _backup(folder, current)
    def update(field):
        def checked(original):
            expected = bytes.fromhex(current[field]) if current[field] is not None else None
            if original != expected:
                raise RuntimeError(f'{field} changed before restore; stopped')
            return restored[field]
        return checked
    backup = apply_configuration(device, folder, mapping_update=update('mapping'),
                                 lighting_update=update('lighting'),
                                 macro_update=update('macros') if restored['macros'] is not None else None,
                                 expected_profile=current['profile'])
    actual = snapshot(device)
    for field in ('identity','profile','hardware_settings','native_mapping_permission','report_rate_code'):
        if actual[field] != current[field]:
            raise RuntimeError(f'{field} changed during restore. Backup: {backup}')
    return actual, recovery
