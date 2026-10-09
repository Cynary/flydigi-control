import ctypes as C
import unittest
from unittest.mock import Mock, patch
from flydigi_control.navigation import GamepadNavigation


class HotplugTests(unittest.TestCase):
    def test_connect_and_disconnect_after_initial_empty_discovery(self):
        nav = GamepadNavigation.__new__(GamepadNavigation)
        nav.lib = Mock()
        nav.devices, nav.previous = {}, set()
        nav.next_repeat = nav.next_discovery = 0
        visible, pending = [], []
        def pump():
            visible[:] = pending
        def ids(count):
            count._obj.value = len(visible)
            return (C.c_uint32 * len(visible))(*visible)
        nav.lib.SDL_PumpEvents.side_effect = pump
        nav.lib.SDL_GetJoysticks.side_effect = ids
        nav.lib.SDL_OpenJoystick.side_effect = lambda ident: ident + 100
        nav.lib.SDL_GetJoystickHat.return_value = 0
        nav.lib.SDL_GetJoystickAxis.return_value = 0
        nav.lib.SDL_GetJoystickButton.side_effect = lambda handle, button: button == 0
        with patch('time.monotonic', side_effect=[0, 1.1, 2.2, 3.3]):
            self.assertEqual(nav.poll(), [])
            pending[:] = [7]
            self.assertEqual(nav.poll(), ['accept'])
            pending.clear()
            self.assertEqual(nav.poll(), [])
            nav.lib.SDL_CloseJoystick.assert_called_once_with(107)
            pending[:] = [8]
            self.assertEqual(nav.poll(), ['accept'])
        self.assertEqual(nav.devices, {8: 108})
