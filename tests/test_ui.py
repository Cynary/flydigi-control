import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import patch
try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication
    from flydigi_control.ui import Window
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

    def test_no_device_disables_writes(self):
        for button in (self.window.apply, self.window.off, self.window.turbo, self.window.hotkeys, self.window.native):
            self.assertFalse(button.isEnabled())

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
        self.press(Qt.Key.Key_Down)
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

    def test_device_change_clears_feature_state(self):
        self.window.feature_values = {'turbo': {'supported': True, 'enabled': True}}
        self.window.device_changed()
        self.assertEqual(self.window.feature_values, {})


if __name__ == '__main__':
    unittest.main()
