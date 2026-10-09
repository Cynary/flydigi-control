"""Configuration-only access: never detach a driver or change input mode."""
from __future__ import annotations

import fcntl
import os
from pathlib import Path
import select
import time

from . import protocol


def discover(sysfs: Path = Path('/sys')) -> list[dict]:
    devices = []
    for node in sorted((sysfs / 'class/hidraw').glob('hidraw*')):
        try:
            hid = (node / 'device').resolve()
            props = dict(line.split('=', 1) for line in
                         (hid / 'uevent').read_text().splitlines() if '=' in line)
            bus, vendor, product = (int(x, 16) for x in props['HID_ID'].split(':'))
            if (bus, vendor, product) != (3, 0x37d7, 0x2401):
                continue
            if not (hid / 'report_descriptor').read_bytes().startswith(protocol.CONFIG_DESCRIPTOR_PREFIX):
                continue
            usb = next(p for p in hid.parents if (p / 'idVendor').exists())
            ancestors = []
            for p in (usb, *usb.parents):
                wake = p / 'power/wakeup'
                if wake.is_file():
                    ancestors.append({'device': p.name, 'wakeup': wake.read_text().strip()})
            desc = (usb / 'descriptors').read_bytes()
            remote_wake = False
            offset = 0
            while offset + 2 <= len(desc):
                length, kind = desc[offset:offset + 2]
                if length < 2 or offset + length > len(desc):
                    break
                if kind == 2 and length >= 9:
                    remote_wake |= bool(desc[offset + 7] & 0x20)
                offset += length
            devices.append({'path': '/dev/' + node.name, 'name': props.get('HID_NAME', 'Vader 5 Pro'),
                            'usb_path': str(usb), 'remote_wake_advertised': remote_wake,
                            'wake_chain': ancestors})
        except (OSError, KeyError, ValueError, StopIteration):
            continue
    return devices


