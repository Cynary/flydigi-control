import io
import json
import os
import unittest
from unittest.mock import patch
from flydigi_control.capture import monitor


class CaptureTests(unittest.TestCase):
    def test_capture_observes_without_changing_input_mode(self):
        report = bytearray(32)
        report[:3] = b'\x5a\xa5\xef'
        report[13] = 4
        output = io.StringIO()
        with patch('flydigi_control.capture.discover', return_value=[{'path': '/dev/hidraw8'}]), \
             patch('os.open', return_value=8) as opened, \
             patch('os.read', return_value=bytes(report)), patch('os.close') as closed, \
             patch('os.write') as written, patch('select.select', return_value=([8], [], [])), \
             patch('time.monotonic', side_effect=[0, 0.1, 0.2, 2]):
            monitor('/dev/hidraw8', 1, output)
        events = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(events[1]['pressed'], ['M1'])
        self.assertEqual(events[-1]['reports'], 1)
        self.assertEqual(opened.call_args.args[1] & os.O_ACCMODE, os.O_RDONLY)
        written.assert_not_called()
        closed.assert_called_once_with(8)


if __name__ == '__main__':
    unittest.main()
