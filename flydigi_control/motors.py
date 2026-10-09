"""Short, cancellable hardware motor tests, independent of Steam's mappings."""
from .protocol import rumble_motors


def pulse(device, levels, cancel, duration=0.5):
    """The caller owns the configuration lock. Does not acquire native input.

    The controller protocol has no pulse duration, so always send zero after a
    start attempt. A disconnected USB device can prevent that stop from being
    delivered; report the error rather than claim the motors have stopped.
    """
    if not 0 < duration <= 1:
        raise ValueError('Motor tests must last at most one second')
    packet = rumble_motors(*levels)
    device.info()  # Verify Vader identity before issuing vibration commands.
    if cancel.is_set():
        return
    try:
        device.send(packet)
        cancel.wait(duration)
    finally:
        device.send(rumble_motors(0, 0, 0, 0))
