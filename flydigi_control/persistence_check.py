"""Read-only snapshots for off/on, receiver replug and PC restart checks."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from . import protocol
from .hardware_settings import parse_status
from .persistence import _backup, _mapping_version
from .transport import ConfigurationDevice, discover


def _read(device):
    info = asdict(device.info())
    state = device.profile_state()
    profile, versions = state
    mapping = device.read_mapping(profile)
    if _mapping_version(mapping) != versions[profile]:
        raise RuntimeError('Profile version changed during read')
    macros = device.read_macros(profile) if mapping[0] >= 2 else None
    lighting_profile, lighting = device.read_lighting()
    reply = device.exchange(protocol.request(0x03))
    settings = parse_status(reply)
    permission = device.mapping_status()['third_party_control']
    if lighting_profile != profile or device.profile_state() != state:
        raise RuntimeError('Active profile changed during read')
    return {
        'schema': 1, 'kind': 'persistence-check',
        # This protocol does not give us a unique controller serial number.
        # Battery and current Steam ownership are deliberately not settings.
        'identity': {k: info[k] for k in ('device_id', 'model', 'connection', 'firmware')},
        'profile': profile, 'versions': list(versions),
        'mapping': mapping.hex(), 'lighting': lighting.hex(),
        'macros': macros.hex() if macros is not None else None,
        'hardware_settings': settings, 'report_rate_code': reply[10],
        'native_mapping_permission': permission,
    }


def snapshot(device):
    """Caller holds the config lock; reject changes between two complete reads."""
    first = _read(device)
    if _read(device) != first:
        raise RuntimeError('Settings changed between reads; no snapshot saved')
    return first


def compare(expected, actual):
    if (not isinstance(expected, dict) or expected.get('schema') != 1
            or expected.get('kind') != 'persistence-check'
            or expected.keys() != actual.keys()):
        raise ValueError('Choose a snapshot made by persistence_check')
    differences = []
    for key in actual:
        before, after = expected[key], actual[key]
        if before == after:
            continue
        difference = {'field': key}
        if key in ('mapping', 'lighting', 'macros') and before is not None and after is not None:
            try:
                old, new = bytes.fromhex(before), bytes.fromhex(after)
            except (TypeError, ValueError) as error:
                raise ValueError(f'Invalid {key} snapshot') from error
            offsets = [i for i in range(max(len(old), len(new)))
                       if old[i:i+1] != new[i:i+1]]
            difference.update(changed_bytes=len(offsets), first_offsets=offsets[:32],
                              before_length=len(old), after_length=len(new))
        else:
            difference.update(before=before, after=after)
        differences.append(difference)
    return differences


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('snapshot', 'check'))
    parser.add_argument('path', type=Path, help='Snapshot directory, or existing snapshot file for check')
    parser.add_argument('--device', help='Configuration hidraw path from flydigi_control --probe')
    args = parser.parse_args(argv)
    try:
        expected = json.loads(args.path.read_text()) if args.operation == 'check' else None
        devices = discover()
        if not args.device and len(devices) != 1:
            parser.error('Connect one Vader or specify --device; no controller settings were changed')
        with ConfigurationDevice(args.device or devices[0]['path']) as device:
            actual = snapshot(device)
        if args.operation == 'snapshot':
            print(_backup(args.path, actual))
            return 0
        differences = compare(expected, actual)
        print(json.dumps({'settings_match': not differences, 'differences': differences,
                          'note': 'Only meaningful after the intended power/reconnect test on the same controller. '
                                  'No unique serial is available; matching data alone does not prove a power cycle.'}, indent=2))
        return 1 if differences else 0
    except (OSError, ValueError, RuntimeError) as error:
        print(f'Check incomplete: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
