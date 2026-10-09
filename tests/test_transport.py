import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from flydigi_control import protocol
from flydigi_control.transport import ConfigurationDevice, discover


class ProtocolTests(unittest.TestCase):
    def test_every_button_is_independent(self):
        for offset, mask, name in protocol.BUTTON_BITS:
            packet = bytearray(32)
            packet[:3] = b'\x5a\xa5\xef'
            packet[offset] = mask
            self.assertEqual(protocol.parse_input(packet).buttons, frozenset([name]), name)
        self.assertTrue({'M1', 'M2', 'M3', 'M4', 'C', 'Z', 'LM', 'RM', 'FN', 'TURBO'}
                        <= set(protocol.BUTTON_NAMES))

    def test_lighting_write_has_zero_report_id(self):
        device = ConfigurationDevice('/dev/hidraw-test')
        device.fd = 9
        with patch('os.write', return_value=33) as write:
            device.send(protocol.led_test_color(0x12, 0x34, 0x56))
        output = write.call_args.args[1]
        self.assertEqual(output[:9], bytes.fromhex('00 5a a5 f5 05 12 34 56 96'))
        self.assertEqual(len(output), 33)

    def test_color_write_does_not_require_an_ack(self):
        device = ConfigurationDevice('unused')
        with patch.object(device, 'info') as info, \
             patch.object(device, 'send') as send, \
             patch.object(device, 'exchange') as exchange:
            device.set_color(12, 34, 56)
            info.assert_called_once()
            send.assert_called_once_with(protocol.led_test_color(12, 34, 56))
            exchange.assert_not_called()

    def test_input_mode_and_firmware_commands_are_rejected(self):
        device = ConfigurationDevice('/dev/hidraw-test')
        with patch('os.write') as write:
            for cmd in (0x11, 0x1c, 0xa6, 0x1f, 0xfd, 0xfe):
                with self.assertRaises(ValueError):
                    device.send(protocol.command(cmd, 2))
            write.assert_not_called()

    def test_out_of_range_colors_are_rejected_before_io(self):
        device = ConfigurationDevice('/dev/hidraw-test')
        with patch.object(device, 'info') as info:
            for color in ((-1, 0, 0), (0, 256, 0), (0, 0, 1.5)):
                with self.assertRaises(ValueError):
                    device.set_color(*color)
            info.assert_not_called()

    def test_partial_write_is_an_error(self):
        with patch('os.write', return_value=3):
            with self.assertRaises(OSError):
                ConfigurationDevice('unused').send(protocol.info_request())

    def test_unrelated_reports_are_not_accepted_as_ack(self):
        device = ConfigurationDevice('unused')
        device.fd = 4
        ack = bytearray(32)
        ack[:5] = b'\x5a\xa5\x01\x01\x00'
        ack[31] = sum(ack[2:31]) & 255
        with patch.object(device, 'send'), patch.object(device, '_read', side_effect=[
            [], [b'\x5a\xa5\xef\x00\x00', b'\x5a\xa5\x01\x01\x00'], [bytes(ack)]
        ]), patch('select.select'):
            self.assertEqual(device.exchange(protocol.info_request()),
                             bytes(ack))
            self.assertTrue(device.last_reply_checksum_matches)

    def test_recorded_wireless_identity_has_a_different_trailer(self):
        # Public Tux InVader fixture, firmware-7.1.4.0-wireless.json,
        # GPL-3.0; source and commit recorded in THIRD_PARTY.md.
        reply = bytes.fromhex('5aa50101008202000000000445010071400467351500000000000010261f0020')
        device = ConfigurationDevice('unused')
        device.fd = 4
        with patch.object(device, 'send'), patch.object(device, '_read', side_effect=[[], [reply]]), \
             patch('select.select'):
            info = device.info()
        self.assertEqual(info.device_id, 130)
        self.assertEqual(info.firmware, '7.1.4.0')
        self.assertFalse(device.last_reply_checksum_matches)

    def test_feature_write_requires_capability_and_readback(self):
        device = ConfigurationDevice('unused')
        with patch.object(device, 'info'), patch.object(device, 'features', side_effect=[
            {'turbo': {'supported': True, 'enabled': False}},
            {'turbo': {'supported': True, 'enabled': True}}
        ]), patch.object(device, 'exchange') as exchange:
            device.set_feature('turbo', True)
            self.assertEqual(exchange.call_args.args[0][:7], bytes.fromhex('5a a5 13 04 04 01 1c'))
        with patch.object(device, 'info'), patch.object(device, 'features', return_value={
            'turbo': {'supported': False, 'enabled': False}
        }), patch.object(device, 'exchange') as exchange:
            with self.assertRaises(ValueError):
                device.set_feature('turbo', True)
            exchange.assert_not_called()

    def test_mapping_permission_preserves_other_stream_flags(self):
        device = ConfigurationDevice('unused')
        with patch.object(device, 'info'), patch.object(device, 'exchange') as exchange, \
             patch.object(device, 'mapping_status', return_value={'third_party_control': True}):
            device.set_third_party_control(True)
            self.assertEqual(exchange.call_args.args[0][2:9],
                             bytes([0x11, 7, 255, 255, 255, 255, 1]))
        with patch('os.write') as write:
            for values in ((1, 255, 255, 255, 1), (255, 0, 255, 255, 1), (255, 255, 255, 255, 2)):
                with self.assertRaises(ValueError):
                    device.send(protocol.request(0x11, *values))
            write.assert_not_called()

    def test_read_timeout_uses_alternate_query_once(self):
        device = ConfigurationDevice('unused')
        wanted = protocol.info_request()
        with patch.object(device, '_exchange_once', side_effect=[TimeoutError(), b'primer', b'reply']) as once:
            self.assertEqual(device.exchange(wanted), b'reply')
            self.assertEqual([c.args[0] for c in once.call_args_list],
                             [wanted, protocol.request(3), wanted])
        with patch.object(device, '_exchange_once', side_effect=TimeoutError()) as once:
            with self.assertRaises(TimeoutError):
                device.exchange(wanted)
            self.assertEqual(once.call_count, 3)
        with patch.object(device, '_exchange_once', side_effect=TimeoutError()) as once:
            with self.assertRaises(TimeoutError):
                device.exchange(protocol.request(0x13, 4, 1))
            self.assertEqual(once.call_count, 1)

    def test_missing_mapping_ack_requires_successful_readback(self):
        device = ConfigurationDevice('unused')
        with patch.object(device, 'info'), patch.object(device, 'exchange', side_effect=TimeoutError()), \
             patch.object(device, 'mapping_status', return_value={'third_party_control': True}):
            device.set_third_party_control(True)
        with patch.object(device, 'info'), patch.object(device, 'exchange', side_effect=TimeoutError()), \
             patch.object(device, 'mapping_status', return_value={'third_party_control': False}):
            with self.assertRaises(RuntimeError):device.set_third_party_control(True)

    def test_other_feature_writes_rejected(self):
        with patch('os.write') as write:
            with self.assertRaises(ValueError):
                ConfigurationDevice('unused').send(protocol.request(0x13, 7, 1))
            write.assert_not_called()


