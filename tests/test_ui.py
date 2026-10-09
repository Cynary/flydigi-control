import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import patch
try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication
    from flydigi_control.ui import Window, ApplyColor
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False


@unittest.skipUnless(QT_AVAILABLE, 'PySide6 not installed')
class UITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.discovery = patch('flydigi_control.ui.discover', return_value=[])
        self.discovery.start()
        self.nav = patch('flydigi_control.ui.GamepadNavigation')
        self.nav.start()
        self.window = Window()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.app.processEvents()
        self.discovery.stop()
        self.nav.stop()

    def press(self, key):
        self.window.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier))

    def test_hotplug_processing_continues_without_dispatch_when_unfocused(self):
        self.window.navigation.devices = {}
        self.window.navigation.poll.return_value = ['accept']
        with patch.object(self.window, 'isActiveWindow', return_value=False), \
             patch.object(self.window, 'keyPressEvent') as dispatch:
            self.window.poll_navigation()
            self.window.navigation.poll.assert_called_once()
            dispatch.assert_not_called()

    def test_no_device_disables_writes(self):
        for button in (self.window.apply, self.window.off, self.window.turbo, self.window.hotkeys, self.window.native):
            self.assertFalse(button.isEnabled())
        for button in self.window.motor_panel.buttons:
            self.assertFalse(button.isEnabled())

    def test_motor_selection_keeps_four_levels_independent(self):
        panel = self.window.motor_panel
        for slider, level in zip(panel.sliders, (20, 40, 60, 80)):
            slider.setValue(level)
        requested = []
        panel.requested.connect(requested.append)
        for side in range(4):
            panel.request(side)
        panel.request(None)
        self.assertEqual(requested, [(51,0,0,0), (0,102,0,0),
                                     (0,0,153,0), (0,0,0,204), (51,102,153,204)])

    def test_curve_preview_has_no_writes_and_rejects_unvalidated_negative_save(self):
        panel = self.window.curve_panel
        panel.set_available(True)
        panel.kind.setCurrentIndex(1)
        self.assertEqual(panel.curve().point1,(64,96))
        self.assertTrue(panel.save.isEnabled())
        panel.sliders[0].setValue(-10)
        self.assertEqual(panel.kind.currentIndex(),3)
        self.assertFalse(panel.save.isEnabled())
        self.assertIn('preview-only',panel.note.text())
        self.assertEqual(len(panel.plot.proposed),9)
        self.assertIsNone(self.window.worker)
        panel.kind.setCurrentIndex(0)
        self.assertEqual(panel.curve().center,0)
        self.assertTrue(panel.save.isEnabled())

    def test_curve_editor_fits_1080p_and_is_controller_navigable(self):
        self.window.pages.setCurrentIndex(6)
        self.app.processEvents()
        self.assertLessEqual(self.window.minimumSizeHint().height(),1080)
        panel = self.window.curve_panel
        panel.sliders[2].setFocus()
        initial = panel.sliders[2].value()
        self.press(Qt.Key.Key_Right)
        self.assertEqual(panel.sliders[2].value(),initial+1)
        self.assertEqual(panel.kind.currentIndex(),3)
        panel.back.setFocus()
        self.press(Qt.Key.Key_Return)
        self.assertEqual(self.window.pages.currentIndex(),3)

    def test_profile_fields_load_without_writes_and_reject_invalid_travel(self):
        from test_profile_controls import profile
        panel=self.window.trigger_panel
        panel.set_available(True)
        panel.load(dict(mapping=profile(),profile=0))
        self.assertEqual(panel.values()['maximum'],45)
        self.assertTrue(panel.save.isEnabled())
        panel.fields['start'].setValue(255)
        self.assertFalse(panel.save.isEnabled())
        self.assertIsNone(self.window.worker)
        panel.side.setCurrentIndex(1)
        self.assertTrue(panel.save.isEnabled())
        self.assertEqual(panel.values()['start'],0)

    def test_unknown_saved_profile_value_is_not_clamped_and_saved(self):
        from test_profile_controls import profile
        value=bytearray(profile());value[149]=150
        panel=self.window.grip_panel
        panel.set_available(True)
        panel.load(dict(mapping=bytes(value),profile=0))
        self.assertFalse(panel.save.isEnabled())
        self.assertIn('Unknown saved strength',panel.details.text())
        panel.clear()
        self.assertIsNone(panel.mapping)

    def test_trigger_page_does_not_clip_motor_fields(self):
        from test_profile_controls import profile
        panel=self.window.trigger_panel
        self.window.pages.setCurrentIndex(7)
        panel.load(dict(mapping=profile(),profile=0))
        for _ in range(3):self.app.processEvents()
        last=panel.fields['strength']
        self.assertLess(last.mapTo(panel,last.rect().bottomLeft()).y(),panel.details.y())
        self.assertLessEqual(self.window.minimumSizeHint().height(),1080)

    def test_motor_stop_remains_available_while_settings_are_locked(self):
        from flydigi_control.motor_ui import MotorTest
        self.window.devices = [dict(path='/dev/test', remote_wake_advertised=False)]
        worker = MotorTest('/dev/test', (0,0,0,0))
        self.window.worker = worker
        self.window.show_device()
        self.assertFalse(self.window.apply.isEnabled())
        self.assertTrue(self.window.motor_panel.stop.isEnabled())
        self.assertFalse(self.window.motor_panel.all.isEnabled())
        self.window.motor_panel.stop.click()
        self.assertTrue(worker.cancel.is_set())
        self.window.worker = None

    def test_first_receiver_is_selected(self):
        device = {'path': '/dev/hidraw99', 'name': 'Vader 5 Pro',
                  'remote_wake_advertised': False}
        with patch('flydigi_control.ui.discover', return_value=[device]):
            self.window.refresh()
        self.assertEqual(self.window.device_box.currentData(), '/dev/hidraw99')
        self.assertTrue(self.window.read_settings.isEnabled())

    def test_navigation_stays_on_visible_page(self):
        self.window.settings_tab.setFocus()
        self.press(Qt.Key.Key_Return)
        self.assertEqual(self.window.pages.currentIndex(), 1)
        self.press(Qt.Key.Key_Right)
        self.assertIs(QApplication.focusWidget(), self.window.test_tab)
        self.window.lighting_tab.setFocus()
        self.press(Qt.Key.Key_Return)
        self.assertEqual(self.window.pages.currentIndex(), 0)
        self.window.brightness.setFocus()
        self.press(Qt.Key.Key_Left)
        self.assertEqual(self.window.brightness.value(), 25)

    def test_button_test_cannot_activate_settings_or_exit(self):
        self.window.testing = True
        self.window.settings_tab.setFocus()
        before = self.window.pages.currentIndex()
        self.press(Qt.Key.Key_Return)
        self.press(Qt.Key.Key_Escape)
        self.assertEqual(self.window.pages.currentIndex(), before)
        self.assertTrue(self.window.isVisible())
        self.window.testing = False

    def test_spatial_navigation_follows_color_grid(self):
        self.window.color_buttons[0].setFocus()
        self.press(Qt.Key.Key_Right)
        self.assertIs(QApplication.focusWidget(), self.window.color_buttons[1])
        self.press(Qt.Key.Key_Down)
        self.assertIs(QApplication.focusWidget(), self.window.color_buttons[4])

    def test_multicolor_editing_and_rgb_are_independent(self):
        self.window.effect.setCurrentIndex(2)
        self.assertEqual(len(self.window.colors), 3)
        self.window.color_slot.setCurrentIndex(1)
        self.window.rgb_sliders[0].setValue(237)
        self.assertEqual(self.window.colors[1][0],237)
        self.assertEqual(self.window.colors[0],(0,0,100))
        self.window.brightness.setValue(7)
        self.assertEqual(self.window.colors[1][0],237)
        self.window.effect.setCurrentIndex(0)
        self.assertEqual(len(self.window.colors),1)
        self.assertFalse(self.window.add_color.isEnabled())

    def test_device_change_clears_feature_state(self):
        self.window.feature_values = {'turbo': {'supported': True, 'enabled': True}}
        self.window.device_changed()
        self.assertEqual(self.window.feature_values, {})
        self.assertIsNone(self.window.stick_values)
        self.assertFalse(self.window.stick_apply.isEnabled())

    def test_stick_page_displays_each_stick_without_copying_settings(self):
        self.window.pages.setCurrentIndex(3)
        self.window.set_stick_values({'profile': 2, 'mapping': b'example',
            'sticks': [{'shape': 0, 'center': 2, 'edge': 4}, {'shape': 1, 'center': 5, 'edge': 6}]})
        self.assertEqual(self.window.stick_shape.currentIndex(), 0)
        self.window.stick_side.setCurrentIndex(1)
        self.assertEqual(self.window.stick_shape.currentIndex(), 1)
        self.assertIn('Center: 5', self.window.stick_summary.text())

    def test_apply_uses_guarded_save_and_reports_failure(self):
        worker = ApplyColor('/dev/hidraw99', 5, [(255, 0, 255)], 30, 15)
        results = []
        worker.result.connect(lambda ok, message: results.append((ok, message)))
        with patch('flydigi_control.ui.ConfigurationDevice') as device, \
             patch('flydigi_control.ui.apply_lighting') as apply:
            worker.run()
            self.assertIs(apply.call_args.args[0], device.return_value.__enter__.return_value)
            self.assertTrue(results[-1][0])
            apply.side_effect = RuntimeError('Save not confirmed')
            worker.run()
            self.assertEqual(results[-1], (False, 'Save not confirmed'))


if __name__ == '__main__':
    unittest.main()
