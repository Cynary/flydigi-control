"""Passive analog measurements, independent of the GUI and input ownership."""
import math
import os
import select
import time
from .protocol import parse_input, strip_report_id
from .transport import discover


class Circularity:
    """32 angular sectors, maximum observed radius, RMS error from radius 1.

    This matches the official app's metric. Coverage is reported separately:
    one point on the perimeter is not evidence of a good full circle.
    """
    def __init__(self):
        self.radii = {}

    def add(self, x, y):
        radius = math.hypot(x, y)
        if radius <= .2:
            return
        angle = math.atan2(y, x)
        sector = math.floor(angle / (math.pi / 16) + .5) % 32
        self.radii[sector] = max(self.radii.get(sector, 0), radius)

    def snapshot(self):
        values = self.radii.values()
        error = math.sqrt(sum((1-v)**2 for v in values) / len(values))*100 if values else None
        return {'radii': dict(self.radii), 'coverage': len(values), 'error_percent': error}


def normalize_axis(value):
    return value / (32768 if value < 0 else 32767)


def monitor_analog(path, seconds, emit):
    if not 0 < seconds <= 600:
        raise ValueError('Choose a duration between 0 and 600 seconds')
    if path not in {d['path'] for d in discover()}:
        raise ValueError('Choose a connected Vader 5 Pro interface')
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
    start = time.monotonic()
    rate_start, rate_count, rate = start, 0, 0.0
    last_emit, last_input = start - 1, start
    circles = [Circularity(), Circularity()]
    try:
        while (remaining := start + seconds - time.monotonic()) > 0:
            if not select.select([fd], [], [], min(remaining, .2))[0]:
                if time.monotonic() - last_input > 3:
                    raise RuntimeError('Native reports stopped. Check the controller connection and Native Steam Input.')
                continue
            try:
                raw = os.read(fd, 64)
            except BlockingIOError:
                continue
            if not raw:
                raise OSError('Controller disconnected')
            state = parse_input(strip_report_id(raw))
            if state is None:
                continue
            now = time.monotonic()
            last_input = now
            rate_count += 1
            if now - rate_start >= 1:
                rate = rate_count / (now - rate_start)
                rate_start, rate_count = now, 0
            sticks = [tuple(normalize_axis(v) for v in pair)
                      for pair in (state.left_stick, state.right_stick)]
            for circle, (x, y) in zip(circles, sticks):
                circle.add(x, y)
            # Preserve every sample in the measurement; throttle only GUI updates.
            if now - last_emit >= 1/30:
                emit({'sticks': sticks, 'triggers': [state.left_trigger/255, state.right_trigger/255],
                      'gyro': state.gyro_dps, 'accel': state.accel_g,
                      'buttons': sorted(state.buttons), 'reports_per_second': rate,
                      'remaining': max(0, math.ceil(start + seconds - now)),
                      'circles': [c.snapshot() for c in circles]})
                last_emit = now
    finally:
        os.close(fd)
