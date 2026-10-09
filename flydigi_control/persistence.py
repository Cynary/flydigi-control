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
    return apply_configuration(device, backup_dir,
        lighting_update=lambda original: make_blob(original, mode, colors, brightness, period))


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


def apply_configuration(device, backup_dir, *, lighting_update=None, mapping_update=None, expected_profile=None):
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
    })
    # Even an unchanged live value may not have been saved, so Apply must commit
    # it. Ordinary UI refreshes and reconnects never call this function.
    if lighting_update:
        device.write_lighting(profile, blob)
    if updated_mapping != mapping:
        device.write_mapping(profile, mapping, updated_mapping)
    if device.read_lighting() != (profile, blob):
        raise RuntimeError(f'Lighting verification failed; no save sent. Backup: {backup}')
    if device.read_mapping(profile) != updated_mapping or device.profile_state() != state:
        raise RuntimeError(f'Profile changed; no save sent. Backup: {backup}')
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
    return backup
