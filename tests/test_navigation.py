import ctypes as C
import unittest
from unittest.mock import Mock, patch
from flydigi_control.navigation import GamepadNavigation


class HotplugTests(unittest.TestCase):
    def test_connect_and_disconnect_after_initial_empty_discovery(self):
        nav = GamepadNavigation.__new__(GamepadNavigation)
        nav.lib = Mock()
        nav.devices, nav.previous = {}, set()
        nav.output_id=nav.output_handle=None
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

    def navigation(self):
        nav=GamepadNavigation.__new__(GamepadNavigation)
        nav.lib=Mock();nav.devices={7:107,8:108};nav.output_id=nav.output_handle=None
        nav.lib.SDL_IsGamepad.side_effect=lambda ident:ident==7
        nav.lib.SDL_GetGamepadNameForID.return_value=b'Steam Virtual Gamepad'
        nav.lib.SDL_OpenGamepad.return_value=207
        return nav

    def test_output_selection_requires_explicit_known_gamepad(self):
        nav=self.navigation()
        self.assertEqual(nav.mapped_devices(),[(7,'Steam Virtual Gamepad')])
        self.assertIsNone(nav.output_snapshot())
        nav.lib.SDL_OpenGamepad.assert_not_called()
        with self.assertRaises(ValueError):nav.select_output(8)
        with self.assertRaises(ValueError):nav.select_output(99)
        nav.select_output(7);nav.select_output(7)
        nav.lib.SDL_OpenGamepad.assert_called_once_with(7)
        nav.select_output(None);nav.lib.SDL_CloseGamepad.assert_called_once_with(207)
        self.assertIsNone(nav.output_snapshot())

    def test_output_uses_standard_axes_and_buttons_without_raw_axis_assumptions(self):
        nav=self.navigation();nav.select_output(7)
        axes=[-32768,-32768,32767,32767,0,32767]
        nav.lib.SDL_GetGamepadAxis.side_effect=lambda handle,axis:axes[axis]
        nav.lib.SDL_GetGamepadButton.side_effect=lambda handle,button:button in (0,4,19)
        value=nav.output_snapshot()
        self.assertEqual(value['id'],7)
        self.assertEqual(value['sticks'],[(-1,1),(1,-1)])
        self.assertEqual(value['triggers'],[0,1])
        self.assertEqual(value['buttons'],['A','View','Left paddle 2'])

    def test_output_disconnect_closes_handle_and_does_not_select_other_device(self):
        nav=self.navigation();nav.select_output(7)
        nav.previous=set();nav.next_repeat=nav.next_discovery=0
        def ids(count):
            count._obj.value=1
            return (C.c_uint32*1)(8)
        nav.lib.SDL_GetJoysticks.side_effect=ids
        nav.lib.SDL_GetJoystickHat.return_value=0
        nav.lib.SDL_GetJoystickAxis.return_value=0
        nav.lib.SDL_GetJoystickButton.return_value=False
        nav.poll()
        self.assertIsNone(nav.output_snapshot())
        nav.lib.SDL_CloseGamepad.assert_called_once_with(207)
        nav.lib.SDL_OpenGamepad.assert_called_once_with(7)
