import threading
import unittest
from unittest.mock import Mock, patch
from flydigi_control.protocol import rumble_motors
from flydigi_control.motors import pulse
from flydigi_control.transport import ConfigurationDevice


class MotorTests(unittest.TestCase):
    def test_wire_packet_matches_vendor_and_sdl_with_independent_levels(self):
        self.assertEqual(rumble_motors(17, 33, 65, 129),
                         bytes.fromhex('5a a5 12 06 11 21 41 81 00') + bytes(23))
        device = ConfigurationDevice('unused')
        device.fd = 9
        with patch('os.write', return_value=33) as write:
            device.send(rumble_motors(1, 2, 3, 4))
            self.assertEqual(write.call_args.args[1], b'\0' + rumble_motors(1, 2, 3, 4))
            bad = bytearray(rumble_motors(1, 2, 3, 4))
            bad[8] = 1
            with self.assertRaises(ValueError):device.send(bytes(bad))
            self.assertEqual(write.call_count, 1)

    def test_pulse_checks_identity_then_sends_start_and_stop_without_save(self):
        device, cancel = Mock(), Mock()
        cancel.is_set.return_value = False
        pulse(device, (1, 2, 3, 4), cancel)
        self.assertEqual([call[0] for call in device.mock_calls], ['info', 'send', 'send'])
        self.assertEqual(device.send.call_args_list[0].args[0], rumble_motors(1, 2, 3, 4))
        self.assertEqual(device.send.call_args_list[1].args[0], rumble_motors(0, 0, 0, 0))
        cancel.wait.assert_called_once_with(0.5)

    def test_partial_start_still_attempts_stop(self):
        device = Mock()
        device.send.side_effect = [OSError('short write'), None]
        with self.assertRaisesRegex(OSError, 'short write'):
            pulse(device, (1, 0, 0, 0), threading.Event())
        self.assertEqual(device.send.call_count, 2)
        self.assertEqual(device.send.call_args.args[0], rumble_motors(0, 0, 0, 0))

    def test_cancel_or_wrong_identity_prevents_start(self):
        device = Mock()
        cancel = threading.Event()
        cancel.set()
        pulse(device, (1, 2, 3, 4), cancel)
        device.send.assert_not_called()
        cancel.clear()
        device.info.side_effect = ValueError('wrong device')
        with self.assertRaises(ValueError):pulse(device, (1, 2, 3, 4), cancel)
        device.send.assert_not_called()

    def test_stop_failure_is_reported(self):
        device, cancel = Mock(), Mock()
        cancel.is_set.return_value = False
        device.send.side_effect = [None, OSError('unplugged')]
        with self.assertRaisesRegex(OSError, 'unplugged'):pulse(device, (1, 2, 3, 4), cancel)

    def test_invalid_levels_and_unbounded_duration_send_nothing(self):
        device = Mock()
        for levels in ((-1,0,0,0),(0,256,0,0),(0,0,True,0),(0,0,0,1.2)):
            with self.assertRaises(ValueError):pulse(device, levels, threading.Event())
        for duration in (0, -1, 2, float('nan')):
            with self.assertRaises(ValueError):pulse(device, (0,0,0,0), threading.Event(), duration)
        device.info.assert_not_called()
        device.send.assert_not_called()
