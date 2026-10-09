import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from flydigi_control import protocol
from flydigi_control.profiles import select_profile
from flydigi_control.persistence_check import snapshot
from flydigi_control.transport import ConfigurationDevice
from test_persistence_check import ReadOnlyController


class Controller(ReadOnlyController):
    fail_ack = False
    ignore_select = False
    change_version = False

    def exchange(self, packet, timeout=None):
        if packet[2] != protocol.CMD_PROFILE_SELECT:
            return super().exchange(packet)
        self.writes.append(packet)
        if not self.ignore_select:
            self.profile = packet[4]
            self.mapping[225:227] = self.versions[self.profile].to_bytes(2, 'little')
        if self.change_version:
            self.versions = tuple(v+1 for v in self.versions)
        if self.fail_ack: raise TimeoutError()
        return b'ack'


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.device = Controller()
        self.previous = snapshot(self.device)
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)

    def test_select_backs_up_old_profile_and_never_saves_or_resets(self):
        actual, backup = select_profile(self.device, self.previous, 2, self.temp.name)
        self.assertEqual(json.loads(backup.read_text()), self.previous)
        self.assertEqual(actual['profile'], 2)
        self.assertEqual(actual['versions'], self.previous['versions'])
        self.assertEqual(self.device.writes, [protocol.profile_select_request(2)])

    def test_lost_ack_uses_readback_without_retry(self):
        self.device.fail_ack = True
        self.assertEqual(select_profile(self.device, self.previous, 3, self.temp.name)[0]['profile'], 3)
        self.assertEqual(len(self.device.writes), 1)

    def test_failed_selection_or_changed_version_does_not_retry_or_roll_back(self):
        for flag in ('ignore_select', 'change_version'):
            device = Controller(); setattr(device, flag, True)
            with self.assertRaisesRegex(RuntimeError, 'not confirmed'):
                select_profile(device, self.previous, 2, self.temp.name)
            self.assertEqual(len(device.writes), 1)

    def test_stale_snapshot_and_backup_failure_send_nothing(self):
        self.device.lighting = b'\x01'+self.device.lighting[1:]
        with self.assertRaisesRegex(RuntimeError, 'Settings changed'):
            select_profile(self.device, self.previous, 2, self.temp.name)
        self.assertEqual(self.device.writes, [])
        self.previous = snapshot(self.device)
        with patch('flydigi_control.profiles._backup', side_effect=OSError('full')):
            with self.assertRaises(OSError): select_profile(self.device, self.previous, 2, self.temp.name)
        self.assertEqual(self.device.writes, [])

    def test_current_target_does_not_write(self):
        data, backup = select_profile(self.device, self.previous, 1, self.temp.name)
        self.assertEqual(data, self.previous); self.assertIsNone(backup)
        self.assertEqual(self.device.writes, [])
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_exact_command_and_transport_framing(self):
        self.assertEqual(protocol.profile_select_request(2)[:6], bytes.fromhex('5aa5a20302a7'))
        for value in (True, -1, 4, 8, 1.0):
            with self.assertRaises(ValueError): protocol.profile_select_request(value)
        device = ConfigurationDevice('/dev/test'); device.fd = 99
        with patch('flydigi_control.transport.os.write', return_value=33) as write:
            device.send(protocol.profile_select_request(2))
            write.assert_called_once_with(99, b'\x00'+protocol.profile_select_request(2))
            broken = bytearray(protocol.profile_select_request(2)); broken[5] ^= 1
            with self.assertRaises(ValueError): device.send(bytes(broken))
            self.assertEqual(write.call_count, 1)
