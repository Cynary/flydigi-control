import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flydigi_control import protocol
from flydigi_control.persistence import apply_lighting
from flydigi_control.persistence import apply_stick_shape, apply_stick_curve, apply_mapping_edit
from flydigi_control.transport import ConfigurationDevice


class Controller:
    def __init__(self):
        self.profile = 1
        self.versions = (10, 20, 30, 40)
        self.mapping = bytearray(840)
        self.mapping[:3] = bytes([2, 3, 79])
        self.mapping[225:227] = (20).to_bytes(2, 'little')
        self.lighting = bytes.fromhex('000300000901140a0700ffffffffffffffffffff') + bytes(300)
        self.writes = []
        self.save_timeout = False
        self.ignore_save = False

    def info(self):
        return protocol.ControllerInfo(130, 'Vader 5 Pro', 'wireless', '7.1.5.0', '40%')

    def profile_state(self):
        return self.profile, self.versions

    def read_mapping(self, profile):
        assert profile == self.profile
        return bytes(self.mapping)

    def read_lighting(self):
        return self.profile, self.lighting

    def write_lighting(self, profile, blob):
        self.writes.append(('lighting', blob))
        self.lighting = blob

    def write_mapping(self, profile, original, updated):
        assert bytes(self.mapping) == original
        self.mapping[:] = updated
        self.writes.append(('mapping', updated))

    def exchange(self, packet, timeout):
        self.writes.append(('save', packet))
        if not self.ignore_save:
            version = int.from_bytes(packet[4:6], 'little')
            v = list(self.versions)
            v[self.profile] = version
            self.versions = tuple(v)
            self.mapping[225:227] = version.to_bytes(2, 'little')
        if self.save_timeout:
            raise TimeoutError()
        return b'ack'


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.device = Controller()

    def apply(self):
        return apply_lighting(self.device, 5, [(255, 0, 255)], 30, 15, self.tmp.name)

    def test_save_has_vendor_framing_and_version_order(self):
        self.assertEqual(protocol.profile_save_request(0x1234)[:7],
                         bytes.fromhex('5a a5 a6 04 34 12 f0'))
        self.assertEqual(protocol.mapping_read_request(2)[:7],
                         bytes.fromhex('5a a5 a3 04 02 14 bd'))
        for value in (-1, 65536, True, 1.5):
            with self.assertRaises(ValueError):protocol.profile_save_request(value)

    def test_backup_precedes_write_and_full_mapping_is_preserved(self):
        before = bytes(self.device.mapping)
        old_write = self.device.write_lighting
        def write(profile, blob):
            backups = list(Path(self.tmp.name).glob('profile-*.json'))
            self.assertEqual(len(backups), 1)
            self.assertEqual(bytes.fromhex(json.loads(backups[0].read_text())['mapping']), before)
            old_write(profile, blob)
        with patch.object(self.device, 'write_lighting', side_effect=write), \
             patch('flydigi_control.persistence.secrets.randbelow', return_value=20):
            backup = self.apply()
        self.assertTrue(backup.exists())
        self.assertEqual(self.device.versions, (10, 21, 30, 40))
        self.assertEqual(self.device.mapping[:225], before[:225])
        self.assertEqual(self.device.mapping[227:], before[227:])
        self.assertEqual([w[0] for w in self.device.writes], ['lighting', 'save'])

    def test_no_write_if_backup_fails_or_format_unknown(self):
        with patch('flydigi_control.persistence._backup', side_effect=OSError('disk')):
            with self.assertRaises(OSError):self.apply()
        self.assertEqual(self.device.writes, [])
        self.device.mapping[1] = 4
        with self.assertRaises(ValueError):self.apply()
        self.assertEqual(self.device.writes, [])

    def test_changed_mapping_prevents_save(self):
        old_write = self.device.write_lighting
        def write(profile, blob):
            old_write(profile, blob)
            self.device.mapping[13] = 42
        with patch.object(self.device, 'write_lighting', side_effect=write):
            with self.assertRaisesRegex(RuntimeError, 'no save sent'):self.apply()
        self.assertEqual([w[0] for w in self.device.writes], ['lighting'])

    def test_lighting_mismatch_prevents_save(self):
        with patch.object(self.device, 'write_lighting'):
            with self.assertRaisesRegex(RuntimeError, 'verification failed'):self.apply()
        self.assertEqual(self.device.writes, [])

    def test_lost_ack_with_verified_save_does_not_repeat_write(self):
        self.device.save_timeout = True
        self.apply()
        self.assertEqual(sum(w[0] == 'save' for w in self.device.writes), 1)

    def test_lost_ack_and_unconfirmed_save_fails_without_replay(self):
        self.device.save_timeout = self.device.ignore_save = True
        with self.assertRaisesRegex(RuntimeError, 'not confirmed'):self.apply()
        self.assertEqual(sum(w[0] == 'save' for w in self.device.writes), 1)

    def test_profile_change_before_save_is_rejected(self):
        old_write = self.device.write_lighting
        def write(profile, blob):
            old_write(profile, blob)
            self.device.profile = 2
        with patch.object(self.device, 'write_lighting', side_effect=write):
            with self.assertRaises(RuntimeError):self.apply()
        self.assertEqual([w[0] for w in self.device.writes], ['lighting'])

    def test_save_that_changes_other_settings_is_reported_without_another_write(self):
        exchange = self.device.exchange
        def save(packet, timeout):
            exchange(packet, timeout)
            self.device.mapping[13] = 42
        with patch.object(self.device, 'exchange', side_effect=save):
            with self.assertRaisesRegex(RuntimeError, 'Profile differs'):self.apply()
        self.assertEqual([w[0] for w in self.device.writes], ['lighting', 'save'])

    def test_unknown_or_switch_profile_rejected(self):
        for profile in (4, 7, 8, 255):
            reply = bytearray(32)
            reply[:3] = bytes.fromhex('5a a5 a1')
            reply[5] = profile
            with self.assertRaises(ValueError):protocol.profile_state(reply)

    def test_mapping_chunks_can_arrive_out_of_order(self):
        d = ConfigurationDevice('unused')
        d.fd = 9
        def reply(index, value):
            return bytes([0x5a, 0xa5, 0xa3, 2, index, 1]) + bytes([value])*20 + bytes(6)
        with patch.object(d, 'profile_state', return_value=(1, (1,2,3,4))), \
             patch.object(d, 'send'), patch.object(d, '_read', side_effect=[[], [reply(1, 8), reply(0, 7)]]), \
             patch('select.select'):
            self.assertEqual(d.read_mapping(1), bytes([7])*20 + bytes([8])*20)

    def test_wrong_profile_reply_is_rejected(self):
        d = ConfigurationDevice('unused')
        d.fd = 9
        reply = bytes([0x5a, 0xa5, 0xa3, 1, 0, 2]) + bytes(26)
        with patch.object(d, 'profile_state', return_value=(1, (1,2,3,4))), \
             patch.object(d, 'send'), patch.object(d, '_read', side_effect=[[], [reply]]), \
             patch('select.select'):
            with self.assertRaises(ValueError):d.read_mapping(1)

    def test_stick_save_preserves_lighting_and_unrelated_mapping_bytes(self):
        original = bytes(self.device.mapping)
        lights = self.device.lighting
        apply_stick_shape(self.device, original, 1, 1, self.tmp.name)
        expected = bytearray(original)
        expected[812] = 1
        expected[225:227] = self.device.mapping[225:227]
        self.assertEqual(self.device.mapping, expected)
        self.assertEqual(self.device.lighting, lights)
        self.assertEqual([w[0] for w in self.device.writes], ['mapping', 'save'])

    def test_stale_ui_snapshot_never_overwrites_another_app_change(self):
        original = bytes(self.device.mapping)
        self.device.mapping[100] = 1
        with self.assertRaisesRegex(RuntimeError, 'read them again'):
            apply_stick_shape(self.device, original, 1, 1, self.tmp.name)
        self.assertEqual(self.device.writes, [])

    def test_curve_save_verifies_complete_mapping_and_preserves_lighting(self):
        from flydigi_control.curves import preset, with_curve
        original, lights = bytes(self.device.mapping), self.device.lighting
        curve = preset(2)
        expected = bytearray(with_curve(original,0,curve))
        apply_stick_curve(self.device,original,0,curve,self.tmp.name)
        expected[225:227] = self.device.mapping[225:227]
        self.assertEqual(self.device.mapping, expected)
        self.assertEqual(self.device.lighting,lights)
        self.assertEqual([w[0] for w in self.device.writes],['mapping','save'])

    def test_identical_mapping_on_a_different_active_profile_is_not_edited(self):
        original=bytes(self.device.mapping)
        with self.assertRaisesRegex(RuntimeError,'Active profile changed'):
            apply_mapping_edit(self.device,original,lambda value:value,self.tmp.name,expected_profile=0)
        self.assertEqual(self.device.writes,[])
        self.assertEqual(list(Path(self.tmp.name).iterdir()),[])
