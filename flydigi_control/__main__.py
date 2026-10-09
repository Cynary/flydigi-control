import argparse
from dataclasses import asdict
import json
from .transport import discover, ConfigurationDevice
from .led import parse_color


def main():
    parser = argparse.ArgumentParser(description='Flydigi Vader 5 Pro configuration')
    parser.add_argument('--probe', action='store_true', help='Read USB identity and wake support without writing commands')
    parser.add_argument('--info', action='store_true', help='Query controller identity')
    parser.add_argument('--macros', action='store_true', help='Read the active profile’s macro bank; no writes')
    parser.add_argument('--hardware-settings', action='store_true', help='Read global filtering, precision, sensitivity and sleep settings')
    parser.add_argument('--features', action='store_true', help='Read Turbo and Fn profile hotkey settings')
    parser.add_argument('--native-input', choices=('on', 'off'), help='Allow Steam to map the extra buttons; restart Steam afterward')
    parser.add_argument('--mapping-status', action='store_true', help='Read third-party mapping permission and owner')
    parser.add_argument('--turbo', choices=('on', 'off'), help='Enable or disable controller-side Turbo chords')
    parser.add_argument('--profile-hotkeys', choices=('on', 'off'), help='Enable or disable Fn+A/B/X/Y profile selection')
    parser.add_argument('--monitor', type=float, metavar='SECONDS', help='Passively record button changes as JSON lines; no input-mode changes')
    parser.add_argument('--color', help='Apply a temporary LED color, e.g. #0080ff')
    parser.add_argument('--device', help='Choose a configuration hidraw path when multiple receivers exist')
    parser.add_argument('--screenshot', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.probe:
        print(json.dumps(discover(), indent=2))
        return
    if args.info or args.color or args.features or args.hardware_settings or args.macros or args.mapping_status or args.native_input or args.turbo or args.profile_hotkeys or args.monitor is not None:
        devices = discover()
        if not args.device and len(devices) != 1:
            parser.error('Connect one Vader 5 Pro or select --device from --probe output')
        if args.monitor is not None:
            import sys
            from .capture import monitor
            monitor(args.device or devices[0]['path'], args.monitor, sys.stdout)
            return
        with ConfigurationDevice(args.device or devices[0]['path']) as device:
            if args.info:
                print(json.dumps(asdict(device.info()), indent=2))
            if args.native_input:
                device.set_third_party_control(args.native_input == 'on')
                print('Native mapping permission saved. Restart Steam to detect the native interface.')
            if args.mapping_status:
                print(json.dumps(device.mapping_status(), indent=2))
            if args.macros:
                from .macro_bank import decode_bank
                device.info()
                state = device.profile_state()
                mapping = device.read_mapping(state[0])
                if mapping[:2] != bytes([2,3]):
                    parser.error('This command requires mapping format 3.2')
                bank = decode_bank(device.read_macros(state[0]))
                if device.profile_state() != state:
                    raise RuntimeError('Profile changed during read')
                print(json.dumps({'profile': state[0], 'bank_version': bank.version,
                                  'macros': [asdict(r.macro) for r in bank.records],
                                  'raw_bank': bank.raw.hex()}, indent=2))
            if args.hardware_settings:
                from . import protocol
                from .hardware_settings import parse_status
                device.info()
                reply = device.exchange(protocol.request(0x03))
                print(json.dumps({'settings': parse_status(reply), 'report_rate_code': reply[10],
                                  'raw_reply': reply.hex()}, indent=2))
            if args.features:
                print(json.dumps(device.features(), indent=2))
            for name, setting in (('turbo', args.turbo), ('profile_hotkeys', args.profile_hotkeys)):
                if setting:
                    device.set_feature(name, setting == 'on')
                    print(f'{name}: {setting} (read back from controller)')
            if args.color:
                color = parse_color(args.color)
                if color is None:
                    parser.error('Color must be six hexadecimal digits')
                device.set_color(*color)
                print('Color command sent. Check the lights; this is a temporary change.')
        return
    from .ui import run
    run(args.screenshot)


if __name__ == '__main__':
    main()
