"""Stick fields in the Vader mapping format, without rebuilding the profile."""
from .persistence import _mapping_version


def read_sticks(mapping):
    _mapping_version(mapping)
    if mapping[0] < 1 or len(mapping) < 840:
        raise ValueError('Stick shape requires mapping format 3.1 or 3.2')
    result = []
    for side in range(2):
        base, extra = 109 + 7 * side, 790 + 12 * side
        shape = mapping[extra + 10]
        if shape not in (0, 1):
            raise ValueError('Unknown stick shape; no settings were changed')
        signed = lambda value: 127 - value if value > 127 else value
        result.append({
            'shape': shape, 'center': signed(mapping[base + 1]),
            'edge': signed(mapping[extra + 11]),
            'curve_type': mapping[base],
            'curve_points': tuple(mapping[extra + 1:extra + 10]),
        })
    return result


def with_shape(mapping, side, shape):
    read_sticks(mapping)
    if type(side) is not int or side not in (0, 1) or type(shape) is not int or shape not in (0, 1):
        raise ValueError('Choose left/right and rectangle/circle')
    updated = bytearray(mapping)
    updated[800 + 12 * side] = shape
    return bytes(updated)
