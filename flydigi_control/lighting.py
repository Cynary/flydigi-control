"""Vader 5 lighting configuration. See docs/LIGHTING.md for protocol evidence."""
PALETTE = [('Red', '#ff0000'), ('Yellow', '#ffff00'), ('Green', '#00ff00'),
           ('Cyan', '#00ffff'), ('Blue', '#0000ff'), ('Magenta', '#ff00ff')]
ORANGE = (255, 80, 5)
GRADIENT = ((0, 0, 100), (100, 0, 0), (0, 100, 0))


def validate_blob(blob):
    if len(blob) < 20 or blob[:2] != b'\x00\x03':
        raise ValueError('Unsupported lighting format')
    zones = blob[7]
    if not 1 <= zones <= 32 or (len(blob) - 20) % (zones * 3):
        raise ValueError('Invalid lighting geometry')
    frames = (len(blob) - 20) // (zones * 3)
    if not 2 <= frames <= 32:
        raise ValueError('Invalid animation frame count')
    return zones, frames


def make_blob(original, mode, colors, brightness, period):
    zones, frames = validate_blob(original)
    if mode not in (1, 2, 3, 5, 6) or not 0 <= brightness <= 100 or not 1 <= period <= 100:
        raise ValueError('Unsupported lighting setting')
    limit = min(5, frames // 2 if mode == 2 else frames)
    if mode not in (1, 6) and not (1 if mode != 3 else 2) <= len(colors) <= (1 if mode == 5 else limit):
        raise ValueError('Invalid number of colors for this effect')
    if any(len(c) != 3 or any(type(v) is not int or not 0 <= v <= 255 for v in c) for c in colors):
        raise ValueError('RGB channels must be integers from 0 to 255')
    blob = bytearray(original[:20]) + bytearray(len(original) - 20)
    blob[2:7] = bytes([0, 0, (len(colors)*2-1 if mode == 2 else len(colors)-1 if mode == 3 else 0), period, brightness])
    blob[8] = mode
    if mode == 1:
        if zones > 12 or frames != 10:
            raise ValueError('Flow preset needs 10 animation frames and at most 12 LED zones')
        blob[4] = frames - 1
        for frame, colors_in_frame in enumerate(FLOW):
            offset = 20 + frame * zones * 3
            blob[offset:offset+zones*3] = bytes(v for c in colors_in_frame[:zones] for v in c)
    elif mode != 6:
        for index, color in enumerate(colors):
            frame = index * 2 if mode == 2 else index
            offset = 20 + frame*zones*3
            blob[offset:offset+zones*3] = bytes(color)*zones
    return bytes(blob)

# Flow RGB frames observed in Space Station 4.2.0.9 (see docs/LIGHTING.md).
FLOW = (
    ((0, 128, 128), (0, 128, 128), (0, 128, 128), (0, 113, 142), (0, 96, 159), (0, 73, 182), (0, 43, 212), (0, 0, 255), (42, 0, 213), (73, 0, 182), (96, 0, 159), (113, 0, 142)),
    ((0, 182, 73), (0, 182, 73), (0, 182, 73), (0, 159, 96), (0, 142, 113), (0, 128, 128), (0, 113, 142), (0, 96, 159), (0, 73, 182), (0, 43, 212), (0, 0, 255), (42, 0, 213)),
    ((43, 212, 0), (43, 212, 0), (43, 212, 0), (0, 255, 0), (0, 213, 42), (0, 182, 73), (0, 159, 96), (0, 142, 113), (0, 128, 128), (0, 113, 142), (0, 96, 159), (0, 73, 182)),
    ((113, 142, 0), (113, 142, 0), (113, 142, 0), (96, 159, 0), (73, 182, 0), (43, 212, 0), (0, 255, 0), (0, 213, 42), (0, 182, 73), (0, 159, 96), (0, 142, 113), (0, 128, 128)),
    ((159, 96, 0), (159, 96, 0), (159, 96, 0), (142, 113, 0), (128, 128, 0), (113, 142, 0), (96, 159, 0), (73, 182, 0), (43, 212, 0), (0, 255, 0), (0, 213, 42), (0, 182, 73)),
    ((255, 0, 0), (255, 0, 0), (255, 0, 0), (212, 42, 0), (182, 73, 0), (159, 96, 0), (142, 113, 0), (128, 128, 0), (113, 142, 0), (96, 159, 0), (73, 182, 0), (43, 212, 0)),
    ((159, 0, 96), (159, 0, 96), (159, 0, 96), (182, 0, 73), (212, 0, 43), (255, 0, 0), (212, 42, 0), (182, 73, 0), (159, 96, 0), (142, 113, 0), (128, 128, 0), (113, 142, 0)),
    ((113, 0, 142), (113, 0, 142), (113, 0, 142), (128, 0, 128), (142, 0, 113), (159, 0, 96), (182, 0, 73), (212, 0, 43), (255, 0, 0), (212, 42, 0), (182, 73, 0), (159, 96, 0)),
    ((42, 0, 213), (42, 0, 213), (42, 0, 213), (73, 0, 182), (96, 0, 159), (113, 0, 142), (128, 0, 128), (142, 0, 113), (159, 0, 96), (182, 0, 73), (212, 0, 43), (255, 0, 0)),
    ((0, 73, 182), (0, 73, 182), (0, 73, 182), (0, 43, 212), (0, 0, 255), (42, 0, 213), (73, 0, 182), (96, 0, 159), (113, 0, 142), (128, 0, 128), (142, 0, 113), (159, 0, 96)),
)
