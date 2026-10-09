"""Back up, edit and verify the active profile before committing it onboard."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import secrets
import tempfile

from . import protocol
from .lighting import make_blob


def _mapping_version(mapping):
    # Space Station's MappingConfigParserV30/V31/V32 layout. Unknown formats
    # must be investigated before saving a whole profile.
    if (len(mapping) < 790 or mapping[1] != 3 or mapping[0] > 2
            or (mapping[0] >= 1 and len(mapping) < 840)):
        raise ValueError('Unsupported mapping format; controller was not changed')
    return int.from_bytes(mapping[225:227], 'little')


def _backup(folder, data):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    fd, path = tempfile.mkstemp(prefix='profile-', suffix='.json', dir=folder)
    with os.fdopen(fd, 'w') as file:
        json.dump(data, file, indent=2)
        file.flush()
        os.fsync(file.fileno())
    directory = os.open(folder, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return Path(path)


def apply_lighting(device, mode, colors, brightness, period, backup_dir):
    profile = None
    if mode == 7:
        if device.info().device_id != 130:
            raise ValueError('Default lighting is only available for Vader 5 Pro device type 130')
        profile, _ = device.profile_state()
    return apply_configuration(device, backup_dir, expected_profile=profile,
        lighting_update=lambda original: make_blob(original, mode, colors, brightness, period,
                                                   factory_profile=profile))


def apply_stick_shape(device, previous_mapping, side, shape, backup_dir, *, expected_profile=None):
    from .sticks import with_shape
    def update(mapping):
        if mapping != previous_mapping:
            raise RuntimeError('Controller settings changed; read them again before applying')
        return with_shape(mapping, side, shape)
    return apply_configuration(device, backup_dir, mapping_update=update, expected_profile=expected_profile)


def apply_stick_curve(device, previous_mapping, side, curve, backup_dir, *, expected_profile=None):
    from .curves import with_curve
    def update(mapping):
        if mapping != previous_mapping:
            raise RuntimeError('Controller settings changed; read them again before applying')
        return with_curve(mapping, side, curve)
    return apply_configuration(device, backup_dir, mapping_update=update, expected_profile=expected_profile)


def apply_mapping_edit(device, previous_mapping, edit, backup_dir, *, expected_profile=None):
    def update(mapping):
        if mapping != previous_mapping:
            raise RuntimeError('Controller settings changed; read them again before applying')
        return edit(mapping)
    return apply_configuration(device, backup_dir, mapping_update=update, expected_profile=expected_profile)


def apply_macro(device, previous_mapping, previous_macros, macro, backup_dir, *, expected_profile):
    from .macro_bank import replace_macro, validate_execution
    validate_execution(macro)
    def unchanged(mapping):
        if mapping != previous_mapping:
            raise RuntimeError('Controller settings changed; read them again before applying')
        return mapping
    def update(macros):
        if macros != previous_macros:
            raise RuntimeError('Macros changed; read them again before applying')
        return replace_macro(macros, macro)
    # The vendor's 3.2 ApplyMacroConfig updates AD/AE only: activation is in
    # the macro record. Do not invent a separate A4/A5 button-map write.
    return apply_configuration(device, backup_dir, mapping_update=unchanged,
                               macro_update=update, expected_profile=expected_profile)


def remove_saved_macro(device, previous_mapping, previous_macros, key, backup_dir, *, expected_profile):
    from .macro_bank import remove_macro, decode_bank
    from .button_mappings import read_button
    if not any(r.macro.key==key for r in decode_bank(previous_macros).records):
        raise ValueError('No saved macro on this button')
    def restore_button(mapping):
        if mapping!=previous_mapping:
            raise RuntimeError('Controller settings changed; read them again before applying')
        if read_button(mapping,key).kind not in ('macro','button','rapid_fire'):
            raise ValueError('Unknown or PC-specific button mapping; it was not changed')
        result=bytearray(mapping)
        result[13+3*key:16+3*key]=bytes([255,0,0])
        return bytes(result)
    def update(macros):
        if macros!=previous_macros:
            raise RuntimeError('Macros changed; read them again before applying')
        return remove_macro(macros,key)
    # Vendor UpdateConfig restores the button first, then removes its separate
    # macro record. Saving occurs only after both banks pass full readback.
    return apply_configuration(device,backup_dir,mapping_update=restore_button,
                               macro_update=update,expected_profile=expected_profile)


def apply_configuration(device, backup_dir, *, lighting_update=None, mapping_update=None, macro_update=None, expected_profile=None):
    """Caller holds ConfigurationDevice's lock throughout this transaction.

    Save only on an explicit Apply, never from a reconnect or polling handler.
    A timeout is an uncertain save: check readback, but never repeat the write.
    Power-cycle validation is still required for each supported firmware.
    """
    identity = device.info()
    state = device.profile_state()
    profile, versions = state
    if expected_profile is not None and profile != expected_profile:
        raise RuntimeError('Active profile changed; read settings again before applying')
    mapping = device.read_mapping(profile)
    if _mapping_version(mapping) != versions[profile]:
        raise RuntimeError('Profile version changed; nothing was written')
    # Version 3.2 moved macros out of the base mapping block. A6 saves the
    # active profile; back up and verify this separate state even for LED edits.
    macros = device.read_macros(profile) if mapping[0] >= 2 else None
    if macro_update and macros is None:
        raise ValueError('Macro editing requires mapping format 3.2')
    updated_macros = macro_update(macros) if macro_update else macros
    if macro_update:
        from .macro_bank import decode_bank
        if decode_bank(macros).version != decode_bank(updated_macros).version:
            raise ValueError('An edit must preserve the macro-bank version')
    led_profile, original = device.read_lighting()
    if led_profile != profile or device.profile_state() != state:
        raise RuntimeError('Profile changed during backup; nothing was written')
    blob = lighting_update(original) if lighting_update else original
    updated_mapping = mapping_update(mapping) if mapping_update else mapping
    if _mapping_version(updated_mapping) != versions[profile] or len(updated_mapping) != len(mapping):
        raise ValueError('An edit must preserve the mapping version and geometry')
    backup = _backup(backup_dir, {
        'schema': 1, 'controller': asdict(identity), 'profile': profile,
        'versions': list(versions), 'mapping': mapping.hex(),
        'lighting': original.hex(), 'requested_lighting': blob.hex(),
        'requested_mapping': updated_mapping.hex(),
        'macros': macros.hex() if macros is not None else None,
        'requested_macros': updated_macros.hex() if updated_macros is not None else None,
    })
    # Even an unchanged live value may not have been saved, so Apply must commit
    # it. Ordinary UI refreshes and reconnects never call this function.
    if macros is not None and device.read_macros(profile) != macros:
        raise RuntimeError(f'Macros changed during backup; nothing was written. Backup: {backup}')
    if lighting_update:
        device.write_lighting(profile, blob)
    if updated_mapping != mapping:
        device.write_mapping(profile, mapping, updated_mapping)
    if updated_macros != macros:
        device.write_macros(profile, macros, updated_macros)
    if device.read_lighting() != (profile, blob):
        raise RuntimeError(f'Lighting verification failed; no save sent. Backup: {backup}')
    if device.read_mapping(profile) != updated_mapping or device.profile_state() != state:
        raise RuntimeError(f'Profile changed; no save sent. Backup: {backup}')
    if macros is not None and device.read_macros(profile) != updated_macros:
        raise RuntimeError(f'Macros changed; no save sent. Backup: {backup}')
    # 0xffff is the vendor's factory/default sentinel. Use a fresh non-sentinel
    # identifier, matching the official app's range, without probabilistic loops.
    version = secrets.randbelow(65535)
    if version == versions[profile]:
        version = (version + 1) % 65535
    try:
        device.exchange(protocol.profile_save_request(version), timeout=10)
    except TimeoutError:
        pass
    expected_versions = list(versions)
    expected_versions[profile] = version
    if device.profile_state() != (profile, tuple(expected_versions)):
        raise RuntimeError(f'Save not confirmed; not retried. Backup: {backup}')
    expected_mapping = bytearray(updated_mapping)
    expected_mapping[225:227] = version.to_bytes(2, 'little')
    if device.read_mapping(profile) != bytes(expected_mapping):
        raise RuntimeError(f'Profile differs after saving; no further writes sent. Backup: {backup}')
    if device.read_lighting() != (profile, blob):
        raise RuntimeError(f'Lighting differs after saving; no further writes sent. Backup: {backup}')
    if macros is not None and device.read_macros(profile) != updated_macros:
        raise RuntimeError(f'Macros differ after saving; no further writes sent. Backup: {backup}')
    return backup
