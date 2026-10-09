"""Onboard gyro-to-stick fields; PC-generated mouse input is separate."""
from .persistence import _mapping_version
from .button_mappings import BUTTONS

TARGETS = ((0, 'Off'), (1, 'Left stick · racing'), (2, 'Right stick · aiming'))
ACTIVATION = ((0, 'Press to enable / press to disable'), (1, 'Hold to enable'))
KEYS = tuple(enumerate(BUTTONS)) + ((24,'Fn'),(25,'Turbo'),(27,'Home'),(255,'None'))


def read_motion(mapping):
    _mapping_version(mapping)
    target, key, activation, deadzone, sx, sy, mode, second = mapping[137:145]
    if target == 3:
        raise ValueError('Gyro-to-mouse uses PC-side settings; this editor preserves it unchanged')
    if target not in dict(TARGETS) or activation not in dict(ACTIVATION) or mode not in (0,1):
        raise ValueError('Unknown motion mapping mode; editing is disabled')
    if key not in dict(KEYS) or second not in dict(KEYS):
        raise ValueError('Unknown motion activation button; editing is disabled')
    if not 0 <= deadzone <= 100 or not 0 <= max(sx,sy) <= 100:
        raise ValueError('Unknown motion sensitivity or deadzone compensation; editing is disabled')
    return dict(target=target,key=key,activation=activation,deadzone=deadzone,
                sensitivity=max(sx,sy),second=second,mode=mode,
                raw_sensitivity=(sx,sy),smoothness=tuple(mapping[830:836]) if mapping[0]>=1 else None)


def with_motion(mapping, *, target, key, activation, deadzone, sensitivity, second):
    current=read_motion(mapping)
    for value,options,name in ((target,dict(TARGETS),'output'),(key,dict(KEYS),'activation button'),
                              (activation,dict(ACTIVATION),'activation mode'),(second,dict(KEYS),'second button')):
        if type(value) is not int or value not in options:
            raise ValueError(f'Unknown motion {name}')
    for value,name in ((deadzone,'Deadzone compensation'),(sensitivity,'Sensitivity')):
        if type(value) is not int or not 0 <= value <= 100:
            raise ValueError(f'{name} must be between 0 and 100')
    if target and key==255:
        raise ValueError('Choose an activation button before enabling motion mapping')
    if target and activation==1 and second!=255 and key==second:
        raise ValueError('The two activation buttons must differ')
    if activation==0 and second!=current['second']:
        raise ValueError('The second button is only editable in hold mode')
    updated=bytearray(mapping)
    updated[137]=target
    if not target:
        return bytes(updated)  # Turning off preserves the last configured values.
    updated[138]=key
    updated[139]=activation
    updated[140]=deadzone
    # The SDK reads max(X,Y) and writes both axes. Avoid silently replacing an
    # asymmetric existing configuration just because another field changed.
    if sensitivity!=current['sensitivity']:
        updated[141:143]=bytes([sensitivity,sensitivity])
    # Matches the official UI: left stick selects racing, right selects FPS.
    updated[143]=1 if target==1 else 0
    if activation==1:
        updated[144]=second
    return bytes(updated)
