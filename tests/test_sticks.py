import unittest
from unittest.mock import patch

from flydigi_control.sticks import read_sticks, with_shape
from flydigi_control.transport import ConfigurationDevice
from flydigi_control import protocol


def profile():
    data = bytearray((i % 251 for i in range(840)))
    data[:3] = bytes([2, 3, 77])
    data[800] = data[812] = 0
    return bytes(data)


class StickTests(unittest.TestCase):
    def test_shape_changes_one_byte_and_preserves_everything_else(self):
        original = profile()
        for side, offset in ((0, 800), (1, 812)):
            updated = with_shape(original, side, 1)
            self.assertEqual([i for i in range(840) if original[i] != updated[i]], [offset])
            self.assertEqual(read_sticks(updated)[side]['shape'], 1)
            self.assertEqual(read_sticks(updated)[1-side]['shape'], 0)

    def test_invalid_selections_and_unknown_format_rejected(self):
        for side, shape in ((2, 0), (0, -1), (True, 1), (0, True)):
            with self.assertRaises(ValueError):with_shape(profile(), side, shape)
        for data in (profile()[:800], bytes([0, 4])+profile()[2:]):
            with self.assertRaises(ValueError):read_sticks(data)

    def test_partial_write_uses_absolute_start_and_relative_data_index(self):
        original = profile()
        updated = with_shape(original, 1, 1)
        device = ConfigurationDevice('unused')
        with patch.object(device, 'read_mapping', return_value=original), \
             patch.object(device, 'profile_state', return_value=(2, (1,2,3,4))), \
             patch.object(device, 'exchange') as exchange:
            device.write_mapping(2, original, updated)
            packets = [c.args[0] for c in exchange.call_args_list]
        self.assertEqual(packets[0][:9], bytes.fromhex('5a a5 a4 06 02 28 01 14 e9'))
        self.assertEqual(packets[1], protocol.mapping_write_pack(0, updated[800:820]))
        self.assertEqual(len(packets), 2)

    def test_stale_mapping_and_profile_switch_refuse_writes(self):
        original = profile()
        updated = with_shape(original, 1, 1)
        device = ConfigurationDevice('unused')
        with patch.object(device, 'read_mapping', return_value=updated), patch.object(device, 'exchange') as send:
            with self.assertRaises(RuntimeError):device.write_mapping(0, original, updated)
            send.assert_not_called()
        with patch.object(device, 'read_mapping', return_value=original), \
             patch.object(device, 'profile_state', return_value=(1, (1,2,3,4))), patch.object(device, 'exchange') as send:
            with self.assertRaises(RuntimeError):device.write_mapping(0, original, updated)
            send.assert_not_called()
