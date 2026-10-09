"""Vader trigger travel and vibration fields in mapping formats 3.0–3.2.

Only named fields are edited. In particular, do not rebuild the adjacent APEX
force-feedback or micro-trigger records when configuring a Vader 5 Pro.
"""
from .persistence import _mapping_version


def _side(mapping, side):
    _mapping_version(mapping)
    if type(side) is not int or side not in (0, 1):
        raise ValueError('Choose left or right')


def _flag(value, off):
    if value not in (0, off):
        raise ValueError('Unknown firmware enable flag; no settings were changed')
    return value == 0


def _int(value, lo, hi, name):
    if type(value) is not int or not lo <= value <= hi:
        raise ValueError(f'{name} must be an integer between {lo} and {hi}')


def _bool(value):
    if type(value) is not bool:
        raise ValueError('Enable settings must be true or false')


def read_grip(mapping, side):
    _side(mapping, side)
    base = 146 + 4*side
    return dict(master_enabled=_flag(mapping[145],255), enabled=_flag(mapping[base],255),
                strength=mapping[base+3], minimum=min(mapping[base+1:base+3]),
                maximum=max(mapping[base+1:base+3]))


def with_grip(mapping, side, *, master_enabled, enabled, strength):
    read_grip(mapping,side)
    _bool(master_enabled);_bool(enabled)
    _int(strength,1,100,'Strength')
    base = 146 + 4*side
    updated = bytearray(mapping)
    updated[145] = 0 if master_enabled else 255
    updated[base] = 0 if enabled else 255
    updated[base+3] = strength
    return bytes(updated)


def read_trigger(mapping, side):
    _side(mapping, side)
    travel, motor = 123 + 7*side, 154 + 14*side
    return dict(start=mapping[travel+1], end=mapping[travel+6],
                enabled=_flag(mapping[154],1),
                minimum=(mapping[motor+2]*100 + 254)//255,
                maximum=(mapping[motor+3]*100 + 254)//255,
                threshold=mapping[motor+4], strength=mapping[motor+6])


def with_trigger(mapping, side, *, start, end, enabled, minimum, maximum, threshold, strength):
    current = read_trigger(mapping,side)
    _bool(enabled)
    for value, lo, hi, name in ((start,0,255,'Start'),(end,0,255,'End'),
            (minimum,1,100,'Minimum amplitude'),(maximum,1,100,'Maximum amplitude'),
            (threshold,1,255,'Vibration threshold'),(strength,1,100,'Strength')):
        _int(value,lo,hi,name)
    if start >= end:
        raise ValueError('Trigger start must be below its end')
    if minimum > maximum:
        raise ValueError('Minimum amplitude must not exceed maximum')
    travel, motor = 123 + 7*side, 154 + 14*side
    updated = bytearray(mapping)
    # The official service sets both endpoint coordinates with the travel
    # bounds. Preserve the existing point bytes if travel was not edited.
    if start != current['start'] or end != current['end']:
        updated[travel+1:travel+7] = bytes([start,start,start,end,end,end])
    updated[154] = 0 if enabled else 1  # One shared enable flag for both sides.
    # Percent conversion loses precision. Do not quantize untouched fields
    # when saving an unrelated setting such as the vibration threshold.
    if minimum != current['minimum']:
        updated[motor+2] = minimum*255//100
    if maximum != current['maximum']:
        updated[motor+3] = maximum*255//100
    updated[motor+4] = threshold
    updated[motor+6] = strength
    return bytes(updated)
