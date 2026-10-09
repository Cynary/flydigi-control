import argparse
from dataclasses import asdict
import json
from .transport import discover, ConfigurationDevice
from .led import parse_color


def main():
    parser = argparse.ArgumentParser(description='Flydigi Vader 5 Pro configuration')
    parser.add_argument('--probe', action='store_true', help='Read USB identity and wake support without writing commands')
    parser.add_argument('--info', action='store_true', help='Query controller identity')
    parser.add_argument('--features', action='store_true', help='Read Turbo and Fn profile hotkey settings')
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
    if args.info or args.color or args.features or args.turbo or args.profile_hotkeys or args.monitor is not None:
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
                print('Color command acknowledged. It resets when the controller powers off.')
        return
    from .ui import run
    run(args.screenshot)


if __name__ == '__main__':
    main()