class DiscoveryTests(unittest.TestCase):
    def test_only_matching_interface_and_wake_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            sysfs = Path(tmp)
            usb = sysfs / 'devices/usb3/3-4'
            hid = usb / '3-4:1.1/0003:37D7:2401.000A'
            hid.mkdir(parents=True)
            (usb / 'idVendor').write_text('37d7')
            (usb / 'power').mkdir()
            (usb / 'power/wakeup').write_text('disabled\n')
            (usb / 'descriptors').write_bytes(bytes([9, 2, 9, 0, 1, 1, 0, 0xa0, 50]))
            (hid / 'uevent').write_text('HID_ID=0003:000037D7:00002401\nHID_NAME=Flydigi\n')
            (hid / 'report_descriptor').write_bytes(b'\x06\xa0\xff')
            node = sysfs / 'class/hidraw/hidraw8'
            node.mkdir(parents=True)
            (node / 'device').symlink_to(hid)
            devices = discover(sysfs)
            self.assertEqual(len(devices), 1)
            self.assertTrue(devices[0]['remote_wake_advertised'])
            self.assertEqual(devices[0]['wake_chain'], [{'device': '3-4', 'wakeup': 'disabled'}])
            (usb / 'descriptors').write_bytes(bytes([9, 2, 9, 0, 1, 1, 0, 0x80, 50]))
            self.assertFalse(discover(sysfs)[0]['remote_wake_advertised'])
            (hid / 'uevent').write_text('HID_ID=0003:000037D7:00002402\n')
            self.assertEqual(discover(sysfs), [])


if __name__ == '__main__':
    unittest.main()