class ConfigurationDevice:
    """Lighting, identity, Turbo and Fn profile-hotkey configuration.

    hidraw broadcasts reports to each opener. Reading this fd doesn't consume
    Steam's reports. No test-mode, acquire, reset, profile-switch or flash command
    is sent. The advisory lock serializes our own configuration clients.
    """
    ALLOWED = {protocol.CMD_INFO, 0x03, 0x10, 0x11, 0x13, protocol.CMD_PROFILE_VERSIONS,
               protocol.CMD_LED_READ, protocol.CMD_LED_WRITE_START,
               protocol.CMD_LED_WRITE_PACK, protocol.CMD_LED_TEST_COLOR}

    def __init__(self, path: str):
        self.path = path
        self.fd = None
        self.last_reply_checksum_matches = None

    def __enter__(self):
        if self.path not in {d['path'] for d in discover()}:
            raise ValueError('Select a connected Vader 5 Pro configuration interface.')
        self.fd = os.open(self.path, os.O_RDWR | os.O_NONBLOCK | os.O_CLOEXEC)
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(self.fd)
            self.fd = None
            raise RuntimeError('Another Flydigi configuration operation is running.')
        return self

    def __exit__(self, *args):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def _read(self):
        for _ in range(1024):
            try:
                raw = os.read(self.fd, 64)
            except BlockingIOError:
                return
            if not raw:
                raise OSError('Controller disconnected')
            yield protocol.strip_report_id(raw)

    def send(self, packet: bytes):
        if len(packet) != 32 or packet[:2] != protocol.MAGIC or packet[2] not in self.ALLOWED:
            raise ValueError('Unsupported configuration command')
        if packet[2] == 0x13 and (packet[3] != 4 or packet[4] not in (1, 4) or packet[5] not in (0, 1)):
            raise ValueError('Only Turbo and Fn profile hotkeys are supported')
        if packet[2] == 0x11 and (packet[3:8] != bytes([7, 255, 255, 255, 255]) or packet[8] not in (0, 1)):
            raise ValueError('Only third-party mapping permission may be changed')
        # Linux hidraw requires a zero report-ID byte for unnumbered reports.
        output = b'\x00' + packet
        if os.write(self.fd, output) != len(output):
            raise OSError('Incomplete HID write')

    def exchange(self, packet: bytes, timeout: float = 0.5) -> bytes:
        try:
            return self._exchange_once(packet, timeout)
        except TimeoutError:
            # Vader 5 Pro 7.1.5.0 suppresses consecutive identical queries,
            # including across fd opens. Waiting 600 ms did not clear it;
            # alternating read-only queries did. Never replay a setting write.
            if packet not in (protocol.info_request(), protocol.request(0x03),
                              protocol.request(0x10)):
                raise
            primer = protocol.request(0x03 if packet[2] != 0x03 else 0x01)
            try:
                self._exchange_once(primer, timeout)
            except TimeoutError:
                # The primer can itself be the last query sent by another
                # client. Only the requested reply determines success.
                pass
            return self._exchange_once(packet, timeout)

    def _exchange_once(self, packet: bytes, timeout: float) -> bytes:
        list(self._read())
        self.send(packet)
        deadline = time.monotonic() + timeout
        while (remaining := deadline - time.monotonic()) > 0:
            select.select([self.fd], [], [], remaining)
            for reply in self._read():
                if len(reply) == 32 and reply[:3] == packet[:3]:
                    # The public 7.1.4.0 wireless capture does not satisfy the
                    # wired checksum convention. Record this as a diagnostic,
                    # not a reason to discard a correctly framed reply. USB
                    # transport has its own CRC; the trailer's meaning on all
                    # receiver firmware versions still needs investigation.
                    self.last_reply_checksum_matches = reply[31] == (sum(reply[2:31]) & 0xff)
                    return reply
        raise TimeoutError('No reply from controller; is it turned on?')

    def info(self):
        reply = self.exchange(protocol.info_request())
        result = protocol.parse_info(reply)
        if result is None or result.device_id != 130:
            raise ValueError('Controller did not identify as a Vader 5 Pro')
        return result

    def set_color(self, red: int, green: int, blue: int):
        if any(type(v) is not int or not 0 <= v <= 255 for v in (red, green, blue)):
            raise ValueError('RGB channels must be integers from 0 to 255')
        self.info()
        # Instant color has no acknowledgement handler in the vendor SDK.
        # A successful write confirms delivery to USB, not the visible result.
        self.send(protocol.led_test_color(red, green, blue))

    def mapping_status(self):
        reply = self.exchange(protocol.request(0x10))
        return {'third_party_control': reply[9] == 1,
                'owner': reply[10:30].split(b'\x00')[0].decode('ascii', 'replace'),
                'controller_data': reply[5] == 1, 'raw_data': reply[6] == 1}

    def set_third_party_control(self, enabled: bool):
        if type(enabled) is not bool:
            raise ValueError('Choose a boolean state')
        self.info()
        # 0xff leaves each stream setting alone; Steam acquires it itself.
        self.exchange(protocol.request(0x11, 255, 255, 255, 255, int(enabled)))
        if self.mapping_status()['third_party_control'] != enabled:
            raise RuntimeError('Controller did not retain third-party mapping permission')

    def features(self):
        reply = self.exchange(protocol.request(0x03))
        return {name: {'supported': bool(reply[5] & mask), 'enabled': bool(reply[6] & mask)}
                for name, mask in (('profile_hotkeys', 1), ('turbo', 8))}

    def set_feature(self, name: str, enabled: bool):
        if name not in ('profile_hotkeys', 'turbo') or type(enabled) is not bool:
            raise ValueError('Choose turbo or profile_hotkeys and a boolean state')
        self.info()
        if not self.features()[name]['supported']:
            raise ValueError('Controller firmware does not advertise this feature')
        subcommand = 1 if name == 'profile_hotkeys' else 4
        self.exchange(protocol.request(0x13, subcommand, int(enabled)))
        if self.features()[name]['enabled'] != enabled:
            raise RuntimeError('Controller did not retain the requested setting')
