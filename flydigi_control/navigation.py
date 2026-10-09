"""Gamepad navigation through SDL's existing evdev devices, without HID writes."""
import ctypes as C
import ctypes.util
import time


class GamepadNavigation:
    def __init__(self):
        self.lib = C.CDLL(ctypes.util.find_library('SDL3') or 'libSDL3.so.0')
        definitions = {
            'SDL_SetHint': ([C.c_char_p, C.c_char_p], C.c_bool),
            'SDL_Init': ([C.c_uint32], C.c_bool),
            'SDL_GetJoysticks': ([C.POINTER(C.c_int)], C.POINTER(C.c_uint32)),
            'SDL_free': ([C.c_void_p], None),
            'SDL_OpenJoystick': ([C.c_uint32], C.c_void_p),
            'SDL_CloseJoystick': ([C.c_void_p], None),
            'SDL_UpdateJoysticks': ([], None),
            'SDL_PumpEvents': ([], None),
            'SDL_FlushEvents': ([C.c_uint32, C.c_uint32], None),
            'SDL_GetJoystickButton': ([C.c_void_p, C.c_int], C.c_bool),
            'SDL_GetJoystickHat': ([C.c_void_p, C.c_int], C.c_uint8),
            'SDL_GetJoystickAxis': ([C.c_void_p, C.c_int], C.c_int16),
            'SDL_QuitSubSystem': ([C.c_uint32], None),
        }
        for name, (args, result) in definitions.items():
            function = getattr(self.lib, name)
            function.argtypes, function.restype = args, result
        self.lib.SDL_SetHint(b'SDL_JOYSTICK_HIDAPI', b'0')
        if not self.lib.SDL_Init(0x200):
            raise RuntimeError('SDL joystick initialization failed')
        self.devices = {}
        self.previous = set()
        self.next_repeat = 0
        self.next_discovery = 0

    def poll(self):
        # udev hotplug processing runs in SDL's event pump, not UpdateJoysticks.
        # Qt owns the UI loop, so pump SDL explicitly on this main-thread timer.
        self.lib.SDL_PumpEvents()
        self.lib.SDL_FlushEvents(0, 0xffff)
        now = time.monotonic()
        if now >= self.next_discovery:
            count = C.c_int()
            ids = self.lib.SDL_GetJoysticks(C.byref(count))
            current = {ids[i] for i in range(count.value)} if ids else set()
            self.lib.SDL_free(ids)
            for identifier in set(self.devices) - current:
                self.lib.SDL_CloseJoystick(self.devices.pop(identifier))
            for identifier in current - self.devices.keys():
                handle = self.lib.SDL_OpenJoystick(identifier)
                if handle:
                    self.devices[identifier] = handle
            self.next_discovery = now + 1
        self.lib.SDL_UpdateJoysticks()
        pressed = set()
        for handle in self.devices.values():
            hat = self.lib.SDL_GetJoystickHat(handle, 0)
            for mask, name in ((1, 'up'), (2, 'right'), (4, 'down'), (8, 'left')):
                if hat & mask:
                    pressed.add(name)
            for axis, low, high in ((0, 'left', 'right'), (1, 'up', 'down')):
                value = self.lib.SDL_GetJoystickAxis(handle, axis)
                if abs(value) > 18000:
                    pressed.add(low if value < 0 else high)
            for button, name in ((0, 'accept'), (1, 'back')):
                if self.lib.SDL_GetJoystickButton(handle, button):
                    pressed.add(name)
        edges = pressed - self.previous
        if pressed != self.previous:
            self.next_repeat = now + 0.4
        elif pressed and now >= self.next_repeat:
            edges = pressed & {'up', 'down', 'left', 'right'}
            self.next_repeat = now + 0.12
        self.previous = pressed
        return sorted(edges)

    def close(self):
        for handle in self.devices.values():
            self.lib.SDL_CloseJoystick(handle)
        self.devices.clear()
        self.lib.SDL_QuitSubSystem(0x200)
