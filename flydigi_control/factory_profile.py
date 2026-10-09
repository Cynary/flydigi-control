"""Restore the active PC profile from verified Vader 5 factory settings."""
from copy import deepcopy
from importlib.resources import files
import json

from .lighting import validate_blob
from .macro_bank import decode_bank
from .profile_restore import restore_data


def source_for(current):
    """Prepare an ordinary restore snapshot; this function never writes hardware.

    Match the captured controller's exact geometry. Do not write the extra FF
    padding emitted by the SDK or infer defaults for other models/firmware.
    """
    try:
        identity = current['identity']
        if identity['device_id'] != 130 or identity['firmware'] != '7.1.5.0':
            raise ValueError('Factory profile defaults require Vader 5 Pro firmware 7.1.5.0')
        profile = current['profile']
        if type(profile) is not int or not 0 <= profile <= 3:
            raise ValueError('Choose PC profile 1–4')
        live = bytes.fromhex(current['mapping'])
        if len(live) != 840 or live[:3] != bytes.fromhex('02034d'):
            raise ValueError('Unrecognized mapping geometry; factory restore is unavailable')
        lighting = bytes.fromhex(current['lighting'])
        if len(lighting) != 320 or validate_blob(lighting) != (10,10):
            raise ValueError('Unrecognized lighting geometry; factory restore is unavailable')
        decode_bank(bytes.fromhex(current['macros']))
        presets = json.loads(files('flydigi_control').joinpath('factory_vader5.json').read_text())
        preset = presets['profiles'][profile]
        mapping = bytearray.fromhex(preset['mapping'])
        # The guarded save creates a fresh version. Do not copy the factory
        # version sentinel into an otherwise compatible restore snapshot.
        mapping[225:227] = live[225:227]
        source = deepcopy(current)
        source.update(mapping=mapping.hex(), lighting=preset['lighting'],
                      macros=(bytes.fromhex('00010000')+bytes([255])*1616).hex())
        restore_data(source,current)  # Share compatibility checks with backup restoration.
        return source
    except (KeyError, TypeError, IndexError, AttributeError) as error:
        raise ValueError('Read a complete active-profile snapshot before restoring defaults') from error
