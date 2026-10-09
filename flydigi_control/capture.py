"""Passive report capture for checking physical buttons against Steam Input.

This opens a second read-only hidraw fd. It never enables test mode or claims
input ownership. Run while Steam is using its native Flydigi input interface.
"""
import json
import os
import select
import time
from . import protocol
from .transport import discover


def monitor(path, seconds, output):
    if not 0 < seconds <= 600:
        raise ValueError('Capture duration must be greater than zero and at most 600 seconds')
    if path not in {d['path'] for d in discover()}:
        raise ValueError('Choose a connected Vader 5 Pro interface')
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
    start = time.monotonic()
    end = start + seconds
    previous = None
    seen = set()
    reports = 0
    def emit(value):
        output.write(json.dumps(value) + '\n')
        output.flush()
    try:
        emit({'event': 'start', 'device': path, 'seconds': seconds, 'mode': 'passive'})
        while (remaining := end - time.monotonic()) > 0:
            if not select.select([fd], [], [], remaining)[0]:
                break
            try:
                data = os.read(fd, 64)
            except BlockingIOError:
                continue
            if not data:
                raise OSError('Controller disconnected')
            data = protocol.strip_report_id(data)
            state = protocol.parse_input(data)
            if state:
                reports += 1
                seen.update(state.buttons)
                if state.buttons != previous:
                    emit({'event': 'buttons', 'time_ms': round((time.monotonic() - start) * 1000, 3),
                          'pressed': sorted(state.buttons), 'raw': data.hex(),
                          'unknown_bits': state.unknown_bits})
                    previous = state.buttons
        emit({'event': 'summary', 'reports': reports, 'buttons_seen': sorted(seen),
              'buttons_not_seen': sorted(set(protocol.BUTTON_NAMES) - seen)})
    finally:
        os.close(fd)
