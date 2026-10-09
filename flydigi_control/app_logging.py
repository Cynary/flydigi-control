"""Bounded diagnostic logs; an unavailable state directory must not block startup."""
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path


def create_handler():
    folder = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'flydigi-control'
    try:
        folder.mkdir(parents=True, exist_ok=True)
        return RotatingFileHandler(folder / 'app.log', maxBytes=256*1024, backupCount=2)
    except OSError as error:
        handler = logging.StreamHandler()
        handler.handle(logging.LogRecord('flydigi-control', logging.WARNING, __file__, 0,
                                         'File logging unavailable: %s', (error,), None))
        return handler
