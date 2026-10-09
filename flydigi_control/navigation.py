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
            'SDL_IsGamepad': ([C.c_uint32], C.c_bool),
            'SDL_GetGamepadNameForID': ([C.c_uint32], C.c_char_p),
            'SDL_OpenGamepad': ([C.c_uint32], C.c_void_p),
            'SDL_CloseGamepad': ([C.c_void_p], None),
            'SDL_GetGamepadAxis': ([C.c_void_p, C.c_int], C.c_int16),
            'SDL_GetGamepadButton': ([C.c_void_p, C.c_int], C.c_bool),
            'SDL_QuitSubSystem': ([C.c_uint32], None),
        }
        for name, (args, result) in definitions.items():
            function = getattr(self.lib, name)
            function.argtypes, function.restype = args, result
        # Qt owns process/window lifecycle; do not turn SIGTERM into a discarded
        # SDL event when pumping the joystick subsystem.
        self.lib.SDL_SetHint(b'SDL_NO_SIGNAL_HANDLERS', b'1')
        self.lib.SDL_SetHint(b'SDL_JOYSTICK_HIDAPI', b'0')
        if not self.lib.SDL_Init(0x200):
            raise RuntimeError('SDL joystick initialization failed')
        self.devices = {}
        self.output_id = None
        self.output_handle = None
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
            if self.output_id is not None and self.output_id not in current:
                self.select_output(None)
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

    def mapped_devices(self):
        """Only OS devices with a known standard SDL gamepad mapping."""
        result=[]
        for identifier in sorted(self.devices):
            if self.lib.SDL_IsGamepad(identifier):
                name=self.lib.SDL_GetGamepadNameForID(identifier)
                result.append((identifier,name.decode('utf-8','replace') if name else 'Unnamed gamepad'))
        return result

    def select_output(self, identifier):
        if identifier==self.output_id:return
        if self.output_handle:
            self.lib.SDL_CloseGamepad(self.output_handle)
        self.output_id,self.output_handle=None,None
        if identifier is not None:
            if identifier not in self.devices or not self.lib.SDL_IsGamepad(identifier):
                raise ValueError('Select a connected standard gamepad')
            handle=self.lib.SDL_OpenGamepad(identifier)
            if not handle:raise RuntimeError('Could not open the selected OS gamepad')
            self.output_id,self.output_handle=identifier,handle

    def output_snapshot(self):
        if not self.output_handle:return None
        from .diagnostics import normalize_axis
        handle=self.output_handle
        axes=[self.lib.SDL_GetGamepadAxis(handle,i) for i in range(6)]
        names=('A','B','X','Y','View','Home','Menu','L3','R3','LB','RB',
               'Up','Down','Left','Right','Misc 1','Right paddle 1','Left paddle 1',
               'Right paddle 2','Left paddle 2','Touchpad','Misc 2','Misc 3','Misc 4','Misc 5','Misc 6')
        return {'id':self.output_id,
                'sticks':[(normalize_axis(axes[0]),-normalize_axis(axes[1])),
                          (normalize_axis(axes[2]),-normalize_axis(axes[3]))],
                'triggers':[max(0,value)/32767 for value in axes[4:]],
                'buttons':[name for i,name in enumerate(names) if self.lib.SDL_GetGamepadButton(handle,i)]}

    def close(self):
        self.select_output(None)
        for handle in self.devices.values():
            self.lib.SDL_CloseJoystick(handle)
        self.devices.clear()
        self.lib.SDL_QuitSubSystem(0x200)
