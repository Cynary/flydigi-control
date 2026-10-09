"""Vader stick response curves, checked against Space Station's settings UI.

The firmware stores nine samples at evenly spaced input positions, offset by
50, plus two control points for the editor. This module rebuilds only the chosen
stick's fields. Negative deadzone serialization needs a hardware comparison:
the vendor SDK reader and writer disagree, so those writes remain disabled.
"""
from dataclasses import dataclass
import math
from .sticks import read_sticks


@dataclass(frozen=True)
class Curve:
    kind: int = 0
    center: int = 0
    edge: int = 0
    point1: tuple[int, int] = (64, 64)
    point2: tuple[int, int] = (127, 127)

    def validate(self):
        if type(self.kind) is not int or self.kind not in range(4):
            raise ValueError('Unknown response curve')
        if any(type(v) is not int or not -100 <= v <= 100 for v in (self.center, self.edge)):
            raise ValueError('Center and edge must be between -100 and 100')
        if len(self.point1) != 2 or len(self.point2) != 2:
            raise ValueError('Each control point needs X and Y')
        if any(type(v) is not int or not 0 <= v <= 127 for v in (*self.point1, *self.point2)):
            raise ValueError('Curve point coordinates must be integers from 0 to 127')
        if self.point1[0] > self.point2[0]:
            raise ValueError('Point 1 must not be to the right of point 2')
        if self.center > 0 and self.edge > 0 and self.center + self.edge > 100:
            raise ValueError('Center and edge deadzones overlap')
        if self.center < 0 and self.edge < 0 and self.center + self.edge < -100:
            raise ValueError('Center and edge compensation overlap')


def preset(kind):
    if type(kind) is not int or kind not in (0, 1, 2):
        raise ValueError('Choose Default, Quick or Slow')
    return Curve(kind=kind, point1=(64, (64, 96, 32)[kind]))


def _round(value):
    # The vendor's JavaScript editor rounds a half towards positive infinity.
    return math.floor(value + .5)


def points(curve):
    curve.validate()
    start = (max(curve.center, 0), max(-curve.center, 0))
    end = (100 - max(curve.edge, 0), 100 + min(curve.edge, 0))
    controls = [tuple(_round(start[i] + (end[i] - start[i]) * p[i] / 127)
                      for i in range(2)) for p in (curve.point1, curve.point2)]
    return (start, *controls, end)


def samples(curve):
    vertices = points(curve)
    result = []
    for step in range(9):
        x = step * 12.5
        # A horizontal zero segment defines a deadzone; extrapolate the next
        # segment below it. Firmware receives negative samples for that region.
        first = 2 if vertices[1][1] == 0 else 1
        y = vertices[-1][1]
        if vertices[0][0] == vertices[1][0] == x and vertices[0][1] == 0:
            y = 0
        else:
            for index in range(first, len(vertices)):
                left, right = vertices[index-1:index+1]
                if x > right[0]:
                    continue
                if x == right[0] and index+1 < len(vertices) and vertices[index+1][0] == x and vertices[index+1][1] > right[1]:
                    y = vertices[index+1][1]
                elif left[0] == right[0]:
                    y = right[1] if left[1] == 0 and right[1] != 0 and x >= left[0] else left[1]
                else:
                    y = left[1] + (right[1]-left[1]) * (x-left[0]) / (right[0]-left[0])
                break
        result.append(min(100, max(-50, _round(y))) + 50)
    return tuple(result)


def with_curve(mapping, side, curve):
    read_sticks(mapping)
    curve.validate()
    if type(side) is not int or side not in (0, 1):
        raise ValueError('Choose left or right stick')
    if curve.center < 0 or curve.edge < 0:
        raise ValueError('Negative compensation can be previewed; its save encoding still needs hardware validation')
    base, extra = 109 + 7*side, 790 + 12*side
    if mapping[base+1] == 127:
        raise ValueError('This stick uses a non-joystick mapping; change its mapping before editing response')
    updated = bytearray(mapping)
    updated[base] = updated[extra] = curve.kind
    updated[base+1] = curve.center
    for offset, point in ((2, curve.point1), (4, curve.point2)):
        # SDK editor coordinates use 0..127. Its base format stores X after
        # applying the center offset, truncating the result to a byte.
        updated[base+offset] = int(curve.center * 127 / 100 + (100-curve.center) * point[0] / 100)
        updated[base+offset+1] = point[1]
    updated[extra+1:extra+10] = bytes(samples(curve))
    updated[extra+11] = curve.edge
    return bytes(updated)
