"""Explicit PC-profile selection with a current-profile backup and readback."""
from . import protocol
from .persistence import _backup
from .persistence_check import snapshot, compare


def select_profile(device, previous, target, folder):
    packet = protocol.profile_select_request(target)
    current = snapshot(device)
    if compare(previous, current):
        raise RuntimeError('Settings changed; read the active profile again before switching')
    if current['profile'] == target:
        return current, None
    backup = _backup(folder, current)
    # File I/O can take time. Do not act on a changed active profile afterward.
    if device.profile_state() != (current['profile'], tuple(current['versions'])):
        raise RuntimeError(f'Profile changed before switching. Backup: {backup}')
    try:
        device.exchange(packet, timeout=3)
    except TimeoutError:
        pass  # A lost ACK is resolved by reading; never repeat the selection.
    if device.profile_state() != (target, tuple(current['versions'])):
        raise RuntimeError(f'Profile selection not confirmed; no retry or rollback sent. Backup: {backup}')
    actual = snapshot(device)
    if (actual['profile'] != target or actual['versions'] != current['versions']
            or actual['identity'] != current['identity']):
        raise RuntimeError(f'Controller state changed during verification. Backup: {backup}')
    for field in ('hardware_settings', 'native_mapping_permission', 'report_rate_code'):
        if actual[field] != current[field]:
            raise RuntimeError(f'{field} changed during selection; no further writes sent. Backup: {backup}')
    return actual, backup
