import math
import unittest
from unittest.mock import patch
from flydigi_control.diagnostics import Circularity, normalize_axis, monitor_analog


class DiagnosticTests(unittest.TestCase):
    def test_center_is_not_a_circularity_measurement(self):
        c = Circularity()
        c.add(.1, .1)
        self.assertEqual(c.snapshot()['coverage'], 0)
        self.assertIsNone(c.snapshot()['error_percent'])

    def test_circle_coverage_and_rms(self):
        c = Circularity()
        for i in range(32):
            angle = i*math.pi/16
            c.add(math.cos(angle)*.9, math.sin(angle)*.9)
        self.assertEqual(c.snapshot()['coverage'], 32)
        self.assertAlmostEqual(c.snapshot()['error_percent'], 10)
        c.add(.2, 0)  # returning to the center must not erase the perimeter
        self.assertAlmostEqual(c.snapshot()['error_percent'], 10)

    def test_square_has_expected_diagonal_overtravel(self):
        c = Circularity()
        c.add(1, 1)
        self.assertAlmostEqual(c.snapshot()['error_percent'], (math.sqrt(2)-1)*100)
        self.assertEqual(c.snapshot()['coverage'], 1)

    def test_axis_endpoints_are_symmetric(self):
        self.assertEqual(normalize_axis(-32768), -1)
        self.assertEqual(normalize_axis(32767), 1)
        self.assertEqual(normalize_axis(0), 0)

    def test_capture_is_read_only_and_closes_fd(self):
        raw = bytes.fromhex('5aa5ef') + bytes(29)
        clock = iter(i*.02 for i in range(100))
        samples = []
        with patch('flydigi_control.diagnostics.discover', return_value=[{'path':'/dev/test'}]), \
             patch('os.open', return_value=9) as opened, patch('os.read', return_value=raw), \
             patch('os.close') as closed, patch('os.write') as write, \
             patch('select.select', return_value=([9],[],[])), \
             patch('time.monotonic', side_effect=lambda: next(clock)):
            monitor_analog('/dev/test', .15, samples.append)
        self.assertGreater(len(samples), 0)
        self.assertEqual(opened.call_args.args[1] & 3, 0)
        write.assert_not_called()
        closed.assert_called_once_with(9)
