"""Controller-wide settings, distinct from the A6-saved mapping profiles.

Wire fields and choices were checked against Space Station 4.2.0.9's NewXInput
SDK and UI. See docs/HARDWARE-SETTINGS.md for exclusions and validation status.
"""
from dataclasses import asdict, dataclass
from . import protocol
from .persistence import _backup


@dataclass(frozen=True)
class Setting:
    label: str
    description: str
    command: int
    offset: int
    choices: tuple
    subcommand: int = 0

    def value(self, reply):
        return bool(reply[6] & (1 << (self.subcommand - 1))) if self.subcommand else reply[self.offset]

    def supported(self, reply):
        if self.subcommand:
            return bool(reply[5] & (1 << (self.subcommand - 1)))
        # The official app always offers sleep; zero means unsupported for
        # precision/sensitivity, but means Never for the sleep timer.
        return self.command == 0x17 or reply[self.offset] != 0


TOGGLE = ((False, 'Off'), (True, 'On'))
SETTINGS = {
    'profile_hotkeys': Setting('Fn profile shortcuts', 'Fn + A/B/X/Y selects the four controller profiles.', 0x13, 6, TOGGLE, 1),
    'home_button': Setting('Home button output', 'Controls the controller’s Xbox Home button output. Disabling it may prevent opening Steam’s menu.', 0x13, 6, TOGGLE, 2),
    'motion_filter': Setting('Motion filtering', 'The firmware’s motion debounce switch. Its effect on native gyro reports still needs measurement.', 0x13, 6, TOGGLE, 3),
    'turbo': Setting('Turbo shortcuts', 'Enables the controller’s Turbo/macro shortcuts; this is not a Steam Input binding.', 0x13, 6, TOGGLE, 4),
    'stick_filter': Setting('Stick filtering', 'The firmware’s stick debounce switch; separate from a profile’s deadzone.', 0x13, 6, TOGGLE, 5),
    'auto_calibration': Setting('Automatic stick calibration', 'Enables the firmware’s automatic calibration. This does not run a manual calibration procedure.', 0x13, 6, TOGGLE, 6),
    'rebound': Setting('Stick rebound suppression', 'The firmware’s anti-rebound switch, intended for stick release. Behavior under Steam Input needs validation.', 0x13, 6, TOGGLE, 7),
    'precision': Setting('Stick precision', 'Selects the firmware’s stick precision. This is not a report-rate setting.', 0x15, 11,
                         ((3, '12 bit'), (5, '11 bit'), (2, '10 bit'), (4, '9 bit'), (1, '8 bit'))),
    'sensitivity': Setting('Stick center sensitivity', 'The official app offers Fast, Medium and Slow. This is separate from the per-profile response curve.', 0x16, 12,
                           ((14, 'Fast'), (17, 'Medium'), (19, 'Slow'))),
    'sleep': Setting('Controller sleep timer', 'How long the controller waits before sleeping. This does not change the PC’s sleep timer or enable USB wake.', 0x17, 9,
                    ((1, '1 minute'), (5, '5 minutes'), (15, '15 minutes'), (60, '1 hour'), (180, '3 hours'), (0, 'Never'))),
}


def parse_status(reply):
    if len(reply) != 32 or reply[:3] != protocol.MAGIC + b'\x03':
        raise ValueError('Invalid hardware-settings reply')
    return {key: {'supported': setting.supported(reply), 'value': setting.value(reply)}
            for key, setting in SETTINGS.items()}


def setting_packet(name, value):
    if name not in SETTINGS:
        raise ValueError('Unknown hardware setting')
    setting = SETTINGS[name]
    value_type = bool if setting.subcommand else int
    if type(value) is not value_type or value not in dict(setting.choices):
        raise ValueError('Unsupported hardware setting value')
    payload = (setting.subcommand, int(value)) if setting.subcommand else (value,)
    return protocol.request(setting.command, *payload)


def valid_packet(packet):
    # Exact comparison checks the length, checksum, trailer and supported value.
    return any(packet == setting_packet(name, value)
               for name, setting in SETTINGS.items() for value, _ in setting.choices)


def apply_setting(device, previous_reply, name, value, backup_dir):
    """One explicit write with backup/readback, never an automatic reconnect write.

    A lost ACK is not permission to replay. A6 saves mapping profiles and is not
    used for these global commands by the official app. Persistence across a
    controller power cycle must be verified separately on real hardware.
    """
    packet = setting_packet(name, value)
    identity = device.info()
    current = device.exchange(protocol.request(0x03))
    status = parse_status(current)
    parse_status(previous_reply)
    # Compare all documented global fields, not the wireless trailer/counter.
    if current[5:13] != previous_reply[5:13]:
        raise RuntimeError('Controller settings changed; read them again before applying')
    if not status[name]['supported']:
        raise ValueError('Controller firmware does not advertise this setting')
    # Do not normalize unrecognized firmware values into one of our choices.
    if status[name]['value'] not in dict(SETTINGS[name].choices):
        raise ValueError('Unknown current value; no settings were changed')
    if status[name]['value'] == value:
        return current
    backup = _backup(backup_dir, {
        'schema': 1, 'kind': 'hardware-settings', 'controller': asdict(identity),
        'status': bytes(current).hex(), 'setting': name, 'requested_value': value,
    })
    try:
        device.exchange(packet)
    except TimeoutError:
        pass
    actual = device.exchange(protocol.request(0x03))
    parse_status(actual)
    expected = bytearray(current)
    setting = SETTINGS[name]
    if setting.subcommand:
        mask = 1 << (setting.subcommand - 1)
        expected[6] = expected[6] | mask if value else expected[6] & ~mask
    else:
        expected[setting.offset] = value
    if actual[5:13] != expected[5:13]:
        raise RuntimeError(f'Settings readback differs; write was not retried. Backup: {backup}')
    return actual
