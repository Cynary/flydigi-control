import logging
from logging.handlers import RotatingFileHandler
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from flydigi_control.app_logging import create_handler


class LoggingTests(unittest.TestCase):
    def test_writable_xdg_state_uses_bounded_file(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict('os.environ', XDG_STATE_HOME=folder):
            handler = create_handler()
            try:
                self.assertIsInstance(handler, RotatingFileHandler)
                self.assertEqual(handler.maxBytes, 256*1024)
                self.assertEqual(handler.backupCount, 2)
                self.assertEqual(Path(handler.baseFilename), Path(folder)/'flydigi-control/app.log')
            finally:
                handler.close()

    def test_unusable_state_path_does_not_block_startup(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder)/'not-a-directory'
            state.write_text('occupied')
            with patch.dict('os.environ', XDG_STATE_HOME=str(state)), patch('sys.stderr'):
                handler = create_handler()
            self.assertIsInstance(handler, logging.StreamHandler)
            self.assertNotIsInstance(handler, RotatingFileHandler)
            handler.close()
